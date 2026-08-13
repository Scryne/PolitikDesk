"""Live Feed ekranı (F3-02, F3-07, F3-18 · Spec §14.1 kalem 1).

F3-02 DoD: salience sıralı olay kartları; her kartta durum rozeti,
kaynak sayısı kırılımı, son güncelleme; **30 sn'de bir sessiz yenileme.**

"Sessiz" burada teknik bir kısıttır: yenileme sırasında sayfa kaymaz,
kaydırma konumu korunur ve açık bir panel kapanmaz. Tam sayfa
`location.reload()` bunların üçünü de bozardı; kart listesi ayrı bir
uçtan (`/feed/cards`) çekilip yerine konur.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from politikdesk.evidence.explain import KIND_LABELS
from politikdesk.users import current_user_id, touch_last_seen
from politikdesk.web import repository
from politikdesk.web.layout import ACTIVITY_JS, esc, event_badge, page, when

router = APIRouter(tags=["web"])

REFRESH_SECONDS = 30

# Salience şeffaflık popover'ı (F3-07). Anahtarlar `evidence/salience.py`
# çıktısındandır; etiketler Spec §8.4'ün bileşen adlarını Türkçeleştirir.
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


def _breakdown_text(raw: dict[str, Any] | None) -> str:
    """{'official':1,'media':3} -> 'Resmî 1 · Medya 3'"""
    if not raw:
        return "kaynak kırılımı yok"
    return " · ".join(
        f"{KIND_LABELS.get(kind, kind)} {count}"
        for kind, count in sorted(raw.items())
        if count
    )


def _salience_popover(row: dict[str, Any]) -> str:
    """Skora tıklayınca açılan kırılım (F3-07).

    DoD'nin ikinci yarısı — "bu bir doğruluk skoru değildir" notu —
    kozmetik değil: Spec §15 madde 13 tek sayısal doğruluk yüzdesini
    yasaklar ve 0-100 arası bir skor, not olmadan öyle okunur.
    """
    breakdown = row.get("salience_breakdown") or {}
    components = breakdown.get("components") or {}
    rows = "".join(
        f"<tr><td>{esc(_COMPONENT_LABELS.get(key, key))}</td>"
        f"<td class='mono'>{esc(round(float(value), 2))}</td></tr>"
        for key, value in sorted(components.items())
        if isinstance(value, int | float)
    )
    # Cezalar ayrı gösterilir: bir olayın skorunun NEDEN düştüğü,
    # nasıl yükseldiği kadar açıklanmalıdır (P4).
    rows += "".join(
        f"<tr><td>{esc(_PENALTY_LABELS.get(key, key))}</td>"
        f"<td class='mono' style='color:var(--bad)'>−{esc(round(float(value), 2))}</td></tr>"
        for key, value in sorted((breakdown.get("penalties") or {}).items())
        if isinstance(value, int | float)
    )
    return f"""<details>
<summary>Salience {row['displayed_salience']} — kırılımı gör</summary>
<table>
  <tr><th>Bileşen</th><th>Puan</th></tr>
  {rows or "<tr><td colspan='2'>Kırılım henüz hesaplanmadı.</td></tr>"}
  <tr><td><b>Global toplam</b> (0-90)</td>
      <td class='mono'><b>{row['global_salience']}</b></td></tr>
  <tr><td>Kişisel ayarlama (0-10, saklanmaz)</td>
      <td class='mono'>+{row['personal_salience']}</td></tr>
</table>
<p class="meta">Bu bir <b>önem</b> skorudur, <b>doğruluk skoru değildir.</b>
Yüksek skor iddianın doğru olduğu anlamına gelmez; gündemde ne kadar yer
tuttuğunu gösterir. Formül kural tabanlıdır ve beğeni/paylaşım gibi
etkileşim girdisi içermez (Spec §8.4, §15 madde 14).</p>
</details>"""


def _card(row: dict[str, Any]) -> str:
    weak = int(row.get("weak_claim_count") or 0)
    claims = int(row.get("claim_count") or 0)
    groups = int(row.get("independence_groups") or 0)

    warnings: list[str] = []
    if groups < 2:
        warnings.append("⚠ Tek yayın grubu")
    if row.get("review_flag") == "needs_review":
        warnings.append("⚠ Denetimde")
    if weak:
        warnings.append(f"{weak}/{claims} iddia teyit bekliyor")

    return f"""<article class="card" style="margin-bottom:.9rem">
  <div class="row meta">
    {event_badge(row["status"])}
    <span>{esc(_breakdown_text(row.get("source_breakdown")))}</span>
    <span>· {row["article_count"]} makale</span>
    <span>· {row["independent_count"]} bağımsız teyit</span>
    <span style="margin-left:auto">Son güncelleme {when(row["last_update_at"])}</span>
  </div>
  <h3 style="margin:.35rem 0 .3rem">
    <a href="/event/{row["id"]}" style="text-decoration:none">{esc(row["title"])}</a>
  </h3>
  <div class="row meta">{"".join(f"<span>{esc(w)}</span>" for w in warnings)}</div>
  <div style="margin-top:.5rem">{_salience_popover(row)}</div>
</article>"""


def _strip(summary: dict[str, Any]) -> str:
    """"Sen yokken ne oldu" şeridi (F3-18) — tek satır."""
    if not summary.get("available"):
        return (
            '<div class="strip">İlk ziyaretin. Feed salience sırasına göre '
            "dizilidir; skor önemi gösterir, doğruluğu değil.</div>"
        )
    total = summary.get("total", 0)
    if not total:
        return '<div class="strip">Son ziyaretinden bu yana yeni olay yok.</div>'

    important = summary.get("important", 0)
    top = summary.get("top_title")
    tail = f" En önemlisi: <b>{esc(top)}</b>." if top else ""
    return (
        f'<div class="strip">Sen yokken <b>{total}</b> yeni olay eklendi, '
        f"<b>{important}</b> tanesi önemli.{tail}</div>"
    )


def _cards_html(user_id: int, limit: int) -> str:
    rows = repository.feed(user_id, limit=limit)
    if not rows:
        return (
            '<p class="meta">Henüz olay yok. <code>make ingest</code> ile '
            "toplama turu çalıştırın.</p>"
        )
    return "".join(_card(row) for row in rows)


@router.get("/", response_class=HTMLResponse)
@router.get("/feed", response_class=HTMLResponse)
def feed_page(limit: int = 40) -> str:
    user_id = current_user_id()
    previous_visit = touch_last_seen(user_id)
    summary = repository.since_last_visit(user_id, previous_visit)

    body = f"""
{_strip(summary)}
<h1>Live Feed</h1>
<p class="meta">Salience sıralı makro ekonomi olayları ·
  <span id="refreshed">şimdi güncellendi</span> ·
  {REFRESH_SECONDS} sn'de bir sessizce yenilenir</p>
<div id="cards">{_cards_html(user_id, limit)}</div>
"""

    js = ACTIVITY_JS + f"""
setInterval(async function(){{
  if (document.hidden) return;
  try {{
    var r = await fetch('/feed/cards?limit={limit}');
    if (!r.ok) return;
    // Sessiz yenileme: açık <details> panelleri korunur, sayfa kaymaz.
    var open = new Set([...document.querySelectorAll('#cards details[open]')]
                       .map(d => d.closest('article').querySelector('a').href));
    document.getElementById('cards').innerHTML = await r.text();
    document.querySelectorAll('#cards article').forEach(function(a){{
      if (open.has(a.querySelector('a').href)) a.querySelector('details').open = true;
    }});
    document.getElementById('refreshed').textContent =
      new Date().toLocaleTimeString('tr-TR') + ' güncellendi';
  }} catch (e) {{ /* ağ hatası sayfayı bozmaz */ }}
}}, {REFRESH_SECONDS * 1000});
"""
    return page("Feed", body, active="/feed", extra_js=js)


@router.get("/feed/cards", response_class=HTMLResponse)
def feed_cards(limit: int = 40) -> str:
    """Sessiz yenilemenin çektiği parça (tam sayfa değil)."""
    return _cards_html(current_user_id(), limit)
