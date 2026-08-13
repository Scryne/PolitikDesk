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
    """"Yukarısı iyi" mi "aşağısı iyi" mi — panonun rozeti buna bakar."""
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
        ("edit_distance", 0.20, "ok"),      # düşük iyi, hedefin altında
        ("edit_distance", 0.60, "off"),     # düşük iyi, hedefin üstünde
        ("diversity_ratio", 3.0, "ok"),     # yüksek iyi, hedefin üstünde
        ("diversity_ratio", 1.2, "off"),    # yüksek iyi, hedefin altında
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
    assert payload["label"] == "Diversity ratio"
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
