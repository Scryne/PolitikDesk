"""PolitikDesk Haber Masası / Kumanda Odası (War Room Live Monitor).

Büyük ekranlar, editoryal ekipler ve anlık gündem takibi için tasarlanmış
canlı, reaktif ve çok sütunlu editoryal kumanda merkezi.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from politikdesk.observability import get_logger
from politikdesk.users import current_user_id
from politikdesk.web import repository
from politikdesk.web.ui import format as fmt
from politikdesk.web.ui.charts import economic_indicator_card
from politikdesk.web.ui.components import (
    card,
    esc,
    event_badge,
    kpi,
    page_head,
    status_badge,
)
from politikdesk.web.ui.icons import icon
from politikdesk.web.ui.shell import ACTIVITY_JS, page

log = get_logger(__name__)
router = APIRouter(tags=["war_room"])


def _war_room_js() -> str:
    return """
(function(){
  var sseSource = null;
  function connectSSE(){
    if (window.EventSource) {
      try {
        sseSource = new EventSource('/api/events/stream');
        sseSource.addEventListener('event_updated', function(e){
          var data = JSON.parse(e.data || '{}');
          if (data && data.title) {
            window.pdToast('Yeni Gelişme: ' + data.title);
            var dot = document.getElementById('wr-live-dot');
            if (dot) {
              dot.style.background = 'var(--color-accent)';
              setTimeout(function(){ dot.style.background = 'var(--color-strong)'; }, 2000);
            }
          }
        });
      } catch (err) {}
    }
  }
  connectSSE();
})();
"""


def _indicator_strip() -> str:
    """Makro gösterge şeridi — **yalnızca kurumun kendi yayımladığı sayı.**

    ⛔ Buradaki sayılar bir dönem koda gömülüydü ve TÜİK/TCMB/Hazine
    imzasıyla gösteriliyordu. Ürünün sözleşmesi (Spec §15/13) kanıtta
    bulunmayan sayıyı yasaklar; kurum imzalı uydurma sayı bunun en ağır
    biçimiydi. Artık tek kaynak `articles.official_value`'dur
    (`repository.official_indicator_series`).

    Veri yoksa **hiçbir sayı üretilmez**: boş durum, boru hattının
    henüz resmî bir sayısal yayın toplamadığını açıkça söyler.
    """
    try:
        series = repository.official_indicator_series()
    except Exception as exc:  # noqa: BLE001
        log.warning("war_room_indicators_failed", error=str(exc))
        series = []

    if not series:
        return (
            '<div class="notice" style="margin-bottom:var(--space-6)">'
            f"<div>{icon('info', 16)}</div>"
            "<div><p><b>Resmî gösterge yayını beklemede.</b> Bu şerit yalnızca "
            "kurumun kendi makine okunur yayınından gelen sayıları gösterir "
            "(TÜİK SDMX gibi). Boru hattı henüz böyle bir yayım toplamadı; "
            "tahmini veya örnek sayı gösterilmez.</p></div></div>"
        )

    cards = []
    for entry in series[:6]:
        history = [float(v) for v in entry["history"]]
        unit = str(entry.get("unit") or "")
        latest = float(entry["latest_value"])
        previous = entry.get("previous_value")

        value_text = fmt.percent(latest, 1) if unit == "%" else fmt.number(latest, 1)

        if previous is None:
            change_text = f"{fmt.period_label(entry.get('latest_period'))} · ilk gözlem"
        else:
            delta = latest - float(previous)
            delta_text = fmt.signed_percent(delta, 1) if unit == "%" else fmt.number(delta, 1)
            change_text = f"{fmt.period_label(entry.get('latest_period'))} · {delta_text}"

        # Kaynağın kendi seri adı varsa o gösterilir ("ABD doları alış
        # kuru"); yoksa metrik anahtarı Türkçeye çevrilir. Ham anahtar
        # ("exchange_rate") hiçbir koşulda ekrana çıkmaz.
        baslik = entry.get("label") or fmt.metric_label(entry.get("metric"))

        cards.append(
            economic_indicator_card(
                str(baslik),
                value_text,
                "" if unit == "%" else unit,
                history,
                change_text,
                source_name=str(entry.get("source_name") or ""),
            )
        )

    return (
        '<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(220px,1fr));'
        'gap:var(--space-3);margin-bottom:var(--space-2);">' + "".join(cards) + "</div>"
        '<p class="subtle" style="margin:0 0 var(--space-6);font-size:var(--text-xs)">'
        "Bu şerit yalnızca kurumun kendi makine okunur yayınından gelen değerleri "
        "gösterir; türetilmiş veya tahmini sayı içermez.</p>"
    )


def _expected_publications() -> str:
    """BEKLENEN RESMÎ YAYINLAR (Spec §9.5 · Roadmap Faz 1.2).

    Ürünün "gizli kozu": yalnızca olanı değil, **olacağı** da bilmek.
    Kaynak Ulusal Veri Yayımlama Takvimi'dir — kurumların kendi ilan
    ettiği program, tahmin değil.

    Kaçırılan yayınlar ayrı gösterilir ve bu bilinçli: "kurum açıkladı
    ama biz görmedik", kaynak kadrosundaki kör noktayı başka hiçbir
    göstergenin söylemediği kadar doğrudan söyler.
    """
    from politikdesk.context import official_calendar as takvim

    try:
        bekleyen = takvim.upcoming(hours=48, limit=8)
        kacirilan = takvim.missed_report(days=3, limit=3)
    except Exception as exc:  # noqa: BLE001
        log.warning("war_room_calendar_failed", error=str(exc))
        return ""

    if not bekleyen and not kacirilan:
        return card(
            '<p class="subtle" style="margin:0;font-size:var(--text-xs)">'
            "Önümüzdeki 48 saatte takvimde resmî yayın görünmüyor.</p>",
            title="Beklenen resmî yayınlar",
        )

    satirlar = []
    for r in bekleyen:
        an = r["expected_at"].astimezone(takvim.CALENDAR_TZ)
        donem = f" · {esc(r['reference_period'])}" if r.get("reference_period") else ""
        satirlar.append(
            f'<div style="padding:var(--space-2) 0;border-bottom:1px solid var(--color-border)">'
            f'<div class="row tight" style="justify-content:space-between;align-items:baseline">'
            f'<span class="mono" style="font-size:var(--text-xs);color:var(--color-accent)">'
            f"{fmt.day_month(an)} {an:%H:%M}</span>"
            f'<span class="badge sm">{esc(r["institution"] or "")}</span></div>'
            f'<div style="font-size:var(--text-sm);margin-top:2px">{esc(r["title"])}</div>'
            f'<div class="subtle" style="font-size:var(--text-xs)">{donem.lstrip(" ·")}</div>'
            f"</div>"
        )

    kacirilan_html = ""
    if kacirilan:
        maddeler = "".join(
            f'<li style="margin-bottom:4px">{esc(r["institution"] or "")} — '
            f'{esc(r["title"][:70])}</li>'
            for r in kacirilan
        )
        kacirilan_html = (
            f'<div style="margin-top:var(--space-4)">'
            f'<p class="eyebrow" style="margin-bottom:var(--space-2);color:var(--color-contra)">'
            f"Yayımlandı, biz görmedik</p>"
            f'<ul style="margin:0;padding-left:18px;font-size:var(--text-xs);'
            f'color:var(--color-fg-muted)">{maddeler}</ul>'
            f'<p class="subtle" style="margin:var(--space-2) 0 0;font-size:var(--text-xs)">'
            f"Kurum yayımladı ama hiçbir kaynağımız haberleştirmedi — kaynak "
            f"kadrosunda kör nokta olabilir.</p></div>"
        )

    return card(
        "".join(satirlar) + kacirilan_html,
        title="Beklenen resmî yayınlar",
        actions=f'<span class="subtle" style="font-size:var(--text-xs)">'
        f"{fmt.plural_count(len(bekleyen), 'yayın')} · 48 saat</span>",
    )


def _anomaly_panel() -> str:
    """GÖSTERGE SAPMALARI (Roadmap Faz 3.1).

    ⛔ Bir anomali bir YORUM DEĞİLDİR. Kart yalnızca ölçümü gösterir:
    hangi seri, hangi dönem, ne kadar saptı, hangi yöntem, hangi eşik.
    "Sebebi şu" demez ve demeyecek — nedensellik kanıt ister.

    Durumlar açık yazılır (NORMAL / SAPMA / VERİ YETERSİZ / BAYAT /
    YOK); kırmızı-yeşil tek anlam taşımaz.
    """
    from politikdesk.analysis.pipeline import open_anomalies

    try:
        kayitlar = open_anomalies(limit=6)
    except Exception as exc:  # noqa: BLE001
        log.warning("war_room_anomaly_failed", error=str(exc))
        return ""

    if not kayitlar:
        return card(
            '<p class="subtle" style="margin:0;font-size:var(--text-sm)">'
            "İzlenen resmî göstergelerde açık sapma yok.</p>"
            '<p class="subtle" style="margin:var(--space-2) 0 0;font-size:var(--text-xs)">'
            "Sapma yokluğu doğruluk kanıtı değildir; yalnızca eşiğin "
            "aşılmadığını söyler.</p>",
            title="Gösterge sapmaları",
        )

    tonlar = {"critical": "bad", "high": "bad", "medium": "warn", "low": ""}
    satirlar = []
    for k in kayitlar:
        ton = tonlar.get(str(k["severity"]), "")
        birim = f" {k['unit']}" if k.get("unit") else ""
        oran = k.get("deviation_ratio")
        satirlar.append(
            f'<div style="padding:var(--space-2) 0;border-bottom:1px solid var(--color-border)">'
            f'<div class="row tight" style="justify-content:space-between;align-items:baseline">'
            f'<span style="font-size:var(--text-sm);font-weight:var(--weight-semibold)">'
            f"{esc(k['label'])}</span>"
            f'<span class="badge sm {ton}">SAPMA · {esc(str(k["severity"]).upper())}</span></div>'
            f'<div class="mono" style="font-size:var(--text-xs);margin-top:2px">'
            f"{esc(fmt.period_label(k['period']))} · "
            f"{esc(fmt.number(float(k['observed_value']), 2))}{esc(birim)}"
            + (f" · {oran:+.1f}σ" if oran is not None else "")
            + "</div>"
            f'<div class="subtle" style="font-size:var(--text-xs)">'
            f"{esc(k['source_name'])} · {esc(k['series_code'])} · "
            f"yöntem {esc(k['detection_method'])}, eşik {esc(str(k['threshold']))}, "
            f"{esc(fmt.plural_count(int(k['baseline_size']), 'gözlem'))}</div>"
            f"</div>"
        )

    return card(
        "".join(satirlar)
        + '<p class="subtle" style="margin:var(--space-4) 0 0;font-size:var(--text-xs)">'
        "Sapma bir <b>ölçümdür</b>, yorum değil: bir gözlemin kendi geçmişine "
        "göre eşiği aştığını söyler. Sebebi hakkında hiçbir iddiada bulunmaz — "
        "nedensellik kanıt ister.</p>",
        title="Gösterge sapmaları",
        actions=f'<span class="subtle" style="font-size:var(--text-xs)">'
        f"{fmt.plural_count(len(kayitlar), 'açık sapma')}</span>",
    )


@router.get("/war-room", response_class=HTMLResponse)
@router.get("/radar", response_class=HTMLResponse, include_in_schema=False)
def war_room_page() -> str:
    """Canlı Editoryal Kumanda Odası Görünümü."""
    user_id = current_user_id()
    try:
        events = repository.feed(user_id=user_id, limit=30)
    except Exception as exc:  # noqa: BLE001
        log.warning("war_room_feed_failed", error=str(exc))
        events = []

    # İstatistikler & Öne Çıkanlar
    strong_count = sum(1 for e in events if e.get("top_claim_status") == "strongly_corroborated")
    breaking_events = [e for e in events if (e.get("salience_score") or 0) >= 55]

    indicators_html = _indicator_strip()

    # Breaking News Bar
    breaking_cards = []
    for ev in breaking_events[:3]:
        sal = ev.get("salience_score", 0)
        breaking_cards.append(
            f'<div class="card" style="border-left:4px solid var(--color-accent);'
            f'background:var(--color-surface-sunken);margin-bottom:var(--space-2);padding:var(--space-3);">'
            f'<div class="row" style="justify-content:space-between;margin-bottom:4px;">'
            f'<span style="font-size:var(--text-xs);font-weight:var(--weight-bold);color:var(--color-accent);'
            f'display:flex;align-items:center;gap:4px;">{icon("zap", 12)} KRİTİK GÜNDEM ({sal}/90)</span>'
            f'<span style="font-size:var(--text-xs);color:var(--color-fg-subtle);">'
            f'{ev.get("article_count", 0)} Bağımsız Kaynak</span>'
            f'</div>'
            f'<a href="/event/{ev["id"]}" style="font-weight:var(--weight-semibold);font-size:var(--text-sm);'
            f'color:var(--color-fg);text-decoration:none;line-height:1.4;display:block;">'
            f'{esc(ev["title"])}</a>'
            f'</div>'
        )
    breaking_section = "".join(breaking_cards) if breaking_cards else (
        '<div style="color:var(--color-fg-subtle);font-size:var(--text-sm);padding:var(--space-2);">'
        'Şu anda 55+ skora sahip kritik gündem kırılması bulunmuyor.</div>'
    )

    # Event Ticker Table / Stream
    event_rows = []
    for ev in events:
        sal = ev.get("salience_score", 0)
        top_status = ev.get("top_claim_status", "unverified")
        src_count = ev.get("article_count", 0)
        clm_count = ev.get("claim_count", 0)

        badge = status_badge(top_status)
        ev_type_badge = event_badge(ev.get("status", "developing"))

        event_rows.append(
            f'<tr style="border-bottom:1px solid var(--color-border);">'
            f'<td style="padding:var(--space-3) var(--space-2);width:50px;text-align:center;">'
            f'<span style="font-family:var(--font-mono);font-size:var(--text-xs);font-weight:var(--weight-bold);'
            f'color:var(--color-accent);">{sal}</span></td>'
            f'<td style="padding:var(--space-3) var(--space-2);">'
            f'<a href="/event/{ev["id"]}" style="font-weight:var(--weight-semibold);color:var(--color-fg);'
            f'text-decoration:none;font-size:var(--text-sm);">{esc(ev["title"])}</a>'
            f'<div class="row" style="gap:var(--space-2);margin-top:4px;font-size:var(--text-xs);'
            f'color:var(--color-fg-muted);">'
            f'<span>{src_count} Kaynak</span> · <span>{clm_count} İddia</span>'
            f'</div></td>'
            f'<td style="padding:var(--space-3) var(--space-2);white-space:nowrap;">{badge}</td>'
            f'<td style="padding:var(--space-3) var(--space-2);white-space:nowrap;">{ev_type_badge}</td>'
            f'<td style="padding:var(--space-3) var(--space-2);text-align:right;white-space:nowrap;">'
            f'<a class="btn sm ghost" href="/event/{ev["id"]}" title="İncele">{icon("arrow-right", 12)}</a>'
            f'</td></tr>'
        )

    table_html = (
        '<div class="responsive-table">'
        '<table class="table-cards" style="width:100%;border-collapse:collapse;font-size:var(--text-sm);">'
        '<thead><tr style="border-bottom:2px solid var(--color-border);text-align:left;'
        'color:var(--color-fg-subtle);font-size:var(--text-xs);">'
        '<th style="padding:var(--space-2);text-align:center;">SKOR</th>'
        '<th style="padding:var(--space-2);">GÜNDEM BAŞLIĞI</th>'
        '<th style="padding:var(--space-2);">KANIT DURUMU</th>'
        '<th style="padding:var(--space-2);">AŞAMA</th>'
        '<th style="padding:var(--space-2);text-align:right;">EYLEM</th>'
        '</tr></thead><tbody>'
        + "".join(event_rows)
        + '</tbody></table></div>'
    )

    kpis = (
        f'<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));'
        f'gap:var(--space-4);margin-bottom:var(--space-6);">'
        f'{kpi("CANLI AKIŞ", f"{len(events)} Olay", delta_note="Son 24 saatte toplanan kümeler", icon_name="clock")}'
        f'{kpi("GÜÇLÜ TEYİTLİ", f"{strong_count}", delta_note="T1 ve çoklu bağımsız kaynak teyidi", icon_name="check")}'
        f'{kpi("KRİTİK GÜNDEM", f"{len(breaking_events)}", delta_note="Gündem skoru 55 ve üzeri olaylar", icon_name="zap")}'
        f'{kpi("HABER BORU HATTI", "Aktif", delta_note="5 dk periyodik otomatik tarama", icon_name="shield")}'
        f'</div>'
    )

    body = f"""
{
        page_head(
            "Haber Masası & Canlı Kumanda Odası",
            lede="Tüm canlı veri kaynaklarının, kanıt zincirlerinin ve anlık gündem kırılmalarının eşzamanlı izleme radarı.",
            badges='<span class="badge sm" style="background:var(--color-surface-sunken);color:var(--color-strong);display:inline-flex;align-items:center;gap:6px;"><span id="wr-live-dot" class="pulse-dot"></span> CANLI YAYIN</span>',
            actions='<a class="btn sm" href="/feed" title="Klasik Çalışma Masası">' + icon("feed", 13) + '<span>Gündem Masası</span></a>',
        )
    }

{kpis}

{indicators_html}

<div class="split">
  <div class="stack" style="flex:2">
    {card(table_html, title="Anlık Gündem & Olay Akışı")}
  </div>
  <div class="stack" style="flex:1;position:sticky;top:calc(var(--topbar-h) + 24px)">
    {card(breaking_section, title="Kritik Kırılmalar")}
    {_anomaly_panel()}
    {_expected_publications()}
    {
        card(
            # Bu listede YALNIZCA bu sayfada gerçekten çalışan kısayollar
            # bulunur. Önceden J/K ve X de yazıyordu; o ikisi `web/feed.py`
            # içindeki dinleyiciye bağlı ve bu sayfada hiçbir şey yapmıyordu.
            # Çalışmayan bir kısayol listesi, kısayol listesi olmamasından
            # kötüdür: kullanıcı tuşa basar, hiçbir şey olmaz, arayüzün
            # bozuk olduğunu düşünür.
            '<div style="font-size:var(--text-xs);color:var(--color-fg-muted);line-height:1.6;">'
            '<p style="margin:0 0 var(--space-2)"><b>Bu ekranda çalışan kısayollar:</b></p>'
            '<p style="margin:0 0 4px"><kbd class="shortcut-key">Ctrl</kbd> + '
            '<kbd class="shortcut-key">K</kbd> : Komuta paleti ve hızlı arama</p>'
            '<p style="margin:0 0 var(--space-3)"><kbd class="shortcut-key">Esc</kbd> : '
            "Açık pencereyi kapat</p>"
            '<p style="margin:0">Olaylar arası klavye gezintisi '
            '(<kbd class="shortcut-key">J</kbd> / <kbd class="shortcut-key">K</kbd>) ve hızlı '
            'X taslağı (<kbd class="shortcut-key">X</kbd>) '
            '<a href="/feed">Gündem Masası</a> ekranındadır.</p>'
            "</div>",
            title="Kumanda Kılavuzu",
        )
    }
  </div>
</div>
"""

    return page(
        "Haber Masası / Kumanda Odası",
        body,
        active="/war-room",
        crumbs=(("Kumanda Odası", "/war-room"),),
        extra_js=ACTIVITY_JS + _war_room_js(),
    )
