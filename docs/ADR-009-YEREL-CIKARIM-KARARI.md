# ADR-009: Yerel Çıkarım (Ollama) — Ölçüldü, Benimsenmedi

**Durum:** Kabul Edildi (Accepted) — **Seçenek D: yetersiz kanıt, entegrasyon yok**
**Tarih:** 19 Ağustos 2026
**İlgili:** Roadmap Faz 6, `eval/benchmark_stance.py`, `eval/golden_stance_v1.jsonl`,
`eval/shadow_stance_run.py`, ADR-008 (karşı kanıt yolu)

---

## 1. Karar

**Yerel çıkarım üretime alınmadı.** Ne `claim_extraction` iş yükü uzaktan
yerele taşındı, ne de duruş sınıflandırma yeni bir kod yolu olarak açıldı.
Üretim kodunda Faz 6 kaynaklı **tek satır değişiklik yoktur**; eklenen her
şey `eval/` altında izole ölçüm aracıdır.

Bu bir başarısızlık değil, Faz 6'nın istediği çıktıdır: *"A measured
decision to NOT adopt Ollama is a successful Phase 6 outcome."*

---

## 2. Neyi ölçtük

İki ayrı iş yükü var ve karıştırılmamalı:

| İş yükü | Durum | Çıktı profili |
|---|---|---|
| `claim_extraction` | **üretimde**, 8.380 çağrı | uzun üretim, ort. 1.019 token |
| duruş sınıflandırma | **aday** (ADR-008'deki ölü R1 yolunu diriltir) | tek etiket |

Faz 6'da ölçülen **yalnızca ikincisidir.** Yerel model `claim_extraction`
üzerinde hiç denenmedi; dolayısıyla o iş yükü için yerel lehine ya da
aleyhine söylenecek ölçülmüş bir şey yok.

### 2.1 Üretim taban çizgisi (`llm_calls`, 8.411 satır)

```
model      nvidia/nemotron-3-super-120b-a12b
başarı     %93   (585 LLMHTTPError, 8 ReadTimeout, 5 TypeError)
gecikme    p50 12.592 ms · p95 43.570 ms · p99 76.056 ms
verim      3,07 çağrı/dk · 2.220 makale/24 sa
```

585 `LLMHTTPError`'ın (%7) kaynağı Faz 6'da bulundu: **ücretsiz NVIDIA NIM
katmanının hız sınırı.** Benchmark 35 kalemlik altın kümede 50 kez 429
yedi. Üretimdeki hata oranı bir model kusuru değil, bir kota kusurudur.

### 2.2 Altın küme

`eval/golden_stance_v1.jsonl` — 35 kalem, 20 kategori, elle gerekçelendirilmiş.
Zorluk: 7 kolay / 15 orta / 13 zor. Etiketler **metin ilişkisi** hakkındadır,
siyasi görüş hakkında değil (yetkinin şartı). Kategoriler olumsuzlama, Türkçe
biçimbilim, kısaltma, sayısal/zamansal çelişki, halüsinasyon yemi, koşullu
ifade, aktarılan söz, alıntı sınırı, eksik bağlam dâhil.

### 2.3 Karşılaştırma

| | Ollama qwen2.5:7b-q5_K_M | Uzak nemotron-120b |
|---|---|---|
| doğruluk | 0,686 | **0,909** |
| makro F1 | 0,645 | **0,881** |
| çelişki duyarlılığı | 0,889 | **1,00** |
| yanlış çelişki oranı | 0,0 | 0,0 |
| **yanlış destek oranı** | **0,16** | **0,0** |
| `insufficient_evidence` duyarlılığı | **0,20** | 0,67 |
| geçersiz çıktı oranı | **0,0** | 0,057 |
| soğuk başlangıç | 6.187 ms | 3.564 ms |
| **p50** | **621 ms** | 2.147 ms |
| p95 | **690 ms** | 5.224 ms |
| hız sınırı çarpması | **0** | **50** |

Sıcaklık her iki tarafta 0,0; `prompt_version=stance.v1`,
`schema_version=stance.schema.v1`. Eşzamanlılık 1/2/4/8'de doğruluk
0,686'da sabit kaldı — ölçüm tekrarlanabilir.

### 2.4 Doyum noktası (yerel)

| eşzamanlılık | p50 | p95 |
|---|---|---|
| 1 | 621 ms | 690 ms |
| 2 | 633 ms | — |
| 4 | 824 ms | 1.164 ms |
| 8 | 1.644 ms | 2.472 ms |

**Doyum 4 ile 8 arasında.** 4'te ~4,9 istek/sn.

### 2.5 Kaynak ayak izi

```
GPU        NVIDIA RTX 4060 Laptop · 8.188 MiB
model      6.248 MiB (%76) · boş kalan 1.709 MiB
host RAM   ~94 MB (ollama 69 MB + ollama app 25 MB)
```

Model **%100 GPU**'da koşuyor. Not: `venv` içindeki PyTorch CPU-only
(`torch 2.13.0+cpu`, `CUDA False`) — bu Ollama hakkında hiçbir şey
söylemez, Ollama kendi CUDA çalışma zamanını kullanır. Faz 6 boyunca bu
ikisini karıştırmamak gerekti.

7B/q5 model VRAM'in dörtte üçünü tutuyor. Daha büyük bir model ya da daha
geniş bağlam CPU'ya taşar ve **621 ms'lik tek üstünlük anında kaybolur.**
Yerel seçeneğin hız avantajı donanıma sıkı bağlıdır, taşınabilir değildir.

---

## 3. Gerçek veri gölge koşumu (WRITE = FALSE)

`python -m eval.shadow_stance_run --limit 60` — 60 iddia/kanıt çifti,
**hiçbir şey veritabanına yazılmadı.**

```
geçerli çıktı  60/60
süre           38,9 sn (1,54 çift/sn)
dağılım        supports 58 · unrelated 1 · partial 1
contradicts    0
anlaşmazlık    2/60 (%3,3)
```

İki anlaşmazlık elle incelendi:

**#7004 — model yanıldı.** İddia *"GASMEK operates under Gaziantep
Büyükşehir Belediyesi"*, kanıt *"Gaziantep Büyükşehir Belediyesi bünyesinde
faaliyet gösteren GASMEK'ten…"*. Açıkça `supports`; model `unrelated` dedi.
İddia İngilizce, kanıt Türkçe — **diller arası çift**, altın kümede
temsil edilmeyen bir kategori.

**#6969 — model muhtemelen haklı.** İddia *"Genç nüfustaki işsizlik oranı
azalmıştır"*, kanıt geniş tanımlı işsizliğin yüksek seyrettiği haberi.
Model `partial` dedi. Mevcut `supports` kaydı bir yargı değil; ADR-008'in
tespit ettiği gibi `nlp/claims_pipeline.py` bu alanı **sabit kodlu**
yazıyor. Yani "anlaşmazlık" mutlaka model hatası anlamına gelmez —
karşılaştırılan taraf bir taban gerçeği değildir.

**Koşumun asıl sınırı:** örneklem yapı gereği taraflıydı. Bir iddia ile
*onu kaynaklayan* makale eşleştirildiği için çift neredeyse tanımı gereği
destekleyicidir; 60 çiftte 0 çelişki çıkması bunun sonucudur. R1'in
ihtiyaç duyduğu şey ise **çapraz makale** çiftleridir: A makalesinden çıkan
iddia ile aynı olayı işleyen B makalesi. Bu ölçülmedi.

---

## 4. Neden benimsenmedi

**a) Yerel modelin kalitesi otonom yazma için yetersiz.**
Yanlış destek oranı 0,16. Bu ürünün çekirdek güvencesi kanıt bağıdır;
%16 oranında **var olmayan bir kanıt bağı üretmek** en pahalı hata türüdür.
`insufficient_evidence` duyarlılığı 0,20 aynı kusurun ikinci yüzü: model
"kanıt yok" durumunu bir bağa çeviriyor. ADR-008'de ölü bırakılan kuralı
güvenilmez bir kuralla doldurmak, ölü bırakmaktan kötüdür.

**b) Ama yerel model çelişki taramasında iyi.**
Çelişki duyarlılığı 0,889 ve yanlış çelişki oranı **0,0**. Yani asla
olmayan bir çatışma uydurmuyor ve gerçek çelişkilerin %89'unu yakalıyor.
Kusuru destek/yetersiz sınırında — R1'in ihtiyacı olan yerde değil. Bu,
"yerel eler, uzak hüküm verir" biçiminde bir hibritin **hipotezini**
kurar.

**c) Hibrit hipotezi ölçülmedi, dolayısıyla önerilmiyor.**
Belirleyici deney (çapraz makale çiftleri) yapılmadı; gölge koşumda
çelişki yolu hiç tetiklenmedi. 35 kalemlik altın küme bir mimari kararı
taşıyacak ağırlıkta değil. Ölçülmemiş bir tasarımı "önerilen" diye
yazmak, Faz 6'nın yasakladığı şeyin ta kendisidir.

**d) Uzak taraf için de değişiklik önerilmiyor.**
Uzak model kalitede açık ara önde (0,909 / makro F1 0,881 / çelişki
duyarlılığı 1,00) ama hız sınırlı ve p95'i 43,5 sn. Yine de yerel model
`claim_extraction` üzerinde hiç denenmediği için, üretimdeki iş yükünü
taşımaya dair ölçülmüş bir gerekçe yok. **Ölçülmeyen şey hakkında karar
verilmez.**

---

## 5. Bu kararı değiştirecek ölçüm

Sırasıyla:

1. **Çapraz makale altın kümesi** — aynı olayı işleyen farklı kaynaklardan
   çift; en az 150 kalem, çelişki sınıfı yeterince temsil edilmiş.
2. Diller arası çiftler (#7004'ün ortaya çıkardığı boşluk).
3. Altın kümenin **ikinci bir insan tarafından** bağımsız etiketlenmesi ve
   uyum (kappa) ölçümü. Mevcut küme tek elden çıktı; bu bir sınırdır.
4. Yerel modelin `claim_extraction` üzerinde ölçülmesi — farklı çıktı
   profili, farklı sonuç verebilir.
5. 8 GB'tan büyük VRAM'de tekrar; mevcut sayı donanıma sıkı bağlı.

Bunlar yapılmadan yerel çıkarım üretime alınmamalıdır.

---

## 6. Korunan kısıtlar

| Kısıt | Durum |
|---|---|
| Domen katmanı satıcıya özel SDK'ya bağlanmaz | ✅ `import ollama` yok; `llm/client.py` jenerik OpenAI-uyumlu, sağlayıcıyı `PD_LLM_BASE_URL` seçer |
| Benchmark üretim kodundan izole | ✅ hepsi `eval/` altında |
| İkinci metin üretim yolu açılmadı | ✅ benchmark yalnızca sınıflandırır, taslak üretmez; `grounding_check` baypas edilmedi |
| İlk gerçek veri koşumu WRITE=FALSE | ✅ gölge koşumda yazma SQL'i yok (AST ile test ediliyor) |
| Yeni duruş taksonomisi icat edilmedi | ✅ DB sözlüğü (`supports`/`contradicts`/`partial`) ölçüldü ve korundu; iki ek etiket **kayıt açmaz** |
| Model siyasi hüküm/nedensellik üretmez | ✅ istem yasaklıyor, testler doğruluyor |
| Model üretimi etiket taban gerçeği sayılmadı | ✅ altın küme elle gerekçelendirildi |
| O-01 uygulama kodunda baypas edilmedi | ✅ açık kaldı |

43 test: `tests/test_stance_benchmark.py`. Hiçbiri ağa çıkmaz.

---

## 7. Sonradan gelen not — yapılandırma bu karara uymuyordu (19 Ağustos 2026)

Karar "yerel çıkarım benimsenmedi" diyordu, ama üretim yapılandırması onu
uygulamıyordu. 19 Ağustos öğleninde `.env` `hybrid` sağlayıcısına
geçirilmiş ve **çıkarım** yerel bir uca yönlendirilmişti:

```
PD_LLM_EXTRACTION_BASE_URL=http://127.0.0.1:11434/v1
PD_LLM_MODEL_EXTRACTION=qwen2.5:7b-instruct-q5_K_M
```

O uç hiçbir zaman çalışamazdı. İki sebep birden vardı:

1. Ortamda hiç Ollama konteyneri yok.
2. Olsaydı bile `127.0.0.1` **konteynerin kendisidir**, host değil.
   Worker kendi içindeki 11434 portuna bağlanmaya çalışıyordu.

### Ölçülen bedel

| | değer |
|---|---|
| Yerel uca giden çağrı | 72 |
| Başarılı | **0** |
| Ortalama gecikme | 174.691 ms (zaman aşımı 180 sn) |
| En yavaş | 335.335 ms |

Her çıkarım önce burada asılıyor, sonra yedeğe — **üretim** modeline
(`llama-3.3-70b`, 53,9 sn) düşüyordu. Yani çıkarım hem gecikme cezası
ödüyor hem de kendisi için seçilmemiş, dört kat yavaş bir modelle
yapılıyordu. Çıkarım/üretim ayrımının (Risk R6) amacı tam tersiydi.

### Düzeltme ve etkisi

Çıkarım, üretimle **aynı uzak uca** alındı; ayrı ve daha hızlı model
korundu. Ölçüm, düzeltmeden 15 dakika sonra:

| | önce | sonra |
|---|---:|---:|
| Çıkarım hızı | 1,7 çağrı/dk | **11,1 çağrı/dk** |
| Ortalama gecikme | 52.743 ms | **8.859 ms** |
| Başarı oranı | %90,5 | **%100** (166/166) |
| Ölü uca giden tur | her çağrıda | **yok** |

**6,5× hızlanma, tek bir yapılandırma satırı.**

### Bu kararın kalıcı dersi

Bir ADR "hayır" dediğinde, o hayrın **yapılandırmada karşılığı olup
olmadığı ayrıca denetlenmelidir.** Karar belgesi ile çalışan sistem
arasında sessiz bir sapma oluşabilir ve buradaki gibi aylarca fark
edilmeyebilir — hata vermiyordu, yalnızca yavaştı.

⚠️ `.env` git'te değildir; bu sapmayı hiçbir test yakalayamazdı.
Kalıcı koruma için çalışma zamanı sağlık kontrolü gerekir
(`scripts/check_deployment.py`'a "çıkarım ucu erişilebilir mi" adımı).
Bu, bu ADR'nin açık bıraktığı iştir.

### Çıkarım modeli seçimi ölçüldü

Düzeltme "uzak uca al" diyordu; hangi model sorusu ayrıca ölçüldü
(`python -m scripts.llm_benchmark`, `eval/golden_set_v1.jsonl`, 4 makale):

| Model | Çağrı | Alıntı sadakati | Makale başına iddia | Gecikme |
|---|---:|---:|---:|---:|
| `nvidia/nemotron-3-super-120b-a12b` | **4/4** | **%90** | 2,2 | 15.104 ms |
| `meta/llama-3.3-70b-instruct` | 2/4 | %50 | 0,5 | 23.180 ms |

Çıkarımda nemotron her eksende önde: güvenilirlik, alıntı sadakati, verim
ve gecikme. Seçim korundu.

**Bu, üretim kararıyla çelişmiyor.** F5-15'te nemotron *üretim* için
elenmişti çünkü taslakta kanıtta olmayan bir TARİH üretmişti ve G3 koşul 2
orada **sert bir kapıdır**. Çıkarım farklı bir görevdir ve kendi sert
kapısı vardır: uydurulmuş alıntı `nlp/claims.py` tarafından reddedilir
(ölçümde nemotron'un 10 iddiasından 1'i bu kapıya takıldı). İki görev,
iki model — çıkarım/üretim ayrımının amacı zaten buydu.

⚠️ **Örneklem küçüktür (4 makale, 12 iddia).** `llama-3.3-70b`'nin 2
başarısız çağrısı, kıyaslamada kullandığım 60 sn'lik zaman aşımına
takılmıştır; üretimdeki 180 sn ile başarabilirdi. Bulgu bu yüzden
*yönlendirici*dir, kesin değil. Model değiştirilecekse ölçüm daha geniş
bir örneklemle tekrarlanmalıdır — bu, Faz 12'nin (LLM regresyon kapısı)
kapsamına girer.
