"""Manuel içe aktarma API ucu (F1-04).

DoD: Bir X gönderi linki veya haber linki yapıştırıldığında Tier 4/3
`article` kaydı oluşuyor.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from politikdesk.ingestion import repository, topics
from politikdesk.ingestion.adapters.manual import (
    ManualImportAdapter,
    UnsafeUrlError,
    is_social,
)
from politikdesk.ingestion.normalizer import normalize
from politikdesk.observability import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])

# Manuel içe aktarma için sanal kaynaklar. Sosyal içerik Tier 4'tür ve
# R7 gereği asla 🟢/🟡 olamaz (Spec §8.3).
MANUAL_SOURCES = {
    "manual-social": {"name": "Manuel içe aktarma — sosyal", "tier": 4, "kind": "social"},
    "manual-web": {"name": "Manuel içe aktarma — web", "tier": 3, "kind": "media"},
}


class ImportRequest(BaseModel):
    url: HttpUrl
    force: bool = False
    """Konu kapsamı dışında olsa da içe aktar (kullanıcı bilinçli seçim yapar)."""


@router.post("/link")
def import_link(payload: ImportRequest) -> dict[str, Any]:
    url = str(payload.url)

    try:
        item = ManualImportAdapter().fetch_one(url)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.warning("manual_import_failed", url=url, error=type(exc).__name__)
        raise HTTPException(
            status_code=502, detail=f"Sayfa alınamadı: {type(exc).__name__}"
        ) from exc

    matched_topics = topics.classify(item.title, item.summary)
    if not matched_topics and not payload.force:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "İçerik MVP konu kapsamı dışında görünüyor "
                "(makro ekonomi). Yine de eklemek için force=true.",
                "title": item.title,
                "detected_topics": [],
            },
        )

    source = _ensure_manual_source(item.source_slug)
    article = normalize(item, topics=matched_topics, vertical=source.vertical)

    article_id = repository.insert_article(
        article,
        source_id=source.id,
        independence_key=f"src:{source.slug}",
        is_manual_import=True,
    )

    if article_id is None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Bu bağlantı zaten içe aktarılmış",
                "canonical_url": article.canonical_url,
            },
        )

    log.info(
        "manual_import_ok",
        url=url,
        article_id=article_id,
        source=source.slug,
        topics=list(matched_topics),
    )

    return {
        "article_id": article_id,
        "title": article.title,
        "canonical_url": article.canonical_url,
        "source_slug": source.slug,
        "tier": source.tier,
        "topics": list(matched_topics),
        "note": (
            "Tier 4 (sosyal) kaynak: bu içerikten türeyen iddialar "
            "R7 gereği en fazla 'tek kaynak' olabilir."
            if is_social(url)
            else None
        ),
    }


def _ensure_manual_source(slug: str):  # noqa: ANN202
    """Manuel içe aktarma sanal kaynağını gerekirse yaratır."""
    from politikdesk.db import connection

    existing = repository.get_source(slug)
    if existing is not None:
        return existing

    meta = MANUAL_SOURCES.get(slug, MANUAL_SOURCES["manual-web"])
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sources (name, slug, tier, kind, access_method,
                                 tos_status, independence_group, adapter)
            VALUES (%s, %s, %s, %s, 'manual', 'allowed', %s, 'manual')
            ON CONFLICT (slug) DO NOTHING
            """,
            (meta["name"], slug, meta["tier"], meta["kind"], f"manual-{slug}"),
        )
        conn.commit()

    source = repository.get_source(slug)
    if source is None:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Manuel kaynak oluşturulamadı")
    return source
