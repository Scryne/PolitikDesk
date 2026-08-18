<div align="center">

# 🏛️ PolitikDesk

**AI Destekli Politik İstihbarat, Deterministik Kanıt Motoru ve Editoryal Çalışma Masası**

[![Python Version](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16-pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Celery + Redis](https://img.shields.io/badge/Celery-Redis_5.2-CC0000?style=for-the-badge&logo=redis&logoColor=white)](https://docs.celeryq.dev)
[![Tests](https://img.shields.io/badge/Tests-1087_Passing-success?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org)
[![Code Style](https://img.shields.io/badge/Ruff_&_Mypy-Strict_0_Errors-blueviolet?style=for-the-badge&logo=mypy&logoColor=white)](https://mypy-lang.org)
[![Architecture Guard](https://img.shields.io/badge/Architecture_Guard-100%25_Deterministic-brightgreen?style=for-the-badge&logo=shield&logoColor=white)](docs/guvenlik-notu.md)

<p align="center">
  <b>Makro ekonomi, yasama, siyaset ve sosyal medya gündemini 88 yapılandırılmış resmî ve bağımsız kaynaktan toplayan; haberleri olaya çeviren, her iddiayı deterministik kurallarla kanıta bağlayan ve kaynaklı editoryal taslak üreten kişisel istihbarat terminali.</b>
</p>

---

</div>

> ### 🛡️ Temel Ürün Sözleşmesi
> **"AI senin yerine konuşmaz. AI senin daha iyi konuşabilmen için gündemi senin adına takip eder."**
>
> PolitikDesk'in tüm mimari kararları bu sözleşmeyi korumak üzere tasarlanmıştır:
> 1. **Kanıt motoru LLM'i import edemez.** Bir iddianın doğruluk durumuna yapay zekâ karar veremez; `evidence_status` yalnızca deterministik kuralların çıktısıdır.
> 2. **Kanıtsız olayda taslak üretimi başlamaz.** (HTTP 409 sert kapı).
> 3. **İnsan onayı olmadan otomatik yayın kod yolu yoktur.** Nihai editoryal irade daima kullanıcıdadır.

---

## 📑 İçindekiler

- [Öne Çıkan Özellikler](#-öne-çıkan-özellikler)
- [Çekirdek Boru Hattı (5 Adım)](#-çekirdek-boru-hattı-5-adım)
- [Mimari & Dizin Yapısı](#-mimari--dizin-yapısı)
- [Pazarlık Edilemez Mimari Kısıtlar](#-pazarlık-edilemez-mimari-kısıtlar)
- [Kaynak Yelpazesi ve Ekosistem](#-kaynak-yelpazesi-ve-ekosistem)
- [Hızlı Başlangıç & Kurulum](#-hızlı-başlangıç--kurulum)
- [Ekranlar & REST API](#-ekranlar--rest-api)
- [Kalite Kapıları & Güvenlik](#-kalite-kapıları--güvenlik)
- [Teknoloji Yığını](#-teknoloji-yığını)
- [Lisans](#-lisans)

---

## 🌟 Öne Çıkan Özellikler

### 1. 🔍 Çoklu Dikey İstihbarat & Çapraz Teyit
* **Makro Ekonomi & Para Politikası (D4):** TCMB faiz kararları ve duyuruları, TÜİK SDMX göstergeleri, Hazine ve Maliye Bakanlığı bültenleri, Resmî Gazete günlük fihristi.
* **Yasama, Siyaset & Denetim (S3/S4):** TBMM kanun teklifleri, Sayıştay denetim bulguları, Cumhurbaşkanlığı Kararnameleri ve siyasi aktör beyanları.
* **Sosyal Medya & X (Twitter) Radarı:** 6 tematik liste üzerinden 500+ canlı aktör akışı, **R7/R8 Epistemik Tavan** kuralı ve **TCK 217/A & Hakaret Önleme Çift Güvenlik Kapısı** (`SocialSecurityGate`).

### 2. 🧠 Deterministik Kanıt Motoru (R0–R8 Rules)
* İddialar **R0–R8** matematiksel kurallarıyla bağımsız teyit havuzlarında sınanır.
* **Mülkiyet Ayrıştırması (`independence_group`):** Aynı medya grubuna ait 5 gazete tek bir bağımsız kaynak sayılır.
* **Epistemik Tavan:** Bir iddia ne kadar viral olursa olsun, resmî veri veya doğrudan kurumsal belge olmadan `verified` statüsüne yükselemez.

### 3. 🎯 Medya Kör Noktası & Çerçeveleme Radarı (Blindspot Radar)
* Bir olayın medyada nasıl konumlandığını anlık analiz eder:
  * `balanced`: Kamu, ana akım ve bağımsız medya dengeli gördü.
  * `independent_only`: Yalnızca bağımsız medya gördü (*Ana akım kör noktası*).
  * `official_only`: Yalnızca resmî kurumlar açıkladı.
  * `mainstream_only`: Bağımsız medyanın henüz teyit etmediği çerçeveleme.

### 4. 🔄 Söylem Değişikliği & Zıtlık Radarı (Stance Shift Detector)
* Siyasi aktörlerin geçmiş vaatleri, meclis oylamaları ve bugünkü açıklamaları arasındaki 180° yön değişikliklerini, çelişkili beyanları ve revizyonları deterministik ilişki grafiğiyle otomatik tespit eder.

### 5. ✍️ Editoryal Çalışma Masası & Grounding Check
* **4 Editoryal Açı:** `Bilgilendir`, `Analiz Et`, `Eleştir`, `Hesap Sor`.
* **Sert Halüsinasyon Kapısı (`grounding_check`):** Kanıtta bulunmayan hiçbir sayı, oran, para birimi veya alıntı taslağa giremez.
* **Dışa Aktarılabilir Kanıt Kartı:** Sosyal medya ve bültenler için yapılandırılmış, kaynaklı infografik veri kartı (`/api/events/{id}/evidence-card`).

---

## 🔄 Çekirdek Boru Hattı (5 Adım)

Sistem her 5 dakikada bir otomatik olarak şu döngüyü işletir:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   1. TOPLA   │ ──▶ │  2. KÜMELE   │ ──▶ │  3. KANITLA  │ ──▶ │ 4. BAĞLAMLAMA│ ──▶ │  5. TASLAK   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
  88 Kaynak            multilingual-e5      R0–R8 Kuralları       Political Memory     4 Editoryal Açı
  RSS / SDMX / WP      Artımlı Centroid     ⛔ LLM Yasak          İlişki Grafı         Grounding Check
  TBMM / X Listeleri   Sayısal Muhafız      Bağımsız Sayım        Vaat & Denetim       İsnat Denetimi
```

1. **Topla (Ingestion):** Kibar bot ilkeleri (Rate limiting, robots.txt, Exponential Backoff, CA demeti) ile 88 yapılandırılmış kaynaktan veri çeker. İçerik hash'i ve SimHash ile tekilleştirir.
2. **Kümele (Clustering):** `multilingual-e5-large` embedding vektörleriyle haberleri olaylara bağlar. Aynı kurumun farklı göstergeleri ayrı olayda tutulur; sayısal çelişkiler `needs_review` bayrağı alır.
3. **Kanıtla (Evidence):** Deterministik kurallarla iddiaları kanıt durumuna (`verified`, `partially_verified`, `disputed`, `unverified`, `prediction`) bağlar.
4. **Bağlamlandır (Context & Memory):** Yeni olayı geçmiş Sayıştay raporları, TBMM oylamaları, vaatler ve aktör siciliyle (`fulfils`, `fails`, `contradicts`, `updates`) bağlar.
5. **Taslak & Denetim (Editorial):** Kullanıcının editoryal profiline uygun olarak 4 farklı editoryal açıda kaynaklı taslak üretir; yayın öncesi 7 maddelik güvenlik kontrolünden geçirir.

---

## 🏗️ Mimari & Dizin Yapısı

PolitikDesk, **Modüler Monolit** (Spec §11.2) prensibiyle tasarlanmıştır.

```
politikdesk/
├── ingestion/           Kaynak adaptörleri, ToS muhafazası, normalizasyon, dedup
│   ├── adapters/        rss · official · resmi_gazete · tuik_sdmx · wp_rest · tbmm · sayistay · twitter
│   ├── http.py          Kibar istemci (User-Agent, rate limit, SSL bundle)
│   ├── guard.py         Kaynak izin defteri ve güvenlik kontrolü
│   └── dedup.py         SimHash ve içerik parmak izi eşleme
├── verticals/           Dikey soyutlama ve kural katmanı
│   ├── macro_economy.py Makro ekonomi gösterge & para politikası kuralları
│   └── legislation.py   Yasama, TBMM & Sayıştay dikey sözleşmeleri
├── political_memory/    Siyasi hafıza, ilişki grafı ve söylem takibi
│   ├── relation_engine.py  İlişki kurucu (fulfils, fails, contradicts)
│   ├── stance_shift.py     Söylem değişikliği ve 180° zıtlık radarı
│   ├── models.py & scoring.py  Ağ modelleri ve ilişki puanlaması
│   └── service.py          Sorgulama, arama ve sayfalama servisi
├── nlp/                 Embedding, NER, iddia çıkarımı, sınıflandırıcı
├── clustering/          Olay kümeleme, artımlı merkez, sayısal koruma
├── evidence/            ⛔ DETERMİNİSTİK KANIT MOTORU (LLM Import Edemez)
│   ├── rules.py         R0–R8 Kanıt kural motoru
│   ├── independence.py  Mülkiyet ve grup bazlı bağımsız sayım
│   ├── blindspot.py     Medya kör noktası ve çerçeveleme analizi
│   └── salience.py      Global salience (0–90) hesaplama
├── editorial/           Taslak üretimi, grounding ve pre-publish güvenlik
│   ├── guards.py        Kanıtsız olay üretim engeli (409 Guard)
│   ├── generator.py     4 Açı taslak üretici (Bilgilendir, Analiz, Eleştir, Hesap Sor)
│   ├── grounding_check.py  Kanıtta olmayan veri/sayı sert kapısı
│   └── checker.py       7 Maddelik yayın öncesi güvenlik denetimi
├── briefing/            Sabah / Akşam editoryal bülten derleyicisi (Deterministik)
├── web/                 UI görünümleri, FastAPI rotaları, REST API, SSE canlı akış
│   └── ui/              Tasarım sistemi — Sıfır harici CSS/CDN, WCAG AA, Lucide SVG
└── llm/                 Sağlayıcı-agnostik bağdaştırıcı, bütçe sayacı ve harcama tavanı
```

---

## 🔒 Pazarlık Edilemez Mimari Kısıtlar

Bu kurallar kod mimarisinde, Pydantic şemalarında ve veritabanı kısıtlarında zorunlu kılınmıştır. Her biri CI testleriyle denetlenir:

| Kısıt | Açıklama | Nerede Zorlanıyor? |
|---|---|---|
| **Deterministik Kanıt** | `evidence/` paketi `llm/` paketini import edemez. | `scripts/check_architecture.py` (CI Adımı) |
| **Epistemik Statü** | `evidence_status` asla bir LLM çıktısı olamaz. | `politikdesk/nlp/claims.py` (Forbidden Fields) |
| **Kanıtsız Taslak Yasağı** | Kanıtlanmamış olay için editoryal taslak üretilemez. | `editorial/guards.py` (HTTP 409 Sert Kapı) |
| **Sert Halüsinasyon Kapısı**| Taslakta kanıtta geçmeyen sayı, oran, tarih veya alıntı yer alamaz. | `editorial/grounding_check.py` |
| **Otomatik Yayın Yasağı**| İnsan onayı olmadan harici sisteme otomatik yayın kod yolu yoktur. | `tests/test_web.py` |
| **Telif & Gizlilik Koruması**| Orijinal makalenin tam metni hiçbir veritabanı alanında saklanmaz. | DB CHECK & `tests/test_schema.py` |
| **Alıntı Uzunluk Sınırı** | Makale alıntısı azami 300 karakter, kanıt alıntısı azami 200 karakterdir. | DB CHECK: `excerpt_len`, `quote_span_len` |
| **Bulut Dışı Yedekleme** | Yedekler BitLocker korumasız bulut eşitleme dizinlerine yazılamaz. | `politikdesk/backup_policy.py` |
| **Güvenli Ağ İzolasyonu** | PostgreSQL ve Redis portları dış dünyaya açılamaz (`127.0.0.1`). | `docker-compose.yml` (F4-09 Kuralı) |
| **Tasarım Bütünlüğü** | Arayüz şablonlarında ham hex kod yer alamaz; WCAG AA renk kontrastı zorunludur. | `politikdesk/web/ui/tokens.py` |

---

## 📡 Kaynak Yelpazesi ve Ekosistem

PolitikDesk, yankı odalarını engellemek için kaynak dağılımını dengeli tutar (Bağımsız kaynak oranı ≥ %75):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             KAYNAK HAVUZU                                   │
├───────────────────────┬──────────────────────────┬──────────────────────────┤
│    T1: RESMÎ KURUMLAR │   T2: AJANS / ANA AKIM   │   T3: BAĞIMSIZ MEDYA     │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ • TCMB                │ • Anadolu Ajansı         │ • BBC Türkçe             │
│ • TÜİK (SDMX API)     │ • BloombergHT            │ • Gazete Duvar           │
│ • Hazine & Maliye Bak.│ • NTV                    │ • Diken                  │
│ • Resmî Gazete        │ • Habertürk              │ • T24                    │
│ • TBMM & Sayıştay     │ • TRT Haber              │ • Sözcü / BirGün / Cumh. │
└───────────────────────┴──────────────────────────┴──────────────────────────┘
```

---

## 🚀 Hızlı Başlangıç & Kurulum

### Gereksinimler
* **Python 3.12+**
* **Docker & Docker Desktop** (PostgreSQL 16 + pgvector ve Redis için)
* **İşletim Sistemi:** Windows (`pd.cmd`) veya Linux/macOS (`make`)

### 1. Depoyu Klonlayın ve Ortamı Hazırlayın
```bash
git clone https://github.com/Scryne/PolitikDesk.git
cd PolitikDesk

# Ortam dosyasını oluşturun ve LLM anahtarınızı girin
cp .env.example .env
```

### 2. Tek Komutla Başlatın
Windows'ta `pd`, Linux/macOS'ta `make` kullanılır:

```bat
:: Windows
pd setup                      :: Python sanal ortamı ve bağımlılıkları kurar
pd start                      :: Docker konteynerlerini, migration'ları ve servisleri ayağa kaldırır
pd sync                       :: Kaynak yapılandırmalarını veritabanına işler
pd open                       :: Web arayüzünü tarayıcıda açar (http://localhost:8000/feed)
```

```bash
# Linux / macOS
make setup
make start
make sync
make open
```

---

## 💻 Ekranlar & REST API

### Web Çalışma Masası

| Sayfa Adresi | Açıklama ve İşlev |
|---|---|
| `http://localhost:8000/feed` | **Live Feed:** Anlık salience ve önem sırasına göre olay akışı |
| `http://localhost:8000/war-room` | **Kumanda Odası:** Canlı gündem radarı, kritik kırılmalar ve resmî gösterge şeridi |
| `http://localhost:8000/accountability` | **Hesap Sor:** Vaat, icraat ve Sayıştay denetim bulgusu takip tablosu |
| `http://localhost:8000/promises` | **Siyasi Vaatler:** Taahhütler ve gerçekleşme oranları |
| `http://localhost:8000/memory` | **Siyasi Hafıza:** Aktör ilişkileri, geçmiş beyanlar ve zıtlıklar |
| `http://localhost:8000/archive` | **İçerik Arşivi:** Üretilen editoryal taslaklar ve geçmiş analizler |
| `http://localhost:8000/briefing/{tarih}` | **Gündem Brifingi:** Sabah (08:30) ve akşam (18:30) özetleri |
| `http://localhost:8000/admin/` | **Sağlık Panosu:** Kaynak durumu, pipeline aşamaları ve bütçe sayacı |

### Programatik REST API

* `GET /api/events/{id}/evidence-card` — Yapılandırılmış sosyal medya kanıt kartı JSON çıktısı.
* `GET /api/events/{id}/export?format=…` — Tek olayın 11 kanala dışa aktarımı: `markdown`, `text`,
  `json`, `svg`, `x_thread`, `bluesky`, `mastodon`, `linkedin`, `instant` (Telegram/WhatsApp),
  `newsletter` (Substack), `podcast`. Her biçim yalnızca **metin üretir**; gönderme eylemi
  kullanıcıdadır (Spec §15/6).
* `GET /api/memory/actors?q=...` — Siyasi aktör arama ve sicil dökümü.
* `GET /api/accountability/search?q=...` — Vaat, icraat ve Sayıştay kayıtlarında parametrik arama.
* `GET /api/events/live` — Server-Sent Events (SSE) ile anlık olay bildirimleri akışı.

---

## 🧪 Kalite Kapıları & Güvenlik

PolitikDesk, sıfır hata toleranslı CI/CD kalite kapılarına sahiptir:

```bat
pd ci                         :: Tüm denetimleri tek seferde koşturur
```

`pd ci` şu adımları eksiksiz doğrular:
1. **Linter & Formatter:** `ruff check .` (0 hata)
2. **Statik Tip Güvenliği:** `mypy politikdesk scripts config` (156 dosya, 0 hata, strict mode)
3. **Bağımsızlık Güvenlik Taraması:** `pip-audit` (0 bilinen zafiyet)
4. **Mimari İzolasyon:** `check_architecture.py` (`evidence/` ➔ `llm/` ihlal denetimi)
5. **Veritabanı Dayanıklılığı:** Çift yönlü migration & idempotency testi
6. **Otomasyon Testleri:** **1087 Pytest** testi (Canlı DB, NLP, kural motoru, güvenlik kapıları)

---

## 🛠️ Teknoloji Yığını

* **Çekirdek:** Python 3.12, FastAPI, Uvicorn, Pydantic v2
* **Veritabanı & Vektör:** PostgreSQL 16, pgvector, Psycopg 3 Pool
* **Kuyruk & Dağıtık Görevler:** Celery 5.4, Redis 5.2
* **Vektör Temsili (Embedding):** `multilingual-e5-large` (Self-hosted)
* **Arayüz:** Server-side Vanilla HTML5, Özel CSS Tasarım Sistemi (Tokens & Shell), Lucide Inline SVG
* **Telemetri & Güvenlik:** Structlog, Sentry SDK, Tenacity, Pip-audit, Playwright UI Checker

---

## 📄 Lisans

Bu proje **Proprietary (Özel Lisanslı)** kişisel bir istihbarat ve editoryal çalışma masası aracıdır. Tüm hakları saklıdır.
