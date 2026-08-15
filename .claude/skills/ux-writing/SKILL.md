---
name: ux-writing
description: Türkçe arayüz metni — buton, başlık, hata mesajı, boş durum, sayı/tarih/para biçimlendirme. Arayüze metin yazarken, hata mesajı kurgularken veya Türkçe biçimlendirme yaparken kullan. Anahtar: Türkçe, metin, buton metni, hata mesajı, boş durum, biçimlendirme, para birimi, tarih, ek uyumu, uppercase.
---

# Türkçe arayüz metni

`DESIGN.md` Ek B'nin uygulama rehberi. Bu projede tüm arayüz Türkçedir ve
i18n katmanı yoktur — metin doğrudan koda yazılır, bu yüzden disiplin
gerektirir.

## Biçimlendirme

| Tür | Doğru | Yanlış |
|---|---|---|
| Para | `₺1.234,56` | `$1,234.56` · `1234.56 TL` |
| Sayı | `184.392` | `184,392` |
| Yüzde | `%12,4` — işaret **önde** | `12.4%` |
| Tarih | `25.07.2026` · `25 Tem 2026` | `07/25/2026` |
| Saat | `14:32` (24 saat) | `2:32 PM` |
| Büyük sayı | `1,2 mn` · `184 b` | `1.2M` · `184K` |

`Intl.NumberFormat('tr-TR')` / `Intl.DateTimeFormat('tr-TR')` kullan; Python
tarafında `politikdesk/web/ui/format.py`. **Elle biçimlendirme yapma** —
`f"{v:.1f}%"` her seferinde yanlış çıkar.

Para/ölçü birimi sayıdan **daha küçük ve muted** olur: `₺` küçük, `184.392`
büyük.

## Üç teknik tuzak

**1. `text-transform: uppercase` Türkçede bozuktur.**
`i → I` yapar, `İ` olması gerekir. "iddia" → "IDDIA" (yanlış), "İDDİA" olmalı.
CSS'e güvenme; küçük etiketlerde metni **elle büyük yaz** veya uppercase'den
tamamen vazgeç. Bu projede tercih: vazgeçmek — `letter-spacing` + `fg-subtle`
küçük etiket için zaten yeterli ayrım verir.

**2. Sıralama `localeCompare('tr')` ister.**
`ç ğ ı i ö ş ü` varsayılan sıralamada yanlış yere düşer. Python'da
`locale.strxfrm` veya açık bir sıra tablosu.

**3. Ek uyumu değişkenle kırılır.**
```
❌ f"{name}'in siparişi"     → sesli/sessiz uyumu bozulur
❌ f"{n} kayıt bulundu"      → n=0 için "0 kayıt bulundu" tuhaf
✅ f"Sipariş sahibi: {name}"
✅ f"Bulunan kayıt: {n}"  /  n==0 için ayrı boş durum metni
```
Ek gerektirmeyen kalıp kur. Bu, Türkçe arayüzde en sık yapılan hatadır.

**Metin uzunluğu:** Türkçe İngilizceden ~%20 uzundur. "Save"→"Kaydet",
"Export"→"Dışa aktar". Buton genişliğini sabitleme, `min-width` ver.

## Ton

- **Cümle düzeni:** başlıkta ilk harf büyük, gerisi küçük.
  ✅ "Yeni tedarikçi ekle" · ❌ "Yeni Tedarikçi Ekle"
- **Butonlar emir kipinde:** "Kaydet", "Sil", "Dışa aktar".
- **Bir eylem baştan sona aynı adı taşır:**
  buton "Yayımla" → onay "Yayımlansın mı?" → toast "Yayımlandı".
- **Sistem dili yasak:** "webhook yapılandırması" değil "bildirimler";
  "null değer" değil "boş"; "senkronizasyon hatası" değil "değişiklikler
  kaydedilemedi".
- **Pazarlama dolgusu yasak:** "kolayca", "sorunsuz", "güçlü", "devrim
  niteliğinde". Bu bir çalışma masası, bir landing sayfası değil.

## Hata mesajı özür dilemez, çözüm söyler

```
❌ "Üzgünüz, bir hata oluştu."
❌ "E-posta geçersiz"
✅ "Dosya yüklenemedi. En fazla 10 MB olmalı."
✅ "E-posta adresi ad@site.com biçiminde olmalı."
```

Yapı: **ne oldu → neden (biliniyorsa) → nasıl çözülür.** Teknik kod
gösterilecekse küçük ve altta: `HTTP 503 · req_a8f2`.

## Boş durum bir davettir

"Veri bulunamadı" yasak. Ne olacağını ve nasıl başlanacağını söyle + aksiyon
butonu koy.

**Filtre-boş durumu ayrı yazılır:** "'metal' aramasıyla eşleşen kayıt yok"
+ [Filtreleri temizle]. Kullanıcı hangi durumda olduğunu bilmeli — hiç veri
yok mu, yoksa filtresi mi tutmadı.

## Bu ürüne özel dil

- Sistem hiçbir yayına **siyasi konum etiketi** vermez. "yandaş", "muhalif",
  "iktidar medyası" gibi sözcükler arayüz metninde bulunamaz (Spec §8.5);
  `tests/test_web.py` tarar.
- **Salience bir doğruluk skoru değildir.** Skorun geçtiği her yerde bu not
  bulunur. "Güvenilirlik", "doğruluk oranı", "puan" gibi sözcüklerle anılamaz;
  doğru sözcük **önem**dir.
- Kanıt durumu bir *hüküm* değil, bir *sayımdır*: "3 bağımsız kaynak
  doğruluyor" ✅, "bu haber doğru" ❌.
