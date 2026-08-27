# POLITIKDESK — PRODUCTION SLO & ALERTING SPECIFICATION (PHASE 27)

**Tarih:** 2026-08-24T21:35:00Z  
**Kapsam:** Hizmet Seviyesi Hedefleri (SLO), Göstergeleri (SLI) ve Çok Seviyeli Uyarı Eşikleri  
**Durum:** 🟢 **PRODUCTION BASELINE SLO DEFINED & CALIBRATED**

---

## 1. HİZMET SEVİYESİ HEDEFLERİ (SLO) MATRİSİ

Aşağıdaki tablo PolitikDesk üretim ortamı için tanımlanmış ve ölçülmüş nominal, uyarı ve kritik eşikleri içerir:

| Servis / Alan | Metrik (SLI) | 🟢 Nominal (GREEN) | 🟡 Uyarı (WARNING) | 🔴 Kritik (CRITICAL) |
|---|---|:---:|:---:|:---:|
| **API Erişilebilirliği** | Uptime / HTTP 2xx-3xx (%) | **>= 99.9%** | `< 99.5%` | `< 99.0%` |
| **Gündem Akış Gecikmesi**| Feed p95 Yanıt Süresi | **< 150 ms** | `150 - 300 ms` | `> 500 ms` |
| **Arama Gecikmesi** | Search p95 Yanıt Süresi | **< 200 ms** | `200 - 400 ms` | `> 800 ms` |
| **Haber Tazeliği** | Medyan Ingestion Delay | **< 5 dakika** | `5 - 15 dakika` | `> 30 dakika` |
| **Kaynak Erişilebilirliği**| Aktif Kaynak Fetch Başarısı | **>= 98.0%** | `95.0% - 98.0%` | `< 95.0%` |
| **Celery Kuyruk Derinliği**| Toplam Bekleyen Görev (`LLEN`)| **< 50** | `50 - 200` | `> 500` |
| **DB Bağlantı Havuzu** | Aktif Bağlantı Sayısı | **< 20** | `20 - 40` | `> 50` |
| **Sistem Bellek RSS** | Toplam Bellek Kullanımı | **< 6.0 GiB** | `6.0 - 8.0 GiB` | `> 10.0 GiB` |
| **CPU Kullanımı** | Küme Ortalama CPU Yükü | **< 40%** | `40% - 75%` | `> 85%` |
| **HTTP Hata Oranı** | 5xx Hata Yüzdesi | **< 0.1%** | `0.1% - 1.0%` | `> 2.0%` |

---

## 2. UYARI VE ALARM POLİTİKASI (ALERT RULES)

### 🔴 Kritik Alarmlar (Sayfalama / Acil Müdahale):
1. **`PolitikDeskAPIDown`**: API `/health/live` art arda 3 kontrolde başarısız (Süre: 30 sn).
2. **`CeleryQueueExplosion`**: Toplam kuyruk derinliği > 500 ve 5 dakika boyunca azalmıyor.
3. **`DatabaseConnectionExhaustion`**: Aktif bağlantı havuzu azami kapasitenin %90'ına ulaştı.
4. **`DisasterRecoveryBackupOverdue`**: Son başarılı tam yedeğin üzerinden > 24 saat geçti.

### 🟡 Uyarı Alarmlar (Bilet Açma / Gün İçi İnceleme):
1. **`SourceDegradationWarning`**: Bir kaynağın devre kesicisi açık (`circuits_open > 0`).
2. **`LLMBudgetWarning`**: Günlük LLM harcaması bütçe tavanının %80'ine ulaştı.
3. **`MemoryHeadroomWarning`**: Sunucu bellek tüketimi 8.0 GiB eşiğini aştı.
