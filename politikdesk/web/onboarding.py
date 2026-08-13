"""Editoryal Kimlik Kartı formu (F3-08 · Spec §10.1, §10.2).

DoD: Spec §10.1 sol kolondaki alanlar toplanıyor; **ideolojik soru yok.**

Form 7 sorudur ve sorular `editorial/profile.py::QUESTIONS` içinde tek
bir yerde tanımlıdır. Bu ekran onları **üretir**, kendisi soru
tanımlamaz: iki yerde ayrı liste tutmak, forma eklenen bir sorunun
derleyiciye ulaşmaması demekti.

⛔ Ekranda ideolojik/siyasi bir soru bulunamaz. Kısıt üç katmanda
zorlanır (şema · `QUESTIONS` beyaz listesi · test) ve
`tests/test_editorial.py` üretilen HTML'i de tarar.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from politikdesk.editorial.profile import QUESTIONS, Question
from politikdesk.editorial.profile_compiler import load_profile
from politikdesk.users import current_user_id
from politikdesk.web.layout import esc, page

router = APIRouter(tags=["web"])


def _field(question: Question, current: dict[str, Any]) -> str:
    value = current.get(question.field)

    if question.kind == "multi":
        selected = set(value or [])
        options = "".join(
            f'<label class="opt"><input type="checkbox" name="{question.field}" '
            f'value="{esc(key)}" {"checked" if key in selected else ""}> '
            f"{esc(label)}</label>"
            for key, label in question.choices
        )
    elif question.kind == "single":
        options = "".join(
            f'<label class="opt"><input type="radio" name="{question.field}" '
            f'value="{esc(key)}" {"checked" if value == key else ""}> '
            f"{esc(label)}</label>"
            for key, label in question.choices
        )
    elif question.kind == "scale":
        options = "".join(
            f'<label class="opt" style="display:inline-block;margin-right:1rem">'
            f'<input type="radio" name="{question.field}" value="{n}" '
            f'{"checked" if value == n else ""}> {n}</label>'
            for n in range(1, 6)
        )
    else:  # list
        joined = ", ".join(value or []) if isinstance(value, list) else esc(value or "")
        options = (
            f'<input type="text" name="{question.field}" style="width:100%" '
            f'value="{esc(joined)}" placeholder="virgülle ayır">'
        )

    help_text = (
        f'<p class="meta" style="margin:.2rem 0 .5rem">{esc(question.help_text)}</p>'
        if question.help_text
        else ""
    )
    return f"""<fieldset>
  <legend>{question.number}. {esc(question.prompt)}</legend>
  {help_text}{options}
</fieldset>"""


@router.get("/onboarding/profile", response_class=HTMLResponse)
def profile_form() -> str:
    current = load_profile(current_user_id()) or {}
    fields = "".join(_field(q, current) for q in QUESTIONS)

    compiled = current.get("compiled_prompt")
    preview = (
        f"""<h2>Derlenmiş sistem promptu bloğu</h2>
<div class="card"><pre class="mono" style="white-space:pre-wrap;margin:0">{esc(compiled)}</pre>
  <p class="meta" style="margin:.7rem 0 0">Derleyici sürümü:
    <span class="mono">{esc(current.get("compiler_version") or "—")}</span> ·
    her üretimde YENİDEN analiz edilmez, olduğu gibi kullanılır (F3-09).</p></div>"""
        if compiled
        else ""
    )

    body = f"""
<h1>Editoryal Kimlik Kartı</h1>
<p class="meta">7 soru. Yanıtlar bir sistem promptu bloğuna derlenir ve her
  taslak üretiminde olduğu gibi kullanılır.</p>

<div class="notice">
  <b>Burada ideolojik soru yoktur ve olmayacaktır.</b>
  Siyasi düşünce KVKK m.6 uyarınca özel nitelikli kişisel veridir; sistemde
  onu kodlayacak bir alan bulunmaz (Spec §10.1, P6). Toplanan her şey
  <b>biçimseldir</b>: ton, cümle uzunluğu, noktalama alışkanlığı, kaynak
  gösterme biçimi. Sen ne düşündüğünü değil, nasıl yazdığını anlatıyorsun.
</div>

<form id="form" style="margin-top:1.2rem">{fields}
  <button class="primary" type="submit">Kaydet ve derle</button>
  <span id="status" class="meta" style="margin-left:.8rem"></span>
</form>
{preview}
"""

    js = """
document.getElementById('form').addEventListener('submit', async function(e){
  e.preventDefault();
  var fd = new FormData(e.target);
  var payload = {
    tone: fd.getAll('tone'),
    sentence_length: fd.get('sentence_length'),
    emoji_usage: fd.get('emoji_usage'),
    // 3. soru tek sorudur; emoji cevabı hashtag alışkanlığını da belirler.
    hashtag_usage: fd.get('emoji_usage'),
    citation_habit: fd.get('citation_habit'),
    formality: fd.get('formality') ? parseInt(fd.get('formality'), 10) : null,
    topic_priorities: fd.get('topic_priorities') || '',
    avoid_list: fd.get('avoid_list') || ''
  };
  var s = document.getElementById('status');
  s.textContent = 'Kaydediliyor…';
  var r = await fetch('/api/profile', {
    method:'PUT', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  if (r.ok) { s.textContent = 'Kaydedildi.'; location.reload(); }
  else { s.textContent = 'Hata: ' + (await r.text()); }
});
"""
    return page("Editoryal Kimlik", body, active="/onboarding/profile", extra_js=js)
