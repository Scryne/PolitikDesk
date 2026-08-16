# PolitikDesk — Aksiyon Planı Görev Listesi

> Bu liste, PolitikDesk kod denetim raporundaki bulgulardan üretilmiştir.
> Bir madde tamamlandığında `- [ ]` yerine `- [x]` yazman yeterli.

---

## 🔴 Kritik / Kısa Vadeli (1-2 Hafta — G4′ Kapanış Dönemi)

- [x] **API Token Üretim Zorunluluğu**
  `politikdesk/config.py`
  `env == "production"` iken `api_token` boşsa uygulamanın ayağa
  kalkmasını engelleyen bir Pydantic `model_validator` eklendi (`tests/test_config_and_api.py`).

- [x] **Editoryal Duruş Prompt Güvenliği (Prompt Injection)**
  `politikdesk/editorial/stance.py`
  `editorial_stance.md` dosyasından okunan metne 2000 karakter sınırı,
  kırpma uyarısı, `<user_editorial_stance>` XML etiket izolasyonu ve etiket sanitizasyonu uygulandı (`tests/test_editorial.py`).

- [x] **Kullanılmayan `anthropic` Bağımlılığının Temizlenmesi**
  `pyproject.toml`
  `anthropic` paketi ana bağımlılıklardan çıkarılarak `optional-dependencies` grubuna taşındı.

- [ ] **G4′ Gözlem ve SMTP Testlerinin Tamamlanması**
  `yol-haritasi-g4-kapanisi.md` — AŞAMA 2
  7 günlük snapshot ve 14 brifing slotu takibini tamamlayıp G4′ kapısını
  resmen kapat.

---

## 🟡 Orta Vadeli (1-2 Ay — Faz 5 / S3 Stabilizasyonu)

- [x] **Sunucu Taraflı Arama ve Sayfalama**
  `politikdesk/political_memory/service.py`, `politikdesk/web/api.py`
  Sunucu taraflı parametrik arama ve sayfalama fonksiyonları (`search_actors`, `search_accountability`) ve REST API uç noktaları (`/api/memory/actors`, `/api/accountability/search`) eklendi.

- [x] **Bağlantı Havuzu Yapılandırmasının Dinamikleştirilmesi**
  `politikdesk/db.py`, `politikdesk/config.py`
  `PD_DB_POOL_MIN` ve `PD_DB_POOL_MAX` ayarları `Settings` sınıfına eklendi; `get_pool()` havuz boyutunu dinamik okuyor.

- [x] **Otomasyon Script Eşitleme Denetimi**
  `pd.cmd` vs `Makefile`
  `pd.cmd` içindeki eksik `:cmd_metrics` eklendi; `tests/test_packaging.py` içine iki dosyanın komut senkronizasyonunu denetleyen test eklendi.

---

## 🔵 Uzun Vadeli (3-6 Ay — Faz 6 & İleri Vizyon)

- [ ] **Dış Politika ve Çok Dilli Dikey Genişlemesi**
  Mevcut `multilingual-e5-large` embedding üzerinden yabancı haber
  kaynaklarını (Reuters, Bloomberg Global) çeviri katmanıyla çapraz
  teyide dahil et.

- [ ] **Etkileşimli Siyasi İlişki Grafiği (Visual Memory Graph)**
  Sayıştay raporları, TBMM oylamaları ve vaatler arasındaki zinciri
  görselleştiren hafif bir SVG/Canvas ağ grafiği bileşeni.

- [ ] **PWA Desteği ve Mobil Bildirimler**
  Web arayüzünü Service Worker ile PWA haline getirip sabah/akşam
  brifinglerini mobil bildirim olarak ilet.

---

## 🧹 Düşük Öncelik / Bakım

- [x] **Tip Uyumsuzluğu Temizliği**
  `politikdesk/web/briefing.py`, `politikdesk/tasks.py`
  `slot` parametresi `Literal["morning", "evening"]` ile tip korumalı yapıldı, eksik `icon` importu giderildi, `mypy` 0 hata ile 153 dosyayı doğruladı.

- [x] **`relation_engine.py` Modül Bölünmesi & Import Temizliği**
  `politikdesk/political_memory/models.py`, `scoring.py`, `relation_engine.py`
  1040 satırlık monolitik motor `models.py` ve `scoring.py` alt modüllerine ayrıldı; atıl importlar (`F401`, `I001`) temizlendi, `ruff` sıfır hata ile geçti.

- [x] **SSE Canlı Akış Bağlantı Güvenliği & Bellek Koruması**
  `politikdesk/web/live_events.py`, `tests/test_live_events.py`
  İstemci bağlantı kopmalarında (`GeneratorExit`) abonenin hub'dan düşürülmesi garanti altına alındı ve test edildi.

- [x] **Veritabanı Bileşik İndeksleme (S3/S4 Performans)**
  `migrations/0015_composite_indexes.sql`
  `claims(event_id, evidence_status)` ve `event_relations(from_event_id, relation)` bileşik indeksleri eklendi.

---

## 💡 Yeni Özellik Backlog'u (Ürün Değeri)

- [ ] **Söylem Değişikliği ve Çelişki Radarı (Stance Shift Detector)**
  Bir aktörün geçmiş beyanı ile bugünkü tutumu arasındaki 180°
  değişimleri otomatik yakala.

- [ ] **Derin Belge Özümseyici (Document Deep-Dive)**
  TBMM kanun teklifi / Sayıştay raporu PDF'lerindeki bulguları otomatik
  olarak ilgili aktörün siciline bağlayıp `accountability_view`'a aktar.

- [ ] **Karşı Görüş ve Kör Nokta Uyarısı (Blindspot & Framing Alert)**
  Bir olay tek bir yayın grubu tarafından çerçeveleniyorsa gazeteciyi
  uyar.

- [x] **TÜİK/TCMB Sparkline Grafikleri**
  `politikdesk/web/ui/charts.py`
  Hafif, bağımsız satır içi SVG sparkline mini eğilim grafiği bileşeni (`sparkline()`) eklendi (`tests/test_accountability.py`).

- [x] **Dışa Aktarılabilir "Kanıt Kartı" Görseli**
  `politikdesk/web/api.py`
  R0–R8 motorunun ürettiği kanıt durumu, kaynak dağılımı ve iddiaları yapılandırılmış sosyal medya kartı formatında dönen `/api/events/{id}/evidence-card` uç noktası eklendi.

---

## 🧭 Stratejik Teknik Yol Haritası

- [ ] **Model Bağımsızlığı / Yerel Inference**
  LLM çıkarım adımlarını VPS üzerinde çalışabilecek açık modellerle
  (Llama-3.1-8B, Qwen-2.5-7B) sıfır API maliyetiyle yerelde koştur.

- [ ] **Graph RAG / Knowledge Graph Genişlemesi**
  `event_relations` tablosunu PostgreSQL recursive graph sorgularıyla
  zenginleştir.

---

## ❓ Netleştirilmesi Gereken Sorular (Karar Bekliyor)

- [ ] Üretim dağıtım ortamı: yerel Docker Compose mi, dış VPS mi?
- [ ] X (Twitter) API entegrasyon politikası — resmî API mi, Web Intent
      köprüsünde mi kalınacak?
- [ ] NVIDIA NIM kota/hız sınırına takılırsa yerel vLLM/Ollama fallback
      planlanıyor mu?

---

## Genel Puanlama (Referans)

| Alan | Puan |
| :--- | :---: |
| Mimari Tasarım | 9.8 / 10 |
| Kod Kalitesi & Standartlar | 9.8 / 10 |
| Güvenlik & Gizlilik | 9.6 / 10 |
| Performans & Optimizasyon | 9.5 / 10 |
| Test & Kalite Güvencesi | 9.8 / 10 |
| Dokümantasyon & DX | 9.8 / 10 |
| **Genel Ortalama** | **9.7 / 10** |
