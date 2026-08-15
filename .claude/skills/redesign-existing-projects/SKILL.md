---
name: redesign-existing-projects
description: Çalışan ama görsel olarak dağınık bir arayüzü davranışını bozmadan yeniden tasarlamak. Mevcut ekranları elden geçirirken, stil borcunu temizlerken veya "her sayfa farklı görünüyor" durumunu düzeltirken kullan. Anahtar: redesign, yeniden tasarım, refactor, stil borcu, tutarsızlık, mevcut ekran.
---

# Mevcut projeyi yeniden tasarlama

Sıfırdan tasarımdan farkı: **davranış zaten doğru ve korunmak zorunda.** Bu
depoda arayüz kısıtları testlerle korunuyor; tasarım turu bir testi kırıyorsa
tasarım yanlıştır, test değil.

## Sıra — bozma

```
1. ENVANTER    hangi ekranlar var, her biri hangi soruyu cevaplıyor
2. TOKEN       tek token dosyası kur, mevcut değerleri ONA taşı
3. KABUK       tek layout/shell — tüm sayfalar aynı kabuğu kullansın
4. BİLEŞEN     tekrar eden parçaları bileşene çıkar (rozet, kart, tablo)
5. SAYFA       sayfaları tek tek yeniden diz
6. TEMİZLİK    ölü CSS, kullanılmayan sınıf, kopya stil bloğu
```

**2'yi 5'ten önce yapmazsan** her sayfayı iki kez yazarsın. **3'ü atlarsan**
sayfalar birbirine benzemez — "her ekran farklı görünüyor" şikayetinin tek
nedeni budur, ayrı ayrı kötü tasarım değil.

## Envanter çıkarırken sor

| Soru | Bulgu ne demek |
|---|---|
| Kaç ayrı CSS bloğu var? | >1 ise kabuk yok demektir |
| Aynı bileşen kaç yerde ayrı yazılmış? | Bileşen katmanı eksik |
| Ham hex sayısı? | Token sistemi yok |
| Kaç farklı radius / gölge? | Karakter kararı verilmemiş |
| `uppercase` var mı? | Türkçede `i→I` bozukluğu (Ek B.3) |
| Emoji ikon var mı? | Tek ikon setine geçilmeli |

## Davranışı koruma kuralı

Yeniden tasarım turu şunları **değiştirmez**:

- URL'ler ve route imzaları
- JSON uçlarının şekli
- JS fonksiyon adları (dış çağrıları olabilir)
- Testlerin aradığı metin dizeleri — değiştirmen gerekiyorsa **testi de**
  aynı commit'te güncelle ve gerekçesini yaz

Bu depoda özellikle: `tests/test_web.py` üretilen HTML içinde belirli cümleleri
arar ("doğruluk skoru değildir", "ideolojik soru yoktur", "KVKK m.6"). Bunlar
kozmetik değil, **ürün sözleşmesidir**. Yeniden yazarken cümleyi güzelleştirmek
serbest, anlamı kaldırmak değil.

## Eski ile yeniyi yan yana koyma

Geçiş sırasında iki stil sistemi bir arada yaşarsa sonuç ikisinden de kötüdür.
Kabuğu değiştirdiğin an **tüm sayfalar** yeni kabuğa geçer; "şimdilik admin
eski kalsın" denmez. Admin ekranları da kullanıcının gördüğü ekranlardır.

## Bitmiş sayılma ölçütü

- Tek CSS kaynağı, tek token dosyası, tek ikon seti
- Her sayfa aynı kabuğu kullanıyor
- `grep -rnE "#[0-9a-fA-F]{6}"` yalnızca token dosyasını gösteriyor
- Eski stil bloğu **silinmiş** (yorum satırında bekletilmiyor)
- Test paketi yeşil
- 375/768/1440/1920 screenshot'ları alınmış ve incelenmiş
