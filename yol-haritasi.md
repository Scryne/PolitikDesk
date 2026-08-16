# Proje Yol Haritası — G4′ Kapanışı ve "Tamamlandı" Tanımına Giden Yol

**Rapor tarihi:** 15 Ağustos 2026, ~20:00 UTC
**Belge amacı:** 15 Ağustos ölçüm raporunda tespit edilen tüm eksik, hata ve açık kalemleri kapatmak için tek referans nokta.
**Kullanım şekli:** Her madde bir görev kartıdır. Sorumlu, tetikleyici tarih ve "kapanış kriteri" birlikte verilmiştir. Bir madde tamamlandığında kutuyu işaretle, tarihi ve kanıtı (komut çıktısı, log, ekran görüntüsü) not düş.

---

## 0. Tek Cümlelik Durum

Proje teknik olarak hazır (kod, mimari, container'lar, CI yeşil); darboğaz **ölçüm ve gözlem süresi**. Kritik yol tek bir insan eylemine bağlı: **günde ~5 olay incelemesi**. Bunu her gün yapmazsan 22 Ağustos tarihi kayar.

---

## 1. Kritik Yol (Bunu Atlarsan Her Şey Gecikir)

> ⚠️ Aşağıdaki madde, tüm G4′ kapanışının tarihini belirleyen tek kullanıcı işidir. Diğer her şey ya sistemin kendi kendine yaptığı bir iş ya da takvimin geçmesini beklemek.

- [ ] **Correction rate için 34 olay incelemesi (n=1 → n=34)** — *(15 Ağu 2026 23:40 UTC: G4′ temiz pencerede 4/34 incelendi, kalan: 30, itiraz: 0, correction rate: %0.00. `pd correction` ile izleniyor)*
  - **Neden kritik:** G4′-3 kapısı hedefi ≤%3, n≥34 incelenmiş olay.
  - **İki Farklı Metrik Ayrımı:**
    1. **G4′-3 Kapı Ölçümü (`scripts.correction_report`):** 15 Ağustos 13:00 UTC sıfırlamasından itibaren açılan olayları ve verilen geri bildirimleri sayar. Şu an: **4/34 incelendi, 0 itiraz, %0.00 hata**. G4′-3 kapısının resmî kapanış kriteri **bu metriktir**.
    2. **Genel Ürün Panosu 7 Günlük Kayan Rollup (`scripts.ingest metrics`):** Son 7 günün tamamına (9–15 Ağustos) bakar; 13 Ağustos'ta girilen 1 adet test itirazını içerdiği için **%14.29 (1/7)** görünür. 20 Ağustos'ta 13 Ağustos pencereden çıkınca ve örneklem 34'e yaklaştıkça bu iki değer birbirine yakınsayacaktır.
  - **Nasıl:** `pd feed` üzerinden günde ~5 olay incele, her biri için doğru/yanlış geri bildirimini `event_feedback` tablosuna işle.
  - **Ritim:** 15–21 Ağustos arası her gün ~5 olay (7 gün × 5 = 35 ≥ 30 kalan).
  - **Kapanış kriteri:** `pd correction` komutu n≥34 ile ≤%3 sonucu döndürdüğünde kapı 🟢 olur.
  - **Yan fayda:** Bu iş aynı zamanda B-75 üretim kapısı örneklemini (madde 6) de doğal olarak biriktirir — ayrı bir efor gerekmiyor.

---

## 2. G4′ Kapanışını Bloklayan 4 Kalem (Hedef: 22 Ağustos 13:00 UTC)

| # | Görev | Sorumlu | Süre/Tarih | Kalan | Kapanış Kriteri |
|---|-------|---------|------------|-------|------------------|
| 1 | Günlük snapshot alma | Sistem | 16–22 Ağu, her gün | 6 snapshot | `scripts/g4_snapshot.py --git-commit` her gün koşuyor ve `docs/G4-SNAPSHOTS.md`'e ekleniyor (Windows Görevi 23:55: 23:55 otomatik koşumu sonuc=0 ile tamamlandı; Task Scheduler üzerinden tetikleme testi commit üretti: `add3a3e7`) |
| 2 | 24 saatlik temiz pencerede arıza oranı ölçümü | Sistem | 16 Ağu 13:00 UTC sonrası | — | 16 Ağu 13:00 UTC'de başlayacak ilk 24h pencere sonrası kaynak tablosu üretilir, arıza ≤%2 ise kapı kapanır |
| 3 | Correction rate: 34 olay incelemesi | **Kullanıcı** | 7 gün, bugün başla | 30 olay | Bkz. Bölüm 1 — kritik yol (G4′ penceresinde 4/34 incelendi, %0.00) |
| 4 | 14 brifing slotunun teslimi | Takvim + izleme | 16–22 Ağu, 08:00/20:00 slotları | 13 slot | Tüm slotlar `send_error=null` ile gitmiş olmalı (Slot #140 teslim edildi) |

- [ ] Madde 1 — Snapshot günlüğü tam (1/7 — Gün 0 `docs/G4-SNAPSHOTS.md`'de kayıtlı ve git'e commit edildi; `windows_schedule.ps1`'e 23:55 görevi kuruldu ve otomatik koşum sonuc=0 ile doğrulandı)
- [ ] Madde 2 — 24h temiz pencere arıza oranı ≤%2 doğrulandı (Henüz ölçülmedi — ilk 24h temiz pencere 16 Ağu 13:00 UTC'de dolacak. *Not: Snapshot'taki %4.75 (116 hata) son 24 saatin tamamına bakar ve 116 hatanın tamamı 15 Ağustos 13:00 UTC sıfırlama öncesine aittir; sıfırlama sonrası 16 kaynaktan 1497/1497 çekim %0.00 hata ile devam etmektedir*)
- [ ] Madde 3 — 34 olay incelemesi tamamlandı, correction rate ≤%3 (G4′ penceresi: 4/34 incelendi, %0.00 hata)
- [ ] Madde 4 — 14/14 brifing slotu send_error=null ile teslim edildi (15 Ağu akşam brifingi #140 başarıyla teslim edildi)

---

## 3. Diversity Kapısı (Kod Hazır, Ölçüm Eksik)

- [ ] **5. Üretim diversity_ratio'sunu yeniden ölç** — 🟡 **AÇIK / KAPI HENÜZ KAPANMADI**
  - B-81 (cross-source matcher) ve B-82 (tarih/number tiplemesi) devreye girdikten sonra ölçüldü: **1,86 grup (n=7 olay)**.
  - **Hedef:** `≥ 2,5 grup` ve `n ≥ 10 olay` (POLITIKDESK-FAZ-FAZ-YOL-HARITASI.md gereği).
  - **Durum:** Hem oran yetersiz (1.86 < 2.50) hem örneklem büyüklüğü eksik (n = 7 < 10).
  - **Aksiyon:** 22 Ağustos'a kadar yeni çok-kaynaklı olay incelemeleri ve kümeleme akışıyla takip edilecek.

- [ ] **6. B-75 üretim kapısı örneklemi (17 → 40 taslak + 50 üretim örneği)**
  - Kalan: 23 taslak.
  - **Aksiyon gerekmiyor ayrıca** — madde 3'teki günlük feed kullanımıyla doğal olarak birikiyor. Sadece takip et.

---

## 4. G4′ Resmî Kapanışı — 22 Ağustos 13:00 UTC Checklist'i

Bu adımlar yalnızca Bölüm 2 ve 3 tamamlandıktan sonra yapılabilir.

- [ ] **7.** 6 kapıyı (G4′-1 … G4′-9) tek tabloda topla, tarih + Git SHA ile damgala
- [ ] **8.** FAZ 9'u 🟡 → 🟢 PASS'a çevir — **yalnızca 6/6 kapı yeşilse**
- [ ] **9.** FAZ 13/14/15'i KOŞULLU'dan PASS'a çevir
- [ ] **10.** S3 fazının resmen başladığını yol haritasında ilan et

> 🔒 **Değişmez Kural 1 hatırlatması:** FAZ 13/14/15 kod ve mimari olarak hazır olsa da, FAZ 9 kapanmadan PASS sayılamaz. Sırayı atlama.

---

## 5. G4′'ü Bloklamayan Ama "Tamamlandı" İçin Gereken Kalemler

Bu kalemler paralel yürüyebilir; G4′ kapanışını beklemek zorunda değiller.

- [ ] **11. B-57 Golden Set genişletme** — *(projenin en uzun kalemi, bitiş tarihini bu belirliyor)*
  - Şu an: 90/300 makale, 42/150 iddia (W1 bitti)
  - Takvim: W2 (23–29 Ağu) → W7 (27 Eyl–3 Eki)
  - **Nihai tarih: 3 Ekim 2026**
  - Sorumlu: Kullanıcı + Sistem

- [ ] **12. B-76: 7 gün üst üste brifing teslimi**
  - G4′-9'dan bağımsız — kesintisiz 7 günlük bir seri gerekiyor, ayrıca takip et.

- [ ] **13. B-59: Haftalık kalite ritüeli ≥3 hafta**
  - Rehber hazır: `docs/HAFTALIK-KALITE-RITUELI.md`
  - Sadece 3 haftanın koşulması gerekiyor.
  - En erken tamamlanma: **~5 Eylül 2026**

- [ ] **14. B-68: LLM aylık kota tavanının ölçülmesi**
  - Günlük tur yeterliliği kanıtlandı; aylık tavan henüz ölçülmedi.

- [ ] **15. §21 Final Kontrol Listesi — 10 açık kutu**
  - ingestion ≤%2 · 7 günlük akış · ≥34 correction sample · correction ≤%3 · diversity ≥2,5 · Golden Set 300/150 · 14 brifing slotu · G4′ PASS · S3 başlamış · S3 gate PASS · final production readiness
  - Bunların hepsi yukarıdaki maddelere bağlı — **ayrı bir iş değil**, yukarıdakiler tamamlanınca otomatik kapanır.

---

## 6. ⚠️ Bu İncelemede Bulunan, Listede Olmayan 3 Kritik Bulgu

Bunlar önceki roadmap'te yoktu ve **acilen doğrulanmaları gerekiyor** — aksi halde G4′ kapanışı yanlış pozitif olabilir.

- [x] **16. Sıfırlamadan bu yana hiçbir makale saklanmadı** — *(15 Ağu 2026 23:40 UTC: DOĞRULANDI)*
  - 16 kaynaktan yapılan canlı çekimde yurt dışı/kapsam dışı haberler doğru elendi, Bloomberg HT'nin AR-GE makalesi `butce_ve_hazine` olarak eşleşti ve önceden çekildiği için `exact_dupes` olarak tespit edildi. Konu filtresinde arıza yok; hafta sonu makro veri sessizliği normal, Pazartesi mesai akışında yeni makale saklama takibi sürecek.
  - Kanıt: `python -c "from politikdesk.ingestion.adapters.rss import RssAdapter; from politikdesk.ingestion.topics import classify..."` ile test edildi.

- [x] **17. Gece metrik rollup'ı 14 Ağustos'tan beri koşmamış** — *(15 Ağu 2026 23:39 UTC: ÇÖZÜLDÜ & DOĞRULANDI)*
  - `metrics.daily_rollup()` manuel çalıştırılarak 8 ürün metriği hesaplandı ve Postgres `metrics` tablosuna yazıldı (`day: 2026-08-15`, `written: 8`). `pd-beat` konteynerinde `metrics-rollup-nightly` görevi `crontab(hour=23, minute=50)` (Europe/Istanbul) ile aktif.
  - Kanıt: `docker exec pd-db psql ...` ve `.venv\Scripts\python.exe -m scripts.ingest metrics` çıktısı.

- [x] **18. BACKLOG.md'de 4 bayat kayıt — belge/gerçek çelişkisi** — *(15 Ağu 2026 23:42 UTC: DÜZELTİLDİ)*
  - **B-42 (TÜİK)**: `tuik_auth.py` (OAuth Bearer) + `tuik_sdmx.py` ile canlı veri çekiliyor → ✅ Kapandı.
  - **B-44 (Resmî Gazete)**: `certs/` özel CA bundle imaja dahil edilerek TLS el sıkışma çözüldü → ✅ Kapandı.
  - **B-81 ve B-82**: `cross_source_matcher.py` ve `claims.v3` prompt/normalizer entegre edildi → ✅ Kapandı.
  - Kanıt: `BACKLOG.md` güncellendi, 877 test yeşil.

> **Öncelik notu:** Madde 17 (rollup) diğer her şeyi etkiliyor — önce onu kontrol et. Ardından madde 16 (saklama), sonra madde 18 (belge düzeltmesi, düşük risk).

---

## 7. Özet Takvim

| Kilometre Taşı | Tarih | Bağımlılık |
|---|---|---|
| Gece rollup doğrulaması | Bu gece (15→16 Ağu, 23:50 UTC) | Madde 17 |
| Saklama oranı doğrulaması | 17 Ağu (Pazartesi) | Madde 16 |
| 24h temiz arıza ölçümü | 16 Ağu | Takvim |
| **G4′ kapanışı → S3 başlangıcı** | **22 Ağu** | 33 olay incelemesi (kritik yol) |
| Haftalık ritüel ≥3 hafta | ~5 Eylül | Takvim |
| **Golden Set 300+150 → proje "tamamlandı"** | **3 Ekim 2026** | B-57 W2–W7 |

---

## 8. Kapsam Dışı (Karıştırma)

BACKLOG'daki **B-01…B-32** (Faz 5/6 kalemleri) bu "tamamlandı" tanımına **dahil değil** — bunlar G4/G5 sonrası genişleme kapsamında, bu yol haritasının parçası değil.

---

## 9. Günlük Rutin Önerisi (16–22 Ağustos)

Kritik yolu kaybetmemek için her gün şu sırayla:

1. `pd feed` aç, ~5 olayı incele, geri bildirim gir (Bölüm 1)
2. Günlük snapshot'ın otomatik alındığını kontrol et (Bölüm 2, madde 1)
3. O gün için 08:00/20:00 brifing slotlarının `send_error=null` ile gittiğini doğrula (Bölüm 2, madde 4)
4. Haftanın ilk günü (17 Ağustos) ek olarak: saklama oranı + rollup kontrolü (Bölüm 6, madde 16 ve 17)

---

## 10. Bilinen Sistem Otomasyonları Envanteri

Projede iki ayrı katmanda çalışan otomatik görevler bulunmaktadır:

### A. Celery Beat Konteyner İçi Görevleri (`pd-beat` / `Europe/Istanbul`)
- `ingest-every-5-minutes`: Her 5 dakikada bir tüm aktif kaynaklardan haber çeker (`politikdesk.ingest_all`).
- `embed-every-minute`: Her dakika embedding bekleyen makaleleri vektörleştirir (`politikdesk.embed_pending`).
- `entities-every-2-minutes`: 2 dakikada bir varlık çıkarımı yapar (`politikdesk.extract_entities_pending`).
- `cluster-every-3-minutes`: 3 dakikada bir olay kümelemesi yapar (`politikdesk.cluster_pending`).
- `evidence-every-5-minutes`: 5 dakikada bir kanıt puanlaması yapar (`politikdesk.score_evidence`).
- `claims-every-10-minutes`: 10 dakikada bir iddia çıkarımı yapar (`politikdesk.extract_claims_pending`).
- `briefing-morning`: Her gün 08:00'de sabah brifingi üretir ve SMTP ile gönderir (`politikdesk.generate_morning_briefing`).
- `briefing-evening`: Her gün 20:00'de akşam brifingi üretir ve SMTP ile gönderir (`politikdesk.generate_evening_briefing`).
- `pipeline-health-hourly`: Her saat başı boru hattı darboğaz/sağlık kontrolü yapar (`politikdesk.check_pipeline_health`).
- `metrics-rollup-nightly`: Her gece 23:50'de 8 ürün metriğini hesaplayıp `metrics` tablosuna yazar (`politikdesk.nightly_metrics_rollup`).
- `purge-daily`: Her gece 03:15'te saklama politikasına göre eski verileri temizler (`politikdesk.purge_old_data`).

### B. Windows Task Scheduler Host Görevleri (`scripts\windows_schedule.ps1`)
- **`PolitikDesk-GunlukYedek` (F4-06):** Her gün 03:30'da (purge sonrası) `scripts.backup create` ile veritabanı yedeği alır; Pazar 03:45'te eski yedekleri siler (`prune`).
- **`PolitikDesk-SaglikNobeti` (F4-05 / F4-10):** Her 6 saatte bir `scripts.watchdog` ile dışarıdan Docker ve API sağlığını denetler; `backups\health.log`'a yazar.
- **`PolitikDesk-G4Snapshot` (G4′-1):** Her gün 23:55'te (metrik rollup sonrası) `scripts.g4_snapshot --git-commit` ile günün ölçümlerini `docs/G4-SNAPSHOTS.md`'e yazar ve otomatik Git commit atar.

---

*Bu belge 15 Ağustos 2026 tarihli ölçüm raporuna dayanır. Yeni bir ölçüm oturumu yapıldığında bu dosyanın güncellenmesi önerilir.*
