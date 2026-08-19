"""Gösterge anomali tespiti (Roadmap Faz 3.1).

-----------------------------------------------------------------------
⛔ ANOMALİ BİR YORUM DEĞİLDİR
-----------------------------------------------------------------------

Bu modül yalnızca şunu söyler: *bir gözlem, kendi geçmişine göre
yapılandırılmış bir eşiği aştı.* Söylemediği şeyler:

    "sebebi şu"                        -> nedensellik; kanıt ister
    "bu siyasi olarak önemli"          -> ayrı bir boyut (salience)
    "bu kötü/iyi"                      -> yorum

Katmanlar ayrı tutulur ve birbirine karıştırılmaz:

    GÖZLEM  ->  İSTATİSTİKSEL ANOMALİ  ->  SİNYAL  ->  KANIT  ->  YORUM

"USD/TRY bir dönemde %4,2 hareket etti" bir gözlemdir.
"%4,2 yapılandırılmış eşiği aşıyor" bir anomalidir.
"Sebebi X" bir yorumdur ve bu modülün işi değildir.

-----------------------------------------------------------------------
YÖNTEM SEÇİMİ — TEK BİR YÖNTEM EVRENSEL DOĞRU DEĞİL
-----------------------------------------------------------------------

Faz 3 yetkisi z-skoru finansal serilere körlemesine uygulamayı açıkça
yasaklıyor ve haklı: kur serileri **durağan değildir** (trendlidir),
seviyeler üzerinde z-skoru trendi anomali sanar. Bu yüzden yöntem seri
karakterine göre seçilir:

┌─────────────────┬──────────────────────┬────────────────────────────┐
│ seri tipi       │ yöntem               │ neden                      │
├─────────────────┼──────────────────────┼────────────────────────────┤
│ günlük finansal │ getiri + MAD         │ Seviye trendli, GETİRİ     │
│ (USD, EUR, M2)  │ (`return_mad`)       │ yaklaşık durağandır. MAD   │
│                 │                      │ aykırı değerden std'den    │
│                 │                      │ çok daha az etkilenir —    │
│                 │                      │ tek bir sıçrama eşiği      │
│                 │                      │ şişirip sonraki gerçek     │
│                 │                      │ sıçramayı gizlemez.        │
├─────────────────┼──────────────────────┼────────────────────────────┤
│ politika faizi  │ mutlak değişim       │ Basamak fonksiyonu: aylarca│
│                 │ (`absolute_change`)  │ sabit, sonra sıçrar. MAD   │
│                 │                      │ sıfıra iner ve HER değişim │
│                 │                      │ sonsuz sapma olur. Faizde  │
│                 │                      │ anlamlı soru zaten "kaç    │
│                 │                      │ puan değişti".             │
├─────────────────┼──────────────────────┼────────────────────────────┤
│ aylık gösterge  │ dönemsel değişim +   │ Az gözlem (65 civarı),     │
│ (rezerv, anket) │ MAD (`change_mad`)   │ seviye trendli. Değişim    │
│                 │                      │ üzerinden MAD, küçük       │
│                 │                      │ örneklemde std'den sağlam. │
└─────────────────┴──────────────────────┴────────────────────────────┘

Her yöntemin gerektirdiği asgari geçmiş, duyarlılığı ve arıza kipleri
kendi `Method` tanımında yazılıdır.

-----------------------------------------------------------------------
SOĞUK BAŞLANGIÇ VE EKSİK VERİ
-----------------------------------------------------------------------

**Yetersiz geçmiş anomali ÜRETMEZ.** Uydurma gözlemle pencere
doldurulmaz. Durum açıkça `insufficient_history` döner.

**Eksik veri sıfır DEĞİLDİR.** Bir gözlemin olmaması, göstergenin sıfıra
düşmesi anlamına gelmez ve asla sayıya çevrilmez. Ayrı durumlar:

    normal               ölçüldü, eşik altında
    anomalous            ölçüldü, eşik aşıldı
    insufficient_history geçmiş yetersiz — ölçülemedi
    stale                seri var ama son gözlem bayat
    unavailable          seri hiç gözlem taşımıyor

⛔ Bu modül `politikdesk.llm` import ETMEZ. Bir anomalinin var olup
olmadığına yapay zekâ karar veremez; kanıt motorunun LLM yasağıyla
(Spec §8.1) aynı gerekçe.
"""

from __future__ import annotations

import hashlib
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal

from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)

DetectionState = Literal[
    "normal", "anomalous", "insufficient_history", "stale", "unavailable"
]
Severity = Literal["low", "medium", "high", "critical"]

# MAD'i standart sapmaya çeviren sabit (normal dağılım varsayımı altında).
# Eşiklerin "kaç sigma" diye okunabilmesini sağlar.
MAD_TO_SIGMA: Final[float] = 1.4826

# MAD sıfıra çok yakınsa bölme patlar ve her kıpırtı sonsuz sapma olur.
# Bu taban, "hiç oynamayan bir seride en küçük hareket bile anomali"
# saçmalığını engeller.
MIN_SCALE: Final[float] = 1e-9


@dataclass(frozen=True)
class Method:
    """Bir temel çizgi yöntemi ve onu kullanılabilir kılan koşullar."""

    key: str
    label: str
    min_history: int
    """Altında ANOMALİ ÜRETİLMEZ. Uydurma veriyle doldurulmaz."""
    window: int
    """Temel çizginin bakacağı en fazla gözlem sayısı."""
    threshold: float
    rationale: str
    failure_modes: str
    min_material_change: float = 0.0
    """İSTATİSTİKSEL ANLAMLILIK ≠ MADDİ ANLAMLILIK.

    Bu taban altındaki hareket, temel çizgi ne kadar sessiz olursa olsun
    anomali sayılmaz.

    Gerekçe ölçülmüştür (19 Ağu 2026 geriye dönük taraması). USD/TRY
    yönetimli kur rejiminde: günlük getiriler %0,04 çevresinde kümeleniyor
    ve MAD %0,0096. Bu ölçekte **%0,22'lik** bir hareket — ekonomik olarak
    önemsiz — `+12,5 sigma` çıkıyordu. Tespit matematiksel olarak doğru,
    pratikte işe yaramazdı: hiçbir analist %0,22'lik kur hareketini
    haber saymaz.

    Taban, "temel çizgi sessizdi" gerekçesiyle önemsiz hareketin sinyal
    üretmesini engeller.
    """
    severity_scale: float = 0.0
    """Şiddet hesabının ölçeği. 0 ise `threshold` kullanılır.

    `absolute_change` için ayrı ölçek şart: eşik "gerçek bir hareket var
    mı" sorusunu yanıtlar (0,25 puan), şiddet ise "ne kadar büyük"
    sorusunu. İkisi karıştırıldığında 27 faiz değişiminin 26'sı
    `critical` çıkıyordu — yani şiddet hiçbir şey ayırt etmiyordu.
    """


METHODS: Final[dict[str, Method]] = {
    "return_mad": Method(
        key="return_mad",
        label="Getiri + MAD",
        # 30 iş günü: bir aylık oynaklık rejimini temsil eder. Daha kısa
        # pencere tek bir hareketli günü "normal" sayar.
        min_history=30,
        window=90,
        threshold=4.0,  # ~4 sigma eşdeğeri
        # %1'lik günlük hareket: yönetimli kur rejiminde bile haber
        # değeri taşıyan eşik. Altındaki hareket, temel çizgi ne kadar
        # sessiz olursa olsun sinyal üretmez.
        min_material_change=1.0,
        rationale=(
            "Kur ve endeks serileri trendlidir (durağan değil); seviyeler "
            "üzerinde z-skoru trendin kendisini anomali sanar. Yüzde getiri "
            "yaklaşık durağandır. Ölçek olarak MAD kullanılır çünkü standart "
            "sapma tek bir sıçramadan sonra şişer ve SONRAKİ gerçek sıçramayı "
            "gizler — finansal seride en sık görülen sessiz arıza budur."
        ),
        failure_modes=(
            "Rejim değişiminde (kur çıpası kaldırılması gibi) yeni oynaklık "
            "bir süre anomali üretir; bu yanlış değil, geçicidir. Çok düşük "
            "oynaklıkta MAD tabana iner ve küçük hareketler büyük görünür — "
            "MIN_SCALE bunu sınırlar."
        ),
    ),
    "absolute_change": Method(
        key="absolute_change",
        label="Mutlak değişim",
        min_history=2,
        window=24,
        # 0,25 puan: "gerçek bir politika hareketi var mı" eşiği.
        # Yuvarlama gürültüsünü eler, 25 baz puanlık gerçek adımı geçirir.
        threshold=0.25,
        min_material_change=0.25,
        # Şiddet AYRI ölçekte: TCMB adımları 100-500 baz puandır.
        # Eşikle aynı ölçek kullanılınca 27 değişimin 26'sı `critical`
        # çıkıyordu — şiddet hiçbir şey ayırt etmiyordu. 2,5 puan
        # ölçeğinde 50bp `low`, 500bp `critical` olur.
        severity_scale=2.5,
        rationale=(
            "Politika faizi bir BASAMAK fonksiyonudur: aylarca sabit kalır, "
            "sonra sıçrar. Sabit dönemde MAD sıfıra iner ve her değişim "
            "sonsuz sapma olur — istatistiksel yöntem burada anlamsızdır. "
            "Faizde anlamlı soru zaten 'kaç puan değişti' sorusudur ve eşik "
            "doğrudan puan cinsindendir."
        ),
        failure_modes=(
            "Eşik para birimi/ölçek duyarlıdır: yüzde puanı için 0,25 "
            "anlamlıdır, endeks için değildir. Yalnızca oran serilerinde "
            "kullanılmalı."
        ),
    ),
    "change_mad": Method(
        key="change_mad",
        label="Dönemsel değişim + MAD",
        # 12 gözlem = aylık seride bir yıl. Altında mevsimsellik ile
        # gerçek sapma ayrılamaz.
        min_history=12,
        window=36,
        threshold=4.0,
        # Aylık göstergelerde %2'lik dönemsel değişim: rezerv ve anket
        # serilerinde gürültüden ayrılan en küçük anlamlı hareket.
        min_material_change=2.0,
        rationale=(
            "Aylık göstergelerde gözlem az (ölçülen: 65 civarı) ve seviye "
            "trendlidir. Dönemden döneme DEĞİŞİM üzerinden MAD, küçük "
            "örneklemde standart sapmadan sağlamdır ve trendi anomali "
            "saymaz."
        ),
        failure_modes=(
            "Güçlü mevsimsellik taşıyan serilerde (turizm, tarım) mevsim "
            "etkisi anomali görünebilir; bu seriler eklenirse mevsimsel "
            "düzeltme gerekir. Şu an izlenenlerde belirgin mevsimsellik yok."
        ),
    ),
}

# Frekanstan yönteme varsayılan eşleme. `indicator_series.method` alanı
# 'auto' değilse o kazanır — seri bazında istisna mümkün.
_FREQUENCY_DEFAULT: Final[dict[str, str]] = {
    "daily": "return_mad",
    "weekly": "return_mad",
    "monthly": "change_mad",
    "quarterly": "change_mad",
    "yearly": "change_mad",
}

# Metrik bazlı istisna: politika faizi hangi frekansta gelirse gelsin
# basamak fonksiyonudur.
_METRIC_OVERRIDE: Final[dict[str, str]] = {
    "policy_rate": "absolute_change",
    "overnight_lending_rate": "absolute_change",
    "overnight_borrowing_rate": "absolute_change",
}

# Bayatlık bütçesi: bu süre geçtiyse seri "stale". Frekansa bağlıdır —
# aylık bir seriye günlük ölçüt uygulamak onu sürekli bayat gösterirdi.
_STALE_BUDGET: Final[dict[str, timedelta]] = {
    "daily": timedelta(days=5),      # hafta sonu + resmî tatil payı
    "weekly": timedelta(days=14),
    "monthly": timedelta(days=70),
    "quarterly": timedelta(days=200),
    "yearly": timedelta(days=500),
}
_DEFAULT_STALE = timedelta(days=90)


def resolve_method(metric: str, frequency: str, configured: str = "auto") -> Method:
    """Seri için kullanılacak yöntemi belirler."""
    if configured and configured != "auto" and configured in METHODS:
        return METHODS[configured]
    if metric in _METRIC_OVERRIDE:
        return METHODS[_METRIC_OVERRIDE[metric]]
    return METHODS[_FREQUENCY_DEFAULT.get(frequency, "change_mad")]


# ---------------------------------------------------------------------------
# İstatistik — küçük ve açık. Harici bağımlılık yok.
# ---------------------------------------------------------------------------
def median_absolute_deviation(values: Sequence[float]) -> tuple[float, float]:
    """(medyan, MAD) döner. MAD ölçek tahminidir, standart sapma değil."""
    if not values:
        return 0.0, 0.0
    med = statistics.median(values)
    mad = statistics.median([abs(v - med) for v in values])
    return med, mad


def _pct_returns(values: Sequence[float]) -> list[float]:
    """Ardışık yüzde değişim. Sıfır bölme güvenli — sıfır atlanır.

    Sıfır bir gözlem SİLİNMEZ (meşru olabilir, ör. bütçe dengesi);
    yalnızca ondan getiri hesaplanamaz.
    """
    out: list[float] = []
    # Kaydırmalı eşleme: uzunluklar BİLEREK farklı (n ve n-1).
    for onceki, simdi in zip(values, values[1:], strict=False):
        if onceki == 0:
            continue
        out.append((simdi - onceki) / abs(onceki) * 100.0)
    return out


def _diffs(values: Sequence[float]) -> list[float]:
    return [b - a for a, b in zip(values, values[1:], strict=False)]


@dataclass(frozen=True)
class Detection:
    """Tek bir gözlemin değerlendirme sonucu — yeniden hesaplanabilir."""

    state: DetectionState
    method: str
    observed_value: float
    expected_value: float | None = None
    deviation: float = 0.0
    deviation_ratio: float | None = None
    threshold: float = 0.0
    baseline_window: int = 0
    baseline_size: int = 0
    severity: Severity | None = None
    reason: str = ""

    @property
    def is_anomaly(self) -> bool:
        return self.state == "anomalous"


def _severity(ratio: float, threshold: float) -> Severity:
    """Şiddet, ölçülen sapmanın eşiğe oranından türer.

    ⛔ Şiddet SİYASİ ÖNEM DEĞİLDİR. 'critical' bir kur hareketi, siyasi
    olarak önemsiz olabilir; tersi de doğrudur. Siyasi önem ayrı bir
    boyuttur (salience) ve bu sayıyla çarpılmaz.
    """
    kat = abs(ratio) / threshold if threshold else 0.0
    if kat >= 3.0:
        return "critical"
    if kat >= 2.0:
        return "high"
    if kat >= 1.5:
        return "medium"
    return "low"


def detect(
    values: Sequence[float],
    method: Method,
    *,
    now_value: float | None = None,
) -> Detection:
    """Serinin SON gözlemini kendi geçmişine göre değerlendirir.

    `values` eskiden yeniye sıralı olmalıdır; son eleman değerlendirilen
    gözlemdir (`now_value` verilirse o kullanılır).
    """
    temiz = [v for v in values if _is_finite(v)]
    if len(temiz) != len(values):
        # NaN/sonsuz bir gözlem VERİ DEĞİLDİR. Sessizce atılmaz, sayılır.
        log.warning("anomaly_non_finite_dropped", dropped=len(values) - len(temiz))

    if not temiz:
        return Detection("unavailable", method.key, 0.0, reason="gözlem yok")

    gozlenen = now_value if now_value is not None else temiz[-1]
    if not _is_finite(gozlenen):
        return Detection("unavailable", method.key, 0.0, reason="gözlem sonlu değil")

    if len(temiz) < method.min_history:
        return Detection(
            "insufficient_history",
            method.key,
            gozlenen,
            baseline_size=len(temiz),
            threshold=method.threshold,
            baseline_window=method.window,
            reason=f"{len(temiz)}/{method.min_history} gözlem — temel çizgi kurulamaz",
        )

    pencere = temiz[-method.window :]

    if method.key == "absolute_change":
        onceki = pencere[-2]
        sapma = gozlenen - onceki
        asildi = abs(sapma) >= method.threshold
        # Şiddet AYRI ölçekte hesaplanır (bkz. `Method.severity_scale`):
        # eşik "hareket var mı", ölçek "ne kadar büyük" sorusunu yanıtlar.
        olcek = method.severity_scale or method.threshold
        return Detection(
            "anomalous" if asildi else "normal",
            method.key,
            gozlenen,
            expected_value=onceki,
            deviation=round(sapma, 6),
            deviation_ratio=round(sapma / method.threshold, 4) if method.threshold else None,
            threshold=method.threshold,
            baseline_window=method.window,
            baseline_size=len(pencere),
            severity=_severity(sapma / olcek, 1.0) if asildi else None,
            reason=f"önceki {onceki:g} -> {gozlenen:g} (değişim {sapma:+g})",
        )

    # MAD tabanlı iki yöntem: fark serisi üzerinde çalışır.
    seri = _pct_returns(pencere) if method.key == "return_mad" else _diffs(pencere)
    if len(seri) < method.min_history - 1:
        return Detection(
            "insufficient_history",
            method.key,
            gozlenen,
            baseline_size=len(seri),
            threshold=method.threshold,
            baseline_window=method.window,
            reason=f"{len(seri)} fark gözlemi — temel çizgi kurulamaz",
        )

    # Değerlendirilen gözlemin kendi farkı temel çizgiye DÂHİL EDİLMEZ:
    # anomalinin kendi eşiğini yükseltmesi, tespiti köreltir.
    guncel = seri[-1]
    gecmis = seri[:-1]
    med, mad = median_absolute_deviation(gecmis)
    olcek = max(mad * MAD_TO_SIGMA, MIN_SCALE)
    oran = (guncel - med) / olcek

    # İKİ KOŞUL BİRDEN aranır: istatistiksel VE maddi.
    #
    # Yalnızca istatistiksel koşul arandığında ölçülen sonuç şuydu
    # (19 Ağu 2026, USD/TRY): yönetimli kur rejiminde günlük getiriler
    # %0,04 çevresinde kümelenir, MAD %0,0096'ya iner ve **%0,22'lik**
    # bir hareket +12,5 sigma çıkar. Matematik doğru, sinyal değersiz —
    # hiçbir analist %0,22'lik kur hareketini haber saymaz.
    #
    # Maddi taban, "temel çizgi sessizdi" gerekçesiyle önemsiz hareketin
    # sinyal üretmesini engeller.
    istatistiksel = abs(oran) >= method.threshold
    maddi = abs(guncel) >= method.min_material_change
    asildi = istatistiksel and maddi

    beklenen = pencere[-2] * (1 + med / 100.0) if method.key == "return_mad" else pencere[-2] + med

    return Detection(
        "anomalous" if asildi else "normal",
        method.key,
        gozlenen,
        expected_value=round(beklenen, 6),
        deviation=round(guncel - med, 6),
        deviation_ratio=round(oran, 4),
        threshold=method.threshold,
        baseline_window=method.window,
        baseline_size=len(gecmis),
        severity=_severity(oran, method.threshold) if asildi else None,
        reason=(
            f"değişim {guncel:+.4g} · temel medyan {med:+.4g} · "
            f"ölçek {olcek:.4g} · {oran:+.2f}σ (eşik {method.threshold}σ)"
            + ("" if maddi else f" · maddi taban {method.min_material_change:g} altında")
        ),
    )


def _is_finite(v: Any) -> bool:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return f == f and f not in (float("inf"), float("-inf"))


def signature(series_code: str, period: str, method: str, value: float) -> str:
    """Anomalinin deterministik kimliği.

    Değişmeyen bir gözlemin tekrar işlenmesi YENİ KAYIT ÜRETMEZ. Değer
    revize edilirse imza değişir; eski kayıt `superseded` olur ve
    denetlenebilirlik korunur.
    """
    ham = f"{series_code}|{period}|{method}|{value!r}"
    return hashlib.sha1(ham.encode("utf-8")).hexdigest()[:24]  # noqa: S324 — kriptografik değil


def staleness(frequency: str, last_observed: datetime | None) -> tuple[bool, str]:
    """Seri bayat mı? Bütçe frekansa bağlıdır."""
    if last_observed is None:
        return True, "hiç gözlem yok"
    butce = _STALE_BUDGET.get(frequency, _DEFAULT_STALE)
    yas = datetime.now(UTC) - last_observed
    return yas > butce, f"{yas.days} gün önce (bütçe {butce.days} gün)"


# ---------------------------------------------------------------------------
# Veritabanı yolu
# ---------------------------------------------------------------------------
def evaluate_series(series_id: int) -> Detection:
    """Tek bir serinin son gözlemini değerlendirir (yalnızca okur)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT metric, frequency, method, series_code FROM indicator_series WHERE id = %s",
            (series_id,),
        )
        seri = cur.fetchone()
        if seri is None:
            return Detection("unavailable", "-", 0.0, reason="seri yok")

        method = resolve_method(seri["metric"], seri["frequency"], seri["method"])
        cur.execute(
            """
            SELECT value, period, observed_at FROM indicator_observations
            WHERE series_id = %s AND superseded_at IS NULL
            ORDER BY period DESC LIMIT %s
            """,
            (series_id, method.window),
        )
        satirlar = list(reversed([dict(r) for r in cur.fetchall()]))

    if not satirlar:
        return Detection("unavailable", method.key, 0.0, reason="gözlem yok")

    bayat, aciklama = staleness(seri["frequency"], satirlar[-1]["observed_at"])
    if bayat:
        return Detection(
            "stale",
            method.key,
            float(satirlar[-1]["value"]),
            baseline_size=len(satirlar),
            threshold=method.threshold,
            baseline_window=method.window,
            reason=aciklama,
        )

    return detect([float(r["value"]) for r in satirlar], method)
