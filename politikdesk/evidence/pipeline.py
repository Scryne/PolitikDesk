"""Kanıt durumu ve salience hesaplama turu (F2-12, F2-13, F2-15 orkestrasyonu).

Spec §11.3 adım 7: bağımsız sayım → R0–R7 → `evidence_status` +
`status_reason`, ardından olay skoru.

⛔ Bu modül `politikdesk.llm` import EDEMEZ (Spec §11.2). Yalnızca
veritabanından okur, deterministik hesaplar, geri yazar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from politikdesk.db import connection
from politikdesk.evidence.independence import EvidenceArticle
from politikdesk.evidence.rules import Claim, Evidence, compute_status, engine_version
from politikdesk.evidence.salience import EventSignals, global_salience
from politikdesk.observability import get_logger

log = get_logger(__name__)

VELOCITY_WINDOW_MINUTES = 60  # Spec §8.4: "ilk 60 dk içindeki makale sayısı"


@dataclass
class EvidenceStats:
    claims_scored: int = 0
    events_scored: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "claims_scored": self.claims_scored,
            "events_scored": self.events_scored,
            "errors": self.errors,
        }


def _parse_vector(literal: str | None) -> list[float]:
    if not literal:
        return []
    return [float(x) for x in literal.strip("[]").split(",") if x]


def _verified_against_official(
    cur: Any, claim_id: int, normalized_value: dict[str, Any] | None
) -> bool:
    """İddianın sayısı, kurumun KENDİ yayınındaki sayıyla aynı mı (F5-19).

    R3 (Spec §8.3) tek kaynağa 🟢 verir — ürünün en güçlü etiketi. Bu
    yüzden doğrulama gerçek olmak zorundadır, lastik damga değil.

    Burada iki BAĞIMSIZ yol karşılaştırılır:
      1. kurumun makine okunur yayını (`articles.official_value`,
         TÜİK SDMX'ten geldiği gibi)
      2. modelin makale metninden çıkardığı `normalized_value`

    İkisi `metric`, `value` ve `period` alanlarının ÜÇÜNDE de buluşuyorsa
    bayrak kalkar. Kısmi eşleşme yetmez: aynı metriğin farklı dönemi ya da
    farklı metriğin aynı değeri "doğrulama" değildir.

    Arıza geçmişi: bu bayrağı eskiden hiçbir şey yazmıyordu
    (`normalized_value.verified_against_source` okunuyordu ama iddia
    çıkarımının şeması böyle bir alan KABUL ETMİYOR — ve etmemeli,
    Spec §8.1). Yani R3 üretimde ölü koddu. Faz 5'e kadar görünmedi
    çünkü resmî sayısal kaynak yoktu (B-42).
    """
    if not normalized_value:
        return False

    metric = normalized_value.get("metric")
    period = normalized_value.get("period")
    value = normalized_value.get("value")
    if metric is None or period is None or value is None:
        return False

    cur.execute(
        """
        SELECT a.official_value
        FROM evidence ev
        JOIN articles a ON a.id = ev.article_id
        WHERE ev.claim_id = %s
          AND ev.stance = 'supports'
          AND a.official_value IS NOT NULL
        """,
        (claim_id,),
    )
    unit = normalized_value.get("unit")

    eslesenler = [
        official
        for row in cur.fetchall()
        if (official := row["official_value"] or {})
        and official.get("metric") == metric
        and official.get("period") == period
        and _same_number(official.get("value"), value)
        and _units_compatible(official.get("unit"), unit)
    ]
    if not eslesenler:
        return False

    # Belirsizlik doğrulama DEĞİLDİR (20 Ağustos 2026 denetimi).
    #
    # Bir metrik birden çok resmî SERİYE karşılık gelebilir: EVDS'te
    # `exchange_rate` altında hem `TP.DK.USD.A.YTL` hem `TP.DK.EUR.A.YTL`
    # vardır ve ikisi de aynı `unit` (TRY) ve aynı `period` ile gelir.
    # Ayıran tek alan `series_code`'dur ve iddia şemasında böyle bir alan
    # YOKTUR (LLM'e ürettirmek yeni epistemik yetki olurdu — Spec §8.1).
    #
    # İddianın değeri TEK bir seriyle eşleşiyorsa, değerin kendisi seriyi
    # belirler ve doğrulama sağlamdır. Ama İKİ farklı seriyle birden
    # eşleşiyorsa hangisinin kastedildiği bilinemez; o zaman doğrulamak,
    # rastgele birini seçmek demektir. Fail-closed davranır.
    #
    # Ölçüldü: bu kısıt bugün hiçbir doğrulamayı düşürmüyor (üretimde
    # değeri birden çok seriyle eşleşen iddia yok).
    kimlikler = {str(o.get("series_code") or "") for o in eslesenler}
    return len(kimlikler) == 1


# `TL` ve `TRY` aynı para birimidir: EVDS seri tanımı `TRY` yazar, Türkçe
# haber metni `TL` der. Bunları ayrı saymak MEŞRU bir doğrulamayı
# engellerdi. Liste bilerek kısadır — her yeni eşleme bir karardır.
_UNIT_ALIASES: dict[str, str] = {"tl": "try"}


def _normalize_unit(raw: Any) -> str | None:
    """Birimi karşılaştırılabilir biçime indirir. Yok/boş ise `None`."""
    if raw is None:
        return None
    text = str(raw).strip().casefold()
    if not text:
        return None
    return _UNIT_ALIASES.get(text, text)


def _units_compatible(official_unit: Any, claim_unit: Any) -> bool:
    """R3 birim kısıtı — İKİ TARAFTA DA birim varsa eşleşmek ZORUNDA.

    **Neden gerekli (20 Ağustos 2026 denetimi).** Karşılaştırma
    `metric` + `period` + `value` üçlüsüne bakıyordu; `unit` hiç
    okunmuyordu. Ölçüldü: `metric`, `period` ve `value` aynı iken
    `unit` `%` ↔ `kisi` olduğunda fonksiyon **`True`** dönüyordu — yani
    "yüzde 48,9" ile "48,9 kişi" aynı resmî değer sayılıyordu.

    Bugün aktif bir arıza DEĞİLDİ (ölçüldü: üretimdeki iki R3 🟢'sinin
    dört alanı da eşleşiyor ve aynı `metric`+`period`+`value` ikilisini
    farklı birimle taşıyan resmî kayıt yok). Ama yol gerçekti:

      * `other` bir yakalama-hepsi metriğidir ve **53 iddia** kullanıyor;
        bu iddiaların birimleri `TL`, `%`, `USD` diye karışıktır.
      * EVDS'in `other` ve `reserves` satırları birimi **BOŞ** bırakıyor.
      * Kapsam büyüdükçe (yeni SDMX serileri, sayım metrikleri) aynı
        `metric`+`period`+`value` üçlüsünün iki farklı birimle görünmesi
        an meselesiydi.

    **Eksik birim FAIL-OPEN bırakıldı ve bu bilinçlidir.** Gerçek veride
    `reserves` ve `other` resmî kayıtlarının birimi boştur; eksik birimde
    reddetmek, bugün doğru çalışan doğrulamaları sebepsiz kırardı.
    Kısıt "birim yoksa kontrol edilemez" der — "birim yoksa yanlıştır"
    demez. Aynı ayrım `_entity_check`'in `inconclusive` sonucunda da var.
    """
    left = _normalize_unit(official_unit)
    right = _normalize_unit(claim_unit)
    if left is None or right is None:
        return True
    return left == right


def _same_number(left: Any, right: Any) -> bool:
    """Sayısal eşitlik — kayan nokta gürültüsüne toleranslı, anlama değil.

    `48.9` ile `48.89999999999999` aynı sayıdır; `48.9` ile `49.0` değildir.
    """
    try:
        return abs(float(left) - float(right)) < 1e-6
    except (TypeError, ValueError):
        return False


def _load_evidence(cur: Any, claim_id: int) -> list[Evidence]:
    cur.execute(
        """
        SELECT ev.stance, ev.quote_span,
               a.id AS article_id, a.simhash, a.independence_key,
               a.embedding::text AS embedding, a.title, a.excerpt,
               s.slug AS source_slug, s.tier, s.kind, s.independence_group
        FROM evidence ev
        JOIN articles a ON a.id = ev.article_id
        JOIN sources s ON s.id = a.source_id
        WHERE ev.claim_id = %s
        """,
        (claim_id,),
    )
    out: list[Evidence] = []
    for r in cur.fetchall():
        out.append(
            Evidence(
                article=EvidenceArticle(
                    article_id=r["article_id"],
                    source_slug=r["source_slug"],
                    tier=r["tier"],
                    kind=r["kind"],
                    independence_group=r["independence_group"],
                    simhash=r["simhash"] or 0,
                    embedding=_parse_vector(r["embedding"]),
                    text=" ".join(filter(None, (r["title"], r["excerpt"]))),
                ),
                stance=r["stance"],
                quote_span=r["quote_span"] or "",
            )
        )
    return out


def score_claims(limit: int = 200) -> int:
    """Durumu hesaplanmamış veya bayatlamış iddiaları puanlar.

    "Bayat" ÜÇ şeyden biri olabilir ve üçü de sorulmak zorundadır:

      1. Hiç puanlanmamış (`status_reason IS NULL`)
      2. Motor sürümü değişmiş (Election Mode dahil — `engine_version()`)
      3. **Puanlamadan SONRA yeni kanıt bağı gelmiş** (F5-17)

    3. koşul eksikti ve etkisi 1. ve 2. kadar sessizdi. Durum bir kez
    hesaplandıktan sonra iddia listeden düşüyordu; oysa `evidence_status`
    kanıt kümesinin FONKSİYONUDUR ve o küme sonradan büyür. İkinci
    bağımsız kaynak bir iddiaya bağlandığında `independent_count`
    değişir ama kimse yeniden sormadığı için ekranda hâlâ 🟠
    `single_source` yazardı.

    Bu, F5-16 ile aynı yapısal körlüktür: yukarıdaki aşama durumu
    değiştiriyor, aşağıdaki aşama bunu bilmiyor. F5-16 çıkarımı, bu da
    puanlamayı yeniden tetikler; ikisi olmadan çapraz teyit veritabanında
    oluşur ama ürüne hiç yansımaz.
    """
    scored = 0
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, claim_text, claim_type, normalized_value, event_id
            FROM claims c
            WHERE status_reason IS NULL
               OR status_reason->>'engine_version' IS DISTINCT FROM %s
               OR EXISTS (
                    SELECT 1 FROM evidence ev
                    WHERE ev.claim_id = c.id
                      AND ev.created_at > (c.status_reason->>'computed_at')::timestamptz
                  )
            ORDER BY id
            LIMIT %s
            """,
            # Yürürlükteki sürüm — Election Mode açıksa "+election" eki
            # alır ve tüm iddialar yeni eşiğe göre yeniden puanlanır.
            (engine_version(), limit),
        )
        rows = list(cur.fetchall())

        BATCH_COMMIT_SIZE = 50
        for row in rows:
            evidence = _load_evidence(cur, row["id"])
            claim = Claim(
                claim_id=row["id"],
                claim_text=row["claim_text"],
                claim_type=row["claim_type"],
                normalized_value=row["normalized_value"],
                # R3, değerin kurumun KENDİ yayınıyla doğrulandığını ister.
                value_verified_against_source=_verified_against_official(
                    cur, row["id"], row["normalized_value"]
                ),
            )
            result = compute_status(claim, evidence)
            cur.execute(
                """
                UPDATE claims
                SET evidence_status = %s, status_reason = %s::jsonb, computed_at = now()
                WHERE id = %s
                """,
                (result.status, json.dumps(result.reason, ensure_ascii=False), row["id"]),
            )
            scored += 1
            if scored % BATCH_COMMIT_SIZE == 0:
                conn.commit()
        conn.commit()

    return scored


def _event_signals(cur: Any, event_id: int) -> EventSignals | None:
    cur.execute(
        """
        SELECT e.first_reported_at,
               (SELECT min(s.tier) FROM articles a JOIN sources s ON s.id = a.source_id
                 WHERE a.event_id = e.id) AS best_tier,
               (SELECT count(*) FROM articles a
                 WHERE a.event_id = e.id
                   AND COALESCE(a.published_at, a.first_seen_at)
                       <= e.first_reported_at + make_interval(mins => %s)) AS velocity,
               (SELECT count(*) > 0 FROM event_entities ee
                 JOIN entities en ON en.id = ee.entity_id
                 WHERE ee.event_id = e.id AND en.is_key_entity) AS has_key_entity,
               (SELECT bool_or(s.tier = 1) FROM articles a
                 JOIN sources s ON s.id = a.source_id WHERE a.event_id = e.id)
                 AS has_primary,
                (SELECT count(DISTINCT COALESCE(a.independence_key, s.slug))
                  FROM articles a JOIN sources s ON s.id = a.source_id
                  WHERE a.event_id = e.id) AS independent_count,
                (SELECT c.evidence_status FROM claims c WHERE c.event_id = e.id
                  ORDER BY
                    CASE c.evidence_status
                      WHEN 'unverified' THEN 0
                      WHEN 'single_source' THEN 1
                      WHEN 'contradicted' THEN 2
                      WHEN 'partially_corroborated' THEN 3
                      WHEN 'attribution_verified' THEN 4
                      WHEN 'strongly_corroborated' THEN 5
                      ELSE 6
                    END ASC, c.id ASC
                  LIMIT 1) AS weakest_status
        FROM events e WHERE e.id = %s
        """,
        (VELOCITY_WINDOW_MINUTES, event_id),
    )
    row = cur.fetchone()
    if row is None:
        return None

    return EventSignals(
        independent_count=row["independent_count"] or 0,
        has_primary_source=bool(row["has_primary"]),
        articles_in_first_hour=row["velocity"] or 0,
        best_tier=row["best_tier"] or 4,
        has_key_entity=bool(row["has_key_entity"]),
        evidence_status=row["weakest_status"] or "unverified",
        first_reported_at=row["first_reported_at"],
        now=datetime.now(UTC),
    )


def score_events(limit: int = 200) -> int:
    """Olayların global salience skorunu hesaplar ve yazar (F2-15).

    Yalnızca **global** kısım saklanır (0–90). Kişisel ayarlama feed
    sorgusunda hesaplanır ve buraya asla yazılmaz (Spec §8.4/B).
    """
    scored = 0
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM events
            WHERE merged_into_id IS NULL
            ORDER BY last_update_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        event_ids = [r["id"] for r in cur.fetchall()]

        BATCH_COMMIT_SIZE = 50
        for event_id in event_ids:
            signals = _event_signals(cur, event_id)
            if signals is None:
                continue
            breakdown = global_salience(signals)
            cur.execute(
                """
                UPDATE events
                SET salience_score = %s,
                    salience_breakdown = %s::jsonb,
                    independent_count = %s,
                    has_primary_source = %s
                WHERE id = %s
                """,
                (
                    breakdown.score,
                    json.dumps(breakdown.as_dict(), ensure_ascii=False),
                    signals.independent_count,
                    signals.has_primary_source,
                    event_id,
                ),
            )
            scored += 1
            if scored % BATCH_COMMIT_SIZE == 0:
                conn.commit()
        conn.commit()

    return scored


def run(limit: int = 200) -> EvidenceStats:
    """Kanıt motoru turu: önce iddia durumları, sonra olay skorları.

    Sıra önemlidir: salience'ın cezası `evidence_status`'a bakar
    (Spec §8.4), o yüzden durumlar önce hesaplanır.
    """
    stats = EvidenceStats()
    try:
        stats.claims_scored = score_claims(limit)
        stats.events_scored = score_events(limit)
    except Exception as exc:  # noqa: BLE001
        stats.errors += 1
        log.error("evidence_run_failed", error=type(exc).__name__, detail=str(exc)[:300])
        raise

    log.info("evidence_run_complete", **stats.as_dict())
    return stats
