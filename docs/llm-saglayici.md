# LLM sağlayıcı kararı — Claude mı, ücretsiz açık model mi?

**Durum:** Çıkarım için karar verildi ve koşuldu.
`openai_compat` + `nvidia/nemotron-3-super-120b-a12b` — model seçiminin
ölçümü ve gerekçesi: **`docs/llm-model-benchmark.md` (D17)**.
Claude ile doğrudan karşılaştırma hâlâ açık (B-67); üretim modeli ayrı
ölçümle seçilecek (B-71).

Aşağıdaki "karara girecek gerçekler" bölümü, karar öncesi yazılan
değerlendirmedir ve **kısmen yanlış çıkmıştır** — bkz. sondaki not.

## Soru

`ANTHROPIC_API_KEY` yokluğu Faz 2'nin son adımını (F2-07 canlı koşum, G2
koşul 5 — B-58) tıkıyordu. NVIDIA'nın [build.nvidia.com](https://build.nvidia.com/models)
üzerinden sunduğu ücretsiz katman bu tıkanmayı maliyetsiz açar mı?

## Ne değişti

`politikdesk/llm/client.py`'ye ikinci bir arka uç eklendi:
`_OpenAICompatBackend`. Mimari zaten buna hazırdı — `Backend` bir
`Protocol`'dü ve F0-17 "sağlayıcı değişirse yalnızca arka uç değişir"
diyordu. Bu, o iddianın ilk sınanmasıdır ve iddia doğru çıktı:
`llm/client.py` dışında hiçbir modül değişmedi. `claims.py`, bütçe
sayacı, defter, şema doğrulaması aynen çalışıyor.

Sağlayıcı değişimi tek satır:

```bash
PD_LLM_PROVIDER=openai_compat
PD_LLM_BASE_URL=https://integrate.api.nvidia.com/v1
PD_LLM_API_KEY_ENV=NVIDIA_API_KEY
PD_LLM_MODEL_EXTRACTION=meta/llama-3.3-70b-instruct
NVIDIA_API_KEY=nvapi-...
```

Uç nokta OpenAI uyumlu olduğu için aynı yol Groq, Together, yerel
vLLM/Ollama için de geçerlidir; NVIDIA yalnızca ilk hedef.

### Arka ucun soğurduğu üç sağlayıcı farkı

1. **Yapılandırılmış çıktının üç lehçesi.** Anthropic'te
   `output_config.format` tek yoldur. OpenAI uyumlu sunucularda hangisinin
   desteklendiği modele göre değişir: `response_format.json_schema`
   (en güçlü garanti), NVIDIA'ya özgü `nvext.guided_json`, ya da kaba
   `response_format: json_object`. Sunucu birini 400 ile reddederse arka uç
   bir alt basamağa **düşer** ve bunu `llm_json_mode_downgraded` uyarısıyla
   loglar. Sessiz davranış değişikliği değil: `json_object` basamağında şema
   sunucu tarafından zorlanamadığı için prompta yazılır ve garanti
   zayıflar — bu logdan görülür.
2. **`effort` yok.** Sıcaklığa çevrilir. Bunun ilginç bir yan etkisi var:
   Spec §11.5'in **özgün** kuralı ("çıkarım 0–0,2, üretim 0,6–0,8") bu
   arka uçta geri geliyor. Faz 0'daki sapma (İtiraz-3, `temperature`'ı 400
   ile reddeden model sınıfı) sağlayıcıya özgüymüş, Spec'e değil.
3. **Akıl yürütme sızıntısı.** Açık modeller (Qwen, DeepSeek, Nemotron)
   JSON'un önüne `<think>…</think>` bloğu veya ```` ```json ```` kod bloğu
   koyar. `json.loads` bunlarda patlar. Kabuk arka uçta soyulur ki
   `LLMClient` sağlayıcı-agnostik kalsın.

Muhasebe bozulmadı: ücretsiz modeller fiyat tablosunda **açıkça** 0 olarak
kayıtlı (`FREE_TIER`). Buradaki 0 "bilinmiyor" değil "ücretsiz" demektir —
"bilinmeyen model sessizce 0 maliyet üretmez" invaryantı korunur. Token
sayımı devam eder; kota takibi ve sağlayıcı karşılaştırması maliyete değil
token'a bakar.

## Karara girecek gerçekler

### Ücretsiz katmanın lehine

- **Maliyet 0.** Günlük 5 $ / aylık 100 $ tavanı tamamen serbest kalır.
- **B-58 bugün koşulabilir.** G2'nin kod tarafındaki son tıkanması kalkar.
- **Yüksek hacimli, düşük riskli işler için yeterli olabilir.** Olay
  başlığı üretimi (B-51) gibi işler pahalı model gerektirmiyor.
- **Geri dönüş bedava.** Adaptör deseni sayesinde beğenilmezse tek satır
  geri alınır.

### Aleyhine — ve bunlar hafife alınmamalı

- **Türkçe kalite riski.** Bu projenin işi Türkçe siyasi/makro haber
  metninden **atomik iddia** çıkarmak; nüans yoğun bir görev. Açık
  modellerin Türkçesi İngilizcesinden belirgin şekilde zayıftır.
  Ölçmeden varsayım yapılmamalı — ama iyimser varsayım da yapılmamalı.
- **Uydurulmuş alıntı riski.** F2-10 alıntının kaynak metinde **birebir**
  geçmesini şart koşuyor ve `verify_quote()` bunu programatik olarak
  denetliyor. Zayıf model bu denetimden daha çok iddia kaybeder; kabul
  oranı düşerse F2-07'nin %90 DoD'si tutmaz. **İyi haber:** savunma
  hattı zaten kurulu, yani kalite düşüşü sessizce sızmaz, reddedilen
  iddia olarak sayılır.
- **Kota ve hız sınırı.** Ücretsiz katman kredi tabanlıdır; günlük tur
  için yetip yetmediği ölçülmedi (B-68).
- **Veri politikası.** Ücretsiz uç noktaya giden veri sağlayıcı tarafından
  kullanılabilir. Bu proje için girdi zaten **kamuya açık haber metni**,
  yani risk düşük. Kullanıcı verisi (Faz 4) aynı uca gönderilmemeli.

## Tavsiye

**Hibrit, ve önce ölç.**

1. **Şimdi:** `openai_compat` ile B-58'i koş. Faz 2'nin son adımı
   maliyetsiz kapanır.
2. **Hemen ardından (B-67):** aynı Golden Set'i iki sağlayıcıyla koş,
   şu dördünü karşılaştır: kabul oranı, uydurulmuş alıntı sayısı,
   `claim_type` doğruluğu, `normalized_value` doğruluğu. Ölçüm altyapısı
   (`eval/`) zaten var; bu bir koşum meselesi.
3. **Sonra karar:** açık model ölçümde tutuyorsa **çıkarımda** kalsın
   (yüksek hacim, ucuz taraf). **Üretim** (taslak yazımı, Faz 3) kalite
   kapısına bağlı olduğu için ölçüm aksini göstermedikçe Claude'da kalsın.
   Zaten `PD_LLM_MODEL_EXTRACTION` ile `PD_LLM_MODEL_GENERATION` ayrı
   ayarlar — ama **şu an sağlayıcı ikisi için ortak.** Farklı sağlayıcı
   isteniyorsa arka uç görev başına seçilmeli; bu değişiklik yapılmadı,
   ölçüm sonucu gerektirirse yapılır.

Bir cümlede: bu, Claude'un yerine geçen bir karar değil, **Claude'a
bağımlılığı kaldıran bir seçenek**. Hangisinin nerede kullanılacağını
tahmin değil ölçüm söyleyecek.

---

## Ölçüm sonrası not (13 Ağu 2026)

Yukarıdaki değerlendirmenin **en çok korktuğu şey doğrulanmadı**, en az
beklediği şey ise belirleyici oldu:

- **"Türkçe kalite riski" tutmadı.** Kıyaslamada hayatta kalan beş adayın
  *hepsi* %100 alıntı sadakati tutturdu ve üretilen Türkçe iddialar
  gerçekten atomikti. Uydurulmuş alıntı korkusu bu görevde gerçekleşmedi.
- **Belirleyici olan güvenilirlikti.** Modeller kaliteyle değil,
  çağrının dönüp dönmemesiyle ayrıştı: sekiz adaydan üçü göreve hiç
  varamadı, ikisi çağrıların dörtte üçünü kaybetti.
- **Kalite savunmasının değeri ayrıca kanıtlandı.** Canlı koşum iki
  gerçek kusur ortaya çıkardı (yarıyıl dönemi, yanlış metrik kodu) ve
  ikisi de sessizce sızmak yerine *reddedilen iddia* olarak göründü —
  tam da bu belgede "iyi haber" diye yazılan mekanizma sayesinde.

Ayrıntı: `docs/llm-model-benchmark.md`.
