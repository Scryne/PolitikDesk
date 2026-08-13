"""Ortak HTML kabuğu, tema ve yardımcılar (F3-01).

### Neden Next.js değil, sunucu tarafı HTML

Yol Haritası F3-01 "Next.js + Tailwind + shadcn" diyordu. Faz 3'e
girilirken bu maddeden **bilinçli olarak sapıldı**; gerekçe
`docs/karar-itirazlari.md` (İtiraz-8) ve `docs/FAZ3-DURUM.md`'de yazılıdır.
Özeti:

  * Ürün **tek kullanıcılı kişisel bir araç** olarak kararlaştırıldı
    (Faz 4 İş Kolu A kapsam dışı). F3-01'in "magic link kimlik
    doğrulama, korumalı rota" DoD'si dayanaksız kaldı.
  * Ayrı bir node araç zinciri, mevcut CI'ın (ruff + mypy + pytest)
    **dışında** kalan bir kod tabanı demekti. Bu depoda her pazarlıksız
    kısıt bir testle korunuyor; arayüzü o disiplinin dışına çıkarmak
    "siyasi etiket yok" (G3 #8) gibi koşulları göz denetimine bırakırdı.
  * `/admin` ekranları Faz 1'den beri aynı desenle çalışıyor.

Sapma **kapsamı daraltmaz**: F3-02…F3-07'nin tüm DoD'leri karşılanır.

### Tema

Tek bir CSS değişkeni bloğu; açık/koyu tema `prefers-color-scheme` ile.
Harici font, CDN ve JS çatısı yok — olay sayfası p95 < 1,5 sn koşulu
(G3 #7) en ucuz yoldan tutulur.
"""

from __future__ import annotations

import html
from typing import Any, Final

# Spec §8.1 durum renkleri. UI'da renk TEK BAŞINA bilgi taşımaz; her
# rozetin yanında metin etiketi de bulunur (renk körlüğü + P4).
STATUS_COLORS: Final[dict[str, str]] = {
    "strongly_corroborated": "var(--ok)",
    "partially_corroborated": "var(--warn)",
    "single_source": "var(--amber)",
    "contradicted": "var(--bad)",
    "unverified": "var(--muted)",
}

STATUS_BADGES: Final[dict[str, tuple[str, str]]] = {
    "strongly_corroborated": ("🟢", "güçlü teyitli"),
    "partially_corroborated": ("🟡", "kısmen teyitli"),
    "single_source": ("🟠", "tek kaynaklı"),
    "contradicted": ("🔴", "çelişkili"),
    "unverified": ("⚪", "doğrulanmamış"),
}

EVENT_STATUS_BADGES: Final[dict[str, tuple[str, str]]] = {
    "developing": ("🟠", "GELİŞİYOR"),
    "settled": ("🟢", "OTURDU"),
    "contradicted": ("🔴", "ÇELİŞKİLİ"),
}

TIER_LABELS: Final[dict[int, str]] = {
    1: "Resmî kaynak", 2: "Ajans", 3: "Yayın", 4: "Sosyal",
}

STYLE: Final[str] = """
:root {
  --bg:#ffffff; --panel:#f6f8fa; --text:#1f2328; --muted:#656d76;
  --border:#d0d7de; --link:#0969da; --ok:#1a7f37; --warn:#9a6700;
  --amber:#bc4c00; --bad:#cf222e; --accent:#0969da;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:#0d1117; --panel:#161b22; --text:#e6edf3; --muted:#8b949e;
    --border:#30363d; --link:#4493f8; --ok:#3fb950; --warn:#d29922;
    --amber:#db6d28; --bad:#f85149; --accent:#4493f8;
  }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font-size:15px;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  line-height:1.55; }
.wrap { max-width:960px; margin:0 auto; padding:1.5rem 1.25rem 4rem; }
a { color:var(--link); }
header.top { border-bottom:1px solid var(--border); background:var(--panel); }
header.top .wrap { padding:.7rem 1.25rem; display:flex; gap:1.2rem;
  align-items:center; flex-wrap:wrap; }
header.top .brand { font-weight:700; letter-spacing:.02em; text-decoration:none;
  color:var(--text); }
header.top nav a { text-decoration:none; font-size:.92rem; color:var(--muted); }
header.top nav a:hover, header.top nav a.on { color:var(--text); }
header.top nav { display:flex; gap:1rem; margin-left:auto; }
h1 { font-size:1.55rem; line-height:1.25; margin:.2rem 0 .5rem; }
h2 { font-size:.8rem; letter-spacing:.09em; text-transform:uppercase;
  color:var(--muted); margin:2rem 0 .6rem; font-weight:600; }
h3 { font-size:1rem; margin:1.2rem 0 .4rem; }
.card { border:1px solid var(--border); border-radius:8px; padding:1rem;
  background:var(--panel); }
.meta { color:var(--muted); font-size:.86rem; }
.row { display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; }
.cols { display:grid; grid-template-columns:1fr 1fr; gap:1.2rem; }
@media (max-width:720px) { .cols { grid-template-columns:1fr; } }
table { border-collapse:collapse; width:100%; }
th,td { border-bottom:1px solid var(--border); padding:.5rem .4rem;
  text-align:left; font-size:.9rem; vertical-align:top; }
th { color:var(--muted); font-weight:600; font-size:.78rem;
  text-transform:uppercase; letter-spacing:.05em; }
.badge { display:inline-flex; align-items:center; gap:.3rem; font-size:.78rem;
  border:1px solid var(--border); border-radius:999px; padding:.1rem .55rem;
  white-space:nowrap; }
.tier { font-size:.72rem; color:var(--muted); border:1px solid var(--border);
  border-radius:4px; padding:0 .3rem; }
button, .btn { font:inherit; font-size:.9rem; cursor:pointer; border-radius:6px;
  border:1px solid var(--border); background:var(--bg); color:var(--text);
  padding:.42rem .9rem; text-decoration:none; display:inline-block; }
button:hover:not(:disabled), .btn:hover { border-color:var(--accent); }
button:disabled { opacity:.45; cursor:not-allowed; }
button.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
details { border:1px solid var(--border); border-radius:6px; padding:.5rem .7rem;
  background:var(--bg); }
details+details { margin-top:.4rem; }
summary { cursor:pointer; font-size:.9rem; }
.notice { border-left:3px solid var(--warn); padding:.5rem .8rem;
  background:var(--panel); border-radius:0 6px 6px 0; font-size:.9rem; }
.notice.bad { border-left-color:var(--bad); }
.notice.ok { border-left-color:var(--ok); }
.claim { padding:.45rem 0; border-bottom:1px solid var(--border); }
.claim:last-child { border-bottom:0; }
.mono { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.82rem; }
.strip { background:var(--panel); border:1px solid var(--border);
  border-radius:6px; padding:.5rem .8rem; font-size:.9rem; margin-bottom:1rem; }
textarea { width:100%; min-height:8rem; font:inherit; padding:.6rem;
  border:1px solid var(--border); border-radius:6px; background:var(--bg);
  color:var(--text); }
input,select { font:inherit; padding:.35rem .5rem; border:1px solid var(--border);
  border-radius:6px; background:var(--bg); color:var(--text); }
fieldset { border:1px solid var(--border); border-radius:8px; margin:0 0 1rem;
  padding:.9rem 1rem; }
legend { font-size:.9rem; font-weight:600; padding:0 .4rem; }
label.opt { display:block; padding:.15rem 0; font-size:.92rem; }
.timeline { list-style:none; margin:0; padding:0; }
.timeline li { padding:.4rem 0 .4rem 1.1rem; border-left:2px solid var(--border);
  margin-left:.35rem; position:relative; }
.timeline li::before { content:""; position:absolute; left:-5px; top:.85rem;
  width:8px; height:8px; border-radius:50%; background:var(--border); }
.bar { height:6px; border-radius:3px; background:var(--border); overflow:hidden; }
.bar span { display:block; height:100%; background:var(--accent); }
"""

NAV: Final[tuple[tuple[str, str], ...]] = (
    ("/feed", "Feed"),
    ("/briefing", "Brifing"),
    ("/onboarding/profile", "Editoryal Kimlik"),
    ("/admin/metrics", "Metrikler"),
    ("/admin/", "Admin"),
)


def esc(value: object) -> str:
    """HTML kaçışı. Kullanıcıdan ve kaynaklardan gelen HER metin geçer."""
    return html.escape(str(value if value is not None else ""))


def badge(status: str) -> str:
    icon, label = STATUS_BADGES.get(status, ("⚪", status))
    color = STATUS_COLORS.get(status, "var(--muted)")
    return f'<span class="badge" style="color:{color}">{icon} {esc(label)}</span>'


def event_badge(status: str) -> str:
    icon, label = EVENT_STATUS_BADGES.get(status, ("⚪", status))
    return f'<span class="badge">{icon} {esc(label)}</span>'


def tier_badge(tier: int | None) -> str:
    tier = int(tier or 4)
    return f'<span class="tier" title="{esc(TIER_LABELS.get(tier, ""))}">T{tier}</span>'


def when(value: Any, fmt: str = "%d %b %H:%M") -> str:
    if value is None:
        return "—"
    try:
        return format(value, fmt)
    except (TypeError, ValueError):
        return esc(value)


def page(title: str, body: str, *, active: str = "", extra_js: str = "") -> str:
    """Sayfayı ortak kabuğa sarar."""
    nav = "".join(
        f'<a href="{href}" class="{"on" if href == active else ""}">{esc(label)}</a>'
        for href, label in NAV
    )
    script = f"<script>{extra_js}</script>" if extra_js else ""

    # Spec §12.6 madde 5: Election Mode açıkken kullanıcıya görünür
    # gösterge. Kapalıyken boş string döner (F4-15 — varsayılan kapalı).
    from config.election_mode import banner

    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · PolitikDesk</title>
<style>{STYLE}</style></head><body>
<header class="top"><div class="wrap">
  <a class="brand" href="/feed">PolitikDesk</a>
  <nav>{nav}</nav>
</div></header>
<div class="wrap">{banner()}{body}</div>
{script}
</body></html>"""


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
