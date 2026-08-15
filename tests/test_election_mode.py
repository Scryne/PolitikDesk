"""Election Mode testleri (F4-15, Spec §12.6).

DoD: "Flag açıldığında eşikler sıkılaşıyor (birim testi); UI göstergesi
hazır; **varsayılan kapalı**."

Bu dosyanın en önemli testi son cümledir. Bir seçim modu, yanlışlıkla
açık kaldığında ürünü sessizce kısıtlar: taslaklar üretilmez, kullanıcı
sebebini anlamaz. Varsayılanın kapalı olduğu her koşumda denetlenir.
"""

from __future__ import annotations

import pytest

from config import election_mode
from politikdesk.evidence.independence import EvidenceArticle
from politikdesk.evidence.rules import Claim, Evidence, compute_status


@pytest.fixture
def election_on(monkeypatch):
    monkeypatch.setenv(election_mode.ENV_VAR, "true")
    return election_mode.current()


@pytest.fixture
def election_off(monkeypatch):
    monkeypatch.delenv(election_mode.ENV_VAR, raising=False)
    return election_mode.current()


# ===================================================== varsayılan kapalı
def test_default_is_off(election_off) -> None:  # noqa: ANN001
    """Pazarlıksız: mod açıkça açılmadıkça kapalıdır."""
    assert election_mode.is_enabled() is False
    assert election_mode.current() is election_mode.NORMAL
    assert election_mode.NORMAL.enabled is False


def test_module_default_config_is_the_loose_one() -> None:
    """Sınıf varsayılanı da gevşek olmalı — `ElectionModeConfig()` kurmak
    kazara sıkı mod açmamalı."""
    assert election_mode.ElectionModeConfig().enabled is False
    assert (
        election_mode.ElectionModeConfig().strongly_corroborated_min_sources
        == election_mode.NORMAL_STRONG_MIN_SOURCES
    )


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_flag_accepts_common_truthy_spellings(monkeypatch, value) -> None:  # noqa: ANN001
    monkeypatch.setenv(election_mode.ENV_VAR, value)
    assert election_mode.is_enabled() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "hayir"])
def test_flag_rejects_everything_else(monkeypatch, value) -> None:  # noqa: ANN001
    """Belirsiz değer kapalı sayılır: sıkı moda yanlışlıkla girilmemeli
    ama yanlışlıkla ÇIKILMASI da kabul edilebilir — çıkış görünürdür
    (banner kaybolur), giriş görünmez olurdu."""
    monkeypatch.setenv(election_mode.ENV_VAR, value)
    assert election_mode.is_enabled() is False


# ===================================================== eşikler sıkılaşıyor
def _article(article_id: int, tier: int, slug: str) -> EvidenceArticle:
    return EvidenceArticle(
        article_id=article_id, source_slug=slug, tier=tier, kind="media",
        independence_group=f"grp{article_id}", simhash=article_id,
        embedding=[], text=f"metin {article_id}",
    )


def _supporting(count: int, *, first_tier1: bool = True) -> list[Evidence]:
    return [
        Evidence(
            article=_article(i, 1 if (i == 0 and first_tier1) else 2, f"kaynak{i}"),
            stance="supports",
            quote_span=f"alinti {i}",
        )
        for i in range(count)
    ]


def _claim() -> Claim:
    return Claim(claim_id=1, claim_text="Enflasyon %30 oldu", claim_type="fact")


def test_three_sources_are_strong_in_normal_mode(election_off) -> None:  # noqa: ANN001
    result = compute_status(_claim(), _supporting(3))
    assert result.status == "strongly_corroborated"
    assert result.rule == "R2"


def test_three_sources_are_not_strong_in_election_mode(election_on) -> None:  # noqa: ANN001
    """Eşiğin sıkılaştığının kanıtı: AYNI kanıt seti, farklı sonuç."""
    result = compute_status(_claim(), _supporting(3))
    assert result.status != "strongly_corroborated"


def test_four_sources_are_strong_in_election_mode(election_on) -> None:  # noqa: ANN001
    result = compute_status(_claim(), _supporting(4))
    assert result.status == "strongly_corroborated"


def test_election_threshold_is_higher_than_normal() -> None:
    assert (
        election_mode.ELECTION.strongly_corroborated_min_sources
        > election_mode.NORMAL.strongly_corroborated_min_sources
    )


def test_official_number_exception_is_closed_in_election_mode(election_on) -> None:  # noqa: ANN001
    """R3 tek Tier 1 resmî kaynağa 🟢 verir. Spec §12.6 "🟢 için ≥4"
    diyorsa bu istisna açık kalamaz."""
    claim = Claim(
        claim_id=2, claim_text="TÜİK enflasyonu %30 açıkladı", claim_type="number",
        normalized_value={"value": 30}, value_verified_against_source=True,
    )
    evidence = [
        Evidence(article=_article(0, 1, "tuik"), stance="supports", quote_span="%30")
    ]
    assert compute_status(claim, evidence).status != "strongly_corroborated"


def test_official_number_exception_works_in_normal_mode(election_off) -> None:  # noqa: ANN001
    """Ters yön: istisna normal modda çalışmaya devam etmeli."""
    claim = Claim(
        claim_id=2, claim_text="TÜİK enflasyonu %30 açıkladı", claim_type="number",
        normalized_value={"value": 30}, value_verified_against_source=True,
    )
    evidence = [
        Evidence(article=_article(0, 1, "tuik"), stance="supports", quote_span="%30")
    ]
    result = compute_status(claim, evidence)
    assert result.status == "strongly_corroborated"
    assert result.rule == "R3"


# ===================================================== üretim kapısı genişler
def test_generation_gate_blocks_only_unverified_normally(election_off) -> None:  # noqa: ANN001
    from politikdesk.editorial.guards import blocked_statuses

    assert blocked_statuses() == frozenset({"unverified"})


def test_generation_gate_also_blocks_single_source_in_election(election_on) -> None:  # noqa: ANN001
    """Spec §12.6 madde 1."""
    from politikdesk.editorial.guards import blocked_statuses

    assert blocked_statuses() == frozenset({"unverified", "single_source"})


# ===================================================== yeniden puanlama
def test_engine_version_changes_with_mode(monkeypatch) -> None:  # noqa: ANN001
    """Mod açıldığında saklanan etiketler yeniden hesaplanmalı.

    `score_claims` "engine_version farklıysa yeniden puanla" der. Sürüm
    moda göre değişmeseydi, mod açıkken ekranda eski GEVŞEK etiketler
    kalırdı: göstergesi açık, koruması kapalı bir mod.
    """
    from politikdesk.evidence.rules import ENGINE_VERSION, engine_version

    monkeypatch.delenv(election_mode.ENV_VAR, raising=False)
    normal = engine_version()

    monkeypatch.setenv(election_mode.ENV_VAR, "true")
    strict = engine_version()

    assert normal == ENGINE_VERSION
    assert strict != normal
    assert "election" in strict


def test_engine_version_is_single_sourced() -> None:
    """`politikdesk.evidence` paketi kendi sürümünü TANIMLAMAMALI.

    Faz 0'da paket bir iskele sürümü tutuyordu ve motor yazıldıktan
    sonra güncellenmedi; iki farklı sürüm dolaşıma girdi.
    """
    import politikdesk.evidence as pkg
    from politikdesk.evidence.rules import ENGINE_VERSION

    assert pkg.ENGINE_VERSION == ENGINE_VERSION


# ===================================================== UI göstergesi
def test_banner_is_empty_when_off(election_off) -> None:  # noqa: ANN001
    assert election_mode.banner() == ""


def test_banner_is_visible_when_on(election_on) -> None:  # noqa: ANN001
    """Spec §12.6 madde 5."""
    banner = election_mode.banner()
    assert "ELECTION MODE" in banner
    assert "12.6" in banner


def test_shell_renders_the_banner(monkeypatch) -> None:  # noqa: ANN001
    from politikdesk.web.ui import page

    monkeypatch.setenv(election_mode.ENV_VAR, "true")
    assert "ELECTION MODE" in page("Test", "<p>govde</p>")

    monkeypatch.delenv(election_mode.ENV_VAR, raising=False)
    assert "ELECTION MODE" not in page("Test", "<p>govde</p>")


# ===================================================== yarı-otomasyon
def test_semi_automation_is_off_in_both_modes() -> None:
    """MVP'de yarı-otomasyon zaten yok (P5). Mod onu da kilitler; iki
    modda da kapalı olması, flag'in yanlışlıkla bir kapı AÇMADIĞININ
    kanıtıdır."""
    assert election_mode.NORMAL.semi_automation_allowed is False
    assert election_mode.ELECTION.semi_automation_allowed is False
