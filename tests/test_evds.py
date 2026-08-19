"""TCMB EVDS adaptörü testleri (Faz 1.1).

Tamamı **fixture tabanlıdır**: hiçbir test ağa çıkmaz. Sebebi tek başına
yeterli — EVDS anahtarı olmayan bir makinede (CI dâhil) bu testlerin
atlanması, adaptörün korumalarının hiç sınanmaması demek olurdu. Bu depo
tam olarak bunu 18 Ağustos denetiminde yaşadı: veritabanı testleri test
sırasına göre sessizce atlanıyordu ve aralarında pazarlıksız kısıtları
koruyanlar vardı (D-06).

Sınanan sözleşme:
  1. HTTP 200 + HTML  -> İSTİSNA (sessiz sıfır öğe DEĞİL)
  2. Doğrulanmamış seri hiçbir sayı üretmez
  3. Eksik gözlem 0.0'a çevrilmez
  4. Revizyon ve tekrar gözlemler doğru ele alınır
  5. Her değer köken (provenance) taşır
  6. Dönem biçimi projenin sözlüğüne uyar
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest

from politikdesk.ingestion.adapters.evds import (
    TRACKED,
    EvdsAdapter,
    EvdsAuthError,
    EvdsResponseError,
    EvdsSeries,
    api_key,
    normalize_period,
    parse_value,
)

# ───────────────────────────────────────────────────────── yardımcılar
SPEC = EvdsSeries(
    code="TP.TEST.SERI",
    label="Sınama serisi",
    metric="policy_rate",
    unit="%",
    expected_name_contains="sinama",
    verified=True,
    qualifier="sınama",
)


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


class FakeHttp:
    """`HttpClient` yerine geçen sahte istemci — çağrıları kaydeder."""

    def __init__(self, response: FakeResponse | Exception) -> None:
        self._response = response
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, headers: dict[str, str] | None = None, **_: Any) -> FakeResponse:
        self.calls.append((url, dict(headers or {})))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    def close(self) -> None:  # pragma: no cover — sahte istemci kapanmaz
        pass


def _payload(rows: list[dict[str, Any]]) -> str:
    return json.dumps({"totalCount": len(rows), "items": rows}, ensure_ascii=False)


def _adapter(response: FakeResponse | Exception, series: tuple[EvdsSeries, ...] = (SPEC,)):
    return EvdsAdapter(http=FakeHttp(response), series=series)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _anahtar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PD_EVDS_API_KEY_ENV", "EVDS_API_KEY")
    monkeypatch.setenv("EVDS_API_KEY", "sinama-anahtari")


# ══════════════════════════════════════════ 1. HTML kabuğu (asıl koruma)
def test_html_body_raises_instead_of_returning_zero_items() -> None:
    """HTTP 200 + HTML **başarı değildir.**

    EVDS anahtarsız istekte 200 ile React SPA kabuğu döndürüyor
    (18 Ağustos 2026'da ölçüldü: text/html, 1354 bayt). Bu depo aynı
    sessiz arızayı iki kez yaşadı — B-42 (TÜİK portalı) ve B-43 (Hazine
    duyuruları); ikisinde de HTML adaptörü 0 öğe üretiyor ve tur
    "başarılı" görünüyordu. Sessiz sıfır yerine gürültülü hata.
    """
    html = '<!DOCTYPE html>\n<html lang="en"><head><title>EVDS</title></head></html>'
    adapter = _adapter(FakeResponse(html))

    with pytest.raises(EvdsResponseError, match="HTML"):
        adapter._parse_payload(html, SPEC)  # noqa: SLF001

    # fetch() istisnayı yutar ama DEFTERE yazar (B-80): tur başarılı sayılmaz.
    assert adapter.fetch() == []
    hatalar = adapter.drain_failures()
    assert any("HTML" in h for h in hatalar), hatalar


def test_html_detection_is_case_and_whitespace_insensitive() -> None:
    adapter = _adapter(FakeResponse(""))
    for govde in ("  <HTML>", "\n<!doctype HTML><body>", "<!DOCTYPE html>"):
        with pytest.raises(EvdsResponseError):
            adapter._parse_payload(govde, SPEC)  # noqa: SLF001


# ═══════════════════════════════════════ 2. doğrulanmamış seri sessiz kalmaz
def test_unverified_series_produces_no_value_and_is_reported() -> None:
    """Doğrulanmamış kod hiçbir sayı üretmemeli — ama sessizce de geçmemeli.

    Yanlış seri kodunun tehlikesi 404 değil, BAŞKA BİR BÜYÜKLÜĞÜ
    döndürmesidir: etiket "politika faizi" der, sayı başka şeydir.
    """
    dogrulanmamis = replace(SPEC, verified=False)
    adapter = _adapter(FakeResponse(_payload([{"Tarih": "18-08-2026", "TP_TEST_SERI": "50"}])),
                       series=(dogrulanmamis,))

    assert adapter.fetch() == []
    hatalar = adapter.drain_failures()
    assert any("doğrulanmadığı" in h for h in hatalar), hatalar
    assert any("probe_evds" in h for h in hatalar), hatalar


def test_every_shipped_series_was_verified_against_the_live_endpoint() -> None:
    """Her seri canlı uçta doğrulanmış olmalı — 19 Ağustos 2026, 6/6.

    **Bu testin ilk hâli tersini söylüyordu** ("hiçbiri doğrulanmamış
    olmalı") ve doğruydu: depoda anahtar yoktu. Anahtar geldiğinde
    `python -m scripts.probe_evds` koşuldu ve KODLARIN DÖRDÜ HATALI
    ÇIKTI:

        TP.APIFON4      veri DÖNDÜRÜYORDU (40,0) ama adı "TCMB Ağırlıklı
                        Ortalama Fonlama Maliyeti" — politika faizi değil
        TP.AB.A01       adı "A.AKTİF" — rezerv değil
        TP.BEK.S01.E.Y  HTTP 400, seri yok
        TP.PARA.M2      HTTP 400, seri yok

    İlk ikisi kapının asıl varlık sebebidir: kod çalışıyor, veri geliyor,
    ama ölçtüğü şey etiketin söylediği şey değil. Kapı olmasaydı
    "TCMB politika faizi: %40,0" ekrana çıkardı — D-01'de kaldırılan
    uydurma göstergenin birebir tekrarı, üstelik bu kez kurum verisi
    kılığında.

    Doğru kodlar tahminle değil, canlı arama ucuyla bulundu.
    """
    dogrulanmamis = [s.code for s in TRACKED if not s.verified]
    assert not dogrulanmamis, (
        f"Su seriler dogrulanmamis: {dogrulanmamis}. "
        "`python -m scripts.probe_evds` kosup dogrulayin; elle "
        "verified=True yapmak dogrulamayi atlamaktir."
    )
    assert len(TRACKED) >= 5, (
        "Roadmap 1.1 cikis olcutu en az 5 gosterge istiyor; "
        f"su an {len(TRACKED)} seri var."
    )


def test_probe_is_the_only_documented_way_to_flip_the_verified_flag() -> None:
    """`verified` bayrağının gerekçesi kodda yazılı kalmalı."""
    import inspect

    from politikdesk.ingestion.adapters import evds

    kaynak = inspect.getsource(evds)
    assert "probe_evds" in kaynak, (
        "Dogrulama yolu kaynakta anlatilmiyor; bayragin nasil acildigi "
        "kaybolursa kapi anlamsizlasir."
    )


# ═════════════════════════════════════════════ 3. bozuk / eksik yanıtlar
def test_malformed_json_raises() -> None:
    adapter = _adapter(FakeResponse("{bozuk json"))
    with pytest.raises(EvdsResponseError, match="JSON"):
        adapter._parse_payload("{bozuk json", SPEC)  # noqa: SLF001


def test_empty_body_raises() -> None:
    adapter = _adapter(FakeResponse("   "))
    with pytest.raises(EvdsResponseError, match="boş gövde"):
        adapter._parse_payload("   ", SPEC)  # noqa: SLF001


def test_missing_items_field_raises_and_names_the_fields_it_saw() -> None:
    govde = json.dumps({"totalCount": 3, "veriler": []})
    adapter = _adapter(FakeResponse(govde))
    with pytest.raises(EvdsResponseError, match="items"):
        adapter._parse_payload(govde, SPEC)  # noqa: SLF001


def test_rows_present_but_no_usable_column_raises_with_diagnostics() -> None:
    """Sütun adı değişmişse sessiz sıfır yerine tanı bilgisi döner."""
    govde = _payload([{"Tarih": "18-08-2026", "BASKA_SUTUN": "1", "IKINCI": "2"}])
    adapter = _adapter(FakeResponse(govde))
    with pytest.raises(EvdsResponseError) as hata:
        adapter._parse_payload(govde, SPEC)  # noqa: SLF001
    assert "TP_TEST_SERI" in str(hata.value)
    assert "BASKA_SUTUN" in str(hata.value)


# ══════════════════════════════════════════════════ 4. eksik gözlem ≠ sıfır
@pytest.mark.parametrize("bos", [None, "", "  ", "ND", "NA", "N/A", "-", "null"])
def test_missing_observation_is_skipped_not_zeroed(bos: Any) -> None:
    """Eksik gözlem 0.0'a çevrilirse kanıt motoruna GERÇEK bir gözlem
    gibi görünür ve R3 yanlış bir sayıyı doğrulamış olur."""
    assert parse_value(bos) is None


def test_rows_with_missing_values_are_dropped_but_others_survive() -> None:
    govde = _payload(
        [
            {"Tarih": "16-08-2026", "TP_TEST_SERI": "45.0"},
            {"Tarih": "17-08-2026", "TP_TEST_SERI": None},
            {"Tarih": "18-08-2026", "TP_TEST_SERI": "46.5"},
        ]
    )
    adapter = _adapter(FakeResponse(govde))
    gozlemler = adapter._parse_payload(govde, SPEC)  # noqa: SLF001
    assert gozlemler == [("2026-08-16", 45.0), ("2026-08-18", 46.5)]


# ════════════════════════════════════════ 5. revizyon ve tekrar gözlem
def test_revised_observation_uses_the_latest_period_value() -> None:
    """Aynı seride sonraki dönem gelirse EN YENİ gözlem yayımlanır."""
    govde = _payload(
        [
            {"Tarih": "17-08-2026", "TP_TEST_SERI": "45.0"},
            {"Tarih": "18-08-2026", "TP_TEST_SERI": "47.5"},
        ]
    )
    adapter = _adapter(FakeResponse(govde))
    (item,) = adapter.fetch()
    deger = item.extra["normalized_value"]
    assert deger["period"] == "2026-08-18"
    assert deger["value"] == 47.5
    assert item.extra["previous_value"] == 45.0


def test_out_of_order_rows_are_sorted_before_picking_the_latest() -> None:
    """EVDS sırayı garanti etmiyor; en yeni gözlem TARİHE göre seçilir."""
    govde = _payload(
        [
            {"Tarih": "18-08-2026", "TP_TEST_SERI": "47.5"},
            {"Tarih": "16-08-2026", "TP_TEST_SERI": "44.0"},
            {"Tarih": "17-08-2026", "TP_TEST_SERI": "45.0"},
        ]
    )
    adapter = _adapter(FakeResponse(govde))
    (item,) = adapter.fetch()
    assert item.extra["normalized_value"]["period"] == "2026-08-18"
    assert item.extra["observation_count"] == 3


def test_same_period_twice_yields_a_single_stable_guid() -> None:
    """Aynı yayım iki kez öğe üretmemeli — tekilleştirme `guid`e bakar."""
    govde = _payload([{"Tarih": "18-08-2026", "TP_TEST_SERI": "47.5"}])
    ilk = _adapter(FakeResponse(govde)).fetch()[0]
    ikinci = _adapter(FakeResponse(govde)).fetch()[0]
    assert ilk.guid == ikinci.guid == "evds:TP.TEST.SERI:2026-08-18"
    assert ilk.url == ikinci.url


# ══════════════════════════════════════════════════ 6. bayat / boş seri
def test_stale_series_with_no_rows_returns_no_item_without_raising() -> None:
    """Sıfır satır bir ARIZA değildir: seri o pencerede yayımlanmamış olabilir."""
    adapter = _adapter(FakeResponse(_payload([])))
    assert adapter.fetch() == []
    assert not adapter.drain_failures()


def test_unparseable_period_is_dropped_not_guessed() -> None:
    """Tanınmayan dönem biçiminde TAHMİN YAPILMAZ."""
    govde = _payload([{"Tarih": "18/08/2026", "TP_TEST_SERI": "47.5"}])
    adapter = _adapter(FakeResponse(govde))
    with pytest.raises(EvdsResponseError):
        adapter._parse_payload(govde, SPEC)  # noqa: SLF001


# ═══════════════════════════════════════════ 7. kimlik / hız sınırı / hata
def test_missing_api_key_is_reported_as_configuration_not_network() -> None:
    """Eksik yapılandırma ile ağ arızası ayrı şeylerdir.

    İkisi karıştırılırsa anahtarı olmayan kullanıcı ağ sorunu sanıp
    yanlış yerde arar (`tuik_auth.py` ile aynı gerekçe).
    """
    import os

    os.environ.pop("EVDS_API_KEY", None)
    with pytest.raises(EvdsAuthError, match="anahtar"):
        api_key()


def test_api_key_never_appears_in_error_messages() -> None:
    """⛔ Sır, hata mesajına bile girmez (`audit.py` ile aynı kural)."""
    import os

    os.environ["EVDS_API_KEY"] = "COK-GIZLI-ANAHTAR-123"
    adapter = _adapter(FakeResponse("<html></html>"))
    adapter.fetch()
    for hata in adapter.drain_failures():
        assert "COK-GIZLI-ANAHTAR-123" not in hata


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_key_raises_auth_error(status: int) -> None:
    adapter = _adapter(FakeResponse("{}", status_code=status))
    assert adapter.fetch() == []
    hatalar = adapter.drain_failures()
    assert any("EvdsAuthError" in h or "reddedildi" in h for h in hatalar), hatalar


def test_timeout_is_recorded_and_does_not_kill_other_series() -> None:
    """Bir seri düşerse diğerleri denenmeye devam eder (F1-02)."""
    import httpx

    adapter = _adapter(httpx.ReadTimeout("zaman asimi"), series=(SPEC, replace(SPEC, code="TP.B")))
    assert adapter.fetch() == []
    hatalar = adapter.drain_failures()
    assert len(hatalar) == 2, hatalar  # iki seri de denendi
    assert all("ReadTimeout" in h for h in hatalar)


def test_rate_limit_response_is_surfaced_not_swallowed() -> None:
    """429 gövdesi JSON değilse sözleşme ihlali olarak raporlanır."""
    adapter = _adapter(FakeResponse("Too Many Requests", status_code=429))
    assert adapter.fetch() == []
    assert adapter.drain_failures()


# ═════════════════════════════════════════════════════ 8. köken (provenance)
def test_every_value_carries_full_provenance() -> None:
    """Roadmap 1.1 veri sözleşmesi: her değer nereden geldiğini taşımalı."""
    govde = _payload([{"Tarih": "18-08-2026", "TP_TEST_SERI": "47.5"}])
    (item,) = _adapter(FakeResponse(govde)).fetch()
    deger = item.extra["normalized_value"]

    for alan in ("metric", "value", "unit", "period", "series_code", "series_label",
                 "source", "source_url", "retrieved_at"):
        assert deger.get(alan), f"koken alani eksik: {alan}"

    assert deger["source"] == "TCMB EVDS"
    assert deger["series_code"] == "TP.TEST.SERI"
    assert "evds3.tcmb.gov.tr" in deger["source_url"]


def test_series_code_discriminates_two_series_sharing_one_metric() -> None:
    """USD/TRY ile EUR/TRY'nin ikisi de `exchange_rate`.

    `metric` tek başına ayırt etmiyor; ayırt edilmezlerse gösterge şeridi
    iki farklı büyüklüğü TEK SERİ gibi çizer — 18 Ağustos'ta kaldırılan
    uydurma gösterge kusurunun (D-01) veri tarafındaki karşılığı olurdu.
    """
    usd = replace(SPEC, code="TP.DK.USD.A.YTL", metric="exchange_rate", label="USD")
    eur = replace(SPEC, code="TP.DK.EUR.A.YTL", metric="exchange_rate", label="EUR")

    govde = _payload([{"Tarih": "18-08-2026", "TP_DK_USD_A_YTL": "34.1"}])
    (u,) = _adapter(FakeResponse(govde), series=(usd,)).fetch()

    govde2 = _payload([{"Tarih": "18-08-2026", "TP_DK_EUR_A_YTL": "37.4"}])
    (e,) = _adapter(FakeResponse(govde2), series=(eur,)).fetch()

    assert u.extra["normalized_value"]["metric"] == e.extra["normalized_value"]["metric"]
    assert u.extra["normalized_value"]["series_code"] != e.extra["normalized_value"]["series_code"]
    assert u.guid != e.guid


# ══════════════════════════════════════════════════ 9. dönem normalizasyonu
@pytest.mark.parametrize(
    "ham,beklenen",
    [
        ("18-08-2026", "2026-08-18"),
        ("01-01-2026", "2026-01-01"),
        ("2026-8", "2026-08"),
        ("2026-12", "2026-12"),
        ("08-2026", "2026-08"),
        ("2026-Q3", "2026-Q3"),
        ("2026Q1", "2026-Q1"),
        ("2026", "2026"),
    ],
)
def test_period_normalization(ham: str, beklenen: str) -> None:
    assert normalize_period(ham) == beklenen


@pytest.mark.parametrize("ham", ["", "   ", "18/08/2026", "Ağustos 2026", "2026-13", "abc"])
def test_unrecognised_period_returns_none(ham: str) -> None:
    """Tanınmayan biçim None döner — yanlış dönem, dönemsizlikten kötüdür."""
    assert normalize_period(ham) is None


def test_every_tracked_metric_exists_in_the_project_vocabulary() -> None:
    """`metric` uydurulamaz: kanıt motoru R3 bu sözlükle karşılaştırır."""
    from politikdesk.nlp.claims import VALID_METRICS

    bilinmeyen = {s.metric for s in TRACKED} - set(VALID_METRICS)
    assert not bilinmeyen, f"VALID_METRICS'te olmayan metrik: {sorted(bilinmeyen)}"


def test_every_tracked_metric_has_a_turkish_label() -> None:
    """Ekrana ham metrik anahtarı çıkmamalı (`ui/format.py::METRIC_LABELS`)."""
    from politikdesk.web.ui.format import METRIC_LABELS

    eksik = {s.metric for s in TRACKED} - set(METRIC_LABELS)
    assert not eksik, f"Turkce karsiligi olmayan metrik: {sorted(eksik)}"


# ════════════════════════════════ 10. adaptör ↔ yapılandırma tutarlılığı
def test_adapter_is_registered_in_the_pipeline() -> None:
    """Adaptör kayıtlı olmalı — aksi hâlde kaynak eklenince `bilinmeyen
    adaptör` hatasıyla düşer."""
    from politikdesk.ingestion.pipeline import ADAPTER_REGISTRY

    assert ADAPTER_REGISTRY.get("evds") is EvdsAdapter


def test_evds_source_is_not_configured_while_series_are_unverified() -> None:
    """Doğrulanmamış adaptör için AKTİF kaynak satırı açılmaz.

    Gerekçe, bu denetimde üç kez tekrarlanan dersin aynısı: veri
    üretemeyeceği kesin olan bir kaynak, sağlık panosunda **kalıcı
    kırmızı** olur. Kalıcı yanlış alarm susturulur, susturulmuş alarm
    gerçek kopmayı gizler (bkz. `pipeline_health.py` iddia aşaması).

    Sıra şudur: anahtar alınır -> `probe_evds` kodları doğrular ->
    `verified=True` yapılır -> ANCAK O ZAMAN `config/sources.yml`'ye
    kaynak eklenir. Bu test o sırayı zorlar.
    """
    from politikdesk.ingestion.sources import load_all_configs

    evds_kaynaklari = [c for c in load_all_configs() if c.adapter == "evds"]
    dogrulanmis_seri = [s for s in TRACKED if s.verified]

    if not dogrulanmis_seri:
        assert not evds_kaynaklari, (
            "config/sources.yml'de evds kaynagi var ama hicbir seri "
            "dogrulanmamis — kaynak veri uretemez ve kalici kirmizi olur. "
            "Once `python -m scripts.probe_evds` calistirin."
        )
    else:
        assert evds_kaynaklari, (
            f"{len(dogrulanmis_seri)} seri dogrulanmis ama config/sources.yml'de "
            "evds kaynagi yok — adaptor hicbir zaman calismaz."
        )


def test_env_example_documents_the_evds_key() -> None:
    """Anahtar dolaylı desenle belgelenmiş olmalı (`PD_LLM_API_KEY_ENV` gibi)."""
    from pathlib import Path

    ornek = (Path(__file__).resolve().parent.parent / ".env.example").read_text(encoding="utf-8")
    assert "PD_EVDS_API_KEY_ENV" in ornek
    assert "probe_evds" in ornek, "Dogrulama adimi .env.example'da anlatilmali."
