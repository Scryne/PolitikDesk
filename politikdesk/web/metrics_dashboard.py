"""Metrik panosu (F3-20 · Spec §13.3).

DoD: 8 metrik günlük olarak görüntüleniyor.

### Neden Metabase/Grafana değil

Yol Haritası F3-20 "Metabase/Grafana panosu" diyordu. İkisi de ayrı bir
konteyner, ayrı bir veritabanı bağlantısı ve panonun sürüm kontrolü
dışında kalan bir tanımı demek. Tek kullanıcılı bir araçta sekiz sayı
için bu, çalıştırılacak yeni bir servis ve bakımı yapılacak yeni bir
yapılandırma yükü getirir.

Panonun asıl işlevi Spec §13.4'ün haftalık ritüelidir: *"metrik panosu
gözden geçirilir, regresyon varsa kök neden aranır."* Bunun için gereken
şey hedefe göre durum (✓/✗) ve 30 günlük eğilimdir; ikisi de burada var
ve **testle korunuyor** — harici bir pano tanımı olamazdı.

Ham veri `metrics` tablosundadır; Grafana istenirse aynı tabloya
bağlanır, bu ekran onu engellemez.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from politikdesk import metrics
from politikdesk.web.layout import esc, page

router = APIRouter(prefix="/admin", tags=["admin", "metrics"])

_STATUS_STYLE = {
    "ok": ("var(--ok)", "✓ hedefte"),
    "off": ("var(--bad)", "✗ hedef dışı"),
    "no_data": ("var(--muted)", "— veri yok"),
}


def _format(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    if unit == "%":
        return f"{value:.0f}%"
    if unit == "oran":
        return f"{value:.3f}"
    return f"{value:,.1f}".replace(",", " ")


def _sparkline(points: list[dict], direction: str, target: float) -> str:
    """30 günlük eğilim — çubuklar, hedef çizgisi renkte.

    SVG/JS grafik kütüphanesi yok: sekiz metrik için bir bağımlılık
    eklemek, ekranın kendi gerekçesiyle çelişirdi.
    """
    if not points:
        return '<span class="meta">geçmiş yok</span>'
    values = [p["value"] for p in points[-30:]]
    top = max(values) or 1.0
    bars = "".join(
        f'<span title="{esc(p["day"])}: {p["value"]:.2f}" style="display:inline-block;'
        f"width:6px;margin-right:2px;vertical-align:bottom;"
        f'height:{max(2, int(28 * p["value"] / top))}px;'
        f"background:{'var(--ok)' if _hits(p['value'], direction, target) else 'var(--bad)'}"
        f'"></span>'
        for p in points[-30:]
    )
    return f'<div style="height:30px">{bars}</div>'


def _hits(value: float, direction: str, target: float) -> bool:
    return value <= target if direction == "lower" else value >= target


@router.get("/metrics", response_class=HTMLResponse)
def metrics_dashboard(days: int = Query(default=30, ge=1, le=365)) -> HTMLResponse:
    today = date.today()
    current = metrics.compute_metrics(today)
    past = metrics.history(days)

    cards = ""
    for metric in current:
        data = metric.as_dict()
        color, label = _STATUS_STYLE[data["status"]]
        arrow = "↓ düşük iyi" if data["direction"] == "lower" else "↑ yüksek iyi"
        cards += f"""
<div class="card" style="margin-bottom:.8rem">
  <div class="row">
    <b>{esc(data["label"])}</b>
    <span class="badge" style="color:{color}">{esc(label)}</span>
    <span style="margin-left:auto;font-size:1.5rem">
      {esc(_format(data["value"], data["unit"]))}
      <span class="meta" style="font-size:.8rem">{esc(data["unit"])}</span></span>
  </div>
  <div class="meta">Hedef {esc(data["target"])} {esc(data["unit"])} ({arrow}) ·
    örneklem {data["sample_size"]} · {esc(data["note"])}</div>
  <div style="margin-top:.5rem">
    {_sparkline(past.get(data["name"], []), data["direction"], float(data["target"]))}
  </div>
</div>"""

    rolled = sum(1 for name in past if past[name])
    body = f"""
<h1>Ürün metrikleri</h1>
<p class="meta">Spec §13.3'ün sekiz metriği · oran metrikleri 7 günlük kayan
  pencerede · {rolled}/8 metriğin günlük geçmişi var</p>

<div class="notice">
  <b>Daily active minutes'ın düşük olması hedeftir.</b> Ürünün vaadi zaman
  tasarrufudur, etkileşim değil; bu metriği yukarı çekmeye çalışan hiçbir
  özellik kabul edilmez (Spec §13.3).
</div>

<div style="margin-top:1rem">{cards}</div>

<h2>Günlük toplama</h2>
<p class="meta">Toplama her gece 23:50'de koşar (<code>metrics_rollup</code>).
  Elle koşmak için: <code>make metrics</code></p>
<button onclick="pdRollup()">Şimdi topla</button>
<span id="rollup-status" class="meta" style="margin-left:.6rem"></span>
"""
    js = """
async function pdRollup(){
  var s = document.getElementById('rollup-status');
  s.textContent = 'Hesaplanıyor…';
  var r = await fetch('/admin/metrics/rollup', {method:'POST'});
  var d = await r.json();
  s.textContent = r.ok ? (d.written + ' metrik yazıldı.') : 'Hata.';
  if (r.ok) setTimeout(function(){ location.reload(); }, 600);
}
"""
    return HTMLResponse(page("Metrikler", body, active="/admin/metrics", extra_js=js))


@router.post("/metrics/rollup")
def rollup(day: str | None = None) -> dict:
    """Günlük toplamayı elle tetikler (F3-19)."""
    target = date.fromisoformat(day) if day else date.today()
    return metrics.daily_rollup(target)


@router.get("/metrics/history")
def metric_history(days: int = Query(default=30, ge=1, le=365)) -> dict:
    return metrics.history(days)


@router.post("/metrics/backfill")
def backfill(days: int = Query(default=7, ge=1, le=90)) -> dict:
    """Geçmiş günleri toplar — pano ilk açıldığında eğilim boş kalmasın."""
    today = date.today()
    written = 0
    for offset in range(days):
        result = metrics.daily_rollup(today - timedelta(days=offset))
        written += int(result["written"])
    return {"days": days, "written": written}
