-- =============================================================================
-- 0008 — Metrik nabzını gerçek koşum zamanına bağlar (B-78 tamamlayıcısı)
-- =============================================================================
--
-- BULUNAN ARIZA: `pipeline_health` metrik aşamasının yaşını NEGATİF
-- gösteriyordu (ölçülen: `en_eski=-14.66`, yani "14 saat sonra"). Bir
-- nabız ölçümünün geleceği göstermesi, ölçümün yanlış sütunu okuduğunun
-- kanıtıdır.
--
-- KÖK NEDEN: `metrics.recorded_at` tek sütunda İKİ ANLAM taşıyordu.
--   * `daily_rollup` onu bir GÜN ETİKETİ olarak yazıyor:
--     `%s::date + interval '12 hours'` — yani "bu satır şu günü anlatıyor".
--     Öğle saati bilinçli bir seçimdir: `recorded_at::date` gün sınırında
--     kaymasın diye (silme/yeniden yazma ve gün bazlı gruplama buna dayanır).
--   * `pipeline_health` ise onu bir OLAY ZAMANI sanıyor: `now() - max(...)`.
--
-- Gün etiketi yerel gün (`date.today()`, TZ=Europe/Istanbul) üzerinden
-- kurulduğu için UTC'ye göre ileri düşebiliyor ve fark eksiye iniyordu.
--
-- ⚠️ Alarm tamamen körelmemişti — etiket sabit kaldığı için yaş gerçek
-- zamanda büyüyor ve eşiği yine aşıyordu; ama ~12 saat erken (48 sa eşiği
-- fiilen ~36 saat gibi davranıyordu) ve panoda anlamsız bir sayı
-- gösteriyordu. Yanlış okunan bir gösterge, okunmayan göstergeden daha
-- kötüdür: sayıya güvenilir sanılır.
--
-- ÇÖZÜM: iki anlam iki sütuna ayrılır.
--   * `recorded_at` — satırın ANLATTIĞI gün (etiket). Değişmedi;
--     gruplama ve idempotent yeniden koşum buna bağlı kalır.
--   * `computed_at` — satırın YAZILDIĞI an (olay). Nabız bunu okur.
-- -----------------------------------------------------------------------------

ALTER TABLE metrics
  ADD COLUMN IF NOT EXISTS computed_at TIMESTAMPTZ NOT NULL DEFAULT now();

COMMENT ON COLUMN metrics.computed_at IS
  'Satirin YAZILDIGI an (gercek duvar saati). pipeline_health nabzi bunu '
  'okur. recorded_at ile karistirilmamali: o, satirin ANLATTIGI gunun '
  'etiketidir ve gun sinirinda kaymasin diye ogleye sabitlenir (0008).';

COMMENT ON COLUMN metrics.recorded_at IS
  'Satirin ANLATTIGI gun (etiket, ogleye sabitlenmis). Gun bazli gruplama '
  've ayni gun icin idempotent yeniden yazma buna dayanir. Kosum zamani '
  'DEGILDIR — onun icin computed_at kullanilir (0008).';

-- Mevcut satırların gerçek koşum zamanı kayıtlı değil; en iyi yaklaşıklık
-- gün etiketinin kendisidir. `least(..., now())` geleceğe düşmüş etiketleri
-- şimdiye çeker — geçmişe dair uydurma bir kesinlik üretmeden nabzı
-- tutarlı kılar.
UPDATE metrics
   SET computed_at = least(recorded_at, now())
 WHERE computed_at > now();

CREATE INDEX IF NOT EXISTS idx_metrics_computed_at
  ON metrics (computed_at DESC);
