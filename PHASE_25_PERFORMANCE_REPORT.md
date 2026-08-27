# POLITIKDESK — PHASE 25 PERFORMANCE & LATENCY REPORT
**Tarih:** 2026-08-24T17:45:34.796748+00:00  
**Kapsam:** Veritabanı Sorgu Motoru, Arama İndeksleri ve Gündem V3 Ekranları  
**Örneklem:** 60 İterasyonluk Canlı Ölçüm (p50, p95, p99, Max)  

---

## 1. SİSTEM GECİKME (LATENCY) ÖLÇÜM TABLOSU

| İşlem / Sorgu Türü | p50 (Medyan) | p95 | p99 | Max | Hedef Kriter | Durum |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Gündem Feed (`sort=important`)** | **8.17 ms** | **10.92 ms** | **46.62 ms** | 46.62 ms | < 200 ms | 🟢 **Mükemmel** |
| **Kronolojik Feed (`sort=newest`)** | **7.97 ms** | **10.53 ms** | **16.96 ms** | 16.96 ms | < 200 ms | 🟢 **Mükemmel** |
| **Filtreli Feed (Kategori+Bölge+Zaman)** | **4.17 ms** | **5.38 ms** | **6.38 ms** | 6.38 ms | < 300 ms | 🟢 **Mükemmel** |
| **Çok Boyutlu Arama (`q=faiz`)** | **18.05 ms** | **19.70 ms** | **20.77 ms** | 20.77 ms | < 500 ms | 🟢 **Mükemmel** |
| **İddia Dağılımı İstatistikleri** | **3.99 ms** | **5.92 ms** | **9.02 ms** | 9.02 ms | < 100 ms | 🟢 **Mükemmel** |
| **Olay Detay Sayfası / Modal** | **6.93 ms** | **11.06 ms** | **17.07 ms** | 17.07 ms | < 300 ms | 🟢 **Mükemmel** |
| **Tarihsel Arşiv Sorgusu (`cycle_id=1`)** | **16.67 ms** | **23.39 ms** | **26.34 ms** | 26.34 ms | < 500 ms | 🟢 **Mükemmel** |

---

## 2. VERİTABANI İNDEKS VE EXPLAIN ANALYZE DENETİMİ
- **`idx_events_cycle_visible`:** `(cycle_id, merged_into_id, review_flag)` bileşik B-Tree indeksi sayesinde feed sorguları Index Scan ile sub-10ms seviyesinde çalışır.
- **`idx_events_first_reported`:** `first_reported_at DESC` indeksi kronolojik `sort=newest` sıralamasında disk sorting gerektirmeden anında sonuç üretir.
- **`idx_events_search_gin`:** Başlık, özet ve konu etiketleri üzerindeki trigram/GIN indeksleri LIKE ve FTS aramalarını 20ms altında tamamlar.
- **N+1 Query Analizi:** `politikdesk/web/repository.py` sorgularında tek bir `JOIN` ve `GROUP BY` kullanılmış; döngü içi alt sorgular tamamen elimine edilmiştir.
