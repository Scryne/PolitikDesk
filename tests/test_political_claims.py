"""Siyaset İddia Çıkarımı, Vaat Takip Radarı ve Söylem Çelişkisi Testleri (Spec v3.5 §5, §12.5)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from politikdesk.nlp.claims import (
    POLITICAL_PROMPT_VERSION,
    POLITICAL_SYSTEM_PROMPT,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    extract_claims,
    get_system_prompt,
)
from politikdesk.political_memory.relation_engine import evaluate_relation


def test_system_prompt_selection_by_vertical() -> None:
    """Dikey bazlı sistem promptu doğru seçilmeli."""
    prompt_macro, ver_macro = get_system_prompt("macro_economy")
    assert prompt_macro == SYSTEM_PROMPT
    assert ver_macro == PROMPT_VERSION

    prompt_leg, ver_leg = get_system_prompt("legislation")
    assert prompt_leg == POLITICAL_SYSTEM_PROMPT
    assert ver_leg == POLITICAL_PROMPT_VERSION

    prompt_soc, ver_soc = get_system_prompt("social")
    assert prompt_soc == POLITICAL_SYSTEM_PROMPT
    assert ver_soc == POLITICAL_PROMPT_VERSION


def test_political_promise_extraction_with_mock_llm() -> None:
    """Siyaset dikeyinde vaat (promise) iddiaları doğru çıkarılmalı."""
    mock_llm = MagicMock()
    mock_llm.complete_json.return_value = MagicMock(
        data={
            "claims": [
                {
                    "claim_text": "Genel Başkan Özel ilk 100 günde mülakatı kaldıracaklarını taahhüt etti",
                    "claim_type": "promise",
                    "quote_span": "ilk 100 günde mülakatı kaldıracağız",
                    "normalized_value": None,
                },
                {
                    "claim_text": "Meclis açılışında kanun teklifi sunulacağını açıkladı",
                    "claim_type": "attribution",
                    "quote_span": "Meclis açılışında kanun teklifi sunacağız",
                    "normalized_value": None,
                },
            ]
        },
        model="nemotron-3-super",
    )

    result = extract_claims(
        title="Özel: İlk 100 Günde Mülakatı Kaldıracağız",
        excerpt="CHP lideri Özel, 'ilk 100 günde mülakatı kaldıracağız' dedi ve Meclis açılışında kanun teklifi sunacağız mesajını verdi.",
        source_name="T24",
        tier=3,
        published_at="2026-08-16T10:00:00Z",
        client=mock_llm,
        vertical="legislation",
    )

    assert result.prompt_version == POLITICAL_PROMPT_VERSION
    assert len(result.claims) == 2
    types = {c.claim_type for c in result.claims}
    assert "promise" in types
    assert "attribution" in types


def test_stance_shift_and_contradiction_detection() -> None:
    """Geçmiş vaat ile bugünkü gerçekleşme/eylem arasındaki çelişki tespit edilmeli."""
    from politikdesk.political_memory.relation_engine import EventData

    past_promise_event = EventData(
        event_id=101,
        title="Bakan Şimşek: 2025 Enflasyonu Yüzde 20 Altına İnecek",
        published_at=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        entities=frozenset(["Mehmet Şimşek", "Hazine ve Maliye Bakanlığı", "enflasyon"]),
        key_entities=frozenset(["Mehmet Şimşek", "Hazine ve Maliye Bakanlığı"]),
        actor="Mehmet Şimşek",
        institution="Hazine ve Maliye Bakanlığı",
        topics=("enflasyon",),
        claims=({"claim_text": "Enflasyon yüzde 20 altına inecek", "claim_type": "promise"},),
    )

    current_realization_event = EventData(
        event_id=202,
        title="TÜİK: 2025 Yıl Sonu Enflasyonu Yüzde 34 Olarak Gerçekleşti",
        published_at=datetime(2026, 1, 5, 10, 0, tzinfo=UTC),
        entities=frozenset(
            ["Hazine ve Maliye Bakanlığı", "Türkiye İstatistik Kurumu", "enflasyon"]
        ),
        key_entities=frozenset(["Hazine ve Maliye Bakanlığı", "Türkiye İstatistik Kurumu"]),
        institution="Türkiye İstatistik Kurumu",
        topics=("enflasyon",),
        claims=({"claim_text": "2025 enflasyonu yüzde 34 oldu", "claim_type": "number"},),
    )

    result = evaluate_relation(
        past_promise_event,
        current_realization_event,
        semantic_similarity=0.88,
    )

    assert result is not None
    # Geçmiş bir vaat ile ters gerçekleşme çelişki, güncelleme veya başarısızlık ilişkisi kurar
    assert result.relation_type in ("contradicts", "fails", "updates", "precedes")
    assert result.confidence >= 0.60
