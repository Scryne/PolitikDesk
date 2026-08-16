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
            ("/memory", "Siyasi Hafıza", "clock"),
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
window.pdToast = function(msg) {
  var t = document.getElementById('pd-toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'pd-toast';
    t.className = 'toast';
    document.body.appendChild(t);
  }
  t.innerHTML = '<span>' + msg + '</span>';
  t.classList.add('show');
  clearTimeout(window._pdToastTimer);
  window._pdToastTimer = setTimeout(function(){ t.classList.remove('show'); }, 2600);
};
window.pdCopy = function(text, label) {
  var ok = function() { window.pdToast((label || 'Metin') + ' kopyalandı.'); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(ok);
  } else {
    var ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    ok();
  }
};
"""

# Kullanım izleme: sayfa açılışı + aktif olunduğunda 60 sn'de bir kalp atışı (F3-19).
# `sendBeacon` sayfa kapanırken de gider; `fetch` gitmezdi.
# Boşta bekleme (idle suppression): Son 65 saniyede kullanıcı etkileşimi
# yoksa heartbeat atılmaz; böylece arkada açık kalan sekmeler aktif dakika
# sayılmaz (Spec §13.3).
ACTIVITY_JS: Final[str] = """
(function(){
  var path = location.pathname;
  var eventId = document.body.dataset.eventId || null;
  var lastActive = Date.now();
  function onUserActive(){ lastActive = Date.now(); }
  ['mousemove','keydown','scroll','touchstart','click'].forEach(function(ev){
    window.addEventListener(ev, onUserActive, {passive:true});
  });
  document.addEventListener('visibilitychange', function(){
    if (!document.hidden) lastActive = Date.now();
  });
  function ping(kind, extra){
    var payload = Object.assign({kind:kind, path:path, event_id:eventId}, extra||{});
    var blob = new Blob([JSON.stringify(payload)], {type:'application/json'});
    if (navigator.sendBeacon) { navigator.sendBeacon('/api/activity', blob); }
  }
  ping(eventId ? 'event_open' : 'page_view');
  var t = setInterval(function(){
    if (!document.hidden && (Date.now() - lastActive < 65000)) {
      ping('heartbeat');
    }
  }, 60000);
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
            f"{' aria-current="page"' if href == active else ''}>"
            f"{icon(name, 16)}<span>{esc(label)}</span></a>"
            for href, label, name in items
        )
        groups.append(f'<div class="nav-group"><p class="eyebrow">{esc(title)}</p>{links}</div>')

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

    cmd_trigger = (
        '<button class="btn ghost sm" id="pd-cmd-btn" type="button" '
        'style="margin-left:auto;gap:var(--space-2);color:var(--color-fg-muted);" '
        'title="Komuta Paleti (Ctrl+K / ⌘K)">'
        f'{icon("search", 14)}<span>Ara & Komutlar</span>'
        '<kbd class="shortcut-key" style="font-size:10px;">⌘K</kbd>'
        '</button>'
    )

    return (
        f'<header class="topbar"><nav class="crumbs" aria-label="Konum">'
        f"{''.join(parts)}</nav>{cmd_trigger}</header>"
    )


_CMD_PALETTE_HTML = """
<div id="pd-cmd-dialog" class="cmd-backdrop" role="dialog" aria-modal="true" aria-label="Komuta Paleti">
  <div class="cmd-box">
    <div class="cmd-header">
      <span class="ic">""" + icon("search", 16) + """</span>
      <input type="text" id="pd-cmd-input" class="cmd-input" placeholder="Sayfa, aktör veya komut ara... (Örn: Gündem, Şimşek, R8)" autocomplete="off" spellcheck="false">
      <kbd class="shortcut-key" style="font-size:10px;">ESC</kbd>
    </div>
    <div id="pd-cmd-body" class="cmd-body"></div>
    <div class="cmd-footer">
      <span>↑↓ ile gezin, ↵ ile seç</span>
      <span>PolitikDesk Komuta Merkezi</span>
    </div>
  </div>
</div>
"""

_CMD_JS = """
(function(){
  var dialog = document.getElementById('pd-cmd-dialog');
  var input = document.getElementById('pd-cmd-input');
  var body = document.getElementById('pd-cmd-body');
  var btn = document.getElementById('pd-cmd-btn');
  if (!dialog || !input || !body) return;

  var DEFAULT_ITEMS = [
    { title: 'Gündem', href: '/feed', group: 'Çalışma Masası' },
    { title: 'Brifingler', href: '/briefing', group: 'Çalışma Masası' },
    { title: 'Vaat Takibi', href: '/promises', group: 'Çalışma Masası' },
    { title: 'Hesap Sor', href: '/accountability', group: 'Çalışma Masası' },
    { title: 'Siyasi Hafıza', href: '/memory', group: 'Çalışma Masası' },
    { title: 'Yayın Arşivi', href: '/archive', group: 'Çalışma Masası' },
    { title: 'Boru Hattı', href: '/admin/', group: 'Denetim' },
    { title: 'Denetim Kuyruğu', href: '/admin/review/', group: 'Denetim' },
    { title: 'Metrikler', href: '/admin/metrics', group: 'Denetim' },
    { title: 'Editoryal Kimlik', href: '/onboarding/profile', group: 'Ayarlar' }
  ];

  function openDialog(){
    dialog.classList.add('open');
    input.value = '';
    renderItems(DEFAULT_ITEMS);
    setTimeout(function(){ input.focus(); }, 50);
  }

  function closeDialog(){
    dialog.classList.remove('open');
  }

  if (btn) btn.addEventListener('click', openDialog);

  window.addEventListener('keydown', function(e){
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      dialog.classList.contains('open') ? closeDialog() : openDialog();
    } else if (e.key === 'Escape' && dialog.classList.contains('open')) {
      closeDialog();
    }
  });

  dialog.addEventListener('click', function(e){
    if (e.target === dialog) closeDialog();
  });

  function renderItems(items){
    body.innerHTML = '';
    if (!items.length) {
      body.innerHTML = '<div style="padding:16px;text-align:center;color:var(--color-fg-subtle);font-size:var(--text-sm)">Sonuç bulunamadı.</div>';
      return;
    }
    var currentGroup = '';
    items.forEach(function(item, idx){
      if (item.group && item.group !== currentGroup) {
        currentGroup = item.group;
        var grp = document.createElement('div');
        grp.className = 'cmd-group-label';
        grp.textContent = currentGroup;
        body.appendChild(grp);
      }
      var a = document.createElement('a');
      a.className = 'cmd-item' + (idx === 0 ? ' selected' : '');
      a.href = item.href;
      a.innerHTML = '<div class="cmd-item-left"><span>' + item.title + '</span></div>' + (item.hint ? '<span class="cmd-item-hint">' + item.hint + '</span>' : '');
      a.addEventListener('click', closeDialog);
      body.appendChild(a);
    });
  }

  var searchTimer = null;
  input.addEventListener('input', function(){
    var q = input.value.trim().toLowerCase();
    if (!q) { renderItems(DEFAULT_ITEMS); return; }
    var filtered = DEFAULT_ITEMS.filter(function(i){ return i.title.toLowerCase().indexOf(q) !== -1 || (i.group && i.group.toLowerCase().indexOf(q) !== -1); });
    renderItems(filtered);

    clearTimeout(searchTimer);
    if (q.length >= 2) {
      searchTimer = setTimeout(function(){
        fetch('/api/memory/actors?q=' + encodeURIComponent(q))
          .then(function(r){ return r.json(); })
          .then(function(data){
            var dynamic = [];
            if (data && data.items) {
              data.items.forEach(function(act){
                dynamic.push({
                  title: act.actor_name,
                  href: '/hafiza/' + encodeURIComponent(act.actor_name),
                  group: 'Aktörler (' + act.total_claims + ' kayıt)',
                  hint: 'Hafıza Profili'
                });
              });
            }
            if (dynamic.length) {
              renderItems(filtered.concat(dynamic));
            }
          }).catch(function(){});
      }, 150);
    }
  });

  input.addEventListener('keydown', function(e){
    var items = body.querySelectorAll('.cmd-item');
    if (!items.length) return;
    var selected = body.querySelector('.cmd-item.selected');
    var idx = Array.prototype.indexOf.call(items, selected);

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (selected) selected.classList.remove('selected');
      var next = (idx + 1) % items.length;
      items[next].classList.add('selected');
      items[next].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (selected) selected.classList.remove('selected');
      var prev = (idx - 1 + items.length) % items.length;
      items[prev].classList.add('selected');
      items[prev].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter') {
      if (selected) {
        e.preventDefault();
        selected.click();
        window.location.href = selected.href;
      }
    }
  });
})();
"""


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
    from config.election_mode import banner

    trail = crumbs or ((title, None),)
    scripts = "\n".join(part for part in (_THEME_JS, _CMD_JS, extra_js) if part)
    election = banner()
    election_html = (
        f'<div style="margin-bottom:var(--space-6)">{election}</div>' if election else ""
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
{_CMD_PALETTE_HTML}
<script>{scripts}</script>
</body></html>"""

