"""Faz 22: Taksonomi Motoru Adversarial ve Türkçe Karakter / Varlık Stres Testleri."""

from __future__ import annotations

import pytest

from politikdesk.analysis.taxonomy import (
    CATEGORIES,
    REGIONS,
    classify_category,
    classify_region,
)


@pytest.mark.parametrize(
    ("title", "excerpt", "vertical", "expected_cat"),
    [
        (
            "TCMB Faizi Sabit Bıraktı",
            "Enflasyonla mücadele devam edecek",
            "macro_economy",
            "ekonomi",
        ),
        (
            "EKONOMİDE YENİ DÖNEM: İHRACAT VE CARİ AÇIK",
            "İSTANBUL TİCARET ODASI AÇIKLADI",
            "macro_economy",
            "ekonomi",
        ),
        (
            "TBMM Genel Kurulu Seçim Kararını Onayladı",
            "Milletvekilleri genel kurulda toplandı",
            "politics",
            "politika",
        ),
        (
            "ANAYASA MAHKEMESİ İPTAL KARARI VERDİ",
            "Yüksek mahkeme hak ihlali tespit etti",
            "law",
            "hukuk",
        ),
        (
            "Dışişleri Bakanlığı'ndan Brüksel Çıkarması",
            "AB ile vize serbestisi ve diplomasi görüşmeleri",
            "diplomacy",
            "dis_politika",
        ),
        (
            "MSB: Terör Hedefleri İmha Edildi",
            "Suriye sınırında hava harekatı ve güvenlik operasyonu",
            "security",
            "guvenlik",
        ),
        (
            "BOTAŞ Doğalgaz Depolama Kapasitesini Artırıyor",
            "Silivri ve Tuz Gölü tesislerinde enerji yatırımı",
            "energy",
            "enerji",
        ),
        (
            "ASELSAN Yapay Zeka Destekli Radar Geliştirdi",
            "Savunma sanayiinde ileri teknoloji ve çip hamlesi",
            "technology",
            "teknoloji",
        ),
        (
            "Sağlık Bakanlığı Şehir Hastaneleri Kapasite Raporu",
            "Toplum sağlığı ve aşı takvimi açıklandı",
            "health",
            "saglik_toplum",
        ),
        (
            "İstanbul Büyükşehir Belediyesi Metro Projesi",
            "Kadıköy ve Beşiktaş hatlarında yerel yönetim çalışmaları",
            "local",
            "yerel",
        ),
        ("Kültür Festivali Açılış Töreni", "Etkinlikler başladı", "other", "diger"),
    ],
)
def test_taxonomy_category_classification_cases(
    title: str, excerpt: str, vertical: str, expected_cat: str
) -> None:
    """Türkçe karakterler, büyük/küçük harf ve anahtar kelimelerle kategori tespiti."""
    cat = classify_category(title, excerpt, vertical=vertical)
    assert cat == expected_cat, f"Başlık: '{title}' -> Beklenen: {expected_cat}, Üretilen: {cat}"


@pytest.mark.parametrize(
    ("title", "excerpt", "entities", "expected_reg"),
    [
        (
            "Ankara'da Bakanlar Kurulu Toplandı",
            "Türkiye genelinde kararlar alındı",
            ["Ankara", "TBMM"],
            "turkiye",
        ),
        (
            "İZMİR VE İSTANBUL'DA YENİ YATIRIM",
            "TÜRKİYE EKONOMİSİNE KATKI",
            ["İzmir", "İstanbul"],
            "turkiye",
        ),
        (
            "Beyaz Saray'dan Faiz ve Dolar Açıklaması",
            "Washington yönetimi ve Fed kararı",
            ["Beyaz Saray", "Fed"],
            "abd",
        ),
        (
            "Avrupa Parlamentosu Yeni İklim Yasasını Onayladı",
            "Brüksel ve Almanya mutabık kaldı",
            ["Avrupa Birliği", "Brüksel"],
            "avrupa",
        ),
        (
            "Orta Doğu'da Ateşkes Müzakereleri",
            "Katar ve Mısır arabuluculuğunda Gazze ve İsrail görüşmesi",
            ["Gazze", "Katar"],
            "orta_dogu",
        ),
        (
            "Moskova ve Kiev Hattında Çatışmalar Sürüyor",
            "Ukrayna ordusu Donbas cephesinde savunmada",
            ["Moskova", "Kiev"],
            "rusya_ukrayna",
        ),
        (
            "Pekin ve Tokyo Arasında Deniz Yetki Alanı Gerilimi",
            "Çin ve Japonya diplomasisi",
            ["Pekin", "Tokyo"],
            "asya_pasifik",
        ),
        (
            "BM Genel Kurulu Küresel İklim Zirvesi",
            "Tüm dünya ülkeleri New York'ta toplandı",
            ["BM", "Birleşmiş Milletler"],
            "kuresel",
        ),
    ],
)
def test_taxonomy_region_classification_cases(
    title: str, excerpt: str, entities: list[str], expected_reg: str
) -> None:
    """Bölge ve uluslararası aktör/şehir eşleştirmeleriyle bölge tespiti."""
    reg = classify_region(title, excerpt, entities=entities)
    assert reg == expected_reg, f"Başlık: '{title}' -> Beklenen: {expected_reg}, Üretilen: {reg}"


def test_taxonomy_completeness_and_immutability() -> None:
    """Taksonominin 10 kategori ve 7 bölgeyi eksiksiz ve değişmez sunduğunu doğrular."""
    assert len(CATEGORIES) == 11  # all + 10 kategoriler
    assert len(REGIONS) == 8  # all + 7 bölgeler

    cat_keys = {c[0] for c in CATEGORIES}
    reg_keys = {r[0] for r in REGIONS}

    assert "ekonomi" in cat_keys
    assert "politika" in cat_keys
    assert "dis_politika" in cat_keys
    assert "guvenlik" in cat_keys
    assert "hukuk" in cat_keys
    assert "enerji" in cat_keys
    assert "teknoloji" in cat_keys
    assert "saglik_toplum" in cat_keys
    assert "yerel" in cat_keys
    assert "diger" in cat_keys

    assert "turkiye" in reg_keys
    assert "abd" in reg_keys
    assert "avrupa" in reg_keys
    assert "orta_dogu" in reg_keys
    assert "rusya_ukrayna" in reg_keys
    assert "asya_pasifik" in reg_keys
    assert "kuresel" in reg_keys
