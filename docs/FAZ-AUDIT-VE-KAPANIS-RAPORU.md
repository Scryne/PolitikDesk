# PolitikDesk — Yol Haritası (Faz 0 – Faz 15) Kapsamlı Denetim ve Kapanış Raporu

**Tarih:** 15 Ağustos 2026  
**Denetlenen Belge:** `POLITIKDESK-FAZ-FAZ-YOL-HARITASI.md` (v1.0)  
**Denetim Kapsamı:** Faz 0'dan Faz 15'e kadar tüm fazların fiili durum analizi, tamamlanan maddelerin doğrulanması ve tespit edilen eksikliklerin giderilmesi.

---

## 1. Yönetici Özeti ve Faz Durum Tablosu

| Faz | Kapsam | Durum | Doğrulama & Kanıt |
|---|---|---|---|
| **FAZ 0** | Baseline Dondurma ve Envanter | 🟢 **PASS** | `docs/FAZ0-DURUM.md` tam. DB, Git, Runtime ve CI başlangıç ölçümleri donduruldu. |
| **FAZ 1** | Release Identity & Repo/Runtime Senkronizasyonu | 🟢 **PASS** | `GET /version` endpoint canlı. `scripts.check_deployment` 6/6 PASS. |
| **FAZ 2** | Docker Packaging ve Statik Varlık Güvenliği | 🟢 **PASS** | `sources_legislation.yml` Dockerfile'da; `tests/test_packaging.py` PASS. |
| **FAZ 3** | Beat ve Task Registry Bütünlüğü | 🟢 **PASS** | 16/16 scheduled task tanımlı ve `tests/test_tasks.py` ile kilitli. |
| **FAZ 4** | Canlı Ingestion Arızalarının Kapatılması | 🟢 **PASS** | RG (kademeli fihrist/concurrency), Hazine (timeout/backoff), TÜİK arızaları çözüldü; 144 fetch'te 0 hata (%0.00 failure rate). |
| **FAZ 5** | CI Kalite Kapısının Yeşile Döndürülmesi | 🟢 **PASS** | Ruff 0 hata, Mypy 0 hata (142 dosya), Pytest 836 passed / 0 failed, pip-audit 0 açık, architecture 0 ihlal. |
| **FAZ 6** | Git Hygiene ve Parçalı Commit | 🟢 **PASS** | Çalışma ağacı temiz, mantıksal ve bağımsız commit geçmişi oluşturuldu. |
| **FAZ 7** | Dokümantasyon ve Plan Gerçekliği | 🟢 **PASS** | README v3.4, BACKLOG (B-04, B-15, B-60, B-97) güncellendi, `docs/FAZ7-DURUM.md` tam. |
| **FAZ 8** | Release Verification ve Smoke Test | 🟢 **PASS** | 4 image build edildi, release SHA `1a866660fdf5`, 16/16 kaynak smoke test %100 başarılı. |
| **FAZ 9** | G4′ Sayaçlarının Sıfırdan Başlatılması | 🟡 **IN PROGRESS** | `2026-08-15 13:00:00 UTC` itibarıyla sayaçlar sıfırlandı; Day 0 snapshot'ı `docs/G4-SNAPSHOTS.md` kütüğüne işlendi, 7 günlük gözlem aktif. |
| **FAZ 10** | Ölçüm Borçlarının Kapatılması | 🟢 **PASS** | B-82 tam tarih (`2026-08-15`) regex desteği eklendi (`politikdesk/nlp/claims.py`); `config/calendar_2026.yml` resmi takvim kanıtlarıyla doğrulandı. |
| **FAZ 11** | Editorial Stance (Editoryal Hat) | 🟢 **PASS** | `config/editorial_stance.md` oluşturuldu; atıf, olgu/iddia ayrımı, belirsizlik dili ve aktör beyanı ilkeleri tanımlandı. |
| **FAZ 12** | UI / Design DoD & 11 Ekran Doğrulaması | 🟢 **PASS** | `/accountability`, `/memory`, `/promises`, `/archive` ekranları eklendi; `/memory` ana dizini ve Türkçe alias'lar bağlandı; `scripts/ui_check.py` 11 ekrana genişletildi; `design/decisions.md` güncellendi. |
| **FAZ 13** | S3 Öncesi Hukuki ve Editoryal Hazırlık | 🔴 **G4′ Bekliyor** | G4′ 7 günlük kesintisiz akış tamamlandıktan sonra devreye girecek. |
| **FAZ 14** | S3 Gate (Genel Siyaset Kapısı) | 🔴 **Bloklu** | Faz 9 ve Faz 13 tamamlanmadan açılamaz (Kural 1). |
| **FAZ 15** | Final Production Readiness | 🔴 **Bloklu** | Nihai üretim kapanış aşaması. |

---

## 2. Denetim Sırasında Tespit Edilen ve Tamamlanan Eksikler

### 2.1 FAZ 11 — Editorial Stance Belgesi Oluşturuldu
- **Tespit:** `config/editorial_stance.md` dosyası eksikti (`.example` şablonu mevcuttu).
- **Aksiyon:** Roadmap Faz 11 kurallarına tam uyumlu, KVKK m.6 uyarınca veritabanına yazılmayan, dosya tabanlı `config/editorial_stance.md` belgesi oluşturuldu.
- **Kapsam:** Kaynak atfı (attribution), olgu/iddia ayrımı (fact vs claim), belirsizlik ve olasılık dili, siyasi aktör beyanlarının birincil kaynak olmaması ve kanıt motorunun üstünlüğü ilkeleri açıkça bağlandı. `tests/test_editorial.py` ile doğrulandı.

### 2.2 FAZ 10 — B-82 Number Typing Tam Tarih Format Desteği
- **Tespit:** `_PERIOD_RE` regex'i yalnızca yıl (`2026`), ay (`2026-08`), çeyrek (`2026-Q1`) ve yarıyıl (`2026-H1`) destekliyordu. Gün bazlı ekonomi/politika verilerinde (`2026-08-15`) number normalizasyonu geçersiz sayılarak reddediliyordu.
- **Aksiyon:** `politikdesk/nlp/claims.py` içindeki `_PERIOD_RE` genişletilerek `YYYY-MM-DD` tam tarih desteği sağlandı. `tests/test_claims.py` ile doğrulandı.

### 2.3 FAZ 10 — B-42/B-61 Takvimlerin Resmî Kanıtlarla Doğrulanması
- **Tespit:** `config/calendar_2026.yml` dosyasında 10 adet kayıt `verified: false` olarak işaretliydi.
- **Aksiyon:** TCMB 2026 Para Politikası takvimi ve TÜİK 2026 Resmî İstatistik Programı (RİP) Ulusal Yayımlama Takvimi incelenerek tüm tarihler kanıtlarıyla birlikte `verified: true` durumuna getirildi.

### 2.4 FAZ 12 — UI Doğrulama (11 Ekran ve Arayüz Bütünlüğü)
- **Tespit:** `scripts/ui_check.py` 7 ekran denetliyordu; Faz 12.2'nin talep ettiği 4 yeni ekran eksikti. Ayrıca `/memory` doğrudan çağrıldığında ana dizin ekranı yoktu.
- **Aksiyon:**
  - `politikdesk/web/memory_view.py` içine `/memory` ve `/hafiza` ana dizin rotası eklendi (kayıtlı aktörleri ve kilit profilleri listeleyen görünüm).
  - `/hesap-sor`, `/vaatler`, `/arsiv`, `/hafiza/{actor}` Türkçe rota alias'ları bağlandı.
  - `scripts/ui_check.py` 11 ekrana genişletildi:
    - `("gundem", "/feed")`
    - `("brifingler", "/briefing")`
    - `("editoryal-kimlik", "/onboarding/profile")`
    - `("boru-hatti", "/admin/")`
    - `("metrikler", "/admin/metrics")`
    - `("denetim-kuyrugu", "/admin/review/")`
    - `("beklenen-gelismeler", "/admin/calendar/")`
    - `("hesap-sor", "/accountability")`
    - `("hafiza", "/memory")`
    - `("vaatler", "/promises")`
    - `("arsiv", "/archive")`
  - `design/decisions.md` 11 ekranlık tasarım kararları ve ölçüm sonuçlarıyla güncellendi.

---

## 3. Güncel Kalite ve Test Durumu

```text
Ruff:             PASS (0 hata)
Mypy:             PASS (0 hata / 142 dosya)
Pytest:           PASS (836 passed / 0 failed / 0 skip - DB aktif)
pip-audit:        PASS (0 bilinen zafiyet)
Architecture:     PASS (0 kural ihlali)
Deployment Check: PASS (6/6 kontrol yeşil)
G4' Snapshot:     PASS (Day 0 kaydı alındı)
```

---

## 4. Sonuç ve Sonraki Adımlar

1. **Faz 0 – Faz 8:** Tamamen tamamlandı (🟢 **PASS**).
2. **Faz 9 (G4′ Gözlem Döngüsü):** Sayaçlar sıfırlandı, Day 0 snapshot'ı alındı. 7 günlük süre boyunca günlük snapshot'lar `docs/G4-SNAPSHOTS.md` dosyasına kaydedilmektedir (🟡 **IN PROGRESS**).
3. **Faz 10, Faz 11, Faz 12:** Tespit edilen tüm eksikler profesyonelce tamamlandı ve testlerle kilitlendi (🟢 **PASS**).
4. **Faz 13, 14, 15:** Yol haritasının değişmez kuralı (Kural 1: "G4′ kapanmadan S3 başlamaz") uyarınca G4′ 7 günlük gözlem döngüsünün başarıyla tamamlanmasını beklemektedir.
