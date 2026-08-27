# Implementation Plan — FAZ 24: Gerçek Veriyle Productionization, Live Ingestion Validation, Source Expansion & Final Launch Readiness

Bu plan; PolitikDesk'in Faz 23 ile tamamlanan arayüz ve editoryal çalışma masası altyapısını, gerçek kaynaklardan gelen canlı haber akışı, ingestion pipeline doğrulaması, kaynak kalite matrisi, 200+ başlıklı taksonomi benchmark'ı, kaynak genişletme kataloğu ve operasyonel dayanıklılık denetimleriyle **üretim lansmanına hazır (Launch Ready)** hale getirmeyi amaçlar.

---

## 1. Dondurulan Baseline & Snapshot
- **Git SHA:** `8dd21ec200d25a7d9d65e20a40d15cca557c37af` (main)
- **Pytest:** 2.130/2.130 passed (48.83s)
- **Production Gates:** 7/7 passed
- **Ruff & Mypy:** Clean (184 source files)
- **Architecture Check:** Clean
- **Docker Stack:** 7/7 containers Up & Healthy
- **Snapshot Backup:** `politikdesk-20260824T172426Z-phase24_preflight.dump` (55.79 MB, SHA-256 doğrulandı, 338 nesne)
- **Publication Cycles:**
  - Cycle #1: `legacy_cycle_0` (11.626 makale, 3.317 olay, status: `archived`)
  - Cycle #2: `prod_cycle_20260824` (status: `active`)

---

## 2. Planlanan Adımlar

### Aşama 1: Kaynak Kataloğu ve Gerçek Ingestion Sağlık Matrisi
- 101 kaynağın analizi (RSS, Atom, API, Resmi Kurumlar, Ajanslar).
- Her kaynak için: Fetch &rarr; Parse &rarr; Normalize &rarr; Dedup &rarr; Classify &rarr; Persist & Latency ölçümü.
- Boş feed, 200 ama 0 item dönen anomalilerin tespiti.

### Aşama 2: Hata Simülasyonu ve Pipeline Dayanıklılığı
- Timeout, DNS hatası, 500 Server Error, 429 Rate Limit, bozuk XML, boş RSS, yönlendirme testleri.
- Retry, exponential backoff, circuit breaker ve loglama/metrik mekanizmalarının tescili.

### Aşama 3: 200+ Başlıklı Editoryal Taksonomi Benchmark'ı
- 200+ gerçekçi Türkçe haber başlığı ile kategori ve bölge doğruluk oranlarının ölçülmesi.
- Çoklu sinyal içeren haberlerde deterministik birincil kategori atama mantığının doğrulanması.

### Aşama 4: Gelişmiş Arama ve Keşif Performansı
- Arama sorgusunun `title`, `summary`, `topic_tags`, `claims` ve `entities` üzerinde <500ms performansla çalışması.
- Gündem V3 filtreleme tepki sürelerinin (<300ms) ölçülmesi.

### Aşama 5: Doğrulanmış Kaynak Genişletme Kataloğu & SQS Modeli
- 50+ gerçek, doğrulanmış kaynak kataloğu (Resmi kurumlar, uluslararası ajanslar, ekonomi/istatistik kurumları).
- Algoritmik Source Quality Score (0-100) formülünün oluşturulması.

### Aşama 6: Nihai Doğrulama ve Launch Raporu
- Tüm testlerin (2.130+) çalıştırılması.
- 7/7 Production Gates.
- `FAZ_24_REAL_DATA_PRODUCTIONIZATION_AND_FINAL_LAUNCH_AUDIT.md` raporunun hazırlanması.
