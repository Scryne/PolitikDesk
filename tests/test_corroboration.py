"""Çapraz teyit yolunun testleri (B-79).

**Bu dosyanın var olma sebebi bir hatadır (13 Ağustos 2026).**

`diversity_ratio` üç faz boyunca 1,0'dı: 48 iddianın tamamı
`single_source` ya da `unverified`, tek bir `corroborated` yok. Backlog
bunu "çapraz teyit edecek bağımsız kaynak yok" diye teşhis etmişti
(B-79, `docs/FAZ3-SONRASI-DENETIM.md` §5).

**Teşhis yanlıştı.** Kaynak vardı; kod onu atıyordu:

    deduped = dedupe_claims([c for c, _ in collected])
    kept    = {id(c) for c in deduped}
    final   = [(c, aid) for c, aid in collected if id(c) in kept]

İki bağımsız kaynak aynı iddiayı söylediğinde ikinci çift **tamamen**
düşüyordu — yalnızca yinelenen metin değil, o kaynağın kanıt bağı da.
`independent_count` hiçbir zaman 1'i geçemiyordu; sekiz kaynak da canlı
olsa oran 1,0'da kalırdı.

Buradaki testler o yolun açık kaldığını denetler.
"""

from __future__ import annotations

from politikdesk.evidence.independence import EvidenceArticle, independent_count
from politikdesk.evidence.rules import Claim, Evidence, compute_status
from politikdesk.nlp.claims import (
    ExtractedClaim,
    dedupe_claims,
    group_claims_by_source,
)


def _claim(text: str, *, quote: str, ctype: str = "fact",
           value: dict | None = None) -> ExtractedClaim:
    return ExtractedClaim(
        claim_text=text, claim_type=ctype, quote_span=quote, normalized_value=value,
    )


# ===========================================================================
# Asıl hata: aynı iddia iki kaynakta -> İKİ kanıt bağı
# ===========================================================================
def test_same_claim_from_two_sources_keeps_both_links() -> None:
    """B-79'un tam testi. Bu düşerse çapraz teyit yine imkânsızdır."""
    collected = [
        (_claim("TCMB faizi %37'de sabit tuttu", quote="faizi yüzde 37'de sabit"), 101),
        (_claim("TCMB faizi %37'de sabit tuttu", quote="politika faizi yüzde 37"), 202),
    ]

    grouped = group_claims_by_source(collected)

    assert len(grouped) == 1, "İddia tek kayıt olmalı (F2-09)"
    _, sources = grouped[0]
    assert len(sources) == 2, (
        "İki bağımsız kaynağın da kanıt bağı korunmalı — B-79'un düzelttiği "
        "hata tam olarak ikincisinin atılmasıydı."
    )
    assert {aid for aid, _ in sources} == {101, 202}


def test_each_source_keeps_its_own_quote() -> None:
    """Kanıt bağı, iddianın O KAYNAKTA hangi sözlerle geçtiğini
    göstermeli. Başka bir makalenin cümlesini göstermek, kanıtın
    kendisini yanlışlar."""
    collected = [
        (_claim("Enflasyon %30", quote="AA'nın cümlesi"), 101),
        (_claim("Enflasyon %30", quote="Dünya'nın cümlesi"), 202),
    ]

    _, sources = group_claims_by_source(collected)[0]
    quotes = dict(sources)

    assert quotes[101] == "AA'nın cümlesi"
    assert quotes[202] == "Dünya'nın cümlesi"


def test_numeric_claims_group_by_normalized_value() -> None:
    """Sayısal imza `metric:value:period`e normalize edilir — yani hata
    tam da çapraz teyidin EN NET olduğu yolda tetikleniyordu.

    Farklı cümleler, aynı sayı: tek iddia, iki kaynak.
    """
    value = {"metric": "cpi", "value": 1.78, "period": "2026-07"}
    collected = [
        (_claim("TÜFE aylık %1,78 arttı", quote="a", ctype="number", value=value), 1),
        (_claim("Aylık enflasyon yüzde 1,78 oldu", quote="b",
                ctype="number", value=value), 2),
    ]

    grouped = group_claims_by_source(collected)
    assert len(grouped) == 1
    assert len(grouped[0][1]) == 2


def test_same_article_twice_yields_one_link() -> None:
    """LLM aynı makalede aynı iddiayı iki kez üretebilir; kanıt bağı
    makale başına tektir — yoksa tek kaynak kendini teyit eder."""
    collected = [
        (_claim("Enflasyon %30", quote="ilk"), 101),
        (_claim("Enflasyon %30", quote="ikinci"), 101),
    ]

    _, sources = group_claims_by_source(collected)[0]
    assert len(sources) == 1, "Aynı makale iki kez sayılamaz"


def test_distinct_claims_stay_distinct() -> None:
    """Ters yön: farklı iddialar birleştirilmemeli."""
    collected = [
        (_claim("TCMB faizi sabit tuttu", quote="a"), 1),
        (_claim("Enflasyon yükseldi", quote="b"), 2),
    ]
    assert len(group_claims_by_source(collected)) == 2


def test_grouping_preserves_first_seen_order() -> None:
    """Sıra kararlı olmalı: aynı girdi aynı kayıt sırasını üretmeli,
    yoksa iki koşumun çıktısı karşılaştırılamaz."""
    collected = [
        (_claim("A iddiasi", quote="q"), 1),
        (_claim("B iddiasi", quote="q"), 2),
        (_claim("A iddiasi", quote="q"), 3),
    ]
    texts = [c.claim_text for c, _ in group_claims_by_source(collected)]
    assert texts == ["A iddiasi", "B iddiasi"]


def test_dedupe_claims_still_works_for_its_own_purpose() -> None:
    """`dedupe_claims` silinmedi — kaynak bilgisi gerekmeyen çağıranlar
    için hâlâ doğru. Yalnızca boru hattı artık onu kullanmıyor."""
    claims = [_claim("Ayni", quote="a"), _claim("Ayni", quote="b")]
    assert len(dedupe_claims(claims)) == 1


# ===========================================================================
# Uçtan uca: iki kaynak -> corroborated
# ===========================================================================
def _evidence(article_id: int, tier: int, group: str) -> Evidence:
    return Evidence(
        article=EvidenceArticle(
            article_id=article_id, source_slug=f"kaynak{article_id}", tier=tier,
            kind="media", independence_group=group, simhash=article_id * 7919,
            embedding=[], text=f"birbirinden farkli metin {article_id}",
        ),
        stance="supports",
        quote_span=f"alinti {article_id}",
    )


def test_two_independent_links_produce_corroboration() -> None:
    """Zincirin sonu: iki kanıt bağı kanıt motorunda `single_source`'u
    aşmalı. Bu tutmazsa gruplama düzeltmesi bir işe yaramamış demektir.
    """
    evidence = [_evidence(1, 2, "grpA"), _evidence(2, 2, "grpB")]

    assert independent_count([e.article for e in evidence]) == 2

    result = compute_status(
        Claim(claim_id=1, claim_text="Enflasyon %30 oldu", claim_type="fact"),
        evidence,
    )
    assert result.status != "single_source"
    assert result.reason["independent_count"] == 2


def test_one_link_is_still_single_source() -> None:
    """Kontrol grubu: tek kaynak hâlâ tek kaynak olmalı. Düzeltme
    `independent_count`'u şişirmemeli."""
    result = compute_status(
        Claim(claim_id=1, claim_text="Enflasyon %30 oldu", claim_type="fact"),
        [_evidence(1, 2, "grpA")],
    )
    assert result.status == "single_source"
    assert result.rule == "R5"
