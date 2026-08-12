-- =============================================================================
-- PolitikDesk — 0002_ingestion
-- Faz 1 (Veri Omurgası) için gereken alanlar.
-- Görevler: F1-05 (zamanlayıcı), F1-11 (yakın tekrar), F1-19 (sağlık paneli)
-- =============================================================================

-- --- Kaynaklar: sağlık paneli ve çekim durumu (F1-19) ---------------------
ALTER TABLE sources ADD COLUMN IF NOT EXISTS adapter TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS extra_feeds TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE sources ADD COLUMN IF NOT EXISTS keyword_filter TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE sources ADD COLUMN IF NOT EXISTS topics TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE sources ADD COLUMN IF NOT EXISTS is_wire_reference BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_success_at TIMESTAMPTZ;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS last_error_at TIMESTAMPTZ;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS consecutive_errors INT NOT NULL DEFAULT 0;

-- --- Makaleler: tekrar zinciri ve konu etiketi ----------------------------
-- Yakın tekrar SAKLANIR (kaynak tablosunda görünmeli) ama işaretlenir:
-- bağımsız kanıt sayımında tek sayılacaktır (Spec §8.2).
ALTER TABLE articles ADD COLUMN IF NOT EXISTS near_duplicate_of_id BIGINT
  REFERENCES articles(id);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS simhash_distance SMALLINT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS independence_key TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS topics TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_manual_import BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMPTZ;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS entities_extracted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_articles_near_dup ON articles (near_duplicate_of_id)
  WHERE near_duplicate_of_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_articles_independence ON articles (independence_key);
CREATE INDEX IF NOT EXISTS idx_articles_pending_embedding ON articles (first_seen_at)
  WHERE embedded_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_articles_pending_entities ON articles (first_seen_at)
  WHERE entities_extracted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_articles_topics ON articles USING gin (topics);

-- Bir makale kendi yakın-tekrarı olamaz
ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_no_self_duplicate;
ALTER TABLE articles ADD CONSTRAINT articles_no_self_duplicate
  CHECK (near_duplicate_of_id IS DISTINCT FROM id);

-- --- Çekim günlüğü (F1-19 sağlık paneli) ----------------------------------
CREATE TABLE IF NOT EXISTS source_fetch_log (
  id            BIGSERIAL PRIMARY KEY,
  source_id     BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  duration_ms   INT NOT NULL DEFAULT 0,
  items_fetched INT NOT NULL DEFAULT 0,
  items_stored  INT NOT NULL DEFAULT 0,
  exact_dupes   INT NOT NULL DEFAULT 0,
  near_dupes    INT NOT NULL DEFAULT 0,
  filtered_out  INT NOT NULL DEFAULT 0,
  succeeded     BOOLEAN NOT NULL DEFAULT TRUE,
  error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_fetch_log_source_time
  ON source_fetch_log (source_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_fetch_log_time ON source_fetch_log (started_at DESC);

-- --- Varlık sözlüğü: alias çözümleme için (F1-16) -------------------------
CREATE INDEX IF NOT EXISTS idx_entities_canonical_lower
  ON entities (lower(canonical_name));
