# PolitikDesk

> Makro ekonomi gündemi için, 8 kaynaktan beslenen, haberleri **olaya** çeviren, her iddiayı
> **deterministik kurallarla kanıta** bağlayan ve kaynaklı editoryal taslak üreten bir çalışma masası.

**AI senin yerine konuşmaz. AI senin daha iyi konuşabilmen için gündemi senin adına takip eder.**

| | |
|---|---|
| Spesifikasyon | [`PolitikDesk_Master_Spec_v3.md`](PolitikDesk_Master_Spec_v3.md) — "ne ve neden" · 🔒 **v3.1 donduruldu** |
| Yol haritası | [`PolitikDesk_Yol_Haritasi_v1.md`](PolitikDesk_Yol_Haritasi_v1.md) — "ne zaman ve nasıl" |
| Mevcut faz | **Faz 4 — Sertleştirme** ✅ 8/8 görev ([Faz 0](docs/FAZ0-DURUM.md) · [Faz 1](docs/FAZ1-DURUM.md) · [Faz 2](docs/FAZ2-DURUM.md) · [Faz 3](docs/FAZ3-DURUM.md) · [denetim](docs/FAZ3-SONRASI-DENETIM.md) · [Faz 4](docs/FAZ4-DURUM.md)) |
| Güvenlik | [`docs/guvenlik-notu.md`](docs/guvenlik-notu.md) — F4-09 gözden geçirmesi |
| Ölçüm | [`eval/eval_report.md`](eval/eval_report.md) · [eşik kalibrasyonu](eval/threshold_report.md) · [embedding kararı](docs/embedding-benchmark.md) · [üretim modeli kararı](docs/llm-generation-benchmark.md) |
| Kapsam | Tek kullanıcılı **kişisel araç** — beta/ücretlendirme/hukuk adımları kapsam dışı |
| MVP dikeyi | Makro ekonomi / para politikası (D4) |

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

`pd start` şunu yapar: Postgres + Redis → migration → API → worker + beat
(**yeniden kurarak**) → `deploy-check`. Sonrası kendiliğinden akar; boru
hattı 5 dakikada bir toplar, embed eder, kümeler, iddia çıkarır, kanıta bağlar.

Günlük kullanım:

```
http://localhost:8000/feed        Live Feed — gündem
http://localhost:8000/admin/      sağlık panosu (kaynaklar + boru hattı aşamaları)
http://localhost:8000/admin/metrics   8 ürün metriği
```

İlk kurulumda bir kez: `/onboarding/profile` — Editoryal Kimlik Kartı (7 soru).
Sonra akış: **feed → olay → [Bilgilendir | Analiz Et | Eleştir] → yayın öncesi
kontrol → kopyala.**

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
pd backup                     :: elle yedek al
pd backup-restore <dosya>     :: AYRI bir DB'ye geri yükle ve satır satır doğrula
```

> ⚠️ **`docker compose --profile workers up -d` tek başına yetmez.** Mevcut bir imaj
> varsa yeniden kurmaz. 13 Ağustos 2026'da beat Faz 1, worker Faz 2 imajıyla koşuyordu;
> kümeleme/iddia/brifing görevleri hiç zamanlanmadı ve toplanan 29 makalenin 18'i
> askıda kaldı. Depodaki kod doğruydu, testler yeşildi — kayma **çalışan imajdaydı.**
> `pd start` / `pd restart` `--build` ile kurar ve ardından `deploy-check` koşar.

### Geliştirme

```bat
pd setup                      :: bağımlılıkları kur
pd ci                         :: lint + mypy + mimari kural + testler
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
│   ├── adapters/  rss · official (TCMB/TÜİK/Hazine) · manual
│   ├── http.py    kibarlık: UA, oran sınırı, robots, geri çekilme
│   ├── guard.py   ToS koruması — forbidden kaynakta istisna
│   ├── dedup.py   content_hash + simhash + n-gram içermesi
│   └── topics.py  MVP konu + Türkiye bağlamı filtresi
├── nlp/         embedding, ANN, NER, alias çözümleme              [Faz 1 ✓]
├── clustering/  olay kümeleme + merge/split                       [Faz 2 ✓]
│   ├── assigner.py      saf karar mantığı (DB'ye dokunmaz)
│   ├── centroid.py      artımlı merkez — üyelerinden yeniden hesaplanabilir
│   ├── numeric_guard.py "faiz %40" vs "%42" -> needs_review
│   └── merger.py        merge/split — %100 geri alınabilir
├── evidence/    ⛔ DETERMİNİSTİK — llm/ import edemez             [Faz 2 ✓]
│   ├── independence.py  Spec §8.2 bağımsız sayım (3 kural)
│   ├── rules.py         R0–R7 kural motoru
│   └── salience.py      global 0–90 + kişisel 0–10
├── context/     olay-olay ilişkileri, tarihsel bağlam             [Faz 2 ✓]
├── editorial/   taslak üretimi, pre-publish check                 [Faz 3 ✓]
│   ├── guards.py          kanıtsız olayda üretim YOK (409, P1)
│   ├── generator.py       3 açı — girdi yalnızca claims+evidence
│   ├── grounding_check.py kanıtta olmayan sayı/tarih/alıntı (sert kapı)
│   ├── checker.py         Spec §14.4'ün 6 kontrolü + engelleyici durum
│   └── profile_compiler.py  form -> statik prompt bloğu (ideoloji YOK)
├── briefing/    sabah/akşam brifingi — DETERMİNİSTİK, LLM yok      [Faz 3 ✓]
├── web/         feed, olay sayfası, taslak, brifing, metrik panosu [Faz 3 ✓]
├── llm/         sağlayıcı-agnostik adapter + bütçe sayacı + alarm  [Faz 0/4 ✓]
├── api/         FastAPI router'ları + manuel içe aktarma          [Faz 0–1 ✓]
├── admin/       kaynak yönetimi, makale denetimi, sağlık          [Faz 1 ✓]
├── audit.py     denetim izi — tek giriş noktası, eylem sözleşmesi [Faz 4 ✓]
└── pipeline_health.py  aşama birikmesi alarmı (sessiz kopma)      [Faz 4 ✓]

config/election_mode.py   Election Mode flag — hazır, varsayılan KAPALI  [Faz 4 ✓]
scripts/backup.py         yedek al / doğrula / ayrı DB'ye geri yükle     [Faz 4 ✓]
scripts/watchdog.py       dışarıdan sağlık nöbeti (Docker kapalıysa da)  [Faz 4 ✓]
scripts/perf_check.py     p95 + N+1 ölçümü                               [Faz 4 ✓]
```

### Pazarlık edilemez kısıtlar

Bunlar yorum değil, kodda ve şemada zorlanan sözleşmelerdir:

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
| Kaynak sayısı sert sınırı (8) | `tests/test_sources_config.py` |
| Olay merkezi üyelerinden yeniden hesaplanabilir kalır | `tests/test_clustering.py::test_remove_member_reverses_add_member` |
| Merge/split %100 geri alınabilir | `tests/test_merger.py` (canlı DB) |
| Salience'ta etkileşim (beğeni/paylaşım) girdisi yok | `tests/test_evidence.py::test_salience_has_no_engagement_input` (AST taraması) |
| LLM çıktısı `evidence_status` üretemez | `nlp/claims.py::CLAIMS_SCHEMA` + `FORBIDDEN_FIELDS` |
| Kanıt alıntısı kaynak metinde birebir geçmeli | `nlp/claims.py::verify_quote` |
| Embedding sağlayıcısı bilinmeyense uygulama açılmaz | `config.py::_provider_must_be_known` + `tests/test_config_and_api.py` |
| Kanıtsız olayda taslak üretimi | `editorial/guards.py` → HTTP 409 (LLM çağrısından **önce**) |
| İsimli kişi hakkında doğrulanmamış iddia varsa üretim yok | `editorial/guards.py` (Spec §15 madde 10) |
| Taslakta kanıtta olmayan sayı/tarih/alıntı | `editorial/grounding_check.py` + `tests/test_grounding.py` (19 test) |
| Kanıta bağlanamayan sayısal iddia yayını engeller | `editorial/checker.py` → onay kutusu (Spec §14.4) |
| Taslak girdisi **yalnızca** claims+evidence | `tests/test_editorial.py::test_user_prompt_contains_only_claims_and_evidence` |
| Otomatik yayın kod yolu yok | `tests/test_web.py::test_no_automatic_publish_code_path_anywhere` |
| UI'da siyasi kaynak etiketi yok | `tests/test_web.py::test_ui_has_no_political_source_labels` |
| Brifing LLM çağırmaz | `tests/test_briefing.py::test_briefing_package_makes_no_llm_calls` |
| Kullanım izi gündem sıralamasına girmez | `tests/test_metrics.py::test_evidence_engine_cannot_read_usage_tables` |
| Prompt belgesi ile gönderilen prompt aynı | `tests/test_editorial.py::test_prompt_file_matches_code` |
| Worker `hashing` embedder'a sessizce düşmez | `docker-compose.yml` (worker `PD_EMBEDDING_*`) + `Dockerfile` `ARG PD_EXTRAS` |
| Sözlüğe 3 karakterden kısa alias giremez | `tests/test_nlp.py::test_no_short_ambiguous_aliases` |
| Tanımlanan her Celery görevi zamanlanmış olmalı | `tests/test_tasks.py` (boru hattı sessizce kopmasın) |
| Çalışan konteyner depodaki kodu taşımalı | `scripts/check_deployment.py` → `pd deploy-check` |
| Bir iddia, onu söyleyen HER kaynağa bağlanmalı | `nlp/claims.py::group_claims_by_source` + `tests/test_corroboration.py` (B-79) |
| Sıfır iddia dönen olay sonsuza dek yeniden denenmemeli | `events.claims_attempted_at` + `MAX_CLAIM_ATTEMPTS` |
| Adaptörün yuttuğu hata turu "başarılı" yapmamalı | `adapters/base.py::FailureRecorder` (B-80) |
| Denetim izine yazılan her eylem tanımlı olmalı | `audit.py::ACTIONS` + `tests/test_hardening.py` |
| Election Mode varsayılan KAPALI | `tests/test_election_mode.py::test_default_is_off` |
| Veritabanı/Redis portları dışarı açılmamalı | `docker-compose.yml` → `127.0.0.1:` bağlama (F4-09) |

Bu kısıtlardan birini gevşetmek isteyen bir değişiklik, Spec'te sürüm artışı gerektirir.

---

## Teknoloji yığını (D11)

Python 3.12 · FastAPI · PostgreSQL 16 + pgvector · Redis + Celery ·
sunucu tarafı HTML (Next.js yerine — [İtiraz-8](docs/karar-itirazlari.md)) ·
sağlayıcı-agnostik LLM adapteri · Docker Compose · tek VPS

---

## Kapsam disiplini

Yeni bir fikir geldiğinde: **yaz, yapma.** Fikir doğrudan [`BACKLOG.md`](BACKLOG.md)'ye yazılır,
aynı gün kodlanmaz (Yol Haritası §5). MVP'ye dahil olmayan 22 kalem
[Spec §14.2](PolitikDesk_Master_Spec_v3.md)'de listelidir ve `BACKLOG.md`'de faza atanmıştır.

---

## Lisans

Özel (proprietary). Bu depo hukuki tavsiye içermez. Proje tek kullanıcılı **kişisel
bir araç** olarak kararlaştırıldığı için hukuk danışmanlığı adımı (F0-10/F0-11)
kapsam dışına alınmıştır (bkz. [Faz 0 durumu](docs/FAZ0-DURUM.md)). Spec §12'deki
teknik kısıtlar — alıntı sınırı, tam metin saklamama, TTL, ToS koruması — kodda
korunmaktadır.
