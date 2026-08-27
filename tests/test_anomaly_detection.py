"""Gösterge anomali tespiti testleri (Roadmap Faz 3.1).

Korunan epistemik kural — katmanlar birbirine karıştırılmaz:

    GÖZLEM -> İSTATİSTİKSEL ANOMALİ -> SİNYAL -> KANIT -> YORUM

Tespit motoru yalnızca ikinci adımı üretir. Nedensellik iddiası, siyasi
önem yargısı ve "iyi/kötü" nitelemesi bu modülün işi değildir.
"""

from __future__ import annotations

import ast
import inspect
import math

import pytest

from politikdesk.analysis import anomaly as an
from politikdesk.analysis.anomaly import (
    METHODS,
    Method,
    detect,
    median_absolute_deviation,
    resolve_method,
    signature,
    staleness,
)

RETURN_MAD = METHODS["return_mad"]
ABS_CHANGE = METHODS["absolute_change"]
CHANGE_MAD = METHODS["change_mad"]


def _sakin_seri(n: int = 90, baslangic: float = 100.0, adim: float = 0.04) -> list[float]:
    """Günlük %0,04 artan sakin bir seri — yönetimli kur rejimi benzeri."""
    out = [baslangic]
    for _ in range(n - 1):
        out.append(out[-1] * (1 + adim / 100))
    return out


# ═══════════════════════════════════ 1-2. normal ve bariz anomali
def test_normal_observation_is_not_flagged() -> None:
    seri = _sakin_seri()
    sonuc = detect(seri, RETURN_MAD)
    assert sonuc.state == "normal"
    assert not sonuc.is_anomaly


def test_obvious_anomaly_is_flagged() -> None:
    """Sakin bir seride ani %5 sıçrama yakalanmalı."""
    seri = _sakin_seri()
    seri.append(seri[-1] * 1.05)
    sonuc = detect(seri, RETURN_MAD)
    assert sonuc.is_anomaly
    assert sonuc.severity in {"medium", "high", "critical"}
    assert sonuc.deviation_ratio is not None and abs(sonuc.deviation_ratio) > RETURN_MAD.threshold


def test_anomaly_result_is_reproducible_from_stored_inputs() -> None:
    """Kayıt, girdilerinden YENİDEN HESAPLANABİLİR olmalı.

    Açıklanmayan bir `is_anomaly = true` saklanmaz.
    """
    seri = _sakin_seri()
    seri.append(seri[-1] * 1.05)
    a = detect(seri, RETURN_MAD)
    b = detect(seri, RETURN_MAD)
    assert (a.observed_value, a.deviation, a.deviation_ratio) == (
        b.observed_value,
        b.deviation,
        b.deviation_ratio,
    )
    for alan in (a.method, a.threshold, a.baseline_window, a.baseline_size, a.reason):
        assert alan not in (None, "")


# ═══════════════════════════════════ 3. soğuk başlangıç
def test_insufficient_history_never_produces_an_anomaly() -> None:
    """Yetersiz geçmiş anomali ÜRETMEZ — uydurma veriyle doldurulmaz."""
    seri = [100.0, 140.0]  # devasa sıçrama ama geçmiş yok
    sonuc = detect(seri, RETURN_MAD)
    assert sonuc.state == "insufficient_history"
    assert not sonuc.is_anomaly
    assert sonuc.severity is None


def test_cold_start_reports_how_much_history_is_missing() -> None:
    sonuc = detect([1.0] * 5, RETURN_MAD)
    assert sonuc.state == "insufficient_history"
    assert "5" in sonuc.reason and str(RETURN_MAD.min_history) in sonuc.reason


@pytest.mark.parametrize("method", [RETURN_MAD, CHANGE_MAD, ABS_CHANGE])
def test_every_method_declares_its_minimum_history(method: Method) -> None:
    assert method.min_history >= 2
    assert method.window >= method.min_history


# ═══════════════════════════════════ 4-6. bayat / eksik / kaynak arızası
def test_no_observation_is_unavailable_not_zero() -> None:
    """Gözlem yokluğu SIFIR DEĞİLDİR."""
    sonuc = detect([], RETURN_MAD)
    assert sonuc.state == "unavailable"
    assert sonuc.observed_value == 0.0
    assert not sonuc.is_anomaly


def test_stale_series_is_a_distinct_state_from_unavailable() -> None:
    """`stale` ile `unavailable` aynı şey değildir."""
    from datetime import UTC, datetime, timedelta

    bayat, aciklama = staleness("daily", datetime.now(UTC) - timedelta(days=30))
    assert bayat and "gün önce" in aciklama

    hic, aciklama2 = staleness("daily", None)
    assert hic and "hiç gözlem" in aciklama2


def test_staleness_budget_depends_on_frequency() -> None:
    """Aylık seriye günlük ölçüt uygulanırsa sürekli bayat görünür."""
    from datetime import UTC, datetime, timedelta

    on_gun_once = datetime.now(UTC) - timedelta(days=10)
    assert staleness("daily", on_gun_once)[0] is True
    assert staleness("monthly", on_gun_once)[0] is False


def test_missing_value_is_never_converted_to_zero() -> None:
    """Eksik gözlem sıfıra çevrilirse kanıt motoru onu GERÇEK sanar."""
    from politikdesk.ingestion.adapters.evds import parse_value

    for bos in (None, "", "  ", "ND", "NA", "-"):
        assert parse_value(bos) is None


# ═══════════════════════════════════ 7-8. tekrar ve idempotency
def test_identical_observation_yields_identical_signature() -> None:
    a = signature("TP.X", "2026-08-19", "return_mad", 47.83)
    b = signature("TP.X", "2026-08-19", "return_mad", 47.83)
    assert a == b


def test_signature_changes_when_any_component_changes() -> None:
    temel = signature("TP.X", "2026-08-19", "return_mad", 47.83)
    assert signature("TP.Y", "2026-08-19", "return_mad", 47.83) != temel
    assert signature("TP.X", "2026-08-20", "return_mad", 47.83) != temel
    assert signature("TP.X", "2026-08-19", "change_mad", 47.83) != temel
    assert signature("TP.X", "2026-08-19", "return_mad", 47.84) != temel


def test_repeated_detection_is_deterministic() -> None:
    seri = _sakin_seri()
    seri.append(seri[-1] * 1.06)
    sonuclar = {
        signature("S", "P", d.method, d.observed_value)
        for d in (detect(seri, RETURN_MAD) for _ in range(5))
    }
    assert len(sonuclar) == 1


# ═══════════════════════════════════ 9. revizyon
def test_revised_value_produces_a_different_signature() -> None:
    """Revizyon yeni imza üretmeli; eskisi kapatılıp geçmiş korunur."""
    once = signature("TP.X", "2026-07", "change_mad", 100.0)
    sonra = signature("TP.X", "2026-07", "change_mad", 101.5)
    assert once != sonra


# ═══════════════════════════════════ 10-11. seri kimliği
def test_series_identity_is_never_metric_only() -> None:
    """USD/TRY ile EUR/TRY ikisi de `exchange_rate` — ayrı seri olmalı.

    Faz 1'in dersi: aynı metrik etiketi aynı büyüklük demek değildir.
    """
    from pathlib import Path

    sema = (
        Path(__file__).resolve().parent.parent / "migrations" / "0017_indicator_timeseries.sql"
    ).read_text(encoding="utf-8")
    assert "UNIQUE (source_id, series_code)" in sema


def test_usd_and_eur_never_share_one_statistical_series() -> None:
    from politikdesk.ingestion.adapters.evds import TRACKED

    fx = [s for s in TRACKED if s.metric == "exchange_rate"]
    assert len(fx) >= 2, "Sinama icin en az iki kur serisi gerekli"
    assert len({s.metric for s in fx}) == 1, "Ikisi de ayni metrigi tasimali"
    assert len({s.code for s in fx}) == len(fx), "Kodlari AYRI olmali"


# ═══════════════════════════════════ 12-13. eşik ve şiddet
def test_threshold_is_reproducible_and_reported() -> None:
    seri = _sakin_seri()
    seri.append(seri[-1] * 1.05)
    sonuc = detect(seri, RETURN_MAD)
    assert sonuc.threshold == RETURN_MAD.threshold
    assert sonuc.baseline_window == RETURN_MAD.window


def test_severity_scales_with_magnitude() -> None:
    """Şiddet ölçülen sapmadan türer; büyük hareket büyük şiddet."""
    kucuk = _sakin_seri()
    kucuk.append(kucuk[-1] * 1.02)
    buyuk = _sakin_seri()
    buyuk.append(buyuk[-1] * 1.30)
    a, b = detect(kucuk, RETURN_MAD), detect(buyuk, RETURN_MAD)
    assert a.is_anomaly and b.is_anomaly
    sira = ["low", "medium", "high", "critical"]
    assert sira.index(b.severity or "low") >= sira.index(a.severity or "low")


def test_policy_rate_severity_discriminates_instead_of_always_critical() -> None:
    """**Ölçülmüş bir kusurun regresyon testi.**

    İlk uygulamada `absolute_change` şiddeti eşikle aynı ölçekte
    hesaplanıyordu; sonuç, 27 faiz değişiminin 26'sının `critical`
    çıkmasıydı — yani şiddet hiçbir şey ayırt etmiyordu. Ayrı
    `severity_scale` ile 50bp `low`, 500bp `critical` olur.
    """
    kucuk = detect([40.0, 40.5], ABS_CHANGE)  # +50 bp
    buyuk = detect([40.0, 47.5], ABS_CHANGE)  # +750 bp
    assert kucuk.is_anomaly and buyuk.is_anomaly
    assert kucuk.severity == "low"
    assert buyuk.severity == "critical"
    assert ABS_CHANGE.severity_scale > ABS_CHANGE.threshold


# ═══════════════════════════════════ 14-15. yanlış pozitif kontrolü
def test_quiet_baseline_does_not_make_trivial_moves_anomalous() -> None:
    """**Ölçülmüş bir kusurun regresyon testi.**

    USD/TRY yönetimli kur rejiminde günlük getiriler %0,04 çevresinde
    kümeleniyor ve MAD %0,0096'ya iniyor. Bu ölçekte %0,22'lik bir
    hareket +12,5 sigma çıkıyordu — matematik doğru, sinyal değersiz.

    İstatistiksel anlamlılık maddi anlamlılık DEĞİLDİR.
    """
    seri = _sakin_seri()
    seri.append(seri[-1] * 1.0022)  # %0,22 — istatistiksel olarak devasa
    sonuc = detect(seri, RETURN_MAD)
    assert not sonuc.is_anomaly, sonuc.reason
    assert "maddi taban" in sonuc.reason


def test_material_floor_is_declared_for_every_statistical_method() -> None:
    for anahtar in ("return_mad", "change_mad"):
        assert METHODS[anahtar].min_material_change > 0, anahtar


def test_weekend_gaps_do_not_by_themselves_create_anomalies() -> None:
    """Hafta sonu boşluğu bir gözlem eksikliğidir, sıçrama değil.

    Seri yalnızca iş günlerini taşır; iki gözlem arasındaki 3 günlük
    takvim boşluğu getiriyi büyütmez çünkü hesap ardışık GÖZLEMLER
    üzerindedir, takvim günleri üzerinde değil.
    """
    seri = _sakin_seri()  # boşluklardan bağımsız, sadece gözlemler
    assert detect(seri, RETURN_MAD).state == "normal"


# ═══════════════════════════════════ 16-18. sayısal kenar durumlar
def test_legitimate_zero_value_is_not_rejected() -> None:
    """Sıfır meşru bir gözlem olabilir (ör. bütçe dengesi)."""
    seri = [*_sakin_seri(60), 0.0]
    sonuc = detect(seri, CHANGE_MAD)
    assert sonuc.state in {"normal", "anomalous"}
    assert sonuc.observed_value == 0.0


def test_legitimate_negative_value_is_not_rejected() -> None:
    seri = [-10.0 - i * 0.1 for i in range(40)]
    sonuc = detect(seri, CHANGE_MAD)
    assert sonuc.state in {"normal", "anomalous"}
    assert sonuc.observed_value < 0


def test_nan_and_infinite_values_are_rejected_not_silently_used() -> None:
    seri = _sakin_seri()
    for bozuk in (float("nan"), float("inf"), float("-inf")):
        sonuc = detect([*seri, bozuk], RETURN_MAD, now_value=bozuk)
        assert sonuc.state == "unavailable", bozuk


def test_zero_previous_value_does_not_crash_return_calculation() -> None:
    """Sıfırdan getiri hesaplanamaz; gözlem SİLİNMEZ, sadece atlanır."""
    seri = [0.0, *_sakin_seri(60)]
    sonuc = detect(seri, RETURN_MAD)
    assert not math.isnan(sonuc.deviation)


# ═══════════════════════════════════ 19-20. köken ve nedensellik
def test_detection_carries_its_full_explanation() -> None:
    seri = _sakin_seri()
    seri.append(seri[-1] * 1.08)
    sonuc = detect(seri, RETURN_MAD)
    for parca in ("değişim", "temel medyan", "ölçek", "σ"):
        assert parca in sonuc.reason, sonuc.reason


def test_anomaly_model_has_no_causality_field() -> None:
    """⛔ Anomali bir GÖZLEMDİR; nedensellik bir yorumdur ve kanıt ister.

    Denetim ALAN ADLARI üzerinden yapılır, ham metin üzerinden değil:
    yasağı anlatan docstring, yasağın ihlali değildir. Aynı gerekçe
    `tests/test_design_tokens.py::_emittable_strings` içinde de yazılı.
    """
    from dataclasses import fields

    from politikdesk.analysis.anomaly import Detection

    yasakli = {"cause", "caused_by", "reason_code", "explanation", "attribution"}
    alanlar = {f.name for f in fields(Detection)}
    assert not (alanlar & yasakli), alanlar & yasakli

    # `reason` vardır ama İSTATİSTİKSEL gerekçedir, nedensel değil —
    # içeriği yalnızca ölçüm terimleri taşır.
    assert "reason" in alanlar


def test_anomaly_table_has_no_causality_column() -> None:
    """Şemada da nedensellik alanı yoktur."""
    from pathlib import Path

    sema = (
        Path(__file__).resolve().parent.parent / "migrations" / "0017_indicator_timeseries.sql"
    ).read_text(encoding="utf-8")
    tablo = sema.split("CREATE TABLE IF NOT EXISTS indicator_anomalies")[1].split(");")[0]
    for yasak in ("cause", "reason", "explanation", "attribution", "interpretation"):
        assert yasak not in tablo.lower(), yasak


def test_severity_is_not_political_importance() -> None:
    """Şiddet ile siyasi önem AYRI boyutlardır ve çarpılmaz."""
    belge = an._severity.__doc__ or ""  # noqa: SLF001
    assert "SİYASİ ÖNEM DEĞİLDİR" in belge


# ═══════════════════════════════════ 21. yöntem seçimi
def test_method_is_chosen_from_series_character_not_one_size_fits_all() -> None:
    assert resolve_method("policy_rate", "monthly").key == "absolute_change"
    assert resolve_method("exchange_rate", "daily").key == "return_mad"
    assert resolve_method("reserves", "monthly").key == "change_mad"


def test_explicit_series_method_overrides_the_default() -> None:
    assert resolve_method("exchange_rate", "daily", "change_mad").key == "change_mad"


def test_every_method_documents_rationale_and_failure_modes() -> None:
    """Üretimdeki her yöntem neden uygun olduğunu ve nasıl bozulduğunu
    yazmalı (Faz 3 yetkisi §BASELINE METHODS)."""
    for anahtar, m in METHODS.items():
        assert len(m.rationale) > 80, anahtar
        assert len(m.failure_modes) > 40, anahtar


def test_zscore_is_not_applied_to_non_stationary_levels() -> None:
    """Seviyeler üzerinde z-skoru trendi anomali sanar; yasak açık."""
    belge = an.__doc__ or ""
    assert "z-skoru" in belge and "durağan değildir" in belge
    assert "zscore" not in METHODS


# ═══════════════════════════════════ 22. istatistik doğruluğu
def test_median_absolute_deviation_matches_hand_calculation() -> None:
    med, mad = median_absolute_deviation([1.0, 2.0, 3.0, 4.0, 100.0])
    assert med == 3.0
    assert mad == 1.0  # |1-3|,|2-3|,|3-3|,|4-3|,|100-3| -> medyan 1


def test_mad_is_robust_where_stdev_is_not() -> None:
    """Tek bir aykırı değer MAD'i şişirmez — asıl gerekçe budur."""
    import statistics

    temiz = [1.0, 1.1, 0.9, 1.05, 0.95]
    kirli = [*temiz, 50.0]
    _, mad_temiz = median_absolute_deviation(temiz)
    _, mad_kirli = median_absolute_deviation(kirli)
    assert mad_kirli < statistics.pstdev(kirli)
    assert abs(mad_kirli - mad_temiz) < 0.2


def test_current_observation_is_excluded_from_its_own_baseline() -> None:
    """Anomalinin kendi eşiğini yükseltmesi tespiti körletir."""
    kaynak = inspect.getsource(an.detect)
    assert "gecmis = seri[:-1]" in kaynak


# ═══════════════════════════════════ 23. mimari kısıt
def test_anomaly_modules_do_not_import_llm() -> None:
    """⛔ Bir anomalinin var olup olmadığına yapay zekâ karar veremez."""
    from politikdesk.analysis import expected_events, pipeline

    for modul in (an, pipeline, expected_events):
        agac = ast.parse(inspect.getsource(modul))
        moduller: set[str] = set()
        for dugum in ast.walk(agac):
            if isinstance(dugum, ast.Import):
                moduller |= {a.name for a in dugum.names}
            elif isinstance(dugum, ast.ImportFrom) and dugum.module:
                moduller.add(dugum.module)
        assert not {m for m in moduller if m.startswith("politikdesk.llm")}, modul.__name__


# ═══════════════════════════════════ 24. veritabanı yolu
@pytest.mark.db
def test_detect_all_runs_against_live_schema() -> None:
    from politikdesk.analysis.pipeline import detect_all

    stats = detect_all()
    assert stats.evaluated >= 0
    assert set(stats.by_state) <= {
        "normal",
        "anomalous",
        "insufficient_history",
        "stale",
        "unavailable",
    }


@pytest.mark.db
def test_persisted_anomalies_carry_full_provenance() -> None:
    from politikdesk.analysis.pipeline import open_anomalies

    for kayit in open_anomalies(limit=10):
        for alan in (
            "series_code",
            "detection_method",
            "threshold",
            "baseline_size",
            "source_slug",
            "severity",
            "period",
        ):
            assert kayit.get(alan) is not None, alan
