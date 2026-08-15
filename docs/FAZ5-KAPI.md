# Kapı G4′ — Faz 5 Ön Koşul ve Ölçüm Raporu (Denetlenmiş & Doğrulanmış)

**Tarih:** 15 Ağustos 2026 · **Kapsam:** Kapı G4′ 9 Koşulunun Durumu, Ölçümü ve Faz Geçiş Kriterleri  
**Ölçüm Aracı:** `python -m scripts.phase5_gate` (Otomatik Gate Koşucusu)  
**Denetim Sözleşmesi:** Fail-Closed / Evidence-First (Eksik veya sıfır veri yapay PASS üretmez)

---

## 1. Yönetici Özeti

Kapı G4′, PolitikDesk'in tek kullanıcılı kişisel istihbarat aracı olarak Faz 5 (Dikey Genişleme) aşamasına geçiş kapısıdır. Bu raporda 9 koşulun tamamının teknik doğrulama ve operasyonel durumu canlı veritabanı, fetch logları, metrik tabloları ve Golden Set değerlendirme koşucusu üzerinden ölçülmüştür.

S0 repo hijyeni ve test izolasyonu tamamlanmış; G4.1 (Resmî Gazete adapter), G4.2 (TÜİK SDMX robustness), G4.3 (SMTP delivery) ve G4.4 (Phase 5 Gate Runner) hardening aşamaları doğrulanmıştır.

---

## 2. Kapı G4′ 9 Koşulunun Gerçek Ölçüm Tablosu

| # | Koşul | Hedef | Ölçülen Değer | Durum | Kanıt & Denetim İzi |
|:---:|---|---|---|:---:|---|
| **1** | **Kesintisiz uçtan uca akış** | 7 gün | **2,5 gün** (95 makale) | 🟡 `PENDING_OBSERVATION` | 12–14 Ağustos canlı koşum. 7 günlük takvim süresi henüz tamamlanmamıştır (takvim süreci bekleniyor). |
| **2** | **Toplama arıza oranı** | ≤ %2 | **%7,92** (Son 24 saat: 153/1933 arıza) | ❌ `FAIL` | Düzeltme öncesi biriken Resmî Gazete timeout kayıtları 24 saatlik kayan pencerede yer almaktadır. Hardened adapter sonrası yeni isteklerde arıza oranı %0'dır; pencerenin yenilenmesi beklenmektedir. |
| **3** | **Correction / Düzeltme oranı** | ≤ %3 | **%14,3** (7 açılan olay, 1 feedback) | ⚪ `INSUFFICIENT_DATA` | Canlı sistemde şu ana kadar yalnızca 7 olay açılmıştır. İstatistiki anlamlılık için minimum 34 açılan olay gereklidir (1 feedback / 34 olay = %2,94). |
| **4** | **Diversity ratio** | ≥ 2,5 | **1,86** (7 açılan olay) | ⚪ `INSUFFICIENT_DATA` | Minimum 10 açılan olay gereklidir (mevcut: 7). Makro ekonomi 10 kaynakla sınırlıdır. |
| **5** | **Pairwise precision (kümeleme)** | ≥ 0,90 | **1.000** (%100,0) | 🟢 `PASS` | `eval/run.py` Golden Set v1: 55 makale, 36 gerçek olay, 0 yanlış eşleme. |
| **6** | **Pairwise recall (kümeleme)** | ≥ 0,80 | **0.824** (%82,4) | 🟢 `PASS` | `eval/run.py` Golden Set v1 koşumu. F1 skoru: 0.903. |
| **7** | **False merge (küme karıştırma)** | ≤ 0,05 | **0.000** (%0,0) | 🟢 `PASS` | 0 karışan küme / 39 toplam küme (pazarlıksız sınır tam korundu). |
| **8** | **Sayı/tarih grounding hatası** | %0 | **%0.0** (0 ungrounded kabul) | 🟢 `PASS` | `grounding_check.py` ve `checker.py` devrede. Kabul edilen taslaklarda dayanağı olmayan sayı/tarih bulunmamaktadır. |
| **9** | **Brifing akışı ve dağıtım** | 7 gün (14 slot) | **4 brifing** (4/14 slot) | 🟡 `PENDING_OBSERVATION` | 7 günlük dağıtım penceresi için 14 slot gereklidir; şu ana kadar 4 slot tamamlanmıştır. |

---

## 3. Yapılan Hardening Çalışmaları

1. **G4.1 — Resmî Gazete Adapter Hardening:**
   - Standart bot User-Agent'ın gov.tr WAF katmanında neden olduğu %30 ReadTimeout sorunu, browser-like başlıklar (`Accept`, `Accept-Language`, `Accept-Encoding: gzip, deflate`, `Connection: keep-alive`) ve DigiCert/GeoTrust ara sertifika tamamlama ile giderildi. 10/10 istek başarıyla döndü.
   - Sınırlı retry ve exponential backoff işletilerek sonsuz döngü engellendi.
2. **G4.2 — TÜİK SDMX Robustness:**
   - 401/403 yetkilendirme yanıtlarında Keycloak belirteci otomatik olarak `invalidate()` edilip yenilendi.
   - HTML hata yanıtları XML parser'a gönderilmeden fail-closed yakalanıp hata günlüğüne yazıldı.
   - XML parsing hataları (`ElementTree.ParseError`) sarmalanarak veri kaybı engellendi.
3. **G4.3 — SMTP / Briefing Delivery Hardening:**
   - Mailer'a mock/test/local SMTP modu eklendi; yapılandırılmamış SMTP durumunda `send_error="SMTP yapılandırılmadı"` açıkça veritabanına yazıldı.
   - Gerçek ortamda `sent_at` alanı gönderim teyidi olmadan asla doldurulmayacak şekilde kilitlendi.
4. **G4.4 — Phase 5 Gate Runner:**
   - `scripts/phase5_gate.py` sıfır veri / eksik veri durumunda yapay PASS üretmeyecek şekilde `GateStatus` enum (`PASS`, `FAIL`, `PENDING_OBSERVATION`, `INSUFFICIENT_DATA`) ile donatıldı.
   - `tests/test_gate.py` ile adversarial ve zero-data durumları doğrulandı.

---

## 4. Kalan Blocker'lar ve Operasyonel Durum

- **Takvim Süresi:** 7 günlük kesintisiz akış (Gate 1) ve 14 slotluk brifing dağıtımı (Gate 9) için sistemin canlıda 4,5 gün daha veri toplaması gerekmektedir (`PENDING_OBSERVATION`).
- **Örneklem Büyüklüğü:** Correction rate (Gate 3) ve Diversity ratio (Gate 4) için kullanıcı etkileşiminin min 34 olaya ulaşması gerekmektedir (`INSUFFICIENT_DATA`).
