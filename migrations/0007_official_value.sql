-- =============================================================================
-- 0007 — Kurumun kendi yayımladığı sayı: R3'ü ÇALIŞIR hâle getirir (F5-19)
-- =============================================================================
--
-- BULUNAN ARIZA: Spec §8.3'ün R3 kuralı (resmî sayısal yayın istisnası)
-- üretimde HİÇ TETİKLENEMİYORDU. Kural `claim.value_verified_against_source`
-- bayrağını istiyor; `evidence/pipeline.py` bunu
-- `normalized_value.verified_against_source` alanından okuyor; ama o alanı
-- hiçbir şey yazmıyordu. İddia çıkarımının JSON şeması böyle bir alan
-- KABUL ETMİYOR (ve etmemeli — Spec §8.1: kanıt durumuna dair yargı LLM
-- çıktısı olamaz).
--
-- Sonuç: TÜİK kendi verisini yayımlasa bile o sayı 🟢 olamıyor, üç bağımsız
-- kaynağın tekrarlamasını bekliyordu. Kural yazılmıştı, ölüydü.
--
-- Arıza Faz 5'e kadar GÖRÜNMEZDİ çünkü resmî sayısal kaynak yoktu: TÜİK
-- ölüydü (B-42). F5-02 onu açınca kural anlamlı hâle geldi ve ölü olduğu
-- ortaya çıktı.
--
-- ÇÖZÜM: adaptörün kurumdan ALDIĞI değer makaleye yazılır. Kanıt motoru,
-- LLM'in çıkardığı `normalized_value` ile makaledeki bu değeri karşılaştırır;
-- metric + value + period ÜÇÜ DE tutuyorsa bayrak kalkar.
--
-- Bu bir lastik damga DEĞİLDİR, gerçek bir doğrulamadır: iki bağımsız yol
-- (kurumun makine okunur yayını ve modelin metinden çıkarımı) aynı sayıda
-- buluşuyor. Tutmazsa bayrak kalkmaz ve iddia normal kurallara tabi olur.
--
-- ⚠️ R3, TEK KAYNAĞA 🟢 verir — ürünün en güçlü etiketi. Bu yüzden
-- karşılaştırma gevşetilemez; kısmi eşleşme yeterli sayılamaz.
-- -----------------------------------------------------------------------------

ALTER TABLE articles ADD COLUMN IF NOT EXISTS official_value JSONB;

COMMENT ON COLUMN articles.official_value IS
  'Kaynağın KENDİ makine okunur yayınından alınan sayı (TÜİK SDMX gibi). '
  'Modelden değil, kurumdan gelir. evidence/pipeline.py bunu iddianın '
  'normalized_value''si ile karşılaştırıp R3''ün verified_against_source '
  'bayrağını belirler (Spec §8.3 R3, F5-19).';

-- R3 adayları küçük bir alt kümedir; kısmi indeks taramayı ona daraltır.
CREATE INDEX IF NOT EXISTS idx_articles_official_value
  ON articles ((official_value->>'metric'))
  WHERE official_value IS NOT NULL;
