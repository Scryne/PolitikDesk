# DURUM — PolitikDesk

> Envanter, sertifika değil. Ölçüm tarihi: 2026-09-26.

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

## Bilinen sınırlar

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
