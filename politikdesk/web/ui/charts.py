"""Satır içi SVG grafikler (DESIGN.md Bölüm 8.2, 8.26).

### Neden grafik kütüphanesi yok

BRIEF `grafik_kutuphanesi: YOK`. recharts/echarts bir node araç zinciri
demek; iki kırmızı çizgiyi birden zorlar (G3 #7 p95 < 1,5 sn · CI'ın
ruff+mypy+pytest dışına çıkmaması). Bu üründe grafik ihtiyacı da buna
uygun: sekiz metriğin 30 günlük eğilimi ve birkaç dağılım çubuğu.

### Donut neden yok

Bölüm 8.13 donut'u tanımlıyor ama 8.12 şunu söylüyor: *"Sıralı dağılım
listesi donut'a göre HER ZAMAN daha okunaklıdır."* Bu üründeki dağılımlar
(kaynak kırılımı, kanıt durumu dağılımı) 4-6 kategorili ve karşılaştırma
amaçlı — liste hepsinde daha iyi. `components.distribution()` kullanılır.

### Bölüm 8.2'nin burada geçerli olan kuralları

  * Yatay grid çizgisi düz (dashed değil), opaklık %60. Dikey grid yok.
  * Eksen çizgisi ve tick işaretleri kapalı.
  * Hedef çizgisi grid DEĞİLDİR ve ondan ayrışır: kesikli çizilir.
  * Çubuk genişliği ≈ boşluğun 2 katı (Bölüm 8.26), ama PİKSEL tavanlı.

Alan/çizgi grafiği ve donut YOK — bu üründe ihtiyaç doğmadı. Bölüm 8.2'nin
alan dolgusu ve çizgi kalınlığı kuralları o gün buraya eklenir; şimdiden
kullanılmayan bir çizgi grafiği yazmak, bakımı yapılmayan bir API demek.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from politikdesk.web.ui.components import esc
from politikdesk.web.ui.format import number


def bar_trend(
    points: Sequence[tuple[str, float]],
    *,
    target: float,
    higher_is_better: bool,
    height: int = 96,
    unit: str = "",
) -> str:
    """Günlük ölçümler + hedef çizgisi.

    Renk disiplini: hedefi tutan çubuklar `chart-1` (mürekkep), tutmayanlar
    `partial` (amber). 30 çubuğu yeşil/kırmızı boyamak ekranı bir uyarı
    tarlasına çevirirdi — bu paletin tezi (doygunluk kanıt skalasının)
    metrik panosunda da geçerli. Bir şey yanlışsa **o çubuk** renklenir.

    Erişilebilirlik: grafik `role="img"` + `aria-label` taşır ve altındaki
    tablo aynı veriyi metin olarak verir; renk tek taşıyıcı değildir.
    """
    if not points:
        return ""

    # ── Ölçü PİKSEL tabanlıdır, yüzde değil ──
    #
    # İlk sürüm `viewBox="0 0 100 h"` + `preserveAspectRatio="none"` ile
    # yüzde genişlik kullanıyordu ve 2 veri noktasında her çubuk ~200px
    # genişliğe gerilerek grafiği bir renk bloğuna çeviriyordu. Çubuk
    # genişliği bir OKUNABİLİRLİK ölçüsüdür, konteynerin bir oranı değil:
    # tavan 14px, taban 3px. Az veri varsa grafik sola yaslanır ve sağı
    # boş kalır — bu doğru davranıştır, "2 gün veri var" bilgisini
    # görsel olarak da verir.
    max_bar, gap = 14, 6
    values = [value for _, value in points]
    ceiling = max([*values, target]) or 1.0
    pad_top, pad_bottom = 8, 4
    plot = height - pad_top - pad_bottom

    bar_w = max(3, min(max_bar, 26 - len(points) // 2))
    width = len(points) * (bar_w + gap)
    target_y = pad_top + plot - (target / ceiling) * plot

    bars = []
    for index, (day, value) in enumerate(points):
        hit = value >= target if higher_is_better else value <= target
        bar_h = max(1.5, (value / ceiling) * plot)
        x = index * (bar_w + gap)
        y = pad_top + plot - bar_h
        fill = "var(--color-chart-1)" if hit else "var(--color-partial)"
        bars.append(
            f'<rect x="{x}" y="{y:.1f}" width="{bar_w}" height="{bar_h:.1f}" '
            f'rx="1.5" fill="{fill}">'
            f"<title>{esc(day)}: {esc(number(value, 2))} {esc(unit)}</title></rect>"
        )

    missed = sum(
        1
        for _, value in points
        if not ((value >= target) if higher_is_better else (value <= target))
    )
    label = (
        f"{len(points)} günlük eğilim. {missed} gün hedef dışı, {len(points) - missed} gün hedefte."
    )
    return (
        f'<svg class="chart" role="img" aria-label="{esc(label)}" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        # Sola yaslı: az veri noktasında grafik ortalanmaz, soldan
        # başlar ve sağı boş kalır — bu doğru davranış.
        f'preserveAspectRatio="xMinYMid meet" '
        f'style="max-width:100%;height:{height}px">'
        # Taban çizgisi — yatay grid, düz (dashed değil), %60 opaklık.
        f'<line class="grid" x1="0" y1="{pad_top + plot}" x2="{width}" '
        f'y2="{pad_top + plot}"/>'
        # Hedef çizgisi: grid değil, bir EŞİK. Kesikli çizilir ki grid ile
        # karışmasın — Bölüm 8.2 "dashed değil" kuralı GRID içindir; eşik
        # farklı bir nesnedir ve ayrışması gerekir.
        f'<line x1="0" y1="{target_y:.1f}" x2="{width}" y2="{target_y:.1f}" '
        f'stroke="var(--color-border-strong)" stroke-width="1" '
        f'stroke-dasharray="3 3"/>'
        f"{''.join(bars)}</svg>"
    )


def sparkline(
    values: Sequence[float],
    *,
    width: int = 64,
    height: int = 20,
    color: str = "var(--color-accent)",
    label: str = "Eğilim grafiği",
) -> str:
    """Satır içi mini SVG kıvılcım (sparkline) çizgisi.

    Boyutlar kompakttır (varsayılan 64x20px); veri tablosu hücrelerine veya
    kart başlıklarının yanına satır içi gömülebilir.
    """
    if not values or len(values) < 2:
        return ""

    min_val = min(values)
    max_val = max(values)
    val_range = max_val - min_val if max_val != min_val else 1.0

    pad_y = 2.0
    plot_h = height - (2 * pad_y)
    step_x = width / (len(values) - 1)

    points = []
    for i, val in enumerate(values):
        x = i * step_x
        y = pad_y + plot_h - ((val - min_val) / val_range) * plot_h
        points.append(f"{x:.1f},{y:.1f}")

    points_str = " ".join(points)
    last_x = (len(values) - 1) * step_x
    last_y = pad_y + plot_h - ((values[-1] - min_val) / val_range) * plot_h

    return (
        f'<svg class="sparkline" role="img" aria-label="{esc(label)}" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="display:inline-block;vertical-align:middle;overflow:visible">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{points_str}"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="2" fill="{color}"/>'
        f"</svg>"
    )


def render_knowledge_graph(
    nodes: Sequence[dict[str, Any]],
    links: Sequence[dict[str, Any]],
    *,
    width: int = 760,
    height: int = 340,
    title: str = "Siyasi İlişki ve Hafıza Grafı",
) -> str:
    """Aktörler, kurumlar, yasalar ve vaatler arası ilişkileri çizen hafif SVG bilgi grafı."""
    if not nodes:
        return ""

    import math

    # Renk paleti eşlemeleri (Tasarım token'larına uyumlu)
    type_fills = {
        "actor": "var(--color-accent)",
        "institution": "var(--color-chart-1)",
        "promise": "var(--color-verified)",
        "event": "var(--color-surface-2)",
        "law": "var(--color-chart-2)",
    }
    rel_strokes = {
        "fulfils": "var(--color-verified)",
        "fails": "var(--color-contradicted)",
        "contradicts": "var(--color-contradicted)",
        "updates": "var(--color-partial)",
        "same_thread": "var(--color-border-strong)",
        "precedes": "var(--color-text-muted)",
    }

    # Düğümleri konumlandır (Halka / Düzenli Grid Düzeni)
    node_coords: dict[str, tuple[float, float]] = {}
    center_x = width / 2.0
    center_y = height / 2.0
    radius_x = min(width, height) * 0.38
    radius_y = min(width, height) * 0.35

    n_count = len(nodes)
    for i, node in enumerate(nodes):
        n_id = str(node.get("id", i))
        angle = (2 * math.pi * i) / max(n_count, 1) - (math.pi / 2)
        nx = center_x + radius_x * math.cos(angle)
        ny = center_y + radius_y * math.sin(angle)
        node_coords[n_id] = (nx, ny)

    # 1. Kenarları (Bağlantı Çizgileri) Çiz
    svg_links = []
    for link in links:
        src = str(link.get("source", ""))
        tgt = str(link.get("target", ""))
        rel = str(link.get("relation", "precedes"))
        rel_label = link.get("label", rel)

        if src in node_coords and tgt in node_coords:
            x1, y1 = node_coords[src]
            x2, y2 = node_coords[tgt]
            stroke = rel_strokes.get(rel, "var(--color-border-strong)")
            dash = ' stroke-dasharray="4 2"' if rel in ("contradicts", "fails") else ""

            # Kenar çizgisi
            svg_links.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{stroke}" stroke-width="1.8"{dash} opacity="0.75">'
                f'<title>{esc(src)} -> {esc(tgt)} ({esc(rel_label)})</title>'
                f'</line>'
            )

    # 2. Düğümleri Çiz
    svg_nodes = []
    for node in nodes:
        n_id = str(node.get("id", ""))
        label = str(node.get("label", n_id))
        n_type = str(node.get("type", "actor"))
        if n_id not in node_coords:
            continue

        nx, ny = node_coords[n_id]
        fill = type_fills.get(n_type, "var(--color-surface-2)")
        short_label = label if len(label) <= 18 else label[:16] + "…"

        svg_nodes.append(
            f'<g class="graph-node" transform="translate({nx:.1f},{ny:.1f})">'
            f'<circle r="14" fill="{fill}" stroke="var(--color-surface)" stroke-width="2">'
            f'<title>{esc(label)} ({esc(n_type)})</title></circle>'
            f'<text y="24" text-anchor="middle" font-size="11" '
            f'fill="var(--color-text)" font-family="var(--font-sans)">{esc(short_label)}</text>'
            f'</g>'
        )

    return (
        f'<svg class="knowledge-graph" role="img" aria-label="{esc(title)}" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="max-width:100%;height:auto;background:var(--color-surface);'
        f'border:1px solid var(--color-border);border-radius:var(--radius-lg);">'
        f'<g class="graph-links">{"".join(svg_links)}</g>'
        f'<g class="graph-nodes">{"".join(svg_nodes)}</g>'
        f'</svg>'
    )


