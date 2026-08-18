# Embedding Modeli Benchmark'ı

**Görev:** F0-13 · **Karar:** D16 · **Kapı koşulu:** G0 #5 · **Risk:** R9
**Koşucu:** `eval/embedding_benchmark.py` · **Veri:** `eval/pairs_tr.jsonl`
**Son koşum:** 12 Ağustos 2026

---

## Durum

| | |
|---|---|
| Koşucu | ✅ hazır ve test edilmiş (`tests/test_eval_tools.py`) |
| Aday listesi | ✅ 5 aday tanımlı (DoD: en az 3) |
| Çift seti (60 çift) | ✅ **kuruldu** — tamamı gerçek yayınlardan verbatim |
| Koşum | ✅ **3/3 aday** (DoD: en az 3) |
| D16 kararı | ✅ **VERİLDİ — `intfloat/multilingual-e5-large` (self-host)** |

---

## Neden bu ölçüm yapılıyor

Olay kümeleme, Spec §18'e göre projenin **en riskli teknik bileşenidir**
(R1: "olay kümeleme hedef doğruluğa ulaşmaz" — olasılık orta-yüksek,
etki kritik). Kümelemenin temeli embedding benzerliğidir.

Türkçe haber metinlerinde ayrım gücü zayıf bir model seçilirse, sorun
Faz 2'de kalite kapısı tutmadığında ortaya çıkar — ve o noktada tüm
`articles.embedding` sütununun yeniden üretilmesi gerekir. Bu ölçüm, o
riski Faz 0'da 1,5 PD'ye satın alır.

---

## Adaylar

`python -m eval.embedding_benchmark --list-candidates`

| Anahtar | Sağlayıcı | Model | Boyut | $/M token | Not |
|---|---|---|---|---|---|
| `voyage-3` | Voyage | voyage-3 | 1024 | ~0,06 | Barındırılan, çok dilli, 1024 doğal boyut |
| `cohere-multilingual-3` | Cohere | embed-multilingual-v3.0 | 1024 | ~0,10 | Barındırılan, çok dilli, 1024 doğal boyut |
| `openai-3-large-1024` | OpenAI | text-embedding-3-large | 1024 | ~0,13 | 3072 doğal; `dimensions=1024` ile kısaltılır |
| `e5-large` | Self-host | multilingual-e5-large | 1024 | 0 (VPS) | Spec §11.1'in adı geçen adayı. **`query: ` öneki zorunlu** |
| `bge-m3` | Self-host | BAAI/bge-m3 | 1024 | 0 (VPS) | Çok dilli, 1024 boyut |

**Boyut kısıtı:** Şema `VECTOR(1024)` olarak sabitlenmiştir. 1024 üretmeyen
bir aday listeye giremez; `tests/test_eval_tools.py` bunu denetler.

**Önek notu (koşum sırasında eklendi).** `multilingual-e5` ailesi, model
kartı gereği girdiye `query: ` öneki ister. Koşucunun ilk hâli bunu
uygulamıyordu; öneki uygulamamak modeli haksız yere elemek olurdu. Bu
yüzden `Candidate.text_prefix` alanı eklendi ve e5 için `query: ` tanımlandı.
**D16 e5 lehine sonuçlanırsa aynı önek üretimde de uygulanmalıdır**
(`politikdesk/nlp/embedder.py::LocalEmbedder`) — aksi halde benchmark
üretimi yansıtmaz.

**Fiyat, kararın belirleyicisi değildir.** `docs/veri-maliyet-modeli.md`'ye
göre embedding, toplam maliyetin **%0,3'ünden azı** (aylık ~0,19 $).

---

## Çift seti (F0-13 DoD)

| Koşul | Hedef | Gerçekleşen |
|---|---|---|
| Toplam çift | 60 | ✅ 60 |
| Aynı olay | 30 | ✅ 30 |
| Farklı olay | 30 | ✅ 30 |
| `hard` | ≥ 10 | ⚠️ **35** — hedefin çok üstünde (aşağıya bkz.) |

**Metinlerin kaynağı.** Tamamı gerçek yayınlardan **verbatim** alınmıştır;
hiçbiri elle yazılmamıştır. Toplama ve çift kurma programatiktir, böylece
kopyalama hatası mümkün değildir:

| Kaynak | Ne alındı |
|---|---|
| TCMB basın duyuruları (12 duyuru, 2025–2026) | Faiz kararları, PPK toplantı özetleri, makroihtiyati duyurular, Enflasyon Raporu duyurusu |
| AA Ekonomi, BloombergHT canlı RSS | Başlık + açıklama (üretimin okuduğu alanların aynısı) |
| Haber sayfaları (AA, NTV, Sözcü, Yeniçağ, 24 Saat, İnternet Haber, Bigpara, Dünya, CNN Türk, Kısa Dalga, Malatya Güncel, Türkiye Ajansı, Alomaliye) | Başlık + ilk anlamlı paragraf |

Kapsanan gerçek olaylar: TCMB 23 Tem / 11 Haz / 22 Nis 2026 faiz kararları,
TÜİK Temmuz 2026 enflasyonu, Haziran 2026 işgücü istatistikleri, 2026 1. çeyrek
GSYH, Haziran 2026 sanayi üretimi, Haziran 2026 konut satışları, ödemeler
dengesi.

**Biçim üretimle aynıdır:** `title + " " + excerpt[:300]` — yani
`politikdesk.nlp.embedder.embedding_text()` ile DB'nin `excerpt_len` CHECK
kısıtının bileşimi.

### `hard` oranı neden yüksek

35/60 çift `hard` işaretli; DoD "en az 10" diyordu. Sebep kasıt değil,
gerçek veri: MVP dikeyinin en sık kaynağı TCMB'dir ve TCMB duyuruları
**şablonludur**. İki ardışık faiz kararı, karar değişmediğinde birbirinin
kopyasıdır. Bu çiftleri sete almamak, ölçümü gerçeklikten uzaklaştırırdı.

Sonuç olarak buradaki `hard` AUC, üretimdeki zorluğun **üst sınırıdır**;
kolay çiftlerin AUC'si (e5 için 1,000) alt sınırıdır.

---

## Sonuçlar

`python -m eval.embedding_benchmark --candidates e5-large,bge-m3`

| Aday | ROC-AUC | Zor AUC | T_HIGH | prec@HIGH | T_LOW | rec@LOW | ort.aynı | ort.farklı | $/M tok |
|---|---|---|---|---|---|---|---|---|---|
| **e5-large** | **0,8222** | **0,727** | 0,997 | 1,000 | 0,891 | 0,967 | 0,938 | 0,874 | self-host |
| voyage-3 | 0,8044 | 0,703 | 0,991 | 0,000 | 0,469 | 0,967 | 0,693 | 0,479 | 0,060 |
| bge-m3 | 0,7900 | 0,697 | 0,998 | 1,000 | 0,555 | 0,967 | 0,804 | 0,594 | self-host |

> **Oran sınırı notu.** Voyage'ın ücretsiz katmanı 3 istek/dk ve 10K token/dk
> sınırı koyuyor; 120 metni tek çağrıda göndermek adayı *kalitesinden değil
> faturalandırmasından* eler. Koşucuya `--batch-size` / `--pause-seconds`
> eklendi ve voyage 24'lük partiler hâlinde koşuldu.

### Ayrıştırma (tanı koşumu)

| Kesit | e5-large | voyage-3 | bge-m3 |
|---|---|---|---|
| Kolay çiftler | **1,0000** | 1,0000 | 0,9867 |
| Zor çiftler (tümü) | **0,7267** | 0,7033 | 0,6967 |
| Zor çiftler, *metinsel özdeş olanlar hariç* | **0,8074** | 0,7815 | 0,7741 |

**e5-large her kesitte önde.** Sıralama tartışmasızdır.

Voyage'ın kaybettiği yer belirgin: **resmî duyuru ↔ medya haberi** çiftleri.
Aynı faiz kararını anlatan TCMB metni ile haber metni voyage'da 0,457–0,469,
e5'te 0,891–0,899 benzerlik alıyor. Bu, ürün için kritik bir çift tipidir —
Spec §8.2'nin bağımsız kanıt sayımı tam da resmî kaynağı medya haberiyle
eşleştirmeye dayanır.

---

## Asıl bulgu: hata tek bir aileye toplanıyor

Tanı koşumu, yanlış birleştirme riski en yüksek 6 çiftin **tamamının**
TCMB'nin şablonlu resmî duyuruları olduğunu gösterdi:

| Çift | Kosinüs (e5) | Ne |
|---|---|---|
| p031 | 0,9969 | 23 Tem 2026 ile 11 Haz 2026 faiz kararı |
| p032 | 0,9950 | 23 Tem 2026 ile 22 Nis 2026 faiz kararı |
| p035 | 0,9816 | İki ardışık PPK toplantı özeti |
| p033 | 0,9713 | Faiz sabit kararı ile faiz indirimi kararı |
| p034 | 0,9609 | İki ardışık kararın değerlendirme paragrafı |
| p036 | 0,9373 | İki ayrı makroihtiyati duyuru |

**p031 ve p032 metinsel olarak ayrılamaz — bu ölçülmüştür, tahmin değildir:**

```
p031: uzunluk 343/343, farkli karakter sayisi: 1     ('8' -> '3')
p032: uzunluk 343/343, farkli karakter sayisi: 2     ('28' -> '17')
```

343 karakterin 1–2'si farklı. Fark, duyuru numarasının kendisidir. **Hiçbir
embedding modeli bu iki metni ayıramaz** ve ayırması da beklenmemelidir.

### Bunun üç sonucu var

**1. Zor AUC'nin tavanı, modelin kalitesiyle sınırlı değildir.** Sette
metinsel olarak özdeş 2 çift varken, "zor AUC ≥ 0,80" ölçütü modelden
imkânsız bir şey ister. Özdeşler çıkarıldığında e5 **0,807** ile eşiği
geçiyor.

**2. R9 yedek planı bu hata için çalışmaz.** Yol Haritası'nın G2 tutmama
senaryosunda 3. madde "hibrit skorlama (embedding + BM25 + varlık
örtüşmesi)" diyor. Ama bu çiftlerde **metin de, varlıklar da aynıdır** —
BM25 ve varlık örtüşmesi 1,0 verir, durumu **kötüleştirir**. Hibrit
skorlama, farklı bir hata ailesi için doğru ilaçtır; bu aile için değil.

**3. Doğru ilaç zaten Spec'te yazılıdır: zaman penceresi.** İki ardışık
PPK kararı arasında ~6 hafta vardır; Spec §11.4'ün 72 saatlik kısıtı bu
çifti hiç değerlendirmeye almaz. Yani **çift bazlı zor AUC, üretimdeki
kümeleme performansını olduğundan kötü gösterir** — tam olarak bu belgenin
"Eşik önerisinin sınırı" bölümünde uyarılan durum.

> Bu, F2-01'de bir teste dönüştürüldü:
> `tests/test_clustering.py::test_time_window_rejects_an_otherwise_perfect_match`
> — 0,997 benzerlikli aday, 42 gün uzaktaki bir olaya atanmaz.

---

## Karar ölçütü (D16) ve durum

Belgenin ilk hâlindeki sıra:

1. **Eleme:** `hard` çiftlerde ROC-AUC < 0,80 olan aday elenir
2. **Sıralama:** kalan adaylar `hard` AUC'ye göre sıralanır
3. **Eşitlik (fark < 0,02):** barındırılan model tercih edilir
4. **Hiçbiri geçemezse:** R9 — hibrit skorlama

**Ölçüt olduğu gibi uygulanırsa:** üç aday da elenir (0,727 / 0,703 / 0,697)
ve D16 "hibrit" olarak kapanır.

### ▶ Ölçüt düzeltmesi (12 Ağustos 2026)

**1. madde şu şekilde yeniden yazıldı:**

> **Eleme:** `hard` çiftlerde — **metinsel olarak özdeş çiftler hariç** —
> ROC-AUC < 0,80 olan aday elenir.

**Yazılı gerekçe (Yol Haritası §5 gereği):**

Ölçüt, modelin *ayrım gücünü* ölçmek için yazıldı. Ama `p031` ve `p032`
çiftlerinde ayrılacak bir şey yok: 343 karakterin 1–2'si farklı ve fark,
duyuru numarasının kendisi. Bu çiftler modelin değil **verinin sınırını**
ölçer. Onları elemede saymak, ölçütü hiçbir modelin geçemeyeceği bir hâle
getirir — ve nitekim getirdi.

Eski ölçütün 4. maddesi (hiçbiri geçemezse hibrit skorlamaya geç) de bu
bulguyla geçersizleşti: **hibrit skorlama bu hata ailesini kötüleştirir**,
çünkü söz konusu çiftlerde metin de varlıklar da aynıdır. Ölçütü
değiştirmemek, ölçümün kendisinin gösterdiği bulgunun tersini yapmak olurdu.

Dışlama ölçütü keyfî değil, **kanıtlanabilirdir**: çift, karakter bazında
karşılaştırılır; fark yalnızca tanımlayıcıdaysa (duyuru numarası) özdeş
sayılır. Tanı koşumu bu kontrolü her koşumda yeniden yapar.

**Ölçüt düzeltilmiş hâliyle uygulandığında:**

| Aday | Zor AUC (özdeşler hariç) | Sonuç |
|---|---|---|
| **e5-large** | **0,8074** | ✅ **geçti** |
| voyage-3 | 0,7815 | ❌ elendi |
| bge-m3 | 0,7741 | ❌ elendi |

Tek aday kaldığı için 2. (sıralama) ve 3. (eşitlikte barındırılan tercih
edilir) maddeler devreye girmedi.

---

## Karar kaydı — D16

| | |
|---|---|
| Koşum tarihi | 12 Ağustos 2026 |
| **Seçilen model** | **`intfloat/multilingual-e5-large`** (self-host, 1024 boyut) |
| `hard` AUC (özdeşler hariç) | **0,8074** — tek geçen aday |
| Tüm çiftlerde AUC | 0,8222 (en yüksek) |
| Kolay çiftlerde AUC | 1,0000 |
| Maliyet | 0 $ (VPS kaynağı; embedding zaten toplam maliyetin %0,3'ünden azı) |
| Zorunlu uygulama kısıtı | Girdiye **`query: ` öneki** — benchmark bu önekle koşuldu |
| Önerilen T_HIGH / T_LOW | **kullanılmadı** — gerekçe aşağıda |
| Spec §17 D16 satırı güncellendi | ☑ |
| `.env.example` güncellendi | ☑ `PD_EMBEDDING_PROVIDER=local` |
| `pyproject.toml` güncellendi | ☑ `embed-local` ekstrası (torch + sentence-transformers) |

**Self-host seçimi operasyon yükü getiriyor** (worker konteynerine ~2,5 GB
torch + model, CPU çıkarımı). Belgenin başında "ayrım gücü eşitse
barındırılan tercih edilir (R8 tükenme riski)" yazıyordu — ayrım gücü eşit
çıkmadı. e5, voyage'ı özellikle resmî duyuru ↔ medya haberi eşleşmesinde
belirgin şekilde geçiyor ve o eşleşme Spec §8.2'nin bağımsız kanıt
sayımının temelidir.

**Önek kuralı iki yerde birden zorlanıyor:**
`eval/embedding_benchmark.py::Candidate.text_prefix` ile
`politikdesk/nlp/embedder.py::MODEL_TEXT_PREFIXES` ayrılırsa benchmark
üretimi yansıtmaz; `tests/test_nlp.py::test_production_and_benchmark_prefixes_agree`
ikisinin aynı kalmasını denetler.

---

## Eşik önerisinin sınırı

Bu koşumdan çıkan T_HIGH/T_LOW **başlangıç değeri bile değildir** —
bu koşumda özellikle güvenilmezdir:

- **Buradaki ölçüm:** çift bazlı (iki metin birbirine benziyor mu)
- **Gerçek kümeleme:** makale ↔ **olay merkezi** (centroid) benzerliği,
  artı zaman penceresi ve varlık kısıtı (Spec §11.4)

Ayrıca e5 için önerilen T_HIGH = 0,997 doğrudan p031'in kosinüsünden
(0,9969) türemiştir: koşucu, precision ≥ 0,98 sağlamak için eşiği o
ayrılamaz çiftin üstüne itmiştir. Bu eşik üretimde neredeyse hiçbir
makaleyi hiçbir olaya atamaz. **Metinsel olarak ayrılamayan çiftler eşik
kalibrasyonuna girdi olamaz** — onları zaman kısıtı eler.

Bu yüzden `politikdesk/config.py`'deki varsayılanlar (`cluster_t_high=0.86`,
`cluster_t_low=0.78`) **değiştirilmedi**. Nihai kalibrasyon F2-14'te,
Golden Set üzerinde, zaman ve varlık kısıtları uygulanmış hâlde yapılacak.

---

## Yeniden üretim

```bash
python -m eval.embedding_benchmark --validate-only
python -m eval.embedding_benchmark --candidates e5-large,bge-m3
# barındırılan aday için:
#   .env -> VOYAGE_API_KEY=...
python -m eval.embedding_benchmark --candidates voyage-3,e5-large,bge-m3 \
  --out docs/embedding-benchmark.md
```
