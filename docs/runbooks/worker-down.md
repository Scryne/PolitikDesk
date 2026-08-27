# Operational Runbook: Worker Down (`worker-down.md`)

## 1. Symptom (Belirti)
- Celery işçisi (`pd-worker` veya `pd-worker-llm`) çalışmıyor veya çökmüş.
- Yeni toplanan makaleler gömülmüyor (`embed` aşamasında birikme), olaylar kümelenmiyor veya iddia çıkarımı (`claims`) durmuş durumda.
- `/admin/pipeline-health` üzerinde birden fazla aşama kırmızıya dönüyor.
- `scripts/watchdog.py` çıktısında `pd-worker` veya `pd-worker-llm` konteynerinin eksik veya durmuş olduğu bildiriliyor.

---

## 2. Detection (Tespit)
- **Watchdog Uyarısı:** `python -m scripts.watchdog` çıktısı:
  ```text
  [HATA] Eksik konteyner: pd-worker
  ```
- **SRE Telemetrisi:** `GET /admin/sre` uyarısı:
  ```json
  {"severity": "CRITICAL", "title": "Boru Hattı Çoklu Aşama Kesintisi", "source": "pipeline"}
  ```
- **Docker Durumu:**
  ```powershell
  docker compose ps
  ```

---

## 3. Diagnosis (Teşhis)
1. **Konteyner Durumunu İnceleyin:**
   ```powershell
   docker compose ps pd-worker pd-worker-llm
   ```
2. **Worker Hata Loglarını Okuyun:**
   ```powershell
   docker compose logs --tail 200 pd-worker
   docker compose logs --tail 200 pd-worker-llm
   ```
3. **Bellek / OOM Kontrolü:**
   Konteyner OOM (Out Of Memory) nedeniyle mi kapandı (`Exit 137`)?
   ```powershell
   docker inspect pd-worker --format='{{.State.OOMKilled}}'
   ```
4. **Veritabanı / Redis Bağlantı Hatası:**
   Loglarda `psycopg.OperationalError` veya `redis.exceptions.ConnectionError` var mı?

---

## 4. Immediate Mitigation (Acil Müdahale)
1. **Worker Konteynerlerini Yeniden Başlatın:**
   ```powershell
   docker compose restart pd-worker pd-worker-llm
   ```
2. **Konteynerler Kalkmıyorsa Yeniden Derleyerek Ayağa Kaldırın:**
   ```powershell
   docker compose --profile workers up -d --build
   ```

---

## 5. Recovery (Kurtarma & Kuyruk Boşaltma)
1. **İşçilerin Ayakta Olduğunu Doğrulayın:**
   ```powershell
   docker compose ps pd-worker pd-worker-llm
   ```
2. **Biriken Kuyruğu Sıralı Boşaltın (Pipeline Drain):**
   ```powershell
   python -m scripts.drain_pipeline
   ```
   *(Eğer LLM sağlayıcı hız sınırı varsa `--skip-llm` veya `--max-llm-events 50` ile çalıştırabilirsiniz).*

---

## 6. Verification (Doğrulama)
1. **Boru Hattı Sağlığını Kontrol Edin:**
   ```powershell
   python -c "from politikdesk import pipeline_health as p; [print(f'{r.status:6} {r.label:24} bekleyen={r.backlog}') for r in p.stage_report()]"
   ```
   Tüm aşamaların `green` (veya normal sınırlar içinde) olduğunu teyit edin.
2. **SRE Telemetrisini Doğrulayın:**
   `GET /admin/sre` çağrısının `"Tüm Sistemler Nominal"` (INFO) döndüğünü görün.
3. **Watchdog Kontrolü:**
   ```powershell
   python -m scripts.watchdog
   ```

---

## 7. Postmortem Checklist (Olay Sonrası Kontrol Listesi)
- [ ] Çökmenin nedeni belgelendi mi (OOM, unhandled exception, network timeout)?
- [ ] Celery `task_soft_time_limit` ve `task_time_limit` sınırları aşıldı mı?
- [ ] Kayıp veya askıda kalan görev var mı (`task_acks_late=True` sayesinde kayıp olmamalı)?
- [ ] `audit_log` üzerinde anomali kaydı var mı?
