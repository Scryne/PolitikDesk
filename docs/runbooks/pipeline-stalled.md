# Operational Runbook: Pipeline Stalled / Degraded (`pipeline-stalled.md`)

## 1. Symptom (Belirti)
- Boru hattının belirli bir aşamasında (`embed`, `entities`, `cluster`, `claims`, `evidence`, `context`, `political_relations`, `scheduler_match`) akış durmuş veya aşırı yavaşlamış.
- `/admin/pipeline-health` üzerinde bir veya daha fazla aşama Kırmızı (`red`) veya Sarı (`amber`) renkte alarm veriyor.
- Yeni toplanan makaleler olaylara dönüşmüyor veya olaylar tarihsel bağlamla ilişkilendirilmiyor.

---

## 2. Detection (Tespit)
- **Watchdog Taraması:**
  ```powershell
  python -m scripts.watchdog
  ```
- **Aşama Sağlık Raporu:**
  ```powershell
  python -c "from politikdesk import pipeline_health as p; [print(f'{r.status:6} {r.label:24} bekleyen={r.backlog} en_eski={r.oldest_hours} sa') for r in p.stage_report()]"
  ```
- **SRE Telemetrisi:** `GET /admin/sre` uyarısı:
  ```json
  {"severity": "CRITICAL", "title": "Boru Hattı Çoklu Aşama Kesintisi", "source": "pipeline"}
  ```

---

## 3. Diagnosis (Aşama Bazlı Teşhis Rehberi)

| Kırmızı Aşama | Olası Kök Neden | Teşhis Komutu |
|---|---|---|
| **Embedding (`embed`)** | `pd-worker` durdu veya embedding modeli yüklenemedi | `docker compose logs pd-worker` |
| **Varlık Çıkarımı (`entities`)** | NER kural istisnası veya worker kilitlenmesi | `python -m scripts.drain_pipeline` |
| **Olay Kümeleme (`cluster`)** | `pd-beat` zamanlaması çalışmıyor veya veritabanı kilitli | `docker compose logs pd-beat` |
| **İddia Çıkarımı (`claims`)** | LLM API hız sınırı (429), bütçe dolması veya LLM worker durması | `python -m scripts.llm_benchmark --quick` |
| **Kanıt Puanlaması (`evidence`)** | `pd-worker` durdu veya sürüm uyuşmazlığı | `docker compose restart pd-worker` |
| **Tarihsel Bağlam (`context`)** | `context-every-30-minutes` beat görevi çalışmıyor | `docker compose logs pd-beat` |
| **Siyasi İlişkiler (`political_relations`)** | `political-relations-every-15-minutes` beat görevi çalışmıyor | `docker compose logs pd-beat` |
| **Takvim Eşleştirmesi (`scheduler_match`)** | Resmî takvim olaylarında zaman aşımı veya eksik veri | `/admin/calendar` kontrolü |

---

## 4. Immediate Mitigation (Acil Müdahale)
1. **Adım 1 — Tüm Boru Hattını Sıralı Boşaltın (Drain Pipeline):**
   ```powershell
   python -m scripts.drain_pipeline
   ```
   *Bu araç aşamaları sırasıyla (Embed ➔ NER ➔ Kümele ➔ İddia ➔ Kanıt ➔ Bağlam ➔ Siyasi İlişkiler ➔ Takvim) çalıştırarak tıkanıklığı giderir.*

2. **Adım 2 — Beat ve Worker Servislerini Yeniden Başlatın:**
   ```powershell
   docker compose restart pd-worker pd-worker-llm pd-beat
   ```

---

## 5. Recovery & Verification (Toparlanma ve Doğrulama)
1. **Boru Hattı Sağlığını Yeniden Ölçün:**
   ```powershell
   python -c "from politikdesk import pipeline_health as p; [print(f'{r.status:6} {r.label:24} bekleyen={r.backlog} en_eski={r.oldest_hours}') for r in p.stage_report()]"
   ```
2. **Tüm Aşamaların Yeşil Olduğunu Doğrulayın:**
   - Bekleyen sayıların eridiğini ve en eski bekleme sürelerinin eşiklerin (`threshold_hours`) altına indiğini teyit edin.
3. **Watchdog'un Temiz Döndüğünü Görün:**
   ```powershell
   python -m scripts.watchdog
   ```

---

## 6. Postmortem Checklist (Olay Sonrası Kontrol Listesi)
- [ ] Tıkanıklık sistemik bir bug'dan mı yoksa geçici kaynak kesintisinden mi kaynaklandı?
- [ ] Arşiv verisi yüklenmesi durumunda yaş hesabı (`OPS-001`) doğru çalıştı mı?
- [ ] Celery worker loglarında unhandled exception veya deadlock var mıydı?
