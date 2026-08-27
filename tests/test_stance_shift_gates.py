"""Söylem kayması kapılarının deterministik testleri (ADR-010 §5).

⛔ NEDEN SENTETİK VERİ

Kapılar gerçek külliyatta sınanamıyor: konuşan atfı olan iddialar
yalnızca **6 günlük** bir pencerede (2026-08-13 → 08-19) ve zaman kapısı
7 gün istiyor. Yani canlı veride hiçbir çift üç kapıyı birden geçemez —
ama bu, kapıların DOĞRU çalıştığının kanıtı değildir; yalnızca hiç
tetiklenmediğinin kanıtıdır.

Eşiği veriye uydurmak (7 → 3 gün) yanlış olurdu: eşik olgunun
doğasından gelir, külliyatın uzunluğundan değil. Bunun yerine kapı
davranışı burada sentetik kayıtlarla sabitlenir.
"""

from __future__ import annotations

from politikdesk.political_memory.service import ActorMemory, MemoryEntry
from politikdesk.political_memory.stance_shift import (
    CONCEPT_LABELS,
    MIN_DAYS_FOR_REVERSAL,
    MIN_TOPIC_OVERLAP,
    _confidence,
    _topic_overlap,
    detect_stance_shifts_from_memory,
)

# Aynı kavramda (para politikası) zıt kutuplu iki beyan.
_ONCE = "Faiz artırımı şarttır, sıkılaşma sürmelidir."
_SONRA = "Faiz indirimi zamanı geldi, parasal gevşeme başlamalıdır."


def _kayit(
    event_id: int,
    metin: str,
    tarih: str,
    *,
    guclu: bool = True,
    konular: tuple[str, ...] = ("para_politikasi",),
) -> MemoryEntry:
    return MemoryEntry(
        event_id=event_id,
        event_title=f"Olay {event_id}",
        claim_id=event_id * 10,
        claim_text=metin,
        claim_type="attribution",
        evidence_status="single_source",
        first_reported_at=tarih,
        speaker="Test Aktör" if guclu else None,
        topic_tags=konular,
        attribution_strength="strong" if guclu else "weak",
    )


def _hafiza(kayitlar: list[MemoryEntry]) -> ActorMemory:
    return ActorMemory(
        actor_name="Test Aktör",
        total_claims=len(kayitlar),
        attributions=kayitlar,
    )


def _reversals(mem: ActorMemory) -> list:
    return [s for s in detect_stance_shifts_from_memory(mem) if s.shift_type == "reversal"]


# ═══════════════════════════ temel: üç kapıyı da geçen çift
def test_valid_reversal_passes_all_gates() -> None:
    mem = _hafiza(
        [
            _kayit(1, _ONCE, "2026-01-01T00:00:00+00:00"),
            _kayit(2, _SONRA, "2026-03-01T00:00:00+00:00"),
        ]
    )
    kaymalar = _reversals(mem)
    assert len(kaymalar) == 1
    assert kaymalar[0].topic_or_metric == CONCEPT_LABELS[0]


# ═══════════════════════════ KAPI 1 — atıf sağlamlığı
def test_weak_attribution_is_rejected() -> None:
    """⛔ ADR-010 §1'deki yanlış isnadın tam kaynağı.

    "Aynı olayda adı geçiyor" bir beyanı o aktöre ait yapmaz.
    """
    mem = _hafiza(
        [
            _kayit(1, _ONCE, "2026-01-01T00:00:00+00:00", guclu=False),
            _kayit(2, _SONRA, "2026-03-01T00:00:00+00:00"),
        ]
    )
    assert _reversals(mem) == []


def test_both_sides_must_be_strongly_attributed() -> None:
    mem = _hafiza(
        [
            _kayit(1, _ONCE, "2026-01-01T00:00:00+00:00"),
            _kayit(2, _SONRA, "2026-03-01T00:00:00+00:00", guclu=False),
        ]
    )
    assert _reversals(mem) == []


# ═══════════════════════════ KAPI 2 — konu örtüşmesi
def test_different_topics_are_rejected() -> None:
    """Farklı konulardaki iki beyan "fikir değiştirdi" sayılamaz."""
    mem = _hafiza(
        [
            _kayit(1, _ONCE, "2026-01-01T00:00:00+00:00", konular=("para_politikasi",)),
            _kayit(2, _SONRA, "2026-03-01T00:00:00+00:00", konular=("yargi_ve_hukuk",)),
        ]
    )
    assert _reversals(mem) == []


def test_missing_topic_tags_are_not_treated_as_agreement() -> None:
    """⛔ Etiket YOKLUĞU örtüşme kanıtı değildir.

    1.0 dönseydi, konusu bilinmeyen her çift "aynı konu" sayılırdı —
    bu projede tekrar tekrar ödenen bedel: *ölçülemedi ≠ eşit*.
    """
    assert _topic_overlap((), ()) == 0.0
    assert _topic_overlap(("a",), ()) == 0.0
    mem = _hafiza(
        [
            _kayit(1, _ONCE, "2026-01-01T00:00:00+00:00", konular=()),
            _kayit(2, _SONRA, "2026-03-01T00:00:00+00:00", konular=()),
        ]
    )
    assert _reversals(mem) == []


def test_partial_overlap_below_threshold_is_rejected() -> None:
    """1 ortak / 3 birleşim = 0,33 < 0,5."""
    assert _topic_overlap(("a", "b"), ("a", "c")) < MIN_TOPIC_OVERLAP
    mem = _hafiza(
        [
            _kayit(1, _ONCE, "2026-01-01T00:00:00+00:00", konular=("a", "b")),
            _kayit(2, _SONRA, "2026-03-01T00:00:00+00:00", konular=("a", "c")),
        ]
    )
    assert _reversals(mem) == []


# ═══════════════════════════ KAPI 3 — zaman
def test_same_day_reversal_is_rejected() -> None:
    """Eski çıktıda 67 kaymanın 17'si aynı gün içindeydi."""
    mem = _hafiza(
        [
            _kayit(1, _ONCE, "2026-01-01T08:00:00+00:00"),
            _kayit(2, _SONRA, "2026-01-01T18:00:00+00:00"),
        ]
    )
    assert _reversals(mem) == []


def test_just_below_temporal_threshold_is_rejected() -> None:
    mem = _hafiza(
        [
            _kayit(1, _ONCE, "2026-01-01T00:00:00+00:00"),
            _kayit(2, _SONRA, f"2026-01-0{MIN_DAYS_FOR_REVERSAL}T00:00:00+00:00"),
        ]
    )
    assert _reversals(mem) == []


# ═══════════════════════════ güven skoru artık sabit değil
def test_confidence_varies_with_input() -> None:
    """⛔ Eskiden 50/50 kayıt tam olarak 0,85 taşıyordu.

    Hep aynı olan bir güven skoru bir güven skoru değildir.
    """
    degerler = {
        _confidence(0, 1.0, 200),
        _confidence(0, 0.5, 7),
        _confidence(1, 1.0, 200),
        _confidence(1, 0.5, 7),
    }
    assert len(degerler) == 4


def test_topical_concept_scores_above_generic_stance_verb() -> None:
    """ "Faiz artırımı ↔ indirimi" bir konudur; "destekliyoruz ↔ karşıyız" değil."""
    assert _confidence(0, 1.0, 30) > _confidence(1, 1.0, 30)


def test_confidence_is_bounded() -> None:
    assert 0.0 < _confidence(0, 1.0, 10_000) <= 0.95


# ═══════════════════════════ konu artık kaydediliyor
def test_matched_concept_is_recorded_not_a_constant() -> None:
    """⛔ Eskiden eşleşen kavram atılıp sabit "Politika / Tutum Beyanı" yazılıyordu."""
    mem = _hafiza(
        [
            _kayit(1, _ONCE, "2026-01-01T00:00:00+00:00"),
            _kayit(2, _SONRA, "2026-03-01T00:00:00+00:00"),
        ]
    )
    s = _reversals(mem)[0]
    assert s.topic_or_metric in CONCEPT_LABELS
    assert s.topic_or_metric != "Politika / Tutum Beyanı"


def test_shift_carries_auditable_evidence() -> None:
    """Bir isnadın sonradan açıklanabilmesi için dayanağı saklanmalı."""
    mem = _hafiza(
        [
            _kayit(1, _ONCE, "2026-01-01T00:00:00+00:00"),
            _kayit(2, _SONRA, "2026-03-01T00:00:00+00:00"),
        ]
    )
    md = _reversals(mem)[0].metadata or {}
    for alan in (
        "concept_index",
        "topic_overlap",
        "shared_topics",
        "earlier_speaker",
        "later_speaker",
    ):
        assert alan in md, alan
