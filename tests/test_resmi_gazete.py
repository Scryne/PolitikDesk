"""F5-20 — Resmî Gazete günlük fihristi (B-44'ün kapanışı).

Kaynak üç faz boyunca "ağ/IP düzeyinde engelli" sayıldı. İki ayrı arıza
üst üste binmişti ve ikisi de yanlış teşhis edilmişti:

  1. Geliştirme makinesindeki GoodbyeDPI, TLS ClientHello'yu parçalıyordu
     (WinDivert sürücü katmanında çalıştığı için Docker dahil TÜM trafiği
     etkiliyordu — "konteynerden de olmuyor" bulgusu bu yüzden yanıltıcıydı).
  2. Altından çıkan gerçek kod arızası: sunucu ARA SERTİFİKAYI göndermiyor.

Üstelik `/rss` hiçbir zaman RSS değildi: HTML döndürüyor, sıfır `<item>`.

Ağ çağrısı yapılmaz; fihrist HTML'i sahte istemciden gelir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from politikdesk.ingestion.adapters.resmi_gazete import (
    ResmiGazeteAdapter,
    clean_item_title,
)

BASE = "https://www.resmigazete.gov.tr"

FIHRIST = f"""
<html><body>
  <a href="{BASE}/eskiler/2026/08/20260813.pdf">PDF Görüntüle</a>
  <a href="{BASE}/eskiler/2026/08/20260813-0.pdf">
     –– Bazı Mallara Uygulanan Özel Tüketim Vergisi Tutarlarının Yeniden Belirlenmesi
  </a>
  <a href="{BASE}/eskiler/2026/08/20260813-1.htm">
     –– Ömrünü Tamamlamış Lastiklerin Kontrolü Yönetmeliğinde Değişiklik
  </a>
  <a href="{BASE}/eskiler/2026/08/20260813-2.htm">
     –– Boğaziçi Üniversitesi Lisans Eğitim-Öğretim Yönetmeliği
  </a>
  <a href="{BASE}/fihrist#nav-contact">Mükerrer Arşivi</a>
  <a href="{BASE}/">T.C. CUMHURBAŞKANLIĞI RESMÎ GAZETE</a>
  <a href="{BASE}/ilanlar">İlanlar</a>
</body></html>
"""


@dataclass
class _FakeResponse:
    text: str


@dataclass
class _FakeHttp:
    body: str = FIHRIST
    calls: list[str] = field(default_factory=list)
    fail: bool = False

    def get(self, url: str, *, headers: dict[str, str] | None = None,
            source_slug: str = "") -> _FakeResponse:
        self.calls.append(url)
        if self.fail:
            raise TimeoutError("okuma zaman asimi")
        return _FakeResponse(self.body)

    def close(self) -> None:  # pragma: no cover
        pass


def _adapter(**kw):  # noqa: ANN003, ANN202
    kw.setdefault("http", _FakeHttp())
    kw.setdefault("days_back", 0)
    return ResmiGazeteAdapter("resmi-gazete", base_url=BASE, **kw)


# --------------------------------------------------------------- ayıklama
def test_navigation_links_are_not_items() -> None:
    """GEZİNTİ bağlantısı kalem değildir.

    `GenericHtmlAdapter` bu sayfada tam olarak bunu yapıyordu: üç öğe
    döndürüyordu ve üçü de "Mükerrer Arşivi", "Resmî Gazete Tarihçesi"
    gibi menü bağlantılarıydı. Kalem adresinin biçimi bu yüzden açıkça
    aranır.
    """
    titles = [i.title for i in _adapter().fetch()]

    assert not any("Mükerrer Arşivi" in t for t in titles)
    assert not any("RESMÎ GAZETE" in t.upper() for t in titles)


def test_full_issue_pdf_is_not_an_item() -> None:
    """Sıra numarasız PDF sayının TAMAMIDIR, tek bir kalem değil."""
    urls = [i.url for i in _adapter().fetch()]
    assert f"{BASE}/eskiler/2026/08/20260813.pdf" not in urls


def test_items_are_extracted_with_clean_titles() -> None:
    items = _adapter().fetch()
    assert len(items) == 3
    assert items[0].title.startswith("Bazı Mallara Uygulanan Özel Tüketim")
    # "–– " listeleme işaretidir, başlığın parçası değil.
    assert not any(i.title.startswith("–") for i in items)


def test_keyword_filter_keeps_only_relevant_items() -> None:
    """Konu filtresi ZORUNLU: RG günde onlarca alakasız kalem yayımlar.

    Filtresiz toplama `articles` tablosunu üniversite yönetmelikleriyle
    doldurur ve embedding maliyetini boşa harcar.
    """
    items = _adapter(keyword_filter=["vergi", "ÖTV"]).fetch()

    assert len(items) == 1
    assert "Özel Tüketim Vergisi" in items[0].title


def test_published_at_is_the_gazette_date() -> None:
    item = _adapter(keyword_filter=["vergi"]).fetch()[0]
    assert item.published_at is not None
    assert item.published_at.tzinfo is not None


def test_days_back_queries_previous_day_too() -> None:
    """Gazete sabaha karşı yayımlanır; "bugün" turun saatinde boş olabilir."""
    http = _FakeHttp()
    ResmiGazeteAdapter("resmi-gazete", base_url=BASE, http=http, days_back=1).fetch()
    assert len(http.calls) == 2


def test_same_item_is_not_returned_twice_across_days() -> None:
    """İki gün aynı HTML'i döndürse bile kalem TEK kez üretilir."""
    items = ResmiGazeteAdapter(
        "resmi-gazete", base_url=BASE, http=_FakeHttp(), days_back=1
    ).fetch()
    assert len(items) == len({i.url for i in items})


def test_failure_is_recorded_not_swallowed() -> None:
    """Yutulan istisna KAYDEDİLİR; boş tur "başarılı" görünmez (B-80)."""
    adapter = ResmiGazeteAdapter(
        "resmi-gazete", base_url=BASE, http=_FakeHttp(fail=True), days_back=0
    )

    assert adapter.fetch() == []
    assert adapter.drain_failures()


def test_clean_item_title() -> None:
    assert clean_item_title("–– Bir Karar") == "Bir Karar"
    assert clean_item_title("<b>Kalın</b> başlık") == "Kalın başlık"
    assert clean_item_title("  bo&#351;luk  ") == "bo&#351;luk".replace("&#351;", "ş")


# ------------------------------------------------------------ CA demeti
def test_ca_bundle_includes_the_missing_intermediate() -> None:
    """Eksik ara sertifika demete giriyor mu (F5-20).

    Sunucu `GeoTrust TLS RSA CA G1` halkasını göndermiyor. Tarayıcılar
    eksik halkayı AIA'dan indirir, Python indirmez — site tarayıcıda
    açılır, koddan açılmaz. Demet bu halkayı taşımazsa doğrulama düşer
    ve kaynak yine "erişilemez" görünür.

    ⚠️ Çözüm `verify=False` DEĞİLDİR: Tier 1 birincil kaynaktan
    okuduğumuzu söylerken karşı tarafı doğrulamamak kanıt zincirini
    çürütürdü.
    """
    from pathlib import Path

    from politikdesk.ingestion.http import CERTS_DIR, ca_bundle_path

    assert (CERTS_DIR / "geotrust-tls-rsa-ca-g1.pem").is_file()

    bundle = Path(ca_bundle_path()).read_text(encoding="ascii")
    extra = (CERTS_DIR / "geotrust-tls-rsa-ca-g1.pem").read_text(encoding="ascii")
    assert extra.strip() in bundle
    # certifi'nin kökleri de duruyor olmalı — demet onun YERİNE geçmez.
    assert bundle.count("BEGIN CERTIFICATE") > 100
