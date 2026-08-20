# Denetim: Seri Granülaritesi ve Metrik Taksonomisi

**Tarih:** 20 Ağustos 2026 · **Baseline:** HEAD `0636065`, 1.640 test, temiz
**Soru:** Aynı `metric` + `unit` + `period` altında birden çok resmî seri
varsa, mevcut veri modeli doğru seriyi deterministik olarak ayırt edebilir mi?

**Sonuç:** Taksonomi genişletilmedi. Belirsizlik **minimal fail-closed
invariantla** kapatıldı.

---

## 1. Metrik taksonomisi — dört soru, kodla cevap

### Soru A — `metric` neyi temsil ediyor?

**Bir gösterge AİLESİNİ**, tekil bir seriyi değil. `VALID_METRICS`'te
21 slug var ve çoğu 1:1 karşılık bulur (`policy_rate`,
`unemployment_rate`); ama `exchange_rate` doğası gereği çok serilidir
(her para birimi için bir seri) ve `other` bir yakalama-hepsidir.

### Soru B — EVDS'in elinde `series_code` var mı, nerede kayboluyor?

Var. Kod boyunca izlendi:

| Katman | `series_code` |
|---|---|
| `evds.py:541` | **üretiliyor** (`spec.code`) |
| `normalizer.py:214` | `official_value`'ya kopyalanıyor |
| `articles.official_value` (DB) | **saklanıyor** (ölçüldü) |
| `tuik_sdmx.py` | **üretmiyor** |
| `claims.py` iddia şeması | **YOK** |
| `evidence/pipeline.py` | **okumuyordu** |

Yani alan kayboluyor değil — **taşınıyor ama kullanılmıyordu**.

### Soru C — İddia daha granüler bilgi üretebiliyor mu?

Kısmen. Gerçek veride para birimi **`unit` alanında zaten var**:
`USD`, `euro`, `TL`, `trillion USD`.

**Ama kur için işe yaramaz:** USD/TRY ve EUR/TRY'nin ikisinin de birimi
`TRY`'dir — çünkü `unit` *fiyatlanan* para birimini taşır, *baz* para
birimini değil. Kurda seri kimliği gerçekten şemada yoktur.

### Soru D — `series_code`'u iddia modeline eklemek?

LLM şeması değişikliği (`claims.py` JSON şeması) + prompt değişikliği +
golden set değişikliği. DB migration gerekmez (`normalized_value` jsonb).
**Ve LLM'e yeni epistemik yetki verir** — Spec §8.1'in kapatmak istediği
şey tam olarak budur.

---

## 2. Üretim belirsizlik analizi — TÜM metrikler

`(metric, normalize edilmiş unit, period)` gruplaması:

| Metric | Unit | Period | Farklı seri | Değerler |
|---|---|---|---|---|
| **exchange_rate** | try | 2026-08-19 | **2** | 47,8293 · 55,366 |
| **exchange_rate** | try | 2026-08-20 | **2** | 47,8467 · 55,5061 |
| employment_rate | % | 2026-06 | 1 | 48,9 |
| participation_rate | % | 2026-06 | 1 | 52,9 |
| policy_rate | % | 2026-06 | 1 | 37,0 |
| unemployment_rate | % | 2026-06 | 1 | 7,6 |
| tufe_annual | % | 2026-07 | 1 | 23,95 |
| reserves | *(boş)* | 2026-05 | 1 | 208.670,9 |
| other | *(boş)* | 2026-08-07 | 1 | 11.906,85 |

**Çakışma yalnızca `exchange_rate`'te.** Yapılandırılmış EVDS seri
listesi de bunu doğruluyor: 6 seriden yalnızca `exchange_rate` iki
seriye (USD, EUR) bağlı; diğerleri 1:1.

> Yani bu **genel bir taksonomi problemi değil**, çok serili tek bir
> metriğin özelliği.

### Yan bulgu (kayda geçti, düzeltilmedi)

`tufe_annual` metriği `TP.ENFBEK.PKA12ENF` serisine bağlı — bu
"12 ay sonrası yıllık enflasyon **beklentisi**", yani anket tahmini;
*gerçekleşmiş* yıllık TÜFE değil. Aynı metrik adı altında **tahmin** ile
**gerçekleşme** buluşuyor.

Bugün zarar vermiyor (ölçüldü): `tufe_annual` metrikli 9 iddianın hepsi
yıl sonu tahmini ve dönemleri `2026`/`2027`/`2028`; resmî kayıt
`2026-07` → **dönem eşleşmiyor, fail-closed**. Yine de metrik adlandırma
tutarsızlığı olarak kayda geçirildi.

---

## 3. Ulaşılabilirlik analizi

| Ölçüm | Değer |
|---|---|
| `metric='exchange_rate'` olan iddia | **0** |
| Kanıt kümesinde aynı `metric`+`period`'de >1 seri gören iddia | **0** |
| Herhangi bir resmî kanıt gören iddia | **8** |

Para birimi geçen sayısal iddialar incelendi (8 örnek): hiçbiri
`exchange_rate` metriğine düşmüyor — `other`, `public_debt`, `reserves`,
`budget_balance` alıyorlar.

**Sınıflandırma: UNREACHABLE** (kategori 1). Belirsizlik veritabanında
var, ama iddia hattı o metriği üretmiyor.

---

## 4. Tasarım alternatifleri

| # | Yaklaşım | Değerlendirme |
|---|---|---|
| **A** | `exchange_rate_usd` / `_eur` | Metrik patlaması (her yeni para birimi yeni slug); `VALID_METRICS` + prompt + golden set + `eval/golden_set_tools.py` birlikte değişir. **Ölçüm bunu haklı çıkarmıyor: 0 exchange_rate iddiası var.** |
| **B** | Ayrı `series` alanı | Aynı maliyet + **LLM'e yeni epistemik yetki** (Spec §8.1 ihlali) |
| **C-geniş** | Birden çok aday varsa reddet | Değer tek seriyi kesin belirlediğinde bile meşru doğrulamayı düşürür — bedeli bugün 0 ama yarın değil |
| **C-dar** | **İddianın değeri ≥2 farklı seriyle eşleşiyorsa reddet** | ✅ **SEÇİLDİ** — yalnızca gerçek belirsizlikte reddeder |
| **D** | Bileşik semantik anahtar | `unit` baz para birimini taşımadığı için kurda türetilemez (Soru C) |

### Neden C-dar?

Ayrım şudur:

* USD 47,8293 ≠ EUR 55,366 → iddia 47,8293 diyorsa **değerin kendisi**
  seriyi belirler. Doğrulama sağlamdır, reddetmek kayıptır.
* İki seri **aynı** değeri taşıyorsa hangisinin kastedildiği bilinemez.
  Doğrulamak, rastgele birini seçmektir.

**Ölçülen maliyet (üretim verisi):**

| Varyant | Düşen doğrulama |
|---|---|
| C-geniş | 0 |
| **C-dar** | **0** |

İkisi de bugün bedelsiz; C-dar gelecekte de bedelsiz kalır.

---

## 5. Karar: MINIMAL INVARIANT (taksonomi genişletilmedi)

`_verified_against_official` artık eşleşen resmî kayıtları **topluyor**
ve birden çok farklı `series_code` kaldıysa **fail-closed** davranıyor.

`series_code` taşımayan kayıtlar (TÜİK) tek kimlik sayılır — aynı
gözlemin iki kez kanıt kümesine girmesi doğrulamayı düşürmez.

**Bu değişiklik USD/EUR yanlış-etiketleme sorununu ÇÖZMEZ** ve bu
bilinçlidir: iddia "Euro 47,83" derse (gerçekte USD kuru) ve yalnızca
USD serisi eşleşirse doğrulanır. Onu çözmek seri kimliğini iddiaya
taşımayı, yani LLM'e yeni yetki vermeyi gerektirir — ve ölçüm bunu
haklı çıkarmıyor (0 `exchange_rate` iddiası).

---

## 6. BEFORE / AFTER

| Metrik | BEFORE | AFTER | Δ |
|---|---|---|---|
| Belirsiz resmî aday kümesi (DB) | 2 (`exchange_rate` × 2 dönem) | 2 | 0 |
| Ulaşılabilir belirsizlik | **0** | **0** | 0 |
| Aktif yanlış doğrulama | 0 | 0 | 0 |
| Resmî kanıt gören iddia | 8 | 8 | 0 |
| R3 ile 🟢 | **2** | **2** | **0** |
| Belirsizlikte fail-closed | ❌ yok | ✅ var | — |
| Test | 1.640 | **1.644** | +4 |

Kanıt motoru yeniden koşuldu (`claims_scored: 3`); claim 208 ve 210
hâlâ 🟢. **Hiçbir doğrulama kırılmadı.**

---

## 7. Kalan riskler

1. **USD/EUR yanlış etiketleme** — kapatılmadı (§5). Ulaşılabilir değil
   (0 `exchange_rate` iddiası). Çözümü metrik granülaritesidir ve ölçüm
   onu haklı çıkarmıyor.
2. **`tufe_annual` = beklenti serisi** (§2) — adlandırma tutarsızlığı;
   bugün dönem uyuşmazlığı koruyor.
3. **`other` yakalama-hepsi metriği** — 53 iddia; granülarite zayıf.
4. **`unit` biçim gürültüsü** — `"trillion USD"` vs `"USD"`; fail-closed
   olduğu için güvenli, yalnızca meşru eşleşme kaçırabilir.
