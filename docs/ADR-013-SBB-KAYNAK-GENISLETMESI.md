# ADR-013: SBB Kaynak Genişletmesi ve Kanıt Motoru Etki Ölçümü

**Durum:** Kabul edildi ve uygulandı
**Tarih:** 20 Ağustos 2026
**Karar Vericiler:** Ürün sahibi (kapasite kararı) · Veri & Altyapı Mühendisliği
**İlgili:** Spec §9.2 / D6 (kaynak sınırı), Spec §8.2 (bağımsızlık), §8.3 R2
**Öncesi:** `docs/KAYNAK-GENISLETME-2026-08-20.md`

---

## 1. Karar

1. `config/sources.yml` içindeki `max_sources` **21 → 22** yapıldı.
2. **SBB** (Cumhurbaşkanlığı Strateji ve Bütçe Başkanlığı) Tier 1 resmî
   kaynak olarak envantere alındı.
3. SBB **ayrı** bir `independence_group` (`official-sbb`) taşır.

> **`max_sources=22`, doğrulanmış TEK bir kaynağın (SBB) alınması için
> yapılmış bilinçli bir kapasite değişikliğidir; genel bir kaynak sınırı
> gevşetmesi DEĞİLDİR.**
>
> Bu ayrım kodla korunur: `max_sources` her zaman kaynak sayısına eşittir
> (`test_cap_has_no_silent_headroom`). Sınırda boşluk bırakılmadığı için
> bir sonraki kaynak MUTLAKA sınırı da değiştirmek zorundadır ve o
> değişiklik testi kırar — yani hiçbir kaynak "sınırın altında yer vardı"
> diye sessizce eklenemez.

---

## 2. `independence_group` kararının kapsamı ve sınırı

SBB'ye ayrı grup verilmesi **siyasi bağımsızlık iddiası değildir.**

Spec §8.2'nin engellemek istediği somut şey, aynı yayın grubunun iki
sitesinin iki bağımsız teyit sayılmasıdır (hurriyet + milliyet +
cnnturk = bir tane, üç değil). SBB'nin kendi yayın sorumluluğu, kendi
sitesi ve kendi analitik çıktısı vardır; `hazine` veya `tcmb`nin ikinci
bir sitesi değildir. Ayrı grup bunun metadata karşılığıdır.

**Mevcut semantik korundu; yeni kural icat edilmedi.** Aynı kurumun iki
akışı için zaten bir mekanizma var (`same_institution_as`, EVDS/TCMB
örneği) ve SBB onu kullanmıyor çünkü ayrı bir kurumdur.

### Kalan risk (kayda geçirildi)

SBB ile `cb-kararname` aynı hiyerarşiye bağlıdır. Cumhurbaşkanlığı bir
açıklama yapıp SBB onu yinelerse, kanıt motoru ikisini AYRI bağımsız
kaynak sayar. Bugün olası değil (SBB veri yorumu yayımlar, cb-kararname
kararname), ama izlenmelidir. Gerçekleşirse çözüm hazırdır:
`same_institution_as: cb-kararname` beyanı — yeni kural gerekmez.

⚠ Daha genel bir yapısal not: `merge_key` (Spec §8.2 kural 1)
`independence_group` tanımlıysa kopya tespitini **kısa devre yapar**.
21 kaynağın tamamında grup tanımlı olduğu için kopyala-yapıştır ve ajans
kopyası kuralları yapılandırılmış kaynaklar arasında fiilen devrede
değildir. Bu SBB ile gelmedi, **önceden vardı**; motorun bağımsızlık
sayımı bu noktada metadata'ya güvenir. Bu yüzden config sözleşmesi
(her kaynak tek ve ayrı grup) testle korunur.

---

## 3. Kanıt motoru etki ölçümü — BEFORE / AFTER

Ölçüm gerçek üretim veritabanında, aynı sorgu seti ile iki kez koşuldu.

| Metrik | BEFORE | AFTER | Δ |
|---|---|---|---|
| Toplam iddia | 5.281 | 5.376 | +95 |
| 🟢 `strongly_corroborated` | **2** | **2** | **0** |
| R2 tam koşulunu sağlayan iddia | **0** | **0** | **0** |
| Tier 1 kanıtı olan iddia | 70 | **77** | **+7** |
| ≥3 bağımsız grup (tier≤3) | 42 | 43 | +1 |
| Tier 1 kanıt bağı | 75 | **82** | **+7** |
| Tier 1 makale | 40 | **43** | +3 |
| 🟠 `single_source` | 4.569 (%86,5) | 4.653 (%86,6) | — |
| R7 tavanlanan | 158 | 165 | +7 |

### SBB'nin ölçülen katkısı

| Ne | Değer |
|---|---|
| Çekilen kalem | 10 |
| Konu filtresinden geçen | 6 |
| Saklanan makale | 6 |
| Oluşan olay | 6 (hepsi tek makaleli) |
| Mevcut olaya atanan | **0** |
| Çıkarılan iddia | 7 (2 reddedildi) |
| Kanıt bağı | 7 |
| Yeşile dönen iddia | **0** |

---

## 4. 🟢 neden artmadı — kök neden analizi

**Bu bir başarısızlık gizlemesi değildir; ölçülen sonuç budur.**

R2 iki ayak ister: **(a)** ≥3 bağımsız grup, **(b)** Tier 1 birincil
kaynak. SBB **(b)'yi sağladı, (a)'yı sağlamadı.**

SBB'nin 7 iddiasının durumu:

```
8710  prediction  unverified     R0  (tip kısıtı — tasarım gereği)
8711  number      single_source  R5  independent_count=1  has_primary_source=TRUE
8712  number      single_source  R5  independent_count=1  has_primary_source=TRUE
8713  number      single_source  R5  independent_count=1  has_primary_source=TRUE
8714  number      single_source  R5  independent_count=1  has_primary_source=TRUE
8715  number      single_source  R5  independent_count=1  has_primary_source=TRUE
8716  number      single_source  R5  independent_count=1  has_primary_source=TRUE
```

Altısında Tier 1 ayağı **açık** (`has_primary_source: true`) ama bağımsız
grup sayısı 1 — çünkü SBB'nin makaleleri kendi olaylarında yalnız.

### Neden yalnız kaldılar?

Kümeleme turu: **6 olay oluşturuldu, 0 atandı.** İki bağımsız sebep
ölçüldü:

**(1) Aynı hikâyeyi kimse yazmamış.** Temmuz TÜFE verisi (SBB iddia
8715: "TÜFE yüzde 1,78 oranında artmıştır") için 1–12 Ağustos
penceresinde medya kapsamı: `cumhuriyet-ekonomi` (2), `trthaber` (1),
`x-tuik` (1). Ama başlıkları okuyunca görülüyor ki bunlar **aynı hikâye
değil**:

```
x-tuik      03 Ağu  TÜFE Temmuz 2026 (TÜİK'in kendi duyurusu)   <- aynı hikâye
trthaber    07 Ağu  "Yılın üçüncü enflasyon raporu 13 Ağustos'ta..."
cumhuriyet  07 Ağu  "Kritik toplantıya günler kaldı: MB enflasyon..."
cumhuriyet  11 Ağu  "Gözler MB'nin Enflasyon Raporu'nda..."
```

Medya *veri açıklamasını* değil, *gelecek raporu ve MB toplantısını*
işliyor. Bunlar farklı olaylardır ve kümeleme onları ayırmakta HAKLIDIR.

**(2) Zaman penceresi.** SBB ile aynı hikâyeyi paylaşan tek kaynak
`x-tuik` (3 Ağustos). SBB'nin yorumu 7 Ağustos. Kümeleme birleştirme
penceresi **72 saat** (`assigner.DEFAULT_TIME_WINDOW_HOURS`), aday
penceresi 96 saat. 4 günlük fark pencerenin dışında.

Ayrıca `x-tuik` Tier 4'tür; birleşselerdi bile bağımsız sayım 2 olurdu
(SBB + TÜİK-sosyal), 3 değil.

### Sonuç: darboğaz yer değiştirdi

Denetimin ilk teşhisi "Tier 1 kanıt yetersiz" idi ve **doğruydu** — SBB
o açığı ölçülebilir biçimde kapattı (Tier 1 kanıt bağı 75 → 82).

Ama 🟢'nin önündeki engel artık **kaynak sayısı değil**:

> **Aynı makro hikâye, kaynaklar arasında ortak bir olayda buluşmuyor.**

Üç sebebi ölçüldü:
1. Medya, resmî veri açıklamasını değil çevresindeki yorumu işliyor.
2. Resmî yayın ile medya yorumu arasındaki gecikme 72 saatlik birleştirme
   penceresini aşabiliyor.
3. Aynı hikâyeyi paylaşan kaynaklardan bazıları Tier 4 (R7 tavanı).

Kaynak eklemeye devam etmek bu üçünü çözmez. Yol haritası buna göre
güncellendi (`docs/YOL-HARITASI-2026-08-20.md`, Faz B).

---

## 5. Yapay yeşil riski — sınandı

**Soru:** SBB yanlış gruplama nedeniyle bir iddiayı yapay olarak yeşile
çevirebilir mi?

**Cevap:** Metadata doğruysa hayır; metadata yanlışsa evet — ve bu yüzden
metadata testle korunur.

Testlerle kilitlenen davranışlar (`tests/test_sbb_source_expansion.py`):

| Senaryo | Beklenen | Test |
|---|---|---|
| Tek başına SBB | 🟢 DEĞİL | `test_sbb_alone_cannot_make_a_claim_green` |
| SBB + 1 medya (2 grup) | 🟢 DEĞİL | `test_sbb_plus_one_media_cannot_make_a_claim_green` |
| SBB + 5 sosyal hesap | 🟢 DEĞİL | `test_sbb_plus_social_cannot_make_a_claim_green` |
| 3 medya, Tier 1 yok | 🟢 DEĞİL | `test_three_media_without_tier1_is_not_green` |
| Aynı SBB 3 kez | `independent_count=1` | `test_sbb_contribution_comes_from_group_diversity_not_tier_alone` |
| SBB + 2 bağımsız medya | 🟢 (R2) | `test_sbb_enables_r2_when_it_genuinely_corroborates` |

Son satır kaynağın eklenme gerekçesinin davranış karşılığıdır: aynı
senaryo SBB'siz 🟡 kalır, SBB ile 🟢 olur — çünkü eksik olan tek şey
Tier 1 birincil kaynaktı.

R2 eşiği değiştirilmedi (`strong_min_sources() == 3`,
`test_r2_threshold_unchanged`).

---

## 6. Canlı feed doğrulaması

İzole tur (`sbb` kaynağı, üretim kod yolu):

| Aşama | Sonuç |
|---|---|
| Kaynak keşfi | id=7286, tier=1, `grp:official-sbb`, aktif |
| HTTP + robots | 200, RssAdapter, robots `/feed/`e açık |
| Ayrıştırma | 10 kalem |
| Normalizasyon | `www.` soyuldu, sondaki `/` kaldırıldı, hash+simhash üretildi |
| Canonical URL | 6/6 `https://` |
| Konu filtresi | 6/10 kapsamda |
| Tekilleştirme | 0 tam tekrar, 0 yakın tekrar |
| Güvensiz URL | 0 reddedilen |
| Saklama | 6 makale |
| Atıf | 6/6 `independence_key = grp:official-sbb` |
| Hata | 0 |

**Regresyon yok:** tam tur öncesi/sonrası kaynak sağlığı, ui_check (48
viewport) ve deploy-check aynı sonucu verdi.

### Yan gözlem — konu sözlüğü boşluğu

SBB'nin en ayırt edici iki kalemi konu filtresinden **elendi**:

```
[ELENDI] 2026 yılı Haziran ayı Ödemeler Dengesi Verileri açıklandı
[ELENDI] 2026 yılı Temmuz ayı geçici Dış Ticaret Verileri açıklandı
```

`topics.py` sözlüğünde `odemeler_dengesi` ve `dis_ticaret` konuları YOK.
Bu bir kusur değil, kapsam kararıdır — ama SBB'den beklenen katkıyı
daraltır ve ürün sahibinin bilmesi gerekir.

Ayrıca bir yanlış pozitif görüldü: "KPSS-2026/1 Yerleştirme Sonuçları"
`butce_ve_hazine` olarak sınıflandı. Tekil ve düşük etkili; kayda geçti.

---

## 7. Doğrulama

| Kapı | Sonuç |
|---|---|
| pytest | **1.616 geçti** (+17: 16 SBB + 1 boşluk koruması) |
| ruff | temiz |
| mypy | 175 dosya, hata yok |
| check_architecture / verify_arch_guard | temiz |
| pip-audit | açık yok |
| Playwright XSS sondası (gerçek Chromium) | **0 çalışan vektör** |
| Lighthouse Accessibility | **12/12 ekran 100** |
| ui_check | 48 viewport temiz |
| deploy-check | api + worker + beat senkron |
