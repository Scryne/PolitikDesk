# POLİTİKDESK — SİYASET VE YASAMA DİKEYİ (FAZ S2) UYGULAMA VE DOĞRULAMA RAPORU
**Event Relations, Deterministik Puanlama Motoru & “Hesap Sor” Hattı**  
**Tarih:** 15 Ağustos 2026 · **Kapsam:** Spec v3.4 §7.3, §8.3, §14.1 (Siyaset ve Yasama Dikey Fazı S2)  
**Karar:** 🟢 PASS — S2 ENGINE & DATA MODEL VALIDATED


---

## 1. Baseline
- **S0 & S1 Durumu:** PASS (Repo hijyeni, DB izolasyonu, multi-vertical kaynaklar, adaptörler).
- **Mypy Başlangıç:** 0 hata / 134 dosya
- **Pytest Başlangıç:** 783 passed, 0 failed, 0 skipped
- **Legislation Golden Set:** Precision = 1.000, Recall = 1.000, False Merge = 0.000
- **Canlı DB Başlangıç Verisi:** 56 events, 1 feedback, 171 claims, 182 evidence, 17 drafts, 4 briefings, 17 scheduled_events, 212 user_activity, 16 sources, 11 event_relations.

---

## 2. Architecture (Mimari Tasarım)
- **Mimari Dokümanı:** [`docs/S2-ARCHITECTURE.md`](file:///c:/Users/scryn/OneDrive/Belgeler/Projeler/PolitikDesk/docs/S2-ARCHITECTURE.md) oluşturuldu.
- **Tasarım Felsefesi:** PolitikDesk bir "siyasi yargı/suçlama motoru" değildir; resmi ve doğrulanmış kanıtlar arasındaki ilişkileri şeffaf ve denetlenebilir şekilde sunan bir **Accountability / Evidence Graph** motorudur.
- **Zincir Modeli:** `Vaat / Beyan Olayı (TBMM / Açıklama)` $\rightarrow$ `İcraat / Karar Olayı (CB Kararnamesi / Resmî Gazete)` $\rightarrow$ `Denetim Olayı (Sayıştay Raporu / Kamu Zararı Tespiti)`.

---

## 3. Data Model (Veri Modeli)
- `event_relations` tablosu genişletilerek güven katsayısı (`confidence REAL`), detaylı kanıt gerekçelendirmesi (`evidence_payload JSONB`) ve deterministik ilişki statüsü (`status TEXT CHECK (status IN ('inferred', 'supported', 'verified', 'unresolved'))`) alanları dahil edildi.
- Gereksiz yapay tablolar açılmayarak PostgreSQL şeması ve sorgu performans sadeliği korundu.

---

## 4. Migrations
- **Dosya:** [`migrations/0011_event_relations_v2.sql`](file:///c:/Users/scryn/OneDrive/Belgeler/Projeler/PolitikDesk/migrations/0011_event_relations_v2.sql)
- **Uygulama:** Geriye dönük uyumlu `ALTER TABLE ADD COLUMN IF NOT EXISTS` yapısıyla canlı verilere zarar vermeden uygulandı.
- **Doğrulama:** [`tests/test_schema.py`](file:///c:/Users/scryn/OneDrive/Belgeler/Projeler/PolitikDesk/tests/test_schema.py) (23/23 PASS).

---

## 5. Relation Engine (İlişki Motoru)
- **Dosya:** [`politikdesk/political_memory/relation_engine.py`](file:///c:/Users/scryn/OneDrive/Belgeler/Projeler/PolitikDesk/politikdesk/political_memory/relation_engine.py)
- **Deterministik Puanlama:**
  - $S_{\text{entity}}$ (Varlık ve aktör örtüşmesi, Jaccard)
  - $S_{\text{institution}}$ (Kurum eşleşmesi ve anayasal ilişkiler: TBMM yasama forumu, Sayıştay genel denetim yetkisi)
  - $S_{\text{topic}}$ (Konu ve kapsam uyumu)
  - $S_{\text{semantic}}$ (Vektör kosinüs benzerliği)
  - $S_{\text{temporal}}$ (Kronolojik öncelik denetimi)
  - $S_{\text{explicit}}$ (Doğrudan kanun no ve Sayıştay rapor kodu boost'u)
- **İlişki Türleri:** `fulfils`, `fails`, `contradicts`, `updates`, `same_thread`, `precedes`.

---

## 6. Evidence Chain (Kanıt Zinciri)
- **Dosya:** [`politikdesk/political_memory/accountability.py`](file:///c:/Users/scryn/OneDrive/Belgeler/Projeler/PolitikDesk/politikdesk/political_memory/accountability.py)
- `EvidenceChainNode` veri yapısı her adımın kaynak adını, URL'sini, yayın tarihini, alıntı metnini ve iddia ID'sini eksiksiz muhafaza eder.

---

## 7. Accountability Pipeline ("Hesap Sor" Hattı)
- `AccountabilityCase` modeli ile vaat metni, yasama/icraat adımları ve Sayıştay denetim bulguları bir araya getirilerek kullanıcıya sunulabilir kütük oluşturulur.
- Yasal çekince (`disclaimer`) her vakaya iliştirilmiştir: "Bu analiz resmî ve doğrulanmış veri kaynaklarının deterministik eşleştirmesine dayanır; doğrudan şahsi cezai veya hukuki sorumluluk hükmü içermez."

---

## 8. Golden Set S2
- **Dosya:** [`eval/golden_set_accountability_v1.jsonl`](file:///c:/Users/scryn/OneDrive/Belgeler/Projeler/PolitikDesk/eval/golden_set_accountability_v1.jsonl)
- **İçerik:** 18 adet gerçek ve zorlayıcı siyasi/denetim vakası:
  - 13 Pozitif Vaka (TBMM yasalaşması, ÖTV zıtlığı, Sayıştay doğrudan temin ihlali, yargı paketi, ikramiye kanunu, tarım desteği, 4734 sayılı kanun vb.)
  - 5 Negatif / Adversarial Kontrol (Farklı kurumlar, ters kronoloji, kapsam uyuşmazlığı, coğrafi fark, doğrulanmamış söylentiler).

---

## 9. Evaluation Metrics & Sonuçlar
Koşulan komut: `uv run python -m eval.run_accountability`

| Metrik | Ölçülen Değer | Hedef (Spec v3.4 S2) | Durum |
|---|:---:|:---:|:---:|
| **Relation Precision** | **1.000** (%100,0) | $\ge 0.90$ | 🟢 PASS |
| **Relation Recall** | **1.000** (%100,0) | $\ge 0.80$ | 🟢 PASS |
| **F1 Score** | **1.000** | — | 🟢 PASS |
| **False Relation Rate** | **0.000** (%0,0) | $\le 0.05$ | 🟢 PASS |
| **Temporal Compatibility** | **1.000** (%100,0) | $1.000$ | 🟢 PASS |

---

## 10. Unit Tests
- **Dosya:** [`tests/test_relation_engine.py`](file:///c:/Users/scryn/OneDrive/Belgeler/Projeler/PolitikDesk/tests/test_relation_engine.py) (5 test)
  - Puanlama dökümü, kanun no eşleşme takviyesi, Sayıştay ihlal tespiti, ters kronoloji engeli, kurum uyuşmazlığı.
  - *Sonuç:* 5/5 PASS.

---

## 11. Integration Tests
- **Dosya:** [`tests/test_accountability.py`](file:///c:/Users/scryn/OneDrive/Belgeler/Projeler/PolitikDesk/tests/test_accountability.py) (2 test)
  - `build_accountability_case` veri bütünlüğü ve veritabanı `record_relation` genişletilmiş alanlar (`confidence`, `evidence_payload`, `status`) testi.
  - *Sonuç:* 2/2 PASS.

---

## 12. E2E Tests
- TBMM kanun teklifleri, Cumhurbaşkanlığı kararları ve Sayıştay denetim raporlarının ingestion'dan başlayıp `get_accountability_digest()` ve `get_promise_tracker()` üzerinden uçtan uca sorgulanabilirliği doğrulandı.

---

## 13. Adversarial Tests
- **Dosya:** [`tests/test_adversarial_relations.py`](file:///c:/Users/scryn/OneDrive/Belgeler/Projeler/PolitikDesk/tests/test_adversarial_relations.py) (5 test)
  - Aynı isim / farklı kurum (Ahmet Yılmaz belediye vs şirket)
  - Aynı kurum / farklı politika alanı (Fidan dikimi vs bina yıkımı)
  - Aynı sayılar / farklı birimler (1000 konut vs 1000 hektar orman)
  - Coğrafi kapsam uyuşmazlığı (Bursa vs Antalya)
  - Ters kronoloji (2024 Sayıştay raporu ↔ 2026 vaadi)
  - *Sonuç:* 5/5 PASS (Tüm durumlarda fail-closed `unresolved` üretildi).

---

## 14. Mypy Typecheck
```powershell
uv run mypy
```
```
Success: no issues found in 137 source files
```
- **Hata Sayısı:** 0

---

## 15. Full Pytest Suite (DB Aktif)
```powershell
$env:PD_DATABASE_URL="postgresql://politikdesk:politikdesk@127.0.0.1:5432/politikdesk"; $env:PD_CI_REQUIRE_DB="1"; uv run pytest
```
```
======================= 795 passed, 1 warning in 44.28s =======================
```
- **Toplam Test:** 795 (Önceki S1 baseline: 783, +12 yeni test)
- **Geçen:** 795 (%100)
- **Başarısız / Atlanan:** 0

---

## 16. DB Contamination Sonucu
```powershell
uv run python scratch/get_counts.py
```
- `events`: 56
- `event_feedback`: 1
- `claims`: 171
- `evidence`: 182
- `drafts`: 17
- `briefings`: 4
- `scheduled_events`: 17
- `user_activity`: 212
- `sources`: 16
- **Test DB Contamination (Sızan Satır):** **0**

---

## 17. Existing Golden Set Regression Denetimi
- **Legislation Golden Set v1:** Precision = 1.000, Recall = 1.000, False Merge = 0.000 (%0 gerileme, 0 regresyon).
- **Macro Economy Golden Set v1:** Precision = 1.000, Recall = 0.824, False Merge = 0.000 (Korundu).

---

## 18. Known Limitations (Bilinen Kısıtlar)
- G4′ takvimsel gözlem süreci (7 günlük kesintisiz akış ve brifing zamanlaması) arka planda planlandığı şekilde devam etmektedir (`PENDING_OBSERVATION`).

---

## 19. Remaining Blockers
- Teknik veya mimari hiçbir engel (blocker) bulunmamaktadır.

---

## 20. S2 Gate Decision
- **Koşulan Gate:** `scripts/phase5_s2_gate.py`
- **S2 Gate Kararı:** **🟢 PASS**
- **Teknik Karar:** S2 (Event Relations & Hesap Sor Pipeline) fazı tüm kalite, güvenlik, grounding ve test kriterlerini eksiksiz sağlayarak tamamlanmıştır.
