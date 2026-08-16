"""Faz 2 İş Kolu C — kanıt motoru (F2-11, F2-12, F2-13, F2-15).

F2-12 DoD: 8 kuralın her biri için birim testi; R0 kısa devresi ayrıca
test edilir; modülde hiçbir LLM çağrısı yok.

Bu testler veritabanı gerektirmez: kanıt motoru saf ve deterministiktir.
"""

from __future__ import annotations

import ast
import inspect
import re
from datetime import UTC, datetime, timedelta

import pytest

from politikdesk.evidence import independence, rules, salience
from politikdesk.evidence.independence import (
    EvidenceArticle,
    breakdown_by_kind,
    has_primary_source,
    independent_count,
    is_copy_paste,
    merge_key,
)
from politikdesk.evidence.rules import Claim, Evidence, compute_status
from politikdesk.evidence.salience import (
    EventSignals,
    displayed_score,
    global_salience,
    personal_adjustment,
)

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
LONG_TEXT = (
    "Para Politikası Kurulu politika faizi olan bir hafta vadeli repo ihale "
    "faiz oranının yüzde 37 seviyesinde sabit tutulmasına karar vermiştir"
)


def _article(article_id: int, slug: str, tier: int, **over: object) -> EvidenceArticle:
    base = {
        "article_id": article_id,
        "source_slug": slug,
        "tier": tier,
        "kind": independence.KIND_BY_TIER[tier],
        "text": f"{slug} metni {article_id} " + LONG_TEXT,
    }
    base.update(over)
    return EvidenceArticle(**base)  # type: ignore[arg-type]


def _supports(*articles: EvidenceArticle) -> list[Evidence]:
    return [Evidence(article=a, stance="supports") for a in articles]


def _claim(**over: object) -> Claim:
    base = {
        "claim_id": 1,
        "claim_text": "Politika faizi yüzde 37'de sabit tutuldu.",
        "claim_type": "fact",
    }
    base.update(over)
    return Claim(**base)  # type: ignore[arg-type]


# ==========================================================================
# F2-11 — bağımsız kanıt sayımı (Spec §8.2)
# ==========================================================================
def test_publisher_group_counts_once() -> None:
    """Kural 1: aynı yayın grubu tek sayılır."""
    a = _article(1, "yayin-a", 3, independence_group="grup-x")
    b = _article(2, "yayin-b", 3, independence_group="grup-x")
    assert independent_count([a, b]) == 1


def test_wire_and_its_copy_count_once() -> None:
    """Kural 2: ajans kopyası ajansın anahtarına düşer.

    Faz 1'de canlı veride yakalanan hata: ajans ile kopyası FARKLI
    anahtarlara düşünce ikisi ayrı sayılıyor ve bağımsız sayım
    sistematik olarak şişiyordu.

    Test edilen sözleşme, anahtarın belirli bir metin olması değil
    **ikisinin aynı anahtara düşmesidir**; anahtar biçimi bir uygulama
    ayrıntısıdır ve F2-16'nın bulgusuyla `grp:` lehine değişti.
    """
    wire = _article(1, "aa-ekonomi", 2, independence_group="wire-aa", simhash=0b1010)
    copy = _article(2, "kopyaci", 3, simhash=0b1011)  # 1 bit fark
    assert merge_key(wire, others=[wire, copy]) == merge_key(copy, others=[wire, copy])
    assert independent_count([wire, copy]) == 1


def test_copy_paste_needs_both_signals() -> None:
    """Kural 3: embedding VE n-gram. Tek sinyal yetmez.

    Yalnız embedding'e bakmak, aynı olayı anlatan iki BAĞIMSIZ haberi kopya
    sayar ve bağımsız sayımı düşürürdü — her şey 🟠'ya kayardı.
    """
    vec = [1.0, 0.0, 0.0]
    same_text = _article(1, "a", 3, embedding=vec, text=LONG_TEXT)
    copied = _article(2, "b", 3, embedding=vec, text=LONG_TEXT + " ek cümle")
    assert is_copy_paste(same_text, copied)

    # Aynı vektör, tamamen farklı ifade -> kopya DEĞİL
    different_wording = _article(
        3,
        "c",
        3,
        embedding=vec,
        text="Enflasyon raporu bilgilendirme toplantısı istanbul finans merkezinde "
        "düzenlenecek ve canlı yayımlanacaktır bugün",
    )
    assert not is_copy_paste(same_text, different_wording)


def test_copy_paste_ignored_when_embeddings_differ() -> None:
    a = _article(1, "a", 3, embedding=[1.0, 0.0], text=LONG_TEXT)
    b = _article(2, "b", 3, embedding=[0.0, 1.0], text=LONG_TEXT)
    assert not is_copy_paste(a, b)


def test_independent_sources_count_separately() -> None:
    articles = [_article(1, "tcmb", 1), _article(2, "aa-ekonomi", 2), _article(3, "dunya", 3)]
    assert independent_count(articles) == 3


def test_breakdown_shows_kinds_not_a_single_total() -> None:
    """Spec §8.2: tek bir toplam sayı gösterilmez."""
    articles = [
        _article(1, "tcmb", 1),
        _article(2, "aa-ekonomi", 2),
        _article(3, "dunya", 3),
        _article(4, "bloomberght", 3),
    ]
    assert breakdown_by_kind(articles) == {"official": 1, "wire": 1, "media": 2, "social": 0}


def test_has_primary_source_requires_tier_one() -> None:
    assert has_primary_source([_article(1, "tcmb", 1)])
    assert not has_primary_source([_article(1, "aa-ekonomi", 2)])


# ==========================================================================
# F2-12 — kural motoru R0–R7
# ==========================================================================
def test_r0_prediction_is_always_unverified() -> None:
    result = compute_status(_claim(claim_type="prediction"), [])
    assert result.rule == "R0"
    assert result.status == "unverified"
    assert result.reason["label"] == "Tahmin"


def test_r0_short_circuits_r1_contradiction() -> None:
    """İtiraz-4'ün tam olarak yakaladığı durum.

    Bir tahmin hakkında hem destekleyen hem çelişen Tier 1–2 kanıt var.
    Eski sıralamada R1 kazanır ve tahmin 🔴 `contradicted` olurdu.
    """
    evidence = [
        Evidence(_article(1, "tcmb", 1), "supports"),
        Evidence(_article(2, "aa-ekonomi", 2), "contradicts"),
    ]
    result = compute_status(_claim(claim_type="prediction"), evidence)
    assert result.status == "unverified"
    assert result.rule == "R0"
    assert result.reason["evaluated_evidence_rules"] is False
    assert "independent_count" not in result.reason


def test_r1_contradiction_wins_over_corroboration() -> None:
    evidence = [
        *_supports(_article(1, "tcmb", 1), _article(2, "aa-ekonomi", 2), _article(3, "dunya", 3)),
        Evidence(_article(4, "bloomberght", 3), "contradicts"),
    ]
    result = compute_status(_claim(), evidence)
    assert result.rule == "R1"
    assert result.status == "contradicted"


def test_r1_needs_at_least_one_tier_one_or_two() -> None:
    """Sosyal medya gürültüsü çelişki üretmemeli."""
    evidence = [
        Evidence(_article(1, "dunya", 3), "supports"),
        Evidence(_article(2, "sosyal", 4), "contradicts"),
    ]
    assert compute_status(_claim(), evidence).rule != "R1"


def test_r2_needs_primary_source_and_three_independent() -> None:
    evidence = _supports(
        _article(1, "tcmb", 1), _article(2, "aa-ekonomi", 2), _article(3, "dunya", 3)
    )
    result = compute_status(_claim(), evidence)
    assert result.rule == "R2"
    assert result.status == "strongly_corroborated"
    assert result.reason["independent_count"] == 3
    assert result.reason["has_primary_source"] is True


def test_r2_blocked_by_any_contradiction() -> None:
    evidence = [
        *_supports(_article(1, "tcmb", 1), _article(2, "aa-ekonomi", 2), _article(3, "dunya", 3)),
        Evidence(_article(4, "sosyal", 4), "contradicts"),
    ]
    # Tier 4 çelişki R1'i tetiklemez ama R2'yi de engellemez (Tier <= 3 şartı)
    assert compute_status(_claim(), evidence).rule == "R2"


def test_r3_official_number_skips_the_three_source_requirement() -> None:
    """TÜİK enflasyon verisini TÜİK açıkladıysa 3 teyit beklemek anlamsız."""
    claim = _claim(
        claim_type="number",
        normalized_value={
            "metric": "tufe_monthly",
            "value": 1.78,
            "unit": "%",
            "period": "2026-07",
        },
        value_verified_against_source=True,
    )
    result = compute_status(claim, _supports(_article(1, "tuik", 1)))
    assert result.rule == "R3"
    assert result.status == "strongly_corroborated"
    assert result.reason["normalized_value"]["value"] == 1.78


def test_r3_requires_verification_against_the_source_format() -> None:
    claim = _claim(claim_type="number", value_verified_against_source=False)
    assert compute_status(claim, _supports(_article(1, "tuik", 1))).rule != "R3"


def test_r3_does_not_apply_to_non_statistical_official_sources() -> None:
    claim = _claim(claim_type="number", value_verified_against_source=True)
    result = compute_status(claim, _supports(_article(1, "bddk", 1)))
    assert result.rule != "R3"


def test_r4_two_independent_without_primary_source() -> None:
    evidence = _supports(_article(1, "aa-ekonomi", 2), _article(2, "dunya", 3))
    result = compute_status(_claim(), evidence)
    assert result.rule == "R4"
    assert result.status == "partially_corroborated"


def test_r4_when_primary_exists_but_elements_are_partial() -> None:
    evidence = _supports(_article(1, "tcmb", 1), _article(2, "dunya", 3))
    result = compute_status(_claim(), evidence, partial_elements=True)
    assert result.rule == "R4"
    assert result.reason["partial_elements"] is True


def test_r5_single_independent_source() -> None:
    result = compute_status(_claim(), _supports(_article(1, "tcmb", 1)))
    assert result.rule == "R5"
    assert result.status == "single_source"


def test_r6_no_evidence_is_unverified() -> None:
    result = compute_status(_claim(), [])
    assert result.rule == "R6"
    assert result.status == "unverified"


def test_r7_caps_social_only_evidence_at_single_source() -> None:
    """Sosyal medyada çok tekrar, doğrulama değildir."""
    evidence = _supports(
        _article(1, "sosyal-a", 4),
        _article(2, "sosyal-b", 4),
        _article(3, "sosyal-c", 4),
        _article(4, "sosyal-d", 4),
    )
    result = compute_status(_claim(), evidence)
    assert result.status == "single_source"
    assert result.rule == "R7"
    assert result.reason["capped_from"] == "partially_corroborated"
    assert result.reason["capped_by_rule"] == "R4"


def test_r7_does_not_cap_when_a_non_social_source_exists() -> None:
    evidence = _supports(_article(1, "dunya", 3), _article(2, "sosyal", 4))
    result = compute_status(_claim(), evidence)
    assert result.rule == "R4"


def test_r8_attribution_verified_for_official_record() -> None:
    """R8 (B-92 · Spec v3.4): Birincil tutanak/resmî kayda dayanan attribution iddiaları."""
    claim = _claim(claim_type="attribution")
    evidence = _supports(_article(1, "tbmm-tutanak", 1))
    result = compute_status(claim, evidence)
    assert result.status == "attribution_verified"
    assert result.rule == "R8"
    assert result.reason["label"] == "Beyan Sabit"


def test_all_nine_rules_are_reachable() -> None:
    """F2-12 / Spec v3.4 DoD: 9 kuralın (R0-R8) her biri için test var."""
    covered = {
        name.split("_")[1].upper() for name in globals() if re.fullmatch(r"test_r\d+_.*", name)
    }
    assert {"R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"} <= covered


# ==========================================================================
# F2-13 — status_reason
# ==========================================================================
def test_status_reason_is_machine_readable() -> None:
    """Serbest metin değil: hangi kural, hangi girdiyle tetiklendi."""
    evidence = _supports(
        _article(1, "tcmb", 1), _article(2, "aa-ekonomi", 2), _article(3, "dunya", 3)
    )
    reason = compute_status(_claim(), evidence).as_status_reason()
    for key in (
        "rule",
        "independent_count",
        "breakdown",
        "has_primary_source",
        "contradictions",
        "computed_at",
        "engine_version",
    ):
        assert key in reason, f"status_reason'da eksik alan: {key}"
    assert reason["engine_version"] == rules.ENGINE_VERSION
    assert reason["breakdown"] == {"official": 1, "wire": 1, "media": 1, "social": 0}


def test_status_reason_records_independence_keys() -> None:
    """Hangi grupların tek sayıldığı geri izlenebilmeli."""
    reason = compute_status(_claim(), _supports(_article(1, "tcmb", 1))).reason
    assert reason["independence_keys"] == ["src:tcmb"]


# ==========================================================================
# F2-15 — salience
# ==========================================================================
def _signals(**over: object) -> EventSignals:
    base = {
        "independent_count": 4,
        "has_primary_source": True,
        "articles_in_first_hour": 5,
        "best_tier": 1,
        "has_key_entity": True,
        "evidence_status": "strongly_corroborated",
        "first_reported_at": NOW - timedelta(hours=1),
        "now": NOW,
    }
    base.update(over)
    return EventSignals(**base)  # type: ignore[arg-type]


def test_global_salience_never_exceeds_ninety() -> None:
    """migrations/0003 üst sınırı 90; formül bunu aşamamalı."""
    maxed = _signals(independent_count=99, articles_in_first_hour=99)
    assert global_salience(maxed).score == salience.GLOBAL_MAX


def test_global_salience_is_never_negative() -> None:
    worst = _signals(
        independent_count=0,
        has_primary_source=False,
        articles_in_first_hour=0,
        best_tier=4,
        has_key_entity=False,
        evidence_status="unverified",
        first_reported_at=NOW - timedelta(days=2),
        duplicate_suspect=True,
    )
    assert global_salience(worst).score >= 0


def test_penalty_applies_only_to_weak_and_stale_events() -> None:
    fresh = _signals(evidence_status="unverified")
    stale = _signals(evidence_status="unverified", first_reported_at=NOW - timedelta(hours=7))
    assert "weak_evidence_and_stale" not in global_salience(fresh).penalties
    assert global_salience(stale).penalties["weak_evidence_and_stale"] == 15
    assert global_salience(stale).score < global_salience(fresh).score


def test_strong_evidence_is_not_penalised_even_when_old() -> None:
    old_but_strong = _signals(first_reported_at=NOW - timedelta(days=3))
    assert global_salience(old_but_strong).penalties == {}


def test_breakdown_is_transparent() -> None:
    """P4: kullanıcı 'neden 84?' sorusunun cevabını görmeli."""
    result = global_salience(_signals())
    assert set(result.components) == {
        "independent_sources",
        "primary_source",
        "velocity",
        "tier_weight",
        "key_entity",
    }
    assert result.as_dict()["range"] == [0, 90]


def test_personal_adjustment_is_not_stored_in_breakdown() -> None:
    """Saklanan alan kullanıcıdan bağımsız kalmalı (İtiraz-7)."""
    payload = global_salience(_signals()).as_dict()
    flat = str(payload)
    assert "personal" not in flat and "kisisel bilesen bu alanda saklanmaz" in flat


def test_personal_adjustment_scales_with_priority_overlap() -> None:
    assert personal_adjustment(["enflasyon"], ["enflasyon"]) == 10
    assert personal_adjustment(["enflasyon"], ["enflasyon", "buyume"]) == 5
    assert personal_adjustment(["buyume"], ["enflasyon"]) == 0
    assert personal_adjustment(["enflasyon"], []) == 0


def test_displayed_score_stays_within_zero_and_hundred() -> None:
    top = global_salience(_signals(independent_count=99, articles_in_first_hour=99))
    assert displayed_score(top.score, 10) == 100


def _identifiers(module) -> set[str]:  # noqa: ANN001
    """Modüldeki tüm tanımlayıcılar — docstring ve yorumlar HARİÇ.

    Düz metin taraması işe yaramaz: yasağı *anlatan* docstring'in kendisi
    yasaklı sözcükleri içerir. Ölçülmesi gereken şey kodun ne yaptığıdır,
    ne söylediği değil.
    """
    tree = ast.parse(inspect.getsource(module))

    # Docstring düğümlerini önce topla — `ast` üst düğüm bağı tutmaz, bu
    # yüzden onları sahiplerinden bulmak gerekir.
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.FunctionDef | ast.ClassDef):
            names.add(node.name)
        # Sözlük anahtarları ve etiketler koddur; docstring değildir.
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            names.add(node.value)
    return {n.lower() for n in names}


def test_salience_has_no_engagement_input() -> None:
    """Spec §13.3: etkileşimi yukarı çeken hiçbir özellik kabul edilmez.

    Beğeni/paylaşım/tıklanma salience'a girerse ürün, kaçındığı şeye —
    popülerlik sıralayıcısına — dönüşür.
    """
    identifiers = _identifiers(salience)
    banned = (
        "like",
        "retweet",
        "share",
        "click",
        "view_count",
        "engagement",
        "begeni",
        "paylasim",
        "tiklan",
        "popular",
    )
    hits = [b for b in banned if any(b in name for name in identifiers)]
    assert not hits, f"salience'ta yasak etkileşim girdisi: {hits}"


def test_event_signals_have_no_user_fields() -> None:
    """Global skorun girdisi yalnızca olayın kendi özellikleridir."""
    fields = set(EventSignals.__dataclass_fields__)
    assert not any("user" in f or "profile" in f or "topic_prior" in f for f in fields)


# ==========================================================================
# Mimari sözleşme
# ==========================================================================
@pytest.mark.parametrize("module", [independence, rules, salience])
def test_evidence_modules_do_not_import_llm(module) -> None:  # noqa: ANN001
    """Spec §11.2 / §8.1 — statik kural testinin yanında ikinci savunma.

    Import ifadeleri AST ile okunur. Düz metin taraması, yasağı açıklayan
    docstring'e takılırdı — kuralı ihlal etmeyen kodu ihlal sanardı.
    """
    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden = [
        name
        for name in imported
        if name.startswith("politikdesk.llm") or name.split(".")[0] == "anthropic"
    ]
    assert not forbidden, (
        f"{module.__name__} yasak modül import ediyor: {forbidden}. "
        "Kanıt motoru deterministiktir (Spec §8.1)."
    )


def test_wire_and_same_group_copy_count_once() -> None:
    """F2-16 eval kosucusunun yakaladigi hata (gc-024).

    Faz 1'de kopya simhash ile tespit ediliyordu ve ajansin anahtarini
    `wire:<slug>` olarak sabitlemek ise yariyordu. Kopya AYNI YAYIN
    GRUBUYLA eslestiginde ayni cozum hatayi geri getiriyordu: ajans
    `wire:aa-ekonomi`, kopyasi `grp:wire-aa` anahtarina dusuyor ve ikisi
    AYRI sayiliyordu.
    """
    wire = _article(1, "aa-ekonomi", 2, independence_group="wire-aa")
    copy = _article(2, "kopyaci", 3, independence_group="wire-aa")
    assert merge_key(wire, others=[wire, copy]) == merge_key(copy, others=[wire, copy])
    assert independent_count([wire, copy]) == 1


def test_wire_without_a_group_still_absorbs_its_simhash_copy() -> None:
    """Regresyon: Faz 1'de duzeltilen ilk bicim bozulmamali."""
    wire = _article(1, "aa-ekonomi", 2, simhash=0b1010)
    copy = _article(2, "kopyaci", 3, simhash=0b1011)
    assert independent_count([wire, copy]) == 1


def test_simhash_copy_inherits_the_wires_group_key() -> None:
    """Ajansin grubu varsa kopya da o gruba dusmeli, slug'a degil."""
    wire = _article(1, "aa-ekonomi", 2, independence_group="wire-aa", simhash=0b1010)
    copy = _article(2, "kopyaci", 3, simhash=0b1011)
    assert merge_key(copy, others=[wire, copy]) == "grp:wire-aa"
    assert independent_count([wire, copy]) == 1


# ==================================================================== L4 (B-92)
def test_explain_r8_attribution_verified() -> None:
    """L4: R8 kuralı ve attribution_verified durumu için explain() eksiksiz çıktı üretmeli."""
    from politikdesk.evidence.explain import RULE_TITLES, STATUS_TITLES, explain

    res = explain(
        "attribution_verified",
        {
            "rule": "R8",
            "has_primary_source": True,
            "independent_count": 1,
            "breakdown": {"official": 1},
        },
    )
    assert res["status"] == "attribution_verified"
    assert res["status_title"] == "Beyan sabit"
    assert res["rule"] == "R8"
    assert res["rule_title"] == "Birincil kayıt ve beyan doğrulaması"
    assert res["rule_title"] != "Bilinmeyen kural"
    assert "resmî kayda" in res["sentence"] or "Aktarım veya beyan" in res["sentence"]
    assert "R8" in RULE_TITLES
    assert "attribution_verified" in STATUS_TITLES


def test_status_badge_renders_attribution_verified() -> None:
    """L4: attribution_verified durumu UI rozetinde Türkçe ve accent stiliyle basılmalı."""
    from politikdesk.web.ui.components import status_badge
    from politikdesk.web.ui.tokens import STATUS_TOKEN

    badge_html = status_badge("attribution_verified")
    assert "beyan sabit" in badge_html
    assert "badge accent" in badge_html
    assert '<path d="M9 10h6"/>' in badge_html
    assert "attribution_verified" not in badge_html  # raw slug görünmemeli
    assert STATUS_TOKEN["attribution_verified"] == "accent"


def test_all_evidence_statuses_have_complete_ui_and_explain_contracts() -> None:
    """L4: Tüm kayıtlı EvidenceStatus değerleri UI ve açıklama sözleşmelerini karşılamalı."""
    from typing import get_args

    from politikdesk.evidence.explain import STATUS_TITLES
    from politikdesk.evidence.rules import EvidenceStatus
    from politikdesk.web.ui import icons
    from politikdesk.web.ui.components import STATUS_LABELS
    from politikdesk.web.ui.tokens import STATUS_TOKEN

    all_statuses = get_args(EvidenceStatus)
    for st in all_statuses:
        assert st in STATUS_TOKEN, f"{st} STATUS_TOKEN içinde eksik"
        assert st in STATUS_LABELS, f"{st} STATUS_LABELS içinde eksik"
        assert st in STATUS_TITLES, f"{st} STATUS_TITLES içinde eksik"
        token = STATUS_TOKEN[st]
        assert f"status-{token}" in icons.names(), f"status-{token} ikonu eksik"
