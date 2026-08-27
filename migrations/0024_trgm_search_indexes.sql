-- =============================================================================
-- PolitikDesk — 0024_trgm_search_indexes
-- Faz 22: PostgreSQL Trigram GIN İndeksleme ve Yüksek Hızlı Arama
--
-- Amaç:
--   1. pg_trgm uzantısını aktifleştirme (CREATE EXTENSION IF NOT EXISTS).
--   2. events ve articles tablolarında fuzzy, substring ve ILIKE aramalarını
--      50k+ kayıt hacminde < 5ms'ye düşüren GIN trigram indeksleri ekleme.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_events_title_trgm
  ON events USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_events_summary_trgm
  ON events USING gin (summary gin_trgm_ops)
  WHERE summary IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_articles_title_trgm
  ON articles USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_articles_excerpt_trgm
  ON articles USING gin (excerpt gin_trgm_ops)
  WHERE excerpt IS NOT NULL;

COMMENT ON INDEX idx_events_title_trgm IS
  'Olay başlıklarında pg_trgm GIN hızlandırma indeksi (Faz 22).';
