# POLITIKDESK — FAZ 23
## PRODUCTION UX / EDITORIAL INTELLIGENCE / GÜNDEM V3
### FINAL PRODUCTIZATION & REAL-WORLD USABILITY AUDIT — IMPLEMENTATION PLAN

---

## 1. Mevcut Durum & Audit Özeti

PolitikDesk teknik üretim sertifikasyonunu (Faz 22) başarıyla tamamlamıştır:
- 2.009/2.009 pytest passed
- 7/7 production gates passed
- Docker servisleri (db, redis, api, beat, worker, worker-llm, rsshub) aktif ve sağlıklı
- Temiz üretim döngüsü (`prod_cycle_20260824`) aktif; tarihsel veri (`legacy_cycle_0`) izole edilmiş durumda
- Gündem V2 canlı, sıralama modları ve filtreler çalışır vaziyette

**Faz 23 Hedefi:**
Gündem ekranını üç editoryal zihinsel modeli eksiksiz destekleyen nihai bir haber/istihbarat masasına dönüştürmek:
1. "Şu anda ne oluyor?" &rarr; Kronolojik / En Yeni akış (`sort=newest`)
2. "Şu anda en önemli ne?" &rarr; Editoryal Önem / Salience akışı (`sort=important`)
3. "Belirli bir şeyi bulmak istiyorum." &rarr; Kategori, Bölge, Zaman, Kaynak, Durum ve Arama keşfi

---

## 2. Tespit Edilen UX & Mimari Problemler

1. **Sıralama Modu Algısı**: Butonlar (`Önemli`, `En Yeni`, `Son Güncellenen`) mevcuttur ancak kullanıcının hangi modda olduğunu ve bu modun ne anlama geldiğini anlatan editoryal rehberlik (tagline) eksiktir.
2. **Kategori & Bölge Keşif Arayüzü**: Şu anda seçimler sadece klasik `<select>` kutularından yapılmaktadır. Profesyonel haber masasında tek tıkla kategori ve bölge çiplerine basarak hızlı geçiş sağlanmalıdır (Discovery Bar).
3. **Aktif Filtre Görünürlüğü**: Kullanıcı birden çok filtre seçtiğinde hangi filtrelerin devrede olduğunu tek bakışta görebileceği ve filtreleri tek tek (`[ Ekonomi × ]`) veya topluca (`[ Filtreleri Temizle ]`) kaldırabileceği bir aktif filtre tepsisi gereklidir.
4. **Yeni Haberler Banner & No-Scroll-Jump**: 30 saniyelik `/api/feed/check-new` polling sonrası gelen `↓ X YENİ GELİŞME` banner'ına tıklandığında, kullanıcının scroll pozisyonu korunmalı ve yeni gelen kartlar DOM içinde hafif bir vurgu efektiyle gösterilmelidir.
5. **Editoryal Taksonomi Doğrulaması**: Kısa kelime köklerinin (`kur`, `oy`, `gaz`, `ab`, `bm`, `fed`) sınır izolasyonları (`\b`) ve 100+ Türkçe gerçekçi haber başlığı üzerindeki kesişim doğruluğu test edilmelidir.
6. **Event vs Article Şeffaflığı**: Kartlar üzerinde "X kaynak · Y makale · Z bağımsız teyit" ve salience kırılımı dürüst biçimde sunulmalıdır.

---

## 3. Önerilen Çözüm & Mimari Tasarım

### A. Gündem Sıralama Modları & Tercih Saklama
- 3 Mod:
  - `🔥 Önemli` &rarr; "Editoryal önem ve etki sıralaması (Salience)"
  - `🕐 En Yeni` &rarr; "İlk bildirilen son gelişmeler (Kronolojik akış)"
  - `⚡ Son Güncellenen` &rarr; "Son değişiklik ve güncelleme alan olaylar (Tazelik akışı)"
- Toolbar altına seçili modun editoryal anlamını belirten açıklama rozeti (`feed-mode-tagline`).
- Tercih saklama: URL parametresi önceliklidir; yoksa `localStorage` tercihi okunarak kullanıcı tercihi korunur.

### B. Kategori & Bölge Keşif Çubuğu (Discovery Bar)
- **Kategori Çipleri**: `[ Tümü ]` `[ 💼 Ekonomi ]` `[ 🏛️ Politika ]` `[ 🌐 Dış Politika ]` `[ 🛡️ Güvenlik ]` `[ ⚖️ Hukuk ]` `[ ⚡ Enerji ]` `[ 💻 Teknoloji ]` `[ 🏥 Sağlık & Toplum ]` `[ 🏙️ Yerel ]` `[ 📋 Diğer ]`
- **Bölge Çipleri**: `[ Tümü ]` `[ 🇹🇷 Türkiye ]` `[ 🇺🇸 ABD ]` `[ 🇪🇺 Avrupa ]` `[ 🏜️ Orta Doğu ]` `[ 🕊️ Rusya-Ukrayna ]` `[ 🌏 Asya-Pasifik ]` `[ 🌐 Küresel ]`
- Mobil ve dar ekranlarda yatay yumuşak kaydırma (`overflow-x: auto`) desteği.

### C. Görünür Aktif Filtreler Tepsisi
- `Aktif Filtreler: [ 💼 Kategori: Ekonomi ✕ ] [ 🇹🇷 Bölge: Türkiye ✕ ] [ ⏱️ Zaman: Son 24 saat ✕ ] [ ✕ Filtreleri Temizle ]`
- Her çipin `✕` butonuna basıldığında o filtre anında kaldırılır ve URL güncellenir.
- Browser Back/Forward ve sayfa yenileme (Refresh) durumunda filtreler %100 korunur.

### D. Canlı Yeni Haber Banner'ı & Scroll Stabilitesi
- 30 saniyede bir sessiz kontrol.
- `↓ X YENİ GELİŞME` banner'ı tıklanınca sessiz parça yenileme (`/feed/cards`) yapılır.
- Scroll sıçraması engellenir, yeni kartlar `@keyframes newCardPulse` ile kısa süreli vurgulanır.

---

## 4. Değişiklik Yapılacak Dosyalar

1. **`politikdesk/web/feed.py`**:
   - Gündem V3 Discovery Bar, Aktif Filtre Tepsisi, Sıralama Tagline ve JS etkileşimlerinin entegrasyonu.
2. **`politikdesk/web/ui/css.py`**:
   - Gündem V3 discovery bar, chip butonları, aktif filtre tepsisi, animasyonlar ve responsive kuralların eklenmesi.
3. **`politikdesk/analysis/taxonomy.py`**:
   - Kural tabanlı taksonomi sınır kontrolleri ve eşleme optimizasyonu.
4. **`tests/test_gundem_v3_ux.py` (Yeni)**:
   - Sıralama, filtreleme, keşif çubuğu, aktif filtre tepsisi ve URL state birim testleri.
5. **`tests/test_taxonomy_100_benchmark.py` (Yeni)**:
   - 100+ Türkçe haber başlığı ile taksonomi ve false-positive doğruluk testi.
6. **`tests/test_journalist_scenarios_e2e.py` (Yeni)**:
   - 10 gerçek gazeteci sabah çalışma senaryosunun testleri.

---

## 5. Test, Performans ve Rollback Planı

- **Testler**:
  - `pytest -q` (Mevcut 2009 test + yeni eklenen Gündem V3 ve taksonomi testleri).
  - `ruff` & `mypy` tip ve kod standartları denetimi.
  - `scripts/check_architecture.py` & `scripts.production_gates` mimari izolasyon doğrulaması.
- **Performans**:
  - DB feed sorguları `EXPLAIN ANALYZE` ile doğrulanacak, p95 < 1.5s hedefi korunacak.
- **Rollback / Güvenlik**:
  - Sıfır yıkıcı silme (No destructive DELETE/DROP).
  - Legacy cycle izolasyonu korunur.

---

## 6. Kabul Kriterleri (Acceptance Criteria)

- [ ] Gündem sıralama modları (Önemli / En Yeni / Güncellenen) net ve açıklayıcı
- [ ] Kategori ve Bölge Keşif Çubuğu (Discovery Bar) responsive ve hızlı
- [ ] Aktif filtreler tepsisi görünür ve tek tıkla temizlenebilir
- [ ] URL state ve sayfa yenileme sonrası state korunumu %100
- [ ] Yeni haber banner'ı scroll jump yapmıyor ve yeni kartları vurguluyor
- [ ] 100+ Türkçe haber başlığında taksonomi doğruluğu kanıtlandı
- [ ] 10 gerçek gazeteci persona senaryosu başarıyla geçti
- [ ] 2.000+ pytest PASS
- [ ] Ruff & Mypy PASS
- [ ] Production Gates (7/7) PASS
- [ ] Docker Stack HEALTHY
