-- -----------------------------------------------------------------------------
-- PolitikDesk Spec v3.4 S2: Event Relations Genişlemesi ve Hesap Sor Kanıt Kütüğü
-- (S2 · Spec v3.4 §7.3, §8.3, §14.1)
--
-- ⛔ MİMARİ KISITLAR (Spec §15):
-- Bu migration ideolojik alan veya sübjektif suçlama etiketleri içermez.
-- Yalnızca kanıt gerekçelendirmesi (evidence_payload), güven skoru (confidence)
-- ve deterministik ilişki statüsünü (status) destekler.
-- -----------------------------------------------------------------------------

ALTER TABLE event_relations ADD COLUMN IF NOT EXISTS confidence REAL DEFAULT 1.0;
ALTER TABLE event_relations ADD COLUMN IF NOT EXISTS evidence_payload JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE event_relations ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'inferred'
  CHECK (status IN ('inferred', 'supported', 'verified', 'unresolved'));

COMMENT ON COLUMN event_relations.confidence IS
  'İlişki güven katsayısı (0.0 - 1.0 arası deterministik puan)';

COMMENT ON COLUMN event_relations.evidence_payload IS
  'İlişkiyi destekleyen kanıtlar, aktör/kurum eşleşmesi ve alıntı gerekçesi';

COMMENT ON COLUMN event_relations.status IS
  'İlişki statüsü: inferred (semantik), supported (varlık/tarih), verified (resmi atıf), unresolved (belirsiz)';
