# Eşik Kalibrasyonu — D20 / F2-14

**Görev:** F2-14 · **Karar:** D20 · **Tarih:** 12 Ağustos 2026
**Koşucu:** `python -m eval.run --sweep` · **Veri:** `eval/golden_set_v1.jsonl` (55 makale, 36 olay)
**Embedder:** `intfloat/multilingual-e5-large` (D16)

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
