"""Söylem Değişikliği ve Zıtlık Radarı (Stance Shift & Flip-Flop Detection Engine).

Bu modül, siyasi aktörlerin geçmiş beyanları, vaatleri ve icraatları arasındaki
180° yön değişikliklerini, çelişkili açıklamalarını ve gerçekleşmeyen taahhütlerini
deterministik kurallar ve ilişki grafiği üzerinden tespit eder.

⛔ MİMARİ KURAL: Deterministiktir. LLM çağırmaz.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

from politikdesk.political_memory.service import ActorMemory

ShiftType = Literal[
    "reversal",            # 180° Tutum değişikliği / Zıt beyan
    "broken_promise",      # Tutulmayan vaat / İcraat çelişkisi
    "numeric_divergence",  # Sayısal hedef/tahmin çelişkisi veya keskin revizyon
    "policy_pivot",        # Kurumsal/politik rota değişikliği
]

# Zıtlık tespitinde kullanılan ikili kutup sözlükleri (Türkçe kökler)
POLARITY_PAIRS: tuple[tuple[frozenset[str], frozenset[str]], ...] = (
    (
        frozenset({"artirilmali", "artacak", "yukselecek", "artis", "sikilasma", "sıkı"}),
        frozenset({"indirilmeli", "dusecek", "azalacak", "dusus", "gevseme", "faiz_indirim"}),
    ),
    (
        frozenset({"destekliyoruz", "evet", "onayliyoruz", "yanindayiz", "kabul"}),
        frozenset({"karsiyiz", "hayir", "reddediyoruz", "kabul_edilemez", "itiraz"}),
    ),
    (
        frozenset({"yasaklanmali", "kapatilmali", "engellenmeli", "cezalandirilmali"}),
        frozenset({"serbest_olmali", "acilmasi", "desteklenmeli", "tesvik"}),
    ),
    (
        frozenset({"asla", "kesinlikle_olmaz", "mumkun_degil", "kirmizi_cizgi"}),
        frozenset({"olabilir", "muzakere_edilebilir", "anlasma_saglandi", "mutabakat"}),
    ),
)


@dataclass(frozen=True)
class StanceShift:
    """İki olay/iddia arasındaki tespit edilmiş söylem değişikliği."""

    actor_name: str
    shift_type: ShiftType
    topic_or_metric: str
    earlier_event_id: int
    earlier_event_title: str
    earlier_claim_text: str
    earlier_date: str
    later_event_id: int
    later_event_title: str
    later_claim_text: str
    later_date: str
    time_span_days: int
    confidence: float
    evidence_summary: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _calc_days_between(date_str1: str, date_str2: str) -> int:
    try:
        d1 = datetime.fromisoformat(date_str1.replace("Z", "+00:00")).date()
        d2 = datetime.fromisoformat(date_str2.replace("Z", "+00:00")).date()
        return abs((d2 - d1).days)
    except Exception:
        return 0


def _extract_metric_and_value(text: str) -> tuple[str | None, float | None]:
    """Basit sayısal gösterge ve değer çıkarımı (örn: '%45', '50 baz puan')."""
    pct_match = re.search(r"%\s*([0-9]+(?:[,\.][0-9]+)?)", text)
    if pct_match:
        val = float(pct_match.group(1).replace(",", "."))
        return "percentage", val
    return None, None


def detect_stance_shifts_from_memory(mem: ActorMemory) -> list[StanceShift]:
    """Bir aktörün hafıza kayıtlarından söylem değişikliklerini deterministik olarak çıkarır."""
    shifts: list[StanceShift] = []
    seen_pairs: set[tuple[int, int]] = set()

    # 1. İlişki Zincirlerinden Gelen Doğrulanmış Çelişkiler (contradicts & fails)
    for chain in mem.relation_chains:
        rel = chain.get("relation")
        from_id = chain.get("from_event_id")
        to_id = chain.get("to_event_id")
        if not from_id or not to_id:
            continue

        pair_key = (from_id, to_id)
        if pair_key in seen_pairs:
            continue

        if rel in ("contradicts", "fails"):
            shift_type: ShiftType = "broken_promise" if rel == "fails" else "reversal"
            from_title = chain.get("from_title", f"Olay #{from_id}")
            to_title = chain.get("to_title", f"Olay #{to_id}")
            payload = chain.get("evidence_payload") or {}

            shifts.append(
                StanceShift(
                    actor_name=mem.actor_name,
                    shift_type=shift_type,
                    topic_or_metric=payload.get("topic", "Genel Politika"),
                    earlier_event_id=from_id,
                    earlier_event_title=from_title,
                    earlier_claim_text=payload.get("source_claim", from_title),
                    earlier_date=chain.get("created_at", ""),
                    later_event_id=to_id,
                    later_event_title=to_title,
                    later_claim_text=payload.get("target_claim", to_title),
                    later_date="",
                    time_span_days=0,
                    confidence=float(chain.get("confidence", 0.90)),
                    evidence_summary=f"İlişki motoru deterministik çelişki tespit etti ({rel}).",
                    metadata=payload,
                )
            )
            seen_pairs.add(pair_key)

    # 2. Beyanlar ve İddialar Arası Semantik Kutup Zıtlığı Taraması
    all_entries = mem.promises + mem.attributions + mem.facts_and_numbers
    sorted_entries = sorted(all_entries, key=lambda e: e.first_reported_at or "")

    for i in range(len(sorted_entries)):
        e1 = sorted_entries[i]
        t1_lower = e1.claim_text.lower()

        for j in range(i + 1, len(sorted_entries)):
            e2 = sorted_entries[j]
            if e1.event_id == e2.event_id:
                continue

            pair = (e1.event_id, e2.event_id)
            if pair in seen_pairs:
                continue

            t2_lower = e2.claim_text.lower()
            days = _calc_days_between(e1.first_reported_at, e2.first_reported_at)

            matched_pair = False
            for pos_set, neg_set in POLARITY_PAIRS:
                has_pos_1 = any(p in t1_lower for p in pos_set)
                has_neg_1 = any(n in t1_lower for n in neg_set)
                has_pos_2 = any(p in t2_lower for p in pos_set)
                has_neg_2 = any(n in t2_lower for n in neg_set)

                if (has_pos_1 and has_neg_2) or (has_neg_1 and has_pos_2):
                    shifts.append(
                        StanceShift(
                            actor_name=mem.actor_name,
                            shift_type="reversal",
                            topic_or_metric="Politika / Tutum Beyanı",
                            earlier_event_id=e1.event_id,
                            earlier_event_title=e1.event_title,
                            earlier_claim_text=e1.claim_text,
                            earlier_date=e1.first_reported_at,
                            later_event_id=e2.event_id,
                            later_event_title=e2.event_title,
                            later_claim_text=e2.claim_text,
                            later_date=e2.first_reported_at,
                            time_span_days=days,
                            confidence=0.85,
                            evidence_summary="İki beyanda zıt kutuplu ifadeler tespit edildi.",
                        )
                    )
                    seen_pairs.add(pair)
                    matched_pair = True
                    break

            if matched_pair:
                continue

            # Sayısal Hedef / Gösterge Çelişkisi Taraması
            m1_type, v1 = _extract_metric_and_value(e1.claim_text)
            m2_type, v2 = _extract_metric_and_value(e2.claim_text)

            if m1_type and m2_type and m1_type == m2_type and v1 is not None and v2 is not None:
                diff = abs(v1 - v2)
                is_promise_pred = (
                    e1.claim_type in ("promise", "prediction")
                    or e2.claim_type in ("promise", "prediction")
                )
                if diff >= 5.0 and is_promise_pred:
                    shifts.append(
                        StanceShift(
                            actor_name=mem.actor_name,
                            shift_type="numeric_divergence",
                            topic_or_metric=f"Sayısal Gösterge ({m1_type})",
                            earlier_event_id=e1.event_id,
                            earlier_event_title=e1.event_title,
                            earlier_claim_text=e1.claim_text,
                            earlier_date=e1.first_reported_at,
                            later_event_id=e2.event_id,
                            later_event_title=e2.event_title,
                            later_claim_text=e2.claim_text,
                            later_date=e2.first_reported_at,
                            time_span_days=days,
                            confidence=0.88,
                            evidence_summary=f"Sayısal sapma ({v1} -> {v2}, fark: {diff:.1f}).",
                        )
                    )
                    seen_pairs.add(pair)

    return shifts
