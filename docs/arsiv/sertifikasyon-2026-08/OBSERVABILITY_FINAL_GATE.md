# POLITIKDESK — OBSERVABILITY & SRE TRIAGE GATE (PHASE 27)

**Tarih:** 2026-08-24T21:35:00Z  
**Kapsam:** Yapılandırılmış Günlükler, Prometheus Metrikleri, Korelasyon Kimlikleri ve SRE Teşhis Kapasitesi  
**Durum:** 🟢 **OBSERVABILITY OPERATIONAL & TRIAGE READY (< 5 MINS)**

---

## 1. YAPILANDIRILMIŞ GÜNLÜKLEME VE KORELASYON

PolitikDesk, üretim ortamında JSON formatında (`structlog` / standart kütüphane JSON formatlayıcı) log üretir.

Her istek ve işlem için aşağıdaki bağlamsal alanlar otomatik olarak eklenir:
* `request_id`: Her HTTP isteği için üretilen benzersiz UUID
* `cycle_id`: İlgili yayın döngüsünün kimliği
* `source_slug`: Haber toplama adımında kaynak belirteci
* `event_id` / `claim_id`: İlgili varlık kimlikleri
* `duration_ms`: İşlem süresi (milisaniye)
* `error` / `exception`: Hata durumunda yığın izleme (stack trace)

---

## 2. PROMETHEUS METRİK DIŞA AKTARICI (`/metrics`)

PolitikDesk Prometheus dışa aktarıcısı aşağıdaki ana operasyonel metrikleri sağlar:

| Metrik Adı | Tip | Açıklama |
|---|---|---|
| `politikdesk_uptime_seconds` | Gauge | Sunucu ve servis çalışma süresi |
| `politikdesk_queue_depth{queue="..."}` | Gauge | Celery ve LLM kuyruklarındaki anlık bekleyen iş sayısı |
| `politikdesk_circuits_open` | Gauge | Açık (kesilmiş/devre dışı) kaynak devre kesici sayısı |
| `politikdesk_llm_budget_used_usd` | Gauge | Günlük tüketilen LLM harcaması (USD) |
| `politikdesk_llm_budget_limit_usd` | Gauge | Günlük azami LLM bütçe tavanı (USD) |
| `politikdesk_backup_age_hours` | Gauge | Son başarılı tam yedeğin üzerinden geçen saat |

---

## 3. OPERATÖR 5 DAKİKA TEŞHİS DEĞERLENDİRMESİ

Bir SRE / Operatör, olası bir kesinti anında aşağıdaki soruları 5 dakikadan kısa sürede cevaplayabilir:

| Soru | Teşhis Yolu & Komut | Beklenen Süre |
|---|---|:---:|
| **"Ne kırıldı?"** | `GET /metrics` veya `GET /api/v1/admin/sre/snapshot` | **< 30 saniye** |
| **"Ne zaman başladı?"** | JSON günlüklerindeki `timestamp` ve Prometheus spike zamanı | **< 1 dakika** |
| **"Hangi kaynak etkilendi?"** | `SELECT * FROM source_fetch_log WHERE succeeded = false;` | **< 1 dakika** |
| **"Kullanıcı istekleri etkilendi mi?"**| `request_id` ve HTTP 5xx logları | **< 2 dakika** |
| **"Kaç kayıt etkilendi?"** | `SELECT count(*) FROM articles WHERE created_at > ...;` | **< 2 dakika** |
| **"İyileşme gerçekleşiyor mu?"** | `/health/ready` ve `politikdesk_queue_depth` grafiği | **< 3 dakika** |
