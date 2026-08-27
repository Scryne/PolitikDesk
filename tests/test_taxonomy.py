"""Faz 21 — Kanonik Kategori ve Bölge Taksonomisi Testleri."""

from __future__ import annotations

from politikdesk.analysis.taxonomy import (
    CATEGORIES,
    CATEGORY_MAP,
    REGION_MAP,
    REGIONS,
    classify_category,
    classify_region,
)


def test_taxonomy_constants_are_canonical_and_complete() -> None:
    """Kategori ve bölge listelerinin eksiksiz ve tekil olduğunu doğrular."""
    cat_keys = [k for k, _ in CATEGORIES]
    reg_keys = [k for k, _ in REGIONS]

    assert len(cat_keys) == len(set(cat_keys)), "Kategori anahtarları tekil olmalı"
    assert len(reg_keys) == len(set(reg_keys)), "Bölge anahtarları tekil olmalı"

    assert "ekonomi" in CATEGORY_MAP
    assert "politika" in CATEGORY_MAP
    assert "dis_politika" in CATEGORY_MAP
    assert "guvenlik" in CATEGORY_MAP
    assert "hukuk" in CATEGORY_MAP

    assert "turkiye" in REGION_MAP
    assert "abd" in REGION_MAP
    assert "avrupa" in REGION_MAP
    assert "orta_dogu" in REGION_MAP
    assert "rusya_ukrayna" in REGION_MAP


def test_classify_category_by_topic_tags() -> None:
    """Konu etiketlerinden deterministik kategori çıkarımı."""
    assert classify_category("Rastgele Başlık", topic_tags=["enflasyon"]) == "ekonomi"
    assert classify_category("Rastgele Başlık", topic_tags=["politika_faizi"]) == "ekonomi"
    assert classify_category("Rastgele Başlık", topic_tags=["kanun_teklifi"]) == "politika"
    assert classify_category("Rastgele Başlık", topic_tags=["denetim_ve_yolsuzluk"]) == "hukuk"


def test_classify_category_by_keywords() -> None:
    """Başlık ve özet metninden kategori tespiti."""
    assert (
        classify_category("Merkez Bankası politika faizini yüzde 50 seviyesinde sabit tuttu")
        == "ekonomi"
    )
    assert (
        classify_category("TBMM Genel Kurulu'nda yeni anayasa ve seçim kanunu görüşüldü")
        == "politika"
    )
    assert (
        classify_category("Dışişleri Bakanı Fidan, NATO Dışişleri Bakanları Zirvesi'ne katıldı")
        == "dis_politika"
    )
    assert (
        classify_category("Milli Savunma Bakanlığı ve TSK'dan sınır ötesi harekat açıklaması")
        == "guvenlik"
    )
    assert classify_category("Anayasa Mahkemesi ve Danıştay'dan kritik iptal kararı") == "hukuk"
    assert (
        classify_category("BOTAŞ ve Karadeniz gazı için yeni sondaj boru hattı anlaşması")
        == "enerji"
    )
    assert (
        classify_category("TÜBİTAK ve TUSAŞ yerli çip ve yapay zeka yazılımını tanıttı")
        == "teknoloji"
    )
    assert (
        classify_category("Sağlık Bakanlığı ve TTB'den yeni hastane ve hekim düzenlemesi")
        == "saglik_toplum"
    )
    assert (
        classify_category("İBB ve ABB büyükşehir belediye meclisinde metro bütçesi onaylandı")
        == "yerel"
    )


def test_classify_region_by_keywords_and_entities() -> None:
    """Metin ve varlıklardan bölge tespiti."""
    assert classify_region("TCMB ve Hazine Ankara'da toplandı") == "turkiye"
    assert classify_region("Fed faiz kararını açıkladı, Beyaz Saray'dan açıklama geldi") == "abd"
    assert classify_region("Avrupa Birliği ve ECB enflasyon tahminini revize etti") == "avrupa"
    assert (
        classify_region("İsrail ve Gazze ateşkes müzakereleri Kahire ve Doha'da sürüyor")
        == "orta_dogu"
    )
    assert (
        classify_region("Rusya ve Ukrayna cephesinde son durum: Moskova ve Kiev hattı")
        == "rusya_ukrayna"
    )
    assert (
        classify_region("Çin Merkez Bankası ve Japonya BOJ piyasalara müdahale etti")
        == "asya_pasifik"
    )


def test_classify_default_fallback() -> None:
    """Eşleşme bulunamayan genel durumlarda dikey varsayılanı atanır."""
    assert classify_category("Genel Belirsiz Başlık", vertical="macro_economy") == "ekonomi"
    assert classify_category("Genel Belirsiz Başlık", vertical="legislation") == "politika"
    assert classify_region("Genel Belirsiz Başlık") == "turkiye"
