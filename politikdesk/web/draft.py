"""Taslak ekranı: pre-publish check, düzenleme, yayın köprüsü.

F3-13 (UI), F3-14, F3-15 · Spec §14.4

Ekranın üç bölgesi vardır ve sırası anlamlıdır:

  1. **Yayın öncesi kontrol** — Spec §14.4'ün altı satırı. Engelleyici
     durum varsa onay kutusu görünür.
  2. **Taslak metni** — düzenlenebilir. Kaydedilen her düzenleme
     `edit_distance` üretir (Spec §13.3).
  3. **Yayın köprüsü** — panoya kopyala + X Web Intent.

⛔ **Otomatik yayın kod yolu yoktur** (Spec §15 madde 6, P5, G3 #9).
Bu dosyada X'e giden hiçbir `POST` bulunmaz; üretilen tek şey
kullanıcının yeni sekmede açtığı bir `intent/tweet` ADRESİDİR ve
gönder tuşuna kullanıcı basar.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from politikdesk.editorial import repository as editorial_repo
from politikdesk.editorial.generator import ANGLES
from politikdesk.web.layout import esc, page, when

router = APIRouter(tags=["web"])

_ACTION_LABELS = {
    "accepted": "Kabul edildi",
    "edited": "Düzenlendi",
    "regenerated": "Yeniden üretildi",
    "rejected": "Reddedildi",
}


def _check_panel(check: dict[str, Any] | None) -> str:
    """Spec §14.4'ün ekran karşılığı."""
    if not check:
        return '<p class="meta">Kontrol çıktısı kaydedilmemiş.</p>'

    rows = "".join(
        f"""<div class="claim">
  <div><span class="mono">{esc(item["mark"])}</span> {esc(item["label"])}
    <span class="meta">{esc(item["detail"])}</span></div>
  {"".join(f'<div class="meta" style="padding-left:1.4rem">→ {esc(x)}</div>'
           for x in item["items"])}
</div>"""
        for item in check["items"]
    )

    blocking = ""
    if check.get("is_blocking"):
        blocking = """
<p class="notice bad" style="margin-top:.8rem">
  <b>Engelleyici:</b> kanıta bağlanamayan sayısal iddia var.
  Devam etmek için aşağıdaki kutuyu işaretlemen gerekir — bu, TCK m. 217/A
  riskinin arayüz karşılığıdır (Spec §12.1, §14.4).</p>
<label class="opt" style="margin-top:.4rem">
  <input type="checkbox" id="override"
         onchange="document.getElementById('go').disabled = !this.checked">
  Kanıtla eşleşmeyen sayısal iddiaya rağmen devam etmek istiyorum.
</label>"""

    return f"""<h2>Yayın öncesi kontrol</h2>
<div class="card">{rows}{blocking}</div>"""


def _grounding_panel(grounding: dict[str, Any] | None, is_grounded: bool) -> str:
    """F3-12 sonucunun ekranı — sert kapının (G3 #2) görünen yüzü."""
    grounding = grounding or {}
    checked = (
        f"{grounding.get('numbers_checked', 0)} sayı · "
        f"{grounding.get('dates_checked', 0)} tarih · "
        f"{grounding.get('quotes_checked', 0)} alıntı"
    )
    if is_grounded:
        return (
            f'<p class="notice ok">✓ Grounding temiz — metindeki her sayı, tarih '
            f"ve alıntı kanıt setinde bulundu ({esc(checked)}).</p>"
        )
    issues = "".join(
        f"<li><span class='mono'>{esc(i['token'])}</span> — "
        f"kanıt setinde yok ({esc(i['kind'])})</li>"
        for i in grounding.get("issues", [])
    )
    return f"""<p class="notice bad"><b>Bu taslak kullanılamaz.</b>
  Kanıtta olmayan öğe içeriyor ({esc(checked)} denetlendi):</p>
<ul>{issues}</ul>
<p class="meta">Kayıt silinmedi: kapı G3 koşul 2 bir ORANDIR ve düşen
  taslakları saymazsa anlamını yitirir. Yeniden üret veya elle düzelt.</p>"""


@router.get("/draft/{draft_id}", response_class=HTMLResponse)
def draft_page(draft_id: int) -> str:
    draft = editorial_repo.get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Taslak yok: {draft_id}")

    angle_label = ANGLES.get(draft["angle"], (draft["angle"], ""))[0]
    body_text = draft.get("final_body") or draft["body"]
    is_grounded = bool(draft["is_grounded"])

    action = draft.get("user_action")
    action_note = (
        f'<p class="meta">Aksiyon: <b>{esc(_ACTION_LABELS.get(action, action))}</b>'
        f' · {when(draft.get("action_at"))}'
        + (
            f' · düzenleme mesafesi {float(draft["edit_distance"]):.3f}'
            if draft.get("edit_distance") is not None
            else ""
        )
        + "</p>"
        if action
        else ""
    )

    cited = ", ".join(str(i) for i in (draft["cited_claim_ids"] or [])) or "—"

    body = f"""
<p class="meta"><a href="/event/{draft["event_id"]}">← Olaya dön</a></p>
<h1>{esc(angle_label)} — {esc(draft["event_title"])}</h1>
<p class="meta">Üretildi {when(draft["created_at"])} ·
  model <span class="mono">{esc(draft["model"] or "—")}</span> ·
  prompt <span class="mono">{esc(draft["prompt_version"] or "—")}</span> ·
  atıf yapılan iddialar <span class="mono">{esc(cited)}</span></p>
{action_note}

{_grounding_panel(draft.get("grounding_result"), is_grounded)}
{_check_panel(draft.get("check_result"))}

<h2>Taslak</h2>
<textarea id="body" {"disabled" if not is_grounded else ""}>{esc(body_text)}</textarea>
<p class="meta"><span id="len">{len(body_text)}</span> karakter ·
  düzenlersen mesafe otomatik hesaplanır</p>

<div class="row" style="margin-top:.6rem">
  <button id="go" class="primary" {"disabled" if not is_grounded else ""}
          onclick="pdAct('accepted')">Kabul et</button>
  <button onclick="pdAct('edited')" {"disabled" if not is_grounded else ""}>
    Düzenlemeyi kaydet</button>
  <button onclick="pdAct('regenerated')">Yeniden üret</button>
  <button onclick="pdAct('rejected')">Reddet</button>
</div>

<h2>Yayın köprüsü</h2>
<div class="card">
  <div class="row">
    <button onclick="pdCopy()">📋 Panoya kopyala</button>
    <a class="btn" id="intent" target="_blank" rel="noopener noreferrer"
       href="#">↗ X'te aç (Web Intent)</a>
  </div>
  <p class="meta" style="margin:.7rem 0 0">
    Yeni sekmede X açılır ve metin hazır gelir; <b>gönder tuşuna sen
    basarsın.</b> Ürün otomatik yayın yapmaz ve böyle bir kod yolu
    bulunmaz (Spec §15 madde 6).</p>
</div>
"""

    js = f"""
var DRAFT_ID = {draft_id};

function pdBody(){{ return document.getElementById('body').value; }}

document.getElementById('body').addEventListener('input', function(){{
  document.getElementById('len').textContent = this.value.length;
}});

async function pdRefreshIntent(){{
  var r = await fetch('/api/drafts/' + DRAFT_ID + '/publish');
  if (!r.ok) return;
  var data = await r.json();
  document.getElementById('intent').href = data.web_intent_url;
}}
pdRefreshIntent();

async function pdCopy(){{
  try {{
    await navigator.clipboard.writeText(pdBody());
    alert('Panoya kopyalandı.');
  }} catch (e) {{
    // Güvenli bağlam yoksa Clipboard API çalışmaz; seçim yedeği.
    var t = document.getElementById('body');
    t.select(); document.execCommand('copy');
    alert('Panoya kopyalandı (yedek yöntem).');
  }}
}}

async function pdAct(action){{
  var payload = {{action: action}};
  if (action === 'accepted' || action === 'edited') payload.final_body = pdBody();
  var r = await fetch('/api/drafts/' + DRAFT_ID + '/action', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify(payload)
  }});
  if (!r.ok) {{ alert('Kaydedilemedi: ' + await r.text()); return; }}
  var data = await r.json();
  if (action === 'regenerated') {{
    location.href = '/event/{draft["event_id"]}';
    return;
  }}
  alert('Kaydedildi.' + (data.edit_distance !== null && data.edit_distance !== undefined
        ? ' Düzenleme mesafesi: ' + data.edit_distance : ''));
  location.reload();
}}
"""
    return page(f"{angle_label} taslağı", body, extra_js=js)
