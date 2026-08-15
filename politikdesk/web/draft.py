"""Taslak ekranı: pre-publish check, düzenleme, yayın köprüsü.

F3-13 (UI), F3-14, F3-15 · Spec §14.4

### Bu sayfanın tek işi (BRIEF `birincil_is`)

> "Bu metni yayımlamama engel olan bir şey var mı?"

Bu yüzden **kapı önce gelir, metin sonra.** Alışılmış sıra tersidir (önce
taslak, altta uyarılar) ve o sıra kullanıcıyı metni okumaya, sonra
engellemeyi keşfetmeye zorlar. Burada ekranın ilk ekranında cevap var:
grounding temiz mi, yayın öncesi kontrolde engelleyici var mı.

Üç bölge ve sırası anlamlıdır:

  1. **Kapı** — grounding (F3-12) + Spec §14.4'ün altı kontrolü.
     Engelleyici durum varsa onay kutusu görünür.
  2. **Taslak metni** — düzenlenebilir. Kaydedilen her düzenleme
     `edit_distance` üretir (Spec §13.3).
  3. **Yayın köprüsü** — panoya kopyala + X Web Intent.

⛔ **Otomatik yayın kod yolu yoktur** (Spec §15 madde 6, P5, G3 #9). Bu
dosyada X'e giden hiçbir `POST` bulunmaz; üretilen tek şey kullanıcının
yeni sekmede açtığı bir `intent/tweet` ADRESİDİR ve gönder tuşuna
kullanıcı basar.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from politikdesk.editorial import repository as editorial_repo
from politikdesk.editorial.checker import SEVERITY_MARK
from politikdesk.editorial.generator import ANGLES
from politikdesk.web.ui import (
    button,
    card,
    esc,
    icon,
    notice,
    page,
    page_head,
    ruled,
)
from politikdesk.web.ui import format as fmt

router = APIRouter(tags=["web"])

_ACTION_LABELS = {
    "accepted": "Kabul edildi",
    "edited": "Düzenlendi",
    "regenerated": "Yeniden üretildi",
    "rejected": "Reddedildi",
}

# Spec §14.4 kontrol satırlarının şiddetini kanıt token'ına eşler; böylece
# kontrol listesi de kanıt cetveliyle aynı görsel dili konuşur.
#
# İşaretler `checker.SEVERITY_MARK`'tan OKUNUR, buraya kopyalanmaz: checker
# işaretini değiştirirse burası sessizce eşleşmeyi kaybeder ve her satır
# nötr cetvelle çizilirdi — görünür bir hata değil, sinsi bir renk kaybı.
_MARK_TONE = {
    SEVERITY_MARK["ok"]: "strongly_corroborated",
    SEVERITY_MARK["warn"]: "single_source",
    SEVERITY_MARK["error"]: "contradicted",
    SEVERITY_MARK["info"]: "unverified",
}


def _gate_summary(draft: dict[str, Any]) -> str:
    """Ekranın ilk cevabı: yayımlanabilir mi?

    Tek satırda ve en üstte; detay aşağıdaki iki panelde. Kullanıcı bu
    satırı okuyup sayfayı kapatabilmeli.
    """
    grounded = bool(draft["is_grounded"])
    check = draft.get("check_result") or {}
    blocking = bool(check.get("is_blocking"))

    if not grounded:
        return notice(
            "<p><b>Bu taslak kullanılamaz.</b> Metinde kanıt setinde "
            "bulunmayan bir sayı, tarih veya alıntı var. Yeniden üret veya "
            "elle düzelt.</p>",
            tone="bad",
        )
    if blocking:
        return notice(
            "<p><b>Yayın engelleyici var.</b> Kanıta bağlanamayan sayısal "
            "iddia bulunuyor; devam etmek için aşağıdaki kutuyu işaretlemen "
            "gerekiyor.</p>",
            tone="warn",
        )
    return notice(
        "<p><b>Yayımlanabilir.</b> Grounding temiz ve yayın öncesi "
        "kontrolde engelleyici bulunmadı.</p>",
        tone="ok",
    )


def _grounding_panel(grounding: dict[str, Any] | None, is_grounded: bool) -> str:
    """F3-12 sonucunun ekranı — sert kapının (G3 #2) görünen yüzü."""
    grounding = grounding or {}
    checked = (
        f"{fmt.plural_count(grounding.get('numbers_checked', 0), 'sayı')} · "
        f"{fmt.plural_count(grounding.get('dates_checked', 0), 'tarih')} · "
        f"{fmt.plural_count(grounding.get('quotes_checked', 0), 'alıntı')}"
    )
    if is_grounded:
        return card(
            f'<p style="margin:0">{icon("check", 14)} Metindeki her sayı, tarih '
            f"ve alıntı kanıt setinde bulundu.</p>"
            f'<p class="subtle" style="margin:8px 0 0;font-size:var(--text-xs)">'
            f"Denetlenen: {esc(checked)}</p>",
            title="Grounding",
        )

    issues = "".join(
        ruled(
            "contradicted",
            f'<div class="mono">{esc(i["token"])}</div>'
            f'<div class="subtle" style="font-size:var(--text-xs)">'
            f'kanıt setinde yok · {esc(i["kind"])}</div>',
        )
        for i in grounding.get("issues", [])
    )
    return card(
        f'<p style="margin:0 0 var(--space-4)">Kanıtta olmayan öğeler '
        f"({esc(checked)} denetlendi):</p>"
        f'<div class="stack-sm">{issues}</div>'
        f'<p class="subtle" style="margin:var(--space-4) 0 0;'
        f'font-size:var(--text-xs)">Kayıt silinmedi: kapı G3 koşul 2 bir '
        f"ORANDIR ve düşen taslakları saymazsa anlamını yitirir.</p>",
        title="Grounding — düştü",
    )


def _check_panel(check: dict[str, Any] | None) -> str:
    """Spec §14.4'ün ekran karşılığı."""
    if not check:
        return card(
            '<p class="subtle" style="margin:0">Kontrol çıktısı kaydedilmemiş.</p>',
            title="Yayın öncesi kontrol",
        )

    rows = "".join(
        ruled(
            _MARK_TONE.get(item["mark"], "unverified"),
            f'<div style="font-size:var(--text-sm)"><b>{esc(item["label"])}</b> '
            f'<span class="subtle">{esc(item["detail"])}</span></div>'
            + "".join(
                f'<div class="subtle" style="font-size:var(--text-xs);'
                f'margin-top:2px">{esc(x)}</div>'
                for x in item["items"]
            ),
        )
        for item in check["items"]
    )

    blocking = ""
    if check.get("is_blocking"):
        blocking = f"""
<div style="margin-top:var(--space-4)">
{notice(
    "<p><b>Engelleyici:</b> kanıta bağlanamayan sayısal iddia var. Devam "
    "etmek için aşağıdaki kutuyu işaretlemen gerekir — bu, TCK m. 217/A "
    "riskinin arayüz karşılığıdır (Spec §12.1, §14.4).</p>",
    tone="bad",
)}
</div>
<label class="opt" style="margin-top:var(--space-3)">
  <input type="checkbox" id="override"
         onchange="document.getElementById('go').disabled = !this.checked">
  <span>Kanıtla eşleşmeyen sayısal iddiaya rağmen devam etmek istiyorum.</span>
</label>"""

    return card(
        f'<div class="stack-sm">{rows}</div>{blocking}',
        title="Yayın öncesi kontrol",
        actions=f'<span class="subtle" style="font-size:var(--text-xs)">'
                f'{fmt.plural_count(len(check["items"]), "kontrol")}</span>',
    )


@router.get("/draft/{draft_id}", response_class=HTMLResponse)
def draft_page(draft_id: int) -> str:
    draft = editorial_repo.get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Taslak yok: {draft_id}")

    angle_label = ANGLES.get(draft["angle"], (draft["angle"], ""))[0]
    body_text = draft.get("final_body") or draft["body"]
    is_grounded = bool(draft["is_grounded"])

    action = draft.get("user_action")
    action_note = ""
    if action:
        distance = (
            f' · düzenleme mesafesi <span class="num">'
            f'{fmt.number(float(draft["edit_distance"]), 3)}</span>'
            if draft.get("edit_distance") is not None
            else ""
        )
        action_note = (
            f'<span class="badge accent">{esc(_ACTION_LABELS.get(action, action))}'
            f"</span>"
            f'<span class="subtle">{esc(fmt.relative(draft.get("action_at")))}'
            f"{distance}</span>"
        )

    cited = ", ".join(str(i) for i in (draft["cited_claim_ids"] or [])) or "—"
    disabled_note = (
        ' title="Grounding düştüğü için metin düzenlemeye kapalı"'
        if not is_grounded
        else ""
    )

    body = f"""
{page_head(
    f"{angle_label} taslağı",
    lede=esc(draft["event_title"]),
    actions=button("Olaya dön", href=f"/event/{draft['event_id']}",
                   icon_name="arrow-left"),
)}
<div class="row subtle" style="font-size:var(--text-xs);
     margin:-16px 0 var(--space-6)">
  {action_note}
  <span>Üretildi {esc(fmt.date_time(draft["created_at"]))}</span>
  <span>· model <span class="mono">{esc(draft["model"] or "—")}</span></span>
  <span>· prompt <span class="mono">{esc(draft["prompt_version"] or "—")}</span></span>
  <span>· atıf yapılan iddialar <span class="mono">{esc(cited)}</span></span>
</div>

<div class="stack">
  {_gate_summary(draft)}

  <div class="halves">
    {_grounding_panel(draft.get("grounding_result"), is_grounded)}
    {_check_panel(draft.get("check_result"))}
  </div>

  {card(
    f'<textarea id="body"{"" if is_grounded else " disabled"}{disabled_note}'
    f' aria-label="Taslak metni">{esc(body_text)}</textarea>'
    f'<div class="row" style="margin-top:12px">'
    f'<span class="subtle" style="font-size:var(--text-xs)">'
    f'<span id="len" class="num">{len(body_text)}</span> karakter · '
    f'düzenlersen mesafe otomatik hesaplanır</span></div>'
    f'<div class="btn-row" style="margin-top:var(--space-4)">'
    + button("Kabul et", variant="primary", icon_name="check",
             onclick="pdAct('accepted')", disabled=not is_grounded, id_="go")
    + button("Düzenlemeyi kaydet", onclick="pdAct('edited')",
             disabled=not is_grounded)
    + button("Yeniden üret", icon_name="refresh", onclick="pdAct('regenerated')")
    + button("Reddet", onclick="pdAct('rejected')")
    + '</div>',
    title="Taslak",
  )}

  {card(
    '<div class="btn-row">'
    + button("Panoya kopyala", icon_name="copy", onclick="pdCopy()")
    + button("X'te aç", href="#", icon_name="external", id_="intent")
    + '</div>'
    '<p class="subtle" style="margin:12px 0 0;font-size:var(--text-xs)">'
    'Yeni sekmede X açılır ve metin hazır gelir; <b>gönder tuşuna sen '
    'basarsın.</b> Ürün otomatik yayın yapmaz ve böyle bir kod yolu '
    'bulunmaz (Spec §15 madde 6).</p>',
    title="Yayın köprüsü",
  )}
</div>
"""

    js = f"""
var DRAFT_ID = {draft_id};
var EVENT_ID = {draft["event_id"]};

function pdBody(){{ return document.getElementById('body').value; }}

document.getElementById('body').addEventListener('input', function(){{
  document.getElementById('len').textContent = this.value.length;
}});

async function pdRefreshIntent(){{
  var link = document.getElementById('intent');
  try {{
    var r = await fetch('/api/drafts/' + DRAFT_ID + '/publish');
    if (!r.ok) throw new Error(r.status);
    link.href = (await r.json()).web_intent_url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
  }} catch (e) {{
    // Adres kurulamadıysa BOZUK BİR LİNK BIRAKMA: butonu kapat ve nedenini
    // söyle. Tıklanabilen ama hiçbir şey yapmayan bir buton daha kötüdür.
    link.removeAttribute('href');
    link.setAttribute('aria-disabled', 'true');
    link.title = 'Yayın adresi alınamadı — sayfayı yenile';
  }}
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
  if (!r.ok) {{
    alert('Kaydedilemedi. Bağlantını kontrol edip tekrar dene.');
    return;
  }}
  var data = await r.json();
  if (action === 'regenerated') {{ location.href = '/event/' + EVENT_ID; return; }}
  alert('Kaydedildi.' + (data.edit_distance !== null && data.edit_distance !== undefined
        ? ' Düzenleme mesafesi: ' + data.edit_distance : ''));
  location.reload();
}}
"""
    return page(
        f"{angle_label} taslağı",
        body,
        active="/feed",
        crumbs=(
            ("Gündem", "/feed"),
            (draft["event_title"][:40], f"/event/{draft['event_id']}"),
            (angle_label, None),
        ),
        extra_js=js,
    )
