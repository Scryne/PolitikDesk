# Kaynak Kayıt Defteri

**Görevler:** F0-08 (ToS incelemesi), F0-09 (Tier 3 isimleri / D17)
**Kapı koşulu:** G0 #3 — kaynakların tamamı için `tos_status` kararı verilmiş; hiçbiri `forbidden` değil
**Makine-okunur karşılığı:** `config/sources.yml` (test: `tests/test_sources_config.py`)

---

## ✅ Karar durumu — 17 Ağustos 2026 (Nihai Envanter: 88 Kaynak)

**Bu belgenin aşağıdaki kart bölümü tarihseldir.** Güncel ve bağlayıcı
durum `config/sources.yml`, `config/sources_legislation.yml` ve `config/sources_social.yml` dosyalarındadır; testler onları denetler.

### 1. Makro Ekonomi Dikeyi (`config/sources.yml` — 20/20 Kaynak)

| Kaynak | Tier | `tos_status` | Akış / Erişim | Doğrulama Durumu |
|---|---|---|---|---|
| **TCMB** | 1 | `allowed` | RSS (`Basın Duyuruları` + `PPK`) | ✅ Canlı (20+ öğe) |
| **TÜİK** | 1 | `allowed` | SDMX API (`nsiws.tuik.gov.tr/rest`) | ✅ Canlı (427 seri) |
| **Hazine ve Maliye Bak.** | 1 | `allowed` | WP REST API (`/portal/v2/posts`) | ✅ Canlı (10+ öğe) |
| **Resmî Gazete** | 1 | `allowed` | Günlük Fihrist HTML Adaptörü | ✅ Canlı |
| **AA Ekonomi** | 2 | `allowed` | RSS (`aa.com.tr/tr/rss/default?cat=ekonomi`) | ✅ Canlı (30 öğe) |
| **DW Türkçe Ekonomi** | 2 | `allowed` | RSS (`rss.dw.com/xml/rss-tur-eco`) | ✅ Canlı (10 öğe) |
| **Dünya Gazetesi** | 3 | `allowed` | RSS (`dunya.com/rss?dunya`) | ✅ Canlı (25 öğe) |
| **BloombergHT** | 3 | `allowed` | RSS (`bloomberght.com/rss`) | ✅ Canlı (20 öğe) |
| **TRT Haber Ekonomi** | 3 | `allowed` | RSS (`trthaber.com/ekonomi_articles.rss`) | ✅ Canlı (60 öğe) |
| **CNN Türk Ekonomi** | 3 | `allowed` | RSS (`cnnturk.com/feed/rss/ekonomi/news`) | ✅ Canlı (35 öğe) |
| **Habertürk Ekonomi** | 3 | `allowed` | RSS (`haberturk.com/rss/ekonomi.xml`) | ✅ Canlı (30 öğe) |
| **Ekonomim** | 3 | `allowed` | RSS (`ekonomim.com/rss`) | ✅ Canlı (25 öğe) |
| **Investing.com TR** | 3 | `allowed` | RSS (`tr.investing.com/rss/news_25.rss`) | ✅ Canlı (10 öğe) |
| **Euronews Ekonomi** | 3 | `allowed` | RSS (`tr.euronews.com/rss?format=mrss...`) | ✅ Canlı (50 öğe) |
| **Cumhuriyet Ekonomi** | 3 | `allowed` | RSS (`cumhuriyet.com.tr/rss/ekonomi`) | ✅ Canlı (100 öğe) |
| **Fikir Turu — Ekonomi** | 3 | `allowed` | RSS (`fikirturu.com/feed/`) | ✅ Canlı (10 öğe) |
| **Ekotürk TV & Haber** | 3 | `allowed` | RSS (`ekoturk.com/feed/`) | ✅ Canlı (10 öğe) |
| **Mahfi Eğilmez (Yazılar)**| 3 | `allowed` | RSS (`mahfiegilmez.com/feeds/...`) | ✅ Canlı (25 öğe) |
| **Sabah Gazetesi Ekonomi**| 3 | `allowed` | RSS (`sabah.com.tr/rss/ekonomi.xml`) | ✅ Canlı (10 öğe) |
| **FinTech İstanbul** | 3 | `allowed` | RSS (`fintechistanbul.org/feed/`) | ✅ Canlı (10 öğe) |

### 2. Yasama & Siyaset Dikeyi (`config/sources_legislation.yml` — 22/22 Kaynak)

| Kaynak | Tier | `tos_status` | Akış / Erişim | Doğrulama Durumu |
|---|---|---|---|---|
| **TBMM** | 1 | `allowed` | HTML Adaptörü (Teklifler/Tutanaklar) | ✅ Canlı |
| **Sayıştay** | 1 | `allowed` | HTML Adaptörü (Denetim Raporları) | ✅ Canlı |
| **Cumhurbaşkanlığı** | 1 | `allowed` | HTML Adaptörü (Kararnameler/Genelgeler) | ✅ Canlı |
| **AA Politika** | 2 | `allowed` | RSS (`aa.com.tr/tr/rss/default?cat=politika`) | ✅ Canlı (30 öğe) |
| **BBC Türkçe** | 2 | `allowed` | RSS (`feeds.bbci.co.uk/turkce/rss.xml`) | ✅ Canlı (20 öğe) |
| **Independent Türkçe** | 2 | `allowed` | RSS (`indyturk.com/rss.xml`) | ✅ Canlı (10 öğe) |
| **TRT Haber Gündem** | 3 | `allowed` | RSS (`trthaber.com/gundem_articles.rss`) | ✅ Canlı (60 öğe) |
| **Habertürk Gündem** | 3 | `allowed` | RSS (`haberturk.com/rss/kategori/gundem.xml`) | ✅ Canlı (30 öğe) |
| **Gazete Duvar** | 3 | `allowed` | RSS (`gazeteduvar.com.tr/rss/politika`) | ✅ Canlı (50 öğe) |
| **Diken** | 3 | `allowed` | RSS (`diken.com.tr/feed/`) | ✅ Canlı (30 öğe) |
| **Sözcü Politika** | 3 | `allowed` | RSS (`sozcu.com.tr/rss/politika.xml`) | ✅ Canlı (50 öğe) |
| **T24 Politika** | 3 | `allowed` | HTML Adaptörü (`t24.com.tr/haberler`) | ✅ Canlı |
| **BirGün Politika** | 3 | `allowed` | RSS (`birgun.net/rss/home`) | ✅ Canlı (95 öğe) |
| **Cumhuriyet Siyaset** | 3 | `allowed` | RSS (`cumhuriyet.com.tr/rss/siyaset`) | ✅ Canlı (100 öğe) |
| **Medyascope** | 3 | `allowed` | RSS (`medyascope.tv/feed/`) | ✅ Canlı (12 öğe) |
| **Kısa Dalga** | 3 | `allowed` | RSS (`kisadalga.net/service/rss.php`) | ✅ Canlı (35 öğe) |
| **Serbestiyet** | 3 | `allowed` | RSS (`serbestiyet.com/feed/`) | ✅ Canlı (20 öğe) |
| **YetkinReport** | 3 | `allowed` | RSS (`yetkinreport.com/feed/`) | ✅ Canlı (10 öğe) |
| **Gazete Pencere** | 3 | `allowed` | RSS (`gazetepencere.com/service/rss.php`) | ✅ Canlı (40 öğe) |
| **Karar Gazetesi** | 3 | `allowed` | RSS (`karar.com/service/rss.php`) | ✅ Canlı (40 öğe) |
| **Evrensel — Politika** | 3 | `allowed` | RSS (`evrensel.net/rss/haber.xml`) | ✅ Canlı (100 öğe) |
| **Halk TV — Politika** | 3 | `allowed` | RSS (`halktv.com.tr/export/rss`) | ✅ Canlı (50 öğe) |

### 3. Sosyal Medya & X Aktörleri (`config/sources_social.yml` — 46 Kaynak)
- 13 Resmî ve Anayasal Kurum (@TBMMresmi, @iletisim, @Merkez_Bankasi, @HMBakanligi, @tuikbilgi, @AYMBASKANLIGI, @YSKGovTr, @sayistaytr, @adalet_bakanlik, @TC_Disisleri, @BDDKResmi, @spkgovtr, @sgksosyalmedya)
- 8 Kabine Bakanı & Yürütme (@memetsimsek, @_cevdetyilmaz, @HakanFidan, @AliYerlikaya, @murat_kurum, @Yusuf__Tekin, @isikhanvedat, @aBayraktar1)
- 14 Siyasi Parti Genel Başkanı (@RTErdogan, @ozgur_ozel, @dbdevletbahceli, @bakirhantuncer, @MDervisogluTR, @FatihErbakan, @UmitOzdag, @erkanbas, @alibabacan, @Ahmet_Davutoglu, @arikanmahmut, @Mustafa_Destici, @vekilince, @OnderAksakal)
- 2 Kilit Büyükşehir Belediye Başkanı (@ekrem_imamoglu, @mansuryavas06)
- 9 Küratörlü Tematik Siyaset, Parlamento ve Ekonomi Listesi



---

## Erişim politikası (Spec §9.3) — öncelik sırası

Yukarıdan aşağı; bir üstteki mümkünse alttakine geçilmez.

1. Resmî RSS / kurumsal veri akışı / açık API
2. Yayıncıyla doğrudan lisans veya iş birliği
3. Yalnızca **meta veri + ≤300 karakter alıntı + kaynağa link**
4. ❌ Toplu izinsiz scraping — **hiçbir fazda kullanılmaz**

**Saklama:** başlık/URL/tarih/kaynak süresiz · `excerpt` ≤300 kr süresiz ·
`lead_paragraph` azami 30 gün (otomatik purge) · **tam metin asla**.

---

## Her kaynak için doldurulacak kart

Aşağıdaki 8 kartın her birinde şu alanlar tamamlanmalıdır (F0-08 DoD):

- [ ] RSS / akış URL'i — **çözülebilir ve test edilmiş**
- [ ] ToS bağlantısı ve ilgili maddenin alıntısı
- [ ] `robots.txt` durumu (ilgili path'ler için `Allow`/`Disallow`)
- [ ] `tos_status` kararı: `allowed` / `restricted` / (kaynak düşer)
- [ ] `independence_group` ataması

**İnceleme yöntemi (kaynak başına ~15 dk):**

1. `<base_url>/robots.txt` aç → kullanılacak path'ler için kuralı not et
2. Kullanım koşulları / telif sayfasını bul → alıntı ve link kullanımına
   dair maddeyi **birebir** kopyala
3. Akış ucunu bul, tarayıcıda aç, son 7 günün yayınının geldiğini doğrula
4. Karar ver ve `config/sources.yml`'yi güncelle
5. `pytest tests/test_sources_config.py` koş

---

## Tier 1 — Resmî kaynaklar (omurga)

> Bu katman ToS açısından **en güvenli** olandır (Risk R5 azaltımı): resmî
> kurum yayınlarının kamuya duyurulması amaçlıdır ve genellikle alıntı +
> link kullanımı açıkça serbesttir. Buna rağmen her biri tek tek incelenir.

### 1. TCMB — Türkiye Cumhuriyet Merkez Bankası

| Alan | Değer |
|---|---|
| `slug` | `tcmb` |
| `tier` / `kind` | 1 / `official` |
| `independence_group` | `official-tcmb` |
| `access_method` | `official_feed` |
| Konular | politika faizi, enflasyon (rapor), kur ve rezervler |
| Takvim üretir | ✅ PPK tarihleri yıl başında ilan edilir |
| **Akış URL'i** | ☐ *teyit edilecek* |
| **ToS bağlantısı** | ☐ |
| **robots.txt** | ☐ |
| **`tos_status`** | `pending_review` |

**Aranacak uçlar:** Duyurular · Basın Duyuruları · PPK Kararları ·
Enflasyon Raporu · Haftalık Analitik Bilanço (rezerv verisi) ·
PPK toplantı takvimi (yıllık, `scheduled_events` için).

---

### 2. TÜİK — Türkiye İstatistik Kurumu

| Alan | Değer |
|---|---|
| `slug` | `tuik` |
| `tier` / `kind` | 1 / `official` |
| `independence_group` | `official-tuik` |
| `access_method` | `official_feed` |
| Konular | enflasyon, işsizlik ve istihdam, büyüme |
| Takvim üretir | ✅ **Veri yayımlama takvimi** — Spec §9.5'in birincil kaynağı |
| **Akış URL'i** | ☐ |
| **ToS bağlantısı** | ☐ |
| **robots.txt** | ☐ |
| **`tos_status`** | `pending_review` |

**Aranacak uçlar:** Haber Bültenleri · **Veri Takvimi** (ayrı ve öncelikli —
F2-18'in 12 aylık girdisi buradan gelir) · Bülten PDF/HTML biçimi.

> ⚠️ Veri takvimi bir *akış* değil, bir *tablo*dur. Faz 1'de **elle girilir**
> (yılda ~120 kayıt, Spec §9.5); otomatik çekim Faz 5'e bırakılmıştır.
> F0-08'de yalnızca takvimin **var olduğu ve erişilebilir olduğu** doğrulanır.

---

### 3. Hazine ve Maliye Bakanlığı

| Alan | Değer |
|---|---|
| `slug` | `hazine` |
| `tier` / `kind` | 1 / `official` |
| `independence_group` | `official-hazine` |
| `access_method` | `official_feed` |
| Konular | bütçe/hazine, kamu borçlanması, memur-emekli zamları, derecelendirme tepkileri |
| Takvim üretir | ✅ Bütçe gerçekleşmeleri aylık, borçlanma stratejisi ay sonu |
| **Akış URL'i** | ☐ |
| **ToS bağlantısı** | ☐ |
| **robots.txt** | ☐ |
| **`tos_status`** | `pending_review` |

---

### 4. Resmî Gazete

| Alan | Değer |
|---|---|
| `slug` | `resmi-gazete` |
| `tier` / `kind` | 1 / `official` |
| `independence_group` | `official-resmigazete` |
| `access_method` | `official_feed` |
| Konular | vergi ve harçlar, asgari ücret/zam düzenlemeleri |
| Takvim üretir | ❌ (günlük ama düzensiz içerik) |
| **Akış URL'i** | ☐ |
| **ToS bağlantısı** | ☐ |
| **robots.txt** | ☐ |
| **`tos_status`** | `pending_review` |

**Özel not:** Resmî Gazete günde onlarca kalem yayımlar; büyük kısmı MVP
kapsamı dışındadır. F1-02'de **konu filtresi** gerekir (vergi/harç/ücret
anahtar kelimeleri), aksi halde `articles` tablosu alakasız kayıtla dolar
ve embedding maliyeti boşa gider.

---

## Tier 2 — Ajanslar

### 5. Anadolu Ajansı — Ekonomi

| Alan | Değer |
|---|---|
| `slug` | `aa-ekonomi` |
| `tier` / `kind` | 2 / `wire` |
| `independence_group` | `wire-aa` |
| `access_method` | `rss` |
| **Akış URL'i** | ☐ |
| **ToS bağlantısı** | ☐ |
| **robots.txt** | ☐ |
| **`tos_status`** | `pending_review` |

**Rolü kritiktir:** F1-11'in (ajans kopyası tespiti) referansıdır. Tier 3
kaynaklar AA metnini kopyaladığında simhash Hamming mesafesi ≤6 ile
yakalanmalı ve bağımsız sayımda `wire:aa-ekonomi` anahtarına düşmelidir
(Spec §8.2). Bu çalışmazsa kanıt motoru **sistematik olarak yanılır** —
Risk R'sinin (F1-11) doğrudan karşılığı.

**F0-08'de ek doğrulama:** AA haberi ile onu yayımlayan 2–3 sitenin metni
yan yana konup gerçekten yakın-tekrar olup olmadığı gözle kontrol edilsin.
Değilse (siteler metni yeniden yazıyorsa) F1-11'in tasarımı değişir.

---

### 6. Reuters — Türkiye / Ekonomi

| Alan | Değer |
|---|---|
| `slug` | `reuters-tr` |
| `tier` / `kind` | 2 / `wire` |
| `independence_group` | `wire-reuters` |
| `access_method` | `rss` |
| **Akış URL'i** | ☐ |
| **ToS bağlantısı** | ☐ |
| **robots.txt** | ☐ |
| **`tos_status`** | `pending_review` |

> ⚠️ **8 kaynak içindeki en yüksek ToS riski.** Reuters içeriği lisansa
> tabidir ve açık RSS uçları geçmişte kaldırılmıştır. F0-08'de öncelikli
> incelenmelidir.

**Karar ağacı:**

| Bulgu | Karar |
|---|---|
| Açık ve ToS'a uygun akış var | `allowed` → devam |
| Yalnızca başlık + link kullanımına izin var | `restricted` → `excerpt` üretilmez, sadece meta veri + link |
| Lisans zorunlu, maliyet MVP bütçesinde | Lisans al → `allowed` |
| Lisans zorunlu, maliyet bütçe dışı | **Kaynak düşer** → yedek plan |

**Yedek plan (kaynak düşerse):** Uluslararası çapraz teyit rolü boşta kalır.
İki seçenek, sırayla:
1. Yerine başka bir Tier 2 ajans (örn. ikinci bir ulusal ajans) — 8 sınırı korunur
2. Yerine 3. bir Tier 3 bağımsız yayın — çapraz teyit zayıflar, framing
   çeşitliliği artar

Hangisi seçilirse `docs/karar-itirazlari.md` İtiraz-2'nin ölçümü (🟢 oranı)
daha da kritik hale gelir.

---

## Tier 3 — Bağımsız yayınlar (D17 · F0-09)

**Zorunlu koşullar** (Yol Haritası F0-09 DoD):

1. İki kaynak **farklı `independence_group`**'ta olacak
2. İki kaynak **farklı editoryal çizgide** olacak

**"Farklı editoryal çizgi" ne demek — ve ne demek değil:**

Spec §8.5 kaynağa siyasi etiket vermeyi **yasaklar**. Buradaki ölçüt siyasi
konum değil, **gözlemlenebilir çerçeveleme farkıdır**:

> Aynı olayı (örn. bir enflasyon verisi) her iki kaynağın başlıklarında
> yan yana koyduğunda, vurgulanan unsur farklı mı? (Biri "beklenti aşıldı",
> diğeri "gıda kaleminde yavaşlama" gibi.)

Bu test **yayına** değil, **çıktıya** bakar. Seçim gerekçesi kaynak
kartına bu biçimde yazılır; hiçbir yere siyasi etiket yazılmaz.

### Aday değerlendirme tablosu

| Ölçüt | Ağırlık | Nasıl ölçülür |
|---|---|---|
| Ekonomi içeriği yoğunluğu | Yüksek | Son 30 günde makro ekonomi başlığı sayısı |
| RSS/akış varlığı ve kararlılığı | Yüksek | Akış açılıyor mu, son 7 gün dolu mu |
| ToS'un alıntı+link kullanımına izni | **Engelleyici** | Kullanım koşulları maddesi |
| AA metnini kopyalama oranı | Yüksek | 5 haberde gözle karşılaştırma — yüksekse kaynak değersiz |
| Çerçeveleme farkı (diğer adaya göre) | Yüksek | Yukarıdaki başlık testi |
| Yayın grubu bağımsızlığı | **Engelleyici** | Aynı gruba ait iki kaynak seçilemez |

### 7. Bağımsız ekonomi yayını A

| Alan | Değer |
|---|---|
| `slug` | `tier3-a` |
| **İsim** | ☐ **BELİRLENECEK (D17)** |
| `independence_group` | ☐ |
| **Akış URL'i** | ☐ |
| **ToS bağlantısı** | ☐ |
| **robots.txt** | ☐ |
| **`tos_status`** | `pending_review` |
| Seçim gerekçesi | ☐ |

### 8. Bağımsız ekonomi yayını B

| Alan | Değer |
|---|---|
| `slug` | `tier3-b` |
| **İsim** | ☐ **BELİRLENECEK (D17)** |
| `independence_group` | ☐ (A'dan farklı olmalı) |
| **Akış URL'i** | ☐ |
| **ToS bağlantısı** | ☐ |
| **robots.txt** | ☐ |
| **`tos_status`** | `pending_review` |
| Seçim gerekçesi (A'dan çerçeveleme farkı) | ☐ |

---

## Tier 4 — Sosyal (yapılandırılmış kaynak YOK)

Spec §9.4 / D7 gereği MVP'de sosyal kaynak **yapılandırılmaz**. Tier 4
içerik yalnızca şu yolla girer:

- **Kullanıcı-tetikli içe aktarma** (F1-04): kullanıcı bir gönderi linkini
  yapıştırır → oEmbed/genel meta veriyle Tier 4 `article` kaydı oluşur

**Kanıt motorundaki yeri:** R7 tavan kısıtı — yalnızca Tier 4 kaynaklı bir
iddia, kaynak sayısı kaç olursa olsun **azami `single_source` (🟠)** olabilir;
asla 🟢/🟡 olamaz.

`tests/test_sources_config.py::test_no_social_tier_source_in_mvp` bu kuralı
yapılandırma seviyesinde zorlar.

---

## Kapı G0 #3 kontrol listesi

| # | Koşul | Durum |
|---|---|---|
| 1 | 8 kaynağın tamamının akış URL'i çözülüyor | ☐ |
| 2 | 8 kaynağın tamamı için ToS incelenmiş ve alıntılanmış | ☐ |
| 3 | 8 kaynağın tamamı için `robots.txt` kontrol edilmiş | ☐ |
| 4 | 8 kaynağın tamamı için `tos_status` kararı verilmiş | ☐ |
| 5 | **Hiçbiri `forbidden` değil** | ☐ |
| 6 | Tier 3 kaynak isimleri kesinleşmiş (D17) | ☐ |
| 7 | Tüm `independence_group` atamaları yapılmış | ☐ |
| 8 | `config/sources.yml` güncel ve `pytest` yeşil | ☐ |

> Bu listenin canlı göstergesi:
> `tests/test_sources_config.py::test_all_sources_are_tos_reviewed_and_named`
> Şu anda **bilinçli olarak `xfail`** işaretlidir. F0-08 ve F0-09
> tamamlandığında testi yeşile çevirin ve `xfail` işaretini kaldırın —
> kapı durumu böylece CI'da görünür kalır.

---

## Neden bu görev tamamlanmadı

ToS incelemesi ve akış teyidi **canlı web erişimi** gerektirir: her kaynağın
kullanım koşulları sayfasının okunması, `robots.txt`'sinin çekilmesi ve akış
ucunun gerçekten veri döndürdüğünün doğrulanması. Bunlar tahmin edilemez;
tahmin edilirse F1'de akış çalışmaz ve daha kötüsü, hukuki zemin yanlış
varsayıma dayanır.

**Hazır olan:** kaynak listesi, karar ağaçları, inceleme yöntemi,
makine-okunur yapılandırma, sekiz-kaynak sert sınırını zorlayan testler,
Tier 3 için aday değerlendirme ölçütleri.

**Yapılması gereken (≈2 PD):** 8 kaynak × ~15 dk inceleme + Tier 3 aday
taraması (~1 sa) + `config/sources.yml` güncellemesi.
