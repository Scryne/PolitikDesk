-- =============================================================================
-- PolitikDesk — 0018_stance_shifts
-- Görev:  Söylem değişikliklerinin kalıcılaştırılması (Roadmap Faz 4.1)
--
-- ÖNCE İNCELENDİ. Roadmap 4.1 "event_relations tablosu oluştur" diyor —
-- ama o tablo ZATEN VAR (606 kayıt, sürüm takibi, güven skoru, kanıt
-- yükü). Faz 2.2'deki durumun aynısı: madde, var olan bir şeyi istiyor.
--
-- ASIL ÖLÇÜLMÜŞ BOŞLUK BAŞKA: söylem değişiklikleri hiçbir yere
-- YAZILMIYOR. `service.list_all_stance_shifts()` her istekte 20 aktörün
-- hafızasını yeniden okuyup O(n²) tarama yapıyor. 18 Ağustos denetiminde
-- ölçülen süre 5,2 saniyeydi; ön hesapla 0,66'ya indi ama hâlâ HER
-- İSTEKTE yeniden hesaplanıyor. Sonuç: tarihsel analiz yok, denetim izi
-- yok, graf sorgusu yok — roadmap 4.1'in saydığı üç kazanımın üçü de yok.
--
-- -----------------------------------------------------------------------------
-- NEDEN `event_relations` KULLANILMIYOR — ÖLÇÜLDÜ, VARSAYILMADI
-- -----------------------------------------------------------------------------
-- `event_relations` birincil anahtarı: (from_event_id, to_event_id, relation)
--
-- Söylem değişikliği ise AKTÖR ve KONU boyutu taşır. Aynı olay çiftinde
-- iki farklı aktör kayması olabilir ve o anahtar altında ikisi tek satıra
-- iner. Ölçüm (19 Ağu 2026, canlı veri):
--
--     toplam söylem değişikliği : 37
--     event_relations anahtarıyla: 2 KAYIT KAYBOLURDU
--     tam kimlikle tekil        : 37 / 37
--
--     örnek çakışma (olay 7700 -> 8041):
--         Devlet Bahçeli · reversal · Politika / Tutum Beyanı
--         Resmî Gazete   · reversal · Politika / Tutum Beyanı
--
-- Bu, Faz 1.2'de 150 TÜİK kaydını sessizce tek satıra indiren hatanın
-- birebir aynısıdır — orada bedeli ödenmişti, burada önceden görüldü.
-- =============================================================================

CREATE TABLE IF NOT EXISTS stance_shifts (
  id                  BIGSERIAL PRIMARY KEY,

  -- Kimlik boyutları. Beşi birden bir kaymayı tekilleştirir.
  actor_name          TEXT   NOT NULL,
  shift_type          TEXT   NOT NULL
                        CHECK (shift_type IN ('reversal', 'broken_promise',
                                              'numeric_divergence')),
  topic_or_metric     TEXT   NOT NULL,
  earlier_event_id    BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  later_event_id      BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,

  -- Kanıt: kaymanın DAYANDIĞI iki beyan. Metinler saklanır çünkü olay
  -- başlığı sonradan değişebilir ve o zaman "bu kayma neden üretildi?"
  -- sorusu yanıtsız kalır (Spec §9.3 alıntı sınırlarına tabidir).
  earlier_event_title TEXT   NOT NULL DEFAULT '',
  earlier_claim_text  TEXT   NOT NULL DEFAULT '',
  earlier_date        TEXT   NOT NULL DEFAULT '',
  later_event_title   TEXT   NOT NULL DEFAULT '',
  later_claim_text    TEXT   NOT NULL DEFAULT '',
  later_date          TEXT   NOT NULL DEFAULT '',

  time_span_days      INTEGER NOT NULL DEFAULT 0,
  confidence          REAL    NOT NULL DEFAULT 0,
  evidence_summary    TEXT    NOT NULL DEFAULT '',
  metadata            JSONB   NOT NULL DEFAULT '{}'::jsonb,

  -- Deterministik kimlik. Aynı kayma her turda yeniden yazılmaz.
  signature           TEXT    NOT NULL,
  -- Tespit mantığı değişirse eski kayıtlar geçersizleşir; hangi sürümün
  -- ürettiği bilinmeden yeniden hesaplama güvenli yapılamaz.
  engine_version      TEXT    NOT NULL DEFAULT 'stance.v1',

  -- `superseded`: kayma artık üretilmiyor (veri değişti ya da motor
  -- güncellendi). SİLİNMEZ — denetim izi korunur.
  status              TEXT    NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'superseded')),

  detected_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

  CHECK (earlier_event_id <> later_event_id)
);

COMMENT ON TABLE stance_shifts IS
  'Söylem değişiklikleri. `event_relations` KULLANILMADI: onun anahtarı '
  '(from,to,relation) aktör ve konu boyutunu taşımıyor ve canlı veride '
  '37 kaydın 2''sini kaybediyordu (19 Ağu 2026 ölçümü).';

COMMENT ON COLUMN stance_shifts.signature IS
  'Deterministik kimlik: aktör|önceki|sonraki|tür|konu. Değişmeyen bir '
  'kaymanın tekrar tespiti yeni kayıt ÜRETMEZ.';

-- Yalnızca AÇIK kayıtlar tekilleştirilir; kapatılmış eski sürümler kalır.
CREATE UNIQUE INDEX IF NOT EXISTS uq_stance_shifts_signature
  ON stance_shifts (signature)
  WHERE status = 'open';

-- "Bu aktörün kaymaları" — hafıza sayfasının ana sorgusu.
CREATE INDEX IF NOT EXISTS idx_stance_shifts_actor
  ON stance_shifts (actor_name, detected_at DESC)
  WHERE status = 'open';

-- Graf yönü: bir olaydan çıkan / bir olaya giren kaymalar.
CREATE INDEX IF NOT EXISTS idx_stance_shifts_earlier
  ON stance_shifts (earlier_event_id) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS idx_stance_shifts_later
  ON stance_shifts (later_event_id) WHERE status = 'open';

-- Tür bazlı filtre (kırılan vaatler ayrı okunur).
CREATE INDEX IF NOT EXISTS idx_stance_shifts_type
  ON stance_shifts (shift_type, detected_at DESC) WHERE status = 'open';
