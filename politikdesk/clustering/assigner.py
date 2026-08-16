"""Olay kümeleme algoritması v1 (F2-01, Spec §11.4).

DoD: Aday getirme + benzerlik + zaman/varlık kısıtı uygulanıyor; yeni olay
yaratma çalışıyor.

**Tasarım kararı: karar mantığı saftır.** `decide()` veritabanına dokunmaz;
girdisi hazır özellik nesneleri, çıktısı bir `Assignment`. Sebep: Spec §18'e
göre kümeleme projenin en riskli bileşenidir ve G2 kapısı sayısal olarak
ölçülür (F2-16). Karar mantığı DB'ye bağlı olsaydı, her eşik denemesi için
veritabanı kurmak gerekirdi ve F2-14 (eşik kalibrasyonu) pratikte
koşulamazdı.

**Kararın şeffaflığı (P4).** `Assignment.trace` her adayın neden elendiğini
taşır. "Neden bu olaya atanmadı?" sorusunun cevabı admin panelinde
görünmelidir; sessiz eleme, yanlış kümelemenin teşhisini imkânsız kılar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from politikdesk.clustering.indicators import indicators_conflict
from politikdesk.clustering.numeric_guard import NumericConflict, find_conflicts
from politikdesk.nlp.entities import jaccard

Action = Literal["assign", "review", "create"]
EntityVerdict = Literal["ok", "inconclusive", "reject"]

# Spec §11.4 varsayılanları. T_HIGH/T_LOW config'ten gelir (D20, F2-14).
DEFAULT_TIME_WINDOW_HOURS = 72
DEFAULT_JACCARD_MIN = 0.25
DEFAULT_CANDIDATE_LIMIT = 20
DEFAULT_CANDIDATE_WINDOW_HOURS = 96


@dataclass(frozen=True)
class Thresholds:
    """Kümeleme eşikleri ve kısıtları.

    `t_high`/`t_low` D20'ye aittir ve F2-14'te Golden Set üzerinde kalibre
    edilir; buradaki varsayılanlar Spec §11.4'ün tahminleridir.
    """

    t_high: float = 0.86
    t_low: float = 0.78
    time_window_hours: int = DEFAULT_TIME_WINDOW_HOURS
    jaccard_min: float = DEFAULT_JACCARD_MIN

    def __post_init__(self) -> None:
        if not 0 <= self.t_low < self.t_high <= 1:
            raise ValueError("0 <= t_low < t_high <= 1 olmalı (Spec §11.4).")


@dataclass(frozen=True)
class ArticleFeatures:
    """Kümelenecek makalenin kümeleme için gereken özellikleri."""

    article_id: int
    embedding: list[float]
    entities: frozenset[str]
    key_entities: frozenset[str]
    published_at: datetime
    text: str = ""  # sayısal çelişki kontrolü için (F2-03)
    vertical: str = "macro_economy"


@dataclass(frozen=True)
class EventCandidate:
    """ANN sorgusundan dönen aday olay."""

    event_id: int
    similarity: float  # cosine(article.embedding, event.centroid)
    entities: frozenset[str]
    key_entities: frozenset[str]
    last_update_at: datetime
    text_sample: str = ""  # olayın temsilci metni (sayısal kontrol için)


@dataclass(frozen=True)
class CandidateTrace:
    """Bir adayın neden kazandığı/elendiği (P4 şeffaflığı)."""

    event_id: int
    similarity: float
    time_ok: bool
    entity_verdict: EntityVerdict
    entity_jaccard: float
    shared_key_entities: tuple[str, ...]
    outcome: Literal[
        "accepted",
        "review",
        "below_t_low",
        "time_reject",
        "entity_reject",
        "entity_unverified",
        "indicator_reject",
    ]
    indicator_conflict: bool = False

    @property
    def entity_ok(self) -> bool:
        return self.entity_verdict == "ok"


@dataclass(frozen=True)
class Assignment:
    """Kümeleme kararı."""

    action: Action
    event_id: int | None = None
    similarity: float | None = None
    needs_review: bool = False
    review_reason: str | None = None
    numeric_conflicts: tuple[NumericConflict, ...] = ()
    trace: tuple[CandidateTrace, ...] = field(default=())

    @property
    def creates_event(self) -> bool:
        return self.action == "create"


def _time_ok(article: ArticleFeatures, cand: EventCandidate, hours: int) -> bool:
    """Spec §11.4: |article.published_at - event.last_update_at| <= 72h.

    Mutlak fark kullanılır: geç toplanan eski bir makale de, olaydan sonra
    gelen bir makale de aynı pencereye tabidir.
    """
    return abs(article.published_at - cand.last_update_at) <= timedelta(hours=hours)


def _entity_check(
    article: ArticleFeatures, cand: EventCandidate, jaccard_min: float
) -> tuple[EntityVerdict, float, tuple[str, ...]]:
    """Spec §11.4: jaccard >= 0.25 VEYA en az 1 ortak anahtar varlık.

    "VEYA" bilinçlidir: TCMB'nin kısa bir duyurusu ile onu işleyen uzun bir
    haberin varlık kümeleri boyut olarak çok farklıdır ve Jaccard düşük
    çıkar; ortak anahtar varlık (TCMB) bağın kendisidir.

    **Üçüncü sonuç: `inconclusive`.** Spec §11.4 kısıtı boş varlık kümesi
    durumunu tanımlamıyor ve harfiyen uygulandığında `jaccard(∅, ∅) = 0`
    olduğu için kısıt **reddeder**. Bu, varlık çıkarımının tanımadığı
    makaleleri sonsuza dek tek başına bırakır: ilk canlı koşumda 11
    makalenin 6'sında hiç varlık yoktu ve 0,9997 benzerlikli iki makale
    (aynı olay) yalnızca bu yüzden ayrı düştü.

    Boş küme **çelişki kanıtı değil, kanıt yokluğudur.** Bu yüzden en az bir
    taraf boşsa kısıt "uygulanamadı" sayılır. Precision önceliği korunur:
    uygulanamayan kısıt, `decide()` içinde otomatik atama hakkı vermez —
    yalnızca T_HIGH üstünde ve **insan denetimiyle** atama yapılır.
    """
    score = jaccard(article.entities, cand.entities)
    shared_key = tuple(sorted(article.key_entities & cand.key_entities))

    if shared_key or score >= jaccard_min:
        return "ok", score, shared_key
    if not article.entities or not cand.entities:
        return "inconclusive", score, shared_key
    return "reject", score, shared_key


def decide(
    article: ArticleFeatures,
    candidates: list[EventCandidate],
    thresholds: Thresholds | None = None,
) -> Assignment:
    """Bir makaleyi aday olaylardan birine atar ya da yeni olay yaratır.

    Sıra (Spec §11.4):
      1. Kısıtlar (zaman, varlık, gösterge) — benzerlik tek başına yetmez
      2. sim >= T_HIGH  -> otomatik atama
      3. sim >= T_LOW   -> geçici atama + insan denetim kuyruğu
      4. hiçbiri        -> yeni olay
      5. Sayısal çelişki (F2-03) -> atama korunur, `needs_review` işaretlenir

    **Gösterge kısıtı (B-62)** bir *reddetme*dir, bayrak değil: sanayi
    üretimi ile dış ticaret endeksi aynı olay değildir, benzerlikleri ne
    olursa olsun. Sayısal çelişkiden farkı budur — orada hangi değerin
    doğru olduğu bilinmez (insan bakar), burada iki konunun ayrı olduğu
    kesindir.

    Varlık kısıtı uygulanamıyorsa (bir taraf varlıksız) atama yalnızca
    T_HIGH üstünde ve **denetim kuyruğuyla** yapılır — bkz. `_entity_check`.
    """
    th = thresholds or Thresholds()

    traces: list[CandidateTrace] = []
    best_high: EventCandidate | None = None
    best_low: EventCandidate | None = None
    best_unverified: EventCandidate | None = None

    for cand in candidates:
        time_ok = _time_ok(article, cand, th.time_window_hours)
        verdict, score, shared_key = _entity_check(article, cand, th.jaccard_min)
        # B-62: aynı kurumun aynı gün yayımladığı FARKLI gösterge ayrı
        # olaydır. Bu bir benzerlik sorunu değil konu sorunudur; bu yüzden
        # eşiklerden ÖNCE, bir kısıt olarak uygulanır.
        indicator_clash = indicators_conflict(article.text, cand.text_sample)

        if not time_ok:
            outcome: str = "time_reject"
        elif verdict == "reject":
            outcome = "entity_reject"
        elif indicator_clash:
            outcome = "indicator_reject"
        elif verdict == "inconclusive":
            # Kısıt doğrulanamadı: yalnızca T_HIGH üstünde ve insan onayıyla.
            if cand.similarity >= th.t_high:
                outcome = "entity_unverified"
                if best_unverified is None or cand.similarity > best_unverified.similarity:
                    best_unverified = cand
            else:
                outcome = "below_t_low"
        elif cand.similarity >= th.t_high:
            outcome = "accepted"
            if best_high is None or cand.similarity > best_high.similarity:
                best_high = cand
        elif cand.similarity >= th.t_low:
            outcome = "review"
            if best_low is None or cand.similarity > best_low.similarity:
                best_low = cand
        else:
            outcome = "below_t_low"

        traces.append(
            CandidateTrace(
                event_id=cand.event_id,
                similarity=cand.similarity,
                time_ok=time_ok,
                entity_verdict=verdict,
                entity_jaccard=score,
                shared_key_entities=shared_key,
                outcome=outcome,  # type: ignore[arg-type]
                indicator_conflict=indicator_clash,
            )
        )

    chosen = best_high or best_low or best_unverified
    if chosen is None:
        return Assignment(action="create", trace=tuple(traces))

    conflicts = tuple(find_conflicts(article.text, chosen.text_sample))

    if best_high is not None and not conflicts:
        return Assignment(
            action="assign",
            event_id=chosen.event_id,
            similarity=chosen.similarity,
            trace=tuple(traces),
        )

    if conflicts:
        reason = "numeric_conflict"
    elif best_low is not None:
        reason = f"similarity_between_thresholds({th.t_low}<=sim<{th.t_high})"
    else:
        reason = "entity_constraint_unverifiable"
    return Assignment(
        action="review",
        event_id=chosen.event_id,
        similarity=chosen.similarity,
        needs_review=True,
        review_reason=reason,
        numeric_conflicts=conflicts,
        trace=tuple(traces),
    )
