---
description: Bir ekranı denetler, bulguları önem sırasına dizer, onay alıp düzeltir
---

`DESIGN.md` oku. $ARGUMENTS ekranını chrome-devtools MCP ile 1440x900'de aç,
screenshot al. Sunucu `http://localhost:8000` üzerindedir.

DESIGN.md Bölüm 5-8, 10, 12, 13'e göre denetle. Bu projede uygulama katmanı
`politikdesk/web/ui/`'dir (Ek A) — token'lar `ui/tokens.py`, bileşenler
`ui/components.py`, ikonlar `ui/icons.py`, biçimlendirme `ui/format.py`.

Bulguları önem sırasına diz — her biri için:
`[önem: kritik/orta/düşük] · [dosya:satır] · [ihlal] · [önerilen düzeltme]`

ONAY BEKLE. Sonra sadece onayladıklarımı, en kritikten başlayarak düzelt.
Her 3 düzeltmede bir screenshot al ve göster.

Düzeltme sonrası `pd ci` koş — bu depoda arayüz kısıtları testle korunur
(`tests/test_web.py`, `tests/test_design_tokens.py`). Kırmızı bırakma.

Bitince `design/decisions.md`'ye bu turun kritiklerini yaz.
