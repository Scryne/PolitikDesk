"""Corroboration Inflation & Multi-Source Independence Regression Tests (Spec §8.2, Faz B).

Ensures that:
  - Scenario A: Wire agency copy published across multiple outlets maps to 1 wire origin.
  - Scenario B: Outlets belonging to the same media group map to 1 group origin.
  - Scenario C: Multi-channel output from the same institution maps to 1 institutional origin.
  - Scenario D: Genuinely independent sources increment the independent corroboration count.
"""

from __future__ import annotations

from politikdesk.ingestion.dedup import compute_simhash
from politikdesk.ingestion.independence import (
    ArticleFingerprint,
    count_independent,
    group_by_independence,
)


def test_scenario_a_wire_agency_syndication_no_inflation() -> None:
    """Senaryo A: AA haberi 10 farklı sitede yayımlandığında bağımsız teyit sayısı 1 kalmalıdır."""
    aa_text = (
        "Türkiye Cumhuriyet Merkez Bankası Para Politikası Kurulu, Merkez Bankası Başkanı "
        "başkanlığında toplandı. Kurul, politika faizi olan bir hafta vadeli repo ihale faiz "
        "oranının yüzde elli düzeyinde sabit tutulmasına karar vermiştir. Kurul, enflasyonun ana "
        "eğiliminde belirgin ve kalıcı bir düşüş sağlanana kadar sıkı para politikası duruşunun "
        "sürdürüleceğini kararlılıkla ifade etmiştir."
    )
    aa_simhash = compute_simhash(aa_text)

    # 1 AA orijinal makalesi
    aa_article = ArticleFingerprint(
        article_id=1,
        source_slug="aa-ekonomi",
        independence_group="wire-aa",
        kind="wire",
        simhash=aa_simhash,
    )

    # 5 farklı medya kuruluşu AA metnini kopyalayıp yayımlıyor
    syndicated_articles = []
    for idx, slug in enumerate(
        ["dunya", "haberturk", "cnnturk", "sozcu-politika", "sabah-ekonomi"], start=2
    ):
        syndicated_articles.append(
            ArticleFingerprint(
                article_id=idx,
                source_slug=slug,
                independence_group=f"media-{slug}",
                kind="media",
                simhash=aa_simhash,  # Ajans kopyası aynı metin parmak izine sahip
            )
        )

    all_articles = [aa_article] + syndicated_articles

    # Bağımsız sayım hesapla
    ind_count = count_independent(all_articles, max_distance=6)
    groups = group_by_independence(all_articles, max_distance=6)

    # Kopyaların tamamı wire:aa-ekonomi anahtarında birleşmelidir
    assert ind_count == 1, (
        f"Beklenen 1 bağımsız kaynak, hesaplanan {ind_count}. Gruplar: {groups.keys()}"
    )
    assert "wire:aa-ekonomi" in groups
    assert len(groups["wire:aa-ekonomi"]) == 6


def test_scenario_b_same_ownership_group_no_inflation() -> None:
    """Senaryo B: Aynı medya grubuna ait farklı siteler (Demirören) tek bağımsız grup sayılmalıdır."""
    art1 = ArticleFingerprint(
        article_id=101,
        source_slug="cnnturk",
        independence_group="media-demiroren",
        kind="media",
        simhash=compute_simhash("Bakan Şimşek enflasyon mesajı verdi."),
    )
    art2 = ArticleFingerprint(
        article_id=102,
        source_slug="hurriyet",
        independence_group="media-demiroren",
        kind="media",
        simhash=compute_simhash("Bakan Şimşek'ten önemli enflasyon açıklaması."),
    )
    art3 = ArticleFingerprint(
        article_id=103,
        source_slug="milliyet",
        independence_group="media-demiroren",
        kind="media",
        simhash=compute_simhash("Hazine Bakanı Şimşek enflasyon hedeflerini değerlendirdi."),
    )

    articles = [art1, art2, art3]
    ind_count = count_independent(articles)
    groups = group_by_independence(articles)

    assert ind_count == 1, f"Aynı gruptaki 3 yayın {ind_count} bağımsız kaynak sayıldı!"
    assert "grp:media-demiroren" in groups
    assert len(groups["grp:media-demiroren"]) == 3


def test_scenario_c_official_multichannel_same_institution() -> None:
    """Senaryo C: Aynı resmi kurumun RSS'i ve EVDS API'si tek resmi köken sayılmalıdır."""
    rss_art = ArticleFingerprint(
        article_id=201,
        source_slug="tcmb",
        independence_group="official-tcmb",
        kind="official",
        simhash=compute_simhash("Para Politikası Kurulu faiz kararını açıkladı."),
    )
    evds_art = ArticleFingerprint(
        article_id=202,
        source_slug="tcmb-evds",
        independence_group="official-tcmb",
        kind="official",
        simhash=compute_simhash("TCMB Politika Faizi (1 Hafta Repo): %50.00"),
    )

    articles = [rss_art, evds_art]
    ind_count = count_independent(articles)
    groups = group_by_independence(articles)

    assert ind_count == 1, "TCMB RSS ve EVDS API iki ayrı bağımsız kaynak sayıldı!"
    assert "grp:official-tcmb" in groups


def test_scenario_d_genuinely_independent_sources_increase_corroboration() -> None:
    """Senaryo D: Gerçekten bağımsız kaynaklar teyit sayısını artırmalıdır (R2 🟢 teyidi)."""
    tcmb = ArticleFingerprint(
        article_id=301,
        source_slug="tcmb",
        independence_group="official-tcmb",
        kind="official",
        simhash=compute_simhash("PPK kararı: Politika faizi yüzde 50."),
    )
    bbc = ArticleFingerprint(
        article_id=302,
        source_slug="bbc-turkce",
        independence_group="wire-bbc",
        kind="wire",
        simhash=compute_simhash(
            "Türkiye Cumhuriyet Merkez Bankası faizi beklentiler doğrultusunda sabit bıraktı."
        ),
    )
    dw = ArticleFingerprint(
        article_id=303,
        source_slug="dw-ekonomi",
        independence_group="media-dw",
        kind="media",
        simhash=compute_simhash("Merkez Bankası'ndan faiz kararı: Yüzde 50'de sabit tutuldu."),
    )
    sozcu = ArticleFingerprint(
        article_id=304,
        source_slug="sozcu-politika",
        independence_group="media-sozcu",
        kind="media",
        simhash=compute_simhash(
            "Piyasaların beklediği faiz kararı açıklandı: Merkez Bankası pas geçti."
        ),
    )

    articles = [tcmb, bbc, dw, sozcu]
    ind_count = count_independent(articles)
    groups = group_by_independence(articles)

    # 4 ayrı bağımsız grup (official-tcmb, wire:bbc-turkce, grp:media-dw, grp:media-sozcu)
    assert ind_count == 4, (
        f"Beklenen 4 bağımsız kaynak, hesaplanan {ind_count}. Gruplar: {groups.keys()}"
    )
