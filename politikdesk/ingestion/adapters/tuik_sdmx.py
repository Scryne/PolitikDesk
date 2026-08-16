"""TÜİK SDMX göstergeleri -> yayın birimi (F5-02 · B-42'nin veri ayağı).

TÜİK'in bültenleri sunucudan okunamıyor (veri portalı React SPA — B-42).
Okunabilen tek uç SDMX servisidir ve o **haber değil, seri** döndürür.
Bu adaptör seçilmiş göstergelerin **en son gözlemini** bir yayın birimine
çevirir: "İşsizlik oranı, Haziran 2026: %8,4".

Kazanç boru hattının en zayıf yerinde: TÜİK Tier 1'dir ve kanıt motoru
🟢 (R2) için `has_primary_source` **ve** `independent_count >= 3` ister.
Faz 5'te medya genişlemesi ikinciyi sağladı, birincisi hâlâ eksikti.

-----------------------------------------------------------------------
TASARIM KURALI — BELİRSİZSE ÜRETME
-----------------------------------------------------------------------
Tek bir veri akışı 96 seri taşıyabiliyor (8 gösterge x 2 yaş grubu x
2 mevsimsellik x 3 cinsiyet). Yanlış seriyi seçmek sessiz ve zararlıdır:
`clustering/numeric_guard.py` ilgisiz iki sayıyı ÇELİŞKİ sanar ve iddia
🔴 etiketlenir (BACKLOG B-69'un uyardığı arıza).

Bu yüzden:
  1. Her gösterge, seriyi TEKİLLEŞTİREN boyutlarla tam olarak pinlenir.
  2. Filtreye birden fazla seri uyarsa öğe ÜRETİLMEZ — belirsizlik
     kaydedilir (`FailureRecorder`), tahmin yapılmaz.
  3. Yalnızca projenin `VALID_METRICS` sözlüğüne KESİN karşılığı olan
     göstergeler izlenir. Karşılığı tartışmalı olan eklenmez.

Gösterge kodlarının Türkçe karşılıkları CL_ISGUCU_GOSTERGE kod
listesinden okunmuştur (13 Ağu 2026):
    6 = İşgücüne Katılma Oranı (%)   7 = İstihdam Oranı (%)
    8 = İşsizlik Oranı (%)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from xml.etree import ElementTree

from politikdesk.ingestion.adapters.base import FailureRecorder, registry
from politikdesk.ingestion.http import HttpClient
from politikdesk.ingestion.models import RawItem
from politikdesk.ingestion.tuik_auth import TuikTokenProvider
from politikdesk.observability import get_logger

log = get_logger(__name__)

SDMX_BASE = "https://nsiws.tuik.gov.tr/rest"
GENERIC_NS = "{http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic}"

_MONTHS_TR = (
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
)


@dataclass(frozen=True)
class TrackedIndicator:
    """İzlenen tek bir gösterge — serisi boyutlarla tam pinlenmiş."""

    dataflow: str
    version: str
    label: str
    metric: str  # politikdesk/nlp/claims.py::VALID_METRICS
    unit: str
    dimensions: dict[str, str]
    qualifier: str = ""  # başlıkta görünen ayrım (ör. "mevsim etkisinden arındırılmış")


# Yalnızca KESİN eşleşenler. Yeni gösterge eklerken kod listesi okunmadan
# ve `metric` karşılığı doğrulanmadan bu tabloya satır eklenmez.
TRACKED: tuple[TrackedIndicator, ...] = (
    TrackedIndicator(
        dataflow="DF_ISGUCU_AYLIK_TEMEL_ISGUCU_C",
        version="1.0",
        label="İşsizlik oranı",
        metric="unemployment_rate",
        unit="%",
        dimensions={
            "ISGUCU_GOSTERGE": "8",
            "TEMEL_YAS": "Y_GE15",
            "SEX": "_T",
            "SEASONAL_ADJUST": "S",
        },
        qualifier="mevsim etkisinden arındırılmış, 15+",
    ),
    TrackedIndicator(
        dataflow="DF_ISGUCU_AYLIK_TEMEL_ISGUCU_C",
        version="1.0",
        label="İstihdam oranı",
        metric="employment_rate",
        unit="%",
        dimensions={
            "ISGUCU_GOSTERGE": "7",
            "TEMEL_YAS": "Y_GE15",
            "SEX": "_T",
            "SEASONAL_ADJUST": "S",
        },
        qualifier="mevsim etkisinden arındırılmış, 15+",
    ),
    TrackedIndicator(
        dataflow="DF_ISGUCU_AYLIK_TEMEL_ISGUCU_C",
        version="1.0",
        label="İşgücüne katılma oranı",
        metric="participation_rate",
        unit="%",
        dimensions={
            "ISGUCU_GOSTERGE": "6",
            "TEMEL_YAS": "Y_GE15",
            "SEX": "_T",
            "SEASONAL_ADJUST": "S",
        },
        qualifier="mevsim etkisinden arındırılmış, 15+",
    ),
)


def tr_lower(text: str) -> str:
    """Türkçe küçültme.

    Python'un `str.lower()`'ı "İ"yi "i̇" (i + birleşen nokta) yapar ve
    "I"yı "i"ye çevirir — ikisi de Türkçe'de yanlıştır. Canlı koşumda
    "İşsizlik".lower() özette "i̇şsizlik" olarak göründü.
    `nlp/claims.py::fold_text` ile aynı deyim.
    """
    return text.replace("İ", "i").replace("I", "ı").lower()


def format_period(period: str) -> str:
    """`2026-06` -> `Haziran 2026`. Tanınmayan biçim olduğu gibi döner."""
    parts = period.split("-")
    if len(parts) == 2 and parts[1].isdigit() and 1 <= int(parts[1]) <= 12:
        return f"{_MONTHS_TR[int(parts[1]) - 1]} {parts[0]}"
    return period


def _series_matches(key: dict[str, str], wanted: dict[str, str]) -> bool:
    return all(key.get(dim) == value for dim, value in wanted.items())


@dataclass
class TuikSdmxAdapter(FailureRecorder):
    """İzlenen göstergelerin son gözlemini yayın birimine çevirir."""

    slug: str = "tuik"
    http: HttpClient | None = None
    tokens: TuikTokenProvider | None = None
    indicators: tuple[TrackedIndicator, ...] = TRACKED
    _owns_http: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        super().__init__()
        if self.http is None:
            # SDMX ve kimlik konakları el sıkışma ortasında düşebiliyor;
            # yeniden deneme burada isteğe bağlı değil, şart.
            self.http = HttpClient(respect_robots=False, timeout=120.0, max_retries=6)
            self._owns_http = True
        if self.tokens is None:
            self.tokens = TuikTokenProvider(client=self.http)

    def fetch(self) -> list[RawItem]:
        items: list[RawItem] = []
        for indicator in self.indicators:
            try:
                item = self._fetch_one(indicator)
            except Exception as exc:  # noqa: BLE001
                # Bir gösterge düşerse diğerleri denenmeye devam eder;
                # yutulan istisna KAYDEDİLİR, yoksa boş tur "başarılı"
                # görünür (B-80).
                self.record_failure(indicator.dataflow, exc)
                log.warning(
                    "tuik_indicator_failed",
                    dataflow=indicator.dataflow,
                    metric=indicator.metric,
                    error=type(exc).__name__,
                    detail=str(exc)[:200],
                )
                continue
            if item is not None:
                items.append(item)
        return items

    def _data_url(self, indicator: TrackedIndicator) -> str:
        return (
            f"{SDMX_BASE}/data/TR,{indicator.dataflow},{indicator.version}/all?lastNObservations=1"
        )

    def _fetch_one(self, indicator: TrackedIndicator) -> RawItem | None:
        assert self.http is not None and self.tokens is not None

        url = self._data_url(indicator)
        response = self.http.get(
            url,
            headers=self.tokens.auth_header(),
            source_slug=self.slug,
        )

        if getattr(response, "status_code", 200) in (401, 403):
            log.warning("tuik_token_expired_retrying", status=getattr(response, "status_code", 200))
            self.tokens.invalidate()
            response = self.http.get(
                url,
                headers=self.tokens.auth_header(),
                source_slug=self.slug,
            )

        text = response.text.strip()
        if not text:
            log.warning("tuik_empty_response", dataflow=indicator.dataflow)
            return None

        if text.startswith("<html") or text.startswith("<!DOCTYPE html"):
            log.warning(
                "tuik_html_response_unexpected",
                dataflow=indicator.dataflow,
                preview=text[:200],
            )
            raise ValueError(f"TÜİK SDMX ucu HTML döndürdü (beklenen SDMX-ML XML): {text[:100]}")

        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError as exc:
            log.error(
                "tuik_sdmx_parse_error",
                dataflow=indicator.dataflow,
                metric=indicator.metric,
                error=str(exc),
                preview=text[:300],
            )
            err_msg = f"TÜİK SDMX XML ayrıştırma hatası ({indicator.dataflow}): {exc}"
            raise ValueError(err_msg) from exc

        matches: list[tuple[str, str]] = []
        for series in root.findall(f".//{GENERIC_NS}Series"):
            key = {
                v.get("id", ""): v.get("value", "")
                for v in series.findall(f"{GENERIC_NS}SeriesKey/{GENERIC_NS}Value")
            }
            if not _series_matches(key, indicator.dimensions):
                continue
            obs = series.find(f"{GENERIC_NS}Obs")
            if obs is None:
                continue
            dim = obs.find(f"{GENERIC_NS}ObsDimension")
            val = obs.find(f"{GENERIC_NS}ObsValue")
            if dim is None or val is None:
                continue
            matches.append((dim.get("value", ""), val.get("value", "")))

        if not matches:
            log.warning(
                "tuik_series_not_found", dataflow=indicator.dataflow, metric=indicator.metric
            )
            return None

        if len(matches) > 1:
            # Filtre seriyi tekilleştirmiyor. TAHMİN YAPILMAZ: yanlış seri,
            # numeric_guard'ın ilgisiz sayıları çelişki sanmasına yol açar.
            raise ValueError(
                f"{indicator.dataflow}/{indicator.metric}: filtreye "
                f"{len(matches)} seri uyuyor, tekil değil"
            )

        period, raw_value = matches[0]
        if not period or not raw_value:
            return None

        # SDMX bazen ikili gösterimden gelen kuyruk basamaklarla döndürüyor
        # ("48.89999999999999"). Yuvarlanmazsa bu değer `normalized_value`e
        # girer ve iddia imzası `metric:value:period` olduğu için AYNI
        # yayımın iki farklı imzaya düşmesine yol açabilir.
        value = round(float(raw_value), 2)
        pretty_value = f"{value:.1f}".replace(".", ",")
        title = (
            f"{indicator.label} ({indicator.qualifier}), {format_period(period)}: %{pretty_value}"
            if indicator.unit == "%"
            else f"{indicator.label}, {format_period(period)}: {pretty_value}"
        )

        return RawItem(
            source_slug=self.slug,
            # Dönemi taşıyan KANONİK adres: her yayım ayrı bir öğedir ve
            # aynı yayım iki kez öğe üretmez (tekilleştirme buna bakar).
            url=f"{self._data_url(indicator)}&_metric={indicator.metric}&_period={period}",
            title=title,
            # Referans dönemi DEĞİL, "bizim için yayımlandığı an". TÜİK bu
            # uçta yayım tarihini vermiyor; dönemi published_at yapmak veriyi
            # haftalarca eski gösterip akışın dibine gömerdi. Referans dönem
            # başlıkta ve `extra`da açıkça duruyor, yani hiçbir şey gizlenmiyor.
            published_at=datetime.now(UTC),
            summary=(
                f"TÜİK, {format_period(period)} dönemi için "
                f"{tr_lower(indicator.label)} değerini %{pretty_value} olarak açıkladı "
                f"({indicator.qualifier})."
                if indicator.unit == "%"
                else f"TÜİK {format_period(period)}: {indicator.label} {pretty_value}"
            ),
            guid=f"tuik:{indicator.metric}:{period}",
            extra={
                "normalized_value": {
                    "metric": indicator.metric,
                    "value": value,
                    "unit": indicator.unit,
                    "period": period,
                },
                "dataflow": indicator.dataflow,
                "dimensions": indicator.dimensions,
                "reference_period": period,
            },
        )

    def close(self) -> None:
        if self._owns_http and self.http is not None:
            self.http.close()


registry.register("tuik_sdmx", TuikSdmxAdapter)
