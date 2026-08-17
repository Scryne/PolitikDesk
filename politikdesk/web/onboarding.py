"""Editoryal Kimlik Kartı formu (F3-08 · Spec §10.1, §10.2 · Editoryal Profil v2).

DoD: Spec §10.1 sol kolondaki alanlar toplanıyor; **ideolojik soru yok.**

Form 10 sorudur ve sorular `editorial/profile.py::QUESTIONS` içinde tek bir
yerde tanımlıdır. Bu ekran onları **üretir**, kendisi soru tanımlamaz: iki
yerde ayrı liste tutmak, forma eklenen bir sorunun derleyiciye ulaşmaması
demekti.

⛔ Ekranda ideolojik/siyasi bir soru bulunamaz. Kısıt üç katmanda zorlanır
(şema · `QUESTIONS` beyaz listesi · test) ve `tests/test_editorial.py`
üretilen HTML'i de tarar.

### Bu sayfanın tek işi (BRIEF `birincil_is`)

> "Sistem benim nasıl yazdığımı ve editoryal ilkelerimi doğru anlamış mı?"

Bu yüzden **derlenmiş prompt bloğu sağ rayda ve yapışkandır** — kullanıcı
soruyu cevaplarken çıktının nasıl değiştiğini yan yana görür.

### Form genişliği

Bölüm 8.6: tek sütun, max 520px. Geniş ekranda form alanlarını esnetmek
okunabilirliği düşürür — 10 soruluk bir formda kullanıcının gözü satır
başına dönmek zorunda kalır.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from politikdesk.editorial.profile import QUESTIONS, Question
from politikdesk.editorial.profile_compiler import load_profile
from politikdesk.users import current_user_id
from politikdesk.web.ui import (
    button,
    card,
    esc,
    icon,
    notice,
    page,
    page_head,
)

router = APIRouter(tags=["web"])


def _field(question: Question, current: dict[str, Any]) -> str:
    value = current.get(question.field)
    if value is None and question.field == "citation_policy":
        value = current.get("citation_habit")

    if question.kind == "multi":
        selected = set(value or [])
        options = "".join(
            f'<label class="opt"><input type="checkbox" name="{question.field}" '
            f'value="{esc(key)}"{" checked" if key in selected else ""}>'
            f"<span>{esc(label)}</span></label>"
            for key, label in question.choices
        )
    elif question.kind == "single":
        options = "".join(
            f'<label class="opt"><input type="radio" name="{question.field}" '
            f'value="{esc(key)}"{" checked" if value == key else ""}>'
            f"<span>{esc(label)}</span></label>"
            for key, label in question.choices
        )
    elif question.kind == "scale":
        # 1–5 ölçeği: uçları etiketlemeden bir ölçek anlamsızdır.
        options = (
            '<div class="row" style="gap:var(--space-3);align-items:center;'
            'margin-top:var(--space-2)">'
            '<span class="subtle" style="font-size:var(--text-xs)">1 · samimi</span>'
            + "".join(
                f'<label class="opt inline" style="margin:0">'
                f'<input type="radio" name="{question.field}" value="{n}"'
                f"{' checked' if value == n else ''}><span>{n}</span></label>"
                for n in range(1, 6)
            )
            + '<span class="subtle" style="font-size:var(--text-xs)">5 · resmî</span>'
            "</div>"
        )
    else:  # list
        joined = ", ".join(value or []) if isinstance(value, list) else str(value or "")
        options = (
            f'<input type="text" name="{question.field}" value="{esc(joined)}" '
            f'placeholder="virgülle ayırarak yazın">'
        )

    help_text = (
        f'<p class="hint" style="margin:0 0 var(--space-2);line-height:1.45">'
        f"{esc(question.help_text)}</p>"
        if question.help_text
        else ""
    )
    return f"""<fieldset style="max-width:520px">
  <legend>{question.number}. {esc(question.prompt)}</legend>
  {help_text}{options}
</fieldset>"""


@router.get("/onboarding", response_class=HTMLResponse)
@router.get("/onboarding/profile", response_class=HTMLResponse)
def profile_form() -> str:
    current = load_profile(current_user_id()) or {}
    fields = "".join(_field(q, current) for q in QUESTIONS)
    compiled = current.get("compiled_prompt")

    if compiled:
        preview = card(
            f'<pre class="mono" style="white-space:pre-wrap;margin:0;'
            f"font-size:var(--text-xs);line-height:1.6;max-height:calc(100vh - 260px);"
            f'overflow-y:auto;padding-right:var(--space-2)">{esc(compiled)}</pre>'
            f'<p class="subtle" style="margin:var(--space-4) 0 0;'
            f'font-size:var(--text-xs)">Derleyici sürümü '
            f'<span class="mono">{esc(current.get("compiler_version") or "—")}</span> · '
            f"her üretimde YENİDEN analiz edilmez, olduğu gibi kullanılır "
            f"(F3-09).</p>",
            title="Derlenmiş prompt bloğu",
        )
    else:
        # Boş durum (10.1): burada aksiyon formun kendisidir, ayrı buton
        # koymak kullanıcıyı zaten baktığı yere yönlendirmek olurdu.
        preview = card(
            f'<div class="empty" style="padding:var(--space-8) var(--space-4)">'
            f"{icon('identity', 28)}<h3>Henüz derlenmedi</h3>"
            f"<p>Soruları yanıtlayıp <b>Kaydet ve derle</b> dediğinde, "
            f"yanıtların burada kapsamlı bir editoryal sistem promptu bloğuna dönüşecek.</p></div>",
            title="Derlenmiş prompt bloğu",
        )

    body = f"""
{
        page_head(
            "Editoryal Kimlik Kartı",
            lede=(
                "10 soru. Yanıtlar kapsamlı bir editoryal sistem promptu bloğuna derlenir "
                "ve her taslak üretiminde olduğu gibi kullanılır."
            ),
        )
    }
<div class="split">
  <div class="stack">
    {
        notice(
            "<p><b>Burada ideolojik soru yoktur ve olmayacaktır.</b></p>"
            "<p>Siyasi düşünce KVKK m.6 uyarınca özel nitelikli kişisel veridir; "
            "sistemde onu kodlayacak bir alan bulunmaz (Spec §10.1, P6). Toplanan "
            "her şey <b>editoryal ve biçimseldir</b>: ton, cümle yapısı, biçimsellik, "
            "kaynak politikası, alıntı ve belirsizlik yönetimi. Sen ne düşündüğünü değil, "
            "nasıl yazdığını ve bilgiyi nasıl sunduğunu anlatıyorsun.</p>"
        )
    }
    <form id="form" class="stack">
      {fields}
      <div class="row" style="margin-top:var(--space-2)">
        {button("Kaydet ve derle", variant="primary", icon_name="check")}
        <span id="status" class="subtle" aria-live="polite"
              style="font-size:var(--text-xs)"></span>
      </div>
    </form>
  </div>
  <div style="position:sticky;top:calc(var(--topbar-h) + 24px)">{preview}</div>
</div>
"""

    js = """
document.getElementById('form').addEventListener('submit', async function(e){
  e.preventDefault();
  var fd = new FormData(e.target);
  var payload = {
    tone: fd.getAll('tone'),
    sentence_length: fd.get('sentence_length'),
    formality: fd.get('formality') ? parseInt(fd.get('formality'), 10) : null,
    emoji_usage: fd.get('emoji_usage'),
    hashtag_usage: fd.get('hashtag_usage'),
    citation_policy: fd.get('citation_policy') || fd.get('citation_habit'),
    citation_habit: fd.get('citation_policy') || fd.get('citation_habit'),
    topic_priorities: fd.get('topic_priorities') || '',
    avoid_list: fd.get('avoid_list') || '',
    quote_habit: fd.get('quote_habit'),
    uncertainty_handling: fd.get('uncertainty_handling')
  };
  var s = document.getElementById('status');
  var btn = e.target.querySelector('button[type=submit], button.primary');
  // Buton genişliği DEĞİŞMEZ (Bölüm 8.5) — metin yerinde kalır.
  if (btn) btn.disabled = true;
  s.textContent = 'Kaydediliyor…';
  try {
    var r = await fetch('/api/profile', {
      method:'PUT', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    if (r.ok) { s.textContent = 'Kaydedildi.'; location.reload(); return; }
    s.textContent = 'Kaydedilemedi. Zorunlu alanları kontrol edip tekrar dene.';
  } catch (err) {
    s.textContent = 'Sunucuya ulaşılamadı. Bağlantını kontrol et.';
  }
  if (btn) btn.disabled = false;
});
"""
    return page(
        "Editoryal Kimlik",
        body,
        active="/onboarding/profile",
        crumbs=(("Ayarlar", None), ("Editoryal kimlik", None)),
        extra_js=js,
    )
