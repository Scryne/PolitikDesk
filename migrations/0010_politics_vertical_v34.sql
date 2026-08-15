-- -----------------------------------------------------------------------------
-- PolitikDesk Spec v3.4: Siyaset Dikeyi, Promise İddia Tipi ve R8 Beyan Kaydı
-- (B-91, B-92, B-93, B-60 · Spec v3.4 §5, §7.3, §8.1, §8.3)
--
-- ⛔ MİMARİ KISITLAR (Spec §15):
-- Bu migration şemaya ideolojik alan veya siyasi etiket eklemez.
-- Yalnızca iddia tiplerini (promise), kanıt durumlarını (attribution_verified)
-- ve olay ilişkilerini (fulfils, fails) genişletir.
-- -----------------------------------------------------------------------------

-- 1. claims.claim_type kısıtını güncelle ('promise' ekle)
ALTER TABLE claims DROP CONSTRAINT IF EXISTS claims_claim_type_check;
ALTER TABLE claims ADD CONSTRAINT claims_claim_type_check
  CHECK (claim_type IN ('fact', 'number', 'attribution', 'prediction', 'promise'));

-- 2. claims.evidence_status kısıtını güncelle ('attribution_verified' ekle)
ALTER TABLE claims DROP CONSTRAINT IF EXISTS claims_evidence_status_check;
ALTER TABLE claims ADD CONSTRAINT claims_evidence_status_check
  CHECK (evidence_status IN (
    'strongly_corroborated',
    'partially_corroborated',
    'single_source',
    'contradicted',
    'unverified',
    'attribution_verified'
  ));

-- 3. event_relations.relation kısıtını güncelle ('fulfils', 'fails' ekle)
ALTER TABLE event_relations DROP CONSTRAINT IF EXISTS event_relations_relation_check;
ALTER TABLE event_relations ADD CONSTRAINT event_relations_relation_check
  CHECK (relation IN ('precedes', 'updates', 'contradicts', 'same_thread', 'fulfils', 'fails'));

-- 4. articles ve sources dikey desteği
ALTER TABLE sources ADD COLUMN IF NOT EXISTS vertical TEXT NOT NULL DEFAULT 'macro_economy';
ALTER TABLE articles ADD COLUMN IF NOT EXISTS vertical TEXT NOT NULL DEFAULT 'macro_economy';
ALTER TABLE events ADD COLUMN IF NOT EXISTS vertical TEXT NOT NULL DEFAULT 'macro_economy';

COMMENT ON COLUMN claims.claim_type IS
  'İddia tipi: fact, number, attribution, prediction, promise (Spec v3.4)';

COMMENT ON COLUMN event_relations.relation IS
  'Olay ilişkisi: precedes, updates, contradicts, same_thread, fulfils, fails (Spec v3.4)';
