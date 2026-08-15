# Mimari Karar Kaydı — B-63 / Spec §11.4 Kaynak Varlık Sinyali (Source Existence Signal)

**Belge Sürümü:** Spec v3.5 Eki  
**Tarih:** 15 Ağustos 2026  
**Durum:** 🟢 KABUL EDİLDİ  
**İlgili Maddeler:** B-63, B-56, Spec §11.4, Spec §8.5  

---

## 1. Problem Tanımı

Mevcut varlık tanıma (NER) boru hattında (`politikdesk/nlp/entities.py`), varlıklar yalnızca makale gövdesinde (`title` ve `excerpt`) açıkça geçen isimler taranarak çıkarılmaktadır.

Ancak birincil resmî kaynaklarda (TÜİK Haber Bültenleri, TCMB Basın Duyuruları, Resmî Gazete İlanları, Hazine ve Maliye Bakanlığı İstatistikleri):
- Kaynak kendi bülteninin başlığında veya özetinde kurumun kendi adını (örneğin "Türkiye İstatistik Kurumu" veya "TÜİK") geçirmeyebilir ("Temmuz Ayı Sanayi Üretim Endeksi Sonuçları").
- Bu durum, makalenin `entities` listesinin boş kalmasına veya `varlik_ok` kuralının gereksiz yere `False` dönmesine yol açmaktadır (B-56 sonrası 16 varlıksız makalenin ana sebebi).

---

## 2. Alınan Karar (Spec §11.4 Değişikliği)

1. **Birincil Kaynak Doğal Varlık İlkesi:**  
   Tier 1 (resmî/birincil) kaynaklardan toplanan haber ve bültenlerde, kaynağın yayıncısı (`source.slug` / `source.name`), makalenin doğal ve birincil varlığı olarak kabul edilir:
   - `tuik` / `tuik_sdmx` → `Türkiye İstatistik Kurumu` (Kanonik Kod: `TÜİK`)
   - `tcmb` → `Türkiye Cumhuriyet Merkez Bankası` (Kanonik Kod: `TCMB`)
   - `resmigazete` → `Resmî Gazete`
   - `hazine` → `Hazine ve Maliye Bakanlığı`
   - `bddk` → `Bankacılık Düzenleme ve Denetleme Kurumu`
   - `spk` → `Sermaye Piyasası Kurulu`
   - `sayistay` → `Sayıştay`
   - `tbmm` → `TBMM`

2. **Kırmızı Çizgi Koruması (Spec §8.5):**  
   Bu kural **yalnızca Tier 1 resmî kurumlar** için geçerlidir. Medya veya ajans kaynaklarında (Tier 2–4) asla "taraf/görüş" varlığı eklenemez. Kaynak entity sinyali tarafsızlık kuralını çiğnemez.

3. **Geriye Dönük Uyumluluk:**  
   `entities.py` içindeki varlık çıkarıcı fonksiyonlar, `source_slug` verildiğinde resmî kurum varlığını otomatik olarak `entities` ve `key_entities` listesine birleştirir.

---

## 3. Doğrulama ve Etki
- Varlıksız kalan Tier 1 makalelerin `entities` kapsamı %100'e çıkarılır.
- Kümeleme algoritmasında (`clustering/assigner.py`) `key_entities` örtüşmesi güçlendirilir.
- Test paketi `tests/test_nlp.py` ve `tests/test_editorial.py` bu kuralı doğrular.
