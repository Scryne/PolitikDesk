# Referans notları

> `DESIGN.md` Bölüm 4 ve `docs/DESIGN-BASLANGIC.md` Adım 4.
> **Her referans için "neyi alıyorum / neyi almıyorum" yazılır.** "Bu güzel"
> yeterli değil — not yoksa ajan 5 referanstan Frankenstein üretir.

---

## ⚠ Durum: görsel referans henüz eklenmedi

Bu klasörde **ekran görüntüsü yok.** Ajan siteyi göremez, link işe yaramaz —
dosya indirmek gerekiyor. Kaynaklar `DESIGN.md` Bölüm 17.2'de; panel işi için
en verimli üçü:

- **refero.design** — gerçek ürün ekranları, akış bazlı
- **boardui.com** — panel odaklı derleme
- **mobbin.com** — akış bazlı (boş durum, onboarding)

5–8 görsel indirip bu klasöre koy, her biri için aşağıdaki şablonla 2 satır
yaz, sonra ajana "refs güncellendi, oku" de.

**Ne kadar eksik kaldı:** Bölüm 1'in kaldıraç tablosunda görsel referans
kalitenin ~%40'ı. Bu tur onun yerine `DESIGN.md` Bölüm 8'i kullandı — ki o
bölümün kendi başlığı *"ölçüler 30 profesyonel panel ekranından çıkarılmıştır"*
diyor, yani damıtılmış referans. Yapı ve ölçü bu yüzden sağlam; **kaybedilen
şey ölçü değil, karakter kalibrasyonu** — "bu kadar boşluk fazla mı, bu
tipografik kontrast yeterli mi" sorusunun gözle cevabı.

### Şablon

```md
- `01-<kaynak>-<ekran>.png`
  ALIYORUM: <yapı / ritim / anatomi — somut>
  ALMIYORUM: <renk / tipografi / layout — somut>
```

---

## Genel yön — bu tur bağlayıcı olan

Görsel referans gelene kadar ajanın kalibrasyonu budur:

**Sakin, hassas, arşivsel.** Bu bir gazete masası değil, bir **kayıt
defteridir**. Ekran bağırmaz; kanıtın ne kadar sağlam olduğunu sessizce ve
kesin biçimde söyler.

| Alınacak | Alınmayacak |
|---|---|
| Veri yoğunluğu — ferah değil, dolu ama nefes alan | Gösterişli efekt, gradient, glow |
| Tipografik kontrast: küçük etiket ↔ büyük değer | Dekoratif ikon, emoji |
| 1px kenarlıkla kurulan yüzey ayrımı | Her karta gölge |
| Tek aksan rengi, durum renklerinin ayrı işi | 3'ten fazla aksan |
| Sayıların hizalı ve sakin durması | Animasyonlu sayaç, canlı zıplayan rakam |

**Signature adayı (Bölüm 16.1 "bu ekranı akılda kalıcı yapan tek öğe"):**
kanıt gücünün *tipografiyle* anlatılması — teyitli iddia tam kontrastta,
teyitsiz iddia kısılmış kontrastta. Rozet değil, **metnin kendisi** kanıt
durumunu taşır. Bu, ürünün tek cümlelik sözleşmesinin ("AI senin yerine
konuşmaz") görsel karşılığıdır ve herhangi bir panel için verilecek bir karar
değildir.

## Kırmızı çizgi — referanstan asla alınmayacak

Ne kadar iyi görünürse görünsün, bir referanstan **kaynağa görsel bir konum/
taraf işareti** (renkli şerit, "eğilim" göstergesi, taraf ikonu) alınamaz.
Spec §8.5 yasaklar, `tests/test_web.py` tarar. Kaynak yalnızca **ad + tier +
yayın grubu** ile anılır.
