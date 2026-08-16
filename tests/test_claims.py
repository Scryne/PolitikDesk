"""Faz 2 İş Kolu B — iddia çıkarımı (F2-06…F2-10).

ANTHROPIC_API_KEY olmadığı için canlı model koşumu yapılmaz; çıkarımın
**doğrulama katmanları** sahte istemciyle test edilir. F2-07'nin sayısal
DoD'u (100 iddialık örnekte ≥%90 doğru tip) canlı koşum gerektirir ve
açıktır.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from politikdesk.nlp.claims import (
    CLAIMS_SCHEMA,
    FORBIDDEN_FIELDS,
    MAX_QUOTE_LEN,
    PROMPT_VERSION,
    dedupe_claims,
    extract_claims,
    validate_claim,
    verify_quote,
)

TITLE = "Faiz Oranlarına İlişkin Basın Duyurusu (2026-28)"
EXCERPT = (
    "Para Politikası Kurulu (Kurul), politika faizi olan bir hafta vadeli repo "
    "ihale faiz oranının yüzde 37’de sabit tutulmasına karar vermiştir. Enflasyonun "
    "ana eğilimi, haziran ayında sınırlı bir miktar gerilemiştir."
)
SOURCE_TEXT = f"{TITLE} {EXCERPT}"


@dataclass
class _FakeResult:
    data: dict[str, Any]
    model: str = "claude-sonnet-5"
    raw_text: str = ""
    prompt_version: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


class FakeClient:
    """Sahte LLM istemcisi — çağrı argümanlarını kaydeder."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def complete_json(self, **kwargs: Any) -> _FakeResult:
        self.calls.append(kwargs)
        return _FakeResult(data=self.payload)


def _claim(**over: Any) -> dict[str, Any]:
    base = {
        "claim_text": "TCMB politika faizini yüzde 37'de sabit tuttu.",
        "claim_type": "fact",
        "quote_span": "politika faizi olan bir hafta vadeli repo ihale faiz oranının "
        "yüzde 37’de sabit tutulmasına karar vermiştir",
    }
    base.update(over)
    return base


# ==========================================================================
# F2-06 — şema ve grounding
# ==========================================================================
def test_schema_rejects_verdict_fields() -> None:
    """Spec §8.1: kanıt durumu LLM çıktısı olamaz — şema kabul etmez."""
    properties = CLAIMS_SCHEMA["properties"]["claims"]["items"]["properties"]
    assert CLAIMS_SCHEMA["properties"]["claims"]["items"]["additionalProperties"] is False
    for banned in FORBIDDEN_FIELDS:
        assert banned not in properties


def test_forbidden_field_in_output_is_rejected() -> None:
    """Şema kaçarsa ikinci savunma hattı devreye girer."""
    result = validate_claim(_claim(evidence_status="strongly_corroborated"), SOURCE_TEXT)
    assert not result.is_valid
    assert any("yasak alan" in p for p in result.problems)


def test_prompt_version_is_sent_to_the_model() -> None:
    """Prompt sürümlenir ve çıktıya işlenir (Spec §11.5)."""
    client = FakeClient({"claims": [_claim()]})
    result = extract_claims(
        title=TITLE,
        excerpt=EXCERPT,
        source_name="TCMB",
        tier=1,
        published_at="2026-07-23",
        client=client,
    )
    # Sürüm sabite bağlanır: elle yazılan dize, sürüm artışında testi
    # kırar ama denetlenen davranış hakkında hiçbir şey söylemez.
    assert client.calls[0]["prompt_version"] == PROMPT_VERSION
    assert client.calls[0]["schema"] is CLAIMS_SCHEMA
    assert result.extracted_by == f"claude-sonnet-5+{PROMPT_VERSION}"


def test_extraction_uses_the_cheap_model_task() -> None:
    """Risk R6 azaltımı: çıkarım ucuz modelde koşar."""
    client = FakeClient({"claims": []})
    extract_claims(
        title=TITLE,
        excerpt=EXCERPT,
        source_name="TCMB",
        tier=1,
        published_at="2026-07-23",
        client=client,
    )
    assert client.calls[0]["task"] == "extraction"


# ==========================================================================
# F2-10 — alıntı doğrulama (halüsinasyon savunması)
# ==========================================================================
def test_quote_must_appear_in_the_source_text() -> None:
    assert verify_quote("politika faizi olan bir hafta vadeli repo", SOURCE_TEXT)
    assert not verify_quote("Kurul faizi yüzde 40'a yükseltti", SOURCE_TEXT)


def test_typographic_differences_do_not_count_as_hallucination() -> None:
    """Yayınlar tipografik tırnakta tutarsızdır; bu uydurma değildir."""
    assert verify_quote("yüzde 37'de sabit tutulmasına", SOURCE_TEXT)
    assert verify_quote("yüzde  37’de   sabit  tutulmasına", SOURCE_TEXT)


def test_fabricated_quote_rejects_the_claim() -> None:
    bad = validate_claim(
        _claim(quote_span="Kurul faizi yüzde 40'a yükseltme kararı almıştır"),
        SOURCE_TEXT,
    )
    assert not bad.is_valid
    assert any("uydurulmus alinti" in p for p in bad.problems)


def test_quote_longer_than_two_hundred_chars_is_rejected() -> None:
    """DB CHECK `quote_span_len` ile aynı sınır."""
    result = validate_claim(_claim(quote_span="x" * (MAX_QUOTE_LEN + 1)), SOURCE_TEXT)
    assert not result.is_valid
    assert any("azami 200" in p for p in result.problems)


def test_empty_quote_is_rejected() -> None:
    assert not validate_claim(_claim(quote_span=""), SOURCE_TEXT).is_valid


# ==========================================================================
# F2-07 / F2-08 — tip ve sayısal normalizasyon
# ==========================================================================
def test_number_claim_requires_normalized_value() -> None:
    result = validate_claim(_claim(claim_type="number"), SOURCE_TEXT)
    assert not result.is_valid
    assert any("normalized_value zorunlu" in p for p in result.problems)


def test_valid_number_claim_passes() -> None:
    result = validate_claim(
        _claim(
            claim_type="number",
            normalized_value={
                "metric": "policy_rate",
                "value": 37.0,
                "unit": "%",
                "period": "2026-07",
            },
        ),
        SOURCE_TEXT,
    )
    assert result.is_valid


@pytest.mark.parametrize(
    "value,expected_problem",
    [
        ({"metric": "faiz", "value": 37, "unit": "%", "period": "2026-07"}, "gecersiz metric"),
        ({"metric": "policy_rate", "value": "37", "unit": "%", "period": "2026-07"}, "sayi olmali"),
        ({"metric": "policy_rate", "value": 37, "unit": "", "period": "2026-07"}, "unit bos"),
        (
            {"metric": "policy_rate", "value": 37, "unit": "%", "period": "Temmuz"},
            "gecersiz period",
        ),
        (
            {"metric": "policy_rate", "value": 37, "unit": "%", "period": "2026-13"},
            "gecersiz period",
        ),
    ],
)
def test_normalized_value_is_validated(value: dict, expected_problem: str) -> None:
    result = validate_claim(_claim(claim_type="number", normalized_value=value), SOURCE_TEXT)
    assert not result.is_valid
    assert any(expected_problem in p for p in result.problems)


@pytest.mark.parametrize("period", ["2026", "2026-07", "2026-Q1"])
def test_accepted_period_formats(period: str) -> None:
    result = validate_claim(
        _claim(
            claim_type="number",
            normalized_value={
                "metric": "tufe_monthly",
                "value": 1.78,
                "unit": "%",
                "period": period,
            },
        ),
        SOURCE_TEXT,
    )
    assert result.is_valid


def test_non_number_claim_must_not_carry_a_value() -> None:
    result = validate_claim(
        _claim(
            claim_type="fact",
            normalized_value={
                "metric": "policy_rate",
                "value": 37,
                "unit": "%",
                "period": "2026-07",
            },
        ),
        SOURCE_TEXT,
    )
    assert not result.is_valid


def test_invalid_claim_type_is_rejected() -> None:
    assert not validate_claim(_claim(claim_type="opinion"), SOURCE_TEXT).is_valid


# ==========================================================================
# F2-09 — tekilleştirme
# ==========================================================================
def test_same_number_claim_in_different_words_is_deduped() -> None:
    """Sözcük tabanlı imza bunları ayrı sayardı."""
    a = validate_claim(
        _claim(
            claim_text="TÜFE aylık yüzde 1,78 arttı.",
            claim_type="number",
            normalized_value={
                "metric": "tufe_monthly",
                "value": 1.78,
                "unit": "%",
                "period": "2026-07",
            },
        ),
        SOURCE_TEXT,
    )
    b = validate_claim(
        _claim(
            claim_text="Aylık enflasyon yüzde 1,78 olarak gerçekleşti.",
            claim_type="number",
            normalized_value={
                "metric": "tufe_monthly",
                "value": 1.78,
                "unit": "%",
                "period": "2026-07",
            },
        ),
        SOURCE_TEXT,
    )
    assert len(dedupe_claims([a, b])) == 1


def test_different_periods_are_not_deduped() -> None:
    def make(period: str):  # noqa: ANN202
        return validate_claim(
            _claim(
                claim_type="number",
                normalized_value={
                    "metric": "tufe_monthly",
                    "value": 1.78,
                    "unit": "%",
                    "period": period,
                },
            ),
            SOURCE_TEXT,
        )

    assert len(dedupe_claims([make("2026-07"), make("2026-06")])) == 2


def test_word_order_does_not_create_a_duplicate() -> None:
    a = validate_claim(_claim(claim_text="Kurul faizi sabit tuttu."), SOURCE_TEXT)
    b = validate_claim(_claim(claim_text="Faizi sabit tuttu Kurul."), SOURCE_TEXT)
    assert len(dedupe_claims([a, b])) == 1


def test_different_types_are_not_deduped() -> None:
    a = validate_claim(_claim(claim_text="Enflasyon düşecek.", claim_type="fact"), SOURCE_TEXT)
    b = validate_claim(
        _claim(claim_text="Enflasyon düşecek.", claim_type="prediction"), SOURCE_TEXT
    )
    assert len(dedupe_claims([a, b])) == 2


# ==========================================================================
# Uçtan uca (sahte istemci)
# ==========================================================================
def test_extraction_separates_accepted_and_rejected() -> None:
    client = FakeClient(
        {
            "claims": [
                _claim(),
                _claim(quote_span="bu cumle metinde yok"),  # uydurma alıntı
                _claim(claim_type="number"),  # değer eksik
            ]
        }
    )
    result = extract_claims(
        title=TITLE,
        excerpt=EXCERPT,
        source_name="TCMB",
        tier=1,
        published_at="2026-07-23",
        client=client,
    )
    assert len(result.claims) == 1
    assert len(result.rejected) == 2


def test_extraction_dedupes_within_one_article() -> None:
    client = FakeClient({"claims": [_claim(), _claim()]})
    result = extract_claims(
        title=TITLE,
        excerpt=EXCERPT,
        source_name="TCMB",
        tier=1,
        published_at="2026-07-23",
        client=client,
    )
    assert len(result.claims) == 1


def test_empty_model_output_is_not_an_error() -> None:
    client = FakeClient({"claims": []})
    result = extract_claims(
        title=TITLE,
        excerpt=EXCERPT,
        source_name="TCMB",
        tier=1,
        published_at="2026-07-23",
        client=client,
    )
    assert result.claims == [] and result.rejected == []


# ------------------------------------------------- prompt sürüm bütünlüğü
def test_prompt_file_matches_code() -> None:
    """Sürümlü prompt belgesi ile kodun GÖNDERDİĞİ prompt aynı olmalı.

    v1'de aynı değillerdi: `prompts/claims.v1.md` izinli `metric` listesini
    ve tip ayrım örneklerini içeriyordu, `claims.py::SYSTEM_PROMPT`
    içermiyordu — yani model o rehberliği hiç görmedi. Sapma sessizdi ve
    ancak canlı koşumda (B-58) yanlış metrik seçimi olarak ortaya çıktı.

    `extracted_by` alanına yazılan sürüm, gerçekte gönderilen promptu
    temsil etmiyorsa denetlenebilirlik iddiası da çöker (Spec §11.5).
    """
    from pathlib import Path

    from politikdesk.nlp.claims import PROMPT_VERSION, SYSTEM_PROMPT

    repo_root = Path(__file__).resolve().parent.parent
    doc = repo_root / "prompts" / f"{PROMPT_VERSION}.md"
    assert doc.is_file(), f"{doc.name} yok — prompt sürümü belgesiz olamaz"

    blocks = doc.read_text(encoding="utf-8").split("## SYSTEM", 1)
    assert len(blocks) == 2, f"{doc.name} içinde '## SYSTEM' bölümü yok"
    documented = blocks[1].split("```")[1].strip()

    assert documented == SYSTEM_PROMPT.strip(), (
        f"{doc.name} ile claims.py::SYSTEM_PROMPT ayrışmış. "
        "Prompt değiştiyse HEM kodu HEM belgeyi güncelleyin ve "
        "PROMPT_VERSION'ı artırın."
    )


def test_half_year_period_is_accepted() -> None:
    """`2026-H1` canlı koşumda reddediliyordu — sözlük boşluğuydu.

    Türkçe ekonomi haberciliğinde "yılın ilk yarısı" yaygın bir dönemdir;
    model doğru üretmişken doğrulama düşürüyordu.
    """
    from politikdesk.nlp.claims import _validate_value

    ok = _validate_value(
        {"metric": "budget_balance", "value": 1.5, "unit": "TL", "period": "2026-H1"}
    )
    assert ok == []

    bad = _validate_value(
        {"metric": "budget_balance", "value": 1.5, "unit": "TL", "period": "2026-H3"}
    )
    assert any("period" in p for p in bad)
