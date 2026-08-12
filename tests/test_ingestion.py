"""Faz 1 — ingestion testleri (F1-01…F1-12)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from politikdesk.ingestion import guard, topics
from politikdesk.ingestion.adapters.base import FakeAdapter, SourceAdapter, registry
from politikdesk.ingestion.adapters.manual import (
    UnsafeUrlError,
    classify_host,
    is_social,
    parse_metadata,
    validate_url,
)
from politikdesk.ingestion.adapters.official import (
    TuikAdapter,
    extract_period_from_title,
    harvest_links,
)
from politikdesk.ingestion.adapters.rss import MalformedFeed, RssAdapter, parse_feed_date
from politikdesk.ingestion.dedup import (
    DuplicateVerdict,
    classify,
    compute_simhash,
    containment,
    hamming_distance,
    is_near_duplicate,
    ngram_set,
    tokenize,
)
from politikdesk.ingestion.independence import (
    ArticleFingerprint,
    breakdown_by_kind,
    count_independent,
    independence_key,
)
from politikdesk.ingestion.models import RawItem
from politikdesk.ingestion.normalizer import (
    EXCERPT_MAX_CHARS,
    RAW_RETENTION_DAYS,
    canonicalize_url,
    clean_text,
    content_hash,
    make_excerpt,
    normalize,
)


# ---------------------------------------------------------------- F1-01
def test_fake_adapter_satisfies_protocol() -> None:
    """DoD: sahte adaptörle test geçiyor."""
    adapter = FakeAdapter("test")
    assert isinstance(adapter, SourceAdapter)
    assert adapter.fetch() == []


def test_registry_resolves_adapters() -> None:
    assert "rss" in registry.keys()  # noqa: SIM118
    assert "tuik" in registry.keys()  # noqa: SIM118
    assert registry.get("rss") is RssAdapter


def test_registry_rejects_duplicate_registration() -> None:
    with pytest.raises(ValueError, match="zaten kayıtlı"):
        registry.register("rss", RssAdapter)


def test_raw_item_rejects_empty_fields() -> None:
    with pytest.raises(ValueError, match="url"):
        RawItem(source_slug="s", url="", title="t")
    with pytest.raises(ValueError, match="title"):
        RawItem(source_slug="s", url="https://x.test", title="")


# ---------------------------------------------------------------- F1-02
RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Test Akisi</title>
  <item>
    <guid isPermaLink="false">1</guid>
    <link>https://ornek.test/tr/ekonomi/enflasyon-verisi/1</link>
    <title>TUIK Temmuz enflasyon verisini acikladi</title>
    <description>Aylik TUFE yuzde 2,1 arttI.</description>
    <pubDate>Wed, 12 Aug 2026 11:06:56 +0300</pubDate>
  </item>
  <item>
    <link>/wps/goreli/yol/2</link>
    <title>TCMB faiz kararini acikladi</title>
    <description>Politika faizi sabit birakildi.</description>
    <pubDate>Wed, 12 Aug 2026 10:00:00 +0300</pubDate>
  </item>
</channel></rss>"""

ATOM_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>a1</id>
    <title>Butce gerceklesmeleri aciklandi</title>
    <link href="https://ornek.test/butce"/>
    <summary>Merkezi yonetim butce acigi.</summary>
    <published>2026-08-12T08:00:00Z</published>
  </entry>
</feed>"""


def test_rss_adapter_parses_items() -> None:
    adapter = RssAdapter("test", "https://ornek.test/rss")
    items = adapter.parse(RSS_SAMPLE)
    # İkinci öğenin linki görelidir ve base_url verilmediği için çözülemez;
    # atlanması doğru davranıştır (bkz. bir sonraki test).
    assert len(items) == 1
    assert items[0].title == "TUIK Temmuz enflasyon verisini acikladi"
    assert items[0].published_at == datetime(2026, 8, 12, 8, 6, 56, tzinfo=UTC)


def test_rss_adapter_skips_unresolvable_relative_link() -> None:
    """base_url yoksa göreli link mutlaklaştırılamaz — uydurulmaz, atlanır."""
    items = RssAdapter("test", "https://ornek.test/rss").parse(RSS_SAMPLE)
    assert all(i.url.startswith("https://ornek.test/tr/") for i in items)


def test_rss_adapter_resolves_relative_links() -> None:
    """TCMB göreli yol döndürür; base_url ile mutlaklaştırılmalı."""
    adapter = RssAdapter("tcmb", "https://ornek.test/rss",
                         base_url="https://www.tcmb.gov.tr")
    items = adapter.parse(RSS_SAMPLE)
    assert len(items) == 2
    assert items[1].url == "https://www.tcmb.gov.tr/wps/goreli/yol/2"


def test_rss_adapter_parses_atom() -> None:
    adapter = RssAdapter("test", "https://ornek.test/atom")
    items = adapter.parse(ATOM_SAMPLE)
    assert len(items) == 1
    assert items[0].url == "https://ornek.test/butce"


def test_rss_adapter_raises_on_malformed_xml() -> None:
    adapter = RssAdapter("test", "https://ornek.test/rss")
    with pytest.raises(MalformedFeed):
        adapter.parse("<rss><channel><item>kapanmamis")


def test_rss_adapter_does_not_crash_on_bad_feed() -> None:
    """DoD: hatalı feed'de çökmüyor, loglayıp geçiyor."""
    class _BoomHttp:
        def get(self, url: str, *, source_slug: str = "") -> object:
            raise ConnectionError("ag hatasi")

    adapter = RssAdapter("test", "https://ornek.test/rss", http=_BoomHttp())
    assert adapter.fetch() == []  # istisna dışarı sızmaz


def test_rss_adapter_skips_items_missing_required_fields() -> None:
    partial = """<rss><channel>
      <item><title>Baslik var link yok</title></item>
      <item><link>https://ornek.test/a</link><title>Enflasyon haberi</title></item>
    </channel></rss>"""
    items = RssAdapter("t", "u").parse(partial)
    assert len(items) == 1


def test_rss_keyword_filter_applies() -> None:
    """Resmî Gazete gibi yüksek hacimli kaynaklar için konu filtresi."""
    adapter = RssAdapter("rg", "u", keyword_filter=["vergi"])
    assert adapter.parse(RSS_SAMPLE) == []

    adapter2 = RssAdapter("rg", "u", keyword_filter=["enflasyon"])
    assert len(adapter2.parse(RSS_SAMPLE)) == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Wed, 12 Aug 2026 11:06:56 +0300", datetime(2026, 8, 12, 8, 6, 56, tzinfo=UTC)),
        ("2026-08-12T08:00:00Z", datetime(2026, 8, 12, 8, 0, tzinfo=UTC)),
        ("2026-08-12T11:00:00+03:00", datetime(2026, 8, 12, 8, 0, tzinfo=UTC)),
        ("gecersiz tarih", None),
        ("", None),
    ],
)
def test_feed_date_parsing_normalizes_to_utc(raw: str, expected: datetime | None) -> None:
    assert parse_feed_date(raw) == expected


# ---------------------------------------------------------------- F1-03
def test_harvest_links_extracts_absolute_urls() -> None:
    html = '<a href="/Bulten/Index?p=Test-Temmuz-2026-123">Bir Bulten</a>'
    links = harvest_links(html, "https://veriportali.tuik.gov.tr/Bulten/Index")
    assert links[0][0].startswith("https://veriportali.tuik.gov.tr/Bulten/Index?p=")


def test_tuik_adapter_parses_bulletin_list() -> None:
    html = """
      <a href="/Bulten/Index?p=Tuketici-Fiyat-Endeksi-Temmuz-2026-58293">
        Tüketici Fiyat Endeksi, Temmuz 2026</a>
      <a href="/Kurumsal/Hakkimizda">Hakkimizda</a>
      <a href="/Bulten/Index?p=Isgucu-Istatistikleri-Haziran-2026-58201">
        İşgücü İstatistikleri, Haziran 2026</a>
    """
    items = TuikAdapter().parse(html, base_url="https://veriportali.tuik.gov.tr/Bulten/Index")
    assert len(items) == 2
    assert "Tüketici Fiyat Endeksi" in items[0].title
    assert items[0].published_at == datetime(2026, 7, 1, tzinfo=UTC)


def test_tuik_adapter_returns_empty_on_js_rendered_page() -> None:
    """Boş liste sessizce başarı sayılmaz — çağıran uyarır."""
    assert TuikAdapter().parse("<html><body></body></html>", base_url="https://x.test") == []


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Tüketici Fiyat Endeksi, Temmuz 2026", datetime(2026, 7, 1, tzinfo=UTC)),
        ("İşgücü İstatistikleri, Aralık 2025", datetime(2025, 12, 1, tzinfo=UTC)),
        ("Başlıkta dönem yok", None),
    ],
)
def test_period_extraction(title: str, expected: datetime | None) -> None:
    assert extract_period_from_title(title) == expected


# ---------------------------------------------------------------- F1-04
def test_manual_import_rejects_localhost() -> None:
    """SSRF koruması — kullanıcı girdisi alan tek uç."""
    for url in ("http://localhost:8000/admin", "http://127.0.0.1/", "http://[::1]/"):
        with pytest.raises(UnsafeUrlError):
            validate_url(url, resolve_dns=False)


def test_manual_import_rejects_private_ranges() -> None:
    for url in ("http://10.0.0.1/", "http://192.168.1.1/", "http://169.254.169.254/"):
        with pytest.raises(UnsafeUrlError):
            validate_url(url, resolve_dns=False)


def test_manual_import_rejects_non_http_schemes() -> None:
    for url in ("file:///etc/passwd", "ftp://ornek.test/x", "gopher://x"):
        with pytest.raises(UnsafeUrlError):
            validate_url(url, resolve_dns=False)


def test_manual_import_accepts_public_url() -> None:
    assert validate_url("https://ornek.test/haber", resolve_dns=False)


def test_social_links_route_to_tier4() -> None:
    """Spec §9.4: X içeriği Tier 4'e düşer, R7 tavanına tabidir."""
    assert is_social("https://x.com/kullanici/status/123")
    assert classify_host("https://x.com/a/status/1") == "manual-social"
    assert classify_host("https://www.dunya.com/haber") == "manual-web"


def test_metadata_parsing_prefers_open_graph() -> None:
    html = """<html><head>
      <title>Sayfa basligi</title>
      <meta property="og:title" content="OG Baslik">
      <meta property="og:description" content="Aciklama">
      <meta property="article:published_time" content="2026-08-12T09:00:00Z">
    </head></html>"""
    meta = parse_metadata(html)
    assert meta["title"] == "OG Baslik"
    assert meta["description"] == "Aciklama"


def test_metadata_falls_back_to_title_tag() -> None:
    meta = parse_metadata("<html><head><title>Yedek baslik</title></head></html>")
    assert meta["title"] == "Yedek baslik"


# ---------------------------------------------------------------- F1-06
def test_guard_blocks_forbidden_source() -> None:
    """DoD: yasaklı kaynak eklendiğinde exception fırlıyor."""
    with pytest.raises(guard.ForbiddenSourceError) as exc:
        guard.check("kotu-kaynak", "forbidden")
    assert exc.value.slug == "kotu-kaynak"


def test_guard_blocks_unreviewed_source() -> None:
    with pytest.raises(guard.UnreviewedSourceError):
        guard.check("yeni-kaynak", "pending_review")


def test_guard_allows_reviewed_source() -> None:
    decision = guard.check("tuik", "allowed")
    assert decision.allowed and decision.store_excerpt


def test_guard_restricted_source_stores_no_excerpt() -> None:
    """`restricted`: yalnızca meta veri + link (Spec §9.3)."""
    decision = guard.check("kisitli", "restricted")
    assert decision.allowed and not decision.store_excerpt


def test_guard_skips_inactive_source_without_error() -> None:
    decision = guard.check("pasif", "allowed", is_active=False)
    assert not decision.allowed


def test_guard_rejects_unknown_status() -> None:
    with pytest.raises(guard.ForbiddenSourceError):
        guard.check("x", "belki")


# ---------------------------------------------------------------- F1-08
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://ornek.test/haber?utm_source=twitter&utm_medium=social",
         "https://ornek.test/haber"),
        ("https://www.ornek.test/haber/", "https://ornek.test/haber"),
        ("https://ORNEK.test/Haber#bolum", "https://ornek.test/Haber"),
        ("https://ornek.test/h?fbclid=abc&id=5", "https://ornek.test/h?id=5"),
        ("https://ornek.test/h?b=2&a=1", "https://ornek.test/h?a=1&b=2"),
        ("https://ornek.test:443/h", "https://ornek.test/h"),
    ],
)
def test_url_canonicalization(raw: str, expected: str) -> None:
    assert canonicalize_url(raw) == expected


def test_canonicalization_makes_tracking_variants_identical() -> None:
    """Aynı içerik farklı URL ile gelirse tekilleştirme çöker."""
    a = canonicalize_url("https://dunya.com/haber/x?utm_source=rss")
    b = canonicalize_url("https://www.dunya.com/haber/x/")
    assert a == b


def test_clean_text_strips_html_and_normalizes_whitespace() -> None:
    assert clean_text("<p>Merhaba  <b>d&uuml;nya</b></p>\n\n") == "Merhaba dünya"
    assert clean_text("a &amp; b") == "a & b"
    assert clean_text(None) == ""


def test_turkish_characters_survive_normalization() -> None:
    """F1-08 DoD: Türkçe karakter sorunları yok."""
    text = "İzmir'de ÜFE ve TÜFE açıklandı — ığüşöç ĞÜŞÖÇ"
    assert clean_text(text) == text


# ---------------------------------------------------------------- F1-09
def test_excerpt_respects_300_char_limit() -> None:
    long_text = "kelime " * 200
    excerpt = make_excerpt(long_text)
    assert excerpt is not None
    assert len(excerpt) <= EXCERPT_MAX_CHARS


def test_excerpt_does_not_cut_mid_word() -> None:
    excerpt = make_excerpt("enflasyon " * 60)
    assert excerpt is not None
    assert not excerpt.rstrip("…").endswith("enflas")


def test_excerpt_returns_none_for_empty_input() -> None:
    assert make_excerpt("") is None
    assert make_excerpt("   ") is None


def test_normalize_sets_purge_deadline_at_30_days() -> None:
    """Spec §9.3: gövde azami 30 gün saklanır."""
    now = datetime(2026, 8, 12, tzinfo=UTC)
    article = normalize(
        RawItem(source_slug="aa", url="https://ornek.test/a", title="Enflasyon",
                summary="TUFE verisi"),
        now=now,
    )
    assert article.raw_purge_at == now + timedelta(days=RAW_RETENTION_DAYS)


def test_normalize_omits_excerpt_for_restricted_source() -> None:
    article = normalize(
        RawItem(source_slug="x", url="https://ornek.test/a", title="Baslik",
                summary="Uzun ozet metni"),
        store_excerpt=False,
    )
    assert article.excerpt is None
    assert article.lead_paragraph is None


def test_normalize_converts_naive_datetime_to_utc() -> None:
    article = normalize(
        RawItem(source_slug="x", url="https://ornek.test/a", title="B",
                published_at=datetime(2026, 8, 12, 10, 0)),
    )
    assert article.published_at is not None
    assert article.published_at.tzinfo is UTC


# ---------------------------------------------------------------- F1-10
def test_identical_content_produces_identical_hash() -> None:
    assert content_hash("Baslik", "ozet") == content_hash("Baslik", "ozet")


def test_content_hash_is_case_insensitive() -> None:
    assert content_hash("BASLIK", "OZET") == content_hash("baslik", "ozet")


def test_exact_duplicate_is_not_stored() -> None:
    """F1-10 DoD: aynı içerik iki kez gelirse ikinci kayıt oluşmuyor."""
    verdict = classify(
        "hash-a", 123,
        existing_hashes={"hash-a": 7}, existing_simhashes=[(7, 123)],
    )
    assert verdict.kind == "exact"
    assert verdict.should_store is False
    assert verdict.matched_article_id == 7


def test_new_article_is_stored() -> None:
    verdict = classify("yeni", 0, existing_hashes={}, existing_simhashes=[])
    assert verdict == DuplicateVerdict(kind="new")
    assert verdict.should_store


# ---------------------------------------------------------------- F1-11
def test_simhash_is_deterministic() -> None:
    text = "TCMB politika faizini sabit birakti"
    assert compute_simhash(text) == compute_simhash(text)


def test_simhash_detects_wire_copy() -> None:
    """F1-11 DoD: ajans metnini kopyalayan site tespit edilmeli."""
    original = (
        "Türkiye Cumhuriyet Merkez Bankası Para Politikası Kurulu politika "
        "faizini yüzde 40 seviyesinde sabit tutma kararı aldı. Karar metninde "
        "enflasyonun ana eğiliminde belirgin bir bozulma görülmediği belirtildi."
    )
    # Kopyalayan site tipik olarak başına/sonuna kendi cümlesini ekler
    copy = (
        "Türkiye Cumhuriyet Merkez Bankası Para Politikası Kurulu politika "
        "faizini yüzde 40 seviyesinde sabit tutma kararı aldı. Karar metninde "
        "enflasyonun ana eğiliminde belirgin bir bozulma görülmediği belirtildi. "
        "Piyasalar kararı bekliyordu."
    )
    # Spec §8.2 iki sinyal tanımlar; kısa metinde simhash tek başına yetmez.
    assert is_near_duplicate(
        compute_simhash(original), compute_simhash(copy),
        text_a=original, text_b=copy,
    ), "Ajans kopyası her iki sinyalle de yakalanamadı"


def test_ngram_containment_catches_what_simhash_misses() -> None:
    """Kısa metne cümle eklenmesi simhash'i 6 bitten fazla kaydırabilir.

    Bu, F1-11'in en riskli senaryosudur: kopyalayan site metnin sonuna
    kendi cümlesini ekler. İkinci sinyal (n-gram içermesi) bunu yakalar.
    """
    original = (
        "Türkiye Cumhuriyet Merkez Bankası Para Politikası Kurulu politika "
        "faizini yüzde 40 seviyesinde sabit tutma kararı aldı."
    )
    copy = original + " Piyasalar kararı bekliyordu ve tepki sınırlı kaldı."

    ratio = containment(ngram_set(original), ngram_set(copy))
    assert ratio >= 0.60, f"n-gram içerme oranı düşük: {ratio:.2f}"


def test_ngram_containment_separates_different_articles() -> None:
    a = "TÜİK temmuz tüketici fiyat endeksini açıkladı aylık enflasyon yükseldi"
    b = "Hazine iç borçlanma stratejisini duyurdu tahvil ihalesi düzenlenecek"
    assert containment(ngram_set(a), ngram_set(b)) < 0.60


def test_simhash_separates_genuinely_different_articles() -> None:
    a = compute_simhash(
        "TÜİK temmuz ayı tüketici fiyat endeksini açıkladı aylık enflasyon yüzde iki"
    )
    b = compute_simhash(
        "Hazine ve Maliye Bakanlığı iç borçlanma stratejisini duyurdu tahvil ihalesi"
    )
    assert hamming_distance(a, b) > 6
    assert not is_near_duplicate(a, b)


def test_near_duplicate_is_stored_but_flagged() -> None:
    """Ajans kopyası ayrı bir yayındır: saklanır ama tek sayılır."""
    text = "TCMB faizi sabit tuttu enflasyon gorunumu degismedi karar metni"
    simhash = compute_simhash(text)
    verdict = classify(
        "farkli-hash", simhash,
        existing_hashes={}, existing_simhashes=[(3, simhash)],
    )
    assert verdict.kind == "near"
    assert verdict.should_store is True
    assert verdict.matched_article_id == 3


def test_empty_simhash_never_matches() -> None:
    assert not is_near_duplicate(0, 0)
    assert not is_near_duplicate(123, 0)


def test_tokenizer_handles_turkish_uppercase_i() -> None:
    """'İSTANBUL' ve 'istanbul' aynı token olmalı."""
    assert tokenize("İSTANBUL ENFLASYON") == tokenize("istanbul enflasyon")


def test_tokenizer_drops_stopwords() -> None:
    assert "ve" not in tokenize("enflasyon ve faiz")


# ------------------------------------------------------- bağımsız sayım
def _fp(aid: int, slug: str, group: str | None, kind: str, simhash: int = 0):
    return ArticleFingerprint(aid, slug, group, kind, simhash)


def test_independent_count_treats_same_group_as_one() -> None:
    """Spec §8.2: aynı yayın grubu tek sayılır."""
    articles = [
        _fp(1, "a", "grup-x", "media"),
        _fp(2, "b", "grup-x", "media"),
        _fp(3, "c", "grup-y", "media"),
    ]
    assert count_independent(articles) == 2


def test_wire_copy_collapses_into_wire_group() -> None:
    """Ajans metnini kopyalayan medya bağımsız teyit sayılmaz."""
    text = "TCMB politika faizini sabit tuttu karar metninde enflasyon vurgusu"
    simhash = compute_simhash(text)

    wire = _fp(1, "aa-ekonomi", "wire-aa", "wire", simhash)
    copier = _fp(2, "kopyaci", None, "media", simhash)
    original = _fp(3, "ozgun", None, "media", compute_simhash(
        "Hazine eurobond ihracina cikti talep guclu geldi yatirimci ilgisi"
    ))

    assert independence_key(copier, wire_articles=[wire]) == "wire:aa-ekonomi"
    assert count_independent([wire, copier, original]) == 2


def test_breakdown_by_kind_matches_ui_contract() -> None:
    """Spec §8.2: tek toplam sayı değil, kırılım gösterilir."""
    articles = [
        _fp(1, "tuik", "official-tuik", "official"),
        _fp(2, "aa-ekonomi", "wire-aa", "wire"),
        _fp(3, "dunya", "media-dunya", "media"),
        _fp(4, "bloomberght", "media-bloomberght", "media"),
    ]
    assert breakdown_by_kind(articles) == {
        "official": 1, "wire": 1, "media": 2, "social": 0
    }


# ---------------------------------------------------------------- konu
def test_topic_classification_matches_mvp_scope() -> None:
    assert "enflasyon" in topics.classify("TÜİK temmuz TÜFE verisini açıkladı")
    assert "politika_faizi" in topics.classify("PPK faiz kararını açıkladı")
    assert "vergi_ve_harclar" in topics.classify("ÖTV oranlarında düzenleme")


def test_out_of_scope_content_is_filtered() -> None:
    """Spec §5: MVP dikeyi makro ekonomi."""
    assert topics.classify("Fenerbahçe Şampiyonlar Ligi maçı ne zaman") == ()
    assert not topics.in_scope("İspanya güneş tutulması turizmi patlattı")


def test_all_topic_keys_match_golden_set_vocabulary() -> None:
    from eval.golden_set_tools import VALID_TOPICS

    assert set(topics.TOPIC_KEYWORDS) == VALID_TOPICS


def test_topic_classifier_is_case_and_diacritic_aware() -> None:
    assert topics.classify("ENFLASYON RAPORU") == topics.classify("enflasyon raporu")


# ------------------------------------------------- ülke bağlamı (Spec §5)
def test_foreign_macro_news_is_out_of_scope() -> None:
    """MVP dikeyi TÜRKİYE makro ekonomisidir.

    Konu anahtar kelimesi eşleşse bile yabancı bağlam kapsam dışıdır
    (docs/mvp-konu-kapsami.md kapsam dışı tablosu).
    """
    assert topics.classify("Almanya'da enflasyon yeniden yükselişte") == ()
    assert topics.classify("Rusya'nın federal bütçe açığı 79 milyar dolara çıktı") == ()
    assert topics.classify("Fed faiz kararı ne zaman açıklanıyor?") == ()
    assert topics.classify("Küresel piyasalarda gözler ABD enflasyon verilerinde") == ()


def test_turkish_macro_news_stays_in_scope() -> None:
    assert "enflasyon" in topics.classify("TÜİK temmuz TÜFE verisini açıkladı")
    assert "politika_faizi" in topics.classify("TCMB PPK faiz kararını açıkladı")
    assert "butce_ve_hazine" in topics.classify(
        "Hazine ve Maliye Bakanlığı bütçe gerçekleşmelerini yayımladı"
    )


def test_topic_match_without_country_filter_is_available_for_diagnosis() -> None:
    """Filtrenin neden elediğini görebilmek gerekir."""
    assert "enflasyon" in topics.match_topics("Almanya'da enflasyon yükseldi")
    assert topics.classify("Almanya'da enflasyon yükseldi") == ()


def test_ambiguous_text_without_foreign_signal_is_kept() -> None:
    """Ülke sinyali hiç yoksa kapsam içi varsayılır (yanlış eleme yapma)."""
    assert topics.classify("Asgari ücret zammı için komisyon toplanıyor")


def test_html_entities_are_decoded() -> None:
    """F1-08 DoD: canlı veride &rsquo; &ldquo; gibi varlıklar sızıyordu."""
    # &rsquo; ASCII kesme işareti değil, U+2019 tipografik kesmedir.
    assert clean_text("Kara&rsquo;n&#305;n &ldquo;T&uuml;rkiye&rdquo; sunumu") == (
        "Kara’nın “Türkiye” sunumu"
    )
    assert clean_text("bo&nbsp;luk") == "bo luk"


def test_keyword_matching_respects_word_boundaries() -> None:
    """Canlı veride ölçülen hata: 'harcandı' vergi konusuna düşüyordu."""
    assert "vergi_ve_harclar" not in topics.match_topics(
        "AR-GE'ye geçen yıl 253,5 milyar lira harcandı"
    )
    assert "vergi_ve_harclar" in topics.match_topics("Harçlara zam yapıldı")


def test_turkish_suffixes_still_match() -> None:
    """Türkçe eklemeli bir dil: 'enflasyonun' da eşleşmeli."""
    assert "enflasyon" in topics.match_topics("Enflasyonun ana eğilimi")
    assert "politika_faizi" in topics.match_topics("Politika faizindeki değişim")


def test_price_listicles_are_not_events() -> None:
    """docs/mvp-konu-kapsami.md: kurun seviyesi olay değil, piyasa fiyatıdır."""
    assert topics.classify("Dolar ve Euro kuru bugün ne kadar oldu? 6 Ağustos 2026") == ()
    assert topics.is_non_event("Güncel kur: dolar kaç TL")


def test_short_abbreviations_do_not_fake_turkey_context() -> None:
    """'tl' iki harfli kısaltması yabancı haberi Türkiye sanıyordu."""
    assert not topics.has_turkey_context(
        "Fed yetkililerinden şahin açıklamalar", "ABD ekonomisi için sinyal"
    )


def test_country_neutral_phrases_do_not_fake_turkey_context() -> None:
    """'ABD merkez bankasının' ifadesi Türkiye bağlamı sayılmamalı."""
    assert topics.classify(
        "Fed yetkililerinden şahin açıklamalar",
        "Minneapolis Fed Başkanı Neel Kashkari, ABD merkez bankasının faiz "
        "oranlarını kademeli artırması gerektiğini söyledi.",
    ) == ()


def test_turkish_central_bank_without_explicit_country_stays_in_scope() -> None:
    """Yabancı sinyal yoksa 'Merkez Bankası' Türkiye varsayılır."""
    assert "politika_faizi" in topics.classify(
        "Merkez Bankası faiz kararını açıkladı"
    )
