"""Gündem ekranı ve X (Twitter) Yayın Merkezi (F3-02, F3-07, F3-18 · Spec §14.1 kalem 1).

F3-02 DoD: salience sıralı olay kartları; her kartta durum rozeti, kaynak
sayısı kırılımı, son güncelleme; **30 sn'de bir sessiz yenileme** ve **entegre X yayın köprüsü**.

### Bu sayfanın tek işi (BRIEF `birincil_is`)

> "Şu an gündemde ne var, hangisi hakkında GÜVENLE yazabilirim ve X paylaşımım hazır mı?"
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from politikdesk.editorial.generator import ANGLES
from politikdesk.evidence.explain import KIND_LABELS
from politikdesk.observability import get_logger
from politikdesk.users import current_user_id, touch_last_seen
from politikdesk.web import repository
from politikdesk.web.ui import (
    ACTIVITY_JS,
    button,
    esc,
    event_badge,
    filtered_empty_state,
    icon,
    kpi,
    page,
    page_head,
    panel,
    ruled,
    search_input,
    segment,
)
from politikdesk.web.ui import format as fmt

log = get_logger(__name__)

router = APIRouter(tags=["web"])

REFRESH_SECONDS = 30

_COMPONENT_LABELS = {
    "independent_sources": "Bağımsız kaynak sayısı",
    "tier_weight": "Kaynak kalitesi (en iyi tier)",
    "velocity": "Yayılma hızı (ilk 60 dk)",
    "key_entity": "Anahtar varlık",
    "primary_source": "Birincil kaynak",
    "freshness": "Tazelik",
}

_PENALTY_LABELS = {
    "weak_evidence_and_stale": "Zayıf kanıt + bayatlama",
    "weak_evidence": "Zayıf kanıt",
    "stale": "Bayatlama",
}

FILTERS: tuple[tuple[str, str], ...] = (
    ("all", "Tümü"),
    ("ready", "Yazıma hazır"),
    ("drafts", "Tweeti hazır"),
    ("pending", "Teyit bekliyor"),
    ("review", "Denetimde"),
)


def _is_ready(row: dict[str, Any]) -> bool:
    """Üretim kapısının feed'den görülebilen iki koşulu (`guards.py`)."""
    return bool(row.get("claim_count")) and bool(row.get("evidence_count"))


def _matches(row: dict[str, Any], selected: str) -> bool:
    if selected == "ready":
        return _is_ready(row)
    if selected == "drafts":
        return bool(row.get("latest_draft"))
    if selected == "pending":
        return bool(row.get("weak_claim_count")) or not row.get("claim_count")
    if selected == "review":
        return row.get("review_flag") == "needs_review"
    return True


def _evidence_tone(row: dict[str, Any]) -> str:
    """Kanıt cetvelinin durumu."""
    claims = int(row.get("claim_count") or 0)
    weak = int(row.get("weak_claim_count") or 0)
    if int(row.get("contradicted_count") or 0):
        return "contradicted"
    if not claims:
        return "unverified"
    if weak == 0:
        return "strongly_corroborated"
    if weak < claims:
        return "partially_corroborated"
    return "single_source"


def _breakdown_text(raw: dict[str, Any] | None) -> str:
    """`{'official':1,'media':3}` → `Resmî 1 · Medya 3`."""
    if not raw:
        return "kaynak kırılımı yok"
    return " · ".join(
        f"{KIND_LABELS.get(kind, kind)} {count}" for kind, count in sorted(raw.items()) if count
    )


def _evidence_line(row: dict[str, Any]) -> str:
    """Kanıt durumunun kesin ifadesi — cetvelin yanındaki OLGU."""
    claims = int(row.get("claim_count") or 0)
    weak = int(row.get("weak_claim_count") or 0)
    contra = int(row.get("contradicted_count") or 0)
    groups = int(row.get("independence_groups") or 0)

    parts: list[str] = []
    if not claims:
        parts.append("iddia çıkarılmadı")
    elif weak == 0:
        parts.append(f"{claims} iddia · tümü teyitli")
    else:
        parts.append(f"{claims} iddia · {claims - weak} teyitli")
    if contra:
        parts.append(f"{contra} çelişkili")
    if groups < 2:
        parts.append("tek yayın grubu")
    if row.get("review_flag") == "needs_review":
        parts.append("denetimde")
    return " · ".join(parts)


def _salience_panel(row: dict[str, Any]) -> str:
    """Skora tıklayınca açılan kırılım (F3-07)."""
    breakdown = row.get("salience_breakdown") or {}
    components = breakdown.get("components") or {}

    rows = "".join(
        f"<tr><td>{esc(_COMPONENT_LABELS.get(key, key))}</td>"
        f"<td class='num mono'>{esc(fmt.number(float(value), 2))}</td></tr>"
        for key, value in sorted(components.items())
        if isinstance(value, int | float)
    )
    rows += "".join(
        f"<tr><td>{esc(_PENALTY_LABELS.get(key, key))}</td>"
        f"<td class='num mono' style='color:var(--color-contra)'>"
        f"−{esc(fmt.number(float(value), 2))}</td></tr>"
        for key, value in sorted((breakdown.get("penalties") or {}).items())
        if isinstance(value, int | float)
    )

    body = f"""<table>
  <thead><tr><th>Bileşen</th><th class="num">Puan</th></tr></thead>
  <tbody>
  {rows or "<tr><td colspan='2' class='subtle'>Kırılım henüz hesaplanmadı.</td></tr>"}
  <tr><td><b>Global toplam</b> <span class="subtle">(0–90)</span></td>
      <td class="num mono"><b>{esc(fmt.number(row["global_salience"]))}</b></td></tr>
  <tr><td>Kişisel ayarlama <span class="subtle">(0–10, saklanmaz)</span></td>
      <td class="num mono">+{esc(fmt.number(row["personal_salience"]))}</td></tr>
  </tbody>
</table>
<p class="subtle" style="margin:12px 0 0;font-size:var(--text-xs)">
  Bu bir <b>önem</b> skorudur, <b>doğruluk skoru değildir.</b> Yüksek skor
  iddianın doğru olduğu anlamına gelmez; gündemde ne kadar yer tuttuğunu
  gösterir. Formül kural tabanlıdır ve beğeni/paylaşım gibi
  etkileşim girdisi içermez (Spec §8.4, §15 madde 14).</p>"""

    summary = (
        f"{icon('shield', 14)}<span>Önem "
        f'<b class="num">{esc(fmt.number(row["displayed_salience"]))}</b></span>'
        f'<span class="subtle">— kırılımı gör</span>'
    )
    return panel(summary, body, cls="quiet")


def _tweet_module(row: dict[str, Any]) -> str:
    """Gündem kartı içi X (Twitter) yayın ve hızlı üretim modülü."""
    event_id = row["id"]
    latest = row.get("latest_draft")
    ready = _is_ready(row)

    if latest and latest.get("is_grounded"):
        draft_id = latest["id"]
        body_text = latest.get("body") or ""
        angle_key = latest.get("angle") or "inform"
        angle_label = ANGLES.get(angle_key, (angle_key, ""))[0]
        char_len = len(body_text)
        is_thread = char_len > 280

        encoded_tweet = urllib.parse.quote(body_text)
        intent_url = f"https://x.com/intent/tweet?text={encoded_tweet}"
        body_json = json.dumps(body_text)

        status_pill = (
            f'<span class="badge strong" style="font-size:11px;height:18px">{char_len}/280 X Uyumlu</span>'
            if not is_thread
            else f'<span class="badge neutral" style="font-size:11px;height:18px">{char_len} Karakter (Thread)</span>'
        )

        return f"""
        <div class="feed-tweet-box" id="tweet-box-{event_id}" data-has-draft="true">
          <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:var(--space-2)">
            <div class="row tight" style="align-items:center">
              <span class="badge accent" style="font-size:11px;height:18px">{icon("share", 11)}X Tweeti Hazır</span>
              <span class="subtle" style="font-size:var(--text-xs)">Açı: <b>{esc(angle_label)}</b></span>
              {status_pill}
            </div>
            <div class="row tight">
              <button class="btn sm ghost" type="button" onclick='pdCopy({body_json}, "X Tweeti")' title="Tweet metnini kopyala">
                {icon("copy", 12)}<span>Kopyala</span>
              </button>
              <a class="btn sm primary" href="{intent_url}" target="_blank" rel="noopener noreferrer" title="Yeni sekmede X'te aç">
                {icon("share", 12)}<span>X'te Paylaş</span>
              </a>
            </div>
          </div>
          <textarea class="feed-tweet-textarea" readonly onclick="this.select()" aria-label="X Tweet Taslağı">{esc(body_text)}</textarea>
          <div class="row" style="justify-content:space-between;align-items:center;margin-top:var(--space-2);font-size:var(--text-xs)">
            <span class="subtle mono">Doğrulanmış kanıt kütüğüne bağlı</span>
            <div class="row tight">
              <a href="/draft/{draft_id}" class="subtle plain" style="font-size:var(--text-xs)">{icon("edit", 11)}Stüdyoda Düzenle &rarr;</a>
            </div>
          </div>
        </div>
        """

    if not ready:
        return f"""
        <div class="row tight" style="margin-top:var(--space-2);font-size:var(--text-xs);color:var(--color-fg-subtle)">
          <span class="badge neutral" style="font-size:11px;height:18px">{icon("clock", 11)}Kanıt bekleniyor</span>
          <span class="subtle">Yeterli kanıt oluşmadan tweet üretimi kapalıdır (Spec §12.1).</span>
        </div>
        """

    # Olay yazıma hazır ama henüz taslak üretilmemiş
    angle_chips = "".join(
        f'<button class="btn sm ghost" type="button" onclick="pdQuickDraft({event_id}, \'{key}\', this)" style="font-size:11px;height:22px;padding:0 6px">'
        f'{esc(ANGLES[key][0])}</button>'
        for key in ANGLES
    )

    return f"""
    <div class="feed-tweet-box" id="tweet-box-{event_id}" data-has-draft="false" style="padding:var(--space-2) var(--space-3)">
      <div class="row" style="justify-content:space-between;align-items:center">
        <div class="row tight" style="align-items:center">
          <span class="badge neutral" style="font-size:11px;height:18px">{icon("zap", 11)}X Tweeti</span>
          <span class="subtle" style="font-size:var(--text-xs)">Açı seç & 1-tıkla hazırla:</span>
          {angle_chips}
        </div>
        <button class="btn sm ghost" type="button" onclick="pdQuickDraft({event_id}, 'inform', this)" style="font-size:12px">
          {icon("zap", 12)}<span>Hızlı Üret</span>
        </button>
      </div>
    </div>
    """


def _card(row: dict[str, Any]) -> str:
    """Gündem kartı — iki sütun: anlatı solda, KARAR ve X yayın modülü sağda/altta."""
    ready = _is_ready(row)
    has_draft = bool(row.get("latest_draft"))

    verdict = (
        f'<span class="badge strong">{icon("check", 13)}kanıta bağlı</span>'
        if ready
        else f'<span class="badge neutral">{icon("clock", 13)}kanıt bekliyor</span>'
    )
    draft_badge = (
        f'<span class="badge accent" style="font-size:11px">{icon("share", 11)}Tweet Hazır</span>'
        if has_draft
        else ""
    )

    body = f"""
  <div class="feed-main">
    <div class="row" style="font-size:var(--text-xs);color:var(--color-fg-subtle);justify-content:space-between">
      <div class="row tight">
        {event_badge(row["status"])}
        <span>{esc(_breakdown_text(row.get("source_breakdown")))}</span>
        <span>· {esc(fmt.plural_count(int(row["article_count"] or 0), "makale"))}</span>
        <span>· {esc(fmt.plural_count(int(row["independent_count"] or 0), "bağımsız teyit"))}</span>
      </div>
      <div class="row tight">
        {draft_badge}
      </div>
    </div>
    <h3 style="margin:8px 0 6px">
      <a class="plain" href="/event/{row["id"]}">{esc(row["title"])}</a></h3>
    <p class="claim-text" style="margin:0 0 10px;font-size:var(--text-sm);
       color:var(--color-fg-muted)">{esc(_evidence_line(row))}</p>
    {_salience_panel(row)}
    {_tweet_module(row)}
  </div>
  <div class="feed-aside">
    {verdict}
    <span class="subtle" style="font-size:var(--text-xs)"
          title="{esc(fmt.precise(row["last_update_at"]))}">
      {esc(fmt.relative(row["last_update_at"]))}</span>
    <a class="btn sm ghost" href="/event/{row["id"]}" style="margin-top:var(--space-2)">
      {icon("arrow-right", 12)}<span>Detay</span>
    </a>
  </div>"""

    search_blob = f"{row['title']} {_evidence_line(row)} {row['status']}".replace('"', "&quot;")
    return (
        f'<div data-event-id="{row["id"]}" data-search="{esc(search_blob)}">'
        + ruled(_evidence_tone(row), f'<article class="card feed-card" id="event-card-{row["id"]}">{body}</article>', cls="feed-card-wrap")
        + "</div>"
    )


def _summary_kpis(rows: list[dict[str, Any]]) -> str:
    """Sol üstteki cevap. Sıra hiyerarşiktir."""
    ready = sum(1 for row in rows if _is_ready(row))
    with_drafts = sum(1 for row in rows if row.get("latest_draft"))
    weak_claims = sum(int(row.get("weak_claim_count") or 0) for row in rows)
    in_review = sum(1 for row in rows if row.get("review_flag") == "needs_review")

    return f"""<div class="kpis" style="margin-bottom:var(--space-6)">
<a href="/feed?f=ready" class="plain">{kpi("Yazıma hazır", fmt.number(ready), unit="olay", icon_name="shield")}</a>
<a href="/feed?f=drafts" class="plain">{kpi("Tweeti hazır", fmt.number(with_drafts), unit="taslak", icon_name="share")}</a>
<a href="/feed?f=pending" class="plain">{kpi("Teyit bekleyen", fmt.number(weak_claims), unit="iddia", icon_name="clock")}</a>
<a href="/feed?f=review" class="plain">{kpi("Denetimde", fmt.number(in_review), unit="olay", icon_name="warning")}</a>
</div>"""


def _strip(summary: dict[str, Any]) -> str:
    """ "Sen yokken ne oldu" şeridi (F3-18) — tek satır."""
    from politikdesk.web.ui import notice

    if not summary.get("available"):
        return notice(
            "<p><b>İlk ziyaretin.</b> Gündem salience sırasına göre dizilidir; "
            "skor önemi gösterir, doğruluğu değil.</p>"
        )
    total = summary.get("total", 0)
    if not total:
        return notice("<p>Son ziyaretinden bu yana yeni olay yok.</p>")

    top = summary.get("top_title")
    tail = f" En önemlisi: <b>{esc(top)}</b>." if top else ""
    return notice(
        f"<p>Sen yokken <b>{fmt.number(total)}</b> yeni olay eklendi, "
        f"<b>{fmt.number(summary.get('important', 0))}</b> tanesi önemli.{tail}</p>"
    )


def _cards_html(rows: list[dict[str, Any]], selected: str) -> str:
    """Kart listesi."""
    if not rows:
        from politikdesk.web.ui import empty_state

        return empty_state(
            "Henüz olay yok",
            "Boru hattı her 5 dakikada bir toplar. İlk turu hemen çalıştırmak "
            "için terminalde `pd ingest` yaz; ardından `pd cluster` ile "
            "haberler olaya dönüşür.",
            action=button("Boru hattını gör", href="/admin/", variant="primary"),
        )

    visible = [row for row in rows if _matches(row, selected)]
    if not visible:
        label = dict(FILTERS).get(selected, selected)
        return filtered_empty_state(
            f"“{label}” filtresi {fmt.plural_count(len(rows), 'olayın')} hiçbiriyle "
            f"eşleşmedi. Gündem dolu — bu filtre şu an boş.",
            "/feed",
        )
    return "".join(_card(row) for row in visible)


_SHORTCUTS_MODAL = f"""
<div id="shortcuts-modal" class="shortcuts-backdrop" onclick="if(event.target===this)pdToggleShortcuts()">
  <div class="shortcuts-modal">
    <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:var(--space-4)">
      <h3 style="margin:0;font-size:var(--text-lg)">Klavye Kısayolları</h3>
      <button class="btn sm ghost" type="button" onclick="pdToggleShortcuts()">{icon("close", 14)}</button>
    </div>
    <div class="shortcut-row"><span>Sonraki olay</span><span class="shortcut-key">J</span></div>
    <div class="shortcut-row"><span>Önceki olay</span><span class="shortcut-key">K</span></div>
    <div class="shortcut-row"><span>X Tweeti hazırla / odaklan</span><span class="shortcut-key">X veya T</span></div>
    <div class="shortcut-row"><span>Seçili tweeti / başlığı kopyala</span><span class="shortcut-key">C</span></div>
    <div class="shortcut-row"><span>Olay detayını aç</span><span class="shortcut-key">Enter veya O</span></div>
    <div class="shortcut-row"><span>Gündemde anlık arama</span><span class="shortcut-key">/</span></div>
    <div class="shortcut-row"><span>Kısayol penceresini aç/kapat</span><span class="shortcut-key">?</span></div>
  </div>
</div>
"""


@router.get("/", response_class=HTMLResponse)
@router.get("/feed", response_class=HTMLResponse)
def feed_page(
    limit: int = Query(default=40, ge=1, le=200),
    f: str = Query(default="all"),
) -> str:
    selected = f if f in dict(FILTERS) else "all"
    try:
        user_id = current_user_id()
        previous_visit = touch_last_seen(user_id)
        summary = repository.since_last_visit(user_id, previous_visit)
        rows = repository.feed(user_id, limit=limit)
    except Exception as exc:  # noqa: BLE001
        log.warning("feed_db_unavailable", error=str(exc))
        summary = {}
        rows = []

    counts = {key: sum(1 for row in rows if _matches(row, key)) for key, _ in FILTERS}
    tabs = segment(
        tuple(
            (
                f"{label} · {fmt.number(counts[key])}",
                f"/feed?f={key}" + (f"&limit={limit}" if limit != 40 else ""),
                key == selected,
            )
            for key, label in FILTERS
        )
    )

    actions_html = (
        search_input("feed-search", "Gündemde ara… [/]", oninput="pdSearchFeed(this.value)")
        + f'<button class="btn sm ghost" type="button" onclick="pdToggleView()" id="view-toggle" title="Görünüm değiştir">'
        f'{icon("grid", 13)}<span id="view-mode-label">Kompakt</span></button>'
        f'<button class="btn sm ghost" type="button" onclick="pdToggleShortcuts()" title="Klavye Kısayolları (?)">'
        f'{icon("info", 13)}<span>Kısayollar</span></button>'
        + button("Yenile", icon_name="refresh", onclick="pdRefresh()")
    )

    body = f"""
{
        page_head(
            "Gündem & X Yayın Merkezi",
            lede="Makro ekonomi olayları, kanıt gücü ve hazır X (Twitter) yayın taslakları.",
            actions=actions_html,
        )
    }
<div class="stack">
  {_strip(summary)}
  {_summary_kpis(rows)}
  <div class="row" style="justify-content:space-between;align-items:center">
    <div class="row tight" style="align-items:center">
      <span class="subtle" style="font-size:var(--text-xs);display:flex;align-items:center;gap:4px">
        {icon("filter", 12)}Filtrele:
      </span>
      {tabs}
    </div>
    <span class="subtle row tight" style="font-size:var(--text-xs)"
          id="pd-refreshed" aria-live="polite">
      <span class="pulse-dot"></span>
      <span>{esc(fmt.plural_count(REFRESH_SECONDS, "saniyede"))} bir sessizce yenilenir</span>
    </span>
  </div>
  <div id="cards" class="stack-sm">{_cards_html(rows, selected)}</div>
  <div id="feed-search-empty" style="display:none;padding:var(--space-12);text-align:center">
    <p class="subtle">Arama kriterinize uygun gündem maddesi bulunamadı.</p>
  </div>
</div>
{_SHORTCUTS_MODAL}
"""

    js = (
        ACTIVITY_JS
        + f"""
var PD_URL = '/feed/cards?limit={limit}&f={selected}';
var selectedIndex = -1;
var isCompact = false;

window.pdToggleView = function() {{
  isCompact = !isCompact;
  var box = document.getElementById('cards');
  var lbl = document.getElementById('view-mode-label');
  if (box) {{
    if (isCompact) {{
      box.classList.add('feed-compact');
      if (lbl) lbl.textContent = 'Detaylı';
    }} else {{
      box.classList.remove('feed-compact');
      if (lbl) lbl.textContent = 'Kompakt';
    }}
  }}
}};

window.pdToggleShortcuts = function() {{
  var modal = document.getElementById('shortcuts-modal');
  if (modal) modal.classList.toggle('open');
}};

window.pdSearchFeed = function(q) {{
  var val = (q || '').toLowerCase().trim();
  var cards = document.querySelectorAll('#cards [data-search]');
  var visible = 0;
  cards.forEach(function(c) {{
    var text = (c.dataset.search || '').toLowerCase();
    if (!val || text.indexOf(val) !== -1) {{
      c.style.display = '';
      visible++;
    }} else {{
      c.style.display = 'none';
    }}
  }});
  var emptyEl = document.getElementById('feed-search-empty');
  if (emptyEl) {{
    emptyEl.style.display = (visible === 0 && cards.length > 0) ? '' : 'none';
  }}
}};

window.pdQuickDraft = async function(eventId, angle, btn) {{
  var box = document.getElementById('tweet-box-' + eventId);
  if (!box) return;
  var origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Hazırlanıyor…';
  window.pdToast('Doğrulanmış kanıtlarla X tweeti üretiliyor…');

  try {{
    var r = await fetch('/api/events/' + eventId + '/drafts', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{angle: angle}})
    }});
    if (!r.ok) {{
      var err = await r.json().catch(function(){{ return null; }});
      throw new Error(err && err.detail ? (err.detail.message || err.detail) : 'Üretilemedi');
    }}
    var data = await r.json();
    var draftId = data.draft_id;
    var body = data.body || '';
    var encTweet = encodeURIComponent(body);
    var intentUrl = 'https://x.com/intent/tweet?text=' + encTweet;
    var isThread = body.length > 280;
    var pill = !isThread
      ? '<span class="badge strong" style="font-size:11px;height:18px">' + body.length + '/280 X Uyumlu</span>'
      : '<span class="badge neutral" style="font-size:11px;height:18px">' + body.length + ' Karakter (Thread)</span>';

    box.innerHTML = `
      <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:var(--space-2)">
        <div class="row tight" style="align-items:center">
          <span class="badge accent" style="font-size:11px;height:18px">X Tweeti Hazır</span>
          <span class="subtle" style="font-size:var(--text-xs)">Açı: <b>` + angle.toUpperCase() + `</b></span>
          ` + pill + `
        </div>
        <div class="row tight">
          <button class="btn sm ghost" type="button" onclick='pdCopy(` + JSON.stringify(body) + `, "X Tweeti")'>
            ` + window.pdIconCopy + `<span>Kopyala</span>
          </button>
          <a class="btn sm primary" href="` + intentUrl + `" target="_blank" rel="noopener noreferrer">
            ` + window.pdIconShare + `<span>X'te Paylaş</span>
          </a>
        </div>
      </div>
      <textarea class="feed-tweet-textarea" readonly onclick="this.select()">` + body + `</textarea>
      <div class="row" style="justify-content:space-between;align-items:center;margin-top:var(--space-2);font-size:var(--text-xs)">
        <span class="subtle mono">Doğrulanmış kanıt kütüğüne bağlı</span>
        <a href="/draft/` + draftId + `" class="subtle plain" style="font-size:var(--text-xs)">Stüdyoda Düzenle &rarr;</a>
      </div>
    `;
    box.dataset.hasDraft = 'true';
    window.pdToast('X Tweeti hazır!');
  }} catch(e) {{
    btn.disabled = false;
    btn.textContent = origText;
    window.pdToast('Tweet hazırlanamadı: ' + e.message);
  }}
}};

window.pdIconCopy = '{icon("copy", 12)}';
window.pdIconShare = '{icon("share", 12)}';

async function pdRefresh(){{
  var box = document.getElementById('cards');
  var note = document.getElementById('pd-refreshed');
  try {{
    var r = await fetch(PD_URL);
    if (!r.ok) throw new Error(r.status);
    var open = new Set([...box.querySelectorAll('details[open]')]
                       .map(function(d){{ return d.closest('article')
                              .querySelector('a').getAttribute('href'); }}));
    box.innerHTML = await r.text();
    if (isCompact) box.classList.add('feed-compact');
    box.querySelectorAll('article').forEach(function(a){{
      var link = a.querySelector('a');
      var panel = a.querySelector('details');
      if (link && panel && open.has(link.getAttribute('href'))) panel.open = true;
    }});
    note.innerHTML = '<span class="pulse-dot"></span><span>' + new Date().toLocaleTimeString('tr-TR') + ' güncellendi</span>';
    var searchEl = document.getElementById('feed-search');
    if (searchEl && searchEl.value) window.pdSearchFeed(searchEl.value);
  }} catch (e) {{
    note.innerHTML = '<span class="subtle">Yenilenemedi — bağlantı yok. Kartlar son hâliyle duruyor.</span>';
  }}
}}

// Klavye Gezintisi (J / K / X / C / Enter / / / ?)
document.addEventListener('keydown', function(e) {{
  var tag = document.activeElement.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') return;

  var cards = Array.from(document.querySelectorAll('#cards .feed-card'));
  if (!cards.length) return;

  if (e.key === 'j' || e.key === 'J' || e.key === 'ArrowDown') {{
    e.preventDefault();
    if (selectedIndex < cards.length - 1) selectedIndex++;
    cards.forEach(function(c, i){{
      if (i === selectedIndex) {{
        c.classList.add('is-selected');
        c.scrollIntoView({{behavior:'smooth', block:'center'}});
      }} else {{
        c.classList.remove('is-selected');
      }}
    }});
  }} else if (e.key === 'k' || e.key === 'K' || e.key === 'ArrowUp') {{
    e.preventDefault();
    if (selectedIndex > 0) selectedIndex--;
    cards.forEach(function(c, i){{
      if (i === selectedIndex) {{
        c.classList.add('is-selected');
        c.scrollIntoView({{behavior:'smooth', block:'center'}});
      }} else {{
        c.classList.remove('is-selected');
      }}
    }});
  }} else if (e.key === 'x' || e.key === 'X' || e.key === 't' || e.key === 'T') {{
    if (selectedIndex >= 0 && selectedIndex < cards.length) {{
      e.preventDefault();
      var selCard = cards[selectedIndex];
      var btn = selCard.querySelector('.feed-tweet-box button');
      if (btn) btn.click();
    }}
  }} else if (e.key === 'c' || e.key === 'C') {{
    if (selectedIndex >= 0 && selectedIndex < cards.length) {{
      e.preventDefault();
      var selCard = cards[selectedIndex];
      var tweetArea = selCard.querySelector('.feed-tweet-textarea');
      var titleLink = selCard.querySelector('h3 a');
      if (tweetArea && tweetArea.value) {{
        window.pdCopy(tweetArea.value, 'X Tweeti');
      }} else if (titleLink) {{
        window.pdCopy(titleLink.textContent, 'Başlık');
      }}
    }}
  }} else if (e.key === 'Enter' || e.key === 'o' || e.key === 'O') {{
    if (selectedIndex >= 0 && selectedIndex < cards.length) {{
      var link = cards[selectedIndex].querySelector('h3 a');
      if (link) link.click();
    }}
  }} else if (e.key === '/') {{
    e.preventDefault();
    var inp = document.getElementById('feed-search');
    if (inp) {{ inp.focus(); inp.select(); }}
  }} else if (e.key === '?') {{
    e.preventDefault();
    window.pdToggleShortcuts();
  }}
}});

setInterval(function(){{ if (!document.hidden) pdRefresh(); }},
            {REFRESH_SECONDS * 1000});
"""
    )
    return page("Gündem", body, active="/feed", crumbs=(("Gündem", None),), extra_js=js)


@router.get("/feed/cards", response_class=HTMLResponse)
def feed_cards(
    limit: int = Query(default=40, ge=1, le=200),
    f: str = Query(default="all"),
) -> str:
    """Sessiz yenilemenin çektiği parça."""
    selected = f if f in dict(FILTERS) else "all"
    try:
        rows = repository.feed(current_user_id(), limit=limit)
    except Exception as exc:  # noqa: BLE001
        log.warning("feed_cards_db_unavailable", error=str(exc))
        rows = []
    return _cards_html(rows, selected)
