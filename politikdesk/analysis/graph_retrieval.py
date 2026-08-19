"""Graf tabanlı kanıt erişimi (Roadmap Faz 4.2 — deterministik yarı).

-----------------------------------------------------------------------
⛔ LLM BU MODÜLDE YOK VE OLMAYACAK
-----------------------------------------------------------------------

Faz 4.2'nin zinciri şu:

    Soru -> Varlık Çözümleme -> Graf Gezinme -> Kanıt Toplama
         -> Zamansal Süzme -> ATIF KÜMESİ -> (LLM Sentezi)

Bu modül **atıf kümesine kadar** olan her adımı üretir ve hepsi
deterministiktir. Son adım bilerek dışarıda:

**LLM asla kanıt ÜRETMEZ, yalnızca var olan kanıt kümesini özetler.**

Sentez adımının buraya bağlanmaması bir eksiklik değil, bir karardır:
bu üründe üretilen her metin `editorial/grounding_check.py` sert
kapısından geçer (kanıtta bulunmayan sayı, oran veya alıntı taslağa
giremez). Buraya ayrı bir üretim yolu açmak, o kapıyı baypas eden ikinci
bir yüzey açardı — ürünün çekirdek garantisinde delik demektir. Sentez
gerektiğinde mevcut editoryal boru hattı kullanılmalı, yenisi değil.

-----------------------------------------------------------------------
GRAF NEDEN VAR
-----------------------------------------------------------------------

Düz metin araması bir olayın KOMŞULARINI bilmez. "Şimşek enflasyon
hedefi" araması hedefi açıklayan olayı bulur; hedefin tutulup
tutulmadığını gösteren olayı bulmaz — o ayrı bir kayıttır ve aralarındaki
bağ `event_relations`/`stance_shifts` kenarlarındadır.

Kullanılan kenarlar (19 Ağu 2026 canlı sayım):

    event_relations.same_thread   453   aynı gelişme dizisi
    event_relations.updates       160   sonraki gelişme
    stance_shifts.reversal         50   söylem değişikliği (Faz 4.1)

Gezinme DERİNLİK SINIRLIDIR. Sınırsız yayılma, 1557 olaylık bir grafta
alakasız her şeyi "bağlam" diye toplar ve atıf kümesini işe yaramaz
hâle getirir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final

from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)

# Gezinme derinliği. 2 hop: olay -> komşusu -> onun komşusu.
# 3'te canlı grafta bileşen boyutu hızla büyüyor ve alaka düşüyor.
MAX_DEPTH: Final[int] = 2

# Tek sorguda dönebilecek azami düğüm. Üst sınır olmadan bir "hub" olay
# (çok bağlantılı) tüm grafı çeker.
MAX_NODES: Final[int] = 40

# Atıf kümesindeki azami kanıt satırı.
MAX_CITATIONS: Final[int] = 60


@dataclass(frozen=True)
class ResolvedEntity:
    """Sorudan çözümlenmiş varlık — deterministik eşleşme."""

    entity_id: int
    canonical_name: str
    entity_type: str
    match_method: str
    matched_term: str


@dataclass(frozen=True)
class Citation:
    """Tek bir atıf. Kökeni eksiksiz taşır — kaynaksız atıf atıf değildir."""

    claim_id: int
    claim_text: str
    evidence_status: str
    event_id: int
    event_title: str
    source_name: str
    source_slug: str
    independence_group: str | None
    article_url: str | None
    published_at: Any
    depth: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "evidence_status": self.evidence_status,
            "event_id": self.event_id,
            "event_title": self.event_title,
            "source_name": self.source_name,
            "source_slug": self.source_slug,
            "independence_group": self.independence_group,
            "article_url": self.article_url,
            "published_at": self.published_at,
            "depth": self.depth,
        }


@dataclass
class RetrievalResult:
    """Atıf kümesi ve nasıl elde edildiği.

    ⛔ Bir CEVAP DEĞİLDİR. Yalnızca "bu soruya dair elimizde ne var"
    sorusunun deterministik yanıtıdır. Yorum insanın işidir.
    """

    question: str
    entities: list[ResolvedEntity] = field(default_factory=list)
    seed_event_ids: list[int] = field(default_factory=list)
    traversed_event_ids: list[int] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    independence_groups: list[str] = field(default_factory=list)
    stance_shift_ids: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "entities": [
                {
                    "entity_id": e.entity_id,
                    "canonical_name": e.canonical_name,
                    "entity_type": e.entity_type,
                    "match_method": e.match_method,
                    "matched_term": e.matched_term,
                }
                for e in self.entities
            ],
            "seed_event_ids": self.seed_event_ids,
            "traversed_event_ids": self.traversed_event_ids,
            "citations": [c.as_dict() for c in self.citations],
            "independence_groups": self.independence_groups,
            "stance_shift_ids": self.stance_shift_ids,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# 1. Varlık çözümleme — deterministik
# ---------------------------------------------------------------------------
# Soruda geçen ve varlık adı olamayacak kadar yaygın sözcükler. Bunlar
# elenmezse "ne oldu" gibi bir soru rastgele varlıklara çarpar.
_STOPWORDS: Final[frozenset[str]] = frozenset(
    {
        "ne", "neden", "nasıl", "kim", "hangi", "nedir", "oldu", "olur",
        "için", "ile", "ve", "veya", "bir", "bu", "şu", "o", "da", "de",
        "mi", "mı", "mu", "mü", "en", "son", "yeni", "kaç", "var", "yok",
    }
)
MIN_TERM_LENGTH: Final[int] = 3


def resolve_entities(question: str, *, limit: int = 6) -> list[ResolvedEntity]:
    """Sorudaki terimleri kayıtlı varlıklara bağlar.

    ⛔ LLM YOK. Eşleşme `entities.canonical_name` üzerinde tam ve
    parçalı (ILIKE) aramadır; yöntem her sonuçta `match_method` olarak
    kaydedilir ki bir atıfın nereden geldiği sonradan denetlenebilsin.
    """
    terimler = [
        t.strip(".,;:!?\"'()")
        for t in (question or "").split()
        if len(t.strip(".,;:!?\"'()")) >= MIN_TERM_LENGTH
    ]
    terimler = [t for t in terimler if t.lower() not in _STOPWORDS]
    if not terimler:
        return []

    bulunan: dict[int, ResolvedEntity] = {}
    with connection() as conn, conn.cursor() as cur:
        # 1) TAM eşleşme. "Mehmet Şimşek" gibi çok sözcüklü adlar
        #    parçalanınca yanlış varlığa çarpar.
        cur.execute(
            "SELECT id, canonical_name, entity_type FROM entities "
            "WHERE lower(canonical_name) = lower(%s) LIMIT %s",
            (question.strip(), limit),
        )
        for r in cur.fetchall():
            bulunan[int(r["id"])] = ResolvedEntity(
                int(r["id"]), r["canonical_name"], r["entity_type"], "exact", question.strip()
            )

        # 2) TAKMA AD. Kısaltmalar canonical adla eşleşmez: soru "TCMB"
        #    derken varlık "Türkiye Cumhuriyet Merkez Bankası"dır ve
        #    parçalı arama onu ASLA bulamaz. `aliases` sütunu tam da
        #    bunun için dolduruluyor (SPK, MGK, VDK, İŞKUR…).
        for terim in terimler:
            if len(bulunan) >= limit:
                break
            cur.execute(
                "SELECT id, canonical_name, entity_type FROM entities "
                "WHERE lower(%s) = ANY(aliases) LIMIT %s",
                (terim, limit),
            )
            for r in cur.fetchall():
                bulunan.setdefault(
                    int(r["id"]),
                    ResolvedEntity(
                        int(r["id"]), r["canonical_name"], r["entity_type"], "alias", terim
                    ),
                )

        # 3) PARÇALI eşleşme — KELİME SINIRINDA ve kaliteye göre sıralı.
        #
        # Sınırsız `ILIKE %terim%` ölçülen bir kusur üretiyordu:
        # "TCMB faiz kararı" sorusu `'Kararı'` ve `'Kararı Resmi Gazete'`
        # varlıklarına çarpıyor, TCMB'yi ise kaçırıyordu. O iki kayıt NER
        # çöpü (tür: `person`, `is_key_entity=False`) ve 566 varlığın
        # yalnızca 14'ü anahtar işaretli — yani bayrak gerçek bir kalite
        # sinyali.
        #
        # `\m` PostgreSQL'de kelime başı çıpasıdır: "kararı" artık
        # "Kararı Resmi Gazete" içindeki baştaki sözcüğe denk gelse de
        # anahtar varlıklar önce sıralanır ve kısa/çöp adlar sona düşer.
        for terim in terimler:
            if len(bulunan) >= limit:
                break
            cur.execute(
                """
                SELECT id, canonical_name, entity_type FROM entities
                 WHERE canonical_name ~* ('\\m' || %s)
                 ORDER BY is_key_entity DESC,
                          length(canonical_name) DESC
                 LIMIT %s
                """,
                (terim, limit),
            )
            for r in cur.fetchall():
                bulunan.setdefault(
                    int(r["id"]),
                    ResolvedEntity(
                        int(r["id"]), r["canonical_name"], r["entity_type"], "partial", terim
                    ),
                )

    # Kalite sırası: tam > takma ad > parçalı. Aynı yöntemde anahtar
    # varlık önce gelir.
    oncelik = {"exact": 0, "alias": 1, "partial": 2}
    return sorted(bulunan.values(), key=lambda e: oncelik.get(e.match_method, 9))[:limit]


# ---------------------------------------------------------------------------
# 2. Graf gezinme
# ---------------------------------------------------------------------------
_TRAVERSE_SQL = """
WITH RECURSIVE seed AS (
    SELECT DISTINCT ee.event_id AS id, 0 AS depth
      FROM event_entities ee
      JOIN events e ON e.id = ee.event_id
     WHERE ee.entity_id = ANY(%s)
       AND e.merged_into_id IS NULL
     ORDER BY ee.event_id DESC
     LIMIT %s
),
gezin AS (
    SELECT id, depth FROM seed
    UNION
    SELECT k.komsu, g.depth + 1
      FROM gezin g
      JOIN (
            SELECT from_event_id AS kaynak, to_event_id   AS komsu FROM event_relations
             UNION ALL
            SELECT to_event_id   AS kaynak, from_event_id AS komsu FROM event_relations
             UNION ALL
            SELECT earlier_event_id AS kaynak, later_event_id   AS komsu
              FROM stance_shifts WHERE status = 'open'
             UNION ALL
            SELECT later_event_id   AS kaynak, earlier_event_id AS komsu
              FROM stance_shifts WHERE status = 'open'
      ) k ON k.kaynak = g.id
     WHERE g.depth < %s
)
SELECT id, min(depth) AS depth FROM gezin GROUP BY id ORDER BY depth, id DESC LIMIT %s
"""


def traverse(entity_ids: list[int], *, depth: int = MAX_DEPTH,
             max_nodes: int = MAX_NODES) -> list[tuple[int, int]]:
    """Varlıklardan başlayıp graf komşuluğunu gezer. `(olay_id, derinlik)`.

    Kenarlar İKİ YÖNLÜ okunur: bir vaadin tutulup tutulmadığı, vaatten
    sonuca da sonuçtan vaade de bakılarak bulunabilir.
    """
    if not entity_ids:
        return []
    with connection() as conn, conn.cursor() as cur:
        cur.execute(_TRAVERSE_SQL, (entity_ids, max_nodes, depth, max_nodes))
        return [(int(r["id"]), int(r["depth"])) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# 3-5. Kanıt toplama, zamansal süzme, atıf kümesi
# ---------------------------------------------------------------------------
_CITATION_SQL = """
    SELECT c.id AS claim_id, c.claim_text, c.evidence_status,
           e.id AS event_id, e.title AS event_title, e.first_reported_at,
           s.name AS source_name, s.slug AS source_slug,
           s.independence_group, a.canonical_url, a.published_at
      FROM claims c
      JOIN events e ON e.id = c.event_id
      LEFT JOIN evidence ev ON ev.claim_id = c.id
      LEFT JOIN articles a ON a.id = ev.article_id
      LEFT JOIN sources s ON s.id = a.source_id
     WHERE c.event_id = ANY(%s)
       {temporal}
     ORDER BY
       CASE c.evidence_status
         WHEN 'strongly_corroborated' THEN 0
         WHEN 'partially_corroborated' THEN 1
         WHEN 'attribution_verified' THEN 2
         WHEN 'single_source' THEN 3
         ELSE 4
       END,
       e.first_reported_at DESC
     LIMIT %s
"""


def retrieve(
    question: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    depth: int = MAX_DEPTH,
    max_citations: int = MAX_CITATIONS,
) -> RetrievalResult:
    """Soru -> atıf kümesi. Her adım deterministik, her atıf kökenli.

    ⛔ Dönen şey bir CEVAP DEĞİL, bir KANIT KÜMESİDİR. Modül hiçbir
    yorum, özet veya nedensellik iddiası üretmez.
    """
    sonuc = RetrievalResult(question=question)

    sonuc.entities = resolve_entities(question)
    if not sonuc.entities:
        sonuc.notes.append("Soruda kayıtlı bir varlık bulunamadı — atıf kümesi boş.")
        return sonuc

    dugumler = traverse([e.entity_id for e in sonuc.entities], depth=depth)
    if not dugumler:
        sonuc.notes.append("Varlık çözümlendi ama bağlı olay yok.")
        return sonuc

    derinlik = dict(dugumler)
    sonuc.traversed_event_ids = [i for i, _ in dugumler]
    sonuc.seed_event_ids = [i for i, d in dugumler if d == 0]

    zaman = ""
    params: list[Any] = [sonuc.traversed_event_ids]
    if since is not None:
        zaman += " AND e.first_reported_at >= %s"
        params.append(since)
    if until is not None:
        zaman += " AND e.first_reported_at <= %s"
        params.append(until)
    params.append(max_citations)

    with connection() as conn, conn.cursor() as cur:
        cur.execute(_CITATION_SQL.format(temporal=zaman), params)  # noqa: S608 — `zaman` sabit
        satirlar = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT id FROM stance_shifts WHERE status = 'open' "
            "AND (earlier_event_id = ANY(%s) OR later_event_id = ANY(%s))",
            (sonuc.traversed_event_ids, sonuc.traversed_event_ids),
        )
        sonuc.stance_shift_ids = [int(r["id"]) for r in cur.fetchall()]

    gruplar: set[str] = set()
    for r in satirlar:
        if r.get("independence_group"):
            gruplar.add(str(r["independence_group"]))
        sonuc.citations.append(
            Citation(
                claim_id=int(r["claim_id"]),
                claim_text=str(r["claim_text"]),
                evidence_status=str(r["evidence_status"]),
                event_id=int(r["event_id"]),
                event_title=str(r["event_title"]),
                source_name=str(r["source_name"] or "—"),
                source_slug=str(r["source_slug"] or "—"),
                independence_group=r.get("independence_group"),
                article_url=r.get("canonical_url"),
                published_at=r.get("published_at") or r.get("first_reported_at"),
                depth=derinlik.get(int(r["event_id"]), 0),
            )
        )

    sonuc.independence_groups = sorted(gruplar)

    # Bağımsızlık, atıf kümesinin en önemli niteliğidir ve GİZLENMEZ:
    # 12 atıfın tek gruptan gelmesi ile dört gruptan gelmesi çok farklı
    # şeylerdir (Spec §8.2). Tek opak "güven" sayısına çevrilmez.
    if len(sonuc.independence_groups) <= 1:
        sonuc.notes.append(
            "Atıflar tek bağımsızlık grubundan geliyor — çapraz teyit yok."
        )

    log.info(
        "graph_retrieval_complete",
        entities=len(sonuc.entities),
        nodes=len(sonuc.traversed_event_ids),
        citations=len(sonuc.citations),
        groups=len(sonuc.independence_groups),
    )
    return sonuc
