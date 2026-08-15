---
name: micro-interactions
description: Hover, focus, yükleniyor, başarı ve geçiş geri bildirimleri; süre ve easing seçimi. Cilalama fazında, bir etkileşim "cansız" hissettiriyorsa veya animasyon eklerken kullan. Anahtar: hover, focus, transition, animasyon, easing, skeleton, yükleniyor, geri bildirim, mikro etkileşim.
---

# Mikro etkileşimler

## Süre tablosu — ezberle

| Etkileşim | Süre | Easing |
|---|---|---|
| Hover / renk geçişi | 120ms | `ease-out` |
| Buton basma | 80ms | `ease-out` |
| Dropdown / popover | 160ms | `cubic-bezier(.16,1,.3,1)` |
| Modal | 220ms | `cubic-bezier(.16,1,.3,1)` |
| Drawer / sheet | 280ms | `cubic-bezier(.32,.72,0,1)` |
| Toast girişi | 200ms | `cubic-bezier(.16,1,.3,1)` |
| Kapanış (her şey) | giriş × 0.75 | `ease-in` |

**300ms'yi geçen hiçbir UI animasyonu olmaz.** Kapanış her zaman açılıştan
hızlıdır — kullanıcı kapatmaya karar vermiştir, beklemek istemez.

## Neyi animasyon edersin

**Edilir:** `opacity`, `transform` (translate/scale) — GPU'da compositor
katmanında koşar, jank yapmaz.

**Edilmez:** `width`, `height`, `top/left`, `margin`, `box-shadow` — her karede
layout/paint tetikler.

Yükseklik animasyonu gerekiyorsa:
```css
grid-template-rows: 0fr → 1fr;   /* ✅ */
height: auto;                     /* ❌ animasyon edilemez */
```

## Layout zıplaması yasak

En çok gözden kaçan kalite kaybı budur:

- **Buton yükleniyor:** metin yerinde kalır, sol tarafa 14px spinner girer,
  buton **genişliği değişmez**.
- **Checkbox işaretleme:** tik 150ms çizilir, metin 200ms'de soluklaşır, satır
  yerinden oynamaz.
- **Canlı güncellenen sayı:** `tabular-nums` — rakam genişliği sabit olmazsa
  her saniye ekran titrer.
- **Eksen etiketi:** sabit karakter uzunluğu veya `tabular-nums`. Etiket
  genişliği değişince grafik alanı kayar.

## Yükleniyor durumu

- **Skeleton, spinner değil.** Skeleton gerçek içeriğin şeklini taklit eder:
  aynı yükseklik, aynı sütun genişlikleri.
- Animasyon: `shimmer` değil, `opacity 0.6 ↔ 1` 1.5s `ease-in-out`.
  Shimmer 2019 estetiğidir.
- **300ms'den kısa sürecek yüklemelerde hiçbir şey gösterme** — yanıp sönen
  skeleton, hiç skeleton olmamasından kötüdür.

## Hover disiplini

- Nav öğesi hover'ında **yalnızca zemin** değişir; metin renk değiştirmez.
  İkisi birden değişirse öğe zıplıyor gibi görünür.
- Kart hover'ında `scale > 1.02` yasak.
- Tablo satırı hover: zemin `surface-sunken`, 100ms.
- Aksiyon butonları satır hover'ında görünür — ama **yer kaplamaya devam
  ederler** (`visibility`/`opacity`, `display` değil), yoksa sütun genişliği
  oynar.

## Yasaklar

- Sayfa yüklenişinde sıralı beliren elemanlar (staggered fade-in) — panelde
  yasak, yalnızca landing'de ve yalnızca bir kez.
- Sonsuz dönen/parlayan arka plan efektleri.
- Scroll-jacking, otomatik oynayan carousel.

## `prefers-reduced-motion`

Zorunlu. Nabız/pulse gibi sonsuz animasyonlar bu sorguda **durdurulur** —
hızlandırılmaz, çünkü hızlandırılmış nabız daha rahatsız edicidir.
