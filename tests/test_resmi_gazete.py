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

    def get(
        self, url: str, *, headers: dict[str, str] | None = None, source_slug: str = ""
    ) -> _FakeResponse:
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
    items = ResmiGazeteAdapter("resmi-gazete", base_url=BASE, http=_FakeHttp(), days_back=1).fetch()
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


def test_http_retry_on_timeout(monkeypatch) -> None:
    """ReadTimeout durumunda exponential backoff ve sınırlı retry işletilir."""
    import httpx

    from politikdesk.ingestion.http import HttpClient

    attempts = 0

    def mock_request(self, method, url, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ReadTimeout("Sunucu yanit vermedi")
        return httpx.Response(200, text=FIHRIST, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.Client, "request", mock_request)

    client = HttpClient(timeout=5.0, max_retries=4, respect_robots=False)
    resp = client.get(f"{BASE}/fihrist?tarih=2026-08-13")
    assert resp.status_code == 200
    assert attempts == 3


def test_http_non_retryable_error(monkeypatch) -> None:
    """404 Not Found gibi kalıcı hatalarda retry yapılmaz, fail-closed fırlatılır."""
    import httpx
    import pytest

    from politikdesk.ingestion.http import HttpClient

    attempts = 0

    def mock_request(self, method, url, **kwargs):
        nonlocal attempts
        attempts += 1
        req = httpx.Request(method, url)
        return httpx.Response(404, request=req)

    monkeypatch.setattr(httpx.Client, "request", mock_request)

    client = HttpClient(timeout=5.0, max_retries=4, respect_robots=False)
    with pytest.raises(httpx.HTTPStatusError):
        client.get(f"{BASE}/fihrist?tarih=2026-08-13")

    assert attempts == 1  # 404 retry edilmez


def test_robots_txt_handling(monkeypatch) -> None:
    """robots.txt açıkça yasakladığında RobotsDisallowed fırlatılır."""
    import httpx
    import pytest

    from politikdesk.ingestion.http import HttpClient, RobotsDisallowed

    robots_content = "User-agent: *\nDisallow: /ozel/\n"

    def mock_get(self, url, **kwargs):
        req = httpx.Request("GET", url)
        if url.endswith("/robots.txt"):
            return httpx.Response(200, text=robots_content, request=req)
        return httpx.Response(200, text="OK", request=req)

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    client = HttpClient(timeout=5.0, respect_robots=True)
    with pytest.raises(RobotsDisallowed):
        client.get(f"{BASE}/ozel/gizli-sayfa")


# ==================================================================== FAZ 4 TESTS
def test_http_client_granular_timeout_construction() -> None:
    """F4: Granüler connect/read/write/pool timeout değerleri httpx.Timeout'a dönüştürülür."""
    import httpx

    from politikdesk.ingestion.http import HttpClient

    client = HttpClient(
        timeout=20.0,
        connect_timeout=5.0,
        read_timeout=10.0,
        write_timeout=4.0,
        pool_timeout=3.0,
    )
    t = client._client.timeout
    assert isinstance(t, httpx.Timeout)
    assert t.connect == 5.0
    assert t.read == 10.0
    assert t.write == 4.0
    assert t.pool == 3.0


def test_calculate_backoff_deterministic_and_jitter() -> None:
    """F4: calculate_backoff deterministik ve jitter seçeneklerinde beklenen aralıklarda kalır."""
    from politikdesk.ingestion.http import calculate_backoff

    # Jitter kapalıyken: deterministik 2^attempt
    assert calculate_backoff(0, jitter=False) == 1.0
    assert calculate_backoff(1, jitter=False) == 2.0
    assert calculate_backoff(2, jitter=False) == 4.0
    assert calculate_backoff(3, jitter=False) == 8.0
    assert calculate_backoff(10, jitter=False) == 30.0  # max_delay=30

    # Override (Retry-After) verildiğinde
    assert calculate_backoff(0, override=15.0) == 15.0
    assert calculate_backoff(0, override=60.0) == 60.0

    # Jitter açıkken: [0.5 * exp_delay, exp_delay] arasında
    for attempt in range(5):
        exp = min(1.0 * (2.0**attempt), 30.0)
        delay = calculate_backoff(attempt, jitter=True)
        assert 0.5 * exp <= delay <= exp


def test_resmi_gazete_partial_timeout_recovery(monkeypatch) -> None:
    """F4: Resmî Gazete bir gün için timeout alsa bile diğer günün verilerini başarıyla toplar."""
    from datetime import date

    import httpx

    from politikdesk.ingestion.adapters.resmi_gazete import ResmiGazeteAdapter

    today_str = date.today().isoformat()

    def mock_request(self, method, url, **kwargs):
        req = httpx.Request(method, url)
        if today_str in str(url):
            raise httpx.ReadTimeout("Gecici gov.tr sunucu takilmasi")
        return httpx.Response(200, text=FIHRIST, request=req)

    monkeypatch.setattr(httpx.Client, "request", mock_request)

    adapter = ResmiGazeteAdapter(
        slug="resmi-gazete",
        base_url=BASE,
        days_back=1,
    )
    items = adapter.fetch()

    # Dünkü fihristten 3 kalem başarıyla çekilmiş olmalı
    assert len(items) == 3
    # Bugünün timeout hatası FailureRecorder'a kaydedilmiş olmalı
    failures = adapter.drain_failures()
    assert len(failures) == 1
    assert "ReadTimeout" in failures[0]
    assert today_str in failures[0]


# ------------------------------------------- konu filtresi ≠ kaynak arızası
#
# 19 Ağustos 2026. Resmî Gazete günde onlarca kalem yayımlar ve çoğu gün
# hiçbiri vergi/gümrük konusunda değildir. Adaptör doğru davranıp 0 öğe
# döndürüyordu, ama boru hattı bunu KAYNAK ARIZASI sayıyordu.
#
# Ölçüldü: 7 günde 1358 turun 516'sı bu yüzden "hata"ydı; ardışık hata
# sayacı 758'e çıkmış ve kaynak kalıcı kırmızıya düşmüştü. Roadmap Faz
# 2.3'ün yasağı buydu: "Alarm yanlış pozitif üretmemeli."
#
# Yanlış alarmın asıl bedeli gürültü değil KÖRLÜK: kaynak zaten hep
# kırmızıysa, gerçekten bozulduğu gün hiçbir şey değişmez.


def test_topic_filter_emptying_the_round_is_not_a_source_failure() -> None:
    """Kalemler ayrıştırıldı ama hiçbiri konumuzla ilgili değil.

    `fetch()` boş döner (doğru), fakat ham sayaç kaynağın SAĞLIKLI
    olduğunu söyler — boru hattı turu arıza saymaz.
    """
    adapter = _adapter(keyword_filter=["bu-kelime-fihristte-yok"])

    assert adapter.fetch() == []
    assert adapter.drain_parsed() == 3, "Fihristten üç kalem ayrıştırılmalıydı."


def test_empty_index_is_still_a_source_failure() -> None:
    """Fihristten TEK kalem bile çıkmazsa bu gerçek bir arızadır.

    ⛔ B-42/B-43'ün koruduğu durum: uç 200 döner, gövde beklenen şey
    değildir, tur sessizce başarılı görünür. Bu koruma KALKMADI.
    """
    adapter = _adapter(http=_FakeHttp(body="<html><body>bos</body></html>"))

    assert adapter.fetch() == []
    assert adapter.drain_parsed() == 0


def test_parsed_counter_is_drained_between_rounds() -> None:
    """Sayaç turlar arasında taşınmaz.

    `drain_failures` ile aynı gerekçe: adaptör örnekleri yeniden
    kullanılabilir ve taşınan bir sayaç, bir sonraki turda kaynağı
    olduğundan sağlıklı gösterirdi.
    """
    adapter = _adapter(keyword_filter=["vergi"])

    adapter.fetch()
    assert adapter.drain_parsed() == 3
    assert adapter.drain_parsed() == 0, "Boşaltılan sayaç sıfırlanmadı."


def test_health_rule_uses_parsed_count_not_filtered_count() -> None:
    """`record_fetch` sözleşmesi: `items_parsed` üretkenliği belirler.

    Sözleşmenin kendisi burada ölçülür; veritabanına gitmeden, kuralın
    hangi girdilerle "üretken" dediği sabitlenir.
    """
    import inspect

    from politikdesk.ingestion import repository

    kaynak = inspect.getsource(repository.record_fetch)
    assert "items_parsed" in kaynak
    assert "uretken = items_fetched > 0 or (items_parsed or 0) > 0" in kaynak


def test_adapters_without_the_counter_keep_the_old_behaviour() -> None:
    """89 kaynağın 88'i konu filtresi kullanmıyor; onlar için değişiklik yok.

    Sayaç tutmayan bir adaptörde `drain_parsed` `None` döner ve
    `record_fetch` eski kuralın aynısını uygular.
    """
    from politikdesk.ingestion.adapters import base as adapter_base

    class _SayacsizAdaptor:
        slug = "sayacsiz"

        def fetch(self):  # noqa: ANN202
            return []

    assert adapter_base.drain_parsed(_SayacsizAdaptor()) is None
