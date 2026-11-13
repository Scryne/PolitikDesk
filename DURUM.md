# DURUM — PolitikDesk

> Envanter, sertifika değil. Ölçüm tarihi: 2026-11-13 (önceki: 2026-09-26).

**Tek cümle:** Uçtan uca çalışıyor. Taze bir veritabanıyla 101 kaynaklık yapılandırmadan 492 makale
toplandı, 336 olaya kümelendi, 28 olaydan 178 iddia çıkarıldı ve kanıta bağlandı, sabah brifingi
üretildi; testler, tip denetimi, mimari kural ve CI yeşil.

## Ne çalışıyor (ölçüldü)

- **Testler:** 2701 geçti, boş veritabanıyla ve `.env` olmadan (CI ile aynı koşul), ~50 sn.
- **Kabul testleri** (`pd test-live`, dolu veritabanına karşı): 16'nın 11'i geçti. Kalan 5'i önceki
  yayın döngüsünden arşivlenmiş binlerce olay ister (ör. "arşivde >3000 olay"); bu yalnız aylarca
  işletimle oluşur, yeni kurulumda beklenmez.
- **CI:** yeşil. 2026-08-17'den beri kırmızıydı (Linux'ta mypy, kilitsiz kurulum, ağa çıkan ve
  geliştirici verisine bağımlı testler); 2026-09-26'da düzeltildi.
- **Boru hattı:** toplama → embedding → varlık → kümeleme → iddia (LLM) → kanıt → bağlam → hafıza →
  gösterge serileri (6 seri, 1807 gözlem) → brifing.
- **LLM:** `nvidia/nemotron-3-ultra-550b-a55b`, projenin kıyaslama betikleriyle seçildi
  (çıkarım 10/10, alıntı sadakati %100; taslak grounding 7/8). Önceki modeller NIM'den kalktı.

## 2026-11-13 denetimi

- **Testler:** 2701 geçti / 1 atlandı, bu kez gerçek `.env` yerindeyken. Önceden tam koşuda ekran
  testleri `.env`'deki üretim veritabanına bağlanıp takılıyordu; `conftest` artık
  `PD_TEST_DATABASE_URL`'i import anında uygular (`fa6ba41`). ruff ve mypy temiz, CI yeşil, açık PR
  yok. `pip-audit`: setuptools 84.2.1 (`4458cbe`). NIM modeli hâlâ listede.
- **Arayüz ilk kez gerçek tarayıcıda gezildi** (Docker'sız: yerel PG'de ayrı gezinti veritabanı,
  demo derlemi gerçek boru hattından geçirildi; yalnız kaynak adaptörü ve LLM sahte). 26 rota ×
  390/1440 × açık/koyu ve 768/1280 açık: taşma 0, konsol hatası 0. Gözle bulunan kusurlar düzeltildi:
  İngilizce/ham etiketler, tanımsız rozet sınıfları, ondalık nokta, arşivde `#None`, graf renkleri ve
  etiket çakışması, 404 metni, telefonda KPI düzeni (`cac1bba`, `ee3d4db`); beyansız dönemde sahte
  "%100" tutarlılık skoru → "—" (`66b02db`); dört KPI'lı satırın 960 px'te 3+1 kırılması (`8109fad`).
- **Olay ekranı veriyle tutarlı:** makale/bağımsız kaynak sayıları, "Ne biliyoruz / Ne bilmiyoruz"
  ayrımı ve TL;DR veritabanındaki iddia durumlarıyla birebir; her kanıt alıntısı makale metninde geçiyor.

## Bilinen sınırlar

- **Kümeleme (karar: Scryne).** 13 Kasım demo derleminde kümeleme iki yönde yanıldı: bir olay üç
  ayrı haberi birleştirdi (Sayıştay raporları + vergi teklifi + bütçe komisyonu; biri 0,929 ile
  T_HIGH üstünde, yani denetimsiz), bir başkası bütçe gerçekleşmesiyle tahvil ihalesini birleştirdi;
  ters yönde faiz indirimi ve enflasyon haberleri üçer ayrı olaya bölündü. Eşiklere dokunulmadı.
  `eval/threshold_report.md` (gerçek veri: TCMB + 13 site, 55 makale / 36 olay, e5-large) seçilen
  0,92 / 0,88'de pairwise precision 0,875 (hedef ≥ 0,90, tutmuyor), otomatik precision 1,000,
  recall 0,824, küme false merge 0,026 ölçüyor; kalan hataların tamamı varlık tanınmayan makalelerden
  (21/55, B-56) geliyor ve rapor setin kapı kararı için küçük olduğunu (tek karışık küme false
  merge'ü 2,7 puan oynatıyor; çok kaynaklı olay yalnız 10) kendisi yazıyor. Yani **bölünme** gerçek
  veride de görülen bir şey (recall 0,824), **otomatik yanlış birleşme** ise gerçek ölçümde hiç
  görülmedi (1,000) ve demodaki örnek büyük olasılıkla kısa, aynı kalıpta (Meclis/TBMM/teklif)
  yazılmış demo metinlerinin sonucu; ama 55 makalelik set bunu dışlamaya yetmiyor. Açık soru:
  300 makalelik altın set (F2-20) ve varlık sözlüğü kapsamı (B-56) öne çekilsin mi.
- **Kumanda odası gösterge şeridi** dört seriyle 1280+ px'te 3+1 diziliyor (son kart tam genişlik);
  KPI satırından ayrı ızgara, düzeltilmedi.

- **Resmî Gazete, Cumhurbaşkanlığı, Sayıştay** bu ağdan TLS el sıkışmasında bağlantıyı reddediyor
  (gerçek tarayıcı dahil); kumanda odasının "Olmayanlar" paneli bunu doğru gösteriyor.
- **NIM ücretsiz katmanı yavaş ve değişken:** iddia çıkarımı ~2 dk/olay. Modeller haber vermeden
  emekliye ayrılıyor; `scripts/llm_benchmark.py` ayda bir yeniden koşulmalı.
- **Operasyonel kapılar** (`yol-haritasi.md`: 34 olay incelemesi, 7 günlük temiz pencere, diversity
  oranı) kod değil süre ve insan incelemesi ister; açık.

## Yerel çalıştırma notu

Gerçek `.env` Telegram, SMTP ve X oturum bilgisi taşır. Denemelerde
`PD_TWITTER_INGESTION_ENABLED=false PD_AUTO_DRAFT_ENABLED=false PD_TELEGRAM_NOTIFY_DRAFTS=false`
verin; brifingi `--send` olmadan üretin.
