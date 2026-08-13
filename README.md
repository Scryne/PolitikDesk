# PolitikDesk

> Makro ekonomi gündemi için, 8 kaynaktan beslenen, haberleri **olaya** çeviren, her iddiayı
> **deterministik kurallarla kanıta** bağlayan ve kaynaklı editoryal taslak üreten bir çalışma masası.

**AI senin yerine konuşmaz. AI senin daha iyi konuşabilmen için gündemi senin adına takip eder.**

| | |
|---|---|
| Spesifikasyon | [`PolitikDesk_Master_Spec_v3.md`](PolitikDesk_Master_Spec_v3.md) — "ne ve neden" · 🔒 **v3.1 donduruldu** |
| Yol haritası | [`PolitikDesk_Yol_Haritasi_v1.md`](PolitikDesk_Yol_Haritasi_v1.md) — "ne zaman ve nasıl" |
| Mevcut faz | **Faz 3 — Editoryal Katman ve Arayüz** ✅ 21/21 görev ([Faz 0](docs/FAZ0-DURUM.md) · [Faz 1](docs/FAZ1-DURUM.md) · [Faz 2](docs/FAZ2-DURUM.md) · [Faz 3](docs/FAZ3-DURUM.md) · [denetim](docs/FAZ3-SONRASI-DENETIM.md)) |
| Ölçüm | [`eval/eval_report.md`](eval/eval_report.md) · [eşik kalibrasyonu](eval/threshold_report.md) · [embedding kararı](docs/embedding-benchmark.md) · [üretim modeli kararı](docs/llm-generation-benchmark.md) |
| Kapsam | Tek kullanıcılı **kişisel araç** — beta/ücretlendirme/hukuk adımları kapsam dışı |
| MVP dikeyi | Makro ekonomi / para politikası (D4) |

---

## Hızlı başlangıç

```bash
cp .env.example .env          # LLM anahtarını doldur (bkz. docs/llm-saglayici.md)
make up                       # Postgres + pgvector + Redis + API
make sync                     # config/sources.yml -> veritabanı
make ingest                   # bir toplama turu (gerçek akışlardan)
open http://localhost:8000/feed       # Live Feed
open http://localhost:8000/admin/     # sağlık panosu
```

Editoryal akış (Faz 3):

```bash
make claims                   # olaylardan iddia çıkar (LLM)
make evidence                 # kanıt durumu + salience
open http://localhost:8000/onboarding/profile   # Editoryal Kimlik Kartı (7 soru)
# feed -> olay -> [Bilgilendir|Analiz Et|Eleştir] -> yayın öncesi kontrol -> kopyala
make briefing                 # sabah brifingi üret (+ SMTP varsa gönder)
make metrics                  # 8 ürün metriğini topla
```

Sürekli çalıştırma (5 dakikalık döngü):

```bash
make workers                  # worker + beat'i YENİDEN KURARAK başlatır
make deploy-check             # konteynerler depodaki kodu mu taşıyor?
```

> ⚠️ **`docker compose --profile workers up -d` tek başına yetmez.** Mevcut bir imaj
> varsa yeniden kurmaz. 13 Ağustos 2026'da beat Faz 1, worker Faz 2 imajıyla koşuyordu;
> kümeleme/iddia/brifing görevleri hiç zamanlanmadı ve toplanan 29 makalenin 18'i
> askıda kaldı. Depodaki kod doğruydu, testler yeşildi — kayma **çalışan imajdaydı.**
> `make workers` `--build` ile kurar ve ardından `deploy-check` koşar.

Yerel geliştirme (Docker olmadan test koşmak için):

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
make setup
make ci                        # lint + mypy + mimari kural + testler
```

`make help` tüm komutları listeler.

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
├── llm/         sağlayıcı-agnostik adapter + bütçe sayacı         [Faz 0 ✓]
├── api/         FastAPI router'ları + manuel içe aktarma          [Faz 0–1 ✓]
└── admin/       kaynak yönetimi, makale denetimi, sağlık          [Faz 1 ✓]
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
| Çalışan konteyner depodaki kodu taşımalı | `scripts/check_deployment.py` → `make deploy-check` |

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
