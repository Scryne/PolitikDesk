# Karar İtirazları — Spec v3 D1–D15 İncelemesi

**Görev:** F0-01 · **Tarih:** 12 Ağustos 2026 · **Statü:** ✅ **Kapandı** — tamamı Spec v3.1'e işlendi (F0-02)

> Bu belge Spec §17'nin "değiştirmek için yazılı gerekçe gerekir" kuralının
> karşılığıdır: **v3.0 → v3.1 sürüm artışının gerekçesi budur.**

> Bu belge Spec v3'ün karar kaydını (§17) madde madde denetler. Her karar için
> **kabul** veya **gerekçeli itiraz** yazılmıştır. İtirazlar, şemayı ve kanıt
> motorunu uygularken ortaya çıkan somut çelişkilerden türemiştir — soyut
> tercih beyanı değildir.

---

## Özet

| Karar | Konu | Sonuç |
|---|---|---|
| D1 | ICP | ✅ Kabul |
| D2 | Çözülen problem | ✅ Kabul |
| D3 | Core Loop | ✅ Kabul |
| D4 | MVP dikeyi (makro ekonomi) | ✅ Kabul |
| D5 | MVP kapsamı (14 dahil / 22 hariç) | ✅ Kabul — bir kozmetik not |
| D6 | 8 kaynak sert sınırı | ⚠️ **İtiraz-2** — Faz 2'ye not olarak işlendi (F2-16 / B-37) |
| D7 | X API MVP'de kullanılmaz | ✅ Kabul |
| D8 | Evidence modeli (R0–R7) | ✅ **İtiraz-4 çözüldü** — v3.1 §8.3: R8 → R0, kanıt kurallarından önce, kısa devre |
| D9 | Salience formülü | ✅ **İtiraz-7 çözüldü** — v3.1 §8.4: global (0–90) saklanır, kişisel (0–10) hesaplanır |
| D10 | Editoryal profil | ✅ Kabul |
| D11 | Teknoloji yığını | ✅ **İtiraz-3 çözüldü** — v3.1 §11.5 effort karşılığıyla yazıldı |
| D12 | Modüler monolit | ✅ Kabul |
| D13 | Veri saklama | ⛔ **İtiraz-5 kapsam dışı** — mühendislik notu F2-02'ye taşındı |
| D14 | Kalite kapıları | ✅ **İtiraz-1 çözüldü** — v3.1 §13.3 + G0 #8a/#8b, G4 #7a/#7b |
| D15 | Trust & Safety sözleşmesi | ✅ Kabul |

**Karar:** D8 ve D9 itirazları **spec-freeze öncesi çözülmelidir** — ikisi de
kod yazılırken karşılaşılan somut çelişkilerdir ve Faz 2'de yeniden yazım
maliyeti doğurur. Diğerleri Spec'e not olarak işlenip fazlarına atanabilir.

**Uygulandı (12 Ağustos 2026, Spec v3.1):** dördü de spec-freeze öncesi
kapatıldı. Her itirazın altında ▶ **Çözüm** kutusu vardır.

---

## ⛔ İtiraz-4 — D8: R1 (çelişki) ile R8 (tahmin) çelişiyor

**Nerede:** Spec §8.3

Kurallar "sıralı, ilk eşleşen kazanır" olarak tanımlanmış ve R1 listenin
başında. R8 ise "EK KURAL" başlığı altında, en sonda:

> R1 → contradicted: ∃ e1,e2 … → **contradicted**
> R8 → tahmin kısıtı: claim_type = 'prediction' → durum **HER ZAMAN** unverified

Bir **tahmin** tipi iddia hakkında hem destekleyen hem çelişen Tier 1–2 kanıt
bulunduğunda ne olur? Sıra kuralına göre R1 kazanır → 🔴 `contradicted`.
R8'in metnine göre → ⚪ `unverified`. İkisi aynı anda doğru olamaz.

Bu kozmetik değil: "Piyasa faizin düşeceğini bekliyor" tipi bir iddia
makro ekonomi dikeyinde **çok sık** görülür ve iki kaynak farklı yön
söylediğinde R1 tetiklenir. Sonuç: bir tahmin, kırmızı "çelişkili" rozetiyle
gösterilir — oysa Spec §12.1'in azaltım listesinde "tahmin tipi iddia asla
doğrulanmış görünemez" der ve R8'in gerekçesi "gelecek doğrulanamaz"dır.
Çelişkili göstermek de bir doğrulama iddiasıdır: iki tahminden birinin
yanlış olduğunu ima eder.

**Önerilen çözüm:** R8'i sıralamanın **başına** al (R0 olarak yeniden numarala)
veya R1'e `claim_type <> 'prediction'` ön koşulu ekle. Birincisi daha
temiz — "tip kısıtları önce, kanıt kuralları sonra".

### ▶ Çözüm (Spec v3.1 §8.3)

Birinci seçenek uygulandı. Kurallar üç bloğa ayrıldı:

| Blok | Kurallar | Davranış |
|---|---|---|
| 1 — tip kısıtı | **R0** (tahmin) | Kanıta bakmaz; eşleşirse **kısa devre**, R1–R7 çalışmaz |
| 2 — kanıt kuralları | R1–R6 | Sıralı, ilk eşleşen kazanır |
| 3 — tavan kısıtı | R7 (yalnız Tier 4) | Blok 2'nin sonucunu yukarıdan sınırlar |

Kural sayısı değişmedi: **R0–R7 = 8 kural** (eski R8'in yerini R0 aldı).
F2-12'nin DoD'u ("8 kuralın her biri için birim testi") geçerliliğini korur;
DoD'a R0 kısa devresinin ayrı testi eklendi.

R0 tetiklendiğinde `status_reason` kanıt alanlarını yazmaz — hesaplanmadılar:

```json
{"rule": "R0", "short_circuit": "claim_type=prediction",
 "evaluated_evidence_rules": false, ...}
```

**DB kısıtının statüsü değişti.** `claims_prediction_always_unverified` artık
"geçici önlem" değil, R0'ın **ikinci savunma hattıdır** ve Spec §8.3'te bu adla
belgelenmiştir (`migrations/0003_salience_split.sql` kısıt yorumunu günceller).
Kural motorundaki bir hata sessiz yanlış etiket olarak değil, reddedilen INSERT
olarak ortaya çıkar.

**Yayılım:** `eval/golden_set_tools.py` (`VALID_RULES` = R0–R7, artı bir tahmin
iddiasının R0 dışında bir kuralla etiketlenmesini reddeden kontrol),
`tests/test_eval_tools.py`, `tests/test_schema.py`, README, Yol Haritası F2-12.

---

## ⛔ İtiraz-7 — D9: Salience formülü tek sütunlu şemaya sığmıyor

**Nerede:** Spec §8.4 ile §7.3 (`events.salience_score`) arasında

Formülün altıncı bileşeni:

> `+ 10 * kullanici_konu_ilgisi — editorial_profiles.topic_priorities eşleşmesi`

Bu bileşen **kullanıcıya özeldir**. Ancak şemada skor `events.salience_score
SMALLINT` — olay başına **tek** bir değer. İki kullanıcının farklı konu
öncelikleri varsa aynı olay için iki farklı skor gerekir; tek sütunda
saklanamaz.

Faz 4'te çok kullanıcıya geçildiğinde (F4-01) bu, ya sessizce yanlış
sonuç üretir (ilk kullanıcının tercihi herkese uygulanır) ya da şema
değişikliği gerektirir — tam olarak Spec'in "yanlış kurulursa 6. ayda
baştan yazılır" dediği durum.

**Önerilen çözüm:** Skoru ikiye ayır.

- **Global salience (0–90):** ilk beş bileşen. `events.salience_score`'a yazılır,
  deterministik, kullanıcıdan bağımsız, `salience_breakdown`'da şeffaf.
- **Kişisel ayarlama (0–10):** feed sorgusu sırasında kullanıcının
  `topic_priorities`'ine göre eklenir. Saklanmaz, hesaplanır.

UI'da gösterilen skor `global + kişisel`; popover kırılımda ikisi ayrı
satır olarak görünür (P4 şeffaflığı korunur, hatta artar: "bu olay senin
konu önceliklerinle eşleştiği için +8").

**Ek fayda:** Global skor kullanıcıdan bağımsız olduğu için önbelleklenebilir
ve F4-08'in feed p95 < 800 ms hedefini kolaylaştırır.

### ▶ Çözüm (Spec v3.1 §8.4 + §7.3)

Önerilen ayrım aynen uygulandı. Skor üç parçalı tanımlanır:

| Parça | Aralık | Saklanır mı | Nerede |
|---|---|---|---|
| Global salience | 0–90 | ✅ `events.salience_score` | §8.4/A — beş bileşen + cezalar |
| Kişisel ayarlama | 0–10 | ❌ sorgu anında hesaplanır | §8.4/B — `topic_priorities` örtüşmesi |
| Gösterilen skor | 0–100 | ❌ türetilir | §8.4/C |

**Kısıt yoruma bırakılmadı.** `migrations/0003_salience_split.sql` üst sınırı
100'den 90'a çekti (`events_salience_global_range`). Kişisel bileşeni
yanlışlıkla bu sütuna yazan bir kod yolu 90 üstü değer üretir üretmez
veritabanı tarafından reddedilir — sessiz yanlış sıralama yerine gürültülü
hata. Canlı şemada doğrulandı:
`tests/test_schema.py::test_salience_global_range_is_enforced_by_database`.

`salience_breakdown` yalnızca global bileşenleri ve cezaları taşır; kişisel
bileşen yanıtta ayrı alan olarak döner (saklanan alan kullanıcıdan bağımsız
kalmalıdır). Sütun yorumları da şemaya işlendi (`COMMENT ON COLUMN`).

---

## ⚠️ İtiraz-1 — D14 / G0 koşul 8: maliyet hedefi ölçek belirtmiyor

**Nerede:** Spec §13.3 ve Yol Haritası G0 koşul 8

> "Kullanıcı başına aylık maliyet ≤ 8 $ öngörüsü doğrulanmış"

Maliyet modeli koşuldu (`scripts/cost_model.py`, sonuçlar
`docs/veri-maliyet-modeli.md`). Bulgu:

| Ölçek | $/kullanıcı/ay | Hedef |
|---|---|---|
| 8 (kapalı beta) | **12,80** | ✗ |
| 10 | 11,03 | ✗ |
| 100 | 4,67 | ✓ |
| 1000 | 4,03 | ✓ |

Sebep yapısaldır: ingestion + embedding + kümeleme + özetleme maliyeti
**kullanıcı sayısından bağımsızdır** (ayda ~71 $). 8 kullanıcıya bölününce
kişi başı 8,84 $ yalnızca sabit taraftan gelir. Başabaş noktası **~18 kullanıcı**.

Bu bir model hatası değil, ürünün gerçek ekonomisidir — ve tam da bu yüzden
kapı koşulu **ölçek belirtmelidir.** Mevcut haliyle koşul ya kapalı betada
otomatik olarak tutmaz (ve G4'ü bloke eder), ya da "öngörü" kelimesine
sığınılarak geçilir — ikisi de kötüdür.

**Önerilen çözüm:** G0 koşul 8 ve G4 koşul 7 şu şekilde ikiye ayrılsın:

- **Birim ekonomi hedefi:** 100 aktif kullanıcı ölçeğinde ≤ 8 $/kullanıcı/ay
  (ürünün ölçeklenebilirlik kanıtı)
- **Beta bütçe tavanı:** kapalı beta boyunca **toplam** aylık maliyet ≤ 150 $
  (nakit gerçekliği; kişi başı rakam bu aşamada anlamlı değil)

Fiyatlandırma kararı (D19) da bu ayrımı kullanmalı: fiyat, 100 kullanıcı
ölçeğindeki birim maliyete göre belirlenir, beta ölçeğindekine göre değil.
(D19 sonradan kapsam dışına alındı — kişisel araç, müşteri yok.)

### ▶ Çözüm (Spec v3.1 §13.3 + kapılar)

Hedef ikiye ayrıldı ve her iki belgeye de işlendi:

| Hedef | Ölçüt | Nerede |
|---|---|---|
| **Birim ekonomi** | 100 aktif kullanıcı ölçeğinde ≤ 8 $/kullanıcı/ay | §13.3, G0 #8a, G4 #7a |
| **Beta bütçe tavanı** | Kapalı beta boyunca **toplam** ≤ 150 $/ay | §13.3, G0 #8b, G4 #7b |

Gerekçe (sabit maliyet ~71 $/ay, başabaş ~18 kullanıcı) G0 tablosunun altına
alıntı olarak eklendi; kapıyı okuyanın maliyet modeline gitmesi gerekmiyor.

---

## ⚠️ İtiraz-2 — D6: 8 kaynak sınırı ile R2 eşiği birlikte ölçülmeli

**Nerede:** Spec §9.2 (8 kaynak) ile §8.3 R2 (`bagimsiz_sayim >= 3`) arasında

MVP kaynak listesi: 4 resmî (TCMB, TÜİK, Hazine, Resmî Gazete) + 2 ajans
(AA, Reuters) + 2 bağımsız yayın. Bir olayda gerçekçi bağımsız sayım:

- **Sayısal resmî veri** (TÜİK enflasyon): R3 devreye girer, 3 teyit
  aranmaz → 🟢. **Sorun yok.**
- **Sayısal olmayan iddia** ("TCMB sıkı duruşu sürdürecek sinyali verdi"):
  R3 uygulanamaz. Bağımsız sayım = TCMB(1) + AA(1) + Yayın A(1) = 3 →
  R2 sınırda tutar. Ancak Yayın A veya B, AA metnini kopyalarsa (§8.2
  `wire:` anahtarı) sayım **2'ye düşer** → R4 → 🟡.

Yani MVP'de **sayısal olmayan iddiaların büyük kısmı 🟡'de kalacak**. Bu
teknik olarak doğrudur ve dürüsttür; ancak ürün algısı açısından bir risk:
kullanıcı sürekli sarı görürse etiketler bilgi taşımayı bırakır.

İtiraz "eşiği düşürelim" değildir — Spec §13.2'nin gerekçesi geçerlidir.
İtiraz, bunun **ölçülmeden bilinmemesidir.**

**Önerilen çözüm:** Faz 2 eval koşucusuna (F2-16) bir çıktı daha eklensin:
Golden Set üzerindeki `evidence_status` **dağılımı**. Eğer 🟢 oranı
%10'un altında kalıyorsa, bu bir kalite kapısı sorunu değil bir
**kaynak portföyü** sorunudur ve Faz 4 sonrası 9. kaynak kararının
(Spec §9.2) girdisi olur.

---

## ⚠️ İtiraz-3 — D11: §11.5'in sıcaklık disiplini seçilen modelde uygulanamıyor

**Nerede:** Spec §11.5

> "Sıcaklık: özetleme/çıkarım için 0–0.2, taslak üretimi için 0.6–0.8"

Seçilen model sınıfı (Claude Opus 5 / Sonnet 5) `temperature`, `top_p` ve
`top_k` parametrelerini **kabul etmiyor** — gönderilirse HTTP 400 döner.
Bu parametrelerin işlevsel karşılığı `output_config.effort` seviyesidir.

Spec'in **amacı** (çıkarım deterministik olmalı, üretim yaratıcı olabilir)
geçerli ve korunabilir; yalnızca mekanizma değişmiştir.

**Uygulanan çözüm:** `politikdesk/config.py` içinde `llm_effort_extraction=low`
ve `llm_effort_generation=high` ayarları. Sapma kod içinde açıkça belgelendi
ve `tests/test_llm_budget.py::test_no_sampling_parameters_are_sent` ile
regresyona karşı korundu.

**Spec'te yapılacak düzeltme:** §11.5'teki satır şu şekilde güncellensin:

> "Derinlik/kararlılık: çıkarım için düşük effort (`low`), taslak üretimi
> için yüksek effort (`high`). Sağlayıcı sıcaklık parametresi sunuyorsa
> çıkarımda 0–0.2, üretimde 0.6–0.8 kullanılır."

### ▶ Çözüm (Spec v3.1 §11.5)

Uygulandı. Satır ayrıca sapmanın **neden** var olduğunu ve nerede zorlandığını
taşıyor (config alanları + regresyon testinin adı). Kuralın amacı — çıkarım
deterministik, üretim yaratıcı — değişmedi; yalnızca sağlayıcıya bağlı
mekanizma yazıldı.

---

## ⚠️ İtiraz-5 — D13: embedding'in hukuki statüsü açık bırakılmış

**Nerede:** Spec §9.3 saklama tablosu

> Embedding — **süresiz** (türetilmiş veri)

`lead_paragraph` 30 gün sonra siliniyor (telif azaltımı), ancak ondan
türetilen embedding süresiz saklanıyor. "Türetilmiş veri" nitelemesi bir
mühendislik tanımıdır, hukuki bir tespit değildir.

İki soru açık:

1. **Telif:** Embedding, kaynak metnin korunmaya değer ifadesini içeriyor
   sayılır mı? (Uygulamada embedding'den metin kısmen geri çıkarılabildiği
   gösterilmiştir.)
2. **KVKK:** Bir haber metninde geçen isimli kişiye ait bilgi embedding'e
   gömülüyse, silme talebi (F4-12) embedding'i de kapsar mı? Kapsıyorsa
   `articles.embedding`'i tek tek silmek `events.centroid_embedding`'i
   bozar — bu bir **mimari** sorudur, sadece hukuki değil.

**Durum: ⛔ KAPSAM DIŞI.** Proje tek kullanıcılı kişisel bir araç olarak
kararlaştırıldı; hukuk danışmanlığı adımı kaldırıldı. Yine de **mühendislik
tarafı geçerliliğini koruyor**: `events.centroid_embedding` üyelerinden
yeniden hesaplanabilir kalmalı, artımlı güncellemeyle geri döndürülemez
hale gelmemelidir (F2-02). Bu, silme talebinden bağımsız olarak yanlış
kümelemeyi geri alabilmek için de gereklidir.

---

## ✅ Kabuller ve notlar

**D1–D4:** İtirazsız kabul. Makro ekonomi dikeyi seçimi (D4) özellikle
sağlam: sayısal doğrulanabilirlik hem Golden Set etiketlemesini hem de
R3 kuralını mümkün kılıyor. Bu iki şey olmadan kalite kapıları ölçülemezdi.

**D5 (kozmetik not):** §14.1'deki 14 özellik listesinde "kanıtsız olayda
üretim engeli" ayrı kalem değil. P1'in kod hâli olarak F3-11'de var, ama
kapsam listesinde görünmediği için "hariç" sanılabilir. Listeye 15. kalem
olarak eklenmesi öneririm — kapsam savunması listeye bakarak yapılıyor.

**D7:** Kabul. X API'yi MVP dışında bırakmak hem maliyet hem ToS riski
açısından doğru; Web Intent + pano yedeği sağlam.

**D10:** Kabul, güçlü karar. Şema seviyesinde zorlanabilir olması onu
beyan olmaktan çıkarıyor. `tests/test_schema.py` bunu hem statik hem canlı
şema üzerinde denetliyor.

**D12:** Kabul. `evidence/ → llm/` import yasağının statik olarak
denetlenebilmesi (F0-16), modüler monolitin en somut faydası.

**D15:** Kabul. 14 maddenin her birinin bir zorlama mekanizması olması,
listeyi etik beyandan mühendislik gereksinimine çeviriyor. `README.md`'de
bu mekanizmalar tablo olarak listelendi.

---

## D16–D20 durumu (Faz 0'da karara bağlanacaklar)

| # | Karar | Durum |
|---|---|---|
| D16 | Embedding modeli | ✅ **Verildi** — `multilingual-e5-large`; 60 gerçek çift, 3 aday, zor AUC 0,807 |
| D17 | Tier 3 kaynak isimleri | ✅ **Dünya + BloombergHT** — ikisi de canlı RSS ile doğrulandı |
| D18 | Hukuki konumlandırma | ⛔ Kapsam dışı — kişisel araç |
| D19 | Fiyatlandırma | ⛔ Kapsam dışı — müşteri yok |
| D20 | Kümeleme eşikleri | ⏳ Faz 2'ye ait; varsayılanlar `config.py`'de (0.86 / 0.78), benchmark ilk öneriyi üretecek |

---

## Sonraki adım — ✅ tamamlandı (12 Ağustos 2026)

| # | Adım | Durum |
|---|---|---|
| 1 | D8 (İtiraz-4) ve D9 (İtiraz-7) Spec'te düzeltilsin | ✅ §8.3, §8.4, §7.3 |
| 2 | D11 (İtiraz-3) §11.5 metni güncellensin | ✅ §11.5 |
| 3 | D14 (İtiraz-1) G0 #8 ve G4 #7 ölçek belirtsin | ✅ §13.3 + kapılar |
| 4 | D6 (İtiraz-2) ve D13 (İtiraz-5) faz görevlerine işlensin | ✅ B-37 → F2-16; İtiraz-5 mühendislik notu → F2-02 |
| 5 | **F0-02: spec-freeze**, `spec-v3.1` etiketi | ✅ Spec §0 (v3.1 bloğu) + §17 sürüm geçmişi |

> Not: itirazlar sürüm artışı gerektirdiği için etiket `spec-v3.0` değil
> **`spec-v3.1`**'dir (Spec §17 spec-freeze kuralı: "Değiştirmek için yazılı
> gerekçe + bu belgeye sürüm artışı gerekir"). Bu belge o yazılı gerekçedir.
