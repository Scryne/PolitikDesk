# BACKLOG

**Görev:** F0-19 · **Kaynak:** Spec §14.2 (MVP'de kesinlikle olmayacaklar) + §16 (ertelenen vizyon haritası)

> **Bu liste bir kayıp değil, bir sıralamadır.** (Spec §14.2)
>
> **Kullanım kuralı (Yol Haritası §5):** Yeni bir fikir geldiğinde **yaz, yapma.**
> Fikir buraya yazılır, aynı gün kodlanmaz. Filtreden geçse bile mevcut fazın
> görev listesinde yoksa **bir sonraki faza** atanır. Yalnızca "beta engelleyici"
> veya "hukuki zorunluluk" etiketli işler faz ortasında listeye girebilir —
> ve bu etiket **yazılı gerekçe** gerektirir.

---

## Faz 5 — Doğrulanmış Büyüme

**Ön koşul: Kapı G4 açık olmalı.** Bu faz takvime değil, MVP'nin *kanıtlanmış*
olmasına bağlıdır.

| # | Kalem | Neden MVP'de yok | Giriş koşulu |
|---|---|---|---|
| B-01 | **Stil öğrenme** (tweet arşivinden biçimsel çıkarım) | DRAFT adımına katkısı marjinal; form ile %80'i alınıyor (Spec §10.2). Ayrı KVKK rıza metni gerektirir. | G4 + ayrı açık rıza metni + ham arşivin işleme sonrası silinmesi garantisi |
| B-02 | **İçerik kuyruğu** (taslak / onay bekleyen / zamanlanmış / yayınlanan) | Bir çıktı; ürünün merkezi kanıt katmanı (Spec §3.3). | G4 + draft acceptance rate ≥ %40 |
| B-03 | **Yayın takvimi** | B-02'ye bağlı. | B-02 |
| B-04 | **İçerik arşivi ve arama** | B-02'ye bağlı. | B-02 |
| B-05 | **Tekrarlayan içerik kontrolü** ("bunu daha önce paylaştın") | B-04 olmadan anlamsız. | B-04 |
| B-06 | **Karşı görüş kontrolü** (tam sürüm) | REVIEW adımına hizmet eder ama MVP'de basit sürümü var (framing paneli + `independence_group` çeşitliliği). | G4 + diversity ratio ≥ 2,5 sürdürülüyor |
| B-07 | **"Bana katılmayan kaynaklar"** | Echo chamber karşı-mekanizmasının derinleşmesi. | B-06 |
| B-08 | **Kaynak/kategori genişlemesi** (8 → azami 15) | Spec §9.2 sert kural: 9. kaynak ancak Faz 4 kalite hedefleri tutulduktan sonra. | G4 + G2 metrikleri regresyona uğramamış |
| B-09 | **Dikey genişleme: Yasama/TBMM** | Motor makro ekonomide kalibre edilmeden yeni dikey açılmaz (Spec §5). | Kümeleme precision ≥ %88 (yeni Golden Set 150 makale) |
| B-10 | **Dikey genişleme: Yargı/hukuk** | En yüksek isimli-kişi riski. | `unverified` iddiada isimli kişi taslak engeli |
| B-11 | **Dikey genişleme: Dış politika** | Çok dilli embedding + çeviri katmanı gerektirir. | Çok dilli kümeleme precision ≥ %85 |
| B-12 | **Dikey genişleme: Genel siyaset** | Kasıtlı olarak en sona bırakıldı — en yüksek risk (Spec §5). | Election Mode canlı testi |
| B-13 | **Konu ve kişi/kurum takibi** (istihbarat) | CONTEXTUALIZE adımını derinleştirir; MVP'de olay grafiği yeterli. | G4 |
| B-14 | **Günlük/haftalık rapor arşivi** | Brifing üretiliyor ama arşivlenmiyor. | B-04 |
| B-15 | **Political Memory v1** (olay zinciri sorgusu) | MVP'de `event_relations` var, sorgu arayüzü yok. | G4 |
| B-16 | **Election Mode aktivasyonu** | Spec §12.6: Faz 1'de flag olarak hazırlanır, Faz 5'te uygulanır. | F4-15 tamamlanmış |
| B-17 | **Yarı-otomasyon** (resmî X API üzerinden, kullanıcı her seferinde onaylar) | P5 (insan onayı) korunmalı; yalnızca `strongly_corroborated` + `number` + Tier 1 içerik için. | X API maliyet modeli gelir modelini karşılıyorsa (B-18) |
| B-18 | **X API ile okuma** | Spec §9.4 / D7: MVP'de kullanılmaz. Maliyet modeli doğrulanmadı. | Kullanıcı başına aylık $ hesabı gelir modelini karşılıyorsa |
| ~~B-19~~ | ~~Ücretlendirme / ödeme altyapısı~~ | ⛔ **KAPSAM DIŞI** — kişisel araç, müşteri yok (D19 geçersiz). | — |

---

## Faz 6 — Platform ve B2B

**Ön koşul: Kapı G5.** Bu faz ekip büyümesi gerektirir; tek geliştiriciyle
gerçekçi değildir.

| # | Kalem | Neden MVP'de yok | Giriş koşulu |
|---|---|---|---|
| B-20 | **Gündem haritası (görsel)** | Core Loop'un hiçbir adımına hizmet etmiyor — özellik filtresinden geçemedi (Spec §6). | G5 |
| B-21 | **Kişi/kurum ilişki grafiği** | CONTEXTUALIZE'a katkısı zayıf; görsel cazibe ≠ değer. | G5 |
| B-22 | **Olay grafiği görselleştirme + trend analizi** | Veri modeli MVP'de birikiyor; görselleştirme sonra gelir. | G5 |
| B-23 | **Söylem değişikliği analizi** | Olgun kanıt zinciri gerektirir. | G5 |
| B-24 | **Açıklama karşılaştırma** (2025 vs 2026) | B-15'in üzerine kurulur. | B-15 |
| B-25 | **"Söz/gerçek karşılaştırması"** | Ürün hüküm veren bir hakem değildir (Spec §1). | G5 |
| B-26 | **Political Memory tam sürüm** | B-15'in üzerine kurulur. | B-15 |
| B-27 | **Belge/PDF analizi** (TBMM dokümanları, resmî kararlar) | Yeni bir ingestion sınıfı; MVP kapsamını iki katına çıkarır. | G5 |
| B-28 | **Medya karşılaştırma paneli** | MVP'deki framing panelinin genişlemesi. | G5 |
| B-29 | **Çoklu platform uyarlaması** (Threads, Bluesky, Instagram, YouTube, Telegram, newsletter, blog) | Dağıtım katmanı; Core Loop'a hizmet etmiyor. | G5 |
| B-30 | **Team Workspace (B2B)** | Farklı ICP, farklı yetki modeli, farklı fiyatlandırma. | G5 + ≥3 kurumsal talep sinyali |
| B-31 | **Genel API + webhook + özel kaynak entegrasyonu** | Platform katmanı. | B-30 |
| B-32 | **Mobil uygulama** | Önce PWA; yerel uygulama ancak talep doğrulanırsa. | G5 + mobil kullanım oranı > %30 |

---

## Kapsam dışı — hiçbir fazda geliştirilmez

Bunlar backlog kalemi **değildir**; ürün sözleşmesinin (Spec §15) parçasıdır.
Buraya taşınmaları teklif edilemez.

| Yasak | Zorlama mekanizması |
|---|---|
| Siyasi kampanya araçları | Ürün sözleşmesi (Spec §15, Faz 6 sınırı) |
| Seçmen segmentasyonu / kitle hedefleme | Kitle/segment veri modeli şemada yok |
| Koordineli yayın / trend manipülasyonu | Toplu yayın API'si yok |
| Kullanıcının siyasi ideolojisini sınıflandırmak | `editorial_profiles`'ta alan yok; `tests/test_schema.py` denetler |
| Kaynağa siyasi konum etiketi vermek | Framing dili; şemada `bias` alanı yok |
| İnsan onayı olmadan yayın | Otomatik yayın kod yolu mevcut değil (P5) |
| Sahte hesap/persona | Tek kullanıcı–tek hesap modeli |
| Toplu izinsiz scraping | `tos_status='forbidden'` kaynaktan ingestion kod seviyesinde engelli |
| Tek sayısal "doğruluk yüzdesi" | Şemada alan yok; `tests/test_schema.py` denetler |

---

## Faz 0'da açılan kalemler

Yol haritasında olmayan, uygulama sırasında ortaya çıkan işler:

| # | Kalem | Kaynak | Faz |
|---|---|---|---|
| ~~B-33~~ | ~~Spec §8.3'te R1/R8 sıra çelişkisinin düzeltilmesi~~ | İtiraz-4 | ✅ **Kapandı** — Spec v3.1 §8.3 (R8 → R0, kısa devre) |
| ~~B-34~~ | ~~Salience'ın global (0–90) + kişisel (0–10) olarak ayrılması~~ | İtiraz-7 | ✅ **Kapandı** — Spec v3.1 §8.4 + `migrations/0003`; uygulaması F2-15 |
| ~~B-35~~ | ~~G0 koşul 8 / G4 koşul 7'nin ölçek belirtecek şekilde yeniden yazılması~~ | İtiraz-1 | ✅ **Kapandı** — G0 #8a/#8b, G4 #7a/#7b |
| ~~B-36~~ | ~~§11.5 sıcaklık disiplininin `effort` karşılığıyla güncellenmesi~~ | İtiraz-3 | ✅ **Kapandı** — Spec v3.1 §11.5 |
| ~~B-37~~ | ~~`evidence_status` dağılımının eval çıktısına eklenmesi~~ | İtiraz-2 | ✅ **Kapandı** — `eval/run.py` dağılımı ve %10 eşiği raporluyor |
| ~~B-38~~ | ~~Embedding'in telif/KVKK statüsü~~ | İtiraz-5 | ⛔ **KAPSAM DIŞI** — kişisel araç |
| ~~B-39~~ | ~~"Kanıtsız olayda üretim engeli"nin Spec §14.1 kapsam listesine eklenmesi~~ | İtiraz-5 kozmetik notu | ✅ **Kapandı** — Spec v3.1 §14.1 kalem 15 |
| ~~B-40~~ | ~~mypy'nin CI'da `continue-on-error` olmaktan çıkarılması~~ | `.github/workflows/ci.yml` | ✅ **Kapandı** — 92 hata temizlendi (`Connection[DictRow]`, `fetch_one`, `TokenUsage`); CI adımı artık zorunlu |
| ~~B-41~~ | ~~`politikdesk/eval/` boş paketinin kaldırılması~~ | Faz 0 uygulaması | ✅ **Kapandı** — kullanıcı onayıyla silindi |
| B-42 | TÜİK bülten listesinin JSON ucunun bulunması (sayfa JS ile yükleniyor) | Faz 1 canlı koşum | 🔴 **KİMLİK BİLGİSİ GEREKİYOR** — 13 Ağu 2026 teşhizi: veriportali React SPA, klasik sitede de sunucu tarafı liste yok (`/Bulten/Index` → 404). Veri servisi `nsiws.tuik.gov.tr/rest/...` (SDMX) **Bearer belirteç** istiyor; belirteç `giris.tuik.gov.tr` (Keycloak) hesabından alınır. **Kullanıcı kararı:** TÜİK hesabı açılsın mı? |
| ~~B-43~~ | ~~Hazine duyuru akışının bulunması~~ | Faz 1 canlı koşum | ✅ **Kapandı (13 Ağu 2026)** — duyuru sayfası React SPA'ymış; besleyen uç bir **WordPress REST** koleksiyonu: `/portal/v2/posts`. Yeni `wp_rest` adaptörü + 7 test. Canlı: 20 çekildi, **5 saklandı**, 0 hata. `robots.txt` `Disallow:` (boş) |
| B-44 | Resmî Gazete `/rss` bağlantı reddinin çözülmesi | Faz 1 canlı koşum | 🔴 **AĞ DÜZEYİNDE ENGEL** — "bot filtresi" tahmini **yanlıştı**. DNS ve TCP 443 açılıyor, sunucu ClientHello'dan sonra düşürüyor. TLS 1.2 sabitleme / SECLEVEL=1 / eski yeniden anlaşma / doğrulama kapatma / www'suz alan / iki ayrı TLS yığını — hepsi aynı noktada düşüyor. **HTTP katmanına hiç ulaşılmıyor**, UA veya robots ile ilgisi yok. Farklı çıkış IP'si (TR) gerektirir |
| B-45 | Reuters'ın düşmesiyle boşalan uluslararası çapraz teyit rolü | Faz 0 F0-08 | Faz 2 sonrası — G2 ölçümüne bağlı |
| B-46 | Konu filtresinin yanlış-negatif oranının Golden Set ile ölçülmesi | Faz 1: 116 öğenin 106'sı elendi | Faz 2 (F2-16) |
| ~~B-47~~ | ~~D16: barındırılan adayın (voyage-3) koşulması~~ | `docs/embedding-benchmark.md` | ✅ **Kapandı** — voyage-3 koşuldu, zor AUC 0,782 ile elendi |
| ~~B-48~~ | ~~D16 eleme ölçütünün yeniden yazılması~~ | Tanı koşumu | ✅ **Kapandı** — ölçüt düzeltildi, yazılı gerekçe `docs/embedding-benchmark.md`'de |
| ~~B-49~~ | ~~Yol Haritası G2 yedek planı 3. maddesinin düzeltilmesi~~ | `docs/embedding-benchmark.md` | ✅ **Kapandı** — Yol Haritası G2 yedek planı madde 3'te ⚠️ uyarısı mevcut |
| ~~B-50~~ | ~~`query: ` önekinin üretim embedder'ına eklenmesi~~ | `nlp/embedder.py` | ✅ **Kapandı** — `MODEL_TEXT_PREFIXES` + iki tarafın aynı kaldığını denetleyen test |
| B-51 | Olay başlığının LLM ile üretilmesi (şu an tohum makalenin başlığı) | F2-01 uygulaması | Faz 3 — `ANTHROPIC_API_KEY` bekliyor |
| B-52 | `numeric_guard` metrik sözlüğünün yanlış-pozitif oranının ölçülmesi | F2-03 uygulaması | Faz 3 — 300 makalelik set bekliyor |
| B-57 | Golden Set'in 300 makale + 150 iddiaya çıkarılması | F2-20 kısmi (55 + 24) | **Faz 3 — açık**, G2 koşul 3 buna bağlı |
| ~~B-58~~ | ~~İddia çıkarımının canlı LLM ile koşulması (G2 koşul 5)~~ | `ANTHROPIC_API_KEY` yok | ✅ **Kapandı** — `openai_compat` arka ucu + D17 modeli ile koşuldu: 9 olay, 4 iddia, 4 kanıt bağı, **0 hata**. F2-07'nin *sayısal* %90 DoD'si Golden Set hacmine bağlı kaldı (B-57) |
| B-67 | **Sağlayıcı karşılaştırması:** aynı Golden Set üzerinde Claude ile açık modelin karşılaştırılması | `ANTHROPIC_API_KEY` `.env`'de **boş**; 13 Ağu'da denendi, 18/18 çağrı `LLMNotConfigured` | **Faz 4 — açık**, anahtar geldiğinde tek komut (çıkarım *ve* üretim) |
| B-68 | Ücretsiz katman kotasının/hız sınırının günlük tura yetip yetmediğinin ölçülmesi | Kıyaslamada 3 model kapasiteden düştü | **Faz 3 — açık** |
| B-69 | **Metrik seçim doğruluğunun ölçülmesi:** doğrulama `metric`'in listede olduğunu denetliyor, DOĞRU olduğunu denetlemiyor | Canlı koşum: AR-GE harcaması `reserves` kodlanmıştı (claims.v2 ile `other`'a düzeldi) | **Faz 3 — açık**, F2-03 `numeric_guard` yanlış kodla ilgisiz sayıları çelişki sayabilir (B-52 ile birlikte) |
| ~~B-70~~ | ~~Mevcut 4 iddianın `claims.v2` ile yeniden çıkarılması~~ | Karışık prompt sürümü | ✅ **Kapandı** — kullanıcı onayıyla koşuldu (13 Ağu). 4 iddia silindi, claims.v2 ile 2 iddia + 2 kanıt bağı, 0 hata. Araç: `make reclaim` (`--yes` zorunlu) |
| ~~B-71~~ | ~~Üretim modelinin kendi ölçümüyle seçilmesi~~ | D17 yalnız *çıkarım* görevini ölçtü | 🟡 **Kapandı ama karar ZAYIF** — D18 (`docs/llm-generation-benchmark.md`): `nemotron-3-super`. Ölçüm ilk iki adayı ayıramadı; karar gecikmeye ve operasyonel tekliğe dayanıyor. Araç: `make genbench` |
| B-59 | Haftalık kalite ritüeli (F2-21, ≥3 hafta) | Takvim zamanı gerektirir | **Faz 3 boyunca** |
| B-60 | `event_relations`'ta `updates` / `contradicts` ilişkileri | F2-17 yalnız `same_thread` kuruyor (yargı içermeyen tek tip) | Faz 3 |
| B-61 | Takvimin `verified: false` kayıtlarının resmî takvimden teyidi | `config/calendar_2026.yml` — 10 kayıt | Faz 3 |
| ~~B-53~~ | ~~Mevcut makalelerin e5 ile yeniden embed edilmesi + kümelemenin tekrar koşulması~~ | D16 kararı | ✅ **Kapandı** — `ingest reembed --yes` aracı + koşuldu. 11 makale e5 ile gömüldü, 9 olay, 1 `same_thread`. **Koşum gizli bir hata ortaya çıkardı → B-65** |
| ~~B-54~~ | ~~Worker konteynerine `embed-local` ekstrası~~ | D16 self-host seçimi | ✅ **Kapandı** — `Dockerfile` `ARG PD_EXTRAS` + CPU torch indeksi; compose'da yalnız worker kurar; `hfcache` volume. Konteynerde doğrulandı: `local`, üretime uygun, 1024 boyut |
| B-55 | Spec §11.4'e varlık kısıtının **boş küme** davranışının yazılması (`ok`/`inconclusive`/`reject`) | Faz 2 canlı koşum: 11 makalenin 6'sı varlıksız | Bir sonraki spec sürümü (v3.2) |
| ~~B-56~~ | ~~Varlık sözlüğü kapsamının genişletilmesi (bakanlıklar, kurullar)~~ | %38 varlıksız oran | ✅ **Kapandı** — 20 → 48 kurum; varlıksız %38 → %29. ⚠️ **Kümeleme metriklerini değiştirmedi**; precision açığının kök nedeni bu değilmiş (bkz. B-62 ve `docs/FAZ2-DURUM.md` bulgu 3) |

| B-62 | **Gösterge (metrik) ayırıcısı:** aynı kurumun aynı gün yayımladığı farklı göstergeler ayrı olay sayılmalı | `docs/FAZ2-DURUM.md` bulgu 3 — kalan precision açığının tamamı bu | **Faz 3 — açık**, G2 koşul 1'e bağlı |
| B-63 | Kaynağın kendisinin varlık sinyali sayılması (TÜİK bülteni metinde "TÜİK" demese de TÜİK varlığı almalı) | B-56 sonrası kalan 16 varliksiz makalenin çoğu bu ailede | Faz 3 — Spec §11.4 `varlik_ok` semantiğini değiştirir, **v3.2 gerektirir** |
| ~~B-65~~ | ~~`same_thread` eşiğinin (0,80) F2-14 kalibrasyonundan sonra güncellenmemesi~~ | B-53 canlı koşumu: 9 olay **22** bağ üretti | ✅ **Kapandı** — eşik `cluster_t_high`'tan türetiliyor; 22 → 1 bağ; değişmez teste bağlandı |
| B-66 | Faz 4 kapsam kararının Spec'e işlenmesi (§14.1 kapsam listesi + G4 → G4′) | Yol Haritası Faz 4 daraltıldı | Spec v3.2 |
| B-64 | `.env.example` satır sonu yorumlarının genel taranması | `PD_EMBEDDING_PROVIDER` tuzağı: boş değer + satır sonu yorumu = yorum değer olur | ✅ **Kapandı** — yorumlar kendi satırına alındı + `Settings` doğrulaması + 3 test |

---

## Faz 3'te açılan kalemler

| # | Kalem | Kaynak | Faz |
|---|---|---|---|
| B-72 | **Spec §15 madde 10'un tahmin muafiyeti Spec'e işlenmeli.** Harfiyen uygulanınca R0 gereği *her* tahmin `unverified` olduğu için üretim her olayda bloke oluyordu. Uygulanan kural: tahmin tipi muaf — madde 10'un koruduğu şey "belirli kişilere yönelik SUÇLAMA"dır, bir kişinin kendi tahmininin aktarılması değil | F3-11 uygulaması (`editorial/guards.py`) | **Spec v3.2** |
| B-73 | **Golden Set kanıt metinleri noktalamasız.** 43 kanıt metninin 43'ünde de virgül yok (`4 milyar 918 2 milyon`). Sayısal grounding bu fikstür üzerinde ölçülemez: modelin doğru okuması (`918,2`) uydurma sayılıyor | B-71 koşumu, `docs/llm-generation-benchmark.md` bulgu 2 | **Faz 4 — açık**, G3 #2 ölçümünü açar |
| B-74 | **B-71'in temiz fikstürle yeniden ölçülmesi.** Mevcut karar (D18) zayıf: kirlenmemiş olaylarda dört adayın da grounding'i %100 ve ölçüm ayırt edemedi | D18 kapsam sınırı | **Faz 4**, B-73'e bağlı |
| B-75 | **G3 #2/#3 denetimi (50 + 40 taslak).** Veritabanında iddiası olan tek olay var; kapı bu boyutta karara bağlanamaz | Kapı G3 ölçümü | **Faz 4**, B-57'ye bağlı |
| B-76 | **Brifing 7 gün üst üste (G3 #5).** `beat` zamanlaması kuruldu (08:00/20:00, TZ=Europe/Istanbul); takvim zamanı gerektirir | Kapı G3 koşul 5 | **Faz 4 boyunca** |

---

## Faz 3 sonrası denetimde açılan kalemler (13 Ağustos 2026)

| # | Kalem | Kaynak | Faz |
|---|---|---|---|
| ~~B-77~~ | ~~**Bayat imaj arızası.** `pd-beat` Faz 1, `pd-worker` Faz 2 imajıyla koşuyordu; 13 zamanlanmış görevin 5'i vardı. Kümeleme/iddia/kanıt/brifing/metrik hiç koşmadı, 29 makalenin **18'i askıda kaldı**~~ | Faz 3 sonrası denetim | ✅ **Kapandı** — `--build` ile yeniden kuruldu; `make workers`, `make deploy-check`, `scripts/check_deployment.py` (kaymayı kanıtlı yakalıyor), `tests/test_tasks.py` (4 test) |
| B-78 | **Sessiz kopma alarmı.** Boru hattı bir adımda dursa kimse fark etmiyor. Kaynak sağlığı izleniyor ama *aşama* sağlığı izlenmiyor: "24 saattir kümelenmemiş makale var" gibi bir eşik yok | B-77'nin kök nedeni | **Faz 4 — F4-05 kapsamında** |
| B-80 | **`source_fetch_log.succeeded` yanıltıcı.** Adaptörler istisnayı içeride yutup `[]` döndürüyor; `Pipeline.run_source` istisna görmediği için kaydı `succeeded=true, 0 öğe` yazıyor. Resmî Gazete'nin TLS hatası logda "başarılı" görünüyor. Sağlık panosu bunu telafi ediyor (0 öğe → kırmızı), yani ürün yanılmıyor — ama **ham kayıt yanlış**. Düzeltme sütunun anlamını değiştirir, mevcut satırları da etkiler | Faz 3 sonrası denetim | **Faz 4 — F4-05 ile birlikte** |
| B-79 | **`diversity_ratio` = 1,0.** Her iddia `single_source` (R5) veya `unverified` (R0); tek bir `corroborated` yok. Kök neden çapraz teyit edecek bağımsız kaynak yokluğu — 4 T1 kaynağın 2'si hâlâ ölü (B-42, B-44) | Faz 3 sonrası denetim; G4′ #4 hedefi ≥ 2,5 | **Faz 4 — açık**, B-42/B-44'e bağlı |

---

## Haftalık kapsam kontrolü

> *"Bu hafta yaptığım işlerin kaçı görev listesindeydi?"*
>
> İki hafta üst üste %70'in altındaysa kapsam kontrolden çıkmıştır; durulur
> ve plan gözden geçirilir. (Yol Haritası §5)

| Hafta | Listede olan | Toplam | Oran | Not |
|---|---|---|---|---|
| W1 | | | | |
