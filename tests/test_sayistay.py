"""Sayıştay Adaptörü Testleri (S1.3 · Spec v3.4 §5).

Sayıştay denetim raporları, kamu zararı bulguları ve duyuruların
ayrıştırılması, hata yönetimi ve metadata testleri.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from politikdesk.ingestion.adapters.sayistay import SayistayAdapter

BASE = "https://www.sayistay.gov.tr"

SAYISTAY_HTML = f"""
<html><body>
  <div class="reports">
    <a href="/pages/2025-yili-buyuksehir-belediyesi-denetim-raporu">
       2025 Yılı Büyükşehir Belediyesi Düzenlilik Denetim Raporu
    </a>
    <a href="{BASE}/pages/kamu-zarari-tespit-ve-tazmin-bulgulari">
       Kamu Zararı Tespit ve İhale Mevzuatı Denetim Bulguları
    </a>
    <div onclick="location.href='/duyuru/105-sayistay-genel-kurul-karari'">
       Sayıştay Duyurusu
    </div>
    <a href="/hakkimizda">Hakkımızda</a>
    <a href="/iletisim">İletişim</a>
  </div>
</body></html>
"""


@dataclass
class _FakeResponse:
    text: str


@dataclass
class _FakeHttp:
    body: str = SAYISTAY_HTML
    calls: list[str] = field(default_factory=list)
    fail: bool = False

    def get(
        self, url: str, *, headers: dict[str, str] | None = None, source_slug: str = ""
    ) -> _FakeResponse:
        self.calls.append(url)
        if self.fail:
            raise TimeoutError("Sayıştay bağlantı hatası")
        return _FakeResponse(self.body)

    def close(self) -> None:
        pass


def test_sayistay_extracts_reports_and_announcements() -> None:
    adapter = SayistayAdapter(slug="sayistay", base_url=BASE, http=_FakeHttp())  # type: ignore[arg-type]
    items = adapter.fetch()

    assert len(items) == 3
    urls = [i.url for i in items]
    assert f"{BASE}/pages/2025-yili-buyuksehir-belediyesi-denetim-raporu" in urls
    assert f"{BASE}/pages/kamu-zarari-tespit-ve-tazmin-bulgulari" in urls
    assert f"{BASE}/duyuru/105-sayistay-genel-kurul-karari" in urls


def test_sayistay_provenance_and_metadata() -> None:
    adapter = SayistayAdapter(slug="sayistay", base_url=BASE, http=_FakeHttp())  # type: ignore[arg-type]
    items = adapter.fetch()

    report_item = next(i for i in items if "Denetim" in i.title)
    assert report_item.source_slug == "sayistay"
    assert report_item.published_at is not None
    assert report_item.extra["category"] == "denetim_ve_yolsuzluk"
    assert report_item.extra["vertical"] == "legislation"


def test_sayistay_empty_and_malformed() -> None:
    adapter_empty = SayistayAdapter(slug="sayistay", base_url=BASE, http=_FakeHttp(body=""))  # type: ignore[arg-type]
    assert adapter_empty.fetch() == []

    adapter_malformed = SayistayAdapter(
        slug="sayistay", base_url=BASE, http=_FakeHttp(body="<<<invalid html")
    )  # type: ignore[arg-type]
    assert adapter_malformed.fetch() == []


def test_sayistay_network_failure_recorded() -> None:
    adapter = SayistayAdapter(slug="sayistay", base_url=BASE, http=_FakeHttp(fail=True))  # type: ignore[arg-type]
    items = adapter.fetch()
    assert items == []
    failures = adapter.drain_failures()
    assert len(failures) >= 1
    assert "TimeoutError" in failures[0]
