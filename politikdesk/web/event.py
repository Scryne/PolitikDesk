"""Olay Sayfası (F3-03 … F3-07, F3-11, F3-21 · Spec §14.3).

Spec §14.3'ün ekran taslağındaki her bölüm burada karşılığını bulur:

| Taslaktaki bölüm | Görev | Uygulama |
|---|---|---|
| Salience 84 ⓘ | F3-07 | `_salience_panel` |
| TL;DR | F3-03 | `_tldr` — **deterministik**, LLM yok |
| NE BİLİYORUZ / NE BİLMİYORUZ | F3-03 | `_knowledge_columns` |
| KANIT + [Neden 🟢?] | F3-04 | `_evidence_block` + `evidence/explain.py` |
| KAYNAKLAR (çerçeve farkı) | F3-05 | `_sources_table` |
| ZAMAN ÇİZELGESİ | F3-06 | `_timeline` |
| ÖNCEKİ BAĞLAM | F3-03 | `_related` |
| SIRADAKİ BEKLENEN | F3-03 | `_upcoming` |
| EDİTORYAL FIRSATLAR | F3-11 | `_editorial_panel` |

### TL;DR neden LLM'siz

Spec §14.3: *"2-3 cümle özet. **Yalnızca doğrulanmış unsurlardan
kurulur.**"* Bu cümle bir üslup tercihi değil, bir kısıttır. Doğrulanmış
iddiaların metni zaten veritabanında duruyor ve `verify_quote` ile
kaynağa bağlanmış durumda. Onları bir modele yeniden yazdırmak, kısıtı
koruyan tek şeyi (metnin kanıttan gelmesi) bir prompt talimatına
indirgerdi. Özet, en güçlü iddialardan **birleştirilir**.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from politikdesk.editorial.generator import ANGLES
from politikdesk.editorial.service import can_generate
from politikdesk.evidence.explain import KIND_LABELS, explain, explain_event_status
from politikdesk.users import current_user_id
from politikdesk.web import repository
from politikdesk.web.layout import (
    ACTIVITY_JS,
    badge,
    esc,
    event_badge,
    page,
    tier_badge,
    when,
)

router = APIRouter(tags=["web"])

# "Ne biliyoruz" sütununa girecek durumlar. Diğerleri "ne bilmiyoruz"
# sütunundadır — bilinmeyeni bilinen gibi göstermek Spec §15 madde 3'ün
# ihlalidir ve bu ayrım onun ekran karşılığıdır.
KNOWN_STATUSES = ("strongly_corroborated", "partially_corroborated")

MAX_TLDR_CLAIMS = 3


def _tldr(claims: list[dict[str, Any]]) -> str:
    """2-3 cümle özet — yalnızca doğrulanmış iddialardan (Spec §14.3)."""
    verified = [c for c in claims if c["evidence_status"] in KNOWN_STATUSES]
    if not verified:
        return (
            '<p class="meta">Bu olayda henüz teyit edilmiş iddia yok. '
            "Özet yalnızca doğrulanmış unsurlardan kurulur; teyit "
            "gelmeden özet de üretilmez.</p>"
        )
    sentences = [
        c["claim_text"].strip().rstrip(".") + "." for c in verified[:MAX_TLDR_CLAIMS]
    ]
    return "<p style='margin:0'>" + " ".join(esc(s) for s in sentences) + "</p>"


def _knowledge_columns(claims: list[dict[str, Any]]) -> str:
    """NE BİLİYORUZ / NE BİLMİYORUZ (Spec §14.3)."""
    known = [c for c in claims if c["evidence_status"] in KNOWN_STATUSES]
    unknown = [c for c in claims if c["evidence_status"] not in KNOWN_STATUSES]

    def _list(items: list[dict[str, Any]], empty: str) -> str:
        if not items:
            return f'<p class="meta">{esc(empty)}</p>'
        return "".join(
            f'<div class="claim">{badge(c["evidence_status"])} '
            f'<span>{esc(c["claim_text"])}</span>'
            f'<div class="meta" style="margin-top:.15rem">'
            f'{esc(c["claim_type"])} · {c["evidence_count"]} kanıt bağı</div></div>'
            for c in items
        )

    return f"""<div class="cols">
  <div><h2>Ne biliyoruz</h2>{_list(known, "Teyit edilmiş iddia yok.")}</div>
  <div><h2>Ne bilmiyoruz</h2>{_list(unknown, "Açık kalan iddia yok.")}</div>
</div>"""


def _evidence_block(data: dict[str, Any]) -> str:
    """KANIT bloğu + "Neden bu durum?" açılır paneli (F3-04)."""
    event = data["event"]
    articles = data["articles"]

    kinds: dict[str, int] = {}
    for article in articles:
        kinds[article["kind"]] = kinds.get(article["kind"], 0) + 1
    breakdown = " · ".join(
        f"{KIND_LABELS.get(kind, kind)} {count}" for kind, count in sorted(kinds.items())
    )

    panels = "".join(
        _why_panel(claim) for claim in data["claims"]
    ) or '<p class="meta">Henüz iddia çıkarılmamış.</p>'

    return f"""<h2>Kanıt</h2>
<div class="card">
  <div>{esc(explain_event_status(
      int(event["independent_count"] or 0),
      bool(event["has_primary_source"]),
      int(event["independence_groups"] or 0),
  ))}</div>
  <div class="meta" style="margin-top:.3rem">{esc(breakdown or "kaynak yok")}</div>
  <div style="margin-top:.7rem">{panels}</div>
</div>"""


def _why_panel(claim: dict[str, Any]) -> str:
    """"Neden bu durum?" — `status_reason` insan diline çevrilir (F3-04).

    Kural adı ve girdiler AÇIKÇA görünür: bir gerekçe, doğrulanabilir
    olmadıkça gerekçe değildir (P4).
    """
    detail = explain(claim["evidence_status"], claim.get("status_reason"))
    facts = "".join(
        f"<tr><td>{esc(f['label'])}</td><td class='mono'>{esc(f['value'])}</td></tr>"
        for f in detail["facts"]
    )
    return f"""<details>
<summary>{badge(claim["evidence_status"])}
  Neden? — <b>{esc(detail["rule"])}: {esc(detail["rule_title"])}</b>
  <span class="meta">· {esc(claim["claim_text"][:80])}</span></summary>
<p style="margin:.5rem 0">{esc(detail["sentence"])}</p>
<table>{facts or "<tr><td class='meta'>Girdi kaydı yok.</td></tr>"}</table>
<p class="meta">Kural motoru: {esc(detail["engine_version"] or "—")} ·
   hesaplandı {esc(detail["computed_at"] or "—")} ·
   bu durum bir LLM çıktısı DEĞİLDİR (Spec §8.1).</p>
</details>"""


def _sources_table(data: dict[str, Any]) -> str:
    """KAYNAKLAR + çerçeve farkı paneli (F3-05).

    ⛔ Bu tabloda **siyasi etiket yoktur ve olamaz** (Spec §8.5, §15
    madde 5). Kaynaklar yalnızca adı, katmanı (tier) ve yayın grubuyla
    anılır; "yandaş/muhalif" gibi bir sütun eklemek ürün sözleşmesinin
    ihlalidir ve `tests/test_web.py` bunu tarar.
    """
    articles = data["articles"]
    if not articles:
        return "<h2>Kaynaklar</h2><p class='meta'>Bu olaya bağlı makale yok.</p>"

    rows = "".join(
        f"""<tr>
  <td><b>{esc(a["source_name"])}</b> {tier_badge(a["tier"])}
      <div class="meta">{esc(a["independence_group"] or a["source_slug"])}</div></td>
  <td>{esc(a["title"])}
      {'<div class="meta">↳ yakın tekrar — bağımsız sayılmaz</div>'
       if a["near_duplicate_of_id"] else ""}</td>
  <td class="meta">{when(a["published_at"] or a["first_seen_at"])}</td>
  <td>{f'<a href="{esc(a["canonical_url"])}" rel="noopener noreferrer" target="_blank">→ link</a>'
       if a["canonical_url"] else "—"}</td>
</tr>"""
        for a in articles
    )

    groups = int(data["event"]["independence_groups"] or 0)
    note = (
        f"ⓘ Bu olay <b>{groups} farklı yayın grubundan</b> raporlanıyor."
        if groups >= 2
        else "⚠ <b>Bu olay tek bir yayın grubundan raporlanıyor.</b> "
        "Farklı bir kaynaktan teyit aramadan kesin konuşma."
    )

    return f"""<h2>Kaynaklar <span class="meta">(çerçeve farkı)</span></h2>
<p class="meta">Başlıklar yan yana durur; farkı sen değerlendirirsin.
  Sistem hiçbir yayına siyasi konum etiketi vermez (Spec §8.5).</p>
<table>
  <tr><th>Kaynak</th><th>Başlık</th><th>Saat</th><th></th></tr>
  {rows}
</table>
<p class="{"meta" if groups >= 2 else "notice"}" style="margin-top:.6rem">{note}</p>"""


def _timeline(data: dict[str, Any]) -> str:
    """ZAMAN ÇİZELGESİ (F3-06) — 20+ makalede de tek sorgu, tek liste."""
    articles = data["articles"]
    if not articles:
        return ""
    items = "".join(
        f"""<li><span class="meta">{when(a["published_at"] or a["first_seen_at"])}</span>
  · <b>{esc(a["source_name"])}</b> {tier_badge(a["tier"])}
  <div>{esc((a["excerpt"] or a["title"])[:160])}</div></li>"""
        for a in articles
    )
    return f"""<h2>Zaman çizelgesi</h2>
<details {"open" if len(articles) <= 6 else ""}>
  <summary>{len(articles)} adım — genişlet</summary>
  <ul class="timeline">{items}</ul>
</details>"""


def _related(data: dict[str, Any]) -> str:
    """ÖNCEKİ BAĞLAM (F2-17 çıktısı)."""
    related = data["related"]
    if not related:
        return ""
    items = "".join(
        f'<li><a href="/event/{r["id"]}">{esc(r["title"])}</a> '
        f'<span class="meta">· {when(r["first_reported_at"], "%d %b %Y")} '
        f'· benzerlik {float(r["similarity"] or 0):.3f} · {esc(r["relation"])}</span></li>'
        for r in related
    )
    return f"<h2>Önceki bağlam</h2><ul style='margin:0;padding-left:1.1rem'>{items}</ul>"


def _upcoming(data: dict[str, Any]) -> str:
    """SIRADAKİ BEKLENEN (Spec §9.5)."""
    upcoming = data["upcoming"]
    if not upcoming:
        return ""
    items = "".join(
        f'<li>{esc(u["title"])} <span class="meta">— '
        f'{when(u["expected_at"], "%d %b %Y %H:%M")}'
        f'{" · " + esc(u["source_name"]) if u["source_name"] else ""}</span></li>'
        for u in upcoming
    )
    return f"<h2>Sıradaki beklenen</h2><ul style='margin:0;padding-left:1.1rem'>{items}</ul>"


def _editorial_panel(event_id: int) -> str:
    """EDİTORYAL FIRSATLAR + P1 zorlaması (F3-11).

    Buton durumu ile API kararı **aynı fonksiyondan** gelir
    (`service.can_generate`). Ayrışsalardı kullanıcı tıklanabilen ama
    her seferinde 409 dönen bir buton görürdü.
    """
    gate = can_generate(event_id)

    if not gate["allowed"]:
        buttons = "".join(
            f'<button disabled title="Kanıtsız olayda üretim yapılmaz">'
            f"{esc(label)}</button> "
            for label, _ in ANGLES.values()
        )
        return f"""<h2>Editoryal fırsatlar</h2>
<div class="card">
  <div class="row">{buttons}</div>
  <p class="notice bad" style="margin-top:.7rem">{esc(gate["message"])}</p>
  <p class="meta">Bu bir arayüz kısıtı değil: API doğrudan çağrılsa da
     <span class="mono">409</span> döner (Spec §14.1 kalem 15, P1).</p>
</div>"""

    buttons = "".join(
        f'<button class="primary" onclick="pdGenerate(\'{key}\')">{esc(label)}</button> '
        for key, (label, _) in ANGLES.items()
    )
    return f"""<h2>Editoryal fırsatlar</h2>
<div class="card">
  <div class="row">{buttons}
    <span class="meta" style="margin-left:auto">Kanıta bağlı üretim ✓
      ({gate["claim_count"]} iddia, {gate["evidence_count"]} kanıt bağı)</span>
  </div>
  <div id="draft-out" style="margin-top:1rem"></div>
</div>"""


def _feedback_panel(event_id: int, open_count: int) -> str:
    """"Bu yanlış" geri bildirim butonu (F3-21)."""
    note = (
        f'<span class="meta">{open_count} açık işaret var — denetim kuyruğunda.</span>'
        if open_count
        else ""
    )
    return f"""<div class="row" style="margin-top:2rem">
  <button onclick="pdFlag()">⚑ Bu yanlış</button> {note}
  <span class="meta" style="margin-left:auto">
    İşaretlediğinde olay insan denetimi kuyruğuna düşer.</span>
</div>"""


_EVENT_JS = """
function pdEventId(){ return document.body.dataset.eventId; }

async function pdGenerate(angle){
  var out = document.getElementById('draft-out');
  out.innerHTML = '<p class="meta">Üretiliyor… (kanıt setinden, birkaç saniye)</p>';
  try {
    var r = await fetch('/api/events/' + pdEventId() + '/drafts', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({angle: angle})
    });
    var data = await r.json();
    if (r.status === 409) {
      out.innerHTML = '<p class="notice bad">' + (data.detail?.message || data.detail) + '</p>';
      return;
    }
    if (!r.ok) { out.innerHTML = '<p class="notice bad">Üretim hatası.</p>'; return; }
    out.innerHTML = '<p class="meta">Taslak hazır — <a href="/draft/' +
      data.draft_id + '">aç ve kontrol et →</a></p>';
    location.href = '/draft/' + data.draft_id;
  } catch (e) { out.innerHTML = '<p class="notice bad">Ağ hatası.</p>'; }
}

async function pdFlag(){
  var note = prompt('Ne yanlış? (isteğe bağlı)');
  if (note === null) return;
  var r = await fetch('/api/events/' + pdEventId() + '/feedback', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({note: note})
  });
  alert(r.ok ? 'İşaretlendi. Olay denetim kuyruğuna alındı.' : 'Kaydedilemedi.');
  if (r.ok) location.reload();
}

// time-to-understanding: "Anladım" tıklamasına kadar geçen süre (F3-19)
function pdUnderstood(btn){
  window.pdPing('understood', {duration_ms: Date.now() - window.pdOpenedAt});
  btn.disabled = true;
  btn.textContent = '✓ Anlaşıldı olarak işaretlendi';
}
"""


@router.get("/event/{event_id}", response_class=HTMLResponse)
def event_page(event_id: int) -> str:
    user_id = current_user_id()
    data = repository.event_page(event_id, user_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Olay yok: {event_id}")

    event = data["event"]
    review = (
        '<p class="notice">⚠ Bu olayın kümeleme kararı belirsiz ve insan '
        "denetimi bekliyor. İçerik üretmeden önce doğrula.</p>"
        if event.get("review_flag") == "needs_review"
        else ""
    )

    body = f"""
<p class="meta"><a href="/feed">← Feed'e dön</a></p>
{review}
<div class="row">
  {event_badge(event["status"])}
  <span class="meta">Salience {event["displayed_salience"]}
    (global {event["global_salience"]} + kişisel {event["personal_salience"]})</span>
  <button style="margin-left:auto" onclick="pdUnderstood(this)">✓ Anladım</button>
</div>
<h1>{esc(event["title"])}</h1>
<p class="meta">İlk rapor {when(event["first_reported_at"])} ·
  Son güncelleme {when(event["last_update_at"])} ·
  {event["article_count"]} makale ·
  {event["independent_count"]} bağımsız teyit</p>

<h2>TL;DR</h2>
<div class="card">{_tldr(data["claims"])}
  <p class="meta" style="margin:.6rem 0 0">Özet yalnızca teyit edilmiş
    iddialardan kurulur; bir model tarafından yeniden yazılmaz.</p></div>

{_knowledge_columns(data["claims"])}
{_evidence_block(data)}
{_sources_table(data)}
{_timeline(data)}
{_related(data)}
{_upcoming(data)}
{_editorial_panel(event_id)}
{_feedback_panel(event_id, data["open_feedback"])}
"""

    html = page(esc(event["title"])[:70], body, active="/feed",
                extra_js=ACTIVITY_JS + _EVENT_JS)
    # `data-event-id` gövdeye yazılır: izleme ve JS uçları onu okur.
    return html.replace("<body>", f'<body data-event-id="{event_id}">', 1)
