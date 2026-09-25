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
    """Spec §9.2 / D6: azami 25 ekonomi kaynağı (23 Ağu 2026, Fed/ECB/BoE ile).

    Bu testin koruduğu sözleşme İKİ parçalıdır ve ikisi de gereklidir:
      1. **Yapısal:** kaynak sayısı beyan edilen sınırı AŞAMAZ.
      2. **Değer:** sınırın kendisi sabittir ve değiştirmek bu testi
         kırar — yani sınır ancak bilinçli bir kararla değişir.
    """
    assert len(SOURCES) <= DATA["max_sources"] == 25, (
        f"{len(SOURCES)} kaynak var. Sınır 25'tir ve gerekçesi "
        "config/sources.yml başlığındadır (F5-01 / Faz B)."
    )


def test_source_count_matches_staged_rollout() -> None:
    """F5-06: 15 -> 20; 19 Ağu: EVDS 21; 20 Ağu: SBB 22; 23 Ağu: Fed/ECB/BoE 25.

    20 kaynak sınırı ile makro ekonomi, piyasalar, fintech, uzman blogları
    ve reel sektör çerçeveleme çeşitliliği en üst seviyeye çıkarıldı.
    21, 22 ve 23–25 MEDYA eklemesi değildir: Tier 1 birincil resmi
    merkez bankaları ve veri servisleridir.
    """
    assert len(SOURCES) == 25


def test_cap_has_no_silent_headroom() -> None:
    """`max_sources` HER ZAMAN kaynak sayısına eşittir — boşluk bırakılmaz.

    **Bu, "sınır 22'ye çıktı, artık yer var" yorumunu imkânsız kılar.**

    Sınır kaynak sayısından büyük olsaydı, sonraki bir ekleme hiçbir testi
    kırmadan sessizce geçerdi ve F5-01'in koruması ("kaynak eklemek
    yanıltıcı derecede tatmin edicidir, kümeleme hatasını gizler") fiilen
    kalkardı. Boşluk bırakmayarak her ekleme MECBUREN sınırı da
    değiştirir; sınır değişikliği bu dosyayı kırar; kırılan test bir
    insanın gerekçe yazmasını zorlar.

    Yani 21 -> 22 bir kapasite gevşetmesi DEĞİL, tek bir doğrulanmış
    kaynağın (SBB) alınmasıdır.
    """
    assert DATA["max_sources"] == len(SOURCES), (
        f"Sınır {DATA['max_sources']}, kaynak sayısı {len(SOURCES)}. "
        "Aradaki boşluk, bir sonraki kaynağın sessizce eklenmesine izin "
        "verir. Sınır her zaman kaynak sayısına eşit tutulmalıdır."
    )


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
    """9 resmî (omurga + küresel MB) + 2 ajans/uluslararası + 14 bağımsız yayın.

    19 Ağu 2026: Tier 1 dörtten beşe çıktı — TCMB EVDS eklendi.
    20 Ağu 2026: beşten altıya — SBB eklendi.
    23 Ağu 2026: altıdan dokuza — Fed, ECB, BoE eklendi.
    """
    counts: dict[int, int] = {}
    for s in SOURCES:
        counts[s["tier"]] = counts.get(s["tier"], 0) + 1
    assert counts == {1: 9, 2: 2, 3: 14}, counts


def test_every_source_has_a_distinct_independence_group() -> None:
    """F5-04'ün ölçütü hacim değil BAĞIMSIZLIKTIR.

    `diversity_ratio` (metrics.py) ve kanıt motorunun `independent_count`
    sayımı `independence_group` üzerinden gider. Aynı gruba iki yayın
    koymak bağımsız sayımı ŞİŞİRİR: sistem "iki bağımsız kaynak doğruluyor"
    derken aslında aynı yayın grubunun iki sitesi olur. Bu, teyit
    yokluğundan daha zararlıdır.

    Somut tuzak: hurriyet ve milliyet Demirören grubundadır, cnnturk da
    öyle. Üçünü birden eklemek üç bağımsız kaynak DEĞİL, bir tanedir.

    ── İSTİSNA: AYNI KURUMUN İKİ AKIŞI (19 Ağu 2026, TCMB EVDS)

    Kural farklı YAYINCILARIN aynı gruba düşmesini engeller. Aynı kurumun
    iki akışı (TCMB'nin RSS duyurusu ve EVDS veri servisi) grubu
    PAYLAŞMALIDIR — aksi hâlde tek kurum iki bağımsız kaynak sayılır ve
    kuralın engellemek istediği şişme tam da o olur. Yani burada grubu
    paylaşmak ihlal değil, kuralın doğru uygulanmasıdır.

    İstisna çıkarımla değil, BEYANLA tanınır: kaynak `same_institution_as`
    alanını taşımalıdır. Böylece kaza eseri çakışma ile bilinçli paylaşım
    birbirine karışmaz.
    """
    beyanli = {s["slug"] for s in SOURCES if s.get("same_institution_as")}
    for s in SOURCES:
        hedef = s.get("same_institution_as")
        if not hedef:
            continue
        esler = [o for o in SOURCES if o["slug"] == hedef]
        assert esler, f"{s['slug']}: same_institution_as='{hedef}' diye bir kaynak yok"
        assert esler[0]["independence_group"] == s["independence_group"], (
            f"{s['slug']} ile {hedef} ayni kurum ilan edilmis ama "
            "independence_group'lari FARKLI — beyan ise yaramiyor."
        )

    groups = [s["independence_group"] for s in SOURCES if s["slug"] not in beyanli]
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
    tier1 = [s for s in SOURCES if s["tier"] == 1]
    assert all(s["independence_group"] for s in tier1), (
        "Tier 1 kaynakların independence_group'u atanmalı"
    )
    # Aynı kurum ilan edenler dışarıda: bkz.
    # `test_every_source_has_a_distinct_independence_group` istisnası.
    groups = [s["independence_group"] for s in tier1 if not s.get("same_institution_as")]
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
    """Spec v3.5 §9.2: Dikey başına azami kaynak sınırı aşılamaz."""
    from politikdesk.ingestion.sources import MAX_VERTICAL_SOURCES, load_config

    leg_path = Path(__file__).resolve().parent.parent / "config" / "sources_legislation.yml"
    if leg_path.is_file():
        cfgs, _ = load_config(leg_path)
        assert len(cfgs) <= MAX_VERTICAL_SOURCES == 30


def test_global_source_limit_enforced() -> None:
    """Spec v3.5 §9.2: Toplam azami kaynak sınırı aşılamaz."""
    from politikdesk.ingestion.sources import MAX_GLOBAL_SOURCES, load_all_configs

    all_cfgs = load_all_configs()
    assert len(all_cfgs) <= MAX_GLOBAL_SOURCES
    assert MAX_GLOBAL_SOURCES == 120


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
    assert "medyascope" in slugs
    assert "kisadalga" in slugs
    assert "indyturk" in slugs
    assert "serbestiyet" in slugs
    assert "yetkinreport" in slugs
    assert "gazetepencere" in slugs
    assert "karar" in slugs
    assert "evrensel-politika" in slugs
    assert "halktv-politika" in slugs

    # Bağımsızlık grupları ayrışmış olmalı
    groups = [c.independence_group for c in configs if c.independence_group]
    assert len(set(groups)) == len(groups)


class _FakeFeedResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


def _fake_http_client(failing_slug: str | None = None):  # noqa: ANN202
    """`HttpClient` yerine geçen ağsız istemci.

    Önceki test gerçek kaynaklara bağlanıyordu: `timeout` yalnız HTTP isteğine
    uygulanıyor, `validate_url`in DNS çözümlemesi (`getaddrinfo`) süresiz. Yavaş
    DNS'li bir makinede tüm test paketi burada asılı kalıyordu. Canlı kaynak
    denetimi test değil operasyon işidir: `pd verify-feeds`.
    """
    rss = "<rss><channel><item><title>x</title></item></channel></rss>"

    class _Client:
        def __init__(self, timeout: float = 0.0) -> None:
            self.timeout = timeout

        def get(self, url: str, source_slug: str = "") -> _FakeFeedResponse:
            if source_slug == failing_slug:
                return _FakeFeedResponse(500, "")
            if "/portal/v2/posts" in url:
                return _FakeFeedResponse(200, '[{"id": 1}]')
            return _FakeFeedResponse(200, rss)

    return _Client


def test_verify_feeds_runner_passes_when_all_feeds_healthy(monkeypatch) -> None:  # noqa: ANN001
    """Tüm kaynaklar öğe döndürürse katı kipte bile çıkış kodu 0 olmalı."""
    import scripts.verify_feeds as verify_feeds

    monkeypatch.setattr(verify_feeds, "HttpClient", _fake_http_client())
    code = verify_feeds.verify_all_feeds(
        config_file="config/sources_legislation.yml", timeout=3.0, strict=True
    )
    assert code == 0


def test_verify_feeds_runner_strict_fails_on_broken_feed(monkeypatch) -> None:  # noqa: ANN001
    """Tek bir kaynak HTTP 500 verirse katı kip 1, gevşek kip 0 döndürmeli."""
    from pathlib import Path

    import scripts.verify_feeds as verify_feeds
    from politikdesk.ingestion.sources import load_config

    configs, _ = load_config(Path("config/sources_legislation.yml"))
    broken = next(c.slug for c in configs if c.adapter == "rss" and c.feed_url)
    monkeypatch.setattr(verify_feeds, "HttpClient", _fake_http_client(failing_slug=broken))
    config = "config/sources_legislation.yml"
    assert verify_feeds.verify_all_feeds(config_file=config, timeout=3.0, strict=True) == 1
    assert verify_feeds.verify_all_feeds(config_file=config, timeout=3.0, strict=False) == 0


def test_sync_to_database_deactivates_obsolete_sources(monkeypatch) -> None:  # noqa: ANN001
    """sync_to_database, YAML'da olmayan eski aktif kaynakları pasife almalı."""
    from contextlib import contextmanager
    from unittest.mock import MagicMock

    from politikdesk.ingestion.sources import SourceConfig, sync_to_database

    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (1,)  # Existing record
    mock_cur.rowcount = 2  # 2 obsolete sources deactivated
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    @contextmanager
    def fake_conn():
        yield mock_conn

    monkeypatch.setattr("politikdesk.db.connection", fake_conn)
    monkeypatch.setattr("politikdesk.audit.write", MagicMock())

    dummy_cfg = [
        SourceConfig(
            slug="test-active-source",
            name="Test Source",
            tier=1,
            kind="official",
            access_method="rss",
            tos_status="allowed",
            adapter="rss",
        )
    ]

    res = sync_to_database(dummy_cfg)
    assert res["deactivated"] == 2
    assert mock_cur.execute.call_count >= 2
