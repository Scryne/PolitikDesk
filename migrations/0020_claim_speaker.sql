-- 0020 — `claims.speaker`: bir beyanın SAHİBİ
--
-- ⛔ GEREKÇE: ADR-010 §6
--
-- Beş modül (`political_memory/candidate_filter.py`, `orchestrator.py`,
-- `service.py`, `editorial/social_publisher.py`) konuşan bilgisini
-- OKUYORDU; hiçbir şey YAZMIYORDU. Ölçüm: 4.542 iddianın 0'ında konuşan
-- vardı.
--
-- Sonucu ADR-010 §1'de görüldü: aktör ataması "olayın herhangi bir
-- makale başlığında ya da bağlı varlığında ad geçiyor mu" gibi gevşek
-- dallara düşüyor ve bir olayda adı anılan aktör, o olaydaki HERKESİN
-- beyanını devralıyordu. Cumhurbaşkanlığı'na Bahçeli'nin sözünün
-- atfedilmesinin sebebi buydu.
--
-- ⛔ NEDEN `status_reason` İÇİNE KONMADI
--
-- `status_reason` tümüyle kanıt motorunun malıdır (`rule`, `breakdown`,
-- `independence_keys`, `engine_version`…) ve her yeniden puanlamada
-- ÜZERİNE YAZILIR. Konuşan oraya konsaydı ilk `score_evidence`
-- koşumunda sessizce silinirdi.
--
-- NULL = "bu cümlede konuşanı belirten kesin bir kalıp yok".
-- Bu dürüst bir cevaptır; boş dize ya da tahmin DEĞİLDİR.
-- Çıkarım deterministiktir (`politikdesk/nlp/speaker.py`), LLM kullanmaz.

ALTER TABLE claims ADD COLUMN IF NOT EXISTS speaker TEXT;

COMMENT ON COLUMN claims.speaker IS
  'Beyanın sahibi (deterministik kalıpla çıkarıldı). NULL = kesin kalıp '
  'yok; tahmin edilmez. Bir YAYIN ORGANI konuşan değildir (ADR-010).';

-- "Bu aktörün beyanları" sorgusu — siyasi hafızanın ana erişim yolu.
CREATE INDEX IF NOT EXISTS idx_claims_speaker
  ON claims (speaker) WHERE speaker IS NOT NULL;
