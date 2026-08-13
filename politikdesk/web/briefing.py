"""Uygulama içi brifing sayfası ve açılma takibi (F3-17).

DoD: `/briefing/[date]` çalışıyor; e-posta HTML'inde olay linkleri
çalışıyor; **açılma takibi var (metrik)**.

Açılma takibi 1×1 saydam GIF ile yapılır: e-posta istemcileri JavaScript
çalıştırmaz, dolayısıyla tek ölçüm yolu bir görsel isteğidir. Belirteç
tahmin edilemez (`secrets.token_urlsafe`) ve **ilk açılış kazanır** —
istemcinin her ön-yüklemesi oranı şişirmesin diye.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from politikdesk.briefing import generator
from politikdesk.web.layout import esc, page, when

router = APIRouter(tags=["web"])

# 1x1 saydam GIF — bağımlılıksız, 43 bayt.
_PIXEL = bytes.fromhex(
    "47494638396101000100800000000000ffffff21f90401000000002c00000000"
    "010001000002024401003b"
)


@router.get("/briefing", response_class=HTMLResponse)
def briefing_index() -> str:
    """Üretilmiş brifinglerin listesi."""
    items = generator.list_briefings()
    if not items:
        rows = (
            "<tr><td colspan='5' class='meta'>Henüz brifing üretilmedi. "
            "<code>make briefing</code> ile üretebilirsin.</td></tr>"
        )
    else:
        rows = "".join(
            f"""<tr>
  <td><a href="/briefing/{r["briefing_date"]}?slot={r["slot"]}">
      {r["briefing_date"]}</a></td>
  <td>{esc(generator.SLOT_LABELS[r["slot"]])}</td>
  <td>{r["event_count"] or 0}</td>
  <td class="meta">{when(r["generated_at"])}</td>
  <td class="meta">{_send_state(r)}</td>
</tr>"""
            for r in items
        )

    body = f"""
<h1>Brifingler</h1>
<p class="meta">Sabah {generator.SLOT_WINDOW_HOURS["morning"]} saatlik,
  akşam {generator.SLOT_WINDOW_HOURS["evening"]} saatlik pencereyi özetler.
  İçerik deterministiktir — brifing üretimi LLM kullanmaz.</p>
<table>
  <tr><th>Tarih</th><th>Slot</th><th>Olay</th><th>Üretim</th><th>Gönderim</th></tr>
  {rows}
</table>"""
    return page("Brifingler", body, active="/briefing")


def _send_state(row: dict) -> str:
    if row.get("sent_at"):
        opened = f" · açıldı {when(row['opened_at'])}" if row.get("opened_at") else ""
        return f"gönderildi {when(row['sent_at'])}{opened}"
    if row.get("send_error"):
        return f"gönderilmedi — {esc(str(row['send_error'])[:60])}"
    return "gönderilmedi"


@router.get("/briefing/open/{token}.gif")
def briefing_open_pixel(token: str) -> Response:
    """E-postadaki izleme ucu (F3-17 metriği).

    Belirteç geçersiz olsa bile 200 + piksel döner: e-posta istemcisine
    kırık görsel göstermek, ölçümün varlığını kullanıcıya sızdırmaktan
    başka bir işe yaramaz.
    """
    generator.mark_opened(token)
    return Response(
        content=_PIXEL,
        media_type="image/gif",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@router.get("/briefing/{on}", response_class=HTMLResponse)
def briefing_page(on: str, slot: str = "morning") -> str:
    """Uygulama içi brifing — e-posta gövdesinin aynısını gösterir."""
    if slot not in ("morning", "evening"):
        raise HTTPException(status_code=400, detail="slot: morning | evening")
    try:
        on_date = date.fromisoformat(on)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Tarih biçimi: YYYY-AA-GG") from exc

    record = generator.get_briefing(on_date, slot)  # type: ignore[arg-type]
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"{on} {slot} brifingi üretilmemiş."
        )

    other = "evening" if slot == "morning" else "morning"
    body = f"""
<p class="meta"><a href="/briefing">← Brifing listesi</a> ·
  <a href="/briefing/{on}?slot={other}">{esc(generator.SLOT_LABELS[other])}</a></p>
<h1>{esc(generator.SLOT_LABELS[slot])} — {esc(on)}</h1>
<p class="meta">Üretildi {when(record["generated_at"])} · {_send_state(record)}</p>
<iframe srcdoc="{esc(record["body_html"])}" style="width:100%;height:78vh;
  border:1px solid var(--border);border-radius:8px;background:#fff"
  title="Brifing gövdesi"></iframe>
<details style="margin-top:1rem"><summary>Düz metin sürümü</summary>
<pre class="mono" style="white-space:pre-wrap">{esc(record["body_text"])}</pre></details>
"""
    return page(f"Brifing {on}", body, active="/briefing")
