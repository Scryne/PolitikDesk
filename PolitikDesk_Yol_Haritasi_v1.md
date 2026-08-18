# PolitikDesk — Uygulama Yol Haritası
## v1.0 · Faz-Faz Görev Planı

---

| | |
|---|---|
| **Eşlik ettiği belge** | `PolitikDesk_Master_Spec_v3.md` (bundan sonra **Spec** olarak anılır) |
| **Sürüm** | 1.0 |
| **Tarih** | 11 Ağustos 2026 |
| **Kapsam** | Faz 0 (karar/doğrulama) → Faz 4 (kapalı beta) tam görev dökümü; Faz 5–6 üst düzey plan |
| **Statü** | Faz 0 başlatılabilir |

---

## 0. Planlama Varsayımları

Bu varsayımlar değişirse takvim değişir; **görev listesi ve sıra değişmez.**

| Varsayım | Değer | Değişirse etkisi |
|---|---|---|
| Ekip | 1 geliştirici (tam zamanlı) + AI kodlama asistanı | 2. geliştirici → Faz 1–3 yaklaşık %35 kısalır; frontend paralelleşir |
| Haftalık verimli kapasite | 5 PD/hafta (1 PD = 6 odaklanmış saat = 30 sa/hafta) | Yarı zamanlı (2,5 PD) → süre iki katına çıkar |
| Başlangıç | 17 Ağustos 2026, Pazartesi (W1) | Takvim kayar, hafta numaraları sabit kalır |
| Kapalı beta hedefi | W22 sonu ≈ 15 Ocak 2027 | Yıl sonu tatil payı W20'ye eklenmiştir |
| Bütçe (Faz 0–4 toplam) | ~1.500–2.500 $ (LLM + altyapı + hukuk danışmanlığı) | Hukuk danışmanlığı en büyük tek kalem |
| Dış bağımlılık | Hukuk danışmanlığı randevusu (F0-10) | Gecikirse Faz 1 başlar, **Faz 3 taslak üretimi bloke olur** |

**Efor birimi:** PD = person-day (1 kişi × 6 odaklanmış saat).
**Toplam planlanan efor (Faz 0–4):** ~108 PD / 22 hafta (≈%98 kapasite kullanımı → buffer görevleri dahil).

---

## 1. Takvim Özeti

| Faz | Hafta | Tarih (yaklaşık) | Ad | Efor | Çıktı |
|---|---|---|---|---|---|
| **Faz 0** | W1–W3 | 17 Ağu – 4 Eyl 2026 | Karar, Doğrulama, Zemin | 15 PD | Kararlar kilitli, hukuki zemin net, altyapı hazır |
| **Faz 1** | W4–W7 | 7 Eyl – 2 Eki 2026 | Veri Omurgası | 20 PD | 8 kaynaktan otomatik toplama, temiz veri, admin |
| **Faz 2** | W8–W12 | 5 Eki – 6 Kas 2026 | Olay Zekâsı | 25 PD | Kümeleme + iddia + kanıt motoru kalite kapısını geçmiş |
| **Faz 3** | W13–W17 | 9 Kas – 11 Ara 2026 | Editoryal Katman & Arayüz | 25 PD | Uçtan uca ürün: feed → olay → taslak → kontrol → yayın |
| **Faz 4** | W18–W20 | 14 – 31 Ara 2026 | Sertleştirme ⚠️ *daraltıldı* | ~8 PD | Dayanıklılık, yedekleme, maliyet alarmı, güvenlik. **Çok kullanıcı ve beta kapsam dışı** (kişisel araç) |
| **Faz 5** | ~Ay 6–11 | Şub – Haz 2027 | Doğrulanmış Büyüme | — | Dikey genişleme, stil öğrenme, içerik kuyruğu, ücretlendirme |
| **Faz 6** | ~Ay 11–18 | Tem 2027+ | Platform & B2B | — | Olay grafiği görselleştirme, çoklu platform, Team Workspace |

```
W1    W3   W4        W7  W8              W12  W13            W17  W18            W22
├─────┤    ├──────────┤   ├────────────────┤    ├──────────────┤    ├──────────────┤
 FAZ 0      FAZ 1          FAZ 2                 FAZ 3               FAZ 4
 Karar      Veri           Olay Zekâsı           Editoryal           Beta
   │          │               │                     │                   │
   ▼          ▼               ▼                     ▼                   ▼
 G0         G1              G2                    G3                  G4
```

**Kapı (Gate) kuralı:** Bir faz, çıkış kapısındaki *tüm* koşullar sağlanmadan kapanmaz. Kapı sağlanmıyorsa iki seçenek vardır: (a) kapsamı daralt, (b) fazı uzat. **Kapıyı düşürmek üçüncü bir seçenek değildir.**

---

## 2. Görev Kartı Formatı

Her görev şu alanlarla tanımlanır:

- **ID** — `F<faz>-<no>`, kalıcı referans
- **Görev** — yapılacak iş
- **Çıktı** — somut, denetlenebilir eser (dosya, tablo, rapor, ekran)
- **DoD** — Definition of Done: "bitti" demenin ölçütü
- **PD** — efor
- **Bağ.** — bağımlılık

---

# FAZ 0 — Karar, Doğrulama ve Zemin

**W1–W3 · 17 Ağu – 4 Eyl 2026 · 15 PD**

> **Fazın tek amacı:** Kod yazmadan önce, yanlış yazılırsa 3 ay kaybettirecek her kararı kapatmak. Bu fazda üretilen tek "kod", altyapı iskeletidir.

**Uyarı:** Bu fazı atlamak cazip gelir. v2'nin tespiti aynen geçerlidir: bu kararlar netleşmeden yazılan kod, kapsam değiştikçe yeniden yazılır.

## İş Kolu A — Ürün ve Kapsam Kilitleme

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F0-01** | Spec v3'ü baştan sona oku, D1–D15 kararlarına itiraz varsa yaz | `karar-itirazlari.md` (boş olabilir) | Her karar için "kabul" veya gerekçeli itiraz yazılmış | 0,5 | — |
| **F0-02** | İtirazları çöz, Spec'i güncelle, **spec-freeze** ilan et | Spec **v3.1** dondurulmuş, git tag `spec-v3.1` | Repo'da tag mevcut; değişiklik artık sürüm artışı gerektiriyor | 0,5 | F0-01 |
| **F0-03** | MVP dikeyinin konu sınırını kesinleştir (Spec §5 listesi) | `mvp-konu-kapsami.md` — 10 konu + her biri için örnek olay | Her konu için son 3 aydan en az 2 gerçek örnek olay bulunmuş | 0,5 | F0-02 |
| **F0-19** | Faz 5/6'ya ertelenen özelliklerin "backlog" kaydını aç | `BACKLOG.md` — Spec §16 haritası görev formatında | 22 hariç kalem tek tek kayıtlı, hangi faza ait olduğu yazılı | 0,5 | F0-02 |

## İş Kolu B — Kullanıcı ve Pazar Doğrulaması

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F0-04** | 12 potansiyel kullanıcıyla 25 dk görüşme yap | `kullanici-gorusmeleri.md` — 12 not + sentez | En az 10 görüşme tamamlanmış; her birinde 5 zorunlu soru sorulmuş | 3,0 | F0-05 |
| **F0-05** | Görüşme kılavuzu hazırla (5 zorunlu soru) | `gorusme-kilavuzu.md` | Sorular: (1) bugün gündemi nasıl takip ediyorsun, (2) günde kaç dk, (3) en son ne zaman yanlış bilgi paylaştın/paylaşmaktan korktun, (4) ayda ne öderdin, (5) hangi özelliği ilk kullanırdın | 0,5 | — |
| **F0-06** | X API güncel fiyatlandırmasını doğrula ve maliyet modeli çıkar | `veri-maliyet-modeli.xlsx` sekme 1 | Geliştirici portalından alınmış güncel rakam + 3 senaryo (10/50/165 hesap) aylık $ | 0,5 | — |
| **F0-07** | LLM + embedding + altyapı maliyet modeli | `veri-maliyet-modeli.xlsx` sekme 2 | Kullanıcı başına aylık $ hesaplanmış; 10/100/1000 kullanıcı senaryosu | 0,5 | — |
| **F0-20** | Emsal/rakip araştırması — isim isim | `rakip-analizi.md` — 8 ürün | Her ürün için: ne yapıyor, fiyatı, PolitikDesk'in farkı, öğrenilecek şey | 1,0 | — |

**F0-04 uyarısı:** Bu görev "yapılmış gibi" geçilemez. 10 görüşmeden 4'ünde "ayda para ödemem" cevabı çıkarsa, Faz 1'e geçmeden önce ICP veya değer önerisi gözden geçirilir.

## İş Kolu C — Veri ve Hukuk

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F0-08** | 8 MVP kaynağının erişim yöntemi ve ToS incelemesi | `kaynak-kayit-defteri.md` — kaynak başına 1 kart | Her kaynak için: RSS/akış URL'i, ToS bağlantısı, `robots.txt` durumu, `tos_status` kararı, `independence_group` ataması | 2,0 | F0-03 |
| **F0-09** | Tier 3 kaynak isimlerini kesinleştir (D17) | Kaynak defterinde 7 ve 8 numaralı satırlar dolu | İki kaynak farklı `independence_group`'ta ve farklı editoryal çizgide | 0,5 | F0-08 |
| **F0-10** | **Medya/teknoloji hukuku danışmanlığı** (min. 1 oturum) | `hukuk-notu.md` | Gündem: TCK 217/A sorumluluk dağılımı · KVKK m.6 ve editoryal profil sınırı · Basın Kanunu kapsamı · telif/alıntı sınırı · kullanıcı sözleşmesi çerçevesi. Danışmanın yazılı/sesli notu kayıtlı | 1,0 | F0-08 |
| **F0-11** | Hukuk notundan çıkan kısıtları Spec'e işle | Spec §12 güncellenmiş + D18 karara bağlanmış | Kısıtlar teknik gereksinime çevrilmiş (örn. "şu ekranda şu uyarı zorunlu") | 0,5 | F0-10 |

**F0-10 blokaj notu:** Bu görev gecikirse Faz 1 (veri toplama) başlayabilir — ingestion hukuki riskin en düşük olduğu katmandır. Ancak **Faz 3'teki taslak üretimi F0-11 tamamlanmadan başlatılamaz.**

## İş Kolu D — Teknik Zemin

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F0-12** | Repo, ortam ve CI iskeleti | `politikdesk/` monorepo, Docker Compose, GitHub Actions | `docker compose up` ile Postgres+pgvector+Redis+API ayağa kalkıyor; CI'da lint+test koşuyor | 1,5 | F0-02 |
| **F0-13** | **Embedding modeli benchmark'ı** (D16) | `embedding-benchmark.md` | En az 3 aday, 60 Türkçe haber çifti (30 aynı olay / 30 farklı olay) üzerinde ayrım gücü (ROC-AUC + eşik önerisi) ölçülmüş; 1024 boyut uyumu doğrulanmış; maliyet karşılaştırması var | 1,5 | F0-12 |
| **F0-14** | Golden Set toplamaya başla (hedef 300 makale) | `eval/golden_set_v1.jsonl` — ilk 100 makale | Son 3 aydan makro ekonomi makaleleri, elle `event_id` etiketli; en az 5 "zor" küme (yakın ama farklı olay) içeriyor | 2,0 | F0-03 |
| **F0-15** | Veri şemasını migration olarak yaz (Spec §7.3) | `migrations/0001_initial.sql` | Tüm tablolar + indeksler + kısıtlar oluşuyor; `editorial_profiles`'ta ideolojik alan yok (test ile doğrulanıyor) | 1,0 | F0-12 |
| **F0-16** | Mimari kural testi: `evidence/` → `llm/` import yasağı | CI'da statik kontrol | Yasağı ihlal eden bir commit CI'ı kırıyor (deneyle doğrulanmış) | 0,5 | F0-12 |
| **F0-17** | LLM adapter iskeleti + maliyet/bütçe sayacı | `llm/client.py`, `llm/budget.py` | Çağrı token'ları loglanıyor; günlük tavan aşılınca `BudgetExceeded` fırlatıyor | 1,0 | F0-12 |
| **F0-18** | Gözlemlenebilirlik temeli | Structured log + Sentry + `metrics` tablosu | Bir hata Sentry'de görünüyor; log JSON formatında | 0,5 | F0-12 |

## 🚪 Kapı G0 — Faz 0 Çıkış Koşulları

| # | Koşul | Kaynak |
|---|---|---|
| 1 | Spec **v3.1** dondurulmuş, `spec-v3.1` tag'i mevcut | F0-02 |
| 2 | En az 10 kullanıcı görüşmesi tamamlanmış ve sentezlenmiş | F0-04 |
| 3 | 8 kaynağın tamamı için `tos_status` kararı verilmiş; hiçbiri `forbidden` değil | F0-08, F0-09 |
| 4 | Hukuk danışmanlığı yapılmış, kısıtlar Spec'e işlenmiş | F0-10, F0-11 |
| 5 | Embedding modeli seçilmiş, ayrım gücü ölçülmüş | F0-13 |
| 6 | Golden Set'in en az %33'ü (100 makale) etiketlenmiş | F0-14 |
| 7 | `docker compose up` ile tüm servisler ayağa kalkıyor, migration'lar uygulanıyor | F0-12, F0-15 |
| 8a | Maliyet modeli çıkarılmış; **birim ekonomi** doğrulanmış: 100 aktif kullanıcı ölçeğinde ≤ 8 $/kullanıcı/ay | F0-07 |
| 8b | **Beta bütçe tavanı** belirlenmiş: kapalı beta boyunca toplam ≤ 150 $/ay | F0-07 |
| 9 | Mimari kural testi CI'da aktif | F0-16 |

> **Neden 8 tek satır değil.** Sabit maliyet (ingestion + embedding + kümeleme + özetleme) kullanıcı sayısından bağımsızdır — ayda ~71 $. Başabaş ~18 kullanıcıdır; 8 kullanıcılı kapalı betada kişi başı 12,80 $ çıkar. Tek satırlık "≤ 8 $" koşulu betada yapısal olarak tutmaz ve kapıyı haksız yere bloke ederdi. Ölçüm: `scripts/cost_model.py`, sonuçlar `docs/veri-maliyet-modeli.md`. (B-35 / İtiraz-1)

**Kapı G0 açılmadan Faz 1'e geçilmez.**

---

# FAZ 1 — Veri Omurgası

**W4–W7 · 7 Eyl – 2 Eki 2026 · 20 PD**

> **Fazın amacı:** 8 kaynaktan sürekli, temiz, tekrarsız ve hukuki olarak güvenli veri akışı kurmak. Bu fazın sonunda henüz "olay" yoktur — yalnızca güvenilir bir `articles` tablosu vardır.

**Fazın felsefesi:** Zekâ katmanı, kirli veri üzerine kurulursa hata kaynağı ayırt edilemez. Önce boru hattı, sonra zekâ.

## İş Kolu A — Toplama (Ingestion)

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F1-01** | Kaynak adaptör arayüzü (`SourceAdapter` protokolü) | `ingestion/adapters/base.py` | Arayüz: `fetch() → list[RawItem]`; sahte (fake) adaptörle test geçiyor | 0,5 | G0 |
| **F1-02** | RSS adaptörü | `ingestion/adapters/rss.py` | Tier 2–3 kaynaklardan başlık/link/tarih çekiliyor; hatalı feed'de çökmüyor, loglayıp geçiyor | 1,0 | F1-01 |
| **F1-03** | Resmî kurum akış adaptörleri (TCMB, TÜİK, Hazine, Resmî Gazete) | `ingestion/adapters/official_*.py` | 4 kurumun tamamından son 7 günün yayınları çekiliyor; her biri için entegrasyon testi var | 3,0 | F1-01 |
| **F1-04** | Kullanıcı-tetikli manuel içe aktarma (link yapıştırma) | `ingestion/adapters/manual_import.py` + API ucu | Bir X gönderi linki veya haber linki yapıştırıldığında Tier 4/3 `article` kaydı oluşuyor | 1,0 | F1-01 |
| **F1-05** | Zamanlayıcı: 5 dakikalık toplama döngüsü | Celery Beat konfigürasyonu | 24 saat kesintisiz çalışıyor; kaynak başına son çekim zamanı `sources` tablosunda | 0,5 | F1-02 |
| **F1-06** | ToS koruması: `tos_status='forbidden'` kaynaktan toplama engeli | `ingestion/guard.py` + test | Yasaklı kaynak eklendiğinde toplama denemesi exception fırlatıyor | 0,5 | F1-01 |
| **F1-07** | Kibarlık (politeness) katmanı: rate limit, User-Agent, `robots.txt` saygısı, geri çekilme (backoff) | `ingestion/http.py` | Kaynak başına dakikada azami istek sınırı uygulanıyor; 429/503'te üstel geri çekilme | 1,0 | F1-02 |

## İş Kolu B — Normalizasyon ve Tekilleştirme

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F1-08** | Normalizasyon: canonical URL, tarih, dil, başlık temizliği | `ingestion/normalizer.py` | UTM parametreleri temizleniyor; tarihler UTC; Türkçe karakter sorunları yok | 1,5 | F1-02 |
| **F1-09** | Alıntı çıkarımı + saklama politikası uygulaması | `excerpt` ≤300 kr, `lead_paragraph` + `raw_purge_at` | Kısıt DB seviyesinde zorlanıyor; tam metin hiçbir alanda saklanmıyor (test ile doğrulanıyor) | 1,0 | F1-08 |
| **F1-10** | Tam tekrar tespiti (`content_hash`) | `ingestion/dedup.py` | Aynı içerik iki kez gelirse ikinci kayıt oluşmuyor | 0,5 | F1-08 |
| **F1-11** | Yakın tekrar / ajans kopyası tespiti (`simhash`) | `dedup.py` + `independence.py` iskeleti | Hamming mesafesi ≤6 olan makaleler işaretleniyor; AA haberini kopyalayan 3 site tespit ediliyor (elle doğrulama) | 2,0 | F1-10 |
| **F1-12** | Otomatik purge işi (30 gün TTL) | Celery periyodik görev | `raw_purge_at` geçmiş kayıtlarda `lead_paragraph` NULL oluyor; `audit_log`'a yazılıyor | 0,5 | F1-09 |

## İş Kolu C — Gömme (Embedding) ve Varlıklar

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F1-13** | Embedding üretim işi | `nlp/embedder.py` + Celery task | Yeni her makale 60 sn içinde embed ediliyor; hata durumunda kuyruğa geri alınıyor | 1,0 | F0-13 |
| **F1-14** | pgvector ANN sorgu katmanı + HNSW indeks ayarı | `nlp/search.py` | 10.000 makalede en yakın 20 komşu < 50 ms | 1,0 | F1-13 |
| **F1-15** | Varlık çıkarımı (NER) — kişi/kurum | `nlp/entities.py` | TCMB, TÜİK, Hazine, bakan isimleri doğru çıkarılıyor; 50 makalelik örnekte ≥%85 doğruluk | 2,0 | F1-13 |
| **F1-16** | Varlık sözlüğü ve alias çözümleme | `entities` tablosu doldurulmuş | "Merkez Bankası" = "TCMB" = "Türkiye Cumhuriyet Merkez Bankası" tek varlığa çözülüyor | 1,0 | F1-15 |

## İş Kolu D — Admin ve İç Araçlar

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F1-17** | Admin: kaynak yönetimi ekranı | `/admin/sources` | Kaynak ekle/düzenle/pasifleştir; `tos_status` düzenlenebilir; son çekim zamanı görünüyor | 1,0 | F1-05 |
| **F1-18** | Admin: makale listesi + filtre + tekrar denetimi | `/admin/articles` | Kaynak/tarih/dedup durumuna göre filtreleme; bir makalenin ham verisi görüntülenebiliyor | 1,0 | F1-17 |
| **F1-19** | Sağlık paneli: kaynak başına akış durumu | `/admin/health` | Bir kaynak 6 saattir veri vermiyorsa kırmızı; e-posta uyarısı gidiyor | 0,5 | F1-05 |
| **F1-20** | Golden Set ikinci parti (100 → 200 makale) | `golden_set_v1.jsonl` güncel | 200 makale etiketli | 1,0 | F0-14 |

## 🚪 Kapı G1 — Faz 1 Çıkış Koşulları

| # | Koşul | Ölçüt |
|---|---|---|
| 1 | 8 kaynağın tamamı otomatik akışta | 72 saat kesintisiz, kaynak başına ≥1 makale/gün |
| 2 | Tekilleştirme çalışıyor | 200 makalelik örnekte tam tekrar %0; ajans kopyası tespit oranı ≥%80 (elle doğrulama) |
| 3 | Saklama politikası uygulanıyor | Tam metin hiçbir alanda yok; purge işi çalıştı |
| 4 | Embedding + ANN hazır | 10.000 makale embed edilmiş; komşu sorgusu < 50 ms |
| 5 | Varlık çıkarımı ≥%85 | 50 makalelik denetim örneği |
| 6 | Admin paneli kullanılabilir | Kaynak ekleme, makale inceleme, sağlık kontrolü çalışıyor |
| 7 | Golden Set 200 makale | `golden_set_v1.jsonl` |
| 8 | Toplam sistem maliyeti öngörü içinde | Aylık altyapı + embedding maliyeti hesaplanmış |

---

# FAZ 2 — Olay Zekâsı

**W8–W12 · 5 Eki – 6 Kas 2026 · 25 PD**

> **Fazın amacı:** Makaleleri olaya çevirmek, iddiaları çıkarmak ve kanıt motorunu deterministik olarak çalıştırmak. **Bu, projenin en riskli fazıdır.** Spec §13.2'deki kalite kapıları burada tutulmalıdır.

**Fazın felsefesi:** Bu fazda hiçbir şey "iyi çalışıyor gibi" duruyor diye kabul edilmez. Her bileşen Golden Set'e karşı sayısal olarak ölçülür.

## İş Kolu A — Olay Kümeleme

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F2-01** | Kümeleme algoritması v1 (Spec §11.4) | `clustering/assigner.py` | Aday getirme + benzerlik + zaman/varlık kısıtı uygulanıyor; yeni olay yaratma çalışıyor | 3,0 | G1 |
| **F2-02** | Olay merkezi (centroid) güncelleme | `clustering/centroid.py` | Yeni makale eklendiğinde merkez artımlı güncelleniyor; drift testi geçiyor | 1,0 | F2-01 |
| **F2-03** | Sayısal çelişki bayrağı | `clustering/numeric_guard.py` | "Faiz %40" ve "faiz %42" içeren makaleler aynı olaya atanırsa `needs_review` işaretleniyor | 1,0 | F2-01 |
| **F2-04** | İnsan denetim kuyruğu (`needs_review`) | `/admin/review` ekranı | Belirsiz atamalar kuyrukta görünüyor; onayla/reddet/taşı aksiyonları var | 1,5 | F2-01 |
| **F2-05** | Merge / Split kaçış valfleri | `clustering/merger.py` + admin aksiyonları | İki olay birleştirilebiliyor (`merged_into_id`), bir olay bölünebiliyor; her işlem `audit_log`'da; geri alınabiliyor | 2,0 | F2-04 |
| **F2-14** | **Eşik kalibrasyonu** (D20: T_HIGH / T_LOW) | `eval/threshold_report.md` | Golden Set üzerinde eşik taraması yapılmış; precision/recall eğrisi çizilmiş; seçilen eşik gerekçelendirilmiş | 2,0 | F2-01, F2-16 |

## İş Kolu B — İddia Çıkarımı

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F2-06** | İddia çıkarım promptu + yapılandırılmış çıktı | `nlp/claims.py`, `prompts/claims.v1.md` | LLM her makaleden atomik iddialar çıkarıyor; JSON şema doğrulaması var; prompt sürümlü | 2,5 | G1 |
| **F2-07** | İddia tipi sınıflandırma (fact / number / attribution / prediction) | `claims.claim_type` doluyor | 100 iddialık örnekte ≥%90 doğru tip | 1,0 | F2-06 |
| **F2-08** | Sayısal değer normalizasyonu | `claims.normalized_value` (metric/value/unit/period) | "Ağustos TÜFE aylık %2,47" → `{metric:"tufe_monthly", value:2.47, unit:"%", period:"2026-08"}` | 1,5 | F2-07 |
| **F2-09** | İddia tekilleştirme (aynı iddia farklı makalelerde) | `claims` benzersizliği | Aynı olayda semantik olarak aynı iddia iki kez kaydedilmiyor | 1,5 | F2-06 |
| **F2-10** | Kanıt eşleme: iddia ↔ makale + `stance` + `quote_span` | `evidence` tablosu doluyor | Her kanıt kaydında ≤200 karakter alıntı ve destek/çelişki yönü var; `extracted_by` model sürümü yazılı | 2,0 | F2-09 |

## İş Kolu C — Kanıt Motoru (Deterministik)

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F2-11** | Bağımsız kanıt sayımı (Spec §8.2) | `evidence/independence.py` | Ajans kopyası, yayın grubu ve kopyala-yapıştır grupları tek sayılıyor; birim testleri var | 1,5 | F1-11 |
| **F2-12** | Kural motoru R0–R7 (Spec §8.3) | `evidence/rules.py` | 8 kuralın her biri için birim testi; **R0 kısa devresi ayrıca test edilir** (çelişkili kanıtlı tahmin `unverified` kalmalı, `contradicted` olmamalı); **modülde hiçbir LLM çağrısı yok** (CI kontrolü) | 2,0 | F2-11 |
| **F2-13** | `status_reason` üretimi (makine-okunur gerekçe) | JSONB alan doluyor | Her durum kaydında kural adı, girdiler, kırılım, motor sürümü var | 0,5 | F2-12 |
| **F2-15** | Salience skoru (Spec §8.4) | `evidence/salience.py` + `salience_breakdown` | Global formül (0–90) uygulanıyor ve saklanıyor; kişisel ayarlama (0–10) sorgu anında hesaplanıyor, **saklanmıyor** (test); kırılım şeffaf; **engagement girdisi yok** (test) | 1,5 | F2-12 |

## İş Kolu D — Bağlam ve Takvim

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F2-17** | Tarihsel bağlam: geçmiş benzer olay araması | `context/related.py` → `event_relations` | Bir enflasyon olayı, önceki ayın enflasyon olayına `same_thread` ile bağlanıyor | 2,0 | F2-01 |
| **F2-18** | ScheduledEvent: elle takvim girişi + admin ekranı | `/admin/calendar` | TÜİK veri takvimi ve TCMB PPK tarihleri (12 ay) girilmiş | 1,0 | F1-17 |
| **F2-19** | Beklenen gelişme → gerçekleşen olay eşleştirmesi | `context/scheduler_match.py` | Takvimde 14:30 TÜİK kaydı varsa, o saatte gelen TÜİK olayı otomatik `linked_event_id` alıyor | 1,0 | F2-18 |

## İş Kolu E — Değerlendirme (Evaluation)

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F2-16** | Eval koşucusu (evaluation harness) | `eval/run.py` + rapor çıktısı | Tek komutla Golden Set koşuluyor; precision/recall/false-merge/status doğruluğu rapor ediliyor | 2,0 | F1-20 |
| **F2-20** | Golden Set tamamlama (200 → 300 makale + 150 iddia) | `golden_set_v1.jsonl`, `golden_claims_v1.jsonl` | 300 makale + 150 iddia etiketli; zor kümeler dahil | 2,0 | F1-20 |
| **F2-21** | Haftalık kalite ritüelini başlat (Spec §13.4) | `kalite-gunlugu.md` | En az 3 hafta üst üste yapılmış; her hafta 10 olay denetlenmiş | 0,5 | F2-16 |

## 🚪 Kapı G2 — Faz 2 Çıkış Koşulları (SERT KAPI)

| # | Koşul | Hedef | Not |
|---|---|---|---|
| 1 | Olay kümeleme precision | ≥ %90 | Golden Set 300 makale |
| 2 | Olay kümeleme recall | ≥ %80 | |
| 3 | **Yanlış birleştirme (false merge)** | ≤ %5 | **Pazarlıksız** |
| 4 | `evidence_status` doğruluğu | ≥ %95 | Elle uygulanan kurala karşı |
| 5 | Uydurulmuş/hatalı iddia oranı | ≤ %2 | 150 iddialık set |
| 6 | Sayısal normalizasyon doğruluğu | ≥ %95 | |
| 7 | `evidence/` modülünde LLM çağrısı | 0 | CI testi |
| 8 | Merge/split geri alınabilir | %100 | Elle test |
| 9 | Haftalık ritüel işliyor | ≥3 hafta | |

> **Ölçüm notu (12 Ağu 2026).** G2'nin 3. koşulu (false merge ≤ %5) Golden Set'in boyutuna duyarlıdır: 36 olay / ~37 küme varken tek bir karışık küme oranı 2,7 puan oynatır. Kapı, **300 makalelik set olmadan karara bağlanamaz** (B-57). Mevcut 55 makalelik ölçüm bir yön gösterir: false merge %2,6, otomatik precision %100. Ayrıntı: `eval/threshold_report.md`.

**Kapı G2 tutmuyorsa yapılacaklar (öncelik sırasıyla):**
1. Eşikleri yeniden kalibre et (F2-14 tekrar)
2. Kısıtları sıkılaştır (varlık jaccard eşiğini yükselt, zaman penceresini daralt)
3. Hibrit skorlama ekle (embedding + BM25 + varlık örtüşmesi ağırlıklı) — ⚠️ **hangi hata ailesi için olduğuna bak.** D16 tanı koşumu (`docs/embedding-benchmark.md`) gösterdi ki şablonlu resmî duyurularda (ardışık PPK kararları) metin de varlıklar da aynıdır; BM25 ve varlık örtüşmesi 1,0 verir ve durumu **kötüleştirir**. O aile için doğru ilaç 2. maddedeki zaman penceresidir. Hibrit skorlama, farklı kelimelerle anlatılan aynı olayın kaçırılması (recall) hatası için uygundur. (B-49)
4. **Son çare:** dikeyi daha da daralt (yalnızca enflasyon + faiz) ve kapıyı bu dar kapsamda tuttur

Kapıyı düşürmek seçenek değildir — Spec §13.2 gerekçesi: yanlış birleştirme, kullanıcıyı yanlış kanıtla içerik üretmeye götürür.

---

# FAZ 3 — Editoryal Katman ve Arayüz

**W13–W17 · 9 Kas – 11 Ara 2026 · 25 PD**

> **Fazın amacı:** Faz 2'nin ürettiği zekâyı kullanıcıya sunmak ve Core Loop'u DRAFT + REVIEW adımlarıyla kapatmak. Bu fazın sonunda ürün uçtan uca çalışır.

**Ön koşul:** F0-11 (hukuk kısıtlarının Spec'e işlenmesi) tamamlanmış olmalı — aksi halde İş Kolu B başlatılamaz.

## İş Kolu A — Çekirdek Arayüz

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F3-01** | Frontend iskeleti (Next.js + Tailwind + shadcn) | `web/` uygulaması | Kimlik doğrulama (magic link), korumalı rota, tema | 1,5 | G2 |
| **F3-02** | **Live Feed** ekranı | `/feed` | Salience sıralı olay kartları; her kartta durum rozeti, kaynak sayısı kırılımı, son güncelleme; 30 sn'de bir sessiz yenileme | 2,5 | F3-01 |
| **F3-03** | **Olay Sayfası** (Spec §14.3) | `/event/[id]` | TL;DR, ne biliyoruz/bilmiyoruz, kanıt bloğu, kaynak tablosu, zaman çizelgesi, önceki bağlam, beklenen gelişme — hepsi çalışır | 4,0 | F3-02 |
| **F3-04** | "Neden bu durum?" açıklama bileşeni | Kanıt bloğunda açılır panel | `status_reason` JSON'u insan diline çevriliyor; kural adı ve girdiler görünüyor | 1,0 | F3-03 |
| **F3-05** | Kaynak karşılaştırma + framing paneli | Olay sayfasında tablo | Başlıklar yan yana, tier rozeti, link; "N farklı yayın grubu" notu; **siyasi etiket yok** (kod incelemesi) | 1,5 | F3-03 |
| **F3-06** | Zaman çizelgesi bileşeni | Genişletilebilir dikey akış | Her adımda saat + kaynak + tek cümle; 20+ makalede performans sorunu yok | 1,0 | F3-03 |
| **F3-07** | Salience şeffaflık popover'ı | Skora tıklayınca kırılım | `salience_breakdown` bileşenleri gösteriliyor; "bu bir doğruluk skoru değildir" notu var | 0,5 | F3-02 |

## İş Kolu B — Editoryal Üretim (Hukuk kısıtlarına bağlı)

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F3-08** | Editoryal Kimlik Kartı formu (7 soru) | `/onboarding/profile` | Spec §10.1 sol kolondaki alanlar toplanıyor; ideolojik soru **yok** | 1,0 | F3-01 |
| **F3-09** | Profil → sistem promptu derleyicisi | `editorial/profile_compiler.py` | Form yanıtları statik prompt bloğuna dönüşüyor; her üretimde yeniden analiz yok | 0,5 | F3-08 |
| **F3-10** | Taslak üretimi — 3 açı (bilgilendir/analiz/eleştir) | `editorial/generator.py`, `prompts/draft.v1.md` | Girdi yalnızca `claims`+`evidence`; grounding talimatı promptta; `cited_claim_ids` doluyor | 3,0 | F3-09, F0-11 |
| **F3-11** | **P1 zorlaması:** kanıt yoksa üretim yok | API 409 + UI mesajı | `claims` boş bir olayda taslak butonu devre dışı; API doğrudan çağrılsa da reddediyor | 0,5 | F3-10 |
| **F3-12** | **Grounding doğrulayıcısı** (programatik) | `editorial/grounding_check.py` | Üretilen metindeki her sayı, tarih ve tırnak içi alıntı, kanıt setinde aranıyor; bulunamayan varsa üretim işaretleniyor | 2,0 | F3-10 |
| **F3-13** | **Pre-publish Check** (Spec §14.4) | `editorial/checker.py` + UI | 6 kontrol: kaynak linki, sayısal eşleşme, haber/yorum ayrımı, tek kaynaklı iddia, bağlanamayan cümle, eksik bağlam. Engelleyici durum çalışıyor | 2,5 | F3-12 |
| **F3-14** | Taslak düzenleme + aksiyon kaydı | Editör bileşeni | Kabul/düzenle/yeniden üret/reddet aksiyonları `drafts.user_action`'a yazılıyor; `edit_distance` hesaplanıyor | 1,5 | F3-10 |
| **F3-15** | Yayın köprüsü: panoya kopyala + X Web Intent | Yayın butonu | Kopyalama çalışıyor; Web Intent yeni sekmede X'i doğru metinle açıyor; **otomatik gönderme yok** | 0,5 | F3-14 |

## İş Kolu C — Brifingler

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F3-16** | Brifing üretici (sabah 08:00 / akşam 20:00) | `briefing/generator.py` | Salience sıralı ilk 5–7 olay + beklenen gelişmeler + doğrulanmamış iddialar bölümü | 2,0 | F3-03 |
| **F3-17** | E-posta gönderimi + uygulama içi brifing sayfası | `/briefing/[date]` + e-posta şablonu | E-posta HTML'de olay linkleri çalışıyor; açılma takibi var (metrik) | 1,5 | F3-16 |
| **F3-18** | "Sen yokken ne oldu" özeti (basit sürüm) | Feed üstünde şerit | Son giriş zamanından bu yana N önemli olay; tek satır | 0,5 | F3-02 |

## İş Kolu D — Ölçüm Altyapısı

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F3-19** | Ürün metrik toplama (Spec §13.3) | `metrics` tablosu + olay izleme | 8 metriğin tamamı kaydediliyor: time-to-understanding, acceptance rate, edit distance, diversity ratio, briefing open, active minutes, correction rate, cost/user | 2,0 | F3-14 |
| **F3-20** | Metrik panosu | Metabase/Grafana panosu | 8 metrik günlük olarak görüntüleniyor | 1,0 | F3-19 |
| **F3-21** | "Bu yanlış" geri bildirim butonu | Olay sayfasında | Kullanıcı işaretlediğinde `needs_review` kuyruğuna düşüyor + `correction_rate` metriğine yazılıyor | 0,5 | F3-03 |

## 🚪 Kapı G3 — Faz 3 Çıkış Koşulları

| # | Koşul | Ölçüt |
|---|---|---|
| 1 | Uçtan uca akış çalışıyor | Feed → olay → taslak → kontrol → kopyala, tek oturumda kesintisiz |
| 2 | **Taslakta kanıtta olmayan sayı/tarih** | **%0** — 50 taslaklık denetim (sert kapı) |
| 3 | Pre-publish check yanlış-negatifi | ≤ %5 — 40 taslaklık test |
| 4 | Kanıtsız olayda taslak üretimi | Engelleniyor (API + UI testi) |
| 5 | Brifing 7 gün üst üste sorunsuz üretildi | Log kontrolü |
| 6 | 8 ürün metriği akıyor | Panoda görünüyor |
| 7 | Olay sayfası yükleme süresi | < 1,5 sn (p95) |
| 8 | UI'da siyasi kaynak etiketi yok | Kod incelemesi + arama |
| 9 | Otomatik yayın kod yolu yok | Kod incelemesi (`POST` ile X'e gönderim yok) |

---

# FAZ 4 — Sertleştirme  ⚠️ **KAPSAM DARALTILDI**

**W18–W20 · 14 – 31 Ara 2026 · ~8 PD**

> **KAPSAM KARARI (12 Ağustos 2026).** Proje **tek kullanıcılı kişisel bir
> araç** olarak kararlaştırıldı (bkz. `docs/FAZ0-DURUM.md`). Bu kararla
> Faz 4'ün özgün amacı — "tek kullanıcılıktan çok kullanıcılığa taşımak ve
> 8 gerçek kullanıcıyla kapalı beta başlatmak" — dayanaksız kaldı.
>
> **MVP artık Faz 3'ün sonunda biter.** Faz 4, yalnızca *tek kullanıcılı
> araç için de gerekli olan* sertleştirme işlerini içerir.

| İş kolu | Karar |
|---|---|
| **A — Çok kullanıcı ve hesap yönetimi** (F4-01…F4-04) | ⛔ **Kapsam dışı.** Kullanıcı = geliştirici. Çok kullanıcıya geçilirse Faz 5'te yeniden açılır. |
| **B — Hukuki ve KVKK** (F4-11…F4-14) | ⛔ **Kapsam dışı** (F0-10/F0-11 ile aynı gerekçe: kişisel araç, veri sahibi = kullanıcı). **İstisna: F4-15 ve F4-16 kalır.** |
| **C — Dayanıklılık ve operasyon** (F4-05…F4-10) | ✅ **Kalır** — tek kullanıcıda da gerekli. Bunlar fazın tamamıdır. |
| **D — Beta yürütme** (F4-17…F4-22) | ⛔ **Kapsam dışı.** Beta kullanıcısı yok. |

**Özgün faz aşağıda olduğu gibi bırakıldı** (kayıt için); kapsam dışı iş
kolları çok kullanıcıya geçiş kararı verilirse buradan geri alınır.

**Not:** W20 yıl sonu tatil dönemine denk gelir; plan bu haftada %50 kapasite varsayar.

## İş Kolu A — Çok Kullanıcı ve Hesap Yönetimi

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F4-01** | Çok kullanıcılı veri izolasyonu | `user_id` bazlı yetkilendirme | Bir kullanıcının taslakları/profili diğerine görünmüyor; test var | 1,5 | G3 |
| **F4-02** | Davet tabanlı kayıt (invite code) | `/invite` akışı | Yalnızca davet kodu olan kayıt olabiliyor | 0,5 | F4-01 |
| **F4-03** | Kullanıcı ayarları: konu öncelikleri, brifing saatleri, bildirim tercihi | `/settings` | Değişiklikler brifing ve salience'a yansıyor | 1,0 | F4-01 |
| **F4-04** | Onboarding akışı (5 adım) | `/onboarding` | Hoş geldin → editoryal kart → konu seçimi → örnek olay turu → ilk brifing | 1,5 | F3-08 |

## İş Kolu B — Hukuki ve KVKK Uyum

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F4-11** | KVKK aydınlatma metni + açık rıza akışı | `/legal/kvkk` + rıza kaydı | Metin F0-10 notuna uygun; rıza zaman damgalı kaydediliyor; rıza olmadan profil oluşmuyor | 1,5 | F0-11 |
| **F4-12** | Veri sahibi hakları: dışa aktarma + silme | `/settings/data` | Kullanıcı tüm verisini JSON indirebiliyor; silme talebi 30 gün içinde tam siliyor | 1,5 | F4-11 |
| **F4-13** | Kullanım koşulları + sorumluluk beyanı | `/legal/terms` | Editoryal sorumluluğun kullanıcıda olduğu açık; F0-10 notuna uygun | 1,0 | F0-11 |
| **F4-14** | Uygulama içi kalıcı uyarı bileşeni | Taslak ekranında | "Bu bir taslaktır; yayınlamadan önce kaynakları doğrulayın" — kapatılamaz | 0,5 | F3-14 |
| **F4-15** | **Election Mode** feature flag + konfigürasyon şeması (uygulanmaz, hazırlanır) | `config/election_mode.py` | Flag açıldığında eşikler sıkılaşıyor (birim testi); UI göstergesi hazır; **varsayılan kapalı** | 1,0 | F2-12 |
| **F4-16** | Denetim izi (audit log) tamamlama | `audit_log` kapsamı | Kaynak değişikliği, merge/split, taslak üretimi, purge, rıza — hepsi kayıtlı | 0,5 | F2-05 |

## İş Kolu C — Dayanıklılık ve Operasyon

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F4-05** | Hata dayanıklılığı: kaynak/LLM/embedding hatalarında zarif bozulma | Retry + dead-letter kuyruk | Bir kaynak 24 sa çökse ürün çalışmaya devam ediyor; LLM hatasında olay sayfası kanıt bloğuyla açılıyor | 2,0 | G3 |
| **F4-06** | Yedekleme ve geri yükleme | Günlük otomatik yedek + geri yükleme prosedürü | Test ortamına geri yükleme başarıyla denendi (belgelendi) | 1,0 | — |
| **F4-07** | Maliyet tavanı ve alarm | `llm/budget.py` genişletme | Günlük/aylık tavan; %80'de uyarı e-postası; tavanda üretim duruyor, ingestion devam ediyor | 1,0 | F0-17 |
| **F4-08** | Performans optimizasyonu | Feed ve olay sayfası | Feed p95 < 800 ms; olay sayfası p95 < 1,5 sn; N+1 sorgu yok | 1,5 | F3-03 |
| **F4-09** | Güvenlik gözden geçirmesi | `guvenlik-notu.md` | Sır yönetimi, oran sınırlama, girdi doğrulama, SSRF (link import), XSS kontrolleri yapılmış | 1,5 | F4-01 |
| **F4-10** | Üretim ortamı kurulumu | VPS + domain + TLS + izleme | Uptime izleme aktif; deploy tek komut | 1,5 | F4-06 |

## İş Kolu D — Beta Yürütme

| ID | Görev | Çıktı | DoD | PD | Bağ. |
|---|---|---|---|---|---|
| **F4-17** | Beta kullanıcı seçimi ve daveti (8 kişi) | Davet listesi + onboarding çağrıları | F0-04 görüşmelerinden 8 kişi seçilmiş ve kabul etmiş | 1,0 | F4-02 |
| **F4-18** | Beta geri bildirim kanalı | Uygulama içi geri bildirim + haftalık form | Her kullanıcıdan haftalık 3 soruluk yanıt toplanıyor | 0,5 | F4-17 |
| **F4-19** | 2 haftalık beta gözlem dönemi | `beta-raporu.md` | 8 metriğin tamamı 2 hafta boyunca toplanmış; kullanıcı başına en az 5 oturum | 2,0 | F4-17 |
| **F4-20** | Beta bulgularının önceliklendirilmesi | `BACKLOG.md` güncel | Bulgular: "beta engelleyici / Faz 5 / reddedildi" olarak sınıflandırılmış | 1,0 | F4-19 |
| **F4-21** | Beta engelleyicilerin düzeltilmesi | Düzeltme sürümü | "Beta engelleyici" işaretli tüm bulgular kapalı | 2,0 | F4-20 |
| **F4-22** | Faz 5 kapsam kararı | `faz5-kapsam.md` | Metriklere dayalı: hangi dikey açılacak, ücretlendirme ne zaman, hangi özellik önce | 1,0 | F4-19 |

## 🚪 Kapı G4 — MVP Tamamlanma Koşulları

> ⚠️ **Yeniden yazıldı (12 Ağustos 2026).** Aşağıdaki özgün G4'ün 11
> koşulundan **7'si gerçek beta kullanıcısı gerektiriyordu** (1, 2, 3, 4,
> 6, 9, 11) ve kişisel araç kararıyla **hiçbir zaman ölçülemez** hale
> geldi. Ölçülemeyen koşul kapı değildir; kapıyı kâğıt üstünde tutmak
> "kapıyı düşürmek üçüncü seçenek değildir" kuralını içten çürütürdü.

### G4′ (yürürlükteki kapı — tek kullanıcılı MVP)

| # | Koşul | Hedef | Kaynak |
|---|---|---|---|
| 1 | Uçtan uca akış 7 gün kesintisiz | Feed → olay → taslak → kontrol → kopyala | G3 #1'in süreye yayılmış hâli |
| 2 | **Taslakta kanıtta olmayan sayı/tarih** | **%0** (50 taslak) | G3 #2 — sert kapı, korunur |
| 3 | **Correction rate** (kullanıcının kendi "bu yanlış" işareti) | ≤ %3 | Tek kullanıcıda da ölçülebilir |
| 4 | **Diversity ratio** | ≥ 2,5 | Kullanıcıdan bağımsız, sistem metriği |
| 5 | Birim ekonomi — ölçülen aylık toplam maliyet | ≤ 30 $ | F0-07 kişisel profil: 22,94 $ |
| 6 | Kritik hata (P0/P1) | 0 açık | Değişmedi |
| 7 | Kümeleme kalite kapıları hâlâ tutuyor | G2 metrikleri regresyona uğramamış | Değişmedi |
| 8 | Yedekleme + geri yükleme denenmiş | Belgelenmiş | F4-06 |
| 9 | Günlük yedek ve maliyet alarmı çalışıyor | F4-06, F4-07 | Değişmedi |

**G4′ tutmuyorsa:** Faz 5'e geçilmez; eksik koşula odaklanan bir düzeltme turu açılır.

### Özgün G4 (kayıt için — çok kullanıcıya geçilirse geri gelir)

| # | Koşul | Hedef |
|---|---|---|
| 1 | 8 beta kullanıcısı ≥2 hafta aktif | Kullanıcı başına ≥5 oturum |
| 2 | **Draft acceptance rate** | ≥ %40 |
| 3 | **Edit distance** | ≤ 0,35 |
| 4 | **Correction rate** ("bu yanlış" işaretleme) | ≤ %3 |
| 5 | **Diversity ratio** | ≥ 2,5 |
| 6 | **Briefing open rate** | ≥ %60 |
| 7a | Birim ekonomi — kullanıcı başına aylık maliyet, **100 kullanıcı ölçeğine izdüşümü** | ≤ 8 $ |
| 7b | Beta bütçe tavanı — ölçülen **toplam** aylık maliyet | ≤ 150 $ |
| 8 | Kritik hata (P0/P1) sayısı | 0 açık |
| 9 | KVKK: aydınlatma, rıza, dışa aktarma, silme | Hepsi canlıda |
| 10 | Kümeleme kalite kapıları hâlâ tutuyor | G2 metrikleri regresyona uğramamış |
| 11 | Ödeme isteği doğrulaması | ≥5 kullanıcı "ayda X TL öderdim" demiş, ortalama fiyat maliyeti karşılıyor |

**G4 tutmuyorsa:** Faz 5'e geçilmez. Metriklerden hangisi düşükse ona odaklanan 3 haftalık bir "düzeltme fazı" (Faz 4b) açılır.

---

# FAZ 5 — Doğrulanmış Büyüme

**Yaklaşık Şubat – Haziran 2027 · üst düzey plan**

> **Ön koşul:** Kapı G4 açılmış olmalı. Bu faz, MVP'nin *kanıtlanmış* olmasına bağlıdır — takvime değil.

**Fazın stratejisi:** Genişleme sırası, riski artan yönde ilerler. Her genişleme adımı kendi kalite kapısını yeniden geçmek zorundadır.

## 5.1 Dikey Genişleme (sıralı, her biri ~3 hafta)

| Sıra | Dikey | Ek görevler | Kapı |
|---|---|---|---|
| 1 | **Yasama / TBMM** | Tutanak ve kanun teklifi adaptörü, komisyon takvimi, yasama süreç durumu (`komisyonda/genel kurulda/kanunlaştı`) | Kümeleme precision ≥%88 (yeni Golden Set 150 makale) |
| 2 | **Yargı / hukuk** | Mahkeme kararı kaynakları, dava süreç zinciri, **isimli kişi koruması sıkılaştırma** | Hukuk danışmanı 2. oturum + `unverified` iddiada isimli kişi taslak engeli |
| 3 | **Dış politika** | Uluslararası kaynak katmanı, çok dilli embedding, çeviri katmanı | Çok dilli kümeleme precision ≥%85 |
| 4 | **Genel siyaset** | En yüksek risk. Election Mode aktifleştirme, sıkı kanıt eşikleri | Hukuk danışmanı 3. oturum + Election Mode canlı testi |

**Kaynak sayısı:** her dikeyde 8 → azami 15. Toplam kaynak 40'ı aşmaz (Faz 6'ya kadar).

## 5.2 Özellik Genişlemesi

| Grup | Özellikler | Not |
|---|---|---|
| **Editoryal derinlik** | Stil öğrenme (tweet arşivinden biçimsel çıkarım, ham arşiv işleme sonrası silinir) · Karşı görüş kontrolü · "Bana katılmayan kaynaklar" · Tekrarlayan içerik kontrolü · 5. ve 6. taslak açısı (bağlamsal, soru odaklı) | Stil öğrenme için ayrı KVKK rıza metni |
| **İş akışı** | İçerik kuyruğu (taslak/onay bekleyen/zamanlanmış/yayınlanan) · Yayın takvimi · İçerik arşivi ve arama | Otomatik yayın **hâlâ yok** |
| **İstihbarat** | Konu takibi · Kişi/kurum takibi · Günlük/haftalık rapor arşivi · Political Memory v1 (olay zinciri sorgusu) | |
| **Otomasyon (kontrollü)** | Resmî X API üzerinden **yarı**-otomasyon: yalnızca `strongly_corroborated` + `number` tipi + Tier 1 kaynaklı içerik; kullanıcı her seferinde onaylar | X API maliyet modeli gelir modelini karşılıyorsa |
| **Ticarileşme** | Ücretlendirme altyapısı · Free/Pro/Creator katmanları · Fatura ve abonelik yönetimi | G4 koşul 11'e dayalı fiyatlandırma |

## 5.3 Faz 5 Kapısı (G5)

| # | Koşul |
|---|---|
| 1 | En az 2 dikey canlıda ve kalite kapılarını geçiyor |
| 2 | ≥50 aktif kullanıcı, ≥%40 haftalık dönüş oranı |
| 3 | ≥15 ödeyen kullanıcı; birim ekonomi pozitif (gelir > kullanıcı başına maliyet) |
| 4 | Correction rate ≤ %3 (genişlemeye rağmen) |
| 5 | Election Mode canlı ortamda test edilmiş |

---

# FAZ 6 — Platform ve B2B

**Yaklaşık Temmuz 2027 sonrası · üst düzey plan**

> **Ön koşul:** G5. Bu faz, ürünün "kişisel masa"dan "platform"a dönüştüğü aşamadır ve ekip büyümesi gerektirir (tek geliştiriciyle gerçekçi değildir).

| Blok | Kapsam |
|---|---|
| **Olay grafiği görselleştirme** | Gündem haritası · konu ilişki grafiği (ekonomi → enflasyon → faiz → TCMB) · kişi/kurum ilişki ağı · olay zinciri görselleştirme · trend analizi |
| **Tarihsel istihbarat** | Political Memory tam sürüm · açıklama karşılaştırma (2025 vs 2026) · söylem değişikliği analizi · söz/gerçek karşılaştırması (kaynak gösteren araştırma yardımcısı olarak, hüküm vermeden) · belge/PDF analizi (TBMM dokümanları, resmî kararlar) |
| **Çoklu kanal** | Threads · Bluesky · Instagram carousel metni · YouTube açıklaması · Telegram · newsletter · blog — her kanal için format uyarlaması (aynı metni kopyalamadan) |
| **Team Workspace (B2B)** | Paylaşılan olay havuzu · rol tabanlı yetki · onay akışı · editoryal atama · ekip arşivi · kullanım raporlaması |
| **Platform** | Genel API · webhook · özel kaynak entegrasyonu · Enterprise katmanı |
| **Mobil** | Önce PWA, talep doğrulanırsa yerel uygulama |

**Faz 6 sınırı (değişmez):** Siyasi kampanya araçları, seçmen segmentasyonu, kitle hedefleme ve koordineli yayın özellikleri **hiçbir koşulda** geliştirilmez (Spec §15).

---

# 3. Çapraz Kesen Disiplinler

Bu ritüeller faz bağımsızdır ve ilgili fazda başladıktan sonra ürün ömrü boyunca sürer.

| Ritüel | Sıklık | Başlangıç | Süre | İçerik |
|---|---|---|---|---|
| **Kalite denetimi** | Haftalık (Cuma) | Faz 2 | 60 dk | 10 olay örneklemesi · `needs_review` boşaltma · Golden Set büyütme · metrik regresyon kontrolü · LLM maliyet trendi |
| **Faz kapısı incelemesi** | Faz sonu | Faz 0 | 2 sa | Kapı koşullarının tek tek denetimi; geçmiyorsa kapsam/süre kararı |
| **Kapsam savunması** | Haftalık | Faz 0 | 15 dk | Bu hafta listede olmayan iş yapıldı mı? Yapıldıysa neden? `BACKLOG.md`'ye taşındı mı? |
| **Maliyet incelemesi** | Aylık | Faz 1 | 30 dk | LLM + embedding + altyapı; kullanıcı başına maliyet; tavan ayarı |
| **Hukuki gözden geçirme** | Faz kapısında + dikey açılışında | Faz 0 | değişken | Yeni özellik/dikey hukuki notu değiştiriyor mu? |
| **Golden Set büyütme** | Haftalık | Faz 0 | 30 dk | Yanlış örnekler sete eklenir; set zamanla zorlaşır |

---

# 4. Karar Noktaları (Decision Gates)

Yol haritası boyunca "devam / değiştir / dur" kararı verilecek anlar:

| Nokta | Ne zaman | Soru | Olası kararlar |
|---|---|---|---|
| **DG-1** | F0-04 sonrası | 10 görüşmede gerçek talep ve ödeme isteği var mı? | Devam · ICP değiştir · değer önerisini yeniden çerçevele |
| **DG-2** | F0-10 sonrası | Hukuki zemin MVP'yi kaldırıyor mu? | Devam · kapsamı daralt · dikeyi değiştir · yapıyı değiştir (örn. tamamen kişisel araç) |
| **DG-3** | Kapı G2 | Kümeleme kalitesi kapıyı geçiyor mu? | Devam · eşik/algoritma iyileştir · dikeyi daralt |
| **DG-4** | Kapı G3 | Taslak grounding'i %100 temiz mi? | Devam · üretimi kısıtla (yalnızca 🟢 iddialar) |
| **DG-5** | Kapı G4 | Beta metrikleri tutuyor mu? | Faz 5 · Faz 4b düzeltme · pivot |
| **DG-6** | Faz 5 ortası | Birim ekonomi pozitif mi? | Büyü · fiyat artır · maliyet düşür · B2B'ye erken geç |

---

# 5. Kapsam Savunma Protokolü

Risk R4 (kapsam şişmesi) bu projenin **en yüksek olasılıklı** riskidir. Karşı önlem, bir süreç kuralıdır:

**Yeni bir fikir geldiğinde uygulanacak 4 adım:**

1. **Yaz, yapma.** Fikir doğrudan `BACKLOG.md`'ye yazılır. Aynı gün kodlanmaz.
2. **Filtreden geçir** (Spec §6): Core Loop'un hangi adımı? Prensiplerle çatışıyor mu? MVP dikeyinde anlamlı mı? Ölçülebilir mi?
3. **Faz ata.** Filtreyi geçse bile, mevcut fazın görev listesinde yoksa **bir sonraki faza** atanır.
4. **İstisna kuralı:** Yalnızca "beta engelleyici" veya "hukuki zorunluluk" etiketli işler faz ortasında listeye girebilir. Bu etiketi koymak yazılı gerekçe gerektirir.

**Haftalık kontrol sorusu:** *"Bu hafta yaptığım işlerin kaçı görev listesindeydi?"* İki hafta üst üste %70'in altındaysa, kapsam kontrolden çıkmıştır ve durup plan gözden geçirilir.

---

# 6. Görev Özeti — Toplu Liste

| Faz | Görev sayısı | PD | Hafta | Kritik yol üzerindeki görevler |
|---|---|---|---|---|
| Faz 0 | 20 | 15,0 | W1–W3 | F0-02 → F0-08 → F0-10 → F0-11 → F0-13 → F0-15 |
| Faz 1 | 20 | 20,0 | W4–W7 | F1-01 → F1-03 → F1-08 → F1-11 → F1-13 |
| Faz 2 | 21 | 25,0 | W8–W12 | F2-01 → F2-06 → F2-10 → F2-11 → F2-12 → F2-16 → F2-14 |
| Faz 3 | 21 | 25,0 | W13–W17 | F3-01 → F3-03 → F3-10 → F3-12 → F3-13 |
| Faz 4 | 22 | 23,0 | W18–W22 | F4-01 → F4-11 → F4-10 → F4-17 → F4-19 |
| **Toplam** | **104** | **108,0** | **22 hafta** | |

**Kritik yol uzunluğu:** ~19 hafta. Kalan 3 hafta, kritik yol dışı görevler ve tampon içindir.

**En yüksek riskli 5 görev:**

| Görev | Neden riskli | Tampon planı |
|---|---|---|
| F2-01 + F2-14 (kümeleme + kalibrasyon) | Kalite kapısı burada tutulmazsa proje durur | +2 hafta tampon; son çare dikey daraltma |
| F0-10 (hukuk danışmanlığı) | Dış bağımlılık, randevu gecikebilir | Faz 1 paralel başlar; Faz 3 İş Kolu B bloke |
| F3-12 (grounding doğrulayıcısı) | %0 hedefi mutlak | Yalnızca 🟢 iddialardan üretim kısıtı yedek plan |
| F1-11 (ajans kopyası tespiti) | Bağımsız sayım buna bağlı; yanlışsa kanıt motoru yanılır | Elle `independence_group` ataması yedek |
| F0-04 (kullanıcı görüşmeleri) | Erteleme eğilimi yüksek, sonucu her şeyi etkiler | Kapı G0'ın koşulu; atlanamaz |

---

# 7. İlk Hafta — Somut Başlangıç

Yol haritası soyut kalmasın diye, W1'in gün gün planı:

| Gün | İş | Çıktı |
|---|---|---|
| **Pzt** | F0-01 Spec'i oku, itirazları yaz · F0-05 görüşme kılavuzunu hazırla | `karar-itirazlari.md`, `gorusme-kilavuzu.md` |
| **Sal** | F0-02 spec-freeze · F0-03 konu kapsamı · F0-19 backlog aç | `spec-v3.1` tag, `mvp-konu-kapsami.md`, `BACKLOG.md` |
| **Çar** | F0-12 repo + Docker Compose + CI · görüşme davetlerini gönder | Çalışan `docker compose up` |
| **Per** | F0-08 kaynak ToS incelemesi (ilk 4 kaynak: TCMB, TÜİK, Hazine, Resmî Gazete) · hukukçu randevusu al | `kaynak-kayit-defteri.md` yarısı |
| **Cum** | F0-08 devam (AA, Reuters, Tier 3 adayları) · F0-06 X API fiyat doğrulaması · haftalık kapsam kontrolü | Kaynak defteri tam, `veri-maliyet-modeli` sekme 1 |

**W1 sonu kontrolü:** Spec dondurulmuş mu? Repo ayakta mı? Hukukçu randevusu alındı mı? Görüşme davetleri gitti mi? Dördü de "evet" değilse W2 planı yeniden düzenlenir.

---

# 8. Sonuç

Bu yol haritası üç şeyi garanti etmez: takvimin tutmasını, kalite kapılarının ilk denemede geçilmesini, gerçek talebin çıkmasını. Bunları garanti eden bir plan zaten yoktur.

Garanti ettiği şey şudur: **her adımda ne yapılacağı, neden yapılacağı ve bittiğinin nasıl anlaşılacağı bellidir** — ve yanlış giden bir şey olduğunda, hangi kapının tutmadığı ve ne yapılacağı önceden yazılmıştır.

Projenin gerçek riski hâlâ teknik değil. Sırasıyla: **kapsam disiplini** (Bölüm 5), **hukuki zemin** (F0-10), **kümeleme kalitesi** (Kapı G2). Bu üçü yönetilirse geri kalan mühendislik işidir.

> **Başlangıç noktası: Faz 0, görev F0-01.**

---

*Bu belge `PolitikDesk_Master_Spec_v3.md` ile birlikte okunmalıdır. Spec "ne ve neden", bu belge "ne zaman ve nasıl" sorusunu cevaplar. İkisi çelişirse Spec önceliklidir.*
