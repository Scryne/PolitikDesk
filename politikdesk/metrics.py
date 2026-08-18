"""Ürün metrikleri — kayıt ve günlük toplama (F0-18, F3-19 · Spec §13.3).

Sekiz metriğin tamamı buradan geçer. İki katman vardır:

  * **Ham iz** — `user_activity`, `drafts`, `briefings`, `event_feedback`,
    `llm_calls` tablolarına olay anında yazılır.
  * **Günlük toplama** — `daily_rollup()` bu izlerden sekiz metriği
    hesaplar ve `metrics` tablosuna yazar. Pano toplanmış satırı okur.

Toplamanın ayrı olmasının sebebi: `draft_acceptance_rate` gibi metrikler
tek bir olayda ölçülemez, oran gerektirir. Her istekte yeniden hesaplamak
pano yükünü sorgu maliyetine çevirirdi.

⛔ **Bu modül gündem sıralamasına girdi vermez.** Spec §15 madde 14:
etkileşimi artırmak için gündemi çarpıtmak yasaktır; salience formülü
etkileşim girdisi içermez (§8.4) ve `evidence/` bu tabloları okuyamaz.
`daily_active_minutes`'ın hedefi bilinçli olarak DÜŞÜK olmaktır.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Final

from politikdesk.db import connection, fetch_one
from politikdesk.observability import get_logger

log = get_logger(__name__)

# Spec §13.3 — MVP'de izlenecek sekiz ürün metriği.
PRODUCT_METRICS: Final[frozenset[str]] = frozenset(
    {
        "time_to_understanding",
        "draft_acceptance_rate",
        "edit_distance",
        "diversity_ratio",
        "briefing_open_rate",
        "daily_active_minutes",
        "correction_rate",
        "cost_per_active_user",
    }
)

# Spec §13.3 hedefleri. `direction` "aşağısı iyi" mi "yukarısı iyi" mi
# olduğunu söyler — `daily_active_minutes`'ta bu ayrım ürünün vaadidir.
#
# `label` ARAYÜZDE görünür, bu yüzden Türkçedir (DESIGN.md Ek B.2: sistem
# dili yasak). Spec §13.3'teki İngilizce adlar sözlük ANAHTARLARIDIR ve
# değişmedi; Spec'e bakan biri eşlemeyi anahtardan bulur.
METRIC_TARGETS: Final[dict[str, dict[str, Any]]] = {
    "time_to_understanding": {
        "label": "Anlama süresi",
        "unit": "dk",
        "target": 10.0,
        "direction": "lower",
        "note": "30-45 dk tarama → ≤ 10 dk",
    },
    "draft_acceptance_rate": {
        "label": "Taslak kabul oranı",
        "unit": "%",
        "target": 40.0,
        "direction": "higher",
        "note": "Küçük düzenlemeyle kullanılan taslaklar",
    },
    "edit_distance": {
        "label": "Düzenleme mesafesi",
        "unit": "oran",
        "target": 0.35,
        "direction": "lower",
        "note": "Normalize Levenshtein",
    },
    "diversity_ratio": {
        "label": "Kaynak çeşitliliği",
        "unit": "grup",
        "target": 2.5,
        "direction": "higher",
        "note": "Görülen olaylarda ortalama farklı yayın grubu",
    },
    "briefing_open_rate": {
        "label": "Brifing açılma oranı",
        "unit": "%",
        "target": 60.0,
        "direction": "higher",
        "note": "Gönderilen brifinglerin açılma oranı",
    },
    "daily_active_minutes": {
        "label": "Günlük aktif dakika",
        "unit": "dk",
        "target": 20.0,
        "direction": "lower",
        "note": "AZ OLMASI İYİ — ürünün vaadi zaman tasarrufu (Spec §13.3)",
    },
    "correction_rate": {
        "label": "Düzeltme oranı",
        "unit": "%",
        "target": 3.0,
        "direction": "lower",
        "note": "'Bu yanlış' işaretlenen olay oranı",
    },
    "cost_per_active_user": {
        "label": "Aktif kullanıcı başına maliyet",
        "unit": "USD/ay",
        "target": 8.0,
        "direction": "lower",
        "note": "Gerçekleşen LLM + altyapı (ölçek: mevcut kullanıcı)",
    },
}

# `draft_acceptance_rate` tanımı (Spec §13.3): "taslakların KÜÇÜK
# DÜZENLEMEYLE kullanılma oranı". Düzenlenmiş bir taslak, düzenleme
# mesafesi bu eşiğin altındaysa "kullanıldı" sayılır. Eşik, `edit_distance`
# hedefiyle aynı sayıdır — iki metriğin farklı sayı kullanması, birinin
# tuttuğu bir taslağı diğerinin düşürmesi demek olurdu.
ACCEPTANCE_EDIT_LIMIT: Final[float] = 0.35

ACTIVITY_KINDS: Final[frozenset[str]] = frozenset(
    {"page_view", "heartbeat", "event_open", "understood"}
)


def record(
    metric_name: str,
    value: float,
    *,
    user_id: int | None = None,
    dimensions: dict[str, Any] | None = None,
) -> None:
    """Tek bir metrik ölçümünü kalıcı olarak kaydeder.

    Metrik yazımı asla çağıran akışı düşürmez: hata loglanır, yutulur.
    """
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO metrics (metric_name, metric_value, user_id, dimensions)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (metric_name, float(value), user_id, json.dumps(dimensions or {})),
            )
            conn.commit()
    except Exception:  # noqa: BLE001 — metrik kaybı ürünü durdurmaz
        log.warning("metric_write_failed", metric_name=metric_name, exc_info=True)


def record_activity(
    *,
    user_id: int,
    kind: str,
    event_id: int | None = None,
    path: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """Kullanım izini `user_activity`'ye yazar (F3-19 ham verisi).

    Ölçüm yazımı hiçbir koşulda sayfayı düşürmez.
    """
    if kind not in ACTIVITY_KINDS:
        log.warning("unknown_activity_kind", kind=kind)
        return
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_activity (user_id, kind, event_id, path, duration_ms)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, kind, event_id, path, duration_ms),
            )
            conn.commit()
    except Exception:  # noqa: BLE001
        log.warning("activity_write_failed", kind=kind, exc_info=True)


# --------------------------------------------------------------- hesaplama
@dataclass(frozen=True)
class MetricValue:
    """Tek bir metriğin bir günlük değeri ve hedefe göre durumu."""

    name: str
    value: float | None
    sample_size: int

    @property
    def meta(self) -> dict[str, Any]:
        return METRIC_TARGETS[self.name]

    @property
    def status(self) -> str:
        """`ok` / `off` / `no_data` — pano rozeti."""
        if self.value is None or self.sample_size == 0 or self.name not in METRIC_TARGETS:
            return "no_data"
        meta = self.meta
        target = float(meta.get("target", 0.0))
        direction = str(meta.get("direction", "higher"))
        if direction == "lower":
            return "ok" if self.value <= target else "off"
        return "ok" if self.value >= target else "off"

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.meta["label"],
            "unit": self.meta["unit"],
            "target": self.meta["target"],
            "direction": self.meta["direction"],
            "note": self.meta["note"],
            "value": self.value,
            "sample_size": self.sample_size,
            "status": self.status,
        }


def _scalar(cur: Any, sql: str, params: tuple[Any, ...]) -> tuple[float | None, int]:
    """(değer, örneklem) döndüren sorguları tek yerden okur."""
    cur.execute(sql, params)
    row = fetch_one(cur)
    value = row["value"]
    return (float(value) if value is not None else None, int(row["n"] or 0))


def compute_metrics(day: date, *, window_days: int = 7) -> list[MetricValue]:
    """Sekiz ürün metriğini belirtilen gün için hesaplar.

    Oran metrikleri `window_days` günlük kayan pencerede ölçülür: tek
    kullanıcılı bir üründe günlük örneklem 0-2 taslaktır ve günlük oran
    yalnızca gürültü üretir. Anlık metrikler (aktif dakika) o güne aittir.
    """
    start = day - timedelta(days=window_days - 1)
    values: list[MetricValue] = []

    with connection() as conn, conn.cursor() as cur:
        # 1 — time_to_understanding: "Anladım" tıklamasına kadar geçen süre
        values.append(
            MetricValue(
                "time_to_understanding",
                *_scalar(
                    cur,
                    """
                    SELECT percentile_cont(0.5) WITHIN GROUP (
                             ORDER BY duration_ms / 60000.0
                           ) AS value,
                           count(*) AS n
                    FROM user_activity
                    WHERE kind = 'understood' AND duration_ms IS NOT NULL
                      AND occurred_at::date BETWEEN %s AND %s
                    """,
                    (start, day),
                ),
            )
        )

        # 2 — draft_acceptance_rate: kabul + küçük düzenlemeyle kullanılan
        values.append(
            MetricValue(
                "draft_acceptance_rate",
                *_scalar(
                    cur,
                    """
                    SELECT 100.0 * count(*) FILTER (
                             WHERE user_action = 'accepted'
                                OR (user_action = 'edited'
                                    AND COALESCE(edit_distance, 1) <= %s)
                           ) / NULLIF(count(*), 0) AS value,
                           count(*) AS n
                    FROM drafts
                    WHERE user_action IS NOT NULL
                      AND action_at::date BETWEEN %s AND %s
                    """,
                    (ACCEPTANCE_EDIT_LIMIT, start, day),
                ),
            )
        )

        # 3 — edit_distance: düzenlenen taslakların ortalaması
        values.append(
            MetricValue(
                "edit_distance",
                *_scalar(
                    cur,
                    """
                    SELECT avg(edit_distance) AS value, count(*) AS n
                    FROM drafts
                    WHERE user_action = 'edited' AND edit_distance IS NOT NULL
                      AND action_at::date BETWEEN %s AND %s
                    """,
                    (start, day),
                ),
            )
        )

        # 4 — diversity_ratio: görülen olay başına farklı yayın grubu
        # (Spec §10.3 echo chamber karşı-mekanizmasının ölçümü)
        values.append(
            MetricValue(
                "diversity_ratio",
                *_scalar(
                    cur,
                    """
                    SELECT avg(groups) AS value, count(*) AS n FROM (
                      SELECT ua.event_id,
                             count(DISTINCT COALESCE(s.independence_group, s.slug))
                               AS groups
                      FROM user_activity ua
                      JOIN articles a ON a.event_id = ua.event_id
                      JOIN sources s ON s.id = a.source_id
                      WHERE ua.kind = 'event_open' AND ua.event_id IS NOT NULL
                        AND ua.occurred_at::date BETWEEN %s AND %s
                      GROUP BY ua.event_id
                    ) seen
                    """,
                    (start, day),
                ),
            )
        )

        # 5 — briefing_open_rate
        values.append(
            MetricValue(
                "briefing_open_rate",
                *_scalar(
                    cur,
                    """
                    SELECT 100.0 * count(*) FILTER (WHERE opened_at IS NOT NULL)
                             / NULLIF(count(*), 0) AS value,
                           count(*) AS n
                    FROM briefings
                    WHERE sent_at IS NOT NULL AND briefing_date BETWEEN %s AND %s
                    """,
                    (start, day),
                ),
            )
        )

        # 6 — daily_active_minutes: farklı DAKİKA kovası sayılır.
        # Ham istek saymak, tek sayfada 20 istek atan bir ekranı "20 dakika
        # aktif" gösterirdi.
        values.append(
            MetricValue(
                "daily_active_minutes",
                *_scalar(
                    cur,
                    """
                    SELECT count(DISTINCT date_trunc('minute', occurred_at))::float
                             AS value,
                           count(*) AS n
                    FROM user_activity
                    WHERE occurred_at::date = %s
                    """,
                    (day,),
                ),
            )
        )

        # 7 — correction_rate: işaretlenen olay / görülen olay (L6)
        # Spec §13.3: Numerator ve denominator aynı event population'ını
        # (window içinde açılan olaylar) kullanır.
        values.append(
            MetricValue(
                "correction_rate",
                *_scalar(
                    cur,
                    """
                    WITH opened AS (
                      SELECT DISTINCT event_id
                      FROM user_activity
                      WHERE kind = 'event_open' AND event_id IS NOT NULL
                        AND occurred_at::date BETWEEN %s AND %s
                    )
                    SELECT 100.0 * (
                             SELECT count(DISTINCT ef.event_id)
                             FROM event_feedback ef
                             JOIN opened o ON o.event_id = ef.event_id
                             WHERE ef.created_at::date BETWEEN %s AND %s
                           ) / NULLIF(count(*), 0) AS value,
                           count(*) AS n
                    FROM opened
                    """,
                    (start, day, start, day),
                ),
            )
        )

        # 8 — cost_per_active_user: GERÇEKLEŞEN harcama, aylığa ölçeklenir.
        # 100 kullanıcılık ÖNGÖRÜ ayrı bir sorudur ve `scripts/cost_model.py`
        # içinde durur (G0 koşul 8a/8b bu ikisini ayrı ölçer).
        cur.execute(
            """
            SELECT COALESCE(sum(cost_usd), 0)::float AS spend,
                   count(*) AS n
            FROM llm_calls
            WHERE created_at::date BETWEEN %s AND %s
            """,
            (start, day),
        )
        llm = fetch_one(cur)
        cur.execute(
            """
            SELECT count(DISTINCT user_id) AS users FROM user_activity
            WHERE occurred_at::date BETWEEN %s AND %s
            """,
            (start, day),
        )
        active_users_count = int(fetch_one(cur)["users"] or 0)
        active_users = max(active_users_count, 1)

    monthly_llm = float(llm["spend"]) * (30.0 / window_days)
    sample_size = max(int(llm["n"] or 0), active_users_count)
    values.append(
        MetricValue(
            "cost_per_active_user",
            (monthly_llm + _monthly_infra_usd()) / active_users,
            sample_size,
        )
    )
    return values


def _monthly_infra_usd() -> float:
    """Altyapının aylık sabit maliyeti (maliyet modelinin varsayımı).

    Tek kaynak: `scripts/cost_model.py`. İki yerde ayrı sayı tutmak,
    panonun G0 koşul 8'den farklı bir maliyet göstermesi demekti.
    """
    from scripts.cost_model import Assumptions

    personal = Assumptions.personal()
    return personal.vps_usd_per_month + personal.backup_and_monitoring_usd


def daily_rollup(day: date | None = None, *, window_days: int = 7) -> dict[str, Any]:
    """Sekiz metriği hesaplar ve `metrics` tablosuna yazar (F3-19).

    Aynı gün için yeniden koşulabilir: eski satırlar silinir, yenisi
    yazılır. Aksi halde iki koşum panoyu ikiye katlardı.
    """
    if day is None:
        import zoneinfo
        from datetime import datetime

        from politikdesk.config import get_settings

        try:
            tz = zoneinfo.ZoneInfo(get_settings().timezone)
            day = datetime.now(tz).date()
        except Exception:  # noqa: BLE001
            day = date.today()

    values = compute_metrics(day, window_days=window_days)

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM metrics
            WHERE metric_name = ANY(%s)
              AND recorded_at::date = %s
              AND dimensions->>'source' = 'daily_rollup'
            """,
            (sorted(PRODUCT_METRICS), day),
        )
        written = 0
        for metric in values:
            if metric.value is None:
                continue
            # İKİ ZAMAN, İKİ SÜTUN (migration 0008):
            #   recorded_at — satırın ANLATTIĞI gün. Öğleye sabitlenir ki
            #     `recorded_at::date` gün sınırında kaymasın; yukarıdaki
            #     DELETE ve gün bazlı gruplama buna dayanır.
            #   computed_at — satırın YAZILDIĞI an. `DEFAULT now()` ile
            #     gelir ve `pipeline_health` nabzı bunu okur.
            # Birleştirilmemeliler: nabız gün etiketini okuduğunda yaş
            # negatife düşüyordu (ölçülen: -14,66 saat).
            cur.execute(
                """
                INSERT INTO metrics (metric_name, metric_value, dimensions, recorded_at)
                VALUES (%s, %s, %s::jsonb, %s::date + interval '12 hours')
                """,
                (
                    metric.name,
                    float(metric.value),
                    json.dumps(
                        {
                            "source": "daily_rollup",
                            "window_days": window_days,
                            "sample_size": metric.sample_size,
                            "status": metric.status,
                        }
                    ),
                    day,
                ),
            )
            written += 1
        conn.commit()

    log.info("metrics_rollup_done", day=str(day), written=written, total=len(values))
    return {
        "day": str(day),
        "written": written,
        "metrics": [m.as_dict() for m in values],
    }


def history(days: int = 30) -> dict[str, list[dict[str, Any]]]:
    """Pano için metrik geçmişi (F3-20)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT metric_name, metric_value, recorded_at::date AS day, dimensions
            FROM metrics
            WHERE metric_name = ANY(%s)
              AND dimensions->>'source' = 'daily_rollup'
              AND recorded_at >= now() - make_interval(days => %s)
            ORDER BY recorded_at
            """,
            (sorted(PRODUCT_METRICS), days),
        )
        rows = [dict(r) for r in cur.fetchall()]

    out: dict[str, list[dict[str, Any]]] = {name: [] for name in sorted(PRODUCT_METRICS)}
    for row in rows:
        out[row["metric_name"]].append(
            {
                "day": str(row["day"]),
                "value": float(row["metric_value"]),
                "sample_size": (row["dimensions"] or {}).get("sample_size"),
                "status": (row["dimensions"] or {}).get("status"),
            }
        )
    return out
