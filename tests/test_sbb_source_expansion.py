"""SBB kaynak genişletmesi — davranış sözleşmesi testleri (20 Ağustos 2026).

**Bu dosya neyi korur.** SBB, kanıt motorunun ölçülen Tier 1 açığını
kapatmak için eklendi (kanıt havuzunun %1,8'i Tier 1'di; R2'nin istediği
">=3 bağımsız grup VE Tier 1 birincil" bileşimini sağlayan iddia sayısı
SIFIR ölçüldü). Bir kaynağın kanıt gücünü artırması meşrudur; **yanlış
gruplama yoluyla artırması değildir.**

Testler bu ikisini ayırır:
  * SBB gerçekten ayrı bir kurumsal yayın olduğu için sayılıyor mu?  ✅
  * SBB tek başına ya da hatalı grupla bir iddiayı yeşile çevirebilir mi? ❌

Testler implementasyona değil **davranışa** bağlanır: hepsi kural
motorunun genel API'sinden (`compute_status`) geçer.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from politikdesk.evidence.independence import EvidenceArticle, independent_count
from politikdesk.evidence.rules import Claim, Evidence, compute_status, strong_min_sources

CONFIG = Path(__file__).resolve().parent.parent / "config" / "sources.yml"
DATA = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
SOURCES = DATA["sources"]
SBB = next((s for s in SOURCES if s["slug"] == "sbb"), None)


# ══════════════════════════════════════════════ 1–4 · envanter sözleşmesi


def test_max_sources_is_25() -> None:
    assert DATA["max_sources"] == 25


def test_sbb_is_in_production_inventory() -> None:
    assert SBB is not None, "SBB `config/sources.yml` içinde bulunamadı"
    assert SBB["tos_status"] == "allowed", "SBB toplanabilir olmalı"
    assert SBB["adapter"] == "rss"
    assert SBB["feed_url"] == "https://www.sbb.gov.tr/feed/"


def test_sbb_tier_is_1() -> None:
    """SBB Tier 1 olmalı — eklenme gerekçesinin TAMAMI budur.

    Tier 2/3 olsaydı R2'nin `has_primary_source` ayağını beslemezdi ve
    kaynak eklemenin hiçbir epistemik karşılığı olmazdı.
    """
    assert SBB is not None
    assert SBB["tier"] == 1
    assert SBB["kind"] == "official"


def test_sbb_independence_group_is_distinct() -> None:
    """Ayrı grup — ama `same_institution_as` BEYANI YOK.

    Ayrı grup, SBB'nin siyaseten bağımsız olduğu iddiası değildir;
    "aynı yayının ikinci sitesi" olmadığının temsilidir (Spec §8.2'nin
    engellediği şey Demirören tipi çakışmadır).
    """
    assert SBB is not None
    assert SBB["independence_group"] == "official-sbb"

    diger = [s["independence_group"] for s in SOURCES if s["slug"] != "sbb"]
    assert SBB["independence_group"] not in diger, (
        "SBB'nin grubu başka bir kaynakla çakışıyor — bağımsız sayım şişer"
    )
    assert not SBB.get("same_institution_as"), (
        "SBB bir kurum paylaşımı beyan etmiyor; beyan eklenirse grubu da "
        "paylaşmalıdır (test_every_source_has_a_distinct_independence_group)"
    )


# ═══════════════════════════════════════ 5–6 · gruplama davranış sözleşmesi


def _makale(article_id: int, slug: str, tier: int, kind: str, group: str | None) -> EvidenceArticle:
    return EvidenceArticle(
        article_id=article_id,
        source_slug=slug,
        tier=tier,
        kind=kind,
        independence_group=group,
        text=f"{slug} metni {article_id}",
    )


def test_same_group_is_never_counted_twice() -> None:
    """Aynı `independence_group`'taki iki makale TEK bağımsız kaynaktır."""
    ayni_grup = [
        _makale(1, "sbb", 1, "official", "official-sbb"),
        _makale(2, "sbb", 1, "official", "official-sbb"),
        _makale(3, "sbb", 1, "official", "official-sbb"),
    ]
    assert independent_count(ayni_grup) == 1, (
        "Aynı grubun üç makalesi üç bağımsız kaynak sayıldı — sayım şişiyor"
    )


def test_sbb_adds_exactly_one_group_of_diversity() -> None:
    """SBB gerçek grup çeşitliliğine katkı verir — bir tane, fazlası değil."""
    medya = [
        _makale(1, "birgun-politika", 3, "media", "media-birgun"),
        _makale(2, "karar", 3, "media", "media-karar"),
    ]
    assert independent_count(medya) == 2

    sbb_ile = [*medya, _makale(3, "sbb", 1, "official", "official-sbb")]
    assert independent_count(sbb_ile) == 3, "SBB bağımsız grup sayısını 1 artırmalı"

    # İkinci bir SBB makalesi sayıyı ARTIRMAZ.
    iki_sbb = [*sbb_ile, _makale(4, "sbb", 1, "official", "official-sbb")]
    assert independent_count(iki_sbb) == 3, (
        "SBB'nin ikinci makalesi bağımsız sayımı artırdı — aynı kurum iki kez sayılıyor"
    )


# ══════════════════════════════════════════ 7 · sessiz büyümeye karşı koruma


def test_cap_cannot_be_silently_exceeded() -> None:
    """Sınır ile kaynak sayısı arasında boşluk YOKTUR.

    Boşluk olsaydı bir sonraki kaynak hiçbir testi kırmadan eklenirdi.
    """
    assert DATA["max_sources"] == len(SOURCES) == 25


def test_loader_rejects_exceeding_the_cap(tmp_path: Path) -> None:
    """Sınır yalnızca testte değil YÜKLEYİCİDE de zorlanır."""
    from politikdesk.ingestion.sources import load_config

    sahte = tmp_path / "sources.yml"
    sahte.write_text(
        yaml.safe_dump(
            {
                "version": 3,
                "vertical": "macro_economy",
                "max_sources": 1,
                "sources": [
                    {
                        "slug": "a",
                        "name": "A",
                        "tier": 1,
                        "kind": "official",
                        "access_method": "rss",
                        "tos_status": "allowed",
                        "independence_group": "g-a",
                    },
                    {
                        "slug": "b",
                        "name": "B",
                        "tier": 1,
                        "kind": "official",
                        "access_method": "rss",
                        "tos_status": "allowed",
                        "independence_group": "g-b",
                    },
                ],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="sert sınır"):
        load_config(sahte)


# ═════════════════════════════ 8–9 · R2 epistemik invariantları KORUNUYOR


def _iddia() -> Claim:
    return Claim(claim_id=1, claim_text="Enflasyon temmuzda geriledi", claim_type="fact")


def _kanit(makaleler: list[EvidenceArticle]) -> list[Evidence]:
    return [Evidence(article=a, stance="supports", quote_span="") for a in makaleler]


def test_r2_threshold_unchanged() -> None:
    """SBB eklenmesi R2 eşiğini DEĞİŞTİRMEDİ."""
    assert strong_min_sources() == 3


def test_sbb_alone_cannot_make_a_claim_green() -> None:
    """Tek başına SBB -> 🟢 OLAMAZ. Tier 1 olmak yetmez; 3 bağımsız grup şart."""
    sonuc = compute_status(_iddia(), _kanit([_makale(1, "sbb", 1, "official", "official-sbb")]))
    assert sonuc.status != "strongly_corroborated", (
        f"Tek SBB makalesi iddiayı yeşile çevirdi ({sonuc.rule}) — R2 delinmiş"
    )


def test_sbb_plus_one_media_cannot_make_a_claim_green() -> None:
    """SBB + 1 medya = 2 grup < 3. Yeşil olmamalı."""
    sonuc = compute_status(
        _iddia(),
        _kanit(
            [
                _makale(1, "sbb", 1, "official", "official-sbb"),
                _makale(2, "karar", 3, "media", "media-karar"),
            ]
        ),
    )
    assert sonuc.status != "strongly_corroborated"


def test_sbb_plus_social_cannot_make_a_claim_green() -> None:
    """Tier 4 teyit sayılmaz: SBB + 5 sosyal hesap yine de yeşil değildir."""
    sosyal = [_makale(10 + i, f"x-hesap-{i}", 4, "social", f"social-{i}") for i in range(5)]
    sonuc = compute_status(
        _iddia(),
        _kanit([_makale(1, "sbb", 1, "official", "official-sbb"), *sosyal]),
    )
    assert sonuc.status != "strongly_corroborated", (
        "Sosyal kaynaklar teyit sayımına girmiş — Spec §8.3 R2 sosyal dışlaması delinmiş"
    )


def test_three_media_without_tier1_is_not_green() -> None:
    """R2'nin İKİNCİ ayağı: 3 bağımsız grup yeter DEĞİLDİR, Tier 1 de şart.

    Canlı ölçüm (20 Ağu 2026): 42 iddia bu durumda — >=3 bağımsız grup var,
    Tier 1 yok, hiçbiri yeşil değil. SBB'nin eklenmesi bu ayağı ancak
    AYNI iddiaya değdiğinde kapatabilir.
    """
    sonuc = compute_status(
        _iddia(),
        _kanit(
            [
                _makale(1, "birgun-politika", 3, "media", "media-birgun"),
                _makale(2, "karar", 3, "media", "media-karar"),
                _makale(3, "gazetepencere", 3, "media", "media-pencere"),
            ]
        ),
    )
    assert sonuc.status != "strongly_corroborated", (
        "Tier 1 olmadan yeşil üretildi — `has_primary_source` koşulu delinmiş"
    )


# ═══════════════════════════════ 10 · SBB'nin GERÇEK katkısı (sentetik fixture)


def test_sbb_enables_r2_when_it_genuinely_corroborates() -> None:
    """SBB, 2 bağımsız medyanın olduğu bir iddiaya Tier 1 ayağını ekler.

    Bu, kaynağın eklenme gerekçesinin davranış karşılığıdır: aynı senaryo
    SBB'siz 🟡 kalır, SBB ile 🟢 olur — çünkü eksik olan tek şey Tier 1
    birincil kaynaktı.
    """
    medya = [
        _makale(1, "birgun-politika", 3, "media", "media-birgun"),
        _makale(2, "karar", 3, "media", "media-karar"),
    ]

    sbbsiz = compute_status(
        _iddia(), _kanit([*medya, _makale(3, "dunya", 3, "media", "media-dunya")])
    )
    assert sbbsiz.status != "strongly_corroborated", "Üç medya + Tier 1 yok -> yeşil olmamalıydı"

    sbb_ile = compute_status(
        _iddia(), _kanit([*medya, _makale(3, "sbb", 1, "official", "official-sbb")])
    )
    assert sbb_ile.status == "strongly_corroborated", (
        f"SBB Tier 1 ayağını kapatmalıydı, sonuç: {sbb_ile.status} ({sbb_ile.rule})"
    )
    assert sbb_ile.rule == "R2"
    assert sbb_ile.reason["has_primary_source"] is True
    assert sbb_ile.reason["independent_count"] == 3


def test_sbb_contribution_comes_from_group_diversity_not_tier_alone() -> None:
    """Katkı GRUP çeşitliliğinden gelmeli, "Tier 1 var" demekten değil.

    SBB üç kez tekrarlansa bile bağımsız sayım 1'de kalır; dolayısıyla
    tek başına R2'yi açamaz. Yeşil ancak GERÇEK grup çeşitliliğiyle gelir.
    """
    uc_kez_sbb = [
        _makale(1, "sbb", 1, "official", "official-sbb"),
        _makale(2, "sbb", 1, "official", "official-sbb"),
        _makale(3, "sbb", 1, "official", "official-sbb"),
    ]
    sonuc = compute_status(_iddia(), _kanit(uc_kez_sbb))
    assert sonuc.reason["independent_count"] == 1
    assert sonuc.status != "strongly_corroborated", (
        "Aynı kurumun üç makalesi R2'yi açtı — bağımsızlık sayımı şişmiş"
    )


def test_wrong_grouping_would_inflate_and_is_therefore_guarded() -> None:
    """SBB yanlışlıkla İKİ ayrı grupla tanımlansaydı ne olurdu?

    Bu test bir hatayı yakalamaz; **neden config sözleşmesinin gerekli
    olduğunu** gösterir. Aynı kurum iki farklı grupla girseydi kanıt
    motoru onu iki bağımsız kaynak sayardı ve R2 yapay olarak açılırdı.
    Config tarafındaki koruma `test_sbb_independence_group_is_distinct`
    ve `test_every_source_has_a_distinct_independence_group`tır.
    """
    yanlis = [
        _makale(1, "sbb", 1, "official", "official-sbb"),
        _makale(2, "sbb", 1, "official", "official-sbb-2"),  # HATALI ikinci grup
        _makale(3, "karar", 3, "media", "media-karar"),
    ]
    sonuc = compute_status(_iddia(), _kanit(yanlis))
    # Motor metadata'ya güvenir; bu yüzden yapay yeşil ÇIKAR.
    assert sonuc.status == "strongly_corroborated"
    assert sonuc.reason["independent_count"] == 3
    # ...ve bu yüzden config'de tek grup olduğu ayrıca doğrulanır:
    assert SBB is not None
    gruplar = [s["independence_group"] for s in SOURCES if s["slug"] == "sbb"]
    assert gruplar == ["official-sbb"], (
        "SBB birden fazla grupla tanımlanmış — kanıt motoru onu birden çok bağımsız kaynak sayar"
    )
