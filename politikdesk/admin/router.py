"""Admin ve iç araçlar (F1-17, F1-18, F1-19).

Tek kullanıcılı kişisel araç olduğu için ayrı bir kimlik doğrulama
katmanı yoktur; API yalnızca yerel ağa açılır (docker-compose port
eşlemesi). Faz 4'te çok kullanıcıya geçilirse bu değişir (F4-01).

Arayüz: sunucu tarafında üretilen HTML + JSON uçları. Ekran **kullanıcı
tarafındaki sayfalarla aynı kabuğu** kullanır (`web/ui/shell.py`); admin
ekranları da kullanıcının gördüğü ekranlardır ve ayrı bir stil adası
olmaları "her sayfa farklı görünüyor" sonucunu üretiyordu.

### Bu sayfanın tek işi (BRIEF `birincil_is`)

> "Boru hattı akıyor mu, nerede tıkandı?"

Bu yüzden **aşama tablosu kaynak tablosundan önce** gelir. Kaynak tablosu
boru hattının GİRİŞİNE bakar (kaynaklar veri veriyor mu?); aşama tablosu
içerisine (gelen veri sonuna kadar gidiyor mu?). 13 Ağustos 2026'da
kaynaklar yemyeşilken kümeleme 13 saat durmuştu ve hiçbir gösterge bunu
söylemedi (B-77/B-78) — sıralama o arızanın dersidir.
"""

from __future__ import annotations

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
            "slug": s.slug,
            "name": s.name,
            "tier": s.tier,
            "kind": s.kind,
            "tos_status": s.tos_status,
            "is_active": s.is_active,
            "access_method": s.access_method,
            "adapter": s.adapter,
            "feed_url": s.feed_url,
            "independence_group": s.independence_group,
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
    vertical: str | None = None,
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
    if vertical:
        conditions.append("a.vertical = %s")
        params.append(vertical)
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


@router.get("/pipeline-health")
def pipeline_health_endpoint() -> list[dict[str, Any]]:
    """Aşama başına birikme durumu (F4-05, B-78).

    `/admin/health` boru hattının GİRİŞİNE bakar (kaynaklar veri veriyor
    mu?). Bu uç içerisine bakar: gelen veri sonuna kadar gidiyor mu?
    """
    from politikdesk import pipeline_health

    return [r.as_dict() for r in pipeline_health.stage_report()]


@router.post("/drain")
def pipeline_drain_endpoint() -> dict[str, Any]:
    """Boru hattındaki tüm bekleyen aşamaları anında boşaltır (F4-05)."""
    from scripts.drain_pipeline import drain_all

    stats = drain_all()
    return {"status": "ok", "stats": stats}


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
# Sağlık durumu -> kanıt skalası token'ı. Ayrı bir renk skalası kurmak
# yerine mevcut olan kullanılır: bir arayüzde iki "iyi/kötü" renk dili
# olması, ikisini de zayıflatır.
_HEALTH_TONE = {
    "green": ("strong", "akıyor"),
    "amber": ("partial", "yavaş"),
    "red": ("contra", "durdu"),
    "blocked": ("single", "engelli"),
    "inactive": ("neutral", "kapalı"),
}


def _tone(status: str) -> tuple[str, str]:
    return _HEALTH_TONE.get(status, ("neutral", status))


@router.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    """Tek sayfalık denetim panosu (F1-17/18/19 görsel karşılığı)."""
    from politikdesk import pipeline_health as ph
    from politikdesk.web.ui import (
        button,
        card,
        cell,
        esc,
        kpi,
        notice,
        page,
        page_head,
        table,
    )
    from politikdesk.web.ui import (
        format as fmt,
    )

    try:
        health = repository.health_report()
        counts = stats()
        stages = ph.stage_report()
    except Exception as exc:  # noqa: BLE001
        log.warning("admin_dashboard_db_unavailable", error=str(exc))
        from politikdesk.web.ui import error_state, page

        return page(
            "Boru hattı",
            error_state(
                "Veritabanı bağlantısı yok",
                "Denetim panosu çalışan bir veritabanı gerektirir. "
                "Vercel vitrin modunda bu ekran kullanılamaz.",
            ),
            active="/admin/",
            crumbs=(("Denetim", None), ("Boru hattı", None)),
        )

    coverage = counts["coverage"]
    embedded_pct = coverage["embedded"] / coverage["total"] * 100 if coverage["total"] else 0

    broken = [s for s in stages if s.status == "red"]
    slow = [s for s in stages if s.status == "amber"]

    # Sayfanın tek sorusunun cevabı en üstte, tek cümlede.
    if broken:
        verdict = notice(
            f"<p><b>Boru hattı kopuk:</b> "
            f"{esc(', '.join(s.label for s in broken))}.</p>"
            f"<p>Aşağıdaki tabloda her aşamanın ipucu var. İlk kırmızıdan "
            f"sonrası zaten onun sonucudur — en üstteki kırmızıdan başla.</p>",
            tone="bad",
        )
    elif slow:
        verdict = notice(
            f"<p><b>Boru hattı akıyor ama birikme var:</b> "
            f"{esc(', '.join(s.label for s in slow))}.</p>",
            tone="warn",
        )
    else:
        verdict = notice("<p><b>Boru hattı akıyor.</b> Birikmiş aşama yok.</p>", tone="ok")

    # Aşama sağlığı (B-78). Boru hattı SIRASIYLA gösterilir ki nerede
    # koptuğu okunsun.
    stage_rows = []
    for s in stages:
        token, label = _tone(s.status)
        stage_rows.append(
            "<tr>"
            + cell(f"<b>{esc(s.label)}</b>", label="Aşama")
            + cell(f'<span class="badge {token}">{esc(label)}</span>', label="Durum")
            + cell(
                esc(fmt.number(s.backlog)) if s.kind == "backlog" else fmt.EMPTY,
                label="Bekleyen",
                cls="num",
            )
            + cell(
                esc(fmt.number(s.oldest_hours, 1)) if s.oldest_hours is not None else fmt.EMPTY,
                label="En eski (sa)",
                cls="num",
            )
            + cell(esc(fmt.number(s.threshold_hours)), label="Eşik (sa)", cls="num")
            + cell(
                f'<span class="subtle">{esc(s.hint)}</span>' if s.status != "green" else "",
                label="İpucu",
            )
            + "</tr>"
        )

    source_rows = []
    for h in health:
        token, label = _tone(h["status"])
        error = (h["last_error"] or "")[:90]
        source_rows.append(
            "<tr>"
            + cell(
                f'<b>{esc(h["name"])}</b><div class="cell-sub mono">{esc(h["slug"])}</div>',
                label="Kaynak",
            )
            + cell(f'<span class="tier">T{h["tier"]}</span>', label="Katman")
            + cell(f'<span class="badge {token}">{esc(label)}</span>', label="Durum")
            + cell(esc(fmt.number(h["articles_24h"])), label="24 saat", cls="num")
            + cell(esc(fmt.number(h["articles_total"])), label="Toplam", cls="num")
            + cell(
                esc(fmt.number(h["hours_since_success"], 1))
                if h["hours_since_success"] is not None
                else fmt.EMPTY,
                label="Son başarı (sa)",
                cls="num",
            )
            + cell(f'<span class="mono">{esc(h["tos_status"])}</span>', label="ToS")
            + cell(
                f'<span class="subtle">{esc(error)}</span>' if error else "",
                label="Son hata",
            )
            + "</tr>"
        )

    body = f"""
{
        page_head(
            "Boru hattı",
            lede="Kaynak tablosu boru hattının GİRİŞİNE bakar, aşama tablosu "
            "İÇERİSİNE. İkisi ayrı sorular sorar ve ayrı arızaları yakalar.",
            actions=(
                button(
                    "Boru Hattını Boşalt",
                    onclick="this.disabled=true;this.innerText='İşleniyor...';fetch('/admin/drain',{method:'POST'}).then(()=>location.reload())",
                    variant="primary",
                    icon_name="pipeline",
                )
                + " "
                + button("Metrikler", href="/admin/metrics", icon_name="metrics")
            ),
        )
    }
<div class="stack">
  {verdict}

  <div class="kpis">
    {kpi("Toplam makale", fmt.number(counts["articles"]), icon_name="briefing")}
    {kpi("Son 24 saat", fmt.number(counts["articles_24h"]), unit="makale", icon_name="clock")}
    {kpi("Yakın tekrar", fmt.number(counts["near_duplicates"]), unit="makale", icon_name="copy")}
    {kpi("Embed edilmiş", fmt.percent(embedded_pct), icon_name="pipeline")}
  </div>

  {
        card(
            table(
                (
                    ("Aşama", ""),
                    ("Durum", ""),
                    ("Bekleyen", "num"),
                    ("En eski (sa)", "num"),
                    ("Eşik (sa)", "num"),
                    ("İpucu", ""),
                ),
                stage_rows,
            ),
            title="Boru hattı aşamaları",
            actions='<span class="subtle" style="font-size:var(--text-xs)">'
            "sırayla — ilk kırmızıdan başla</span>",
        )
    }

  {
        card(
            table(
                (
                    ("Kaynak", ""),
                    ("Katman", ""),
                    ("Durum", ""),
                    ("24 saat", "num"),
                    ("Toplam", "num"),
                    ("Son başarı (sa)", "num"),
                    ("ToS", ""),
                    ("Son hata", ""),
                ),
                source_rows,
            ),
            title=f"Kaynaklar · {len(health)}",
            actions='<span class="subtle" style="font-size:var(--text-xs)">'
            "katman siyasi konum değildir</span>",
        )
    }

  {
        card(
            '<p class="subtle mono" style="margin:0;font-size:var(--text-xs)">'
            "/admin/sources · /admin/articles · /admin/health · "
            "/admin/pipeline-health · /admin/stats</p>",
            title="JSON uçları",
        )
    }
</div>
"""
    return page(
        "Boru hattı",
        body,
        active="/admin/",
        crumbs=(("Denetim", None), ("Boru hattı", None)),
    )
