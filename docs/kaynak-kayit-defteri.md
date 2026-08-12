# Kaynak Kayıt Defteri

**Görevler:** F0-08 (ToS incelemesi), F0-09 (Tier 3 isimleri / D17)
**Kapı koşulu:** G0 #3 — kaynakların tamamı için `tos_status` kararı verilmiş; hiçbiri `forbidden` değil
**Makine-okunur karşılığı:** `config/sources.yml` (test: `tests/test_sources_config.py`)

---

## ✅ Karar durumu — 12 Ağustos 2026

**Bu belgenin aşağıdaki kart bölümü tarihseldir.** Güncel ve bağlayıcı
durum `config/sources.yml` dosyasındadır; testler onu denetler.

| Kaynak | Tier | `tos_status` | Akış | Doğrulama |
|---|---|---|---|---|
| TCMB | 1 | `allowed` | RSS (2 akış: Basın Duyuruları + PPK) | ✅ canlı, 41 öğe |
| TÜİK | 1 | `allowed` | ❌ RSS yok, liste JS ile yükleniyor | 🔎 B-42 |
| Hazine | 1 | `allowed` | ❌ aday yollar sonuç vermedi | 🔎 B-43 |
| Resmî Gazete | 1 | `allowed` | `/rss` var ama bağlantı reddediliyor | 🔎 B-44 |
| AA Ekonomi | 2 | `allowed` | `aa.com.tr/tr/rss/default?cat=ekonomi` | ✅ canlı, 30 öğe |
| **Dünya Gazetesi** | 3 | `allowed` | `dunya.com/rss?dunya` | ✅ canlı, 25 öğe |
| **BloombergHT** | 3 | `allowed` | `bloomberght.com/rss` | ✅ canlı, 20 öğe |

**Reuters düşürüldü.** Açık RSS ucu yok, içerik lisansa tabi — aşağıdaki
karar ağacının "lisans zorunlu, bütçe dışı → kaynak düşer" dalı işletildi.
Kaynak sayısı 8 → **7**.

**D17 kararı (F0-09):** Dünya + BloombergHT. Farklı yayın grubu ✓,
farklı çerçeveleme ✓ (Dünya genel gündem ağırlıklı, BloombergHT
piyasa/veri ağırlıklı).

**Kalan iş:** Üç Tier 1 kaynağın akışı bulunmalı —
`python -m scripts.discover_feeds` **yerel ağdan** koşturulmalı.
Etkisi `docs/FAZ1-DURUM.md` içinde ayrıntılı.

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
