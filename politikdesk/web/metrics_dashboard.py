"""Metrik panosu (F3-20 · Spec §13.3).

DoD: 8 metrik günlük olarak görüntüleniyor.

### Neden Metabase/Grafana değil

Yol Haritası F3-20 "Metabase/Grafana panosu" diyordu. İkisi de ayrı bir
konteyner, ayrı bir veritabanı bağlantısı ve panonun sürüm kontrolü dışında
kalan bir tanımı demek. Tek kullanıcılı bir araçta sekiz sayı için bu,
çalıştırılacak yeni bir servis ve bakımı yapılacak yeni bir yapılandırma
yükü getirir.

Panonun asıl işlevi Spec §13.4'ün haftalık ritüelidir: *"metrik panosu
gözden geçirilir, regresyon varsa kök neden aranır."* Bunun için gereken
şey hedefe göre durum (✓/✗) ve 30 günlük eğilimdir; ikisi de burada var ve
**testle korunuyor** — harici bir pano tanımı olamazdı.

Ham veri `metrics` tablosundadır; Grafana istenirse aynı tabloya bağlanır,
bu ekran onu engellemez.

### Bu sayfanın tek işi (BRIEF `birincil_is`)

> "Ürün sözünü tutuyor mu, hangi metrik hedef dışı?"

Bu yüzden **hedef dışı metrikler listenin başında** durur ve sayfanın en
büyük tipografisi "kaç metrik hedefte" sayısıdır. Sekiz metriği alfabetik
veya sabit sırada dizmek, kullanıcıyı sekizini de okumaya zorlardı —
Bölüm 8.1: 4'ten fazla eşit ağırlıklı kart okunmaz.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from politikdesk import metrics
from politikdesk.web.ui import (
    button,
    card,
    charts,
    esc,
    kpi,
    notice,
    page,
    page_head,
)
from politikdesk.web.ui import format as fmt

router = APIRouter(prefix="/admin", tags=["admin", "metrics"])

_STATUS = {
    "ok": ("strong", "hedefte"),
    "off": ("contra", "hedef dışı"),
    "no_data": ("neutral", "veri yok"),
}

# Hedef dışı olanlar önce, sonra veri yok, en sonda hedefte olanlar.
_ORDER = {"off": 0, "no_data": 1, "ok": 2}


def _value_and_unit(value: float | None, unit: str) -> tuple[str, str]:
    """Değeri ve GÖSTERİLECEK birimi ayrı döner.

    Yüzde metrikleri Türkçede işareti **önde** taşır (`%20`, Ek B.1); ayrıca
    bir de arkasına `%` basmak `%20 %` üretiyordu. Birim, sayının içine
    girdiği durumda ayrıca yazılmaz.
    """
    if value is None:
        return fmt.EMPTY, unit
    if unit == "%":
        return fmt.percent(value, 1), ""
    if unit == "oran":
        return fmt.number(value, 3), unit
    return fmt.number(value, 1), unit


def _metric_card(data: dict, history: list[dict]) -> str:
    token, label = _STATUS[data["status"]]
    higher_is_better = data["direction"] != "lower"
    arrow = "düşük iyi" if data["direction"] == "lower" else "yüksek iyi"

    value, unit = _value_and_unit(data["value"], data["unit"])
    target_value, target_unit = _value_and_unit(float(data["target"]), data["unit"])
    unit_html = f'<span class="kpi-unit">{esc(unit)}</span>' if unit else ""

    window = history[-30:]
    trend = charts.bar_trend(
        [(str(point["day"]), float(point["value"])) for point in window],
        target=float(data["target"]),
        higher_is_better=higher_is_better,
        unit=data["unit"],
    )
    # Eğilim yoksa açıklama satırı da basılmaz — boş bir grafiğin altına
    # "amber çubuklar…" yazmak, olmayan bir şeyi tarif etmektir.
    trend_block = (
        f'<div style="margin-top:var(--space-4)">{trend}</div>'
        f'<p class="subtle" style="margin:6px 0 0;font-size:11px">'
        f"{esc(fmt.plural_count(len(window), 'günlük eğilim'))} · "
        f"kesikli çizgi hedef · amber çubuklar hedefin dışında kalan günler</p>"
        if window
        else '<p class="subtle" style="margin:var(--space-4) 0 0;'
        'font-size:var(--text-xs)">Günlük geçmiş henüz yok — '
        "aşağıdan geçmiş günleri toplayabilirsin.</p>"
    )

    return card(
        f"""
<div class="row" style="align-items:flex-start;flex-wrap:nowrap">
  <div style="min-width:0">
    <div class="kpi-label">{esc(data["label"])}</div>
    <div class="kpi-value" style="margin-top:6px">{esc(value)}{unit_html}</div>
  </div>
  <span class="spacer badge {token}">{esc(label)}</span>
</div>
<p class="subtle" style="margin:var(--space-3) 0 0;font-size:var(--text-xs)">
  Hedef <b class="num">{esc(target_value)}</b> {esc(target_unit)} ({arrow}) ·
  örneklem <span class="num">{esc(fmt.number(data["sample_size"]))}</span>
</p>
<p class="subtle" style="margin:4px 0 0;font-size:var(--text-xs)">
  {esc(data["note"])}</p>
{trend_block}""",
        cls="metric",
    )


@router.get("/metrics", response_class=HTMLResponse)
def metrics_dashboard(days: int = Query(default=30, ge=1, le=365)) -> HTMLResponse:
    today = date.today()
    try:
        current = [metric.as_dict() for metric in metrics.compute_metrics(today)]
        past = metrics.history(days)
    except Exception:  # noqa: BLE001
        current = []
        past = {}

    on_target = sum(1 for d in current if d["status"] == "ok")
    off_target = sum(1 for d in current if d["status"] == "off")
    no_data = sum(1 for d in current if d["status"] == "no_data")
    with_history = sum(1 for name in past if past[name])

    ordered = sorted(current, key=lambda d: (_ORDER[d["status"]], d["label"]))
    cards = "".join(_metric_card(d, past.get(d["name"], [])) for d in ordered)

    lede = (
        "Ürünün sekiz sağlık metriği. Oran metrikleri 7 günlük kayan pencerede "
        "hesaplanır; hedef dışı olanlar listenin başında durur."
    )

    body = f"""
{
        page_head(
            "Ürün metrikleri",
            lede=lede,
            actions=button("Şimdi topla", icon_name="refresh", action="rollup")
            + '<span id="rollup-status" class="subtle" aria-live="polite" '
            'style="font-size:var(--text-xs)"></span>',
        )
    }
<div class="stack">
  <div class="kpis">
    {kpi("Hedefte", fmt.number(on_target), unit=f"/ {len(current)} metrik", icon_name="check")}
    {kpi("Hedef dışı", fmt.number(off_target), unit="metrik", icon_name="warning")}
    {kpi("Veri yok", fmt.number(no_data), unit="metrik", icon_name="clock")}
    {
        kpi(
            "Günlük geçmişi olan",
            fmt.number(with_history),
            unit=f"/ {len(current)} metrik",
            icon_name="metrics",
        )
    }
  </div>

  {
        notice(
            "<p><b>Daily active minutes'ın düşük olması hedeftir.</b></p>"
            "<p>Ürünün vaadi zaman tasarrufudur, etkileşim değil; bu metriği yukarı "
            "çekmeye çalışan hiçbir özellik kabul edilmez.</p>"
        )
    }

  <div class="halves">{cards}</div>

  {
        card(
            '<p style="margin:0">Toplama her gece 23:50\'de koşar '
            '(<span class="mono">metrics_rollup</span>). Pano ilk açıldığında eğilim '
            "boş kalmasın diye geçmiş günler toplanabilir.</p>"
            '<div class="btn-row" style="margin-top:var(--space-4)">'
            + button("Son 7 günü topla", action="backfill", action_args=(7,))
            + button("Son 30 günü topla", action="backfill", action_args=(30,))
            + "</div>",
            title="Günlük toplama",
        )
    }
</div>
"""
    js = """
async function pdRun(url, note){
  var s = document.getElementById('rollup-status');
  s.textContent = note;
  try {
    var r = await fetch(url, {method:'POST'});
    if (!r.ok) throw new Error(r.status);
    var d = await r.json();
    s.textContent = (d.written || 0) + ' metrik yazıldı.';
    setTimeout(function(){ location.reload(); }, 600);
  } catch (e) {
    s.textContent = 'Toplanamadı. Veritabanına ulaşılamıyor olabilir.';
  }
}
function pdRollup(){ pdRun('/admin/metrics/rollup', 'Hesaplanıyor…'); }
function pdBackfill(n){
  pdRun('/admin/metrics/backfill?days=' + n, n + ' gün toplanıyor…');
}
window.pdAction('rollup', pdRollup);
window.pdAction('backfill', pdBackfill);
"""
    return HTMLResponse(
        page(
            "Metrikler",
            body,
            active="/admin/metrics",
            crumbs=(("Denetim", None), ("Metrikler", None)),
            extra_js=js,
        )
    )


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
