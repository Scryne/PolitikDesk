# POLITIKDESK — PHASE 25 PRODUCTION OBSERVABILITY & SECURITY AUDIT
**Tarih:** 2026-08-24T17:47:00Z  
**Kapsam:** Prometheus Metrikleri, Yapılandırılmış JSON Loglama, Alertmanager Kuralları ve Güvenlik/SSRF Katmanı  
**Durum:** 🟢 **OBSERVABILITY & SECURITY FULLY ACTIVE & CERTIFIED**  

---

## 1. PROMETHEUS METRİK ENDPOINT DENETİMİ (`/metrics`)

| Metrik Adı | Tip | Etiketler (Labels) | Açıklama |
|---|:---:|---|---|
| `pd_http_requests_total` | Counter | `method`, `handler`, `status` | HTTP istek sayısı ve HTTP durum kodları |
| `pd_http_request_duration_seconds` | Histogram | `handler` | Uç nokta yanıt gecikmesi (p50/p95/p99) |
| `pd_source_fetches_total` | Counter | `source_slug`, `status` | Canlı kaynak çekme denemeleri |
| `pd_source_latency_seconds` | Gauge | `source_slug` | Kaynak yanıt süreleri |
| `pd_source_sqs_score` | Gauge | `source_slug` | Kaynak Kalite Skoru (SQS 0-100) |
| `pd_articles_ingested_total` | Counter | `source_slug`, `kind` | Alınan makale sayısı |
| `pd_events_clustered_total` | Counter | `category`, `region` | Kümelenen olay sayısı |
| `pd_db_pool_connections` | Gauge | `state` (`idle`, `active`) | PostgreSQL bağlantı havuzu doluluğu |
| `pd_anomalies_detected_total` | Counter | `anomaly_type` | Tespit edilen anomali sayısı |

---

## 2. YAPILANDIRILMIŞ JSON LOGLAMA (STRUCTURED LOGGING)
Tüm servisler (`pd-api`, `pd-worker`, `pd-beat`) JSON formatında log üretir:
```json
{
  "timestamp": "2026-08-24T17:45:00.123456Z",
  "level": "info",
  "logger": "politikdesk.ingestion.pipeline",
  "event": "articles_ingested",
  "source_slug": "tcmb-haberler",
  "items_count": 5,
  "sqs": 98.0,
  "duration_ms": 124.5
}
```

---

## 3. PROMETHEUS ALARM KURALLARI (ALERT RULES)

1. **`SourceDegradedCritical`:** Bir kaynağın ardışık 3 cycle boyunca hata vermesi veya SQS skorunun 50 altına düşmesi.
2. **`FeedLatencyHigh`:** `/api/feed` p95 yanıt süresinin 500 ms eşiğini aşması.
3. **`DbPoolExhaustion`:** PostgreSQL bağlantı havuzunun %90'ın üzerinde dolu kalması.
4. **`IngestionGapsDetected`:** Beklenen resmi kurum takviminde 30 dakikadan fazla gecikme olması.

---

## 4. GÜVENLİK, SSRF VE EPISTEMIC GROUNDING DENETİMİ

- **SSRF Loopback Guard:** `politikdesk.ingestion.http` katmanında `UnsafeUrlError` devrededir; `localhost`, `127.0.0.1`, `10.0.0.0/8`, `169.254.169.254` adreslerine yapılan tüm istekler fail-closed engellenir.
- **CSP & Güvenlik Başlıkları:** `Content-Security-Policy: default-src 'self'`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`.
- **TCK 217/A & Epistemic Grounding Guard:** Spekülatif / doğrulanmamış iddialar `needs_review` bayrağı ile işaretlenir; uydurma iddialar asla canlı feed'e onaylı olarak çıkmaz.
