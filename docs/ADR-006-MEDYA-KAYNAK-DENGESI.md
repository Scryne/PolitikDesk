# ADR-006: Medya Kaynak Yelpazesi, Editoryal Denge ve Bağımsızlık Mimarisi

**Durum:** Kabul Edildi (Accepted)  
**Tarih:** 16 Ağustos 2026  
**Karar Vericiler:** PolitikDesk Veri & Editoryal Mühendisliği  
**İlgili Modüller:** `config/sources_legislation.yml`, `politikdesk.evidence.independence`

---

## 1. Bağlam ve Problem Tanımı

PolitikDesk deterministik kanıt motoru, siyasi ve yasal iddiaları çapraz doğrularken tek bir editoryal veya siyasi bloğun "yankı odası" (echo-chamber) oluşturmasını engellemek zorundadır (Spec v3.5 §5, §8.3).

Bu mimari karar kaydı; kamu, özel ve bağımsız medya kuruluşlarının seçim gerekçelerini, mülkiyet yapılarını ve `independence_group` mekanizması ile sağlanan epistemik dengeyi belgeler.

---

## 2. Kaynak Envanteri ve Editoryal Yelpaze Haritası

| Kaynak | Tier | Tür | Sahiplik / Finansman Yapısı | Editoryal Yelpaze | Bağımsızlık Grubu |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **TBMM** | 1 | Resmî | Anayasal Yasama Organı | Resmî Tutanak | `official-tbmm` |
| **Sayıştay** | 1 | Resmî | Anayasal Yüksek Denetim Kurumu | Resmî Rapor | `official-sayistay` |
| **Cumhurbaşkanlığı** | 1 | Resmî | Yürütme Organı | Resmî Kararname | `official-cb` |
| **Anadolu Ajansı (AA)** | 2 | Ajans | Kamu İktisadi Kuruluşu / Hazine | Kamu / Hükümet Ağırlıklı | `wire-aa` |
| **BBC Türkçe** | 2 | Ajans | Uluslararası Kamu Yayıncısı (BBC Trust) | Bağımsız / Uluslararası | `wire-bbc` |
| **TRT Haber** | 3 | Medya | Kamu Yayın Kuruluşu (TRT) | Kamu / Hükümet Hattı | `media-trt` |
| **Habertürk** | 3 | Medya | Ciner Yayın Holding (Özel) | Merkez / Özel Sektör | `media-haberturk` |
| **Gazete Duvar** | 3 | Medya | Bağımsız Dijital Gazetecilik | Eleştirel / Bağımsız | `media-duvar` |
| **Diken** | 3 | Medya | Bağımsız İnternet Medyası | Eleştirel / Bağımsız | `media-diken` |
| **Sözcü** | 3 | Medya | Estetik Yayıncılık A.Ş. | Muhalefet / Merkez Sol | `media-sozcu` |
| **BirGün** | 3 | Medya | Birgün Yayıncılık A.Ş. (Kolektif) | Bağımsız / Sol / Emek | `media-birgun` |
| **Cumhuriyet** | 3 | Medya | Cumhuriyet Vakfı | Köklü / Cumhuriyetçi | `media-cumhuriyet` |
| **T24** | 3 | Medya | T24 Bağımsız Gazetecilik A.Ş. | Bağımsız İnternet Medyası | `media-t24` |

---

## 3. Epistemik Denge ve Yankı Odası Engelleme Garantileri

1. **`independence_group` Tekil Oy İlkesi:**
   - Aynı sahiplik veya kurumsal çatı altındaki organlar (örn. kamu medyası olan AA ve TRT Haber) aynı iddia için bağımsız teyit sayısını yapay olarak şişiremez. AA (`wire-aa`) ve TRT Haber (`media-trt`) bağımsız gruplar olarak tanımlanmış olsa dahi, Tier 3 niteliğindeki TRT Haber tek başına Tier 1 resmî teyidin yerine geçemez.
2. **Kamu vs. Bağımsız Medya Denge Oranı:**
   - Dikeyde 2 kamu bağlantılı medya kaynağına (AA, TRT) karşılık **6 bağımsız/eleştirel medya kuruluşu** (BBC Türkçe, Gazete Duvar, Diken, Sözcü, BirGün, Cumhuriyet, T24) yer alır. Bu sayede bağımsız teyit havuzunun çoğunluğu (%75+) tarafsız ve eleştirel yayıncılardan oluşur.
3. **T24 WAF Durumu ve Gözlem:**
   - T24'ün kamuya açık RSS uçları Cloudflare WAF ile korunduğundan, sistem `generic_html` adaptörü ile T24'ün haber akışını izler. DOM değişikliklerinde `FailureRecorder` devreye girerek sessizce düşmeyi engeller ve alarm üretir.

---

## 4. Sonuç

PolitikDesk siyaset dikeyi kaynak dağılımı çoğulcudur, tüm anayasal aktörleri ve meclis içi/dışı muhalefeti kapsayan 360 derece dengeye sahiptir.
