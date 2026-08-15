# POLİTİKDESK — FAZ 9 BAŞLANGIÇ VE DAY 0 BASELINE RAPORU

**Tarih:** 15 Ağustos 2026  
**Kapsam:** FAZ 9 — G4′ Sayaçlarının Sıfırdan Başlatılması ve 7 Günlük Gözlem Protokolü  
**Başlangıç Zamanı (Baseline Reset):** 2026-08-15 13:00:00 UTC (16:00:00 TSİ)  
**Canlı Release Kimliği:** Git SHA `1a866660fdf5` | DB Schema `0012_event_relations_reverse_idx`  
**Durum:** 🟡 **IN PROGRESS — SAYAÇLAR SIFIRLANDI, 7 GÜNLÜK GÖZLEM BAŞLATILDI**

---

## 1. Yönetici Özeti

Roadmap **FAZ 9** direktifleri ve değişmez kuralları (Kural 2: *Deployment doğrulanmadan ölçüm sayacı başlamaz; bayat image ile geçen süre G4′ 7 günlük süreye dahil edilmez*) uyarınca:

1. **Önceki 2,5 Günlük Süre Sıfırlandı:**  
   Faz 8 öncesindeki bayat imaj ve eski loglar yeni 7 günlük pencereye dahil edilmemiştir. Faz 8 doğrulanmış release'i (`1a866660fdf5`) temel alınarak Day 0 başlangıç noktası tescil edilmiştir.

2. **G4′ Denetim ve Kapı Koşucusu Genişletildi:**  
   `scripts/phase5_gate.py` betiğine `--since` zaman filtreleme yeteneği kazandırılmış; 9 kapı koşulunun tamamı sıfırlanmış pencere üzerinden fail-closed mantıkla işletilmeye başlanmıştır.

3. **Günlük Snapshot Mekanizması Devreye Alındı:**  
   Roadmap G4′-1 şartlarına uygun `scripts/g4_snapshot.py` CLI aracı oluşturulmuş ve ilk **Day 0 Snapshot**'ı `docs/G4-SNAPSHOTS.md` denetim defterine işlenmiştir.

4. **Konteyner ve Ingestion Sağlığı:**  
   Faz 8 sonrası gerçekleştirilen 144 fetch işleminin tamamı (%100) başarıyla tamamlanmış, arıza oranı **%0.00** olarak ölçülmüştür.

---

## 2. Kapı G4′ — Day 0 Başlangıç Durumu Panosu

| # | Koşul | Hedef | Day 0 Ölçülen | Durum | Kanıt & İzleme Notu |
|---|---|---|---|---|---|
| **1** | **Kesintisiz uçtan uca akış** | 7 gün | 0.0 gün | 🟡 `PENDING_OBS` | Sıfırlama: 2026-08-15 13:00 UTC. Hedef bitiş: 2026-08-22 13:00 UTC |
| **2** | **Toplama arıza oranı** | ≤ %2 | **%0.00** | 🟢 `PASS` | Sıfırlamadan beri 0/144 arıza (16/16 kaynak aktif) |
| **3** | **Correction oranı** | ≤ %3 | %0 (0 olay) | ⚪ `INSUFFICIENT` | Min 34 açılan olay gerekli (Kullanıcı feed etkileşimi bekleniyor) |
| **4** | **Diversity ratio** | ≥ 2,5 | 0.00 (0 olay) | ⚪ `INSUFFICIENT` | Min 10 açılan olay gerekli (B-82 ve B-81 geliştirmelerine tabi) |
| **5** | **Pairwise precision (kümeleme)** | ≥ 0,90 | **1.000** | 🟢 `PASS` | Golden Set v1 (55 makale, 36 olay) |
| **6** | **Pairwise recall (kümeleme)** | ≥ 0,80 | **0.824** | 🟢 `PASS` | F1: 0.903 |
| **7** | **False merge (küme karıştırma)** | ≤ 0,05 | **0.000** | 🟢 `PASS` | 0 karışan küme / 39 toplam küme |
| **8** | **Sayı/tarih grounding hatası** | %0 | 0 kabul taslak | 🟡 `PENDING_OBS` | Yeni üretilecek taslakların editoryal kabullerinde %0 hata aranacak |
| **9** | **Brifing akışı ve dağıtım** | 14 slot | 0/14 slot | 🟡 `PENDING_OBS` | Günde 2 slot (sabah/akşam) × 7 gün boyunca izlenecek |

---

## 3. Canlı Altyapı ve Veri Durumu (Day 0)

- **Konteynerler:** 5 servis UP (`pd-api`, `pd-worker`, `pd-beat`, `pd-db`, `pd-redis`)
- **Canlı SHA:** `1a866660fdf5`
- **DB Schema:** `0012_event_relations_reverse_idx`
- **Aktif Kaynak Sayısı:** 16/16 aktif
- **Pipeline Durumu:** 🟢 8/8 GREEN (Toplama, Embedding, Varlık, Kümeleme, İddia, Kanıt, Brifing, Metrik)
- **Veritabanı Envanteri:** 98 makale, 59 olay, 192 iddia, 203 kanıt, 11 ilişki

---

## 4. 7 Günlük G4′ Operasyonel Takvimi

| Gün | Tarih | Beklenen Eylem & Doğrulama | Sorumlu Araç |
|---|---|---|---|
| **Gün 0** | 15 Ağu 2026 | Sayaçların sıfırlanması, Day 0 snapshot kaydı | `scripts/g4_snapshot.py` |
| **Gün 1** | 16 Ağu 2026 | 2 brifing slotu, günlük fetch arıza oranı kontrolü | `scripts/g4_snapshot.py` |
| **Gün 2** | 17 Ağu 2026 | 4 brifing slotu, feed etkileşimi (correction/diversity takibi) | `scripts/g4_snapshot.py` |
| **Gün 3** | 18 Ağu 2026 | 6 brifing slotu, B-82 number typing iyileştirmesi hazırlığı | `scripts/g4_snapshot.py` |
| **Gün 4** | 19 Ağu 2026 | 8 brifing slotu, haftalık kalite ritüeli kontrolü | `scripts/g4_snapshot.py` |
| **Gün 5** | 20 Ağu 2026 | 10 brifing slotu, grounding sıfır hata doğrulama | `scripts/g4_snapshot.py` |
| **Gün 6** | 21 Ağu 2026 | 12 brifing slotu, olay düzeltme geri bildirimleri kontrolü | `scripts/g4_snapshot.py` |
| **Gün 7** | 22 Ağu 2026 | 14 brifing slotu, nihai G4′ kapanış testi | `scripts/phase5_gate.py --strict` |

---

## 5. Çıkış Kriteri Değerlendirmesi

> **Faz 9 Başlangıç Kriteri:**  
> - Faz 8 başarıyla geçmiş olmalı (🟢 PASS)  
> - Sayaçlar sıfırlanmış ve başlangıç snapshot'ı kaydedilmiş olmalı (🟢 TAMAMLANDI)  
> - 7 günlük kesintisiz akış sayacı resmi olarak başlatılmış olmalı (🟢 BAŞLATILDI)
