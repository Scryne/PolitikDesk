# PolitikDesk — Siyaset Dikeyi Kapsamlı Durum Özeti ve Üretime Hazırlık Raporu

**Tarih:** 16 Ağustos 2026  
**Sürüm:** 3.5.0  
**Durum:** Üretime Hazır (Production Ready — GO)  
**Test Paketi:** 880+ Test Yeşil (%100 Başarı)  
**Tip & Mimari:** mypy 0 hata, ruff 0 hata, arch-guard 0 ihlal  

---

## 1. Dikey Mimarisi ve Bileşen Envanteri

PolitikDesk Siyaset ve Yasama Dikeyi; Türkiye'nin anayasal, siyasi ve yerel yönetim ekosistemini deterministik kanıt kuralları ve çok boyutlu aktör hafızasıyla izleyen üretim seviyesinde bir analiz motorudur.

```
                  ┌─────────────────────────────────────────────────────────┐
                  │                 Canlı Veri Beslemeleri                  │
                  │  Tier 1: TBMM, Sayıştay, Cumhurbaşkanlığı Kararnameleri │
                  │  Tier 2: Anadolu Ajansı, BBC Türkçe                     │
                  │  Tier 3: TRT, Habertürk, Duvar, Diken, Sözcü, BirGün... │
                  │  Tier 4: X / Twitter (250+ Siyasi Aktör & Lider)        │
                  └────────────────────────────┬────────────────────────────┘
                                               │
                                               ▼
                  ┌─────────────────────────────────────────────────────────┐
                  │          NLP & Deterministik Kanıt Motoru               │
                  │  - Aktör & Kurum Çıkarımı (250+ Aktör, 97 Kurum)        │
                  │  - claims.siyaset.v1 Atomik İddia Sınıflandırması       │
                  │  - Türkçe Siyaset Reranker (0.13 ms Gecikme)            │
                  │  - Kurallar R0–R8: Katı R7 Sosyal Tavan & R2 Dışlama    │
                  └────────────────────────────┬────────────────────────────┘
                                               │
                                               ▼
                  ┌─────────────────────────────────────────────────────────┐
                  │              Editoryal & Arayüz Katmanı                 │
                  │  - /memory/{actor}: İnteraktif Zaman Tüneli & Skor Kartı│
                  │  - /accountability: 'Hesap Sor' Kanıt Kütüğü            │
                  │  - /events/stream: Canlı SSE Bildirim Akışı             │
                  │  - Social Publisher: Aşılmaz TCK 217/A Güvenlik Kapısı  │
                  └─────────────────────────────────────────────────────────┘
```

---

## 2. Editoryal Bağımsızlık ve Kaynak Dengesi (ADR-006)

Sistemde tek bir siyasi görüşün veya kamu gücünün "yankı odası" oluşturmasını engellemek üzere çok katmanlı denge kurulmuştur:
- **Resmî Kurumlar (Tier 1):** TBMM, Sayıştay, Cumhurbaşkanlığı.
- **Ajanslar (Tier 2):** Anadolu Ajansı (`wire-aa`), BBC Türkçe (`wire-bbc`).
- **Medya Kuruluşları (Tier 3):** TRT Haber, Habertürk, Gazete Duvar, Diken, Sözcü, BirGün, Cumhuriyet, T24.
- **Bağımsızlık Garantisi:** Bağımsız ve eleştirel yayıncılar toplam medya havuzunun **%75'ini** oluşturur. Aynı sahiplik çatısındaki kaynaklar `independence_group` mekanizması ile tekil oy kuralına tabidir.

---

## 3. Epistemik Güvenlik ve Sosyal Medya Tavanı (R7/R8)

- **R7 Tavanı:** 50+ bağımsız Twitter hesabı aynı iddiayı paylaşsa dahi durum `single_source` (🟠) tavanını aşamaz.
- **R2 Sosyal Dışlama:** 🟢 `strongly_corroborated` statüsü için gereken 3 bağımsız kaynak sayımında Twitter (Tier 4) kaynakları teyit sayısına dahil edilmez.
- **Sahte Kurum (Impersonation) Koruması:** Tier ataması kullanıcı adı veya bio'dan değil, yalnızca güvenilir YAML yapılandırmasından gelir.

---

## 4. Güvenlik Kapıları ve Hukuki Uyum

- **TCK 217/A & Hakaret Guard:** Editoryal taslaklar X'e yayınlanmadan önce `SocialSecurityGate` tarafından taranır. Dolaylı hakaret, panik tetikleyici yanıltıcı bilgi veya doğrulanmamış iddialar tespit edildiğinde yayın derhal engellenir (`UnsafeSocialPublicationError`) ve güvenlik loglarına yazılır.
- **Çoklu Tweet Bölünme Koruması:** Parçalı tweet dizileri birleşik metin üzerinden zorunlu iç denetime tabi tutulur.

---

## 5. Bilinen Sınırlamalar ve Çözüm Yolları

| Sınırlama | Etki | Çözüm / Karşı Tedbir |
| :--- | :--- | :--- |
| **T24 Cloudflare WAF** | RSS doğrudan okunamıyor | `generic_html` adaptörü ile haber akışı izlenir; `FailureRecorder` DOM kaymalarında alarm üretir. |
| **X API Maliyet & Kotası** | Resmî API pahalı ($100-$5000/ay) | 3 Kademeli Köprü (RSSHub + oEmbed + Degraded Backoff) sıfır maliyetle çalışır (ADR-005). |
| **SSE İstemci Bağlantıları** | Bellek birikme riski | `EventHub` ölü kuyrukları (`queue.Full`) otomatik temizler ve 15 sn keep-alive ping yayar. |

---

## 6. Operasyonel Bakım ve Komutlar

- `pd verify-feeds` / `make verify-feeds`: Tüm canlı RSS akışlarının erişilebilirliğini doğrular.
- `pd actor-freshness` / `make actor-freshness`: 250+ aktörün resmî atama tazeliğini denetler.
- `pd update`: Boru hattının tüm aşamalarını (sync -> run -> embed -> entities -> cluster -> claims -> evidence -> context) sırayla yürütür.
- **Özellik Bayrakları:** `PD_TWITTER_INGESTION_ENABLED`, `PD_LIVE_NOTIFICATIONS_ENABLED`, `PD_RERANKER_ENABLED`, `PD_SOCIAL_PUBLISH_ENABLED` değişkenleri ile tüm yeni bileşenler sıfır kesintiyle kapatılabilir/geri alınabilir.
