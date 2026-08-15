from __future__ import annotations

from politikdesk.ingestion import topics
from politikdesk.verticals import get_vertical, list_verticals
from politikdesk.verticals.legislation import LEGISLATION_VERTICAL
from politikdesk.verticals.macro_economy import MACRO_ECONOMY_VERTICAL


def test_vertical_registry() -> None:
    """Kayıtlı tüm dikeyler sorgulanabilir olmalı."""
    verts = list_verticals()
    slugs = {v.slug for v in verts}
    assert "macro_economy" in slugs
    assert "legislation" in slugs

    macro = get_vertical("macro_economy")
    assert macro.slug == MACRO_ECONOMY_VERTICAL.slug
    assert macro.name == "Makro Ekonomi"

    leg = get_vertical("legislation")
    assert leg.slug == LEGISLATION_VERTICAL.slug
    assert leg.name == "Yasama ve TBMM"


def test_legislation_topic_classification() -> None:
    """Yasama dikeyinde konu sınıflandırması doğru çalışmalı."""
    # Kanun teklifi / yasama süreci
    res = topics.classify("TBMM Genel Kurulu'nda yeni vergi kanun teklifi kabul edildi", vertical="legislation")
    assert "yasama_sureci" in res

    # Atama ve kadro
    res = topics.classify("Resmî Gazete'de yayımlandı: Bakan Yardımcısı atama kararı", vertical="legislation")
    assert "atama_ve_kadro" in res

    # Sayıştay ve yolsuzluk / denetim
    res = topics.classify("Sayıştay denetim raporu: Bakanlıkta kamu zararı tespiti", vertical="legislation")
    assert "denetim_ve_yolsuzluk" in res

    # Anayasa Mahkemesi ve yargı
    res = topics.classify("Anayasa Mahkemesi'nden yeni hak ihlali kararı", vertical="legislation")
    assert "yargi_ve_hukuk" in res


def test_legislation_non_event_filtering_is_not_vacuous() -> None:
    """L2: Konu eşleşmesi olan ancak non-event kalıbı içeren başlıklar filtrelenmeli."""
    # 1. Günün köşe yazıları: TBMM'de torba kanun
    # topic eşleşmesi var: "yasama_sureci"
    matched = topics.match_topics("Günün köşe yazıları: TBMM'de torba kanun", vertical="legislation")
    assert "yasama_sureci" in matched
    assert topics.is_non_event("Günün köşe yazıları: TBMM'de torba kanun", vertical="legislation") is True
    assert topics.classify("Günün köşe yazıları: TBMM'de torba kanun", vertical="legislation") == ()

    # 2. Son anket: Seçim kanunu değişikliğine destek
    # topic eşleşmesi var: "secim_ve_ysk"
    matched_anket = topics.match_topics("Son anket: Seçim kanunu değişikliğine destek", vertical="legislation")
    assert "secim_ve_ysk" in matched_anket
    assert topics.is_non_event("Son anket: Seçim kanunu değişikliğine destek", vertical="legislation") is True
    assert topics.classify("Son anket: Seçim kanunu değişikliğine destek", vertical="legislation") == ()

    # 3. Burç yorumları: Meclis gündemi ne diyor
    # topic eşleşmesi var: "yasama_sureci"
    matched_burc = topics.match_topics("Burç yorumları: Meclis gündemi ne diyor", vertical="legislation")
    assert "yasama_sureci" in matched_burc
    assert topics.is_non_event("Burç yorumları: Meclis gündemi ne diyor", vertical="legislation") is True
    assert topics.classify("Burç yorumları: Meclis gündemi ne diyor", vertical="legislation") == ()


def test_legislation_positive_recall() -> None:
    """L2: Gerçek yasama olayları non-event filtresine takılmadan geçmeli."""
    res1 = topics.classify("TBMM'de yeni kanun teklifi kabul edildi", vertical="legislation")
    assert "yasama_sureci" in res1

    res2 = topics.classify("Meclis'te torba kanun görüşmeleri başladı", vertical="legislation")
    assert "yasama_sureci" in res2


def test_legislation_context_filtering() -> None:
    """L2: Gerekli Türkiye / dikey bağlamı yoksa elenmeli, varsa geçmeli."""
    # Bağlam sinyali olmayan yabancı haber
    assert topics.has_turkey_context("Fransa'da yeni yasa teklifi ve genel kurul tutanakları", vertical="legislation") is False
    assert topics.classify("Fransa'da yeni yasa teklifi ve genel kurul tutanakları", vertical="legislation") == ()

    # TBMM bağlamı olan haber
    assert topics.has_turkey_context("TBMM'de yeni yasa teklifi ve genel kurul tutanakları", vertical="legislation") is True
    res = topics.classify("TBMM'de yeni yasa teklifi ve genel kurul tutanakları", vertical="legislation")
    assert "yasama_sureci" in res


def test_macro_economy_backward_compatibility() -> None:
    """Eski topics.classify çağrıları varsayılan olarak makro ekonomiye düşmeli."""
    res = topics.classify("TÜİK temmuz ayı TÜFE enflasyon verisini açıkladı")
    assert "enflasyon" in res

    # Almanya haberi makro ekonomide elenir
    assert topics.classify("Almanya'da enflasyon yükseldi") == ()
