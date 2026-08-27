"""Deduplication Precision, Recall & False Positive Regression Tests (Spec §7.2, Faz B).

Validates:
  - Binary exact duplicate hash match
  - Charikar SimHash (64-bit, Hamming distance <= 6)
  - 3-Gram containment (>= 0.60)
  - Independence isolation (Same event != Duplicate article)
"""

from __future__ import annotations

import hashlib

from politikdesk.ingestion.dedup import (
    classify,
    compute_simhash,
    containment,
    hamming_distance,
    is_near_duplicate,
    ngram_set,
)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_exact_binary_duplicate_detection() -> None:
    """Birebir aynı metin 'exact' olarak etiketlenmelidir."""
    text = "Hazine ve Maliye Bakanlığı 2026 yılı bütçe gerçekleşmelerini açıkladı."
    chash = _content_hash(text)
    shash = compute_simhash(text)

    existing_hashes = {chash: 10}
    existing_simhashes = [(10, shash)]

    verdict = classify(
        content_hash=chash,
        simhash=shash,
        existing_hashes=existing_hashes,
        existing_simhashes=existing_simhashes,
        text=text,
    )

    assert verdict.kind == "exact"
    assert verdict.matched_article_id == 10
    assert not verdict.should_store


def test_syndicated_near_duplicate_simhash_distance() -> None:
    """Ajans haberinin başlığı/girişi hafifçe değiştirildiğinde near_duplicate tespit edilmelidir."""
    orig_text = (
        "Türkiye Cumhuriyet Merkez Bankası Para Politikası Kurulu politika "
        "faizini yüzde kırk seviyesinde sabit tutma kararı aldı. Karar metninde "
        "enflasyonun ana eğiliminde belirgin bir bozulma görülmediği belirtildi."
    )
    synd_text = (
        "Türkiye Cumhuriyet Merkez Bankası Para Politikası Kurulu politika "
        "faizini yüzde kırk seviyesinde sabit tutma kararı aldı. Karar metninde "
        "enflasyonun ana eğiliminde belirgin bir bozulma görülmediği belirtildi. "
        "Piyasalar kararı bekliyordu."
    )

    shash_orig = compute_simhash(orig_text)
    shash_synd = compute_simhash(synd_text)

    assert is_near_duplicate(shash_orig, shash_synd, text_a=orig_text, text_b=synd_text)

    existing_hashes = {_content_hash(orig_text): 20}
    existing_simhashes = [(20, shash_orig)]
    existing_texts = {20: orig_text}

    verdict = classify(
        content_hash=_content_hash(synd_text),
        simhash=shash_synd,
        existing_hashes=existing_hashes,
        existing_simhashes=existing_simhashes,
        text=synd_text,
        existing_texts=existing_texts,
    )

    assert verdict.kind == "near"
    assert verdict.matched_article_id == 20
    assert verdict.should_store  # Yakın tekrar saklanır ama işaretlenir


def test_same_event_independent_reporting_is_not_collapsed() -> None:
    """Aynı olayı farklı açılardan yazan bağımsız makaleler birbirinin kopyası sayılmamalıdır."""
    article_a = (
        "Cumhurbaşkanı Erdoğan Kabine toplantısı sonrasında yaptığı açıklamada ekonomi programının "
        "kararlılıkla uygulanacağını ve enflasyonda kalıcı düşüşün hedeflendiğini vurguladı."
    )
    article_b = (
        "Muhalefet partileri Kabine toplantısından çıkan kararları eleştirerek halkın alım gücündeki "
        "düşüşün devam ettiğini ve asgari ücretin yeniden düzenlenmesi gerektiğini savundu."
    )

    shash_a = compute_simhash(article_a)
    shash_b = compute_simhash(article_b)
    h_dist = hamming_distance(shash_a, shash_b)

    set_a = ngram_set(article_a)
    set_b = ngram_set(article_b)
    cont = containment(set_a, set_b)

    assert h_dist > 6, (
        f"Farklı editoryal bakış açıları SimHash mesafesinde {h_dist} <= 6 olarak çöktü!"
    )
    assert cont < 0.60, f"Containment {cont} >= 0.60; bağımsız haberler yanlışlıkla birleşti."

    existing_hashes = {_content_hash(article_a): 30}
    existing_simhashes = [(30, shash_a)]
    existing_texts = {30: article_a}

    verdict = classify(
        content_hash=_content_hash(article_b),
        simhash=shash_b,
        existing_hashes=existing_hashes,
        existing_simhashes=existing_simhashes,
        text=article_b,
        existing_texts=existing_texts,
    )

    assert verdict.kind == "new"
    assert verdict.matched_article_id is None
    assert verdict.should_store


def test_acronym_shift_deduplication_recognized() -> None:
    """Faz D: Kurum adı açılımı ile kısaltması arasındaki eşdeğerlik yakalanmalıdır."""
    text_full = "Türkiye İstatistik Kurumu temmuz ayı enflasyon verilerini kamuoyuyla paylaştı."
    text_acronym = "TÜİK temmuz ayı enflasyon verilerini kamuoyuyla paylaştı."

    sh_full = compute_simhash(text_full)
    sh_acr = compute_simhash(text_acronym)

    assert is_near_duplicate(sh_full, sh_acr, text_a=text_full, text_b=text_acronym)


def test_short_boilerplate_numeric_and_monthly_conflict_guard() -> None:
    """Faz D & Rem: Sayı veya ay içeren kısa şablon duyuruları yanlışlıkla birbirine yapışmamalıdır."""
    auction_a = (
        "Hazine 2 yıl vadeli sabit kuponlu devlet tahvili ihalesinde net 15 milyar TL borçlandı."
    )
    auction_b = (
        "Hazine 5 yıl vadeli TÜFE'ye endeksli devlet tahvili ihalesinde net 12 milyar TL borçlandı."
    )

    sh_a = compute_simhash(auction_a)
    sh_b = compute_simhash(auction_b)

    assert not is_near_duplicate(sh_a, sh_b, text_a=auction_a, text_b=auction_b), (
        "Farklı vadeli ve tutarlı ihale duyuruları near_duplicate olarak etiketlendi!"
    )

    verdict_auction = classify(
        content_hash=_content_hash(auction_b),
        simhash=sh_b,
        existing_hashes={_content_hash(auction_a): 101},
        existing_simhashes=[(101, sh_a)],
        text=auction_b,
        existing_texts={101: auction_a},
    )
    assert verdict_auction.kind == "new", (
        "Farklı tutarlı ihale duyurusu classify tarafından near sayıldı!"
    )
    assert verdict_auction.matched_article_id is None

    tcmb_jan = "TCMB Ocak ayı Para Politikası Kurulu toplantısında politika faizini yüzde 45 düzeyinde belirledi."
    tcmb_feb = "TCMB Şubat ayı Para Politikası Kurulu toplantısında politika faizini yüzde 45 düzeyinde sabit tuttu."

    sh_jan = compute_simhash(tcmb_jan)
    sh_feb = compute_simhash(tcmb_feb)

    assert not is_near_duplicate(sh_jan, sh_feb, text_a=tcmb_jan, text_b=tcmb_feb), (
        "Farklı aylara ait PPK kararları near_duplicate olarak çöktü!"
    )

    verdict_ppk = classify(
        content_hash=_content_hash(tcmb_feb),
        simhash=sh_feb,
        existing_hashes={_content_hash(tcmb_jan): 202},
        existing_simhashes=[(202, sh_jan)],
        text=tcmb_feb,
        existing_texts={202: tcmb_jan},
    )
    assert verdict_ppk.kind == "new", (
        "Farklı aylara ait PPK kararı classify tarafından near sayıldı!"
    )
    assert verdict_ppk.matched_article_id is None
