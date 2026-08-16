"""Cumhurbaşkanlığı Adaptörü Testleri (S1.4 · Spec v3.4 §5).

Cumhurbaşkanlığı kararnameleri ve resmi basın açıklamalarının
ayrıştırılması, hata yönetimi ve metadata testleri.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from politikdesk.ingestion.adapters.sayistay import (
    CumhurbaskanligiAdapter,
    classify_tccb_item,
)

BASE = "https://www.tccb.gov.tr"

CB_HTML = f"""
<html><body>
  <div class="press-releases">
    <a href="/basin-aciklamalari/bazi-kamu-kurumlarina-yonetici-atama-kararnamesi">
       Bazı Kamu Kurum ve Kuruluşlarına İlişkin Atama Kararnamesi Yayımlandı
    </a>
    <a href="{BASE}/basin-aciklamalari/milli-egitim-ve-universite-yonetmelikleri">
       Milli Eğitim ve Üniversite Kadrolarına Dair Kararname Yayımlandı
    </a>
    <a href="{BASE}/basin-aciklamalari/cumhurbaskani-nato-zirvesi-ikili-gorusme">
       Cumhurbaşkanı NATO Liderler Zirvesi Kapsamında İkili Görüşmeler Gerçekleştirdi
    </a>
    <a href="{BASE}/basin-aciklamalari/kabine-toplantisi-sonrasi-ulusa-seslenis">
       Kabine Toplantısı Sonrası Ulusa Sesleniş ve Değerlendirme Açıklaması
    </a>
    <a href="/iletisim">İletişim</a>
  </div>
</body></html>
"""


@dataclass
class _FakeResponse:
    text: str


@dataclass
class _FakeHttp:
    body: str = CB_HTML
    calls: list[str] = field(default_factory=list)
    fail: bool = False

    def get(
        self, url: str, *, headers: dict[str, str] | None = None, source_slug: str = ""
    ) -> _FakeResponse:
        self.calls.append(url)
        if self.fail:
            raise TimeoutError("Cumhurbaşkanlığı bağlantı hatası")
        return _FakeResponse(self.body)

    def close(self) -> None:
        pass


def test_cumhurbaskanligi_extracts_statements() -> None:
    adapter = CumhurbaskanligiAdapter(slug="cb-kararname", base_url=BASE, http=_FakeHttp())  # type: ignore[arg-type]
    items = adapter.fetch()

    assert len(items) == 4
    urls = [i.url for i in items]
    assert f"{BASE}/basin-aciklamalari/bazi-kamu-kurumlarina-yonetici-atama-kararnamesi" in urls
    assert f"{BASE}/basin-aciklamalari/milli-egitim-ve-universite-yonetmelikleri" in urls
    assert f"{BASE}/basin-aciklamalari/cumhurbaskani-nato-zirvesi-ikili-gorusme" in urls
    assert f"{BASE}/basin-aciklamalari/kabine-toplantisi-sonrasi-ulusa-seslenis" in urls
    assert f"{BASE}/iletisim" not in urls


def test_cumhurbaskanligi_categorization_and_provenance() -> None:
    adapter = CumhurbaskanligiAdapter(slug="cb-kararname", base_url=BASE, http=_FakeHttp())  # type: ignore[arg-type]
    items = adapter.fetch()

    # 1. Atama
    assert items[0].extra["category"] == "atama_ve_kadro"
    assert items[0].extra["vertical"] == "legislation"

    # 2. Kararname / Kadro
    assert items[1].extra["category"] == "atama_ve_kadro"

    # 3. Diplomasi (NATO zirvesi)
    assert items[2].extra["category"] == "diplomasi"
    assert items[2].extra["vertical"] == "legislation"

    # 4. Genel basın açıklaması (Kabine / Ulusa Sesleniş)
    assert items[3].extra["category"] == "basin_aciklamasi"
    assert items[3].extra["vertical"] == "legislation"


def test_classify_tccb_item_unit_cases() -> None:
    """TCCB sınıflandırıcı farklı başlıkları doğru kategoriye eşler."""
    assert classify_tccb_item("Bakan Yardımcısı Atama Kararları")[0] == "atama_ve_kadro"
    assert classify_tccb_item("Devlet Memurları Disiplin Yönetmeliği ve Kararnamesi")[0] == "kararname"
    assert classify_tccb_item("Cumhurbaşkanı ve Fransa Devlet Başkanı İkili Görüşmesi")[0] == "diplomasi"
    assert classify_tccb_item("Haftalık Basın Bilgilendirme Toplantısı Notları")[0] == "basin_aciklamasi"


def test_cumhurbaskanligi_empty_and_malformed() -> None:
    adapter_empty = CumhurbaskanligiAdapter(
        slug="cb-kararname", base_url=BASE, http=_FakeHttp(body="")
    )  # type: ignore[arg-type]
    assert adapter_empty.fetch() == []


def test_cumhurbaskanligi_network_failure_recorded() -> None:
    adapter = CumhurbaskanligiAdapter(slug="cb-kararname", base_url=BASE, http=_FakeHttp(fail=True))  # type: ignore[arg-type]
    items = adapter.fetch()
    assert items == []
    failures = adapter.drain_failures()
    assert len(failures) >= 1
    assert "TimeoutError" in failures[0]
