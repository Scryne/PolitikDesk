# PolitikDesk — Veritabanı Ölçekleme ve Bölümleme (Partitioning) Politikası

Bu doküman, PolitikDesk PostgreSQL veritabanının veri büyümesi, indeks sağlığı, sorgu gecikmeleri ve tablo bölümleme (table partitioning) stratejisini ölçülebilir eşiklerle tanımlar.

---

## 1. Mevcut Mimari ve İndeks Durumu

PolitikDesk çekirdek tabloları (`articles`, `events`, `claims`, `evidence_items`, `actor_positions`):
- `articles.excerpt`: `VARCHAR(300)` telif hakkı üst sınırı ile sınırlandırılmıştır; tam makale metni (`body`) veritabanında saklanmaz.
- `articles.canonical_url`: Kaynak düzeyinde yinelenen haberleri engellemek için `UNIQUE` indeks taşır.
- `events`: `first_seen_at` ve `updated_at` üzerinden zamana dayalı besleme (`/feed`, `/war-room`) sorguları çalıştırır.
- Composite İndeksler (`migrations/0015_composite_indexes.sql`):
  - `idx_events_feed_covering ON events (first_seen_at DESC, id)`
  - `idx_articles_clustering ON articles (published_at, source_id)`

---

## 2. Neden Erken Bölümleme (Premature Partitioning) Yapılmadı?

1. **Çalışma Kümesi Boyutu**: Günde ortalama ~500-1.500 makale ve ~50-100 kümelenmiş olay işlenmektedir. Yıllık toplam satır artışı ~350.000 satır civarındadır.
2. **RAM & Buffer Pool Etkinliği**: 1 milyon satır altındaki B-Tree indeksler PostgreSQL `shared_buffers` içinde <100 MB yer tutar. İndeks tarama süresi PostgreSQL 16 üzerinde ortalama **0.8 - 2.1 ms** aralığındadır.
3. **Global Unique Kısıtı Zorluğu**: PostgreSQL'de deklaratif bölümleme yapıldığında `UNIQUE (canonical_url)` gibi global kısıtlar ancak partition key'i (`published_at`) kısıt bileşeni yapıldığında yerel olarak desteklenir. Bu durum haber URL'si tekilliğini garanti etmeyi zorlaştırır.

---

## 3. Ölçülebilir Ölçekleme Eşikleri

| Aşama / Eşik | Satır Sayısı (`articles` / `events`) | İndeks Bellek İzi | Tetiklenecek Eylem |
| :--- | :--- | :--- | :--- |
| **Normal Çalışma** | `< 250.000` satır | `< 30 MB` | Mevcut composite B-tree indeksler ve otomatik `VACUUM ANALYZE`. |
| **Uyarı Eşiği (Warning)** | `250.000 - 500.000` | `~30 - 65 MB` | `pg_stat_user_indexes` ve `pg_stat_statements` ile p95 sorgu gecikmelerinin izlenmesi; index bloat analizi. |
| **İnceleme Eşiği (Review)** | `500.000 - 1.000.000` | `~65 - 150 MB` | Aylık deklaratif range partitioning (`PARTITION BY RANGE (published_at)`) migrasyon planının staging ortamında test edilmesi. |
| **Bölümleme Eşiği (Partitioning)** | `> 1.000.000` satır | `> 150 MB` | Üretim ortamında `articles` ve `events` tablolarının aylık partisyonlara bölünmesi ve eski partisyonların sıkıştırılmış `pg_partman` arşivine taşınması. |

---

## 4. İnceleme Metrikleri ve SLA

Aşağıdaki metrikler haftalık bakım ritüelinde denetlenir:
- **P95 Besleme Sorgusu Gecikmesi**: `< 50 ms`
- **İndeks Önbellek İsabet Oranı (Cache Hit Ratio)**: `> 99.0%`
- **Dead Tuples Oranı**: `< 5%`
