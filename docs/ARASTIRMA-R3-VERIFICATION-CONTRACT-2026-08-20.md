# Denetim: R3 Doğrulama Sözleşmesi ve Resmî Veri Bütünlüğü

**Tarih:** 20 Ağustos 2026 · **Baseline:** HEAD `22bec47`, 1.616 test, temiz ağaç
**Soru:** R3 gerçekten fail-closed mı? `metric`/`value`/`unit`/`period`
eşleşmelerinde gizli yanlış doğrulama yolu var mı?

**Sonuç:** Bir **dormant invariant boşluğu** bulundu ve kapatıldı.
Aktif üretim arızası yoktu.

---

## 1. R3 veri akışı — hangi alan nereden geliyor?

| Aşama | Alan | Kaynak | Güven |
|---|---|---|---|
| Resmî API yanıtı | SDMX gözlemi / EVDS JSON | kurum | **birincil** |
| Adaptör | `extra["normalized_value"]` = `{metric, value, unit, period}` | **deterministik kod** (`indicator.metric`, seri tanımı) | yüksek |
| Depolama | `articles.official_value` | `normalizer.py:214` | yüksek |
| İddia çıkarımı | `claims.normalized_value` | **LLM** | doğrulanmalı |
| Doğrulama | `_verified_against_official` | deterministik kod | — |
| Durum ataması | `evidence_status` | `rules.compute_status` | LLM **üretemez** (`FORBIDDEN_FIELDS`) |

**LLM yalnızca bir alana dokunuyor** (`claims.normalized_value`) ve R3
tam olarak onu resmî değere karşı sınıyor. Tasarım doğru.

---

## 2. Sözleşme — ölçülerek çıkarıldı (tahminle değil)

Gerçek fonksiyon sahte imleçle çalıştırıldı. **Düzeltme öncesi:**

| Metric | Value | Unit | Period | Sonuç |
|---|---|---|---|---|
| aynı | aynı | aynı | aynı | ✅ verified |
| **farklı** | aynı | aynı | aynı | ❌ reddedildi |
| aynı | **farklı** | aynı | aynı | ❌ reddedildi |
| aynı | aynı | **FARKLI** | aynı | **⚠ VERIFIED** |
| aynı | aynı | aynı | **farklı** | ❌ reddedildi |
| **eksik** | aynı | aynı | aynı | ❌ reddedildi |
| aynı | **eksik** | aynı | aynı | ❌ reddedildi |
| aynı | aynı | aynı | **eksik** | ❌ reddedildi |
| aynı | aynı | **eksik** | aynı | ✅ verified (fail-open) |

Ek ölçümler: `7.6` ↔ `7.599999999` eşleşir (1e-6 tolerans, doğru);
`7.6` ↔ `7.7` eşleşmez; `2026-6` ↔ `2026-06` eşleşmez (dönem
normalizasyonu **yok**, fail-closed).

**Bulgu:** `metric`, `period` ve `value` aynıyken `unit` `%` ↔ `kisi`
olduğunda fonksiyon **`True`** dönüyordu — "yüzde 48,9" ile "48,9 kişi"
aynı resmî değer sayılıyordu.

---

## 3. Gerçek üretim verisi — boşluk teorik mi, gerçekçi mi?

Tüm `official_value` kayıtları (11 satır, 2 kaynak):

| Kaynak | metric | unit | period | value | series_code |
|---|---|---|---|---|---|
| tcmb-evds | exchange_rate | TRY | 2026-08-19 | 55.366 | TP.DK.**EUR**.A.YTL |
| tcmb-evds | exchange_rate | TRY | 2026-08-19 | 47.8293 | TP.DK.**USD**.A.YTL |
| tcmb-evds | exchange_rate | TRY | 2026-08-20 | 47.8467 | TP.DK.USD.A.YTL |
| tcmb-evds | exchange_rate | TRY | 2026-08-20 | 55.5061 | TP.DK.EUR.A.YTL |
| tcmb-evds | **other** | *(boş)* | 2026-08-07 | 11906.8515 | TP.KAVRAMSAL.HAMM2.INDX |
| tcmb-evds | policy_rate | % | 2026-06 | 37.0 | TP.BISPOLFAIZ.TUR |
| tcmb-evds | **reserves** | *(boş)* | 2026-05 | 208670.9 | TP.AB.B6 |
| tcmb-evds | tufe_annual | % | 2026-07 | 23.95 | TP.ENFBEK.PKA12ENF |
| tuik | employment_rate | % | 2026-06 | 48.9 | — |
| tuik | participation_rate | % | 2026-06 | 52.9 | — |
| tuik | unemployment_rate | % | 2026-06 | 7.6 | — |

* Benzersiz metric: **7** · benzersiz unit: **3 + boş** · dönem biçimi: **3**
  (`YYYY-MM`, `YYYY-MM-DD`, EVDS günlük)
* **İki resmî kayıt birimi BOŞ bırakıyor** (`other`, `reserves`).

### Boşluğun gerçekçi yolu

`other` bir **yakalama-hepsi** metriğidir ve **53 iddia** kullanıyor.
O iddiaların birimleri karışık: `TL`, `%`, `USD`. Yani aynı
`metric` + `period` + `value` üçlüsünün iki farklı birimle görünmesi
kapsam büyüdükçe (yeni SDMX serileri, sayım metrikleri) an meselesiydi.

---

## 4. Bulgu sınıflandırması

### 4.1 Birim kısıtı — **DORMANT INVARIANT GAP → KAPATILDI**

* Sentetik olarak kanıtlandı (§2).
* Aktif değildi: üretimdeki iki R3 🟢'sinin (claim 208, 210) dört alanı da
  eşleşiyor (`unemployment_rate`/`%`, `employment_rate`/`%`) ve aynı
  `metric`+`period`+`value` ikilisini farklı birimle taşıyan kayıt yok.
* Gerçekçi yolu var (§3) → kapatıldı.

### 4.2 Seri belirsizliği — **DORMANT, KAPATILMADI (tasarım kararı gerekir)**

Gerçek veride `exchange_rate` **iki farklı seriyi** (EUR, USD) aynı
`metric` + `unit` + `period` altında taşıyor. Ayıran tek şey
`series_code` ve karşılaştırma ona **bakmıyor**.

Yanlış doğrulama senaryosu: bir iddia "Euro kuru 47,83 TL" derse
(gerçekte USD kuru) ve USD resmî satırı 47,8293 ise → **doğrulanır.**

**Neden bu turda kapatılmadı:** iddia şemasında `series_code` **yok** ve
LLM'e onu ürettirmek yeni epistemik yetki vermek olurdu (yasak). Doğru
çözüm metrik granülaritesidir (`exchange_rate` → `exchange_rate_usd`,
`exchange_rate_eur`) ve bu, `VALID_METRICS` + prompt + golden set
değişikliği ister — ayrı bir karardır.

**Bugün ulaşılabilir değil (ölçüldü):**
* `metric='exchange_rate'` olan iddia sayısı: **0**
* Kanıt kümesinde aynı `metric`+`period`'i taşıyan >1 resmî kayıt gören
  iddia sayısı: **0**

Testle kayda geçirildi: `test_wrong_series_value_does_not_verify_when_unit_or_value_differs`.

---

## 5. Uygulanan düzeltme (minimal)

`_verified_against_official` artık `unit`'i de karşılaştırıyor:

> **İki tarafta da birim varsa, normalize edilmiş birim eşleşmek zorunda.**

* Normalizasyon: büyük/küçük harf + boşluk; tek alias **`TL` ≡ `TRY`**
  (EVDS `TRY` yazar, Türkçe metin `TL` der — ayrı saymak meşru bir
  doğrulamayı engellerdi).
* **Eksik birim FAIL-OPEN bırakıldı ve bu bilinçlidir:** gerçek veride
  `reserves` ve `other` kayıtlarının birimi boş; eksik birimde reddetmek
  bugün doğru çalışan doğrulamaları sebepsiz kırardı. Kısıt "birim yoksa
  kontrol edilemez" der, "birim yoksa yanlıştır" demez — `_entity_check`'in
  `inconclusive` sonucundaki ayrımın aynısı.

**Sözleşme ihlali: 2 → 0.**

---

## 6. BEFORE / AFTER (gerçek üretim)

| Metrik | BEFORE | AFTER | Δ |
|---|---|---|---|
| `official_value` kayıtları | 11 | 11 | 0 |
| R3 ile 🟢 | **2** | **2** | **0** |
| Birim uyuşmazlığı reddi (sentetik) | **0/5** | **5/5** | +5 |
| Dönem uyuşmazlığı reddi | ✅ | ✅ | 0 |
| Yanlış verified | 0 | 0 | 0 |
| Sözleşme ihlali (karar tablosu) | **2** | **0** | −2 |
| Test | 1.616 | **1.640** | +24 |

Kanıt motoru yeniden koşuldu (`claims_scored: 28`). **Hiçbir mevcut
doğrulama kırılmadı:** claim 208 ve 210 hâlâ 🟢 ve birimleri eşleşiyor.

---

## 7. Kalan riskler

1. **Seri belirsizliği** (§4.2) — dormant, kayda geçti, tasarım kararı bekliyor.
2. **`other` yakalama-hepsi metriği** — 53 iddia kullanıyor. Birim kısıtı
   riski daralttı ama metrik granülaritesi hâlâ zayıf.
3. **Dönem normalizasyonu yok** — `2026-6` ≠ `2026-06`. Fail-closed
   olduğu için güvenli; yalnızca meşru doğrulamaları kaçırabilir.
4. **`value` string kabul ediliyor** — `"7.6"` (string) doğrulanıyor
   çünkü `_same_number` `float()` deniyor. Zararsız, kayda geçti.
