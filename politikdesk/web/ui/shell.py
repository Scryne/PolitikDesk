"""Sayfa kabuğu — sidebar + topbar + içerik (DESIGN.md Bölüm 7.1, 7.2).

**Depodaki TÜM sayfalar bu kabuğu kullanır**, admin ekranları dahil. Eskiden
`/feed` ailesi bir kabukta, `/admin/`, `/admin/review/` ve `/admin/calendar/`
üç ayrı gövdesiz HTML'de yaşıyordu; "her sayfa farklı görünüyor" şikayetinin
kaynağı oydu. Admin ekranları da kullanıcının gördüğü ekranlardır.

### Neden sol ray, üstte sekme değil

Nav 7 öğeye çıktı ve üç mantıksal gruba ayrılıyor (çalışma masası · denetim ·
ayarlar). Bölüm 7.2: *"7'den fazla öğe varsa gruplamak zorunludur"* — yatay
sekme çubuğu grup başlığı taşıyamaz.

### Tema

Üç durumlu: sistem · açık · koyu. Tercih `localStorage`'da tutulur ve
`<head>` içindeki **senkron** betikle uygulanır — `DOMContentLoaded`
beklenirse sayfa bir kare açık temada çizilir ve göz kırpar (FOUC).
"""

from __future__ import annotations

from typing import Final

from politikdesk.web.ui.components import esc
from politikdesk.web.ui.css import stylesheet
from politikdesk.web.ui.icons import icon

STATIC_BASE: Final[str] = "/static"

# (grup başlığı, ((href, etiket, ikon), ...))
# Sıra ürünün günlük akışını izler: feed → olay → taslak (README "günlük
# kullanım"), sonra denetim, en sonda ayar.
NAV: Final[tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...]] = (
    (
        "Çalışma masası",
        (
            ("/feed", "Gündem", "feed"),
            ("/briefing", "Brifingler", "briefing"),
            ("/promises", "Vaat Takibi", "promise"),
            ("/accountability", "Hesap Sor", "accountability"),
            ("/archive", "Yayın Arşivi", "archive"),
        ),
    ),
    (
        "Denetim",
        (
            ("/admin/", "Boru hattı", "pipeline"),
            ("/admin/review/", "Denetim kuyruğu", "review"),
            ("/admin/calendar/", "Beklenen gelişmeler", "calendar"),
            ("/admin/metrics", "Metrikler", "metrics"),
        ),
    ),
    (
        "Ayarlar",
        (("/onboarding/profile", "Editoryal kimlik", "identity"),),
    ),
)

# FOUC önleyici. `<head>` içinde, stylesheet'ten ÖNCE koşar.
_THEME_BOOT: Final[str] = (
    "(function(){try{var t=localStorage.getItem('pd-theme');"
    "if(t==='dark'||t==='light')document.documentElement.dataset.theme=t;}"
    "catch(e){}})()"
)

_THEME_JS: Final[str] = """
(function(){
  var root = document.documentElement;
  var btn  = document.getElementById('pd-theme');
  if (!btn) return;
  var ORDER = ['system','light','dark'];
  var LABEL = {system:'Tema: sistem', light:'Tema: açık', dark:'Tema: koyu'};
  function current(){ return root.dataset.theme || 'system'; }
  function paint(){
    var mode = current();
    btn.title = LABEL[mode] + ' — değiştirmek için tıkla';
    btn.setAttribute('aria-label', btn.title);
    btn.querySelectorAll('[data-mode]').forEach(function(el){
      el.hidden = el.dataset.mode !== mode;
    });
  }
  btn.addEventListener('click', function(){
    var next = ORDER[(ORDER.indexOf(current()) + 1) % ORDER.length];
    if (next === 'system') { delete root.dataset.theme; }
    else { root.dataset.theme = next; }
    try {
      next === 'system' ? localStorage.removeItem('pd-theme')
                        : localStorage.setItem('pd-theme', next);
    } catch (e) {}
    paint();
  });
  paint();
})();
"""

# Kullanım izleme: sayfa açılışı + 60 sn'de bir kalp atışı (F3-19).
# `sendBeacon` sayfa kapanırken de gider; `fetch` gitmezdi.
ACTIVITY_JS: Final[str] = """
(function(){
  var path = location.pathname;
  var eventId = document.body.dataset.eventId || null;
  function ping(kind, extra){
    var payload = Object.assign({kind:kind, path:path, event_id:eventId}, extra||{});
    var blob = new Blob([JSON.stringify(payload)], {type:'application/json'});
    if (navigator.sendBeacon) { navigator.sendBeacon('/api/activity', blob); }
  }
  ping(eventId ? 'event_open' : 'page_view');
  var t = setInterval(function(){ if(!document.hidden) ping('heartbeat'); }, 60000);
  window.addEventListener('pagehide', function(){ clearInterval(t); });
  window.pdPing = ping;
  window.pdOpenedAt = Date.now();
})();
"""


def _sidebar(active: str) -> str:
    groups = []
    for title, items in NAV:
        links = "".join(
            f'<a class="nav-item" href="{esc(href)}"'
            f'{" aria-current=\"page\"" if href == active else ""}>'
            f'{icon(name, 16)}<span>{esc(label)}</span></a>'
            for href, label, name in items
        )
        groups.append(
            f'<div class="nav-group"><p class="eyebrow">{esc(title)}</p>{links}</div>'
        )

    theme_button = (
        '<button class="btn ghost icon sm" id="pd-theme" type="button" '
        'title="Tema" aria-label="Tema">'
        f'<span data-mode="system" hidden>{icon("system", 16)}</span>'
        f'<span data-mode="light" hidden>{icon("sun", 16)}</span>'
        f'<span data-mode="dark" hidden>{icon("moon", 16)}</span>'
        "</button>"
    )

    return f"""<aside class="side">
  <div class="side-head">
    <a class="brand" href="/feed">
      <span class="brand-mark" aria-hidden="true">P</span>
      <span class="brand-text">
        <span class="brand-name">PolitikDesk</span><br>
        <span class="brand-sub">makro ekonomi masası</span>
      </span>
    </a>
  </div>
  <nav class="side-nav" aria-label="Ana gezinme">{"".join(groups)}</nav>
  <div class="side-foot">{theme_button}
    <span class="who subtle" style="font-size:var(--text-xs)">Tek kullanıcı</span>
  </div>
</aside>"""


def _topbar(crumbs: tuple[tuple[str, str | None], ...]) -> str:
    """`((etiket, href|None), ...)` — son öğe her zaman linksiz "burası"dır."""
    parts: list[str] = []
    for index, (label, href) in enumerate(crumbs):
        if index:
            parts.append('<span class="sep" aria-hidden="true">/</span>')
        if href:
            parts.append(f'<a href="{esc(href)}">{esc(label)}</a>')
        else:
            parts.append(f'<span class="here">{esc(label)}</span>')
    return (
        f'<header class="topbar"><nav class="crumbs" aria-label="Konum">'
        f'{"".join(parts)}</nav></header>'
    )


def page(
    title: str,
    body: str,
    *,
    active: str = "",
    crumbs: tuple[tuple[str, str | None], ...] = (),
    extra_js: str = "",
    body_attrs: str = "",
) -> str:
    """Sayfayı ortak kabuğa sarar.

    `title` tarayıcı sekmesinde ve breadcrumb'ın sonunda kullanılır;
    sayfanın görünen H1'i `body` içindedir (`components.page_head`).
    """
    # Spec §12.6 madde 5: Election Mode açıkken kullanıcıya görünür gösterge.
    # Kapalıyken boş string döner (F4-15 — varsayılan kapalı).
    from config.election_mode import banner

    trail = crumbs or ((title, None),)
    scripts = "\n".join(part for part in (_THEME_JS, extra_js) if part)
    election = banner()
    election_html = (
        f'<div style="margin-bottom:var(--space-6)">{election}</div>'
        if election
        else ""
    )

    return f"""<!doctype html>
<html lang="tr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{esc(title)} · PolitikDesk</title>
<script>{_THEME_BOOT}</script>
<style>{stylesheet(STATIC_BASE)}</style>
</head>
<body{body_attrs}>
<a class="sr" href="#main">İçeriğe atla</a>
<div class="app">
{_sidebar(active)}
<div class="main">
{_topbar(trail)}
<main class="content" id="main">{election_html}{body}</main>
</div>
</div>
<script>{scripts}</script>
</body></html>"""
