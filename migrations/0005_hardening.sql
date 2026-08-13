-- =============================================================================
-- 0005 — Faz 4 sertleştirme
-- =============================================================================

-- -----------------------------------------------------------------------------
-- İddia çıkarımı: deneme izi (F4-05)
--
-- `pending_events` "iddiası olmayan olayları" seçiyordu. Çıkarımın meşru
-- şekilde SIFIR iddia döndürmesi mümkündür (başlıktan ibaret bir duyuru,
-- özeti olmayan bir bülten) — ve bu durumda olay listeden hiç düşmüyordu.
--
-- 13 Ağustos 2026'da ölçülen sonuç: 3 olay 28 saat boyunca her 10 dakikada
-- bir yeniden LLM'e gönderildi. Her tur ~4 dakika sürüyor ve her seferinde
-- aynı boş yanıt dönüyordu. Arıza değildi; **sonsuz bir yeniden deneme
-- döngüsüydü** ve kapasiteyi kalıcı olarak yakıyordu.
--
-- Çözüm iki sütun: son deneme zamanı ve deneme sayısı. Yeniden deneme
-- ölçütü "iddia yok" değil, **"olaya yeni malzeme geldi"** olur:
-- `last_update_at > claims_attempted_at`. Yeni makale katılmadıkça aynı
-- metinden farklı bir sonuç beklemek için sebep yoktur.
-- -----------------------------------------------------------------------------
ALTER TABLE events ADD COLUMN IF NOT EXISTS claims_attempted_at TIMESTAMPTZ;
ALTER TABLE events ADD COLUMN IF NOT EXISTS claims_attempt_count INT NOT NULL DEFAULT 0;

COMMENT ON COLUMN events.claims_attempted_at IS
  'İddia çıkarımının bu olay için en son denendiği an. Sıfır iddia dönmesi '
  'bir hata değildir; bu damga olmadan olay sonsuza dek yeniden denenir (F4-05).';
COMMENT ON COLUMN events.claims_attempt_count IS
  'Kaç kez denendi. Üst sınır kod tarafında (claims_pipeline.MAX_CLAIM_ATTEMPTS); '
  'olaya yeni makale katıldığında sayaç sıfırlanır.';

-- Bekleyen olay sorgusu bu iki sütunu okuyor; kısmi indeks sorguyu
-- iddiası olmayan küçük alt kümeye daraltır.
CREATE INDEX IF NOT EXISTS idx_events_claims_attempt
  ON events (claims_attempted_at NULLS FIRST, last_update_at DESC)
  WHERE merged_into_id IS NULL;

-- -----------------------------------------------------------------------------
-- Denetim izi: eylem başına sorgu (F4-16)
--
-- `audit.exists_since()` alarm tekrarını bastırmak için (action, target)
-- çiftini zaman penceresiyle sorguluyor. Mevcut indeksler yalnızca
-- `created_at` ve `target` üzerinde; eylem adı indekssizdi.
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_audit_log_action_time
  ON audit_log (action, created_at DESC);
