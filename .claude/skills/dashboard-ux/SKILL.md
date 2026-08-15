---
name: dashboard-ux
description: Panel ve izleme ekranlarında bilgi hiyerarşisi, drill-down, eşik ve uyarı mantığı. Bir ekranın "5 saniyede hangi soruyu cevapladığını" belirlerken, neyi büyük neyi küçük yapacağına karar verirken, KPI seçerken kullan. Anahtar: bilgi hiyerarşisi, KPI, drill-down, eşik, uyarı, panel, gündem sıralaması.
---

# Panel UX — bilgi hiyerarşisi

## Tek soru kuralı

Her ekranın **bir** işi vardır: kullanıcı 5 saniyede tek bir soruya cevap
bulmalı. O soruya cevap veren öğe ekranın sol-üst çeyreğinde ve en büyük
tipografiye sahip olur. Geri kalan her şey ikinci seviyedir.

Bir ekran iki soruya birden cevap veriyorsa iki ekran olmalıdır.

PolitikDesk'te sayfa başına birincil soru `DESIGN.md` Bölüm 4 BRIEF'te
yazılıdır. Yeni ekran açarken oraya bir satır eklenir — yoksa ekran jenerik
çıkar, istisnası yok.

## Hiyerarşiyi boşlukla anlat, çizgiyle değil

`space-y-4` ile her şeye aynı boşluk vermek hiyerarşiyi yok eder. Kural:

```
aynı gruptaki öğeler     8–12px
grup içi bölümler        16–24px
bölümler arası           32px
sayfa bölgeleri arası    48px
```

Ayırıcı çizgi, boşluğun yetmediği yerde gelir — boşluğun yerine değil.

## KPI seçimi

- **Maks 4.** 5. karttan sonra kullanıcı hiçbirini okumaz.
- Bir metrik ancak **bir karara** yol açıyorsa KPI'dır. "Toplam kayıt sayısı"
  bir karara yol açmaz; "24 saatte teyitsiz kalan iddia" açar.
- Delta bağlamsız yazılmaz: `↑ %12,4` değil, `↑ %12,4 geçen haftaya göre`.
- Delta rengi **iyi/kötü**yü anlatır, artış/azalışı değil. "Hata sayısı arttı"
  kırmızıdır. Bunu bileşene `sentiment` prop'u olarak geçir, yönden türetme.

## Eşik ve uyarı

- Eşikler **koda gömülmez**, yapılandırmadan gelir. Bu depoda eşikler
  `config/` altında ve `pipeline_health.py` içindedir.
- Uyarı sayısı azdır. Sidebar'da aynı anda 3'ten fazla dikkat rozeti varsa
  hiçbiri acil değildir.
- Bir uyarı **ne yapılacağını** söyler. "Kümeleme 13 saattir durdu" bir uyarı
  değil, bir gözlemdir. "Kümeleme 13 saattir durdu — `pd cluster` ile elle
  çalıştır" bir uyarıdır.

## Drill-down

Her toplu sayının altında **detayı** olmalı ve tıklanabilmeli:

```
salience 84  →  bileşen kırılımı  →  hangi kaynak, hangi kural
15 makale    →  makale listesi    →  tek makale + kaynağa link
```

Kırılımı gösteremiyorsan sayıyı gösterme. Açıklanamayan sayı güven kaybettirir;
bu üründe özellikle, çünkü ürünün tamamı "kararın nedenini göster" üzerine
kuruludur.

## Yoğunluk modu tüm sayfalarda aynı kalır

| Mod | Kart padding | Satır yük. | Metin |
|---|---|---|---|
| Ferah | 24px | 52px | 14px |
| Dengeli | 20px | 48px | 14px |
| Yoğun | 16px | 44px | 13px |

BRIEF'teki `yogunluk` alanı bunu belirler. Sayfa başına değiştirmek
tutarsızlık üretir — bir ekran "sıkışık", diğeri "boş" hissettirir.

## Kaçınılacaklar

- Dekoratif KPI: gösterilen ama hiçbir karara bağlanmayan sayı.
- Sayfa açılışında sıralı beliren elemanlar (staggered fade-in). Kullanıcı bu
  ekranı günde 40 kez açıyor; 3. seferde sinir bozucu olur.
- Aynı veriyi iki farklı görselleştirmeyle iki kez göstermek.
- "Son 7 gün" varsayılanının hiçbir yerde yazmaması.
