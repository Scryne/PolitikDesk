# PolitikDesk

> Makro ekonomi ve yasama/siyaset gündemini 16 kaynaktan toplayan, haberleri **olaya** çeviren, her iddiayı
> **deterministik kurallarla kanıta** bağlayan ve kaynaklı editoryal taslak üreten bir
> çalışma masası.

**AI senin yerine konuşmaz. AI senin daha iyi konuşabilmen için gündemi senin adına takip eder.**

Ürünün tek cümlelik sözleşmesi budur ve mimarinin tamamı onu korumak üzere kurulmuştur:
kanıt motoru LLM'i *import edemez*, taslak üretimi kanıtsız olayda *başlamaz*, yayın
insan onayı olmadan *mümkün değildir*. Bunlar yorum değil, kodda ve veritabanı
şemasında zorlanan kısıtlardır — listesi [aşağıda](#pazarlık-edilemez-kısıtlar).

| | |
|---|---|
| **Spesifikasyon** | [`PolitikDesk_Master_Spec_v3.md`](PolitikDesk_Master_Spec_v3.md) — "ne ve neden" · 🔒 **v3.4 donduruldu** |
| **Yol haritası** | [`POLITIKDESK-FAZ-FAZ-YOL-HARITASI.md`](POLITIKDESK-FAZ-FAZ-YOL-HARITASI.md) — "ne zaman ve nasıl" |
| **Mevcut faz** | **Faz 7 — Dokümantasyon ve Plan Gerçekliği** · Faz 0–6 tamamlandı |
| **Faz kayıtları** | [Faz 0](docs/FAZ0-DURUM.md) · [Faz 1](docs/FAZ1-DURUM.md) · [Faz 2](docs/FAZ2-DURUM.md) · [Faz 3](docs/FAZ3-DURUM.md) · [denetim](docs/FAZ3-SONRASI-DENETIM.md) · [Faz 4](docs/FAZ4-DURUM.md) · [Faz 5](docs/FAZ5-KAPI.md) |
| **Güvenlik** | [`docs/guvenlik-notu.md`](docs/guvenlik-notu.md) — F4-09 gözden geçirmesi + bağımlılık taraması |
| **Ölçüm** | [`eval/eval_report.md`](eval/eval_report.md) · [eşik kalibrasyonu](eval/threshold_report.md) · [embedding kararı](docs/embedding-benchmark.md) · [üretim modeli kararı](docs/llm-generation-benchmark.md) |
| **Açık kalemler** | [`BACKLOG.md`](BACKLOG.md) — kapanan ve bekleyen her madde gerekçesiyle |
| **Kapsam** | Tek kullanıcılı **kişisel araç** — beta / ücretlendirme / hukuk adımları kapsam dışı |
| **MVP dikeyleri** | Makro ekonomi / para politikası (D4) + Yasama / Siyaset (`verticals/`, `political_memory/`) |

---

## Ne yapar

Çekirdek döngü beş adımdır ve ürünün tamamı bu döngüye hizmet eder:

```
TOPLA  ──▶  KÜMELE  ──▶  KANITLA  ──▶  BAĞLAMLANDIR  ──▶  TASLAK
16 kaynak   haber →      her iddia      olay ↔ olay        4 açı,
5 dk'da     olay         R0–R8 kural    ilişkileri         yalnız kanıttan
bir tur                  motoru                            beslenir
```

Ayırt edici nokta üçüncü adımdadır: **bir iddianın kanıt durumuna LLM karar veremez.**
`evidence_status` yalnızca deterministik kuralların (kaç bağımsız kaynak doğruluyor,
kurum kendi sayısını yayımlamış mı, çelişki var mı) çıktısıdır. Bu ayrım mimari
düzeyde zorlanır: `politikdesk/evidence/` paketi `politikdesk/llm/` paketini import
edemez ve bu yasak bir CI adımıdır.

---

## Hızlı başlangıç

**Windows:** `pd` · **Linux/macOS:** `make` — ikisi de aynı komut adlarını taşır.
(`make` Windows'ta kurulu gelmez; `pd.cmd` onun birebir karşılığıdır.)

```bat
copy .env.example .env        :: LLM anahtarını doldur (bkz. docs/llm-saglayici.md)
pd start                      :: TÜM yığını kurar ve ayağa kaldırır
pd sync                       :: config/sources.yml -> veritabanı
pd open                       :: Live Feed'i tarayıcıda açar
```

`pd start` şu sırayı uygular: Postgres + Redis → migration → API → worker + beat
(**yeniden kurarak**) → `deploy-check`. Sonrası kendiliğinden akar; boru hattı
5 dakikada bir toplar, embed eder, kümeler, iddia çıkarır, kanıta bağlar.

İlk kurulumda bir kez: `/onboarding/profile` — **Editoryal Kimlik Kartı** (10 soru).
Sonra günlük akış:

> **feed → olay → [Bilgilendir | Analiz Et | Eleştir] → yayın öncesi kontrol → kopyala**

### Günlük kullanım

| Adres | Ne var |
|---|---|
| `http://localhost:8000/feed` | Live Feed — gündem, salience sırasıyla |
| `http://localhost:8000/accountability` | Hesap Sor — vaat, icraat ve Sayıştay denetim zinciri |
| `http://localhost:8000/promises` | Siyasi Vaatler — taahhüt ve gerçekleşme takip tablosu |
| `http://localhost:8000/memory` | Political Memory — olay grafiği ve ilişki ağları |
| `http://localhost:8000/archive` | İçerik Arşivi — üretilen taslaklar ve geçmiş analizler |
| `http://localhost:8000/admin/` | sağlık panosu — kaynaklar + boru hattı aşamaları |
| `http://localhost:8000/admin/metrics` | 8 ürün metriği + LLM bütçe sayacı |
| `http://localhost:8000/briefing/<tarih>` | sabah/akşam brifingi |

### Arka plan işleri (bir kez kur, unut)

```bat
pd schedule-install           :: günlük yedek 03:30 + sağlık nöbeti 6 saatte bir
pd schedule-status            :: kurulu mu, en son ne zaman koştu?
```

> Docker Desktop'ın **açılışta başlaması** da gerekir:
> *Settings → General → "Start Docker Desktop when you sign in"*.
> Konteynerlerde `restart: unless-stopped` var; Docker kalkınca yığın kendi kalkar.

### Sağlık ve yedek

```bat
pd watchdog                   :: dışarıdan nöbet: konteyner + API + aşama
pd pipeline-health            :: hangi aşamada birikme var?
pd deploy-check               :: çalışan konteyner depodaki kodu mu taşıyor?
pd backup                     :: elle yedek al
pd backup-list                :: yedekleri ve dizini listele
pd backup-restore <tam-yol>   :: AYRI bir DB'ye geri yükle ve satır satır doğrula
```

> ⚠️ **`docker compose --profile workers up -d` tek başına yetmez.** Mevcut bir imaj
> varsa yeniden kurmaz. 13 Ağustos 2026'da beat Faz 1, worker Faz 2 imajıyla koşuyordu;
> kümeleme/iddia/brifing görevleri hiç zamanlanmadı ve toplanan 29 makalenin 18'i
> askıda kaldı. Depodaki kod doğruydu, testler yeşildi — kayma **çalışan imajdaydı.**
> `pd start` / `pd restart` `--build` ile kurar ve ardından `deploy-check` koşar.

**Yedekler bulut eşitlemesinin dışına yazılır** (varsayılan Windows'ta
`%LOCALAPPDATA%\PolitikDesk\backups`). OneDrive/Dropbox altındaki bir yol
*reddedilir*: yedek makale alıntısı, editoryal profil ve taslak içerir ve
BitLocker bulut kopyasını korumaz. Gerekçe `politikdesk/backup_policy.py`
başlığında; bilerek buluta yazmak için `PD_BACKUP_ALLOW_CLOUD=1`.

### Geliştirme

```bat
pd setup                      :: bağımlılıkları kur
pd ci                         :: lint + mypy + pip-audit + mimari kural + testler
pd ui-check                   :: arayüz denetimi — 7 ekran x 4 viewport
pd help                       :: tüm komutlar
```

Boru hattı adımları elle de koşturulabilir:
`pd ingest | embed | entities | cluster | claims | evidence | context | briefing | metrics`

---

## Mimari

Modüler monolit (Spec §11.2, D12). Mikroservis MVP'de yasak; Kubernetes MVP'de yasak.

```
politikdesk/
├── ingestion/   kaynak adaptörleri, normalizasyon, dedup          [Faz 1 ✓]
│   ├── adapters/  rss · official · resmi_gazete · tuik_sdmx · wp_rest · tbmm · sayistay · manual
│   ├── http.py    kibarlık: UA, oran sınırı, robots, geri çekilme, CA demeti
│   ├── guard.py   ToS koruması — forbidden kaynakta istisna
│   ├── dedup.py   content_hash + simhash + n-gram içermesi
│   └── topics.py  Çoklu dikey konu ve bağlam filtresi
├── verticals/   dikey soyutlamaları (makro ekonomi + yasama)     [Faz 5 ✓]
│   ├── base.py            Vertical sözleşmesi
│   ├── macro_economy.py   Makro ekonomi dikey kuralları
│   └── legislation.py     Yasama & Siyaset dikey kuralları
├── political_memory/ olay ilişkileri, vaat-denetim grafı, aday kısıtı [Faz 5 ✓]
│   ├── relation_engine.py   deterministik ilişki motoru (fulfils, fails, contradicts, updates)
│   ├── candidate_filter.py  sert aday tavanı (bounded retrieval)
│   ├── orchestrator.py      idempotent ilişki kurucu (s3.v1)
│   ├── accountability.py    kanıt zinciri ve vaka modelleri
│   └── service.py           ilişki CRUD ve sorgulama servisi
├── nlp/         embedding, ANN, NER, alias, iddia çıkarımı        [Faz 1/5 ✓]
│   └── opinion_classifier.py haber/yorum filtresi (hazır)
├── clustering/  olay kümeleme + merge/split                       [Faz 2 ✓]
│   ├── assigner.py      saf karar mantığı (DB'ye dokunmaz)
│   ├── centroid.py      artımlı merkez — üyelerinden yeniden hesaplanabilir
│   ├── indicators.py    aynı kurumun farklı göstergesi ayrı olaydır (B-62)
│   ├── numeric_guard.py "faiz %40" vs "%42" -> needs_review
│   └── merger.py        merge/split — %100 geri alınabilir
├── evidence/    ⛔ DETERMİNİSTİK — llm/ import edemez             [Faz 2/5 ✓]
│   ├── independence.py  Spec §8.2 bağımsız sayım (3 kural)
│   ├── rules.py         R0–R8 kural motoru (`attribution_verified` dahil)
│   └── salience.py      global 0–90 + kişisel 0–10
├── context/     olay-olay ilişkileri, tarihsel bağlam             [Faz 2 ✓]
├── editorial/   taslak üretimi (4 açı), pre-publish check         [Faz 3/5 ✓]
│   ├── guards.py          kanıtsız olayda üretim YOK (409, P1)
│   ├── generator.py       4 açı — Bilgilendir, Analiz Et, Eleştir, Hesap Sor
│   ├── grounding_check.py kanıtta olmayan sayı/tarih/alıntı (sert kapı)
│   ├── checker.py         Spec §14.4'ün 7 kontrolü + isnat dili uyarısı
│   ├── stance.py          dosya tabanlı editoryal hat (DB dışı)
│   └── profile_compiler.py form -> statik prompt bloğu (ideoloji YOK)
├── briefing/    sabah/akşam brifingi — DETERMİNİSTİK, LLM yok      [Faz 3 ✓]
├── web/         feed, hesap sor, vaatler, hafıza, arşiv, admin    [Faz 3/5 ✓]
│   ├── accountability_view.py  hesap sorma ve denetim görünümü
│   ├── promises_view.py        vaat takip tablosu
│   ├── memory_view.py          ilişki grafiği ve hafıza zinciri
│   ├── archive_view.py         taslak arşivi ve arama
│   └── ui/        tasarım sistemi — TEK kabuk, TEK stylesheet (DESIGN.md Ek A)
│       ├── tokens.py     renk/spacing/tipografi — ham hex YALNIZ burada
│       ├── css.py        stylesheet, tokens'tan türetilir
│       ├── icons.py      lucide satır içi SVG — tek set, emoji yok
│       ├── format.py     Türkçe sayı/tarih/para (Ek B)
│       ├── components.py DESIGN.md Bölüm 8 bileşen spec'leri
│       └── shell.py      sidebar + topbar + tema; TÜM sayfalar bunu kullanır
├── llm/         sağlayıcı-agnostik adapter + bütçe sayacı + alarm  [Faz 0/4 ✓]
├── api/         FastAPI router'ları + manuel içe aktarma          [Faz 0–1 ✓]
├── admin/       kaynak yönetimi, makale denetimi, sağlık          [Faz 1 ✓]
├── audit.py     denetim izi — tek giriş noktası, eylem sözleşmesi [Faz 4 ✓]
├── pipeline_health.py  aşama birikmesi alarmı (sessiz kopma)      [Faz 4 ✓]
└── backup_policy.py    yedek konumu kuralı — bulut dışı (B-84)     [Faz 5 ✓]

config/election_mode.py      Election Mode flag — hazır, varsayılan KAPALI [Faz 4 ✓]
certs/                       sunucuların göndermediği ARA sertifikalar     [Faz 5 ✓]
scripts/backup.py            yedek al / doğrula / ayrı DB'ye geri yükle    [Faz 4 ✓]
scripts/watchdog.py          dışarıdan sağlık nöbeti (Docker kapalıysa da) [Faz 4 ✓]
scripts/check_deployment.py  imaj kayması + varlık denetimi                [Faz 4/5 ✓]
scripts/perf_check.py        p95 + N+1 ölçümü                              [Faz 4 ✓]
```


### Pazarlık edilemez kısıtlar

Bunlar yorum değil, kodda ve şemada zorlanan sözleşmelerdir. Her satırın bir
denetleyicisi vardır; denetleyici kırmızıya dönerse CI kırılır.

| Kısıt | Nerede zorlanıyor |
|---|---|
| `evidence/` → `llm/` import yasak | `scripts/check_architecture.py`, CI adımı |
| `evidence_status` asla LLM çıktısı olamaz | Yukarıdaki kural + `evidence/` deterministik |
| Tahmin tipi iddia her zaman `unverified` (R0) | DB CHECK: `claims_prediction_always_unverified` |
| Alıntı ≤ 300 karakter, kanıt alıntısı ≤ 200 | DB CHECK: `excerpt_len`, `quote_span_len` |
| Tam metin hiçbir alanda saklanmaz | `tests/test_schema.py::test_no_full_text_column` |
| Saklanan salience yalnızca **global** (0–90); kişisel bileşen saklanmaz | DB CHECK: `events_salience_global_range` |
| `editorial_profiles`'ta ideolojik alan yok | `tests/test_schema.py` (statik + canlı şema) |
| Tek sayısal "doğruluk skoru" şemada yok | `tests/test_schema.py::test_no_truth_score_column` |
| Günlük LLM bütçe tavanı | `politikdesk/llm/budget.py` → `BudgetExceeded` |
| Yasaklı/incelenmemiş kaynaktan toplama | `ingestion/guard.py` → istisna |
| MVP dikeyi dışına çıkma | `ingestion/topics.py` — konu + Türkiye bağlamı |
| Manuel içe aktarmada SSRF | `adapters/manual.py::validate_url` |
| Kaynak sayısı sert sınırı (azami 15, kademeli) | `tests/test_sources_config.py` (D6 v3.3) |
| Olay merkezi üyelerinden yeniden hesaplanabilir kalır | `tests/test_clustering.py::test_remove_member_reverses_add_member` |
| Merge/split %100 geri alınabilir | `tests/test_merger.py` (canlı DB) |
| Salience'ta etkileşim (beğeni/paylaşım) girdisi yok | `tests/test_evidence.py::test_salience_has_no_engagement_input` (AST taraması) |
| LLM çıktısı `evidence_status` üretemez | `nlp/claims.py::CLAIMS_SCHEMA` + `FORBIDDEN_FIELDS` |
| Kanıt alıntısı kaynak metinde birebir geçmeli | `nlp/claims.py::verify_quote` |
| Embedding sağlayıcısı bilinmeyense uygulama açılmaz | `config.py::_provider_must_be_known` + `tests/test_config_and_api.py` |
| Kanıtsız olayda taslak üretimi | `editorial/guards.py` → HTTP 409 (LLM çağrısından **önce**) |
| İsimli kişi hakkında doğrulanmamış iddia varsa üretim yok | `editorial/guards.py` (Spec §15 madde 10) |
| Taslakta kanıtta olmayan sayı/tarih/alıntı | `editorial/grounding_check.py` + `tests/test_grounding.py` |
| Kanıta bağlanamayan sayısal iddia yayını engeller | `editorial/checker.py` → onay kutusu (Spec §14.4) |
| Taslak girdisi **yalnızca** claims+evidence | `tests/test_editorial.py::test_user_prompt_contains_only_claims_and_evidence` |
| Otomatik yayın kod yolu yok | `tests/test_web.py::test_no_automatic_publish_code_path_anywhere` |
| UI'da siyasi kaynak etiketi yok | `tests/test_web.py::test_ui_has_no_political_source_labels` |
| Brifing LLM çağırmaz | `tests/test_briefing.py::test_briefing_package_makes_no_llm_calls` |
| Kullanım izi gündem sıralamasına girmez | `tests/test_metrics.py::test_evidence_engine_cannot_read_usage_tables` |
| Prompt belgesi ile gönderilen prompt aynı | `tests/test_claims.py::test_prompt_file_matches_code` |
| Worker `hashing` embedder'a sessizce düşmez | `docker-compose.yml` + `Dockerfile` `ARG PD_EXTRAS` |
| Sözlüğe 3 karakterden kısa alias giremez | `tests/test_nlp.py::test_no_short_ambiguous_aliases` |
| Tanımlanan her Celery görevi zamanlanmış olmalı | `tests/test_tasks.py` (boru hattı sessizce kopmasın) |
| Çalışan konteyner depodaki kodu taşımalı | `scripts/check_deployment.py` → `pd deploy-check` |
| Kodun okuduğu veri dizinleri imaja girmeli | `tests/test_packaging.py` + varlık denetimi (B-85) |
| Bir iddia, onu söyleyen HER kaynağa bağlanmalı | `nlp/claims.py::group_claims_by_source` + `tests/test_corroboration.py` (B-79) |
| Sıfır iddia dönen olay sonsuza dek yeniden denenmemeli | `events.claims_attempted_at` + `MAX_CLAIM_ATTEMPTS` |
| Adaptörün yuttuğu hata turu "başarılı" yapmamalı | `adapters/base.py::FailureRecorder` (B-80) |
| Nabız ölçümü gün etiketini değil koşum anını okumalı | `metrics.computed_at` + `tests/test_hardening.py` (B-86) |
| Yedek bulut eşitlemesi altına yazılamaz | `politikdesk/backup_policy.py` + `tests/test_backup_policy.py` (B-84) |
| Denetim izine yazılan her eylem tanımlı olmalı | `audit.py::ACTIONS` + `tests/test_hardening.py` |
| Election Mode varsayılan KAPALI | `tests/test_election_mode.py::test_default_is_off` |
| Veritabanı/Redis portları dışarı açılmamalı | `docker-compose.yml` → `127.0.0.1:` bağlama (F4-09) |
| Bağımlılıklarda bilinen açık bulunmamalı | `pip-audit` — CI adımı, `pd audit` (B-83) |
| Arayüzde ham hex yok — renk yalnız `web/ui/tokens.py`'de | `tests/test_design_tokens.py` |
| Palet WCAG AA geçer (açık + koyu tema, her metin/zemin çifti) | aynı dosya — oranlar her koşumda hesaplanır |
| Arayüz fontlarında Türkçe glif tam (`İ ı Ğ ğ Ş ş`) | aynı dosya — woff2 cmap okunur |
| Ekranlarda emoji ikon yok, tek ikon seti | aynı dosya |
| `text-transform: uppercase` yok (Türkçede `i`→`I` bozar) | aynı dosya |

Bu kısıtlardan birini gevşetmek isteyen bir değişiklik, Spec'te sürüm artışı gerektirir.

---

## Kaynaklar

D6 (v3.4): Çoklu dikey (Makro Ekonomi + Yasama/Siyaset) mimarisinde toplam 16 kaynak tanımlı:

| Dikey | Kademe | Kaynak | Nasıl okunuyor |
|---|---|---|---|
| Makro Ekonomi | T1 | TCMB | RSS |
| Makro Ekonomi | T1 | TÜİK | SDMX (`nsiws.tuik.gov.tr`, Bearer belirteç) |
| Makro Ekonomi | T1 | Hazine ve Maliye Bakanlığı | WordPress REST (`/portal/v2/posts`) |
| Makro Ekonomi | T1 | Resmî Gazete | günlük fihrist (`/fihrist?tarih=…`) |
| Yasama & Siyaset | T1 | TBMM | Özel adaptör (`tbmm`) |
| Yasama & Siyaset | T1 | Sayıştay Başkanlığı | Özel adaptör (`sayistay`) |
| Yasama & Siyaset | T1 | Cumhurbaşkanlığı Kararnameleri | Özel adaptör (`cumhurbaskanligi`) |
| Genel / Medya | T2 | Anadolu Ajansı — Ekonomi & Güncel | RSS |
| Genel / Medya | T3 | Dünya · BloombergHT · TRT Haber · CNN Türk · Habertürk · NTV | RSS |

Kaynak kayıt defteri ve ToS durumları: [`docs/kaynak-kayit-defteri.md`](docs/kaynak-kayit-defteri.md).

---

## Teknoloji yığını (D11)

Python 3.12 · FastAPI · PostgreSQL 16 + pgvector · Redis + Celery ·
sunucu tarafı HTML (Next.js yerine — [İtiraz-8](docs/karar-itirazlari.md)) ·
sağlayıcı-agnostik LLM adapteri · Docker Compose · tek VPS

Embedding `multilingual-e5-large`, self-host (D16 — [ölçüm](docs/embedding-benchmark.md)).
Çıkarım ve üretim modelleri ayrıdır (Risk R6): ucuz model iddia çıkarır, pahalı
model taslak yazar.

---

## Kalite kapıları

Depoda yeşil olmayan hiçbir şey birleştirilmez. `pd ci` yerelde CI'ın koştuğu
her adımı koşar:

| Adım | Kapsam |
|---|---|
| `ruff` | biçim + lint (0 hata) |
| `mypy` | `politikdesk` paketi (141 dosya, 0 hata, `continue-on-error` **değil**) |
| `pip-audit` | bağımlılık açıkları (0 açık) |
| `check_architecture` | `evidence/` → `llm/` yasağı + Stance DB yasağı |
| `verify_arch_guard` | korumanın kendisi çalışıyor mu — canlı deney |
| `migrate up` ×2 | gerçek Postgres+pgvector (12 migration), ikinci koşum idempotent |
| `pytest` | **831 test** (52 dosya), canlı DB testleri dahil |

Model kalitesi ayrıca Golden Set üzerinde ölçülür (`pd eval`): kümeleme
precision/recall, `evidence_status` doğruluğu ve sayısal normalizasyon —
G2 eşikleriyle birlikte [`eval/eval_report.md`](eval/eval_report.md)'de.


---

## Kapsam disiplini

Yeni bir fikir geldiğinde: **yaz, yapma.** Fikir doğrudan [`BACKLOG.md`](BACKLOG.md)'ye
yazılır, aynı gün kodlanmaz (Yol Haritası §5). Filtreden geçse bile mevcut fazın
görev listesinde yoksa bir sonraki faza atanır. Yalnızca "beta engelleyici" veya
"hukuki zorunluluk" etiketli işler faz ortasında listeye girebilir — ve bu etiket
**yazılı gerekçe** gerektirir.

`BACKLOG.md` bir kayıp listesi değil, bir **sıralamadır**: kapanan her madde neyin
ölçüldüğüyle, açık kalan her madde neyi beklediğiyle birlikte kayıtlıdır.

---

## Lisans

Özel (proprietary). Bu depo hukuki tavsiye içermez. Proje tek kullanıcılı **kişisel
bir araç** olarak kararlaştırıldığı için hukuk danışmanlığı adımı (F0-10/F0-11)
kapsam dışına alınmıştır (bkz. [Faz 0 durumu](docs/FAZ0-DURUM.md)). Spec §12'deki
teknik kısıtlar — alıntı sınırı, tam metin saklamama, TTL, ToS koruması — kodda
korunmaktadır.
