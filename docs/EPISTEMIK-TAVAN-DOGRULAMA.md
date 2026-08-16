# PolitikDesk — Epistemik Tavan ve Sosyal Medya Güvenlik Doğrulama Notu

**Tarih:** 16 Ağustos 2026  
**Standart:** Spec v3.5 §8.3 (Kurallar R0–R8), §9.4 (Sosyal Medya Katmanı)  
**Modül:** `politikdesk.evidence.rules`, `politikdesk.evidence.independence`, `politikdesk.ingestion.adapters.twitter`

---

## 1. Epistemik Tehdit Modeli ve Çözüm Mimarisi

Sosyal medya (Twitter/X) platformları bot ağları, koordineli propaganda, manipülasyon ve asılsız iddiaların hızla yayılabildiği mecralardır. PolitikDesk deterministik kanıt motorunda bu risklere karşı tavizsiz 3 kademeli epistemik güvenlik mimarisi uygulanır:

### Kural 1 (R7 Tavan Sınırı — Social Ceiling)
- Bir iddiayı destekleyen kanıtların **tamamı Tier 4 (social)** ise, kaç farklı bağımsız hesap veya fenomen paylaşmış olursa olsun (örn. 50+ farklı X hesabı), iddia durumu **ASLA 🟢 (strongly_corroborated) veya 🟡 (partially_corroborated) olamaz**.
- Statü kesin olarak `single_source` (🟠) tavanına sabitlenir ve `rule: "R7"`, `ceiling_reason: "all_evidence_is_tier_4_social"` damgası vurulur.

### Kural 2 (R2 Sosyal Dışlama — Non-Social Corroboration Guard)
- 🟢 `strongly_corroborated` statüsü için gereken asgari 3 bağımsız kaynak şartında (`strong_min_sources()`), sosyal medya (Tier 4) kaynakları teyit sayısına **DAHİL EDİLMEZ**.
- 1 Tier 1 Resmî Belge + 2 Twitter Paylaşımı kombinasyonu `strongly_corroborated` (🟢) ÜRETEMEZ. En fazla `partially_corroborated` (🟡) düzeyinde kalır. 🟢 için en az 3 bağımsız resmî (Tier 1), ajans (Tier 2) veya bağımsız medya (Tier 3) kaynağı zorunludur.

### Kural 3 (R8 Tutanak / Resmî Beyan İstisnası — Attribution Verified)
- Bir aktörün beyanı (`attribution`) yalnızca birincil resmî tutanakta (TBMM Tutanak Dergisi, Resmî Gazete, Sayıştay Raporu) yer alıyorsa `attribution_verified` (🔵 Beyan Sabit) statüsü alır.
- X paylaşımları hiçbir zaman `attribution_verified` (🔵) alamaz; yalnızca `attribution` olarak işlenir ve R7 tavanına tabidir.

---

## 2. Adversarial Negatif Test Sonuçları (1. Tur)

`tests/test_twitter_adapter.py` ve `tests/test_evidence.py` altında koşulan birim testleri ile kanıtlanan senaryolar:

| Test Senaryosu | Girdi | Beklenen ve Gerçekleşen Sonuç | Kural |
| :--- | :--- | :--- | :--- |
| **50+ Bağımsız X Hesabı** | 50 adet Tier 4 bağımsız kaynak | `single_source` (🟠) | R7 |
| **1 Bağımsız Medya + 1 X Hesabı** | 1x Tier 3 + 1x Tier 4 | `partially_corroborated` (🟡) | R4 |
| **1 Resmî Belge + 2 X Hesabı** | 1x Tier 1 + 2x Tier 4 | `partially_corroborated` (🟡) | R4 |
| **1 Resmî Belge + 2 Bağımsız Medya + 5 X Hesabı** | 1x Tier 1 + 2x Tier 3 + 5x Tier 4 | `strongly_corroborated` (🟢) | R2 |
| **Tahmin İçeren Sosyal Paylaşım** | `claim_type = 'prediction'` | `unverified` (⚪) — R0 Kısa Devre | R0 |
| **Resmî Tutanak Dışı X İddiası** | `claim_type = 'attribution'`, 2x Tier 4 | `single_source` (🟠) | R7 |

---

## 3. 2. Tur Adversarial Bulguları: Sahte Kurum ve Thread Manipülasyonu

### 3.1 Sahte Kurum Hesabı / Taklit (Impersonation) Koruması
- **Tehdit:** Bir X hesabının kendisini "TBMM Resmî", "Sayıştay Başkanlığı" gibi tanıtarak mavi tik/onaylı görünümle Tier 1 statüsü talep etmesi.
- **Güvence:** PolitikDesk'te Tier ataması tweet metninden, yazar biyografisinden veya kullanıcı adından **ASLA ÇIKARILMAZ**. Yalnızca `config/sources*.yml` içinde tanımlı güvenilir `source_slug` eşleşmesi ile verilir. Herhangi bir X hesabından gelen veri her zaman `tier=4` ve `kind="social"` kalır (`test_adversarial_impersonation_account_retains_tier_4_ceiling`).

### 3.2 Thread İçi Çelişkili İfadelerin Ayrıştırılması
- **Tehdit:** Bir aktörün tek bir zincirleme tweet dizisi (thread) içinde hem vaatte bulunup hem de çelişen bir beyan vererek sistemi kendi kendini teyit eden tekil bir iddiaya zorlaması.
- **Güvence:** `aggregate_threads` ve `claims.siyaset.v1` her çelişen önermeyi ayrı bir atomik iddia olarak çıkarır. İlişki motoru (`relation_engine.py`) bu iddialar arasındaki `contradicts` ilişkisini tespit eder ve "Hesap Sor" hafızasına çelişki olarak kaydeder (`test_adversarial_thread_contradictory_claims_distinction`).

---

## 4. Sonuç ve Güvence

PolitikDesk kanıt motoru deterministiktir, LLM tabanlı doğruluk kararı içermez ve kod seviyesinde hiçbir manuel override veya gizli bypass yolu barındırmaz.
