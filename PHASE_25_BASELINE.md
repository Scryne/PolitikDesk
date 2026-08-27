# POLITIKDESK — PHASE 25 IMMUTABLE BASELINE AUDIT
**Tarih:** 2026-08-24T17:34:05.397862+00:00  
**Git SHA:** `8dd21ec200d25a7d9d65e20a40d15cca557c37af` (main)  
**Pytest:** 2.348 / 2.348 Passed (%100 Başarı - 60.97s)  
**Production Gates:** 7 / 7 Passed  
**Docker Stack:** 7 / 7 Up & Healthy  

---

## 1. Veritabanı Varlık Sayımları
| Tablo Adı | Toplam Kayıt | Arşivlenmiş (`legacy_cycle_0`) | Aktif (`prod_cycle_20260824`) |
|---|:---:|:---:|:---:|
| **Articles (Makaleler)** | **11732** | 11626 | 104 |
| **Events (Olaylar)** | **3380** | 3317 | 63 |
| **Claims (İddialar)** | **11805** | 11.790 | 15 |
| **Evidence (Kanıtlar)** | **14921** | 14.906 | 15 |
| **Sources (Kaynaklar)** | **101** | - | 101 |
| **Publication Cycles** | **2** | 1 (`archived`) | 1 (`active`) |

---

## 2. Publication Cycles
- **Cycle #1:** `legacy_cycle_0` | Status: `archived` | Start: `2026-07-31 21:00:00+00:00` | End: `2026-08-24 16:42:45.221750+00:00`
- **Cycle #2:** `prod_cycle_20260824` | Status: `active` | Start: `2026-08-24 16:42:45.221750+00:00` | End: `None`

---

## 3. Kümeleme (Event Clustering) ve Tekilleştirme (Dedup) İstatistikleri
- **Toplam Olay:** 3380
- **Ortalama Makale / Olay:** 3.47
- **Maksimum Makale İçeren Olay:** 626
- **Çoklu Makaleli Olaylar:** 837 (%24.76)
- **Tek Makaleli Olaylar:** 2424 (%71.72)
- **Birleştirilen (Merged) Olaylar:** 0
- **Near-Duplicate Makaleler:** 2076 / 11732 (%17.70)

---

## 4. Zaman Damgaları ve Tazelik (Freshness)
- **Makale İlk Görülme Aralığı:** `2026-08-12 10:11:05.595749+00:00` &rarr; `2026-08-24 17:33:30.131094+00:00`
- **Makale Yayın Tarihi Aralığı:** `2015-11-02 09:26:59+00:00` &rarr; `2026-08-24 18:25:49+00:00`
- **Olay Oluşturulma Aralığı:** `2026-08-12 21:12:07.232358+00:00` &rarr; `2026-08-24 17:33:06.646249+00:00`
- **Olay İlk Raporlanma Aralığı:** `2015-11-02 09:26:59+00:00` &rarr; `2026-08-24 18:25:49+00:00`
- **Olay Son Güncellenme Aralığı:** `2015-11-02 09:26:59+00:00` &rarr; `2026-08-24 18:25:49+00:00`

---

## 5. Kaynak Dağılımı (Sources Breakdown)
- **Türe Göre:**
  - `social`: 46
  - `media`: 37
  - `official`: 12
  - `wire`: 6
- **Adaptöre Göre:**
  - `rss`: 47
  - `twitter`: 46
  - `cumhurbaskanligi`: 1
  - `evds`: 1
  - `generic_html`: 1
  - `tbmm`: 1
  - `tuik_sdmx`: 1
  - `wp_rest`: 1
  - `resmi_gazete`: 1
  - `sayistay`: 1

---

## 6. Docker Stack & Canlı HTTP Uç Noktaları
- `pd-api` (Healthy - 127.0.0.1:8000)
- `pd-beat` (Up)
- `pd-db` (Healthy - 127.0.0.1:5432)
- `pd-redis` (Healthy - 127.0.0.1:6379)
- `pd-rsshub` (Up - 127.0.0.1:1200)
- `pd-worker` (Up)
- `pd-worker-llm` (Up)

Tüm 8 canlı HTTP uç noktası (`/health/live`, `/health/ready`, `/metrics`, `/api/feed`, `/api/feed/check-new`, `/api/feed/taxonomy`, `/feed`, `/feed?sort=newest`) 200 OK ile doğrulanmıştır.
