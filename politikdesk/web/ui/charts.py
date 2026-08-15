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
        f"{len(points)} günlük eğilim. "
        f"{missed} gün hedef dışı, {len(points) - missed} gün hedefte."
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

