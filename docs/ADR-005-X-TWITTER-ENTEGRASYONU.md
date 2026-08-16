# ADR-005: X (Twitter) Siyasi Hesap İzleme Entegrasyon Mimarisi

**Durum:** Kabul Edildi (Accepted)  
**Tarih:** 16 Ağustos 2026  
**Karar Vericiler:** PolitikDesk Veri & Altyapı Mühendisliği  
**İlgili Modüller:** `politikdesk.ingestion.adapters.twitter`, `config.sources_social`

---

## 1. Bağlam ve Problem Tanımı

PolitikDesk, Türkiye'deki 250+ siyasi aktörün (parti liderleri, kabine üyeleri, büyükşehir belediye başkanları) anlık beyanlarını, taahhütlerini ve duruş değişikliklerini takip etmek amacıyla sosyal medya (Twitter/X) akışlarını veri boru hattına dahil etmek istemektedir.

Entegrasyon tasarımında iki temel yaklaşım değerlendirilmiştir:
1. **Seçenek A:** Resmî X (Twitter) Enterprise / Basic REST API & Webhook
2. **Seçenek B:** 3 Kademeli Dayanıklı Mimari (Kendi Sunucumuzda Koşan / Kamuya Açık RSSHub/Nitter Bridge + Public oEmbed + Sentetik Geri Çekilme)

---

## 2. Karar Gerekçeleri ve Karşılaştırma Analizi

| Kriter | Seçenek A: Resmî X API / Webhook | Seçenek B: RSSHub / Bridge + oEmbed (Seçilen) |
| :--- | :--- | :--- |
| **Maliyet ve Bütçe** | Basic plan $100-$200/ay, Pro plan $5,000/ay. Projenin açık kaynak/bağımsız mimarisine aşırı yüksek ve öngörülemez maliyet getirir. | **Sıfır maliyet.** Docker üzerinde kendi kendini barındıran (self-hosted) RSSHub veya açık köprüler. |
| **Hizmet Şartları (ToS) & Veri Saklama** | Resmî API ToS, yerel metin analiz ve arşivleme üzerinde sıkı kısıtlamalar (veri silme zorunlulukları) uygular; bu da deterministik doğrulanabilirlik modelimizle çelişir. | Kamuoyuyla paylaşılmış açık beyanların salt metin özetini ve URL provenance kaydını kibar (polite) oran sınırlarıyla çeker. |
| **Hizmet Kesintisi & Rate Limit** | Tek API anahtarına bağımlılık; X kurumsal API politika değişikliklerinde veya kotalar dolduğunda tüm sistem kilitlenir. | **3 Kademeli Dayanıklılık:** Birincil köprü düşerse kamuya açık oEmbed ve profil ayrıştırıcısına otomatik geçer. |
| **Epistemik Bütünlük** | API'den gelse dahi içerik güvenilirlik açısından Tier 4'tür. | İçerik HER ZAMAN Tier 4 (social) ve `attribution` olarak damgalanır; R7 tavanına tabidir. |

---

## 3. Alınan Karar ve Uygulanan Mimari

PolitikDesk, **Seçenek B** doğrultusunda **3 Kademeli Esnek Adaptör Mimarisini** benimsemiştir:

1. **Kademe 1 (Birincil):** RSSHub / Nitter uyumlu XML köprü uç noktası (`/twitter/user/{handle}`).
2. **Kademe 2 (İkincil / Fallback):** Kamuya açık oEmbed JSON servisi (`publish.twitter.com/oembed`).
3. **Kademe 3 (Geri Çekilme & Sağlık İzleme):** Ardışık 3 başarısız denemede kaynağı `is_degraded = True` olarak işaretleyip hata defterine (`drain_failures`) yazan ve başarı sağlandığında otomatik düzelen izleme mekanizması.

---

## 4. Sonuçlar ve Güvenceler

- Sistem herhangi bir ücretli üçüncü taraf API anahtarına bağımlı kalmadan tam otonom çalışabilmektedir.
- Kaynak bozulmaları `pipeline_health` ve `check_deployment` tarafından anında tespit edilir.
- Sosyal medya içeriği hiçbir koşulda bağımsız teyit sayısını şişiremez (R7 ve R2 güvenceleri).
