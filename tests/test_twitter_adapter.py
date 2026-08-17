"""Twitter / X Adaptörü, Thread Birleştirme ve Epistemik Güvenlik Testleri (Spec v3.5 §9.4, §12.4)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from politikdesk.evidence.independence import EvidenceArticle
from politikdesk.evidence.rules import Claim, Evidence, compute_status
from politikdesk.ingestion.adapters.twitter import (
    TweetItem,
    TwitterAdapter,
    aggregate_threads,
)


def test_thread_aggregator_merges_connected_tweets() -> None:
    """Aynı yazarın kısa aralıkla attığı zincirleme tweet'ler tek RawItem'da birleşmeli."""
    now = datetime(2026, 8, 16, 10, 0, tzinfo=UTC)

    tweets = [
        TweetItem(
            tweet_id="1001",
            author_handle="ozgur_ozel",
            text="1/ Meclis açılışında yeni anayasa tartışmalarına dair ilk açıklamam:",
            published_at=now,
            url="https://x.com/ozgur_ozel/status/1001",
        ),
        TweetItem(
            tweet_id="1002",
            author_handle="ozgur_ozel",
            text="2/ Mevcut anayasaya uymayanlarla yeni anayasa masasına oturmayız.",
            published_at=datetime(2026, 8, 16, 10, 2, tzinfo=UTC),
            url="https://x.com/ozgur_ozel/status/1002",
            in_reply_to_tweet_id="1001",
        ),
        TweetItem(
            tweet_id="1003",
            author_handle="ozgur_ozel",
            text="3/ Hukuk devleti ve kuvvetler ayrılığı ilkeleri kırmızı çizgimizdir.",
            published_at=datetime(2026, 8, 16, 10, 5, tzinfo=UTC),
            url="https://x.com/ozgur_ozel/status/1003",
            in_reply_to_tweet_id="1002",
        ),
    ]

    items = aggregate_threads(tweets)
    assert len(items) == 1
    item = items[0]

    assert item.source_slug == "x-ozgur_ozel"
    assert item.extra["is_thread"] is True
    assert item.extra["tweet_count"] == 3
    assert "[1/3]" in item.extra["full_text"]
    assert "[3/3]" in item.extra["full_text"]
    assert item.extra["tier"] == 4
    assert item.extra["claim_type_enforced"] == "attribution"


def test_quote_tweet_reference_detection() -> None:
    """Alıntı tweet içeren gönderi referans metaverisiyle yakalanmalı."""
    tweet = TweetItem(
        tweet_id="2001",
        author_handle="mansuryavas06",
        text="Ankara'da su tarifesi iddialarına cevabımızdır: https://x.com/belediye/status/9999",
        published_at=datetime(2026, 8, 16, 12, 0, tzinfo=UTC),
        url="https://x.com/mansuryavas06/status/2001",
        quoted_tweet_url="https://x.com/belediye/status/9999",
    )

    items = aggregate_threads([tweet])
    assert len(items) == 1
    assert items[0].extra["quoted_tweet_urls"] == ["https://x.com/belediye/status/9999"]


def test_twitter_adapter_rsshub_xml_parsing() -> None:
    """RSSHub XML akışı TweetItem nesnelerine dönüştürülmeli."""
    xml_sample = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Twitter - @TBMMresmi</title>
        <link>https://x.com/TBMMresmi</link>
        <item>
          <title>Genel Kurul 14:00'te toplanacak</title>
          <description><![CDATA[TBMM Genel Kurulu bugün saat 14:00'te 9. Yargı Paketi gündemiyle toplanacak.]]></description>
          <link>https://x.com/TBMMresmi/status/1824419200000000000</link>
          <pubDate>Sun, 16 Aug 2026 09:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""

    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = xml_sample
    mock_http.get.return_value = mock_resp

    adapter = TwitterAdapter("x-tbmm", handle="TBMMresmi", http=mock_http)
    items = adapter.fetch()

    assert len(items) == 1
    assert "TBMM Genel Kurulu" in items[0].summary
    assert items[0].extra["author_handle"] == "TBMMresmi"


def test_r7_rule_enforcement_on_social_claims() -> None:
    """R7 Kuralı: Sosyal medya (Tier 4) kanıtı olan iddia ASLA 🟢/🟡 olamaz; azami 🟠 (single_source) olur."""
    claim = Claim(
        claim_id=501,
        claim_text="Lider X yeni ittifak kuracağını açıkladı",
        claim_type="attribution",
    )

    social_article_1 = EvidenceArticle(
        article_id=1,
        source_slug="x-liderx",
        tier=4,
        kind="social",
        independence_group="social-liderx",
    )
    social_article_2 = EvidenceArticle(
        article_id=2,
        source_slug="x-haberci",
        tier=4,
        kind="social",
        independence_group="social-haberci",
    )

    evidence_list = [
        Evidence(article=social_article_1, stance="supports"),
        Evidence(article=social_article_2, stance="supports"),
    ]

    result = compute_status(claim, evidence_list)

    # İki farklı hesap desteklese bile R7 tavanı single_source'a indirir
    assert result.status == "single_source"
    assert result.rule == "R7"
    assert result.reason.get("ceiling_reason") == "all_evidence_is_tier_4_social"


def test_fifty_distinct_social_accounts_cannot_exceed_single_source() -> None:
    """Negatif Adversarial Test: 50 bağımsız X hesabı paylaşsa dahi R7 tavanı aşılamaz (🟠)."""
    claim = Claim(
        claim_id=601,
        claim_text="Seçim barajının yüzde 3'e düşürüleceği iddia edildi",
        claim_type="attribution",
    )

    evidence_list = [
        Evidence(
            article=EvidenceArticle(
                article_id=i,
                source_slug=f"x-hesap-{i}",
                tier=4,
                kind="social",
                independence_group=f"social-grp-{i}",
                text=f"x tweet metni {i}",
            ),
            stance="supports",
        )
        for i in range(1, 51)
    ]

    result = compute_status(claim, evidence_list)

    assert result.status == "single_source"
    assert result.rule == "R7"
    assert result.reason["capped_from"] in ("partially_corroborated", "strongly_corroborated")
    assert result.reason["ceiling_reason"] == "all_evidence_is_tier_4_social"


def test_social_and_independent_media_corroboration() -> None:
    """Sosyal Medya + Bağımsız Medya: 1 Medya (Tier 3) + 1 Sosyal (Tier 4) = 🟡 (partially_corroborated), ASLA 🟢 olamaz."""
    claim = Claim(
        claim_id=701,
        claim_text="Bakanlık bütçe görüşmeleri ertelendi",
        claim_type="fact",
    )

    media_article = EvidenceArticle(
        article_id=1,
        source_slug="t24-politika",
        tier=3,
        kind="media",
        independence_group="media-t24",
    )
    social_article = EvidenceArticle(
        article_id=2,
        source_slug="x-milletvekili",
        tier=4,
        kind="social",
        independence_group="social-milletvekili",
    )

    evidence_list = [
        Evidence(article=media_article, stance="supports"),
        Evidence(article=social_article, stance="supports"),
    ]

    result = compute_status(claim, evidence_list)

    # 1 medya + 1 sosyal: Tier 1 birincil resmi kaynak olmadığı için 🟢 olamaz; 🟡 (R4) olur.
    assert result.status == "partially_corroborated"
    assert result.rule == "R4"


def test_social_cannot_satisfy_strongly_corroborated_threshold() -> None:
    """1 Tier 1 + 2 Tier 4 Sosyal: Sosyal kaynaklar R2 için gereken 3'lü bağımsız teyit sayımına dahil edilemez."""
    claim = Claim(
        claim_id=801,
        claim_text="TBMM Genel Kurulu yeni kanun teklifini onayladı",
        claim_type="fact",
    )

    primary_article = EvidenceArticle(
        article_id=1,
        source_slug="tbmm",
        tier=1,
        kind="official",
        independence_group="official-tbmm",
    )
    social_1 = EvidenceArticle(
        article_id=2,
        source_slug="x-vekil1",
        tier=4,
        kind="social",
        independence_group="social-vekil1",
    )
    social_2 = EvidenceArticle(
        article_id=3,
        source_slug="x-vekil2",
        tier=4,
        kind="social",
        independence_group="social-vekil2",
    )

    evidence_list = [
        Evidence(article=primary_article, stance="supports"),
        Evidence(article=social_1, stance="supports"),
        Evidence(article=social_2, stance="supports"),
    ]

    result = compute_status(claim, evidence_list)

    # 1 Tier 1 + 2 Tier 4: Tier 1 var ama non-social teyit sayısı 1 (< 3).
    # Bu nedenle 🟢 (R2) olamaz; 🟡 (R4) olur.
    assert result.status == "partially_corroborated"
    assert result.rule == "R4"


def test_twitter_adapter_degraded_state_and_recovery() -> None:
    """Adaptörün ardışık başarısızlıkta degraded olması ve başarıda düzelmesi test edilmeli."""
    mock_http = MagicMock()
    # 1. ve 2. çağrıda HTTP 500
    mock_resp_fail = MagicMock()
    mock_resp_fail.status_code = 500
    mock_http.get.return_value = mock_resp_fail

    adapter = TwitterAdapter(
        "x-test", handle="testhashtag", http=mock_http, max_consecutive_failures=3
    )

    # 1. başarısızlık
    adapter.fetch()
    assert adapter._consecutive_failures == 1
    assert adapter.is_degraded is False

    # 2. başarısızlık
    adapter.fetch()
    assert adapter._consecutive_failures == 2
    assert adapter.is_degraded is False

    # 3. başarısızlık -> degraded olmalı
    adapter.fetch()
    assert adapter._consecutive_failures == 3
    assert adapter.is_degraded is True
    failures = adapter.drain_failures()
    assert len(failures) > 0

    # 4. çağrıda başarı sağlansın -> recovery
    xml_sample = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Twitter - @testhashtag</title>
        <link>https://x.com/testhashtag</link>
        <item>
          <title>Test Açıklama</title>
          <description>Kurtarma testi başarılı</description>
          <link>https://x.com/testhashtag/status/9999</link>
          <pubDate>Sun, 16 Aug 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""
    mock_resp_ok = MagicMock()
    mock_resp_ok.status_code = 200
    mock_resp_ok.text = xml_sample
    mock_http.get.return_value = mock_resp_ok

    items = adapter.fetch()
    assert len(items) == 1
    assert adapter._consecutive_failures == 0
    assert adapter.is_degraded is False


def test_adversarial_impersonation_account_retains_tier_4_ceiling() -> None:
    """Resmî kurumu taklit eden (sahte onaylı) bir X hesabı Tier 4 tavanını kıramaz."""
    impersonator_article = EvidenceArticle(
        article_id=999,
        source_slug="x-fake-tbmm",
        tier=4,
        kind="social",
        independence_group="social-fake-tbmm",
    )
    impersonator_article_2 = EvidenceArticle(
        article_id=1000,
        source_slug="x-fake-sayistay",
        tier=4,
        kind="social",
        independence_group="social-fake-sayistay",
    )

    claim = Claim(
        claim_id=850,
        claim_text="Yeni anayasa referandumu tarihi kesinleşti",
        claim_type="fact",
    )

    # 1. Senaryo: Tek sahte hesap -> R5 (tek kaynak)
    res1 = compute_status(claim, [Evidence(article=impersonator_article, stance="supports")])
    assert res1.status == "single_source"
    assert res1.rule == "R5"

    # 2. Senaryo: 2 farklı sahte hesap -> R7 (Tier 4 sosyal medya tavanı)
    res2 = compute_status(
        claim,
        [
            Evidence(article=impersonator_article, stance="supports"),
            Evidence(article=impersonator_article_2, stance="supports"),
        ],
    )
    assert res2.status == "single_source"
    assert res2.rule == "R7"
    assert res2.reason.get("ceiling_reason") == "all_evidence_is_tier_4_social"


def test_adversarial_thread_contradictory_claims_distinction() -> None:
    """Aynı thread içinde aktörün çelişkili vaat/beyan vermesi durumunda tekilleştirme yapılamaz."""
    from politikdesk.ingestion.adapters.twitter import TweetItem, aggregate_threads

    t1 = TweetItem(
        tweet_id="1001",
        author_handle="siyasi_lider",
        text="Seçimi kazandığımızda emekli maaşlarına %100 seyyanen zam yapacağız.",
        published_at=datetime.now(UTC),
        url="https://x.com/siyasi_lider/status/1001",
    )
    t2 = TweetItem(
        tweet_id="1002",
        author_handle="siyasi_lider",
        text="Mevcut bütçe kısıtları nedeniyle seyyanen zam yapılması mümkün değildir.",
        published_at=datetime.now(UTC),
        url="https://x.com/siyasi_lider/status/1002",
    )

    aggregated = aggregate_threads([t1, t2])
    assert len(aggregated) == 2
    # İki ayrı ham metin korunur, böylece NLP iddia çıkarımında iki ayrı atomik iddia olarak işlenir
    assert "zam yapacağız" in str(aggregated[0].summary or aggregated[0].title)
    assert "mümkün değildir" in str(aggregated[1].summary or aggregated[1].title)


def test_twitter_adapter_oembed_fallback_success() -> None:
    """Bridge çöktüğünde ikincil oEmbed uç noktası devreye girmeli ve tweet'leri başarıyla çekmeli."""
    mock_http = MagicMock()

    # Bridge çağrısı HTTP 502 dönsün
    resp_bridge_fail = MagicMock()
    resp_bridge_fail.status_code = 502
    resp_bridge_fail.text = "Bad Gateway"

    # oEmbed çağrısı geçerli JSON dönsün
    resp_oembed_ok = MagicMock()
    resp_oembed_ok.status_code = 200
    resp_oembed_ok.json.return_value = {
        "url": "https://x.com/iletisim",
        "author_name": "İletişim Başkanlığı",
        "html": (
            '<blockquote class="twitter-tweet"><p lang="tr" dir="ltr">'
            "Cumhurbaşkanlığı İletişim Başkanlığı haftalık dezenformasyon bülteni yayımlandı."
            '</p>&mdash; İletişim Başkanlığı (@iletisim) <a href="https://x.com/iletisim/status/1890000000000000000">'
            "August 16, 2026</a></blockquote>"
        ),
    }

    def mock_get(url: str, **kwargs: object) -> MagicMock:
        if "publish.twitter.com/oembed" in url:
            return resp_oembed_ok
        return resp_bridge_fail

    mock_http.get.side_effect = mock_get

    adapter = TwitterAdapter("x-iletisim", handle="iletisim", http=mock_http)
    items = adapter.fetch()

    assert len(items) == 1
    assert "dezenformasyon bülteni" in items[0].summary
    assert items[0].url == "https://x.com/iletisim/status/1890000000000000000"
    assert adapter.is_degraded is False
    assert adapter._consecutive_failures == 0


def test_twitter_adapter_both_bridge_and_oembed_fail() -> None:
    """Hem bridge hem oEmbed çöktüğünde kaynak başarısızlığı ve hata defteri doğru güncellenmeli."""
    mock_http = MagicMock()
    resp_fail = MagicMock()
    resp_fail.status_code = 503
    resp_fail.text = "Service Unavailable"
    mock_http.get.return_value = resp_fail

    adapter = TwitterAdapter("x-test", handle="testaccount", http=mock_http, max_consecutive_failures=2)
    items = adapter.fetch()

    assert len(items) == 0
    assert adapter._consecutive_failures == 1
    assert adapter.is_degraded is False

    # 2. başarısızlık -> degraded
    items2 = adapter.fetch()
    assert len(items2) == 0
    assert adapter._consecutive_failures == 2
    assert adapter.is_degraded is True
    failures = adapter.drain_failures()
    assert any("hiçbir kademeden veri alınamadı" in f for f in failures)


def test_twitter_adapter_list_xml_parsing_with_multiple_authors() -> None:
    """Twitter Listesi akışından farklı yazarların tweet'leri doğru yazar ve slug ile ayrıştırılmalı."""
    xml_list_sample = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Twitter List - 1473396544820948992</title>
        <link>https://x.com/i/lists/1473396544820948992</link>
        <item>
          <title>Gazeteci A: Meclis kulislerinde yeni vergi paketi konuşuluyor</title>
          <description><![CDATA[Meclis kulislerinde yeni vergi paketi konuşuluyor. Torba teklif yarın komisyonda.]]></description>
          <link>https://x.com/gazeteci_a/status/1824419200000000001</link>
          <pubDate>Sun, 16 Aug 2026 09:00:00 GMT</pubDate>
        </item>
        <item>
          <title>Gazeteci B: 1/ Anayasa Mahkemesi'nin son kararı gerekçesi açıklandı</title>
          <description><![CDATA[1/ Anayasa Mahkemesi'nin son kararı gerekçesi açıklandı.]]></description>
          <link>https://x.com/gazeteci_b/status/1824419200000000002</link>
          <pubDate>Sun, 16 Aug 2026 09:05:00 GMT</pubDate>
        </item>
        <item>
          <title>Gazeteci B: 2/ Kararda mülkiyet hakkı vurgusu öne çıkıyor</title>
          <description><![CDATA[2/ Kararda mülkiyet hakkı vurgusu öne çıkıyor.]]></description>
          <link>https://x.com/gazeteci_b/status/1824419200000000003</link>
          <pubDate>Sun, 16 Aug 2026 09:07:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""

    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = xml_list_sample
    mock_http.get.return_value = mock_resp

    adapter = TwitterAdapter(
        slug="x-list-1473396544820948992",
        list_id="1473396544820948992",
        http=mock_http,
    )
    items = adapter.fetch()

    # 3 tweet var, Gazeteci B'nin 2 tweet'i flood olarak birleştiğinden 2 RawItem dönmeli
    assert len(items) == 2

    # 1. Gazeteci A
    assert items[0].source_slug == "x-list-1473396544820948992"
    assert items[0].extra["author_handle"] == "gazeteci_a"
    assert "Meclis kulislerinde yeni vergi paketi" in items[0].summary

    # 2. Gazeteci B (Flood / Thread birleşimi)
    assert items[1].source_slug == "x-list-1473396544820948992"
    assert items[1].extra["author_handle"] == "gazeteci_b"
    assert items[1].extra["is_thread"] is True
    assert items[1].extra["tweet_count"] == 2
    assert "[1/2]" in items[1].extra["full_text"]
    assert "[2/2]" in items[1].extra["full_text"]


def test_twitter_list_sources_config_validation() -> None:
    """Eklenen 6 adet X listesi sources_social.yml içinde eksiksiz ve geçerli olmalı."""
    from politikdesk.ingestion.sources import load_all_configs

    all_cfgs = load_all_configs()
    slugs = {c.slug for c in all_cfgs}

    expected_lists = {
        "x-list-1473396544820948992",
        "x-list-1494242247231033347",
        "x-list-1326818255273680896",
        "x-list-1481019746921467908",
        "x-list-1480924470277812233",
        "x-list-1465344996131971087",
        "x-list-1641042698202226688",
        "x-list-1856602506538717451",
        "x-list-1635155394849914880",
    }


    for el in expected_lists:
        assert el in slugs, f"{el} sources konfigürasyonunda bulunamadı!"


def test_twitter_adapter_reads_bridge_url_from_env(monkeypatch) -> None:  # noqa: ANN001
    """TwitterAdapter, PD_TWITTER_BRIDGE_URL ortam değişkenini okumalı."""
    monkeypatch.setenv("PD_TWITTER_BRIDGE_URL", "http://my-custom-bridge:9999")
    adapter = TwitterAdapter(slug="x-test", handle="testuser")
    assert adapter.bridge_url == "http://my-custom-bridge:9999"


def test_pipeline_skips_twitter_when_feature_flag_disabled(monkeypatch) -> None:  # noqa: ANN001
    """PD_TWITTER_INGESTION_ENABLED=false iken Pipeline Twitter kaynağını hatasız atlamalı."""
    from politikdesk.ingestion.pipeline import Pipeline
    from politikdesk.ingestion.repository import SourceRow

    monkeypatch.setenv("PD_TWITTER_INGESTION_ENABLED", "false")

    pipeline = Pipeline()
    source = SourceRow(
        id=1,
        slug="x-testuser",
        name="Test Twitter",
        tier=4,
        kind="social",
        independence_group="social-test",
        access_method="social",
        tos_status="allowed",
        adapter="twitter",
        base_url="https://x.com/testuser",
        feed_url=None,
        extra_feeds=[],
        keyword_filter=[],
        topics=["meclis_gundemi"],
        is_active=True,
        is_wire_reference=False,
    )

    stats = pipeline.run_source(source)
    assert stats.fetched == 0
    assert stats.errors == 0


def test_thread_aggregator_does_not_merge_unrelated_replies() -> None:
    """DEF-01 Regresyon Testi: Başka tweetlere/kullanıcılara atılan yanıtlar zincire dahil edilmemelidir."""
    t1 = TweetItem(
        tweet_id="101",
        author_handle="siyasetci",
        text="Önemli bir açıklama yapıyorum:",
        published_at=datetime(2026, 8, 16, 10, 0, tzinfo=UTC),
        url="https://x.com/siyasetci/status/101",
    )
    # Thread içi devam tweeti (101'e yanıt)
    t2 = TweetItem(
        tweet_id="102",
        author_handle="siyasetci",
        text="Açıklamamın ikinci maddesi budur.",
        published_at=datetime(2026, 8, 16, 10, 2, tzinfo=UTC),
        url="https://x.com/siyasetci/status/102",
        in_reply_to_tweet_id="101",
    )
    # Aynı yazarın 10 dakika sonra bambaşka bir kullanıcıya verdiği yanıt
    t3_unrelated = TweetItem(
        tweet_id="103",
        author_handle="siyasetci",
        text="Tebrik ederim, başarılar dilerim.",
        published_at=datetime(2026, 8, 16, 10, 10, tzinfo=UTC),
        url="https://x.com/siyasetci/status/103",
        in_reply_to_tweet_id="999999",  # Harici bir tweet'e yanıt
    )
    # Başka bağımsız numaralandırılmış flood
    t4_flood1 = TweetItem(
        tweet_id="104",
        author_handle="siyasetci",
        text="1/ Yeni bir konuya geçiyoruz.",
        published_at=datetime(2026, 8, 16, 11, 0, tzinfo=UTC),
        url="https://x.com/siyasetci/status/104",
    )
    t5_flood2 = TweetItem(
        tweet_id="105",
        author_handle="siyasetci",
        text="2/ Yeni konunun ikinci kısmı.",
        published_at=datetime(2026, 8, 16, 11, 2, tzinfo=UTC),
        url="https://x.com/siyasetci/status/105",
    )

    items = aggregate_threads([t1, t2, t3_unrelated, t4_flood1, t5_flood2])

    assert len(items) == 3, f"Beklenen 3 ayrı grup (flood1, harici yanıt, flood2), fakat {len(items)} geldi"
    # Grup 1: t1 + t2
    assert items[0].extra["is_thread"] is True
    assert items[0].extra["tweet_count"] == 2
    # Grup 2: t3_unrelated (tekil)
    assert items[1].extra["is_thread"] is False
    assert items[1].extra["tweet_count"] == 1
    assert "Tebrik ederim" in items[1].summary
    # Grup 3: t4 + t5
    assert items[2].extra["is_thread"] is True
    assert items[2].extra["tweet_count"] == 2



