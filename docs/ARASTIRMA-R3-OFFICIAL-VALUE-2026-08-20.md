# Araştırma: R3 `official_value` Çıkarımı (Faz B8)

**Tarih:** 20 Ağustos 2026 · **Baseline:** HEAD `bd49af4`, 1.616 test, temiz ağaç
**Soru:** SBB gibi Tier 1 resmî yayınlardan sayısal değerler, mevcut epistemik
güvenlik modelini zayıflatmadan deterministik olarak çıkarılabilir mi?

**Cevap: HAYIR.** Kod değiştirilmedi.

---

## 1. Mevcut R3 mimarisi (Faz 0)

### Soru A — `official_value` neyi temsil ediyor?

Kurumun **makine okunur yayınından** gelen sayı. Yalnızca iki adaptör
doldurur: `tuik_sdmx` (SDMX gözlemi) ve `evds` (TCMB EVDS JSON).
`normalizer.py:214` onu `articles.official_value`'ya yazar.

### Soru B — Ne zaman "official"?

Adaptör `item.extra["normalized_value"]` koyduğunda. Bu alan **API
alanlarından** kurulur (`indicator.metric`, SDMX değeri, dataflow dönemi) —
düz metinden ayrıştırılmaz.

### Soru C — LLM `official_value` üretebilir mi?

**HAYIR.** LLM yalnızca iddia üstündeki `normalized_value`'yu üretir.
`FORBIDDEN_FIELDS` ayrıca modelin `evidence_status` üretmesini yasaklar.
**Production blocker yok** — tasarım doğru.

### Soru D — Yanlış parser değeri ne yakalar?

`_verified_against_official` iki yolu `metric` + `period` + `value`
**üçünde birden** karşılaştırır (`_same_number`, 1e-6 tolerans). Kısmi
eşleşme yetmez. Uyuşmazlık → bayrak kalkmaz → **fail-closed**.

### Soru E — Birden fazla sayı varsa?

Üçlü eşleşme ayırır: yanlış sayı seçilirse `metric` veya `period` tutmaz.

### R3'ün gerçek garantisi

```
API değeri  →  Türkçe cümle üret  →  LLM okur  →  API değeriyle karşılaştır
   (yol 1)                              (yol 2)
```

Bu bir **tur kontrolüdür (round-trip)**: iddianın sayısı kurumun yayımladığı
sayıyı sadakatle yansıtıyor mu? Halüsinasyona karşı gerçek koruma sağlar.

---

## 2. Kritik mimari sonuç: prose kaynakta iki yol ÇÖKER

SBB bir RSS/HTML kaynağıdır; makine okunur veri servisi değildir.
`official_value` üretmek için **düzyazıdan sayı ayrıştırmak** gerekir.

O zaman:

| | Bugün (TÜİK/EVDS) | SBB'de olurdu |
|---|---|---|
| Yol 1 | API alanı | **SBB düzyazısı** (regex) |
| Yol 2 | LLM, üretilmiş cümleyi okur | **SBB düzyazısı** (LLM) |

**İki yol da aynı cümleyi okur.** R3'ün tüm epistemik gücü iki *bağımsız*
türetmenin buluşmasından geliyordu; bu, "aynı metni iki kez okuyup kendini
doğrulama"ya iner — yani lastik damga.

Daha kötüsü: `official_value` sütununun **anlamı** sistem genelinde
değişirdi. Bugün "kurumun makine okunur yayını" demek; prose parser
eklenirse "birinin metinden okuduğu sayı" demeye başlar ve R3'ün mevcut
iki kullanıcısı (TÜİK, EVDS) da bu zayıflamış anlamı miras alır.

---

## 3. Gerçek SBB içeriği (Faz 1)

Saklanan 6 SBB makalesinin tamamı incelendi.

| ID | İçerik | Sayı | Sınıf |
|---|---|---|---|
| 47901 | "Kamu Sektörü İstihdam Sayıları 2026 2. Çeyrek" — özet başlığın tekrarı | yok | **C** |
| 47903 | "İşgücü Piyasasındaki Gelişmelerin Makro Analizi" — özet başlık | yok | **C** |
| 47905 | "Bütçe Gerçekleşmeleri Raporu … için tıklayınız." | yok | **C** |
| 47906 | KPSS yerleştirme duyurusu | tarih | **C** |
| 47902 | TÜFE — **4 sayı** iç içe: 1,78 · 0,35 · 31,75 · 2,59 | var | **B** |
| 47904 | İşgücü — **5 sayı**: 7,6 · 32.733.000 · 48,9 · 35.420.000 · 52,9 | var | **B** |

**6 makalenin 4'ünde hiç sayı yok.** Sayı içeren 2'sinde dört-beş farklı
metrik, birim ve dönem tek paragrafta karışık.

> Örneklem küçüktür ve bu **kaynağın kendi hacmidir**: SBB ayda ~10 kalem
> yayımlar. Görev 30 örnek istiyordu; mevcut olan 6'dır ve hepsi
> incelenmiştir. Daha büyük örneklem için haftalar beklenmesi gerekir —
> bu, kararın kendisini değiştirmez (aşağıdaki §4 belirleyicidir).

Ayrıca: `excerpt` Spec §9.3 gereği **≤300 karakter**. 47902'nin metni
zaten "…" ile kesik. Parser cümlenin tamamını göremez.

---

## 4. Ölçülen belirleyici kanıt: metrik bağlama hata oranı %50

Aynı SBB metninden LLM'in ürettiği `normalized_value`:

| Claim | Metin | LLM metriği | Doğru mu |
|---|---|---|---|
| 8711 | "İstihdam edilenlerin **sayısı** 32 milyon 733 bin **kişi**" | `employment_rate` | ❌ sayı ≠ oran |
| 8712 | "İstihdam **oranı** yüzde 48,9" | `employment_rate` | ✅ |
| 8713 | "**İşgücü** 35 milyon 420 bin **kişi**" | `participation_rate` | ❌ sayı ≠ oran |
| 8714 | "İşgücüne katılım **oranı** yüzde 52,9" | `participation_rate` | ✅ |
| 8715 | "TÜFE yüzde 1,78" | `tufe_monthly` | ✅ |
| 8716 | "yıllık **enflasyon** yüzde 31,75" | `ufe_annual` | ❌ TÜFE'yi ÜFE saymış |

**6 çıkarımın 3'ü yanlış metrik bağlamış (%50).**

Dikkat: 8711 ve 8712 **aynı** `metric` + `period` taşıyor ama değerleri
32.733.000 ve 48,9. Şema bunu kabul ediyor çünkü `unit` farklı.

### Kök nedenin bir kısmı şemadadır

`VALID_METRICS` yalnızca **oran** metrikleri içeriyor
(`employment_rate`, `participation_rate`, `unemployment_rate` …).
"İstihdam edilen kişi sayısı" veya "işgücü büyüklüğü" için **slot yok**.
LLM sayıyı mecburen bir orana sıkıştırdı — ve **deterministik bir parser
da aynı kısıtla karşılaşır.**

---

## 5. Extraction alternatifleri (Faz 3)

| # | Yaklaşım | Precision | Karar |
|---|---|---|---|
| A | Genel sayısal regex | çok düşük — 47904'te 5 aday sayı | ❌ |
| B | SBB'ye özel yapılandırılmış parser | orta; ama §2 gereği iki yol yine aynı metni okur | ❌ |
| C | Claim-güdümlü deterministik eşleşme | fail-closed, güvenli — ama §4'te LLM'in metriği %50 yanlış, dolayısıyla eşleşme çoğunlukla olmaz; olduğunda da §2'deki bağımsızlık sorunu sürer | ❌ |
| D | Bağlı resmî API/doküman | **epistemik olarak doğru** — ama SBB'nin makine okunur ucu **yok** (Faz B7'de 15 kurum yoklandı, yalnızca RSS bulundu) | ⏸ ön koşulu yok |

**D doğru cevaptır ama SBB için uygulanabilir değildir:** SBB'nin verisi
zaten TÜİK'ten gelir ve TÜİK'in SDMX ucu **hâlihazırda entegre**. Yani
SBB üzerinden aynı sayıya ikinci bir yol açmak, kaynağını zayıflatarak
tekrarlamak olurdu.

---

## 6. Epistemik risk analizi (Faz 5)

| # | Invariant | Bugün | Prose parser eklenirse |
|---|---|---|---|
| 1 | LLM `official_value` icat edemez | ✅ | ✅ (parser da LLM değil) |
| 2 | LLM doğrulama sonucunu belirleyemez | ✅ | ✅ |
| 3 | Resmî olmayan kaynak `official_value` üretemez | ✅ | ✅ |
| 4 | Sayı bağlamından koparılamaz | ✅ (API alanı) | **⚠ RİSK** — 5 sayılı paragraf |
| 5 | Dönem uyumsuzluğu engeller | ✅ | ✅ |
| 6 | Birim uyumsuzluğu engeller | ⚠ `unit` karşılaştırılmıyor | **⚠ AĞIRLAŞIR** |
| 7 | İki farklı değer birbirinin yerine geçemez | ✅ | **⚠ RİSK** |
| 8 | Revize veri sessizce çakışmaz | ✅ (period ayırır) | ✅ |
| 9 | Provenance saklanır | ✅ (EVDS `source_url` yazıyor) | ✅ |
| 10 | Ham kanıt doğrulanabilir | ⚠ excerpt ≤300 kr, kesik | **⚠ AĞIRLAŞIR** |

### Kayda geçen mevcut zayıflık (değiştirilmedi)

`_verified_against_official` `metric` + `period` + `value` karşılaştırıyor
ama **`unit`'i karşılaştırmıyor**. Bugün zararsız çünkü `official_value`
API'den geliyor ve birim seri tanımıyla sabit. Ama 8711/8712 örneği
gösteriyor ki aynı `metric` + `period` iki farklı birimle iki farklı
değer taşıyabiliyor. Prose parser eklenseydi bu **aktif bir yanlış
doğrulama yolu** olurdu.

> Bu bir düzeltme önerisidir, bu görevde uygulanmadı: `unit` karşılaştırmaya
> eklenirse invariant 6 güçlenir ve maliyeti sıfıra yakındır.
>
> **Mevcut iki 🟢 denetlendi (§8): birimlerin dördü de eşleşiyor**, yani
> bugün aktif bir arıza yok. Bu yüzden ölçülmüş bir arıza olmadan R3'ün
> karşılaştırma mantığına dokunulmadı — görev kuralı: *"R3 kurallarını
> ölçüm olmadan değiştirme."*

---

## 7. GO / NO-GO (Faz 6)

**NO-GO.** Gerekçeler, önem sırasıyla:

1. **Mimari:** prose parser, R3'ün iki-yol bağımsızlığını çökertir ve
   `official_value` sütununun anlamını sistem genelinde zayıflatır (§2).
2. **Ölçüm:** LLM'in metrik bağlama hata oranı bu kaynakta **%50** (§4);
   ikinci yol güvenilir değil.
3. **Şema:** `VALID_METRICS` SBB'nin yayımladığı büyüklükleri (kişi sayısı)
   **kapsamıyor**; parser da aynı duvara çarpar (§4).
4. **Hacim:** 6 makalenin 4'ünde hiç sayı yok; kalan 2'sinde 4–5 metrik
   iç içe (§3).
5. **Gereksizlik:** SBB'nin sayıları zaten TÜİK kökenlidir ve TÜİK SDMX
   **entegre** — ikinci ve daha zayıf bir yol açmanın kazancı yok (§5-D).

> Görev kuralı: *"Yanlış bir değeri official evidence olarak kabul etmek,
> hiçbir değer çıkaramamaktan daha kötüdür."* Ölçümler bu riski
> doğruluyor.

---

## 8. BEFORE / AFTER (Faz 8)

Kod değişmediği için üretim metrikleri kasıtlı olarak aynıdır:

| Metrik | BEFORE | AFTER |
|---|---|---|
| `official_value` taşıyan makale | **11** (`tcmb-evds` 8 + `tuik` 3) | 11 |
| `official_value` üreten kaynak | 2 | 2 |
| Tier 1 kanıt bağı | 82 | 82 |
| R3 ile 🟢 | 2 | 2 |
| Yanlış official value | 0 | 0 |

Mevcut iki 🟢 denetlendi — dördü de (iddia/resmî × metrik/birim) eşleşiyor:

| Claim | İddia metrik/birim | Resmî metrik/birim | Değer |
|---|---|---|---|
| 208 | `unemployment_rate` / `%` | `unemployment_rate` / `%` | 7,6 |
| 210 | `employment_rate` / `%` | `employment_rate` / `%` | 48,9 |

Yani §6'daki `unit` boşluğu **bugün aktif bir arıza değildir**; teorik bir
açıktır ve prose parser eklenseydi aktifleşirdi.

**🟢 artmadı ve bu beklenen sonuçtur** — hipotez ölçülüp reddedildiği için
uygulanmadı.

---

## 9. Doğru yol nedir?

R3'ün kapsamını genişletmenin epistemik olarak sağlam tek yolu, **yeni
makine okunur resmî uç** eklemektir — prose ayrıştırmak değil.

Faz B7'de 15 kurum yoklandı; hiçbirinde makine okunur veri ucu bulunamadı
(yalnızca SBB'de RSS). Dolayısıyla bu yol **şu an için kapalıdır**.

Sıradaki gerçekçi adımlar:

1. `OFFICIAL_STATISTICAL_SOURCES`'a kaynak eklemek **yalnızca** o kaynağın
   yapılandırılmış ucu varsa anlamlıdır. SBB için yoktur.
2. TÜİK SDMX kapsamını genişletmek (şu an işsizlik/istihdam/GSYH; TÜFE
   bu uçta **yok** — `sources.yml` notunda kayıtlı). Bu, mevcut ve
   kanıtlanmış yolu derinleştirir.
3. `VALID_METRICS`'e sayım (count) metrikleri eklemek — LLM'i orana
   sıkışmaya zorlamayı bitirir. Ayrı ölçüm ister.
4. `unit` karşılaştırmasını `_verified_against_official`'a eklemek (§6).

---

## 10. Sonuç

Hipotez ölçüldü ve reddedildi. Mevcut R3 tasarımı **doğrudur ve
korunmuştur**: `official_value` yalnızca kurumun makine okunur yayınından
gelir, LLM onu üretemez, doğrulama iki bağımsız yolun buluşmasını ister.

Bu sınırın gevşetilmesi 🟢 sayısını artırırdı — ve tam da bu yüzden
gevşetilmemelidir.
