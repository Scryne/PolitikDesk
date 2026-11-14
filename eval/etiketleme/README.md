# Golden Set v2 etiketleme (F2-20: 300 makale)

Bugünkü altın set: 55 insan etiketli makale (`label_source: human_v1`) + 35 W1
makalesi (`w1_unverified`, insan onayı kaydı yok). Hedef: 300 insan etiketli
makale. Eksik: **245**.

**Etiket insan işidir.** Model, ajan ya da sistemin kendi kümelemesi etiket
üretmez: ölçüm döngüsel olur ve W1'de olduğu gibi set sessizce bozulur
(`eval/threshold_report.md`, 2026-11-14).

## Kim ne yapar

| Adım | Kim | Süre (tahmini) | Ne |
|---|---|---|---|
| 1. Örneklem | Scryne | ~5 dk | Üretim veritabanına (yalnız SELECT) `orneklem.py` koşar, `aday.csv` çıkar |
| 2. Etiket A | Etiketleyici A (Scryne) | ~2–2,5 sa | `aday.csv`'nin kopyasında `event_id`, `difficulty`, `etiketleyen` doldurur |
| 3. Etiket B | Etiketleyici B (ikinci kişi) | ~2–2,5 sa | Aynı dosyanın **ayrı** kopyasında, A'nın etiketini görmeden aynı işi yapar |
| 4. Birleştirme | Scryne | ~5 dk | `birlestir.py` koşar; uyum oranına ve anlaşmazlık listesine bakar |
| 5. Hakem | A ve B birlikte (ya da üçüncü kişi) | ~20–40 dk | `anlasmazlik.csv`'de `hakem_event_id`'yi doldurur, birleştirme yeniden koşulur |
| 6. Ekleme | Scryne | ~10 dk | `golden_set_v2_aday.jsonl`'i gözden geçirip `golden_set_v1.jsonl`'e ekler, `validate` ve `eval.run` koşar |

İkinci kişi yoksa B'yi aynı kişi **en az bir hafta sonra**, A'nın dosyasına
bakmadan yapar. Bu zayıf bir ikinci etikettir; `labelers` alanında iki ad aynı
olur ve raporda böyle belirtilir.

## Komutlar (proje kökünde)

```bash
# 1. Örneklem (gerçek .env üretim veritabanını gösterir; betik yazmaz)
python -m eval.etiketleme.orneklem --baslangic 2026-09-01 --bitis 2026-11-30 \
    --hedef 245 --cikti eval/etiketleme/aday.csv

# 2–3. aday.csv → aday-A.csv, aday-B.csv (kopyala, ayrı ayrı doldur)

# 4. Birleştir
python -m eval.etiketleme.birlestir eval/etiketleme/aday-A.csv eval/etiketleme/aday-B.csv \
    --cikti eval/golden_set_v2_aday.jsonl --anlasmazlik eval/etiketleme/anlasmazlik.csv

# 5. Hakemden sonra
python -m eval.etiketleme.birlestir eval/etiketleme/aday-A.csv eval/etiketleme/aday-B.csv \
    --hakem eval/etiketleme/anlasmazlik.csv \
    --cikti eval/golden_set_v2_aday.jsonl --anlasmazlik eval/etiketleme/anlasmazlik-kalan.csv

# 6. Ekledikten sonra
python -m eval.golden_set_tools validate
python -m eval.run --live-entities --label-source human_v1   # eski insan seti
python -m eval.run --live-entities --label-source human_v2   # yeni insan seti
```

## Etiket kuralları

- `event_id`: aynı gerçek dünya gelişmesini anlatan makalelere aynı serbest ad
  (`tufe-ekim`, `ppk-kasim`). Ad önemli değil, **gruplama** önemli; iki
  etiketleyicinin adları farklı olabilir.
- Aynı olay: aynı açıklama/karar/veri yayımı ve onun haberleri, yorumları.
  Farklı olay: aynı kurumun aynı gün yaptığı iki ayrı yayım (TÜİK sanayi
  üretimi ≠ TÜİK Tarım-GFE), aynı ayın beklentisi ≠ açıklaması, ilk açıklama ≠
  revizyon, iki ayrı Sayıştay raporu.
- `difficulty`: yanındaki makalelerle kolayca karışabilecekse `hard`, değilse
  `easy`. Her iki etiketleyiciden biri `hard` derse `hard` kalır.
- `topic`: örneklem, kaynağın konusundan tahmin eder; yanlışsa düzeltin
  (`docs/mvp-konu-kapsami.md`'deki 10 konudan biri).
- Emin değilseniz `not` sütununa yazın; boş `event_id` o makaleyi dışarıda
  bırakır, uydurma etiket ölçümü bozar.

## Örneklem neyi garanti eder

Konu başına eşit kota; her tohum makalenin yanına 72 saat içindeki en yakın
komşuları (benzerlik ≥ 0,80) eklenir. Böylece çok makaleli olay ve "yakın ama
farklı" zor küme sayısı artar (v1'de olayların yarısı tek makaleliydi).
Satırlar konu ve zamana göre sıralanır; sistemin benzerlik kararı etiketleyene
gösterilmez.
