-- =============================================================================
-- 0003 — Salience'ın global / kişisel ayrımı  (Spec v3.1 §8.4, B-34 / İtiraz-7)
-- =============================================================================
--
-- Spec v3.0'da salience tek bir 0-100 skoruydu ve altıncı bileşeni
-- "10 * kullanici_konu_ilgisi" idi. Bu bileşen kullanıcıya özeldir; olay
-- başına tek sütunda saklanamaz. Çok kullanıcıya geçildiğinde (F4-01) ya
-- ilk kullanıcının tercihi sessizce herkese uygulanır ya da şema değişir.
--
-- v3.1 skoru ikiye ayırdı:
--   A) global salience  0-90  -> events.salience_score (SAKLANIR)
--   B) kişisel ayarlama 0-10  -> feed sorgusunda hesaplanır (SAKLANMAZ)
--   gösterilen skor = A + B   (0-100, UI'da iki satır olarak kırılır)
--
-- Bu migration üst sınırı 100'den 90'a çeker. Böylece kişisel bileşeni
-- yanlışlıkla bu sütuna yazan bir kod yolu 90 üstü değer üretir üretmez
-- veritabanı seviyesinde reddedilir — sessiz yanlış sıralama yerine
-- gürültülü hata (P4).
-- -----------------------------------------------------------------------------

ALTER TABLE events DROP CONSTRAINT events_salience_score_check;

ALTER TABLE events ADD CONSTRAINT events_salience_global_range
  CHECK (salience_score BETWEEN 0 AND 90);

COMMENT ON COLUMN events.salience_score IS
  'GLOBAL salience (0-90, Spec §8.4/A). Deterministik ve kullanıcıdan '
  'bağımsızdır; önbelleklenebilir. Kişisel ayarlama (0-10) BURAYA YAZILMAZ — '
  'feed sorgusunda editorial_profiles.topic_priorities ile hesaplanır.';

COMMENT ON COLUMN events.salience_breakdown IS
  'Global bileşenler + cezalar (Spec §8.4/A). Kişisel bileşen buraya '
  'yazılmaz: saklanan alan kullanıcıdan bağımsız kalmalıdır.';

-- -----------------------------------------------------------------------------
-- R8 -> R0 yeniden numaralandırması (Spec v3.1 §8.3, B-33 / İtiraz-4)
-- -----------------------------------------------------------------------------
--
-- Tahmin kısıtı artık sıralamanın SONUNDA "EK KURAL R8" değil, BAŞINDA
-- "R0 tip kısıtı"dır ve kısa devre yapar. Böylece bir tahmin hakkında hem
-- destekleyen hem çelişen kanıt bulunduğunda R1 (contradicted) tetiklenmez.
--
-- Aşağıdaki CHECK 0001'de eklendi ve DEĞİŞMEDİ; yalnızca gerekçesi güncellendi:
-- artık "geçici önlem" değil, R0'ın ikinci savunma hattıdır.

COMMENT ON CONSTRAINT claims_prediction_always_unverified ON claims IS
  'Spec §8.3 R0 (tip kısıtı, kanıt kurallarından önce çalışır ve kısa devre '
  'yapar): tahmin tipi iddia HER ZAMAN unverified. Kural motorundaki bir hata '
  'sessiz yanlış etiket olarak değil, reddedilen INSERT olarak ortaya çıkar.';
