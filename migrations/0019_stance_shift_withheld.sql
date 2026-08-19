-- 0019 — Söylem değişikliği kayıtlarını yayından çek: 'withheld' durumu
--
-- ⛔ GEREKÇE: DENETİMDE BULUNAN YANLIŞ SİYASİ ATIF (19 Ağustos 2026)
--
-- `stance_shifts` tablosundaki 50 kaydın tamamı kullanıcıya görünür
-- durumdaydı (`/event/{id}` "Söylem" kartı ve `/api/memory/stance-shifts`)
-- ve içerikleri denetlendiğinde şu çıktı:
--
--   * 50/50 kayıt `topic_or_metric = 'Politika / Tutum Beyanı'`
--     — yani KONU EŞLEŞTİRMESİ HİÇ YOK. Tamamen farklı konulardaki iki
--     beyan "aynı konuda fikir değiştirdi" diye karşılaştırılıyor.
--   * 50/50 kayıt `shift_type='reversal'` ve `confidence=0.85`.
--     Hep aynı olan bir güven skoru bir güven skoru değildir; ölçülmüş
--     gibi görünen sabit bir sayıdır.
--   * Aktör alanında "Adayı" (Türkçe bir sözcük parçası) ve "Resmî
--     Gazete" (bir yayın) gibi değerler var — varlık çıkarımı sızdırmış.
--   * 14 kayıt aynı gün içinde "U dönüşü" iddia ediyor.
--
-- Somut örnek: Cumhurbaşkanlığı'na `reversal` atfeden kayıt, 42 dakika
-- arayla atılmış, biri Kılıçdaroğlu/Özel biri 2007'de Erkan Mumcu
-- hakkında olan ve HİÇBİRİ Cumhurbaşkanlığı'nın beyanı olmayan iki
-- tweete dayanıyor.
--
-- Bu, adı geçen gerçek kişi ve kurumlara yöneltilmiş, sistem tarafından
-- üretilmiş bir YANLIŞ SİYASİ İSNATTIR. Kanıta dayalılık güvencesi veren
-- bir üründe verilebilecek en pahalı çıktıdır.
--
-- ADR-008'de kayda geçen ilke burada da geçerlidir:
--   «Ölü kuraldan kötü olan tek şey, yanlış çalışan kuraldır.»
--
-- Kayıtlar SİLİNMEZ — dedektör düzeltildiğinde aynı veriyle yeniden
-- ölçüm yapılabilmesi için saklanır. Yalnızca yayından çekilir.
--
-- İlgili: ADR-010, politikdesk/political_memory/shift_store.py

ALTER TABLE stance_shifts DROP CONSTRAINT IF EXISTS stance_shifts_status_check;

ALTER TABLE stance_shifts
  ADD CONSTRAINT stance_shifts_status_check
  CHECK (status IN ('open', 'superseded', 'withheld'));

-- Mevcut yayındaki kayıtların tamamı geri çekilir.
UPDATE stance_shifts SET status = 'withheld' WHERE status = 'open';

-- ⛔ TEKİLLİK İNDEKSİ GENİŞLETİLMELİ.
--
-- 0018'deki `uq_stance_shifts_signature` yalnızca `status='open'`
-- satırlarını kapsıyordu. Dedektör bundan sonra `withheld` yazacağı için
-- o indeks hiçbir yeni satırı görmez; `ON CONFLICT` hedefi eşleşmez ve
-- her koşumda AYNI kayma tekrar tekrar eklenir. Yani yayını kapatma
-- hamlesi, farkında olunmadan idempotentliği kıran bir hamleye dönüşürdü.
--
-- Doğru kapsam "yürürlükteki her kayıt" = 'open' ∪ 'withheld'
-- ('superseded' hariç, çünkü eski sürümler bilerek saklanıyor).
DROP INDEX IF EXISTS uq_stance_shifts_signature;

CREATE UNIQUE INDEX IF NOT EXISTS uq_stance_shifts_signature
  ON stance_shifts (signature)
  WHERE status <> 'superseded';

-- Okuma indeksleri de geri çekilmiş kayıtları kapsamalı: dedektör
-- düzeltilip kayıtlar yeniden yayına alındığında indeks hazır olsun.
DROP INDEX IF EXISTS idx_stance_shifts_actor;
CREATE INDEX IF NOT EXISTS idx_stance_shifts_actor
  ON stance_shifts (actor_name, detected_at DESC) WHERE status <> 'superseded';

DROP INDEX IF EXISTS idx_stance_shifts_earlier;
CREATE INDEX IF NOT EXISTS idx_stance_shifts_earlier
  ON stance_shifts (earlier_event_id) WHERE status <> 'superseded';

DROP INDEX IF EXISTS idx_stance_shifts_later;
CREATE INDEX IF NOT EXISTS idx_stance_shifts_later
  ON stance_shifts (later_event_id) WHERE status <> 'superseded';

DROP INDEX IF EXISTS idx_stance_shifts_type;
CREATE INDEX IF NOT EXISTS idx_stance_shifts_type
  ON stance_shifts (shift_type, detected_at DESC) WHERE status <> 'superseded';
