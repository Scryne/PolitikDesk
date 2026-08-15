"""TBMM Adaptörü Testleri (S1.2 · Spec v3.4 §5, §8.3 R8).

TBMM kanun teklifleri ve tutanak sayfalarının ayrıştırılması,
hata yakalama, canonical URL ve provenance koruması.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from politikdesk.ingestion.adapters.tbmm import TbmmAdapter, clean_text

BASE = "https://www.tbmm.gov.tr"

TBMM_HTML = f"""
<html><body>
  <div class="content">
    <a href="/yasama/teklif/12345">
       Bazı Vergi Kanunları ile Diğer Bazı Kanunlarda Değişiklik Yapılmasına Dair Kanun Teklifi
    </a>
    <a href="{BASE}/yasama/teklif/67890">
       İş Sağlığı ve Güvenliği Kanununda Değişiklik Yapılması Hakkında Kanun Teklifi
    </a>
    <a href="/tutanak/28-donem-3-yasama-yili-102-birlesim">
       28. Dönem 3. Yasama Yılı 102. Birleşim Tutanağı
    </a>
    <a href="/anasayfa">Ana Sayfa</a>
    <a href="/iletisim">İletişim</a>
    <a href="/kisa">Kısa</a>
  </div>
</body></html>
"""


@dataclass
class _FakeResponse:
    text: str


@dataclass
class _FakeHttp:
    body: str = TBMM_HTML
    calls: list[str] = field(default_factory=list)
    fail: bool = False

    def get(self, url: str, *, headers: dict[str, str] | None = None, source_slug: str = "") -> _FakeResponse:
        self.calls.append(url)
        if self.fail:
            raise TimeoutError("TBMM bağlantı zaman aşımı")
        return _FakeResponse(self.body)

    def close(self) -> None:
        pass


def test_clean_text() -> None:
    assert clean_text("<b>Kalın</b> &nbsp; Başlık ") == "Kalın Başlık"
    assert clean_text("  Çoklu   \n  boşluklar  ") == "Çoklu boşluklar"


def test_tbmm_extracts_proposals_and_tutanaklar() -> None:
    adapter = TbmmAdapter(slug="tbmm", base_url=BASE, http=_FakeHttp())  # type: ignore[arg-type]
    items = adapter.fetch()

    assert len(items) == 3
    urls = [i.url for i in items]
    assert f"{BASE}/yasama/teklif/12345" in urls
    assert f"{BASE}/yasama/teklif/67890" in urls
    assert f"{BASE}/tutanak/28-donem-3-yasama-yili-102-birlesim" in urls

    # Navigation linkleri elenmeli
    assert f"{BASE}/anasayfa" not in urls
    assert f"{BASE}/iletisim" not in urls


def test_tbmm_provenance_and_metadata() -> None:
    adapter = TbmmAdapter(slug="tbmm", base_url=BASE, http=_FakeHttp())  # type: ignore[arg-type]
    items = adapter.fetch()

    proposal_item = next(i for i in items if "Vergi" in i.title)
    assert proposal_item.source_slug == "tbmm"
    assert proposal_item.published_at is not None
    assert proposal_item.extra["category"] == "kanun_teklifi"
    assert proposal_item.extra["vertical"] == "legislation"

    tutanak_item = next(i for i in items if "Tutanağı" in i.title)
    assert tutanak_item.extra["category"] == "genel_kurul_tutanak"
    assert tutanak_item.extra["vertical"] == "legislation"


def test_tbmm_keyword_filter() -> None:
    adapter = TbmmAdapter(
        slug="tbmm",
        base_url=BASE,
        http=_FakeHttp(),  # type: ignore[arg-type]
        keyword_filter=["vergi"],
    )
    items = adapter.fetch()
    assert len(items) == 1
    assert "Vergi" in items[0].title


def test_tbmm_empty_and_malformed_html() -> None:
    # Boş HTML
    adapter_empty = TbmmAdapter(slug="tbmm", base_url=BASE, http=_FakeHttp(body=""))  # type: ignore[arg-type]
    assert adapter_empty.fetch() == []

    # Bozuk HTML
    adapter_malformed = TbmmAdapter(slug="tbmm", base_url=BASE, http=_FakeHttp(body="<unclosed <div><a>Kopuk"))  # type: ignore[arg-type]
    assert adapter_malformed.fetch() == []


def test_tbmm_network_failure_recorded() -> None:
    adapter = TbmmAdapter(slug="tbmm", base_url=BASE, http=_FakeHttp(fail=True))  # type: ignore[arg-type]
    items = adapter.fetch()
    assert items == []
    failures = adapter.drain_failures()
    assert len(failures) >= 1
    assert "TimeoutError" in failures[0]
