---
name: accessibility-wcag
description: WCAG 2.2 AA erişilebilirlik — kontrast, klavye gezinme, focus görünürlüğü, ARIA, form etiketleme, renk körlüğü. Her UI değişikliğinden önce ve her PR denetiminde kullan. Anahtar: erişilebilirlik, kontrast, klavye, focus, ARIA, aria-label, aria-live, ekran okuyucu, Lighthouse.
---

# Erişilebilirlik — WCAG 2.2 AA

Bunlar "sonra bakarız" maddeleri değil, ilk yazımda uygulanır. Sonradan
eklenen erişilebilirlik her zaman yamadır ve yama gibi görünür.

## Kontrast

| Ne | Eşik |
|---|---|
| Normal metin | 4.5:1 |
| Büyük metin (≥18.66px/600 veya ≥24px) | 3:1 |
| UI bileşeni kenarlığı, ikon, grafik çizgisi | 3:1 |
| Devre dışı öğe | muaf — ama okunabilir kalsın |

`fg-subtle` en riskli token'dır: etiket ve placeholder onunla yazılır ve
çoğu paletde 4.5:1'i **kıl payı kaçırır**. Hesapla, tahmin etme.

## Klavye

- Her etkileşimli öğe `Tab` ile erişilebilir, sıra görsel sırayla aynı.
- `outline: none` yazdığın **her yerde** alternatif focus stili zorunlu.
  Bu projede tek kural: `outline: 2px solid accent; outline-offset: 2px`.
- Modal/drawer: focus trap + `Esc` ile kapanış + kapanınca focus tetikleyene
  döner.
- `<details>`/`<summary>` klavyeyle açılır — özel açılır panel yazmadan önce
  onu düşün.
- Tıklanabilir `<div>` yasak. `<button>` veya `<a>` kullan; `role="button"` bir
  düzeltme değil, bir itiraftır.

## Anlam yalnızca renkte olamaz

Durum rozetinde **metin her zaman yazılır**. `🟢` tek başına bir durum değildir;
`● güçlü teyitli` bir durumdur. Grafiklerde renk + desen/etiket yedeği bulunur.

Bu proje için özellikle kritik: `evidence_status` beş değerlidir ve renkleri
yeşil/sarı/turuncu/kırmızı/gri'dir. Kırmızı-yeşil renk körlüğünde bu skala
tek başına okunamaz — metin etiketi kaldırılamaz.

## Form

- Her alan `<label for>` ile bağlı.
- Yardım ve hata metni `aria-describedby` ile alana bağlı.
- Hata: `aria-invalid="true"` + hata metni **ne yapılacağını** söyler.
- Zorunlu alan: `required` + etikette `*` + form başında "* zorunlu alan".

## Yapı ve dinamik içerik

- Sayfa `<h1>` ile başlar, başlık seviyeleri atlanmaz.
- `<html lang="tr">`.
- İkon-only butonda `aria-label` **zorunlu**.
- Dinamik değişen bölge (arama sonucu, sessiz yenileme, toast):
  `aria-live="polite"`. Hata için `assertive`.
- Dekoratif SVG: `aria-hidden="true"` + `focusable="false"`.

## Hareket

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    transition-duration: .01ms !important;
    scroll-behavior: auto !important;
  }
}
```
Nabız/pulse gibi sonsuz animasyonlar bu sorguda **durdurulur**, hızlandırılmaz.

## Denetim

chrome-devtools MCP → Lighthouse Accessibility. **Skor ≥ 95 olmadan görev
kapanmaz.** Skor 100 olsa bile şunlar otomatik yakalanmaz, elle bak:

- Tab sırası mantıklı mı?
- Focus halkası her adımda **görünür** mü (koyu temada da)?
- Ekran okuyucu sırası görsel sırayla aynı mı?
- 200% zoom'da yatay kaydırma çıkıyor mu?
