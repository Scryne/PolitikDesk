"""İkon seti — lucide, satır içi SVG (DESIGN.md Bölüm 13.4, 13.5).

**Emoji ikon olarak kullanılmaz.** Eski arayüzde durum rozetleri 🟢🟡🟠🔴⚪
ile çiziliyordu; bunun üç sorunu vardı ve üçü de somut:

  1. Emoji görünümü **işletim sistemine göre değişir** — aynı ekran
     Windows'ta, macOS'ta ve Android'de üç farklı tasarım gösterir.
     Bir tasarım sisteminin kontrol edemediği bir öğe, sistemin dışındadır.
  2. Emoji **renk token'ı almaz**. Koyu temada 🟡 aynı sarıyı basar ve
     yüzeyle kontrastı bozulur.
  3. Ekran okuyucu 🟢'yı "yeşil daire" diye okur — durumu değil, şekli.

Satır içi SVG üçünü de çözer: `currentColor` ile token'a bağlanır, her
platformda aynı görünür, `aria-hidden` ile okuyucudan gizlenip anlamı
metne bırakılır.

Harici ikon paketi (CDN, npm) yok — BRIEF kırmızı çizgisi. Yalnızca
kullanılan ikonlar buraya alınır; kullanılmayan ikon eklemek bu dosyayı
bir kütüphaneye çevirir ve amacını bozar.

Kaynak: lucide.dev · ISC lisansı · 24×24 viewBox, stroke tabanlı.
"""

from __future__ import annotations

from typing import Final

# DESIGN.md 7.2: ikonlar 16px, `stroke-width: 1.75`.
STROKE_WIDTH: Final[str] = "1.75"

# İkon gövdeleri — `<svg>` sarmalayıcısı `icon()` tarafından eklenir.
_PATHS: Final[dict[str, str]] = {
    # ── Navigasyon ──
    "feed": (
        '<rect width="7" height="7" x="3" y="3" rx="1"/>'
        '<rect width="7" height="7" x="14" y="3" rx="1"/>'
        '<rect width="7" height="7" x="14" y="14" rx="1"/>'
        '<rect width="7" height="7" x="3" y="14" rx="1"/>'
    ),
    "briefing": (
        '<path d="M15 18h-5"/><path d="M18 14h-8"/>'
        '<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0'
        ' 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/>'
        '<rect width="8" height="4" x="10" y="6" rx="1"/>'
    ),
    "identity": (
        '<rect width="18" height="18" x="3" y="3" rx="2"/>'
        '<circle cx="12" cy="10" r="3"/>'
        '<path d="M7 21v-1a5 5 0 0 1 10 0v1"/>'
    ),
    "metrics": ('<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="m7 14 3-4 3 3 4-6"/>'),
    "pipeline": (
        '<ellipse cx="12" cy="5" rx="9" ry="3"/>'
        '<path d="M3 5v14a9 3 0 0 0 18 0V5"/>'
        '<path d="M3 12a9 3 0 0 0 18 0"/>'
    ),
    "review": (
        '<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/>'
        '<path d="M6 21V9a9 9 0 0 0 9 9"/>'
    ),
    "calendar": (
        '<rect width="18" height="18" x="3" y="4" rx="2"/>'
        '<path d="M8 2v4"/><path d="M16 2v4"/><path d="M3 10h18"/>'
    ),
    "promise": (
        '<path d="m9 11 3 3L22 4"/>'
        '<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>'
    ),
    "accountability": (
        '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>'
        '<path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>'
        '<path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>'
    ),
    "archive": (
        '<rect width="20" height="5" x="2" y="3" rx="1"/>'
        '<path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/>'
        '<path d="M10 12h4"/>'
    ),
    # ── Kanıt durumu (Bölüm 8.4 / Spec v3.4 §8.1) ──
    # Durumların AYRI SİLUETLERİ var. Renk körlüğünde tek ayırt edici
    # budur ve bu yüzden şekiller bilerek birbirine benzemiyor.
    "status-strong": '<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    "status-partial": '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z"/>',
    "status-single": '<circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><path d="M12 16.5h.01"/>',
    "status-contra": '<circle cx="12" cy="12" r="9"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "status-unverified": '<circle cx="12" cy="12" r="9" stroke-dasharray="3 3"/>',
    "status-accent": '<circle cx="12" cy="12" r="9"/><path d="M9 10h6"/><path d="M9 14h4"/>',
    # ── Eylem ──
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "close": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "copy": (
        '<rect width="14" height="14" x="8" y="8" rx="2"/>'
        '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>'
    ),
    "download": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="7 10 12 15 17 10"/>'
        '<line x1="12" x2="12" y1="15" y2="3"/>'
    ),
    "external": (
        '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>'
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
    ),
    "flag": (
        '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/>'
    ),
    "refresh": (
        '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>'
        '<path d="M21 3v5h-5"/>'
        '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>'
        '<path d="M8 16H3v5"/>'
    ),
    "edit": ('<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>'),
    "link": (
        '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
        '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'
    ),
    # ── Yön ──
    "arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "trend-up": '<path d="M16 7h6v6"/><path d="m22 7-8.5 8.5-5-5L2 17"/>',
    "trend-down": '<path d="M16 17h6v-6"/><path d="m22 17-8.5-8.5-5 5L2 7"/>',
    "trend-flat": '<path d="M3 12h18"/><path d="m16 7 5 5-5 5"/>',
    # ── Bilgi ──
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-5"/><path d="M12 8h.01"/>',
    "warning": (
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0'
        ' 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>'
    ),
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "shield": (
        '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4'
        " 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51"
        ' 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>'
    ),
    "inbox": (
        '<path d="M22 12h-6l-2 3h-4l-2-3H2"/>'
        '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2'
        ' 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>'
    ),
    "filter-off": (
        '<path d="M8 3H2l7.6 9.5"/><path d="M14 10.5V21l-4-3v-4"/>'
        '<path d="m2 2 20 20"/><path d="M22 3H10l3 3.5"/>'
    ),
    "filter": '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "printer": (
        '<polyline points="6 9 6 2 18 2 18 9"/>'
        '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>'
        '<rect width="12" height="8" x="6" y="14"/>'
    ),
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "share": '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    "zap": (
        '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1'
        ' 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1'
        ' 1 0 0 0 11 14z"/>'
    ),
    "list": (
        '<line x1="8" x2="21" y1="6" y2="6"/><line x1="8" x2="21" y1="12" y2="12"/>'
        '<line x1="8" x2="21" y1="18" y2="18"/><line x1="3" x2="3.01" y1="6" y2="6"/>'
        '<line x1="3" x2="3.01" y1="12" y2="12"/><line x1="3" x2="3.01" y1="18" y2="18"/>'
    ),
    "grid": (
        '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/>'
        '<rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>'
    ),
    # ── Kabuk ──
    "sun": (
        '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/>'
        '<path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/>'
        '<path d="M2 12h2"/><path d="M20 12h2"/>'
        '<path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>'
    ),
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "system": (
        '<rect width="20" height="14" x="2" y="3" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>'
    ),
    "menu": '<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>',
}


def icon(name: str, size: int = 16, *, label: str | None = None) -> str:
    """Satır içi SVG üretir.

    `label` verilirse ikon **anlam taşır** ve ekran okuyucuya açılır;
    verilmezse dekoratiftir ve gizlenir. Üçüncü bir seçenek yoktur:
    etiketsiz ve gizlenmemiş bir ikon, okuyucuda "graphic" diye okunur.

    ⚠️ İkon-only bir butonda `label` vermek **zorunludur** (Bölüm 12).
    """
    body = _PATHS.get(name)
    if body is None:
        raise KeyError(
            f"Bilinmeyen ikon: {name!r}. Tek set kuralı (Bölüm 13.5) gereği "
            f"yeni ikon ancak icons.py'ye eklenerek kullanılır."
        )
    a11y = f'role="img" aria-label="{label}"' if label else 'aria-hidden="true" focusable="false"'
    return (
        f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="{STROKE_WIDTH}" '
        f'stroke-linecap="round" stroke-linejoin="round" {a11y}>{body}</svg>'
    )


def status_icon(status: str, size: int = 14) -> str:
    """Kanıt durumunun ikonu. Bilinmeyen durum `unverified` siluetine düşer.

    Eşleme `tokens.STATUS_TOKEN`'dan gelir — ikon ile renk aynı tablodan
    türer, ayrışamazlar.
    """
    from politikdesk.web.ui.tokens import STATUS_TOKEN

    return icon(f"status-{STATUS_TOKEN.get(status, 'unverified')}", size)


def names() -> tuple[str, ...]:
    """Kayıtlı ikon adları — `tests/test_design_tokens.py` ölü ikon arar."""
    return tuple(sorted(_PATHS))
