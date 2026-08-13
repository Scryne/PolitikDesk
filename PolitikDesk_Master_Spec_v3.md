# PolitikDesk
## Nihai Ürün Spesifikasyonu — v3.2 (Master Spec)
### AI Political Intelligence & Editorial Workspace

---

| | |
|---|---|
| **Doküman türü** | Nihai ürün spesifikasyonu — kararların *verildiği* belge |
| **Sürüm** | 3.2 |
| **Tarih** | 11 Ağustos 2026 (v3.0) · 12 Ağustos 2026 (v3.1) · **13 Ağustos 2026 (v3.2)** |
| **Önceki sürümler** | `PROJE FİKİR RAPORU.md` (v1, vizyon) → `PolitikDesk_Konsolide_Proje_Raporu.md` (eleştirel konsolidasyon) → `PolitikDesk_Proje_Raporu_v2.md` (daraltılmış kapsam) |
| **Eşlik eden belge** | `PolitikDesk_Yol_Haritasi_v1.md` (faz-faz uygulama planı) |
| **Statü** | 🔒 **DONDURULDU** — `spec-v3.2`. D1–D15 değiştirmek için yazılı gerekçe + sürüm artışı gerekir (Bölüm 17). |
| **Değişiklik gerekçesi** | `docs/karar-itirazlari.md` — D1–D15'in madde madde denetimi. v3.1'e taşıyan itirazlar: İtiraz-4 (D8), İtiraz-7 (D9), İtiraz-3 (D11), İtiraz-1 (D14). v3.2: B-55, B-62, B-66, B-72 (uygulama bulguları). |

---

## 0. Bu Sürüm Neyi Değiştiriyor?

v2, doğru teşhisi koydu ve şu cümleyle bitti: *"Kodlamaya başlamadan önce netleştirilmesi gereken 10 karar."* Ancak o 10 kararı **açıkta bıraktı** — teknoloji seçimini, MVP dikeyini, kanıt hesaplama kurallarını, veri şemasını bilinçli olarak spesifiye etmedi.

v3'ün tek işlevi budur: **o kararları vermek.** Bu belgede

- her açık karar bir **karar kaydına** (Bölüm 17) bağlanmış, gerekçesi ve alternatifi yazılmıştır;
- MVP dikeyi tek bir alana sabitlenmiştir (Bölüm 5);
- kanıt durumu (Evidence Status) **çalıştırılabilir kural setine** dönüştürülmüştür (Bölüm 8);
- veri modeli tablo/alan seviyesinde tanımlanmıştır (Bölüm 7);
- teknoloji yığını gerekçeli şekilde seçilmiştir (Bölüm 11);
- "yapmayacağız" listesi sözleşmeye dönüştürülmüştür (Bölüm 15).

v3 vizyondan hiçbir şey kesmez. Sadece **sıraya** koyar.

### v3.1 — kod yazılırken bulunan çelişkilerin düzeltilmesi

v3.0 dondurulmadan önce karar kaydı madde madde denetlendi
(`docs/karar-itirazlari.md`) ve şema ile kanıt motoru uygulanırken **dört somut
çelişki** ortaya çıktı. v3.1 yalnızca bunları düzeltir; hiçbir kapsam kararını
değiştirmez, hiçbir özellik eklemez veya çıkarmaz.

| # | Ne değişti | Neden | Nerede |
|---|---|---|---|
| 1 | Tahmin kısıtı **R8 → R0**: sıralamanın sonundan başına alındı ve kısa devre yapar hâle getirildi | Bir tahmin hakkında hem destekleyen hem çelişen Tier 1–2 kanıt bulunduğunda R1 kazanıyor ve tahmin 🔴 `contradicted` etiketleniyordu. Oysa R8 "tahmin HER ZAMAN ⚪" diyordu — ikisi aynı anda doğru olamaz. Makro ekonomide bu durum sık görülür ("piyasa faizin düşeceğini bekliyor"). | §8.3 |
| 2 | Salience **global (0–90) + kişisel (0–10)** olarak ayrıldı | Formülün altıncı bileşeni kullanıcıya özeldi; `events.salience_score` ise olay başına tek sütun. İki kullanıcının farklı konu öncelikleri tek sütunda saklanamaz — çok kullanıcıya geçişte (F4-01) ya sessiz yanlış sonuç ya şema değişikliği demekti. | §8.4, §7.3 |
| 3 | §11.5'in sıcaklık disiplini **effort** karşılığıyla yazıldı | Seçilen model sınıfı `temperature`/`top_p`/`top_k` kabul etmiyor (HTTP 400). Kuralın amacı korunuyor, mekanizması sağlayıcıya göre yazılıyor. | §11.5 |
| 4 | Maliyet hedefi **ölçek belirtir** hâle getirildi: birim ekonomi (100 kullanıcıda ≤ 8 $) + beta bütçe tavanı (toplam ≤ 150 $) | Sabit maliyet kullanıcı sayısından bağımsız (~71 $/ay); başabaş ~18 kullanıcı. Tek satırlık "≤ 8 $" koşulu kapalı betada yapısal olarak tutmaz ve kapıyı haksız yere bloke ederdi. | §13.3, G0 #8, G4 #7 |

Ayrıca kozmetik: "kanıtsız olayda üretim engeli" §14.1 kapsam listesine 15.
kalem olarak eklendi — kapsam savunması bu listeye bakarak yapıldığı için,
P1'in kod hâli listede görünmeliydi.

> **Not:** Bu dördü de soyut tercih beyanı değil, uygulama sırasında karşılaşılan
> somut çelişkilerdir. Faz 2'ye taşınsalardı kural motorunun ve şemanın yeniden
> yazılmasını gerektirirdi — Spec'in kendi deyimiyle *"yanlış kurulursa 6. ayda
> baştan yazılır"* durumu.

### v3.2 — Faz 2–3 canlı koşumlarının Spec'e işlenmesi

v3.1 gibi bu sürüm de yeni bir şey *tasarlamaz*; kodun canlı veride
karşılaştığı ve zaten çözdüğü dört durumu belgeye taşır. Üçü Spec'in
**tanımsız bıraktığı** boşluklardı ve harfiyen uygulandıklarında ürünü
bloke ediyorlardı.

| # | Ne değişti | Neden | Nerede |
|---|---|---|---|
| 1 | §11.4 varlık kısıtına **boş küme davranışı** yazıldı: bir taraf varlıksızsa kısıt *uygulanamaz*, reddetmez | Harfiyen `jaccard(∅,∅)=0` reddediyordu. İlk canlı koşumda 11 makalenin 6'sı varlıksızdı; 0,9997 benzerlikli iki makale yalnızca bu yüzden ayrı düştü. Boş küme çelişki kanıtı değil, kanıt yokluğudur. (B-55) | §11.4 |
| 2 | §11.4'e **gösterge kısıtı** eklendi: aynı kurumun aynı gün yayımladığı farklı göstergeler ayrı olaydır | `docs/FAZ2-DURUM.md` bulgu 3: kalan kümeleme precision açığının **tamamı** bu aileden geliyordu. TÜİK'in sanayi üretimi ile dış ticaret endeksi bültenleri tek olaya birleşiyordu. Ölçülen etki: pairwise precision 0,875 → **1,000**, false merge 0,026 → **0,000**, recall değişmedi. (B-62) | §11.4 |
| 3 | §15 madde 10'a **tahmin muafiyeti** yazıldı | R0 gereği her `prediction` iddiası `unverified`'dır; madde harfiyen uygulanınca **her olayda** üretim bloke oluyordu. Maddenin koruduğu şey suçlamadır, bir kişinin kendi tahminini aktarmak değil. (B-72) | §15 |
| 4 | §14.1 ve G4 **tek kullanıcılı kapsama** göre güncellendi | 12 Ağu 2026'da proje tek kullanıcılı kişisel araç olarak kararlaştırıldı; G4'ün 11 koşulundan 7'si gerçek beta kullanıcısı gerektiriyordu ve **hiçbir zaman ölçülemez** hale gelmişti. Ölçülemeyen koşul kapı değildir. (B-66) | §14.1, §13.2 |

> **Ortak ders.** Dördü de aynı biçimde ortaya çıktı: Spec bir *sınır durumu*
> tanımsız bıraktı, kod harfiyen uyguladı, canlı veri patladı. Tanımsız
> bırakılan sınır durumu, yazılı olmayan bir karar değildir — yalnızca
> **ertelenmiş** bir karardır ve bedelini uygulama öder.

---

## 1. Ürün Tanımı

**Tek cümle:**

> PolitikDesk, Türkiye gündemindeki haberleri tek tek değil **olay** bazında birleştiren, her iddiayı **kaynak ve kanıt zinciriyle** eşleyen, olayın **tarihsel bağlamını** çıkaran ve kullanıcıya **kaynağı gösterilmiş editoryal taslaklar** hazırlayan, insan onayı zorunlu bir siyasi istihbarat çalışma masasıdır.

**Ürün felsefesi (değişmez):**

> AI senin yerine konuşmaz. AI senin daha iyi konuşabilmen için gündemi senin adına takip eder, kanıtları senin için organize eder — kararı ve sözü sana bırakır.

**Kategori konumlandırması:**

| Ne değil | Ne |
|---|---|
| AI tweet botu / metin üretici | Kanıt organize eden araştırma masası |
| AI haber okuyucu / özetleyici | Olay grafiği ve kanıt zinciri kurucusu |
| Fact-checker / hakem | Evidence synthesizer — hüküm vermez, kanıtı gösterir |
| Political profiling aracı | Editoryal tercih (stil) asistanı |
| Sosyal medya otomasyon aracı | Editoryal iş akışı (workflow) aracı |

**Savunulabilir değer (moat):** LLM'in ürettiği metin değil — bu bir haftada taklit edilir. Moat, zamanla biriken **olay grafiği + kanıt zinciri + tarihsel bağlam arşividir.** Ürün 6. ayında değil, 18. ayında rakipsiz hale gelir. Bu, mimari kararların (Bölüm 7, 11) neden "veri modeli önce" mantığıyla kurulduğunu açıklar.

---

## 2. Sabit Ürün Prensipleri (Pazarlık Edilemez)

Bu altı prensip, her tasarım ve mühendislik kararının üzerinde bir filtre olarak çalışır. Bir özellik bunlardan biriyle çatışıyorsa, özellik değişir — prensip değişmez.

| # | Prensip | Mühendislik karşılığı |
|---|---|---|
| P1 | **Evidence before opinion** — önce kanıt, sonra yorum | Taslak üretimi, kanıt zinciri kurulmadan tetiklenemez (API seviyesinde engel) |
| P2 | **Events before headlines** — önce olay, sonra başlık | Birincil UI nesnesi `Event`, `Article` değil |
| P3 | **Context before reaction** — önce bağlam, sonra tepki | Olay sayfası, bağlam bloğu boş olsa bile bunu açıkça söyler |
| P4 | **Transparency before certainty** — kesinlik yerine şeffaflık | Tek sayısal "güven skoru" yasak; kategorik + gerekçeli durum zorunlu |
| P5 | **Human approval before publication** — yayın öncesi insan onayı | Sistemde otomatik yayın *kod yolu* dahi bulunmaz (Faz 5'e kadar) |
| P6 | **Editorial preference, not political profiling** | Kullanıcı modeli yalnızca stilistik/biçimsel öznitelik tutar; ideolojik sınıflandırma şeması veritabanında mevcut değildir |

**P7 (v3'te eklenen):** **Falsifiability before shipping** — ölçülemeyen özellik yayına girmez. Olay kümeleme, kanıt eşleme ve taslak kalitesi, elle etiketlenmiş test setine karşı sayısal hedefle çalışır (Bölüm 13).

---

## 3. Problem ve Rekabet Çerçevesi

### 3.1 Problem

Türkiye siyasi gündemi dakikalar içinde onlarca haber sitesinde, yüzlerce X hesabında ve resmî kanalda paralel belirir. Tek başına takip eden kullanıcı için sonuç: önemli gelişmelerin kaybolması, aynı haberin onlarca kez tekrarı, kaynakların birbirinden kopukluğu, doğrulanmamış iddianın gerçek gibi yayılması, olayın geçmişinin unutulması, haber–yorum karışması ve içerik hazırlığının saatler alması.

### 3.2 "Zaten ChatGPT/Perplexity var" itirazına cevap

Bu, ürünün cevaplaması gereken tek gerçek soru. Cevap üç maddede toplanır:

1. **Pull vs. push.** Genel amaçlı asistanlar *sorulduğunda* cevap verir. PolitikDesk sen sormadan izler, kümeler ve seni beklerken çalışır.
2. **Süreksiz vs. birikimli.** Bir sohbet oturumu kapandığında bilgi kaybolur. PolitikDesk her olayı kalıcı bir grafiğe yazar; 6 ay sonra "bu konu daha önce ne zaman gündeme geldi" sorusunun cevabı vardır.
3. **Metin vs. kanıt yapısı.** Genel asistan akıcı bir paragraf verir; PolitikDesk her cümlenin arkasındaki kaynağı, kaynak katmanını ve çelişkileri yapısal olarak gösterir.

Bu üç maddeyi karşılamayan hiçbir özellik ürünün farklılaşmasına katkı sağlamaz.

### 3.3 Emsal haritası (Faz 0'da isim isim doğrulanacak)

| Emsal kategorisi | Örnek | PolitikDesk'in ayrımı |
|---|---|---|
| Perspektif karşılaştırması | Ground News | Olay grafiği + iddia/kanıt ayrıştırması + editoryal üretim katmanı |
| Haber istihbaratı / B2B | medya izleme platformları | Bireysel içerik üreticisi için fiyatlanmış, editoryal aksiyona bağlı |
| İçerik kuyruğu | Buffer, Hootsuite | Kuyruk bir çıktı; ürünün merkezi kanıt katmanı |
| AI yazım araçları | genel amaçlı üreticiler | Kaynağa bağlı üretim (source-grounded), üretim öncesi kanıt zorunluluğu |
| RSS/okuyucu | Feedly ve türevleri | Makale değil olay; özet değil kanıt zinciri |

---

## 4. Hedef Kullanıcı (ICP)

**Birincil ICP — MVP:**

> Türkiye gündemini düzenli takip eden, X'te siyasi/ekonomik/toplumsal içerik paylaşan, 5.000–100.000 takipçili, tek başına çalışan bağımsız içerik üreticisi. Gündem takibine günde 1–2 saat harcıyor, bu süreyi azaltmak ve paylaşımlarını kaynaklandırmak istiyor.

**Kullanıcının "işe alma" gerekçesi (job to be done):**
*"Gündemi kaçırmadan takip etmek istiyorum, ama paylaştığım şeyin arkasında durabileceğimden de emin olmak istiyorum."*

**İkincil ICP — Faz 5:** ekonomi/finans içerik üreticileri, sektörel bülten yazarları.
**Üçüncül ICP — Faz 6 (B2B):** küçük medya ekipleri, araştırma masaları, kurumsal iletişim/analiz birimleri. B2B ürünü "Team Workspace" (paylaşılan olay havuzu + onay akışı) olur.

**Kesin olarak hedeflenmeyecek segment:** siyasi kampanya ekipleri, seçmen hedefleme yapan yapılar, koordineli etki operasyonları. Bu, bir pazar tercihi değil, Bölüm 15'teki sözleşmenin parçasıdır.

---

## 5. MVP Dikeyi — KARAR: Makro Ekonomi

v2 "dar bir kategori seç (örn. ekonomi *veya* TBMM)" dedi ama seçmedi. v3 seçiyor: **MVP dikeyi Makro Ekonomi / Para Politikası.**

**Gerekçe (dört kriter üzerinden):**

| Kriter | Makro Ekonomi | TBMM/Yasama | Genel Siyaset |
|---|---|---|---|
| Tier-1 birincil kaynak yoğunluğu | **Çok yüksek** (TCMB, TÜİK, Hazine, Resmî Gazete, BDDK, TÜİK takvimi) | Yüksek (tutanak, kanun teklifi metni) | Düşük |
| İddiaların doğrulanabilirliği | **Sayısal ve kesin** (%X enflasyon, Y puan faiz) | Metinsel, orta | Yoruma açık |
| Hukuki risk profili (dezenformasyon/hakaret) | **En düşük** | Orta | En yüksek |
| Planlı olay akışı ("beklenen gelişme" özelliği için) | **Mükemmel** (TÜİK veri takvimi, PPK toplantı takvimi, enflasyon raporu tarihleri) | İyi (komisyon takvimi) | Yok |
| Kullanıcının içerik üretme sıklığı | Yüksek | Orta | Çok yüksek |

**Karar mantığı:** Makro ekonomi, sistemin **en zor iki bileşenini** (olay kümeleme doğruluğu, kanıt eşleme) **en düşük hukuki riskle** ve **en yüksek doğrulanabilirlikle** test etmeye izin verir. Enflasyon verisinin açıklandığı bir olayda "doğru kümelendi mi", "kanıt doğru eşlendi mi" soruları nesnel olarak yanıtlanabilir; bir siyasi tartışmada yanıtlanamaz. Motor burada kalibre edilir, sonra daha zor dikeylere taşınır.

**MVP dikey kapsamı (V1 konu sınırı):**
enflasyon (TÜFE/ÜFE) · politika faizi ve PPK kararları · kur ve rezervler · bütçe/hazine nakit dengesi · işsizlik ve istihdam · büyüme (GSYH) · asgari ücret ve memur/emekli zamları · vergi/harç düzenlemeleri · kamu borçlanması · derecelendirme kuruluşu kararları.

**Faz 5 genişleme sırası:** (1) Yasama/TBMM, (2) Yargı/hukuk, (3) Dış politika, (4) Genel siyaset. Genel siyaset **kasıtlı olarak en sona** bırakılmıştır — motor ve hukuki çerçeve olgunlaşmadan en riskli dikeye girilmez.

---

## 6. Core Loop ve Özellik Filtresi

```
┌──────────────────────────────────────────────────────────────────┐
│  1. DISCOVER      →  Sinyali yakala        (ingestion)           │
│  2. UNDERSTAND    →  Haberi olaya çevir    (event clustering)    │
│  3. VERIFY        →  Kanıtı karşılaştır    (evidence engine)     │
│  4. CONTEXTUALIZE →  Geçmişe bağla         (event graph / memory)│
│  5. DRAFT         →  Editoryal seçenek sun (grounded generation) │
│  6. REVIEW        →  İnsan onayı           (pre-publish check)   │
└──────────────────────────────────────────────────────────────────┘
```

v2'nin 5 adımlı döngüsüne v3'te **6. adım (REVIEW)** açıkça eklenmiştir. Gerekçe: P5 bir prensip olarak kalırsa unutulur; döngünün adımı olursa kod olur.

**Özellik filtresi (her yeni fikir için zorunlu test):**

1. Core Loop'un hangi adımına hizmet ediyor? → Cevap yoksa **reddedilir.**
2. Prensiplerden (P1–P7) hiçbiriyle çatışıyor mu? → Çatışıyorsa **reddedilir.**
3. MVP dikeyi (makro ekonomi) içinde anlamlı mı? → Değilse **Faz 5+.**
4. Ölçülebilir mi? → Değilse **ölçüm tanımlanana kadar bekletilir.**

**Filtrenin örnek uygulaması:**

| Fikir | Adım | Karar |
|---|---|---|
| Kaynak karşılaştırma tablosu | VERIFY | MVP ✅ |
| Olay zaman çizelgesi | UNDERSTAND + CONTEXTUALIZE | MVP ✅ |
| Pre-publish check | REVIEW | MVP ✅ |
| Gündem haritası (görsel) | — (hiçbiri) | Faz 6 ❌ |
| Kişi ilişkileri grafiği | CONTEXTUALIZE (zayıf) | Faz 6 ❌ |
| 500 tweet'ten stil öğrenme | DRAFT (marjinal) | Faz 5 ❌ |
| Çoklu platform uyarlaması | — (dağıtım) | Faz 6 ❌ |
| "Karşı görüş" kontrolü | REVIEW | Faz 5 ⚠️ (MVP'de basit sürüm) |

---

## 7. Bilgi Modeli — Olay Grafiği (Event Graph)

Ürünün omurgası. Bu model doğru kurulursa geri kalan her şey üzerine inşa edilir; yanlış kurulursa 6. ayda baştan yazılır.

### 7.1 Kavramsal model

```
Source ──publishes──> Article ──belongs_to──> Event
                         │                      │
                         │                   mentions
                         ▼                      ▼
                      Claim  ──supported_by──> Evidence ──from──> Source
                         │                                          
                    about │                                    Entity
                         ▼                                   (Person/Org)
                      Entity                                       
                         
Event ──relates_to──> Event        (tarihsel bağlam / thread)
Event ──expects──> ScheduledEvent  (beklenen gelişme)
Event ──generates──> Draft ──cites──> Claim
```

### 7.2 Varlık tanımları

| Varlık | Tanım | Kritik alanlar |
|---|---|---|
| **Source** | Bir yayın kaynağı (kurum, ajans, site, hesap) | `tier` (1–4), `access_method`, `tos_status`, `independence_group` |
| **Article** | Tek bir yayın birimi (haber, tebliğ, gönderi) | `canonical_url`, `published_at`, `first_seen_at`, `content_hash`, `simhash`, `embedding` |
| **Event** | Gerçek dünyada olan tek bir gelişme; N adet Article'ı birleştirir | `status` (developing/settled/contradicted), `salience_score`, `first_reported_at`, `last_update_at`, `centroid_embedding` |
| **Claim** | Bir olay hakkındaki tek, atomik, doğrulanabilir ifade | `claim_text`, `claim_type` (fact/attribution/number/prediction), `evidence_status`, `status_reason` |
| **Evidence** | Bir Claim'i destekleyen/çürüten kaynak referansı | `stance` (supports/contradicts/partial), `quote_span`, `article_id` |
| **Entity** | Kişi, kurum, kuruluş | `canonical_name`, `aliases[]`, `entity_type`, `role` |
| **ScheduledEvent** | Beklenen gelişme (veri açıklaması, toplantı, karar) | `expected_at`, `confidence`, `linked_event_id` |
| **Draft** | Kullanıcı için üretilen editoryal taslak | `angle`, `body`, `cited_claim_ids[]`, `check_result`, `user_action` |
| **EditorialProfile** | Kullanıcının stilistik tercihleri | yalnızca biçimsel alanlar — Bölüm 10 |

### 7.3 Şema taslağı (PostgreSQL + pgvector)

```sql
-- Kaynaklar
CREATE TABLE sources (
  id                  BIGSERIAL PRIMARY KEY,
  name                TEXT NOT NULL,
  slug                TEXT UNIQUE NOT NULL,
  tier                SMALLINT NOT NULL CHECK (tier BETWEEN 1 AND 4),
  kind                TEXT NOT NULL,          -- official | wire | media | social
  independence_group  TEXT,                   -- aynı yayın grubu/ajans zinciri aynı grup
  access_method       TEXT NOT NULL,          -- rss | api | official_feed | manual
  tos_status          TEXT NOT NULL,          -- allowed | restricted | forbidden | pending_review
  tos_reviewed_at     DATE,
  base_url            TEXT,
  is_active           BOOLEAN NOT NULL DEFAULT TRUE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Makaleler (tam metin SAKLANMAZ; bkz. Bölüm 9.3)
CREATE TABLE articles (
  id              BIGSERIAL PRIMARY KEY,
  source_id       BIGINT NOT NULL REFERENCES sources(id),
  canonical_url   TEXT UNIQUE NOT NULL,
  title           TEXT NOT NULL,
  excerpt         TEXT,                       -- kısa alıntı, azami 300 karakter
  lead_paragraph  TEXT,                       -- işleme amaçlı, TTL ile silinir
  published_at    TIMESTAMPTZ,
  first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  content_hash    TEXT NOT NULL,              -- tam-tekrar tespiti
  simhash         BIGINT,                     -- yakın-tekrar / ajans kopyası tespiti
  embedding       VECTOR(1024),
  lang            TEXT DEFAULT 'tr',
  event_id        BIGINT REFERENCES events(id),
  cluster_score   REAL,                       -- kümeye atanma benzerliği
  raw_purge_at    TIMESTAMPTZ,                -- ham metin silme zamanı
  CONSTRAINT excerpt_len CHECK (char_length(excerpt) <= 300)
);
CREATE INDEX ON articles USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON articles (published_at DESC);
CREATE INDEX ON articles (event_id);

-- Olaylar
CREATE TABLE events (
  id                  BIGSERIAL PRIMARY KEY,
  title               TEXT NOT NULL,          -- LLM üretir, insan düzeltebilir
  summary             TEXT,
  vertical            TEXT NOT NULL DEFAULT 'macro_economy',
  topic_tags          TEXT[] DEFAULT '{}',
  status              TEXT NOT NULL DEFAULT 'developing',
  salience_score      SMALLINT,               -- GLOBAL salience 0-90 (Bölüm 8.4/A)
                                              -- kişisel bileşen BURAYA YAZILMAZ
  salience_breakdown  JSONB,                  -- şeffaflık: global bileşenler + cezalar
  centroid_embedding  VECTOR(1024),
  first_reported_at   TIMESTAMPTZ NOT NULL,
  last_update_at      TIMESTAMPTZ NOT NULL,
  article_count       INT NOT NULL DEFAULT 0,
  independent_count   INT NOT NULL DEFAULT 0, -- Bölüm 8.2
  has_primary_source  BOOLEAN NOT NULL DEFAULT FALSE,
  merged_into_id      BIGINT REFERENCES events(id), -- birleştirme geçmişi korunur
  review_flag         TEXT,                   -- needs_review | verified | rejected
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON events USING hnsw (centroid_embedding vector_cosine_ops);
CREATE INDEX ON events (last_update_at DESC) WHERE merged_into_id IS NULL;

-- İddialar
CREATE TABLE claims (
  id               BIGSERIAL PRIMARY KEY,
  event_id         BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  claim_text       TEXT NOT NULL,
  claim_type       TEXT NOT NULL,             -- fact | number | attribution | prediction
  normalized_value JSONB,                     -- sayısal iddialar için: {metric, value, unit, period}
  evidence_status  TEXT NOT NULL,             -- Bölüm 8.1
  status_reason    JSONB NOT NULL,            -- hangi kural, hangi girdilerle tetiklendi
  computed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Kanıtlar
CREATE TABLE evidence (
  id           BIGSERIAL PRIMARY KEY,
  claim_id     BIGINT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
  article_id   BIGINT NOT NULL REFERENCES articles(id),
  stance       TEXT NOT NULL,                 -- supports | contradicts | partial
  quote_span   TEXT,                          -- azami 200 karakter alıntı
  extracted_by TEXT NOT NULL,                 -- model adı + sürüm (denetlenebilirlik)
  confidence   REAL,
  UNIQUE (claim_id, article_id)
);

-- Varlıklar ve bağlantıları
CREATE TABLE entities (
  id             BIGSERIAL PRIMARY KEY,
  canonical_name TEXT NOT NULL,
  entity_type    TEXT NOT NULL,               -- person | institution | company | country
  aliases        TEXT[] DEFAULT '{}',
  UNIQUE (canonical_name, entity_type)
);
CREATE TABLE event_entities (
  event_id  BIGINT REFERENCES events(id) ON DELETE CASCADE,
  entity_id BIGINT REFERENCES entities(id),
  role      TEXT,                             -- actor | subject | mentioned
  PRIMARY KEY (event_id, entity_id)
);

-- Tarihsel bağlam (olay-olay ilişkisi)
CREATE TABLE event_relations (
  from_event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
  to_event_id   BIGINT REFERENCES events(id) ON DELETE CASCADE,
  relation      TEXT NOT NULL,                -- precedes | updates | contradicts | same_thread
  similarity    REAL,
  created_by    TEXT NOT NULL,                -- system | user
  PRIMARY KEY (from_event_id, to_event_id, relation)
);

-- Beklenen gelişmeler
CREATE TABLE scheduled_events (
  id              BIGSERIAL PRIMARY KEY,
  title           TEXT NOT NULL,
  expected_at     TIMESTAMPTZ NOT NULL,
  source_id       BIGINT REFERENCES sources(id),
  vertical        TEXT NOT NULL,
  linked_event_id BIGINT REFERENCES events(id),
  status          TEXT NOT NULL DEFAULT 'pending'  -- pending | occurred | cancelled
);

-- Taslaklar
CREATE TABLE drafts (
  id              BIGSERIAL PRIMARY KEY,
  user_id         BIGINT NOT NULL,
  event_id        BIGINT NOT NULL REFERENCES events(id),
  angle           TEXT NOT NULL,              -- inform | analyze | critique | contextualize | question
  body            TEXT NOT NULL,
  cited_claim_ids BIGINT[] NOT NULL DEFAULT '{}',
  check_result    JSONB,                      -- pre-publish check çıktısı
  user_action     TEXT,                       -- accepted | edited | regenerated | rejected
  final_body      TEXT,                       -- kullanıcının düzenlediği hâli
  edit_distance   REAL,                       -- metrik (Bölüm 13)
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Editoryal profil — YALNIZCA biçimsel alanlar (Bölüm 10)
CREATE TABLE editorial_profiles (
  user_id            BIGINT PRIMARY KEY,
  tone               TEXT[],                  -- direct | analytical | ironic | formal
  sentence_length    TEXT,                    -- short | medium | long
  emoji_usage        TEXT,                    -- none | minimal | frequent
  hashtag_usage      TEXT,
  citation_habit     TEXT,                    -- always_link | sometimes | never
  formality          SMALLINT,                -- 1-5
  avoid_list         TEXT[],                  -- kullanıcının kendi yazdığı kaçınma kuralları
  topic_priorities   TEXT[],                  -- ekonomi | bütçe | faiz ...
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- NOT: Bu tabloda ideolojik/siyasi sınıflandırma alanı BİLİNÇLİ OLARAK YOKTUR (P6, KVKK m.6).

-- Denetim izi
CREATE TABLE audit_log (
  id         BIGSERIAL PRIMARY KEY,
  actor      TEXT NOT NULL,                   -- system:<job> | user:<id>
  action     TEXT NOT NULL,
  target     TEXT NOT NULL,
  payload    JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 7.4 Model kararları ve gerekçeleri

| Karar | Gerekçe |
|---|---|
| Tam metin saklanmaz; `excerpt` ≤300 karakter + `lead_paragraph` TTL'li | Telif riski (Bölüm 12.4). İşleme için gereken metin geçicidir; kalıcı arşiv meta veri + link. |
| `simhash` ayrı tutulur | Ajans kopyası tespiti embedding'den daha güvenilir şekilde metinsel benzerlikle yapılır (Bölüm 8.2). |
| `salience_breakdown` JSONB | Skor şeffaf olmalı; kullanıcı "neden 84?" sorusunun cevabını görmeli (P4). |
| `salience_score` yalnızca **global** kısmı (0–90) tutar | Olay başına tek sütun; kullanıcıya özel bileşen burada saklanamaz (Bölüm 8.4). Kişisel ayarlama sorgu anında eklenir — çok kullanıcıya geçiş şema değişikliği gerektirmez. |
| `merged_into_id` ile birleştirme geçmişi korunur | Yanlış birleştirme geri alınabilir olmalı; kümeleme hatası veri kaybına dönüşmemeli. |
| `evidence.extracted_by` model sürümü tutar | Model değiştiğinde geriye dönük kalite karşılaştırması ve denetim mümkün olsun. |
| `status_reason` JSONB, serbest metin değil | Kanıt durumu deterministik; hangi kuralın hangi girdiyle tetiklendiği makine-okunur olmalı. |

---

## 8. Kanıt Motoru (Evidence Engine) — Çalıştırılabilir Kurallar

v2 "deterministik olmalı" dedi. v3 kuralları yazıyor. **Bu bölüm ürünün en kritik teknik sözleşmesidir.**

### 8.1 Evidence Status — kategorik durumlar

Durum **iddia (Claim) seviyesinde** hesaplanır, olay seviyesinde değil. Bir olayda aynı anda 🟢 doğrulanmış ve ⚪ doğrulanmamış iddialar bulunabilir; olay kartında en zayıf iddianın durumu uyarı olarak gösterilir.

| Etiket | Kod | Anlamı |
|---|---|---|
| 🟢 | `strongly_corroborated` | Birincil kaynak var **ve** ≥2 bağımsız teyit |
| 🟡 | `partially_corroborated` | Bazı unsurlar doğrulanmış, bazıları değil |
| 🟠 | `single_source` | Tek bağımsız kaynak |
| 🔴 | `contradicted` | Güvenilir kaynaklar arasında çelişki |
| ⚪ | `unverified` | Yeterli kanıt yok |

**Yasak:** Bu etiket hiçbir koşulda bir LLM çağrısının çıktısı olamaz. LLM'in tek görevi, **hesaplanmış** etiketi kullanıcıya açıklayan metni yazmaktır.

### 8.2 Bağımsız kanıt sayımı (independent evidence count)

"10 kaynak yazdı" ≠ "10 bağımsız teyit". Sayım algoritması:

```
FONKSİYON bagimsiz_sayim(claim):
  destekleyen = [e for e in claim.evidence if e.stance == 'supports']
  gruplar = {}

  HER e IÇIN destekleyen:
    anahtar = birlestirme_anahtari(e)
    gruplar[anahtar] = gruplar.get(anahtar, []) + [e]

  DÖN len(gruplar)

FONKSİYON birlestirme_anahtari(e):
  # 1) Aynı yayın grubu / ajans zinciri → tek grup
  EĞER e.source.independence_group VARSA:
      DÖN "grp:" + e.source.independence_group
  # 2) Ajans kopyası: metin yakın-tekrar ise → ajans grubuna yaz
  EĞER simhash_hamming(e.article, herhangi_ajans_makalesi) <= 6:
      DÖN "wire:" + ajans_makalesi.source.slug
  # 3) Gövde benzerliği çok yüksek (kopyala-yapıştır)
  EĞER cosine(e.article.embedding, diger.embedding) >= 0.95
       VE ortak_ngram_orani >= 0.60:
      DÖN "dup:" + min(id'ler)
  DÖN "src:" + e.source.slug
```

Kullanıcı arayüzünde her zaman **kırılımlı** gösterilir: `Resmî: 1 · Ajans: 1 · Bağımsız medya: 3 · Sosyal: 4` — tek bir toplam sayı gösterilmez.

### 8.3 Durum hesaplama kuralları (sıralı, ilk eşleşen kazanır)

Kurallar üç bloktan oluşur ve **bu sırayla** uygulanır:

1. **Tip kısıtı (R0)** — iddianın tipinden gelir, kanıta bakmaz. Eşleşirse
   kısa devre yapar; sonraki hiçbir kural çalışmaz.
2. **Kanıt kuralları (R1–R6)** — sıralı, ilk eşleşen kazanır.
3. **Tavan kısıtı (R7)** — kanıt kurallarının sonucuna uygulanır, sonucu
   yukarıdan sınırlar.

```
KURAL R0 → tip kısıtı: tahmin (⚪)          [BLOK 1 — kanıttan önce]
  EĞER claim.claim_type = 'prediction'
  → durum HER ZAMAN unverified (⚪) + "Tahmin" etiketi
  → KISA DEVRE: R1–R7 değerlendirilmez
  # Gerekçe: gelecek doğrulanamaz. Bu, haber/yorum ayrımının kod hâli.
  # Neden en başta: bir tahmin hakkında hem destekleyen hem çelişen kanıt
  #   bulunması olağandır ("piyasa faizin düşeceğini bekliyor" / "yükseleceğini").
  #   R1 önce çalışsaydı bu tahmin 🔴 contradicted olurdu — oysa çelişkili
  #   göstermek de bir doğrulama iddiasıdır: iki tahminden birinin yanlış
  #   olduğunu ima eder. Tip kısıtı, kanıt kuralının önüne geçmelidir.

KURAL R1 → contradicted (🔴)                [BLOK 2 — kanıt kuralları]
  EĞER ∃ e1, e2 ∈ evidence:
        e1.stance = 'supports' VE e2.stance = 'contradicts'
        VE e1.source.tier <= 3 VE e2.source.tier <= 3
        VE (e1.source.tier <= 2 VEYA e2.source.tier <= 2)
  → contradicted
  # Gerekçe: çelişki her şeyin önünde gelir; en az bir taraf Tier 1-2 olmalı ki
  #          sosyal medya gürültüsü çelişki üretmesin.

KURAL R2 → strongly_corroborated (🟢)
  EĞER has_primary_source (Tier 1 kaynakta supports kanıtı var)
       VE bagimsiz_sayim >= 3
       VE HİÇBİR contradicts kanıtı yok (Tier <= 3)
  → strongly_corroborated

KURAL R3 → strongly_corroborated (🟢) — resmî sayısal veri istisnası
  EĞER claim.claim_type = 'number'
       VE kaynak Tier 1 kurumun kendi yayını (TÜİK/TCMB/Hazine/Resmî Gazete)
       VE normalized_value kurumun yayın formatıyla doğrulandı
  → strongly_corroborated
  # Gerekçe: TÜİK enflasyon verisini TÜİK açıkladıysa 3 teyit beklemek anlamsız.

KURAL R4 → partially_corroborated (🟡)
  EĞER bagimsiz_sayim >= 2
       VE (has_primary_source = FALSE VEYA bazı unsurlar yalnız tek kaynakta)
  → partially_corroborated

KURAL R5 → single_source (🟠)
  EĞER bagimsiz_sayim = 1
  → single_source

KURAL R6 → unverified (⚪)
  DİĞER TÜM DURUMLAR
  # Özellikle: yalnızca Tier 4 (sosyal) kaynak varsa, sayı kaç olursa olsun
  #            R2/R3 tetiklenemez.

KURAL R7 → tavan kısıtı                     [BLOK 3 — sonuca uygulanır]
  EĞER tüm kanıtlar Tier 4 (sosyal) ise
  → azami durum single_source (🟠); asla 🟢/🟡 olamaz.
```

**Toplam 8 kural: R0–R7.** Numaralandırma değişmez; R0'ın eklenmesi
kural sayısını artırmaz (eski R8'in yerini alır).

Her hesaplama `claims.status_reason` alanına şu formatta yazılır:

```json
{
  "rule": "R2",
  "independent_count": 4,
  "breakdown": {"official": 1, "wire": 1, "media": 2, "social": 3},
  "has_primary_source": true,
  "contradictions": 0,
  "computed_at": "2026-08-11T14:22:03Z",
  "engine_version": "evidence-engine@1.0.0"
}
```

R0 tetiklendiğinde kanıt alanları **hesaplanmadıkları için** yazılmaz;
kayıt kısa devrenin kendisini belgeler:

```json
{
  "rule": "R0",
  "short_circuit": "claim_type=prediction",
  "evaluated_evidence_rules": false,
  "computed_at": "2026-08-11T14:22:03Z",
  "engine_version": "evidence-engine@1.0.0"
}
```

**İkinci savunma hattı:** R0 yalnızca kural motorunda yaşamaz. `claims`
tablosunda `claims_prediction_always_unverified` CHECK kısıtı vardır; motor
bir tahmini `unverified` dışında bir durumla yazmaya kalkarsa INSERT
veritabanı seviyesinde reddedilir. Kural motorundaki bir hata, sessiz yanlış
etiket olarak değil, gürültülü bir hata olarak ortaya çıkar (P4).

### 8.4 Gündem skoru (Salience) — deterministik

v1'deki "94/100" fikri korunur ama **şeffaf ve kural tabanlı** hale getirilir. Skor bir doğruluk göstergesi **değildir** — yalnızca sıralama içindir ve UI'da bu açıkça belirtilir.

Skor **iki bileşene ayrılır**: olayın kendisinden gelen global kısım ve
kullanıcının konu önceliklerinden gelen kişisel kısım. Ayrım kozmetik
değildir — global kısım olay başına *tek* bir değerdir ve saklanır; kişisel
kısım kullanıcı başına *farklı* olduğu için saklanamaz, sorgu anında
hesaplanır.

**A) Global salience (0–90) — saklanır, kullanıcıdan bağımsız**

```
global_salience = CLAMP(ROUND(
    25 * norm(bagimsiz_kaynak_sayisi, 0, 8)
  + 20 * (has_primary_source ? 1 : 0)
  + 20 * norm(yayilma_hizi, 0, 10)        -- ilk 60 dk içindeki makale sayısı
  + 15 * tier_agirligi                     -- en yüksek tier kaynak: T1=1.0, T2=0.8, T3=0.5, T4=0.2
  + 10 * varlik_onemi                      -- TCMB/Hazine/Bakan gibi anahtar varlık: 1.0
  - CEZA
), 0, 90)

CEZA:
  15 EĞER evidence_status ∈ {unverified, single_source} ve olay 6 saatten eski
  10 EĞER tekrar/duplike olay şüphesi (benzer olay son 48 saatte)
```

`events.salience_score` alanına **yalnızca bu değer** yazılır. Girdilerinin
tamamı olayın kendi özellikleridir; hiçbir kullanıcıya ait veri içermez.

**B) Kişisel ayarlama (0–10) — saklanmaz, sorgu anında hesaplanır**

```
kisisel_ayarlama(olay, kullanici) =
  ROUND(10 * ortusme(olay.topic_tags, kullanici.topic_priorities))
```

**C) Gösterilen skor**

```
gosterilen_skor = global_salience + kisisel_ayarlama(olay, kullanici)   -- 0-100
```

**Neden ayrıldı.** `events.salience_score` olay başına tek bir sütundur. Konu
öncelikleri farklı iki kullanıcı aynı olay için farklı skor gerektirir; tek
sütunda saklanamaz. Bileşen formülde bırakılıp şemada tek sütun tutulsaydı,
çok kullanıcıya geçildiğinde (F4-01) ya ilk kullanıcının tercihi sessizce
herkese uygulanırdı ya da şema değişikliği gerekirdi.

**İki ek fayda:**

- Global skor kullanıcıdan bağımsız olduğu için **önbelleklenebilir** ve
  yalnızca olay güncellendiğinde yeniden hesaplanır (F4-08'in feed
  p95 < 800 ms hedefi).
- Şeffaflık artar: kullanıcı "senin konu önceliklerinle eşleştiği için +8"
  satırını ayrı görür (P4).

`salience_breakdown` alanına global bileşenler ve cezalar yazılır; kişisel
bileşen **oraya yazılmaz** (saklanan alan kullanıcıdan bağımsız kalmalıdır),
yanıtta ayrı bir alan olarak döner. UI'da kullanıcı skora tıklayınca
kırılımı iki blok halinde görür (P4).

### 8.5 Framing farkı — "bias" değil

Aynı olayın farklı başlıklarla sunulması gösterilir, ancak **kaynağa siyasi etiket verilmez.** Sistem çıktısı yalnızca gözlemdir:

> *"Bu olay 6 kaynakta farklı çerçevelerle sunuluyor."* + başlıkların yan yana listesi + nötr sözcük farkı vurgusu.

Yasak çıktılar: "bu kaynak taraflı", "hükümet yanlısı", "muhalif medya", herhangi bir siyasi konum etiketi. Kullanıcı kendi özel notunu/etiketini ekleyebilir; bu veri kullanıcıya özeldir ve model eğitimine girmez.

---

## 9. Veri Stratejisi

### 9.1 Kaynak katmanlaması

| Tier | Kind | İçerik | MVP'deki rol |
|---|---|---|---|
| **Tier 1** | `official` | TCMB, TÜİK, Hazine ve Maliye Bakanlığı, Resmî Gazete, BDDK, TBMM tutanakları, mahkeme kararları | **Omurga.** Kanıt zincirinin çıpası. |
| **Tier 2** | `wire` | AA, Reuters, DHA, Bloomberg | Hızlı sinyal + ajans kopyası referansı |
| **Tier 3** | `media` | Farklı editoryal çizgide haber kuruluşları | Framing karşılaştırması |
| **Tier 4** | `social` | Ekonomi gazetecileri, akademisyenler, uzmanlar | **MVP'de kısıtlı** (Bölüm 9.4) |

Tier 1 kanıtı varsa UI'da her zaman öne çıkar: **"Birincil kaynak mevcut"** rozeti.

### 9.2 MVP kaynak listesi (8 kaynak — kesin sınır)

| # | Kaynak | Tier | Erişim | Not |
|---|---|---|---|---|
| 1 | TCMB (duyuru/PPK/bülten) | 1 | Resmî akış/RSS | Faiz, rezerv, enflasyon raporu |
| 2 | TÜİK (haber bülteni + veri takvimi) | 1 | Resmî akış | TÜFE/ÜFE/işsizlik/GSYH + `scheduled_events` kaynağı |
| 3 | Hazine ve Maliye Bakanlığı | 1 | Resmî akış | Bütçe, borçlanma, nakit dengesi |
| 4 | Resmî Gazete | 1 | Resmî akış | Vergi/harç, yönetmelik |
| 5 | Anadolu Ajansı — Ekonomi | 2 | RSS | Ajans referansı |
| 6 | Reuters — Türkiye/Ekonomi | 2 | RSS/lisans | Uluslararası çapraz teyit |
| 7 | Bağımsız ekonomi yayını A | 3 | RSS | Framing çeşitliliği |
| 8 | Bağımsız ekonomi yayını B | 3 | RSS | Farklı editoryal çizgi |

**Sert kural:** MVP'de 8'den fazla kaynak eklenmez. Kaynak eklemek kolay ve yanıltıcı derecede tatmin edicidir; kaliteyi düşürür, kümeleme hatasını gizler. 9. kaynak ancak Faz 4 kalite hedefleri tutulduktan sonra eklenir.

7 ve 8 numaralı kaynakların ismi Faz 0'da, ToS incelemesi (F0-08) sonucunda kesinleşir.

### 9.3 Erişim ve telif politikası

Öncelik sırası — yukarıdan aşağı, bir üstteki mümkünse alttakine geçilmez:

1. Resmî RSS / kurumsal veri akışı / açık API
2. Yayıncıyla doğrudan lisans veya iş birliği
3. Yalnızca **meta veri + ≤300 karakter alıntı + kaynağa link**
4. ❌ Toplu izinsiz scraping — **hiçbir fazda kullanılmaz**

**Saklama politikası:**

| Veri | Saklama |
|---|---|
| Başlık, URL, yayın zamanı, kaynak | Süresiz |
| Alıntı (`excerpt`) | Süresiz, ≤300 karakter |
| İşleme için çekilen gövde (`lead_paragraph`) | **Azami 30 gün**, sonra otomatik purge (`raw_purge_at`) |
| Embedding | Süresiz (türetilmiş veri) |
| Tam metin | **Hiçbir zaman saklanmaz** |

Bu politika hem telif riskini (Bölüm 12.4) hem de depolama maliyetini yönetir.

### 9.4 X (Twitter) verisi — KARAR: MVP'de API kullanılmaz

v2'nin tespiti korunur ve karara dönüştürülür.

**MVP'de X entegrasyonu:**
- ❌ X API ile okuma — kullanılmaz
- ❌ Resmî API dışı otomasyon / scraping — hiçbir fazda kullanılmaz (hesap askıya alma riski + ToS)
- ✅ **Kullanıcı-tetikli içe aktarma:** kullanıcı bir gönderi linkini panoya yapıştırır, sistem oEmbed/genel meta veriyle Tier 4 kanıt olarak kaydeder
- ✅ **Yayın köprüsü:** kopyala-panoya + X'in resmî *Web Intent* bağlantısı (`intent/post?text=…`) — API gerektirmez, ToS uyumludur, otomatik yayın değildir (kullanıcı X'te "Gönder"e basar)

**Faz 5'te yeniden değerlendirme koşulu:** X API maliyet modeli (kaç hesap × kaç okuma/gün × aylık $) çıkarılıp, gelir modeli bu kalemi kullanıcı başına karşılıyorsa — ve yalnızca o zaman.

> ⚠️ **Doğrulama notu:** v2, X'in Şubat 2026'da kullanım-bazlı faturalamaya geçtiğini ve Enterprise eşiğinin aylık 42.000 $'dan başladığını aktarıyor. Bu bilgi hızla değişebilir; **Faz 0 / F0-06 görevinde güncel fiyatlandırma doğrudan X geliştirici portalından teyit edilecektir.** MVP kararı bu rakamlardan bağımsız olarak geçerlidir (API zaten kullanılmıyor).

### 9.5 Beklenen gelişmeler (ScheduledEvent) — MVP'nin gizli kozu

Makro ekonomi dikeyinin en büyük avantajı: **gelecek takvimi kamuya açıktır.** TÜİK veri yayımlama takvimi, TCMB PPK toplantı tarihleri, enflasyon raporu tanıtımları, bütçe sunum tarihleri önceden bilinir.

Bu, MVP'de düşük maliyetle yüksek algılanan değer üretir:

- Sabah brifinginde **"Bugün 14:30'da TÜİK Ağustos TÜFE'sini açıklayacak"**
- Veri açıklandığında `scheduled_events` → `events` eşleştirmesi otomatik
- Kullanıcı hazırlığını önceden yapabilir (`Faz 5: ön-taslak`)

Faz 1'de bu takvim **elle girilebilir** (yılda ~120 kayıt); otomatik çekim Faz 5'e bırakılır. Bu, "en yüksek değer / en düşük mühendislik" oranına sahip MVP özelliğidir.

---

## 10. Editoryal Profil — Stil, İdeoloji Değil

### 10.1 Tasarım kısıtı

KVKK m.6 uyarınca **siyasi düşünce özel nitelikli kişisel veridir.** Bu, hukuki bir uyarı değil, bir **şema kısıtıdır**: sistemde kullanıcının ideolojisini kodlayacak alan bulunmaz (Bölüm 7.3, `editorial_profiles`).

| ✅ Öğrenilir / saklanır | ❌ Asla çıkarılmaz / saklanmaz |
|---|---|
| Ortalama cümle uzunluğu | Siyasi konum / parti yakınlığı |
| Ton tercihi (doğrudan, analitik, ironik) | Hükümet/muhalefet desteği skoru |
| Emoji / hashtag / noktalama alışkanlığı | İdeolojik sınıflandırma etiketi |
| Kaynak gösterme alışkanlığı | Dini/etnik/cinsel yönelim çıkarımı |
| Biçimsellik düzeyi (1–5) | Oy verme eğilimi tahmini |
| Konu ilgi alanları (enflasyon, bütçe…) | Kişilik profili |
| Kullanıcının kendi yazdığı kaçınma kuralları | Diğer kullanıcılarla siyasi kümeleme |

### 10.2 MVP'de nasıl toplanır

**Form.** Stil öğrenme (tweet analizi) MVP'de **yoktur.** Kullanıcı onboarding'de 7 soruluk bir formu doldurur ve bir *Editoryal Kimlik Kartı* oluşur. Bu kart bir sistem promptu bloğuna derlenir ve her üretimde statik olarak kullanılır — ham arşiv her seferinde yeniden işlenmez (token maliyeti optimizasyonu).

**Faz 5'te opsiyonel stil çıkarımı:** kullanıcı kendi tweet arşivini **bir kez** yükler → yalnızca yukarıdaki sol kolondaki biçimsel öznitelikler çıkarılır → kart güncellenir → **ham arşiv işleme sonrası silinir.** Açık rıza metni bu sınırı kelimesi kelimesine belirtir.

### 10.3 Echo chamber karşı-mekanizması (ölçülebilir)

v1 "echo chamber'dan kaçınılmalı" dedi, mekanizma vermedi. v3'ün mekanizması:

- **Zorunlu çeşitlilik:** Her olay sayfasında, kaynak listesinde en az **2 farklı `independence_group`** gösterilir; koşul sağlanamıyorsa UI açıkça yazar: *"Bu olay tek bir yayın grubundan raporlanıyor."*
- **Framing paneli varsayılan açık:** Kullanıcı kapatabilir ama varsayılan görünür.
- **Ölçüm:** `diversity_ratio` = kullanıcının bir haftada gördüğü olaylardaki ortalama farklı `independence_group` sayısı. Hedef ≥ 2,5. Bu metrik Bölüm 13'te izlenir.

---

## 11. Teknik Mimari — KARAR

### 11.1 Teknoloji yığını

v2 teknoloji seçimini açık bıraktı ve bir değerlendirmenin C#/PHP + Flutter önerisini "en doğal seçim değil" diye işaretledi. v3 seçimi yapıyor:

| Katman | Seçim | Gerekçe |
|---|---|---|
| **Backend** | Python 3.12 + FastAPI | Embedding, vektör arama, NER, LLM orkestrasyon kütüphanelerinin olgunluk merkezi. Tip ipuçları + Pydantic ile şema disiplini. |
| **Veritabanı** | PostgreSQL 16 + `pgvector` | Tek sistemde ilişkisel graf (Bölüm 7) **ve** vektör arama. MVP ölçeğinde ayrı vektör DB gereksiz karmaşıklık. `pgvector` HNSW ile milyonlarca satıra kadar yeter. |
| **Kuyruk / worker** | Redis + Celery (alternatif: `arq`) | Ingestion, embedding, kümeleme, LLM çağrıları arka planda; UI hiçbir zaman bloklanmaz. |
| **Zamanlayıcı** | Celery Beat | 5 dakikalık ingestion döngüsü, brifing tetikleri |
| **LLM** | Anthropic Claude (Opus/Sonnet sınıfı), **adapter arkasında** | Türkçe akıcılığı ve talimat takibi güçlü; uzun bağlam kanıt sentezine uygun. Adapter deseni model kilidini kırar. |
| **Embedding** | Faz 0'da benchmark: çok dilli barındırılan model **vs.** self-host `multilingual-e5-large` | Türkçe haber benzerliğinde performans **ölçülerek** seçilir (F0-13). Boyut şemada 1024'e sabitlendi. |
| **Frontend** | Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui | Sunucu bileşenleriyle hızlı olay sayfası; tek geliştiriciyle sürdürülebilir. |
| **Kimlik** | E-posta + magic link (Faz 1'de tek kullanıcı, Faz 4'te çok kullanıcı) | Beta ölçeğinde OAuth karmaşıklığı gereksiz. |
| **Barındırma** | Tek VPS (Hetzner/DO sınıfı) + Docker Compose | MVP'de Kubernetes yasak. Aylık maliyet öngörülebilir. |
| **Gözlemlenebilirlik** | Structured logging + Sentry + basit Grafana/Metabase paneli | Metrikler (Bölüm 13) ilk günden toplanır. |
| **Mimari desen** | **Modüler monolit** | Mikroservis MVP'de sadece gecikme ve operasyon yükü ekler. Modül sınırları net tutulur, ayrıştırma gerçek yük çıkınca yapılır. |

### 11.2 Modül sınırları (monolit içinde)

```
politikdesk/
├── ingestion/        # kaynak adaptörleri, normalizasyon, dedup
│   ├── adapters/     #   rss.py, official_feed.py, manual_import.py
│   ├── normalizer.py
│   └── dedup.py      #   content_hash + simhash
├── nlp/              # embedding, NER, iddia çıkarımı
│   ├── embedder.py
│   ├── entities.py
│   └── claims.py
├── clustering/       # olay kümeleme + birleştirme/ayırma
│   ├── assigner.py
│   └── merger.py
├── evidence/         # DETERMİNİSTİK — LLM ÇAĞRISI YOK
│   ├── rules.py      #   R0-R7 (Bölüm 8.3)
│   ├── independence.py
│   └── salience.py
├── context/          # olay-olay ilişkileri, tarihsel bağlam
├── editorial/        # taslak üretimi, pre-publish check
│   ├── generator.py
│   ├── prompts/
│   └── checker.py
├── briefing/         # sabah/akşam brifingi
├── llm/              # sağlayıcı-agnostik adapter + maliyet takibi
│   ├── client.py
│   └── budget.py
├── api/              # FastAPI router'ları
├── admin/            # kaynak yönetimi, olay denetimi, eval arayüzü
└── eval/             # test seti, ölçüm koşucusu (Bölüm 13)
```

**Mimari kural (kod incelemesinde zorlanır):** `evidence/` modülü `llm/` modülünü **import edemez.** Bu, P4'ün derleme-zamanı garantisidir. CI'da statik kontrol ile denetlenir.

### 11.3 İşleme hattı (pipeline)

```
[1] FETCH        her 5 dk · kaynak adaptörleri · yeni içerik keşfi
      ↓
[2] NORMALIZE    başlık/tarih/URL temizliği · canonical_url · dil tespiti
      ↓
[3] DEDUP        content_hash (tam) → simhash (yakın) → varsa mevcut article'a bağla
      ↓
[4] EMBED        embedding üret · articles.embedding
      ↓
[5] EXTRACT      NER (kişi/kurum) · iddia çıkarımı (LLM) · sayısal değer normalizasyonu
      ↓
[6] CLUSTER      pgvector ANN ile aday olaylar → eşik + zaman + varlık kontrolü
                 → mevcut olaya ata VEYA yeni olay yarat
      ↓
[7] EVIDENCE     ⚠ DETERMİNİSTİK · bağımsız sayım → R0-R7 → evidence_status + status_reason
      ↓
[8] SALIENCE     deterministik skor + breakdown
      ↓
[9] CONTEXT      benzer geçmiş olay araması → event_relations
      ↓
[10] SUMMARIZE   LLM: olay başlığı, TL;DR, "ne biliyoruz / ne bilmiyoruz"
                 ⚠ yalnızca kanıt listesine dayalı (source-grounded), yeni bilgi eklemez
      ↓
[11] SURFACE     salience sıralı feed · brifing kuyruğu · bildirim
      ↓
[12] DRAFT       (kullanıcı tetikler) kanıta bağlı taslak üretimi + pre-publish check
```

**Kritik hat kuralları:**
- Adım 7 ve 8, LLM çağrısı içermez.
- Adım 10 ve 12, yalnızca veritabanındaki `claims` + `evidence` kayıtlarını girdi alır; ham web içeriğine veya model iç bilgisine dayanamaz.
- Adım 12, `claims` tablosunda kayıt yoksa **çalışmaz** (P1'in kod hâli — API 409 döner).

### 11.4 Olay kümeleme algoritması (detay)

Ürünün en riskli teknik bileşeni. Yaklaşım: **artımlı (incremental) merkez tabanlı kümeleme + kısıt kontrolü.**

```
FONKSİYON kumele(article):
  # 1) Aday olayları getir: son 96 saat, aynı dikey
  adaylar = SELECT id, centroid_embedding, first_reported_at, entity_set
            FROM events
            WHERE vertical = article.vertical
              AND last_update_at > now() - INTERVAL '96 hours'
              AND merged_into_id IS NULL
            ORDER BY centroid_embedding <=> article.embedding
            LIMIT 20

  en_iyi = NULL
  HER aday IÇIN adaylar:
      sim = cosine(article.embedding, aday.centroid_embedding)

      # 2) Kısıt kontrolleri — benzerlik tek başına yetmez
      zaman_ok   = |article.published_at - aday.last_update_at| <= 72h
      varlik_ok  = jaccard(article.entities, aday.entity_set) >= 0.25
                   VEYA en az 1 ortak Tier-1 varlık
                   VEYA "uygulanamaz" (bir taraf varlıksızsa — v3.2)
      gosterge_ok = article ile aday AYNI göstergeden bahsediyor    # v3.2
                   (iki taraf da doluysa ve kesişim boşsa → AYRI OLAY)
      sayi_ok    = article'daki sayısal iddialar aday ile çelişmiyor
                   (örn. "faiz %40" vs "faiz %42" → farklı olay olabilir → BAYRAK)

      EĞER DEĞİL gosterge_ok:
          → aday ELENIR (bayrak değil, ret)
      EĞER sim >= T_HIGH (0.86) VE zaman_ok VE varlik_ok:
          en_iyi = max(en_iyi, (sim, aday))
      DEĞİLSE EĞER sim >= T_LOW (0.78) VE zaman_ok VE varlik_ok:
          → İNSAN DENETİM KUYRUĞUNA (review_flag='needs_review'), geçici atama

  EĞER en_iyi VARSA:
      ata(article, en_iyi.aday); merkezi_guncelle(); last_update_at = now()
  DEĞİLSE:
      yeni_olay_yarat(article)
```

**Eşikler (`T_HIGH=0.86`, `T_LOW=0.78`) tahmindir ve Faz 2'de test setiyle kalibre edilir** (F2-14). Kalibrasyon, precision'ı recall'a tercih eder: **yanlış birleştirme, ayrı kalmaktan daha zararlıdır** (kullanıcı yanlış kanıtla içerik üretir).

**Zorunlu kaçış valfleri:**
- Kullanıcı/admin bir olayı **ayırabilir** (`split`) ve iki olayı **birleştirebilir** (`merge`); her iki işlem `audit_log`'a yazılır.
- `merged_into_id` sayesinde her birleştirme geri alınabilir.
- Çelişkili sayısal iddia bayrağı, olayı otomatik `needs_review`'a alır.

#### Varlık kısıtının boş küme davranışı (v3.2)

v3.1 bu durumu tanımlamıyordu ve kısıt harfiyen uygulandığında
`jaccard(∅, ∅) = 0` olduğu için **reddediyordu.** İlk canlı koşumda 11
makalenin 6'sında hiç varlık yoktu; 0,9997 benzerlikli iki makale (aynı
olay) yalnızca bu yüzden ayrı düştü.

**Kural:** Boş küme çelişki kanıtı değil, **kanıt yokluğudur.** En az bir
taraf boşsa kısıt *uygulanamamış* sayılır (`inconclusive`) ve reddetmez.
Precision önceliği korunur: uygulanamayan kısıt otomatik atama hakkı
vermez — atama yalnızca `T_HIGH` üstünde ve **insan denetimiyle** yapılır.

#### Gösterge kısıtı (v3.2)

Aynı kurumun aynı gün yayımladığı **farklı göstergeler ayrı olaydır.**
TÜİK bir sabah hem sanayi üretimini hem dış ticaret endekslerini açıklar;
iki metin de aynı kurumdan, aynı tarihli, aynı varlıklara sahip ve gömme
uzayında komşudur. Benzerlik ve varlık kısıtı ikisini de geçirir.

Bu bir *benzerlik* sorunu değil, bir *konu* sorunudur — bu yüzden kısıt
bir **ret**tir, bayrak değil. Sayısal çelişkiden farkı: orada hangi
değerin doğru olduğu bilinmez (insan bakar), burada iki konunun ayrı
olduğu kesindir.

Boş küme semantiği burada da geçerlidir: bir taraf göstergesizse kısıt
uygulanamaz ve reddetmez.

Zorlama: `politikdesk/clustering/indicators.py`, `tests/test_clustering.py`.

### 11.5 LLM kullanım disiplini

| Kural | Gerekçe |
|---|---|
| Tüm çağrılar `llm/client.py` üzerinden | Model değişimi tek noktadan; maliyet ve token sayımı merkezî |
| Her çağrı için token/maliyet loglanır, günlük bütçe tavanı var | Maliyet sürprizi yok; tavan aşılırsa hat durur ve uyarır |
| **Derinlik/kararlılık:** çıkarım ve özetleme için düşük seviye (`effort=low`), taslak üretimi için yüksek seviye (`effort=high`). Sağlayıcı sıcaklık parametresi sunuyorsa çıkarımda 0–0.2, üretimde 0.6–0.8 kullanılır. | Çıkarım deterministik olmalı; üretim yaratıcı olabilir. **Mekanizma sağlayıcıya göre değişir, amaç değişmez:** seçilen model sınıfı (Claude Opus 5 / Sonnet 5) `temperature`/`top_p`/`top_k` kabul etmez — gönderilirse HTTP 400 döner; işlevsel karşılığı `output_config.effort`tur. `politikdesk/config.py` → `llm_effort_extraction` / `llm_effort_generation`; regresyon koruması `tests/test_llm_budget.py::test_no_sampling_parameters_are_sent`. |
| Yapılandırılmış çıktı zorunlu (JSON şema / tool use) | Serbest metin ayrıştırma kırılgan |
| Her prompt sürümlenir (`prompts/claims.v3.md`) ve çıktıya işlenir | Kalite regresyonu izlenebilir |
| **Grounding kuralı:** prompt'ta *"Yalnızca verilen kanıt listesindeki bilgiyi kullan. Kanıtta olmayan hiçbir olgu, sayı, tarih veya alıntı ekleme. Eksikse 'kanıt yok' yaz."* | Halüsinasyon riskinin birincil savunması |
| Çıktı doğrulaması: üretilen metindeki her sayı/tarih, kanıt setinde geçiyor mu — **programatik kontrol** | Prompt talimatı yeterli değil; makine denetimi şart |

---

## 12. Hukuki ve Güvenlik Çerçevesi

> ⚖️ Bu bölüm hukuki görüş değildir. Kodlamaya başlamadan önce medya/teknoloji hukuku danışmanıyla görüşülmesi **Faz 0'ın çıkış koşuludur** (F0-10).

### 12.1 TCK m. 217/A (7418 sayılı Kanun) — dezenformasyon

Kamu düzenini bozmaya elverişli şekilde gerçeğe aykırı bilgiyi yayma cezai sorumluluk taşır. Ürünün işlevi bu riskle **doğrudan kesişir.**

**v3'ün yapısal azaltımları:**

| Azaltım | Nerede |
|---|---|
| `unverified` / `single_source` etiketi **zorunlu ve gizlenemez** | Bölüm 8.1 · UI'da kapatılamaz |
| Tahmin tipi iddia asla doğrulanmış görünemez (R0) | Bölüm 8.3 |
| Yalnızca sosyal kaynaklı iddia asla 🟢 olamaz (R7) | Bölüm 8.3 |
| Taslak, kanıt kaydı yoksa üretilemez | Bölüm 11.3, adım 12 |
| Pre-publish check, doğrulanmamış iddia içeren taslakta **engelleyici uyarı** gösterir | Bölüm 14.3 |
| Otomatik yayın kod yolu mevcut değil (P5) | Bölüm 2 |
| Kullanıcı sözleşmesinde editoryal sorumluluğun kullanıcıda olduğu açıkça yazılır | F0-11 |

### 12.2 KVKK (6698) — özel nitelikli veri

- Siyasi düşünce özel nitelikli veridir → **şemada ideolojik alan yok** (Bölüm 7.3, 10.1).
- Aydınlatma metni + açık rıza akışı, veri türü ve amacı kelimesi kelimesine sınırlar (F4-11).
- Saklama süresi politikası tanımlı (Bölüm 9.3) ve otomatik purge işiyle uygulanır.
- Veri sahibi hakları: dışa aktarma ve silme uçları Faz 4'te canlıya çıkar (F4-12).
- Siyasi aktörler hakkında biriken kamuya açık veri (olay grafiği) → **kamuya açık kaynak + gazetecilik/ifade özgürlüğü** çerçevesinde konumlandırılır; bu değerlendirme F0-10 danışmanlığının gündem maddesidir.

### 12.3 Basın Kanunu / internet yayıncılığı kapsamı

Sistem "haber toplayan, özetleyen, sunan" bir yapı olduğu için ilerleyen aşamada bu kapsamda değerlendirilme riski taşır. MVP'de ürün **kapalı beta, kullanıcıya özel çalışma masası** olarak konumlanır — kamuya açık bir yayın organı değildir. Kamuya açık bir "gündem sayfası" yayımlama fikri (cazip olsa da) **Faz 6'ya ve hukuki netliğe** bağlıdır.

### 12.4 Telif hakkı

Azaltım: Bölüm 9.3'teki saklama politikası (meta veri + ≤300 karakter alıntı + link; tam metin yok, `lead_paragraph` 30 gün TTL). Kaynak karşılaştırma ekranı **başlık + kısa alıntı + link** gösterir; yan yana tam metin göstermez. Her kaynak için `tos_status` alanı tutulur ve `forbidden` işaretli kaynaktan ingestion yapılmaz (kod seviyesinde engel).

### 12.5 X platform politikası

Bölüm 9.4 — resmî API dışı otomasyon hiçbir fazda kullanılmaz. MVP'de yayın, Web Intent + panoya kopyalama ile kullanıcı eylemine bağlıdır.

### 12.6 Election Mode (Faz 5'te uygulanır, Faz 1'de tasarlanır)

Seçim dönemlerinde elle veya takvimle etkinleşen sıkı mod:

- Tüm `single_source` ve `unverified` iddialar için taslak üretimi **devre dışı**
- Kanıt eşiği yükselir: 🟢 için `independent_count ≥ 4` **ve** Tier 1 zorunlu
- Her taslakta zorunlu kaynak linki
- Yarı-otomasyonun tamamı kapalı
- Kullanıcıya görünür mod göstergesi

Bu mod Faz 1'de bir **feature flag + konfigürasyon şeması** olarak hazırlanır (uygulanmaz), böylece ihtiyaç anında haftalar değil saatler içinde açılabilir.

### 12.7 Trust & Safety — sistemin asla yapmayacakları

Bölüm 15'e bakınız. Bu liste ürün sözleşmesidir, tercih değildir.

---

## 13. Ölçüm ve Değerlendirme (Evaluation)

P7'nin uygulanması. **Ölçülemeyen özellik yayına girmez.**

### 13.1 Altın test seti (Golden Set)

| Özellik | Değer |
|---|---|
| Boyut | 300 makale → ~80–100 olay (makro ekonomi, geçmiş 3 ay) |
| Etiketleme | Elle; her makale → doğru olay kimliği |
| İçerik | Kolay küme (aynı veri, farklı gazete) + zor küme (aynı konu farklı olay, örn. iki ayrı PPK) + çelişkili kaynak örnekleri + ajans kopyası örnekleri |
| İddia alt seti | 150 iddia → doğru `evidence_status` (kural el ile uygulanarak) |
| Sürümleme | Git'te versiyonlanır; her model/prompt değişiminde yeniden koşulur |
| Sahiplik | Faz 0'da başlar (F0-14), Faz 2 sonuna kadar tamamlanır |

### 13.2 Kalite hedefleri (yayın kapısı — gate)

| Metrik | Hedef | Kapı |
|---|---|---|
| Olay kümeleme — **precision** | ≥ %90 | Faz 2 çıkışı |
| Olay kümeleme — **recall** | ≥ %80 | Faz 2 çıkışı |
| Yanlış birleştirme oranı (false merge) | ≤ %5 | Faz 2 çıkışı — **sert kapı** |
| `evidence_status` doğruluğu (elle uygulanan kurala karşı) | ≥ %95 | Faz 2 çıkışı |
| İddia çıkarımı — hatalı/uydurulmuş iddia oranı | ≤ %2 | Faz 2 çıkışı |
| Taslakta kanıtta olmayan sayı/tarih | **%0** | Faz 3 çıkışı — **sert kapı** |
| Pre-publish check yanlış-negatif (kaçırılan doğrulanmamış iddia) | ≤ %5 | Faz 3 çıkışı |

Precision, recall'a tercih edilir: yanlış birleştirme kullanıcıyı yanlış bilgiyle içerik üretmeye götürür; ayrı kalan olay yalnızca rahatsızlık yaratır.

#### MVP çıkış kapısı G4′ (v3.2)

Özgün G4'ün 11 koşulundan **7'si gerçek beta kullanıcısı gerektiriyordu**
(draft acceptance, edit distance, briefing open rate, oturum sayısı, KVKK
canlıda, ödeme isteği, 100 kullanıcı izdüşümü). Tek kullanıcılı kapsam
kararıyla (§14.1) bunlar **hiçbir zaman ölçülemez** hale geldi.

**Ölçülemeyen koşul kapı değildir.** Kapıyı kâğıt üstünde tutmak, Spec'in
kendi kuralını ("kapıyı düşürmek üçüncü seçenek değildir") içten
çürütürdü. Yürürlükteki kapı:

| # | Koşul | Hedef |
|---|---|---|
| 1 | Uçtan uca akış 7 gün kesintisiz | Feed → olay → taslak → kontrol → kopyala |
| 2 | Taslakta kanıtta olmayan sayı/tarih | **%0** (50 taslak) — sert kapı, korunur |
| 3 | Correction rate | ≤ %3 |
| 4 | Diversity ratio | ≥ 2,5 |
| 5 | Ölçülen aylık toplam maliyet | ≤ 30 $ |
| 6 | Kritik hata (P0/P1) | 0 açık |
| 7 | G2 metrikleri regresyona uğramamış | — |
| 8 | Yedekleme + geri yükleme denenmiş | Belgelenmiş |
| 9 | Günlük yedek ve maliyet alarmı çalışıyor | — |

Özgün G4 kayıt için Yol Haritası'nda saklanır; çok kullanıcıya geçilirse
geri gelir.

### 13.3 Ürün metrikleri (Faz 3'ten itibaren toplanır)

| Metrik | Tanım | MVP hedefi |
|---|---|---|
| **Time-to-understanding** | Olay sayfasında ilk anlamaya kadar geçen süre (oturum ölçümü + kullanıcı beyanı) | 30–45 dk tarama → ≤ 10 dk |
| **Draft acceptance rate** | Taslakların (küçük düzenlemeyle) kullanılma oranı | ≥ %40 |
| **Edit distance** | Kullanıcının taslağı değiştirme oranı (normalize Levenshtein) | ≤ 0,35 |
| **Diversity ratio** | Görülen olaylarda ortalama farklı `independence_group` sayısı | ≥ 2,5 |
| **Briefing open rate** | Sabah brifingi açılma oranı | ≥ %60 |
| **Daily active minutes** | Günlük aktif kullanım (dakika) | 10–20 dk (az olması **iyi**) |
| **Correction rate** | Kullanıcının "bu yanlış" işaretlediği olay oranı | ≤ %3 |
| **Cost per active user / ay** — *birim ekonomi* | LLM + embedding + altyapı, **100 aktif kullanıcı ölçeğinde** | ≤ 8 $ |
| **Toplam aylık maliyet** — *beta bütçe tavanı* | Kapalı beta boyunca tüm altyapı + model harcaması | ≤ 150 $ |

**Neden maliyet hedefi ölçek belirtir.** Ingestion, embedding, kümeleme ve özetleme maliyeti kullanıcı sayısından **bağımsızdır** (ayda ~71 $ sabit; `docs/veri-maliyet-modeli.md`). Başabaş noktası ~18 kullanıcıdır: 8 kullanıcılı kapalı betada kişi başı 12,80 $, 100 kullanıcıda 4,67 $ çıkar. Ölçek belirtmeyen tek bir hedef, kapalı betada ya otomatik olarak tutmaz (ve kapıyı bloke eder) ya da "öngörü" kelimesine sığınılarak geçilir. Bu yüzden hedef ikiye ayrılmıştır: **birim ekonomi** ürünün ölçeklenebilirlik kanıtıdır, **beta bütçe tavanı** nakit gerçekliğidir. Kapı koşulları (G0 #8, G4 #7) bu iki satırı ayrı ayrı ölçer.

`daily_active_minutes`'ın **düşük** olmasının hedef olması bilinçlidir: ürünün vaadi zaman tasarrufudur, etkileşim değil. Bu metriği yukarı çekmeye çalışan hiçbir özellik kabul edilmez.

### 13.4 Haftalık kalite ritüeli

Her Cuma, 60 dakika:
1. Rastgele 10 olay örneklenir → kümeleme ve kanıt durumu elle denetlenir
2. `needs_review` kuyruğu boşaltılır
3. Yanlış örnekler Golden Set'e eklenir (set büyür ve zorlaşır)
4. Metrik panosu gözden geçirilir, regresyon varsa kök neden aranır
5. LLM maliyet trendi kontrol edilir

Bu ritüel Faz 2'de başlar ve ürün ömrü boyunca devam eder.

---

## 14. MVP Fonksiyonel Kapsam

### 14.1 MVP'ye dahil (kesin liste)

| # | Özellik | Core Loop adımı |
|---|---|---|
| 1 | **Live Feed** — makro ekonomi olayları, salience sıralı | DISCOVER |
| 2 | **Event Clustering** — haberleri olayda birleştirme | UNDERSTAND |
| 3 | **Olay Sayfası** — TL;DR / ne biliyoruz / ne bilmiyoruz | UNDERSTAND |
| 4 | **Source Comparison** — kaynaklar yan yana + framing paneli | VERIFY |
| 5 | **Evidence Status** — iddia bazlı kategorik durum + gerekçe | VERIFY |
| 6 | **Zaman Çizelgesi** — olayın gelişme akışı | UNDERSTAND |
| 7 | **Tarihsel Bağlam** — "bu konu daha önce ne zaman gündeme geldi" | CONTEXTUALIZE |
| 8 | **Beklenen Gelişmeler** — TÜİK/TCMB takvimi | CONTEXTUALIZE |
| 9 | **Editoryal Taslaklar** — 3 açı (bilgilendir / analiz et / eleştir), kaynaklı | DRAFT |
| 10 | **Pre-publish Check** — yayın öncesi editoryal kontrol | REVIEW |
| 11 | **Yayın Köprüsü** — panoya kopyala + X Web Intent | REVIEW |
| 12 | **Sabah / Akşam Brifingi** — e-posta + uygulama içi | DISCOVER |
| 13 | **Editoryal Kimlik Kartı** — 7 soruluk form | DRAFT |
| 14 | **Admin / Denetim Paneli** — kaynak yönetimi, olay merge/split, eval | (iç araç) |
| 15 | **Kanıtsız olayda üretim engeli** — yeterli kanıtı olmayan olayda taslak üretimi kod yolu olarak açılmaz | REVIEW (P1) |

#### Kapsam düzeltmesi: tek kullanıcılı araç (v3.2)

12 Ağustos 2026'da proje **tek kullanıcılı kişisel bir araç** olarak
kararlaştırıldı (`docs/FAZ0-DURUM.md`). Bu kararla yukarıdaki 15 kalem
değişmez — **MVP'nin işlevsel kapsamı aynıdır** — ama şunlar kapsam
dışına çıkar:

| Kapsam dışı | Gerekçe |
|---|---|
| Çok kullanıcılı veri izolasyonu, davet, kullanıcı ayarları (F4-01…04) | Kullanıcı = geliştirici |
| KVKK aydınlatma/rıza, veri sahibi hakları, kullanım koşulları (F4-11…14) | Veri sahibi = kullanıcı; hukuk danışmanlığı adımı (F0-10/11) da bu gerekçeyle düştü |
| Kapalı beta yürütme (F4-17…22) | Beta kullanıcısı yok |
| Ücretlendirme / ödeme altyapısı | Müşteri yok (D19 geçersiz) |

**İstisna:** Election Mode flag'i (F4-15) ve denetim izi (F4-16) kalır —
ikisi de tek kullanıcıda da gereklidir.

**MVP artık Faz 3'ün sonunda biter.** Faz 4, yalnızca tek kullanıcılı araç
için de gerekli olan sertleştirme işlerini (dayanıklılık, yedekleme,
maliyet tavanı, güvenlik, üretim ortamı) içerir. Bunun kapı karşılığı
G4′'tür (§13.2).

### 14.2 MVP'de KESİNLİKLE olmayacaklar

Gündem haritası (görsel) · kişi/kurum ilişki grafiği · söylem değişikliği analizi · tam Political Memory arşivi · 500 tweet'ten stil öğrenme · X API ile okuma · otomatik/yarı-otomatik yayın · içerik kuyruğu ve yayın takvimi · çoklu platform uyarlaması (Threads, Instagram, YouTube, newsletter) · mobil uygulama · Team/B2B workspace · 8'den fazla kaynak · ekonomi dışında dikey · belge/PDF analizi · "söz/gerçek karşılaştırması" · tekrarlayan içerik kontrolü · ücretlendirme/ödeme altyapısı.

**Bu liste bir kayıp değil, bir sıralamadır.** Her biri Faz 5/6'da adreslenir (Bölüm 16).

### 14.3 Anahtar ekran: Olay Sayfası

```
┌───────────────────────────────────────────────────────────────────────────┐
│  ← Feed'e dön                                       Salience 84  ⓘ       │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  TÜİK Ağustos enflasyon verisini açıkladı        🟠 GELİŞİYOR             │
│  İlk rapor 10:00 · Son güncelleme 12:47 · 11 makale · 4 bağımsız teyit   │
│                                                                           │
│  ┌─ TL;DR ─────────────────────────────────────────────────────────────┐ │
│  │ 2-3 cümle özet. Yalnızca doğrulanmış unsurlardan kurulur.           │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  NE BİLİYORUZ                          NE BİLMİYORUZ                     │
│  🟢 Aylık TÜFE %X (TÜİK)               ⚪ TCMB'nin tepkisi                │
│  🟢 Yıllık TÜFE %Y (TÜİK)              🟠 Piyasa beklentisi (tek kaynak)  │
│  🟡 Gıda kalemi etkisi (kısmi)          🔴 Çekirdek oranda çelişki        │
│                                                                           │
│  ┌─ KANIT ─────────────────────────────────────────────────────────────┐ │
│  │ Birincil kaynak mevcut ✓   Resmî 1 · Ajans 1 · Medya 3 · Sosyal 4   │ │
│  │ [Neden 🟢?] → R2: birincil kaynak + 4 bağımsız teyit, çelişki yok   │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  KAYNAKLAR (çerçeve farkı)                                                │
│  ┌──────────────┬──────────────────────────────────┬────────┬──────────┐  │
│  │ TÜİK      T1 │ "Ağustos ayı TÜFE sonuçları"     │ 10:00  │ → link   │  │
│  │ AA        T2 │ "Enflasyon ağustosta …"          │ 10:04  │ → link   │  │
│  │ Yayın A   T3 │ "Enflasyonda beklenti aşıldı"    │ 10:22  │ → link   │  │
│  │ Yayın B   T3 │ "Veri sonrası piyasada …"        │ 10:31  │ → link   │  │
│  └──────────────┴──────────────────────────────────┴────────┴──────────┘  │
│  ⓘ Bu olay 3 farklı yayın grubundan raporlanıyor.                        │
│                                                                           │
│  ZAMAN ÇİZELGESİ    10:00 → 10:04 → 10:22 → 11:15 → 12:47   [genişlet]   │
│                                                                           │
│  ÖNCEKİ BAĞLAM      • Temmuz verisi (12 Tem) — %Z                        │
│                     • TCMB enflasyon raporu (8 Tem)                       │
│                                                                           │
│  SIRADAKİ BEKLENEN  • TCMB PPK toplantısı — 21 Ağu 14:00                  │
│                                                                           │
├───────────────────────────────────────────────────────────────────────────┤
│  EDİTORYAL FIRSATLAR                                                      │
│  [ Bilgilendir ]  [ Analiz Et ]  [ Eleştir ]        Kanıta bağlı üretim ✓ │
└───────────────────────────────────────────────────────────────────────────┘
```

**Dil kararı:** Buton metinleri asla `Tweet Üret` olmaz. `Bilgilendir` / `Analiz Et` / `Eleştir` / `Açıyı keşfet` / `Argümanı geliştir` kullanılır. Bu, ürünü "metin üretici"den "araştırma ortağı"na taşıyan en düşük maliyetli karardır.

### 14.4 Pre-publish Check çıktısı

```
YAYIN ÖNCESİ KONTROL

✓  Kaynak linki mevcut                              (2 link)
✓  Tüm sayısal veriler kanıtla eşleşti              (3/3)
✓  Haber ile yorum ayrı işaretlendi
⚠  1 iddia yalnızca tek kaynaklı                    → "piyasa beklentisi %X"
✗  1 cümle hiçbir kanıta bağlanamadı                → "bu eğilim sürecek"
                                                       (Tahmin olarak etiketle?)
ⓘ  Eksik bağlam: önceki ayın verisine değinilmemiş

[ Düzelt ]   [ Yine de devam et ]   [ Yeniden üret ]
```

**Engelleyici (blocking) durum:** "Kanıta bağlanamayan sayısal iddia" tespit edilirse `Yine de devam et` butonu, kullanıcı bir onay kutusunu işaretlemeden etkinleşmez. Bu, 12.1'in UI karşılığıdır.

---

## 15. Sistemin Asla Yapmayacakları (Ürün Sözleşmesi)

Bu liste yalnızca bir etik beyan değil; her maddesi **kod veya şema seviyesinde** karşılığı olan bir kısıttır.

| # | Yasak | Zorlama mekanizması |
|---|---|---|
| 1 | Kaynakta olmayan olgu/sayı/tarih/alıntı üretmek | Grounding promptu + programatik sayı/tarih doğrulaması (11.5) |
| 2 | Sahte alıntı veya uydurma kaynak göstermek | Her alıntı `evidence.quote_span`'e bağlı; bağlanmayan alıntı taslaktan silinir |
| 3 | Doğrulanmamış iddiayı doğrulanmış gibi sunmak | Deterministik R0–R7 + gizlenemez etiket |
| 4 | Kullanıcının siyasi ideolojisini sınıflandırmak | Şemada alan yok (7.3, 10.1) |
| 5 | Bir kaynağa siyasi konum etiketi vermek | Framing dili, "bias" değil (8.5) |
| 6 | İnsan onayı olmadan yayın yapmak | Otomatik yayın kod yolu mevcut değil (P5) |
| 7 | Sahte hesap/persona oluşturmak veya yönetmek | Ürün tek kullanıcı-tek hesap modeli; çoklu hesap özelliği yok |
| 8 | Koordineli/toplu paylaşım, trend manipülasyonu | Toplu yayın API'si yok; oran sınırı yok çünkü yayın özelliği yok |
| 9 | Kişisel/hassas veri üzerinden seçmen hedefleme | Kitle/segment veri modeli mevcut değil |
| 10 | Belirli kişilere yönelik suçlama üretmek | İsimli kişi hakkında `unverified` iddia varsa taslak üretimi engellenir — **`prediction` tipi muaftır** (v3.2, aşağıya bakınız) |
| 11 | Resmî API dışı platform otomasyonu | Yalnızca Web Intent + pano (9.4) |
| 12 | Toplu izinsiz scraping | `tos_status='forbidden'` kaynaktan ingestion kod seviyesinde engelli |
| 13 | Tek sayısal "doğruluk yüzdesi" göstermek | Salience skoru "önem" olarak etiketlenir; doğruluk skoru şemada yok |
| 14 | Etkileşimi artırmak için gündemi çarpıtmak/sansasyonelleştirmek | Salience formülü kural tabanlı ve şeffaf; "engagement" girdisi içermez |

#### Madde 10'un kapsamı: tahmin muafiyeti (v3.2)

Madde 10 harfiyen uygulandığında **her olayı** bloke ediyordu. Sebep R0'dır:
`prediction` tipindeki her iddia, kanıt yokluğundan değil **tip kısıtından**
`unverified`'dır (§8.3). "Bakan X enflasyonun düşeceğini öngördü" cümlesi,
hakkında hiçbir isnat bulunmayan bir kişi yüzünden üretimi durduruyordu.

**Kural:** Maddenin koruduğu şey belirli kişilere yönelik **suçlamadır**; bir
kişinin kendi tahminini aktarmak suçlama değildir. Bu yüzden `claim_type =
'prediction'` olan `unverified` iddialar engelleme sayımına girmez.

Muafiyet **yalnızca tip kısıtından** doğan `unverified`'ı kapsar. Kanıt
yokluğundan `unverified` kalan bir `fact` veya `attribution` iddiası isimli
kişi içeriyorsa üretim **hâlâ engellenir** — maddenin asıl hedefi odur.

Zorlama: `politikdesk/editorial/guards.py`, `tests/test_editorial.py`.

---

## 16. Ertelenen Vizyon — Nerede Duruyor?

v1'in 58 bölümündeki hiçbir fikir çöpe atılmadı. Haritası:

| v1 fikri | Nerede |
|---|---|
| Olay kümeleme, zaman çizelgesi, kaynak karşılaştırma, güven sistemi, iddia ayrımı, haber/yorum ayrımı, editoryal profil, çok açılı taslak, gündem skoru, sabah/akşam brifingi, insan onayı, kalite kontrolü, beklenen gelişmeler | **MVP (Faz 1–4)** |
| Stil öğrenme (tweet analizi), içerik kuyruğu, yayın takvimi, içerik arşivi, tekrarlayan içerik kontrolü, karşı görüş kontrolü, "bana katılmayan kaynaklar", kaynak/kategori genişlemesi, konu-kişi takibi, günlük/haftalık rapor arşivi, Election Mode, yarı-otomasyon | **Faz 5 — Doğrulanmış Büyüme** |
| Gündem haritası, konu/kişi ilişki grafikleri, olay grafiği görselleştirme, trend analizi, medya karşılaştırma paneli, açıklama karşılaştırma, söz/gerçek karşılaştırması, belge analizi, Political Memory tam sürüm, çoklu platform (Threads/Instagram/YouTube/newsletter), "sen yokken neler oldu", Team/B2B workspace, mobil uygulama | **Faz 6 — Platform** |

---

## 17. Karar Kaydı (Decision Log)

v2'nin "netleşmesi gereken 10 karar"ı, v3'te verilmiş kararlar olarak:

| # | Karar konusu | v3 KARARI | Gerekçe / Bölüm | Statü |
|---|---|---|---|---|
| D1 | ICP | 5K–100K takipçili, tek çalışan bağımsız içerik üreticisi | §4 | ✅ Verildi |
| D2 | Çözülen problem | Gündem takibi + kaynaklandırma ikilemi | §3.1 | ✅ Verildi |
| D3 | Core Loop | Discover → Understand → Verify → Contextualize → Draft → **Review** | §6 | ✅ Verildi |
| D4 | **MVP dikeyi** | **Makro ekonomi / para politikası** | §5 | ✅ Verildi |
| D5 | MVP kapsamı | 14 özellik dahil / 22 kalem hariç | §14 | ✅ Verildi |
| D6 | Kaynak sayısı | **8 kaynak, sert sınır** | §9.2 | ✅ Verildi |
| D7 | X API | **MVP'de kullanılmaz**; Web Intent + pano ile yayın | §9.4 | ✅ Verildi |
| D8 | Evidence modeli | 5 kategorik durum + deterministik **R0–R7** (R0 tip kısıtı kanıt kurallarından önce, kısa devre) | §8 | ✅ Verildi · **v3.1'de düzeltildi** |
| D9 | Salience | Deterministik formül + şeffaf kırılım; **global (0–90) saklanır, kişisel (0–10) sorguda hesaplanır** | §8.4 | ✅ Verildi · **v3.1'de düzeltildi** |
| D10 | Editoryal profil | Yalnızca biçimsel; MVP'de form, öğrenme Faz 5 | §10 | ✅ Verildi |
| D11 | Teknoloji yığını | Python/FastAPI + Postgres+pgvector + Redis/Celery + Next.js | §11.1 | ✅ Verildi · **v3.1: LLM disiplini effort ile yazıldı** |
| D12 | Mimari desen | Modüler monolit, tek VPS, Docker Compose | §11.1 | ✅ Verildi |
| D13 | Veri saklama | Meta veri + ≤300 kr alıntı; tam metin yok; gövde 30 gün TTL | §9.3 | ✅ Verildi |
| D14 | Kalite kapıları | Kümeleme P≥%90 / R≥%80, false merge ≤%5, taslakta uydurma sayı %0; **maliyet hedefi ölçek belirtir** | §13.2, §13.3 | ✅ Verildi · **v3.1'de düzeltildi** |
| D15 | Trust & Safety | 14 maddelik sözleşme, her biri kod/şema zorlamalı | §15 | ✅ Verildi |
| D16 | Embedding modeli | **`intfloat/multilingual-e5-large`** (self-host, 1024 boyut, `query: ` öneki zorunlu). 60 gerçek Türkçe çiftte 3 aday ölçüldü; tek geçen aday. | §11.1, F0-13, `docs/embedding-benchmark.md` | ✅ Verildi (12 Ağu 2026) |
| D17 | Tier 3 kaynak isimleri | **Dünya + BloombergHT** — ikisi de canlı RSS ile doğrulandı | §9.2, F0-08 | ✅ Verildi (Faz 0) |
| D18 | Hukuki konumlandırma | ⛔ **Kapsam dışı** — tek kullanıcılı kişisel araç; danışmanlık adımı kaldırıldı | §12 | ⛔ Kapsam dışı |
| D19 | Fiyatlandırma | ⛔ **Kapsam dışı** — müşteri yok | — | ⛔ Kapsam dışı |
| D20 | Kümeleme eşikleri | T_HIGH/T_LOW Golden Set ile kalibre edilecek | §11.4, F2-14 | ⏳ Faz 2 |

**Spec-freeze kuralı:** D1–D15 dondurulmuştur. Değiştirmek için yazılı gerekçe + bu belgeye sürüm artışı gerekir. D16–D20, ilgili fazda karara bağlanır ve bu tabloya işlenir.

**Sürüm geçmişi:**

| Sürüm | Tarih | Değişiklik | Yazılı gerekçe |
|---|---|---|---|
| 3.0 | 11 Ağu 2026 | D1–D15 verildi | — |
| **3.1** | **12 Ağu 2026** | D8 (R0 sıralaması), D9 (salience ayrımı), D11 (effort), D14 (maliyet ölçeği) düzeltildi; §14.1'e 15. kalem | `docs/karar-itirazlari.md` |
| **3.2** | **13 Ağu 2026** | §11.4 boş küme davranışı (B-55) + gösterge kısıtı (B-62); §15 madde 10 tahmin muafiyeti (B-72); §14.1/G4 tek kullanıcılı kapsam (B-66) | `docs/FAZ2-DURUM.md`, `docs/FAZ3-DURUM.md`, `docs/FAZ3-SONRASI-DENETIM.md` |

---

## 18. Risk Kaydı

| # | Risk | Olasılık | Etki | Azaltım | Erken uyarı sinyali |
|---|---|---|---|---|---|
| R1 | Olay kümeleme hedef doğruluğa ulaşmaz | Orta-Yüksek | Kritik | Golden Set + insan denetim kuyruğu + merge/split kaçış valfi; gerekirse dikey daha da daralır | Faz 2 ortasında precision < %80 |
| R2 | Halüsinasyon taslağa sızar | Orta | Kritik | Grounding + programatik sayı/tarih doğrulaması + pre-publish check | Eval'de uydurma sayı > %0 |
| R3 | Hukuki konumlandırma MVP'yi geçersiz kılar | Düşük-Orta | Kritik | F0-10 danışmanlığı **kod yazımından önce**; kapsam daraltma hazır | Danışman "bu haliyle olmaz" derse |
| R4 | Kapsam şişmesi | **Yüksek** | Yüksek | Spec-freeze + özellik filtresi + 14.2 hariç listesi + faz kapıları | Sprint'e listede olmayan iş girmesi |
| R5 | Kaynak erişimi ToS nedeniyle kapanır | Orta | Yüksek | Tier 1 omurga (resmî kaynaklar ToS açısından en güvenli); kaynak başına `tos_status` | Bir kaynak 403/robots değişimi |
| R6 | LLM maliyeti öngörülemez büyür | Orta | Orta | Günlük bütçe tavanı, statik profil, sıcaklık/token disiplini, ucuz model ile çıkarım-pahalı model ile üretim ayrımı | Kullanıcı başına aylık maliyet > 8 $ |
| R7 | Gerçek talep yok / ödeme isteği düşük | Orta | Yüksek | F0-04'te 12 görüşme; beta'da 8 aktif kullanıcı hedefi | Beta'da haftalık dönüş oranı < %40 |
| R8 | Tek geliştirici tükenmesi | **Yüksek** | Yüksek | 22 haftalık gerçekçi plan, faz kapıları, "hariç listesi" disiplini, haftalık ritüel | 2 hafta üst üste plan sapması > %30 |
| R9 | Türkçe embedding kalitesi yetersiz | Düşük-Orta | Yüksek | F0-13 benchmark; alternatif: hibrit (embedding + BM25 + varlık kısıtı) | Benchmark'ta ayrım gücü zayıf |
| R10 | Kullanıcı AI çıktısına aşırı güvenir | Orta | Yüksek | Pre-publish check engelleyici, gizlenemez etiketler, kanıt her zaman görünür | Draft acceptance %80'in üzerinde (şüpheli yüksek) |
| R11 | Ürün "engagement makinesi"ne dönüşme baskısı | Orta | Orta | 13.3 — düşük kullanım süresi hedefi; salience'ta engagement girdisi yasak | Metrik hedefini yukarı çekme isteği |
| R12 | X politikası yayın köprüsünü kırar | Düşük | Düşük | Pano kopyalama her zaman yedek yol | Web Intent davranış değişimi |

---

## 19. Sonuç

PolitikDesk'in fikri v1'de kurulmuş, v2'de dürüstçe eleştirilmiş ve daraltılmıştır. v3'ün katkısı tek bir şeydir: **kararsızlığı bitirmek.**

Ürün artık şu üç cümleyle özetlenebilir:

1. **Ne inşa ediyoruz:** Makro ekonomi gündemi için, 8 kaynaktan beslenen, haberleri olaya çeviren, her iddiayı deterministik kurallarla kanıta bağlayan ve kaynaklı editoryal taslak üreten bir çalışma masası.
2. **Neyi inşa etmiyoruz:** Bölüm 14.2'deki 22 kalemi — şimdilik.
3. **Nasıl bileceğiz doğru çalıştığını:** Bölüm 13.2'deki yedi kalite kapısı ve Bölüm 13.3'teki sekiz ürün metriği.

Riskin teknik olmadığı v2'de doğru tespit edilmişti. v3, o riski üç mekanizmayla yönetir: **spec-freeze** (kapsam), **deterministik kanıt motoru** (doğruluk), **hukuki kapı** (yasal zemin).

> **AI senin yerine konuşmaz. AI senin daha iyi konuşabilmen için gündemi senin adına takip eder.**

---

**Sonraki adım:** `PolitikDesk_Yol_Haritasi_v1.md` → Faz 0, görev F0-01.

---

*Bu belge hukuki tavsiye içermez. Bölüm 12'deki başlıklar için medya/teknoloji hukuku danışmanına başvurulması Faz 0'ın çıkış koşuludur. Dış faktörlere dayalı bilgiler (X API fiyatlandırması, mevzuat durumu, kaynak erişim şartları) hızla değişebilir ve Faz 0'da güncel olarak teyit edilecektir.*
