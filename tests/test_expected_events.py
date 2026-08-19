"""Beklenen yayın motoru testleri (Roadmap Faz 3.2).

Korunan değişmez — **üç farklı anlam, üç farklı durum**:

    delayed     Kurum henüz yayımlamadı. Gecikme KURUMUNDUR.
    published   Kurum yayımladı ama BİZ görmedik. Eksiklik BİZDEDİR.
    occurred    Yayımlandı ve eşleşti. Gecikme varsa GÖRME gecikmemizdir.

Bunlar `cancelled`'dan ayrıdır: beklenen şey hiç gerçekleşmedi.
Faz 1.2'nin `published != cancelled` değişmezi burada da korunur.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime

import pytest

from politikdesk.analysis import expected_events as ee
from politikdesk.analysis.expected_events import (
    ABANDON_AFTER,
    TOLERANCE,
    ExpectationSignal,
    _delay_minutes,
)


def _sinyal(**over: object) -> ExpectationSignal:
    temel: dict[str, object] = {
        "scheduled_id": 1,
        "signal_type": "release_observed",
        "institution": "TÜİK",
        "title": "Tüketici Fiyat Endeksi",
        "expected_at": datetime(2026, 8, 19, 10, 0, tzinfo=UTC),
        "observed_at": datetime(2026, 8, 19, 10, 12, tzinfo=UTC),
        "delay_minutes": 12,
        "state": "occurred",
        "reference_period": "Temmuz 2026",
        "url": "https://example.test/b",
        "linked_event_id": 42,
    }
    temel.update(over)
    return ExpectationSignal(**temel)  # type: ignore[arg-type]


# ═══════════════════════════════ 1. durum sözlüğü ve değişmez
def test_status_vocabulary_covers_all_required_states() -> None:
    from pathlib import Path

    sema = (
        Path(__file__).resolve().parent.parent / "migrations" / "0017_indicator_timeseries.sql"
    ).read_text(encoding="utf-8")
    for durum in ("pending", "delayed", "published", "occurred", "cancelled"):
        assert f"'{durum}'" in sema, durum


def test_published_is_never_equal_to_cancelled() -> None:
    """**Faz 1.2 değişmezi.**

    Kurumun yayımladığı ama bizim görmediğimiz bir yayın, hiç
    gerçekleşmemiş bir yayınla aynı kefeye konulamaz — konulursa kaynak
    kör noktasını gösteren tek sinyal sessizce yok olur.
    """
    assert ee._STATE_MAP["published"] != ee._STATE_MAP["cancelled"]  # noqa: SLF001
    assert ee._STATE_MAP["published"] == "published"  # noqa: SLF001
    assert ee._STATE_MAP["cancelled"] == "cancelled"  # noqa: SLF001


def test_the_three_delay_meanings_are_distinct_states() -> None:
    esler = {ee._STATE_MAP[k] for k in ("delayed", "published", "occurred")}  # noqa: SLF001
    assert len(esler) == 3


def test_marking_delayed_touches_only_pending_records() -> None:
    """`published` bir kayıt "gecikmiş" DEĞİLDİR — kurum onu yayımlamıştır.

    Eksik olan bizim görmemizdir ve o ayrı bir sinyaldir.
    """
    kaynak = inspect.getsource(ee.mark_delayed)
    assert "status = 'pending'" in kaynak
    assert "SET status = 'delayed'" in kaynak
    assert "'published'" not in kaynak.split("WHERE")[1]


# ═══════════════════════════════ 2. gecikme resmî zamandan ölçülür
def test_delay_is_measured_from_the_official_expected_timestamp() -> None:
    beklenen = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)
    gorulen = datetime(2026, 8, 19, 10, 45, tzinfo=UTC)
    assert _delay_minutes(beklenen, gorulen) == 45


def test_negative_delay_is_preserved_not_clamped() -> None:
    """Haberi resmî saatten ÖNCE görmek mümkündür ve gerçektir.

    Sıfıra kırpmak, ölçümü yalancı yapar.
    """
    beklenen = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)
    gorulen = datetime(2026, 8, 19, 9, 5, tzinfo=UTC)
    assert _delay_minutes(beklenen, gorulen) == -55


def test_unknown_delay_is_none_not_zero() -> None:
    """"Ne kadar geciktiği bilinmiyor" ile "hiç gecikmedi" ayrı şeylerdir."""
    beklenen = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)
    assert _delay_minutes(beklenen, None) is None
    assert _delay_minutes(None, beklenen) is None


def test_no_guessed_expected_timestamp() -> None:
    """Beklenen zaman TAHMİN EDİLMEZ; takvim kaydından gelir."""
    kaynak = inspect.getsource(ee)
    assert "se.expected_at" in kaynak
    for yasak in ("estimate", "guess", "assume_at", "tahmin_et"):
        assert yasak not in kaynak.lower(), yasak


# ═══════════════════════════════ 3. hoşgörü penceresi
def test_tolerance_window_exists_and_is_documented() -> None:
    assert TOLERANCE.total_seconds() > 0
    assert ABANDON_AFTER > TOLERANCE


def test_tolerance_is_consistent_with_the_matcher_window() -> None:
    """Eşleştirici hâlâ ararken "gecikti" demek kendimizle çelişmektir."""
    from politikdesk.context.scheduler_match import MATCH_WINDOW

    assert TOLERANCE <= MATCH_WINDOW


def test_abandon_threshold_matches_the_calendar_module() -> None:
    """İki modül aynı olayı farklı adlandırmamalı."""
    assert ABANDON_AFTER.total_seconds() == 48 * 3600


# ═══════════════════════════════ 4. deterministik eşleştirme
def test_matching_is_deterministic_and_not_llm_based() -> None:
    """⛔ Birincil eşleştirme LLM anlamsal benzerliğiyle YAPILMAZ."""
    from politikdesk.context import scheduler_match

    agac = ast.parse(inspect.getsource(scheduler_match))
    moduller: set[str] = set()
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            moduller |= {a.name for a in dugum.names}
        elif isinstance(dugum, ast.ImportFrom) and dugum.module:
            moduller.add(dugum.module)
    assert not {m for m in moduller if m.startswith("politikdesk.llm")}


def test_matching_uses_source_and_time_not_text_similarity() -> None:
    kaynak = inspect.getsource(__import__(
        "politikdesk.context.scheduler_match", fromlist=["match_pending"]
    ).match_pending)
    assert "a.source_id" in kaynak
    assert "first_reported_at BETWEEN" in kaynak


# ═══════════════════════════════ 5. sinyal modeli
def test_signal_keeps_dimensions_visible_not_collapsed() -> None:
    """Kaynak kalitesi, tazelik ve bağımsızlık tek bir opak "güven"
    sayısına ÇARPILMAZ (Faz 3 yetkisi)."""
    from dataclasses import fields

    alanlar = {f.name for f in fields(ExpectationSignal)}
    assert "confidence" not in alanlar
    assert "score" not in alanlar
    for gerekli in ("institution", "expected_at", "observed_at", "delay_minutes", "state"):
        assert gerekli in alanlar, gerekli


def test_signal_links_back_to_the_official_calendar_record() -> None:
    s = _sinyal()
    assert s.scheduled_id > 0
    assert s.as_dict()["scheduled_id"] == s.scheduled_id


def test_signal_carries_provenance_url_and_period() -> None:
    s = _sinyal()
    d = s.as_dict()
    assert d["url"] and d["reference_period"]


@pytest.mark.parametrize(
    "fn,tur",
    [
        ("upcoming", "upcoming_release"),
        ("delayed", "release_delayed"),
        ("observation_gaps", "observation_gap"),
        ("observed", "release_observed"),
    ],
)
def test_each_query_declares_its_signal_type(fn: str, tur: str) -> None:
    kaynak = inspect.getsource(getattr(ee, fn))
    assert f'signal_type="{tur}"' in kaynak


# ═══════════════════════════════ 6. gözlem boşluğu
def test_observation_gap_requires_published_without_a_linked_event() -> None:
    """"Kurum yayımladı ama biz görmedik" tam olarak bu koşuldur."""
    kaynak = inspect.getsource(ee.observation_gaps)
    assert "se.status = 'published'" in kaynak
    assert "se.linked_event_id IS NULL" in kaynak


def test_observation_gap_is_not_confused_with_institutional_delay() -> None:
    gap = inspect.getsource(ee.observation_gaps)
    gec = inspect.getsource(ee.delayed)
    assert "'published'" in gap and "'delayed'" in gec
    assert "'delayed'" not in gap


# ═══════════════════════════════ 7. mimari
def test_expected_events_module_does_not_import_llm() -> None:
    agac = ast.parse(inspect.getsource(ee))
    moduller: set[str] = set()
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            moduller |= {a.name for a in dugum.names}
        elif isinstance(dugum, ast.ImportFrom) and dugum.module:
            moduller.add(dugum.module)
    assert not {m for m in moduller if m.startswith("politikdesk.llm")}


def test_engine_reuses_the_calendar_instead_of_duplicating_it() -> None:
    """Takvim bilgisi ikinci bir sistemde YENİDEN ÜRETİLMEZ."""
    kaynak = inspect.getsource(ee)
    assert "scheduled_events" in kaynak
    assert "CREATE TABLE" not in kaynak


# ═══════════════════════════════ 8. canlı şema
@pytest.mark.db
def test_queries_run_against_the_live_schema() -> None:
    assert isinstance(ee.mark_delayed(), dict)
    for fn in (ee.upcoming, ee.delayed, ee.observation_gaps, ee.observed):
        for s in fn(limit=5):
            assert s.state in {
                "expected", "delayed", "published", "occurred", "cancelled", "unavailable"
            }


@pytest.mark.db
def test_summary_reports_observation_gap_separately() -> None:
    ozet = ee.summary()
    assert "observation_gap" in ozet
