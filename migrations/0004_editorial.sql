-- =============================================================================
-- PolitikDesk — 0004_editorial
-- Faz 3 (Editoryal Katman ve Arayüz) için gereken alanlar.
-- Görevler: F3-10, F3-12, F3-13, F3-14, F3-16, F3-17, F3-19, F3-21
--
-- Kritik kısıtlar (bunlar yorum değil, sözleşmedir):
--   * user_activity ETKİLEŞİM ÖLÇER, GÜNDEM SIRALAMAZ  (Spec §15 madde 14)
--   * drafts'ta otomatik yayın durumu YOK              (Spec §15 madde 6, P5)
--   * event_feedback bir DÜZELTME sinyalidir, skor değil (Spec §15 madde 13)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Taslaklar: grounding sonucu ve aksiyon zamanı (F3-12, F3-14)
--
-- `check_result` (0001) pre-publish check çıktısıdır (§14.4). Grounding
-- doğrulaması AYRI bir alandır çünkü ayrı bir kapıya bağlıdır: G3 koşul 2
-- ("taslakta kanıtta olmayan sayı/tarih = %0") yalnızca buraya bakar.
-- İkisini tek JSONB'de birleştirmek, sert kapının ölçümünü yumuşak
-- kontrollerin gürültüsüne karıştırırdı.
-- -----------------------------------------------------------------------------
ALTER TABLE drafts ADD COLUMN IF NOT EXISTS grounding_result JSONB;
ALTER TABLE drafts ADD COLUMN IF NOT EXISTS model TEXT;
ALTER TABLE drafts ADD COLUMN IF NOT EXISTS action_at TIMESTAMPTZ;

-- Grounding başarısız olan taslak KULLANILABİLİR DEĞİLDİR (Spec §15 madde 1).
-- Kayıt silinmez — denetim izi olarak kalır ve G3 #2 ölçümüne girer.
ALTER TABLE drafts ADD COLUMN IF NOT EXISTS is_grounded BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_drafts_ungrounded ON drafts (created_at DESC)
  WHERE NOT is_grounded;

COMMENT ON COLUMN drafts.grounding_result IS
  'F3-12 programatik grounding doğrulaması (Spec §11.5). Kapı G3 koşul 2 '
  'YALNIZCA bu alanı sayar: kanıt setinde bulunamayan sayı/tarih/alıntı.';

COMMENT ON COLUMN drafts.check_result IS
  'F3-13 pre-publish check çıktısı (Spec §14.4, 6 kontrol). Grounding''den '
  'ayrıdır: bu editoryal kalite, o halüsinasyon savunmasıdır.';

-- -----------------------------------------------------------------------------
-- Brifingler (F3-16, F3-17 · Spec §14.1 kalem 12)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS briefings (
  id             BIGSERIAL PRIMARY KEY,
  user_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  briefing_date  DATE NOT NULL,
  slot           TEXT NOT NULL CHECK (slot IN ('morning', 'evening')),
  event_ids      BIGINT[] NOT NULL DEFAULT '{}',
  -- Üretilmiş içerik (bizim metnimiz), kaynak makale metni DEĞİL.
  -- Spec §9.3'ün "tam metin saklanmaz" kuralı kaynak içeriği ilgilendirir.
  body_html      TEXT NOT NULL,
  body_text      TEXT NOT NULL,
  -- Açılma takibi: e-postadaki izleme ucu bu belirteci taşır.
  open_token     TEXT NOT NULL UNIQUE,
  generated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at        TIMESTAMPTZ,
  send_error     TEXT,
  opened_at      TIMESTAMPTZ,
  UNIQUE (user_id, briefing_date, slot)
);
CREATE INDEX IF NOT EXISTS idx_briefings_date ON briefings (briefing_date DESC, slot);

COMMENT ON TABLE briefings IS
  'Sabah/akşam brifingi (Spec §14.1 kalem 12). briefing_open_rate metriği '
  'sent_at / opened_at üzerinden hesaplanır (Spec §13.3).';

-- -----------------------------------------------------------------------------
-- "Bu yanlış" geri bildirimi (F3-21)
--
-- Bu tablo bir DOĞRULUK SKORU DEĞİLDİR (Spec §15 madde 13). Tek işlevi
-- olayı insan denetimi kuyruğuna düşürmek ve correction_rate metriğini
-- beslemektir. Sayısal bir "güvenilirlik" alanı buraya eklenemez.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_feedback (
  id          BIGSERIAL PRIMARY KEY,
  event_id    BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  user_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
  scope       TEXT NOT NULL DEFAULT 'event'
                CHECK (scope IN ('event', 'claim', 'source', 'summary')),
  claim_id    BIGINT REFERENCES claims(id) ON DELETE CASCADE,
  note        TEXT,
  resolved_at TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT event_feedback_note_len CHECK (char_length(note) <= 500)
);
CREATE INDEX IF NOT EXISTS idx_event_feedback_event ON event_feedback (event_id);
CREATE INDEX IF NOT EXISTS idx_event_feedback_open ON event_feedback (created_at DESC)
  WHERE resolved_at IS NULL;

-- -----------------------------------------------------------------------------
-- Kullanım izleri (F3-19 · Spec §13.3)
--
-- ⛔ BU TABLO GÜNDEM SIRALAMASINA GİRDİ OLAMAZ.
--    Gerekçe: Spec §15 madde 14 — "etkileşimi artırmak için gündemi
--    çarpıtmak" yasaktır ve salience formülü etkileşim girdisi içermez
--    (§8.4). evidence/ bu tabloyu okumaz; tests/test_evidence.py denetler.
--
--    Ölçülen metrikler bilinçli olarak ÜRÜNÜ FRENLEYEN yöndedir:
--    daily_active_minutes'ın DÜŞÜK olması hedeftir (Spec §13.3).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_activity (
  id          BIGSERIAL PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind        TEXT NOT NULL
                CHECK (kind IN ('page_view', 'heartbeat', 'event_open', 'understood')),
  event_id    BIGINT REFERENCES events(id) ON DELETE SET NULL,
  path        TEXT,
  duration_ms INT CHECK (duration_ms IS NULL OR duration_ms >= 0),
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_activity_time
  ON user_activity (user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_activity_event
  ON user_activity (event_id) WHERE event_id IS NOT NULL;

COMMENT ON TABLE user_activity IS
  'Ürün metriği ham verisi (Spec §13.3). Gündem sıralamasına GİRDİ DEĞİLDİR '
  '(Spec §15 madde 14); evidence/ bu tabloyu okuyamaz.';

-- -----------------------------------------------------------------------------
-- Kullanıcı: son görülme (F3-18 "sen yokken ne oldu")
-- -----------------------------------------------------------------------------
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;

-- -----------------------------------------------------------------------------
-- Editoryal profil: derleme denetlenebilirliği (F3-09)
--
-- `compiled_prompt` 0001'de var. Hangi form sürümünden derlendiği
-- kaydedilmezse, taslak kalitesindeki bir regresyonun profilden mi promptdan
-- mı geldiği ayırt edilemez (Spec §11.5 "her prompt sürümlenir").
-- -----------------------------------------------------------------------------
ALTER TABLE editorial_profiles ADD COLUMN IF NOT EXISTS compiler_version TEXT;
