# ADR-014: TÜFE Metrik Semantiği — Ölçüm ile Beklentinin Ayrılması

**Durum:** Kabul edildi ve uygulandı
**Tarih:** 20 Ağustos 2026 · **Baseline:** HEAD `ff15ee2`, 1.644 test, temiz
**İlgili:** Spec §8.3 R3, §8.1 (LLM yetki sınırı), ADR-013

---

## Bulgu

**Finding.** `metric` bir gösterge **ailesidir** ve iki farklı epistemik
nesneyi aynı ada çökertiyordu. EVDS'in `TP.ENFBEK.PKA12ENF` serisi
"12 ay sonrası yıllık enflasyon **beklentisi**"dir (piyasa katılımcıları
anketi) ama `metric="tufe_annual"` taşıyor — yani *gerçekleşmiş* yıllık
TÜFE ile aynı ad.

**Evidence.** Resmî seri envanteri (kod: `evds.py`, `tuik_sdmx.py`):

| series_code | kaynak | metric | gerçek semantik |
|---|---|---|---|
| TP.BISPOLFAIZ.TUR | EVDS | policy_rate | ölçüm |
| TP.DK.USD.A.YTL | EVDS | exchange_rate | ölçüm |
| TP.DK.EUR.A.YTL | EVDS | exchange_rate | ölçüm |
| TP.AB.B6 | EVDS | reserves | ölçüm |
| **TP.ENFBEK.PKA12ENF** | EVDS | **tufe_annual** | **BEKLENTİ (anket)** |
| TP.KAVRAMSAL.HAMM2.INDX | EVDS | other | ölçüm (M2) |
| — | TÜİK SDMX | unemployment/employment/participation_rate | ölçüm |

**`tufe_annual`'a bağlı TEK seri vardır ve o da beklentidir.** Sistemde
gerçekleşmiş yıllık TÜFE resmî serisi hiç yok.

Bu nedenle ADR-013'ün seri belirsizliği invariantı burada **yardım
etmiyor**: tek seri olduğu için `len(kimlikler) == 1` sağlanıyor ve
doğrulama geçiyor.

**Karşı-olgusal ölçüm** (gerçek `_verified_against_official` çağrıldı):

| Senaryo | Düzeltme öncesi | Epistemik doğru |
|---|---|---|
| Gerçekleşmiş iddia ← beklenti serisi | **`True`** | `False` ❌ |
| Her iki seri birlikte | `False` | — |
| Dönem farklı | `False` | `False` ✅ |

Bir anket beklentisi, olmuş bir olguyu doğrulayamaz. R3'ün verdiği 🟢
ürünün en güçlü etiketidir; bu tam anlamıyla lastik damga olurdu.

**Üretim ulaşılabilirliği (ölçüldü):**

| Ölçüm | Değer |
|---|---|
| `metric='tufe_annual'` iddia | 9 (hepsi *tahmin*, dönem `2026`/`2027`/`2028`) |
| Bunlardan resmî kanıt göreni | **0** |
| Beklenti serisini kanıt olarak gören iddia | **0** |
| Aktif yanlış doğrulama | **0** |

Gerçekleşmiş yıllık enflasyon iddiası **var** (claim 8716, %31,75,
dönem `2026-07`) ve dönemi resmî beklenti kaydıyla **birebir aynı**;
bugün yalnızca değerler farklı olduğu için çarpışmıyor.

> Dönem hizası tesadüf değil **yapısaldır**: beklenti serisi aylık
> yayımlanır (`2026-07`) ve gerçekleşmiş yıllık TÜFE de aynı ay damgasını
> taşır. Değerler yakınsadığı gün çarpışma kendiliğinden oluşur.

**Decision.** Aktif arıza yok, ama **gerçekçi karşı-olgusal collision
fail-open ölçüldü** → görev kuralı 2 sağlandı. Minimal fail-closed
invariant eklendi.

---

## Karar

Ayrım **kaynak tarafında** beyan edilir; iddia tarafına yeni alan
eklenmez.

```python
EvdsSeries(code="TP.ENFBEK.PKA12ENF", ..., semantic="expectation")
```

R3 yalnızca `semantic == "measurement"` serilerini kabul eder.

### Neden iddia tarafında değil

İddia şeması semantik tip taşımıyor ve LLM'e ürettirmek **yeni epistemik
yetki** olurdu (Spec §8.1). Kaynak ise ne yayımladığını deterministik
olarak bilir — bilgi zaten `label` ve `qualifier` alanlarında duruyordu,
yalnızca makine okunur hâle getirildi.

### Neden metrik ayrılmadı (Alternatif A reddedildi)

`tufe_annual` → `inflation_expectation_12m` ayrımı `VALID_METRICS` +
prompt + golden set + `eval/golden_set_tools.py` değişikliğini birlikte
gerektirir ve **LLM'in yanlış metrik seçmesi** diye yeni bir hata sınıfı
açar. Ölçüm bunu haklı çıkarmıyor: mevcut 9 `tufe_annual` iddiasının
hiçbiri resmî kanıt görmüyor.

### Eski kayıtlar — migration gerekmedi

İki yol birlikte çalışır:

* `semantic` alanı varsa doğrudan okunur (yeni kayıtlar).
* Yoksa `series_code` kaynak yapılandırmasına sorulur
  (`_non_measurement_series`, `TRACKED`'dan türetilir).

Veritabanında **hâlihazırda duran** beklenti kaydı ikinci yolla kapsanır.

### Fail-open bırakılan yer (bilinçli)

`series_code` **ve** `semantic` taşımayan kayıtlar ölçüm sayılır. TÜİK
SDMX kayıtları böyledir ve hepsi gerçekleşmiş veridir; aksi hâlde
üretimdeki iki R3 🟢'si sebepsiz kırılırdı.

---

## Alternatifler

| # | Yaklaşım | Karar |
|---|---|---|
| A | Metriği ayır (`inflation_expectation_12m`) | ❌ prompt + golden set + LLM yanlış-seçim riski; ölçüm haklı çıkarmıyor |
| **B** | **Kaynak tarafında semantik tip** | ✅ **seçildi** — LLM'e yetki vermez, migration istemez |
| C | `series_code` whitelist per metric | ❌ B'nin daha kırılgan hâli; her metrik için elle liste |
| D | Belirsizlikte fail-closed | ⏸ ADR-013'te zaten var; tek seri olduğu için burada tetiklenmiyor |
| E | Yeni semantik taksonomi | ❌ A'nın büyüğü; ölçüm haklı çıkarmıyor |

---

## BEFORE / AFTER

| Metrik | BEFORE | AFTER | Δ |
|---|---|---|---|
| Toplam iddia | 6.433 | 6.433 | 0 |
| `tufe_annual` iddia | 9 | 9 | 0 |
| Beklenti serisi resmî kaydı | 1 | 1 | 0 |
| Gerçekleşmiş TÜFE resmî kaydı | **0** | **0** | 0 |
| Ulaşılabilir semantik collision | 0 | 0 | 0 |
| **Karşı-olgusal fail-open collision** | **1** | **0** | **−1** |
| R3 ile 🟢 | **2** | **2** | **0** |
| Yanlış doğrulama yolu | 1 (dormant) | 0 | −1 |
| Test | 1.644 | **1.652** | +8 |

> Toplam iddia sayısı, worker arka planda çalışmaya devam ettiği için
> turlar arasında artar; BEFORE ve AFTER aynı anda ölçülmüştür ve bu
> değişikliğin sonucu değildir.

**Mevcut 🟢'ler yeni mantıkla tek tek yeniden sınandı** (`ENGINE_VERSION`
değişmediği için pipeline onları yeniden puanlamaz):

```
claim 208 (R3) İşsizlik oranı   -> True  KORUNDU
claim 210 (R3) İstihdam oranı   -> True  KORUNDU
Beklenti serisini kanıt olarak gören iddia: 0
```

Kanıt motoru iki kez koşuldu; `claims_scored: 0` — **idempotent**.

---

## Kalan riskler

1. ~~**Gerçekleşmiş yıllık TÜFE resmî serisi yok.**~~ `tufe_annual` artık
   hiçbir resmî kayıtla doğrulanamaz — çünkü tek kaydı beklentiydi ve
   artık reddediliyor. Bu **doğru** davranıştır (yanlış doğrulamadansa
   doğrulamamak), ama boşluk kayda geçti: TÜİK SDMX ucunda TÜFE **yok**
   (`config/sources.yml` notunda kayıtlı).

   > ⚠ **DÜZELTİLDİ — ADR-015 (20 Ağustos 2026).** Bu maddenin dayandığı
   > "TÜİK SDMX'te TÜFE yok" önermesi **YANLIŞTI**. Canlı katalog
   > bağımsız olarak yeniden sayıldığında 421 akıştan 11'inin TÜFE
   > olduğu görüldü (`DF_TUFE_SDMX_TT01..TT10`). Yanlış kayıt bir
   > ölçüm hatasından doğmuştu: `scripts/probe_tuik.py` eşleşen akışları
   > 12 satırda kesiyordu ve `DF_TUFE_SDMX_TT10` kesilen kısımda kalıyordu.
   > Boşluk ADR-015 ile kapatıldı.
   >
   > Aynı turda bu ADR'deki bir ölçüm hatası daha düzeltildi: claim 8716
   > `tufe_annual` değil **`ufe_annual`** metriği taşıyor (üretimde
   > doğrulandı). Yani beklenti kaydıyla "yalnızca değerler farklı olduğu
   > için" çarpışmıyor değildi — metrikleri de farklıydı. Bu, ADR-014'ün
   > **kararını değiştirmez** (beklenti serisinin reddi bağımsız olarak
   > doğrudur), yalnızca gerekçedeki bir ayrıntıyı düzeltir.
2. **`ENGINE_VERSION` bilerek artırılmadı.** Ölçüldü: beklenti serisiyle
   doğrulanmış iddia **0**, dolayısıyla geriye dönük yeniden puanlama
   gereksiz. Artırmak 6.433 iddianın tamamını yeniden hesaplatırdı.
3. **`other` yakalama-hepsi metriği** — semantik granülarite hâlâ zayıf
   (ADR-013 §7'de kayıtlı).
4. **Diğer beklenti serileri** ileride eklenirse `semantic="expectation"`
   beyanı unutulabilir. Test bunu kısmen koruyor
   (`test_evds_expectation_series_declares_its_semantic`).
