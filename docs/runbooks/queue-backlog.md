# Operational Runbook: Queue Backlog & Explosion (`queue-backlog.md`)

## 1. Symptom (Belirti)
- Redis içindeki Celery kuyruk derinliği (`celery` veya `llm`) hızla artıyor ve 100+ veya 500+ görev birikmiş durumda.
- Boru hattı aşamaları gecikiyor; yeni makaleler sisteme girmesine rağmen feed kartları saatlerce güncellenmiyor.
- `/admin/pipeline-health` üzerinde `claims` veya `cluster` aşamalarında yüksek birikme sayısı raporlanıyor.

---

## 2. Detection (Tespit)
- **SRE Telemetrisi:** `GET /admin/sre` uyarısı:
  ```json
  {"severity": "CRITICAL", "title": "Celery Kuyruk Patlaması (Queue Explosion)", "source": "queue"}
  ```
  veya:
  ```json
  {"severity": "WARNING", "title": "Celery Kuyruk Derinliği Yüksek", "source": "queue"}
  ```
- **Kuyruk Derinliği Sorgulaması:**
  ```powershell
  python -c "from politikdesk.sre_metrics import get_queue_depths; print(get_queue_depths())"
  ```

---

## 3. Diagnosis (Teşhis)
1. **Hangi Kuyrukta Birikme Var?**
   - `celery` kuyruğu mu (Embedding, NER, Kümeleme, Kanıt, Tarihsel Bağlam)?
   - `llm` kuyruğu mu (İddia Çıkarımı, Brifing Üretimi)?
2. **Kuyruk Tıkanıklığının Nedeni:**
   - **LLM Kuyruğu İçin:** NVIDIA NIM / upstream model sağlayıcısı HTTP 429 (Rate Limit) veya 503 mü veriyor? Günlük bütçe (`PD_LLM_DAILY_BUDGET_USD`) doldu mu?
   - **Default Kuyruk İçin:** `pd-worker` işçisi durdu mu veya veritabanı sorgusu kilitlendi mi?
3. **Kuyruk Loglarını İnceleyin:**
   ```powershell
   docker compose logs --tail 100 pd-worker
   docker compose logs --tail 100 pd-worker-llm
   ```

---

## 4. Immediate Mitigation (Acil Müdahale)
1. **İşçi Eşzamanlılığı ve Durumunu Kontrol Edin:**
   Eğer worker kilitlenmişse yeniden başlatın:
   ```powershell
   docker compose restart pd-worker pd-worker-llm
   ```
2. **Kuyruk Boşaltma Scriptini Çalıştırın:**
   ```powershell
   python -m scripts.drain_pipeline
   ```
3. **Eğer LLM Sağlayıcısı Kesintideyse:**
   LLM görevlerini atlayıp deterministik veritabanı ve NLP aşamalarını temizleyin:
   ```powershell
   python -m scripts.drain_pipeline --skip-llm
   ```

---

## 5. Recovery (Toparlanma)
1. **Kuyrukların Eridiğini Doğrulayın:**
   ```powershell
   python -c "from politikdesk.sre_metrics import get_queue_depths; print(get_queue_depths())"
   ```
2. **Aşama Sağlık Raporunu Alın:**
   ```powershell
   python -c "from politikdesk import pipeline_health as p; [print(f'{r.status:6} {r.label:24} bekleyen={r.backlog}') for r in p.stage_report()]"
   ```

---

## 6. Verification (Doğrulama)
- `GET /admin/sre` çağrısının `alerts` listesinde kuyruk uyarısının kalmadığını doğrulayın.
- Feed sayfasının (`/feed`) en son olayları doğru salience sıralamasıyla gösterdiğini teyit edin.

---

## 7. Postmortem Checklist (Olay Sonrası Kontrol Listesi)
- [ ] Kuyruk patlamasının tetikleyicisi neydi (anormal veri akışı, harici API yavaşlığı, worker çökmesi)?
- [ ] Celery beat `expires = 0.9 * interval` kuralı bayat görev birikmesini önledi mi?
- [ ] Kalıcı hata veren zehirli mesaj (poison pill) var mıydı?
