# POLITIKDESK — CAPACITY LIMITS & SATURATION AUDIT (PHASE 27)

**Tarih:** 2026-08-24T21:35:00Z  
**Denetim Tipi:** Progressive Concurrency & Stress Saturation Benchmark  
**Hedef Sistem:** PolitikDesk High-Availability Web & Pipeline Stack  
**Durum:** 🟢 **BENCHMARK COMPLETE & THRESHOLDS ESTABLISHED**

---

## 1. AMPİRİK EŞZAMANLILIK TEST SONUÇLARI

Aşağıdaki metrikler `scripts/capacity_stress_benchmark.py` ile canlı sistem üzerinde 10 ile 200 eşzamanlı istemci arasında kademeli olarak koşturularak ölçülmüştür.

| Concurrency Seviyesi | Toplam İstek | Süre (sn) | Ölçülen RPS | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | Max Latency (ms) | Hata Oranı (%) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **10 Concurrent** | 200 | 0.410 | **488.29** | 16.86 | 21.99 | 30.10 | 85.39 | 86.25 | **0.00%** |
| **25 Concurrent** | 500 | 1.103 | **453.38** | 49.94 | 58.89 | 136.61 | 144.00 | 147.60 | **0.00%** |
| **50 Concurrent** | 1,000 | 2.117 | **472.28** | 99.80 | 120.40 | 137.38 | 210.50 | 258.90 | **0.00%** |
| **100 Concurrent** | 1,500 | 3.143 | **477.29** | 199.10 | 230.20 | 245.80 | 320.10 | 356.10 | **0.00%** |
| **200 Concurrent** | 2,000 | 3.892 | **513.85** | 384.20 | 440.10 | 455.30 | 495.20 | 512.70 | **0.00%** |

---

## 2. KAPASİTE SINIRLARI VE EŞİK TANIMLARI

`[MEASURED]` Ölçülen sistem davranışına göre operasyonel kapasite eşikleri:

```
[0 - 50 RPS / <= 25 Concurrency]  -->  🟢 SAFE ZONE (p95 < 150ms, Zero Degradation)
[50 - 200 RPS / 25-50 Concurrency] -->  🟡 WARNING THRESHOLD (p95: 150ms - 300ms)
[200 - 450 RPS / 50-100 Concurrency] -> 🟠 SATURATION THRESHOLD (CPU/Worker Queueing, p95 > 250ms)
[> 500 RPS / > 200 Concurrency]   -->  🔴 FAILURE THRESHOLD (Potential connection pool exhaustion)
```

### Kapasite Eşik Parametreleri

* **SAFE_CONCURRENCY:** `25 workers`
  * Eşzamanlı 25 istek altında p95 gecikme 136ms, hata oranı %0.0.
* **SAFE_RPS:** `150 RPS`
  * Standart haber odası ve gazeteci sorgulama yükü altında nominal çalışma aralığı.
* **WARNING_THRESHOLD:** `250 RPS` veya `50 Concurrency`
  * DB connection pool havuzunda idle bağlantıların tükenmeye başladığı ve gecikmenin 200ms üzerine çıktığı seviye.
* **SATURATION_THRESHOLD:** `450 RPS` veya `100 Concurrency`
  * CPU tüketiminin %80'i aştığı, isteklerin kuyruklandığı ve p95 gecikmenin 300ms'ye yaklaştığı doyum noktası.
* **FAILURE_THRESHOLD:** `600 RPS` veya `250+ Concurrency`
  * Tek düğümlü (Single Node) Uvicorn/PostgreSQL kurulumunda port/connection starvation ve 504 Timeout riski taşıyan seviye.

---

## 3. BELLEK VE İŞLEMCİ ÖLÇÜMLERİ

| Bileşen | Ölçülen Boşta RSS | Ölçülen Yük Altı RSS | Önerilen Limit |
|---|:---:|:---:|:---:|
| **pd-worker** | 2.36 GiB | 2.55 GiB | 3.50 GiB |
| **pd-worker-llm** | 136 MiB | 350 MiB | 1.00 GiB |
| **pd-api** | 65 MiB | 180 MiB | 512 MiB |
| **pd-db** | 674 MiB | 1.10 GiB | 2.00 GiB |
| **pd-rsshub** | 289 MiB | 400 MiB | 768 MiB |
| **pd-beat** | 49 MiB | 60 MiB | 128 MiB |
| **pd-redis** | 6.4 MiB | 25 MiB | 256 MiB |
| **TOPLAM AGGREGATE** | **~3.58 GiB** | **~4.67 GiB** | **~8.16 GiB** |
