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

from functools import lru_cache
from typing import Final

from politikdesk.web.ui import keys
from politikdesk.web.ui.components import esc, script_json
from politikdesk.web.ui.css import stylesheet
from politikdesk.web.ui.icons import icon
from politikdesk.web.ui.nonce import nonce_attr

STATIC_BASE: Final[str] = "/static"

# (grup başlığı, ((href, etiket, ikon), ...))
# Sıra ürünün günlük akışını izler: feed → olay → taslak (README "günlük
# kullanım"), sonra denetim, en sonda ayar.
NAV: Final[tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...]] = (
    (
        "Çalışma masası",
        (
            ("/feed", "Gündem", "feed"),
            ("/war-room", "Kumanda Odası", "zap"),
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

# ── Eylem dağıtıcısı (Faz 7 / ADR-011) ──────────────────────────────────
#
# `onclick="pdX()"` özniteliklerinin yerini alır. CSP'de `'unsafe-inline'`
# kalktığı an satır içi öznitelik işleyicileri tarayıcı tarafından SESSİZCE
# çalıştırılmaz — nonce onları KURTARMAZ, çünkü nonce yalnızca `<script>`
# etiketine uygulanır. Bu yüzden hepsi buraya taşındı.
#
# ### Neden delegasyon, neden öğe başına addEventListener değil
#
# `feed.py::pdRefresh` canlı yenilemede `box.innerHTML = await r.text()` ile
# kart listesinin TAMAMINI değiştirir. Yükleme anında tek tek bağlanan
# dinleyiciler o değişimde kaybolurdu ve yenilemeden sonra hiçbir kart
# düğmesi çalışmazdı. `document` üzerinde tek bir dinleyici DOM değişse de
# ayakta kalır.
#
# ### Neden `window[isim]` değil, açık allowlist
#
# Eylem adını `window` üzerinde çözmek gerçek bir CSP bypass'ı açardı:
# `data-pd-click="eval"` + `data-pd-args='["...kod..."]'` yazabilen bir
# enjeksiyon, dağıtıcıyı kendi kodunu çalıştıran bir gadget'a çevirirdi.
# `pdActions` prototipsiz (`Object.create(null)`) bir kayıt defteridir;
# yalnızca `pdAction()` ile AÇIKÇA kaydedilmiş fonksiyonlar çağrılabilir.
# Prototipsiz olması `__proto__`/`constructor` gibi adların da boş dönmesini
# garanti eder.
#
# ### Argüman sözleşmesi
#
#     fn.apply(öğe, [...data-pd-args] + [öğe, olay])
#
# Yani veri argümanları önce, sonra öğenin kendisi, en sonda olay nesnesi.
# Bu sıra bilinçli seçildi: eski `pdFilterAcc('all', this)` çağrısı
# `('all', öğe, olay)` olur ve `function(filterKey, btn)` imzası HİÇ
# DEĞİŞMEDEN doğru argümanları alır. Fazla argüman JavaScript'te yok
# sayılır. Böylece 50 işleyici taşınırken tek bir fonksiyon gövdesi
# değiştirilmedi — regresyon yüzeyi işaretlemeyle sınırlı kaldı.
_DISPATCH_JS: Final[str] = """
window.pdActions = Object.create(null);
window.pdAction = function(name, fn){ window.pdActions[name] = fn; };
(function(){
  function dispatch(ev, attr){
    var target = ev.target;
    if (!target || typeof target.closest !== 'function') return;
    var el = target.closest('[' + attr + ']');
    if (!el) return;
    var fn = window.pdActions[el.getAttribute(attr)];
    if (typeof fn !== 'function') return;
    var args = [];
    var raw = el.getAttribute('data-pd-args');
    if (raw) {
      try { args = JSON.parse(raw); } catch (e) { return; }
      if (!Array.isArray(args)) return;
    }
    fn.apply(el, args.concat([el, ev]));
  }
  document.addEventListener('click', function(ev){ dispatch(ev, 'data-pd-click'); });
  document.addEventListener('input', function(ev){ dispatch(ev, 'data-pd-input'); });
  document.addEventListener('change', function(ev){ dispatch(ev, 'data-pd-change'); });
})();
"""

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
  var s = document.createElement('span');
  s.textContent = msg;
  t.replaceChildren(s);
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

// Kabuk düzeyindeki eylemler. `pdCopy` her ekranda kullanılıyor; `print` ve
// `select-all` ise eskiden satır içi tıklama özniteliğinde duran iki tek
// satırlık ifadeydi (window.print / this.select).
window.pdAction('copy', window.pdCopy);
window.pdAction('print', function(){ window.print(); });
window.pdAction('select-all', function(el){ el.select(); });
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
    """Kenar çubuğu.

    **`aria-label` neden zorunlu (20 Ağustos 2026 erişilebilirlik ölçümü).**

    Dar ekranda `css.py` etiketleri `.nav-item span{display:none}` ile
    gizler. `display:none` öğeyi yalnızca görünmez yapmaz — onu
    **erişilebilirlik ağacından tamamen siler.** İkonlar (doğru biçimde)
    `aria-hidden="true"` taşıdığı için geriye hiçbir ad kalmıyordu:
    ekran okuyucu 13 gezinme bağlantısının hepsini adsız "link" diye
    okuyordu, yani uygulama klavye/ekran okuyucu ile gezilemezdi.

    Lighthouse ölçtü: `/feed` erişilebilirlik skoru **93** (DESIGN.md
    Bölüm 12 eşiği ≥95), `link-name` denetimi 13 öğede düştü.

    `aria-label` görünür etiketin AYNISIDIR — bu WCAG 2.5.3 (Label in
    Name) gereğidir: sesli komutla "Kumanda Odası" diyen kullanıcı ile
    ekranda yazanı gören kullanıcı aynı adı kullanabilmeli.
    """
    groups = []
    for title, items in NAV:
        links = "".join(
            f'<a class="nav-item" href="{esc(href)}" aria-label="{esc(label)}"'
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

    return f"""<aside class="side" id="pd-sidebar">
  <div class="side-head">
    <a class="brand" href="/feed" aria-label="PolitikDesk — gündeme dön">
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

    menu_btn = (
        f'<button class="btn ghost icon sm mobile-menu-btn" id="pd-menu-btn" type="button" '
        f'aria-label="Menüyü Aç" aria-expanded="false" title="Menü">'
        f'{icon("menu", 18)}</button>'
    )

    cmd_trigger = (
        '<button class="btn ghost sm" id="pd-cmd-btn" type="button" '
        'style="margin-left:auto;gap:var(--space-2);color:var(--color-fg-muted);" '
        'title="Komuta Paleti (Ctrl+K / ⌘K)">'
        f'{icon("search", 14)}<span>Ara & Komutlar</span>'
        '<kbd class="shortcut-key" style="font-size:10px;">⌘K</kbd>'
        '</button>'
    )

    return (
        f'<header class="topbar">{menu_btn}<nav class="crumbs" aria-label="Konum">'
        f"{''.join(parts)}</nav>{cmd_trigger}</header>"
    )


# Paletin boşken gösterdiği gezinme listesi — `NAV`'dan TÜRETİLİR.
#
# Bu satır bir kopyayı siliyor: liste eskiden `_CMD_JS` içinde elle
# yazılmış 11 nesneydi. Nav'a bir sayfa eklendiğinde palette görünmüyor,
# nav'dan bir sayfa kalktığında palette kırık bağlantı olarak kalıyordu.
# İkisi de sessiz arızadır — kimse "palette eksik" diye şikâyet etmez,
# özelliğin var olduğunu bilmez.
#
# Sözleşme `web/search.py::SearchHit` ile aynı: {title, subtitle, href}.
# `group` alanı paletin grup başlığıdır ve sunucu tarafındaki arama da
# aynı başlıkları üretir; iki kaynak aynı ekranda buluştuğunda başlıklar
# tutmazsa kullanıcı iki ayrı "Sayfalar" grubu görürdü.
@lru_cache(maxsize=1)
def _nav_items_js() -> str:
    # Geç içe aktarma: `web.search` bu modülün `NAV`ını okur, bu modül de
    # onun `page_hits`ini. Modül düzeyinde içe aktarılsaydı döngü olurdu.
    from politikdesk.web.search import page_hits

    items = [hit.as_dict() for hit in page_hits()]
    return f"window.pdNavItems = {script_json(items)};\n"


_CMD_PALETTE_HTML = """
<div id="pd-cmd-dialog" class="cmd-backdrop" role="dialog" aria-modal="true" aria-label="Komuta Paleti">
  <div class="cmd-box">
    <div class="cmd-header">
      <span class="ic">""" + icon("search", 16) + """</span>
      <label class="sr" for="pd-cmd-input">Sayfa, olay, aktör, iddia, kaynak veya gösterge ara</label>
      <input type="text" id="pd-cmd-input" class="cmd-input" autocomplete="off" spellcheck="false"
             placeholder="Sayfa, olay, aktör, iddia, kaynak, gösterge ara…">
      <kbd class="shortcut-key" style="font-size:10px;">Esc</kbd>
    </div>
    <div id="pd-cmd-body" class="cmd-body" role="listbox" aria-label="Arama sonuçları"></div>
    <div class="cmd-footer">
      <span>↑↓ ile gezin, ↵ ile seç</span>
      <span>En az 2 harf</span>
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

  // Boş paletin gösterdiği gezinme listesi. SUNUCUDAN gelir
  // (`window.pdNavItems`, `shell.NAV`'dan türetilir). Bir dönem burada
  // elle yazılmış 11 satırlık bir kopya duruyordu; nav'a eklenen sayfa
  // palette görünmüyordu ve kimse fark etmiyordu.
  var DEFAULT_ITEMS = window.pdNavItems || [];

  // Sunucudaki `search.fold` ile AYNI kural: dört "i" harfi (İ I ı i)
  // tek harfe indirgenir. Aynı sorgunun istemcide ve sunucuda farklı
  // eşleşmesi, kullanıcıya listenin "yanıp sönmesi" olarak görünürdü.
  function pdFold(s){
    return String(s).replace(/[İIı]/g, 'i').toLowerCase();
  }

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

  function emptyMessage(text){
    var box = document.createElement('div');
    box.className = 'cmd-empty';
    box.textContent = text;
    body.replaceChildren(box);
  }

  function renderItems(items){
    if (!items.length) {
      emptyMessage('Eşleşen kayıt yok. Aktör, olay, iddia, kaynak veya gösterge adı deneyin.');
      return;
    }
    var frag = document.createDocumentFragment();
    var currentGroup = '';
    items.forEach(function(item, idx){
      if (item.group && item.group !== currentGroup) {
        currentGroup = item.group;
        var grp = document.createElement('div');
        grp.className = 'cmd-group-label';
        grp.textContent = currentGroup;
        frag.appendChild(grp);
      }
      var a = document.createElement('a');
      a.className = 'cmd-item' + (idx === 0 ? ' selected' : '');
      a.href = item.href;
      // innerHTML DEĞİL: `item.title` aktör ve iddia aramasında
      // veritabanından gelir ve o metinler NER/LLM ile DIŞ KAYNAKLI
      // makale gövdesinden çıkarılır. Kaynağı güvenilmez bir dizeyi
      // innerHTML'e vermek saklı XSS'tir.
      var left = document.createElement('div');
      left.className = 'cmd-item-left';
      var titleEl = document.createElement('span');
      titleEl.textContent = item.title;
      left.appendChild(titleEl);
      a.appendChild(left);
      if (item.subtitle) {
        var hintEl = document.createElement('span');
        hintEl.className = 'cmd-item-hint';
        hintEl.textContent = item.subtitle;
        a.appendChild(hintEl);
      }
      a.addEventListener('click', closeDialog);
      frag.appendChild(a);
    });
    body.replaceChildren(frag);
  }

  // Sunucudaki aramanın en son hangi harf dizisi için istendiği. Ağdan
  // geç dönen bir yanıt, kullanıcının o sırada yazdığı YENİ sorgunun
  // sonucunu ezmemeli — yoksa hızlı yazan biri kendi sorgusunun değil
  // iki harf öncesinin sonuçlarını görür.
  var inFlightFor = '';
  var searchTimer = null;

  input.addEventListener('input', function(){
    var q = input.value.trim();
    if (!q) { inFlightFor = ''; renderItems(DEFAULT_ITEMS); return; }

    // Anında geri bildirim: sayfa listesi istemcide filtrelenir, ağ
    // beklenmez. Sunucu yanıtı gelince yerini tam sonuç listesine bırakır.
    var needle = pdFold(q);
    var local = DEFAULT_ITEMS.filter(function(i){
      return pdFold(i.title).indexOf(needle) !== -1;
    });
    renderItems(local);

    clearTimeout(searchTimer);
    if (q.length < 2) { inFlightFor = ''; return; }
    searchTimer = setTimeout(function(){
      inFlightFor = q;
      // Tek uç, tek sözleşme: {results: [{kind, group, title, subtitle, href}]}.
      // Türe göre ayrı uç ve ayrı okuma kodu, D-02'deki sessiz arızanın
      // yedi kopyası olurdu (gerekçe: politikdesk/web/search.py başlığı).
      fetch('/api/search?q=' + encodeURIComponent(q))
        .then(function(r){ return r.ok ? r.json() : null; })
        .then(function(data){
          if (!data || inFlightFor !== q) return;
          if (!data.results || !data.results.length) {
            if (!local.length) emptyMessage('“' + q + '” ile eşleşen kayıt yok.');
            return;
          }
          renderItems(data.results);
        })
        .catch(function(){
          // Ağ düştüyse istemcide filtrelenmiş gezinme listesi ekranda
          // KALIR; palet gezinme aracı olmaya devam eder.
        });
    }, 150);
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


_DRAWER_JS: Final[str] = """
(function(){
  var menuBtn = document.getElementById('pd-menu-btn');
  var side = document.getElementById('pd-sidebar');
  var backdrop = document.getElementById('pd-side-backdrop');
  if (!menuBtn || !side || !backdrop) return;

  function openDrawer(){
    side.classList.add('open');
    backdrop.classList.add('open');
    menuBtn.setAttribute('aria-expanded', 'true');
  }
  function closeDrawer(){
    side.classList.remove('open');
    backdrop.classList.remove('open');
    menuBtn.setAttribute('aria-expanded', 'false');
  }

  menuBtn.addEventListener('click', function(){
    side.classList.contains('open') ? closeDrawer() : openDrawer();
  });
  backdrop.addEventListener('click', closeDrawer);
  window.addEventListener('keydown', function(e){
    if (e.key === 'Escape' && side.classList.contains('open')) closeDrawer();
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
    # `_DISPATCH_JS` EN BAŞTA: kayıt defterini (`window.pdAction`) o kurar,
    # sonraki her blok ona eylem kaydeder. Sıra bozulursa kayıtlar
    # `undefined is not a function` ile düşer.
    #
    # Kısayol tablosu (Faz 8.3) `active` rotasından OTOMATİK gelir. Sayfa
    # modülü kendi tablosunu yazmaz — yazabilseydi sözleşme yine ikiye
    # bölünürdü. Tablo dağıtıcıdan ÖNCE gelir; dağıtıcı onu okur.
    scripts = "\n".join(
        part
        for part in (
            _DISPATCH_JS,
            keys.keymap_js(active),
            keys.DISPATCH_JS,
            _THEME_JS,
            _DRAWER_JS,
            _nav_items_js(),
            _CMD_JS,
            extra_js,
        )
        if part
    )
    # Bu isteğin nonce'u. Her iki `<script>` etiketi de AYNI değeri taşır ve
    # o değer yanıtın CSP başlığındakiyle birebir aynıdır.
    nonce = nonce_attr()
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
<script{nonce}>{_THEME_BOOT}</script>
<style>{stylesheet(STATIC_BASE)}</style>
</head>
<body{body_attrs}>
<a class="sr" href="#main">İçeriğe atla</a>
<div class="side-backdrop" id="pd-side-backdrop" aria-hidden="true"></div>
<div class="app">
{_sidebar(active)}
<div class="main">
{_topbar(trail)}
<main class="content" id="main">{election_html}{body}</main>
</div>
</div>
{_CMD_PALETTE_HTML}
<script{nonce}>{scripts}</script>
</body></html>"""

