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

from politikdesk.nlp.claims import fold_text
from politikdesk.political_memory.service import ActorMemory

ShiftType = Literal[
    "reversal",            # 180° Tutum değişikliği / Zıt beyan
    "broken_promise",      # Tutulmayan vaat / İcraat çelişkisi
    "numeric_divergence",  # Sayısal hedef/tahmin çelişkisi veya keskin revizyon
    "policy_pivot",        # Kurumsal/politik rota değişikliği
]

# Zıtlık tespitinde kullanılan ikili kutup sözlükleri (Türkçe kökler ve deyimler)
_POLARITY_PAIRS_RAW: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        (
            "artırılmalı",
            "artacak",
            "yükselecek",
            "artış",
            "sıkılaşma",
            "sıkılaştırma",
            "faiz artırımı",
        ),
        (
            "indirilmeli",
            "düşecek",
            "azalacak",
            "düşüş",
            "gevşeme",
            "faiz indirimi",
            "parasal gevşeme",
        ),
    ),
    (
        ("destekliyoruz", "onaylıyoruz", "yanındayız", "kabul ediyoruz"),
        ("karşıyız", "reddediyoruz", "kabul edilemez", "itiraz ediyoruz"),
    ),
    (
        ("yasaklanmalı", "kapatılmalı", "engellenmeli", "cezalandırılmalı"),
        ("serbest olmalı", "açılmalı", "açılması", "desteklenmeli", "teşvik edilmeli"),
    ),
    (
        ("asla olmaz", "kesinlikle olmaz", "mümkün değil", "kırmızı çizgi", "kırmızı çizgimiz"),
        ("müzakere edilebilir", "anlaşma sağlandı", "mutabakat sağlandı", "mümkündür"),
    ),
)

# Kavramların insan okunur adı. Sıra `_POLARITY_PAIRS_RAW` ile birebir.
# ⛔ Eskiden eşleşen kavram atılıp yerine sabit "Politika / Tutum Beyanı"
# yazılıyordu; 50 kaydın 50'si aynı konuyu gösteriyordu.
CONCEPT_LABELS: tuple[str, ...] = (
    "Para politikası (faiz yönü)",
    "Genel destek / karşıtlık",
    "Yasak / serbestlik",
    "Kesin ret / müzakere",
)

# Kavramın KONUSAL ağırlığı. Para politikası bir konuyu adlandırır;
# "destekliyoruz / karşıyız" özneden bağımsız bir duruş fiilidir ve tek
# başına neyin desteklendiğini söylemez. Ölçüm: eski çıktıdaki 67
# kaymanın 53'ü (%79,1) bu içeriksiz fiillerden geliyordu.
CONCEPT_SPECIFICITY: tuple[float, ...] = (0.90, 0.55, 0.55, 0.60)

# Konu örtüşmesi eşiği (Jaccard). Ölçüm gerekçesi `detect` içinde.
MIN_TOPIC_OVERLAP: float = 0.5

# Bir "U dönüşü" iddiası için asgari süre. Saatler içinde görüş
# değişmez; eski çıktıda 17 kayma aynı gün içindeydi.
MIN_DAYS_FOR_REVERSAL: int = 7

MAX_CONFIDENCE: float = 0.95


def _topic_overlap(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """İki olayın konu kümesi Jaccard benzerliği. Etiket yoksa 0."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        # Etiket yokluğu örtüşme KANITI değildir. 1.0 dönmek, konusu
        # bilinmeyen her çifti "aynı konu" saymak olurdu.
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _confidence(concept_index: int, topic_overlap: float, days: int) -> float:
    """Kayma güveni — GİRDİYE GÖRE DEĞİŞİR.

    ⛔ Eskiden bu değer sabit 0,85'ti. Hep aynı olan bir güven skoru bir
    güven skoru değildir; ölçülmüş gibi görünen bir sabittir (ADR-010 §1).

    Üç bileşen: kavramın konusal özgüllüğü, konu örtüşmesinin gücü ve
    beyanlar arasındaki sürenin makullüğü. Üçü de yükseldikçe iddia
    güçlenir.
    """
    ozgulluk = CONCEPT_SPECIFICITY[concept_index]
    # Eşiğin (0,5) üstündeki örtüşme 0..1 aralığına yayılır.
    ortusme = (topic_overlap - MIN_TOPIC_OVERLAP) / (1.0 - MIN_TOPIC_OVERLAP)
    # 7 günden 180 güne doğru artan, sonra sabitlenen bir katkı.
    sure = min(1.0, (days - MIN_DAYS_FOR_REVERSAL) / 173.0)
    ham = 0.45 * ozgulluk + 0.35 * ortusme + 0.20 * sure
    return round(min(MAX_CONFIDENCE, ham), 3)


POLARITY_PAIRS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = tuple(
    (
        tuple(sorted((fold_text(w) for w in pos), key=len, reverse=True)),
        tuple(sorted((fold_text(w) for w in neg), key=len, reverse=True)),
    )
    for pos, neg in _POLARITY_PAIRS_RAW
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


def _calc_days_between(date_str1: str | None, date_str2: str | None) -> int:
    if not date_str1 or not date_str2:
        return 0
    try:
        d1 = datetime.fromisoformat(str(date_str1).replace("Z", "+00:00")).date()
        d2 = datetime.fromisoformat(str(date_str2).replace("Z", "+00:00")).date()
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


_TURKISH_VERBAL_NEGATION_RE = re.compile(
    r"(?:mamal[ıi]|memel[ıi]|mamas[ıi]|memes[ıi]|mayacag|meyece[gk]|maz|mez|m[ıiuü]yor|mad[ıi]|med[ıi]|mam[ıi]s|mem[ıi]s|may[ıi]p|mey[ıi]p)"
)


def _has_morphological_negation(concept_stem: str, text: str) -> bool:
    """Türkçe fiil kökünün olumsuzluk eki alıp almadığını kontrol eder.

    Örn: 'art' / 'artır' kökü -> 'artırmayacağız', 'artmayacak', 'artmadı'.
    """
    stem_norm = fold_text(concept_stem).strip()
    text_norm = fold_text(text)

    words = text_norm.split()
    for w in words:
        if stem_norm in w:
            idx = w.find(stem_norm)
            after_stem = w[idx + len(stem_norm):]
            if _TURKISH_VERBAL_NEGATION_RE.search(after_stem):
                return True
    return False


def _matches_concept(concept: str, text_folded: str) -> tuple[bool, bool]:
    """Kavramın metinde geçip geçmediğini ve morfolojik olarak
    olumsuzlanıp olumsuzlanmadığını döner.
    """
    c_folded = fold_text(concept)
    if " " in c_folded:
        if c_folded in text_folded:
            return True, False
        return False, False

    sentential_neg = any(
        neg in text_folded
        for neg in ("olmayacak", "olmaz", "yapilmayacak", "edilmeyecek", "degil", "yok")
    )

    if c_folded in text_folded:
        is_neg = _has_morphological_negation(c_folded, text_folded) or sentential_neg
        return True, is_neg

    c_stem = c_folded[:4] if len(c_folded) >= 4 else c_folded
    words = text_folded.split()
    for w in words:
        if len(w) >= len(c_stem) and w.startswith(c_stem):
            is_neg = _has_morphological_negation(c_stem, text_folded) or sentential_neg
            return True, is_neg

    return False, False


def _evaluate_text_polarity(
    text_folded: str,
    pos_set: tuple[str, ...] | frozenset[str],
    neg_set: tuple[str, ...] | frozenset[str],
) -> str | None:
    """Bir metnin kavram çiftine göre kutbunu (pos/neg) morfoloji duyarlı olarak çıkarır."""
    has_pos_kw = False
    pos_negated = False
    for p in pos_set:
        matched, is_neg = _matches_concept(p, text_folded)
        if matched:
            has_pos_kw = True
            if is_neg:
                pos_negated = True
            break

    has_neg_kw = False
    neg_negated = False
    for n in neg_set:
        matched, is_neg = _matches_concept(n, text_folded)
        if matched:
            has_neg_kw = True
            if is_neg:
                neg_negated = True
            break

    if has_pos_kw and pos_negated:
        return "neg"
    if has_neg_kw and neg_negated:
        return "pos"

    if has_pos_kw and not has_neg_kw:
        return "pos"
    if has_neg_kw and not has_pos_kw:
        return "neg"

    return None


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

    # Kutup vektörü ve metrik ayrıştırması KAYIT BAŞINA hesaplanır, çift
    # başına değil. Bunlar bir kaydın kendi özellikleridir; ikinci kaydın
    # ne olduğuna bağlı değildir.
    #
    # Neden önemli: aşağıdaki tarama O(n²) çifttir. Ön hesap olmadan aynı
    # kaydın metni n kez foldlanıyor, kutbu n × kavram-çifti kez yeniden
    # çıkarılıyordu. 100 kayıt ve 10 kavram çiftinde 100.000 değerlendirme
    # yerine 1.000 yeter. Ölçülen etki: `/api/memory/stance-shifts`
    # 5,2 sn → 0,3 sn (aynı çıktı; bu bir davranış değişikliği değil,
    # yalnızca tekrarın kaldırılmasıdır).
    folded_texts = [fold_text(e.claim_text) for e in sorted_entries]
    polarity_vectors = [
        tuple(
            _evaluate_text_polarity(folded, pos_set, neg_set)
            for pos_set, neg_set in POLARITY_PAIRS
        )
        for folded in folded_texts
    ]
    metric_values = [_extract_metric_and_value(e.claim_text) for e in sorted_entries]

    for i in range(len(sorted_entries)):
        e1 = sorted_entries[i]

        # ⛔ KAPI 1 — ATIF SAĞLAMLIĞI (ADR-010 §5/2)
        #
        # Beyan gerçekten bu aktöre ait olmalı. "Aynı olayda adı geçiyor"
        # yetmez: eski davranış buydu ve Cumhurbaşkanlığı'na Bahçeli'nin
        # sözünün atfedilmesinin sebebi tam olarak buydu.
        if e1.attribution_strength != "strong":
            continue

        for j in range(i + 1, len(sorted_entries)):
            e2 = sorted_entries[j]
            if e2.attribution_strength != "strong":
                continue
            if e1.event_id == e2.event_id:
                continue

            pair = (e1.event_id, e2.event_id)
            if pair in seen_pairs:
                continue

            # ⛔ KAPI 2 — KONU ÖRTÜŞMESİ (ADR-010 §5/1)
            #
            # Farklı konulardaki iki beyan "fikir değiştirdi" sayılamaz.
            # Ölçüm: rastgele bir olay çiftinde ≥1 ortak etiket bulunma
            # oranı %29,5 — yani "en az bir ortak etiket" zayıf bir
            # kapıdır. Jaccard ≥ 0,5'te bu oran %17,5'e iniyor. Olay
            # başına medyan etiket sayısı 1 olduğu için eşik, yaygın
            # durumda "tam aynı konu" demeye gelir.
            ortak = _topic_overlap(e1.topic_tags, e2.topic_tags)
            if ortak < MIN_TOPIC_OVERLAP:
                continue

            days = _calc_days_between(e1.first_reported_at, e2.first_reported_at)

            # ⛔ KAPI 3 — ZAMAN (ADR-010 §5/5)
            #
            # Saatler içinde "U dönüşü" olmaz. Eski çıktıda 67 kaymanın
            # 17'si aynı gün içindeydi; bunlar bir görüş değişikliği
            # değil, çoğunlukla iki ayrı konuydu.
            if days < MIN_DAYS_FOR_REVERSAL:
                continue

            for k, (pol1, pol2) in enumerate(
                zip(polarity_vectors[i], polarity_vectors[j], strict=True)
            ):
                if pol1 is not None and pol2 is not None and pol1 != pol2:
                    # ⛔ Eşleşen KAVRAM kaydedilir. Eskiden sabit
                    # "Politika / Tutum Beyanı" yazılıyordu; hangi
                    # kavramın eşleştiği biliniyor olmasına rağmen
                    # atılıyordu ve 50 kaydın 50'si aynı konuyu
                    # gösteriyordu.
                    kavram = CONCEPT_LABELS[k]
                    guven = _confidence(k, ortak, days)
                    shifts.append(
                        StanceShift(
                            actor_name=mem.actor_name,
                            shift_type="reversal",
                            topic_or_metric=kavram,
                            earlier_event_id=e1.event_id,
                            earlier_event_title=e1.event_title,
                            earlier_claim_text=e1.claim_text,
                            earlier_date=e1.first_reported_at,
                            later_event_id=e2.event_id,
                            later_event_title=e2.event_title,
                            later_claim_text=e2.claim_text,
                            later_date=e2.first_reported_at,
                            time_span_days=days,
                            confidence=guven,
                            evidence_summary=(
                                f"'{kavram}' ekseninde zıt kutuplu iki beyan. "
                                f"Konu örtüşmesi {ortak:.2f}; arada {days} gün. "
                                f"Her iki beyan da aktöre doğrudan atfedilmiş."
                            ),
                            metadata={
                                "concept_index": k,
                                "topic_overlap": round(ortak, 3),
                                "shared_topics": sorted(
                                    set(e1.topic_tags) & set(e2.topic_tags)
                                ),
                                "earlier_speaker": e1.speaker,
                                "later_speaker": e2.speaker,
                            },
                        )
                    )
                    seen_pairs.add(pair)
                    break

            if pair in seen_pairs:
                continue

            # Sayısal Hedef / Gösterge Çelişkisi Taraması
            m1_type, v1 = metric_values[i]
            m2_type, v2 = metric_values[j]

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
