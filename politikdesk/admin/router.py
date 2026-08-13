"""Admin ve iç araçlar (F1-17, F1-18, F1-19).

Tek kullanıcılı kişisel araç olduğu için ayrı bir kimlik doğrulama
katmanı yoktur; API yalnızca yerel ağa açılır (docker-compose port
eşlemesi). Faz 4'te çok kullanıcıya geçilirse bu değişir (F4-01).

Arayüz: sunucu tarafında üretilen sade HTML + JSON uçları. Faz 3'te
Next.js arayüzü gelene kadar denetim bu ekranlardan yapılır.
"""

from __future__ import annotations

import html
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from politikdesk.ingestion import repository
from politikdesk.observability import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------- kaynaklar
class SourceUpdate(BaseModel):
    tos_status: str | None = Field(
        default=None, pattern="^(allowed|restricted|forbidden|pending_review)$"
    )
    is_active: bool | None = None


@router.get("/sources")
def list_sources() -> list[dict[str, Any]]:
    """Kaynak listesi (F1-17)."""
    return [
        {
            "slug": s.slug, "name": s.name, "tier": s.tier, "kind": s.kind,
            "tos_status": s.tos_status, "is_active": s.is_active,
            "access_method": s.access_method, "adapter": s.adapter,
            "feed_url": s.feed_url, "independence_group": s.independence_group,
            "topics": s.topics,
        }
        for s in repository.list_sources(only_active=False)
    ]


@router.patch("/sources/{slug}")
def update_source(slug: str, payload: SourceUpdate) -> dict[str, Any]:
    """`tos_status` ve aktiflik düzenleme (F1-17 DoD).

    Her değişiklik `audit_log`'a yazılır — ToS kararı denetlenebilir olmalı.
    """
    from politikdesk.db import connection

    source = repository.get_source(slug)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Kaynak yok: {slug}")

    updates: list[str] = []
    params: list[Any] = []
    if payload.tos_status is not None:
        updates.append("tos_status = %s")
        params.append(payload.tos_status)
    if payload.is_active is not None:
        updates.append("is_active = %s")
        params.append(payload.is_active)

    if not updates:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")

    params.append(slug)
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE sources SET {', '.join(updates)} WHERE slug = %s",  # noqa: S608
            params,
        )
        cur.execute(
            """
            INSERT INTO audit_log (actor, action, target, payload)
            VALUES ('user:admin', 'source_updated', %s, %s::jsonb)
            """,
            (f"sources/{slug}", payload.model_dump_json(exclude_none=True)),
        )
        conn.commit()

    log.info("source_updated", source=slug, **payload.model_dump(exclude_none=True))
    return {"slug": slug, **payload.model_dump(exclude_none=True)}


@router.post("/sources/sync")
def sync_sources() -> dict[str, int]:
    """`config/sources.yml` -> veritabanı senkronizasyonu."""
    from politikdesk.ingestion.sources import sync_to_database

    return sync_to_database()


# ---------------------------------------------------------------- makaleler
@router.get("/articles")
def list_articles(
    source: str | None = None,
    topic: str | None = None,
    duplicates: str | None = Query(default=None, pattern="^(near|original)$"),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
) -> dict[str, Any]:
    """Makale listesi + filtreler (F1-18)."""
    from politikdesk.db import connection, fetch_one

    conditions: list[str] = []
    params: list[Any] = []

    if source:
        conditions.append("s.slug = %s")
        params.append(source)
    if topic:
        conditions.append("%s = ANY(a.topics)")
        params.append(topic)
    if duplicates == "near":
        conditions.append("a.near_duplicate_of_id IS NOT NULL")
    elif duplicates == "original":
        conditions.append("a.near_duplicate_of_id IS NULL")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT a.id, a.title, a.canonical_url, a.excerpt, a.published_at,
                   a.first_seen_at, a.topics, a.near_duplicate_of_id,
                   a.simhash_distance, a.independence_key,
                   a.embedding IS NOT NULL AS has_embedding,
                   a.lead_paragraph IS NOT NULL AS has_lead,
                   s.slug AS source_slug, s.tier
            FROM articles a JOIN sources s ON s.id = a.source_id
            {where}
            ORDER BY a.first_seen_at DESC
            LIMIT %s OFFSET %s
            """,  # noqa: S608
            [*params, limit, offset],
        )
        rows = list(cur.fetchall())

        cur.execute(
            f"SELECT count(*) AS total FROM articles a "  # noqa: S608
            f"JOIN sources s ON s.id = a.source_id {where}",
            params,
        )
        total = fetch_one(cur)["total"]

    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@router.get("/articles/{article_id}")
def article_detail(article_id: int) -> dict[str, Any]:
    """Bir makalenin ham verisi (F1-18 DoD)."""
    from politikdesk.db import connection
    from politikdesk.nlp.repository import article_entities

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.*, s.slug AS source_slug, s.name AS source_name, s.tier
            FROM articles a JOIN sources s ON s.id = a.source_id
            WHERE a.id = %s
            """,
            (article_id,),
        )
        row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Makale yok: {article_id}")

    # Embedding vektörünü JSON'a koymak faydasız ve büyük; yalnızca varlığı bildirilir.
    row = dict(row)
    row["has_embedding"] = row.pop("embedding", None) is not None
    row["entities"] = article_entities(article_id)
    return row


# ------------------------------------------------------------------ sağlık
@router.get("/health")
def source_health() -> list[dict[str, Any]]:
    """Kaynak başına akış durumu (F1-19)."""
    return repository.health_report()


@router.get("/stats")
def stats() -> dict[str, Any]:
    """Boru hattı özeti."""
    from politikdesk.db import connection, fetch_one
    from politikdesk.nlp.repository import embedding_coverage

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              (SELECT count(*) FROM articles) AS articles,
              (SELECT count(*) FROM articles
                WHERE first_seen_at > now() - interval '24 hours') AS articles_24h,
              (SELECT count(*) FROM articles
                WHERE near_duplicate_of_id IS NOT NULL) AS near_duplicates,
              (SELECT count(*) FROM entities) AS entities,
              (SELECT count(*) FROM sources WHERE is_active) AS active_sources
            """
        )
        base = dict(fetch_one(cur))

    return {**base, "coverage": embedding_coverage()}


# -------------------------------------------------------------- HTML panel
@router.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    """Tek sayfalık denetim panosu (F1-17/18/19 görsel karşılığı)."""
    health = repository.health_report()
    counts = stats()

    badge = {"green": "#1a7f37", "amber": "#9a6700", "red": "#cf222e",
             "blocked": "#8250df", "inactive": "#6e7781"}

    rows = "".join(
        f"<tr>"
        f"<td><strong>{html.escape(h['slug'])}</strong><br>"
        f"<small>{html.escape(h['name'])}</small></td>"
        f"<td>T{h['tier']}</td>"
        f"<td><span style='color:{badge.get(h['status'], '#000')}'>"
        f"● {h['status']}</span></td>"
        f"<td>{h['articles_24h']}</td>"
        f"<td>{h['articles_total']}</td>"
        f"<td>{h['hours_since_success'] if h['hours_since_success'] is not None else '—'}</td>"
        f"<td>{html.escape(h['tos_status'])}</td>"
        f"<td><small>{html.escape((h['last_error'] or '')[:80])}</small></td>"
        f"</tr>"
        for h in health
    )

    coverage = counts["coverage"]
    embedded_pct = (
        round(coverage["embedded"] / coverage["total"] * 100)
        if coverage["total"] else 0
    )

    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<title>PolitikDesk — Admin</title>
<style>
 body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 1100px;
        color: #1f2328; }}
 h1 {{ font-size: 1.4rem; }}
 table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
 th, td {{ border-bottom: 1px solid #d0d7de; padding: .5rem; text-align: left;
          font-size: .9rem; vertical-align: top; }}
 th {{ background: #f6f8fa; }}
 .cards {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }}
 .card {{ border: 1px solid #d0d7de; border-radius: 6px; padding: .8rem 1.2rem;
         min-width: 130px; }}
 .card b {{ display: block; font-size: 1.6rem; }}
 small {{ color: #656d76; }}
</style></head><body>
<h1>PolitikDesk — Veri Omurgası</h1>
<div class="cards">
  <div class="card"><b>{counts['articles']}</b><small>makale</small></div>
  <div class="card"><b>{counts['articles_24h']}</b><small>son 24 saat</small></div>
  <div class="card"><b>{counts['near_duplicates']}</b><small>yakın tekrar</small></div>
  <div class="card"><b>{counts['entities']}</b><small>varlık</small></div>
  <div class="card"><b>{embedded_pct}%</b><small>embed edilmiş</small></div>
</div>
<table>
<tr><th>Kaynak</th><th>Tier</th><th>Durum</th><th>24s</th><th>Toplam</th>
    <th>Son başarı (sa)</th><th>ToS</th><th>Son hata</th></tr>
{rows}
</table>
<p><small>Uçlar: <code>/admin/sources</code> · <code>/admin/articles</code> ·
<code>/admin/health</code> · <code>/admin/stats</code></small></p>
</body></html>"""
