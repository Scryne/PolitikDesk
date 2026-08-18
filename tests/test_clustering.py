"""Faz 2 İş Kolu A testleri — F2-01 (assigner), F2-02 (centroid), F2-03 (numeric_guard).

Bu testlerin hiçbiri veritabanı gerektirmez: karar mantığı bilinçli olarak
saftır (bkz. assigner.py modül açıklaması). F2-14 eşik kalibrasyonunun
koşulabilmesi buna bağlıdır.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest

from politikdesk.clustering.assigner import (
    ArticleFeatures,
    Assignment,
    EventCandidate,
    Thresholds,
    decide,
)
from politikdesk.clustering.centroid import (
    add_member,
    cosine,
    drift,
    is_recomputable,
    recompute,
    remove_member,
)
from politikdesk.clustering.indicators import detect_indicators, indicators_conflict
from politikdesk.clustering.numeric_guard import extract_numbers, find_conflicts

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


# ==========================================================================
# F2-03 — sayısal çelişki bayrağı
# ==========================================================================
def test_extracts_policy_rate_from_official_wording() -> None:
    """Gerçek TCMB duyuru cümlesi (2026-28)."""
    text = (
        "Para Politikası Kurulu (Kurul), politika faizi olan bir hafta vadeli repo "
        "ihale faiz oranının yüzde 37'de sabit tutulmasına karar vermiştir."
    )
    metrics = {m.metric: m.value for m in extract_numbers(text)}
    assert metrics["policy_rate"] == 37.0


def test_numbers_without_a_metric_are_discarded() -> None:
    """'23 çeyrektir büyüdü' bir yüzde değildir; bayrağı kirletmemeli."""
    assert extract_numbers("Türkiye ekonomisi art arda 23 çeyrektir büyüdü.") == []


def test_dod_case_forty_versus_fortytwo() -> None:
    """F2-03 DoD: 'faiz %40' ile 'faiz %42' çelişki üretmeli."""
    conflicts = find_conflicts(
        "Merkez Bankası politika faizini yüzde 40 seviyesinde tuttu.",
        "Merkez Bankası politika faizini yüzde 42 seviyesinde tuttu.",
    )
    assert len(conflicts) == 1
    assert conflicts[0].metric == "policy_rate"
    assert {conflicts[0].left, conflicts[0].right} == {40.0, 42.0}


def test_same_value_written_differently_is_not_a_conflict() -> None:
    conflicts = find_conflicts(
        "Politika faizi yüzde 37 olarak açıklandı.",
        "Politika faizi %37 seviyesinde sabit tutuldu.",
    )
    assert conflicts == []


def test_missing_metric_on_one_side_is_not_a_conflict() -> None:
    """Eksik bilgi ≠ çelişkili bilgi."""
    assert (
        find_conflicts(
            "Politika faizi yüzde 37 olarak açıklandı.",
            "Merkez Bankası kararını açıkladı.",
        )
        == []
    )


def test_real_world_industrial_production_contradiction() -> None:
    """Gerçek örnek: iki kaynak aynı TÜİK bülteni için farklı sayı verdi.

    eval/pairs_tr.jsonl p021 — bir kaynak yıllık düşüşü %1,4, diğeri %1,8
    olarak aktardı. Bu ikisi aynı olaydır ve `needs_review` gerektirir.
    """
    conflicts = find_conflicts(
        "Verilere göre sanayi üretimi, haziranda yıllık bazda yüzde 1,4 geriledi.",
        "Buna göre sanayi üretimi, haziranda geçen yılın aynı ayına göre yüzde 1,8 azaldı.",
    )
    assert [c.metric for c in conflicts] == ["industrial_production"]


def test_multiple_values_for_same_metric_do_not_conflict_if_they_overlap() -> None:
    """Bir haber hem eski hem yeni faizi verebilir; kesişim varsa çelişki yok."""
    assert (
        find_conflicts(
            "Politika faizi yüzde 39,5'ten yüzde 38'e indirildi.",
            "Politika faizi yüzde 38 olarak belirlendi.",
        )
        == []
    )


def test_distinct_rates_in_one_sentence_are_not_confused() -> None:
    """Aynı cümlede üç farklı faiz geçer; her biri kendi metriğine bağlanmalı."""
    text = (
        "politika faizi olan bir hafta vadeli repo ihale faiz oranının yüzde 37'de "
        "sabit tutulmasına karar vermiştir. Kurul ayrıca, Merkez Bankası gecelik "
        "vadede borç verme faiz oranını yüzde 40'ta, gecelik vadede borçlanma faiz "
        "oranını ise yüzde 35,5'te sabit tutmuştur."
    )
    metrics = {m.metric: m.value for m in extract_numbers(text)}
    assert metrics["policy_rate"] == 37.0
    assert metrics["overnight_lending_rate"] == 40.0
    assert metrics["overnight_borrowing_rate"] == 35.5


# ==========================================================================
# F2-02 — merkez güncelleme
# ==========================================================================
def test_incremental_mean_equals_recomputed_mean() -> None:
    rng = random.Random(20260812)
    vectors = [[rng.uniform(-1, 1) for _ in range(64)] for _ in range(50)]

    centroid: list[float] | None = None
    for i, v in enumerate(vectors):
        centroid = add_member(centroid, i, v)

    assert centroid is not None
    assert is_recomputable(centroid, vectors)


def test_drift_stays_within_tolerance_over_long_sequence() -> None:
    """F2-02 DoD 'drift testi': 500 artımlı güncelleme sonrası sapma."""
    rng = random.Random(7)
    vectors = [[rng.gauss(0, 1) for _ in range(32)] for _ in range(500)]

    centroid: list[float] | None = None
    for i, v in enumerate(vectors):
        centroid = add_member(centroid, i, v)

    recomputed = recompute(vectors)
    assert centroid is not None and recomputed is not None
    assert drift(centroid, recomputed) < 1e-9


def test_remove_member_reverses_add_member() -> None:
    """G2 koşul 8: merge/split %100 geri alınabilir olmalı."""
    rng = random.Random(3)
    members = [[rng.uniform(-1, 1) for _ in range(16)] for _ in range(6)]

    centroid: list[float] | None = None
    for i, v in enumerate(members):
        centroid = add_member(centroid, i, v)
    assert centroid is not None

    intruder = [rng.uniform(-1, 1) for _ in range(16)]
    polluted = add_member(centroid, len(members), intruder)
    restored = remove_member(polluted, len(members) + 1, intruder)

    assert restored is not None
    assert drift(restored, centroid) < 1e-9


def test_removing_the_last_member_yields_undefined_centroid() -> None:
    """Sıfır vektör döndürmek 'her şeye eşit uzak' merkez üretirdi."""
    assert remove_member([1.0, 2.0], 1, [1.0, 2.0]) is None


def test_centroid_is_not_normalised_so_that_mean_identity_holds() -> None:
    """Merkez normalize edilseydi remove_member bozulurdu."""
    centroid = add_member(add_member(None, 0, [3.0, 4.0]), 1, [3.0, 4.0])
    assert centroid == [3.0, 4.0]  # normalize edilseydi [0.6, 0.8] olurdu


def test_cosine_is_scale_invariant() -> None:
    assert cosine([1.0, 0.0], [7.0, 0.0]) == pytest.approx(1.0)


def test_dimension_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="Boyut uyuşmazlığı"):
        add_member([1.0, 2.0], 1, [1.0])


# ==========================================================================
# F2-01 — atama kararı
# ==========================================================================
def _article(**over: object) -> ArticleFeatures:
    base = {
        "article_id": 1,
        "embedding": [1.0, 0.0],
        "entities": frozenset({"Türkiye Cumhuriyet Merkez Bankası", "Para Politikası Kurulu"}),
        "key_entities": frozenset({"Türkiye Cumhuriyet Merkez Bankası"}),
        "published_at": NOW,
        "text": "Politika faizi yüzde 37'de sabit tutuldu.",
    }
    base.update(over)
    return ArticleFeatures(**base)  # type: ignore[arg-type]


def _candidate(**over: object) -> EventCandidate:
    base = {
        "event_id": 10,
        "similarity": 0.93,
        "entities": frozenset({"Türkiye Cumhuriyet Merkez Bankası", "Para Politikası Kurulu"}),
        "key_entities": frozenset({"Türkiye Cumhuriyet Merkez Bankası"}),
        "last_update_at": NOW - timedelta(hours=2),
        "text_sample": "TCMB politika faizini yüzde 37'de sabit bıraktı.",
    }
    base.update(over)
    return EventCandidate(**base)  # type: ignore[arg-type]


def test_no_candidates_creates_a_new_event() -> None:
    result = decide(_article(), [])
    assert result.action == "create"
    assert result.event_id is None


def test_high_similarity_assigns_automatically() -> None:
    result = decide(_article(), [_candidate(similarity=0.93)])
    assert result.action == "assign"
    assert result.event_id == 10
    assert result.needs_review is False


def test_similarity_between_thresholds_goes_to_review_queue() -> None:
    """Spec §11.4: T_LOW <= sim < T_HIGH -> geçici atama + denetim kuyruğu."""
    result = decide(_article(), [_candidate(similarity=0.81)])
    assert result.action == "review"
    assert result.event_id == 10
    assert result.needs_review is True
    assert result.review_reason is not None
    assert "similarity_between_thresholds" in result.review_reason


def test_similarity_below_t_low_creates_a_new_event() -> None:
    result = decide(_article(), [_candidate(similarity=0.5)])
    assert result.action == "create"
    assert result.trace[0].outcome == "below_t_low"


def test_time_window_rejects_an_otherwise_perfect_match() -> None:
    """Benzerlik tek başına yetmez — iki ardışık PPK kararı bu kısıtla ayrılır.

    D16 tanı koşumu (docs/embedding-benchmark.md) gösterdi ki iki ardışık
    faiz duyurusu metinsel olarak birebir aynıdır (cosine 0,997). Onları
    ayıran tek sinyal zamandır.
    """
    result = decide(
        _article(),
        [_candidate(similarity=0.997, last_update_at=NOW - timedelta(days=42))],
    )
    assert result.action == "create"
    assert result.trace[0].outcome == "time_reject"
    assert result.trace[0].time_ok is False


def test_entity_constraint_rejects_unrelated_event_with_high_similarity() -> None:
    result = decide(
        _article(),
        [
            _candidate(
                similarity=0.95,
                entities=frozenset({"Borsa İstanbul"}),
                key_entities=frozenset(),
            )
        ],
    )
    assert result.action == "create"
    assert result.trace[0].outcome == "entity_reject"
    assert result.trace[0].entity_jaccard == 0.0


def test_shared_key_entity_rescues_a_low_jaccard_pair() -> None:
    """Kısa resmî duyuru ile uzun haber: Jaccard düşük, ortak anahtar varlık var."""
    result = decide(
        _article(entities=frozenset({"Türkiye Cumhuriyet Merkez Bankası"})),
        [
            _candidate(
                similarity=0.90,
                entities=frozenset(
                    {
                        "Türkiye Cumhuriyet Merkez Bankası",
                        "Borsa İstanbul",
                        "Hazine ve Maliye Bakanlığı",
                        "Fitch Ratings",
                        "Moody's",
                    }
                ),
            )
        ],
    )
    assert result.action == "assign"
    assert result.trace[0].entity_jaccard < 0.25
    assert result.trace[0].shared_key_entities == ("Türkiye Cumhuriyet Merkez Bankası",)


def test_numeric_conflict_keeps_assignment_but_flags_review() -> None:
    """F2-03 DoD: aynı olaya atanır, ama `needs_review` işaretlenir."""
    result = decide(
        _article(text="Merkez Bankası politika faizini yüzde 40'a çekti."),
        [
            _candidate(
                similarity=0.95,
                text_sample="Merkez Bankası politika faizini yüzde 42'ye çekti.",
            )
        ],
    )
    assert result.action == "review"
    assert result.event_id == 10
    assert result.needs_review is True
    assert result.review_reason == "numeric_conflict"
    assert [c.metric for c in result.numeric_conflicts] == ["policy_rate"]


def test_best_candidate_wins_among_several_above_t_high() -> None:
    result = decide(
        _article(),
        [
            _candidate(event_id=1, similarity=0.88),
            _candidate(event_id=2, similarity=0.95),
            _candidate(event_id=3, similarity=0.91),
        ],
    )
    assert result.event_id == 2


def test_t_high_candidate_beats_t_low_candidate() -> None:
    result = decide(
        _article(),
        [_candidate(event_id=1, similarity=0.80), _candidate(event_id=2, similarity=0.87)],
    )
    assert result.action == "assign"
    assert result.event_id == 2


def test_trace_records_every_candidate_for_transparency() -> None:
    """P4: 'neden bu olaya atanmadı?' cevaplanabilir olmalı."""
    result = decide(
        _article(),
        [
            _candidate(event_id=1, similarity=0.95, last_update_at=NOW - timedelta(days=9)),
            _candidate(event_id=2, similarity=0.40),
            _candidate(event_id=3, similarity=0.90),
        ],
    )
    assert [t.event_id for t in result.trace] == [1, 2, 3]
    assert [t.outcome for t in result.trace] == ["time_reject", "below_t_low", "accepted"]


def test_thresholds_must_be_ordered() -> None:
    with pytest.raises(ValueError, match="t_low < t_high"):
        Thresholds(t_high=0.7, t_low=0.8)


def test_assignment_creates_event_property() -> None:
    assert Assignment(action="create").creates_event is True
    assert Assignment(action="assign", event_id=1).creates_event is False


# --------------------------------------------------------------------------
# Varlık kısıtının uygulanamadığı durum — ilk canlı koşumda bulundu
# --------------------------------------------------------------------------
def test_two_entityless_articles_can_still_cluster() -> None:
    """Spec §11.4 boş varlık kümesini tanımlamıyor; harfiyen uygulanırsa
    `jaccard(∅, ∅) = 0` çıkar ve kısıt reddeder.

    Canlı koşumda 11 makalenin 6'sında hiç varlık yoktu; aynı olayı anlatan
    ve 0,9997 benzerlikteki iki makale yalnızca bu yüzden ayrı düştü.
    Boş küme çelişki kanıtı değil, kanıt yokluğudur.
    """
    result = decide(
        _article(
            entities=frozenset(),
            key_entities=frozenset(),
            text="Ulaştırma yatırımlarına 6 ayda 41,5 milyar lira harcandı.",
        ),
        [
            _candidate(
                similarity=0.9997,
                entities=frozenset(),
                key_entities=frozenset(),
                text_sample="Ulaştırma yatırımlarına 6 ayda 41,5 milyar harcandı.",
            )
        ],
    )
    assert result.action == "review"
    assert result.event_id == 10
    assert result.needs_review is True
    assert result.review_reason == "entity_constraint_unverifiable"
    assert result.trace[0].outcome == "entity_unverified"


def test_unverifiable_entity_constraint_does_not_grant_automatic_assignment() -> None:
    """Precision önceliği: doğrulanamayan kısıt otomatik atama hakkı vermez."""
    result = decide(
        _article(entities=frozenset(), key_entities=frozenset()),
        [_candidate(similarity=0.90, entities=frozenset(), key_entities=frozenset())],
    )
    assert result.action != "assign"


def test_below_t_high_with_unverifiable_constraint_creates_new_event() -> None:
    """T_HIGH altındaysa denetim kuyruğuna bile alınmaz — yeni olay olur."""
    result = decide(
        _article(entities=frozenset(), key_entities=frozenset()),
        [_candidate(similarity=0.82, entities=frozenset(), key_entities=frozenset())],
    )
    assert result.action == "create"
    assert result.trace[0].outcome == "below_t_low"


def test_contradicting_entities_are_still_a_hard_reject() -> None:
    """İki taraf da doluysa ve örtüşmüyorsa kısıt hâlâ REDDEDER."""
    result = decide(
        _article(
            entities=frozenset({"Türkiye İstatistik Kurumu"}),
            key_entities=frozenset({"Türkiye İstatistik Kurumu"}),
        ),
        [
            _candidate(
                similarity=0.99, entities=frozenset({"Borsa İstanbul"}), key_entities=frozenset()
            )
        ],
    )
    assert result.action == "create"
    assert result.trace[0].outcome == "entity_reject"
    assert result.trace[0].entity_verdict == "reject"


def test_verified_constraint_still_assigns_automatically() -> None:
    """Regresyon: normal yol değişmedi."""
    assert decide(_article(), [_candidate(similarity=0.93)]).action == "assign"


# ==========================================================================
# B-62 — gösterge ayırıcısı
#
# docs/FAZ2-DURUM.md bulgu 3: kalan precision açığının TAMAMI tek bir hata
# ailesindendi — aynı kurumun aynı gün yayımladığı farklı göstergeler.
# Golden Set'te TÜİK'in sanayi üretimi bülteni ile dış ticaret endeksi
# bülteni tek olaya birleşiyordu.
# ==========================================================================
def test_detects_indicator_family_without_any_number() -> None:
    """Gösterge tespiti sayıya bağlı DEĞİLDİR.

    "TÜİK işsizlik oranını açıkladı" cümlesinde hiç sayı yok ama gösterge
    bellidir; `numeric_guard` bu cümlede hiçbir şey bulamaz.
    """
    assert detect_indicators("TÜİK işsizlik oranını açıkladı") == frozenset({"unemployment"})
    assert extract_numbers("TÜİK işsizlik oranını açıkladı") == []


def test_different_indicators_conflict() -> None:
    assert indicators_conflict(
        "Sanayi üretimi verileri aylık arttı, yıllık geriledi",
        "TÜİK haziran ayı dış ticaret endekslerini açıkladı",
    )


def test_same_indicator_does_not_conflict() -> None:
    assert not indicators_conflict(
        "Sanayi üretimi Haziran'da yıllık yüzde 1,4 azaldı",
        "Sanayi üretimi verileri aylık arttı, yıllık geriledi",
    )


def test_empty_indicator_side_never_conflicts() -> None:
    """Boş küme kanıt yokluğudur, çelişki kanıtı değildir (Spec §11.4 dersi).

    Aksi halde sözlüğün tanımadığı her makale sonsuza dek tek başına
    kalırdı — `_entity_check`'te aynı hata bir kez yapılmıştı.
    """
    assert not indicators_conflict("Sanayi üretimi arttı", "TÜİK verilerini açıkladı")
    assert not indicators_conflict("", "Sanayi üretimi arttı")


def test_indicator_clash_blocks_assignment_despite_high_similarity() -> None:
    """Asıl regresyon testi: benzerlik yüksek olsa bile ayrı olay.

    Bu çift Golden Set'te 0,9+ benzerlikle aynı olaya düşüyordu.
    """
    article = _article(
        text="Sanayi üretimi Haziran'da yıllık yüzde 1,4 azaldı",
        entities=frozenset({"Türkiye İstatistik Kurumu"}),
        key_entities=frozenset({"Türkiye İstatistik Kurumu"}),
    )
    candidate = _candidate(
        similarity=0.97,
        text_sample="TÜİK haziran ayı dış ticaret endekslerini açıkladı",
        entities=frozenset({"Türkiye İstatistik Kurumu"}),
        key_entities=frozenset({"Türkiye İstatistik Kurumu"}),
    )
    result = decide(article, [candidate])
    assert result.action == "create"
    assert result.trace[0].outcome == "indicator_reject"
    assert result.trace[0].indicator_conflict is True


def test_same_indicator_still_assigns_at_high_similarity() -> None:
    """Kısıt yalnızca AYIRIR; aynı göstergede kümelemeyi bozmamalı."""
    article = _article(text="Sanayi üretimi Haziran'da yıllık yüzde 1,4 azaldı")
    candidate = _candidate(
        similarity=0.95,
        text_sample="Sanayi üretimi verileri aylık arttı, yıllık geriledi",
    )
    result = decide(article, [candidate])
    assert result.action == "assign"
    assert result.trace[0].indicator_conflict is False


def test_indicator_detection_is_case_and_diacritic_aware() -> None:
    """Türkçe tuzağı: 'İŞSİZLİK' ile 'işsizlik' aynı köke inmeli."""
    assert detect_indicators("İŞSİZLİK ORANI") == detect_indicators("issizlik orani")
