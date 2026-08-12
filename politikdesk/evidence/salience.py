"""Gündem skoru — salience (F2-15 · Spec v3.1 §8.4).

DoD: Formül uygulanıyor; kırılım şeffaf; **engagement girdisi yok** (test).

Skor **bir doğruluk göstergesi değildir** — yalnızca sıralama içindir ve
UI'da bu açıkça belirtilir (Spec §8.4).

## v3.1'in ayrımı

| Parça | Aralık | Saklanır mı |
|---|---|---|
| Global salience | 0–90 | ✅ `events.salience_score` |
| Kişisel ayarlama | 0–10 | ❌ sorgu anında hesaplanır |
| Gösterilen skor | 0–100 | ❌ türetilir |

Ayrım kozmetik değildir: `events.salience_score` olay başına **tek**
sütundur; iki kullanıcının farklı konu öncelikleri tek sütunda saklanamaz
(İtiraz-7). `migrations/0003` üst sınırı 90'a çekerek bunu veritabanı
seviyesinde zorlar — kişisel bileşeni bu sütuna yazan bir kod yolu
`CheckViolation` alır.

## Engagement yasağı

Formülde beğeni, paylaşım, tıklanma **yoktur** ve olmayacaktır. Spec §13.3:
"`daily_active_minutes`'ın düşük olması hedeftir; bu metriği yukarı çekmeye
çalışan hiçbir özellik kabul edilmez." Etkileşimi salience'a sokmak, ürünü
tam da kaçındığı şeye — popülerlik sıralayıcısına — çevirirdi.
`tests/test_evidence.py` bu yasağı modül kaynağı üzerinde denetler.

⛔ Bu modül `politikdesk.llm` import EDEMEZ (Spec §11.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

GLOBAL_MAX = 90       # migrations/0003: events_salience_global_range
PERSONAL_MAX = 10

# Spec §8.4 ağırlıkları (ilk beş bileşen — toplam 90)
W_INDEPENDENT = 25
W_PRIMARY = 20
W_VELOCITY = 20
W_TIER = 15
W_ENTITY = 10

NORM_INDEPENDENT_MAX = 8    # norm(bagimsiz_kaynak_sayisi, 0, 8)
NORM_VELOCITY_MAX = 10      # ilk 60 dk içindeki makale sayısı

TIER_WEIGHTS = {1: 1.0, 2: 0.8, 3: 0.5, 4: 0.2}

PENALTY_WEAK_AND_STALE = 15
PENALTY_DUPLICATE_SUSPECT = 10
STALE_AFTER = timedelta(hours=6)

WEAK_STATUSES = frozenset({"unverified", "single_source"})


def _norm(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


@dataclass(frozen=True)
class EventSignals:
    """Global salience'ın girdileri — hepsi olayın kendi özellikleri.

    Hiçbiri kullanıcıya ait değildir; bu yüzden sonuç önbelleklenebilir.
    """

    independent_count: int
    has_primary_source: bool
    articles_in_first_hour: int
    best_tier: int                      # en yüksek katman: 1 en güçlü
    has_key_entity: bool
    evidence_status: str
    first_reported_at: datetime
    now: datetime = field(default_factory=lambda: datetime.now(UTC))
    duplicate_suspect: bool = False


@dataclass(frozen=True)
class SalienceBreakdown:
    """`events.salience_breakdown` alanına yazılan şeffaflık kaydı (P4).

    Kişisel bileşen **buraya yazılmaz**: saklanan alan kullanıcıdan
    bağımsız kalmalıdır.
    """

    score: int
    components: dict[str, float]
    penalties: dict[str, int]

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "range": [0, GLOBAL_MAX],
            "components": self.components,
            "penalties": self.penalties,
            "note": "kisisel bilesen bu alanda saklanmaz (Spec §8.4/B)",
        }


def global_salience(signals: EventSignals) -> SalienceBreakdown:
    """Spec §8.4/A — 0–90, deterministik, kullanıcıdan bağımsız."""
    components = {
        "independent_sources": W_INDEPENDENT * _norm(
            signals.independent_count, 0, NORM_INDEPENDENT_MAX
        ),
        "primary_source": float(W_PRIMARY if signals.has_primary_source else 0),
        "velocity": W_VELOCITY * _norm(
            signals.articles_in_first_hour, 0, NORM_VELOCITY_MAX
        ),
        "tier_weight": W_TIER * TIER_WEIGHTS.get(signals.best_tier, 0.0),
        "key_entity": float(W_ENTITY if signals.has_key_entity else 0),
    }

    penalties: dict[str, int] = {}
    is_stale = (signals.now - signals.first_reported_at) > STALE_AFTER
    if signals.evidence_status in WEAK_STATUSES and is_stale:
        penalties["weak_evidence_and_stale"] = PENALTY_WEAK_AND_STALE
    if signals.duplicate_suspect:
        penalties["duplicate_suspect"] = PENALTY_DUPLICATE_SUSPECT

    raw = sum(components.values()) - sum(penalties.values())
    score = max(0, min(GLOBAL_MAX, round(raw)))

    return SalienceBreakdown(
        score=score,
        components={k: round(v, 2) for k, v in components.items()},
        penalties=penalties,
    )


def personal_adjustment(
    event_topics: list[str] | frozenset[str],
    topic_priorities: list[str] | frozenset[str],
) -> int:
    """Spec §8.4/B — 0–10, SAKLANMAZ, feed sorgusunda hesaplanır.

    Örtüşme oranı, kullanıcının önceliklerine göre ölçülür: kullanıcı 3 konu
    seçtiyse ve olay 2'siyle eşleşiyorsa 2/3'tür. Olayın etiket sayısına
    bölmek, çok etiketli olayları haksız yere cezalandırırdı.
    """
    priorities = frozenset(topic_priorities)
    if not priorities:
        return 0
    overlap = len(frozenset(event_topics) & priorities) / len(priorities)
    return round(PERSONAL_MAX * overlap)


def displayed_score(global_score: int, personal: int) -> int:
    """Spec §8.4/C — UI'da gösterilen skor (0–100)."""
    return global_score + personal


def explain(global_breakdown: SalienceBreakdown, personal: int) -> dict:
    """UI popover'ı: iki blok, ayrı satırlar (P4 şeffaflığı)."""
    return {
        "displayed_score": displayed_score(global_breakdown.score, personal),
        "global": global_breakdown.as_dict(),
        "personal": {
            "score": personal,
            "range": [0, PERSONAL_MAX],
            "reason": "konu önceliklerinizle eşleşme",
        },
    }
