"""Golden Set v2 etiketleme araçlarının saf mantığı (eval/etiketleme)."""

from __future__ import annotations

import random

from eval.etiketleme.birlestir import merge
from eval.etiketleme.orneklem import select, topic_quotas


def test_quotas_split_target_evenly() -> None:
    q = topic_quotas(245, ["a", "b", "c"])
    assert sum(q.values()) == 245
    assert max(q.values()) - min(q.values()) <= 1


def test_same_partition_with_different_names_is_accepted() -> None:
    a = {"x1": "tufe", "x2": "tufe", "x3": "ppk"}
    b = {"x1": "enf-ekim", "x2": "enf-ekim", "x3": "faiz"}
    m = merge(a, b, dict.fromkeys(a, "t"))
    assert m.disputed == []
    assert m.accepted["x1"] == m.accepted["x2"] != m.accepted["x3"]
    assert m.pair_agreement == 1.0


def test_partition_disagreement_goes_to_the_referee() -> None:
    a = {"x1": "e1", "x2": "e1", "x3": "e2"}
    b = {"x1": "k1", "x2": "k2", "x3": "k3"}
    m = merge(a, b, dict.fromkeys(a, "t"))
    assert sorted(m.disputed) == ["x1", "x2"]
    assert set(m.accepted) == {"x3"}
    # 3 çiftten yalnız (x1,x2) kararında ayrıştılar
    assert m.pairs == 3
    assert abs(m.pair_agreement - 2 / 3) < 1e-9


def test_sampler_fills_topic_quota_with_neighbours_and_never_labels() -> None:
    pool = [
        {"id": i, "topics": ["enflasyon"], "published_at": i, "title": f"t{i}"} for i in range(1, 7)
    ] + [{"id": 10, "topics": ["buyume"], "published_at": 10, "title": "b"}]
    rows = select(
        pool,
        {"enflasyon": 3, "buyume": 1},
        lambda aid: [aid + 1, aid + 2],
        random.Random(1),
    )
    assert sum(1 for r in rows if r["topic"] == "enflasyon") == 3
    assert sum(1 for r in rows if r["topic"] == "buyume") == 1
    assert all("event_id" not in r for r in rows)
