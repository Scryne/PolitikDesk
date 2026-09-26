"""Gündem V2 — Live Intelligence Feed & X Yayın Merkezi (Faz 21 · Spec §14.1).

Gündem V2 Özellikleri:
  * Sıralama Modları: Önemli (Salience), En Yeni (Newest), Son Güncellenen (Updated)
  * Canlı Gelişmeler Bildirimi: "↓ X Yeni Gelişme" banner'ı (scroll kayması yapmaz)
  * Çok Boyutlu Filtreleme: Kategori, Bölge, Zaman, Kaynak, Durum
  * URL Tabanlı Durum Saklama: /gundem?sort=newest&category=...
  * Aktif Üretim Döngüsü İzolasyonu: Arşivlenmiş veriyi sızdırmaz
"""

from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from politikdesk.analysis.taxonomy import CATEGORIES, CATEGORY_MAP, REGION_MAP, REGIONS
from politikdesk.editorial.generator import ANGLES
from politikdesk.evidence.explain import KIND_LABELS
from politikdesk.ingestion.repository import list_sources
from politikdesk.observability import get_logger
from politikdesk.users import current_user_id, touch_last_seen
from politikdesk.web import repository
from politikdesk.web.ui import (
    ACTIVITY_JS,
    action_attrs,
    button,
    esc,
    event_badge,
    filtered_empty_state,
    icon,
    keys,
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

TIME_RANGES: tuple[tuple[str, str], ...] = (
    ("all", "Tüm Zamanlar"),
    ("15m", "Son 15 dakika"),
    ("1h", "Son 1 saat"),
    ("6h", "Son 6 saat"),
    ("24h", "Son 24 saat"),
    ("7d", "Son 7 gün"),
)

SORT_MODES: tuple[tuple[str, str, str, str], ...] = (
    ("important", "Önemli", "shield", "Editoryal önem ve etki sıralaması"),
    ("newest", "En Yeni", "clock", "İlk bildirilen son gelişmeler (Kronolojik Akış)"),
    ("updated", "Son Güncellenen", "zap", "Son değişiklik ve güncelleme alan olaylar (Tazelik Akışı)"),
)
SORT_MODE_MAP = {k: (lbl, ic, desc) for k, lbl, ic, desc in SORT_MODES}



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
              <a class="btn sm ghost" href="/api/events/{event_id}/card.svg" target="_blank" rel="noopener noreferrer" title="SVG İnfografik Kartını Gör / İndir">
                {icon("download", 12)}<span>Görsel Kart</span>
              </a>
              <button class="btn sm ghost" type="button"{action_attrs("copy", body_text, "X Tweeti")} title="Tweet metnini kopyala">
                {icon("copy", 12)}<span>Kopyala</span>
              </button>
              <a class="btn sm primary" href="{intent_url}" target="_blank" rel="noopener noreferrer" title="Yeni sekmede X'te aç">
                {icon("share", 12)}<span>X'te Paylaş</span>
              </a>
            </div>
          </div>
          <textarea class="feed-tweet-textarea" readonly{action_attrs("select-all")} aria-label="X Tweet Taslağı">{esc(body_text)}</textarea>
          <div class="row" style="justify-content:space-between;align-items:center;margin-top:var(--space-2);font-size:var(--text-xs)">
            <span class="subtle mono">Doğrulanmış kanıt kütüğüne bağlı</span>
            <div class="row tight">
              <a href="/draft/{draft_id}" class="subtle plain" style="font-size:var(--text-xs)">{icon("edit", 11)}Stüdyoda Düzenle &rarr;</a>
            </div>
          </div>
        </div>
        """

    if not ready:
        return """
        <div class="row tight" style="margin-top:var(--space-2);font-size:var(--text-xs);color:var(--color-fg-subtle)">
          <span class="subtle">Yeterli kanıt oluşmadan paylaşım taslağı üretilmez.</span>
        </div>
        """

    # Olay yazıma hazır ama henüz taslak üretilmemiş
    angle_chips = "".join(
        f'<button class="btn sm ghost" type="button"'
        f'{action_attrs("quick-draft", event_id, key)} style="font-size:11px;height:22px;padding:0 6px">'
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
        <button class="btn sm ghost" type="button"{action_attrs("quick-draft", event_id, "inform")} style="font-size:12px">
          {icon("zap", 12)}<span>Hızlı Üret</span>
        </button>
      </div>
    </div>
    """


def _card(row: dict[str, Any]) -> str:
    """Gündem V2 Canlı İstihbarat Kartı."""
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

    cat_label = CATEGORY_MAP.get(row.get("category", "ekonomi"), row.get("category", "Ekonomi"))
    reg_label = REGION_MAP.get(row.get("region", "turkiye"), row.get("region", "Türkiye"))

    new_badge = '<span class="badge-new">YENİ</span>' if row.get("is_new") else ""

    body = f"""
  <div class="feed-main">
    <div class="row" style="font-size:var(--text-xs);color:var(--color-fg-subtle);justify-content:space-between;margin-bottom:4px">
      <div class="row tight" style="align-items:center">
        {new_badge}
        <span class="badge-category">{esc(cat_label)}</span>
        <span class="badge-region">{esc(reg_label)}</span>
        {event_badge(row["status"])}
        <span>{esc(_breakdown_text(row.get("source_breakdown")))}</span>
        <span>· {esc(fmt.plural_count(int(row["article_count"] or 0), "makale"))}</span>
        <span>· {esc(fmt.plural_count(int(row["independent_count"] or 0), "bağımsız teyit"))}</span>
      </div>
      <div class="row tight">
        {draft_badge}
      </div>
    </div>
    <h2 class="h3" style="margin:6px 0 6px">
      <a class="plain" href="/event/{row["id"]}">{esc(row["title"])}</a></h2>
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

    search_blob = f"{row['title']} {_evidence_line(row)} {cat_label} {reg_label} {row['status']}".replace('"', "&quot;")
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

    return f"""<div class="kpis" style="margin-bottom:var(--space-4)">
<a href="/feed?f=ready" class="plain">{kpi("Yazıma hazır", fmt.number(ready), unit="olay", icon_name="shield")}</a>
<a href="/feed?f=drafts" class="plain">{kpi("Tweeti hazır", fmt.number(with_drafts), unit="taslak", icon_name="share")}</a>
<a href="/feed?f=pending" class="plain">{kpi("Teyit bekleyen", fmt.number(weak_claims), unit="iddia", icon_name="clock")}</a>
<a href="/feed?f=review" class="plain">{kpi("Denetimde", fmt.number(in_review), unit="olay", icon_name="warning")}</a>
</div>"""


def _strip(summary: dict[str, Any]) -> str:
    """ "Sen yokken ne oldu" şeridi (F3-18)."""
    from politikdesk.web.ui import notice

    if not summary.get("available"):
        return notice(
            "<p><b>PolitikDesk gündem masası.</b> "
            "Aktif döngüdeki gelişmeler anlık doğrulanır ve kanıta bağlanır.</p>"
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


def _cards_html(rows: list[dict[str, Any]], selected_filter: str) -> str:
    """Kart listesi."""
    if not rows:
        from politikdesk.web.ui import empty_state

        return empty_state(
            "Henüz aktif döngüde olay yok",
            "Boru hattı her 5 dakikada bir otomatik toplar. İlk turu başlatmak "
            "için terminalde `pd ingest` yaz; ardından `pd cluster` ile "
            "haberler doğrulanmış olaya dönüşür.",
            action=button("Boru hattını gör", href="/admin/", variant="primary"),
        )

    visible = [row for row in rows if _matches(row, selected_filter)]
    if not visible:
        label = dict(FILTERS).get(selected_filter, selected_filter)
        return filtered_empty_state(
            f"“{label}” filtresi {fmt.plural_count(len(rows), 'olayın')} hiçbiriyle "
            f"eşleşmedi. Gündem dolu — bu filtre şu an boş.",
            "/feed",
        )
    return "".join(_card(row) for row in visible)


_SHORTCUTS_MODAL = f"""
<div id="shortcuts-modal" class="shortcuts-backdrop"{action_attrs("shortcuts-backdrop")}>
  <div class="shortcuts-modal">
    <div class="row" style="justify-content:space-between;align-items:center;margin-bottom:var(--space-4)">
      <h2 class="h3" style="margin:0;font-size:var(--text-lg)">Klavye kısayolları</h2>
      <button class="btn sm ghost icon" type="button" title="Kapat" aria-label="Kapat"
              {action_attrs("toggle-shortcuts")}>{icon("close", 14)}</button>
    </div>
    {keys.help_rows("/feed")}
  </div>
</div>
"""


def _build_feed_url(
    *,
    sort: str = "important",
    f: str = "all",
    category: str = "all",
    region: str = "all",
    range_: str = "all",
    source: int | None = None,
    q: str | None = None,
    limit: int = 40,
    keep_default_sort: bool = False,
) -> str:
    params: list[str] = []
    if sort and (sort != "important" or keep_default_sort):
        params.append(f"sort={sort}")
    if f and f != "all":
        params.append(f"f={f}")
    if category and category != "all":
        params.append(f"category={category}")
    if region and region != "all":
        params.append(f"region={region}")
    if range_ and range_ != "all":
        params.append(f"range={range_}")
    if source:
        params.append(f"source={source}")
    if q and q.strip():
        params.append(f"q={urllib.parse.quote(q.strip())}")
    if limit != 40:
        params.append(f"limit={limit}")
    return "/feed" + ("?" + "&".join(params) if params else "")


def _active_filters_tray(
    selected_sort: str,
    selected_f: str,
    selected_cat: str,
    selected_reg: str,
    selected_range: str,
    source: int | None,
    sources_list: list[Any],
    q: str | None,
) -> str:
    pills = []
    close_ic = icon("close", 10)
    if selected_cat != "all":
        cat_label = CATEGORY_MAP.get(selected_cat, selected_cat)
        remove_url = _build_feed_url(sort=selected_sort, f=selected_f, category="all", region=selected_reg, range_=selected_range, source=source, q=q)
        pills.append(
            f'<span class="feed-active-pill"><span>Kategori: <b>{esc(cat_label)}</b></span>'
            f'<a class="feed-active-pill-remove" href="{remove_url}" title="Kategori filtresini kaldır">{close_ic}</a></span>'
        )
    if selected_reg != "all":
        reg_label = REGION_MAP.get(selected_reg, selected_reg)
        remove_url = _build_feed_url(sort=selected_sort, f=selected_f, category=selected_cat, region="all", range_=selected_range, source=source, q=q)
        pills.append(
            f'<span class="feed-active-pill"><span>Bölge: <b>{esc(reg_label)}</b></span>'
            f'<a class="feed-active-pill-remove" href="{remove_url}" title="Bölge filtresini kaldır">{close_ic}</a></span>'
        )
    if selected_range != "all":
        range_label = dict(TIME_RANGES).get(selected_range, selected_range)
        remove_url = _build_feed_url(sort=selected_sort, f=selected_f, category=selected_cat, region=selected_reg, range_="all", source=source, q=q)
        pills.append(
            f'<span class="feed-active-pill"><span>Zaman: <b>{esc(range_label)}</b></span>'
            f'<a class="feed-active-pill-remove" href="{remove_url}" title="Zaman filtresini kaldır">{close_ic}</a></span>'
        )
    if source is not None:
        src_obj = next((s for s in sources_list if s.id == source), None)
        src_name = src_obj.name if src_obj else f"Kaynak #{source}"
        remove_url = _build_feed_url(sort=selected_sort, f=selected_f, category=selected_cat, region=selected_reg, range_=selected_range, source=None, q=q)
        pills.append(
            f'<span class="feed-active-pill"><span>Kaynak: <b>{esc(src_name)}</b></span>'
            f'<a class="feed-active-pill-remove" href="{remove_url}" title="Kaynak filtresini kaldır">{close_ic}</a></span>'
        )
    if q and q.strip():
        remove_url = _build_feed_url(sort=selected_sort, f=selected_f, category=selected_cat, region=selected_reg, range_=selected_range, source=source, q=None)
        pills.append(
            f'<span class="feed-active-pill"><span>Arama: <b>"{esc(q.strip())}"</b></span>'
            f'<a class="feed-active-pill-remove" href="{remove_url}" title="Aramayı temizle">{close_ic}</a></span>'
        )
    if selected_f != "all":
        f_label = dict(FILTERS).get(selected_f, selected_f)
        remove_url = _build_feed_url(sort=selected_sort, f="all", category=selected_cat, region=selected_reg, range_=selected_range, source=source, q=q)
        pills.append(
            f'<span class="feed-active-pill"><span>Durum: <b>{esc(f_label)}</b></span>'
            f'<a class="feed-active-pill-remove" href="{remove_url}" title="Durum filtresini kaldır">{close_ic}</a></span>'
        )

    if not pills:
        return ""

    clear_all_url = f"/feed?sort={selected_sort}" if selected_sort != "important" else "/feed"
    return f"""
    <div class="feed-active-tray" aria-label="Aktif Filtreler">
      <span class="feed-active-tray-label">{icon("filter", 12)}Aktif Filtreler:</span>
      {''.join(pills)}
      <a class="btn sm ghost" href="{clear_all_url}" style="margin-left:auto;font-size:11px;height:22px;padding:0 8px" title="Tüm filtreleri sıfırla">
        {icon("close", 11)}<span>Filtreleri Temizle</span>
      </a>
    </div>
    """


def _discovery_bar(
    selected_sort: str,
    selected_f: str,
    selected_cat: str,
    selected_reg: str,
    selected_range: str,
    source: int | None,
    q: str | None,
) -> str:
    cat_chips = []
    for k, lbl in CATEGORIES:
        is_active = k == selected_cat
        url = _build_feed_url(sort=selected_sort, f=selected_f, category=k, region=selected_reg, range_=selected_range, source=source, q=q)
        active_attr = ' aria-current="true"' if is_active else ""
        active_cls = " active" if is_active else ""
        cat_chips.append(f'<a class="feed-chip{active_cls}" href="{url}"{active_attr}>{esc(lbl)}</a>')

    reg_chips = []
    for k, lbl in REGIONS:
        is_active = k == selected_reg
        url = _build_feed_url(sort=selected_sort, f=selected_f, category=selected_cat, region=k, range_=selected_range, source=source, q=q)
        active_attr = ' aria-current="true"' if is_active else ""
        active_cls = " active" if is_active else ""
        reg_chips.append(f'<a class="feed-chip{active_cls}" href="{url}"{active_attr}>{esc(lbl)}</a>')

    return f"""
    <div class="feed-discovery-bar">
      <div class="feed-discovery-section">
        <span class="feed-discovery-label">{icon("grid", 11)}Kategori</span>
        <div class="feed-chip-group" role="tablist" aria-label="Kategori Keşfi">
          {''.join(cat_chips)}
        </div>
      </div>
      <div class="feed-discovery-section">
        <span class="feed-discovery-label">{icon("filter", 11)}Bölge</span>
        <div class="feed-chip-group" role="tablist" aria-label="Bölge Keşfi">
          {''.join(reg_chips)}
        </div>
      </div>
    </div>
    """


@router.get("/", response_class=HTMLResponse)
@router.get("/feed", response_class=HTMLResponse)
@router.get("/gundem", response_class=HTMLResponse)
def feed_page(
    request: Request,
    limit: int = Query(default=40, ge=1, le=200),
    f: str = Query(default="all"),
    sort: str = Query(default="important"),
    category: str = Query(default="all"),
    region: str = Query(default="all"),
    range: str = Query(default="all"),
    source: int | None = Query(default=None),
    q: str | None = Query(default=None),
) -> str:
    selected_f = f if f in dict(FILTERS) else "all"
    selected_sort = sort if sort in SORT_MODE_MAP else "important"
    selected_cat = category if category in dict(CATEGORIES) else "all"
    selected_reg = region if region in dict(REGIONS) else "all"
    selected_range = range if range in dict(TIME_RANGES) else "all"

    try:
        user_id = current_user_id()
        previous_visit = touch_last_seen(user_id)
        summary = repository.since_last_visit(user_id, previous_visit)
        rows = repository.feed(
            user_id,
            limit=limit,
            sort=selected_sort,
            category=selected_cat,
            region=selected_reg,
            time_range=selected_range,
            source_id=source,
            query=q,
        )
        sources_list = list_sources(only_active=True)
    except Exception as exc:  # noqa: BLE001
        log.warning("feed_db_unavailable", error=str(exc))
        summary = {}
        rows = []
        sources_list = []

    counts = {key: sum(1 for row in rows if _matches(row, key)) for key, _ in FILTERS}
    tabs = segment(
        tuple(
            (
                f"{label} · {fmt.number(counts[key])}",
                _build_feed_url(
                    sort=selected_sort,
                    f=key,
                    category=selected_cat,
                    region=selected_reg,
                    range_=selected_range,
                    source=source,
                    q=q,
                    limit=limit,
                ),
                key == selected_f,
            )
            for key, label in FILTERS
        )
    )

    # Sıralama Düğmeleri & Açıklayıcı Tagline
    sort_buttons_html = "".join(
        f'<a class="feed-sort-btn" href="{_build_feed_url(sort=k, f=selected_f, category=selected_cat, region=selected_reg, range_=selected_range, source=source, q=q, limit=limit, keep_default_sort=True)}"'
        f' {"aria-current=\"true\"" if k == selected_sort else ""}'
        f' {action_attrs("save-sort-pref", k)}>'
        f'{icon(ic, 13)}<span>{esc(lbl)}</span></a>'
        for k, lbl, ic, _desc in SORT_MODES
    )

    active_sort_info = SORT_MODE_MAP.get(selected_sort, ("Önemli", "shield", "Editoryal önem ve etki sıralaması"))
    mode_tagline_html = (
        f'<div class="feed-mode-tagline">'
        f'{icon(active_sort_info[1], 12)}<span>Sıralama Modu: <b>{esc(active_sort_info[0])}</b> — {esc(active_sort_info[2])}</span>'
        f'</div>'
    )

    # Zaman Select
    time_options = "".join(
        f'<option value="{k}" {"selected" if k == selected_range else ""}>{esc(lbl)}</option>'
        for k, lbl in TIME_RANGES
    )

    # Kaynak Select
    src_options = '<option value="">Tüm Kaynaklar</option>' + "".join(
        f'<option value="{s.id}" {"selected" if source == s.id else ""}>{esc(s.name)}</option>'
        for s in sources_list
    )

    actions_html = (
        search_input(
            "feed-search",
            "Haber, olay, kişi veya konu ara… [/]",
            value=q or "",
            action="search-feed",
        )
        + f'<button class="btn sm ghost" type="button"{action_attrs("toggle-view")} id="view-toggle" title="Görünüm değiştir">'
        f'{icon("grid", 13)}<span id="view-mode-label">Kompakt</span></button>'
        f'<button class="btn sm ghost" type="button"{action_attrs("toggle-shortcuts")} title="Klavye Kısayolları (?)">'
        f'{icon("info", 13)}<span>Kısayollar</span></button>'
        + button("Yenile", icon_name="refresh", action="refresh")
    )

    top_timestamp = (
        rows[0]["last_update_at"].isoformat()
        if rows and "last_update_at" in rows[0] and hasattr(rows[0]["last_update_at"], "isoformat")
        else datetime.now(UTC).isoformat()
    )

    active_tray_html = _active_filters_tray(
        selected_sort=selected_sort,
        selected_f=selected_f,
        selected_cat=selected_cat,
        selected_reg=selected_reg,
        selected_range=selected_range,
        source=source,
        sources_list=sources_list,
        q=q,
    )

    discovery_bar_html = _discovery_bar(
        selected_sort=selected_sort,
        selected_f=selected_f,
        selected_cat=selected_cat,
        selected_reg=selected_reg,
        selected_range=selected_range,
        source=source,
        q=q,
    )

    body = f"""
{
        page_head(
            "Gündem",
            lede="Makro ekonomi ve siyaset gündemi. Her olay önemi ve kanıt durumuyla birlikte.",
            actions=actions_html,
        )
    }
<div class="stack">
  {_strip(summary)}
  {_summary_kpis(rows)}

  <!-- Gündem Toolbar -->
  <div class="feed-toolbar">
    <div class="feed-toolbar-row">
      <div class="feed-sort-group" role="tablist" aria-label="Sıralama Modu">
        {sort_buttons_html}
      </div>
      <div class="row tight" style="align-items:center">
        {tabs}
      </div>
    </div>

    {mode_tagline_html}

    {discovery_bar_html}

    <div class="feed-toolbar-row" style="border-top:1px solid var(--color-border);padding-top:var(--space-3)">
      <div class="feed-filter-bar">
        <span class="subtle" style="font-size:var(--text-xs);display:flex;align-items:center;gap:4px">
          {icon("filter", 12)}Filtrele:
        </span>

        <!-- Kategori ve bölge yukarıdaki çiplerde; ikinci kez açılır menüyle sunulmaz. -->
        <select id="filter-range" class="feed-select" aria-label="Zaman Aralığı" {action_attrs("apply-filters")}>
          {time_options}
        </select>

        <select id="filter-source" class="feed-select" aria-label="Haber Kaynağı" {action_attrs("apply-filters")}>
          {src_options}
        </select>
      </div>

      <span class="subtle row tight" style="font-size:var(--text-xs)"
            id="pd-refreshed" aria-live="polite">
        <span class="pulse-dot"></span>
        <span>{esc(fmt.plural_count(REFRESH_SECONDS, "saniyede"))} bir sessizce yenilenir</span>
      </span>
    </div>
  </div>

  {active_tray_html}

  <!-- Canlı Gelişmeler Bildirim Banner'ı (Scroll jump engeller) -->
  <button id="feed-new-banner" class="feed-new-banner" type="button" {action_attrs("load-new-items")}>
    <span class="pulse-dot" style="background:var(--color-fg-on-accent)"></span>
    <span id="feed-new-banner-text">↓ Yeni gelişmeler var</span>
  </button>

  <div id="cards" class="stack-sm">{_cards_html(rows, selected_f)}</div>
  <div id="feed-search-empty" style="display:none;padding:var(--space-12);text-align:center">
    <p class="subtle">Arama ve filtre kriterinize uygun canlı gündem maddesi bulunamadı.</p>
  </div>
</div>
{_SHORTCUTS_MODAL}
"""

    current_query_encoded = urllib.parse.quote(q or "")

    js = (
        ACTIVITY_JS
        + f"""
var PD_LIMIT = {limit};
var PD_FILTER = '{selected_f}';
var PD_SORT = '{selected_sort}';
var PD_CAT = '{selected_cat}';
var PD_REG = '{selected_reg}';
var PD_RANGE = '{selected_range}';
var PD_SOURCE = '{source or ""}';
var PD_QUERY = '{current_query_encoded}';
var PD_TOP_TS = '{top_timestamp}';

var selectedIndex = -1;
var isCompact = false;

// ── Kullanıcı Tercihi Saklama (Sorting Preference) ──
(function(){{
  try {{
    var urlParams = new URLSearchParams(window.location.search);
    if (!urlParams.has('sort')) {{
      var savedSort = localStorage.getItem('pd-feed-sort');
      if (savedSort && savedSort !== PD_SORT && (savedSort === 'important' || savedSort === 'newest' || savedSort === 'updated')) {{
        urlParams.set('sort', savedSort);
        window.location.replace(window.location.pathname + '?' + urlParams.toString());
      }}
    }}
  }} catch(e) {{}}
}})();

window.pdSaveSortPref = function(sortKey) {{
  try {{
    if (sortKey) localStorage.setItem('pd-feed-sort', sortKey);
  }} catch(e) {{}}
}};

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

window.pdApplyFilters = function() {{
  var catEl = document.getElementById('filter-category');
  var regEl = document.getElementById('filter-region');
  var rangeEl = document.getElementById('filter-range');
  var srcEl = document.getElementById('filter-source');
  var searchEl = document.getElementById('feed-search');

  var cat = catEl ? catEl.value : PD_CAT || 'all';
  var reg = regEl ? regEl.value : PD_REG || 'all';
  var range = rangeEl ? rangeEl.value : 'all';
  var src = srcEl ? srcEl.value : '';
  var q = searchEl ? searchEl.value.trim() : '';

  var params = new URLSearchParams();
  if (PD_SORT && PD_SORT !== 'important') params.set('sort', PD_SORT);
  if (PD_FILTER && PD_FILTER !== 'all') params.set('f', PD_FILTER);
  if (cat && cat !== 'all') params.set('category', cat);
  if (reg && reg !== 'all') params.set('region', reg);
  if (range && range !== 'all') params.set('range', range);
  if (src) params.set('source', src);
  if (q) params.set('q', q);

  window.location.href = '/feed?' + params.toString();
}};

window.pdSearchFeed = function(el) {{
  var val = (el.value || '').toLowerCase().trim();
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

// Enter ile sunucu araması
var searchInputEl = document.getElementById('feed-search');
if (searchInputEl) {{
  searchInputEl.addEventListener('keydown', function(e) {{
    if (e.key === 'Enter') {{
      window.pdApplyFilters();
    }}
  }});
}}

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

    box.replaceChildren();

    var head = document.createElement('div');
    head.className = 'row';
    head.style.cssText = 'justify-content:space-between;align-items:center;margin-bottom:var(--space-2)';

    var headLeft = document.createElement('div');
    headLeft.className = 'row tight';
    headLeft.style.alignItems = 'center';

    var readyBadge = document.createElement('span');
    readyBadge.className = 'badge accent';
    readyBadge.style.cssText = 'font-size:11px;height:18px';
    readyBadge.textContent = 'X Tweeti Hazır';

    var angleEl = document.createElement('span');
    angleEl.className = 'subtle';
    angleEl.style.fontSize = 'var(--text-xs)';
    angleEl.textContent = 'Açı: ' + angle;

    var pill = document.createElement('span');
    pill.className = isThread ? 'badge neutral' : 'badge strong';
    pill.style.cssText = 'font-size:11px;height:18px';
    pill.textContent = isThread
      ? body.length + ' karakter (zincir)'
      : body.length + '/280 X uyumlu';

    headLeft.append(readyBadge, angleEl, pill);

    var headRight = document.createElement('div');
    headRight.className = 'row tight';

    var copyBtn = document.createElement('button');
    copyBtn.className = 'btn sm ghost';
    copyBtn.type = 'button';
    copyBtn.innerHTML = window.pdIconCopy;
    var copyLabel = document.createElement('span');
    copyLabel.textContent = 'Kopyala';
    copyBtn.appendChild(copyLabel);
    copyBtn.addEventListener('click', function(){{ window.pdCopy(body, 'X Tweeti'); }});

    var shareLink = document.createElement('a');
    shareLink.className = 'btn sm primary';
    shareLink.href = intentUrl;
    shareLink.target = '_blank';
    shareLink.rel = 'noopener noreferrer';
    shareLink.innerHTML = window.pdIconShare;
    var shareLabel = document.createElement('span');
    shareLabel.textContent = "X'te Paylaş";
    shareLink.appendChild(shareLabel);

    headRight.append(copyBtn, shareLink);
    head.append(headLeft, headRight);

    var area = document.createElement('textarea');
    area.className = 'feed-tweet-textarea';
    area.readOnly = true;
    area.value = body;
    area.addEventListener('click', function(){{ area.select(); }});

    var foot = document.createElement('div');
    foot.className = 'row';
    foot.style.cssText = 'justify-content:space-between;align-items:center;margin-top:var(--space-2);font-size:var(--text-xs)';
    var footNote = document.createElement('span');
    footNote.className = 'subtle mono';
    footNote.textContent = 'Doğrulanmış kanıt kütüğüne bağlı';
    var studioLink = document.createElement('a');
    studioLink.href = '/draft/' + encodeURIComponent(draftId);
    studioLink.className = 'subtle plain';
    studioLink.style.fontSize = 'var(--text-xs)';
    studioLink.textContent = 'Stüdyoda Düzenle →';
    foot.append(footNote, studioLink);

    box.append(head, area, foot);
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

// ── Canlı Gelişmeleri Denetleme & Bildirme (Banner) ──
async function pdCheckNew() {{
  if (!PD_TOP_TS) return;
  try {{
    var url = '/api/feed/check-new?since=' + encodeURIComponent(PD_TOP_TS)
      + (PD_CAT && PD_CAT !== 'all' ? '&category=' + encodeURIComponent(PD_CAT) : '')
      + (PD_REG && PD_REG !== 'all' ? '&region=' + encodeURIComponent(PD_REG) : '');
    var r = await fetch(url);
    if (!r.ok) return;
    var data = await r.json();
    var banner = document.getElementById('feed-new-banner');
    var bannerText = document.getElementById('feed-new-banner-text');
    if (banner && bannerText) {{
      if (data.new_count > 0) {{
        bannerText.textContent = '↓ ' + data.new_count + ' YENİ GELİŞME (Görmek için tıklayın)';
        banner.style.display = 'flex';
      }} else {{
        banner.style.display = 'none';
      }}
    }}
  }} catch (e) {{}}
}}

window.pdLoadNewItems = function() {{
  var banner = document.getElementById('feed-new-banner');
  if (banner) banner.style.display = 'none';
  pdRefresh(true);
}};

async function pdRefresh(highlightNew) {{
  var box = document.getElementById('cards');
  var note = document.getElementById('pd-refreshed');
  try {{
    var fetchUrl = '/feed/cards?limit=' + PD_LIMIT + '&f=' + PD_FILTER
      + '&sort=' + PD_SORT + '&category=' + PD_CAT + '&region=' + PD_REG + '&range=' + PD_RANGE
      + (PD_SOURCE ? '&source=' + PD_SOURCE : '')
      + (PD_QUERY ? '&q=' + PD_QUERY : '');

    var r = await fetch(fetchUrl);
    if (!r.ok) throw new Error(r.status);
    var existingIds = new Set([...box.querySelectorAll('[data-event-id]')].map(function(el){{ return el.dataset.eventId; }}));
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

    // Yeni gelen kartlara hafif vurgu efekti
    if (highlightNew) {{
      box.querySelectorAll('[data-event-id]').forEach(function(el){{
        if (!existingIds.has(el.dataset.eventId)) {{
          var art = el.querySelector('article');
          if (art) art.classList.add('card-new-highlight');
        }}
      }});
    }}

    PD_TOP_TS = new Date().toISOString();
    var banner = document.getElementById('feed-new-banner');
    if (banner) banner.style.display = 'none';
    note.innerHTML = '<span class="pulse-dot"></span><span>' + new Date().toLocaleTimeString('tr-TR') + ' güncellendi</span>';
    var searchEl = document.getElementById('feed-search');
    if (searchEl && searchEl.value) window.pdSearchFeed(searchEl);
  }} catch (e) {{
    note.innerHTML = '<span class="subtle">Yenilenemedi — bağlantı yok. Kartlar son hâliyle duruyor.</span>';
  }}
}}

function pdCards() {{
  return Array.from(document.querySelectorAll('#cards .feed-card'));
}}

function pdSelect(cards, index) {{
  selectedIndex = index;
  cards.forEach(function(c, i){{
    if (i === selectedIndex) {{
      c.classList.add('is-selected');
      c.scrollIntoView({{behavior:'smooth', block:'center'}});
    }} else {{
      c.classList.remove('is-selected');
    }}
  }});
}}

function pdSelected() {{
  var cards = pdCards();
  if (selectedIndex < 0 || selectedIndex >= cards.length) return null;
  return cards[selectedIndex];
}}

window.pdKey('next-event', function(){{
  var cards = pdCards();
  if (!cards.length) return;
  pdSelect(cards, Math.min(selectedIndex + 1, cards.length - 1));
}});

window.pdKey('prev-event', function(){{
  var cards = pdCards();
  if (!cards.length) return;
  pdSelect(cards, Math.max(selectedIndex - 1, 0));
}});

window.pdKey('draft-x', function(){{
  var card = pdSelected();
  if (!card) return;
  var btn = card.querySelector('.feed-tweet-box button');
  if (btn) btn.click();
}});

window.pdKey('copy-selected', function(){{
  var card = pdSelected();
  if (!card) return;
  var tweetArea = card.querySelector('.feed-tweet-textarea');
  var titleLink = card.querySelector('h3 a');
  if (tweetArea && tweetArea.value) {{
    window.pdCopy(tweetArea.value, 'X Tweeti');
  }} else if (titleLink) {{
    window.pdCopy(titleLink.textContent, 'Başlık');
  }}
}});

window.pdKey('open-event', function(){{
  var card = pdSelected();
  if (!card) return;
  var link = card.querySelector('h3 a');
  if (link) link.click();
}});

window.pdKey('focus-search', function(){{
  var inp = document.getElementById('feed-search');
  if (inp) {{ inp.focus(); inp.select(); }}
}});

window.pdKey('toggle-shortcuts', window.pdToggleShortcuts);

window.pdAction('toggle-view', window.pdToggleView);
window.pdAction('toggle-shortcuts', window.pdToggleShortcuts);
window.pdAction('search-feed', window.pdSearchFeed);
window.pdAction('apply-filters', window.pdApplyFilters);
window.pdAction('load-new-items', window.pdLoadNewItems);
window.pdAction('save-sort-pref', function(sortKey){{ window.pdSaveSortPref(sortKey); }});
window.pdAction('quick-draft', window.pdQuickDraft);
window.pdAction('refresh', function(){{ pdRefresh(false); }});
window.pdAction('shortcuts-backdrop', function(el, ev){{
  if (ev.target === el) window.pdToggleShortcuts();
}});

if (window.EventSource) {{
  try {{
    var es = new EventSource('/api/feed/stream');
    es.addEventListener('feed_update', function() {{ if (!document.hidden) pdCheckNew(); }});
    es.addEventListener('claims_update', function() {{ if (!document.hidden) pdCheckNew(); }});
  }} catch (e) {{}}
}}

setInterval(function(){{ if (!document.hidden) pdCheckNew(); }}, {REFRESH_SECONDS * 1000});
"""
    )
    return page("Gündem V3", body, active="/feed", crumbs=(("Gündem", None),), extra_js=js)


@router.get("/api/feed/stream")
async def feed_stream_endpoint(request: Request) -> StreamingResponse:
    """Canlı haber ve iddia güncellemeleri için Server-Sent Events (SSE) akışı."""
    from politikdesk.events_stream import sse_event_stream

    return StreamingResponse(
        sse_event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/feed/cards", response_class=HTMLResponse)
def feed_cards(
    limit: int = Query(default=40, ge=1, le=200),
    f: str = Query(default="all"),
    sort: str = Query(default="important"),
    category: str = Query(default="all"),
    region: str = Query(default="all"),
    range: str = Query(default="all"),
    source: int | None = Query(default=None),
    q: str | None = Query(default=None),
) -> str:
    """Sessiz yenilemenin çektiği parça."""
    selected = f if f in dict(FILTERS) else "all"
    try:
        rows = repository.feed(
            current_user_id(),
            limit=limit,
            sort=sort,
            category=category,
            region=region,
            time_range=range,
            source_id=source,
            query=q,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("feed_cards_db_unavailable", error=str(exc))
        rows = []
    return _cards_html(rows, selected)
