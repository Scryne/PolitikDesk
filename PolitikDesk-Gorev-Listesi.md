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

- [x] **Söylem Değişikliği ve Çelişki Radarı (Stance Shift Detector)**
  `politikdesk/political_memory/stance_shift.py`
  İlişki zincirlerinden (`contradicts`/`fails`), morfolojik kutup
  zıtlığından ve sayısal sapmadan üç ayrı sinyal üretiliyor;
  `/api/memory/stance-shifts` ve `/hafiza/{aktör}` ekranlarına bağlı.
  18 Ağu 2026: kutup çıkarımı çift başına değil kayıt başına
  hesaplanacak şekilde düzeltildi (5,2 sn → 0,7 sn, çıktı aynı).

- [ ] **Derin Belge Özümseyici (Document Deep-Dive)**
  TBMM kanun teklifi / Sayıştay raporu PDF'lerindeki bulguları otomatik
  olarak ilgili aktörün siciline bağlayıp `accountability_view`'a aktar.

- [x] **Karşı Görüş ve Kör Nokta Uyarısı (Blindspot & Framing Alert)**
  `politikdesk/evidence/blindspot.py`, `politikdesk/web/event.py`
  `analyze_blindspot()` beş şiddet düzeyi (`balanced`, `mainstream_only`,
  `independent_only`, `single_source`, `minimal`) üretiyor; olay
  sayfasındaki "Medya Kapsamı ve Kör Nokta Radarı" kartı kademe dağılımı
  ve kapsama oranıyla birlikte gösteriyor. `/api/events/{id}/blindspot`.

- [x] **Çok Kanallı Editoryal Dışa Aktarım (Omnichannel Export)**
  `politikdesk/web/export_formats.py`, `politikdesk/web/event.py`
  11 kanal (Markdown, düz metin, JSON, SVG kart, X zinciri, Bluesky,
  Mastodon, LinkedIn, Telegram/WhatsApp, Substack e-bülten, seslendirme
  metni). 18 Ağu 2026: yedi kanalın API'de var olup arayüzde hiçbir
  bağlantısı olmadığı tespit edildi; olay sayfasına "Dışa aktarım
  kanalları" kartı eklendi ve ayrışma testle kilitlendi.

- [x] **TÜİK/TCMB Sparkline Grafikleri**
  `politikdesk/web/ui/charts.py`
  Hafif, bağımsız satır içi SVG sparkline mini eğilim grafiği bileşeni (`sparkline()`) eklendi (`tests/test_accountability.py`).

- [x] **Dışa Aktarılabilir "Kanıt Kartı" Görseli**
  `politikdesk/web/api.py`
  R0–R8 motorunun ürettiği kanıt durumu, kaynak dağılımı ve iddiaları yapılandırılmış sosyal medya kartı formatında dönen `/api/events/{id}/evidence-card` uç noktası eklendi.

---

## 🔬 18 Ağustos 2026 Tam Kapsam Denetimi — Kapatılan Bulgular

- [x] **D-01 · Kumanda odasında uydurma makro göstergeler (KRİTİK)**
  `politikdesk/web/war_room.py`
  Gösterge kartları koda gömülü sayılar gösteriyor ve bunları
  TCMB / TÜİK SDMX / Hazine imzasıyla sunuyordu ("Politika Faizi %45,00",
  "Yıllık TÜFE %58,2", "BIST 100: 10.250"). Spec §15/13 ve
  `editorial/grounding_check.py` kanıtta bulunmayan sayıyı yasaklar;
  kurum imzalı uydurma sayı bu yasağın en ağır ihlaliydi.
  → Tek kaynak `articles.official_value` oldu
  (`repository.official_indicator_series`). Veri yoksa hiçbir sayı
  üretilmiyor, dürüst boş durum gösteriliyor. `war_room.py` içinde kayan
  noktalı sabit bulunmasını yasaklayan test eklendi.

- [x] **D-02 · Komuta paletinin aktör araması hiç çalışmıyordu**
  `politikdesk/web/ui/shell.py`
  Palet `data.items` / `act.actor_name` okuyordu; `service.search_actors`
  sözleşmesi `{actors: [{name, entity_type}]}`. Üç anahtar da yanlıştı,
  arama sessizce hiç sonuç döndürmüyordu — ne hata veriyordu ne sonuç.

- [x] **D-03 · Aktör adlarının `innerHTML` ile basılması (saklı XSS)**
  `politikdesk/web/ui/shell.py`
  Aktör adları NER ile dış kaynaklı makale metninden çıkarılır. D-02
  düzeltilince bu yol canlanacaktı; `textContent` ile DOM düğümü
  kurmaya çevrildi.

- [x] **D-04 · Kesme işareti kopyala düğmesini bozuyordu**
  `politikdesk/web/feed.py`
  `onclick` özniteliği tek tırnakla açılıyor, taslak gövdesi
  `json.dumps` ile içine gömülüyordu. JSON kaçışı tek tırnağı kaçırmaz;
  Türkçede kesme işareti kural olduğu için ("Silivri'deki",
  "Mahkemesi'nde") düğme pratikte HER taslakta bozuluyordu ve kalan
  metin işaretleme olarak ayrıştırılıyordu. Sunucu tarafında `esc()`,
  istemci tarafında DOM kurulumu.

- [x] **D-05 · İddia çıkarımı alarmı yapısal olarak kalıcı kırmızıydı**
  `politikdesk/pipeline_health.py`
  Yaş ölçütü `min(last_update_at)` idi. Kuyruk `last_update_at DESC`
  işlenir (eski uç KASTEN sonda bekler) ve geriye dönük yüklenen
  Sayıştay/TBMM arşivinde bu alan belgenin kendi tarihidir. Ölçülen yaş
  94.617 saat (~10,8 yıl) çıkıyor, alarm yeşile dönemiyordu — oysa iddia
  çıkarımı 16 dakika önce koşmuştu. Modülün kendi kuralı: *"Yanlış alarm
  veren bir alarm kapatılır."* Ölçüt işçi canlılığına
  (`max(claims_attempted_at)`) bağlandı; birikme sayısı bilgi olarak kaldı.

- [x] **D-06 · Veritabanı testleri test sırasına göre sessizce atlanıyordu**
  `tests/conftest.py`
  `Settings.model_config["env_file"] = None` `.env`'i engellediğini
  sanıyordu; `config.get_settings()` her çağrısında `load_env_file()` ile
  `.env`'i doğrudan `os.environ`'a kopyalıyor. `pytest` 65 DB testini
  koşuyor, `pytest tests/test_schema.py` aynı testlerin 9'unu atlıyordu —
  aralarında alıntı 300 karakter sınırı ve tam metin saklama yasağını
  koruyanlar vardı. `.env` artık `conftest`'te açıkça, tek seferde
  yükleniyor; regresyon testi `tests/test_packaging.py`'de.

- [x] **D-07 · Test artığı canlı veritabanına aktif kaynak olarak sızmıştı**
  `tests/test_schema.py`, `tests/conftest.py`
  `db_conn` fixture'ı `autocommit=True` bağlanır, dolayısıyla testteki
  `rollback()` çağrıları etkisizdir. `test-excerpt-src` canlı veritabanında
  **aktif bir Tier-1 kaynak** olarak kalmış, toplayıcı onu 5 dakikada bir
  çekmeye çalışıyor ve sağlık panosunda kalıcı kırmızı gösteriyordu.
  Kaynak artık `pytest-` önekiyle ve `is_active = false` ekleniyor;
  süpürge `test-%` desenini de siliyor.

- [x] **D-08 · Yedi dışa aktarım kanalı arayüzden erişilemiyordu**
  `politikdesk/web/event.py` — bkz. Omnichannel Export maddesi.

- [x] **D-09 · Kumanda odası kılavuzu çalışmayan kısayol reklamı yapıyordu**
  `politikdesk/web/war_room.py`
  J / K / X kısayolları yalnızca `/feed` dinleyicisine bağlı; bu ekranda
  hiçbir şey yapmıyorlardı. Liste bu sayfada gerçekten çalışanlarla
  sınırlandı, diğerleri için `/feed`'e yönlendirme eklendi.

- [x] **D-10 · Content-Security-Policy başlığı yoktu**
  `politikdesk/api/main.py`
  "Sıfır harici CSS/CDN" sözü (DESIGN.md 6.1) yalnızca disiplinle
  tutuluyordu. `default-src 'self'`, `connect-src 'self'`,
  `object-src 'none'`, `base-uri 'self'` eklendi; artık yanlışlıkla
  eklenen bir CDN bağlantısını tarayıcı reddediyor.

- [x] **D-11 · Söylem değişikliği taraması O(n²) yeniden hesap yapıyordu**
  `politikdesk/political_memory/stance_shift.py`
  `/api/memory/stance-shifts` 5,2 saniye sürüyordu (olay sayfası hedefi
  p95 < 1,5 sn). Kutup vektörü ve metrik ayrıştırması kayıt başına
  ön-hesaba alındı: 0,66 sn, çıktı birebir aynı (29 kayıt).

- [x] **D-12 · Kanıt etiketi tablosu üç yerde kopyalanmıştı**
  `politikdesk/web/api.py` → `export_formats.STATUS_LABELS` tek kaynak.

### Denetimde bulunan, KOD DIŞI (ortam/işletim) sorunlar

- [ ] **O-01 · Üç `.gov.tr` kaynağında TLS el sıkışma hatası**
  `resmi-gazete` (KIRMIZI, 15 Ağu'dan beri), `sayistay`, `cb-kararname`
  hepsi aynı imzayı veriyor:
  `SSL: UNEXPECTED_EOF_WHILE_READING`. Üç farklı konakta aynı hata,
  `config/sources.yml`'de kayıtlı GoodbyeDPI/DPI-atlatma senaryosunun
  imzasıdır (TLS ClientHello parçalanması). Makinede böyle bir araç
  çalışıyorsa kapatılıp yeniden denenmeli.

- [ ] **O-02 · RSSHub köprüsü (`rsshub:1200`) zaman aşımına uğruyor**
  Devre kesici açık; 9 X kaynağı hiç veri alamadı, ~41'i amber.
  Devre kesici tasarlandığı gibi çalışıyor — sorun köprü servisinde.

- [ ] **O-03 · Canlı veritabanındaki test artıkları temizlenmeli**
  Kod düzeltildi ama mevcut satırlar duruyor. Tek seferlik:
  `DELETE FROM sources WHERE slug IN ('test-excerpt-src','test-phase5-src');`
  (ikisinin de makale sayısı 0'dır, kontrol edildi)

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
