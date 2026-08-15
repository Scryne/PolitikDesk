---
name: design-system
description: Tasarım token sistemi kurmak, denetlemek ve tutarlılığı korumak. Renk/spacing/radius/gölge/tipografi token'ları üretirken, WCAG kontrast hesaplarken, koyu tema varyantı türetirken veya "sayfalar birbirine benzemiyor" şikayetini kovalarken kullan. Anahtar: token, palet, kontrast, koyu tema, tutarlılık denetimi, ham hex.
---

# Tasarım sistemi

`DESIGN.md` Bölüm 5–6 bu projenin token sözleşmesidir. Bu skill onu **uygular
ve denetler**; değerleri yeniden tartışmaz.

## Bu projede token'lar nerede

Tek kaynak: `politikdesk/web/ui/tokens.py`. Stylesheet ondan **türetilir**
(`ui/css.py`), elle yazılmaz. Bir renk değiştirmek isteyen `tokens.py`'yi
değiştirir; başka hiçbir yere dokunmaz.

Kural: `tokens.py` **dışında** hiçbir `.py` dosyasında `#rrggbb` yoktur.
Denetim `tests/test_design_tokens.py` içindedir ve CI adımıdır.

```bash
grep -rnE "#[0-9a-fA-F]{6}" politikdesk/ --include="*.py" | grep -v ui/tokens.py
```
Boş dönmüyorsa token sistemi sızdırıyor demektir; düzelt, gerekçe arama.

## Token üretirken sıra

1. **Önce prose.** Paleti 4–6 isimlendirilmiş renkle *anlat* — "koyu mürekkep
   mavisi, kağıt beyazı, arşiv grisi". İsim veremiyorsan palet yoktur, rastgele
   hex vardır.
2. **Sonra kontrast.** Her metin/zemin çifti için oran hesapla. Metin 4.5:1,
   UI/kenarlık 3:1. Tabloyla göster; "sanırım geçer" kabul edilmez.
3. **Sonra koyu tema.** Aynı isimler, ayrı blok. Saf siyah yasak. Koyu temada
   derinliği gölge değil **yüzey açıklığı** verir. Aksan light'takinden ~%10
   daha açık ve daha az doygun olur.
4. **En son grafik paleti.** Sıralı ve renk körü güvenli. Kategori sırası ile
   renk sırası **sabit** kalır — sayfa yenilendiğinde renk değişiyorsa hata var.

## Ölçek disiplini

Kalite = az sayıda karar, tutarlı uygulanmış. Somut tavan:

| Eksen | Tavan |
|---|---|
| Aksan rengi | 1 |
| Yüzey katmanı | 3 |
| Metin seviyesi | 4 |
| Spacing değeri | 7 (4px tabanlı) |
| Radius değeri | 4 + full |
| Gölge seviyesi | 2 (+1 yalnız modal) |
| Aynı ekranda font boyutu | 5 |
| Font ağırlığı | 3 (400/500/600) |

Yeni token eklemek bir **karardır**. `design/decisions.md`'ye gerekçesi
yazılmadan token eklenmez.

## Türkçe glif kontrolü — font seçerken atlanamaz

`İ ı Ğ ğ Ş ş Ç ç Ö ö Ü ü` — eksik olan fontu **önerme**. Eksikse tarayıcı
fallback yapar ve arayüzde iki font karışır; tasarım anında ucuzlar.
Google Fonts'ta "Latin Extended" alt kümesi işaretli olmalı.

## Denetim turu

```
1. Ham hex taraması (yukarıdaki grep)
2. Ham px taraması: spacing için literal px var mı?
3. Aynı ekranda kaç radius değeri var? >1 karakterse ihlal.
4. Aynı ekranda kaç aksan rengi var? >1 ise ihlal.
5. Kontrast: her metin/zemin çifti geçiyor mu?
6. Koyu tema: aynı sayfayı iki temada aç, aynı hiyerarşi okunuyor mu?
```
