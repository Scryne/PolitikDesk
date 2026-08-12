# Faz 2 — Durum Panosu

**Faz:** Olay Zekâsı · **Plan:** W8–W12 · 25 PD
**Son güncelleme:** 12 Ağustos 2026

> **Fazın felsefesi:** Bu fazda hiçbir şey "iyi çalışıyor gibi" duruyor diye
> kabul edilmez. Her bileşen Golden Set'e karşı sayısal olarak ölçülür.

---

## Faza giriş durumu

Faz 2, Spec **v3.1** dondurulduktan sonra başlatıldı. Faz 0'ın açık iki
kalemi kapatıldı, üçüncüsü kısmi:

| Ön koşul | Durum |
|---|---|
| Spec-freeze (`spec-v3.1`) | ✅ 4 itiraz Spec'e işlendi |
| R0/R7 kural sıralaması | ✅ §8.3 düzeltildi + `migrations/0003` |
| Salience global/kişisel ayrımı | ✅ §8.4 + DB kısıtı `events_salience_global_range` |
| Çift seti (F0-13) | ✅ 60 gerçek çift kuruldu |
| **D16 embedding kararı** | ✅ **`multilingual-e5-large`** — 3 aday koşuldu; bkz. `docs/embedding-benchmark.md` |
| Golden Set | 🔴 0/200 — F2-16 ve F2-20 buna bağlı |

**D16 kapandı.** Üç aday ölçüldü (e5-large 0,822 / voyage-3 0,804 /
bge-m3 0,790). Eleme ölçütü "zor AUC — **metinsel özdeş çiftler hariç** —
≥ 0,80" olarak yeniden yazıldı ve yalnızca e5-large geçti (0,807). Ölçüt
değişikliğinin yazılı gerekçesi `docs/embedding-benchmark.md`'dedir.

**Uygulama borcu:** mevcut makaleler hâlâ `hashing` embedder ile
gömülüdür; e5'e geçildiğinde `articles.embedding` yeniden üretilmeli ve
kümeleme tekrar koşulmalıdır (B-53). Worker konteyneri de `embed-local`
ekstrasını (torch + sentence-transformers, ~2,5 GB) gerektirir (B-54).

---

## Görev durumu

### İş Kolu A — Olay Kümeleme

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F2-01 | Kümeleme algoritması v1 | ✅ | `clustering/assigner.py` + `repository.py` + `pipeline.py` |
| F2-02 | Olay merkezi güncelleme | ✅ | `clustering/centroid.py` — drift < 1e-9, geri alınabilir |
| F2-03 | Sayısal çelişki bayrağı | ✅ | `clustering/numeric_guard.py` — 11 metrik sözlüğü |
| F2-04 | İnsan denetim kuyruğu | 🔜 | `/admin/review` |
| F2-05 | Merge / Split kaçış valfleri | 🔜 | `clustering/merger.py` |
| F2-14 | Eşik kalibrasyonu (D20) | ⏳ | F2-16 + Golden Set'e bağlı |

Diğer iş kolları (B: iddia çıkarımı, C: kanıt motoru, D: bağlam, E: eval)
henüz başlamadı.

---

## Tasarım kararları ve gerekçeleri

| Karar | Alternatif | Gerekçe |
|---|---|---|
| Karar mantığı **saf** (`decide()` DB'ye dokunmaz) | Repository içinde karar vermek | F2-14 (eşik kalibrasyonu) ve F2-16 (eval) her eşik denemesi için veritabanı kurmak zorunda kalmamalı. 28 kümeleme testinin hiçbiri DB gerektirmiyor. |
| Merkez **normalize edilmemiş** ortalama | Her adımda L2 normalize etmek | `centroid = mean(members)` özdeşliği korunmalı; aksi halde `remove_member` bozulur ve merge/split geri alınamaz (G2 koşul 8, İtiraz-5 mühendislik notu). Kosinüs ölçekten bağımsız olduğu için normalizasyon gereksiz. |
| Sayısal çelişki **atamayı engellemez**, işaretler | Ayrı olay saymak | Çelişki "bu iki metin farklı olay" demek değildir; "biri yanlış olabilir" demektir. Hüküm insanındır (Spec §11.4 kaçış valfleri). |
| Metriğe bağlanamayan sayı **atılır** | Tüm sayıları karşılaştırmak | "23 çeyrektir büyüdü" ile "yüzde 23 büyüdü" karışırsa bayrak gürültüye boğulur ve denetim kuyruğu okunamaz hale gelir. |
| Makaleler **yayın zamanına göre sırayla** işlenir | Rastgele/id sırası | Kümeleme artımlıdır; sıra sonucu etkiler. Tekrar üretilemeyen sonuç F2-16'da ölçülemez. |
| Aday elemesi `trace` ile kaydedilir | Sessiz eleme | P4: "neden bu olaya atanmadı?" admin panelinde cevaplanabilir olmalı. |
| Olay başlığı tohum makaleden | Boş bırakıp LLM beklemek | LLM başlığı F2-06 sonrası gelir; o zamana kadar denetim kuyruğu okunamaz olurdu. |

---

## Canlı doğrulama (12 Ağustos 2026)

11 gerçek makale üzerinde uçtan uca koşum:

```
{'processed': 11, 'assigned': 1, 'created': 10,
 'needs_review': 0, 'numeric_conflicts': 0, 'errors': 0}
```

Tek birleştirme doğru: aynı TCMB sunum duyurusunun iki kaydı
(benzerlik 0,933).

### Canlı veride bulunan hata

| # | Hata | Belirti | Düzeltme |
|---|---|---|---|
| 1 | **`SET LOCAL hnsw.ef_search = %s` çalışmıyor** | 11 makalenin 11'i de `syntax error at or near "$1"` ile düştü | Postgres'te `SET` bind parametresi kabul etmez. `set_config('hnsw.ef_search', %s, true)` ile değiştirildi. |
| 2 | **Varlıksız makaleler hiç kümelenemiyor** | 0,9997 benzerlikli iki makale (aynı olay) ayrı olaylara düştü | Spec §11.4 boş varlık kümesini tanımlamıyor; `jaccard(∅, ∅) = 0` olduğu için kısıt reddediyordu. Kısıt üç durumlu yapıldı: `ok` / `inconclusive` / `reject`. |

> **Bu bir Faz 1 hatasıydı.** `nlp/search.py::_set_ef_search` F1-14'te
> yazılmış ve "✅ doğrulandı" işaretlenmişti; ama kod yolu canlı
> veritabanına karşı hiç koşmamıştı — `nearest_events()` ilk kez Faz 2'de
> çağrıldı. Regresyon testi eklendi
> (`tests/test_nlp.py::test_ef_search_is_set_via_set_config_not_set_local`).

### 2 numaralı hata: varlık kısıtı sessizce recall'ı öldürüyordu

Aynı koşumda iki makale ayrı olaylara düştü:

```
event 12  Ulaştırma alanındaki yatırım projelerine 6 ayda 41,5 milyar lira harcandı
event 13  Ulaştırma alanındaki yatırım projelerine 6 ayda 41,5 milyar harcandı
```

İlk teşhis "embedder zayıf" idi. **Yanlış çıktı.** Ölçüm:

| | benzerlik |
|---|---|
| `hashing` (kullanımdaki) | 0,9848 |
| `e5-large` (D16 kararı) | 0,9997 |

İkisi de `T_HIGH = 0,86`'nın çok üstünde. Onları ayıran benzerlik değil,
**varlık kısıtıydı**: iki makalede de tanınan varlık yok, `jaccard(∅, ∅) = 0`
ve ortak anahtar varlık da yok → `entity_reject`.

Canlı veride **11 makalenin 6'sında hiç varlık yok** (%55). Kısıt bu hâliyle
bu makalelerin her birini sonsuza dek tek başına bir olay yapardı — G2'nin
recall koşulu (≥ %80) hiçbir zaman tutmazdı.

**Düzeltme.** Boş küme *çelişki kanıtı değil, kanıt yokluğudur.* Kısıt üç
durumlu yapıldı:

| Durum | Koşul | Sonuç |
|---|---|---|
| `ok` | jaccard ≥ 0,25 **veya** ortak anahtar varlık | Normal yol — T_HIGH'da otomatik atama |
| `inconclusive` | en az bir taraf varlıksız | Yalnızca T_HIGH üstünde, **her zaman `needs_review`** |
| `reject` | iki taraf da dolu, örtüşme yok | Reddedilir (değişmedi) |

Precision önceliği korunuyor: doğrulanamayan kısıt otomatik atama hakkı
vermiyor, insan onayına gidiyor.

> **Bu bir Spec §11.4 boşluğudur** (kısıt boş küme durumunu tanımlamıyor).
> Uygulama kararı koda ve teste yazıldı; §11.4'e işlenmesi B-55'te,
> bir sonraki spec sürümüne bırakıldı — Spec v3.1 az önce donduruldu ve
> kapsam disiplini "aynı gün ikinci kez açma" demiyor.

---

## Kapı G2 hazırlığı

| # | Koşul | Hedef | Durum |
|---|---|---|---|
| 1 | Kümeleme precision | ≥ %90 | ⏳ Golden Set yok |
| 2 | Kümeleme recall | ≥ %80 | ⏳ |
| 3 | **Yanlış birleştirme** | ≤ %5 | ⏳ **pazarlıksız** |
| 4 | `evidence_status` doğruluğu | ≥ %95 | ⏳ F2-12 yazılmadı |
| 5 | Uydurulmuş iddia oranı | ≤ %2 | ⏳ |
| 6 | Sayısal normalizasyon | ≥ %95 | ⏳ |
| 7 | `evidence/` içinde LLM çağrısı | 0 | ✅ CI'da aktif |
| 8 | Merge/split geri alınabilir | %100 | 🟡 Merkez tarafı hazır (`remove_member`), UI yok |
| 9 | Haftalık ritüel | ≥3 hafta | ⏳ |

### G2 tutmama planına düzeltme

Yol Haritası'nın G2 yedek planında 3. madde "hibrit skorlama (embedding +
BM25 + varlık örtüşmesi)" diyor. **D16 tanı koşumu bunun bu proje için
yanlış ilaç olduğunu gösterdi:** en yüksek yanlış-birleştirme riski taşıyan
çiftlerin tamamı TCMB'nin şablonlu duyurularıdır ve bu çiftlerde metin de
varlıklar da aynıdır — BM25 ve varlık örtüşmesi 1,0 verir, durumu
kötüleştirir. Doğru ilaç zaten Spec §11.4'te yazılı olan **zaman
penceresidir**. Ayrıntı: `docs/embedding-benchmark.md`.

---

## Kalan iş

| İş | Efor | Not |
|---|---|---|
| Makaleleri e5 ile yeniden embed et + kümelemeyi tekrar koş (B-53) | 0,3 PD | `hashing` ile gömülü veri geçersiz |
| Worker imajına `embed-local` ekstrası (B-54) | 0,5 PD | torch + model ~2,5 GB |
| Varlık sözlüğü kapsamını genişlet | 0,5 PD | %55 varlıksız oran `inconclusive` yolunu aşırı yükler |
| F2-04 denetim kuyruğu | 1,5 PD | `/admin/review` |
| F2-05 merge/split | 2,0 PD | `remove_member` hazır; UI ve `audit_log` akışı kaldı |
| Golden Set 200 makale | 2 PD | F2-16 ve F2-14'ün ön koşulu |
