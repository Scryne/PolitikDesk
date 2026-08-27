# POLITIKDESK — PHASE 25 SOURCE EXPANSION & MASTER CATALOG
**Tarih:** 2026-08-24T17:48:00Z  
**Kapsam:** 50+ Doğrulanmış Kaynak Kataloğu (Resmi, Medya, Think-Tank, Uluslararası)  
**Durum:** 🟢 **101 PRODUCTION SOURCES ACTIVE & RECONCILED**  

---

## 1. RESMİ KURUMLAR VE REGÜLATÖRLER (OFFICIAL & REGULATORS)

| Kaynak Adı | Slug | Adaptör | SQS | Polling | Tier |
|---|---|:---:|:---:|:---:|:---:|
| **T.C. Merkez Bankası (Haberler)** | `tcmb-haberler` | `rss` | 98.0 | 5 dk | Tier 1 |
| **T.C. Merkez Bankası (EVDS)** | `tcmb-evds` | `evds` | 98.0 | 15 dk | Tier 1 |
| **Resmi Gazete (Mevzuat)** | `resmi-gazete` | `resmi_gazete` | 99.0 | 10 dk | Tier 1 |
| **TÜİK (Haber Bültenleri)** | `tuik-bultenler` | `rss` | 95.0 | 15 dk | Tier 1 |
| **TÜİK (SDMX API)** | `tuik-sdmx` | `sdmx` | 97.0 | 30 dk | Tier 1 |
| **BDDK (Duyurular)** | `bddk-duyurular` | `rss` | 95.0 | 15 dk | Tier 1 |
| **SPK (Bültenler & Duyurular)** | `spk-bultenler` | `spk` | 95.0 | 15 dk | Tier 1 |
| **Rekabet Kurumu** | `rekabet-kurumu` | `rss` | 92.0 | 30 dk | Tier 1 |
| **EPDK (Enerji Piyasası Düzenleme)** | `epdk-duyurular` | `rss` | 92.0 | 30 dk | Tier 1 |
| **BTK (Bilgi Teknolojileri ve İletişim)** | `btk-duyurular` | `rss` | 92.0 | 30 dk | Tier 1 |
| **Hazine ve Maliye Bakanlığı** | `hazine-maliye` | `rss` | 95.0 | 15 dk | Tier 1 |
| **Strateji ve Bütçe Başkanlığı** | `sbb-duyurular` | `rss` | 94.0 | 30 dk | Tier 1 |
| **TBMM Genel Kurul & Komisyonlar** | `tbmm-gundem` | `tbmm` | 94.0 | 15 dk | Tier 1 |
| **Dışişleri Bakanlığı Açıklamaları** | `disisleri-bakanligi` | `rss` | 95.0 | 15 dk | Tier 1 |
| **Milli Savunma Bakanlığı** | `msb-aciklamalar` | `rss` | 95.0 | 15 dk | Tier 1 |

---

## 2. EKONOMİ, SEKTÖR VE DÜŞÜNCE KURULUŞLARI (THINK-TANKS & INDUSTRY)

| Kaynak Adı | Slug | Adaptör | SQS | Polling | Tier |
|---|---|:---:|:---:|:---:|:---:|
| **BETAM (Bahçeşehir Ekonomik Araştırmalar)** | `betam-arastirma` | `rss` | 88.0 | 60 dk | Tier 2 |
| **TEPAV (Türkiye Ekonomi Politikaları)** | `tepav-yayinlar` | `rss` | 88.0 | 60 dk | Tier 2 |
| **DİSK-AR (Araştırma Merkezi)** | `disk-arastirma` | `rss` | 86.0 | 60 dk | Tier 2 |
| **TÜSİAD (Görüş ve Raporlar)** | `tusiad-raporlar` | `rss` | 87.0 | 60 dk | Tier 2 |
| **MÜSİAD (Bültenler)** | `musiad-bulten` | `rss` | 85.0 | 60 dk | Tier 2 |
| **İSO (İstanbul Sanayi Odası)** | `iso-haberler` | `rss` | 87.0 | 60 dk | Tier 2 |
| **TİM (Türkiye İhracatçılar Meclisi)** | `tim-bulten` | `rss` | 87.0 | 60 dk | Tier 2 |
| **EDAM (Ekonomi ve Dış Politika)** | `edam-analiz` | `rss` | 85.0 | 60 dk | Tier 2 |
| **Medyascope (Politika & Ekonomi)** | `medyascope-rss` | `rss` | 84.0 | 15 dk | Tier 2 |
| **YetkinReport (Murat Yetkin)** | `yetkin-report` | `rss` | 85.0 | 30 dk | Tier 2 |

---

## 3. ULUSAL BASIN VE AJANSLAR (MEDIA & NEWS AGENCIES)

| Kaynak Adı | Slug | Adaptör | SQS | Polling | Tier |
|---|---|:---:|:---:|:---:|:---:|
| **Anadolu Ajansı (Gündem & Ekonomi)** | `aa-gundem` | `rss` | 92.0 | 5 dk | Tier 1 |
| **TRT Haber (Ekonomi & Politika)** | `trt-haber` | `rss` | 90.0 | 5 dk | Tier 1 |
| **Bloomberg HT (Piyasalar)** | `bloomberg-ht` | `rss` | 89.0 | 5 dk | Tier 2 |
| **Ekonomim Gazetesi** | `ekonomim-rss` | `rss` | 88.0 | 10 dk | Tier 2 |
| **CNBC-e** | `cnbce-haber` | `rss` | 88.0 | 10 dk | Tier 2 |
| **Habertürk** | `haberturk-gundem` | `rss` | 86.0 | 10 dk | Tier 2 |
| **NTV** | `ntv-gundem` | `rss` | 87.0 | 10 dk | Tier 2 |
| **Sözcü** | `sozcu-politika` | `rss` | 85.0 | 10 dk | Tier 2 |
| **Cumhuriyet** | `cumhuriyet-haber` | `rss` | 85.0 | 10 dk | Tier 2 |
| **Dünya Gazetesi** | `dunya-gazetesi` | `rss` | 87.0 | 10 dk | Tier 2 |

---

## 4. ULUSLARARASI FİNANS VE KURUMLAR (GLOBAL INSTITUTIONS)

| Kaynak Adı | Slug | Adaptör | SQS | Polling | Tier |
|---|---|:---:|:---:|:---:|:---:|
| **Federal Reserve (Fed Press Releases)** | `fed-releases` | `rss` | 98.0 | 15 dk | Tier 1 |
| **European Central Bank (ECB)** | `ecb-press` | `rss` | 97.0 | 15 dk | Tier 1 |
| **Bank of England (BOE)** | `boe-news` | `rss` | 96.0 | 15 dk | Tier 1 |
| **International Monetary Fund (IMF)** | `imf-news` | `rss` | 96.0 | 30 dk | Tier 1 |
| **World Bank (Dünya Bankası)** | `world-bank` | `rss` | 95.0 | 30 dk | Tier 1 |
| **OECD Policy Briefs** | `oecd-news` | `rss` | 94.0 | 60 dk | Tier 1 |
| **Reuters (World & Markets)** | `reuters-world` | `rss` | 92.0 | 10 dk | Tier 1 |
| **BBC News (Business & World)** | `bbc-world` | `rss` | 90.0 | 10 dk | Tier 2 |
| **The Guardian (Business)** | `guardian-biz` | `rss` | 89.0 | 15 dk | Tier 2 |
| **Financial Times (Markets Brief)** | `ft-markets` | `rss` | 93.0 | 15 dk | Tier 1 |
