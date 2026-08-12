"""Kaynak yapılandırması testleri (F0-08, F0-09, D6).

Spec §9.2'nin "8 kaynak sert sınırı" bir yorum değil, denetlenen bir kuraldır:
"Kaynak eklemek kolay ve yanıltıcı derecede tatmin edicidir; kaliteyi
düşürür, kümeleme hatasını gizler."
"""

from __future__ import annotations

from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "sources.yml"
DATA = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
SOURCES = DATA["sources"]

VALID_KINDS = {"official", "wire", "media", "social"}
VALID_ACCESS = {"rss", "api", "official_feed", "manual"}
VALID_TOS = {"allowed", "restricted", "forbidden", "pending_review"}


def test_source_count_never_exceeds_hard_limit() -> None:
    """Spec §9.2 / D6: MVP'de 8'den fazla kaynak eklenmez."""
    assert len(SOURCES) <= DATA["max_sources"] == 8, (
        f"{len(SOURCES)} kaynak var. 9. kaynak ancak Faz 4 kalite hedefleri "
        "tutulduktan sonra eklenir (BACKLOG.md B-08)."
    )


def test_source_count_is_seven_after_reuters_dropped() -> None:
    """Reuters düşürüldü (açık akış yok, lisans riski) -> 8 yerine 7 kaynak.

    Sert sınır tavandır, hedef değil: 7 kaynak sınırın altındadır.
    """
    assert len(SOURCES) == 7


def test_slugs_are_unique() -> None:
    slugs = [s["slug"] for s in SOURCES]
    assert len(set(slugs)) == len(slugs)


def test_field_values_match_database_constraints() -> None:
    """Yapılandırma, migrations/0001_initial.sql CHECK kısıtlarını ihlal edemez."""
    for s in SOURCES:
        assert 1 <= s["tier"] <= 4, s["slug"]
        assert s["kind"] in VALID_KINDS, s["slug"]
        assert s["access_method"] in VALID_ACCESS, s["slug"]
        assert s["tos_status"] in VALID_TOS, s["slug"]


def test_no_forbidden_source_is_configured() -> None:
    """Spec §12.4 / F1-06: forbidden kaynaktan ingestion kod seviyesinde engelli.

    Böyle bir kaynağın listede durması yapılandırma hatasıdır.
    """
    forbidden = [s["slug"] for s in SOURCES if s["tos_status"] == "forbidden"]
    assert not forbidden, f"'forbidden' kaynak listeden çıkarılmalı: {forbidden}"


def test_no_social_tier_source_in_mvp() -> None:
    """Spec §9.4 / D7: Tier 4 içerik yalnızca kullanıcı-tetikli içe aktarımla girer."""
    social = [s["slug"] for s in SOURCES if s["kind"] == "social" or s["tier"] == 4]
    assert not social, f"MVP'de yapılandırılmış sosyal kaynak olamaz: {social}"


def test_tier_distribution() -> None:
    """4 resmî (omurga) + 1 ajans (kopya referansı) + 2 bağımsız yayın.

    Spec §9.2 iki ajans öngörüyordu; Reuters'ın açık akışı olmadığı için
    çapraz teyit rolü tek ajansa indi. Etkisi: sayısal olmayan iddialarda
    bağımsız sayım düşer (bkz. docs/karar-itirazlari.md İtiraz-2) ve
    Faz 2'de evidence_status dağılımı ile ölçülmelidir.
    """
    counts: dict[int, int] = {}
    for s in SOURCES:
        counts[s["tier"]] = counts.get(s["tier"], 0) + 1
    assert counts == {1: 4, 2: 1, 3: 2}, counts


def test_wire_reference_exists_for_copy_detection() -> None:
    """F1-11 ajans kopyası tespitinin çıpası tanımlı olmalı."""
    references = [s["slug"] for s in SOURCES if s.get("is_wire_reference")]
    assert references == ["aa-ekonomi"]


def test_primary_sources_exist_for_evidence_anchor() -> None:
    """Spec §9.1: Tier 1 omurga — kanıt zincirinin çıpası."""
    assert sum(1 for s in SOURCES if s["tier"] == 1) >= 4


def test_tier1_sources_are_in_distinct_independence_groups() -> None:
    """Dört resmî kurum birbirinden bağımsızdır; aynı gruba düşerlerse
    bağımsız kanıt sayımı (Spec §8.2) çöker."""
    groups = [s["independence_group"] for s in SOURCES if s["tier"] == 1]
    assert None not in groups, "Tier 1 kaynakların independence_group'u atanmalı"
    assert len(set(groups)) == len(groups), f"Tier 1 grupları çakışıyor: {groups}"


def test_wire_sources_have_distinct_independence_groups() -> None:
    """AA ve Reuters ayrı ajanslardır; kopyalama tespiti buna dayanır."""
    groups = [s["independence_group"] for s in SOURCES if s["kind"] == "wire"]
    assert len(set(groups)) == len(groups), groups


def test_scheduled_event_producers_exist() -> None:
    """Spec §9.5: 'beklenen gelişme' özelliği en az bir takvim kaynağı ister."""
    producers = [s["slug"] for s in SOURCES if s.get("produces_scheduled_events")]
    assert len(producers) >= 3, producers
    assert "tuik" in producers, "TÜİK veri takvimi MVP'nin gizli kozudur"


def test_declared_topics_are_within_mvp_scope() -> None:
    """Kaynak, MVP konu sınırı dışında bir konu beyan edemez (D4)."""
    from eval.golden_set_tools import VALID_TOPICS

    for s in SOURCES:
        unknown = set(s.get("topics") or []) - VALID_TOPICS
        assert not unknown, f"{s['slug']}: kapsam dışı konu(lar) {sorted(unknown)}"


def test_all_sources_have_tos_decision_and_name() -> None:
    """G0 koşul 3: kaynakların tamamı için tos_status kararı verilmiş.

    Hiçbiri 'pending_review' veya 'forbidden' olamaz.
    """
    for s in SOURCES:
        assert s["tos_status"] in {"allowed", "restricted"}, (
            f"{s['slug']}: ToS kararı yok ({s['tos_status']})"
        )
        assert s["independence_group"], f"{s['slug']}: independence_group atanmamış"
        assert "BELİRLENECEK" not in s["name"], f"{s['slug']}: isim kesinleşmemiş"


def test_verified_sources_have_a_feed_url() -> None:
    """`verified: true` iddiası boş olamaz — akış URL'i bulunmalı."""
    for s in SOURCES:
        if s.get("verified"):
            assert s["feed_url"], f"{s['slug']}: verified ama feed_url yok"


def test_unverified_sources_declare_a_probe_plan() -> None:
    """Doğrulanmamış kaynak, nasıl doğrulanacağını söylemeli.

    `scripts/discover_feeds.py` bu aday listesini kullanır.
    """
    for s in SOURCES:
        if s.get("verified"):
            continue
        has_plan = bool(s.get("probe")) or bool(s.get("feed_url"))
        assert has_plan, (
            f"{s['slug']}: doğrulanmamış ve probe planı yok. "
            "config/sources.yml içine probe.candidates ekleyin."
        )
