-- =============================================================================
-- PolitikDesk — 0023_data_lifecycle_and_gundem_v2
-- Faz 21: Fresh Production Cycle & Gündem V2 Live Intelligence Feed
--
-- Amaç:
--   1. Üretim veri yaşam döngüsü (publication_cycles) ve döngüsel izolasyon.
--   2. Mevcut geçmiş veriyi arşiv döngüsüne (legacy_cycle_0) bağlayarak koruma (0 destructive delete).
--   3. Yeni temiz üretim döngüsünü (prod_cycle_20260824) aktif başlangıç noktası yapma.
--   4. Gündem V2 için kategori, bölge ve yüksek performanslı bileşik indeksler.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Üretim / Yayın Döngüleri Tablosu
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS publication_cycles (
  id          BIGSERIAL PRIMARY KEY,
  cycle_key   TEXT UNIQUE NOT NULL,
  name        TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('active', 'archived', 'draft')),
  started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at    TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  meta        JSONB NOT NULL DEFAULT '{}'
);

-- Veritabanı seviyesinde en fazla 1 adet 'active' döngü bulunabilir kısıtı
CREATE UNIQUE INDEX IF NOT EXISTS idx_publication_cycles_active
  ON publication_cycles (status) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_publication_cycles_status_started
  ON publication_cycles (status, started_at DESC);

-- -----------------------------------------------------------------------------
-- 2. Makaleler ve Olaylar için Döngü, Kategori ve Bölge Alanları
-- -----------------------------------------------------------------------------
ALTER TABLE events ADD COLUMN IF NOT EXISTS cycle_id BIGINT REFERENCES publication_cycles(id);
ALTER TABLE events ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'ekonomi';
ALTER TABLE events ADD COLUMN IF NOT EXISTS region TEXT NOT NULL DEFAULT 'turkiye';

ALTER TABLE articles ADD COLUMN IF NOT EXISTS cycle_id BIGINT REFERENCES publication_cycles(id);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'ekonomi';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS region TEXT DEFAULT 'turkiye';

-- -----------------------------------------------------------------------------
-- 3. Geçmiş Veriyi Arşivleme & Yeni Temiz Üretim Döngüsünü Başlatma
-- -----------------------------------------------------------------------------
-- A) Arşiv Döngüsü: Faz 1 - Faz 20 arasındaki tüm mevcut veriyi kapsar
INSERT INTO publication_cycles (cycle_key, name, status, started_at, ended_at, meta)
VALUES (
  'legacy_cycle_0',
  'Faz 1-20 Tarihsel Arşiv Döngüsü',
  'archived',
  '2026-08-01 00:00:00+03',
  now(),
  '{"description": "Faz 21 öncesi tüm certified geçmiş üretim verisi", "archived_at": "2026-08-24"}'::jsonb
)
ON CONFLICT (cycle_key) DO NOTHING;

-- Mevcut tüm olay ve makaleleri arşiv döngüsüne bağla
DO $$
DECLARE
  v_legacy_id BIGINT;
BEGIN
  SELECT id INTO v_legacy_id FROM publication_cycles WHERE cycle_key = 'legacy_cycle_0';
  IF v_legacy_id IS NOT NULL THEN
    UPDATE events SET cycle_id = v_legacy_id WHERE cycle_id IS NULL;
    UPDATE articles SET cycle_id = v_legacy_id WHERE cycle_id IS NULL;
  END IF;
END $$;

-- B) Yeni Aktif Üretim Döngüsü: Bugünden itibaren gelen canlı verileri karşılar
INSERT INTO publication_cycles (cycle_key, name, status, started_at, meta)
VALUES (
  'prod_cycle_20260824',
  'Faz 21 Canlı İstihbarat Döngüsü',
  'active',
  now(),
  '{"description": "Faz 21 Gündem V2 Canlı Üretim Başlangıcı", "created_at": "2026-08-24"}'::jsonb
)
ON CONFLICT (cycle_key) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 4. Gündem V2 Performans ve Sıralama İndeksleri
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_events_cycle ON events(cycle_id);
CREATE INDEX IF NOT EXISTS idx_articles_cycle ON articles(cycle_id);

CREATE INDEX IF NOT EXISTS idx_events_active_salience
  ON events (cycle_id, salience_score DESC, last_update_at DESC)
  WHERE merged_into_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_events_active_newest
  ON events (cycle_id, first_reported_at DESC)
  WHERE merged_into_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_events_active_updated
  ON events (cycle_id, last_update_at DESC)
  WHERE merged_into_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_events_active_cat_salience
  ON events (cycle_id, category, salience_score DESC)
  WHERE merged_into_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_events_active_reg_salience
  ON events (cycle_id, region, salience_score DESC)
  WHERE merged_into_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_articles_cycle_first_seen
  ON articles (cycle_id, first_seen_at DESC);

COMMENT ON TABLE publication_cycles IS
  'Üretim veri yaşam döngüleri (Faz 21). Aktif ve arşiv verisini birbirinden izole eder.';
