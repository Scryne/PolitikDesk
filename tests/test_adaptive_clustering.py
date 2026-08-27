"""Adaptif Zaman Penceresi ve Makro Eşleştirme Testleri (Roadmap B6/B7)."""

from __future__ import annotations

from datetime import datetime, timedelta

from politikdesk.clustering.assigner import (
    ArticleFeatures,
    EventCandidate,
    Thresholds,
    _effective_time_window_hours,
    decide,
)


def test_effective_time_window_macro_entities() -> None:
    now = datetime(2026, 8, 20, 12, 0)
    art = ArticleFeatures(
        article_id=1,
        embedding=[0.1] * 384,
        entities=frozenset({"TÜİK", "Enflasyon"}),
        key_entities=frozenset({"TÜİK"}),
        published_at=now,
    )
    cand = EventCandidate(
        event_id=10,
        similarity=0.95,
        entities=frozenset({"TÜİK", "TÜFE"}),
        key_entities=frozenset({"TÜİK"}),
        last_update_at=now - timedelta(days=7),  # 168 saat önce (> 72 saat)
    )

    # Standart 72 saatlik pencere 336 saate (14 güne) esner
    eff_hours = _effective_time_window_hours(art, cand, 72)
    assert eff_hours == 336

    # Karar: zaman kısıtına takılmadan kabul edilir
    res = decide(art, [cand], thresholds=Thresholds(t_high=0.90, t_low=0.80, time_window_hours=72))
    assert res.action == "assign"
    assert res.event_id == 10
    assert res.trace[0].outcome == "accepted"


def test_effective_time_window_non_macro_entities() -> None:
    now = datetime(2026, 8, 20, 12, 0)
    art = ArticleFeatures(
        article_id=2,
        embedding=[0.1] * 384,
        entities=frozenset({"Futbol Kulübü"}),
        key_entities=frozenset({"Futbol Kulübü"}),
        published_at=now,
    )
    cand = EventCandidate(
        event_id=20,
        similarity=0.95,
        entities=frozenset({"Futbol Kulübü"}),
        key_entities=frozenset({"Futbol Kulübü"}),
        last_update_at=now - timedelta(days=5),  # 120 saat önce (> 72 saat)
    )

    # Standart 72 saatlik pencere korunur
    eff_hours = _effective_time_window_hours(art, cand, 72)
    assert eff_hours == 72

    # Karar: zaman kısıtından elenir (time_reject)
    res = decide(art, [cand], thresholds=Thresholds(t_high=0.90, t_low=0.80, time_window_hours=72))
    assert res.action == "create"
    assert res.trace[0].outcome == "time_reject"
