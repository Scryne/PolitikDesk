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
| B-37 | Golden Set üzerinde `evidence_status` dağılımının eval çıktısına eklenmesi | İtiraz-2 | Faz 2 (F2-16) |
| ~~B-38~~ | ~~Embedding'in telif/KVKK statüsü~~ | İtiraz-5 | ⛔ **KAPSAM DIŞI** — kişisel araç |
| ~~B-39~~ | ~~"Kanıtsız olayda üretim engeli"nin Spec §14.1 kapsam listesine eklenmesi~~ | İtiraz-5 kozmetik notu | ✅ **Kapandı** — Spec v3.1 §14.1 kalem 15 |
| B-40 | mypy'nin CI'da `continue-on-error` olmaktan çıkarılması | `.github/workflows/ci.yml` | Faz 1 |
| B-41 | `politikdesk/eval/` boş paketinin kaldırılması (ölçüm eserleri kök `eval/` altında) | Faz 0 uygulaması | Faz 1 |
| B-42 | TÜİK bülten listesinin JSON ucunun bulunması (sayfa JS ile yükleniyor) | Faz 1 canlı koşum | **Faz 1 — açık** |
| B-43 | Hazine duyuru akışının bulunması | Faz 1 canlı koşum | **Faz 1 — açık** |
| B-44 | Resmî Gazete `/rss` bağlantı reddinin çözülmesi (bot filtresi?) | Faz 1 canlı koşum | **Faz 1 — açık** |
| B-45 | Reuters'ın düşmesiyle boşalan uluslararası çapraz teyit rolü | Faz 0 F0-08 | Faz 2 sonrası — G2 ölçümüne bağlı |
| B-46 | Konu filtresinin yanlış-negatif oranının Golden Set ile ölçülmesi | Faz 1: 116 öğenin 106'sı elendi | Faz 2 (F2-16) |
| ~~B-47~~ | ~~D16: barındırılan adayın (voyage-3) koşulması~~ | `docs/embedding-benchmark.md` | ✅ **Kapandı** — voyage-3 koşuldu, zor AUC 0,782 ile elendi |
| ~~B-48~~ | ~~D16 eleme ölçütünün yeniden yazılması~~ | Tanı koşumu | ✅ **Kapandı** — ölçüt düzeltildi, yazılı gerekçe `docs/embedding-benchmark.md`'de |
| B-49 | Yol Haritası G2 yedek planı 3. maddesinin düzeltilmesi: hibrit skorlama şablonlu resmî duyuru ailesini **kötüleştirir** | `docs/embedding-benchmark.md` | Faz 2 (B-48 ile birlikte) |
| ~~B-50~~ | ~~`query: ` önekinin üretim embedder'ına eklenmesi~~ | `nlp/embedder.py` | ✅ **Kapandı** — `MODEL_TEXT_PREFIXES` + iki tarafın aynı kaldığını denetleyen test |
| B-51 | Olay başlığının LLM ile üretilmesi (şu an tohum makalenin başlığı) | F2-01 uygulaması | Faz 2 (F2-06 sonrası) |
| B-52 | `numeric_guard` metrik sözlüğünün Golden Set ile yanlış-pozitif oranının ölçülmesi | F2-03 uygulaması | Faz 2 (F2-16) |
| B-53 | Mevcut makalelerin e5 ile yeniden embed edilmesi + kümelemenin tekrar koşulması | D16 kararı | **Faz 2 — açık** |
| B-54 | Worker konteynerine `embed-local` ekstrası (torch + sentence-transformers, ~2,5 GB) | D16 self-host seçimi | **Faz 2 — açık** |
| B-55 | Spec §11.4'e varlık kısıtının **boş küme** davranışının yazılması (`ok`/`inconclusive`/`reject`) | Faz 2 canlı koşum: 11 makalenin 6'sı varlıksız | Bir sonraki spec sürümü (v3.2) |
| B-56 | Varlık sözlüğü kapsamının genişletilmesi (bakanlıklar, kurullar) | %55 varlıksız oran `inconclusive` yolunu aşırı yüklüyor | Faz 2 |

---

## Haftalık kapsam kontrolü

> *"Bu hafta yaptığım işlerin kaçı görev listesindeydi?"*
>
> İki hafta üst üste %70'in altındaysa kapsam kontrolden çıkmıştır; durulur
> ve plan gözden geçirilir. (Yol Haritası §5)

| Hafta | Listede olan | Toplam | Oran | Not |
|---|---|---|---|---|
| W1 | | | | |
