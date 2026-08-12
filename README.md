# PolitikDesk

> Makro ekonomi gündemi için, 8 kaynaktan beslenen, haberleri **olaya** çeviren, her iddiayı
> **deterministik kurallarla kanıta** bağlayan ve kaynaklı editoryal taslak üreten bir çalışma masası.

**AI senin yerine konuşmaz. AI senin daha iyi konuşabilmen için gündemi senin adına takip eder.**

| | |
|---|---|
| Spesifikasyon | [`PolitikDesk_Master_Spec_v3.md`](PolitikDesk_Master_Spec_v3.md) — "ne ve neden" · 🔒 **v3.1 donduruldu** |
| Yol haritası | [`PolitikDesk_Yol_Haritasi_v1.md`](PolitikDesk_Yol_Haritasi_v1.md) — "ne zaman ve nasıl" |
| Mevcut faz | **Faz 2 — Olay Zekâsı** ([Faz 0](docs/FAZ0-DURUM.md) · [Faz 1](docs/FAZ1-DURUM.md) · [Faz 2](docs/FAZ2-DURUM.md)) |
| Kapsam | Tek kullanıcılı **kişisel araç** — beta/ücretlendirme/hukuk adımları kapsam dışı |
| MVP dikeyi | Makro ekonomi / para politikası (D4) |

---

## Hızlı başlangıç

```bash
cp .env.example .env          # ANTHROPIC_API_KEY'i doldur (LLM gerekiyorsa)
make up                       # Postgres + pgvector + Redis + API
make sync                     # config/sources.yml -> veritabanı
make ingest                   # bir toplama turu (gerçek akışlardan)
open http://localhost:8000/admin/     # sağlık panosu
```

Sürekli çalıştırma (5 dakikalık döngü):

```bash
docker compose --profile workers up -d
```

Yerel geliştirme (Docker olmadan test koşmak için):

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
make setup
make ci                        # lint + mimari kural + testler
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
├── clustering/  olay kümeleme + merge/split                       [Faz 2 🚧]
│   ├── assigner.py      saf karar mantığı (DB'ye dokunmaz)
│   ├── centroid.py      artımlı merkez — üyelerinden yeniden hesaplanabilir
│   └── numeric_guard.py "faiz %40" vs "%42" -> needs_review
├── evidence/    ⛔ DETERMİNİSTİK — llm/ import edemez             [Faz 2]
├── context/     olay-olay ilişkileri, tarihsel bağlam             [Faz 2]
├── editorial/   taslak üretimi, pre-publish check                 [Faz 3]
├── briefing/    sabah/akşam brifingi                              [Faz 3]
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

Bu kısıtlardan birini gevşetmek isteyen bir değişiklik, Spec'te sürüm artışı gerektirir.

---

## Teknoloji yığını (D11)

Python 3.12 · FastAPI · PostgreSQL 16 + pgvector · Redis + Celery · Next.js 15 (Faz 3) ·
Anthropic Claude (adapter arkasında) · Docker Compose · tek VPS

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
