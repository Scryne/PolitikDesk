"""Birleşik arama — komuta paletinin tek veri kaynağı (Roadmap Faz 8.2).

Roadmap 8.2 paletten altı nesne türünün aranmasını ister: aktör, olay,
iddia, kaynak, gösterge, ilişki. Buna yedinci olarak **sayfa** eklendi:
paletin en sık kullanımı gezinmedir ve o liste bugüne kadar JS içinde
`shell.NAV`'ın elle tutulan bir KOPYASIYDI. Kopya, sözleşmeyi ikiye
bölen şeydir; artık `NAV`'dan türetiliyor ve nav'a eklenen bir sayfa
palette kendiliğinden görünür.

### Neden tek uç, neden istemcide birleştirme yok

D-02'nin dersi şuydu: palet aktör aramasını **sessizce** hiç
göstermiyordu, çünkü JS `{actors: [...]}` sözleşmesinde olmayan iki
anahtarı okuyordu. Ne hata veriyordu ne sonuç. Her tür için ayrı uç ve
ayrı istemci kodu, o hatanın altı kopyası demekti. Tek uç + tek
sözleşme (`SearchHit`) + sözleşme testi bunu yapısal olarak kapatır.

### Kırmızı çizgiler

⛔ Kaynak sonucu **siyasi konum etiketi taşımaz** (Spec §8.5). Alt
   satırda yalnızca katman ("Resmî kaynak") ve bağımsızlık grubu yazar;
   ikisi de yayının duruşu hakkında hiçbir şey söylemez.

⛔ Olay sonucunda gündem skoru **"önem"** diye anılır, "güven" veya
   "doğruluk" diye değil (Spec §15/13).

⛔ İlişki sonuçları ADR-010 yayın kapısına tabidir. Kapı kapalıyken
   ilişki sonucu ÜRETİLMEZ — `shift_store` okuma yolunu zaten kapatıyor,
   burada ikinci kez kontrol edilmesinin sebebi bu modülün o tabloya
   kendi sorgusunu atması ve kapıyı atlayabilecek olmasıdır.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from politikdesk.db import connection
from politikdesk.observability import get_logger
from politikdesk.web.ui import format as fmt

log = get_logger(__name__)

# Tür → paletteki grup başlığı. **Sıra gösterim sırasıdır** ve rastgele
# değil: kullanıcı paleti en sık gezinmek için açar, sonra bir olayı
# aramak için. En seyrek aranan (ilişki) en altta.
KINDS: Final[tuple[tuple[str, str], ...]] = (
    ("page", "Sayfalar"),
    ("event", "Olaylar"),
    ("actor", "Aktörler"),
    ("claim", "İddialar"),
    ("indicator", "Göstergeler"),
    ("source", "Kaynaklar"),
    ("relation", "İlişkiler"),
)

KIND_LABELS: Final[dict[str, str]] = dict(KINDS)

# Tür başına tavan. Toplam tavan yerine tür başına tavan seçildi: tek bir
# tür (ör. 40 eşleşen iddia) listeyi doldurup diğer altısını ekrandan
# atamaz. Palet bir liste değil, bir AYIRIM aracıdır.
PER_KIND: Final[int] = 5

# Bu uzunluğun altında sorgu çalıştırılmaz. Tek harf, veritabanındaki
# neredeyse her satırla eşleşir; sonuç listesi değil gürültü olur.
MIN_QUERY: Final[int] = 2

# Türkçe nokta ayrımını arama için KALDIRAN eşleme.
#
# `str.casefold()` "İ"yi "i̇" (i + birleşen nokta) yapar; o dizede "iddia"
# aranırsa BULUNMAZ, çünkü araya görünmez bir karakter girer. `str.lower()`
# ise "I"yı "i" yapar ve Türkçede yanlıştır.
#
# Palette doğru davranış YÜKSEK GERİ ÇAĞIRMA'dır: kullanıcı "ılgaz" da
# yazsa "Ilgaz" da yazsa aradığını bulmalı. Bu yüzden dört harfin dördü
# de "i"ye indirgenir. Bu bir SIRALAMA kuralı değildir (orada
# `localeCompare('tr')` gerekir), yalnızca eşleştirme kuralıdır.
_FOLD: Final[dict[int, str]] = str.maketrans({"İ": "i", "I": "i", "ı": "i", "i": "i"})


def fold(text: str) -> str:
    """Arama karşılaştırması için Türkçe-güvenli küçültme."""
    return text.translate(_FOLD).lower()


@dataclass(frozen=True)
class SearchHit:
    """Paletin TEK sonuç sözleşmesi.

    `subtitle` her zaman doldurulur ve her zaman bir AYIRT EDİCİ taşır:
    iki olay aynı başlığı taşıyabilir, ikisinin tarihi ve kaynak sayısı
    aynı olmaz. Boş bir alt satır, kullanıcıyı iki sonuç arasında
    seçemez hâlde bırakır.
    """

    kind: str
    title: str
    subtitle: str
    href: str

    def as_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "group": KIND_LABELS.get(self.kind, self.kind),
            "title": self.title,
            "subtitle": self.subtitle,
            "href": self.href,
        }


# ═══════════════════════════════════════════════════════════ sayfalar


@lru_cache(maxsize=1)
def page_hits() -> tuple[SearchHit, ...]:
    """Tüm gezinme hedefleri — `shell.NAV`'dan TÜRETİLİR, kopyalanmaz.

    Hem sunucu araması hem paletin boşken gösterdiği liste buradan
    beslenir. İkisi ayrı yazılsaydı aynı ekranda iki farklı "Sayfalar"
    listesi belirebilirdi.

    Alt satır **yolun kendisidir**, grup adı değil: grup zaten başlık
    olarak yazılıyor ve onu tekrarlamak boş gürültü olurdu. Yol ise
    kullanıcıya nereye düşeceğini söyler.
    """
    from politikdesk.web.ui.shell import NAV

    return tuple(
        SearchHit("page", label, href, href)
        for _group, items in NAV
        for href, label, _icon in items
    )


def _pages(q: str) -> list[SearchHit]:
    """Sorguyla eşleşen gezinme hedefleri (`q` zaten `fold`'lanmıştır)."""
    return [hit for hit in page_hits() if q in fold(hit.title)][:PER_KIND]


# ═══════════════════════════════════════════════════════ veritabanı

_EVENTS = """
    SELECT id, title, salience_score, article_count, independent_count, last_update_at
      FROM events
     WHERE merged_into_id IS NULL
       AND title ILIKE %s
     ORDER BY salience_score DESC NULLS LAST, last_update_at DESC
     LIMIT %s
"""

_ACTORS = """
    SELECT canonical_name AS name, entity_type
      FROM entities
     WHERE entity_type IN ('person', 'institution')
       AND canonical_name ILIKE %s
     ORDER BY is_key_entity DESC, canonical_name ASC
     LIMIT %s
"""

_CLAIMS = """
    SELECT c.id, c.claim_text, c.evidence_status, c.event_id, e.title AS event_title
      FROM claims c
      JOIN events e ON e.id = c.event_id
     WHERE c.claim_text ILIKE %s
       AND e.merged_into_id IS NULL
     ORDER BY c.created_at DESC
     LIMIT %s
"""

_SOURCES = """
    SELECT name, tier, independence_group, is_active
      FROM sources
     WHERE name ILIKE %s OR slug ILIKE %s
     ORDER BY tier ASC, name ASC
     LIMIT %s
"""

_INDICATORS = """
    SELECT s.series_code, s.label, s.metric, s.unit, src.name AS source_name
      FROM indicator_series s
      LEFT JOIN sources src ON src.id = s.source_id
     WHERE s.is_active
       AND (s.label ILIKE %s OR s.metric ILIKE %s OR s.series_code ILIKE %s)
     ORDER BY s.label ASC
     LIMIT %s
"""

_RELATIONS = """
    SELECT actor_name, shift_type, topic_or_metric, later_event_id, later_date
      FROM stance_shifts
     WHERE status = 'open'
       AND (actor_name ILIKE %s OR topic_or_metric ILIKE %s)
     ORDER BY detected_at DESC
     LIMIT %s
"""

_ACTOR_KIND: Final[dict[str, str]] = {"institution": "Kurum", "person": "Siyasi aktör"}


def _db_hits(q: str) -> list[SearchHit]:
    """Altı türün tamamı — tek bağlantı, tür başına tek sorgu."""
    like = f"%{q}%"
    hits: list[SearchHit] = []

    with connection() as conn, conn.cursor() as cur:
        # ── olaylar ────────────────────────────────────────────────────
        cur.execute(_EVENTS, (like, PER_KIND))
        for row in cur.fetchall():
            # "önem" — skor bir DOĞRULUK ölçüsü değildir (Spec §15/13).
            parcalar = [f"önem {int(row['salience_score'] or 0)}"]
            if row.get("article_count"):
                parcalar.append(fmt.plural_count(int(row["article_count"]), "kaynak"))
            if row.get("independent_count"):
                parcalar.append(f"{int(row['independent_count'])} bağımsız grup")
            hits.append(
                SearchHit(
                    "event",
                    str(row["title"]),
                    " · ".join(parcalar),
                    f"/event/{int(row['id'])}",
                )
            )

        # ── aktörler ───────────────────────────────────────────────────
        cur.execute(_ACTORS, (like, PER_KIND))
        for row in cur.fetchall():
            ad = str(row["name"])
            hits.append(
                SearchHit(
                    "actor",
                    ad,
                    _ACTOR_KIND.get(str(row["entity_type"]), "Aktör"),
                    f"/hafiza/{_yol(ad)}",
                )
            )

        # ── iddialar ───────────────────────────────────────────────────
        # İddianın kendi sayfası yok; kanıtıyla birlikte olay sayfasında
        # yaşar. Oraya götürmek, "iddiayı bağlamsız göster"menin
        # alternatifidir — bu üründe iddia kanıtından ayrı gösterilmez.
        cur.execute(_CLAIMS, (like, PER_KIND))
        for row in cur.fetchall():
            from politikdesk.web.ui.components import STATUS_LABELS

            durum = STATUS_LABELS.get(str(row["evidence_status"]), str(row["evidence_status"]))
            hits.append(
                SearchHit(
                    "claim",
                    fmt.shorten(str(row["claim_text"]), 90),
                    f"{durum} · {fmt.shorten(str(row['event_title']), 44)}",
                    f"/event/{int(row['event_id'])}",
                )
            )

        # ── göstergeler ────────────────────────────────────────────────
        cur.execute(_INDICATORS, (like, like, like, PER_KIND))
        for row in cur.fetchall():
            birim = f" · {row['unit']}" if row.get("unit") else ""
            hits.append(
                SearchHit(
                    "indicator",
                    str(row["label"] or row["metric"]),
                    f"{row['source_name'] or 'kaynak yok'} · {row['series_code']}{birim}",
                    "/war-room",
                )
            )

        # ── kaynaklar ──────────────────────────────────────────────────
        # ⛔ Alt satırda YALNIZCA katman ve bağımsızlık grubu. Kaynağın
        # duruşuna dair hiçbir işaret olamaz (Spec §8.5).
        cur.execute(_SOURCES, (like, like, PER_KIND))
        for row in cur.fetchall():
            from politikdesk.web.ui.components import TIER_LABELS

            parcalar = [TIER_LABELS.get(int(row["tier"] or 4), "Kaynak")]
            if row.get("independence_group"):
                parcalar.append(f"yayın grubu: {row['independence_group']}")
            if not row.get("is_active"):
                parcalar.append("pasif")
            hits.append(
                SearchHit("source", str(row["name"]), " · ".join(parcalar), "/admin/")
            )

        # ── ilişkiler ──────────────────────────────────────────────────
        # ADR-010: kapı kapalıyken bu tablo okuma yolundan geçmez.
        from politikdesk.political_memory import shift_store

        if shift_store.PUBLISH_GATE_OPEN:
            cur.execute(_RELATIONS, (like, like, PER_KIND))
            for row in cur.fetchall():
                hits.append(
                    SearchHit(
                        "relation",
                        f"{row['actor_name']} — {row['topic_or_metric'] or 'konu yok'}",
                        f"{row['shift_type']} · {fmt.relative(row['later_date'])}",
                        f"/hafiza/{_yol(str(row['actor_name']))}",
                    )
                )

    return hits


def _yol(value: str) -> str:
    """Aktör adını URL parçasına çevirir.

    `safe=""` kritik: Türkçe adlarda nokta ve eğik çizgi geçebiliyor
    ("Prof. Dr. …"); kaçırılmazsa yol başka bir rotaya kayar.
    """
    return urllib.parse.quote(value, safe="")


# ═══════════════════════════════════════════════════════════ genel uç


def search(query: str, *, limit: int = 40) -> list[SearchHit]:
    """Yedi türde arama; grup sırası `KINDS`.

    Veritabanı erişilemezse **sayfa sonuçları yine döner**. Gerekçe:
    palet aynı zamanda gezinme aracıdır ve veritabanı düştüğünde
    kullanıcının `/admin/` sayfasına ulaşması tam da o an gerekir.
    Sessiz düşen bir palet, arızayı arıza anında gizler.
    """
    ham = query.strip()
    if len(ham) < MIN_QUERY:
        return []
    q = fold(ham)

    hits = _pages(q)
    try:
        # Veritabanı tarafında `ILIKE` kullanılır ve o, `fold`'un yaptığı
        # nokta indirgemesini YAPMAZ. Bu yüzden sorgu ham hâliyle gider:
        # `fold` "İ"yi "i"ye çevirdiği için "İBB" araması `ILIKE '%ibb%'`
        # olur ve Postgres'in Türkçe olmayan büyük/küçük eşlemesinde
        # "İBB" ile eşleşmezdi.
        hits += _db_hits(ham)
    except Exception as exc:  # noqa: BLE001
        log.warning("search_db_unavailable", error=str(exc), query_len=len(q))

    sira = {kind: i for i, (kind, _) in enumerate(KINDS)}
    hits.sort(key=lambda hit: sira.get(hit.kind, len(sira)))
    return hits[:limit]
