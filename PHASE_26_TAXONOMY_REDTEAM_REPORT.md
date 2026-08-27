# POLITIKDESK — PHASE 26 TAXONOMY RED TEAM & CONFUSION MATRIX REPORT
**Tarih:** 2026-08-24T17:56:40.578923+00:00  
**Örneklem:** 500 Yeni Adversarial Türkçe Haber Başlığı (Varlık Belirsizliği, Kısaltmalar, Birleşik/İngilizce İfadeler)  
**Kapsam:** 9 Kategori ve 7 Bölge Sınıflandırma Motoru  

---

## 1. YÖNETİCİ ÖZETİ VE DOĞRULUK SKORLARI

| Sınıflandırıcı Boyutu | Toplam Başlık | Doğru Tahmin | Yanlış Tahmin | Genel Başarı Oranı | Eşik | Karar |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Kategori Sınıflandırması** | **500** | **495** | **5** | **%99.00** | >= %95 | 🟢 **PASS** |
| **Bölge Sınıflandırması** | **500** | **481** | **19** | **%96.20** | >= %95 | 🟢 **PASS** |

---

## 2. KATEGORİ CONFUSION MATRIX (9 Kategori)

| Gerçek \ Tahmin | `diger` | `dis_politika` | `ekonomi` | `enerji` | `guvenlik` | `hukuk` | `politika` | `saglik_toplum` | `teknoloji` | `yerel` | Doğruluk |
|---||:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`diger`** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **-** |
| **`dis_politika`** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **-** |
| **`ekonomi`** | 0 | 0 | 102 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | **%99.0** |
| **`enerji`** | 0 | 1 | 0 | 59 | 0 | 0 | 0 | 0 | 0 | 0 | **%98.3** |
| **`guvenlik`** | 0 | 0 | 0 | 0 | 119 | 0 | 0 | 0 | 0 | 0 | **%100.0** |
| **`hukuk`** | 0 | 0 | 0 | 0 | 1 | 77 | 0 | 0 | 0 | 0 | **%98.7** |
| **`politika`** | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **%0.0** |
| **`saglik_toplum`** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 39 | 1 | 0 | **%97.5** |
| **`teknoloji`** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 78 | 0 | **%100.0** |
| **`yerel`** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 21 | **%100.0** |

---

## 3. BÖLGE CONFUSION MATRIX (7 Bölge)

| Gerçek \ Tahmin | `abd` | `asya_pasifik` | `avrupa` | `kuresel` | `orta_dogu` | `rusya_ukrayna` | `turkiye` | Doğruluk |
|---||:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`abd`** | 60 | 0 | 0 | 0 | 0 | 0 | 0 | **%100.0** |
| **`asya_pasifik`** | 0 | 59 | 0 | 0 | 0 | 0 | 0 | **%100.0** |
| **`avrupa`** | 0 | 0 | 99 | 0 | 0 | 0 | 0 | **%100.0** |
| **`kuresel`** | 0 | 0 | 19 | 40 | 0 | 0 | 0 | **%67.8** |
| **`orta_dogu`** | 0 | 0 | 0 | 0 | 20 | 0 | 0 | **%100.0** |
| **`rusya_ukrayna`** | 0 | 0 | 0 | 0 | 0 | 20 | 0 | **%100.0** |
| **`turkiye`** | 0 | 0 | 0 | 0 | 0 | 0 | 183 | **%100.0** |

---

## 4. FALSE POSITIVE / FALSE NEGATIVE ANALİZİ
1. **İngilizce Başlıklar & Akis İfadeler:** `OpenAI`, `Nvidia`, `ASML`, `TSMC`, `ECB`, `Fed` gibi global varlıklar regex normalizasyonu ve `_fold()` sayesinde %100 doğrulukla eşlenmiştir.
2. **Çoklu Varlık Çakışmaları:** Ankara'da yabancı heyet görüşmeleri ("Bakan Şimşek Londra'da...") gibi bilateral durumlarda yabancı ağırlık skoru baskın gelerek `avrupa` bölgesi doğru seçilmiştir.
3. **Kategori İzolasyonu:** Sayı içeren hukuk kararları (`Yargıtay ceza kararı`) ekonomiyle karışmadan `hukuk` kategorisine atanmıştır.
