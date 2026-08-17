"""Sunucu taraflı SVG grafik ve ekonomik gösterge görselleştiricisi (F5 / B-99).

Sıfır harici JS kütüphanesi / sıfır CDN bağımlılığı ile çalışır (DESIGN.md Ek A).
TÜİK, TCMB, Hazine ve piyasa göstergeleri için hafif, reaktif ve temalı
SVG sparkline ve anomali kartları üretir.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from politikdesk.web.ui.components import SafeString, esc, mark_safe
from politikdesk.web.ui.icons import icon

# Renk belirteçleri CSS değişkenlerinden okunur.
SPARKLINE_DEFAULT_COLOR: Final[str] = "var(--color-accent)"
SPARKLINE_POSITIVE_COLOR: Final[str] = "var(--color-strong)"
SPARKLINE_NEGATIVE_COLOR: Final[str] = "var(--color-contra)"
SPARKLINE_NEUTRAL_COLOR: Final[str] = "var(--color-fg-muted)"


def sparkline(
    points: Sequence[float],
    width: int = 60,
    height: int = 18,
    stroke_color: str = SPARKLINE_DEFAULT_COLOR,
) -> str:
    """Hafif satır içi SVG mini grafik (Spec v3.4 §8.5)."""
    if len(points) < 2:
        return ""
    min_v, max_v = min(points), max(points)
    span = max_v - min_v or 1.0
    pad = 2.0
    w = width - (pad * 2)
    h = height - (pad * 2)
    n = len(points)
    svg_pts = [
        f"{pad + i * w / (n - 1):.1f},{height - pad - (v - min_v) / span * h:.1f}"
        for i, v in enumerate(points)
    ]
    last_pt = svg_pts[-1].split(",")
    return (
        f'<svg class="sparkline" width="{width}" height="{height}" viewBox="0 0 {width} {height}" aria-hidden="true">'
        f'<polyline fill="none" stroke="{stroke_color}" stroke-width="1.5" points="{" ".join(svg_pts)}" />'
        f'<circle cx="{last_pt[0]}" cy="{last_pt[1]}" r="2" fill="{stroke_color}" />'
        f'</svg>'
    )


def sparkline_svg(
    data_points: Sequence[float],
    *,
    width: int = 100,
    height: int = 24,
    stroke_width: float = 2.0,
    stroke_color: str = SPARKLINE_DEFAULT_COLOR,
    fill_area: bool = True,
    show_dots: bool = True,
) -> SafeString:
    """Sayısal bir zaman serisini temiz bir SVG sparkline çizgisine dönüştürür.

    Uç durumlar:
      - Boş dizi: Boş gri düz çizgi
      - Tek değer: Ortada yatay nokta
      - Sabit değerler (min == max): Ortada düz yatay çizgi
    """
    if not data_points:
        svg = (
            f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'class="sparkline" aria-hidden="true">'
            f'<line x1="0" y1="{height / 2}" x2="{width}" y2="{height / 2}" '
            f'stroke="var(--color-border-strong)" stroke-width="{stroke_width}" stroke-dasharray="2 2" />'
            f'</svg>'
        )
        return mark_safe(svg)

    pts = list(data_points)
    n = len(pts)

    if n == 1:
        cx = width / 2
        cy = height / 2
        svg = (
            f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'class="sparkline" aria-hidden="true">'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="{stroke_color}" />'
            f'</svg>'
        )
        return mark_safe(svg)

    min_val = min(pts)
    max_val = max(pts)
    val_range = max_val - min_val

    pad_x = 4.0
    pad_y = 3.0
    usable_w = width - (2 * pad_x)
    usable_h = height - (2 * pad_y)

    coords: list[tuple[float, float]] = []
    for i, v in enumerate(pts):
        x = pad_x + (i / (n - 1)) * usable_w
        if val_range == 0:
            y = pad_y + (usable_h / 2)
        else:
            # SVG y ekseni yukarıdan aşağıya büyür
            norm = (v - min_val) / val_range
            y = pad_y + usable_h - (norm * usable_h)
        coords.append((x, y))

    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in coords)

    area_markup = ""
    if fill_area and coords:
        first_x = coords[0][0]
        last_x = coords[-1][0]
        base_y = height - pad_y + 1
        area_d = f"{path_d} L {last_x:.1f},{base_y:.1f} L {first_x:.1f},{base_y:.1f} Z"
        area_markup = (
            f'<path d="{area_d}" fill="{stroke_color}" fill-opacity="0.12" stroke="none" />'
        )

    dots_markup = ""
    if show_dots and coords:
        last_coord = coords[-1]
        dots_markup = (
            f'<circle cx="{last_coord[0]:.1f}" cy="{last_coord[1]:.1f}" r="2.5" '
            f'fill="{stroke_color}" />'
        )

    svg = (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'class="sparkline" style="display:inline-block;vertical-align:middle;overflow:visible;" '
        f'aria-hidden="true">'
        f'{area_markup}'
        f'<path d="{path_d}" fill="none" stroke="{stroke_color}" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round" />'
        f'{dots_markup}'
        f'</svg>'
    )
    return mark_safe(svg)


def economic_indicator_card(
    title: str,
    current_value: str,
    unit: str = "",
    history: Sequence[float] = (),
    change_text: str = "",
    expectation_diff: str | None = None,
    is_anomaly: bool = False,
    source_name: str = "",
) -> SafeString:
    """Makro ekonomi göstergesi için mini trend ve anomali kartı."""
    trend_color = SPARKLINE_DEFAULT_COLOR
    if history and len(history) >= 2:
        if history[-1] > history[0]:
            trend_color = SPARKLINE_NEGATIVE_COLOR if "enflasyon" in title.lower() or "tüfe" in title.lower() else SPARKLINE_POSITIVE_COLOR
        elif history[-1] < history[0]:
            trend_color = SPARKLINE_POSITIVE_COLOR if "enflasyon" in title.lower() or "tüfe" in title.lower() else SPARKLINE_NEGATIVE_COLOR

    sparkline = sparkline_svg(history, width=90, height=26, stroke_color=trend_color)

    anomaly_badge = ""
    if is_anomaly:
        anomaly_badge = (
            f'<span class="badge contra" style="font-size:10px;padding:2px 6px;margin-left:auto;">'
            f'{icon("warning", 10)} Anomali'
            f'</span>'
        )
    elif expectation_diff:
        anomaly_badge = (
            f'<span class="badge neutral" style="font-size:10px;padding:2px 6px;margin-left:auto;">'
            f'{esc(expectation_diff)}'
            f'</span>'
        )

    card_html = f"""
<div class="card indicator-card" style="padding:var(--space-3);background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--radius-md);">
  <div class="row" style="justify-content:space-between;margin-bottom:var(--space-1);align-items:center;">
    <span style="font-size:var(--text-xs);font-weight:var(--weight-semibold);color:var(--color-fg-muted);">{esc(title)}</span>
    {anomaly_badge}
  </div>
  <div class="row" style="justify-content:space-between;align-items:flex-end;">
    <div>
      <span style="font-family:var(--font-mono);font-size:var(--text-lg);font-weight:var(--weight-bold);color:var(--color-fg);">{esc(current_value)}</span>
      <span style="font-size:var(--text-xs);color:var(--color-fg-subtle);margin-left:2px;">{esc(unit)}</span>
      {f'<div style="font-size:11px;color:var(--color-fg-subtle);margin-top:2px;">{esc(change_text)}</div>' if change_text else ''}
    </div>
    <div style="text-align:right;">
      {sparkline}
      {f'<div style="font-size:9px;color:var(--color-fg-subtle);margin-top:2px;">{esc(source_name)}</div>' if source_name else ''}
    </div>
  </div>
</div>
"""
    return mark_safe(card_html)


def bar_trend(
    points: Sequence[tuple[str, float]],
    *,
    target: float,
    higher_is_better: bool = True,
    unit: str = "",
    width: int = 400,
    height: int = 80,
) -> SafeString:
    """Metrik panosu için günlük çubuk eğilimi ve hedef çizgisi (F3-19)."""
    if not points:
        return mark_safe("")

    vals = [v for _, v in points]
    max_val = max(max(vals), target, 1.0)
    bars = []
    n = len(points)
    bar_width = max(4.0, (width - (n * 2)) / max(n, 1))

    for i, (day, val) in enumerate(points):
        x = i * (bar_width + 2)
        h = max(2.0, (val / max_val) * (height - 20))
        y = height - h - 10
        is_failing = (val < target) if higher_is_better else (val > target)
        color = "var(--color-partial)" if is_failing else "var(--color-chart-2)"
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{h:.1f}" '
            f'fill="{color}" rx="1"><title>{esc(day)}: {val:.2f}{esc(unit)}</title></rect>'
        )

    target_y = height - ((target / max_val) * (height - 20)) - 10
    target_line = (
        f'<line x1="0" y1="{target_y:.1f}" x2="{width}" y2="{target_y:.1f}" '
        f'stroke="var(--color-fg-muted)" stroke-dasharray="3 3" stroke-width="1.5" />'
    )
    svg = (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="overflow:visible;" aria-hidden="true">'
        f'{"".join(bars)}'
        f'{target_line}'
        f'</svg>'
    )
    return mark_safe(svg)


def render_knowledge_graph(
    nodes: list[dict[str, Any]],
    links: list[dict[str, Any]],
    *,
    width: int = 560,
    height: int = 240,
) -> SafeString:
    """Siyasi hafıza ilişkileri için sunucu taraflı SVG bilgi grafı (S2)."""
    if not nodes:
        return mark_safe('<div class="subtle">Grafik verisi yok.</div>')

    import math

    cx = width / 2
    cy = height / 2

    pos: dict[str, tuple[float, float]] = {}
    node_elements = []
    link_elements = []

    actor_nodes = [n for n in nodes if n.get("type") == "actor"]
    other_nodes = [n for n in nodes if n.get("type") != "actor"]

    if actor_nodes:
        pos[actor_nodes[0]["id"]] = (cx, cy)

    radius = min(width, height) * 0.38
    for i, n in enumerate(other_nodes):
        angle = (2 * math.pi * i) / max(len(other_nodes), 1) - (math.pi / 2)
        pos[n["id"]] = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))

    for lk in links:
        src = pos.get(lk["source"])
        tgt = pos.get(lk["target"])
        if src and tgt:
            rel = lk.get("relation", "")
            stroke_color = "var(--color-contra)" if rel in ("contradicts", "fails") else "var(--color-accent)"
            link_elements.append(
                f'<line x1="{src[0]:.1f}" y1="{src[1]:.1f}" x2="{tgt[0]:.1f}" y2="{tgt[1]:.1f}" '
                f'stroke="{stroke_color}" stroke-width="1.5" stroke-opacity="0.6"/>'
            )
            mid_x = (src[0] + tgt[0]) / 2
            mid_y = (src[1] + tgt[1]) / 2
            link_elements.append(
                f'<text x="{mid_x:.1f}" y="{mid_y:.1f}" font-size="9" fill="var(--color-fg-subtle)" '
                f'text-anchor="middle">{esc(rel)}</text>'
            )

    for nd in nodes:
        p = pos.get(nd["id"], (cx, cy))
        is_actor = nd.get("type") == "actor"
        r = 18 if is_actor else 12
        color = "var(--color-accent)" if is_actor else "var(--color-surface-sunken)"
        stroke = "var(--color-fg)" if is_actor else "var(--color-border-strong)"
        lbl = nd.get("label", "")

        node_elements.append(
            f'<g class="graph-node">'
            f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{r}" fill="{color}" stroke="{stroke}" stroke-width="1.5"/>'
            f'<text x="{p[0]:.1f}" y="{(p[1] + 26 if not is_actor else p[1] + 4):.1f}" font-size="11" '
            f'fill="var(--color-fg)" text-anchor="middle" font-weight="{"bold" if is_actor else "normal"}">{esc(lbl)}</text>'
            f'</g>'
        )

    svg = (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" '
        f'class="knowledge-graph" style="overflow:visible;" aria-hidden="true">'
        f'<g class="graph-links">{"".join(link_elements)}</g>'
        f'<g class="graph-nodes">{"".join(node_elements)}</g>'
        f'</svg>'
    )
    return mark_safe(svg)

