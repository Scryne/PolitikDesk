"""PolitikDesk — Comprehensive Deterministic Corroboration & Epistemic Evaluation Harness.

Evaluates evidence rules R0–R8, syndication vs independence invariants,
hard negatives, cross-actor, cross-date, official vs media lag, and
corroboration status transitions against a 104-case production-derived corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from politikdesk.evidence.independence import EvidenceArticle, independent_count
from politikdesk.evidence.rules import (
    Claim,
    Evidence,
    compute_status,
)


@dataclass(frozen=True)
class CorroborationTestCase:
    id: str
    description: str
    category: str
    claim: Claim
    evidence_list: list[Evidence]
    expected_status: str
    expected_rule: str
    expected_independent_count: int
    partial_elements: bool = False


# -----------------------------------------------------------------------------
# 104-Case Production-Derived Golden Benchmark Corpus
# -----------------------------------------------------------------------------
CORPUS: list[CorroborationTestCase] = [
    # -------------------------------------------------------------------------
    # Category 1: Syndication & Wire Duplicate Suppression (Cases 1-16)
    # -------------------------------------------------------------------------
    CorroborationTestCase(
        id="SYN-01-AA-WIRE-4-OUTLETS",
        description="Anadolu Ajansı bülteni 4 farklı haber sitesinde kopyalanmış (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=101, claim_text="Enflasyon beklentisi açıklandı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=1, source_slug="anadolu-ajansi", tier=2, kind="wire", independence_group="wire-aa", text="AA: Enflasyon beklentisi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=2, source_slug="haberturk", tier=3, kind="media", independence_group="wire-aa", text="AA: Enflasyon beklentisi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3, source_slug="cnnturk", tier=3, kind="media", independence_group="wire-aa", text="AA: Enflasyon beklentisi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=4, source_slug="milliyet", tier=3, kind="media", independence_group="wire-aa", text="AA: Enflasyon beklentisi"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-02-DHA-WIRE-3-OUTLETS",
        description="Demirören Haber Ajansı bülteni 3 portalda yayınlanmış (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=102, claim_text="Sanayi üretim verileri açıklandı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=5, source_slug="dha", tier=2, kind="wire", independence_group="media-demiroren", text="DHA: Sanayi verisi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=6, source_slug="hurriyet", tier=3, kind="media", independence_group="media-demiroren", text="Sanayi verisi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=7, source_slug="posta", tier=3, kind="media", independence_group="media-demiroren", text="Sanayi verisi"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-03-TURKUVAZ-GROUP-INTERNAL",
        description="Turkuvaz Medya Grubu içi 3 farklı gazete aynı haberi paylaşmış (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=103, claim_text="Bakan Şimşek yeni vergi reformunu duyurdu", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=8, source_slug="sabah", tier=3, kind="media", independence_group="media-turkuvaz", text="Sabah: Vergi reformu"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=9, source_slug="takvim", tier=3, kind="media", independence_group="media-turkuvaz", text="Takvim: Vergi reformu"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=10, source_slug="ahaber", tier=3, kind="media", independence_group="media-turkuvaz", text="A Haber: Vergi reformu"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-04-IHA-WIRE-2-OUTLETS",
        description="İhlas Haber Ajansı bülteni 2 yerel haber sitesinde (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=104, claim_text="İhracat rakamları limanlarda artış gösterdi", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=11, source_slug="iha", tier=2, kind="wire", independence_group="media-ihlas", text="İHA: İhracat arttı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=12, source_slug="turkiyegazetesi", tier=3, kind="media", independence_group="media-ihlas", text="İhracat limanlarda arttı"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-05-ANKA-WIRE-2-OUTLETS",
        description="ANKA Haber Ajansı bülteni 2 bağımsız sitede kopyalanmış (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=105, claim_text="Sendikalar asgari ücret talebini açıkladı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=13, source_slug="anka", tier=2, kind="wire", independence_group="wire-anka", text="ANKA: Asgari ücret talebi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=14, source_slug="tele1", tier=3, kind="media", independence_group="wire-anka", text="ANKA: Asgari ücret talebi"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-06-REUTERS-TURKISH-WIRE",
        description="Reuters Türkçe bülteni ve çeviri kopyası (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=106, claim_text="Uluslararası derecelendirme kuruluşu not artırdı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=15, source_slug="reuters-tr", tier=2, kind="wire", independence_group="wire-reuters", text="Reuters: Not artışı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=16, source_slug="bloomberght", tier=3, kind="media", independence_group="wire-reuters", text="Reuters'a göre not artışı"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-07-CINER-GROUP-INTERNAL",
        description="Ciner Medya Grubu içi 2 portal aynı haberi yayınlamış (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=107, claim_text="Konut satışlarında aylık artış kaydedildi", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=17, source_slug="haberturk", tier=3, kind="media", independence_group="media-haberturk", text="Konut satışları arttı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=18, source_slug="haberturk-gundem", tier=3, kind="media", independence_group="media-haberturk", text="Konut satışlarında artış"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-08-SINGLE-ARTICLE-ONLY",
        description="Yalnızca tek bir makalede yer alan haber",
        category="syndication",
        claim=Claim(claim_id=108, claim_text="Yerel belediye yeni altyapı ihalesini tamamladı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=19, source_slug="diken-siyaset", tier=3, kind="media", independence_group="media-diken", text="İhale tamamlandı"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-09-CUMHURIYET-INTERNAL-TWO-SECTIONS",
        description="Cumhuriyet Ekonomi ve Politika aynı haberi girmiş (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=109, claim_text="Sendika genel grev çağrısı yaptı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=1101, source_slug="cumhuriyet-ekonomi", tier=3, kind="media", independence_group="media-cumhuriyet", text="Grev çağrısı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=1102, source_slug="cumhuriyet-politika", tier=3, kind="media", independence_group="media-cumhuriyet", text="Grev çağrısı"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-10-TRT-HABER-SECTIONS-INTERNAL",
        description="TRT Haber iki farklı servisi aynı haberi girmiş (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=110, claim_text="Savunma sanayi ihracatı yeni rekor kırdı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=1103, source_slug="trthaber", tier=3, kind="media", independence_group="media-trt", text="TRT: İhracat rekoru"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=1104, source_slug="trthaber-politika", tier=3, kind="media", independence_group="media-trt", text="TRT Politika: İhracat rekoru"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-11-AA-POLITIKA-AND-EKONOMI",
        description="AA Ekonomi ve AA Politika aynı bülteni geçmiş (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=111, claim_text="Kabine toplantısı Beştepe'de sona erdi", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=1105, source_slug="aa-ekonomi", tier=2, kind="wire", independence_group="wire-aa", text="AA: Kabine sona erdi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=1106, source_slug="aa-politika", tier=2, kind="wire", independence_group="wire-aa", text="AA: Kabine toplantısı bitti"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-12-DOGUS-GROUP-INTERNAL",
        description="Doğuş Medya Grubu içi 2 kanal aynı haberi yayınlamış (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=112, claim_text="Otomotiv pazarında satışlar geriledi", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=1107, source_slug="ntv", tier=3, kind="media", independence_group="media-dogus", text="NTV: Satışlar geriledi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=1108, source_slug="ntvpara", tier=3, kind="media", independence_group="media-dogus", text="NTV Para: Otomotiv satışları düştü"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-13-BLOOMBERG-HT-AND-CINER",
        description="BloombergHT ve Habertürk Ciner grubu ortak haberi (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=113, claim_text="Borsa İstanbul günü yükselişle tamamladı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=1109, source_slug="bloomberght", tier=3, kind="media", independence_group="media-ciner", text="Borsa günü primli kapattı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=1110, source_slug="haberturk", tier=3, kind="media", independence_group="media-ciner", text="BIST 100 yükselişle kapandı"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-14-WIRE-AA-COPIED-BY-SABAH",
        description="AA bülteni Sabah tarafından kaynak gösterilerek aynen girilmiş (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=114, claim_text="Tarım Kredi marketlerinde temel gıdada indirim", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=1111, source_slug="aa-ekonomi", tier=2, kind="wire", independence_group="wire-aa", text="AA: Tarım Kredi indirimi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=1112, source_slug="sabah-ekonomi", tier=3, kind="media", independence_group="wire-aa", text="AA'nın haberine göre indirim"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-15-WIRE-ANKA-COPIED-BY-BIRGUN",
        description="ANKA bülteni BirGün tarafından aynen kullanılmış (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=115, claim_text="Öğretmenler Meclis önünde basın açıklaması yaptı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=1113, source_slug="anka", tier=2, kind="wire", independence_group="wire-anka", text="ANKA: Öğretmenler Meclis önünde"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=1114, source_slug="birgun-politika", tier=3, kind="media", independence_group="wire-anka", text="ANKA: Öğretmenler Meclis önünde"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SYN-16-WIRE-DHA-COPIED-BY-CNN",
        description="DHA bülteni CNN Türk tarafından kullanılmış (1 bağımsız grup)",
        category="syndication",
        claim=Claim(claim_id=116, claim_text="Turizm bölgesinde yeni tesis açılışı yapıldı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=1115, source_slug="dha", tier=2, kind="wire", independence_group="media-demiroren", text="DHA: Tesis açıldı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=1116, source_slug="cnnturk", tier=3, kind="media", independence_group="media-demiroren", text="DHA: Tesis açıldı"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),

    # -------------------------------------------------------------------------
    # Category 2: Independent Media Corroboration R4 (Cases 17-32)
    # -------------------------------------------------------------------------
    CorroborationTestCase(
        id="MED-01-TWO-INDEPENDENT-OUTLETS",
        description="Kısmi teyit: Cumhuriyet ve BirGün bağımsız olarak haberleştirdi",
        category="independent_media",
        claim=Claim(claim_id=201, claim_text="Yeni ekonomi paketi haftaya Meclis'e geliyor", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=21, source_slug="cumhuriyet-politika", tier=3, kind="media", independence_group="media-cumhuriyet", text="Cumhuriyet: Ekonomi paketi Meclis'e geliyor"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=22, source_slug="birgun-politika", tier=3, kind="media", independence_group="media-birgun", text="BirGün: Meclis yeni paketi görüşecek"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="MED-02-THREE-INDEPENDENT-OUTLETS",
        description="Kısmi teyit: Sözcü, T24 ve Dünya Gazetesi bağımsız haberleştirdi (Tier 1 yok)",
        category="independent_media",
        claim=Claim(claim_id=202, claim_text="Bankacılık sektöründe kredi büyüme sınırları değişti", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=23, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="Kredi büyüme sınırları güncellendi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=24, source_slug="t24-politika", tier=3, kind="media", independence_group="media-t24", text="BDDK kulisleri: Kredi sınırları değişti"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=25, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="Bankacılıkta yeni kredi kararları"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="MED-03-FOUR-INDEPENDENT-OUTLETS",
        description="Kısmi teyit: 4 farklı medya grubu bağımsız haberleştirdi (Tier 1 yok)",
        category="independent_media",
        claim=Claim(claim_id=203, claim_text="Enerji sübvansiyonlarında kademeli tarifeye geçiliyor", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=26, source_slug="karar", tier=3, kind="media", independence_group="media-karar", text="Enerjide kademeli tarife hazırlığı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=27, source_slug="evrensel-politika", tier=3, kind="media", independence_group="media-evrensel", text="Elektrik ve doğalgazda yeni tarife modeli"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=28, source_slug="gazetepencere", tier=3, kind="media", independence_group="media-pencere", text="Enerji Bakanlığı yeni modele geçiyor"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=29, source_slug="ekoturk", tier=3, kind="media", independence_group="media-ekoturk", text="Enerjide sübvansiyon revizyonu"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=4,
    ),
    CorroborationTestCase(
        id="MED-04-WIRE-PLUS-ONE-INDEPENDENT-MEDIA",
        description="Kısmi teyit: 1 Ajans (AA) + 1 Bağımsız Haber Sitesi (T24)",
        category="independent_media",
        claim=Claim(claim_id=204, claim_text="Tahıl koridoru görüşmeleri İstanbul'da başladı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=30, source_slug="aa-ekonomi", tier=2, kind="wire", independence_group="wire-aa", text="AA: Görüşmeler başladı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=31, source_slug="t24-politika", tier=3, kind="media", independence_group="media-t24", text="İstanbul'da diplomasi trafiği başladı"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="MED-05-TWO-WIRE-SERVICES-INDEPENDENT",
        description="Kısmi teyit: 2 Farklı Bağımsız Ajans (AA ve ANKA)",
        category="independent_media",
        claim=Claim(claim_id=205, claim_text="Meclis komisyonunda bütçe maratonu başladı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=32, source_slug="aa-politika", tier=2, kind="wire", independence_group="wire-aa", text="AA: Plan ve Bütçe Komisyonu toplandı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=33, source_slug="anka", tier=2, kind="wire", independence_group="wire-anka", text="ANKA: Komisyonda bütçe görüşmeleri başladı"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="MED-06-SYNDICATED-GROUP-PLUS-ONE-OUTSIDER",
        description="Kısmi teyit: Turkuvaz Grubu (2 gazete) + Sözcü (2 bağımsız grup)",
        category="independent_media",
        claim=Claim(claim_id=206, claim_text="Savunma sanayiinde yeni ihracat sözleşmesi imzalandı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=34, source_slug="sabah-ekonomi", tier=3, kind="media", independence_group="media-turkuvaz", text="Sabah: Savunma ihracatı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=35, source_slug="takvim", tier=3, kind="media", independence_group="media-turkuvaz", text="Takvim: Savunma anlaşması"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=36, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="Sözcü: Savunma sözleşmesi imzalandı"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="MED-07-OPINION-ADJUSTED-TWO-SOURCES",
        description="Kısmi teyit: 2 bağımsız haber sitesinde kulis haberi",
        category="independent_media",
        claim=Claim(claim_id=207, claim_text="Kabinede sonbaharda revizyon bekleniyor", claim_type="attribution"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=37, source_slug="karar", tier=3, kind="media", independence_group="media-karar", text="Kulis: Kabinede değişim"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=38, source_slug="kisadalga", tier=3, kind="media", independence_group="media-kisadalga", text="Kulis: Kabine revizyonu"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="MED-08-INTERNATIONAL-AND-LOCAL-MEDIA",
        description="Kısmi teyit: BBC Türkçe + Cumhuriyet (2 bağımsız grup)",
        category="independent_media",
        claim=Claim(claim_id=208, claim_text="Deprem bölgesinde yeniden imar çalışmaları hızlandı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=39, source_slug="bbc-turkce", tier=2, kind="wire", independence_group="wire-bbc", text="BBC: Deprem konutları"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=40, source_slug="cumhuriyet-ekonomi", tier=3, kind="media", independence_group="media-cumhuriyet", text="Cumhuriyet: Bölgede inşaat faaliyetleri"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="MED-09-DUVAR-AND-DIKEN",
        description="Kısmi teyit: Gazete Duvar ve Diken bağımsız haberleştirdi (2 grup)",
        category="independent_media",
        claim=Claim(claim_id=209, claim_text="Anayasa Mahkemesi yeni iptal kararını açıkladı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=2091, source_slug="gazeteduvar-politika", tier=3, kind="media", independence_group="media-duvar", text="Duvar: AYM iptal kararı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=2092, source_slug="diken-siyaset", tier=3, kind="media", independence_group="media-diken", text="Diken: AYM'den iptal"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="MED-10-HALKTV-AND-MEDYASCOPE",
        description="Kısmi teyit: Halk TV ve Medyascope bağımsız haberleştirdi (2 grup)",
        category="independent_media",
        claim=Claim(claim_id=210, claim_text="Muhalefet partileri Meclis açılışı öncesi toplandı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=2101, source_slug="halktv-politika", tier=3, kind="media", independence_group="media-halktv", text="Halk TV: Muhalefet zirvesi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=2102, source_slug="medyascope", tier=3, kind="media", independence_group="media-medyascope", text="Medyascope: Parti liderleri görüştü"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="MED-11-EKONOMIM-AND-DUNYA",
        description="Kısmi teyit: Ekonomim ve Dünya Gazetesi bağımsız haberleştirdi (2 grup)",
        category="independent_media",
        claim=Claim(claim_id=211, claim_text="Reeskont kredilerinde faiz maliyeti düşürüldü", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=2111, source_slug="ekonomim", tier=3, kind="media", independence_group="media-ekonomim", text="Ekonomim: Reeskont faiz indirimi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=2112, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="Dünya: Reeskont kredisi maliyetleri indi"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="MED-12-EURONEWS-AND-DW",
        description="Kısmi teyit: Euronews ve DW Türkçe bağımsız ajans/medya (2 grup)",
        category="independent_media",
        claim=Claim(claim_id=212, claim_text="Avrupa Birliği vize kolaylığı müzakereleri başladı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=2121, source_slug="euronews-ekonomi", tier=3, kind="media", independence_group="media-euronews", text="Euronews: Vize müzakereleri"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=2122, source_slug="dw-ekonomi", tier=2, kind="wire", independence_group="media-dw", text="DW: Vize kolaylığı görüşmeleri"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="MED-13-SERBESTIYET-AND-YETKINREPORT",
        description="Kısmi teyit: Serbestiyet ve YetkinReport bağımsız analiz portalları (2 grup)",
        category="independent_media",
        claim=Claim(claim_id=213, claim_text="Dış politikada yeni bölgesel normalleşme adımı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=2131, source_slug="serbestiyet", tier=3, kind="media", independence_group="media-serbestiyet", text="Serbestiyet: Dış politika adımı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=2132, source_slug="yetkinreport", tier=3, kind="media", independence_group="media-yetkinreport", text="Yetkin: Normalleşme trafiği"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="MED-14-FIVE-INDEPENDENT-MEDIA-NO-OFFICIAL",
        description="Kısmi teyit: 5 bağımsız medya grubu (Tier 1 resmi kaynak yok -> en fazla R4)",
        category="independent_media",
        claim=Claim(claim_id=214, claim_text="Otomotiv sektöründe yeni yatırım teşvik paketi bekleniyor", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=2141, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="Sözcü: Teşvik paketi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=2142, source_slug="cumhuriyet-ekonomi", tier=3, kind="media", independence_group="media-cumhuriyet", text="Cumhuriyet: Otomotiv teşviki"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=2143, source_slug="birgun-politika", tier=3, kind="media", independence_group="media-birgun", text="BirGün: Teşvik hazırlığı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=2144, source_slug="karar", tier=3, kind="media", independence_group="media-karar", text="Karar: Yeni teşvik paketi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=2145, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="Dünya: Teşvik kulisleri"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=5,
    ),
    CorroborationTestCase(
        id="MED-15-HABERTURK-AND-SABAH",
        description="Kısmi teyit: Ciner Grubu ve Turkuvaz Grubu bağımsız haberleştirdi (2 grup)",
        category="independent_media",
        claim=Claim(claim_id=215, claim_text="Merkez Bankası döviz swap ihalelerinde limitleri artırdı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=2151, source_slug="haberturk", tier=3, kind="media", independence_group="media-haberturk", text="Habertürk: Swap limiti arttı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=2152, source_slug="sabah-ekonomi", tier=3, kind="media", independence_group="media-turkuvaz", text="Sabah: Swap düzenlemesi"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="MED-16-MAHFI-EGILMEZ-AND-DUNYA",
        description="Kısmi teyit: Uzman analist (Mahfi Eğilmez) ve Dünya Gazetesi (2 grup)",
        category="independent_media",
        claim=Claim(claim_id=216, claim_text="Cari açık finansmanında doğrudan yatırımların payı arttı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=2161, source_slug="mahfiegilmez", tier=3, kind="media", independence_group="expert-mahfiegilmez", text="Mahfi Eğilmez: Cari açık analizi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=2162, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="Dünya: Cari denge verileri"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),

    # -------------------------------------------------------------------------
    # Category 3: Strong Corroboration R2 (Official Tier 1 + Media) (Cases 33-48)
    # -------------------------------------------------------------------------
    CorroborationTestCase(
        id="STR-01-TCMB-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): TCMB resmi açıklaması + Sözcü + Dünya (3 bağımsız grup)",
        category="official_corroboration",
        claim=Claim(claim_id=301, claim_text="TCMB politika faizini yüzde 50 düzeyinde sabit tuttu", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=41, source_slug="tcmb", tier=1, kind="official", independence_group="official-tcmb", text="TCMB Duyurusu: Politika faizi %50"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=42, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="Merkez Bankası faizi %50'de bıraktı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=43, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="PPK kararı: Faiz sabit kaldı"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-02-RESMI-GAZETE-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): Resmî Gazete kararı + Cumhuriyet + Habertürk (3 bağımsız grup)",
        category="official_corroboration",
        claim=Claim(claim_id=302, claim_text="KDV oranlarında yeni düzenleme Resmî Gazete'de yayımlandı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=44, source_slug="resmi-gazete", tier=1, kind="official", independence_group="official-resmigazete", text="Resmî Gazete Sayı 33000: KDV Kararnamesi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=45, source_slug="cumhuriyet-ekonomi", tier=3, kind="media", independence_group="media-cumhuriyet", text="KDV düzenlemesi Resmî Gazete'de"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=46, source_slug="haberturk", tier=3, kind="media", independence_group="media-haberturk", text="KDV oranları yürürlüğe girdi"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-03-HAZINE-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): Hazine borçlanma bülteni + Ekotürk + Sabah (3 bağımsız grup)",
        category="official_corroboration",
        claim=Claim(claim_id=303, claim_text="Hazine iki tahvil ihalesinde 101,7 milyar TL borçlandı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=47, source_slug="hazine", tier=1, kind="official", independence_group="official-hazine", text="Hazine Bülteni: İhale sonuçları 101.7 milyar TL"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=48, source_slug="ekoturk", tier=3, kind="media", independence_group="media-ekoturk", text="Hazine ihale ile 101,7 milyar borçlandı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=49, source_slug="sabah-ekonomi", tier=3, kind="media", independence_group="media-turkuvaz", text="Hazine ihalelerle borçlandı"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-04-TBMM-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): TBMM Kanun metni + T24 + BirGün (3 bağımsız grup)",
        category="official_corroboration",
        claim=Claim(claim_id=304, claim_text="Öğretmenlik Mesleği Kanunu TBMM Genel Kurulu'nda kabul edildi", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=50, source_slug="tbmm", tier=1, kind="official", independence_group="official-tbmm", text="TBMM Kanun No 7520 kabul edildi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=51, source_slug="t24-politika", tier=3, kind="media", independence_group="media-t24", text="Öğretmenlik Kanunu Meclis'ten geçti"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=52, source_slug="birgun-politika", tier=3, kind="media", independence_group="media-birgun", text="Tartışmalı Öğretmenlik Kanunu yasalaştı"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-05-CB-KARARNAME-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): CB Kararnamesi + Karar + Diken (3 bağımsız grup)",
        category="official_corroboration",
        claim=Claim(claim_id=305, claim_text="Siber Güvenlik Başkanlığı kurulmasına dair Cumhurbaşkanlığı Kararnamesi yayımlandı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=53, source_slug="cb-kararname", tier=1, kind="official", independence_group="official-cb", text="CB Kararnamesi Sayı 160: Siber Güvenlik"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=54, source_slug="karar", tier=3, kind="media", independence_group="media-karar", text="Siber Güvenlik Başkanlığı kuruldu"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=55, source_slug="diken-siyaset", tier=3, kind="media", independence_group="media-diken", text="Yeni başkanlık kuruldu"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-06-SAYISTAY-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): Sayıştay Raporu + Gazete Pencere + Evrensel (3 bağımsız grup)",
        category="official_corroboration",
        claim=Claim(claim_id=306, claim_text="Sayıştay denetim raporunda kamu ihale mevzuatına aykırılıklar tespit edildi", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=56, source_slug="sayistay", tier=1, kind="official", independence_group="official-sayistay", text="Sayıştay 2025 Yılı Düzenlilik Denetim Raporu"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=57, source_slug="gazetepencere", tier=3, kind="media", independence_group="media-pencere", text="Sayıştay raporundaki usulsüzlükler"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=58, source_slug="evrensel-politika", tier=3, kind="media", independence_group="media-evrensel", text="Sayıştay'dan ihale uyarısı"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-07-SBB-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): Strateji ve Bütçe Başkanlığı Raporu + Dünya + BloombergHT (3 bağımsız grup)",
        category="official_corroboration",
        claim=Claim(claim_id=307, claim_text="2026 yılı merkezi yönetim bütçe gerçekleşmeleri yayımlandı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=59, source_slug="sbb", tier=1, kind="official", independence_group="official-sbb", text="SBB: Merkezi Yönetim Bütçe Bülteni"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=60, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="Bütçe gerçekleşmeleri açıklandı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=61, source_slug="bloomberght", tier=3, kind="media", independence_group="media-bloomberght", text="Bütçe açığı rakamları netleşti"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-08-TUIK-PLUS-FOUR-MEDIA",
        description="Güçlü teyit (R2): TÜİK Basın Bülteni + 4 Farklı Medya Grubu",
        category="official_corroboration",
        claim=Claim(claim_id=308, claim_text="TÜİK işsizlik oranını yüzde 8,8 olarak açıkladı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=62, source_slug="tuik", tier=1, kind="official", independence_group="official-tuik", text="TÜİK Haber Bülteni: İşgücü İstatistikleri %8,8"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=63, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="İşsizlik oranı %8,8 oldu"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=64, source_slug="cumhuriyet-ekonomi", tier=3, kind="media", independence_group="media-cumhuriyet", text="TÜİK işsizlik verisini duyurdu"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=65, source_slug="turkiyegazetesi", tier=3, kind="media", independence_group="media-ihlas", text="İşsizlikte tek hane devam ediyor"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=4,
    ),
    CorroborationTestCase(
        id="STR-09-TCMB-EVDS-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): TCMB EVDS veri serisi + Ekonomim + T24 (3 bağımsız grup)",
        category="official_corroboration",
        claim=Claim(claim_id=309, claim_text="TCMB brüt rezervleri 150 milyar doları aştı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=3091, source_slug="tcmb-evds", tier=1, kind="official", independence_group="official-tcmb", text="EVDS: Brüt rezervler 152.4 milyar USD"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3092, source_slug="ekonomim", tier=3, kind="media", independence_group="media-ekonomim", text="Rezervlerde tarihi rekor"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3093, source_slug="t24-politika", tier=3, kind="media", independence_group="media-t24", text="TCMB rezervleri 150 milyar doların üzerinde"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-10-RESMI-GAZETE-OTV-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): Resmi Gazete ÖTV Kararnamesi + Dünya + CNN Türk (3 bağımsız grup)",
        category="official_corroboration",
        claim=Claim(claim_id=310, claim_text="Motorinde kademeli ÖTV indirimi Resmi Gazete'de yayımlandı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=3101, source_slug="resmi-gazete", tier=1, kind="official", independence_group="official-resmigazete", text="Resmi Gazete: Motorin ÖTV Düzenlemesi Karar 8800"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3102, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="Motorinde ÖTV sıfırlandı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3103, source_slug="cnnturk", tier=3, kind="media", independence_group="media-demiroren", text="Motorine kademeli ÖTV yürürlüğe girdi"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-11-TBMM-BUTCE-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): TBMM Bütçe Kanun Teklifi + Sözcü + Sabah (3 bağımsız grup)",
        category="official_corroboration",
        claim=Claim(claim_id=311, claim_text="2027 Yılı Merkezi Yönetim Bütçe Kanun Teklifi TBMM'ye sunuldu", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=3111, source_slug="tbmm", tier=1, kind="official", independence_group="official-tbmm", text="TBMM Başkanlığı: 2027 Bütçe Teklifi sevk edildi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3112, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="Bütçe maratonu Meclis'te başladı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3113, source_slug="sabah-ekonomi", tier=3, kind="media", independence_group="media-turkuvaz", text="2027 Bütçesi TBMM'ye sunuldu"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-12-HAZINE-BORC-PLUS-THREE-MEDIA",
        description="Güçlü teyit (R2): Hazine Borç Stoku Bülteni + 3 Bağımsız Medya",
        category="official_corroboration",
        claim=Claim(claim_id=312, claim_text="Merkezi yönetim iç borç stoku açıklandı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=3121, source_slug="hazine", tier=1, kind="official", independence_group="official-hazine", text="Hazine: Haziran 2026 Borç Stoku İstatistikleri"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3122, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="İç borç stoku verileri açıklandı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3123, source_slug="birgun-politika", tier=3, kind="media", independence_group="media-birgun", text="Hazine borç rakamlarını duyurdu"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-13-TUIK-SANAYI-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): TÜİK Sanayi Üretim Endeksi + BloombergHT + Cumhuriyet (3 grup)",
        category="official_corroboration",
        claim=Claim(claim_id=313, claim_text="Sanayi üretimi yıllık yüzde 4,2 artış kaydetti", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=3131, source_slug="tuik", tier=1, kind="official", independence_group="official-tuik", text="TÜİK Bülteni: Sanayi Üretim Endeksi Haziran 2026"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3132, source_slug="bloomberght", tier=3, kind="media", independence_group="media-bloomberght", text="Sanayi üretiminde yıllık %4,2 artış"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3133, source_slug="cumhuriyet-ekonomi", tier=3, kind="media", independence_group="media-cumhuriyet", text="Sanayi üretimi Haziran'da arttı"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-14-CB-ATAMA-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): CB Atama Kararnamesi + Karar + Gazete Duvar (3 grup)",
        category="official_corroboration",
        claim=Claim(claim_id=314, claim_text="Valiler Kararnamesi ile 16 ilin valisi değişti", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=3141, source_slug="cb-kararname", tier=1, kind="official", independence_group="official-cb", text="CB Kararı 2026/300: Valiler Kararnamesi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3142, source_slug="karar", tier=3, kind="media", independence_group="media-karar", text="16 ilin valisi değişti"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3143, source_slug="gazeteduvar-politika", tier=3, kind="media", independence_group="media-duvar", text="Valiler Kararnamesi Resmi Gazete'de"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-15-SAYISTAY-BELEDIYE-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): Sayıştay Denetim Raporu + T24 + Gazete Pencere (3 grup)",
        category="official_corroboration",
        claim=Claim(claim_id=315, claim_text="Sayıştay belediye denetiminde bütçe dışı borçlanma tespit etti", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=3151, source_slug="sayistay", tier=1, kind="official", independence_group="official-sayistay", text="Sayıştay Yerel Yönetimler Denetim Raporu"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3152, source_slug="t24-politika", tier=3, kind="media", independence_group="media-t24", text="Sayıştay raporundaki belediye borçları"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3153, source_slug="gazetepencere", tier=3, kind="media", independence_group="media-pencere", text="Sayıştay'dan belediyelere borç uyarısı"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="STR-16-SBB-YATIRIM-PLUS-TWO-MEDIA",
        description="Güçlü teyit (R2): SBB Kamu Yatırım Raporu + Dünya + Ekonomim (3 grup)",
        category="official_corroboration",
        claim=Claim(claim_id=316, claim_text="2026 yılı kamu yatırımlarında ulaştırma sektörü ilk sırada yer aldı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=3161, source_slug="sbb", tier=1, kind="official", independence_group="official-sbb", text="SBB: 2026 Yılı Yatırım Programı İzleme Raporu"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3162, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="Kamu yatırımlarında ulaştırma lider"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=3163, source_slug="ekonomim", tier=3, kind="media", independence_group="media-ekonomim", text="Yatırım bütçesinde aslan payı ulaştırmanın"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R2",
        expected_independent_count=3,
    ),

    # -------------------------------------------------------------------------
    # Category 4: Official Numeric Publication Exception R3 (Cases 49-60)
    # -------------------------------------------------------------------------
    CorroborationTestCase(
        id="NUM-01-TUIK-TUFE-EXACT-R3",
        description="Resmi sayısal yayın (R3): TÜİK resmi TÜFE enflasyon açıklaması tam eşleşme",
        category="numeric_r3",
        claim=Claim(
            claim_id=401,
            claim_text="Temmuz 2026 TÜFE yıllık yüzde 31,75 oldu",
            claim_type="number",
            normalized_value={"metric": "tufe_annual", "value": 31.75, "unit": "%", "period": "2026-07"},
            value_verified_against_source=True,
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=71, source_slug="tuik", tier=1, kind="official", independence_group="official-tuik", text="TÜİK: Yıllık TÜFE %31,75"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R3",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="NUM-02-TCMB-POLICY-RATE-EXACT-R3",
        description="Resmi sayısal yayın (R3): TCMB resmi politika faizi tam eşleşme",
        category="numeric_r3",
        claim=Claim(
            claim_id=402,
            claim_text="TCMB bir hafta vadeli repo faiz oranını yüzde 50 olarak belirledi",
            claim_type="number",
            normalized_value={"metric": "policy_rate", "value": 50.0, "unit": "%", "period": "2026-08"},
            value_verified_against_source=True,
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=72, source_slug="tcmb", tier=1, kind="official", independence_group="official-tcmb", text="TCMB Kararı: Politika faizi %50"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R3",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="NUM-03-HAZINE-DEBT-STOCK-EXACT-R3",
        description="Resmi sayısal yayın (R3): Hazine merkezi yönetim borç stoku",
        category="numeric_r3",
        claim=Claim(
            claim_id=403,
            claim_text="Merkezi yönetim borç stoku 15,5 trilyon TL oldu",
            claim_type="number",
            normalized_value={"metric": "public_debt", "value": 15.5, "unit": "trilyon TL", "period": "2026-07"},
            value_verified_against_source=True,
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=73, source_slug="hazine", tier=1, kind="official", independence_group="official-hazine", text="Hazine: Borç stoku 15.5 trilyon TL"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R3",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="NUM-04-NUMERIC-NOT-VERIFIED-AGAINST-OFFICIAL",
        description="Sayısal iddia resmi değerle eşleşmedi (value_verified=False) -> single_source",
        category="numeric_r3",
        claim=Claim(
            claim_id=404,
            claim_text="Enflasyon yüzde 42 olarak gerçekleşti",
            claim_type="number",
            normalized_value={"metric": "tufe_annual", "value": 42.0, "unit": "%", "period": "2026-07"},
            value_verified_against_source=False,
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=74, source_slug="karar", tier=3, kind="media", independence_group="media-karar", text="Haber: Enflasyon %42 iddiası"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="NUM-05-NUMERIC-UNOFFICIAL-INDEX",
        description="Resmi olmayan endeks (ENAG) sayısı -> media kaynaklı, R3 alamaz",
        category="numeric_r3",
        claim=Claim(
            claim_id=405,
            claim_text="ENAG E-TÜFE yıllık yüzde 74,5 arttı",
            claim_type="number",
            normalized_value={"metric": "tufe_annual", "value": 74.5, "unit": "%", "period": "2026-07"},
            value_verified_against_source=False,
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=75, source_slug="cumhuriyet-ekonomi", tier=3, kind="media", independence_group="media-cumhuriyet", text="ENAG enflasyonu açıkladı: %74.5"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=76, source_slug="birgun-politika", tier=3, kind="media", independence_group="media-birgun", text="ENAG: Yıllık artış %74.5"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="NUM-06-NUMERIC-PERIOD-MISMATCH",
        description="Resmi veri var ama dönem uyuşmuyor -> R3 reddi, R5 kalır",
        category="numeric_r3",
        claim=Claim(
            claim_id=406,
            claim_text="Ağustos 2026 TÜFE yüzde 35 oldu",
            claim_type="number",
            normalized_value={"metric": "tufe_annual", "value": 35.0, "unit": "%", "period": "2026-08"},
            value_verified_against_source=False,
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=77, source_slug="t24-politika", tier=3, kind="media", independence_group="media-t24", text="Ağustos tahmini"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="NUM-07-TUIK-UFE-EXACT-R3",
        description="Resmi sayısal yayın (R3): TÜİK ÜFE yıllık yüzde 28,10",
        category="numeric_r3",
        claim=Claim(
            claim_id=407,
            claim_text="Temmuz 2026 Yİ-ÜFE yıllık yüzde 28,10 oldu",
            claim_type="number",
            normalized_value={"metric": "ufe_annual", "value": 28.10, "unit": "%", "period": "2026-07"},
            value_verified_against_source=True,
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=4071, source_slug="tuik", tier=1, kind="official", independence_group="official-tuik", text="TÜİK Bülteni: Yİ-ÜFE %28,10"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R3",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="NUM-08-TUIK-UNEMPLOYMENT-EXACT-R3",
        description="Resmi sayısal yayın (R3): TÜİK İşsizlik oranı yüzde 7,6",
        category="numeric_r3",
        claim=Claim(
            claim_id=408,
            claim_text="Haziran 2026 işsizlik oranı yüzde 7,6 oldu",
            claim_type="number",
            normalized_value={"metric": "unemployment_rate", "value": 7.6, "unit": "%", "period": "2026-06"},
            value_verified_against_source=True,
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=4081, source_slug="tuik", tier=1, kind="official", independence_group="official-tuik", text="TÜİK: İşsizlik oranı %7,6"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R3",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="NUM-09-TCMB-RESERVES-EXACT-R3",
        description="Resmi sayısal yayın (R3): TCMB brüt rezervleri 152,4 milyar USD",
        category="numeric_r3",
        claim=Claim(
            claim_id=409,
            claim_text="TCMB brüt rezervleri 152,4 milyar dolar olarak gerçekleşti",
            claim_type="number",
            normalized_value={"metric": "reserves", "value": 152.4, "unit": "milyar USD", "period": "2026-08"},
            value_verified_against_source=True,
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=4091, source_slug="tcmb-evds", tier=1, kind="official", independence_group="official-tcmb", text="EVDS: Rezervler 152.4 milyar USD"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R3",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="NUM-10-SBB-BUDGET-DEFICIT-EXACT-R3",
        description="Resmi sayısal yayın (R3): SBB bütçe açığı gerçekleşmesi",
        category="numeric_r3",
        claim=Claim(
            claim_id=410,
            claim_text="Merkezi yönetim bütçe açığı 95,2 milyar TL oldu",
            claim_type="number",
            normalized_value={"metric": "budget_balance", "value": -95.2, "unit": "milyar TL", "period": "2026-07"},
            value_verified_against_source=True,
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=4101, source_slug="sbb", tier=1, kind="official", independence_group="official-sbb", text="SBB: Temmuz Bütçe Dengesi -95.2 milyar TL"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R3",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="NUM-11-ITO-ISTANBUL-INFLATION-R4",
        description="İTO İstanbul enflasyon endeksi (resmi istatistik değil) -> R4",
        category="numeric_r3",
        claim=Claim(
            claim_id=411,
            claim_text="İstanbul'da perakende fiyat artışı yüzde 4,2 oldu",
            claim_type="number",
            normalized_value={"metric": "tufe_monthly", "value": 4.2, "unit": "%", "period": "2026-07"},
            value_verified_against_source=False,
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=4111, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="İTO enflasyonu %4,2"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=4112, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="İTO İstanbul fiyat endeksi %4,2"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="NUM-12-CORRUPTED-NUMERIC-VALUE",
        description="Bozuk sayısal değer eşleşmesi (value_verified=False) -> R5",
        category="numeric_r3",
        claim=Claim(
            claim_id=412,
            claim_text="Politika faizi yüzde 999 oldu iddiası",
            claim_type="number",
            normalized_value={"metric": "policy_rate", "value": 999.0, "unit": "%", "period": "2026-08"},
            value_verified_against_source=False,
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=4121, source_slug="x-hesap", tier=4, kind="social", independence_group="social-x", text="Faiz %999"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),

    # -------------------------------------------------------------------------
    # Category 5: Primary Attribution Verification R8 (Cases 61-70)
    # -------------------------------------------------------------------------
    CorroborationTestCase(
        id="ATT-01-TBMM-TUTANAK-SPEECH-R8",
        description="Resmi tutanak beyan sabiti (R8): TBMM Genel Kurul tutanağında sabit beyan",
        category="attribution_r8",
        claim=Claim(claim_id=501, claim_text="Bakan Şimşek bütçe disiplininden taviz verilmeyeceğini söyledi", claim_type="attribution"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=81, source_slug="tbmm", tier=1, kind="official", independence_group="official-tbmm", text="TBMM Tutanak Dergisi: Bakan Mehmet Şimşek konuşması."), stance="supports"),
        ],
        expected_status="attribution_verified",
        expected_rule="R8",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="ATT-02-CB-OFFICIAL-STATEMENT-R8",
        description="Resmi açıklama beyan sabiti (R8): TCCB resmi basın açıklaması",
        category="attribution_r8",
        claim=Claim(claim_id=502, claim_text="Cumhurbaşkanı Erdoğan bölgesel barış için diplomasi çağrısında bulundu", claim_type="attribution"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=82, source_slug="cb-kararname", tier=1, kind="official", independence_group="official-cb", text="T.C. Cumhurbaşkanlığı Basın Açıklaması"), stance="supports"),
        ],
        expected_status="attribution_verified",
        expected_rule="R8",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="ATT-03-RESMI-GAZETE-APPOINTMENT-R8",
        description="Resmi Gazete atama beyan sabiti (R8): Atama kararı",
        category="attribution_r8",
        claim=Claim(claim_id=503, claim_text="Yeni Merkez Bankası Başkan Yardımcısı atandı", claim_type="attribution"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=83, source_slug="resmi-gazete", tier=1, kind="official", independence_group="official-resmigazete", text="Resmî Gazete Atama Kararı 2026/200"), stance="supports"),
        ],
        expected_status="attribution_verified",
        expected_rule="R8",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="ATT-04-MEDIA-QUOTING-WITHOUT-OFFICIAL-RECORD",
        description="Medya kaynaklı aktör beyanı (Resmi tutanak yok) -> 1 bağımsız kaynak single_source",
        category="attribution_r8",
        claim=Claim(claim_id=504, claim_text="CHP Lideri Özel asgari ücret için Meclis'i olağanüstü toplantıya çağırdı", claim_type="attribution"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=84, source_slug="halktv-politika", tier=3, kind="media", independence_group="media-halktv", text="Halk TV: Özel açıklamalarda bulundu"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="ATT-05-MEDIA-MULTI-QUOTING-WITHOUT-OFFICIAL",
        description="Medya kaynaklı aktör beyanı (2 bağımsız medya grubu) -> partially_corroborated",
        category="attribution_r8",
        claim=Claim(claim_id=505, claim_text="İYİ Parti lideri ekonomi yönetimine tepki gösterdi", claim_type="attribution"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=85, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="Sözcü: Dervişoğlu'ndan ekonomi eleştirisi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=86, source_slug="karar", tier=3, kind="media", independence_group="media-karar", text="Karar: Dervişoğlu sert konuştu"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="ATT-06-TBMM-KANUN-GEREKCESI-R8",
        description="Resmi tutanak kanun gerekçesi (R8): TBMM Komisyon Raporu",
        category="attribution_r8",
        claim=Claim(claim_id=506, claim_text="Komisyon raporunda düzenlemenin kayıt dışılığı azaltacağı vurgulandı", claim_type="attribution"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=5061, source_slug="tbmm", tier=1, kind="official", independence_group="official-tbmm", text="TBMM Plan ve Bütçe Komisyonu Raporu Sıra Sayısı 120"), stance="supports"),
        ],
        expected_status="attribution_verified",
        expected_rule="R8",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="ATT-07-TCMB-BASKAN-SUNUMU-R8",
        description="TCMB Başkanı resmi bilgilendirme sunumu metni (R8)",
        category="attribution_r8",
        claim=Claim(claim_id=507, claim_text="TCMB Başkanı parasal sıkılığın korunacağını belirtti", claim_type="attribution"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=5071, source_slug="tcmb", tier=1, kind="official", independence_group="official-tcmb", text="TCMB: Başkan Karahan'ın Enflasyon Raporu Sunumu Metni"), stance="supports"),
        ],
        expected_status="attribution_verified",
        expected_rule="R8",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="ATT-08-HAZINE-BAKANLIK-DUYURUSU-R8",
        description="Hazine ve Maliye Bakanlığı resmi basın bülteni (R8)",
        category="attribution_r8",
        claim=Claim(claim_id=508, claim_text="Bakanlık gri listeden çıkışın reform kararlılığını gösterdiğini bildirdi", claim_type="attribution"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=5081, source_slug="hazine", tier=1, kind="official", independence_group="official-hazine", text="Hazine Basın Duyurusu 2026/45"), stance="supports"),
        ],
        expected_status="attribution_verified",
        expected_rule="R8",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="ATT-09-MEDIA-OPINION-COLUMN-QUOTE-R5",
        description="Köşe yazısında aktarılan kulis beyanı (Resmi teyit yok) -> R5",
        category="attribution_r8",
        claim=Claim(claim_id=509, claim_text="Bakan Yardımcısının istifa edeceği öne sürüldü", claim_type="attribution"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=5091, source_slug="t24-politika", tier=3, kind="media", independence_group="media-t24", text="T24 Kulis: İstifa iddiası"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="ATT-10-MEDIA-THREE-OUTLETS-ATTRIBUTION-R4",
        description="3 bağımsız medya organında ortak aktarılan parti sözcüsü beyanı -> R4",
        category="attribution_r8",
        claim=Claim(claim_id=510, claim_text="Parti sözcüsü erken seçim taleplerini yineledi", claim_type="attribution"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=5101, source_slug="cumhuriyet-politika", tier=3, kind="media", independence_group="media-cumhuriyet", text="Cumhuriyet: Erken seçim çağrısı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=5102, source_slug="birgun-politika", tier=3, kind="media", independence_group="media-birgun", text="BirGün: Erken seçim talebi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=5103, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="Sözcü: Sözcüden seçim açıklaması"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=3,
    ),

    # -------------------------------------------------------------------------
    # Category 6: Contradiction Detection R1 (Cases 71-80)
    # -------------------------------------------------------------------------
    CorroborationTestCase(
        id="CON-01-OFFICIAL-CONTRADICTED-BY-MEDIA",
        description="Çelişki (R1): Resmi kaynak bütçe açığının düştüğünü söylerken medya çelişki bildirdi",
        category="contradiction_r1",
        claim=Claim(claim_id=601, claim_text="Bütçe fazlası verildi", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=91, source_slug="hazine", tier=1, kind="official", independence_group="official-hazine", text="Hazine: Bütçe açığı gerçekleşti"), stance="contradicts"),
            Evidence(article=EvidenceArticle(article_id=92, source_slug="sabah-ekonomi", tier=3, kind="media", independence_group="media-turkuvaz", text="Bütçede fazla verildi"), stance="supports"),
        ],
        expected_status="contradicted",
        expected_rule="R1",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="CON-02-TWO-MEDIA-OUTLETS-CONTRADICTING",
        description="Ajans (Tier 2) ve Medya (Tier 3) çelişkisi -> R1 çelişki",
        category="contradiction_r1",
        claim=Claim(claim_id=602, claim_text="Doğalgaza yüzde 25 zam yapıldı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=93, source_slug="birgun-politika", tier=3, kind="media", independence_group="media-birgun", text="Doğalgaza %25 zam geldi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=94, source_slug="aa-ekonomi", tier=2, kind="wire", independence_group="wire-aa", text="BOTAŞ: Doğalgaza zam yapıldığı iddiaları doğru değildir"), stance="contradicts"),
        ],
        expected_status="contradicted",
        expected_rule="R1",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="CON-03-OFFICIAL-AND-MULTIPLE-CONTRADICTIONS",
        description="Çelişki (R1): 2 destekleyen medya, 1 resmi tekzip eden kaynak",
        category="contradiction_r1",
        claim=Claim(claim_id=603, claim_text="Rezervlerde tarihi erime yaşandı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=95, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="Rezervler eridi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=96, source_slug="karar", tier=3, kind="media", independence_group="media-karar", text="Rezervlerde gerileme"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=97, source_slug="tcmb", tier=1, kind="official", independence_group="official-tcmb", text="TCMB: Brüt rezervler artış gösterdi"), stance="contradicts"),
        ],
        expected_status="contradicted",
        expected_rule="R1",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="CON-04-NUMBER-CONTRADICTION",
        description="Çelişki (R1): Sayısal iddiada medya haberi resmi veriyle çelişiyor",
        category="contradiction_r1",
        claim=Claim(
            claim_id=604,
            claim_text="Yıllık TÜFE enflasyonu yüzde 20 oldu",
            claim_type="number",
            normalized_value={"metric": "tufe_annual", "value": 20.0, "unit": "%", "period": "2026-07"},
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=98, source_slug="sabah-ekonomi", tier=3, kind="media", independence_group="media-turkuvaz", text="Enflasyon %20"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=99, source_slug="tuik", tier=1, kind="official", independence_group="official-tuik", text="TÜİK Resmi: Enflasyon %31,75"), stance="contradicts"),
        ],
        expected_status="contradicted",
        expected_rule="R1",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="CON-05-WIRE-AND-MEDIA-CONTRADICTION",
        description="Çelişki (R1): AA ile T24 arasında karşılıklı çelişki",
        category="contradiction_r1",
        claim=Claim(claim_id=605, claim_text="Maden ocağındaki izinler iptal edildi", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=100, source_slug="t24-politika", tier=3, kind="media", independence_group="media-t24", text="İzinler iptal edildi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=101, source_slug="aa-politika", tier=2, kind="wire", independence_group="wire-aa", text="Bakanlık: İzinlerin iptali söz konusu değil"), stance="contradicts"),
        ],
        expected_status="contradicted",
        expected_rule="R1",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="CON-06-TBMM-VOTE-CONTRADICTION",
        description="Çelişki (R1): Resmi tutanak kabul edildi derken ret iddiası",
        category="contradiction_r1",
        claim=Claim(claim_id=606, claim_text="Yasa teklifi Meclis Genel Kurulu'nda reddedildi", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=6061, source_slug="tbmm", tier=1, kind="official", independence_group="official-tbmm", text="TBMM Tutanağı: Kanun teklifi kabul edilmiştir"), stance="contradicts"),
            Evidence(article=EvidenceArticle(article_id=6062, source_slug="diken-siyaset", tier=3, kind="media", independence_group="media-diken", text="Teklif reddedildi iddiası"), stance="supports"),
        ],
        expected_status="contradicted",
        expected_rule="R1",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="CON-07-MINISTRY-STATEMENT-CONTRADICTION",
        description="Çelişki (R1): Medya iddiası ve İletişim Başkanlığı DMM resmi tekzibi",
        category="contradiction_r1",
        claim=Claim(claim_id=607, claim_text="Kredi kartı limitlerine devlet el koydu", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=6071, source_slug="karar", tier=3, kind="media", independence_group="media-karar", text="Kredi kartlarına el konulacağı iddiası"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=6072, source_slug="cb-kararname", tier=1, kind="official", independence_group="official-cb", text="DMM Tekzibi: İddialar tamamen asılsızdır"), stance="contradicts"),
        ],
        expected_status="contradicted",
        expected_rule="R1",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="CON-08-POLICY-RATE-CONTRADICTION",
        description="Çelişki (R1): TCMB faiz kararı ile kulis haberi çelişkisi",
        category="contradiction_r1",
        claim=Claim(claim_id=608, claim_text="Merkez Bankası faiz indirimine gitti", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=6081, source_slug="tcmb", tier=1, kind="official", independence_group="official-tcmb", text="TCMB: Politika faizi sabit tutulmuştur"), stance="contradicts"),
            Evidence(article=EvidenceArticle(article_id=6082, source_slug="haberturk", tier=3, kind="media", independence_group="media-haberturk", text="Faiz indirildi iddiası"), stance="supports"),
        ],
        expected_status="contradicted",
        expected_rule="R1",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="CON-09-BORROWING-INTEREST-CONTRADICTION",
        description="Çelişki (R1): Hazine ihale faizi çelişkisi",
        category="contradiction_r1",
        claim=Claim(claim_id=609, claim_text="Hazine tahvil faizleri yüzde 60'a yükseldi", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=6091, source_slug="hazine", tier=1, kind="official", independence_group="official-hazine", text="Hazine Bülteni: İhalede bileşik faiz %48,50"), stance="contradicts"),
            Evidence(article=EvidenceArticle(article_id=6092, source_slug="cumhuriyet-ekonomi", tier=3, kind="media", independence_group="media-cumhuriyet", text="Faizler fırladı iddiası"), stance="supports"),
        ],
        expected_status="contradicted",
        expected_rule="R1",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="CON-10-UNEMPLOYMENT-CONTRADICTION",
        description="Çelişki (R1): TÜİK işsizlik verisi ile yanlış haber çelişkisi",
        category="contradiction_r1",
        claim=Claim(claim_id=610, claim_text="İşsizlik çift haneye çıktı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=6101, source_slug="tuik", tier=1, kind="official", independence_group="official-tuik", text="TÜİK Resmi: İşsizlik %7,6"), stance="contradicts"),
            Evidence(article=EvidenceArticle(article_id=6102, source_slug="karar", tier=3, kind="media", independence_group="media-karar", text="İşsizlik %12 iddiası"), stance="supports"),
        ],
        expected_status="contradicted",
        expected_rule="R1",
        expected_independent_count=1,
    ),

    # -------------------------------------------------------------------------
    # Category 7: Prediction Short-Circuit R0 (Cases 81-88)
    # -------------------------------------------------------------------------
    CorroborationTestCase(
        id="PRE-01-FUTURE-INFLATION-PREDICTION",
        description="Gelecek tahmini (R0): Enflasyon 2027'de tek haneye inecek (unverified)",
        category="prediction_r0",
        claim=Claim(claim_id=701, claim_text="Enflasyon 2027 sonunda tek haneye inecek", claim_type="prediction"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=111, source_slug="tcmb", tier=1, kind="official", independence_group="official-tcmb", text="TCMB Enflasyon Raporu Projeksiyonu"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=112, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="Piyasa beklentisi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=113, source_slug="bloomberght", tier=3, kind="media", independence_group="media-bloomberght", text="Ekonomist anketi"), stance="supports"),
        ],
        expected_status="unverified",
        expected_rule="R0",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="PRE-02-FUTURE-GROWTH-FORECAST",
        description="Gelecek tahmini (R0): Büyüme tahmini gerçekleşmiş olgu değildir",
        category="prediction_r0",
        claim=Claim(claim_id=702, claim_text="Türkiye ekonomisi 2027 yılında yüzde 4,5 büyüyecek", claim_type="prediction"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=114, source_slug="sbb", tier=1, kind="official", independence_group="official-sbb", text="OVP Projeksiyonu: 2027 %4.5 büyüme"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=115, source_slug="reuters-tr", tier=2, kind="wire", independence_group="wire-reuters", text="Reuters: OVP hedefleri"), stance="supports"),
        ],
        expected_status="unverified",
        expected_rule="R0",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="PRE-03-ELECTION-PROMISE",
        description="Siyasi vaat / tahmin: Asgari ücret vaadi gerçekleşme değildir -> R4",
        category="prediction_r0",
        claim=Claim(claim_id=703, claim_text="İktidara geldiğimizde emekli maaşı asgari ücrete eşitlenecek", claim_type="promise"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=116, source_slug="cumhuriyet-politika", tier=3, kind="media", independence_group="media-cumhuriyet", text="Muhalefet vaadi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=117, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="Parti programı açıklandı"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="PRE-04-MARKET-TARGET-PREDICTION",
        description="Piyasa hedef tahmini (R0): BIST 100 yıl sonunda 15.000 puanı aşacak",
        category="prediction_r0",
        claim=Claim(claim_id=704, claim_text="BIST 100 endeksi yıl sonunda 15.000 puanı aşacak", claim_type="prediction"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=118, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="Aracı kurum hedefi"), stance="supports"),
        ],
        expected_status="unverified",
        expected_rule="R0",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="PRE-05-EXCHANGE-RATE-FORECAST",
        description="Döviz kuru tahmini (R0): Dolar yıl sonunda 45 TL olacak",
        category="prediction_r0",
        claim=Claim(claim_id=705, claim_text="Dolar kuru yıl sonunda 45 TL seviyesine ulaşacak", claim_type="prediction"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=7051, source_slug="ekonomim", tier=3, kind="media", independence_group="media-ekonomim", text="Piyasa anketi dolar tahmini"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=7052, source_slug="karar", tier=3, kind="media", independence_group="media-karar", text="Ekonomistlerin kur beklentisi"), stance="supports"),
        ],
        expected_status="unverified",
        expected_rule="R0",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="PRE-06-INTEREST-RATE-CUT-PREDICTION",
        description="Faiz indirim takvimi tahmini (R0): İlk faiz indirimi Kasım'da yapılacak",
        category="prediction_r0",
        claim=Claim(claim_id=706, claim_text="TCMB ilk faiz indirimini Kasım ayında gerçekleştirecek", claim_type="prediction"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=7061, source_slug="bloomberght", tier=3, kind="media", independence_group="media-bloomberght", text="Yabancı banka faiz beklentisi"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=7062, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="Piyasalarda faiz indirimi beklentisi"), stance="supports"),
        ],
        expected_status="unverified",
        expected_rule="R0",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="PRE-07-BUDGET-TARGET-OVP-PROJECTION",
        description="OVP 3 yıllık bütçe hedefi (R0): 2028'de bütçe açığı yüzde 1,5'e gerileyecek",
        category="prediction_r0",
        claim=Claim(claim_id=707, claim_text="Bütçe açığının GSYH'ye oranı 2028'de yüzde 1,5 olacak", claim_type="prediction"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=7071, source_slug="sbb", tier=1, kind="official", independence_group="official-sbb", text="OVP Hedefleri Tablosu"), stance="supports"),
        ],
        expected_status="unverified",
        expected_rule="R0",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="PRE-08-OIL-PRICE-PROJECTION",
        description="Petrol fiyat tahmini (R0): Brent petrol varili 100 dolara çıkacak",
        category="prediction_r0",
        claim=Claim(claim_id=708, claim_text="Brent petrolün varil fiyatı son çeyrekte 100 doları aşacak", claim_type="prediction"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=7081, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="Emtia raporu projeksiyonu"), stance="supports"),
        ],
        expected_status="unverified",
        expected_rule="R0",
        expected_independent_count=1,
    ),

    # -------------------------------------------------------------------------
    # Category 8: Social Media Ceiling R7 (Cases 89-96)
    # -------------------------------------------------------------------------
    CorroborationTestCase(
        id="SOC-01-THREE-SOCIAL-ACCOUNTS",
        description="Sosyal medya tavanı (R7): 3 farklı X hesabı paylaşmış -> en fazla single_source",
        category="social_ceiling_r7",
        claim=Claim(claim_id=801, claim_text="Sosyal medyada yayılan kulis iddiası", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=121, source_slug="x-hesap-1", tier=4, kind="social", independence_group="social-1", text="Kulis 1"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=122, source_slug="x-hesap-2", tier=4, kind="social", independence_group="social-2", text="Kulis 2"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=123, source_slug="x-hesap-3", tier=4, kind="social", independence_group="social-3", text="Kulis 3"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R7",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="SOC-02-FIVE-SOCIAL-ACCOUNTS",
        description="Sosyal medya tavanı (R7): 5 farklı X hesabı viral paylaşmış -> en fazla single_source",
        category="social_ceiling_r7",
        claim=Claim(claim_id=802, claim_text="Bakan istifa etti dedikodusu", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=124, source_slug="x-hesap-a", tier=4, kind="social", independence_group="social-a", text="İstifa iddiası A"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=125, source_slug="x-hesap-b", tier=4, kind="social", independence_group="social-b", text="İstifa iddiası B"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=126, source_slug="x-hesap-c", tier=4, kind="social", independence_group="social-c", text="İstifa iddiası C"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=127, source_slug="x-hesap-d", tier=4, kind="social", independence_group="social-d", text="İstifa iddiası D"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=128, source_slug="x-hesap-e", tier=4, kind="social", independence_group="social-e", text="İstifa iddiası E"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R7",
        expected_independent_count=5,
    ),
    CorroborationTestCase(
        id="SOC-03-SOCIAL-PLUS-ONE-MEDIA",
        description="Sosyal medya + 1 Media Portalı -> 2 bağımsız kaynak (R4)",
        category="social_ceiling_r7",
        claim=Claim(claim_id=803, claim_text="Ünlü futbol kulübü satılıyor iddiası", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=129, source_slug="x-hesap-1", tier=4, kind="social", independence_group="social-1", text="Sosyal medya iddiası"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=130, source_slug="karar", tier=3, kind="media", independence_group="media-karar", text="Karar: Sosyal medyada kulüp satışı iddiası"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="SOC-04-SINGLE-SOCIAL-ACCOUNT",
        description="Tek bir sosyal medya hesabı paylaşımı (count=1 -> R5)",
        category="social_ceiling_r7",
        claim=Claim(claim_id=804, claim_text="Anonim hesap iddiası", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=131, source_slug="x-hesap-1", tier=4, kind="social", independence_group="social-1", text="Anonim paylaşım"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="SOC-05-SIX-POLITICIAN-TWEETS-ONLY",
        description="Sosyal medya tavanı (R7): 6 farklı siyasetçi tweet atmış -> R7 single_source",
        category="social_ceiling_r7",
        claim=Claim(claim_id=805, claim_text="Yeni parti kurulacağı iddiaları", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=8051, source_slug="x-memetsimsek", tier=4, kind="social", independence_group="social-memetsimsek", text="Tweet 1"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=8052, source_slug="x-ozgurozel", tier=4, kind="social", independence_group="social-ozgurozel", text="Tweet 2"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=8053, source_slug="x-alibabacan", tier=4, kind="social", independence_group="social-alibabacan", text="Tweet 3"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=8054, source_slug="x-ahmetdavutoglu", tier=4, kind="social", independence_group="social-ahmetdavutoglu", text="Tweet 4"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=8055, source_slug="x-umitozdag", tier=4, kind="social", independence_group="social-umitozdag", text="Tweet 5"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=8056, source_slug="x-ekremimamoglu", tier=4, kind="social", independence_group="social-ekremimamoglu", text="Tweet 6"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R7",
        expected_independent_count=6,
    ),
    CorroborationTestCase(
        id="SOC-06-MINISTRY-TWEET-PLUS-TWO-MEDIA",
        description="Bakanlık Twitter hesabı (Tier 4) + 2 Bağımsız Medya (Tier 3) -> R4 partially_corroborated",
        category="social_ceiling_r7",
        claim=Claim(claim_id=806, claim_text="Konut kampanyasında başvuru tarihleri açıklandı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=8061, source_slug="x-muratkurum", tier=4, kind="social", independence_group="social-muratkurum", text="Murat Kurum tweet: Başvurular başladı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=8062, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="Sözcü: Konut başvuruları başladı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=8063, source_slug="cumhuriyet-ekonomi", tier=3, kind="media", independence_group="media-cumhuriyet", text="Cumhuriyet: Başvuru detayları"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=3,
    ),
    CorroborationTestCase(
        id="SOC-07-TWO-SOCIAL-ACCOUNTS-ONLY",
        description="Sosyal medya tavanı (R7): 2 farklı X hesabı -> R7 single_source",
        category="social_ceiling_r7",
        claim=Claim(claim_id=807, claim_text="Metro arızası yaşandığı iddiası", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=8071, source_slug="x-hesap-1", tier=4, kind="social", independence_group="social-1", text="Metro arıza yaptı"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=8072, source_slug="x-hesap-2", tier=4, kind="social", independence_group="social-2", text="Metro durdu"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R7",
        expected_independent_count=2,
    ),
    CorroborationTestCase(
        id="SOC-08-FOUR-SOCIAL-LIST-ACCOUNTS",
        description="Sosyal medya tavanı (R7): 4 farklı bot/liste hesabı -> R7 single_source",
        category="social_ceiling_r7",
        claim=Claim(claim_id=808, claim_text="Kripto para düzenlemesi sızdırıldı dedikodusu", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=8081, source_slug="x-list-1", tier=4, kind="social", independence_group="social-l1", text="Sızıntı 1"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=8082, source_slug="x-list-2", tier=4, kind="social", independence_group="social-l2", text="Sızıntı 2"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=8083, source_slug="x-list-3", tier=4, kind="social", independence_group="social-l3", text="Sızıntı 3"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=8084, source_slug="x-list-4", tier=4, kind="social", independence_group="social-l4", text="Sızıntı 4"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R7",
        expected_independent_count=4,
    ),

    # -------------------------------------------------------------------------
    # Category 9: Hard Negatives (Cases 97-100)
    # -------------------------------------------------------------------------
    CorroborationTestCase(
        id="HARD-01-SAME-ACTOR-DIFFERENT-DATE",
        description="Hard Negative: Aynı aktörün (Erdoğan) farklı tarihteki farklı beyanları ayrık kalmalıdır",
        category="hard_negative",
        claim=Claim(claim_id=901, claim_text="Cumhurbaşkanı Erdoğan Marmaris'te vatandaşlarla bir araya geldi", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=141, source_slug="haberturk", tier=3, kind="media", independence_group="media-haberturk", text="Cumhurbaşkanı Erdoğan Marmaris ziyareti"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="HARD-02-SAME-INDICATOR-DIFFERENT-MONTH",
        description="Hard Negative: Aynı gösterge (TÜFE) fakat Haziran vs Temmuz dönemi ayrı kalmalıdır",
        category="hard_negative",
        claim=Claim(
            claim_id=902,
            claim_text="Haziran ayı TÜFE yıllık yüzde 37,00 oldu",
            claim_type="number",
            normalized_value={"metric": "tufe_annual", "value": 37.00, "unit": "%", "period": "2026-06"},
            value_verified_against_source=True,
        ),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=142, source_slug="tuik", tier=1, kind="official", independence_group="official-tuik", text="TÜİK Haziran 2026 TÜFE %37,00"), stance="supports"),
        ],
        expected_status="strongly_corroborated",
        expected_rule="R3",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="HARD-03-SAME-AGENCY-DIFFERENT-ACTION",
        description="Hard Negative: TÜİK enflasyon ile TÜİK sanayi üretimi iki ayrı işlemdir",
        category="hard_negative",
        claim=Claim(claim_id=903, claim_text="TÜİK sanayi üretim endeksi verilerini açıkladı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=9031, source_slug="tuik", tier=1, kind="official", independence_group="official-tuik", text="TÜİK Sanayi Raporu"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),
    CorroborationTestCase(
        id="HARD-04-SAME-DECISION-NO-DIFFERENT-ENTITY",
        description="Hard Negative: 2026/10 sayılı karar BDDK vs TCMB farklı kurumlardır",
        category="hard_negative",
        claim=Claim(claim_id=904, claim_text="BDDK 2026/10 sayılı kredi kartı kararını yayımladı", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=9041, source_slug="dunya", tier=3, kind="media", independence_group="media-dunya", text="BDDK 2026/10 Kararı"), stance="supports"),
        ],
        expected_status="single_source",
        expected_rule="R5",
        expected_independent_count=1,
    ),

    # -------------------------------------------------------------------------
    # Category 10: Edge Cases (Cases 101-104)
    # -------------------------------------------------------------------------
    CorroborationTestCase(
        id="EDGE-01-PARTIAL-ELEMENTS-FALLBACK",
        description="Edge Case: partial_elements=True bayrağı ile eksik kanıt elemanları güvenli şekilde ele alınmalıdır",
        category="edge_case",
        claim=Claim(claim_id=9901, claim_text="Eksik bileşenli iddia testi", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=9911, source_slug="birgun-politika", tier=3, kind="media", independence_group="media-birgun", text="Metin"), stance="supports"),
            Evidence(article=EvidenceArticle(article_id=9912, source_slug="sozcu-politika", tier=3, kind="media", independence_group="media-sozcu", text="Metin"), stance="supports"),
        ],
        expected_status="partially_corroborated",
        expected_rule="R4",
        expected_independent_count=2,
        partial_elements=True,
    ),
    CorroborationTestCase(
        id="EDGE-02-EMPTY-EVIDENCE-LIST-R6",
        description="Edge Case: Sıfır kanıt bağı olan iddia (R6 unverified)",
        category="edge_case",
        claim=Claim(claim_id=9902, claim_text="Hiçbir kanıt bağı olmayan yetim iddia", claim_type="fact"),
        evidence_list=[],
        expected_status="unverified",
        expected_rule="R6",
        expected_independent_count=0,
    ),
    CorroborationTestCase(
        id="EDGE-03-SINGLE-MENTIONS-ONLY",
        description="Edge Case: Sadece 'mentions' stance içeren makale (destekleme yok) -> R6 unverified",
        category="edge_case",
        claim=Claim(claim_id=9903, claim_text="Yalnızca değinilen iddia", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=9913, source_slug="karar", tier=3, kind="media", independence_group="media-karar", text="Değinme"), stance="mentions"),
        ],
        expected_status="unverified",
        expected_rule="R6",
        expected_independent_count=0,
    ),
    CorroborationTestCase(
        id="EDGE-04-SINGLE-CONTRADICTS-ONLY",
        description="Edge Case: Sadece tek bir 'contradicts' stance içeren makale (destekleme sıfır) -> R6 unverified",
        category="edge_case",
        claim=Claim(claim_id=9904, claim_text="Yalanlanan iddia", claim_type="fact"),
        evidence_list=[
            Evidence(article=EvidenceArticle(article_id=9914, source_slug="aa-politika", tier=2, kind="wire", independence_group="wire-aa", text="Yalanlama"), stance="contradicts"),
        ],
        expected_status="unverified",
        expected_rule="R6",
        expected_independent_count=0,
    ),
]


@dataclass
class EvalMetrics:
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    precision: float = 0.0
    recall: float = 0.0
    false_corroboration_rate: float = 0.0
    category_scores: dict[str, dict[str, int]] | None = None
    failures: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "false_corroboration_rate": round(self.false_corroboration_rate, 4),
            "category_scores": self.category_scores or {},
            "failures": self.failures or [],
        }


def run_corroboration_evaluation(corpus: list[CorroborationTestCase] | None = None) -> EvalMetrics:
    """Tüm altın korpusu değerlendirir ve kesin doğruluk metriklerini hesaplar."""
    test_cases = corpus or CORPUS
    total = len(test_cases)
    passed = 0
    failures: list[dict[str, Any]] = []
    false_corroborations = 0
    cat_scores: dict[str, dict[str, int]] = {}

    for tc in test_cases:
        cat = tc.category
        if cat not in cat_scores:
            cat_scores[cat] = {"total": 0, "passed": 0}
        cat_scores[cat]["total"] += 1

        res = compute_status(tc.claim, tc.evidence_list, partial_elements=tc.partial_elements)
        supporting = [e.article for e in tc.evidence_list if e.supports]
        actual_ind_count = independent_count(supporting)

        ok_status = res.status == tc.expected_status
        ok_rule = res.rule == tc.expected_rule
        ok_ind = actual_ind_count == tc.expected_independent_count

        if ok_status and ok_rule and ok_ind:
            passed += 1
            cat_scores[cat]["passed"] += 1
        else:
            if res.status in ("strongly_corroborated", "partially_corroborated") and tc.expected_status in (
                "single_source",
                "unverified",
                "contradicted",
            ):
                false_corroborations += 1

            failures.append(
                {
                    "case_id": tc.id,
                    "category": tc.category,
                    "description": tc.description,
                    "expected": {
                        "status": tc.expected_status,
                        "rule": tc.expected_rule,
                        "independent_count": tc.expected_independent_count,
                    },
                    "actual": {
                        "status": res.status,
                        "rule": res.rule,
                        "independent_count": actual_ind_count,
                    },
                }
            )

    precision = passed / total if total > 0 else 0.0
    recall = passed / total if total > 0 else 0.0
    false_rate = false_corroborations / total if total > 0 else 0.0

    return EvalMetrics(
        total_cases=total,
        passed_cases=passed,
        failed_cases=len(failures),
        precision=precision,
        recall=recall,
        false_corroboration_rate=false_rate,
        category_scores=cat_scores,
        failures=failures,
    )


if __name__ == "__main__":
    metrics = run_corroboration_evaluation()
    print(f"Corroboration Evaluation: {metrics.passed_cases}/{metrics.total_cases} passed ({metrics.precision * 100:.1f}%)")
    print(f"False Corroboration Rate: {metrics.false_corroboration_rate * 100:.1f}%")
    print("Category Breakdown:")
    for cat, score in (metrics.category_scores or {}).items():
        print(f"  {cat:25}: {score['passed']}/{score['total']}")
    if metrics.failures:
        print("Failures:")
        for f in metrics.failures:
            print(" ", f)
