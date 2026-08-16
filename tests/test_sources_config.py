"""Kaynak yapılandırması testleri (F0-08, F0-09, D6 · F5-01'de revize).

Spec §9.2'nin kaynak sınırı bir yorum değil, denetlenen bir kuraldır:
"Kaynak eklemek kolay ve yanıltıcı derecede tatmin edicidir; kaliteyi
düşürür, kümeleme hatasını gizler."

**F5-01 (13 Ağu 2026): sınır 8 -> 15.** Uyarı hâlâ geçerli ama ölçüm
sınırın ürünün ana metriğini yapısal olarak engellediğini gösterdi:
iddiası olan 25 olayın yalnızca 2'sinde birden fazla bağımsız kaynak
grubu vardı, dolayısıyla R2'nin (🟢) istediği `independent_count >= 3`
hiçbir zaman sağlanamıyordu. Gerekçe `config/sources.yml` başlığında.

Sınırın gevşemesi kalite kapılarının gevşemesi DEĞİLDİR — aşağıdaki
bağımsızlık ve dağılım testleri korunur ve genişletilir.
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
    """Spec §9.2 / D6 (v3.3): azami 15 kaynak."""
    assert len(SOURCES) <= DATA["max_sources"] == 15, (
        f"{len(SOURCES)} kaynak var. Sınır 15'tir ve gerekçesi "
        "config/sources.yml başlığındadır (F5-01)."
    )


def test_source_count_matches_staged_rollout() -> None:
    """F5-04: 7 -> 10. 15'e TEK ADIMDA çıkılmaz.

    Kademe kasıtlıdır: 10 kaynakla en az bir hafta ölçülür (kümeleme
    precision >= 0,88 korunuyor mu, konu filtresi yeni kaynaklarda
    alakasız içerik geçiriyor mu) ve ancak regresyon yoksa 15'e devam
    edilir (F5-05). Bu test o kademeyi görünür tutar: sayıyı artıran
    kişi testi de değiştirmek zorundadır, yani artış bilinçli olur.
    """
    assert len(SOURCES) == 10


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
    """4 resmî (omurga) + 1 ajans (kopya referansı) + 5 bağımsız yayın.

    Spec §9.2 iki ajans öngörüyordu; Reuters'ın açık akışı olmadığı için
    çapraz teyit rolü tek ajansa indi. Etkisi: sayısal olmayan iddialarda
    bağımsız sayım düşer (bkz. docs/karar-itirazlari.md İtiraz-2).

    F5-04 Tier 3'ü 2'den 5'e çıkardı. Tier 1 SABİT kaldı ve bu bir
    eksiklik değil, engeldir: TÜİK (B-42, hesap gerekiyor) ve Resmî
    Gazete (B-44, TR çıkış IP'si gerekiyor) hâlâ ölü. R2'nin (🟢)
    istediği `has_primary_source` bu ikisi açılmadan güçlenmez —
    Tier 3 genişlemesi `diversity_ratio` ve R4'ü (🟡) besler, R2'yi değil.
    """
    counts: dict[int, int] = {}
    for s in SOURCES:
        counts[s["tier"]] = counts.get(s["tier"], 0) + 1
    assert counts == {1: 4, 2: 1, 3: 5}, counts


def test_every_source_has_a_distinct_independence_group() -> None:
    """F5-04'ün ölçütü hacim değil BAĞIMSIZLIKTIR.

    `diversity_ratio` (metrics.py) ve kanıt motorunun `independent_count`
    sayımı `independence_group` üzerinden gider. Aynı gruba iki yayın
    koymak bağımsız sayımı ŞİŞİRİR: sistem "iki bağımsız kaynak doğruluyor"
    derken aslında aynı yayın grubunun iki sitesi olur. Bu, teyit
    yokluğundan daha zararlıdır.

    Somut tuzak: hurriyet ve milliyet Demirören grubundadır, cnnturk da
    öyle. Üçünü birden eklemek üç bağımsız kaynak DEĞİL, bir tanedir.
    """
    groups = [s["independence_group"] for s in SOURCES]
    duplicates = {g for g in groups if groups.count(g) > 1}
    assert not duplicates, f"aynı bağımsızlık grubunda birden fazla kaynak: {duplicates}"


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


# ===========================================================================
# S1.1 — Multi-Vertical Configuration Tests
# ===========================================================================
def test_load_all_configs_loads_both_verticals() -> None:
    """sources.yml ve sources_legislation.yml birlikte yüklenir."""
    from politikdesk.ingestion.sources import load_all_configs

    all_cfgs = load_all_configs()
    slugs = {c.slug for c in all_cfgs}
    assert "tcmb" in slugs
    assert "tbmm" in slugs
    assert "sayistay" in slugs
    assert "cb-kararname" in slugs

    verticals = {c.vertical for c in all_cfgs}
    assert "macro_economy" in verticals
    assert "legislation" in verticals


def test_vertical_source_limit_enforced() -> None:
    """Spec v3.5 §9.2: Dikey başına azami 15 kaynak sınırı aşılamaz."""
    from politikdesk.ingestion.sources import MAX_VERTICAL_SOURCES, load_config

    leg_path = Path(__file__).resolve().parent.parent / "config" / "sources_legislation.yml"
    if leg_path.is_file():
        cfgs, _ = load_config(leg_path)
        assert len(cfgs) <= MAX_VERTICAL_SOURCES == 15


def test_global_source_limit_enforced() -> None:
    """Spec v3.5 §9.2: Toplam azami kaynak sınırı aşılamaz."""
    from politikdesk.ingestion.sources import MAX_GLOBAL_SOURCES, load_all_configs

    all_cfgs = load_all_configs()
    assert len(all_cfgs) <= MAX_GLOBAL_SOURCES
    assert MAX_GLOBAL_SOURCES == 60


def test_duplicate_slug_across_verticals_rejected(tmp_path: Path) -> None:
    """İki dikeyde aynı slug kullanılırsa load_all_configs ValueError fırlatır."""
    from politikdesk.ingestion.sources import load_all_configs

    f1 = tmp_path / "sources_1.yml"
    f1.write_text(
        """
vertical: macro_economy
max_sources: 12
sources:
  - slug: dup-source
    name: Test 1
    tier: 1
    kind: official
    access_method: rss
    tos_status: allowed
    base_url: https://test1.com
""",
        encoding="utf-8",
    )

    f2 = tmp_path / "sources_2.yml"
    f2.write_text(
        """
vertical: legislation
max_sources: 12
sources:
  - slug: dup-source
    name: Test 2
    tier: 1
    kind: official
    access_method: rss
    tos_status: allowed
    base_url: https://test2.com
""",
        encoding="utf-8",
    )

    import pytest

    with pytest.raises(ValueError, match="çakışan slug"):
        load_all_configs(tmp_path)


def test_legislation_sources_configured() -> None:
    """sources_legislation.yml dosyasındaki tüm medya ve resmi kaynaklar doğrulanmalı."""
    from politikdesk.ingestion.sources import load_config

    leg_path = Path(__file__).resolve().parent.parent / "config" / "sources_legislation.yml"
    configs, _ = load_config(leg_path)
    slugs = {c.slug for c in configs}

    assert "t24-politika" in slugs
    assert "gazeteduvar-politika" in slugs
    assert "diken-siyaset" in slugs
    assert "sozcu-politika" in slugs
    assert "bbc-turkce" in slugs
    assert "tbmm" in slugs
    assert "sayistay" in slugs
    assert "cb-kararname" in slugs

    # Bağımsızlık grupları ayrışmış olmalı
    groups = [c.independence_group for c in configs if c.independence_group]
    assert len(set(groups)) == len(groups)


def test_verify_feeds_runner() -> None:
    """verify_feeds aracı yapılandırma dosyalarını başarıyla denetlemeli."""
    from scripts.verify_feeds import verify_all_feeds

    # Mock/hızlı çalıştırma testi
    code = verify_all_feeds(config_file="config/sources_legislation.yml", timeout=3.0, strict=False)
    assert code == 0
