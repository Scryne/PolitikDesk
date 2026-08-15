---
name: enterprise-dashboard-design
description: Veri yoğun kurumsal panel yerleşimi — sidebar, topbar, grid, tablo, filtre çubuğu, sayfalama. Uygulama iskeleti kurarken, tablo ekranı yazarken veya bir panelin ölçülerine karar verirken kullan. Anahtar: sidebar, topbar, grid, tablo, layout, filtre, sayfalama, responsive, veri yoğun.
---

# Kurumsal panel yerleşimi

Ölçüler `DESIGN.md` Bölüm 7–8'den gelir ve tartışmaya açık değildir. Bu skill
onları **uygularken** en sık yapılan hataları kesiyor.

## İskelet

```
┌────────────┬──────────────────────────────────────┐
│            │  Topbar 56px                         │
│  Sidebar   ├──────────────────────────────────────┤
│  264px     │  İçerik · padding 24px 32px          │
│            │  max-width 1440px                    │
├────────────┤                                      │
│ Kullanıcı  │                                      │
└────────────┴──────────────────────────────────────┘
```

- Sidebar 264px, daraltılmış 64px (yalnız ikon).
- İçerik 1440px'de sabitlenir; **1920px'de ortalanır**, esnetilmez.
- Okunabilir metin bloğu max 68 karakter.

## En sık üç hata

**1. `minmax(0, ...)` unutmak.** Panellerde en sık görülen layout hatası:

```css
grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
```

`1fr` yazarsan içerideki tablo/grafik grid'i patlatır ve yatay kaydırma çıkar.
Nedeni: `1fr` aslında `minmax(auto, 1fr)`'dir ve `auto` içeriğin min-content
genişliğinden küçülemez.

**2. Eşit olmayan kart yükseklikleri.** `items-stretch` kullan. Bir satırdaki
kartların alt kenarı hizalanmıyorsa ekran anında amatör görünür.

**3. Tabloyu mobilde yatay kaydırmaya bırakmak.** Yasak. Ya kart listesine
dönüşür, ya sütunlar öncelik sırasına göre gizlenir.

## Tablo

| Özellik | Kural |
|---|---|
| Satır yüksekliği | 44px (yoğun) / 52px (iki satırlı hücre) |
| Zebra şerit | **Yok.** 1px alt border yeter. |
| Başlık | Sticky, `surface-sunken`, alt border 1px |
| Sayısal sütun | Sağa hizalı + `tabular-nums` |
| Tarih sütunu | Göreli ("3 saat önce") + `title`'da tam tarih |
| Aksiyon sütunu | En sağda, sabit genişlik |
| Sayfalama | Alt sağda; **toplam kayıt sayısı her zaman yazılır** |
| Yükleniyor | 5 skeleton satır, spinner değil |

Tam ızgaralı tablo (`bordered`) ağır durur — dikey çizgi kullanma.

## Kartlar gölge kullanmaz

Panel kartı: 1px border + radius 12px + **gölge yok**. Gölge yalnızca "yüzeyin
üstünde yüzen" şeyler içindir: dropdown, modal, toast, sürüklenen kart.
Her karta gölge = ucuz görünüm, istisnasız.

## Filtre çubuğu

- Çip 32px, radius 8px, 1px border.
- **Aktif filtre görsel olarak ayrışır:** kenarlık `accent`, zemin
  `accent-subtle`, metin `accent`. Bu ayrım yoksa kullanıcı neyi filtrelediğini
  unutur ve boş sonucu hata sanar.
- En az 1 filtre aktifse sağda "Sıfırla" belirir.
- Filtreler URL'de tutulur (`?status=active&page=2`) — yenilenince kaybolmaz,
  link paylaşılabilir.

## Kırılma noktaları

| Ad | px | Davranış |
|---|---|---|
| mobile | <768 | Sidebar → drawer, KPI 1 sütun, tablo → kart |
| tablet | 768–1279 | Sidebar daraltılmış, KPI 2 sütun |
| desktop | 1280–1919 | Tam sidebar, KPI 4 sütun |
| wide | ≥1920 | İçerik 1440'ta sabit + ortalı |
