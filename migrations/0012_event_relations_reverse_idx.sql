-- -----------------------------------------------------------------------------
-- PolitikDesk Spec v3.4 S3: Event Relations Ters İndeks ve Sürümleme Güçlendirmesi
-- (S3 · Spec v3.4 §7.3, §8.3, §14.1)
--
-- ⛔ MİMARİ KISITLAR (Spec §15):
-- Bu migration geriye dönük tam uyumludur. Hiçbir tablo silinmez veya değiştirilmez.
-- Yalnızca sorgu optimizasyonu (ters indeks), motor sürümleme (engine_version)
-- ve güncellenme zaman damgası (updated_at) ekler.
-- -----------------------------------------------------------------------------

-- 1. Ters yönlü arama indeksi (to_event_id üzerinden olay geçmişi sorguları)
CREATE INDEX IF NOT EXISTS idx_event_relations_to_event
  ON event_relations(to_event_id);

-- 2. Motor sürümleme ve zaman damgası alanları
ALTER TABLE event_relations ADD COLUMN IF NOT EXISTS engine_version TEXT NOT NULL DEFAULT 's2.v1';
ALTER TABLE event_relations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

COMMENT ON INDEX idx_event_relations_to_event IS
  'Olay geçmişi ve hesap verebilirlik zinciri ters sorgu indeksi (Spec §14.1)';

COMMENT ON COLUMN event_relations.engine_version IS
  'İlişkiyi üreten deterministik motor sürümü (örn. s2.v1, s3.v1)';

COMMENT ON COLUMN event_relations.updated_at IS
  'İlişki kaydının son güncelleme zaman damgası (idempotent upsert takibi)';
