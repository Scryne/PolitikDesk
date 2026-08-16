"""Ürün metriği testleri (F3-19, F3-20 · Spec §13.3).

Korunan iki kısıt:

  * **Sekiz metriğin tamamı hesaplanır** — G3 koşul 6.
  * **Kullanım izi gündem sıralamasına girmez** (Spec §15 madde 14).
    `evidence/` modülü `user_activity`'yi okuyamaz; salience formülü
    etkileşim girdisi içermez.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from politikdesk.metrics import (
    ACCEPTANCE_EDIT_LIMIT,
    ACTIVITY_KINDS,
    METRIC_TARGETS,
    PRODUCT_METRICS,
    MetricValue,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = REPO_ROOT / "politikdesk" / "evidence"

# Kullanım/etkileşim tabloları — kanıt motorunun görmemesi gerekenler.
ENGAGEMENT_TABLES = ("user_activity", "event_feedback", "briefings", "drafts")


# =============================================================== kapsam
def test_all_eight_product_metrics_have_targets() -> None:
    """G3 koşul 6: 8 metriğin tamamı akıyor."""
    assert len(PRODUCT_METRICS) == 8
    assert set(METRIC_TARGETS) == PRODUCT_METRICS


def test_every_target_declares_a_direction() -> None:
    """ "Yukarısı iyi" mi "aşağısı iyi" mi — panonun rozeti buna bakar."""
    for name, meta in METRIC_TARGETS.items():
        assert meta["direction"] in ("lower", "higher"), name
        assert isinstance(meta["target"], int | float), name
        assert meta["label"] and meta["note"], name


def test_daily_active_minutes_target_is_lower_is_better() -> None:
    """Spec §13.3: az olması İYİdir — ürünün vaadi zaman tasarrufudur.

    Bu satır bir tercih değil, ürün sözleşmesinin bir parçasıdır:
    "bu metriği yukarı çekmeye çalışan hiçbir özellik kabul edilmez."
    """
    meta = METRIC_TARGETS["daily_active_minutes"]
    assert meta["direction"] == "lower"
    assert "AZ OLMASI İYİ" in meta["note"]


def test_acceptance_limit_matches_edit_distance_target() -> None:
    """İki metrik aynı eşiği kullanmalı.

    Farklı sayılar kullansalardı, birinin "kabul edildi" saydığı bir
    taslağı diğeri "fazla düzenlenmiş" sayardı.
    """
    assert METRIC_TARGETS["edit_distance"]["target"] == ACCEPTANCE_EDIT_LIMIT


def test_activity_kinds_are_closed_set() -> None:
    assert {"page_view", "heartbeat", "event_open", "understood"} == ACTIVITY_KINDS


# =========================================================== durum mantığı
@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("edit_distance", 0.20, "ok"),  # düşük iyi, hedefin altında
        ("edit_distance", 0.60, "off"),  # düşük iyi, hedefin üstünde
        ("diversity_ratio", 3.0, "ok"),  # yüksek iyi, hedefin üstünde
        ("diversity_ratio", 1.2, "off"),  # yüksek iyi, hedefin altında
        ("daily_active_minutes", 8.0, "ok"),
        ("daily_active_minutes", 90.0, "off"),
    ],
)
def test_status_respects_direction(name: str, value: float, expected: str) -> None:
    assert MetricValue(name, value, sample_size=5).status == expected


def test_missing_data_is_not_reported_as_success() -> None:
    """Örneklem yoksa "hedefte" denmez — ölçülmemişi tutuyor saymak
    G3 koşul 6'yı anlamsız kılardı."""
    assert MetricValue("edit_distance", None, 0).status == "no_data"
    assert MetricValue("edit_distance", 0.1, 0).status == "no_data"


def test_metric_value_serialises_for_the_dashboard() -> None:
    payload = MetricValue("diversity_ratio", 2.9, 12).as_dict()
    # Etiket ARAYÜZ metnidir ve Türkçedir (Ek B.2 sistem dili yasağı);
    # Spec §13.3'ün İngilizce adı sözlük ANAHTARIDIR ve değişmedi.
    assert payload["name"] == "diversity_ratio"
    assert payload["label"] == "Kaynak çeşitliliği"
    assert payload["target"] == 2.5
    assert payload["status"] == "ok"
    assert payload["sample_size"] == 12


# ============================================== Spec §15 madde 14 zorlaması
def test_evidence_engine_cannot_read_usage_tables() -> None:
    """Salience, etkileşimden beslenemez (Spec §8.4, §15 madde 14).

    `scripts/check_architecture.py` import yasağını denetler; bu test
    SQL metnini denetler — kanıt motoru bir kullanım tablosuna SORGU
    atarsa import kuralı bunu yakalamazdı.
    """
    offenders: list[str] = []
    for path in EVIDENCE_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        # Yalnızca dize sabitlerine bakılır: yorumda tablo adı geçebilir
        # (ve geçiyor — kısıtın kendisi orada açıklanıyor).
        tree = ast.parse(source, filename=str(path))
        literals = " ".join(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ).lower()
        offenders += [
            f"{path.name}: {table}"
            for table in ENGAGEMENT_TABLES
            if f"from {table}" in literals or f"join {table}" in literals
        ]
    assert not offenders, (
        f"Kanıt motoru kullanım tablosu okuyor: {offenders}. "
        "Salience etkileşim girdisi içeremez (Spec §15 madde 14)."
    )


def test_metrics_module_does_not_write_to_events() -> None:
    """Ölçüm, gündemi DEĞİŞTİREMEZ — yalnızca okur ve kendi tablosuna yazar."""
    source = (REPO_ROOT / "politikdesk" / "metrics.py").read_text(encoding="utf-8")
    lowered = source.lower()
    assert "update events" not in lowered
    assert "insert into events" not in lowered


# ================================================================ canlı DB
@pytest.mark.db
def test_compute_metrics_returns_all_eight(db_conn) -> None:  # noqa: ANN001
    """Sorguların hepsi gerçek şemaya karşı koşabilmeli.

    Bu testin asıl işi SQL doğrulamasıdır: bir sütun adı kayarsa
    pano boş görünmek yerine burada patlar.
    """
    from politikdesk import metrics

    values = metrics.compute_metrics(date.today())
    assert {m.name for m in values} == PRODUCT_METRICS
    for metric in values:
        assert metric.value is None or isinstance(metric.value, float)


@pytest.mark.db
def test_daily_rollup_is_idempotent(db_conn) -> None:  # noqa: ANN001
    """Aynı gün iki kez toplanırsa pano ikiye katlanmamalı."""
    from politikdesk import metrics

    day = date.today()
    metrics.daily_rollup(day)
    first = metrics.history(1)
    metrics.daily_rollup(day)
    second = metrics.history(1)

    for name in PRODUCT_METRICS:
        assert len(first[name]) == len(second[name]), name


@pytest.mark.db
def test_correction_rate_population_alignment(db_conn) -> None:  # noqa: ANN001
    """L6: correction_rate yalnızca window içinde açılan olaylar havuzunu (population) oranlar."""
    from datetime import UTC, date, datetime

    from politikdesk import metrics

    today = date.today()
    now = datetime.now(UTC)

    with db_conn.cursor() as cur:
        # İki test olayı oluşturalım
        cur.execute(
            """
            INSERT INTO events (title, status, first_reported_at, last_update_at)
            VALUES ('L6 Test Event 1', 'developing', %s, %s),
                   ('L6 Test Event 2', 'developing', %s, %s),
                   ('L6 Test Event 3', 'developing', %s, %s)
            RETURNING id
            """,
            (now, now, now, now, now, now),
        )
        rows = cur.fetchall()
        e1_id, e2_id, e3_id = [r["id"] if isinstance(r, dict) else r[0] for r in rows]

        # 1. Event 1: Bugün açıldı (event_open) ve bugün 2 adet feedback aldı
        cur.execute(
            """
            INSERT INTO user_activity (user_id, kind, event_id, occurred_at)
            VALUES (1, 'event_open', %s, %s)
            """,
            (e1_id, now),
        )
        cur.execute(
            """
            INSERT INTO event_feedback (user_id, event_id, note, created_at)
            VALUES (1, %s, 'Geri bildirim 1', %s),
                   (1, %s, 'Geri bildirim 2', %s)
            """,
            (e1_id, now, e1_id, now),
        )

        # 2. Event 2: Bugün açıldı (event_open), hiç feedback almadı
        cur.execute(
            """
            INSERT INTO user_activity (user_id, kind, event_id, occurred_at)
            VALUES (1, 'event_open', %s, %s)
            """,
            (e2_id, now),
        )

        # 3. Event 3: Bugün AÇILMADI (örneğin eski olay), fakat bugün feedback aldı
        cur.execute(
            """
            INSERT INTO event_feedback (user_id, event_id, note, created_at)
            VALUES (1, %s, 'Açılmamış olaya gelen feedback', %s)
            """,
            (e3_id, now),
        )

    event_ids = [e1_id, e2_id, e3_id]
    try:
        # compute_metrics çalıştır
        values = {m.name: m for m in metrics.compute_metrics(today)}
        cr = values["correction_rate"]

        # Popülasyon: Bugün açılan olaylar = {e1, e2} (toplam 2)
        # Bu popülasyondan feedback alanlar = {e1} (toplam 1, çoklu feedback tek sayılır)
        # Event 3 popülasyonda olmadığı için numerator'a dahil edilmez.
        # Beklenen: 1 / 2 = %50.0 (veya en azından e3 eklenip 2/2 = %100 OLMAMALI)
        assert cr.value is not None
        assert 0.0 <= cr.value <= 100.0
        # Örneklem sayısı en az 2 (e1 ve e2)
        assert cr.sample_size >= 2
        # e3 dahil edilmediği için oran %100'den küçük olmalıdır
        assert cr.value < 100.0
    finally:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM event_feedback WHERE event_id = ANY(%s)", (event_ids,))
            cur.execute("DELETE FROM user_activity WHERE event_id = ANY(%s)", (event_ids,))
            cur.execute("DELETE FROM events WHERE id = ANY(%s)", (event_ids,))
        db_conn.commit()
