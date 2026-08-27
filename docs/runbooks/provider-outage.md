# Operational Runbook: LLM Provider Degradation & Outage (`provider-outage.md`)

## 1. Symptom (Belirti)
- Harici LLM sağlayıcısı (NVIDIA NIM veya Anthropic) HTTP 429 (Rate Limit / Quota Exceeded), HTTP 503 (Service Unavailable) veya zaman aşımı (Timeout) döndürüyor.
- `/admin/pipeline-health` üzerinde `claims` (İddia çıkarımı) aşamasında birikme artıyor.
- `POST /api/events/{id}/drafts` istekleri 502 (Bad Gateway / LLMError) veya 429 (Bütçe Aşıldı) dönüyor.
- Deterministik pipeline (Toplama, Embedding, NER, Kümeleme, Kanıt, Siyasi İlişkiler) çalışmaya devam ediyor ancak yeni iddialar ve editoryal taslaklar üretilemiyor.

---

## 2. Detection (Tespit)
- **API Hata Kodları:** `LLMHTTPError (429 / 503 / 504)`
- **SRE Telemetrisi:** `GET /admin/sre` uyarısı:
  ```json
  {"severity": "WARNING", "title": "Boru Hattı Aşama Birikmesi", "detail": "İddia çıkarımı (claims)", "source": "pipeline"}
  ```
- **Konteyner Logları:**
  ```powershell
  docker compose logs --tail 100 pd-worker-llm
  ```

---

## 3. Diagnosis (Teşhis)
1. **Model ve Uç Nokta Yanıtını Kontrol Edin:**
   ```powershell
   python -m scripts.llm_benchmark --task extraction --quick
   ```
2. **Günlük Harcama ve Bütçe Durumu:**
   ```powershell
   python -c "from politikdesk.llm.budget import BudgetGuard; print(BudgetGuard().status())"
   ```
3. **API Anahtarı ve Kotası:**
   - NVIDIA NIM dashboard üzerinden API anahtarının aktif ve kota durumunun geçerli olduğunu doğrulayın.

---

## 4. Immediate Mitigation (Acil Müdahale & Kontrollü Degradasyon)
1. **Sistemik Güvenlik (Fail-Safe Davranışı):**
   - PolitikDesk mimarisi gereği LLM arızaları `evidence/` deterministik kurallarını ETKİLEMEZ.
   - `claims_pipeline.py` içindeki `_is_transient` fonksiyonu, sağlayıcı kaynaklı geçici hatalarda olayların deneme hakkını (`claims_attempt_count`) YAKMAZ; güvenle bekler.
2. **Kuyruk Ayrımı Güvencesi:**
   - LLM işleri ayrık `llm` kuyruğundadır (`pd-worker-llm`).
   - Ana `pd-worker` veritabanı, haber toplama ve kümeleme işlemlerini kesintisiz sürdürür.
3. **Geçici Olarak Yerel / Alternatif Modele Geçiş (İsteğe Bağlı):**
   Eğer yerel Ollama / vLLM kurulduysa `.env` dosyasında:
   ```dotenv
   PD_LLM_OPENAI_BASE_URL=http://localhost:11434/v1
   PD_LLM_EXTRACTION_MODEL=llama3.2:3b
   ```
   olarak güncellenip worker yeniden başlatılabilir.

---

## 5. Recovery (Sağlayıcı Döndüğünde Toparlanma)
1. **Sağlayıcı Ayakta mı Doğrulayın:**
   ```powershell
   python -m scripts.llm_benchmark --task extraction --quick
   ```
2. **Biriken İddia Kuyruğunu Kontrollü Boşaltın:**
   ```powershell
   python -m scripts.drain_pipeline --max-llm-events 100
   ```

---

## 6. Verification (Doğrulama)
- `/admin/pipeline-health` sayfasında `İddia çıkarımı` aşamasının yeşile döndüğünü doğrulayın.
- Olay detay sayfasında (`/event/{id}`) yeni taslak üretiminin (`can_generate`) 200 OK döndüğünü ve taslak üretilebildiğini teyit edin.

---

## 7. Postmortem Checklist (Olay Sonrası Kontrol Listesi)
- [ ] Kesinti süresince `claims_attempt_count` haksız yere arttı mı?
- [ ] Günlük bütçe tavanı doğru şekilde korundu mu?
- [ ] `llm_calls` tablosunda hata kayıtları doğru kodlarla kaydedildi mi?
