-- =============================================================================
-- PolitikDesk — 0001_initial
-- Kaynak: PolitikDesk_Master_Spec_v3.md §7.3 (Şema taslağı)
-- Görev:  F0-15
--
-- Kritik kısıtlar (bunlar yorum değil, sözleşmedir):
--   * articles.excerpt <= 300 karakter          (Spec §9.3, D13)
--   * evidence.quote_span <= 200 karakter       (Spec §7.3)
--   * TAM METİN HİÇBİR ALANDA SAKLANMAZ         (Spec §9.3)
--   * editorial_profiles'ta ideolojik alan YOK  (Spec §10.1, P6, KVKK m.6)
--   * embedding boyutu 1024 sabit                (Spec §11.1, D16)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- -----------------------------------------------------------------------------
-- Kullanıcılar
-- Spec §7.3'te ayrı tablo olarak listelenmemiş; drafts.user_id ve
-- editorial_profiles.user_id referansları için altyapı gereği eklenmiştir.
-- Kimlik doğrulama: e-posta + magic link (Spec §11.1).
-- -----------------------------------------------------------------------------
CREATE TABLE users (
  id          BIGSERIAL PRIMARY KEY,
  email       TEXT UNIQUE NOT NULL,
  display_name TEXT,
  is_active   BOOLEAN NOT NULL DEFAULT TRUE,
  invited_at  TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- Kaynaklar (Spec §9.1 katmanlama, §9.2 sekiz kaynak sert sınırı)
-- -----------------------------------------------------------------------------
CREATE TABLE sources (
  id                  BIGSERIAL PRIMARY KEY,
  name                TEXT NOT NULL,
  slug                TEXT UNIQUE NOT NULL,
  tier                SMALLINT NOT NULL CHECK (tier BETWEEN 1 AND 4),
  kind                TEXT NOT NULL
                        CHECK (kind IN ('official', 'wire', 'media', 'social')),
  independence_group  TEXT,                   -- aynı yayın grubu/ajans zinciri aynı grup
  access_method       TEXT NOT NULL
                        CHECK (access_method IN ('rss', 'api', 'official_feed', 'manual')),
  tos_status          TEXT NOT NULL
                        CHECK (tos_status IN ('allowed', 'restricted', 'forbidden', 'pending_review')),
  tos_reviewed_at     DATE,
  base_url            TEXT,
  feed_url            TEXT,
  is_active           BOOLEAN NOT NULL DEFAULT TRUE,
  last_fetched_at     TIMESTAMPTZ,            -- F1-05 sağlık paneli girdisi
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sources_active ON sources (is_active) WHERE is_active;
CREATE INDEX idx_sources_independence_group ON sources (independence_group);

-- -----------------------------------------------------------------------------
-- Olaylar (Spec §7.2)
-- articles.event_id bu tabloya baktığı için events önce yaratılır.
-- -----------------------------------------------------------------------------
CREATE TABLE events (
  id                  BIGSERIAL PRIMARY KEY,
  title               TEXT NOT NULL,          -- LLM üretir, insan düzeltebilir
  summary             TEXT,
  vertical            TEXT NOT NULL DEFAULT 'macro_economy',
  topic_tags          TEXT[] NOT NULL DEFAULT '{}',
  status              TEXT NOT NULL DEFAULT 'developing'
                        CHECK (status IN ('developing', 'settled', 'contradicted')),
  salience_score      SMALLINT CHECK (salience_score BETWEEN 0 AND 100),
  salience_breakdown  JSONB,                  -- şeffaflık: skorun bileşenleri (P4)
  centroid_embedding  VECTOR(1024),
  first_reported_at   TIMESTAMPTZ NOT NULL,
  last_update_at      TIMESTAMPTZ NOT NULL,
  article_count       INT NOT NULL DEFAULT 0,
  independent_count   INT NOT NULL DEFAULT 0, -- Spec §8.2
  has_primary_source  BOOLEAN NOT NULL DEFAULT FALSE,
  merged_into_id      BIGINT REFERENCES events(id),  -- birleştirme geri alınabilir
  review_flag         TEXT
                        CHECK (review_flag IN ('needs_review', 'verified', 'rejected')),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT events_no_self_merge CHECK (merged_into_id IS DISTINCT FROM id)
);
CREATE INDEX idx_events_centroid_hnsw
  ON events USING hnsw (centroid_embedding vector_cosine_ops);
CREATE INDEX idx_events_last_update
  ON events (last_update_at DESC) WHERE merged_into_id IS NULL;
CREATE INDEX idx_events_salience
  ON events (salience_score DESC) WHERE merged_into_id IS NULL;
CREATE INDEX idx_events_review_flag
  ON events (review_flag) WHERE review_flag = 'needs_review';

-- -----------------------------------------------------------------------------
-- Makaleler
-- ⚠ TAM METİN SAKLANMAZ (Spec §9.3 / D13):
--     excerpt        — süresiz, azami 300 karakter
--     lead_paragraph — işleme amaçlı, raw_purge_at ile silinir (azami 30 gün)
-- -----------------------------------------------------------------------------
CREATE TABLE articles (
  id              BIGSERIAL PRIMARY KEY,
  source_id       BIGINT NOT NULL REFERENCES sources(id),
  canonical_url   TEXT UNIQUE NOT NULL,
  title           TEXT NOT NULL,
  excerpt         TEXT,
  lead_paragraph  TEXT,
  published_at    TIMESTAMPTZ,
  first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  content_hash    TEXT NOT NULL,              -- tam-tekrar tespiti (F1-10)
  simhash         BIGINT,                     -- yakın-tekrar / ajans kopyası (F1-11)
  embedding       VECTOR(1024),
  lang            TEXT NOT NULL DEFAULT 'tr',
  event_id        BIGINT REFERENCES events(id),
  cluster_score   REAL,
  raw_purge_at    TIMESTAMPTZ,                -- F1-12 purge işi bunu kullanır
  CONSTRAINT excerpt_len CHECK (char_length(excerpt) <= 300)
);
CREATE INDEX idx_articles_embedding_hnsw
  ON articles USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_articles_published ON articles (published_at DESC);
CREATE INDEX idx_articles_event ON articles (event_id);
CREATE INDEX idx_articles_content_hash ON articles (content_hash);
CREATE INDEX idx_articles_simhash ON articles (simhash);
CREATE INDEX idx_articles_purge_due
  ON articles (raw_purge_at) WHERE lead_paragraph IS NOT NULL;

-- -----------------------------------------------------------------------------
-- İddialar (Spec §8.1 — durum İDDİA seviyesinde hesaplanır, olay seviyesinde değil)
-- evidence_status asla bir LLM çıktısı olamaz (Spec §8.1 "Yasak").
-- -----------------------------------------------------------------------------
CREATE TABLE claims (
  id               BIGSERIAL PRIMARY KEY,
  event_id         BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  claim_text       TEXT NOT NULL,
  claim_type       TEXT NOT NULL
                     CHECK (claim_type IN ('fact', 'number', 'attribution', 'prediction')),
  normalized_value JSONB,                     -- {metric, value, unit, period}
  evidence_status  TEXT NOT NULL
                     CHECK (evidence_status IN (
                       'strongly_corroborated',   -- 🟢
                       'partially_corroborated',  -- 🟡
                       'single_source',           -- 🟠
                       'contradicted',            -- 🔴
                       'unverified'               -- ⚪
                     )),
  status_reason    JSONB NOT NULL,            -- {rule, independent_count, breakdown, ...}
  extracted_by     TEXT,                      -- prompt/model sürümü (denetlenebilirlik)
  computed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_claims_event ON claims (event_id);
CREATE INDEX idx_claims_status ON claims (evidence_status);

-- R8 zorlaması (Spec §8.3): tahmin tipi iddia HER ZAMAN unverified.
-- Kural motorunun yanında ikinci savunma hattı olarak DB seviyesinde de zorlanır.
ALTER TABLE claims ADD CONSTRAINT claims_prediction_always_unverified
  CHECK (claim_type <> 'prediction' OR evidence_status = 'unverified');

-- -----------------------------------------------------------------------------
-- Kanıtlar (Spec §7.3)
-- -----------------------------------------------------------------------------
CREATE TABLE evidence (
  id           BIGSERIAL PRIMARY KEY,
  claim_id     BIGINT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
  article_id   BIGINT NOT NULL REFERENCES articles(id),
  stance       TEXT NOT NULL
                 CHECK (stance IN ('supports', 'contradicts', 'partial')),
  quote_span   TEXT,
  extracted_by TEXT NOT NULL,                 -- model adı + sürüm
  confidence   REAL CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (claim_id, article_id),
  CONSTRAINT quote_span_len CHECK (char_length(quote_span) <= 200)
);
CREATE INDEX idx_evidence_claim ON evidence (claim_id);
CREATE INDEX idx_evidence_article ON evidence (article_id);

-- -----------------------------------------------------------------------------
-- Varlıklar ve bağlantıları
-- -----------------------------------------------------------------------------
CREATE TABLE entities (
  id             BIGSERIAL PRIMARY KEY,
  canonical_name TEXT NOT NULL,
  entity_type    TEXT NOT NULL
                   CHECK (entity_type IN ('person', 'institution', 'company', 'country')),
  aliases        TEXT[] NOT NULL DEFAULT '{}',
  is_key_entity  BOOLEAN NOT NULL DEFAULT FALSE,  -- salience "varlik_onemi" girdisi (§8.4)
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (canonical_name, entity_type)
);
CREATE INDEX idx_entities_aliases ON entities USING gin (aliases);

CREATE TABLE event_entities (
  event_id  BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  entity_id BIGINT NOT NULL REFERENCES entities(id),
  role      TEXT CHECK (role IN ('actor', 'subject', 'mentioned')),
  PRIMARY KEY (event_id, entity_id)
);
CREATE INDEX idx_event_entities_entity ON event_entities (entity_id);

CREATE TABLE article_entities (
  article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  entity_id  BIGINT NOT NULL REFERENCES entities(id),
  PRIMARY KEY (article_id, entity_id)
);

-- -----------------------------------------------------------------------------
-- Tarihsel bağlam (olay-olay ilişkisi)
-- -----------------------------------------------------------------------------
CREATE TABLE event_relations (
  from_event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  to_event_id   BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  relation      TEXT NOT NULL
                  CHECK (relation IN ('precedes', 'updates', 'contradicts', 'same_thread')),
  similarity    REAL,
  created_by    TEXT NOT NULL CHECK (created_by IN ('system', 'user')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (from_event_id, to_event_id, relation),
  CONSTRAINT event_relations_no_self CHECK (from_event_id <> to_event_id)
);

-- -----------------------------------------------------------------------------
-- Beklenen gelişmeler (Spec §9.5 — MVP'nin gizli kozu)
-- -----------------------------------------------------------------------------
CREATE TABLE scheduled_events (
  id              BIGSERIAL PRIMARY KEY,
  title           TEXT NOT NULL,
  expected_at     TIMESTAMPTZ NOT NULL,
  source_id       BIGINT REFERENCES sources(id),
  vertical        TEXT NOT NULL DEFAULT 'macro_economy',
  linked_event_id BIGINT REFERENCES events(id),
  status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'occurred', 'cancelled')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_scheduled_events_expected ON scheduled_events (expected_at);

-- -----------------------------------------------------------------------------
-- Taslaklar (Spec §7.3, §14.3)
-- -----------------------------------------------------------------------------
CREATE TABLE drafts (
  id              BIGSERIAL PRIMARY KEY,
  user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  event_id        BIGINT NOT NULL REFERENCES events(id),
  angle           TEXT NOT NULL
                    CHECK (angle IN ('inform', 'analyze', 'critique', 'contextualize', 'question')),
  body            TEXT NOT NULL,
  cited_claim_ids BIGINT[] NOT NULL DEFAULT '{}',
  check_result    JSONB,                      -- pre-publish check çıktısı (§14.4)
  user_action     TEXT
                    CHECK (user_action IN ('accepted', 'edited', 'regenerated', 'rejected')),
  final_body      TEXT,
  edit_distance   REAL,
  prompt_version  TEXT,                       -- Spec §11.5: her prompt sürümlenir
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_drafts_user ON drafts (user_id, created_at DESC);
CREATE INDEX idx_drafts_event ON drafts (event_id);

-- -----------------------------------------------------------------------------
-- Editoryal profil — YALNIZCA biçimsel alanlar
--
-- ⛔ BU TABLOYA İDEOLOJİK/SİYASİ SINIFLANDIRMA ALANI EKLENEMEZ.
--    Gerekçe: P6 (editorial preference, not political profiling) ve
--             KVKK m.6 (siyasi düşünce özel nitelikli kişisel veridir).
--    Bu kısıt tests/test_schema.py içinde otomatik denetlenir (F0-15 DoD).
-- -----------------------------------------------------------------------------
CREATE TABLE editorial_profiles (
  user_id            BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  tone               TEXT[] NOT NULL DEFAULT '{}',   -- direct | analytical | ironic | formal
  sentence_length    TEXT CHECK (sentence_length IN ('short', 'medium', 'long')),
  emoji_usage        TEXT CHECK (emoji_usage IN ('none', 'minimal', 'frequent')),
  hashtag_usage      TEXT CHECK (hashtag_usage IN ('none', 'minimal', 'frequent')),
  citation_habit     TEXT CHECK (citation_habit IN ('always_link', 'sometimes', 'never')),
  formality          SMALLINT CHECK (formality BETWEEN 1 AND 5),
  avoid_list         TEXT[] NOT NULL DEFAULT '{}',
  topic_priorities   TEXT[] NOT NULL DEFAULT '{}',
  compiled_prompt    TEXT,                    -- F3-09: form → statik prompt bloğu
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE editorial_profiles IS
  'Yalnızca biçimsel/stilistik alanlar. İdeolojik sınıflandırma alanı eklemek '
  'P6 ve KVKK m.6 ihlalidir; tests/test_schema.py bunu denetler.';

-- -----------------------------------------------------------------------------
-- Denetim izi (Spec §7.3, F4-16)
-- -----------------------------------------------------------------------------
CREATE TABLE audit_log (
  id         BIGSERIAL PRIMARY KEY,
  actor      TEXT NOT NULL,                   -- system:<job> | user:<id>
  action     TEXT NOT NULL,
  target     TEXT NOT NULL,
  payload    JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_log_created ON audit_log (created_at DESC);
CREATE INDEX idx_audit_log_target ON audit_log (target);

-- -----------------------------------------------------------------------------
-- Metrikler (Spec §13.3 — 8 ürün metriği; F0-18 / F3-19)
-- -----------------------------------------------------------------------------
CREATE TABLE metrics (
  id           BIGSERIAL PRIMARY KEY,
  metric_name  TEXT NOT NULL,
  metric_value DOUBLE PRECISION NOT NULL,
  user_id      BIGINT REFERENCES users(id) ON DELETE SET NULL,
  dimensions   JSONB NOT NULL DEFAULT '{}'::jsonb,
  recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_metrics_name_time ON metrics (metric_name, recorded_at DESC);
CREATE INDEX idx_metrics_user ON metrics (user_id, recorded_at DESC);

-- -----------------------------------------------------------------------------
-- LLM çağrı kayıtları (F0-17 — maliyet/bütçe sayacı)
-- Spec §11.5: her çağrı için token/maliyet loglanır, günlük tavan var.
-- -----------------------------------------------------------------------------
CREATE TABLE llm_calls (
  id             BIGSERIAL PRIMARY KEY,
  purpose        TEXT NOT NULL,               -- claims | summarize | draft | ...
  model          TEXT NOT NULL,
  prompt_version TEXT,
  input_tokens   INT NOT NULL DEFAULT 0,
  output_tokens  INT NOT NULL DEFAULT 0,
  cache_read_tokens     INT NOT NULL DEFAULT 0,
  cache_write_tokens    INT NOT NULL DEFAULT 0,
  cost_usd       NUMERIC(12, 6) NOT NULL DEFAULT 0,
  latency_ms     INT,
  user_id        BIGINT REFERENCES users(id) ON DELETE SET NULL,
  succeeded      BOOLEAN NOT NULL DEFAULT TRUE,
  error_type     TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_llm_calls_created ON llm_calls (created_at DESC);
CREATE INDEX idx_llm_calls_purpose ON llm_calls (purpose, created_at DESC);
