"""X (Twitter) Yayınlama ve Güvenlik Kapısı (TCK 217/A & Hakaret Guard) Testleri."""

from __future__ import annotations

import pytest

from politikdesk.editorial.social_publisher import (
    UnsafeSocialPublicationError,
    XPublisherClient,
    evaluate_social_safety_gate,
    format_x_thread,
)


def test_clean_draft_passes_social_safety_gate() -> None:
    """Temiz ve doğrulanmış editoryal taslak güvenlik kapısını başarıyla geçer."""
    text = "TBMM Genel Kurulu 9. Yargı Paketi kanun teklifini kabul etti."
    result = evaluate_social_safety_gate(text, evidence_status="strongly_corroborated")

    assert result.passed is True
    assert len(result.reasons) == 0
    assert result.has_tck217a_risk is False
    assert result.has_defamation_risk is False


def test_defamatory_draft_fails_social_safety_gate() -> None:
    """Hakaret ve hukuka aykırı isnat içeren taslak güvenlik kapısından geçemez."""
    text = "Bakanlık yetkilisi vatan haini ve hırsız olarak nitelendirildi."
    result = evaluate_social_safety_gate(text, evidence_status="strongly_corroborated")

    assert result.passed is False
    assert result.has_defamation_risk is True
    assert any("Hakaret" in r for r in result.reasons)


def test_tck217a_panic_disinformation_fails_gate() -> None:
    """TCK 217/A dezenformasyon ve panik ifadeleri güvenlik kapısından geçemez."""
    text = "Kulis iddiası: Tüm bankalar battı ve olağanüstü hal ilan edildi."
    result = evaluate_social_safety_gate(text, evidence_status="single_source")

    assert result.passed is False
    assert result.has_tck217a_risk is True


def test_unverified_claim_fails_without_attribution() -> None:
    """Doğrulanmamış iddia attribution şerhi olmadan paylaşılamaz."""
    text = "Ekonomi yönetiminde sürpriz istifa gerçekleşti."
    result = evaluate_social_safety_gate(text, evidence_status="unverified", is_attribution=False)

    assert result.passed is False
    assert result.epistemic_verified is False


def test_publisher_client_blocked_by_default_feature_flag() -> None:
    """Varsayılan ortamda (PD_SOCIAL_PUBLISH_ENABLED tanımlı değilken) publish_thread devre dışıdır."""
    client = XPublisherClient()
    with pytest.raises(UnsafeSocialPublicationError, match="devre dışı bırakıldı"):
        client.publish_thread(["Temiz tweet"])


def test_publisher_client_strictly_blocks_unsafe_drafts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Güvenlik kapısını geçemeyen içerik yayınlanmaya çalışıldığında UnsafeSocialPublicationError fırlatır."""
    monkeypatch.setenv("PD_SOCIAL_PUBLISH_ENABLED", "1")
    unsafe_gate = evaluate_social_safety_gate(
        "Yolsuzluk yapan alçak yetkili", evidence_status="unverified"
    )
    client = XPublisherClient()

    with pytest.raises(UnsafeSocialPublicationError, match="Güvenlik kapısı ihlali"):
        client.publish_thread(["Tweet 1"], gate_result=unsafe_gate)


def test_thread_formatter_output() -> None:
    """Thread formatlayıcı bağlantı provenance ve atomik iddiaları doğru düzenlemeli."""
    thread = format_x_thread(
        title="Merkez Bankası Faiz Kararı",
        lead="TCMB Para Politikası Kurulu politika faizini yüzde 37'de sabit tuttu.",
        claims=[
            {
                "claim_text": "Politika faizi yüzde 37'de sabit tutuldu",
                "evidence_status": "strongly_corroborated",
                "source": "TCMB",
            },
            {
                "claim_text": "Enflasyonun düşüş eğilimi sürecek",
                "evidence_status": "partially_corroborated",
                "speaker": "Başkan Karahan",
                "source": "PPK Metni",
            },
        ],
        event_id=105,
    )

    assert len(thread) == 3
    assert "https://politikdesk.com/event/105" in thread[0]
    assert "[1/2]" in thread[1]
    assert "[Dogrulandi]" in thread[1]
    assert "[2/2]" in thread[2]
    assert "[Kismen Dogrulandi]" in thread[2]


def test_adversarial_forged_gate_result_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sahte SafetyGateResult(passed=True) geçilse dahi birleşik metin kontrolü yayını engeller."""
    monkeypatch.setenv("PD_SOCIAL_PUBLISH_ENABLED", "1")
    from politikdesk.editorial.social_publisher import SafetyGateResult

    forged_gate = SafetyGateResult(passed=True)  # Sahte başarılı kapı sonucu
    malicious_thread = [
        "[Haber] İddia Özeti",
        "İlgili bakan açıkça vatan haini olarak nitelendirildi",
    ]

    client = XPublisherClient()
    with pytest.raises(UnsafeSocialPublicationError, match="Güvenlik kapısı ihlali"):
        client.publish_thread(malicious_thread, gate_result=forged_gate)

    assert len(client.published_threads) == 0
    assert len(client.blocked_attempts) == 1


def test_adversarial_split_payload_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tekil olarak zararsız görünen ancak birleştiğinde TCK 217/A riski oluşturan parçalı tweet'ler engellenir."""
    monkeypatch.setenv("PD_SOCIAL_PUBLISH_ENABLED", "1")
    split_thread = [
        "[1/3] Kulis bilgisi:",
        "[2/3] tüm bankalar battı ve finans sistemi çöktü",
        "[3/3] olağanüstü hal ilan edildi",
    ]

    client = XPublisherClient()
    with pytest.raises(UnsafeSocialPublicationError, match="Güvenlik kapısı ihlali"):
        client.publish_thread(split_thread)

    assert len(client.published_threads) == 0
    assert len(client.blocked_attempts) == 1
    assert any("TCK 217/A" in r for r in client.blocked_attempts[0]["reasons"])


def test_adversarial_quoted_defamation_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Alıntı içinde hakaret / dezenformasyon taşınması güvenlik kapısını atlatamaz."""
    monkeypatch.setenv("PD_SOCIAL_PUBLISH_ENABLED", "1")
    quoted_thread = [
        "Açıklama yapıldı:",
        "Muhalefet vekili 'bu kurumdakilerin tamamı hırsız ve alçaktır' dedi.",
    ]

    client = XPublisherClient()
    with pytest.raises(UnsafeSocialPublicationError, match="Güvenlik kapısı ihlali"):
        client.publish_thread(quoted_thread)

    assert len(client.published_threads) == 0


def test_intent_only_publish_workflow_preserved() -> None:
    """Web intent yayın köprüsü insan müdahalesi gerektirir (requires_human_send=True)."""
    from urllib.parse import unquote

    import politikdesk.editorial.repository as repo
    from politikdesk.editorial.service import publish_payload

    original_get_draft = repo.get_draft
    try:
        repo.get_draft = lambda draft_id: {  # type: ignore[assignment]
            "id": 42,
            "body": "Politika faizi sabit tutuldu.",
            "final_body": None,
            "is_grounded": True,
        }
        payload = publish_payload(42)
        assert payload["requires_human_send"] is True
        assert "https://x.com/intent/tweet?text=" in payload["web_intent_url"]
        assert "Politika faizi sabit tutuldu." in unquote(payload["web_intent_url"])
    finally:
        repo.get_draft = original_get_draft  # type: ignore[assignment]
