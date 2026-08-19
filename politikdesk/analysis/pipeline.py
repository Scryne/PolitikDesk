"""Gösterge serisi kalıcılaştırma ve anomali tespiti boru hattı (Faz 3.1).

İki iş yapar ve ikisi de **idempotenttir**:

  1. `sync_series()`  — adaptörlerin çektiği tam gözlem penceresini
                        `indicator_observations`'a yazar. Revizyon
                        güvenlidir: değişen değer eskisini SİLMEZ,
                        `superseded_at` ile işaretler.
  2. `detect_all()`   — her serinin son gözlemini değerlendirir ve
                        anomaliyi imzasıyla kaydeder. Değişmeyen gözlemin
                        tekrar işlenmesi yeni kayıt üretmez.

⛔ Bu modül `politikdesk.llm` import ETMEZ.

-----------------------------------------------------------------------
NEDEN AYRI BİR SENKRON ADIMI VAR
-----------------------------------------------------------------------

`articles.official_value` her seri için TEK satır taşır: adaptör 120
günlük pencere çeker ama yalnızca son gözlemi yayın birimine çevirir.
Bu doğru bir tasarımdır — bir makale haber birimidir, gözlem değil — ama
anomali tespiti için geçmiş gerekir ve o geçmiş kaynakta duruyordu.

Bu adım aynı pencereyi okuyup zaman serisine yazar. Adaptör mantığı
değişmez; makale üretimi olduğu gibi kalır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from politikdesk.analysis.anomaly import Detection, resolve_method, signature
from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)

# Seri kalıcılaştırırken kaç günlük geçmiş istenecek.
# Ölçüm (19 Ağu 2026): 5 yıllık pencere USD/EUR'da 683, M2'de 293,
# aylık serilerde 65-67 gözlem döndürüyor — hepsi yeterli.
HISTORY_DAYS = 1825


@dataclass
class SyncStats:
    series: int = 0
    inserted: int = 0
    revised: int = 0
    unchanged: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "series": self.series,
            "inserted": self.inserted,
            "revised": self.revised,
            "unchanged": self.unchanged,
            "errors": self.errors,
        }


@dataclass
class DetectStats:
    evaluated: int = 0
    anomalies: int = 0
    new_anomalies: int = 0
    by_state: dict[str, int] = field(default_factory=dict)
    by_severity: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "evaluated": self.evaluated,
            "anomalies": self.anomalies,
            "new_anomalies": self.new_anomalies,
            "by_state": self.by_state,
            "by_severity": self.by_severity,
        }


# ---------------------------------------------------------------------------
# 1. Seri kimliği ve gözlem yazımı
# ---------------------------------------------------------------------------
def upsert_series(
    *,
    source_slug: str,
    series_code: str,
    metric: str,
    label: str,
    unit: str,
    frequency: str,
) -> int | None:
    """Seri kimliğini garanti eder ve id döner.

    ⛔ Kimlik (kaynak, seri kodu) çiftidir — `metric` DEĞİL. USD/TRY ile
    EUR/TRY ikisi de `exchange_rate` taşır; metriğe göre kimliklenselerdi
    tek seri olurlardı ve iki farklı büyüklük aynı istatistiğe girerdi.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM sources WHERE slug = %s", (source_slug,))
        kaynak = cur.fetchone()
        if kaynak is None:
            log.warning("indicator_series_source_missing", slug=source_slug)
            return None

        cur.execute(
            """
            INSERT INTO indicator_series
                (source_id, series_code, metric, label, unit, frequency)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_id, series_code) DO UPDATE SET
                metric = EXCLUDED.metric,
                label  = EXCLUDED.label,
                unit   = EXCLUDED.unit,
                frequency = EXCLUDED.frequency
            RETURNING id
            """,
            (kaynak["id"], series_code, metric, label, unit, frequency),
        )
        satir = cur.fetchone()
        if satir is None:  # pragma: no cover — RETURNING her zaman satır döner
            return None
        seri_id = int(satir["id"])
        conn.commit()
    return seri_id


def store_observations(
    series_id: int, observations: list[tuple[str, float]], *, source_url: str | None = None
) -> tuple[int, int, int]:
    """Gözlemleri idempotent yazar. `(eklenen, revize, değişmeyen)` döner.

    REVİZYON GÜVENLİĞİ: aynı dönem farklı değerle gelirse eski satır
    SİLİNMEZ — `superseded_at` damgalanır ve yeni satır eklenir. Bir
    anomalinin neden üretildiği, o an yürürlükte olan değere bakılarak
    açıklanabilmelidir; geçmişi silmek denetlenebilirliği yok eder.
    """
    eklenen = revize = ayni = 0
    simdi = datetime.now(UTC)

    with connection() as conn, conn.cursor() as cur:
        for period, value in observations:
            cur.execute(
                """
                SELECT id, value FROM indicator_observations
                WHERE series_id = %s AND period = %s AND superseded_at IS NULL
                """,
                (series_id, period),
            )
            mevcut = cur.fetchone()

            if mevcut is not None:
                if float(mevcut["value"]) == float(value):
                    ayni += 1
                    continue
                cur.execute(
                    "UPDATE indicator_observations SET superseded_at = %s WHERE id = %s",
                    (simdi, mevcut["id"]),
                )
                revize += 1
            else:
                eklenen += 1

            cur.execute(
                """
                INSERT INTO indicator_observations
                    (series_id, period, value, observed_at, source_url)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (series_id, period, float(value), simdi, source_url),
            )
        conn.commit()

    return eklenen, revize, ayni


def sync_series(*, history_days: int = HISTORY_DAYS) -> SyncStats:
    """EVDS serilerinin tam geçmişini zaman serisine yazar.

    Yalnızca DOĞRULANMIŞ seriler işlenir (`EvdsSeries.verified`) —
    Faz 1.1'in kapısı burada da geçerlidir: doğrulanmamış bir kod veri
    üretmez.
    """
    from politikdesk.ingestion.adapters.evds import TRACKED, EvdsAdapter, api_key

    stats = SyncStats()
    try:
        key = api_key()
    except Exception as exc:  # noqa: BLE001
        log.warning("indicator_sync_no_key", error=type(exc).__name__)
        stats.errors += 1
        return stats

    adapter = EvdsAdapter(lookback_days=history_days)
    try:
        for spec in TRACKED:
            if not spec.verified:
                continue
            try:
                url = adapter.data_url(spec)
                yanit = adapter.http.get(url, headers={"key": key}, source_slug=adapter.slug)  # type: ignore[union-attr]
                gozlemler = adapter._parse_payload(yanit.text, spec)  # noqa: SLF001
            except Exception as exc:  # noqa: BLE001 — bir seri diğerini düşürmez
                log.warning(
                    "indicator_sync_series_failed",
                    code=spec.code,
                    error=type(exc).__name__,
                    detail=str(exc)[:180],
                )
                stats.errors += 1
                continue

            if not gozlemler:
                continue

            seri_id = upsert_series(
                source_slug=adapter.slug,
                series_code=spec.code,
                metric=spec.metric,
                label=spec.label,
                unit=spec.unit,
                frequency=_infer_frequency(gozlemler),
            )
            if seri_id is None:
                stats.errors += 1
                continue

            a, r, u = store_observations(seri_id, gozlemler, source_url=url)
            stats.series += 1
            stats.inserted += a
            stats.revised += r
            stats.unchanged += u
    finally:
        adapter.close()

    log.info("indicator_sync_complete", **stats.as_dict())
    return stats


def _infer_frequency(observations: list[tuple[str, float]]) -> str:
    """Dönem etiketinin BİÇİMİNDEN frekans çıkarır.

    Tahmin değil, biçim okuması: `2026-08-19` günlük/haftalık,
    `2026-08` aylık, `2026-Q3` çeyreklik, `2026` yıllık. Günlük ile
    haftalık ayrımı ardışık iki dönem arasındaki gün farkından gelir.
    """
    if not observations:
        return "unknown"
    ornek = observations[-1][0]
    parca = ornek.split("-")

    if len(parca) == 3:
        if len(observations) < 3:
            return "daily"
        from datetime import date

        try:
            tarihler = [date.fromisoformat(p) for p, _ in observations[-6:]]
        except ValueError:
            return "daily"
        farklar = [
            (b - a).days
            for a, b in zip(tarihler, tarihler[1:], strict=False)
            if (b - a).days > 0
        ]
        if not farklar:
            return "daily"
        ortanca = sorted(farklar)[len(farklar) // 2]
        return "weekly" if ortanca >= 5 else "daily"

    if len(parca) == 2:
        return "quarterly" if parca[1].upper().startswith("Q") else "monthly"
    return "yearly" if ornek.isdigit() else "irregular"


# ---------------------------------------------------------------------------
# 2. Tespit ve kalıcılaştırma
# ---------------------------------------------------------------------------
def _persist(series_id: int, series_code: str, period: str, obs_id: int,
             detection: Detection) -> bool:
    """Anomaliyi imzasıyla kaydeder. Yeni kayıt açıldıysa True döner.

    Idempotency: imza (seri|dönem|yöntem|değer) üzerinden kuruludur.
    Aynı gözlem her turda yeniden işlense de tek kayıt kalır.
    """
    imza = signature(series_code, period, detection.method, detection.observed_value)

    with connection() as conn, conn.cursor() as cur:
        # Aynı dönemin ESKİ imzalı anomalileri (revizyon sonrası) kapatılır;
        # silinmez — geçmiş denetlenebilir kalmalı.
        cur.execute(
            """
            UPDATE indicator_anomalies
               SET status = 'superseded'
             WHERE series_id = %s AND period = %s
               AND signature <> %s AND status = 'open'
            """,
            (series_id, period, imza),
        )
        cur.execute(
            """
            INSERT INTO indicator_anomalies (
                series_id, observation_id, period,
                observed_value, expected_value, deviation, deviation_ratio,
                detection_method, threshold, baseline_window, baseline_size,
                severity, signature
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (signature) DO NOTHING
            RETURNING id
            """,
            (
                series_id, obs_id, period,
                detection.observed_value, detection.expected_value,
                detection.deviation, detection.deviation_ratio,
                detection.method, detection.threshold,
                detection.baseline_window, detection.baseline_size,
                detection.severity or "low", imza,
            ),
        )
        yeni = cur.fetchone() is not None
        conn.commit()
    return yeni


def detect_all() -> DetectStats:
    """Tüm aktif serileri değerlendirir ve anomalileri kaydeder."""
    from politikdesk.analysis.anomaly import detect, staleness

    stats = DetectStats()

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, series_code, metric, frequency, method FROM indicator_series "
            "WHERE is_active ORDER BY series_code"
        )
        seriler = [dict(r) for r in cur.fetchall()]

    for seri in seriler:
        method = resolve_method(seri["metric"], seri["frequency"], seri["method"])
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, value, period, observed_at FROM indicator_observations
                WHERE series_id = %s AND superseded_at IS NULL
                ORDER BY period DESC LIMIT %s
                """,
                (seri["id"], method.window),
            )
            satirlar = list(reversed([dict(r) for r in cur.fetchall()]))

        stats.evaluated += 1

        if not satirlar:
            stats.by_state["unavailable"] = stats.by_state.get("unavailable", 0) + 1
            continue

        bayat, _ = staleness(seri["frequency"], satirlar[-1]["observed_at"])
        if bayat:
            stats.by_state["stale"] = stats.by_state.get("stale", 0) + 1
            continue

        sonuc = detect([float(r["value"]) for r in satirlar], method)
        stats.by_state[sonuc.state] = stats.by_state.get(sonuc.state, 0) + 1

        if not sonuc.is_anomaly:
            continue

        stats.anomalies += 1
        if sonuc.severity:
            stats.by_severity[sonuc.severity] = stats.by_severity.get(sonuc.severity, 0) + 1

        son = satirlar[-1]
        if _persist(seri["id"], seri["series_code"], str(son["period"]), int(son["id"]), sonuc):
            stats.new_anomalies += 1
            log.info(
                "indicator_anomaly_detected",
                series=seri["series_code"],
                period=son["period"],
                method=sonuc.method,
                severity=sonuc.severity,
                ratio=sonuc.deviation_ratio,
            )

    log.info("indicator_detect_complete", **stats.as_dict())
    return stats


def open_anomalies(limit: int = 50) -> list[dict[str, Any]]:
    """Açık anomaliler, kaynak ve köken bilgisiyle."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.period, a.observed_value, a.expected_value,
                   a.deviation, a.deviation_ratio, a.detection_method,
                   a.threshold, a.baseline_size, a.severity, a.detected_at,
                   s.series_code, s.label, s.unit, s.metric, s.frequency,
                   src.slug AS source_slug, src.name AS source_name,
                   src.independence_group
            FROM indicator_anomalies a
            JOIN indicator_series s ON s.id = a.series_id
            JOIN sources src ON src.id = s.source_id
            WHERE a.status = 'open'
            ORDER BY a.detected_at DESC, abs(a.deviation_ratio) DESC NULLS LAST
            LIMIT %s
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]
