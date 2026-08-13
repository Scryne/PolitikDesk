# D18 — Taslak üretimi için LLM model seçimi

**Karar:** `nvidia/nemotron-3-super-120b-a12b` (NVIDIA NIM ücretsiz katmanı)
**Güven düzeyi:** 🟡 **zayıf — ölçüm iki adayı ayıramadı** (aşağıya bakınız)
**Tarih:** 13 Ağustos 2026
**Araç:** `python -m scripts.generation_benchmark`
**Bağlam:** B-71 (D17'nin açık bıraktığı kalem) · `docs/llm-model-benchmark.md`

---

## Bu kararın gerekçesi neden D17'den farklı

D17 **çıkarım** görevini ölçtü ve kapsam sınırını açıkça yazdı:

> "`PD_LLM_MODEL_GENERATION` şimdilik aynı modele ayarlandı ama bu bir
> karar değil, yer tutucudur: taslak yazımı farklı bir görevdir (uzun
> metin, üslup, tutarlılık) ve Faz 3'te kendi ölçümüyle seçilmelidir."

Bu belge o ölçümü yapar. Sonuç aynı modeli işaret ediyor — ama **aynı
sebeple değil** ve **aynı güvenle değil.**

## Yöntem

Ölçüt tahmine değil kapıya dayanır. Kapı G3 koşul 2 nesnel ve ikilidir:
*"taslakta kanıtta olmayan sayı/tarih = %0"* (sert kapı, Spec §13.2).
Bunu ölçmek için "iyi taslak hangisiydi" bilgisine gerek yoktur: kanıt
seti bilinir, üretilen metin bilinir, `editorial/grounding_check.py`
ikisini karşılaştırır.

| Ölçülen | Nasıl |
|---|---|
| **Grounding** | Kanıt dışı sayı/tarih/alıntı üretmeyen taslak oranı (F3-12) |
| **Sözleşme uyumu** | Uydurulmuş `cited_claim_ids`, yasak alan, boş gövde (F3-10) |
| **Güvenilirlik** | Çağrının dönüp dönmediği — D17'de ayırt edici olan buydu |
| **Gecikme / maliyet** | Üretim modeli çıkarımdan pahalıdır (Spec §13.3) |

Girdi: `eval/golden_claims_v1.jsonl` — 3 olay × 3 açı (`Bilgilendir` /
`Analiz Et` / `Eleştir`) × 4 aday = 36 çağrı. Örnek deterministiktir.

## Ham bulgular

```
python -m scripts.generation_benchmark --events 3 --timeout 240 --retries 3
```

| Model | Çağrı | Taslak | Grounding (ham) | Sözleşme | Ort. uzunluk | Gecikme |
|---|---:|---:|---:|---:|---:|---:|
| `nvidia/nemotron-3-super-120b-a12b` | **8/9** | 8 | 88% | 100% | 229 | **19,0 sn** |
| `deepseek-ai/deepseek-v4-flash-0731` | **8/9** | 8 | 62% | 100% | 549 | 42,3 sn |
| `openai/gpt-oss-120b` | 3/9 | 3 | 67% | 67% | 516 | 98,1 sn |
| `z-ai/glm-5.2` | 2/9 | 2 | 100% | 100% | 380 | 10,3 sn |

Ham tablo **iki ölçüm hatası içeriyordu.** İkisi de bu koşumda bulundu.

---

## Bulgu 1 — denetleyicide gerçek bir yanlış pozitif (düzeltildi)

`gpt-oss-120b` metne iddia referansı yazdı:

```
...cari işlemler açığı 4 milyar 918 2 milyon dolar seviyesinde olacak (C1).
```

`grounding_check` bunu **"kanıtta bulunmayan sayı: 1"** diye işaretledi:
sayı deseni `C1` içindeki rakamı yakalıyordu.

Teşhis yanlıştı. `C1` bir veri değil, bir tanımlayıcıdır. Referansın
gövdede bulunması yine de istenmez — ama onu yakalaması gereken kontrol
F3-13'ün "bağlanamayan cümle"sidir, halüsinasyon savunması değil.

**Düzeltme:** harfe bitişik rakam (`C1`, `BIST100`, `A101`) sayı
sayılmaz. Regresyon koruması:
`tests/test_grounding.py::test_identifiers_are_not_treated_as_data`.

Düzeltmeden sonra `gpt-oss-120b`'nin iki "kanıt dışı" öğesinin **ikisi
de** ortadan kalktı (3/3 → %100).

## Bulgu 2 — Golden Set kanıt metinleri noktalamasız (ölçüm kirliliği)

`deepseek-v4-flash`'in üç ihlalinin **üçü de aynı sayıydı**: `918,2`.

Kanıt metni şöyle:

```
Ankete gore ekonomistler cari islemler hesabinin 4 milyar 918 2 milyon
dolar acik verecegini ongordu
```

Model **doğru okudu** — `918 2` → `918,2`. Denetleyici ise kanıtta
"918" ve "2" adında iki ayrı sayı gördü ve `918,2`'yi uydurma saydı.

Ölçüldü: **43 kanıt metninin 43'ünde de virgül yok.** Golden Set'in
`evidence[].text` alanları aksansız ve noktalamasız normalleştirilmiş.
Bu bir fikstür özelliğidir, üretim davranışı değil — üretimde
`evidence.quote_span` gerçek makale metninden gelir ve `verify_quote`
onun **birebir** geçtiğini zaten doğrular.

**Bu, denetleyici hatası değildir ve denetleyici bunun için
gevşetilmemiştir.** Ama sayısal grounding'in bu fikstür üzerinde
ölçülemeyeceği anlamına gelir. Yeni kalem: **B-73**.

---

## Düzeltilmiş bulgular

Kaydedilmiş taslak gövdeleri, düzeltilmiş denetleyiciyle yeniden
puanlandı (yeni API çağrısı yapılmadan — `--out` JSON'u gövdeleri
saklıyor):

| Model | Çağrı | Grounding (tümü) | **Grounding (evt-022 hariç)** | Kalan ihlal |
|---|---:|---:|---:|---|
| `nvidia/nemotron-3-super-120b-a12b` | 8/9 | 7/8 (88%) | **6/6 (100%)** | `52,391` — türetme |
| `deepseek-ai/deepseek-v4-flash-0731` | 8/9 | 5/8 (62%) | **5/5 (100%)** | `918,2` ×3 — fikstür |
| `openai/gpt-oss-120b` | 3/9 | 3/3 (100%) | — | — |
| `z-ai/glm-5.2` | 2/9 | 2/2 (100%) | **2/2 (100%)** | — |

`evt-022` noktalaması soyulmuş sayıyı içeren tek olaydır; dışarıda
bırakıldığında **dört adayın da grounding'i %100.**

`nemotron`'un kalan tek ihlali gerçektir ve tam olarak kapının var olma
sebebidir: kanıt "52 milyar 391 milyon dolar" derken model bunu
"52,391 milyon dolar" olarak **yeniden ifade etti**. Aritmetik doğru,
davranış yanlış — promptun açık yasağı: *"Kendi hesabını yapma."*

## Gerekçe

**Ölçüm ilk iki adayı ayıramadı.** Kirlenmemiş olaylarda ikisi de %100,
güvenilirlikte ikisi de 8/9. Karar bu yüzden ikincil ölçütlere düştü:

| Ölçüt | `nemotron-3-super` | `deepseek-v4-flash` |
|---|---|---|
| Kirli olmayan grounding | %100 (6/6) | %100 (5/5) |
| Tamamlanan çağrı | 8/9 | 8/9 |
| **Gecikme** | **19,0 sn** | 42,3 sn (2,2×) |
| Ortalama uzunluk | 229 krk | 549 krk |
| Operasyon | **çıkarım modeliyle aynı** | ikinci bir kapasite havuzu |

Belirleyici olan **gecikme ve operasyonel teklik** oldu. Günde iki
brifing penceresi ve etkileşimli bir "Üret" butonu olan bir üründe iki
kat gecikme kullanıcıya doğrudan yansır. Ayrıca çıkarım ve üretimin aynı
modelde olması tek bir kota havuzu, tek bir hata modu ve tek bir izleme
noktası demektir.

`deepseek-v4-flash`'in daha uzun taslak üretmesi (549 vs 229 karakter,
600 karakter bütçesinde) bir kalite avantajı **olabilir** ama ölçülmedi:
uzunluk kalite değildir ve bu koşumda üslup değerlendirmesi yapılmadı.

### Elenen ikisi

`gpt-oss-120b` (3/9) ve `glm-5.2` (2/9) **kapasiteden düştü.** İkisinin
de grounding'i temizdi; ama D17'nin dersi burada da geçerli:
*"cevabı iyi ama üçte biri düşüyor" kabul edilebilir değil.*
`gpt-oss-120b` ayrıca var olmayan bir iddia kimliği (`0`) uydurdu —
tek sözleşme ihlali.

## Kararın sınırı — bu ölçüm neyi KANITLAMAZ

Bu, D17'den **daha zayıf** bir karardır ve öyle işaretlenmiştir:

1. **Örneklem küçük** — model başına 8 taslak. G3 koşul 2 elli taslaklık
   denetim ister; bu ölçüm bir *ön eleme*dir, kapı kararı değil.
2. **Ayırt edici ölçüt ayıramadı** — grounding'de beraberlik var, karar
   gecikmeye dayanıyor. Gecikme önemlidir ama kapının ölçütü değildir.
3. **Fikstür kirli** (B-73) — sayısal grounding, Golden Set'in bu
   sürümünde güvenilir ölçülemez.
4. **Claude ölçülmedi** (B-67) — `ANTHROPIC_API_KEY` `.env`'de **boş**.
   İki Claude modeliyle koşum denendi ve 18 çağrının 18'i
   `LLMNotConfigured` ile düştü.
5. **Üslup ve Türkçe kalite göz denetimine girmedi** — D17'nin
   Kademe 3'ünün karşılığı burada yapılmadı.

### Kararı yeniden açması gereken durumlar

* Anahtar geldiğinde Claude karşılaştırması (**B-67**)
* Fikstür düzeltildikten sonra yeniden ölçüm (**B-73 → B-74**)
* `nemotron` kapasitesi düşerse: geçiş tek satırdır —
  `PD_LLM_MODEL_GENERATION=deepseek-ai/deepseek-v4-flash-0731`

## Yeniden üretme

```bash
# Ücretsiz katman (NVIDIA NIM)
python -m scripts.generation_benchmark --events 3 --timeout 240 --out sonuc.json

# Claude karşılaştırması (B-67 — ANTHROPIC_API_KEY gerekir)
python -m scripts.generation_benchmark --provider anthropic \
    --models claude-sonnet-5,claude-opus-5 --events 3
```

> ⚠ Ücretsiz katman kapasitesi gün içinde ciddi değişir. Bu koşumun
> ikinci turu (4 olay × 3 açı × 3 model) saatte ~5 çağrı hızına düştü ve
> yarıda kesildi. Kota davranışı hâlâ ölçülmemiş bir kalemdir (**B-68**).
