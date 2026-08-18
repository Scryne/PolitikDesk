"""Ölçüm araçları testleri (F0-13, F0-14).

Golden Set doğrulayıcısının gerçekten hata yakaladığını kanıtlar — aksi
halde "set geçerli" çıktısı yanıltıcı bir güvence olur.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from eval.embedding_benchmark import (
    CANDIDATES,
    REQUIRED_DIM,
    Pair,
    cosine,
    recommend_thresholds,
    roc_auc,
    threshold_sweep,
    validate_pairs,
)
from eval.golden_set_tools import (
    VALID_TOPICS,
    validate_articles,
    validate_claims,
)


# ------------------------------------------------------- embedding benchmark
def test_all_candidates_produce_1024_dimensions() -> None:
    """Şema VECTOR(1024) — 1024 üretmeyen aday listeye giremez."""
    for c in CANDIDATES.values():
        assert c.dim == REQUIRED_DIM, f"{c.key} boyutu {c.dim}"


def test_at_least_three_candidates_available() -> None:
    """F0-13 DoD: en az 3 aday."""
    assert len(CANDIDATES) >= 3


def test_cosine_basics() -> None:
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_roc_auc_perfect_separation() -> None:
    scores = [0.9, 0.95, 0.2, 0.1]
    labels = [True, True, False, False]
    assert roc_auc(scores, labels) == pytest.approx(1.0)


def test_roc_auc_random_is_half() -> None:
    scores = [0.5, 0.5, 0.5, 0.5]
    labels = [True, False, True, False]
    assert roc_auc(scores, labels) == pytest.approx(0.5)


def test_roc_auc_requires_both_classes() -> None:
    with pytest.raises(ValueError, match="Hem"):
        roc_auc([0.9, 0.8], [True, True])


def test_recommended_thresholds_favour_precision() -> None:
    """Spec §11.4: yanlış birleştirme, ayrı kalmaktan daha zararlıdır."""
    scores = [0.95, 0.92, 0.90, 0.70, 0.60, 0.50]
    labels = [True, True, True, False, False, False]
    t_high, t_low = recommend_thresholds(threshold_sweep(scores, labels))
    assert t_low < t_high
    assert t_high >= 0.90


def _pairs(same: int, diff: int, hard: int = 10) -> list[Pair]:
    out: list[Pair] = []
    for i in range(same):
        out.append(Pair(f"s{i}", "a", "b", True, "hard" if i < hard // 2 else "easy"))
    for i in range(diff):
        out.append(Pair(f"d{i}", "a", "b", False, "hard" if i < hard // 2 else "easy"))
    return out


def test_pair_validation_accepts_conforming_set() -> None:
    assert validate_pairs(_pairs(30, 30)) == []


def test_pair_validation_rejects_too_few_pairs() -> None:
    problems = validate_pairs(_pairs(10, 10))
    assert any("60" in p for p in problems)


def test_pair_validation_rejects_unbalanced_set() -> None:
    problems = validate_pairs(_pairs(50, 15))
    assert any("farklı olay" in p for p in problems)


def test_pair_validation_catches_duplicate_ids() -> None:
    pairs = [Pair("dup", "a", "b", True), Pair("dup", "a", "b", False)]
    assert any("Yinelenen" in p for p in validate_pairs(pairs))


# ------------------------------------------------------------- golden set
def _article(**over: object) -> dict:
    base = {
        "article_id": "gs-0001",
        "source_slug": "tuik",
        "title": "Baslik",
        "event_id": "evt-1",
        "topic": "enflasyon",
        "difficulty": "easy",
    }
    base.update(over)  # type: ignore[arg-type]
    return base


def test_article_validation_catches_missing_fields() -> None:
    problems = validate_articles([{"article_id": "gs-1"}])
    assert any("eksik alan" in p for p in problems)


def test_article_validation_catches_duplicate_ids() -> None:
    rows = [_article(), _article(event_id="evt-2")]
    assert any("yinelenen article_id" in p for p in validate_articles(rows))


def test_article_validation_rejects_topic_outside_mvp_scope() -> None:
    """MVP dikeyi makro ekonomi — kapsam dışı konu sete giremez (D4)."""
    problems = validate_articles([_article(topic="dis_politika")])
    assert any("MVP konu listesinde yok" in p for p in problems)


def test_mvp_topic_list_has_ten_entries() -> None:
    """Spec §5: MVP dikeyi 10 konuyla sınırlı."""
    assert len(VALID_TOPICS) == 10


def test_article_validation_requires_hard_clusters() -> None:
    """F0-14 DoD: en az 5 zor küme."""
    rows = [
        _article(article_id=f"gs-{i}", event_id=f"evt-{i // 2}", difficulty="easy")
        for i in range(20)
    ]
    assert any("zor" in p for p in validate_articles(rows))


def test_article_validation_flags_mostly_singleton_events() -> None:
    """Tek makalelik olaylar kümeleme ölçümünü anlamsızlaştırır."""
    rows = [_article(article_id=f"gs-{i}", event_id=f"evt-{i}") for i in range(20)]
    assert any("tek makaleli" in p for p in validate_articles(rows))


def _claim(**over: object) -> dict:
    base = {
        "claim_id": "gc-1",
        "event_id": "evt-1",
        "claim_text": "Mayis TUFE aylik %3 artti.",
        "claim_type": "number",
        "expected_status": "strongly_corroborated",
        "normalized_value": {
            "metric": "tufe_monthly",
            "value": 3.0,
            "unit": "%",
            "period": "2026-05",
        },
    }
    base.update(over)  # type: ignore[arg-type]
    return base


def test_claim_validation_accepts_valid_claim() -> None:
    assert validate_claims([_claim()], {"evt-1"}) == []


def test_claim_validation_enforces_rule_r0() -> None:
    """Spec §8.3 R0: tahmin tipi iddia HER ZAMAN unverified."""
    bad = _claim(
        claim_type="prediction",
        expected_status="strongly_corroborated",
        normalized_value=None,
    )
    problems = validate_claims([bad], {"evt-1"})
    assert any("R0 ihlali" in p for p in problems)


def test_claim_validation_rejects_prediction_labelled_with_evidence_rule() -> None:
    """Spec §8.3 (v3.1): R0 kısa devre yapar — tahmin R1'e düşemez.

    İtiraz-4'ün tam olarak yakaladığı durum: bir tahmin hakkında hem
    destekleyen hem çelişen Tier 1-2 kanıt varsa eski sıralamada R1
    (contradicted) kazanıyordu. Golden Set bu etiketi kabul etmemeli.
    """
    bad = _claim(
        claim_type="prediction",
        expected_status="unverified",
        expected_rule="R1",
        normalized_value=None,
    )
    problems = validate_claims([bad], {"evt-1"})
    assert any("kisa devre ihlali" in p for p in problems)


def test_claim_validation_accepts_prediction_with_r0() -> None:
    ok = _claim(
        claim_type="prediction",
        expected_status="unverified",
        expected_rule="R0",
        normalized_value=None,
    )
    assert validate_claims([ok], {"evt-1"}) == []


def test_claim_validation_requires_normalized_value_for_numbers() -> None:
    """F2-08 sayısal normalizasyon doğruluğu bu alana dayanır."""
    problems = validate_claims([_claim(normalized_value=None)], {"evt-1"})
    assert any("normalized_value" in p for p in problems)


def test_claim_validation_catches_orphan_event_reference() -> None:
    problems = validate_claims([_claim(event_id="evt-yok")], {"evt-1"})
    assert any("makale setinde yok" in p for p in problems)


def test_claim_validation_rejects_invalid_status() -> None:
    problems = validate_claims([_claim(expected_status="probably_true")], {"evt-1"})
    assert any("expected_status" in p for p in problems)


# ---------------------------------------------------------------------------
# B-73 — Golden Set kanıt metinlerinde ondalık ayracı
#
# Normalleştirme sırasında virgüller düşmüştü ("4 milyar 918 2 milyon").
# `grounding_check` kanıtta iki ayrı sayı görüyor, modelin DOĞRU okuması
# ("918,2") uydurma sayılıyordu — yani sayısal grounding bu fikstür
# üzerinde ölçülemiyordu (bkz. docs/llm-generation-benchmark.md bulgu 2).
# ---------------------------------------------------------------------------

GOLDEN_CLAIMS = Path(__file__).resolve().parent.parent / "eval" / "golden_claims_v1.jsonl"

# "12 8" gibi YALNIZCA boşlukla ayrılmış iki sayı: kaybolmuş bir ondalık
# ayracının izi.
#
# Türkçe sayı sözcüğüyle kurulan biçimler ("25 bin 993", "4 milyar 918,2
# milyon") bu kalıba zaten TAKILMAZ, çünkü aradaki sözcük eşleşmeyi böler.
# Bu yüzden ayrıca bir muafiyet listesi YOK: muafiyet eklemek, "milyar"
# sözcüğünü gördüğü için gerçek `918 2` hatasını yutuyordu.
_SPLIT_NUMBER = re.compile(r"\d+\s+\d+")


def _golden_evidence() -> list[tuple[str, str, str]]:
    rows = [
        json.loads(line)
        for line in GOLDEN_CLAIMS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [
        (row["claim_id"], ev["source_slug"], ev["text"])
        for row in rows
        for ev in row.get("evidence", [])
    ]


def test_golden_evidence_has_no_split_decimals() -> None:
    """Kanıt metinlerinde bölünmüş ondalık kalmamalı.

    Kalırsa sayısal grounding ölçümü sessizce anlamsızlaşır: doğru okuyan
    model ihlal işaretlenir ve G3 #2 yanlış ölçülür.
    """
    offenders = [
        (claim_id, slug, text)
        for claim_id, slug, text in _golden_evidence()
        if _SPLIT_NUMBER.search(text)
    ]
    assert not offenders, f"Bölünmüş ondalık içeren kanıt metinleri: {offenders}"


def test_golden_evidence_decimals_match_normalized_value() -> None:
    """Kanıttaki sayı, iddianın normalize edilmiş değeriyle uyuşmalı.

    Onarım sırasında virgülün YANLIŞ yere konması (7,6 yerine 76) bu
    testle yakalanır — fikstür kendi kendini doğrular.
    """
    rows = [
        json.loads(line)
        for line in GOLDEN_CLAIMS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    checked = 0
    for row in rows:
        normalized = row.get("normalized_value")
        if not normalized or normalized.get("unit") != "%":
            continue
        # İşaret normalize değerde taşınır ("-1.4"); metinde "geriledi" der.
        needle = f"{abs(normalized['value'])}".replace(".", ",")
        texts = " ".join(ev["text"] for ev in row.get("evidence", []))
        if needle in texts:
            checked += 1
    assert checked >= 5, f"Yalnızca {checked} iddiada kanıt–değer eşleşmesi doğrulanabildi"
