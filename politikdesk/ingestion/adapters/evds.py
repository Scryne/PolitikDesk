"""TCMB EVDS göstergeleri -> yayın birimi (Faz 1.1).

TÜİK SDMX adaptörünün (`tuik_sdmx.py`) kardeşidir ve aynı işi TCMB için
yapar: bir **seriyi** okur, son gözlemi bir **yayın birimine** çevirir.
Kazanç kanıt motorundadır — R3 (Spec §8.3) kurumun kendi makine okunur
yayınından gelen sayıya tek kaynakla 🟢 verebilir, ama bunun için o sayının
`articles.official_value` alanına yazılması gerekir (migration 0007).
TÜİK açıldığında R3 canlanmıştı; TCMB ile politika faizi, kur ve rezervler
de aynı kapıdan geçebilir hâle gelir.

-----------------------------------------------------------------------
İKİ SERT KURAL
-----------------------------------------------------------------------

**1. HTTP 200 BAŞARI DEMEK DEĞİLDİR.**

EVDS, anahtarsız istekte `200 OK` ile bir React SPA kabuğu döndürür
(18 Ağustos 2026'da ölçüldü: `text/html`, 1354 bayt, `<!DOCTYPE html>`).
Bu depo aynı tuzağa iki kez düştü:

    B-42  TÜİK veri portalı  — 200 + "JavaScript gerekli" kabuğu
    B-43  Hazine duyuruları  — 200 + "enable JavaScript" kabuğu,
                               HTML adaptörü 0 öğe üretiyordu ve tur
                               SESSİZCE başarılı görünüyordu

Bu yüzden `_parse_payload` gövdeyi ayrıştırmadan önce HTML olup olmadığına
bakar ve HTML görürse **istisna fırlatır**. Sessiz sıfır öğe yerine
gürültülü hata: kaynak sağlık panosu kırmızıya döner ve arıza görünür.

**2. DOĞRULANMAMIŞ SERİ KODU VERİ ÜRETMEZ.**

Yanlış bir seri kodunun tehlikesi 404 almak değildir — o zaten görünür.
Tehlike, kodun **başka bir büyüklüğü** döndürmesidir: etiket "politika
faizi" der, sayı başka bir şeydir ve kimse fark etmez. `tuik_sdmx.py`'nin
başlığındaki "BELİRSİZSE ÜRETME" kuralı burada da geçerlidir, çünkü
sonuç aynıdır: `numeric_guard` ilgisiz iki sayıyı çelişki sanar ve iddia
🔴 etiketlenir (BACKLOG B-69).

Bu yüzden her seri bir `verified` bayrağı taşır ve adaptör **yalnızca
doğrulanmış serileri yayımlar**. Bayrak elle açılmaz; `scripts/probe_evds.py`
canlı uçtan seri adını okur, beklenen adla karşılaştırır ve uygulanacak
farkı yazdırır.

⛔ API anahtarı loglanmaz ve istisna metnine girmez (`tuik_auth.py` ile
aynı kural).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Final

from politikdesk.ingestion.adapters.base import FailureRecorder, registry
from politikdesk.ingestion.http import HttpClient
from politikdesk.ingestion.models import RawItem
from politikdesk.observability import get_logger

log = get_logger(__name__)

# ⚠️ EVDS v2 KAPANDI (19 Ağustos 2026'da ölçüldü).
#
# `evds2.tcmb.gov.tr/service/evds/...` artık veri döndürmüyor: her yol —
# anahtar başlıkta, anahtar sorgu dizesinde ya da anahtarsız — `302` ile
# `https://evds3.tcmb.gov.tr` KÖKÜNE yönlendiriyor. Yönlendirme takip
# edilince gelen şey bir React SPA kabuğu, yani HTML.
#
# Bu, adaptörün HTML muhafızının neden şart olduğunun canlı kanıtıdır:
# muhafız olmasaydı adaptör her turda 200 alır, 0 öğe üretir ve tur
# "başarılı" görünürdü — B-42 ve B-43'ün aynısı.
#
# Sözleşme v3'te KORUNMUŞ, yalnızca taban değişmiş:
#     GET https://evds3.tcmb.gov.tr/igmevdsms-dis/series=<KOD>
#         &startDate=DD-MM-YYYY&endDate=DD-MM-YYYY&type=json
#         Header: key: <APIKEY>
#     -> {"totalCount": N, "items": [{"Tarih": "...", "TP_DK_USD_A_YTL": "..."}]}
#
# Taban `evds3.tcmb.gov.tr` JS paketinden çıkarıldı
# (`axios.defaults.baseURL = "/igmevdsms-dis"`); yöntem `tuik_auth.py` ve
# `context/official_calendar.py` ile aynı.
EVDS_BASE: Final[str] = "https://evds3.tcmb.gov.tr/igmevdsms-dis"

# Seri adını doğrulayan uç (yalnızca `scripts/probe_evds.py` kullanır).
EVDS_SEARCH_URL: Final[str] = EVDS_BASE + "/searchResults?searchVal={code}"

# Kaç günlük pencere istenecek. Seriler farklı sıklıkta yayımlanır
# (günlük kur, haftalık rezerv, aylık beklenti); 120 gün, en seyrek
# yayımlanan seride bile birden fazla gözlem görmeye yeter ve
# "önceki değere göre değişim" hesaplanabilir olur.
LOOKBACK_DAYS: Final[int] = 120


class EvdsAuthError(RuntimeError):
    """API anahtarı yok veya reddedildi. Mesaj anahtar İÇERMEZ."""


class EvdsResponseError(RuntimeError):
    """Uç beklenen sözleşmeyi döndürmedi (HTML kabuğu, bozuk JSON, eksik sütun)."""


def api_key() -> str:
    """EVDS anahtarını dolaylı desenle çözer.

    Depo genelindeki kural (`PD_LLM_API_KEY_ENV`, `PD_TUIK_API_KEY_ENV`):
    `.env` anahtarın KENDİSİNİ değil, anahtarı taşıyan ortam değişkeninin
    ADINI tutar. Böylece sır, yapılandırma dosyalarından bağımsız
    yönetilebilir.
    """
    var = os.environ.get("PD_EVDS_API_KEY_ENV", "EVDS_API_KEY")
    key = os.environ.get(var, "").strip()
    if not key:
        raise EvdsAuthError(
            f"TCMB EVDS API anahtarı yok: '{var}' ortam değişkeni boş. "
            "Anahtar evds2.tcmb.gov.tr üzerinden ücretsiz alınır; "
            ".env'e PD_EVDS_API_KEY_ENV ve anahtarı ekleyin."
        )
    return key


@dataclass(frozen=True)
class EvdsSeries:
    """İzlenen tek bir EVDS serisi.

    `metric` projenin `nlp/claims.py::VALID_METRICS` sözlüğünden gelir ve
    kanıt motorunun R3 karşılaştırmasında kullanılır.

    `verified` neden var: bkz. modül başlığı, "2. sert kural". `False`
    olan seri ÇEKİLMEZ ve hiçbir sayı üretmez.

    `expected_name_contains` doğrulamanın ölçütüdür: `probe_evds.py`
    canlı uçtan gelen seri adında bu parçayı arar. Eşleşmezse kod
    yanlıştır ve bayrak açılmaz.
    """

    code: str
    label: str
    metric: str
    unit: str
    expected_name_contains: str
    verified: bool = False
    qualifier: str = ""
    semantic: str = "measurement"
    """Serinin epistemik türü: `measurement` mi, `expectation` mı?

    **Neden gerekli (20 Ağustos 2026 denetimi).** `metric` bir gösterge
    AİLESİDİR ve iki farklı epistemik nesneyi aynı ada çökertebiliyordu:
    `TP.ENFBEK.PKA12ENF` "12 ay sonrası enflasyon BEKLENTİSİ"dir (piyasa
    katılımcıları anketi) ama `metric="tufe_annual"` ile temsil ediliyor —
    yani *gerçekleşmiş* yıllık TÜFE ile aynı ad.

    Ölçüldü: gerçekleşmiş enflasyon iddiası, değeri ve dönemi tutarsa
    beklenti serisiyle **doğrulanıyordu** (`_verified_against_official`
    `True` dönüyordu). Bir anket beklentisi, olmuş bir olguyu doğrulayamaz.

    Ayrım iddia tarafına konulamaz: iddia şeması semantik tip taşımıyor ve
    LLM'e ürettirmek yeni epistemik yetki olurdu (Spec §8.1). Bu yüzden
    KAYNAK tarafında beyan edilir ve R3 yalnızca `measurement` serilerini
    kabul eder.
    """

    @property
    def response_key(self) -> str:
        """EVDS, yanıt sütun adında noktaları alt çizgiye çevirir.

        `TP.DK.USD.A` -> `TP_DK_USD_A`. Bu dönüşüm belgelenmiş değil,
        yanıt gövdesinden okunur; bu yüzden `_read_value` sütunu ararken
        yalnızca buna güvenmez, birkaç aday dener.
        """
        return self.code.replace(".", "_")


# ---------------------------------------------------------------------------
# İzlenen seriler — HEPSİ 19 AĞUSTOS 2026'DA CANLI UÇTA DOĞRULANDI.
#
# Doğrulama `python -m scripts.probe_evds` ile yapıldı: her kod için hem
# veri çekildi hem de TCMB'nin serine verdiği RESMÎ AD okunup
# `expected_name_contains` ile karşılaştırıldı.
#
# ⚠️ İLK TABLO YANLIŞTI VE PROBE ONU YAKALADI. Bu, `verified` kapısının
# neden var olduğunun kanıtıdır — altı kodun dördü hatalıydı:
#
#   TP.APIFON4      veri DÖNDÜRÜYORDU (40,0) ama adı "TCMB Ağırlıklı
#                   Ortalama Fonlama Maliyeti" — politika faizi DEĞİL.
#                   Kapı olmasaydı bu sayı "politika faizi" etiketiyle
#                   ekrana çıkardı. Tehlike 404 almak değil, tam olarak
#                   budur: çalışan ama BAŞKA BİR ŞEYİ ölçen kod.
#   TP.AB.A01       adı "A.AKTİF" — rezerv değil.
#   TP.BEK.S01.E.Y  HTTP 400, seri yok.
#   TP.PARA.M2      HTTP 400, seri yok.
#
# Doğru kodlar tahminle değil, canlı arama ucuyla bulundu
# (`/searchResults?searchVal=...`).
#
# Yeni seri eklerken bayrak ELLE açılmaz: önce probe koşulur.
# ---------------------------------------------------------------------------
TRACKED: tuple[EvdsSeries, ...] = (
    EvdsSeries(
        code="TP.BISPOLFAIZ.TUR",
        label="TCMB politika faizi",
        metric="policy_rate",
        unit="%",
        expected_name_contains="politika faiz",
        verified=True,
        # Dürüstlük notu: bu seri BIS derlemesidir ve AYLIKTIR; TCMB'nin
        # PPK gününde yayımladığı anlık karar duyurusu değildir. Faiz
        # KARARININ kendisi `sources.yml`'deki TCMB RSS akışından
        # (PPK Kararları) haber olarak geliyor; bu seri o kararın
        # makine okunur zaman serisi karşılığıdır.
        qualifier="BIS derlemesi, aylık",
    ),
    EvdsSeries(
        code="TP.DK.USD.A.YTL",
        label="ABD doları alış kuru",
        metric="exchange_rate",
        unit="TRY",
        expected_name_contains="abd dolari",
        verified=True,
        qualifier="döviz alış, günlük",
    ),
    EvdsSeries(
        code="TP.DK.EUR.A.YTL",
        label="Euro alış kuru",
        metric="exchange_rate",
        unit="TRY",
        expected_name_contains="euro",
        verified=True,
        qualifier="döviz alış, günlük",
    ),
    EvdsSeries(
        code="TP.AB.B6",
        label="Toplam rezervler",
        metric="reserves",
        # Birim BİLEREK boş: EVDS bu seri için birim beyan etmiyor
        # (arama ucunda `birim` alanı yok). Uydurulmuş bir birim
        # ("USD mn"), uydurulmuş bir sayı kadar yanıltıcıdır.
        unit="",
        expected_name_contains="rezerv",
        verified=True,
        qualifier="aylık; birim TCMB tarafından beyan edilmiyor",
    ),
    EvdsSeries(
        code="TP.ENFBEK.PKA12ENF",
        label="12 ay sonrası yıllık enflasyon beklentisi",
        metric="tufe_annual",
        unit="%",
        expected_name_contains="enflasyon beklenti",
        verified=True,
        qualifier="piyasa katılımcıları anketi, aylık",
        # ⛔ BEKLENTİ — gerçekleşmiş veri DEĞİL. R3 bu seriyi resmî
        # doğrulama olarak KABUL ETMEZ: bir anket beklentisi olmuş bir
        # olguyu doğrulayamaz. Gösterge şeridinde görünmeye devam eder.
        semantic="expectation",
    ),
    EvdsSeries(
        code="TP.KAVRAMSAL.HAMM2.INDX",
        label="M2 para arzı (kur etkisinden arındırılmamış)",
        metric="other",
        unit="",
        expected_name_contains="m2",
        verified=True,
        qualifier="haftalık (cuma); birim TCMB tarafından beyan edilmiyor",
    ),
)


# ---------------------------------------------------------------------------
# Dönem normalizasyonu
# ---------------------------------------------------------------------------
# EVDS tarih alanını serinin sıklığına göre farklı biçimlerde döndürür:
#   günlük    "18-08-2026"
#   aylık     "2026-8"   veya "08-2026"
#   çeyreklik "2026-Q3"
#   yıllık    "2026"
# Projenin dönem sözlüğü `nlp/claims.py` ile aynı olmalıdır: YYYY-MM,
# YYYY-Qn, YYYY. Aksi hâlde R3 karşılaştırması dönem eşleşmesinde
# başarısız olur ve doğrulanmış sayı boşa gider.
_GUNLUK = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")
_AYLIK_TIRE = re.compile(r"^(\d{4})-(\d{1,2})$")
_AYLIK_TERS = re.compile(r"^(\d{1,2})-(\d{4})$")
_CEYREK = re.compile(r"^(\d{4})-?[Qq](\d)$")
_YILLIK = re.compile(r"^(\d{4})$")


def normalize_period(raw: str) -> str | None:
    """EVDS tarih alanını projenin dönem biçimine çevirir.

    Tanınmayan biçimde **None** döner ve öğe üretilmez. Tahmin edilmez:
    yanlış bir dönem, R3'ün doğru sayıyı yanlış yayıma bağlaması demektir.
    """
    text = (raw or "").strip()
    if not text:
        return None

    if m := _GUNLUK.match(text):
        gun, ay, yil = m.groups()
        return f"{yil}-{int(ay):02d}-{int(gun):02d}"
    if m := _CEYREK.match(text):
        return f"{m.group(1)}-Q{m.group(2)}"
    if m := _AYLIK_TIRE.match(text):
        yil, ay = m.groups()
        if 1 <= int(ay) <= 12:
            return f"{yil}-{int(ay):02d}"
        return None
    if m := _AYLIK_TERS.match(text):
        ay, yil = m.groups()
        if 1 <= int(ay) <= 12:
            return f"{yil}-{int(ay):02d}"
        return None
    if m := _YILLIK.match(text):
        return m.group(1)
    return None


def parse_value(raw: Any) -> float | None:
    """EVDS sayısını float'a çevirir. Boş/eksik gözlem **None** döner.

    EVDS eksik gözlemi `null`, `""` veya `"ND"` olarak döndürebilir.
    Üçü de "veri yok" demektir ve 0.0'a çevrilmesi felakettir: sıfır,
    kanıt motoruna gerçek bir gözlem gibi görünür.
    """
    if raw is None:
        return None
    if isinstance(raw, int | float):
        return round(float(raw), 4)
    text = str(raw).strip()
    if not text or text.upper() in {"ND", "NA", "N/A", "-", "NULL"}:
        return None
    # EVDS ondalık ayırıcı olarak nokta kullanır; binlik ayırıcı gelmez.
    try:
        return round(float(text), 4)
    except ValueError:
        return None


@dataclass
class EvdsAdapter(FailureRecorder):
    """İzlenen EVDS serilerinin son gözlemini yayın birimine çevirir."""

    slug: str = "tcmb-evds"
    http: HttpClient | None = None
    series: tuple[EvdsSeries, ...] = TRACKED
    lookback_days: int = LOOKBACK_DAYS
    _owns_http: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        super().__init__()
        if self.http is None:
            # EVDS hız sınırı uygular ve yoğun saatlerde yavaşlar;
            # yeniden deneme burada isteğe bağlı değil.
            self.http = HttpClient(respect_robots=False, timeout=60.0, max_retries=4)
            self._owns_http = True

    # ---------------------------------------------------------------- fetch
    def fetch(self) -> list[RawItem]:
        pending = [s for s in self.series if s.verified]
        skipped = [s for s in self.series if not s.verified]

        if skipped:
            # Sessizce atlanmaz: doğrulanmamış seri bir EKSİKLİKTİR ve
            # kaynak sağlık panosunda görünmelidir.
            self.note_failure(
                f"{len(skipped)} EVDS serisi doğrulanmadığı için atlandı "
                f"({', '.join(s.code for s in skipped)}). "
                "Doğrulamak için: python -m scripts.probe_evds"
            )

        if not pending:
            return []

        try:
            key = api_key()
        except EvdsAuthError as exc:
            # Eksik yapılandırma ile ağ arızası ayrı şeylerdir; anahtar
            # yokluğunu ağ hatası gibi raporlamak kullanıcıyı yanlış yere
            # gönderir (`tuik_auth.py` ile aynı gerekçe).
            self.record_failure("evds:auth", exc)
            log.warning("evds_api_key_missing")
            return []

        items: list[RawItem] = []
        for spec in pending:
            try:
                item = self._fetch_one(spec, key)
            except Exception as exc:  # noqa: BLE001 — bir seri diğerlerini düşürmez
                self.record_failure(spec.code, exc)
                log.warning(
                    "evds_series_failed",
                    code=spec.code,
                    metric=spec.metric,
                    error=type(exc).__name__,
                    detail=str(exc)[:200],
                )
                continue
            if item is not None:
                items.append(item)
        return items

    # ---------------------------------------------------------------- HTTP
    def data_url(self, spec: EvdsSeries, *, today: date | None = None) -> str:
        end = today or datetime.now(UTC).date()
        start = date.fromordinal(max(end.toordinal() - self.lookback_days, 1))
        return (
            f"{EVDS_BASE}/series={spec.code}"
            f"&startDate={start:%d-%m-%Y}&endDate={end:%d-%m-%Y}"
            f"&type=json"
        )

    def _fetch_one(self, spec: EvdsSeries, key: str) -> RawItem | None:
        assert self.http is not None

        url = self.data_url(spec)
        response = self.http.get(url, headers={"key": key}, source_slug=self.slug)

        status = getattr(response, "status_code", 200)
        if status in (401, 403):
            raise EvdsAuthError(f"EVDS anahtarı reddedildi (HTTP {status}).")

        observations = self._parse_payload(response.text, spec)
        if not observations:
            log.warning("evds_no_observation", code=spec.code, metric=spec.metric)
            return None

        return self._build_item(spec, observations, url)

    # ------------------------------------------------------------- parsing
    def _parse_payload(self, body: str, spec: EvdsSeries) -> list[tuple[str, float]]:
        """Gövdeyi (dönem, değer) çiftlerine çevirir — eskiden yeniye sıralı.

        HTML gövdesi burada **istisnaya** dönüşür. Sebebi modül başlığında:
        EVDS anahtarsız istekte 200 + SPA kabuğu döndürüyor ve bu depo
        aynı sessiz arızayı iki kez yaşadı (B-42, B-43).
        """
        import json

        text = (body or "").strip()
        if not text:
            raise EvdsResponseError(f"{spec.code}: EVDS boş gövde döndürdü.")

        onek = text.lstrip()[:200].lower()
        if onek.startswith(("<!doctype html", "<html")):
            raise EvdsResponseError(
                f"{spec.code}: EVDS HTML döndürdü (beklenen JSON). "
                "Anahtar geçersiz ya da eksik olabilir — uç, yetkisiz "
                "istekte HTTP 200 ile SPA kabuğu döndürüyor."
            )

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise EvdsResponseError(
                f"{spec.code}: EVDS yanıtı JSON değil: {str(exc)[:120]}"
            ) from exc

        if not isinstance(payload, dict):
            raise EvdsResponseError(f"{spec.code}: EVDS yanıtı beklenen nesne değil.")

        rows = payload.get("items")
        if rows is None:
            raise EvdsResponseError(
                f"{spec.code}: EVDS yanıtında 'items' alanı yok "
                f"(gelen alanlar: {sorted(payload)[:6]})."
            )
        if not isinstance(rows, list):
            raise EvdsResponseError(f"{spec.code}: 'items' bir liste değil.")

        out: list[tuple[str, float]] = []
        taninmayan_donem = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            ham_tarih = row.get("Tarih") or row.get("TARIH") or row.get("tarih")
            period = normalize_period(str(ham_tarih or ""))
            if period is None:
                taninmayan_donem += 1
                continue
            value = self._read_value(row, spec)
            if value is None:
                continue  # eksik gözlem: 0.0 yapılmaz, atlanır
            out.append((period, value))

        if taninmayan_donem:
            log.warning(
                "evds_unparsed_periods",
                code=spec.code,
                count=taninmayan_donem,
            )

        if rows and not out:
            # Satır var ama tek bir kullanılabilir gözlem çıkmadı: sütun adı
            # değişmiş olabilir. Sessiz sıfır yerine gürültülü hata.
            ornek = sorted(rows[0]) if isinstance(rows[0], dict) else []
            raise EvdsResponseError(
                f"{spec.code}: {len(rows)} satır geldi ama gözlem çıkarılamadı. "
                f"Beklenen sütun '{spec.response_key}', gelen sütunlar: {ornek[:8]}"
            )

        out.sort(key=lambda pair: pair[0])
        return out

    def _read_value(self, row: dict[str, Any], spec: EvdsSeries) -> float | None:
        """Satırdan serinin değerini okur.

        Sütun adı dönüşümü (nokta -> alt çizgi) EVDS'nin belgelenmemiş
        davranışıdır; tek bir ada güvenmek kırılgan olurdu. Birkaç aday
        denenir, sonra `Tarih`/`UNIXTIME` dışındaki tek sayısal sütuna
        düşülür — seri zaten tek tek istendiği için o sütun bu seridir.
        """
        adaylar = (spec.response_key, spec.code, spec.response_key.upper())
        for ad in adaylar:
            if ad in row:
                return parse_value(row[ad])

        artanlar = [
            k for k in row if k.lower() not in {"tarih", "unixtime", "yearweek", "yearmonth"}
        ]
        if len(artanlar) == 1:
            return parse_value(row[artanlar[0]])
        return None

    # -------------------------------------------------------------- item
    def _build_item(
        self, spec: EvdsSeries, observations: list[tuple[str, float]], url: str
    ) -> RawItem:
        period, value = observations[-1]
        previous = observations[-2][1] if len(observations) >= 2 else None

        pretty = f"{value:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
        deger_metni = f"%{pretty}" if spec.unit == "%" else f"{pretty} {spec.unit}".strip()
        donem_metni = _donem_metni(period)

        baslik = f"{spec.label}, {donem_metni}: {deger_metni}"
        ozet = (
            f"TCMB EVDS, {donem_metni} dönemi için {spec.label.lower()} değerini "
            f"{deger_metni} olarak yayımladı"
            + (f" ({spec.qualifier})." if spec.qualifier else ".")
        )

        return RawItem(
            source_slug=self.slug,
            # Dönemi taşıyan KANONİK adres: aynı yayım iki kez öğe üretmez
            # (tekilleştirme buna bakar), yeni dönem ayrı öğedir.
            url=f"{url}&_metric={spec.metric}&_series={spec.code}&_period={period}",
            title=baslik,
            # Referans dönemi DEĞİL, "bizim için yayımlandığı an" — EVDS bu
            # uçta yayım anını vermiyor. `tuik_sdmx.py` ile aynı gerekçe:
            # dönemi published_at yapmak veriyi haftalarca eski gösterip
            # akışın dibine gömerdi. Dönem başlıkta ve `extra`da duruyor.
            published_at=datetime.now(UTC),
            summary=ozet,
            guid=f"evds:{spec.code}:{period}",
            extra={
                "normalized_value": {
                    "metric": spec.metric,
                    "value": value,
                    "unit": spec.unit,
                    "period": period,
                    # Köken (provenance). `metric` tek başına yetmiyor:
                    # USD/TRY ile EUR/TRY'nin ikisi de `exchange_rate`
                    # ve ayırt edilmezlerse gösterge şeridi iki farklı
                    # büyüklüğü TEK SERİ gibi çizer.
                    "series_code": spec.code,
                    "series_label": spec.label,
                    # Epistemik tür: R3 yalnızca `measurement` kabul eder.
                    "semantic": spec.semantic,
                    "source": "TCMB EVDS",
                    "source_url": url,
                    "retrieved_at": datetime.now(UTC).isoformat(),
                },
                "previous_value": previous,
                "observation_count": len(observations),
                "reference_period": period,
            },
        )

    def close(self) -> None:
        if self._owns_http and self.http is not None:
            self.http.close()


_AYLAR_TR: Final[tuple[str, ...]] = (
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


def _donem_metni(period: str) -> str:
    """`2026-08-18` -> `18 Ağustos 2026` · `2026-08` -> `Ağustos 2026`."""
    parcalar = period.split("-")
    if len(parcalar) == 3 and all(p.isdigit() for p in parcalar):
        yil, ay, gun = parcalar
        return f"{int(gun)} {_AYLAR_TR[int(ay) - 1]} {yil}"
    if len(parcalar) == 2 and parcalar[1].isdigit() and 1 <= int(parcalar[1]) <= 12:
        return f"{_AYLAR_TR[int(parcalar[1]) - 1]} {parcalar[0]}"
    return period


registry.register("evds", EvdsAdapter)
