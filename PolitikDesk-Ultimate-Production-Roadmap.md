# PolitikDesk — Ultimate Production Roadmap

> Sürüm: 1.0  
> Tarih: 18 Ağustos 2026  
> Referans: 18 Ağustos 2026 Tam Kapsam Denetim Raporu  
> Hedef: PolitikDesk'i güvenilir bir politik istihbarat / kanıt / brifing platformundan, ölçülebilir biçimde "production-grade political intelligence system" seviyesine taşımak.

---

## 0. Başlangıç Kapısı — Önce Mevcut Durumu Dondur

### Amaç
Yeni özellik geliştirmeden önce 18 Ağustos audit çıktısını değişmez bir baseline olarak kabul etmek.

### Yapılacaklar

- [x] 22 değişikliği incele. → 23 dosya, `audit/2026-08-18` dalında.
- [x] `git diff --check` → **0 uyarı.** İlk koşumda yüzlerce uyarı verdi
      ve hiçbiri gerçek değildi: depoda 39 `.py` + 10 `.md` CRLF, 290
      dosya LF, 2 dosya karışıktı ve `.gitattributes`'ta `*.py` kuralı
      yoktu. CRLF'li dosyada satır sonundaki `\r` "trailing whitespace"
      sayılıyor. Kural eklendi, 59 dosya normalize edildi
      (`git diff --ignore-cr-at-eol` içerik farkı olmadığını doğruladı).
      `pd.cmd` CRLF kaldı — orada CRLF `cmd.exe` gereğidir; bayt bayt
      doğrulandı.
- [x] `ruff check .` → 0 hata
- [x] `mypy` → 156 dosya, 0 hata
- [x] `pytest` → **1092 passed / 0 skipped** (denetim sırasında 1080'di)
- [x] `pip-audit` → 0 zafiyet
- [x] `scripts/check_architecture.py` → temiz
- [x] Boru hattı sağlık kontrolü → **12/12 green**
- [x] Test verisi artıklarını canlı DB'den kaldırma kararını ver.
      → Silindi. Kapsam ilk sanılandan büyük çıktı: 2 kaynak + 6 makale +
      6 **olay** + 15 ilişki. Olaylar `example.com` URL'liydi ve gündem
      akışında görünüyordu; ilişkilerin hiçbiri gerçek olaya sızmamıştı.
      Silmeden önce tam yedek alındı ve doğrulandı (22 MB, 254 nesne).
- [x] `.gov.tr` TLS problemini ağ/ortam seviyesinde çöz.
      → **Kök neden bulundu, çözüm kullanıcı eylemi gerektiriyor.**
      Ayrıntı aşağıda (O-01).
- [x] RSSHub servisinin neden timeout verdiğini çöz. → **Çözüldü** (O-02).
- [x] Baseline commit oluştur. → `60866b9`, ardından `76d37f4` (satır
      sonu) ve `a4fb130` (RSSHub). Push edilmedi.

### O-01 · `.gov.tr` TLS — teşhis kesin, eylem sizde

Üç konak (`resmigazete`, `sayistay`, `tccb`) TCP'de sorunsuz bağlanıyor
ama TLS el sıkışması **sunucu tarafından sıfırlanıyor** (`WinError 10054`),
sertifika doğrulaması KAPALIYKEN bile. Aynı testte `tuik`, `tcmb` ve
`aa` sorunsuz el sıkışıyor.

Sebep süreç listesinde bulundu: **`goodbyedpi.exe` (PID 5536) Windows
servisi olarak çalışıyor** (`SERVICE_NAME: GoodbyeDPI`, durum RUNNING).
GoodbyeDPI, DPI atlatmak için TLS ClientHello'yu WinDivert sürücü
katmanında parçalar; bu üç sunucu parçalanmış el sıkışmayı reddediyor.
Bu, `config/sources.yml`'de B-44 olarak zaten kayıtlı olan senaryonun
birebir tekrarıdır.

Servisi durdurmadım — sistem servisi, yönetici hakkı istiyor ve muhtemelen
bilinçli bir sebeple orada. Denemek isterseniz:

```
net stop GoodbyeDPI          :: yönetici komut isteminde
```

Sonrasında doğrulama: `python -m scripts.verify_feeds` veya `pd ingest`.

### O-02 · RSSHub — çözüldü

Köprünün önbellek ıskası ölçüldü: 21,6 / 22,6 / 24,0 / 24,7 sn
(önbellek isabetinde 4 ms). Adaptörün okuma zaman aşımı 18 sn'ydi — eşik
işin gerçek süresinin altındaydı. Her ıska `ReadTimeout` oluyor, üç
hatada devre kesici açılıyor ve kalan tüm sosyal kaynaklar anında
düşüyordu.

Zaman aşımını tek başına yükseltmek çözüm değildi: toplama sıralı ve
46 × ~30 sn ≈ 23 dk, oysa çekirdek tur 5 dakikada bir koşuyor. İki küme
ayrıldı (`Pipeline.run_all(select=...)`, yeni `ingest_social` görevi,
30 dk aralık, ölçüme dayalı zaman aşımları).

| | kaynak | süre | öğe | hata | aralık |
|---|---:|---:|---:|---:|---:|
| çekirdek tur | 42 | **19,9 sn** | 1408 | 0 | 300 sn |
| sosyal tur | 46 | **476,6 sn** | 1131 | 18 | 1800 sn |

Sosyal turun 8 dakika sürmesi ayırmanın neden zorunlu olduğunu tek başına
gösteriyor: 5 dakikalık turun içine hiçbir zaman sığmıyordu.

Kaynak sağlığı: `{green 39, amber 41, red 9}` → `{green 69, amber 11, red 8}`.
Devre kesici kaynaklı tek bir hata kalmadı. Kalan 8 kırmızının 7'si
RSSHub'ın X'ten aldığı HTTP 503 (yukarı akış), 1'i O-01'e bağlı.

### Exit Criteria

- [x] CI ile lokal sonuçlar birebir.
- [x] 0 skip. *(Denetimde bulunan D-06 bunu mümkün kıldı: DB testleri
      test sırasına göre sessizce atlanıyordu.)*
- [x] 0 bilinen kritik/yüksek kod kusuru.
- [x] Canlı DB test artığı yok.
- [x] Baseline commit mevcut.
- [ ] **AÇIK:** O-01 (GoodbyeDPI) kullanıcı eylemi bekliyor. Kod tarafında
      yapılacak bir şey yok; `resmi-gazete` bu çözülene kadar kırmızı kalır.

**Öncelik: P0 — kod tarafı KAPANDI, tek açık madde O-01.**

---

# PHASE 1 — Güvenilirlik ve Veri Kaynağı Temeli

## 1.1 TCMB EVDS Entegrasyonu

**Öncelik: P0 — TAMAMLANDI (19 Ağu 2026). 6/6 gösterge canlı doğrulandı.**

### Sonuç

| Seri | TCMB adı | Sıklık |
|---|---|---|
| `TP.BISPOLFAIZ.TUR` | Türkiye Merkez Bankası Politika Faiz Oranı | aylık |
| `TP.DK.USD.A.YTL` | (USD) ABD Doları (Döviz Alış) | günlük |
| `TP.DK.EUR.A.YTL` | (EUR) Euro (Döviz Alış) | günlük |
| `TP.AB.B6` | Toplam Rezervler | aylık |
| `TP.ENFBEK.PKA12ENF` | Piyasa katılımcılarının 12 ay sonrası yıllık enflasyon beklentileri (%) | aylık |
| `TP.KAVRAMSAL.HAMM2.INDX` | Kur Etkisinden Arındırılmamış M2 | haftalık |

### Yol boyunca çıkan iki gerçek

**EVDS v2 kapanmış.** `evds2.tcmb.gov.tr/service/evds/...` her yolda 302 ile
evds3 köküne yönlendiriyor; gelen şey React SPA kabuğu. Adaptörün HTML
muhafızı bunu yakaladı — muhafız olmasaydı her tur 200 alıp 0 öğe üretir
ve "başarılı" görünürdü (B-42/B-43'ün aynısı). Yeni taban SPA'nın JS
paketinden çıkarıldı: `/igmevdsms-dis`.

**Probe dört hatalı kod yakaladı.** İkisi veri döndürüyordu ama başka bir
büyüklüğü ölçüyordu — `TP.APIFON4` "Ağırlıklı Ortalama Fonlama Maliyeti"
getiriyor, politika faizi değil. Kapı olmasaydı "TCMB politika faizi:
%40,0" ekrana çıkardı. Doğru kodlar canlı arama ucuyla bulundu.

### Hedef

TCMB'nin makine okunabilir ekonomik göstergelerini birinci sınıf `official_value` kaynağı haline getirmek.

### Kapsam

- EVDS adapter
- API credential yönetimi
- rate limiting
- retry/backoff
- response schema validation
- metric mapping
- period normalization
- source provenance
- freshness tracking
- historical series persistence

### İlk göstergeler

1. Politika faizi
2. USD/TRY
3. EUR/TRY
4. Rezervler
5. Enflasyon beklentileri
6. Para ve banka istatistikleri

### Veri sözleşmesi

```text
metric
value
unit
period
source
source_url
retrieved_at
published_at
revision
```

### Testler

- fixture tabanlı API response testleri
- malformed response
- missing value
- revised observation
- duplicate observation
- stale data
- rate-limit
- timeout
- source provenance

### Exit Criteria

- EVDS'den en az 5 gösterge güvenilir şekilde geliyor.
- Gösterge şeridi yalnızca resmi veriden besleniyor.
- Uydurma/fallback numeric value üretimi imkânsız.
- Her değer provenance taşıyor.

---

## 1.2 TÜİK Veri Yayımlama Takvimi

**Öncelik: P0 — TAMAMLANDI (19 Ağu 2026). F2-18 üç faz sonra kapandı.**

Kapsam beklenenden büyük çıktı: bu yalnızca TÜİK takvimi değil, **Ulusal**
Veri Yayımlama Takvimi — 31 kurum, 2026 için 4.085 kayıt. Uç kimlik
doğrulama istemiyor ve yayımlananları/bekleyenleri ayrı listelerde
veriyor, yani "beklenen/gerçekleşen" ayrımını kurum yapıyor.

| | |
|---|---:|
| içe aktarılan | 3.474 kayıt (API ile birebir, sıfır kayıp) |
| bugün beklenen | 8 resmî yayın |
| eşleşen | 243 |
| kaçırılan | 15 → 0 |

Gecikme ölçümü kurum bazında: TCMB 0,6 dk · TÜİK 1,0 dk · BDDK 42,8 dk.

TÜİK'in 2026 Ulusal Veri Yayımlama Takvimi resmi yayın tarihlerini ve saatlerini önceden ilan ediyor. Bu nedenle PolitikDesk'in "beklenen gelişme" katmanı için doğal bir birincil kaynak. citeturn0search0turn0search48

### Yapılacaklar

- Takvim adapter'ı
- kurum filtresi
- yayın türü
- beklenen yayın zamanı
- gerçekleşen yayın zamanı
- gecikme metriği
- upcoming-events tablosu
- takvim → olay ilişkilendirme

### Exit Criteria

Kullanıcı:

> "Bugün hangi resmi ekonomik verilerin açıklanması bekleniyor?"

sorusuna deterministik veri tabanlı cevap alabilmeli.

---

## 1.3 KAP

**Öncelik: P1 — ERTELENDİ (19 Ağu 2026). Karar: `docs/ADR-007-KAP-ENTEGRASYONU.md`**

### Ölçüm önce yapıldı, adaptör yazılmadı

Bu maddenin dayanağı "KAP'ın Veri Yayın Servisi REST API duyurusu"ydu.
Ölçüm bu varsayımı doğrulamadı: **VYS, veri satıcılarına yönelik
abonelikli bir yayın servisidir, açık bir REST API değildir.**

`scripts/probe_kap.py` ile ölçülenler:

| Ne | Sonuç |
|---|---|
| Site sayfaları | HTTP 200 (erişilebilir) |
| `robots.txt` | **HTTP 666** — izin beyanı okunamıyor |
| `/tr/api/disclosures` | **ReadTimeout** (tüm parametre ve User-Agent kombinasyonları) |
| Diğer bildirim uçları | HTTP 404 |
| Sayfanın sunucu yükü | Bildirim **içermiyor** (yalnızca endeks/şirket meta verisi) |

Tarayıcı ve bot User-Agent'ı **aynı** sonucu verdi — hedefli bot engeli
değil, uç herkese kapalı.

### Neden adaptör yazılmadı

1. **Doğrulanmamış uca adaptör yazılmaz.** Aynı kural bu fazda EVDS seri
   kodlarına da uygulandı (altı serinin altısı `verified=False`). Bu depo
   doğrulanmamış kaynağın bedelini üç kez ödedi (B-42, B-43, EVDS'nin
   anahtarsız HTML yanıtı): uç 200 döner, gövde beklenen şey değildir,
   tur **sessizce başarılı** görünür.
2. **İzin beyanı okunamıyor.** `robots.txt` alınamıyor; `HttpClient` bunu
   "politika yok" sayıp izin veriyor — ama bu izin değil, izin yokluğunun
   varsayılan davranışıdır.
3. **Hacim/alaka oranı.** KAP günde yüzlerce kurumsal bildirim yayımlar,
   çoğu bu ürünün dikeyiyle ilgisiz. Sert bir konu filtresi şart — ve o
   filtre erişim çözülmeden tasarlanamaz.

### Faz 1.2 bu maddenin bir bölümünü zaten karşıladı

| Sinyal | Erişilebilir karşılığı | Durum |
|---|---|---|
| SPK düzenleme/yaptırım | Ulusal Veri Yayımlama Takvimi (515 kayıt) | ✅ |
| BDDK bankacılık verileri | Aynı takvim (554 kayıt) | ✅ |
| Özelleştirme, kamu bankası | Resmî Gazete + Hazine | ✅ |

Açık kalan asıl katman **şirket düzeyinde özel durum açıklamalarıdır.**

### Yeniden açılma koşulu

`python -m scripts.probe_kap` çıkış kodu 0 döndürürse, ya da VYS
aboneliği alınırsa. Ayrıntı ADR-007 §6'da.

---

# PHASE 2 — Source Intelligence

## 2.1 Kaynak Kalitesi Skoru

**Öncelik: P0 — TAMAMLANDI (19 Ağu 2026)**

⛔ Skor bir **güvenilirlik yargısı değildir.** Kaynağın haberciliği
hakkında hiçbir şey söylemez; yalnızca akışın teknik sağlığını ölçer.
Gerekçe Spec §8.5'tir ve `tests/test_source_quality.py` hiçbir bileşenin
içeriğe bakmadığını tarar.

Altı bileşen, hepsi `source_fetch_log`'dan (7 günde 51.166 tur) ölçülmüş:
authority · independence · freshness · reliability · structuredness · yield.

**Ölçülemeyen ≠ sıfır.** "Hiç turu yok" ile "hep başarısız" aynı şey
değil; ölçülemeyen bileşen ortalamaya girmez ve `coverage` alanı skorun
kaç bileşene dayandığını söyler.

**Bakım sinyali yapısal özellik için yanmaz.** İlk uygulama 24 kaynağı
`authority` yüzünden işaretliyordu — sosyal kaynakları sosyal oldukları
için. Sinyal artık yalnızca düzeltilebilir bileşenlerden geliyor.

Canlı sonuç: `resmi-gazete` (tazelik 0, başarı %53,6 → O-01), 7 X hesabı
(0/400-600 tur), ve **yeni bir bulgu**: sosyal kaynaklar 4.600 öğe çekip
4.610'unu tekrar diye atıyor — ölçülmemiş bir israftı, artık görünür.

Uçlar: `/admin/source-quality`, `/admin/source-quality/attention`.

### Score

```text
source_quality =
    authority
  + independence
  + freshness
  + reliability
  + structuredness
  + historical_consistency
```

### Her kaynak için

- authority score
- independence_group
- reliability score
- freshness SLA
- parse success rate
- HTTP health
- duplicate rate
- correction rate

### Dashboard

```text
Source
Health
Freshness
Reliability
Independence
Last Success
Last Failure
```

---

## 2.2 Source Dependency Graph

**Öncelik: P1 — ÇIKIŞ ÖLÇÜTÜ ZATEN SAĞLANMIŞ (19 Ağu 2026 doğrulaması)**

Ayrım hâlihazırda hem veri hem arayüz katmanında var:
`events.article_count` (görünen kaynak) ile `independence_groups` ve
`independent_count` (bağımsız grup) ayrı taşınıyor; `web/feed.py` ve
`web/event.py` ikisini ayrı gösteriyor.

Canlı örnek — istenen sinyalin ta kendisi:

| olay | makale | bağımsız grup |
|---:|---:|---:|
| 7748 | 27 | **2** |
| 1819 | 11 | 7 |
| 7750 | 13 | **1** |

Açık kalan kısım yalnızca **sunum**: roadmap'teki ağaç görünümü
(Government / Parliament / Official Statistics / Independent Media)
mevcut veriden türetilebilir bir görselleştirmedir, yeni bir ölçüm
değil. `evidence/blindspot.py` kademe kırılımını zaten üretiyor.

Örnek:

```text
Event
├── Government
├── Parliament
├── Official Statistics
├── Financial Disclosure
└── Independent Media
```

### Exit Criteria

"12 kaynak doğruladı" ile "4 bağımsız grup doğruladı" birbirinden ayrılmalı.

---

## 2.3 Kaynak Sağlık Otomasyonu

**Öncelik: P1 — büyük ölçüde karşılandı**

Maddenin istediği alanların tamamı `source_quality.report()` çıktısında:
success rate, latency (`avg_ms`), freshness, consecutive failures,
parser errors. Devre durumu `pipeline_health.circuit_status_report()`'ta.

Maddenin asıl şartı — *"Alarm yanlış pozitif üretmemeli"* — bu oturumda
üç kez uygulandı: iddia çıkarımı alarmı (kalıcı kırmızıydı), DB testleri
(sessizce atlanıyordu), `git diff --check` (yüzlerce sahte uyarı). Bakım
listesi de aynı ilkeyle kuruldu: yapısal özellik alarm üretmez.

Her source için:

- success rate
- latency
- freshness
- consecutive failures
- circuit state
- parser errors

### Alarm

Yanlış pozitif üretmemeli.

Alarm sadece:

```text
worker_liveness
+
source_failure
+
freshness_breach
```

birlikte anlamlı olduğunda yükselmeli.

---

# PHASE 3 — Proactive Intelligence

## 3.1 Gösterge Anomali Tespiti

**Öncelik: P0 — TAMAMLANDI (19 Ağu 2026).** 3 yöntem (return_mad /
absolute_change / change_mad); istatistiksel VE maddi anlamlılık birlikte
aranır. Geri test iki gerçek kusur çıkardı ve düzeltildi. ⚠️ Beat görevi
canlıda EKSİK — konteyner yeniden inşası bekliyor.

Audit sonrası en yüksek ürün değerlerinden biri.

Amaç:

> PolitikDesk yalnızca "ne oldu?" demesin; "olağandışı bir şey oluyor" desin.

### Model

İlk sürümde ML kullanma.

```text
rolling_mean
rolling_std
median_absolute_deviation
historical_band
seasonality
```

### Event

```text
INDICATOR_ANOMALY
```

### Örnek

```text
TÜFE
actual: X
historical_band: A-B
deviation: +Y sigma
```

### Güvenlik

Anomali = iddia değildir.

Anomali:

```text
observation
```

olarak etiketlenmeli.

---

## 3.2 Expected Event Engine

**Öncelik: P0**

TÜİK takvimi + TCMB takvimi + diğer resmi takvimlerden:

```text
EXPECTED
PUBLISHED
LATE
MISSED
REVISED
```

durumları üret.

Bu katman, mevcut F2-18 açığını kapatır.

---

# PHASE 4 — Event Intelligence Graph

## 4.1 Event Relations Persistence

**Öncelik: P0 — TAMAMLANDI, SONRA YAYINDAN ÇEKİLDİ (ADR-010).**
Kalıcılaştırma çalışıyor (219× okuma hızlanması) ama üretilen kayıtların
içeriği denetlendiğinde yanlış siyasi isnat ürettiği görüldü: konu
eşleştirmesi yok, güven skoru sabit 0,85. Yayın kapısı KAPALI.

Şu an her request'te hesaplanan söylem değişikliğini kalıcılaştır.

### Tablo

```text
event_relations
----------------
id
source_event_id
target_event_id
relation_type
confidence
created_at
model_version
evidence_id
```

### Relation Types

- CONTRADICTS
- SUPPORTS
- REPEATS
- ESCALATES
- RETRACTS
- FOLLOWS
- PROMISE_FULFILLS
- PROMISE_BREAKS

### Kazanç

- request-time O(n²) maliyet azalır
- historical analysis mümkün olur
- graph queries mümkün olur
- auditability artar

---

## 4.2 Graph RAG

**Öncelik: P1**

LLM'e doğrudan serbest metin yığını vermek yerine:

```text
Question
 ↓
Entity Resolution
 ↓
Graph Traversal
 ↓
Evidence Retrieval
 ↓
Temporal Filtering
 ↓
Citation Set
 ↓
LLM Synthesis
```

### Kritik invariant

LLM hiçbir zaman kanıt üretmemeli.

Sadece mevcut evidence setini özetlemeli.

---

# PHASE 5 — Claim Intelligence

## 5.1 Claim Lifecycle

**Öncelik: P0 — KISMEN.** `evidence_status` beş durumu canlı taşıyor
(single_source 3.923 / partially_corroborated 314 / unverified 256 /
attribution_verified 27 / strongly_corroborated 2) ve `claim_signature`
kimlik gruplamasını yapıyor (4.522 iddia → 4.461 tekil imza).
AÇIK: `contradicted` durumu hiç üretilmiyor (ADR-008) ve
RETRACTED/UPDATED geçişleri yok.

Her iddia:

```text
EXTRACTED
→ NORMALIZED
→ VERIFIED
→ CONTRADICTED
→ UPDATED
→ RETRACTED
```

durumlarını desteklemeli.

### Claim Identity

Aynı iddianın farklı haberlerde tekrar edilmesini tek claim altında grupla.

---

## 5.2 Claim Evidence Matrix

Her claim için:

```text
Claim
├── Evidence +
├── Evidence -
├── Official data
├── Primary source
├── Independent source
├── Counterclaim
└── Last verified
```

### Kullanıcı çıktısı

```text
DESTEKLENİYOR
KISMEN DESTEKLENİYOR
ÇELİŞİLİYOR
DOĞRULANAMADI
```

Kesinlik dili kontrollü olmalı.

---

# PHASE 6 — Local Inference / Throughput

## 6.1 Önce Ölç

**Öncelik: P1 — TAMAMLANDI (19 Ağu 2026). Karar: BENİMSENMEDİ (ADR-009).**
Yerel doğruluk 0,686 / yanlış destek 0,16; uzak 0,909 / 0,0. Ölçülmüş
bir "hayır" da fazın geçerli çıktısıdır.

Audit'e göre bottleneck maliyet değil throughput: 651 olay birikimi ve yaklaşık 10 dakikada 5 olay işlenmesi raporlandı.

Önce:

```text
events/minute
claims/minute
tokens/event
CPU
RAM
GPU
queue_depth
```

ölç.

---

## 6.2 Ollama + Qwen Deneyi

**Öncelik: P1**

Mevcut `openai_compat` / hybrid mimari korunarak deneysel local inference katmanı oluştur.

### Karşılaştır

| Metric | Cloud | Local |
|---|---:|---:|
| latency | ölç | ölç |
| throughput | ölç | ölç |
| extraction accuracy | baseline | karşılaştır |
| Turkish accuracy | baseline | karşılaştır |
| cost | ölç | ölç |
| failure rate | ölç | ölç |

### Gate

Accuracy cloud baseline'ın altında belirlenen eşikten fazla düşerse production'a alınmaz.

---

# PHASE 7 — Security Hardening 2.0

## 7.1 CSP Nonce

**Öncelik: P0**

`unsafe-inline` kaldır.

Architecture:

```text
request
 ↓
generate nonce
 ↓
page()
 ↓
script nonce
 ↓
CSP header
```

### Exit Criteria

- `unsafe-inline` yok
- inline script'ler nonce ile çalışıyor
- CSP violation telemetry var
- Playwright smoke tests green

---

## 7.2 Trusted HTML Boundary

**Öncelik: P0**

Tüm:

- `innerHTML`
- template injection
- onclick
- data-* attributes

için merkezi güvenli API.

### Kural

Dış kaynaktan gelen string:

```text
raw HTML
```

olamaz.

---

# PHASE 8 — UI / Command Center

## 8.1 War Room 2.0

**Öncelik: P1**

War Room sadece haber listesi olmaktan çıkarılmalı.

Ana yüzey:

```text
┌─────────────────────────────────────┐
│ LIVE SIGNALS                        │
├──────────────┬──────────────────────┤
│ Indicators   │ Emerging Events      │
├──────────────┼──────────────────────┤
│ Claims       │ Source Health        │
├──────────────┼──────────────────────┤
│ Relations    │ Expected Events      │
└──────────────┴──────────────────────┘
```

---

## 8.2 Command Palette

D-02 sonrası sözleşme:

```json
{
  "actors": [
    {
      "name": "...",
      "entity_type": "..."
    }
  ]
}
```

tek kaynaktan tanımlanmalı.

### Arama

- aktör
- olay
- claim
- source
- indicator
- relation

---

## 8.3 Keyboard Contract

J / K / X gibi kısayollar gerçekten hangi sayfada aktifse UI'da sadece orada gösterilmeli.

Kısayol sözleşmesi test edilmeli.

---

# PHASE 9 — Publishing & Intelligence Products

## 9.1 11 Format → 11 UI

API 11 format üretiyorsa arayüz de bunların tamamını temsil etmeli.

Eksik kalanlar:

- X
- Bluesky
- Mastodon
- LinkedIn
- Telegram
- Substack
- audio

### Kural

API capability ≠ product capability.

İkisi contract test ile eşleşmeli.

---

## 9.2 Briefing Generator

Kullanıcı:

```text
Bugünün Türkiye ekonomi-politik özeti
```

dediğinde:

```text
1. Major events
2. Official indicators
3. Claims
4. Contradictions
5. Emerging signals
6. Expected events
7. Source confidence
```

üret.

Her bölüm evidence-backed olmalı.

---

# PHASE 10 — Mobile / PWA

**Öncelik: P2**

## PWA

- installable
- offline shell
- push notification
- background refresh
- responsive war room

## Mobile briefing

Sabah:

```text
07:30
↓
Top 5 overnight developments
↓
3 indicator changes
↓
2 emerging contradictions
↓
Today's expected releases
```

---

# PHASE 11 — Observability & SRE

## 11.1 SLI/SLO

### API

- p95 < 1.5s
- p99 tracked

### Pipeline

- event processing latency
- claim processing latency
- queue depth
- failure rate

### Sources

- freshness SLA
- successful fetch ratio

### AI

- extraction accuracy
- hallucination rate
- citation coverage

---

## 11.2 Evidence Integrity Metrics

En kritik yeni metrik seti:

```text
citation_coverage
official_value_coverage
unsupported_claim_rate
source_independence_score
evidence_freshness
claim_verification_rate
```

Bu metrikler ürünün gerçek kalite göstergesi olmalı.

---

# PHASE 12 — Evaluation System

## 12.1 Golden Dataset

**Öncelik: P0**

Gerçek Türkçe politik haberlerden anonimleştirilmiş / lisans açısından uygun bir evaluation corpus oluştur.

### Test alanları

- entity extraction
- claim extraction
- stance
- contradiction
- temporal reasoning
- source attribution
- official data grounding
- Turkish negation

---

## 12.2 LLM Regression Gate

Model değiştiğinde:

```text
new model
 ↓
golden dataset
 ↓
score
 ↓
compare baseline
 ↓
PASS / FAIL
```

Model değişikliği yalnızca benchmark geçtiğinde production'a alınmalı.

---

# PHASE 13 — Data Governance

## 13.1 Provenance Everywhere

Her kritik veri için:

```text
source_id
source_url
retrieved_at
published_at
content_hash
parser_version
model_version
```

---

## 13.2 Reproducibility

Bir kullanıcı:

> "Bu brifingi neden böyle ürettiniz?"

dediğinde sistem:

```text
briefing
 ↓
claims
 ↓
evidence
 ↓
source snapshots
 ↓
processing version
```

zincirini gösterebilmeli.

---

# PHASE 14 — Product Differentiation

## 14.1 Political Memory

PolitikDesk'in ana farklılaştırıcı ürünü:

> "Bir siyasi aktör geçmişte ne söyledi, sonra ne yaptı ve bugün bununla nasıl çelişiyor?"

### Timeline

```text
Promise
 ↓
Statement
 ↓
Policy
 ↓
Outcome
 ↓
Current position
```

---

## 14.2 Contradiction Radar

Her aktör için:

```text
Current Statement
vs
Historical Statement
vs
Official Data
vs
Observed Action
```

karşılaştırması.

Bu özellik ürünün "haber okuyucu" kategorisinden çıkıp "political intelligence" kategorisine geçmesini sağlar.

---

# PHASE 15 — Release Engineering

## Release Gate

Her release:

- [ ] pytest 100%
- [ ] 0 skip
- [ ] ruff
- [ ] mypy
- [ ] pip-audit
- [ ] architecture guard
- [ ] security regression
- [ ] DB migration test
- [ ] API contract tests
- [ ] UI Playwright tests
- [ ] performance smoke test
- [ ] evidence integrity tests
- [ ] source health checks

### Release Artifact

Her release için:

```text
GIT_SHA
BUILD_TIMESTAMP
SCHEMA_VERSION
MODEL_VERSION
SOURCE_CONFIG_VERSION
```

kaydedilmeli.

---

# Önceliklendirilmiş Sıra

## P0 — Mutlaka Önce

1. Baseline commit
2. Canlı test artıkları kararı
3. `.gov.tr` TLS / RSSHub ortam sorunları
4. TCMB EVDS
5. TÜİK yayın takvimi
6. Source quality + freshness
7. Expected Event Engine
8. Indicator anomaly detection
9. Event relations persistence
10. Claim lifecycle
11. CSP nonce
12. Golden dataset
13. LLM regression gate
14. Evidence integrity metrics

## P1 — Ürünü Üst Seviyeye Taşı

15. KAP
16. Source dependency graph
17. Graph RAG
18. Local inference benchmark
19. War Room 2.0
20. 11-format UI parity
21. Political Memory
22. Contradiction Radar
23. SRE/observability

## P2 — Ölçek ve Ürünleşme

24. Interactive relationship graph
25. PWA
26. Mobile briefing
27. Advanced anomaly models
28. Automated source onboarding
29. Advanced personalization
30. Enterprise-grade audit exports

---

# Önerilen Bağımlılık Grafiği

```text
                    ┌───────────────┐
                    │ Baseline Gate │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ↓             ↓             ↓
          EVDS/TÜİK      Source IQ     Security 2.0
              │             │             │
              └──────┬──────┴──────┬──────┘
                     ↓             ↓
              Expected Events   Official Data
                     │             │
                     └──────┬──────┘
                            ↓
                    Event Intelligence
                            │
                     ┌──────┴──────┐
                     ↓             ↓
               Claim Graph    Anomaly Engine
                     │             │
                     └──────┬──────┘
                            ↓
                       Graph RAG
                            │
                     ┌──────┴──────┐
                     ↓             ↓
                War Room      Briefing Engine
                     │             │
                     └──────┬──────┘
                            ↓
                    Political Memory
                            │
                            ↓
                   Contradiction Radar
```

---

# İlk 30 Gün — Uygulama Sırası

## Hafta 1 — Stabilizasyon

- Baseline commit
- canlı DB test artıkları kararı
- TLS problemi
- RSSHub problemi
- README / sources.yml drift
- release gate
- source health metrics

## Hafta 2 — Official Data

- TCMB EVDS adapter
- official metric schema
- TÜİK takvim adapter
- expected event model
- provenance
- integration tests

## Hafta 3 — Intelligence

- event_relations
- claim lifecycle
- indicator anomaly engine
- evidence integrity metrics
- golden dataset başlangıcı

## Hafta 4 — Security + Product

- CSP nonce
- trusted HTML boundary
- API/UI format parity
- War Room 2.0 foundation
- Playwright critical flows
- production release candidate

---

# 60 Günlük Hedef

60 gün sonunda:

```text
Official Data
      +
Expected Events
      +
Source Intelligence
      +
Claim Graph
      +
Anomaly Detection
      +
Evidence Integrity
      +
Security Hardening
      =
Proactive Political Intelligence
```

---

# 90 Günlük Nihai Hedef

PolitikDesk'in ana kullanıcı deneyimi şu soruyu cevaplamalı:

> "Türkiye'de şu anda ne oluyor, bunun kanıtı ne, hangi resmi veriler bunu destekliyor, kim ne söyledi, geçmişte ne söylemişti, hangi iddialar çelişiyor ve sırada ne olması bekleniyor?"

Bunu sağlayan sistem:

- sadece haber toplamaz,
- sadece LLM ile özet üretmez,
- sadece dashboard göstermez.

**Kaynakları bağımsızlık açısından değerlendirir, resmi verileri doğrudan bağlar, iddiaları kanıta bağlar, olayları zamansal ilişkilendirir, anomalileri tespit eder ve tüm sonuçların nasıl üretildiğini geriye dönük açıklayabilir.**

---

# Final Definition of Done

PolitikDesk "Ultimate Production Ready" ancak şu koşulların tamamı sağlandığında ilan edilmeli:

- [ ] 0 kritik güvenlik açığı
- [ ] 0 yüksek öncelikli doğruluk açığı
- [ ] 0 test skip
- [ ] 100% release gate
- [ ] official data provenance
- [ ] claim → evidence traceability
- [ ] event → relation traceability
- [ ] source independence scoring
- [ ] freshness monitoring
- [ ] anomaly detection
- [ ] expected-event engine
- [ ] CSP nonce
- [ ] UI/API contract parity
- [ ] golden evaluation set
- [ ] model regression gate
- [ ] p95 performance SLO
- [ ] source health SLO
- [ ] reproducible briefings
- [ ] Political Memory
- [ ] Contradiction Radar
- [ ] production rollback procedure
- [ ] disaster recovery verification
- [ ] documented operational runbook

**Nihai hedef:**

> PolitikDesk'i "AI destekli politik haber uygulaması" değil, **kanıta dayalı, kaynak-bağımsızlığı ölçülebilen, zaman içinde politik hafıza oluşturan ve proaktif sinyal üreten bir politik istihbarat altyapısı** haline getirmek.
