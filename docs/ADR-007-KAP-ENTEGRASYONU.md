# ADR-007: KAP (Kamuyu Aydınlatma Platformu) Entegrasyonu

**Durum:** Ertelendi (Deferred) — erişim doğrulanamadı
**Tarih:** 19 Ağustos 2026
**Karar Vericiler:** PolitikDesk Veri & Altyapı Mühendisliği
**İlgili:** Roadmap Faz 1.3 (P1), `scripts/probe_kap.py`

---

## 1. Bağlam

Ultimate Production Roadmap, KAP'ı "ekonomi-politika kesişiminde güçlü bir
birincil kaynak adayı" olarak Faz 1.3'e (P1) koydu. Gerekçe olarak KAP'ın
**Veri Yayın Servisi (VYS)** duyurusu gösterildi.

Çıkış ölçütü: *"KAP olayları ayrı `independence_group` ile sisteme
girebilmeli."*

---

## 2. Ölçüm (19 Ağustos 2026)

Adaptör yazmadan önce erişim ölçüldü. Ölçüm `scripts/probe_kap.py` ile
yeniden koşulabilir.

| Ne | Sonuç |
|---|---|
| `www.kap.org.tr/tr/` | HTTP 200 · 162 KB |
| `/tr/bildirim-sorgu` | HTTP 200 · 1,1 MB |
| `robots.txt` | **HTTP 666** · hata sayfası — okunamıyor |
| `/tr/api/disclosures` | **ReadTimeout** (45 sn, tüm parametre kombinasyonları) |
| `/tr/api/disclosure/list`, `/query` | HTTP 404 |
| `/tr/api/member/filter/bist-sirket` | HTTP 200 · `[]` |
| Sayfanın sunucu yükünde bildirim | **Yok** (`publishDate`, `disclosureIndex`, `kapTitle` = 0) |

İki ek denetim:

* **Bot engeli mi, genel mi?** Tarayıcı benzeri ve bot benzeri User-Agent
  **aynı** sonucu verdi. Yani hedefli bir bot savunması değil; uç herkese
  kapalı.
* **Sayfa sunucu tarafında mı üretiliyor?** Hayır. 1,1 MB'lık gövde
  Next.js RSC yükü ve yalnızca endeks/şirket meta verisi taşıyor;
  bildirimler istemci tarafında, yanıt vermeyen uçtan çekiliyor.

**Sonuç: bildirimlere ulaşan, sunucudan okunabilir ve doğrulanabilir bir
uç bulunamadı.**

---

## 3. Roadmap'in dayanağı hakkında bir düzeltme

Roadmap'teki "REST API entegrasyonu için ayrı bir servis duyurusu"
ifadesi **Veri Yayın Servisi**'ne işaret ediyor. VYS, veri satıcılarına
yönelik **abonelikli bir yayın servisidir** — açık bir REST API değildir.
Ölçüm de bunu doğruluyor: açık uç yok.

Bu, roadmap'in yanlış olduğu anlamına gelmiyor; KAP gerçekten değerli bir
kaynak. Ama "API var" varsayımı doğrulanmadı ve Faz 1.3 bu varsayım
üzerine kuruluydu.

---

## 4. Karar

**KAP entegrasyonu ERTELENDİ. Adaptör yazılmadı.**

Üç gerekçe, önem sırasıyla:

### 4.1 Doğrulanmamış uca adaptör yazılmaz

Bu, bu deponun yerleşik kuralıdır ve aynı oturumda iki kez uygulandı:

* `adapters/evds.py` — altı seri kodunun altısı da `verified=False` ile
  geldi, çünkü canlı uçta doğrulanamadılar. Yanlış seri kodunun tehlikesi
  404 almak değil, **başka bir büyüklüğü** döndürmesidir.
* `adapters/tuik_sdmx.py` — "BELİRSİZSE ÜRETME": filtreye birden fazla
  seri uyarsa öğe üretilmez.

Yanıt vermeyen bir uca adaptör yazmak, çalıştığı varsayılan ama hiç
sınanmamış kod demektir. Bu depo o tür kodun bedelini üç kez ödedi
(B-42, B-43 ve EVDS'nin anahtarsız HTML yanıtı): uç 200 döndürür, gövde
beklenen şey değildir, adaptör 0 öğe üretir ve tur **sessizce başarılı**
görünür.

### 4.2 İzin beyanı okunamıyor

`robots.txt` HTTP 666 döndürüyor ve içeriği bir hata sayfası. Yani KAP'ın
otomatik erişime dair beyanı **alınamıyor**.

`HttpClient` okunamayan `robots.txt`'i "politika yok" sayar ve isteğe izin
verir (`ingestion/http.py:374-388`). Bu **izin değil, izin yokluğunun
varsayılan davranışıdır.** README'nin "kibar bot ilkeleri" taahhüdü ve
`sources.yml`'nin `tos_status` alanı, kaynak başına açık bir ToS kararı
ister. KAP için o karar bugün verilemiyor.

### 4.3 Hacim/alaka oranı ürünün kısıtına aykırı

KAP günde yüzlerce kurumsal bildirim yayımlar ve büyük çoğunluğu bu
ürünün dikeyiyle ilgisizdir (küçük ölçekli bir şirketin yönetim kurulu
değişikliği). `config/sources.yml` başlığındaki uyarı tam olarak bunu
anlatıyor:

> *"kaynak eklemek yanıltıcı derecede tatmin edicidir, kümeleme hatasını
> gizler"*

KAP eklenecekse **sert bir konu filtresiyle** eklenmeli (kamu bankaları,
özelleştirme, düzenleyici yaptırım, TVF portföyü) — filtresiz ingestion
`articles` tablosunu alakasız kayıtla doldurur ve embedding maliyetini
boşa harcar. Bu filtre, erişim çözülmeden tasarlanamaz.

---

## 5. Bunun yerine ne yapıldı

* `scripts/probe_kap.py` — ölçümü **yeniden koşulabilir** kılar. Erişim
  politikası değişirse ya da VYS aboneliği alınırsa betik saniyeler içinde
  yeni durumu söyler ve bu ADR güncellenir.
* Bulgu bu ADR'ye ve roadmap'e işlendi.

---

## 6. Yeniden değerlendirme koşulları

Aşağıdakilerden **biri** gerçekleşirse ADR yeniden açılır:

1. `python -m scripts.probe_kap` çıkış kodu 0 döndürürse (uç erişilebilir).
2. Veri Yayın Servisi aboneliği alınırsa — o zaman sözleşmeli, belgeli ve
   kararlı bir uç olur; bu ADR'nin üç gerekçesinden ikisi (4.1 ve 4.2)
   birden düşer.
3. Tarayıcı üzerinden gerçek uç adresi yakalanırsa. Bu, chrome-devtools
   ile tek adımlık bir iştir ama **erişim iznini çözmez** — 4.2 hâlâ
   geçerli kalır.

---

## 7. Alternatif: aynı bilgiyi taşıyan erişilebilir kaynaklar

KAP'ın taşıdığı ekonomi-politika sinyalinin bir kısmı, hâlihazırda
erişilebilir ve **doğrulanmış** kaynaklardan geliyor:

| Sinyal | Erişilebilir karşılığı | Durum |
|---|---|---|
| SPK düzenleme ve yaptırımları | Ulusal Veri Yayımlama Takvimi (SPK: 515 kayıt) | ✅ Faz 1.2'de bağlandı |
| BDDK bankacılık verileri | Aynı takvim (BDDK: 554 kayıt) | ✅ Faz 1.2'de bağlandı |
| Özelleştirme, kamu bankası | Resmî Gazete + Hazine | ✅ mevcut |
| Piyasa tepkisi | BloombergHT, Ekonomim, Investing | ✅ mevcut |

Yani Faz 1.3'ün ürün değerinin bir bölümü Faz 1.2 ile zaten karşılandı.
KAP'ın eklediği asıl fark **şirket düzeyinde özel durum açıklamalarıdır**
ve o katman, erişim çözülene kadar açık kalıyor.
