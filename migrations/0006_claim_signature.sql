-- =============================================================================
-- 0006 — İddia imzası: mükerrer iddiayı veritabanı düzeyinde engelle (F5-18)
-- =============================================================================
--
-- ÖLÇÜLEN ARIZA (13 Ağustos 2026): 124 iddianın 9'u mükerrerdi — aynı olayda
-- aynı imzaya sahip iki ayrı satır. Çiftler 20-30 saniye arayla yazılmıştı ve
-- bir kısmı F5-16 düzeltmesinden ÖNCEYE aitti (10:28), yani bu düzeltmenin
-- yan etkisi değil, önceden var olan bir YARIŞ DURUMUDUR: aynı olay iki süreç
-- tarafından (worker turu + elle koşum, ya da üst üste binen Celery görevleri)
-- eşzamanlı işlendiğinde ikisi de "bu iddia henüz yok" görüp ikisi de yazıyor.
--
-- NEDEN ÖNEMLİ — zararı tam da düzeltmeye çalıştığımız yerde:
-- Mükerrer iddia, kanıt bağlarını İKİ SATIRA BÖLER. Üç bağımsız kaynak aynı
-- şeyi söylediğinde bağlar 2+1 dağılırsa `independent_count` hiçbir satırda
-- 3'e ulaşmaz ve iddia 🟡/🟢 olamaz. Yani mükerrerlik, B-79 ve F5-16 ile
-- AYNI sonucu doğurur: çapraz teyit sessizce çöker.
--
-- ÇÖZÜM: (event_id, claim_signature) üzerinde tekil indeks. Kısıt burada,
-- HESAP Python'da (`nlp/claims.py::claim_signature`).
--
-- İmza SQL'de yeniden yazılmadı ve bu bilinçli: imza `fold_text`'e dayanır
-- (İ->i, I->ı katlaması, NFKD ayrıştırma, birleşen işaretlerin atılması,
-- tipografik tırnakların temizlenmesi) ve sayısal iddialarda
-- `metric:value:period`e normalize olur. Aynı hesabın SQL'de ikinci bir
-- kopyası, `fold_text`'in kendi belgesinde yasakladığı şeydir: "İki farklı
-- katlama, iddia çıkarımında kabul edilen bir alıntının taslak denetiminde
-- uydurma sayılmasına yol açardı." Aynı gerekçe burada da geçerlidir —
-- iki katlama, aynı iddianın bir yerde tek bir yerde çift sayılması demektir.
--
-- Sütun NULL kabul eder ve indeks KISMİDİR: mevcut satırlar
-- `scripts/backfill_claim_signatures.py` ile doldurulana kadar kısıt onları
-- kapsamaz. Doldurma bittiğinde indeks fiilen tam kısıt hâline gelir.
-- -----------------------------------------------------------------------------

ALTER TABLE claims ADD COLUMN IF NOT EXISTS claim_signature TEXT;

COMMENT ON COLUMN claims.claim_signature IS
  'Olay içinde iddiayı tekilleştiren imza. nlp/claims.py::claim_signature '
  'tarafından üretilir; SQL''de yeniden hesaplanmaz (tek doğruluk kaynağı). '
  'Sayısal iddialarda metric:value:period, diğerlerinde tip + sözcük kümesi.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_claims_event_signature
  ON claims (event_id, claim_signature)
  WHERE claim_signature IS NOT NULL;
