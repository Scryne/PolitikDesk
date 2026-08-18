-- =============================================================================
-- PolitikDesk — 0016_official_calendar
-- Görev:  Ulusal Veri Yayımlama Takvimi (F2-18 · Roadmap Faz 1.2)
--
-- BULUNAN AÇIK: `scheduled_events` üç fazdır elle bakımlı bir YAML'den
-- besleniyordu (`config/calendar_2026.yml`, 17 kayıt). F2-18 "TÜİK Veri
-- Yayımlama Takvimi adaptörü" olarak Faz 2'den beri AÇIKTI ve gerekçesi
-- şuydu: TÜİK'in takvim sayfası bir React SPA, sunucudan okunamıyor
-- (B-42'nin aynısı).
--
-- Teşhis yanlıştı. 19 Ağustos 2026'da SPA'nın JS paketi
-- (takvim.tuik.gov.tr/ulusaltakvim/index.js) okundu ve içinden çağrı
-- çıkarıldı — `tuik_auth.py`'deki protokolün bulunma yönteminin aynısı:
--
--     GET https://takvim.tuik.gov.tr/Kurumsal/GetYillikHaberBulteniListesi?yil=YYYY
--     -> {"yayindaOlanlarList": [...], "yayindaOlmayanlarList": [...]}
--
-- Uç kimlik doğrulama İSTEMİYOR ve 2026 için 4.085 kayıt döndürüyor
-- (2.548 yayımlanmış + 1.537 bekleyen), 31 kurumdan: TCMB, BDDK, SPK,
-- TÜİK, HMB, EPDK, ETKB...  Yani bu yalnızca TÜİK takvimi değil,
-- ULUSAL veri yayımlama takvimi.
--
-- Kritik olan: uç, yayımlananları ve bekleyenleri AYRI LİSTELERDE
-- veriyor. Yani "beklenen" ile "gerçekleşen" ayrımını kurumun kendisi
-- yapıyor; bizim çıkarım yapmamız gerekmiyor.
--
-- BU MIGRATION NE EKLİYOR
--
--   external_id        Kurumun kendi kayıt kimliği -> idempotent upsert.
--                      Olmadan her tur aynı yayını yeniden eklerdi.
--   institution        31 kurumun çoğu `sources` tablosunda YOK ve
--                      olmamalı da (onlardan haber toplamıyoruz).
--                      `source_id` bu yüzden yetersiz kalıyor.
--   reference_period   Yayının ANLATTIĞI dönem ("17-08-2026"), yayım
--                      anı değil. İkisi karıştırılırsa "Haziran işsizlik
--                      verisi" Ağustos verisi sanılır.
--   url                Kurumun kendi yayın adresi — köken (provenance).
--   published_at       GERÇEKLEŞEN yayım anı. `expected_at` ile farkı
--                      gecikme metriğidir (Roadmap 1.2).
--   status 'published' Yeni durum: takvim yayımlandığını söylüyor ama
--                      bizim boru hattımız henüz olayı görmedi.
--
-- DURUM SÖZLÜĞÜ neden genişledi:
--   pending    beklenen, henüz yayımlanmadı
--   published  kurum yayımladı, bizim olayımızla HENÜZ eşleşmedi
--   occurred   yayımlandı VE bizim olayımızla eşleşti
--   cancelled  beklenen zaman geçti, hiçbir şey gelmedi
--
-- `published` ile `occurred` arasındaki fark ürünün asıl sorusudur:
-- "kurum açıkladı ama biz kaçırdık mı?" Tek bir durumla bu sorulamazdı.
-- =============================================================================

ALTER TABLE scheduled_events
  ADD COLUMN IF NOT EXISTS external_id      TEXT,
  ADD COLUMN IF NOT EXISTS institution      TEXT,
  ADD COLUMN IF NOT EXISTS reference_period TEXT,
  ADD COLUMN IF NOT EXISTS url              TEXT,
  ADD COLUMN IF NOT EXISTS published_at     TIMESTAMPTZ;

COMMENT ON COLUMN scheduled_events.external_id IS
  'Kaynağın kendi kayıt kimliği (TÜİK takviminde `id`). Idempotent '
  'upsert''in anahtarı: aynı yayım her turda yeniden eklenmez.';

COMMENT ON COLUMN scheduled_events.institution IS
  'Yayımdan sorumlu kurumun kısa adı (TCMB, BDDK, SPK, TÜİK, HMB...). '
  '`source_id` yetersizdir: takvimdeki 31 kurumun çoğundan haber '
  'toplamıyoruz ve `sources` tablosunda yokturlar.';

COMMENT ON COLUMN scheduled_events.reference_period IS
  'Yayının ANLATTIĞI dönem, yayım anı değil. "Haziran işsizlik verisi" '
  'Ağustos''ta yayımlanabilir; ikisi karıştırılırsa veri yanlış tarihlenir.';

COMMENT ON COLUMN scheduled_events.published_at IS
  'GERÇEKLEŞEN yayım anı. `expected_at` ile arasındaki fark gecikme '
  'metriğidir. Kurum takvimi yayımlananları ayrı listede verdiği için '
  'bu alan çıkarım değil, ölçümdür.';

-- Durum sözlüğü genişliyor: 'published' eklendi.
ALTER TABLE scheduled_events DROP CONSTRAINT IF EXISTS scheduled_events_status_check;
ALTER TABLE scheduled_events
  ADD CONSTRAINT scheduled_events_status_check
  CHECK (status IN ('pending', 'published', 'occurred', 'cancelled'));

-- Idempotent upsert'in dayanağı. Kısmi indeks: elle girilen kayıtlarda
-- `external_id` NULL'dır ve onlar bu kısıta tabi değildir.
CREATE UNIQUE INDEX IF NOT EXISTS uq_scheduled_events_external
  ON scheduled_events (external_id)
  WHERE external_id IS NOT NULL;

-- "Bugün hangi resmî veri bekleniyor?" sorgusunun indeksi (Roadmap 1.2
-- çıkış ölçütü). Kurum filtresi de aynı indeksten yararlanır.
CREATE INDEX IF NOT EXISTS idx_scheduled_events_institution_expected
  ON scheduled_events (institution, expected_at);

-- Gecikme raporu yalnızca yayımlanmış kayıtları tarar.
CREATE INDEX IF NOT EXISTS idx_scheduled_events_published
  ON scheduled_events (published_at)
  WHERE published_at IS NOT NULL;
