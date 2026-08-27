# POLİTİKDESK — FAZ 21: FRESH PRODUCTION CYCLE & GÜNDEM V2 LIVE INTELLIGENCE FEED
**Rapor Türü:** Staff / Principal Engineering Architecture & Delivery Report  
**Tarih:** 2026-08-24  
**Sürüm:** PolitikDesk v3.6 (Faz 21)  
**Durum:** PRODUCTION CERTIFIED — AKTİF VE DEVREDE  

---

## 1. YÖNETİCİ ÖZETİ (EXECUTIVE SUMMARY)

PolitikDesk Faz 21 kapsamında iki kritik stratejik hedef başarıyla gerçekleştirilmiştir:

1. **Sıfır Veri Kaybı ile Temiz Üretim Döngüsü (Data Lifecycle & Isolation Engine):**
   * Faz 1–20 boyunca birikmiş 11.626 makale, 3.317 olay, 11.737 iddia ve 14.840 kanıt kaydı **tek bir bayt bile silinmeden (0 destructive delete)** `legacy_cycle_0` kimliğiyle güvenli bir arşiv döngüsüne taşınmıştır.
   * `publication_cycles` tablosu ve PostgreSQL seviyesinde tekil kısmi indeks kısıtı (`WHERE status = 'active'`) ile `prod_cycle_20260824` ("Faz 21 Canlı İstihbarat Döngüsü") aktif başlangıç noktası olarak devreye alınmıştır.
   * Boru hattı (`ingestion`, `clustering`, `web/feed`, `search`, `api`) döngüsel izolasyon motoruna bağlanmıştır.

2. **Gündem V2 — Canlı İstihbarat Masası (Live Intelligence Feed):**
   * Gündem ekranı klasik bir haber listesi olmaktan çıkarılmış; gerçek zamanlı, çok boyutlu filtrelenebilir, kesintisiz okuma garantili modern bir istihbarat paneline dönüştürülmüştür.
   * 3 farklı sıralama modu: **🔥 Önemli (Salience Score)**, **🕐 En Yeni (Discovery Time)**, **⚡ Son Güncellenen (Last Update)**.
   * **↓ X Yeni Gelişme Bildirim Banner'ı:** Yeni gelen haberlerde kullanıcının okuma konumunu sıçratmadan (*no scroll jump*) tıkla-öne-ekle mekanizması.
   * Kanonik Kategori (10 adet) ve Bölge (7 adet) taksonomisi ile çoklu filtreleme (Kategori, Bölge, Konu, Zaman Aralığı, Kaynak, Durum).
   * URL tabanlı durum kalıcılığı (`/feed?sort=newest&category=ekonomi&range=24h`).
   * X (Twitter) hızlı yayın taslağı üretimi ve tek tıkla paylaşım entegrasyonu.

---

## 2. GERÇEKLEŞTİRİLEN MİMARİ VE VERİ YAPISI DEĞİŞİKLİKLERİ

### 2.1 Veritabanı Şeması ve İzolasyon (`migrations/0023_data_lifecycle_and_gundem_v2.sql`)

```sql
-- 1. Üretim Döngüleri Tablosu
CREATE TABLE IF NOT EXISTS publication_cycles (
  id          BIGSERIAL PRIMARY KEY,
  cycle_key   TEXT UNIQUE NOT NULL,
  name        TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'paused')),
  started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at    TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  meta        JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Kısmi Tekil İndeks: Sistemde AYNI ANDA YALNIZCA 1 AKTİF DÖNGÜ olabilir!
CREATE UNIQUE INDEX IF NOT EXISTS idx_publication_cycles_active 
  ON publication_cycles (status) WHERE status = 'active';

-- 2. Makale ve Olay Tablolarına Döngü, Kategori ve Bölge Alanları
ALTER TABLE events ADD COLUMN IF NOT EXISTS cycle_id BIGINT REFERENCES publication_cycles(id);
ALTER TABLE events ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'ekonomi';
ALTER TABLE events ADD COLUMN IF NOT EXISTS region TEXT NOT NULL DEFAULT 'turkiye';

ALTER TABLE articles ADD COLUMN IF NOT EXISTS cycle_id BIGINT REFERENCES publication_cycles(id);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'ekonomi';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS region TEXT NOT NULL DEFAULT 'turkiye';
```

### 2.2 Taksonomi Motoru (`politikdesk/analysis/taxonomy.py`)

Kural tabanlı, deterministik ve konu etiketlerine duyarlı sınıflandırıcı:
* **Kanonik Kategoriler (10):**
  1. `ekonomi` (Makro Ekonomi & Finans)
  2. `politika` (İç Politika & Yasama)
  3. `dis_politika` (Dış Politika & Diplomasi)
  4. `guvenlik` (Güvenlik & Savunma)
  5. `hukuk` (Hukuk & Yargı)
  6. `enerji` (Enerji & Tabii Kaynaklar)
  7. `teknoloji` (Teknoloji & Sanayi)
  8. `saglik_toplum` (Sağlık & Toplum)
  9. `yerel` (Yerel Yönetimler)
  10. `diger` (Diğer Gelişmeler)

* **Kanonik Bölgeler (7):**
  1. `turkiye` (Türkiye & Ulusal)
  2. `abd` (Kuzey Amerika / ABD)
  3. `avrupa` (Avrupa Birliği & Kıta Avrupası)
  4. `orta_dogu` (Orta Doğu & Körfez)
  5. `rusya_ukrayna` (Avrasya / Rusya-Ukrayna)
  6. `asya_pasifik` (Asya-Pasifik)
  7. `kuresel` (Küresel & Çok Taraflı)

---

## 3. ÜRETİM DÖNGÜSÜ YÖNETİM ARACI (CLI)

`scripts/production_cycle.py` CLI aracı ile tam denetlenebilir döngü yönetimi:

```bash
# Aktif ve arşiv döngülerinin durum raporu
python -m scripts.production_cycle status

# Döngü listesini görüntüleme
python -m scripts.production_cycle list

# Yeni aktif döngü başlatma (mevcudu arşivler, audit log kaydeder)
python -m scripts.production_cycle create --name "Eylül 2026 Döngüsü" --dry-run
python -m scripts.production_cycle create --name "Eylül 2026 Döngüsü" -y

# Mevcut aktif döngüyü arşivleme
python -m scripts.production_cycle archive-current -y
```

---

## 4. GÜNDEM V2 CANLI İSTİHBARAT MASASI ÖZELLİKLERİ

| Özellik | Açıklama |
| :--- | :--- |
| **Sıralama Seçenekleri** | `🔥 Önemli` (Salience + Kişisel Öncelik), `🕐 En Yeni` (İlk Bildirilen), `⚡ Son Güncellenen` (Tazelik) |
| **Canlı Bildirim Banner'ı** | 15 sn'de bir arka planda denetler; yeni olay geldiğinde `↓ X YENİ GELİŞME` banner'ı gösterir, tıklanınca scroll sıçraması yapmadan başa ekler |
| **Dinamik [YENİ] Rozeti** | Son 45 dakika içinde ilk kez keşfedilen olaylarda yanıp sönen `[YENİ]` etiketi |
| **Çok Boyutlu Filtreleme** | Kategori, Bölge, Konu, Zaman (15m, 1h, 6h, 24h, 7d), Kaynak ve Durum (Hazır, Taslaklı, Teyit Bekleyen, Denetimde) |
| **URL Durum Kalıcılığı** | Filtre ve sıralama seçimleri query parameter'a yazılır (`/feed?sort=newest&category=ekonomi&range=24h`), paylaşılabilir ve yenilendiğinde korunur |
| **X (Twitter) Köprüsü** | Tek tıkla kanıta bağlı 4 farklı açıdan (`inform`, `critique`, `advocate`, `investigate`) tweet üretimi ve doğrudan X paylaşımı |
| **Erişilebilirlik & Kısayollar** | Tam WCAG 2.1 AA uyumlu başlık hiyerarşisi (`h1 -> h2.h3`), klavye ile gezinti (`j/k`, `x`, `Enter`, `/`, `?`) |

---

## 5. TEST VE DOĞRULAMA METRİKLERİ

### 5.1 Pytest Test Paketi
* **Toplam Test Sayısı:** 1.973
* **Başarılı:** 1.973 (%100)
* **Hata / Başarısızlık:** 0
* **Çalışma Süresi:** 53.52 saniye

### 5.2 Üretim Kapıları (Production Gates)
* **Gate 1 (Source & Database Reconciliation):** [PASS] 101 kaynak 1:1 sıfır farkla doğrulandı.
* **Gate 2 (Data Integrity & Foreign Key):** [PASS] 0 yetim kayıt (orphan claims, evidence, articles).
* **Gate 3 (Observability & Anomaly Model):** [PASS] Anomali sınıflandırıcıları ve Prometheus sayaçları aktif.
* **Gate 4 (Network Security & SSRF Guard):** [PASS] Loopback / dahili IP koruması (`UnsafeUrlError`) aktif.
* **Gate 5 (Architecture Boundary Isolation):** [PASS] Katman sınırları temiz (zero leaking).
* **Gate 6 (Disaster Recovery & Backup Policy):** [PASS] SHA-256 bütünlük doğrulaması ve yük devretme hazır.
* **Gate 7 (Epistemic Grounding & Social Safety):** [PASS] TCK 217/A dezenformasyon koruması ve kanıt temeli aktif.
* **Sonuç:** **GATES PASSED: 7 / 7 (%100 SUCCESS)**

### 5.3 Tasarım Belirteçleri (Design Tokens)
* **Ham Hex Taraması:** 0 ihlal (Tüm stiller `tokens.py` ve semantik CSS değişkenlerine bağlıdır).

---

## 6. MEVCUT VERİTABANI VE DÖNGÜ DURUMU

```text
======================================================================
POLİTİKDESK PRODUCTION DATA LIFECYCLE STATUS
======================================================================
[*] AKTİF DÖNGÜ: #2 [prod_cycle_20260824]
    İsim:        Faz 21 Canlı İstihbarat Döngüsü
    Başlangıç:   2026-08-24 16:42:45.221750+00:00
    Veri Sayıları (Aktif):
      - Makaleler: 0 (Temiz Başlangıç)
      - Olaylar:   0 (Temiz Başlangıç)
      - İddialar:  0
      - Kanıtlar:  0
----------------------------------------------------------------------
ARŞİVLENMİŞ DÖNGÜLER (1 adet):
  • #1 [legacy_cycle_0] "Faz 1-20 Tarihsel Arşiv Döngüsü"
    (2026-07-31 21:00:00 -> 2026-08-24 16:42:45) | 11.626 makale, 3.317 olay
======================================================================
```

---

## 7. SONUÇ VE DEVREYE ALMA

PolitikDesk **Faz 21 (Fresh Production Cycle & Gündem V2)** başarıyla tamamlanmış, tüm güvenlik, epistemik ve performans kısıtları %100 karşılanarak üretime hazır hale getirilmiştir.
