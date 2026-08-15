"""B-46 Konu Filtresi İzolasyon ve Kapsam Doğrulama Testleri (AŞAMA 9 · Madde 12).

B-46: Konu filtresinin (topics.py) yanlış-negatif (false-negative) ve
yanlış-pozitif (false-positive) oranlarının ölçülmesi; Türkiye makro ekonomi
bağlamı, yabancı haber izolasyonu ve olay-dışı (fiyat/servis) içeriklerin elenmesi.
"""

from __future__ import annotations

import pytest

from politikdesk.ingestion.topics import (
    classify,
    has_turkey_context,
    in_scope,
    is_non_event,
)


# ===========================================================================
# 1. Kapsam İçi Makro Ekonomi Haberleri (Recall Testi / 0 Yanlış Negatif)
# ===========================================================================
@pytest.mark.parametrize(
    ("title", "summary", "expected_topic"),
    [
        (
            "TÜİK Temmuz ayı enflasyon verilerini açıkladı",
            "Tüketici fiyat endeksi yıllık bazda yüzde 28,4 artış kaydetti.",
            "enflasyon",
        ),
        (
            "Merkez Bankası politika faizini yüzde 45 seviyesinde sabit tuttu",
            "PPK toplantısı sonrası yapılan açıklamada dezenflasyon sürecine vurgu yapıldı.",
            "politika_faizi",
        ),
        (
            "TCMB toplam rezervleri 150 milyar doları aştı",
            "Brüt döviz rezervlerinde tarihi zirve kaydedildi.",
            "kur_ve_rezervler",
        ),
        (
            "Hazine ve Maliye Bakanlığı merkezi yönetim bütçe dengesini duyurdu",
            "Temmuz ayında bütçe açığı 95 milyar TL olarak gerçekleşti.",
            "butce_ve_hazine",
        ),
        (
            "İşsizlik oranı mevsim etkisinden arındırılmış olarak yüzde 8,8 oldu",
            "TÜİK işgücü istatistiklerine göre istihdam oranı yükseldi.",
            "issizlik_ve_istihdam",
        ),
        (
            "Türkiye ekonomisi yılın ilk çeyreğinde yüzde 4,2 büyüdü",
            "GSYH verileri beklentilerin üzerinde açıklandı.",
            "buyume",
        ),
        (
            "Hazine ve Maliye Bakanlığı 5 yıl vadeli eurobond ihracına çıktı",
            "Uluslararası piyasalardan 2,5 milyar dolar borçlanma sağlandı.",
            "kamu_borclanmasi",
        ),
        (
            "Kredi derecelendirme kuruluşu Fitch Türkiye'nin kredi notunu yükseltti",
            "Görünüm pozitif olarak teyit edildi.",
            "derecelendirme",
        ),
    ],
)
def test_b46_in_scope_macro_economy_retained(title: str, summary: str, expected_topic: str) -> None:
    """Kapsam içi makro ekonomi olayları elenmemeli ve doğru konuya atanmalıdır."""
    assert has_turkey_context(title, summary)
    assert not is_non_event(title, summary)
    topics = classify(title, summary)
    assert in_scope(title, summary)
    assert expected_topic in topics, f"'{title}' için '{expected_topic}' konusu atanmalıydı, çıkan: {topics}"


# ===========================================================================
# 2. Yabancı / Dış Ekonomi Haberleri (İzolasyon ve Precision Testi)
# ===========================================================================
@pytest.mark.parametrize(
    ("title", "summary"),
    [
        (
            "Almanya'da enflasyon beklentilerin üzerinde yükseldi",
            "Avrupa Merkez Bankası faiz indirimlerini erteleyebilir.",
        ),
        (
            "ABD Federal Rezerv (Fed) faiz kararını açıkladı",
            "Wall Street piyasalarında dalgalanma sürüyor.",
        ),
        (
            "Japonya Merkez Bankası (BOJ) faiz artırımı sinyali verdi",
            "Yen küresel piyasalarda değer kazandı.",
        ),
        (
            "Çin ekonomisinde büyüme hedeflerin altında kaldı",
            "Sanayi üretimi ve gayrimenkul krizi devam ediyor.",
        ),
    ],
)
def test_b46_foreign_macro_news_isolated(title: str, summary: str) -> None:
    """Türkiye bağlamı taşımayan yabancı makro haberler elenmelidir."""
    assert not has_turkey_context(title, summary), f"'{title}' Türkiye bağlamı taşımamalıdır."
    assert not in_scope(title, summary)


# ===========================================================================
# 3. Fiyat Listesi ve Servis Sayfaları (Non-Event Elenmesi)
# ===========================================================================
@pytest.mark.parametrize(
    ("title", "summary"),
    [
        ("Dolar bugün ne kadar oldu? Güncel döviz kurları", "Canlı dolar kuru ve euro fiyatları"),
        ("Gram altın kaç TL oldu? Kapalıçarşı güncel altın fiyatları", "Çeyrek altın alış satış fiyatı"),
        ("Merkez Bankası faiz kararı ne zaman açıklanacak?", "PPK toplantı takvimi ve saat detayları"),
    ],
)
def test_b46_non_event_price_checks_filtered(title: str, summary: str) -> None:
    """Fiyat arama, piyasa servis sayfaları ve takvim soruları olay olmadığı için elenmelidir."""
    assert is_non_event(title, summary), f"'{title}' non-event olarak tespit edilmeliydi."
    assert not in_scope(title, summary)


# ===========================================================================
# 4. Kapsam Dışı Spor ve Magazin Haberleri (Out-of-scope Elenmesi)
# ===========================================================================
@pytest.mark.parametrize(
    ("title", "summary"),
    [
        ("Süper Lig'de derbi heyecanı: Fenerbahçe Beşiktaş maç sonucu", "Karşılaşmada atılan goller"),
        ("Sinemaseverler müjde: Yeni film festivali başlıyor", "Vizyona girecek filmler ve konserler"),
    ],
)
def test_b46_out_of_scope_sports_and_entertainment_filtered(title: str, summary: str) -> None:
    """Spor ve magazin haberleri makro ekonomi kapsamına girmemelidir."""
    topics = classify(title, summary)
    assert len(topics) == 0, f"'{title}' konusu boş olmalıdır, çıkan: {topics}"
    assert not in_scope(title, summary)
