"""F5-02 — TÜİK SDMX göstergelerinin yayın birimine çevrilmesi.

Adaptörün en tehlikeli hatası sessizdir: **yanlış seriyi seçmek.** Tek
bir veri akışı 96 seri taşıyabiliyor (8 gösterge x 2 yaş x 2 mevsimsellik
x 3 cinsiyet). Yanlış seri, `clustering/numeric_guard.py`'nin ilgisiz iki
sayıyı ÇELİŞKİ sanmasına ve iddianın 🔴 etiketlenmesine yol açar
(BACKLOG B-69). Bu yüzden testler "veri geldi mi"den çok
"DOĞRU veri mi geldi"yi kovalar.

Ağ çağrısı yapılmaz; SDMX yanıtı sahte istemciden gelir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from politikdesk.ingestion.adapters.tuik_sdmx import (
    TrackedIndicator,
    TuikSdmxAdapter,
    format_period,
    tr_lower,
)

NS = 'xmlns:generic="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic"'


def _series(dims: dict[str, str], period: str, value: str) -> str:
    keys = "".join(f'<generic:Value id="{k}" value="{v}" />' for k, v in dims.items())
    return (
        f"<generic:Series><generic:SeriesKey>{keys}</generic:SeriesKey>"
        f'<generic:Obs><generic:ObsDimension value="{period}" />'
        f'<generic:ObsValue value="{value}" /></generic:Obs></generic:Series>'
    )


def _document(*series: str) -> str:
    return (
        f"<message:GenericData {NS} "
        'xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message">'
        f"<message:DataSet>{''.join(series)}</message:DataSet></message:GenericData>"
    )


@dataclass
class _FakeResponse:
    text: str


@dataclass
class _FakeHttp:
    body: str
    calls: list[str] = field(default_factory=list)

    def get(
        self, url: str, *, headers: dict[str, str] | None = None, source_slug: str = ""
    ) -> _FakeResponse:
        self.calls.append(url)
        return _FakeResponse(self.body)

    def close(self) -> None:  # pragma: no cover
        pass


class _FakeTokens:
    def auth_header(self) -> dict[str, str]:
        return {"Authorization": "Bearer sahte"}


UNEMPLOYMENT = TrackedIndicator(
    dataflow="DF_TEST",
    version="1.0",
    label="İşsizlik oranı",
    metric="unemployment_rate",
    unit="%",
    dimensions={"ISGUCU_GOSTERGE": "8", "SEX": "_T", "SEASONAL_ADJUST": "S"},
    code="TUIK:DF_TEST:GOSTERGE_8",
    qualifier="mevsim etkisinden arındırılmış, 15+",
)


def _adapter(body: str, indicators: tuple[TrackedIndicator, ...] = (UNEMPLOYMENT,)):
    return TuikSdmxAdapter(
        slug="tuik",
        http=_FakeHttp(body),  # type: ignore[arg-type]
        tokens=_FakeTokens(),  # type: ignore[arg-type]
        indicators=indicators,
    )


# ------------------------------------------------------------ doğru seri
def test_picks_the_series_that_matches_every_dimension() -> None:
    """Karışık serilerden YALNIZCA filtreye tam uyanı alır."""
    body = _document(
        # İstihdam oranı — gösterge farklı
        _series({"ISGUCU_GOSTERGE": "7", "SEX": "_T", "SEASONAL_ADJUST": "S"}, "2026-06", "48.9"),
        # İşsizlik ama ERKEK
        _series({"ISGUCU_GOSTERGE": "8", "SEX": "1", "SEASONAL_ADJUST": "S"}, "2026-06", "6.9"),
        # İşsizlik, toplam, ama mevsimsellikten arındırılmamış
        _series({"ISGUCU_GOSTERGE": "8", "SEX": "_T", "SEASONAL_ADJUST": "N"}, "2026-06", "8.4"),
        # ARANAN
        _series({"ISGUCU_GOSTERGE": "8", "SEX": "_T", "SEASONAL_ADJUST": "S"}, "2026-06", "7.6"),
    )
    items = _adapter(body).fetch()

    assert len(items) == 1
    assert items[0].extra["normalized_value"] == {
        "metric": "unemployment_rate",
        "value": 7.6,
        "unit": "%",
        "period": "2026-06",
        # Köken ve epistemik tür kanıt motorunun sözleşmesidir:
        # `series_code` ADR-013 belirsizlik invariantını, `semantic`
        # ADR-014 ölçüm/beklenti ayrımını besler.
        "series_code": "TUIK:DF_TEST:GOSTERGE_8",
        "series_label": "İşsizlik oranı",
        "semantic": "measurement",
    }


def test_ambiguous_filter_produces_no_item() -> None:
    """Filtre seriyi tekilleştirmiyorsa TAHMİN YAPILMAZ.

    İki seri uyuyorsa hangisinin doğru olduğu bilinmiyordur. Birini
    seçmek, yanlış sayıyı Tier 1 kanıt olarak sisteme sokmak demektir —
    kanıt motorunun en çok güvendiği kaynağa yalan söyletmek.
    """
    body = _document(
        _series({"ISGUCU_GOSTERGE": "8", "SEX": "_T", "SEASONAL_ADJUST": "S"}, "2026-06", "7.6"),
        _series({"ISGUCU_GOSTERGE": "8", "SEX": "_T", "SEASONAL_ADJUST": "S"}, "2026-06", "9.1"),
    )
    adapter = _adapter(body)

    assert adapter.fetch() == []
    # Yutulan arıza KAYDEDİLİR; boş tur "başarılı" görünmez (B-80).
    assert adapter.drain_failures()


def test_missing_series_is_not_an_error_but_yields_nothing() -> None:
    body = _document(
        _series({"ISGUCU_GOSTERGE": "7", "SEX": "_T", "SEASONAL_ADJUST": "S"}, "2026-06", "48.9"),
    )
    assert _adapter(body).fetch() == []


# ------------------------------------------------------------ biçimleme
def test_float_noise_is_rounded_away() -> None:
    """`48.89999999999999` normalized_value'ye GİRMEZ.

    İddia imzası `metric:value:period` olduğu için kuyruk basamaklar aynı
    yayımın iki farklı imzaya düşmesine yol açardı — yani çapraz teyit
    yine kurulamazdı.
    """
    body = _document(
        _series(
            {"ISGUCU_GOSTERGE": "8", "SEX": "_T", "SEASONAL_ADJUST": "S"},
            "2026-06",
            "48.89999999999999",
        ),
    )
    assert _adapter(body).fetch()[0].extra["normalized_value"]["value"] == 48.9


def test_turkish_lowercase_does_not_produce_combining_dot() -> None:
    """Python'un `lower()`'ı "İ"yi "i̇" yapar; canlı koşumda görüldü."""
    assert tr_lower("İşsizlik") == "işsizlik"
    assert tr_lower("Işık") == "ışık"
    assert "i̇" not in tr_lower("İstihdam oranı")


def test_summary_uses_turkish_lowercase() -> None:
    body = _document(
        _series({"ISGUCU_GOSTERGE": "8", "SEX": "_T", "SEASONAL_ADJUST": "S"}, "2026-06", "7.6"),
    )
    summary = _adapter(body).fetch()[0].summary or ""
    assert "işsizlik oranı" in summary
    assert "i̇şsizlik" not in summary


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        ("2026-06", "Haziran 2026"),
        ("2026-01", "Ocak 2026"),
        ("2026", "2026"),
        ("2026-Q1", "2026-Q1"),
    ],
)
def test_period_is_written_in_turkish(period: str, expected: str) -> None:
    assert format_period(period) == expected


# ------------------------------------------------------------ tekillik
def test_url_and_guid_carry_the_period() -> None:
    """Her yayım AYRI bir öğedir; aynı yayım iki kez öğe üretmez.

    Tekilleştirme `canonical_url` üzerinden gider — dönem adreste
    olmasaydı yeni ayın verisi eskisinin tekrarı sanılırdı.
    """
    body = _document(
        _series({"ISGUCU_GOSTERGE": "8", "SEX": "_T", "SEASONAL_ADJUST": "S"}, "2026-06", "7.6"),
    )
    item = _adapter(body).fetch()[0]
    assert "2026-06" in item.url
    assert item.guid == "tuik:unemployment_rate:2026-06"


def test_tracked_metrics_are_in_the_project_vocabulary() -> None:
    """İzlenen her gösterge `VALID_METRICS` sözlüğünde OLMALI.

    Sözlükte olmayan bir kod doğrulamadan geçemez ve iddia sessizce
    reddedilir; adaptör boşuna çağrı yapmış olur.
    """
    from politikdesk.ingestion.adapters.tuik_sdmx import TRACKED
    from politikdesk.nlp.claims import VALID_METRICS

    for indicator in TRACKED:
        assert indicator.metric in VALID_METRICS, indicator.metric


def test_every_tracked_indicator_is_uniquely_pinned() -> None:
    """İki gösterge AYNI boyut filtresini paylaşamaz.

    Paylaşsalardı ikisi de aynı seriyi okur ve biri yanlış `metric`
    koduyla kaydedilirdi.
    """
    from politikdesk.ingestion.adapters.tuik_sdmx import TRACKED

    seen: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    for indicator in TRACKED:
        fingerprint = (indicator.dataflow, tuple(sorted(indicator.dimensions.items())))
        assert fingerprint not in seen, f"{indicator.metric}: boyut filtresi tekil değil"
        seen.add(fingerprint)


def test_pipeline_resolves_the_adapter_for_a_tuik_sdmx_source() -> None:
    """`adapter: tuik_sdmx` yazan kaynak satırı bu sınıfa çözümlenmeli.

    ⚠️ Bu test bilinçli olarak `registry`'yi DEĞİL `build_adapter`'ı
    denetler. `adapters/base.py` "yeni adaptör eklemek yalnızca kayda bir
    satır eklemeyi gerektirir" diyor ama bu doğru değil: `registry.get()`
    üretimde hiçbir yerden çağrılmıyor, `build_adapter` açık if
    dallarıyla çözümlüyor (her adaptörün kurucu argümanları farklı).

    Kayda bakan bir test yeşil yanar ve hiçbir şey kanıtlamaz — nitekim
    canlı konteynerde `registry.keys()` yalnızca `['fake']` döndürüyor,
    çünkü kayıt yalnızca modül import edilirse oluşuyor. Boru hattının
    gerçekten kullandığı yol budur.
    """
    from politikdesk.ingestion.pipeline import build_adapter
    from politikdesk.ingestion.repository import SourceRow

    source = SourceRow(
        id=1,
        slug="tuik",
        name="TÜİK",
        tier=1,
        kind="official",
        independence_group="official-tuik",
        access_method="api",
        tos_status="allowed",
        adapter="tuik_sdmx",
        base_url="https://www.tuik.gov.tr",
        feed_url="https://nsiws.tuik.gov.tr/rest",
        extra_feeds=[],
        keyword_filter=[],
        topics=[],
        is_active=True,
        is_wire_reference=False,
    )

    adapter = build_adapter(source)
    try:
        assert isinstance(adapter, TuikSdmxAdapter)
        assert adapter.slug == "tuik"
    finally:
        adapter.close()


def test_html_response_is_rejected_as_failure() -> None:
    """TÜİK SDMX ucu geçersiz token durumunda HTML döndürürse fail-closed yakalanır."""
    html_body = "<!DOCTYPE html><html><body><h1>401 Unauthorized</h1></body></html>"
    adapter = _adapter(html_body)
    items = adapter.fetch()
    assert len(items) == 0
    failures = adapter.drain_failures()
    assert len(failures) == 1
    assert "HTML döndürdü" in failures[0]


def test_malformed_xml_is_rejected_as_failure() -> None:
    """Bozuk XML yanıtı sessizce veri kaybı yaratmaz, açıkça hata kaydeder."""
    bad_xml = "<message:GenericData><unclosed_tag>"
    adapter = _adapter(bad_xml)
    items = adapter.fetch()
    assert len(items) == 0
    failures = adapter.drain_failures()
    assert len(failures) == 1
    assert "ayrıştırma hatası" in failures[0]


def test_token_expiry_triggers_invalidation_and_retry() -> None:
    """401/403 durumunda token invalidate edilir ve tek seferlik retry yapılır."""
    invalidated = False

    class _MockTokenProvider:
        def auth_header(self) -> dict[str, str]:
            return {"Authorization": "Bearer token1"}

        def invalidate(self) -> None:
            nonlocal invalidated
            invalidated = True

    class _MockHttpRetry:
        def __init__(self) -> None:
            self.calls = 0

        def get(self, url: str, **kwargs) -> _FakeResponse:
            self.calls += 1
            if self.calls == 1:
                resp = _FakeResponse("Unauthorized")
                resp.status_code = 401  # type: ignore[attr-defined]
                return resp
            resp = _FakeResponse(
                _document(
                    _series(
                        {"ISGUCU_GOSTERGE": "8", "SEX": "_T", "SEASONAL_ADJUST": "S"},
                        "2026-06",
                        "7.6",
                    )
                )
            )
            resp.status_code = 200  # type: ignore[attr-defined]
            return resp

    adapter = TuikSdmxAdapter(
        slug="tuik",
        http=_MockHttpRetry(),  # type: ignore[arg-type]
        tokens=_MockTokenProvider(),  # type: ignore[arg-type]
        indicators=(UNEMPLOYMENT,),
    )
    items = adapter.fetch()
    assert len(items) == 1
    assert invalidated is True


# ═══════════════════════════ gerçekleşmiş TÜFE serisi (ADR-015)


def test_realized_cpi_series_are_tracked() -> None:
    """TÜFE serileri izleniyor ve METRİKLERİ doğru.

    ADR-014 "TÜİK SDMX'te TÜFE YOK" diye kayda geçmişti; 20 Ağustos 2026'da
    canlı katalog yeniden sayıldığında DF_TUFE_SDMX_TT10 bulundu.
    """
    from politikdesk.ingestion.adapters.tuik_sdmx import TRACKED

    tufe = {i.metric: i for i in TRACKED if i.dataflow == "DF_TUFE_SDMX_TT10"}
    assert set(tufe) == {"tufe_annual", "tufe_monthly"}
    # Yıllık = "bir önceki yılın aynı ayına göre" (CL_DEGISIM kodu 4).
    assert tufe["tufe_annual"].dimensions["DEGISIM"] == "4"
    # Aylık = "bir önceki aya göre" (kod 2).
    assert tufe["tufe_monthly"].dimensions["DEGISIM"] == "2"
    for indicator in tufe.values():
        assert indicator.unit == "%"


def test_every_tracked_series_declares_measurement_semantics() -> None:
    """**Yeni seri yanlış semantikle eklenemez.**

    TÜİK kataloğunda beklenti serileri de var (`DF_TUKETICI_EGILIM_SDMX`
    — tüketici eğilimi anketi). Böyle bir seri beyansız eklenirse R3 onu
    sessizce ÖLÇÜM sayardı (ADR-014'ün fail-open'ı). Beyan zorunludur.
    """
    from politikdesk.ingestion.adapters.tuik_sdmx import TRACKED

    for indicator in TRACKED:
        assert indicator.semantic == "measurement", (
            f"{indicator.code}: ölçüm olmayan seri izleniyorsa `semantic` açıkça beyan edilmeli"
        )


def test_tracked_series_codes_are_unique() -> None:
    """Kimlikler ADR-013 belirsizlik invariantını besler; çakışamaz."""
    from politikdesk.ingestion.adapters.tuik_sdmx import TRACKED

    kodlar = [i.code for i in TRACKED]
    assert len(set(kodlar)) == len(kodlar)
    assert all(kodlar)


def test_official_value_carries_series_identity_and_semantics() -> None:
    """Kanıt motorunun okuduğu alanlar üretiliyor mu?"""
    body = _document(
        _series({"ISGUCU_GOSTERGE": "8", "SEX": "_T", "SEASONAL_ADJUST": "S"}, "2026-06", "7.6"),
    )
    nv = _adapter(body).fetch()[0].extra["normalized_value"]
    assert nv["series_code"] == "TUIK:DF_TEST:GOSTERGE_8"
    assert nv["semantic"] == "measurement"


# ═══════════════════════════ başlık, resmî değeri KAYBETMEZ


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (7.6, "7,6"),  # mevcut başlıklar birebir korunur
        (48.9, "48,9"),
        (8.0, "8,0"),
        (31.75, "31,75"),  # TÜFE iki ondalıkla yayımlanır
        (1.78, "1,78"),
        (0.99, "0,99"),  # `.1f` bunu "1,0" yapıyordu
    ],
)
def test_title_value_keeps_the_published_precision(value: float, expected: str) -> None:
    """`.1f` TÜFE'yi DEĞİŞTİRİYORDU: 31,75 -> "31,8".

    Zincir: başlık -> LLM iddiayı çıkarır -> R3 aynı makalenin
    `official_value`'suyla karşılaştırır. Başlık yuvarlarsa iddia
    31,8 olur, `official_value` 31.75 kalır ve doğrulama HİÇ kurulamaz.
    """
    from politikdesk.ingestion.adapters.tuik_sdmx import format_value

    assert format_value(value) == expected


def test_title_and_official_value_agree_on_the_number() -> None:
    """Başlıktaki sayı ile `official_value` AYNI sayı olmalı."""
    body = _document(
        _series({"ISGUCU_GOSTERGE": "8", "SEX": "_T", "SEASONAL_ADJUST": "S"}, "2026-07", "31.75"),
    )
    item = _adapter(body).fetch()[0]
    assert "%31,75" in item.title
    assert item.extra["normalized_value"]["value"] == 31.75
