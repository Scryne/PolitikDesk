"""Siyasi Hafıza Zamansal Söylem Karşılaştırma Ekranı (Spec v3.4 §7.3 · B-24).

Kullanıcının bir siyasi aktör ve politika başlığı seçerek iki farklı zaman
dilimindeki (ör. 2024 öncesi vs sonrası) beyanları ve söylem tutarlılığını
yan yana karşılaştırmasını sağlar.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from politikdesk.political_memory.comparison import (
    compare_actor_statements,
    get_known_comparison_topics,
    get_tracked_actors,
)
from politikdesk.users import current_user_id, touch_last_seen
from politikdesk.web.ui import (
    ACTIVITY_JS,
    card,
    cell,
    esc,
    icon,
    kpi,
    notice,
    page,
    page_head,
    status_badge,
    table,
)

router = APIRouter(tags=["web"])


@router.get("/memory/compare", response_class=HTMLResponse)
@router.get("/hafiza/karsilastir", response_class=HTMLResponse)
def statement_comparison_page(
    request: Request,
    actor: str = "Mehmet Şimşek",
    topic: str = "",
    year: int = 2025,
    limit: int = 50,
) -> HTMLResponse:
    """Zamansal söylem karşılaştırma arayüzü."""
    touch_last_seen(current_user_id())

    actors = get_tracked_actors()
    topics = get_known_comparison_topics()

    # Karşılaştırmayı çalıştır
    result = compare_actor_statements(
        actor_name=actor,
        topic=topic if topic else None,
        split_year=year,
        limit=limit,
    )

    # 1. Filtreleme Formu
    actor_options = "".join(
        f'<option value="{esc(a)}"'
        f'{" selected" if a == actor else ""}>{esc(a)}</option>'
        for a in actors
    )
    topic_options = '<option value="">Tüm Politika Başlıkları</option>' + "".join(
        f'<option value="{esc(t["slug"])}"'
        f'{" selected" if t["slug"] == topic else ""}>{esc(t["title"])}</option>'
        for t in topics
    )
    year_options = "".join(
        f'<option value="{y}"{" selected" if y == year else ""}>{y}</option>'
        for y in (2023, 2024, 2025, 2026)
    )

    filter_form_html = f"""
    <form method="GET" action="/memory/compare" class="filters" style="display:flex;gap:var(--space-3);flex-wrap:wrap;align-items:flex-end">
      <div style="flex:1;min-width:180px">
        <label class="form-label" style="display:block;margin-bottom:var(--space-1);font-size:var(--text-xs);font-weight:600">Siyasi Aktör / Kurum</label>
        <select name="actor" class="input select" style="width:100%">{actor_options}</select>
      </div>
      <div style="flex:1;min-width:200px">
        <label class="form-label" style="display:block;margin-bottom:var(--space-1);font-size:var(--text-xs);font-weight:600">Politika Başlığı</label>
        <select name="topic" class="input select" style="width:100%">{topic_options}</select>
      </div>
      <div style="width:120px">
        <label class="form-label" style="display:block;margin-bottom:var(--space-1);font-size:var(--text-xs);font-weight:600">Ayrım Yılı</label>
        <select name="year" class="input select" style="width:100%">{year_options}</select>
      </div>
      <div>
        <button type="submit" class="btn primary" style="height:36px">
          {icon("filter", size=14)}<span>Karşılaştır</span>
        </button>
      </div>
    </form>
    """

    filter_card = card(filter_form_html, title="Karşılaştırma Parametreleri")

    kpi_grid = f"""
    <div class="kpis" style="margin-bottom:var(--space-4)">
      {kpi("Seçilen Aktör", actor, icon_name="identity")}
      {kpi(f"{result.earlier_period} Beyan", str(len(result.earlier_statements)), icon_name="clock")}
      {kpi(f"{result.later_period} Beyan", str(len(result.later_statements)), icon_name="zap")}
      {kpi("Tutarlılık Skoru", f"%{int(result.consistency_score * 100)}", icon_name="check")}
    </div>
    """

    summary_notice = notice(
        f"<b>Analitik Değerlendirme:</b> {esc(result.shift_summary)}",
        tone="warn" if result.shift_detected else "ok",
    )

    # 3. İki Zaman Kolonu: Yan Yana Beyan Karşılaştırması
    def _render_statement_card(s) -> str:  # noqa: ANN001
        polarity_color = "var(--color-strong)" if s.stance_polarity == "support" else ("var(--color-contra)" if s.stance_polarity == "oppose" else "var(--color-accent)")
        polarity_label = "Destek / Savunma" if s.stance_polarity == "support" else ("Karşıtlık / İtiraz" if s.stance_polarity == "oppose" else ("Vaat" if s.stance_polarity == "promise" else "Nötr Beyan"))
        return f"""
        <div class="timeline-item" style="padding:var(--space-3);margin-bottom:var(--space-3);background:var(--color-surface-sunken);border-left:3px solid {polarity_color};border-radius:var(--radius-sm)">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--space-1)">
            <span class="mono subtle" style="font-size:var(--text-xs)">{esc(s.date_str)}</span>
            <span class="badge" style="font-size:var(--text-xs)">{polarity_label}</span>
          </div>
          <p style="margin:0 0 var(--space-2) 0;font-size:var(--text-sm);font-weight:500;line-height:1.4">“{esc(s.claim_text)}”</p>
          <div style="display:flex;justify-content:space-between;align-items:center;font-size:var(--text-xs)" class="subtle">
            <span>{icon("calendar", size=12)} <a href="/event/{s.event_id}" style="color:inherit">{esc(s.event_title[:45])}...</a></span>
            <span>{status_badge(s.evidence_status)}</span>
          </div>
        </div>
        """

    earlier_cards = "".join(_render_statement_card(s) for s in result.earlier_statements) or '<p class="subtle" style="padding:var(--space-4);text-align:center">Bu dönemde eşleşen beyan bulunamadı.</p>'
    later_cards = "".join(_render_statement_card(s) for s in result.later_statements) or '<p class="subtle" style="padding:var(--space-4);text-align:center">Bu dönemde eşleşen beyan bulunamadı.</p>'

    timeline_grid = f"""
    <div class="halves" style="margin-top:var(--space-4)">
      <div>
        <h3 style="margin-top:0;font-size:var(--text-base);display:flex;align-items:center;gap:var(--space-2)">
          {icon("clock", size=16)} {esc(result.earlier_period)}
        </h3>
        <div class="timeline-column">{earlier_cards}</div>
      </div>
      <div>
        <h3 style="margin-top:0;font-size:var(--text-base);display:flex;align-items:center;gap:var(--space-2)">
          {icon("zap", size=16)} {esc(result.later_period)}
        </h3>
        <div class="timeline-column">{later_cards}</div>
      </div>
    </div>
    """

    comparison_card = card(
        timeline_grid,
        title=f"{esc(actor)} — Zamansal Beyan Ayrışması ({esc(result.topic_query)})",
    )

    # 4. Kanıt ve İlişki Eşleşme Matrisi
    matrix_rows = []
    for item in result.evidence_matrix[:8]:
        align_badge = '<span class="badge strong">Uyumlu</span>' if item["aligned"] else '<span class="badge contra">Ayrışma</span>'
        matrix_rows.append(
            "<tr>"
            + cell(f'<span class="mono">{esc(item["earlier_date"])}</span><br><a href="/event/{item["earlier_event_id"]}">“{esc(item["earlier_text"][:60])}...”</a>', label=result.earlier_period)
            + cell(f'<span class="mono">{esc(item["later_date"])}</span><br><a href="/event/{item["later_event_id"]}">“{esc(item["later_text"][:60])}...”</a>', label=result.later_period)
            + cell(align_badge, label="Durum")
            + "</tr>"
        )

    matrix_table = table(
        headers=[
            (result.earlier_period, ""),
            (result.later_period, ""),
            ("Söylem İlişkisi", ""),
        ],
        rows=matrix_rows,
    ) if matrix_rows else ""

    matrix_card = card(matrix_table, title="Beyanlar Arası İlişki ve Çapraz Kanıt Matrisi") if matrix_rows else ""

    undated_section = ""
    if result.undated_statements:
        undated_cards = "".join(_render_statement_card(s) for s in result.undated_statements[:8])
        undated_section = card(
            f"""
            <p class="subtle" style="margin-top:0;margin-bottom:var(--space-3);font-size:var(--text-xs)">
              Bu beyanların kesinleşmiş tarih damgası bulunmadığından yapay olarak cari yıla dahil edilmemiş ve zamansal tutarlılık analizinden izole edilmiştir.
            </p>
            <div class="timeline-column">{undated_cards}</div>
            """,
            title=f"Tarihi Belirsiz Beyanlar ({len(result.undated_statements)})",
        )

    body = f"""
    {page_head("Söylem Karşılaştırma", lede="Siyasi aktörlerin farklı dönemlerdeki açıklamalarını, vaatlerini ve politika tutarlılığını analitik hafıza üzerinden yan yana inceleyin.")}
    {filter_card}
    {kpi_grid}
    {summary_notice}
    {comparison_card}
    {matrix_card}
    {undated_section}
    """

    return HTMLResponse(
        page(
            title=f"{actor} Söylem Karşılaştırması",
            body=body,
            active="/memory/compare",
            crumbs=(("Çalışma masası", None), ("Siyasi Hafıza", "/memory"), ("Söylem Karşılaştırma", None)),
            extra_js=ACTIVITY_JS,
        )
    )
