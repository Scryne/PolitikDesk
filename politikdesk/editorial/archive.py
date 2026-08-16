"""İçerik ve Kanıt Arşivi (B-04 · Spec v3.4 §14.4).

Yayınlanan veya kaydedilen her taslağın dayandığı kanıt bağlarını
(`cited_claim_ids`, alıntılar, kaynak listesi, zaman damgası)
kalıcı olarak arşivler ve denetlenebilir kılar.
"Bu metni neye dayanarak yazdım?" sorusunun deterministik cevabıdır.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class ArchivedEvidenceItem:
    claim_id: int
    claim_text: str
    claim_type: str
    evidence_status: str
    source_name: str
    quote_span: str
    article_url: str = ""


@dataclass
class ArchivedPublication:
    """Yayınlanmış bir taslağın kanıt kütüğü."""

    draft_id: int
    event_id: int
    body: str
    angle: str
    published_at: str
    cited_claim_ids: list[int]
    evidence_trail: list[ArchivedEvidenceItem] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def export_audit_manifest(self) -> dict[str, Any]:
        """Dışa aktarılabilir ve doğrulanabilir denetim manifestosu üretir."""
        return {
            "draft_id": self.draft_id,
            "event_id": self.event_id,
            "angle": self.angle,
            "published_at": self.published_at,
            "body": self.body,
            "cited_claim_ids": self.cited_claim_ids,
            "evidence_count": len(self.evidence_trail),
            "evidence_trail": [asdict(e) for e in self.evidence_trail],
            "metadata": self.metadata,
        }


def create_archive_record(
    draft_id: int,
    event_id: int,
    body: str,
    angle: str,
    cited_claim_ids: list[int],
    evidence_trail: list[ArchivedEvidenceItem],
    *,
    extra_metadata: dict[str, Any] | None = None,
) -> ArchivedPublication:
    """Yeni bir arşiv kaydı nesnesi oluşturur."""
    now_iso = datetime.now(UTC).isoformat()
    return ArchivedPublication(
        draft_id=draft_id,
        event_id=event_id,
        body=body,
        angle=angle,
        published_at=now_iso,
        cited_claim_ids=cited_claim_ids,
        evidence_trail=evidence_trail,
        metadata=extra_metadata or {},
    )


def persist_draft_archive(draft_id: int, final_body: str | None = None) -> ArchivedPublication:
    """Kabul edilen taslağın kanıt kütüğünü oluşturur ve denetim günlüğüne yazar."""
    from politikdesk import audit

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, event_id, body, angle, cited_claim_ids, model_name, engine_version
            FROM drafts
            WHERE id = %s;
            """,
            (draft_id,),
        )
        draft = cur.fetchone()
        if not draft:
            raise LookupError(f"Taslak bulunamadı: {draft_id}")

        cited_ids = list(draft["cited_claim_ids"] or [])
        evidence_items: list[ArchivedEvidenceItem] = []

        if cited_ids:
            cur.execute(
                """
                SELECT c.id as claim_id, c.claim_text, c.claim_type, c.evidence_status,
                       COALESCE(s.name, 'Bilinmeyen Kaynak') as source_name,
                       COALESCE(ev.quote_span, '') as quote_span,
                       COALESCE(a.canonical_url, '') as article_url
                FROM claims c
                LEFT JOIN evidence ev ON ev.claim_id = c.id
                LEFT JOIN articles a ON a.id = ev.article_id
                LEFT JOIN sources s ON s.id = a.source_id
                WHERE c.id = ANY(%s);
                """,
                (cited_ids,),
            )
            for r in cur.fetchall():
                evidence_items.append(
                    ArchivedEvidenceItem(
                        claim_id=r["claim_id"],
                        claim_text=r["claim_text"],
                        claim_type=r["claim_type"],
                        evidence_status=r["evidence_status"],
                        source_name=r["source_name"],
                        quote_span=r["quote_span"],
                        article_url=r["article_url"],
                    )
                )

        record = create_archive_record(
            draft_id=draft["id"],
            event_id=draft["event_id"],
            body=final_body or draft["body"],
            angle=draft["angle"],
            cited_claim_ids=cited_ids,
            evidence_trail=evidence_items,
            extra_metadata={
                "model_name": draft["model_name"],
                "engine_version": draft["engine_version"],
            },
        )

        audit.write(
            "draft_archived",
            f"drafts/{draft_id}",
            payload=record.export_audit_manifest(),
            cursor=cur,
        )
        conn.commit()

    log.info("draft_archived_persisted", draft_id=draft_id, claims_count=len(cited_ids))
    return record


def list_archived_publications(limit: int = 50) -> list[dict[str, Any]]:
    """Yayınlanmış / kabul edilmiş arşivlenmiş taslakların listesini döndürür."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id as draft_id, d.event_id, e.title as event_title,
                   d.body, d.angle, d.user_action, d.created_at,
                   d.cited_claim_ids, d.is_grounded
            FROM drafts d
            JOIN events e ON e.id = d.event_id
            WHERE d.user_action IN ('accepted', 'edited', 'published')
               OR d.is_grounded = true
            ORDER BY d.created_at DESC
            LIMIT %s;
            """,
            (limit,),
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "draft_id": r["draft_id"],
                    "event_id": r["event_id"],
                    "event_title": r["event_title"],
                    "body": r["body"],
                    "angle": r["angle"],
                    "user_action": r["user_action"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else "",
                    "cited_claim_ids": list(r["cited_claim_ids"] or []),
                    "is_grounded": r["is_grounded"],
                }
            )
        return out
