# Haftalık Kalite Ritüeli ve Gözlem Rehberi (B-59 · B-76 · F2-21)

Bu belge, PolitikDesk üretim ortamında haftalık düzenli kalite denetimlerinin (F2-21 ritüeli, ≥3 hafta kesintisiz kayıt) nasıl yürütüleceğini, hangi metriklerin kontrol edileceğini ve olası sapmalarda hangi aksiyonların alınacağını tanımlar.

---

## 1. Haftalık Ritüel Zamanlaması

- **Gözlem Günü / Saati:** Her Pazar günü saat 21:00 UTC (Pazartesi sabah brifingi öncesi).
- **Süre:** ~15–20 dakika.
- **Komut:** `pd health` ve `pd snapshot` ve `pd correction`.

---

## 2. 6 Aşamalı Kalite Kontrol Listesi

Her haftalık ritüelde aşağıdaki 6 adım sırayla uygulanır ve sonuçlar `docs/G4-SNAPSHOTS.md` dosyasına eklenir:

### Adım 1 — Dağıtım ve Sürüm Bütünlüğü
```bat
pd deploy-check
```
- [ ] 3 container'ın (`pd-api`, `pd-worker`, `pd-beat`) Git SHA ve kod hash'i repodaki HEAD ile tam eşleşiyor mu?
- [ ] DB migration durumu güncel mi? (0 bekleyen migration)

### Adım 2 — Kaynak Sağlığı ve Toplama Arıza Oranı (G4′-2)
```bat
pd health
```
- [ ] Son 24 saat ve son 7 günlük toplama arıza oranı ≤ %2 mi?
- [ ] 10 kaynaktan herhangi biri 3 ardışık tur boyunca `failing` veya `unreachable` durumunda kaldı mı?

### Adım 3 — Kümeleme ve Kural Motoru Doğrulaması (G4′-5, G4′-7, G4′-8)
```bat
pd eval
```
- [ ] Pairwise precision ≥ 0,90 (Mevcut: 1.000)
- [ ] Pairwise recall ≥ 0,80 (Mevcut: 0.824)
- [ ] False merge rate ≤ 0,05 (Mevcut: 0.000)
- [ ] `evidence_status` doğruluğu ≥ 0,95 (Mevcut: 0.958)
- [ ] Sayısal normalizasyon doğruluğu ≥ 0,95 (Mevcut: 1.000)

### Adım 4 — Editoryal Düzeltme ve İnceleme Takibi (G4′-3)
```bat
pd correction
```
- [ ] İncelenen olay sayısı hedef doğrultusunda ilerliyor mu? (Haftalık +35 hedefi)
- [ ] Düzeltme / itiraz oranı ≤ %3 seviyesinde mi?

### Adım 5 — Brifing Teslimatı ve Kuyruk Sağlığı (G4′-9)
- [ ] Son 7 günde 14 brifing slotunun tamamı başarıyla üretilip iletildi mi (`send_error = null`)?
- [ ] Boru hattı aşamalarında birikme var mı? (`pd pipeline-health`)

### Adım 6 — Yedekleme Kontrolü
```bat
pd backup list
```
- [ ] Son 7 günün otomatik veya manuel yedekleri `%LOCALAPPDATA%\PolitikDesk\backups` altında mevcut mu?

---

## 3. Sapma Durumunda Müdahale Protokolü

1. **Toplama Arızası > %2 ise:**
   - Hangi kaynağın bozulduğunu `pd health` ile izole et.
   - Seçici DOM veya SDMX uç noktası değişmişse ilgili adaptörü güncelle ve test et.
2. **False Merge > 0 ise:**
   - Karışan kümeyi `eval/run.py` çıktısından tespit et.
   - İlgili makalelerin varlık veya özetlerini incele; `T_HIGH` ve `Jaccard` eşiklerini değerlendir.
3. **Correction Rate > %3 ise:**
   - Düzeltme notlarını `pd correction` ile listele.
   - Hata tipine (kümeleme, iddia çıkarımı, grounding) göre kök nedeni raporla.
