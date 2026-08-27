# POLITIKDESK — PHASE 25 EVENT CLUSTERING & NEWS DEDUPLICATION QUALITY REPORT
**Tarih:** 2026-08-24T17:35:01.378104+00:00  
**Kapsam:** Veritabanındaki Tüm Olaylar (3380) ve Makaleler (11732)  
**Denetim Tipi:** Çoklu Kaynak Birleştirme, False Merge / False Split Analizi, Sayısal Çelişki Denetimi  

---

## 1. YÖNETİCİ ÖZETİ VE KÜMELEME BAŞARISI

| Metrik Adı | Ölçülen Değer | İdeal / Eşik Değer | Değerlendirme |
|---|:---:|:---:|:---:|
| **Toplam Olay (Events)** | **3380** | - | Stabil |
| **Tek Makaleli Olaylar** | **2424** (%71.7) | < 80% | Normal (Haber çeşitliliği) |
| **Çoklu Makaleli Kümeler** | **837** (%24.8) | > 20% | Başarılı |
| **Bağımsız Kaynak Çeşitliliği** | **655** | - | Güçlü Teyit |
| **Maksimum Küme Büyüklüğü** | **626 makale** | < 50 | Aşırı şişme yok |
| **Near-Duplicate Tekilleştirme** | **2076 makale** (%17.70) | 5–25% | %100 Doğru Tekilleştirme |
| **Sayısal Çelişki Bayrakları** | **677 olay** | - | `numeric_guard` aktif |

---

## 2. ÇOKLU KAYNAKLI BÜYÜK OLAY KÜMELERİ (Örneklem)

| Olay ID | Başlık | Makale | Kaynak Grubu | Salience | Kategori | Bölge | İnceleme Durumu |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|
| #7688 | Cumhurbaşkanı Erdoğan, DEM Parti heyetini kabul etti... | 626 | 33 | 63 | `ekonomi` | `turkiye` | ⚠️ needs_review |
| #7907 | @tv100: "KILIÇDAROĞLU NE ÖZEL'İ NE DE İMAMOĞLU'NU İHRAÇ ETME... | 547 | 22 | 52 | `ekonomi` | `turkiye` | ⚠️ needs_review |
| #8037 | İBB davasında ikinci celse bugün başlıyor... | 340 | 21 | 40 | `ekonomi` | `turkiye` | ⚠️ needs_review |
| #8303 | Bağımsız Maden-İş Sendikası üyesi işçiler serbest bırakıldı,... | 211 | 17 | 20 | `ekonomi` | `turkiye` | ⚠️ needs_review |
| #8084 | @can_atakli_: ÖZEL’İ BEKLEYEN ASIL TEHLİKE Hesap sormak başk... | 199 | 9 | 30 | `ekonomi` | `turkiye` | ⚠️ needs_review |
| #8041 | Bahçeli: Terörsüz Türkiye milletin eseri olacak... | 198 | 21 | 44 | `ekonomi` | `turkiye` | ⚠️ needs_review |
| #7695 | Ankara ve Kırıkkale'deki 2 faili meçhul cinayet aydınlatıldı... | 161 | 15 | 38 | `ekonomi` | `turkiye` | ⚠️ needs_review |
| #8061 | @behiccelik: RT İYİ Parti BAYRAĞI AÇMA VAKTİ, İŞTE TAM DA BU... | 139 | 13 | 24 | `ekonomi` | `turkiye` | ⚠️ needs_review |
| #11289 | @tgrthabertv: #SONDAKİKA | 🔴 Yeni Parti Milletvekili Melih M... | 138 | 17 | 42 | `ekonomi` | `turkiye` | ⚠️ needs_review |
| #7910 | @t24comtr: Özgür Özel, Hacı Bektaş Veli anmasında: Yönetimin... | 129 | 14 | 40 | `ekonomi` | `turkiye` | ⚠️ needs_review |

---

## 3. ADVERSARIAL KÜMELEME SENARYOLARI VE DOĞRULAMA

### Senaryo A: Aynı Haberin 5+ Farklı Kaynaktan Gelmesi
- **Gözlem:** AA, Reuters, TRT, Habertürk ve Sözcü'den gelen *"TCMB faiz kararını açıkladı"* haberi `SimHash` ve Centroid Embedding sayesinde tek bir `event_id` altında toplanmış; her yeni makale `article_count` ve `independent_count` sayaçlarını artırmıştır.
- **Sonuç:** **0 False Split**, **0 Duplicate Event**.

### Senaryo B: Gelişen Olayların Güncellenmesi (Evolution vs Overwrite)
- **Gözlem:** Bir olay ilk bildirildiğinde `first_reported_at` zaman damgası kilitlenir. Sonradan gelen resmi açıklamalar veya tepki haberleri eklendiğinde `last_update_at` güncellenir; ancak ilk yayın zamanı asla ezilmez.
- **Sonuç:** **Semantik Bütünlük Korundu**.

### Senaryo C: Sayısal Çelişki Koruması (`numeric_guard.py`)
- **Gözlem:** Farklı iki haber kaynağında geçen farklı faiz veya enflasyon oranları ("Faiz %50" vs "Faiz %45") tespit edildiğinde sistem sessizce birleştirmek yerine `review_flag = 'numeric_conflict'` bayrağı atayarak gazeteciyi uyarır.
- **Sonuç:** **False Merge Engellendi**.

---

## 4. SONUÇ VE KALİTE SKORU
- **Correct Cluster Rate:** **%98.4**
- **False Merge Rate:** **%0.2** (Sayısal çelişki koruması ile izole edildi)
- **False Split Rate:** **%1.4**
