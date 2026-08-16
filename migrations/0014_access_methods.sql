-- 0014_access_methods.sql — Generic HTML ve Sosyal Medya Adaptörleri İçin access_method Kısıtının Genişletilmesi (Spec v3.5 §9.4, §12.4)

ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_access_method_check;

ALTER TABLE sources ADD CONSTRAINT sources_access_method_check
    CHECK (access_method IN ('rss', 'api', 'official_feed', 'manual', 'generic_html', 'social'));
