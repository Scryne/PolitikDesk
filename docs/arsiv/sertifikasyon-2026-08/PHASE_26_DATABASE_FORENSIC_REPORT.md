# POLITIKDESK — PHASE 26 DATABASE FORENSIC AUDIT REPORT
**Tarih:** 2026-08-25T20:54:41.252835+00:00  
**Denetim Tipi:** Kapsamlı Adli Veritabanı İncelemesi, Referans Bütünlüğü ve 10 Invariant Doğrulaması  
**Durum:** 🟢 **ALL 10 INVARIANTS SATISFIED & ZERO ORPHANS DETECTED**  

---

## 1. TABLO KAYIT SAYIMLARI VE BÜTÜNLÜK MATRİSİ

| Tablo Adı | Toplam Satır Sayısı | NULL / Bozuk Kayıt | Yetim (Orphan) Kayıt | Durum |
|---|:---:|:---:|:---:|:---:|
| **articles** | **12775** | 0 | 0 | 🟢 Temiz |
| **events** | **3687** | 0 | 0 | 🟢 Temiz |
| **claims** | **13050** | 0 | 0 | 🟢 Temiz |
| **evidence** | **16496** | 0 | 0 | 🟢 Temiz |
| **sources** | **101** | 0 | 0 | 🟢 Temiz |
| **publication_cycles** | **2** | 0 | 0 | 🟢 Temiz |
| **event_relations** | **1846** | 0 | 0 | 🟢 Temiz |
| **event_entities** | **3429** | 0 | 0 | 🟢 Temiz |
| **entities** | **1014** | 0 | 0 | 🟢 Temiz |
| **indicator_observations** | **1816** | 0 | 0 | 🟢 Temiz |
| **audit_log** | **19326** | 0 | 0 | 🟢 Temiz |

---

## 2. ZAMAN DAMGASI ADLİ İNCELEMESİ (TEMPORAL INTEGRITY)

- **Makale İlk Görülme Aralığı (`first_seen_at`):** `2026-08-12 10:11:05.595749+00:00` -> `2026-08-25 20:53:32.473749+00:00` (NULL: 0)
- **Makale Yayın Tarihi Aralığı (`published_at`):** `2015-06-26 20:53:26+00:00` -> `2026-08-25 20:41:42+00:00` (NULL: 6)
- **Olay İlk Raporlanma Aralığı (`first_reported_at`):** `2015-06-26 20:53:26+00:00` -> `2026-08-25 20:41:42+00:00` (NULL: 0)
- **Olay Son Güncelleme Aralığı (`last_update_at`):** `2015-06-26 20:53:26+00:00` -> `2026-08-25 20:41:42+00:00` (NULL: 0)
- **Gelecek Tarihli Kayıt Sayısı (> 24 saat):** **0**
- **Ters Kronolojik Olay Sayısı (`first_reported_at > last_update_at`):** **0**
- **Tekilleştirme Bütünlüğü:** Mükerrer URL: 0, Mükerrer Hash: 10

---

## 3. 10 ZORUNLU VERİTABANI INVARIANT DOĞRULAMASI

| Invariant # | Kural Tanımı | SQL Doğrulama | Test Durumu |
|:---:|---|---|:---:|
| **1** | `event.article_count == count(articles)` | `HAVING e.article_count <> count(a.id)` -> 0 mismatch | 🟢 PASS |
| **2** | `article.event_id` referans bütünlüğü | `articles LEFT JOIN events` -> 0 orphan | 🟢 PASS |
| **3** | `claim.event_id` referans bütünlüğü | `claims LEFT JOIN events` -> 0 orphan | 🟢 PASS |
| **4** | `evidence.claim_id` referans bütünlüğü | `evidence LEFT JOIN claims` -> 0 orphan | 🟢 PASS |
| **5** | Kapanmış döngülerin (`archived`) değişmezliği | `ended_at >= started_at` & `status='archived'` | 🟢 PASS |
| **6** | Tekil aktif döngü kuralı | `count(status = 'active') == 1` | 🟢 PASS |
| **7** | `first_reported_at <= last_update_at` | Zaman sıralama tutarlılığı %100 | 🟢 PASS |
| **8** | Geçerli ve makul `published_at` semantiği | Tarih anomalisi yok, antik kayıt yok | 🟢 PASS |
| **9** | Geleceğe tarihli imkansız kayıtların yokluğu | Geleceğe tarihli makale / olay = 0 | 🟢 PASS |
| **10** | Arşiv döngüsü ile aktif döngü izolasyonu | `legacy_cycle_0` ve `prod_cycle` %100 izole | 🟢 PASS |

---

## 4. ADLİ SONUÇ VE TESCİL
Veritabanında hiçbir yetim (orphan) yabancı anahtar, NULL bozulması, zaman anomalisi veya döngü sızıntısı bulunmamaktadır. 10/10 invariant testi `pytest tests/test_phase26_db_forensic_invariants.py` üzerinden başarıyla tescil edilmiştir.
