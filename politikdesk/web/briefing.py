"""Uygulama içi brifing sayfası ve açılma takibi (F3-17).

DoD: `/briefing/[date]` çalışıyor; e-posta HTML'inde olay linkleri
çalışıyor; **açılma takibi var (metrik)**.

Açılma takibi 1×1 saydam GIF ile yapılır: e-posta istemcileri JavaScript
çalıştırmaz, dolayısıyla tek ölçüm yolu bir görsel isteğidir. Belirteç
tahmin edilemez (`secrets.token_urlsafe`) ve **ilk açılış kazanır** —
istemcinin her ön-yüklemesi oranı şişirmesin diye.

### Bu sayfanın tek işi (BRIEF `birincil_is`)

> "Ben yokken ne oldu?"

Liste ekranında en yeni brifing **en üstte ve açık** olur; kullanıcının
sabah yapacağı ilk şey odur. Eski brifingler bir arşivdir, bir gezinti
hedefi değil — bu yüzden liste sade bir tablodur, kart ızgarası değil.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from politikdesk.briefing import generator
from politikdesk.web.ui import (
    button,
    card,
    cell,
    empty_state,
    esc,
    page,
    page_head,
    panel,
    relative_time,
    segment,
    table,
)
from politikdesk.web.ui import format as fmt

router = APIRouter(tags=["web"])

# 1x1 saydam GIF — bağımlılıksız, 43 bayt.
_PIXEL = bytes.fromhex(
    "47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b"
)


def _send_state(row: dict) -> str:
    if row.get("sent_at"):
        opened = (
            f" · açıldı {fmt.relative(row['opened_at'])}"
            if row.get("opened_at")
            else " · henüz açılmadı"
        )
        return f"gönderildi {fmt.relative(row['sent_at'])}{opened}"
    if row.get("send_error"):
        return f"gönderilmedi — {str(row['send_error'])[:60]}"
    return "gönderilmedi"


@router.get("/briefing", response_class=HTMLResponse)
def briefing_index() -> str:
    """Üretilmiş brifinglerin listesi."""
    items = generator.list_briefings()

    if not items:
        # Boş durum (10.1): ne olacağını ve nasıl başlanacağını söyler.
        body = page_head(
            "Brifingler",
            lede="Sabah ve akşam brifingleri gündem penceresini deterministik "
            "olarak özetler — brifing üretimi LLM kullanmaz.",
        ) + empty_state(
            "Henüz brifing üretilmedi",
            "Brifingler her sabah ve akşam otomatik üretilir. İlkini hemen "
            "üretmek için terminalde `pd briefing` yaz.",
            action=button("Gündeme dön", href="/feed", variant="primary"),
            icon_name="briefing",
        )
        return page("Brifingler", body, active="/briefing", crumbs=(("Brifingler", None),))

    rows = [
        "<tr>"
        + cell(
            f'<a href="/briefing/{r["briefing_date"]}?slot={r["slot"]}">'
            f"{esc(fmt.full_date(r['briefing_date']))}</a>",
            label="Tarih",
        )
        + cell(
            f'<span class="badge neutral">{esc(generator.SLOT_LABELS[r["slot"]])}</span>',
            label="Slot",
        )
        + cell(esc(fmt.number(r["event_count"] or 0)), label="Olay", cls="num")
        + cell(relative_time(r["generated_at"]), label="Üretim")
        + cell(f'<span class="subtle">{esc(_send_state(r))}</span>', label="Gönderim")
        + "</tr>"
        for r in items
    ]

    body = f"""
{
        page_head(
            "Brifingler",
            lede=f"Sabah {generator.SLOT_WINDOW_HOURS['morning']} saatlik, akşam "
            f"{generator.SLOT_WINDOW_HOURS['evening']} saatlik pencereyi özetler. "
            f"İçerik deterministiktir — brifing üretimi LLM kullanmaz.",
        )
    }
{
        card(
            table(
                (("Tarih", ""), ("Slot", ""), ("Olay", "num"), ("Üretim", ""), ("Gönderim", "")),
                rows,
            ),
            cls="flush",
        )
    }
"""
    return page("Brifingler", body, active="/briefing", crumbs=(("Brifingler", None),))


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
        raise HTTPException(status_code=404, detail=f"{on} {slot} brifingi üretilmemiş.")

    slots = segment(
        tuple(
            (generator.SLOT_LABELS[key], f"/briefing/{on}?slot={key}", key == slot)
            for key in ("morning", "evening")
        )
    )

    # E-posta gövdesi `srcdoc` ile izole edilir: brifing HTML'i kendi
    # stilini taşır ve sayfa stiliyle karışmamalıdır. `sandbox` betik
    # çalıştırmayı kapatır — gövde bir e-posta şablonu, betik içermez.
    body = f"""
{
        page_head(
            generator.SLOT_LABELS[slot],
            lede=esc(fmt.full_date(on_date)),
            actions=button("Listeye dön", href="/briefing", icon_name="arrow-left"),
        )
    }
<div class="row" style="margin:-16px 0 var(--space-6)">
  {slots}
  <span class="spacer subtle" style="font-size:var(--text-xs)">
    Üretildi {esc(fmt.relative(record["generated_at"]))} · {esc(_send_state(record))}
  </span>
</div>
{
        card(
            f'<iframe srcdoc="{esc(record["body_html"])}" sandbox '
            f'style="width:100%;height:72vh;border:0;border-radius:var(--radius-md);'
            f'background:var(--color-surface)" title="Brifing gövdesi" loading="lazy"></iframe>',
            cls="flush",
        )
    }
<div style="margin-top:var(--space-6)">
{
        panel(
            "Düz metin sürümü",
            f'<pre class="mono" style="white-space:pre-wrap;margin:0">'
            f"{esc(record['body_text'])}</pre>",
        )
    }
</div>
"""
    return page(
        f"Brifing {on}",
        body,
        active="/briefing",
        crumbs=(("Brifingler", "/briefing"), (fmt.full_date(on_date), None)),
    )
