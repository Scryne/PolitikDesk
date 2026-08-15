"""Cumhurbaşkanlığı Adaptörü Testleri (S1.4 · Spec v3.4 §5).

Cumhurbaşkanlığı kararnameleri ve resmi basın açıklamalarının
ayrıştırılması, hata yönetimi ve metadata testleri.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from politikdesk.ingestion.adapters.sayistay import CumhurbaskanligiAdapter

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

    def get(self, url: str, *, headers: dict[str, str] | None = None, source_slug: str = "") -> _FakeResponse:
        self.calls.append(url)
        if self.fail:
            raise TimeoutError("Cumhurbaşkanlığı bağlantı hatası")
        return _FakeResponse(self.body)

    def close(self) -> None:
        pass


def test_cumhurbaskanligi_extracts_statements() -> None:
    adapter = CumhurbaskanligiAdapter(slug="cb-kararname", base_url=BASE, http=_FakeHttp())  # type: ignore[arg-type]
    items = adapter.fetch()

    assert len(items) == 2
    urls = [i.url for i in items]
    assert f"{BASE}/basin-aciklamalari/bazi-kamu-kurumlarina-yonetici-atama-kararnamesi" in urls
    assert f"{BASE}/basin-aciklamalari/milli-egitim-ve-universite-yonetmelikleri" in urls
    assert f"{BASE}/iletisim" not in urls


def test_cumhurbaskanligi_provenance_and_metadata() -> None:
    adapter = CumhurbaskanligiAdapter(slug="cb-kararname", base_url=BASE, http=_FakeHttp())  # type: ignore[arg-type]
    items = adapter.fetch()

    item = items[0]
    assert item.source_slug == "cb-kararname"
    assert item.published_at is not None
    assert item.extra["category"] == "atama_ve_kadro"
    assert item.extra["vertical"] == "legislation"


def test_cumhurbaskanligi_empty_and_malformed() -> None:
    adapter_empty = CumhurbaskanligiAdapter(slug="cb-kararname", base_url=BASE, http=_FakeHttp(body=""))  # type: ignore[arg-type]
    assert adapter_empty.fetch() == []


def test_cumhurbaskanligi_network_failure_recorded() -> None:
    adapter = CumhurbaskanligiAdapter(slug="cb-kararname", base_url=BASE, http=_FakeHttp(fail=True))  # type: ignore[arg-type]
    items = adapter.fetch()
    assert items == []
    failures = adapter.drain_failures()
    assert len(failures) >= 1
    assert "TimeoutError" in failures[0]
