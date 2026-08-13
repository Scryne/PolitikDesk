# D17 — İddia çıkarımı için LLM model seçimi

**Karar:** `nvidia/nemotron-3-super-120b-a12b` (NVIDIA NIM ücretsiz katmanı)
**Tarih:** 13 Ağustos 2026
**Araç:** `python -m scripts.llm_benchmark`
**Bağlam:** B-58 (F2-07 canlı koşum, G2 koşul 5) · `docs/llm-saglayici.md`

## Yöntem

D16'da embedding kararı benchmark'la verilmişti; bu onun LLM tarafıdır.

Girdi: `eval/golden_set_v1.jsonl` — gerçek Türkçe makro-ekonomi haberleri
(sentetik metin değil). Örnek deterministik ve zorluk dengeli seçilir;
rastgele örnek koşumlar arası karşılaştırmayı imkânsız kılardı.

**Yer gerçeği (ground truth) olmadan neden ölçülebilir:** iddia
çıkarımının DoD'si programatik olarak denetlenebilir dört şey istiyor —
şema geçerliliği (F2-06), tip doğruluğu (F2-07), sayısal normalizasyon
(F2-08) ve **alıntının kaynak metinde birebir geçmesi** (F2-10).
Sonuncusu en ayırt edicidir: uydurulmuş alıntı nesnel olarak yanlıştır ve
"doğru iddia hangisiydi" bilgisine ihtiyaç duymadan yakalanır.

Aday havuzu, katalog kartlarından değil **`/v1/models` uç noktasından**
çıkarıldı: anahtara açık 102 model listelendi, metin üretmeyenler
(gömme, güvenlik sınıflandırıcısı, görüntü, kod) elendi.

## Bulgular

### Kademe 1 — eleme (8 aday × 2 makale, 60 sn, tek deneme)

Üç aday görevin kendisine varmadan düştü:

| Model | Düşme sebebi |
|---|---|
| `moonshotai/kimi-k2.6` | HTTP 404 `Not found for account` — **katalogda listeli, anahtara açık değil** |
| `nvidia/nemotron-3-ultra-550b-a55b` | Geçerli JSON ama nesne değil (dizi döndürdü) — şema sözleşmesini tutmuyor |
| `deepseek-ai/deepseek-v4-flash-0731` | 60 sn'de ReadTimeout (zaman aşımı düşük seçilmişti; Kademe 2'de geçti) |

### Kademe 2 — derinlemesine (5 aday × 8 makale, 150 sn, 3 deneme)

| Model | Çağrı | Kabul or. | Alıntı sadakati | Makale başına | Gecikme |
|---|---:|---:|---:|---:|---:|
| **`nvidia/nemotron-3-super-120b-a12b`** | **8/8** | 83% | **100%** | 1,25 | 34 sn |
| `deepseek-ai/deepseek-v4-flash-0731` | 8/8 | 82% | **100%** | 1,12 | 26 sn |
| `openai/gpt-oss-120b` | 5/8 | 92% | **100%** | 2,40 | 14 sn |
| `minimaxai/minimax-m3` | 2/8 | 75% | **100%** | 1,50 | 11 sn |
| `z-ai/glm-5.2` | 2/8 | 67% | **100%** | 1,00 | 10 sn |

### Kademe 3 — Türkçe kalite (3 aday × 4 makale, gözle inceleme)

`nemotron-3-super` ve `deepseek-v4-flash` neredeyse özdeş, doğru ve
gerçekten **atomik** Türkçe iddialar üretti:

```
[number] GSYH 2026 yılı birinci çeyrek ilk tahmini, zincirlenmiş hacim endeksi…
[fact]   Türkiye ekonomisi art arda 23 çeyrektir büyüdü.
[number] Türkiye ekonomisi bu yılın birinci çeyreğinde … yüzde … arttı.
```

`gpt-oss-120b` bu turda 150 sn'de bile **0/4** — elendi.

## Gerekçe

**Ayırt edici ölçüt kalite değil, güvenilirlik oldu.** Hayatta kalan beş
adayın *hepsi* %100 alıntı sadakati tutturdu — yani Türkçe kalite
korkusu (bkz. `docs/llm-saglayici.md`) bu görev için doğrulanmadı;
`verify_quote()` savunması zaten kurulu olduğu için risk de sınırlıydı.

Ayrım çağrıların geçip geçmediğinde çıktı. `nemotron-3-super`, üç
koşumun **üçünde de** hatasız: toplam 14/14 çağrı. Ücretsiz katmanda
paylaşımlı kapasite gerçek bir kısıt ve günlük bir boru hattı için
"cevabı iyi ama üçte biri düşüyor" kabul edilebilir değil.

`gpt-oss-120b` en yüksek verimi (makale başına 2,4 iddia) ve en düşük
gecikmeyi verdi ama iki koşumda toplam 5/12 çağrı tamamlandı — verim
ancak çağrı dönerse anlamlıdır.

**İkinci sıradaki `deepseek-v4-flash` neredeyse eşdeğer ve %25 daha
hızlı.** Kapasite sorunu yaşanırsa geçiş tek satırdır:
`PD_LLM_MODEL_EXTRACTION=deepseek-ai/deepseek-v4-flash-0731`

## Kapsam sınırı — bu karar neyi KAPSAMAZ

Ölçüm **yalnızca çıkarım** görevindedir. `PD_LLM_MODEL_GENERATION` şimdilik
aynı modele ayarlandı ama bu bir karar değil, yer tutucudur: taslak
yazımı farklı bir görevdir (uzun metin, üslup, tutarlılık) ve Faz 3'te
kendi ölçümüyle seçilmelidir.

Ayrıca ölçülmedi: uzun vadeli kota davranışı (B-68) ve aynı Golden Set'te
Claude ile doğrudan karşılaştırma (B-67) — ikincisi anahtar geldiğinde
`--provider anthropic` ile tek komut.

## Yeniden üretme

```bash
python -m scripts.llm_benchmark --articles 8 --timeout 150 --retries 3
python -m scripts.llm_benchmark --provider anthropic --models claude-sonnet-5
```
