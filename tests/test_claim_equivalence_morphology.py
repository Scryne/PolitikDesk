"""Test Claim Equivalence and Turkish Morphology Normalization (Gate 3)."""

from politikdesk.nlp.claims import ExtractedClaim, claim_signature


def test_turkish_verb_morphology_equivalence() -> None:
    """Türkçe morfoloji varyasyonları iddiayı parçalamamalıdır."""
    c1 = ExtractedClaim("Kanun teklifi Meclis'te kabul edildi", "fact", "", None)
    c2 = ExtractedClaim("Kanun teklifi Meclis'te kabul edilmiştir", "fact", "", None)
    c3 = ExtractedClaim("Kanun teklifi Meclis'te kabul edildiğini", "fact", "", None)

    sig1 = claim_signature(c1)
    sig2 = claim_signature(c2)
    sig3 = claim_signature(c3)

    assert sig1 == sig2 == sig3, f"Morfoloji varyasyonları farklı imza üretti: {sig1} vs {sig2} vs {sig3}"


def test_turkish_approval_verbs_equivalence() -> None:
    """Onaylama fiil varyasyonları aynı imzaya indirgenmelidir."""
    c1 = ExtractedClaim("Yeni bütçe Meclis komisyonunda onaylandı", "fact", "", None)
    c2 = ExtractedClaim("Yeni bütçe Meclis komisyonunda onaylanmıştır", "fact", "", None)

    assert claim_signature(c1) == claim_signature(c2)


def test_hard_negative_same_actor_different_date() -> None:
    """Aynı aktörün farklı tarihlerdeki beyanları ayrık kalmalıdır."""
    c1 = ExtractedClaim("Bakan Şimşek Temmuz ayı verilerini değerlendirdi", "fact", "", None)
    c2 = ExtractedClaim("Bakan Şimşek Ağustos ayı verilerini değerlendirdi", "fact", "", None)

    assert claim_signature(c1) != claim_signature(c2)


def test_hard_negative_same_number_different_context() -> None:
    """Aynı sayısal değer farklı metriklerde ayrık kalmalıdır."""
    c1 = ExtractedClaim(
        "Politika faizi yüzde 50 olarak belirlendi",
        "number",
        "",
        {"metric": "policy_rate", "value": 50.0, "unit": "%", "period": "2026-08"},
    )
    c2 = ExtractedClaim(
        "Kredi kartı faiz tavanı yüzde 50 oldu",
        "number",
        "",
        {"metric": "credit_card_cap", "value": 50.0, "unit": "%", "period": "2026-08"},
    )

    assert claim_signature(c1) != claim_signature(c2)


def test_hard_negative_same_decision_number_different_institution() -> None:
    """Aynı karar numarası farklı kurumlarda ayrık kalmalıdır."""
    c1 = ExtractedClaim("TCMB 2026/10 sayılı kararı yayımladı", "fact", "", None)
    c2 = ExtractedClaim("BDDK 2026/10 sayılı kararı yayımladı", "fact", "", None)

    assert claim_signature(c1) != claim_signature(c2)


def test_hard_negative_same_institution_different_action() -> None:
    """Aynı kurumun farklı işlemleri ayrık kalmalıdır."""
    c1 = ExtractedClaim("TÜİK enflasyon verilerini duyurdu", "fact", "", None)
    c2 = ExtractedClaim("TÜİK işsizlik verilerini duyurdu", "fact", "", None)

    assert claim_signature(c1) != claim_signature(c2)
