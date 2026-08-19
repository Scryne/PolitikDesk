# Kaynak Envanteri ve Genişletme Analizi — 20 Ağustos 2026

Bu belge bir dilek listesi değildir. Her öneri (a) ölçülmüş bir eksikliğe
bağlıdır ve (b) erişilebilirliği **canlı olarak yoklanmıştır**.

> ✅ **KARAR VERİLDİ VE UYGULANDI (20 Ağustos 2026).** Ürün sahibi
> `max_sources` 21 → 22 kapasitesini onayladı; SBB envantere alındı.
> Uygulama, ölçüm ve etki analizi:
> **`docs/ADR-013-SBB-KAYNAK-GENISLETMESI.md`**
>
> Bu belge kararın gerekçesini ve alternatifleri kayda geçirir; sonuç
> ADR-013'tedir. Özet: SBB Tier 1 kanıt bağını 75 → 82'ye çıkardı, ancak
> 🟢 sayısı değişmedi (2 → 2) çünkü R2'nin ikinci ayağı (≥3 bağımsız grup)
> açık kaldı. Darboğaz kaynak sayısından **hikâye eşleşmesine** kaydı.

---

## 1. Mevcut envanter (canlı veritabanı)

| Tier | Tür | Adet | Son 24 saatte veri veren |
|---|---|---|---|
| 1 | official | 8 | 8 |
| 2 | wire | 5 | 5 |
| 3 | media | 30 | 30 |
| 4 | social | 46 | 39 |

**Tier 1 (8):** TCMB, TCMB-EVDS, TÜİK, Hazine ve Maliye, Resmî Gazete,
TBMM, Sayıştay, Cumhurbaşkanlığı.

Kaynak sağlığı iyi: 89 aktif kaynağın 82'si son 24 saatte veri verdi.
Susan 7'si RSSHub'ın X'ten aldığı HTTP 503'e bağlı ve gerçek sessizliktir
(ADR-012'de kayıtlı).

---

## 2. Ölçülen asıl sorun: kanıt motoru **aç**

Envanterdeki sayı değil, **kanıt havuzundaki ağırlık** belirleyicidir.

### 2.1 Kanıt havuzunun tier dağılımı

| Tier | Kanıt bağı | Makale | Pay |
|---|---|---|---|
| 1 | 75 | 40 | **%1,8** |
| 2 | 171 | 60 | %2,6 |
| 3 | 2.391 | 747 | %36,6 |
| 4 | 3.892 | 1.353 | **%59,6** |

### 2.2 Sonucu: 🟢 pratikte ulaşılamıyor

Kanıt durumlarının canlı dağılımı (5.262 iddia):

| Durum | Adet | Pay |
|---|---|---|
| 🟠 single_source | 4.544 | %86,4 |
| 🟡 partially_corroborated | 377 | %7,2 |
| ⚪ unverified | 312 | %5,9 |
| 🔵 attribution_verified | 27 | %0,5 |
| 🟢 **strongly_corroborated** | **2** | **%0,04** |

R2 kuralı 🟢 için iki şeyi birden ister: **≥3 bağımsız kaynak** (Tier 4
sayılmaz) **VE bir Tier 1 birincil kaynak**. Canlı veride bu bileşimi
sağlayan iddia sayısı ölçüldü:

```sql
-- >=3 bagimsiz (tier<=3) VE tier 1 birincil kaynakli iddia
SELECT count(*) ... -> 0
```

**Sıfır.** Yürürlükteki iki 🟢 R2'den değil, R3'ten (resmî sayı
doğrulaması) geliyor.

### 2.3 Bu bir kural kusuru DEĞİLDİR

`docs/EPISTEMIK-TAVAN-DOGRULAMA.md` R2/R7'nin katılığını bilinçli bir
epistemik politika olarak tanımlıyor ve adversarial testlerle
kilitlemiş. Kurallar doğru çalışıyor.

Sorun **girdi tarafında**: motorun 🟢 üretebilmesi için Tier 1 kanıtın
medya kanıtıyla aynı iddiada buluşması gerekiyor, ama Tier 1 havuzun
%1,8'i. Tier 1 üretimi 7 günde toplam 88 makale:

| Kaynak | 7 günde saklanan | Konu filtresi elemesi |
|---|---|---|
| sayistay | 29 | %32 |
| cb-kararname | 28 | %35 |
| tbmm | 13 | %20 |
| hazine | 7 | %73 |
| tcmb-evds | 6 | %0 |
| tuik | 3 | %0 |
| resmi-gazete | 1 | %76 |
| tcmb | 1 | %80 |

Makro gündemin **veri üreten** kurumları (TÜİK 3, TCMB 1, Resmî Gazete 1)
en az katkıyı veriyor.

> Not: 393 olayın `independent_count` değeri 0, 1.085'inin 1. Ancak bu
> tek başına kümeleme kusuru DEĞİL — sınandı: 48 saatteki 7 "enflasyon"
> makalesi gerçekten 7 ayrı hikâyeydi (Portekiz, Malta, Avro Bölgesi,
> RBA…), gerçek Türkiye haberi ise olay 1819'da **12 makaleyle doğru
> kümelenmişti.** Kümeleme çalışıyor; havuz seyrek.

---

## 3. Öneri — Tier 1 yoğunluğunu artır

Kaynak eklemenin gerekçesi "daha çok haber" değildir; dosyanın kendi
uyarısı hâlâ geçerli: *"kaynak eklemek yanıltıcı derecede tatmin
edicidir, kümeleme hatasını gizler."* Buradaki gerekçe farklı ve
ölçülebilir: **R2'nin gerektirdiği Tier 1 birincil kaynağı üretmek.**

### 3.1 Erişim yoklaması (20 Ağu 2026, canlı ölçüm)

15 aday yoklandı; 11'i erişilebilir, **yalnızca 1'inde makine okunur
besleme var**.

| Aday | Erişim | Besleme | Değerlendirme |
|---|---|---|---|
| **SBB** (Strateji ve Bütçe Bşk.) | 200 | ✅ `/feed/` RSS | **1. sıra öneri** |
| YSK | 200 | ✗ | HTML adaptörü gerekir; seçim dönemi kritik |
| SPK | 200 | ✗ | HTML |
| BDDK | 200 | ✗ | HTML |
| Rekabet Kurumu | 200 | ✗ | HTML |
| EPDK | 200 | ✗ | HTML |
| Ticaret Bakanlığı | 200 | ✗ | HTML (ASP.NET, 404 yönlendirmeli) |
| ÇSGB | 200 | ✗ | HTML; asgari ücret için değerli |
| SGK | 200 | ✗ | HTML |
| Danıştay | 200 | ✗ | HTML |
| Yargıtay | 200 | ✗ | HTML (`?feed=rss2` → 403) |
| Anayasa Mahkemesi | 404 | — | Kök dizin 404; ayrı yol araştırması gerekir |
| Kamu İhale Kurumu | ConnectError | — | Erişilemedi |
| TCMB Blog | ConnectError | — | Erişilemedi |

### 3.2 Birinci öneri: SBB — doğrulandı

**Neden tam hedef.** Yayımladığı kalemler doğrudan makro gündem
yorumudur. Canlı beslemeden alınan gerçek başlıklar:

- "2026 yılı Haziran ayı Ödemeler Dengesi Verileri açıklandı"
- "2026 yılı Temmuz ayı Tüketici ve Üretici Fiyat Gelişmeleri açıklandı"
- "2026 yılı Temmuz ayı geçici Dış Ticaret Verileri açıklandı"
- "İşgücü Piyasasındaki Gelişmelerin Makro Analizi — 2026 I. Çeyrek"
- "Kamu Sektörü İstihdam Sayıları 2026 2. Çeyrek"
- "Türkiye Ekonomisinde Haftalık Gelişmeler ve Genel Görünüm"

Bunlar TÜİK/TCMB verisinin yayımlandığı **günlerde** çıkar; yani medya
haberleriyle aynı iddiada buluşma olasılığı yüksek — R2'nin ihtiyacı
tam olarak budur.

**Ölçülen erişim.** WordPress RSS, HTTP 200, 10 kalem, ~49 KB.
`robots.txt`: `Disallow: /wp-admin/` — besleme yolu **açık**.

**Önerilen yapılandırma:**

```yaml
- slug: sbb
  name: "Cumhurbaşkanlığı Strateji ve Bütçe Başkanlığı"
  tier: 1
  kind: official
  independence_group: "official-sbb"   # Hazine/TCMB'den AYRI kurum
  access_method: rss
  tos_status: allowed
  base_url: "https://www.sbb.gov.tr"
  feed_url: "https://www.sbb.gov.tr/feed/"
  adapter: rss
  topics: [enflasyon, butce_ve_hazine, issizlik_ve_istihdam, buyume,
           kamu_borclanmasi]
```

`independence_group` **ayrı** olmalı: SBB, Hazine'den ve TCMB'den farklı
bir kurumdur ve bağımsız teyit sayar. Cumhurbaşkanlığına bağlı olması
onu `cb-kararname` ile aynı gruba koymaz — ölçüt kurumsal yayın
sorumluluğudur, hiyerarşi değil. (Karşı görüş savunulabilir; karar
verilmeden önce tartışılmalı, çünkü yanlış gruplama bağımsız sayımı
şişirir.)

**Karar:** `max_sources` 21 → 22 **onaylandı ve uygulandı** (ADR-013).

### 3.3 İkinci dalga (adaptör işi gerektirir)

Besleme yok, `generic_html` veya özel adaptör gerekir. Değer sırası:

1. **YSK** — seçim dönemi için tekil kritik kaynak; şu an yalnızca X
   üzerinden (Tier 4) izleniyor, yani R7 tavanı gereği **hiçbir zaman
   🟢 üretemiyor.**
2. **ÇSGB** — asgari ücret (`asgari_ucret_ve_zamlar` konusu tanımlı ama
   birincil kaynağı yok).
3. **BDDK / SPK** — finansal düzenleme kararları.
4. **Rekabet Kurumu** — soruşturma ve ceza kararları.

### 3.4 Aynı sorunun ikinci yüzü: Tier 4'e hapsolmuş kurumlar

Şu kurumlar sisteme **yalnızca X hesabı olarak** giriyor: AYM, BDDK,
SPK, SGK, YSK, TBMM, TCMB, TÜİK, Sayıştay, Hazine, Dışişleri, Adalet.

Son beşinin resmî muadili Tier 1'de var; **ilk beşinin yok.** R7 gereği
bu beş kurumun beyanı kaç kez tekrarlanırsa tekrarlansın `single_source`
tavanında kalır. Canlı ölçüm: **157 iddia** hâlihazırda
`ceiling_reason: all_evidence_is_tier_4_social` damgası taşıyor.

---

## 4. Redundan / düşük katkı

* **KAP** — Roadmap Faz 1.3'te P1'di; ADR-007 ile **doğru biçimde
  ertelendi** (robots.txt HTTP 666, doğrulanabilir uç yok). Yeniden
  önerilmiyor.
* **Tier 4 sosyal kadro (46)** — geniş ve iyi seçilmiş; parti liderlerinin
  neredeyse tamamı kapsanıyor. **Büyütülmesi önerilmez:** R7 tavanı
  nedeniyle marjinal epistemik katkısı sıfıra yakındır, buna karşılık
  RSSHub köprüsü zaten turun en yavaş ve en kırılgan parçası.

---

## 5. Karar özeti

| # | Eylem | Karar mercii | Hazırlık |
|---|---|---|---|
| 1 | ~~`max_sources` 21 → 22, SBB ekle~~ | Ürün (Spec §9.2/D6) | ✅ **UYGULANDI** (ADR-013) |
| 2 | ~~SBB `independence_group` tartışması~~ | Ürün | ✅ **AYRI** olarak karara bağlandı (ADR-013 §2) |
| 3 | YSK için HTML adaptörü | Mühendislik | seçim takvimine bağlı |
| 4 | ÇSGB / BDDK / SPK / Rekabet | Mühendislik | 2. dalga |
| 5 | Tier 4 kadrosunu büyütme | — | **önerilmiyor** |
