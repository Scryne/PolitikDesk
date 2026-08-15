---
description: Bir ekranı DESIGN.md Definition of Done listesine göre denetler (düzeltme yapmaz)
---

`DESIGN.md` dosyasını oku ve $ARGUMENTS ile belirtilen sayfayı/bileşeni
Bölüm 15 Definition of Done listesine göre denetle.

Ekran adresleri `politikdesk/api/main.py` router'larından bulunur; sunucu
`http://localhost:8000` üzerindedir (`pd start` ile kalkar).

chrome-devtools MCP ile 375, 768, 1440, 1920 genişliklerinde screenshot al ve
`design/shots/` altına kaydet. Console mesajlarını listele. Lighthouse
Accessibility çalıştır.

Çıktı: DoD listesinin her maddesi için ✅ / ❌ + ❌ olanlar için tek satır
gerekçe ve `dosya:satır` referansı.

Bu projeye özel ek kontroller (CLAUDE.md "Ürün kısıtları"):
- Kaynak tablosunda siyasi konum etiketi var mı? (olmamalı)
- Salience gösterilen her yerde "doğruluk skoru değildir" notu var mı?
- Yayın köprüsünde giden bir POST var mı? (olmamalı)
- `tokens.py` dışında ham hex var mı?
  `grep -rnE "#[0-9a-fA-F]{6}" politikdesk/ --include="*.py"`
- `text-transform: uppercase` var mı? Türkçe'de `i → I` bozar (Ek B.3).

Sonunda "Bu ekranın en zayıf 3 yanı" başlığı altında somut düzeltmeler öner.
DÜZELTME YAPMA, sadece raporla.
