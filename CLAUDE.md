# CLAUDE.md — PolitikDesk

## Frontend kuralları — ATLANAMAZ

UI/frontend içeren HER görevde, kod yazmadan önce `DESIGN.md` dosyasını baştan
sona oku ve `design/refs/README.md` içindeki referans notlarını incele.

- DESIGN.md Bölüm 13 (Anti-slop) ve Bölüm 14 (Görsel doğrulama döngüsü)
  atlanamaz.
- Görev, Bölüm 15'teki Definition of Done listesi doldurulmadan "bitti"
  sayılmaz.
- Her UI görevinin sonunda `design/decisions.md` güncellenir.

### Bu projede uygulama katmanı: Tailwind/React değil, Python + HTML

DESIGN.md **Ek A** geçerlidir: dosyanın tamamı bağlayıcıdır, yalnızca uygulama
katmanı farklıdır. Arayüz `politikdesk/web/ui/` altında sunucu tarafında
üretilir (karar gerekçesi: `docs/karar-itirazlari.md` İtiraz-8).

| DESIGN.md diyor | Bu projede karşılığı |
|---|---|
| `@theme` bloğu / `tailwind.config` | `politikdesk/web/ui/tokens.py` — **tek kaynak** |
| shadcn bileşeni | `politikdesk/web/ui/components.py` — Bölüm 8 spec'leri |
| `lucide-react` | `politikdesk/web/ui/icons.py` — satır içi SVG, tek set |
| `Intl.NumberFormat('tr-TR')` | `politikdesk/web/ui/format.py` |

**Ham hex / ham px yasağı burada da geçerlidir.** `tokens.py` dışında hiçbir
`.py` dosyasında `#rrggbb` bulunmaz; denetimi `tests/test_design_tokens.py`
yapar ve CI adımıdır.

### MCP

`.mcp.json` yalnızca **chrome-devtools** tanımlar — DESIGN.md Bölüm 2.1'in
"zorunlu üçlüsü"nden diğer ikisi bu projede uygulanamaz:

- **shadcn MCP** React/`components.json` ister; bu depoda React yok.
- **21st.dev Magic** React bileşeni üretir; çıktısı doğrudan kullanılamaz.

Bölüm 2.1'in kendi notu geçerli: *"En kritik MCP chrome-devtools. Diğer ikisi
olmasa da olur."* Bileşen kaynağı (Kaldıraç 5) yerine bu projede DESIGN.md
Bölüm 8 spesifikasyonları birebir kodlanmıştır.

## Ürün kısıtları — arayüzü de bağlar

`README.md` "Pazarlık edilemez kısıtlar" tablosu her UI değişikliğinde geçerlidir.
Arayüze doğrudan dokunan dört tanesi:

1. **Kaynağa siyasi konum etiketi verilemez** (Spec §8.5) — `tests/test_web.py`
   üretilen dizeleri tarar. Kaynak yalnızca ad + tier + yayın grubu ile anılır.
2. **Otomatik yayın kod yolu yoktur** (Spec §15/6) — yayın köprüsü yalnızca bir
   Web Intent *adresi* üretir; gönder tuşuna kullanıcı basar.
3. **Salience bir doğruluk skoru değildir** (Spec §15/13) — skorun gösterildiği
   her yerde bu not bulunur.
4. **Editoryal Kimlik Kartı'nda ideolojik soru yoktur** (KVKK m.6, Spec §10.1).

Bunlardan birini gevşeten bir arayüz değişikliği Spec'te sürüm artışı gerektirir.

## Geliştirme

`pd ci` = ruff + mypy + pip-audit + mimari kural + testler. Yeşil olmayan
hiçbir şey birleştirilmez. Windows'ta `pd`, Linux/macOS'ta `make`.
