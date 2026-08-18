"""Arayüz katmanı — DESIGN.md'nin bu depodaki uygulaması (Ek A).

```
tokens.py       renk/spacing/radius/tipografi — TEK KAYNAK, ham hex yalnız burada
css.py          stylesheet, tokens.py'den TÜRETİLİR
icons.py        lucide satır içi SVG — tek set, emoji yok
format.py       Türkçe sayı/tarih/para biçimlendirme (Ek B)
components.py   Bölüm 8 bileşen spesifikasyonları
charts.py       satır içi SVG grafik (kütüphane yok)
shell.py        sidebar + topbar + tema anahtarı; TÜM sayfalar bunu kullanır
```

Sayfa modülleri (`web/feed.py`, `admin/router.py`, …) yalnızca buradan
içe aktarır; kendi stilini, ikonunu veya biçimlendirmesini tanımlamaz.
"""

from politikdesk.web.ui import charts, format
from politikdesk.web.ui.components import (
    button,
    card,
    cell,
    chip,
    distribution,
    empty_state,
    error_state,
    esc,
    event_badge,
    filtered_empty_state,
    kpi,
    notice,
    page_head,
    panel,
    relative_time,
    ruled,
    search_input,
    segment,
    skeleton_rows,
    status_badge,
    table,
    tier_badge,
    timeline,
)
from politikdesk.web.ui.icons import icon, status_icon
from politikdesk.web.ui.shell import ACTIVITY_JS, page

__all__ = [
    "ACTIVITY_JS",
    "button",
    "card",
    "cell",
    "charts",
    "chip",
    "distribution",
    "empty_state",
    "error_state",
    "esc",
    "event_badge",
    "filtered_empty_state",
    "format",
    "icon",
    "kpi",
    "notice",
    "page",
    "page_head",
    "panel",
    "relative_time",
    "ruled",
    "search_input",
    "segment",
    "skeleton_rows",
    "status_badge",
    "status_icon",
    "table",
    "tier_badge",
    "timeline",
]
