# eval/ — Ölçüm eserleri

Spec §13'ün (Ölçüm ve Değerlendirme) veri ve araç dizini. P7'nin uygulaması:
**ölçülemeyen özellik yayına girmez.**

| Dosya | Görev | Durum |
|---|---|---|
| `pairs_tr.jsonl` | F0-13 — embedding benchmark çift seti (60 çift) | ✅ **kuruldu** — tamamı gerçek yayınlardan verbatim |
| `embedding_benchmark.py` | F0-13 — koşucu | ✅ hazır |
| `golden_set_v1.jsonl` | F0-14 → F2-20 — altın makale seti | 🟡 **55/300** — gerçek veri, hedefin altında (B-57) |
| `golden_claims_v1.jsonl` | F2-20 — altın iddia seti | 🟡 **24/150** — beklenen durumlar Spec §8.3 elle uygulanarak verildi |
| `golden_set_tools.py` | doğrulayıcı + istatistik | ✅ hazır |
| `run.py` | F2-16 — eval koşucusu | ✅ hazır ve koşuldu |
| `eval_report.md` | F2-16 çıktısı | ✅ |
| `threshold_report.md` | F2-14 — D20 eşik kalibrasyonu | ✅ **T_HIGH=0,92 / T_LOW=0,88** |

---

## Golden Set nasıl etiketlenir

**Amaç:** Aynı gerçek-dünya gelişmesini anlatan makaleler aynı `event_id`'yi
paylaşır. Kümeleme precision/recall'ı bu etikete karşı ölçülür.

1. Son 3 aydan makro ekonomi makaleleri toplayın (MVP'nin 10 konusu —
   `docs/mvp-konu-kapsami.md`).
2. Her makaleye elle bir `event_id` verin. Aynı olay = aynı id.
3. **Zor kümeleri işaretleyin** (`"difficulty": "hard"`): yakın ama farklı
   olaylar. Örnekler:
   - İki ayrı PPK toplantısı kararı (aynı kurum, aynı konu, farklı tarih)
   - Aynı ay için TÜFE *beklentisi* ile TÜFE *açıklaması*
   - Aynı verinin ilk açıklaması ile revizyonu
   - Ajans haberi ile onu kopyalayan sitenin haberi (aynı olay, tespit edilmeli)
   - Çelişkili sayı içeren iki haber (biri "faiz %40", diğeri "%42")

   F0-14 DoD: **en az 5 zor küme.**
4. `python -m eval.golden_set_tools validate` ile doğrulayın.
5. `python -m eval.golden_set_tools stats` ile ilerlemeyi izleyin.

**Kilometre taşları:** F0-14 → 100 makale · F1-20 → 200 · F2-20 → 300 + 150 iddia.

> ⚠️ Golden Set haftalık büyür ve **zorlaşır**: sistemin yanlış yaptığı her
> örnek sete eklenir (Yol Haritası §3, haftalık ritüel).

---

## Embedding çift seti nasıl hazırlanır

`pairs_tr.jsonl` — satır başına bir çift:

```json
{"id": "p001", "a": "TÜİK Mayıs enflasyon verisini açıkladı...", "b": "Enflasyon mayısta...", "same_event": true, "difficulty": "easy", "note": ""}
```

**DoD (F0-13):** 60 çift = 30 aynı olay + 30 farklı olay; en az 10'u `hard`.

`a` ve `b` alanlarına **başlık + ilk paragraf** yazın (sistemin gerçekte
embed edeceği metinle aynı biçim — aksi halde benchmark üretimi yansıtmaz).

Doğrulama:

```bash
python -m eval.embedding_benchmark --validate-only
```

Koşum (en az 3 aday, F0-13 DoD):

```bash
python -m eval.embedding_benchmark \
  --candidates voyage-3,cohere-multilingual-3,e5-large \
  --out docs/embedding-benchmark.md
```

`python -m eval.embedding_benchmark --list-candidates` mevcut adayları listeler.

---

## Neden bu setler koda dahil değil de veri?

Golden Set ürünün **moat**'ının ölçüm tarafıdır: model ve prompt her
değiştiğinde yeniden koşulur (Spec §13.1). Git'te sürümlenir, Docker imajına
girmez (`.dockerignore`).


---

## Golden Set nasıl üretildi (F2-20, kısmi)

Makale setinin olay etiketleri **elle verilmiştir** ama iki kez
etiketlenmemiştir: `pairs_tr.jsonl`'deki "aynı olay" etiketlerinin
**geçişli kapanışı** gerçek olay kimliklerini üretir. Üretim sırasında
tutarlılık denetlenir — "farklı olay" etiketli bir çift aynı kümeye
düşerse üretim durur.

İddia setinin `expected_status` alanları **Spec §8.3 elle uygulanarak**
verilmiştir. Kural motorunun çıktısından türetilmiş olsalardı ölçüm
döngüsel olurdu: motor kendi kendini doğrulardı.

Her iddiada `note` alanı, o durumun neden beklendiğini yazar. Bir
uyuşmazlıkta önce **notun** doğruluğu tartışılır, sonra kodun.

## Koşum

```bash
export PD_EMBEDDING_PROVIDER=local
export PD_EMBEDDING_MODEL=intfloat/multilingual-e5-large

python -m eval.run                              # tam rapor
python -m eval.run --sweep                      # eşik taraması (F2-14)
python -m eval.run --review-as split            # denetim kuyruğu reddedilmiş senaryosu
python -m eval.run --out eval/eval_report.md    # raporu dosyaya yaz
```
