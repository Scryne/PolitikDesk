"""İddia kanıt matrisi (Roadmap Faz 5.2).

Bir iddianın arkasındaki kanıt havuzunu **boyut boyut** açar: kaç kaynak,
hangi kademeden, kaç bağımsız grup, kurumun kendi sayısı var mı, en son
ne zaman değerlendirildi.

-----------------------------------------------------------------------
⛔ BOYUTLAR TEK BİR SAYIYA ÇARPILMAZ
-----------------------------------------------------------------------

"Şu iddia %78 güvenilir" demek, yedi ayrı olguyu tek bir opak sayıya
gömmektir ve o sayı hiçbir soruyu yanıtlamaz. Matris her boyutu ayrı
gösterir; hüküm `evidence_status`'tadır ve onu **deterministik kural
motoru** verir (Spec §8.1 — bir LLM değil).

-----------------------------------------------------------------------
KARŞI KANIT BOYUTU: ÖLÇÜLEMEDİ, SIFIR DEĞİL
-----------------------------------------------------------------------

Roadmap 5.2 matriste "Evidence −" ve "Counterclaim" boyutlarını istiyor.
Bu boyutlar bu üründe **yapısal olarak doldurulamıyor** ve sebebi
ölçüldü (19 Ağu 2026):

    evidence.stance dağılımı        5.309 satırın 5.309'u 'supports'
    stance='contradicts' yazan yol  YOK (depo geneli arama)
    evidence_status='contradicted'  4.331 iddianın 0'ı

`nlp/claims_pipeline.py` kanıt bağını **sabit** `stance='supports'` ile
yazıyor; `evidence/rules.py::_r1_contradicted()` yazılmış ve test
edilmiş, ama üretimde **asla ateşleyemez**. Bu, migration 0007'nin
belgelediği durumun aynısı: *"Kural yazılmıştı, ölüydü."*

Deterministik bir çıkış yolu arandı ve ÖLÇÜLDÜ: `numeric_guard`
(aynı metrik, farklı değer) canlı korpusta 4.000 kanıt bağında 1,
20.000 çapraz (iddia × kaynaklamayan makale) çiftinde **0** çelişki
buldu. Yani o yolla da doldurulamıyor.

Bu yüzden matris karşı kanıtı **`unavailable`** olarak işaretler,
`0` olarak değil. İkisi çok farklı şeydir: sıfır "aradık, bulamadık"
demektir; `unavailable` "bu boyut ölçülmüyor" demektir. Ayrıntı
`docs/ADR-008-KARSI-KANIT-YOLU.md`'de.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Literal

from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)

DimensionState = Literal["measured", "unavailable"]

# Kullanıcıya gösterilen kesinlik dili — KONTROLLÜ.
#
# `evidence/explain.py::STATUS_TITLES` motorun teknik etiketidir
# ("Güçlü teyitli"); bu tablo ürünün KULLANICIYA söylediği cümledir.
# İkisi ayrı tutulur çünkü teknik durum sayısı değişebilir ama
# kullanıcıya verilen kesinlik dili dört kovada sabit kalmalıdır.
CERTAINTY: Final[dict[str, str]] = {
    "strongly_corroborated": "DESTEKLENİYOR",
    "partially_corroborated": "KISMEN DESTEKLENİYOR",
    "attribution_verified": "BEYAN SABİT",
    "single_source": "DOĞRULANAMADI",
    "unverified": "DOĞRULANAMADI",
    "contradicted": "ÇELİŞİLİYOR",
}

# ⛔ Bu kovaların dışına çıkılmaz. "Muhtemelen doğru", "büyük ihtimalle"
# gibi ifadeler kesinlik dilini kaydırır ve ürünün epistemik sözleşmesini
# bozar: sistem bir olasılık tahmini yapmaz, kanıt havuzunu tarif eder.
ALLOWED_CERTAINTY: Final[frozenset[str]] = frozenset(CERTAINTY.values())

# Resmî istatistik kaynakları — R3'ün "kurumun kendi yayını" istisnası
# (`evidence/rules.py::OFFICIAL_STATISTICAL_SOURCES` ile aynı küme).
OFFICIAL_SLUGS: Final[frozenset[str]] = frozenset(
    {"tuik", "tcmb", "tcmb-evds", "hazine", "sbb", "resmi-gazete", "resmigazete"}
)


@dataclass(frozen=True)
class Dimension:
    """Matrisin tek bir boyutu.

    `state='unavailable'` **sıfır değildir**: boyutun ölçülmediğini
    söyler. Sıfır "aradık, bulamadık" demektir.
    """

    key: str
    label: str
    count: int | None
    state: DimensionState
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "count": self.count,
            "state": self.state,
            "detail": self.detail,
        }


@dataclass
class ClaimMatrix:
    """Bir iddianın kanıt matrisi."""

    claim_id: int
    claim_text: str
    claim_type: str
    evidence_status: str
    certainty: str
    last_verified: Any
    engine_version: str | None
    dimensions: list[Dimension] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    sibling_claim_ids: list[int] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "claim_type": self.claim_type,
            "evidence_status": self.evidence_status,
            "certainty": self.certainty,
            "last_verified": self.last_verified,
            "engine_version": self.engine_version,
            "dimensions": [d.as_dict() for d in self.dimensions],
            "sources": self.sources,
            "sibling_claim_ids": self.sibling_claim_ids,
        }


_CLAIM_SQL = """
    SELECT cl.id, cl.claim_text, cl.claim_type, cl.evidence_status,
           cl.computed_at, cl.status_reason, cl.claim_signature
      FROM claims cl
     WHERE cl.id = %s
"""

_SOURCE_SQL = """
    SELECT s.slug, s.name, s.tier, s.kind, s.independence_group,
           ev.stance, ev.quote_span, a.canonical_url, a.published_at,
           (a.official_value IS NOT NULL) AS has_official_value
      FROM evidence ev
      JOIN articles a ON a.id = ev.article_id
      JOIN sources s  ON s.id = a.source_id
     WHERE ev.claim_id = %s
     ORDER BY s.tier, s.slug
"""

# Aynı iddianın başka olaylardaki kopyaları. `claim_signature` bu iş
# için var (migration 0006) ve canlı veride %99,8 dolu.
_SIBLING_SQL = """
    SELECT id FROM claims
     WHERE claim_signature = %s AND id <> %s
     ORDER BY id
     LIMIT 20
"""


def build(claim_id: int) -> ClaimMatrix | None:
    """Tek bir iddianın kanıt matrisini kurar."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(_CLAIM_SQL, (claim_id,))
        claim = cur.fetchone()
        if claim is None:
            return None

        cur.execute(_SOURCE_SQL, (claim_id,))
        kaynaklar = [dict(r) for r in cur.fetchall()]

        kardesler: list[int] = []
        if claim.get("claim_signature"):
            cur.execute(_SIBLING_SQL, (claim["claim_signature"], claim_id))
            kardesler = [int(r["id"]) for r in cur.fetchall()]

    durum = str(claim["evidence_status"])
    reason = claim.get("status_reason") or {}

    matrix = ClaimMatrix(
        claim_id=int(claim["id"]),
        claim_text=str(claim["claim_text"]),
        claim_type=str(claim["claim_type"]),
        evidence_status=durum,
        certainty=CERTAINTY.get(durum, "DOĞRULANAMADI"),
        last_verified=claim.get("computed_at"),
        engine_version=(reason or {}).get("engine_version"),
        sources=kaynaklar,
        sibling_claim_ids=kardesler,
    )
    matrix.dimensions = _dimensions(kaynaklar)
    return matrix


def _dimensions(kaynaklar: list[dict[str, Any]]) -> list[Dimension]:
    """Yedi boyut — beşi ölçülü, ikisi yapısal olarak ölçülemez."""
    destek = [k for k in kaynaklar if k.get("stance") == "supports"]
    gruplar = {k["independence_group"] for k in kaynaklar if k.get("independence_group")}
    birincil = [k for k in kaynaklar if int(k.get("tier") or 9) == 1]
    resmi_sayi = [k for k in kaynaklar if k.get("has_official_value")]
    bagimsiz = [k for k in kaynaklar if str(k.get("slug")) not in OFFICIAL_SLUGS]

    return [
        Dimension(
            "supporting", "Destekleyen kanıt", len(destek), "measured",
            f"{len(destek)} kaynak bağı",
        ),
        # ⛔ SIFIR DEĞİL, ÖLÇÜLEMEDİ. Gerekçe modül başlığında ve
        # ADR-008'de; ölçüldü, uydurulmadı.
        Dimension(
            "contradicting", "Çelişen kanıt", None, "unavailable",
            "Bu boyut ölçülmüyor — kanıt bağları yalnızca 'supports' "
            "olarak yazılıyor (bkz. ADR-008)",
        ),
        Dimension(
            "counterclaim", "Karşı iddia", None, "unavailable",
            "Çelişen kanıt ölçülmediği için karşı iddia da türetilemiyor",
        ),
        Dimension(
            "official_data", "Kurumun kendi sayısı", len(resmi_sayi), "measured",
            f"{len(resmi_sayi)} makale makine okunur değer taşıyor (R3 girdisi)",
        ),
        Dimension(
            "primary_source", "Birincil kaynak", len(birincil), "measured",
            f"{len(birincil)} Tier 1 kaynak",
        ),
        Dimension(
            "independent", "Bağımsız kaynak", len(bagimsiz), "measured",
            f"{len(bagimsiz)} resmî olmayan kaynak",
        ),
        Dimension(
            "independence_groups", "Bağımsızlık grubu", len(gruplar), "measured",
            ", ".join(sorted(gruplar)) or "grup atanmamış",
        ),
    ]


def coverage_report() -> dict[str, Any]:
    """Matrisin kaç iddiada anlamlı doldurulabildiği — dürüstlük ölçüsü.

    Bir matris boyutu tüm iddialarda boşsa, o boyutu arayüzde göstermek
    kullanıcıyı yanıltır. Bu rapor onu ölçer.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM claims")
        toplam_satiri = cur.fetchone()
        toplam = int(toplam_satiri["n"]) if toplam_satiri else 0

        cur.execute("SELECT stance, count(*) AS n FROM evidence GROUP BY stance")
        stance = {str(r["stance"]): int(r["n"]) for r in cur.fetchall()}

        cur.execute("SELECT evidence_status, count(*) AS n FROM claims GROUP BY evidence_status")
        durumlar = {str(r["evidence_status"]): int(r["n"]) for r in cur.fetchall()}

        cur.execute(
            "SELECT count(DISTINCT ev.claim_id) AS n FROM evidence ev "
            "JOIN articles a ON a.id = ev.article_id WHERE a.official_value IS NOT NULL"
        )
        resmi_satiri = cur.fetchone()

        cur.execute("SELECT count(*) AS n FROM claims WHERE claim_signature IS NOT NULL")
        imza_satiri = cur.fetchone()

    return {
        "claims": toplam,
        "stance_distribution": stance,
        "status_distribution": durumlar,
        "claims_with_official_value": int(resmi_satiri["n"]) if resmi_satiri else 0,
        "claims_with_signature": int(imza_satiri["n"]) if imza_satiri else 0,
        "contradiction_path_alive": stance.get("contradicts", 0) > 0,
    }
