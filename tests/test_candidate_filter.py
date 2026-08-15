"""S3 Candidate Pre-Filter Birim ve Doğruluk Testleri (Spec v3.4 §14.1)."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from politikdesk.political_memory.candidate_filter import (
    ABSOLUTE_MAX_CANDIDATES,
    DEFAULT_CANDIDATE_LIMIT,
    filter_candidates_in_memory,
)
from politikdesk.political_memory.relation_engine import EventData


def _dt(offset_days: int = 0) -> datetime:
    return datetime(2026, 8, 1, 12, 0, tzinfo=UTC) + timedelta(days=offset_days)


def test_candidate_filter_limits_to_default_and_hard_ceiling() -> None:
    src = EventData(
        event_id=1,
        title="Kaynak Olay",
        published_at=_dt(0),
        actor="Bakan",
        institution="Bakanlık",
        topics=("kamu",),
    )

    # 100 aday üret
    pool = [
        EventData(
            event_id=i,
            title=f"Aday Olay {i}",
            published_at=_dt(i % 10),
            actor="Bakan" if i % 2 == 0 else "Diğer",
            institution="Bakanlık" if i % 3 == 0 else "Kurum",
            topics=("kamu",) if i % 2 == 0 else ("ekonomi",),
        )
        for i in range(2, 102)
    ]

    # Varsayılan limit
    selected_default = filter_candidates_in_memory(src, pool)
    assert len(selected_default) <= DEFAULT_CANDIDATE_LIMIT

    # Aşırı yüksek limit istendiğinde sert tavan devreye girer
    selected_over = filter_candidates_in_memory(src, pool, limit=999)
    assert len(selected_over) <= ABSOLUTE_MAX_CANDIDATES


def test_candidate_filter_ignores_self_event() -> None:
    src = EventData(
        event_id=1,
        title="Olay 1",
        published_at=_dt(0),
        actor="Bakan",
        institution="Bakanlık",
    )
    pool = [src]
    selected = filter_candidates_in_memory(src, pool)
    assert len(selected) == 0


def test_candidate_filter_prioritizes_matching_actor_and_institution() -> None:
    src = EventData(
        event_id=1,
        title="Sağlık Bakanı Randevu Vaadi",
        published_at=_dt(0),
        actor="Kemal Memişoğlu",
        institution="Sağlık Bakanlığı",
        topics=("saglik",),
    )

    exact_cand = EventData(
        event_id=2,
        title="Sağlık Bakanlığı MHRS Genelgesi",
        published_at=_dt(5),
        actor="Kemal Memişoğlu",
        institution="Sağlık Bakanlığı",
        topics=("saglik",),
    )

    unrelated_cand = EventData(
        event_id=3,
        title="Tarım Bakanlığı Mazot Desteği",
        published_at=_dt(10),
        actor="İbrahim Yumaklı",
        institution="Tarım Bakanlığı",
        topics=("tarim",),
    )

    pool = [unrelated_cand, exact_cand]
    selected = filter_candidates_in_memory(src, pool)
    assert len(selected) >= 1
    assert selected[0].event_id == 2


def test_candidate_filter_benchmark_1000_events() -> None:
    """1000 olaylık havuzda aday ön filtrelemenin bounded ve hızlı çalıştığını doğrular."""
    src = EventData(
        event_id=1,
        title="Önemli Siyasi Vaat",
        published_at=_dt(0),
        actor="Yetkili",
        institution="Kurum",
        topics=("politika",),
    )

    # 1000 olay üret
    pool = [
        EventData(
            event_id=i,
            title=f"Geçmiş Olay {i}",
            published_at=_dt(-(i % 300)),
            actor="Yetkili" if i % 10 == 0 else f"Aktör {i}",
            institution="Kurum" if i % 5 == 0 else f"Kurum {i}",
            topics=("politika",) if i % 4 == 0 else ("diger",),
        )
        for i in range(2, 1002)
    ]

    t0 = time.perf_counter()
    selected = filter_candidates_in_memory(src, pool, limit=20)
    elapsed = time.perf_counter() - t0

    assert len(selected) <= 20
    # 1000 olay filtrelemesi 0.1 saniyenin altında tamamlanmalıdır
    assert elapsed < 0.10, f"Aday filtreleme çok yavaş: {elapsed:.4f}s"
