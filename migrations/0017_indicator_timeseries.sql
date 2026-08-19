-- =============================================================================
-- PolitikDesk — 0017_indicator_timeseries
-- Görev:  Gösterge zaman serisi ve anomali kaydı (Roadmap Faz 3.1)
--
-- ÖNCE İNCELENDİ, SONRA YAZILDI. Faz 3 yetkisi "yeterli bir soyutlama
-- zaten varsa yenisini yapma" diyor. Var olanlar tek tek bakıldı:
--
--   articles.official_value  Bir YAYIN kaydıdır, zaman serisi değil.
--                            Ölçüldü: her serinin TAM 1 satırı var.
--                            Adaptör 120 günlük pencere çekiyor ama
--                            yalnızca SON gözlemi yayımlıyor; tarih
--                            kaynakta duruyor, bizde durmuyor.
--                            Bir makale haber birimidir, bir gözlem veri
--                            noktası; ikisini aynı tabloda tutmak
--                            "TÜİK bugün ne açıkladı" ile "işsizlik
--                            2021'den beri nasıl seyretti" sorularını
--                            birbirine karıştırırdı.
--
--   metrics                  Ürün metriği tablosu (metric_name/value/
--                            dimensions). Seri kimliği, dönem ve revizyon
--                            kavramı YOK.
--
--   scheduled_events         Beklenti kaydı; sayısal gözlem taşımıyor.
--
-- Yani bu tablolar bir tekrar değil, eksik olanı ekliyor.
--
-- KAYNAKTA NE KADAR TARİH VAR (19 Ağu 2026 ölçümü, 2021-2026 penceresi):
--     TP.DK.USD.A.YTL          683 gözlem  (günlük, seri 2023-11'de başlıyor)
--     TP.DK.EUR.A.YTL          683 gözlem  (günlük)
--     TP.KAVRAMSAL.HAMM2.INDX  293 gözlem  (haftalık)
--     TP.ENFBEK.PKA12ENF        67 gözlem  (aylık)
--     TP.AB.B6                  65 gözlem  (aylık)
-- Yani gerçek bir temel çizgi hesaplanabilir; uydurmaya gerek yok.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. GÖSTERGE KİMLİĞİ
-- -----------------------------------------------------------------------------
-- ⛔ KİMLİK YALNIZCA `metric` OLAMAZ.
--
-- Faz 1'in dersi: USD/TRY ile EUR/TRY'nin İKİSİ DE `exchange_rate`
-- metriğini taşıyor. Metriğe göre gruplanan bir seri, iki farklı
-- büyüklüğü tek eğri gibi çizer — `web/repository.py` içinde bu kusur
-- bir kez önlendi, burada tekrar edemez.
--
-- Kimlik = (kaynak, seri kodu). `metric` bir ETİKETTİR, kimlik değil.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS indicator_series (
  id            BIGSERIAL PRIMARY KEY,
  source_id     BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  series_code   TEXT   NOT NULL,
  metric        TEXT   NOT NULL,
  label         TEXT   NOT NULL,
  unit          TEXT   NOT NULL DEFAULT '',
  -- Frekans tespit yönteminin girdisidir: günlük finansal seriye
  -- uygulanan yöntem aylık ankete uygulanamaz.
  frequency     TEXT   NOT NULL DEFAULT 'unknown'
                  CHECK (frequency IN ('daily','weekly','monthly','quarterly',
                                       'yearly','irregular','unknown')),
  -- Hangi temel çizgi yöntemi kullanılacak (analysis/anomaly.py).
  method        TEXT   NOT NULL DEFAULT 'auto',
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_id, series_code)
);

COMMENT ON TABLE indicator_series IS
  'Gösterge kimliği. `metric` tek başına kimlik DEĞİLDİR: USD/TRY ve '
  'EUR/TRY ikisi de exchange_rate taşır ve ayrı seri olmak zorundadır.';

CREATE INDEX IF NOT EXISTS idx_indicator_series_metric
  ON indicator_series (metric);


-- -----------------------------------------------------------------------------
-- 2. GÖZLEMLER
-- -----------------------------------------------------------------------------
-- Revizyon güvenliği: resmî kurumlar yayımlanmış bir değeri düzeltebilir.
-- Eski değer SİLİNMEZ — `superseded_at` ile işaretlenir. Denetlenebilirlik
-- bunu gerektirir: "bu anomali neden üretildi?" sorusu, o an geçerli olan
-- değere bakılarak yanıtlanabilmelidir.
--
-- Kısmi tekil indeks yalnızca YÜRÜRLÜKTEKİ gözlemi tekilleştirir; aynı
-- dönemin revize edilmiş eski sürümleri tabloda kalır.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS indicator_observations (
  id            BIGSERIAL PRIMARY KEY,
  series_id     BIGINT NOT NULL REFERENCES indicator_series(id) ON DELETE CASCADE,
  -- Kurumun dönem etiketi: '2026-08-19', '2026-08', '2026-Q3', '2026'.
  -- Serbest metin çünkü frekans serilere göre değişir; sıralama
  -- ISO-benzeri biçim sayesinde sözlüksel olarak doğrudur.
  period        TEXT   NOT NULL,
  value         DOUBLE PRECISION NOT NULL,
  -- Kurumun yayımladığı an DEĞİL, bizim gördüğümüz an.
  observed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  -- Revize edildiyse dolar. NULL = yürürlükteki değer.
  superseded_at TIMESTAMPTZ,
  source_url    TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN indicator_observations.superseded_at IS
  'Revizyon işareti. Eski değer SİLİNMEZ: bir anomalinin neden '
  'üretildiği, o an yürürlükte olan değere bakılarak açıklanabilmelidir.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_indicator_obs_current
  ON indicator_observations (series_id, period)
  WHERE superseded_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_indicator_obs_series_period
  ON indicator_observations (series_id, period DESC)
  WHERE superseded_at IS NULL;


-- -----------------------------------------------------------------------------
-- 3. ANOMALİLER
-- -----------------------------------------------------------------------------
-- ⛔ AÇIKLANMAYAN BİR `is_anomaly = true` SAKLANMAZ.
--
-- Kayıt, üretildiği girdilerden YENİDEN HESAPLANABİLİR olmalıdır:
-- gözlenen değer, beklenen değer, sapma, yöntem, eşik, pencere. Aksi
-- hâlde "bu sinyal neden var?" sorusu yanıtsız kalır ve açıklanamayan
-- bir uyarı, uyarı olmaktan çıkar.
--
-- ⛔ NEDENSELLİK YOK. Bu tabloda "sebebi X" diye bir alan bilerek
-- yoktur. Anomali bir GÖZLEMDİR; yorum insanın işidir ve kanıt ister.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS indicator_anomalies (
  id              BIGSERIAL PRIMARY KEY,
  series_id       BIGINT NOT NULL REFERENCES indicator_series(id) ON DELETE CASCADE,
  observation_id  BIGINT NOT NULL REFERENCES indicator_observations(id) ON DELETE CASCADE,
  period          TEXT   NOT NULL,

  observed_value  DOUBLE PRECISION NOT NULL,
  expected_value  DOUBLE PRECISION,
  deviation       DOUBLE PRECISION NOT NULL,
  deviation_ratio DOUBLE PRECISION,

  detection_method TEXT  NOT NULL,
  threshold        DOUBLE PRECISION NOT NULL,
  baseline_window  INTEGER NOT NULL,
  baseline_size    INTEGER NOT NULL,

  severity  TEXT NOT NULL
              CHECK (severity IN ('low','medium','high','critical')),
  status    TEXT NOT NULL DEFAULT 'open'
              CHECK (status IN ('open','superseded','resolved')),

  -- Idempotency çıpası: aynı (seri, dönem, yöntem, değer) her turda
  -- yeniden anomali üretmez. Değer revize edilirse imza değişir ve
  -- yeni kayıt doğar; eskisi `superseded` olur.
  signature  TEXT NOT NULL,

  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE indicator_anomalies IS
  'İstatistiksel sapma kaydı. Bir YORUM değildir: nedensellik alanı '
  'bilerek yoktur. Kayıt, saklanan girdilerden yeniden hesaplanabilir.';

COMMENT ON COLUMN indicator_anomalies.signature IS
  'Deterministik kimlik (seri|dönem|yöntem|değer). Değişmeyen gözlemin '
  'tekrar işlenmesi yeni kayıt ÜRETMEZ.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_indicator_anomaly_signature
  ON indicator_anomalies (signature);

CREATE INDEX IF NOT EXISTS idx_indicator_anomaly_open
  ON indicator_anomalies (series_id, detected_at DESC)
  WHERE status = 'open';


-- -----------------------------------------------------------------------------
-- 4. TAKVİM: GECİKME DURUMU
-- -----------------------------------------------------------------------------
-- Faz 1.2'nin `published != cancelled` değişmezi korunuyor; üzerine
-- `delayed` ekleniyor.
--
-- ÜÇ FARKLI ANLAM, ÜÇ FARKLI DURUM (Faz 3 yetkisi §DELAY DETECTION):
--   pending    kurum henüz yayımlamadı
--   delayed    beklenen zaman geçti, kurum hâlâ yayımlamadı
--   published  kurum yayımladı ama BİZ görmedik
--   occurred   yayımlandı VE bizim olayımızla eşleşti
--   cancelled  beklenen zaman çoktan geçti, hiç gelmedi
-- -----------------------------------------------------------------------------
ALTER TABLE scheduled_events DROP CONSTRAINT IF EXISTS scheduled_events_status_check;
ALTER TABLE scheduled_events
  ADD CONSTRAINT scheduled_events_status_check
  CHECK (status IN ('pending', 'delayed', 'published', 'occurred', 'cancelled'));

-- "Bugün ne gecikti?" sorgusu istek yolunda tam tarama yapmasın.
CREATE INDEX IF NOT EXISTS idx_scheduled_events_status_expected
  ON scheduled_events (status, expected_at DESC);
