"""İddia çıkarımı turu ve kalıcılığı (F2-06, F2-09, F2-10 · DB tarafı).

Çıkarım **olay bazlı** koşar, makale bazlı değil: F2-09 aynı olayda aynı
iddianın iki kez kaydedilmemesini ister ve bu ancak olayın tüm makaleleri
birlikte görüldüğünde yapılabilir.

Akış:
  1. Olayın kümelenmiş makalelerini al
  2. Her makaleden LLM ile iddia çıkar (doğrulama katmanları `claims.py`'de)
  3. Olay düzeyinde tekilleştir
  4. `claims` satırlarını yaz; her iddiayı kaynağı olan makaleye
     `evidence` satırıyla bağla (`stance='supports'`, `quote_span`)

**Neden `stance` başlangıçta hep `supports`:** bir makaleden çıkarılan
iddia, o makale tarafından desteklenir — tanım gereği. `contradicts`
bağları, aynı olaydaki *başka* makalelerin aynı iddiaya karşı çıkması
durumunda kurulur; bu, sayısal çelişki bayrağından (F2-03) ve iddia
eşleştirmesinden gelir.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from politikdesk.db import connection
from politikdesk.llm.errors import LLMNotConfigured
from politikdesk.nlp.claims import (
    PROMPT_VERSION,
    ExtractedClaim,
    dedupe_claims,
    extract_claims,
)
from politikdesk.observability import get_logger

log = get_logger(__name__)


@dataclass
class ClaimStats:
    events_processed: int = 0
    claims_extracted: int = 0
    claims_rejected: int = 0
    evidence_links: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "events_processed": self.events_processed,
            "claims_extracted": self.claims_extracted,
            "claims_rejected": self.claims_rejected,
            "evidence_links": self.evidence_links,
            "errors": self.errors,
        }


def pending_events(limit: int = 10) -> list[int]:
    """İddiası çıkarılmamış olaylar (en yeni önce)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.id FROM events e
            WHERE e.merged_into_id IS NULL
              AND e.article_count > 0
              AND NOT EXISTS (SELECT 1 FROM claims c WHERE c.event_id = e.id)
            ORDER BY e.last_update_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [r["id"] for r in cur.fetchall()]


def _articles_of(cur: Any, event_id: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT a.id, a.title, a.excerpt, a.published_at,
               s.name AS source_name, s.tier
        FROM articles a JOIN sources s ON s.id = a.source_id
        WHERE a.event_id = %s
        ORDER BY s.tier, a.published_at
        """,
        (event_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def _persist(
    cur: Any,
    event_id: int,
    claims: list[tuple[ExtractedClaim, int]],
    extracted_by: str,
) -> int:
    """İddiaları ve kanıt bağlarını yazar; kurulan bağ sayısını döndürür."""
    links = 0
    for claim, article_id in claims:
        cur.execute(
            """
            INSERT INTO claims (event_id, claim_text, claim_type, normalized_value,
                                evidence_status, status_reason)
            VALUES (%s, %s, %s, %s::jsonb, 'unverified', %s::jsonb)
            RETURNING id
            """,
            (
                event_id,
                claim.claim_text,
                claim.claim_type,
                json.dumps(claim.normalized_value, ensure_ascii=False)
                if claim.normalized_value else None,
                # Başlangıç durumu: kanıt motoru henüz koşmadı. `unverified`
                # güvenli varsayılandır — R0'ın tahmin kısıtıyla da uyumlu,
                # ve DB CHECK'i ihlal etmez.
                json.dumps({"rule": "pending", "engine_version": "not_yet_scored"}),
            ),
        )
        claim_id = cur.fetchone()["id"]

        cur.execute(
            """
            INSERT INTO evidence (claim_id, article_id, stance, quote_span, extracted_by)
            VALUES (%s, %s, 'supports', %s, %s)
            ON CONFLICT (claim_id, article_id) DO NOTHING
            """,
            (claim_id, article_id, claim.quote_span, extracted_by),
        )
        links += cur.rowcount
    return links


def run(limit: int = 10, client: Any = None) -> ClaimStats:
    """İddia çıkarımı turu.

    `client` verilmezse `LLMClient` kurulur — ANTHROPIC_API_KEY gerekir.
    """
    if client is None:
        from politikdesk.llm.client import LLMClient

        client = LLMClient()

    stats = ClaimStats()

    for event_id in pending_events(limit):
        try:
            with connection() as conn, conn.cursor() as cur:
                articles = _articles_of(cur, event_id)
                if not articles:
                    continue

                collected: list[tuple[ExtractedClaim, int]] = []
                extracted_by = f"unknown+{PROMPT_VERSION}"

                for article in articles:
                    result = extract_claims(
                        title=article["title"],
                        excerpt=article["excerpt"] or "",
                        source_name=article["source_name"],
                        tier=article["tier"],
                        published_at=str(article["published_at"] or ""),
                        client=client,
                    )
                    extracted_by = result.extracted_by
                    stats.claims_rejected += len(result.rejected)
                    collected.extend((c, article["id"]) for c in result.claims)

                # F2-09: olay düzeyinde tekilleştirme — aynı iddia iki
                # makalede de geçebilir; kayıt tek olmalı.
                deduped = dedupe_claims([c for c, _ in collected])
                kept = {id(c) for c in deduped}
                final = [(c, aid) for c, aid in collected if id(c) in kept]

                stats.evidence_links += _persist(cur, event_id, final, extracted_by)
                stats.claims_extracted += len(final)
                conn.commit()

            stats.events_processed += 1

        except LLMNotConfigured:
            # Yapılandırma eksikliği olay başına hata değildir; tur biter.
            raise
        except Exception as exc:  # noqa: BLE001
            stats.errors += 1
            log.error(
                "claim_extraction_failed",
                event_id=event_id,
                error=type(exc).__name__,
                detail=str(exc)[:300],
            )

    log.info("claim_extraction_complete", **stats.as_dict())
    return stats
