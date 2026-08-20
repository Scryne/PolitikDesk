-- 0021 — `events.claims_last_outcome`: denemenin NEDEN sonuçsuz kaldığı
--
-- ⛔ GEREKÇE: 20 Ağustos 2026 denetimi
--
-- `MAX_CLAIM_ATTEMPTS = 3` tavanına vurmuş ve HÂLÂ iddiasız **430 olay**
-- ölçüldü — toplam 2.044 olayın %21'i. Bunlar bir daha denenmez
-- (olaya yeni makale katılmadıkça), yani kalıcı olarak iddiasızdır.
--
-- Sorun bu davranış DEĞİL — F4-05'te bilinçle seçildi ve doğrudur:
-- "iddiası olmayan" ile "iddia çıkarılamayan" farklı şeylerdir ve
-- sıfır iddia dönen olayı sonsuza dek LLM'e göndermek 13 Ağustos'ta
-- üç olayı 28 saat boyunca döndürmüştü.
--
-- Sorun şu: **hangisi olduğu kayıtlı değil.** İki yol da aynı sayaca
-- yazıyordu:
--
--   * `claim_extraction_empty`  -> metinde gerçekten iddia yok (MEŞRU)
--   * `claim_extraction_failed` -> şema/ayrıştırma/ağ arızası (KAYIP)
--
-- Fark yalnızca konteyner logundaydı ve log döner. Ölçüm sırasında
-- `llm_calls` tablosuna bakıldı: model çağrısı `succeeded = true`
-- görünüyor, çünkü HTTP başarılı; çıktının geçersiz JSON olduğu bir
-- ÜST katmanda anlaşılıyor ve oraya hiç yazılmıyordu. Yani 430'un ne
-- kadarının gerçek kayıp olduğu veriyle CEVAPLANAMIYORDU.
--
-- Bu sütun o soruyu cevaplanabilir yapar. Davranışı değiştirmez;
-- yalnızca son denemenin sonucunu kaydeder.
--
-- NULL = henüz hiç denenmemiş (ya da bu sütundan önce denenmiş).
-- Geriye dönük doldurma YAPILMAZ: geçmiş denemelerin nedeni artık
-- bilinemez ve uydurmak, ölçmek için eklenen sütunu kirletirdi.

ALTER TABLE events ADD COLUMN IF NOT EXISTS claims_last_outcome TEXT;

COMMENT ON COLUMN events.claims_last_outcome IS
  'Son iddia çıkarımı denemesinin sonucu: ''ok'' (iddia üretildi), '
  '''empty'' (metinde iddia yok — meşru), ya da istisna sınıfının adı '
  '(ör. ''SchemaValidationError'' — gerçek kayıp). NULL = hiç denenmedi '
  'veya migration 0021 öncesinde denendi.';

-- "Tavana vurmuş ve ARIZA yüzünden iddiasız kalmış olaylar" sorgusu:
-- kalıcı kaybın tek erişim yolu budur.
CREATE INDEX IF NOT EXISTS idx_events_claims_last_outcome
  ON events (claims_last_outcome)
  WHERE claims_last_outcome IS NOT NULL AND claims_last_outcome <> 'ok';
