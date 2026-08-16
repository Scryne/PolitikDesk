-- =============================================================================
-- PolitikDesk — 0015_composite_indexes
-- Görev:  S3/S4 Performans ve Bileşik İndeks Optimizasyonu
--
-- Gerekçe:
--   * claims(event_id, evidence_status) bileşik indeksi:
--     Hesap verebilirlik ve olay detayında kanıt durumuna göre filtrelemeleri hızlandırır.
--   * event_relations(from_event_id, relation) bileşik indeksi:
--     Vaat takibi ve icraat eşleştirmelerinde (fulfils, fails, contradicts)
--     alt sorguların index-only scan yapmasını sağlar.
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_claims_event_status
  ON claims (event_id, evidence_status);

CREATE INDEX IF NOT EXISTS idx_event_relations_from_relation
  ON event_relations (from_event_id, relation);

CREATE INDEX IF NOT EXISTS idx_event_relations_to_relation
  ON event_relations (to_event_id, relation);
