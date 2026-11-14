# Eşik Kalibrasyonu — D20 / F2-14

**Görev:** F2-14 · **Karar:** D20 · **Tarih:** 12 Ağustos 2026
**Koşucu:** `python -m eval.run --sweep` · **Veri:** `eval/golden_set_v1.jsonl` (55 makale, 36 olay)
**Embedder:** `intfloat/multilingual-e5-large` (D16)

---

## 2026-11-14 yeniden ölçüm (eşikler değişmedi: 0,92 / 0,88)

Aşağıdaki "Karar" bölümündeki 0,875 precision 12 Ağustos kodunun ölçümüdür; o
günden beri gösterge kısıtı (B-62) ve kaynak varlığı (B-63) eklendi. Bu tur
iş eşikte değil, varlık ve konu tarafında yapıldı.

**Bulunan iki ölçüm sorunu.**

1. *Donmuş varlıklar.* Koşucu varlıkları setteki `entities` alanından okuyor;
   bu alan etiketleme anındaki çıkarıcının çıktısı ve sözlük büyüdükçe eskiyor
   (55 makalenin 21'i donmuş alanda varlıksız, güncel çıkarıcıda 14). Sözlük
   değişikliği bu yüzden ölçülemiyordu. `--live-entities` varlıkları üretimdeki
   gibi yeniden çıkarır (kaynak slug'ı dahil, B-63).
2. *Bozulmuş etiketler.* W1 genişletmesi (`1641f33`) donmuş 55'lik insan
   etiketinde 11 makalenin `event_id`'sini gerekçesiz değiştirip ilgisiz
   haberleri tek olayda birleştirmişti (ör. Ziraat Bankası kârı + A101/CarrefourSA
   izni + katılım sigortası; VDK MİHENK + dış ticaret cezası + Resmî Gazete
   özeti). Bu 11 etiket `ac0e79f`'deki insan etiketine geri alındı. Her satıra
   `label_source` eklendi: `human_v1` (55, insan) ve `w1_unverified` (35, W1'de
   eklendi, insan onayı kaydı yok). **Hedef ölçüt yalnız `human_v1` üzerinden
   verilir**; 35'lik kısım ayrıca raporlanır ama karar dayanağı değildir.
   Geri almadan sonra 51 olayın 26'sı tek makaleli kaldı (`golden_set_tools
   validate` uyarısı); W1'in yeniden etiketlemesi büyük olasılıkla bu uyarıyı
   susturmak içindi. Uyarı doğrudur: çok kaynaklı olay sayısı az, çözüm 300'lük
   set (F2-20), birleştirilmiş sahte olay değil.

**Değişiklikler.** Varlık çıkarıcı kesmesiz Türkçe hâl eklerini uzun / çok
sözcüklü alias'larda tanır ("Bakanlığının", "Kurulunca"; kısaltmalar katı
kalır); 17 bakanlığa unvan alias'ı ("Ticaret Bakanı" → Ticaret Bakanlığı).
Gösterge kısıtına üç gösterge ailesi (H-ÜFE, Tarım-GFE, para-banka/rezerv)
ve üç belge türü ailesi (denetim raporu, kanun teklifi, bütçe teklifi) eklendi.
TÜFE → TÜİK gibi gösterge-kurum eşlemesi bilerek eklenmedi: "E-TÜFE" ENAG'ındır
ve TÜİK'e yazmak siyasi açıdan yanlış bir atıf olurdu.

`python -m eval.run --live-entities [--label-source …]`, `--review-as merge`:

| Küme | Ölçüt | Önce (donmuş varlık) | Önce (canlı varlık) | **Sonra (canlı)** |
|---|---|---|---|---|
| `human_v1` (55 / 36) | Pairwise precision | 1,000 | 1,000 | **1,000** |
| | Recall | 0,824 | 0,971 | **0,971** |
| | False merge | 0,000 | 0,000 | **0,000** |
| | Otomatik precision | 1,000 | 1,000 | **1,000** |
| Tamamı (90 / 51, etiket geri alınmış) | Pairwise precision | 0,839 | 0,846 | **1,000** |
| | Recall | 0,881 | 0,932 | **0,949** |
| | False merge | 0,038 | 0,038 | **0,000** |
| | Otomatik precision | 0,974 | 0,972 | **1,000** |
| `w1_unverified` (35 / 15) | precision / recall / FM | — | — | 1,000 / 0,920 / 0,000 |
| Yasama seti (12 / 5) | precision / recall / FM | 1,000 / 1,000 / 0 (elle varlık) | 0,636 / 0,778 / 0,200 | **0,692 / 1,000 / 0,250** |

Kötüleşen ölçüt yok. Yasama setinde false merge oranının 0,200 → 0,250
çıkması payda etkisidir: karışık küme sayısı önce de sonra da 1 (iki ayrı
Sayıştay raporu, aynı kurum + aynı belge türü; sözlükle ayrılamaz), düzelen bir
bölünme küme sayısını 5'ten 4'e indirdi. `--review-as split` (kuyruk tümüyle
reddedilirse) `human_v1`'de recall 0,441: denetim kuyruğu ölçümün yarısını
taşıyor, insan incelemesi işlemezse recall hedefin altına düşer.

**Sınır.** Sözlük eklemeleri aynı setin kaçırdıklarından türetildi; aynı sette
ölçülen iyileşme iyimserdir. Bağımsız ölçüm 300'lük set ister
(`eval/etiketleme/`). Demo derlemindeki yanlış birleşme (vergi teklifi +
Sayıştay) varlık kısıtının işi değildir — ikisi de TBMM'yi anar — ve artık
belge türü kısıtıyla ayrılır (`tests/test_clustering.py`).

---

## Karar

| Eşik | Eski (Spec §11.4 tahmini) | **Yeni (kalibre edilmiş)** |
|---|---|---|
| `T_HIGH` | 0,86 | **0,92** |
| `T_LOW` | 0,78 | **0,88** |

`politikdesk/config.py` varsayılanları güncellendi.

### Neden

| Ölçüt | 0,86 / 0,78 | **0,92 / 0,88** | G2 hedefi |
|---|---|---|---|
| Pairwise precision | 0,515 | **0,875** | ≥ 0,90 ❌ |
| Otomatik precision | 0,950 | **1,000** | ≥ 0,90 ✅ |
| Pairwise recall | 1,000 | **0,824** | ≥ 0,80 ✅ |
| **False merge (küme)** | 0,107 ❌ | **0,026** ✅ | ≤ 0,05 **pazarlıksız** |
| Denetime düşen | 14/55 | **7/55** | — |

Spec §11.4 precision'ı recall'a tercih eder: *"yanlış birleştirme, ayrı
kalmaktan daha zararlıdır — kullanıcı yanlış kanıtla içerik üretir."*
Kalibrasyon bu tercihi izler. Recall 1,000'den 0,824'e düşüyor ama hâlâ
hedefin üstünde; false merge dörtte bire iniyor.

---

## Tarama

`python -m eval.run --sweep` (T_LOW = min(0,78, T_HIGH − 0,02))

| T_HIGH | precision | oto. precision | recall | F1 | false merge | denetime düşen |
|---|---|---|---|---|---|---|
| 0,70–0,82 | 0,227 | 0,864 | 1,000 | 0,370 | 0,158 | 22/55 |
| 0,84 | 0,288 | 0,864 | 1,000 | 0,447 | 0,136 | 19/55 |
| 0,86 | 0,515 | 0,950 | 1,000 | 0,680 | 0,107 | 14/55 |
| 0,88 | 0,694 | 0,950 | 1,000 | 0,819 | 0,129 | 11/55 |
| 0,90 | 0,810 | 0,950 | 1,000 | 0,895 | 0,059 | 8/55 |
| **0,92** | 0,824 | **1,000** | 0,824 | 0,824 | 0,054 | 8/55 |
| 0,94 | 0,824 | 1,000 | 0,824 | 0,824 | 0,054 | 10/55 |
| 0,96 | 0,806 | 1,000 | 0,735 | 0,769 | 0,053 | 12/55 |
| 0,98 | 0,833 | 1,000 | 0,588 | 0,690 | 0,050 | 15/55 |

### T_LOW taraması (T_HIGH = 0,92 sabit)

| T_LOW | precision | recall | false merge | denetime düşen |
|---|---|---|---|---|
| 0,78 | 0,824 | 0,824 | 0,054 ❌ | 8/55 |
| 0,84 | 0,824 | 0,824 | 0,054 ❌ | 8/55 |
| **0,88** | **0,875** | **0,824** | **0,026** ✅ | **7/55** |
| 0,90 | 0,875 | 0,824 | 0,026 ✅ | 7/55 |

T_LOW'u 0,88'e çekmek false merge'ü yarıya indiriyor ve denetim kuyruğunu
küçültüyor. 0,90'da fark yok; 0,88 seçildi çünkü T_HIGH'a daha geniş bir
denetim bandı bırakır.

---

## İki ölçüm, iki farklı soru

Koşucu precision'ı **iki kez** raporlar ve bu ayrım kasıtlıdır:

| Metrik | Neyi ölçer |
|---|---|
| **Pairwise precision** | Denetim kuyruğu hiç işlenmemişken sistemin bıraktığı durum |
| **Otomatik precision** | Sistemin **sormadan** verdiği kararların kalitesi |

Denetim kuyruğuna düşen bir atama sistemin iddiası değil, **sorusudur**.
Otomatik precision'ın 1,000 olması, sistemin emin olduğu her seferinde
haklı olduğu anlamına gelir; belirsizlik doğru yere — insana — yönlendirilir.

Gerçek performans iki satırın arasındadır ve kuyruğun ne kadar iyi
işlendiğine bağlıdır. `--review-as split` (insan hepsini reddetti)
senaryosunda precision 0,950'ye çıkıyor, recall 0,559'a düşüyor.

---

## Bu kalibrasyonun sınırları

**1. Golden Set 55 makale — 5'lik kapı bu boyutta ölçülemez.**
36 gerçek olay, ~37 üretilen küme var. Tek bir karışık küme false
merge'ü 2,7 puan oynatıyor. G2'nin ≤ %5 koşulu 2 kümeye denk geliyor;
yani metrik **1–2 makalelik gürültüye** duyarlı. Kapıyı *karara bağlamak*
için F2-20'nin 300 makalelik seti gerekir. Buradaki sonuç bir **yön**
göstergesidir, bir kapı kararı değil.

**2. Veri kaynağı çeşitliliği dar.** Set, TCMB duyuruları + 13 haber
sitesinden derlendi ve olayların çoğu tek kaynaklı. Çok kaynaklı olay
sayısı 10; kümelemenin asıl işi olan "aynı olayı farklı kaynaklardan
birleştirme" bu 10 küme üzerinde ölçülüyor.

**3. Precision hâlâ hedefin altında (0,875 < 0,90).** Kalan hataların
tamamı **varlıksız makalelerden** geliyor: 55 makalenin 21'inde tanınan
varlık yok ve varlık kısıtı uygulanamıyor (`inconclusive` yolu). Eşik
ayarıyla kapatılacak bir açık değil — varlık sözlüğü kapsamı sorunu
(B-56).

---

## Yeniden üretim

```bash
export PD_EMBEDDING_PROVIDER=local
export PD_EMBEDDING_MODEL=intfloat/multilingual-e5-large

python -m eval.run                                  # mevcut eşiklerle
python -m eval.run --sweep                          # tarama
python -m eval.run --t-high 0.92 --t-low 0.88       # tek nokta
python -m eval.run --review-as split                # kuyruk reddedilmiş senaryosu
```
