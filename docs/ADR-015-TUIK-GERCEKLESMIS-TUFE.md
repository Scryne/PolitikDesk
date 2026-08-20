# ADR-015: TÜİK SDMX Gerçekleşmiş TÜFE — ADR-014'ün Boşluğu Kapatıldı

**Durum:** Kabul edildi ve uygulandı
**Tarih:** 20 Ağustos 2026 · **Baseline:** HEAD `0a3b55a`, 1.652 test, temiz
**İlgili:** ADR-013 (seri belirsizliği), ADR-014 (ölçüm ≠ beklenti),
Spec §8.3 R3, §8.1 (LLM yetki sınırı)

---

## 1. Bulgu — önceki turun önermesi YANLIŞTI

**Finding.** ADR-014, `tufe_annual` için resmî doğrulama yolunu kapatırken
boşluğu şu gerekçeyle kabul etmişti: *"TÜİK SDMX ucunda TÜFE **yok**."*
Bu önerme **yanlıştır**.

**Evidence.** Canlı katalog bağımsız olarak yeniden sayıldı
(`nsiws.tuik.gov.tr/rest/dataflow/TR/all/latest`, 20 Ağu 2026):

| Ölçüm | Değer |
|---|---:|
| HTTP | **200** |
| Toplam veri akışı | **421** |
| Fiyat/enflasyon adayı | 27 |
| **TÜFE akışı** | **11** (`DF_TUFE_SDMX_TT01..TT10`, `TT05_O`) |

`all/all/latest` (tüm ajanslar) aynı 421 akışı döndürdü; başka ajans yok.

**Kök neden — ölçüm aracının kendisi.** `scripts/probe_tuik.py` akış
`id`sinde `("UFE", "ISGUCU", "GSYH")` arıyordu. `DF_TUFE_SDMX_TT10` bu
filtreye **UYUYOR** (`T-UFE`), ama betik çıktıyı `if shown >= 12: break`
ile kesiyordu ve TÜFE akışları listenin sonunda kalıyordu. Kesme
kaldırıldığında **56** akış eşleşti — yani eski sayım 44 akışı gizliyordu.

> Bir **görüntü kısıtı**, `config/sources.yml` notuna ve ADR-014'e
> "seri yok" diye geçti ve üç tur boyunca doğru kabul edildi.

**Decision.** Önerme düzeltildi, kök neden ölçüm aracında onarıldı
(kesme kaldırıldı, `TUFE` filtreye açıkça eklendi, çıktı artık
"TÜFE VARDIR" diyor). Yanlış notu taşıyan iki belge düzeltildi.

---

## 2. Seri semantik sözleşmesi

`DF_TUFE_SDMX_TT10` — *"Tüketici fiyat endeksi ve değişim oranları"*.

`all` sorgusu **yalnızca 5 seri** döndürür; seri tek boyutla tekilleşir.
`CL_DEGISIM` kod listesi (resmî metadata'dan okundu):

| DEGISIM | Resmî tanım | 2026-07 |
|---:|---|---:|
| 1 | Endeks | 132,31 |
| 2 | **Bir önceki aya göre değişim oranı (%)** | **1,78** |
| 3 | Bir önceki yılın Aralık ayına göre değişim (%) | 19,86 |
| 4 | **Bir önceki yılın aynı ayına göre (yıllık) değişim oranı (%)** | **31,75** |
| 5 | Oniki aylık ortalamalara göre değişim (%) | 31,90 |

```
series_code      TUIK:DF_TUFE_SDMX_TT10:DEGISIM_4
semantic         measurement          ← beklenti DEĞİL
metric           tufe_annual
unit             %
frequency        monthly (FREQ=M)
period_semantics referans ay, TIME_PERIOD = YYYY-MM
value_semantics  bir önceki yılın aynı ayına göre yüzde değişim
source_authority TÜİK (SDMX 2.1, DSD_TUFE 1.12)
R3 eligibility   YES
```

**Gerçekleşmiş mi?** Bilinen kamuya açık değerlerle çapraz doğrulandı:

| Dönem | Seri | Bilinen TÜİK manşet |
|---|---:|---:|
| 2024-07 | 61,78 | 61,78 ✅ |
| 2023-10 | 61,36 | 61,36 ✅ |
| 2022-10 | 85,51 | 85,51 ✅ |

Ayrıca SBB'nin resmî bülteni (üretimdeki makale 47902) aynı iki sayıyı
veriyor: *"Temmuz ayında TÜFE yüzde 1,78 ... yıllık enflasyon ... yüzde
31,75 düzeyinde gerçekleşmiştir."* İki bağımsız resmî kaynak birebir
uyuşuyor.

**4 ≠ 5.** "Yıllık değişim" (31,75) ile "12 aylık ortalamalara göre
değişim" (31,90) ayrı büyüklüklerdir. Yalnızca 4 izlenir; 5 izlenmez,
yani onunla doğrulama olmaz (test kilitler).

---

## 3. Karar — config değil, KOD (tek satır tablo)

`TRACKED` bir Python tablosudur (`sources.yml` seri metadata'sı taşımaz),
dolayısıyla "config-only" seçeneği **mevcut değil**. En küçük değişiklik
tabloya iki satır eklemektir; yeni soyutlama, yeni adaptör, yeni metrik,
migration, prompt/golden-set değişikliği YOK.

| # | Alternatif | Karar |
|---|---|---|
| A | SDMX → mevcut adaptör → config-only | ❌ `TRACKED` config'te değil |
| **B** | **Mevcut adaptöre iki `TrackedIndicator` satırı** | ✅ **seçildi** |
| C | Ayrı TÜFE adaptörü | ❌ aynı uç, aynı ayrıştırıcı — gereksiz |
| D | Yeni metrik (`cpi_realized`) | ❌ prompt + golden set + LLM yanlış-seçim riski |
| E | Semantic source metadata | ✅ B'nin içinde (aşağıda) |

**Pinlenen boyutlar:** `REF_AREA=TR`, `FREQ=M`, `SINIFLAMA_DUZEYI=TUFE`,
`DEGISIM=4`, `COICOP_2018=0`, `INDICATOR=F_TFE`.

**Bilerek pinlenmeyen:** `BASE_PER` (bugün 2025) ve `YAYIM_DONEMI`
(bugün 2026_01). İkisi de defter tutma boyutudur ve endeks yeniden baz
alındığında değişir; pinlenselerdi baz değişiminde seri sessizce
kaybolurdu. Pinlenmedikleri için TÜİK iki bazı aynı anda yayımlarsa
filtreye iki seri uyar ve adaptör **fail-closed** davranır.

---

## 4. Yol boyunca bulunan iki gerçek arıza

### 4.1 Başlık, resmî değeri YUVARLIYORDU (sessiz R3 kırığı)

Başlık `f"{value:.1f}"` ile yazılıyordu. İşgücü oranlarında bu görünmez
(7,6 · 48,9 zaten tek ondalık) ama TÜFE iki ondalıkla yayımlanır:

| Gerçek | Eski başlık | Yeni başlık |
|---:|---:|---:|
| 31,75 | **31,8** ❌ | 31,75 ✅ |
| 1,78 | **1,8** ❌ | 1,78 ✅ |
| 0,99 | **1,0** ❌ | 0,99 ✅ |
| 7,6 | 7,6 | 7,6 (aynı) |
| 48,9 | 48,9 | 48,9 (aynı) |

Zincir şöyle işler: adaptör başlığı yazar → LLM başlıktan iddiayı çıkarır
→ R3 iddiayı **aynı makalenin** `official_value`'suyla karşılaştırır.
Başlık "31,8" derken `official_value` 31.75 taşısaydı `_same_number`
(tolerans 1e-6) eşleşmez ve **yeni seri hiçbir zaman doğrulama
üretemezdi**. 208/210 🟢'leri tam bu zincirle oluşmuştu.

`format_value` en fazla iki ondalık yazar, gereksiz sıfırı atar, en az
bir ondalık bırakır — mevcut başlıklar **birebir** korunur.

### 4.2 TÜİK kayıtları kimliksizdi (ADR-013 invariantı TÜİK'te ölüydü)

ADR-013'ün belirsizlik invariantı `series_code` üzerinden çalışır. TÜİK
kayıtları bu alanı taşımıyordu; hepsi `""` kimliğine çöküyordu.
Karşı-olgusal ölçüldü (gerçek `_verified_against_official` çağrısı):

| Senaryo | Ölçülen |
|---|---|
| Kimliksiz **iki AYRI** ölçüm, aynı metric+value+unit+period | **`True`** ❌ |

`len({""}) == 1` olduğu için belirsizlik "tek seri" sanılıyordu. Aktif
arıza değildi (üç TÜİK göstergesinin metrikleri ayrı) ama TÜFE ile TÜİK
seri sayısı 3→5'e çıkıyor ve yüzey büyüyor. Adaptör artık kimlik
yayımlıyor; invariant TÜİK tarafında da anlamlı.

### 4.3 `semantic` beyanı TÜİK'te fail-open'dı

ADR-014 TÜİK kayıtlarını "beyansız → ölçüm" sayıyordu. Bu bugün doğru,
ama TÜİK kataloğunda **beklenti serileri de var**:
`DF_TUKETICI_EGILIM_SDMX` — *"Tüketici eğilimine ilişkin endeksler"*
(anket), canlı katalogda ölçüldü. Böyle bir seri ileride eklenirse
sessizce ölçüm sayılırdı. Beyan artık zorunlu ve test koruyor.

---

## 5. Semantik çarpışma — GERÇEK üretim kayıtlarıyla

Beklenti serisi aylık yayımlanır (`2026-07`) ve gerçekleşmiş yıllık TÜFE
de aynı ay damgasını taşır; dönem hizası **yapısaldır** (ADR-014).
İkisi artık gerçekten aynı anda veritabanında:

| Senaryo (gerçek `articles.official_value` satırları) | R3 |
|---|---|
| Yalnız TÜİK ölçümü | **True** ✅ |
| Yalnız EVDS beklentisi | **False** ✅ |
| İkisi birlikte, **aynı değer** | **True** (yalnızca ölçüm sayıldı) ✅ |
| Yalnız beklenti, değer eşitlenmiş | **False** ✅ |
| Yanlış dönem / yanlış birim | **False** ✅ |
| 12 aylık ortalama değeri (31,90) | **False** ✅ |

---

## 6. Üretim doğrulaması — uçtan uca

`pd deploy-check` **PASS** (kod özeti + git SHA üç konteynerde de senkron).

| Aşama | Sonuç |
|---|---|
| Discovery (katalog) | PASS — 421 akış, 11 TÜFE |
| HTTP (veri) | PASS — 200 |
| Parsing (SDMX-ML) | PASS — 5 seri |
| Seri seçimi | PASS — `DEGISIM=4` tekil |
| Normalization | PASS — 31.75 / `%` / `2026-07` |
| Canonicalization | PASS — dönem URL+guid'de |
| Topic filtering | PASS — `['enflasyon']` |
| Dedup | PASS — 2. tur `stored=0, exact_dupes=5` |
| Storage | PASS — makale 53258/53259 |
| Official evidence | PASS — `series_code` + `semantic` yazıldı |
| **R3 verification** | **PASS — claim 10437 🟢** |

```
claim 10437  tufe_monthly 1.78 % 2026-07
  -> rule R3, exception official_numeric_publication
  -> evidence_status: strongly_corroborated
claim 208 (R3) -> KORUNDU
claim 210 (R3) -> KORUNDU
2. kanıt motoru turu: claims_scored 0  (idempotent)
```

---

## 7. BEFORE / AFTER

| Metrik | BEFORE | AFTER | Δ |
|---|---:|---:|---:|
| `official_value` kaydı | 12 | 14 | +2 |
| **Gerçekleşmiş TÜFE kaydı** | **0** | **2** | **+2** |
| Beklenti kaydı | 1 | 1 | 0 |
| `series_code` taşıyan kayıt | 9 | 11 | +2 |
| `semantic` beyanlı kayıt | 0 | 2 | +2 |
| `tufe_annual` iddia | 9 | 9 | 0 |
| `tufe_monthly` iddia | 2 | 3 | +1 |
| Resmî kanıt gören `tufe*` iddia | 0 | **1** | **+1** |
| **R3 ile 🟢** | **2** | **3** | **+1** |
| Yanlış doğrulama yolu | 0 | 0 | 0 |
| Belirsiz doğrulama yolu (TÜİK) | 1 (dormant) | 0 | −1 |
| Test | 1.652 | **1.668** | +16 |

> Toplam iddia sayısı turlar arasında artar (worker arka planda çalışıyor);
> bu değişikliğin sonucu değildir.

---

## 8. `tufe_annual` neden hâlâ 0 iddia doğruluyor — ve bu neden sorun değil

Resmî kayıt **var** ve doğrulamaya **hazır** (§5'te gerçek kayıtla
kanıtlandı). Bugün eşleşen iddia yok, çünkü:

* Mevcut 9 `tufe_annual` iddiasının **hepsi yıl sonu TAHMİNİ**
  (dönem `2026`/`2027`/`2028`) — gerçekleşmiş aylık veri değil.
* Gerçekleşmiş yıllık TÜFE'yi taşıyan üretim iddiası **claim 8716**'dır
  (%31,75 · `2026-07`) ama metriği **`ufe_annual`** — yani *üretici*
  fiyat endeksi. Kaynak SBB bülteni açıkça TÜFE diyor; bu bir **LLM
  çıkarım hatası**dır.

R3 metrik eşitliği ister, dolayısıyla claim 8716 doğrulanmaz. **Bu doğru
davranıştır:** etiketi yanlış olan bir iddiayı doğrulamak, yanlış etiketi
🟢 ile mühürlemek olurdu. Düzeltmesi LLM çıkarımına dokunmayı gerektirir
ve bu turun sınırı dışındadır (Spec §8.1 — yeni epistemik yetki yok).

Kayda geçti: **B-8x — `ufe_annual`/`tufe_annual` çıkarım karışması**
(golden set adayı; ölçüldü, bu turda uygulanmadı).

---

## 9. Kalan riskler (yalnızca ölçülenler)

1. **Baz yılı değişimi.** `BASE_PER=2025`. TÜİK yeniden bazladığında
   akış bir süre iki bazı birlikte yayımlarsa filtreye iki seri uyar →
   fail-closed (öğe üretilmez, arıza kaydedilir). Sessiz yanlış veri
   değil, sessiz **eksik** veri riski.
2. **Revizyon.** TT10 tek vintage yayımlıyor (`YAYIM_DONEMI=2026_01`,
   2005-01→2026-07 boyunca tek seri) — revizyon geçmişi ayrı akıştadır
   (`TT05_O`). `official_value` bir **snapshot**'tır ve kayıt
   immutable'dır; TÜİK geçmiş bir değeri revize ederse eski kayıt eski
   değeri taşımaya devam eder. `lastNObservations=1` olduğu için yalnızca
   güncel dönem çekilir, yani revizyon pratikte yeniden çekilmez.
3. **Eski TÜİK kayıtları kimliksiz.** İşgücü kayıtlarının 3'ü
   `series_code` taşımıyor (guid tekilleştirmesi onları yeniden
   yazmıyor). Metrikleri ayrı olduğu için belirsizlik üretemezler;
   migration **gerekmedi**.
4. **`ufe_annual` çıkarım karışması** (§8) — dormant, kayda geçti.
5. **Katalog kayması.** Akış sayısı 427 (13 Ağu) → 421 (20 Ağu). Seri
   metadata'sı değişebilir; `probe_tuik.py` artık tam sayım yapıyor.
6. **Yeni TÜFE alt serileri.** TT01..TT09 izlenmiyor. İzlenmek istenirse
   `semantic` beyanı ve tekil pinleme zorunludur (test koruyor).

---

## 10. LLM sınırı — değişmedi

LLM yalnızca `normalized_value` üretmeye devam ediyor. Bu turda LLM
**hiçbir** yeni yetki almadı: `official_value`, `semantic`, seri seçimi
ve `evidence_status` deterministik olarak adaptör/motor tarafında üretilir.
Prompt, `VALID_METRICS` ve golden set **değiştirilmedi**.
