"""Siyasi Hafıza — Zamansal Söylem & Beyan Karşılaştırma Matrisi (Spec v3.4 §7.3, §8.3, B-24).

Bir siyasi aktörün (veya kurumun) belirli politika başlıklarındaki geçmiş
beyanlarını, vaatlerini ve açıklamalarını farklı zaman dilimlerine göre (örn.
2023 vs 2024 vs 2026, seçim öncesi vs seçim sonrası) yan yana getirir ve
söylem tutarlılığını/değişimini analiz eder.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from politikdesk.db import connection
from politikdesk.observability import get_logger
from politikdesk.political_memory.service import get_actor_memory

log = get_logger(__name__)

# Konu bazlı anahtar kelimeler
TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "faiz": ("faiz", "tcmb", "politika faizi", "ppk", "para politikası", "sıkılaşma"),
    "enflasyon": ("enflasyon", "tüfe", "üfe", "hayat pahalılığı", "fiyat artışı"),
    "asgari_ucret": ("asgari ücret", "maaş", "zam", "emekli", "tespit komisyonu"),
    "vergi": ("vergi", "kdv", "ötv", "harç", "gelir vergisi", "bütçe geliri"),
    "anayasa": ("anayasa", "yargı", "mahkeme", "hukuk", "reform", "değişiklik"),
    "siginmaci": ("sığınmacı", "göç", "mülteci", "suriyeli", "hudut"),
    "kamu_tasarruf": ("tasarruf", "kamu harcaması", "bütçe açığı", "israf", "ödenek"),
    "dis_politika": ("dış politika", "nato", "ab", "diplomasi", "akdeniz", "antlaşma"),
}

# Polarite ve söylem tespiti için anahtar kelimeler
_SUPPORT_PATTERNS = (
    r"\b(destekliyoruz|artıracağız|düşüreceğiz|sağlayacağız|kararlıyız|hedeflenmektedir)\b",
    r"\b(kesinlikle|zorunludur|şarttır|doğrudur|olumludur|uygulanacak|başlatıldı)\b",
)
_OPPOSE_PATTERNS = (
    r"\b(karşıyız|kabul\s*edilemez|reddediyoruz|yanlıştır|vazgeçilmelidir|durdurulmalıdır)\b",
    r"\b(yetersizdir|hukuksuzdur|başarısızdır|felakettir|zararlıdır|kınıyoruz)\b",
)


@dataclass(frozen=True)
class TemporalStatement:
    """Zaman damgalı tekil siyasi beyan kaydı."""

    event_id: int
    claim_id: int
    date_str: str
    year: int | None
    claim_text: str
    speaker: str
    event_title: str
    evidence_status: str
    topic_tags: tuple[str, ...]
    stance_polarity: str  # support, oppose, neutral, promise
    source_names: tuple[str, ...] = ()
    attribution_strength: str = "strong"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StatementComparisonResult:
    """Zamansal beyan karşılaştırma analizi çıktısı."""

    actor_name: str
    topic_query: str
    earlier_period: str
    later_period: str
    earlier_statements: list[TemporalStatement] = field(default_factory=list)
    later_statements: list[TemporalStatement] = field(default_factory=list)
    undated_statements: list[TemporalStatement] = field(default_factory=list)
    shift_detected: bool = False
    shift_summary: str = ""
    shift_confidence: float = 0.0
    consistency_score: float = 1.0  # 1.0 = tam tutarlı, 0.0 = tam çelişki
    evidence_matrix: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_name": self.actor_name,
            "topic_query": self.topic_query,
            "earlier_period": self.earlier_period,
            "later_period": self.later_period,
            "earlier_statements": [s.to_dict() for s in self.earlier_statements],
            "later_statements": [s.to_dict() for s in self.later_statements],
            "undated_statements": [s.to_dict() for s in self.undated_statements],
            "shift_detected": self.shift_detected,
            "shift_summary": self.shift_summary,
            "shift_confidence": round(self.shift_confidence, 2),
            "consistency_score": round(self.consistency_score, 2),
            "evidence_matrix": self.evidence_matrix,
        }


def detect_polarity(text: str, claim_type: str = "factual") -> str:
    """Metin ve iddia türünden söylem polaritesini çıkarır."""
    if claim_type == "promise":
        return "promise"

    lowered = text.casefold()
    for pat in _OPPOSE_PATTERNS:
        if re.search(pat, lowered):
            return "oppose"
    for pat in _SUPPORT_PATTERNS:
        if re.search(pat, lowered):
            return "support"
    return "neutral"


def _parse_year(dt_str: str | None) -> int | None:
    """ISO veya tarih dizesinden geçerli yılı ayıklar (1900-2100).

    Belirsiz, boş, geçersiz veya aralık dışı tarih dizeleri için None döner.
    Tarihsiz kayıtlar varsayılan olarak cari yıla veya geleceğe yuvarlanmaz.
    """
    if not dt_str or not isinstance(dt_str, str) or not dt_str.strip():
        return None
    raw = dt_str.strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if 1900 <= dt.year <= 2100:
            return dt.year
    except Exception:  # noqa: BLE001
        pass

    match = re.search(r"\b(19\d{2}|20\d{2})\b", raw)
    if match:
        year = int(match.group(1))
        if 1900 <= year <= 2100:
            return year
    return None


def get_tracked_actors() -> list[str]:
    """Sistemde bellek kaydı veya iddiaları bulunan popüler siyasi aktörler."""
    sql = """
        SELECT DISTINCT COALESCE(speaker, canonical_name) AS actor
        FROM (
            SELECT speaker, NULL AS canonical_name
            FROM claims WHERE speaker IS NOT NULL AND speaker != ''
            UNION ALL
            SELECT NULL, canonical_name
            FROM entities WHERE entity_type IN ('person', 'institution')
        ) sub
        WHERE actor IS NOT NULL AND length(actor) > 2
        ORDER BY actor ASC
        LIMIT 100
    """
    actors: list[str] = []
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            actors = [r["actor"] for r in rows if isinstance(r, dict) and r.get("actor")]
    except Exception:  # noqa: BLE001
        actors = []

    return actors or [
        "Recep Tayyip Erdoğan",
        "Mehmet Şimşek",
        "Özgür Özel",
        "Kemal Kılıçdaroğlu",
        "Devlet Bahçeli",
        "Ali Babacan",
        "Mansur Yavaş",
        "Ekrem İmamoğlu",
        "Fatih Karahan",
    ]


def get_known_comparison_topics() -> list[dict[str, str]]:
    """Karşılaştırma için önerilen standart politika ve ekonomi başlıkları."""
    return [
        {"slug": "faiz", "title": "Faiz Politikası & TCMB Kararları"},
        {"slug": "enflasyon", "title": "Enflasyon & Hayat Pahalılığı"},
        {"slug": "asgari_ucret", "title": "Asgari Ücret & Emekli Maaşları"},
        {"slug": "vergi", "title": "Vergi Düzenlemeleri & Bütçe Gelirleri"},
        {"slug": "anayasa", "title": "Yeni Anayasa & Yargı Reformu"},
        {"slug": "siginmaci", "title": "Sığınmacılar & Göç Politikası"},
        {"slug": "kamu_tasarruf", "title": "Kamuda Tasarruf & Harcama Disiplini"},
        {"slug": "dis_politika", "title": "Dış Politika & Doğu Akdeniz"},
    ]


def compare_actor_statements(
    actor_name: str,
    *,
    topic: str | None = None,
    split_year: int = 2025,
    limit: int = 50,
) -> StatementComparisonResult:
    """Bir aktörün geçmiş beyanlarını iki zaman periyodu arasında karşılaştırır."""
    actor_name = (actor_name or "").strip()
    if not actor_name:
        return StatementComparisonResult(
            actor_name="",
            topic_query=topic or "Tüm Konular",
            earlier_period=f"{split_year} Öncesi",
            later_period=f"{split_year} ve Sonrası",
            shift_summary="Aktör adı belirtilmedi.",
        )

    actor_mem = get_actor_memory(actor_name)
    limit = max(1, min(limit, 100))
    memories = (actor_mem.promises + actor_mem.attributions + actor_mem.facts_and_numbers)[:limit]
    earlier_statements: list[TemporalStatement] = []
    later_statements: list[TemporalStatement] = []
    undated_statements: list[TemporalStatement] = []

    topic_fold = topic.casefold().strip() if topic else ""

    for m in memories:
        # Konu filtresi varsa denetle
        if topic_fold:
            matches_topic = (
                topic_fold in m.claim_text.casefold()
                or topic_fold in m.event_title.casefold()
                or any(topic_fold in t.casefold() for t in m.topic_tags)
            )
            # Standart topic keyword eşleşmesi
            if not matches_topic:
                keywords = TOPIC_KEYWORDS.get(topic_fold, ())
                matches_topic = any(kw.casefold() in m.claim_text.casefold() for kw in keywords)
            if not matches_topic:
                continue

        year = _parse_year(m.first_reported_at)
        polarity = detect_polarity(m.claim_text, m.claim_type)

        if m.first_reported_at and m.first_reported_at.strip():
            date_str = m.first_reported_at[:10]
        elif year is not None:
            date_str = str(year)
        else:
            date_str = "Bilinmiyor"

        stmt = TemporalStatement(
            event_id=m.event_id,
            claim_id=m.claim_id,
            date_str=date_str,
            year=year,
            claim_text=m.claim_text,
            speaker=m.speaker or actor_name,
            event_title=m.event_title,
            evidence_status=m.evidence_status,
            topic_tags=m.topic_tags,
            stance_polarity=polarity,
            source_names=m.source_names,
            attribution_strength=m.attribution_strength,
        )

        if year is None:
            undated_statements.append(stmt)
        elif year < split_year:
            earlier_statements.append(stmt)
        else:
            later_statements.append(stmt)

    # Sıralama: zamana göre
    earlier_statements.sort(key=lambda s: s.date_str)
    later_statements.sort(key=lambda s: s.date_str)
    undated_statements.sort(key=lambda s: s.claim_id)

    # Söylem kayması ve tutarlılık hesaplama
    shift_detected = False
    shift_summary = "İki dönem arasında belirgin bir söylem çelişkisi tespit edilmedi."
    shift_confidence = 0.0
    consistency = 1.0

    earlier_polarities = [
        s.stance_polarity for s in earlier_statements if s.stance_polarity != "neutral"
    ]
    later_polarities = [
        s.stance_polarity for s in later_statements if s.stance_polarity != "neutral"
    ]

    if earlier_polarities and later_polarities:
        has_oppose_to_support = ("oppose" in earlier_polarities and "support" in later_polarities)
        has_support_to_oppose = ("support" in earlier_polarities and "oppose" in later_polarities)
        has_promise_to_fail = ("promise" in earlier_polarities and "oppose" in later_polarities)

        if has_oppose_to_support or has_support_to_oppose or has_promise_to_fail:
            shift_detected = True
            shift_confidence = 0.85
            consistency = 0.35
            if has_oppose_to_support:
                shift_summary = (
                    f"{actor_name}, {split_year} öncesinde eleştirdiği/karşı çıktığı politikayı "
                    f"{split_year} sonrasında destekleyen veya uygulayan beyanlarda bulunmuştur."
                )
            elif has_support_to_oppose:
                shift_summary = (
                    f"{actor_name}, {split_year} öncesinde savunduğu veya vaat ettiği politikaya "
                    f"{split_year} sonrasında karşıt yönde açıklamalar yapmıştır."
                )
            else:
                shift_summary = (
                    f"{actor_name} tarafından verilen vaatlerle sonraki dönem beyanları arasında "
                    "politika eksenli ayrışma görülmektedir."
                )
        else:
            shift_confidence = 0.75
            consistency = 0.90
            shift_summary = (
                f"{actor_name} her iki zaman diliminde de tutarlı bir söylem çizgisi sürdürmüştür."
            )
    elif not earlier_statements or not later_statements:
        undated_note = f" (Tarihsiz: {len(undated_statements)} beyan)" if undated_statements else ""
        shift_summary = (
            f"Seçilen filtrelerde karşılaştırma için yeterli iki taraflı veri bulunamadı "
            f"({split_year} öncesi: {len(earlier_statements)}, "
            f"sonrası: {len(later_statements)} beyan{undated_note})."
        )

    # Kanıt matrisi tablosu
    evidence_matrix = []
    for e_stmt in earlier_statements[:5]:
        for l_stmt in later_statements[:5]:
            evidence_matrix.append({
                "earlier_date": e_stmt.date_str,
                "earlier_text": e_stmt.claim_text,
                "earlier_polarity": e_stmt.stance_polarity,
                "earlier_event_id": e_stmt.event_id,
                "later_date": l_stmt.date_str,
                "later_text": l_stmt.claim_text,
                "later_polarity": l_stmt.stance_polarity,
                "later_event_id": l_stmt.event_id,
                "aligned": e_stmt.stance_polarity == l_stmt.stance_polarity,
            })

    return StatementComparisonResult(
        actor_name=actor_name,
        topic_query=topic or "Tüm Konular",
        earlier_period=f"{split_year} Öncesi",
        later_period=f"{split_year} ve Sonrası",
        earlier_statements=earlier_statements,
        later_statements=later_statements,
        undated_statements=undated_statements,
        shift_detected=shift_detected,
        shift_summary=shift_summary,
        shift_confidence=shift_confidence,
        consistency_score=consistency,
        evidence_matrix=evidence_matrix,
    )
