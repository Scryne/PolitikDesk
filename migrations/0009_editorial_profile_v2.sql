-- -----------------------------------------------------------------------------
-- Editoryal Profil v2: 10 soruluk genişletilmiş editoryal kimlik (F3-08/F3-09 revizyonu)
--
-- Bu migration, editoryal kimlik kartını salt stil ayarından kapsamlı bir
-- "Editoryal Profil ve Doğruluk Katmanı"na yükseltir.
--
-- ⛔ TASARIM KISITI (Spec §10.1, P6, KVKK m.6):
-- Bu tabloda ideolojik/siyasi soru veya sınıflandırma alanı BULUNMAZ.
-- Eklenen sütunlar yalnızca biçimsel ve editoryal aktarım tercihleridir.
-- -----------------------------------------------------------------------------

ALTER TABLE editorial_profiles ADD COLUMN IF NOT EXISTS quote_habit TEXT;
ALTER TABLE editorial_profiles ADD COLUMN IF NOT EXISTS uncertainty_handling TEXT;

-- Mevcut kısıtları yeni seçenekleri kapsayacak şekilde güncelle:
ALTER TABLE editorial_profiles DROP CONSTRAINT IF EXISTS editorial_profiles_emoji_usage_check;
ALTER TABLE editorial_profiles ADD CONSTRAINT editorial_profiles_emoji_usage_check
  CHECK (emoji_usage IS NULL OR emoji_usage IN ('none', 'rare', 'minimal', 'necessary', 'frequent'));

ALTER TABLE editorial_profiles DROP CONSTRAINT IF EXISTS editorial_profiles_hashtag_usage_check;
ALTER TABLE editorial_profiles ADD CONSTRAINT editorial_profiles_hashtag_usage_check
  CHECK (hashtag_usage IS NULL OR hashtag_usage IN ('none', 'rare', 'minimal', 'topic_bound', 'frequent'));

ALTER TABLE editorial_profiles DROP CONSTRAINT IF EXISTS editorial_profiles_citation_habit_check;
ALTER TABLE editorial_profiles ADD CONSTRAINT editorial_profiles_citation_habit_check
  CHECK (citation_habit IS NULL OR citation_habit IN ('always', 'always_link', 'necessary', 'sometimes', 'inline_short', 'never'));

ALTER TABLE editorial_profiles DROP CONSTRAINT IF EXISTS editorial_profiles_quote_habit_check;
ALTER TABLE editorial_profiles ADD CONSTRAINT editorial_profiles_quote_habit_check
  CHECK (quote_habit IS NULL OR quote_habit IN ('direct_quote', 'summarized', 'minimal_quote'));

ALTER TABLE editorial_profiles DROP CONSTRAINT IF EXISTS editorial_profiles_uncertainty_handling_check;
ALTER TABLE editorial_profiles ADD CONSTRAINT editorial_profiles_uncertainty_handling_check
  CHECK (uncertainty_handling IS NULL OR uncertainty_handling IN ('explicit', 'essential_only', 'natural_concise'));

COMMENT ON COLUMN editorial_profiles.quote_habit IS
  'Alıntı ve haber aktarım tercihi: direct_quote, summarized, minimal_quote';

COMMENT ON COLUMN editorial_profiles.uncertainty_handling IS
  'Doğrulanmamış veya tek kaynaklı bilgide belirsizlik dili tercihi: explicit, essential_only, natural_concise';
