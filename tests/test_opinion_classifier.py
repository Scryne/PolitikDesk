"""Haber/Yorum ayrımı sınıflandırıcısı testleri (B-97 · Spec v3.4 §5)."""

from __future__ import annotations

from politikdesk.nlp.opinion_classifier import classify_content_kind


def test_classify_news_article() -> None:
    """Olgusal haber metni 'news' olarak sınıflandırılmalı."""
    res = classify_content_kind(
        title="TÜİK Temmuz Ayı Enflasyon Rakamlarını Açıkladı",
        text="Türkiye İstatistik Kurumu verilerine göre TÜFE aylık yüzde 1,78 arttı.",
    )
    assert not res.is_opinion
    assert res.content_kind == "news"


def test_classify_opinion_column_by_category() -> None:
    """Kategori/bölüm köşe yazısı olan metin 'opinion_column' olmalı."""
    res = classify_content_kind(
        title="Mecliste Bütçe Pazarlıkları Kızışıyor",
        text="Görüşmeler dün başladı.",
        section="Köşe Yazarları",
    )
    assert res.is_opinion
    assert res.content_kind == "opinion_column"


def test_classify_opinion_by_author_and_first_person() -> None:
    """Yazar ve birinci şahıs dili içeren metin köşe yazısı sayılmalı."""
    res = classify_content_kind(
        title="Ankara'da Son Durum",
        text="Bence bu kararın ekonomik sonuçları ağır olacak, köşemde bunu anlatıyorum.",
        author="Ahmet Yılmaz",
    )
    assert res.is_opinion
    assert res.content_kind == "opinion_column"


def test_classify_opinion_keywords_folding() -> None:
    """L5: Türkçe karakterli tüm anahtar kelimeler fold edilerek doğru eşleşmeli."""
    # 1. Başlık ipuçları
    title_samples = [
        "Günün Köşe Yazısı: Meclis Gündemi",
        "Köşe Yazarları Bugün Ne Yazdı?",
        "Günün Yazısı: Yeni Vergi Paketi",
        "Başyazı: Demokrasi ve Hukuk",
        "Başkent Kulisi: Kabine Değişikliği",
        "Ekonomide Son Gözlem ve Değerlendirmeler",
    ]
    for sample in title_samples:
        res = classify_content_kind(title=sample)
        assert res.is_opinion, f"Başlık eşleşmedi: {sample}"
        assert res.content_kind == "opinion_column"

    # 2. Bölüm / kategori ipuçları
    section_samples = [
        "Köşe Yazısı",
        "Köşe Yazarları",
        "Günün Yazısı",
        "Başyazı",
        "Başkent Kulisi",
        "Gözlem",
        "Değerlendirme",
    ]
    for s in section_samples:
        res = classify_content_kind(title="Rapor Özeti", section=s)
        assert res.is_opinion, f"Kategori eşleşmedi: {s}"
        assert res.content_kind == "opinion_column"

    # 3. Yazar + birinci tekil şahıs belirteçleri
    first_person_samples = [
        "Bana göre bu adım geç atıldı.",
        "Benim gördüğüm kadarıyla tablo farklı.",
        "Şahsen bu iddiayı doğru bulmuyorum.",
        "Köşemde daha önce de belirttim.",
        "Bu kararın olumlu olacağını düşünüyorum.",
    ]
    for text in first_person_samples:
        res = classify_content_kind(
            title="Genel Bakış",
            text=text,
            author="Mehmet Demir",
        )
        assert res.is_opinion, f"Birinci tekil şahıs eşleşmedi: {text}"
        assert res.content_kind == "opinion_column"
