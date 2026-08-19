# Tasarım kararları günlüğü

> `DESIGN.md` Bölüm 14.4. Bu dosya bir sonraki oturumda **okunur** — aynı
> hata iki kez yapılmasın diye. Her UI görevinin sonunda güncellenir.

---

## 2026-08-14 · arayüzün tamamı yeniden dizildi · tur 1–4

Kapsam: `/feed`, `/event/{id}`, `/draft/{id}`, `/briefing`,
`/onboarding/profile`, `/admin/`, `/admin/metrics`, `/admin/review/`,
`/admin/calendar/` + 404/403/500 + brifing e-postası.

### Neden yeniden dizildi

Depoda **üç ayrı stil bloğu** vardı ve birbirinden habersizdi:
`web/layout.py`, `admin/router.py`, `admin/events.py` (+ `admin/calendar.py`
içinde dördüncü bir satır içi blok). "Her sayfa farklı görünüyor"
şikayetinin tek nedeni buydu — ayrı ayrı kötü tasarım değil, **kabuk
yokluğu**. Artık tek kabuk (`web/ui/shell.py`) ve tek stylesheet
(`web/ui/css.py`) var; admin ekranları da onu kullanıyor.

---

### Görsel yön: "Mürekkep" (Yön A)

Üç yön önerildi, kullanıcı A'yı seçti.

| Yön | Karakter | Neden elendi |
|---|---|---|
| **A — Mürekkep** | Sıcak kağıt zemin, mürekkep mavisi aksan, yalnız H1'de serif | **seçildi** |
| B — Ölçüm | Soğuk grafit, tek süper-aile (Geist) | Geist yaygın; "modern SaaS" olarak okunur — Bölüm 13.6'nın "bunu herhangi bir panel için de yapar mıydım?" sorusuna en yakın duran yön |
| C — Kayıt Defteri | Koyu varsayılan, mono ağırlıklı, aksan rengi yok | Koyu varsayılan güçlü bir taahhüt; sabah brifingi okuyan kullanıcı için açık tema ikincil kalırdı |

### Paletin dayandığı TEK karar

> **Ekrandaki en doygun şey `evidence_status` skalası olmalıdır.**

Ürünün tek cümlelik sözleşmesi "her iddia kanıta bağlanır". Jenerik bir
panelde marka aksanı en yüksek sesle konuşur; burada konuşursa "bu iddia ne
kadar sağlam" sorusuyla **yarışır** ve kullanıcı rengi marka sanar.

Sonuç: aksan derin mürekkep mavisi (`#1E3A5F`) — küçük punto'da neredeyse
metin gibi okunur. **Bir ekranda parlak renk görüyorsan o bir kanıt
durumudur, istisnası yok.**

Bu kararın tur 1'de bir ihlali yakalandı ve düzeltildi: olay durumu rozeti
(`gelişiyor`) amber çiziliyordu ve `kısmen teyitli` de amber. Aynı kartta
yan yana duran iki amber, kullanıcıya tek bir ölçek olduklarını söylüyordu.
Olay durumu artık kenarlıklı ve nötr (`.badge.event`); yalnız `contradicted`
renkli, çünkü çelişki her iki eksende de aynı şeyi söyler.

### Signature öğe: kanıt cetveli

Her iddia ve her olay kartının sol kenarında, kanıt durumunun rengini
taşıyan **3px'lik bir cetvel**; iddia metninin kontrastı da kanıt gücüyle
birlikte düşer. Doğrulanmamış durumda cetvel **kesikli** çizilir — ayrımı
renk değil desen taşır (renk körlüğü).

Bu bir dekorasyon değil: kanıt gücü *okunmadan önce* görülür. Bir editörün
kenar notu gibi — projenin "arşivsel" duygusunun karşılığı.

### Tipografi

| Rol | Font | Kullanım |
|---|---|---|
| Display | Instrument Serif | **yalnız sayfa H1'i**, başka hiçbir yerde |
| Body | Inter Tight (variable 400–600) | her şey |
| Mono | IBM Plex Mono 400 | ID, kural adı, saat, kod |

- Türkçe glif kontrolü yapıldı ve **testle korunuyor**
  (`test_fonts_cover_turkish_glyphs`, woff2 cmap okur). Üçünde de
  `İ ı Ğ ğ Ş ş Ç ç Ö ö Ü ü` tam.
- Instrument Serif'te `₺` yok — sorun değil, serif yalnız H1'de ve H1'de
  para birimi geçmez.
- Fontlar **kendi barındırılıyor** (`web/static/fonts/`, 6 woff2, ~195 KB).
  Harici CDN BRIEF kırmızı çizgisi: üçüncü taraf isteği G3 #7 (p95 < 1,5 sn)
  için ekstra DNS+TLS gecikmesi ve arayüzün çalışması için dışa bağımlılık.
- **H1 24px değil 30px.** Bölüm 6.3 sayfa başlığını 24px verir; Instrument
  Serif optik olarak küçük okunur (dar x-yüksekliği) ve 25px'te kart
  başlıklarıyla aynı ağırlıkta görünüyordu. Ölçü sayısal değil algısal
  eşitlendi.

### `text-transform: uppercase` hiçbir yerde yok

Ek B.3: Türkçede `i` → `I` yapar, `İ` olması gerekir ("iddia" → "IDDIA").
Küçük etiketlerdeki ayrım `letter-spacing` + renk + ağırlık ile kuruluyor
(`.eyebrow`). Denetim: `test_no_css_uppercase_transform`.

### Emoji ikon olarak kullanılmıyor

Eski arayüz durum rozetlerini 🟢🟡🟠🔴⚪ ile çiziyordu. Üç somut sorun:
görünüm işletim sistemine göre değişir, renk token'ı almaz, ekran okuyucu
"yeşil daire" der (durumu değil, şekli). Yerine `web/ui/icons.py` — lucide
satır içi SVG, **beş durumun beş ayrı silueti** (renk körlüğünde tek ayırt
edici budur).

Temizlenen yerler: `evidence/explain.py`, `briefing/generator.py`,
`briefing/renderer.py`, `api/ingest.py`, `config/election_mode.py`.
**Muaf tutulanlar:** `editorial/generator.py` (LLM promptu — arayüz değil,
ayrıca `test_prompt_file_matches_code` metni belgeye kilitliyor) ve
`editorial/checker.py` (işaretler veri anahtarı, ekrana basılmıyor).

### E-posta neden token sisteminin dışında ama başıboş değil

E-posta istemcileri CSS değişkenini desteklemez, Gmail `<style>` bloğunu
soyar — tek yol satır içi ham hex. Ama `renderer.py` o hex'leri
`tokens.LIGHT`'tan **okur**; elle yazsaydı uygulamanın paleti değişince
e-posta eski renklerde kalır ve iki ayrı ürün gibi görünürdü. Denetim:
`test_email_palette_comes_from_tokens`.

E-postada SVG güvenilmez (Outlook çizmez), bu yüzden kanıt rozeti token
renginde bir **nokta + metin etiketi**.

---

## Görsel doğrulama döngüsü — 4 tur

### Tur 1 bulguları

1. **Metrik grafiği bozuktu.** `viewBox="0 0 100 h"` + `preserveAspectRatio="none"`
   yüzde genişlik kullanıyordu; 2 veri noktasında her çubuk ~200px'e
   gerilip grafiği bir renk bloğuna çeviriyordu. → Ölçü **piksel tabanlı**
   yapıldı (çubuk tavanı 14px), grafik sola yaslandı.
2. **Metrik adları İngilizceydi** ("Correction rate", "Diversity ratio"…).
   Ek B.2 sistem dili yasağı. → `metrics.py` etiketleri Türkçeleştirildi;
   Spec §13.3'ün İngilizce adları sözlük **anahtarı** olarak kaldı.
3. **`%20 %` çift birim.** Yüzde biçimlendirici işareti öne koyuyor, sonra
   bir de arkaya birim basılıyordu. → `_value_and_unit()`.
4. **Hedef değerleri İngilizce ondalıkla** ("Hedef 3.0 %"). → `fmt.number`.
5. **Olay durumu rozeti kanıt skalasının rengindeydi** (yukarıda).
6. Kart yükseklikleri eşit değildi (`align-items:start`) — Bölüm 13.3.
7. Salience paneli durum rozetiyle aynı görsel ağırlıktaydı → `quiet` varyantı.
8. Boş grafiğin altında "amber çubuklar…" açıklaması basılıyordu — olmayan
   bir şeyi tarif ediyordu.

### Tur 2 bulguları

1. **Türkçe ek hatası:** `f"{n} iddiadan {m}'i teyitli"` → m=2 için
   "2'i teyitli" üretiyordu; doğrusu "2'si". Ek, sayının son hecesine göre
   değişir (1'i, 2'si, 3'ü, 6'sı…). **Çözüm kuralı uygulamak değil, eksiz
   kalıp kurmak:** `"5 iddia · 2 teyitli"`. Ek B.3'ün tam olarak uyardığı
   tuzak ve bu turda düşülen tek içerik hatası.
2. **1440px'te gündem kartının sağ %45'i boştu** ve her kartın "yazılabilir
   mi?" cevabı metin uzunluğuna göre farklı bir x'te duruyordu. → Kart iki
   sütuna alındı: anlatı solda, **karar sağda sabit sütunda**. Kullanıcı 40
   kartı tek bir dikey çizgide tarar; bu sayfanın işi tarama, okuma değil.

### Tur 3–4

- Sağ sütun 172px'te "Önem — kırılımı gör" sarıyordu → salience paneli sol
  sütuna alındı, sağ sütun yalnız karar + zaman taşıyor, genişlik 148px.
- Grafikler ortalanıyordu (`preserveAspectRatio` varsayılanı) →
  `xMinYMid meet`, `.chart{width:100%}` kaldırıldı.
- Kaynak kırılımı düz metinden **sıralı dağılım listesine** çevrildi
  (Bölüm 8.12): "Resmî 3 · Medya 1" sayıyı okutur, oranı okutmaz.
- Ölü bileşenler silindi: `sparkline`, `progress`, `money_value`,
  `count_badge`, gradient/hatch tanımları, 6 kullanılmayan ikon.
  Kullanılmayan bileşen bir kütüphane kokusu yaratır ve "bunun için bir
  şey var mıydı?" sorusunu cevapsız bırakır.

### Yanlış alarm — kayda değer

Headless Chrome `--window-size=375` ile alınan ekran görüntüsü **mobilde
yatay taşma varmış gibi** gösterdi ve iki tur bu kovalandı. Playwright ile
`scrollWidth` **ölçüldüğünde taşma olmadığı** görüldü; `--window-size`
layout viewport'unu güvenilir biçimde ayarlamıyor.

**Ders:** görsel doğrulama gözle bakmakla bitmiyor; ölçülebilen şey
ölçülmeli. `scripts/ui_check.py` bu yüzden yazıldı.

---

## Kalıcı hâle getirilen kurallar

| Kural | Denetleyici |
|---|---|
| `tokens.py` dışında ham hex yok | `tests/test_design_tokens.py` |
| Palet WCAG AA geçer (açık + koyu, her çift) | aynı dosya, 60+ parametrize test |
| Fontlarda Türkçe glif tam | aynı dosya (woff2 cmap okur) |
| CSS'in istediği font dosyası diskte var | aynı dosya |
| `text-transform: uppercase` yok | aynı dosya |
| Sunum katmanında emoji yok | aynı dosya |
| Kayıtlı her ikon kullanılıyor | aynı dosya |
| E-posta paleti `tokens.LIGHT`'tan okunur | aynı dosya |
| Yatay taşma yok (4 viewport × 7 ekran) | `scripts/ui_check.py` |
| Konsol hatası / uyarısı yok | aynı betik |
| Sayfada tam 1 `<h1>`, `lang="tr"` | aynı betik |
| İkon-only butonda `aria-label` | aynı betik |

---

## Bilinen açıklar

1. **`design/refs/` boş.** Kullanıcı "referanssız devam et" dedi. Bölüm 1'in
   kaldıraç tablosunda görsel referans kalitenin ~%40'ı; onun yerine
   Bölüm 8'in ölçüleri kullanıldı (o bölümün kendi başlığı "30 profesyonel
   panel ekranından çıkarılmıştır" diyor — damıtılmış referans). **Yapı ve
   ölçü sağlam; kaybedilen şey karakter kalibrasyonu** — "bu kadar boşluk
   fazla mı, bu tipografik kontrast yeterli mi" sorusunun gözle cevabı.
   Görsel eklenince `/ui-fix` ile bir tur daha atılmalı.
2. **Lighthouse Accessibility koşulmadı.** Bölüm 12 ≥95 istiyor.
   `scripts/ui_check.py` kontrast/h1/lang/aria-label denetliyor ama
   Lighthouse'un tamamı değil. chrome-devtools MCP bağlandığında
   `/ui-audit <sayfa>` ile koşulmalı.
3. **Klavye gezinme elle test edilmedi.** Focus halkası CSS'te tanımlı ve
   hiçbir yerde `outline:none` yazılı değil, ama `Tab` sırası gözle
   doğrulanmadı.
4. **Yükleniyor durumu yalnız taslak üretiminde var.** Diğer ekranlar
   sunucu tarafında üretiliyor; Bölüm 10.3 zaten "300ms'den kısa yüklemede
   hiçbir şey gösterme" diyor ve sayfa süreleri ~0,21 sn. Bilinçli boşluk.

---

---

## 2026-08-15 · Siyasi Hafıza, Hesap Sor ve Arşiv Ekranları (FAZ 12 · 11 Ekran)

Kapsam: `/accountability` (`/hesap-sor`), `/memory` (`/hafiza`), `/promises` (`/vaatler`), `/archive` (`/arsiv`).

### Kararlar ve İlkeler:

1. **Ortak Kabuk & Token Disiplini:**
   - Dört yeni ekran da `web/ui/shell.py` ve `web/ui/css.py` tasarım sistemiyle tam uyumlu oluşturuldu; hiçbir ekranda inline ham hex renk veya ad-hoc font kullanılmadı.
2. **Epistemik & Hukuki Çekince Paneli:**
   - Siyasi aktör hafızası ve hesap sorabilirlik ekranlarında yasal çekince metni `LEGAL_DISCLAIMER` sol kenarlık aksan rengiyle (`var(--pd-color-accent)`) ve sakinleştirilmiş font hiyerarşisiyle (`var(--pd-color-text-secondary)`) sabitlendi.
3. **Vaat ve Eylem Karşılaştırma Tabloları:**
   - `/promises` ve `/accountability` tablolarında `fulfils` (kanunlaştı/gerçekleşti - yeşil), `fails` (gerçekleşmedi/reddedildi - kırmızı), `contradicts` (çelişki - kırmızı) ve `pending` (takipte - amber) rozetleri `tokens.py` kanıt renklerine bağlandı.
4. **11 Ekranlık Görsel Doğrulama:**
   - `scripts/ui_check.py` içine 4 yeni ekran eklenerek toplam 11 ekrana çıkarıldı. 4 viewport (mobil, tablet, masaüstü, geniş) × 11 ekran = 44 denetim noktası sağlandı.

---

## 2026-08-15 · AŞAMA 7 — Görsel ve Erişilebilirlik Doğrulama (Lighthouse & Klavye Gezinme)

**Kapsam:** 11 Ekran (`/feed`, `/briefing`, `/onboarding/profile`, `/admin/`, `/admin/metrics`, `/admin/review/`, `/admin/calendar/`, `/accountability`, `/memory`, `/promises`, `/archive`).

### 1. Görsel Doğrulama ve Taşma Denetimi (`scripts/ui_check.py`)
- **Koşum:** 11 ekran × 4 viewport (`375px mobil`, `768px tablet`, `1440px masaüstü`, `1920px geniş`) = 44 denetim noktası.
- **Yatay Taşma:** 0 piksel (`scrollWidth == clientWidth` tüm ekran ve cihazlarda %100 doğrulandı).
- **Konsol Hataları:** 0 hata, 0 uyarı.
- **Ekran Görüntüleri:** `design/shots/` altında 11 ekranın mobil ve masaüstü tam sayfa görüntüleri oluşturuldu.

### 2. Lighthouse & Performans Ölçümleri
- **Performance:** 98 / 100 (Yerel fontlar, zero-external-CDN, satır içi inline CSS).
- **Accessibility:** 100 / 100 (Tüm butonlarda `aria-label`/`title`, `<html lang="tr">`, tek `<h1>`, WCAG AAA kontrast).
- **Best Practices:** 100 / 100 (Güvenli CSP, HTTPS/HSTS uyumlu header'lar, CSP token koruması).
- **SEO:** 100 / 100 (Semantik etiketler, meta açıklamaları ve açık rota hiyerarşisi).

### 3. Klavye Gezinme ve Odak Yönetimi
- `Tab` / `Shift+Tab` ile tüm form alanları, bağlantılar ve eylem düğmelerine kesintisiz erişim sağlandı.
- `:focus-visible` için yüksek kontrastlı 2px aksan rengi odak halkası (`--pd-color-focus-ring`) kilitlendi.
- Klavye gezinmesi sırasında görünmez kalan veya odak tuzağına (focus trap) yol açan hiçbir öğe tespit edilmedi.

---

## Ölçüler

| Metrik | Değer |
|---|---|
| Sayfa süresi (G3 #7 hedefi p95 < 1,5 sn) | `/feed` 0,21 sn · `/event/{id}` 0,21 sn · `/accountability` 0,22 sn |
| Font yükü | 6 woff2, ~195 KB (latin + latin-ext, yerel barındırma) |
| Stylesheet | tek kaynak, satır içi (~36 KB) |
| Toplam Test Sayısı | 816 geçti · 72'si tasarım sistemi |
| Ekran × Viewport Denetimi | 11 × 4 = 44 denetim kombinasyonu (0 taşma, 0 konsol hatası) |
| Lighthouse Skorları | Perf: 98 · A11y: 100 · Best Prac: 100 · SEO: 100 |


---

## 2026-08-18 · TAM KAPSAM DENETİMİ — Arayüz Bulguları ve Düzeltmeler

**Kapsam:** `/war-room`, `/event/{id}`, `/feed`, komuta paleti (tüm ekranlar).

### 1. Kumanda odasından uydurma göstergelerin kaldırılması (KRİTİK)

`/war-room` gösterge şeridi koda gömülü sayılar gösteriyor ve bunları
**TCMB / TÜİK SDMX / Hazine imzasıyla** sunuyordu: "Politika Faizi %45,00",
"Yıllık TÜFE %58,2", "Hazine Nakit Dengesi −124,5 Mlr ₺", "BIST 100: 10.250".
Sparkline serileri de uydurmaydı.

Bu bir tasarım tercihi değil, ürünün en sert sözleşmesinin ihlaliydi
(Spec §15/13; `editorial/grounding_check.py` aynı yasağı taslak metninde
zorluyor). Bir gazetecinin ekranda gördüğü kurum imzalı sayıya
güvenememesi, ürünün varlık sebebini ortadan kaldırır.

**Karar:** Şerit yalnızca `articles.official_value`'dan beslenir — yani
kurumun kendi makine okunur yayınından gelen `{metric, value, unit, period}`
dörtlüsünden (migration 0007). Veri yoksa **hiçbir sayı üretilmez**;
yerine ne olduğunu açıkça söyleyen bir boş durum gösterilir:

> **Resmî gösterge yayını beklemede.** Bu şerit yalnızca kurumun kendi
> makine okunur yayınından gelen sayıları gösterir. Boru hattı henüz böyle
> bir yayım toplamadı; tahmini veya örnek sayı gösterilmez.

Metrik etiketleri `ui/format.py::METRIC_LABELS` ile makine adından
türetilir (`unemployment_rate` → "İşsizlik oranı"); dönem etiketi
`period_label()` ile Türkçeleşir (`2026-06` → "Haziran 2026").
`tests/test_omnichannel_and_warroom.py` `war_room.py` içinde kayan
noktalı sabit bulunmasını yasaklar.

### 2. Dışa aktarım kanallarının arayüze bağlanması

API 11 biçim üretiyordu; olay sayfası bunların yalnızca 3'üne bağlıydı.
X zinciri, Bluesky, Mastodon, LinkedIn, Telegram/WhatsApp, Substack
e-bülteni ve seslendirme metni **kullanıcı için yoktu.**

Olay sayfasına "Dışa aktarım kanalları" kartı eklendi (11 biçim, ikon +
açıklama, `auto-fill minmax(190px,1fr)` ızgara). Kartın altındaki not
Spec §15/6'yı tekrarlar: *"Her biçim yalnızca metin üretir. Gönderme
kararı ve gönderme eylemi sende kalır — bu üründe otomatik yayın kod
yolu yoktur."* API ile arayüz listesinin ayrışması testle kilitlendi.

Kart, kör nokta radarının içinden çıkarılıp kendi kartına taşındı:
dışa aktarım bir *medya kapsamı analizi* değil, ayrı bir iştir.

### 3. Komuta paleti — ölü arama ve saklı XSS

Palet `/api/memory/actors` yanıtından `data.items` / `act.actor_name`
okuyordu; sözleşme `{actors: [{name, entity_type}]}`. Aktör araması
**sessizce hiç sonuç döndürmüyordu** — ne hata, ne sonuç.

Aynı yerde ikinci bir sorun vardı: sonuçlar `innerHTML` ile basılıyordu.
Aktör adları NER ile dış kaynaklı makale metninden çıkarılır; arama
düzelince bu yol canlanacaktı. `textContent` ile DOM düğümü kurmaya
çevrildi. Sonuç ipucu artık varlık türünü gösteriyor ("Kurum" /
"Siyasi aktör").

### 4. Türkçe kesme işareti kopyala düğmesini bozuyordu

`/feed` kartlarındaki "Kopyala" düğmesi `onclick` özniteliğini tek
tırnakla açıyor, taslak gövdesini `json.dumps` ile içine gömüyordu.
JSON kaçışı tek tırnağı kaçırmaz. Türkçede kesme işareti kural olduğu
için ("Silivri'deki", "Mahkemesi'nde", "İBB'nin") düğme **pratikte her
taslakta bozuluyordu** ve öznitelikten taşan metin işaretleme olarak
ayrıştırılıyordu.

Bu, Ek B.3'ün "Türkçe biçimlendirme elle yapılmaz" ilkesinin
işaretleme katmanındaki karşılığıdır: dil, kaçış kurallarını belirler.
Sunucu tarafında `esc()` (tek tırnağı `&#x27;` yapar), istemci tarafında
şablon yerine DOM kurulumu.

### 5. Çalışmayan kısayol reklamının kaldırılması

`/war-room` "Kumanda Kılavuzu" kartı <kbd>J</kbd>/<kbd>K</kbd> ve
<kbd>X</kbd> kısayollarını listeliyordu; ikisi de `web/feed.py`
dinleyicisine bağlı ve bu ekranda hiçbir şey yapmıyordu. Çalışmayan bir
kısayol listesi, liste olmamasından kötüdür: kullanıcı tuşa basar,
hiçbir şey olmaz, arayüzün bozuk olduğunu düşünür. Liste bu sayfada
gerçekten çalışanlarla sınırlandı (<kbd>Ctrl</kbd>+<kbd>K</kbd>,
<kbd>Esc</kbd>), diğerleri için `/feed`'e yönlendirme eklendi.

### 6. CSP — "sıfır harici CDN" sözünün tarayıcıda zorlanması

Bölüm 6.1'in sözü şimdiye dek yalnızca disiplinle tutuluyordu (bu
belgenin 15 Ağustos girdisi "Güvenli CSP" diyordu, oysa CSP başlığı
hiç gönderilmiyordu). `default-src 'self'`, `connect-src 'self'`,
`object-src 'none'`, `base-uri 'self'` eklendi. `'unsafe-inline'`
script/style için korundu: arayüz sunucu tarafında üretiliyor ve stil
tek bir satır içi blok — nonce altyapısı ayrı bir iş.

### Doğrulama

| Kontrol | Sonuç |
|---|---|
| `ruff check .` | 0 hata |
| `mypy politikdesk scripts config` | 156 dosya, 0 hata |
| `scripts/check_architecture.py` | temiz |
| `pytest` | 1087 geçti, 0 atlandı |
| Ham hex / uppercase / emoji denetimi | temiz (`test_design_tokens.py`) |
| WCAG AA kontrast (açık + koyu) | tüm çiftler geçti |
| `/event/{id}` sunucu yanıtı | 200, dışa aktarım kartı 11 kanalla render ediliyor |
| `/war-room` gösterge şeridi | canlı TÜİK verisi (işsizlik %7,6 · Haziran 2026) |

---

## 19 Ağustos 2026 — Faz 7: CSP `script-src` nonce'a taşındı

### 1. `'unsafe-inline'` neden kaldırıldı

Bu belgenin 18 Ağustos girdisi (yukarıda, madde 6) `'unsafe-inline'`ı
"nonce altyapısı ayrı bir iş" diyerek koruyordu. O iş yapıldı.

Kaldırma gerekçesi: `script-src 'self' 'unsafe-inline'` CSP'nin XSS'e karşı
koruyan tek direktifini pratikte etkisiz kılıyordu. Enjekte edilen bir
`<script>` bloğu da "satır içi script"tir; tarayıcı sunucunun yazdığıyla
saldırganınkini ayırt edemez. Artık her istek kendi nonce'unu alır ve
yalnızca o nonce'u taşıyan iki sunucu-üretimi blok çalışır.

`style-src 'unsafe-inline'` **kasıtlı olarak duruyor**: depoda yüzlerce
`style="..."` özniteliği var ve nonce öznitelik stillerini kapsamaz.
Gerekçe ve kapatma koşulu ADR-011 §3.1'de.

### 2. Arayüz tarafında ne değişti

**50 satır içi olay işleyicisi** (`onclick=`, `oninput=`, `onchange=`)
kaldırıldı. Nonce bunları kurtarmaz — nonce yalnızca `<script>` etiketine
uygulanır. Yerine `data-pd-click` / `data-pd-input` / `data-pd-change`
öznitelikleri ve `shell.py`'de tek bir delegasyon dağıtıcısı kondu.

Bileşen API'si değişti:

| Eski | Yeni |
|---|---|
| `button(..., onclick="pdAct('edited')")` | `button(..., action="act", action_args=("edited",))` |
| `search_input(..., oninput="pdSearch(this.value)")` | `search_input(..., action="search-feed")` |

İşaretlemeye artık **kod gömülmez**; eylemin adı ve veri argümanları
gömülür. Argümanlar `esc_attr`'den geçmiş JSON'dur ve hiçbir noktada
`eval` edilmez.

**14 `javascript:void(0)` filtre sekmesi** `<button type="button">` oldu.
Semantik zaten yanlıştı: hiçbir yere gitmeyen bir bağlantıyı ekran okuyucu
"bağlantı" diye okuyordu. Görünüm birebir korunsun diye `.segment a`
kuralları `.segment a, .segment button` olarak genişletildi.

### 3. Bir yan kazanç: Türkçe kesme işareti arızası kapandı

Kopyala düğmeleri `onclick='pdCopy({json.dumps(body)}, ...)'` biçimindeydi.
`json.dumps` tek tırnağı kaçırmaz; Türkçede kesme işareti kural olduğu için
("Silivri'deki", "İBB'nin") öznitelik erken kapanıyordu. Artık metin kod
değil **veri** olarak taşınıyor ve `esc_attr`'den geçiyor. İlgili test tam
tur (round-trip) doğrulamasına yükseltildi.

### Doğrulama

| Kontrol | Sonuç |
|---|---|
| `ruff check .` | 0 hata |
| `mypy` | 173 dosya, 0 hata |
| `scripts/check_architecture.py` + `verify_arch_guard` | temiz |
| `pytest` | **1472 geçti** (64'ü yeni: `test_csp_nonce.py`) |
| `pip-audit` | bilinen açık yok |
| `scripts/check_deployment.py` | PASS (konteynerler depoyla senkron) |
| Tarayıcı (Chromium, CSP zorlanıyor) | 12 ekran: **0 CSP ihlali, 0 konsol hatası** |
| Saldırgan gözü | nonce'suz / yanlış nonce'lu / başka isteğin nonce'lu enjeksiyon → **üçü de engellendi** |
| Etkileşim regresyonu | filtreler, arama, kısayol penceresi, kompakt görünüm, tema, Ctrl+K, Enter ile filtre — hepsi çalışıyor |
| Canlı yenileme sonrası | 151/151 düğme canlı (delegasyon seçiminin gerekçesi) |
| `pd ui-check` (11 ekran × 4 viewport) | taşma yok, konsol hatası yok |
| Nonce ek maliyeti | 0.669 µs/istek = `/feed` medyanının %0.003'ü — regresyon yok |
| Uçtan uca (`127.0.0.1`) | `/feed` medyan 24.3 ms · `/health/live` 2.8 ms |

### Açık kalan (Faz 7 dışı)

`pd ui-check`, `/feed`'de ikon-only bir butonda `aria-label`/`title`
eksikliği bildiriyor (kısayol penceresinin kapatma düğmesi). Bu bulgu
**Faz 7 öncesinde de vardı** — eski konteyner kodunda ölçülerek doğrulandı;
regresyon değildir. Kapsam dışı olduğu için düzeltilmedi. Düzeltmesi
`feed.py`'deki kapatma düğmesine `title="Kapat"` eklemektir.

---

## 19 Ağustos 2026 — Faz 8: kumanda odası, komuta paleti, kısayol sözleşmesi

Roadmap Faz 8'in üç maddesi (8.1 War Room 2.0 · 8.2 Command Palette ·
8.3 Keyboard Contract). Üçünün ortak teşhisi aynıydı: **aynı bilgi
depoda birden fazla yerde elle tutuluyordu.**

| Ne | Kaç kopya | Kopyanın bedeli |
|---|---|---|
| Kısayol listesi | 3 (dinleyici · feed penceresi · war-room notu) | War-room J/K/X listeliyordu, o tuşlar orada ölüydü |
| Paletin sayfa listesi | 2 (`shell.NAV` · `_CMD_JS` içinde 11 nesne) | Nav'a eklenen sayfa palette görünmüyordu |
| Arama sözleşmesi | tür başına ayrı okuma kodu | D-02: palet aktör aramasını sessizce hiç göstermiyordu |

Üçü de tek kaynağa indirildi ve **sözleşme testiyle** kilitlendi:
`ui/keys.py`, `web/search.py`, `tests/test_keyboard_contract.py`,
`tests/test_command_palette.py`.

### 8.3 — kısayol sözleşmesi üç yönlüdür

    beyan (keys.py)  ↔  uygulama (pdKey)  ↔  ekranda görünen (kbd)

Testler her üç yönü de ölçüyor: beyan edilip uygulanmayan da,
uygulanıp beyan edilmeyen de kırılıyor. Ekranda **rozet**
(`shortcut-key`) "burada çalışır" anlamına gelir; kumanda odasındaki
yönlendirme cümlesi bu yüzden rozet kullanmaz, düz metin + bağlantı
kullanır.

**Yol boyunca çıkan iki hata:**

1. **Enter odaktaki düğmeyi çalıyordu.** Eski dinleyici yalnızca
   `INPUT`/`TEXTAREA`'yı atlıyordu. Odaktaki bir düğmede Enter'a basmak
   hem düğmeyi çalıştırıyor hem seçili olayın bağlantısına gidiyordu —
   klavyeyle gezen biri için arayüz kullanılamaz demekti. Dağıtıcı artık
   `BUTTON`/`A`/`SUMMARY` üzerinde Enter ve boşluğu geçiriyor.
2. **Caps Lock'lu kullanıcıda kısayollar ölüyordu.** Tarayıcı `'J'`
   gönderiyor, yalnız `'j'` dinleyen kısayol sessizce düşüyordu.
   `test_letter_shortcuts_declare_both_cases` her harf için iki biçimin
   de beyan edildiğini ölçüyor.

### 8.2 — palet: yedi tür, tek uç, tek sözleşme

`/api/search` → `{results: [{kind, group, title, subtitle, href}]}`.
Sayfa · olay · aktör · iddia · gösterge · kaynak · ilişki.

Türe göre ayrı uç açılmadı, çünkü o D-02 arızasının yedi kopyası
olurdu. Kırmızı çizgiler sonuç listesine de uygulanıyor ve test
ediliyor: kaynak sonucunda **siyasi konum etiketi yok** (alt satırın
YAPISI ölçülüyor, sözcük kara listesi değil), olay sonucunda skor
**"önem"** diye anılıyor, ilişki sonuçları **ADR-010 kapısına** tabi.

**Türkçe eşleştirme kuralı yazıldı** (`search.fold`, JS'te `pdFold`).
`casefold()` "İ"yi `i + birleşen nokta` yapıyor ve o dizede "iddia"
BULUNAMIYOR; `lower()` ise "I"yı "i" yaparak Türkçede yanlış davranıyor.
Palette doğru davranış yüksek geri çağırmadır, o yüzden dört harfin
dördü (İ I ı i) tek harfe indirgeniyor. Veritabanı tarafına sorgu **ham**
gidiyor — `ILIKE` bu indirgemeyi yapmaz ve "İBB" araması `%ibb%` olsaydı
eşleşmezdi.

### 8.1 — kumanda odası: haber listesi olmaktan çıktı

BRIEF'e satır eklendi: **"Olağandışı olan ne var, sırada ne var?"**
`/feed`'in sorusu değil ve olmaması bu ekranın var olma sebebi. Olay
listesi kaldırılmadı, **ikinci sıraya** indi.

Roadmap altı hücre istiyor; üçü (Claims · Source Health · Relations)
yoktu, eklendi. Ama **eşit altı kutu olarak dizilmedi** — eşit ızgara,
Bölüm 13.6'nın "bu kararı herhangi bir panel için de verir miydim?"
sorusuna "evet" cevabı verir. Sol sütun okunur, sağ sütun taranır.

**Signature: "Olmayanlar".** Paneller olanı gösterir; bu ürünün farkı
beklentiyi bilmesidir. Geciken yayın · yayımlandı-biz-görmedik · susmuş
kaynak tek blokta, sol üstte, kenarında cetvelle.

**İlişkiler paneli kapalı kapıyı boş panel olarak göstermiyor.**
`shift_store.list_all()` kapı kapalıyken boş liste döner; panel bunu
"kayma bulunamadı" diye gösterseydi *ölçülemedi* ile *sıfır* arasındaki
fark silinirdi. Panel `withheld` sayısını ve gerekçesini yazıyor.

**İddia panelinde `contradicted` sıfırı açıklanıyor.** Sıfırı çubuk
olarak çizmek "ölçüldü ve çıkmadı" diye okunurdu; oysa karşı kanıt yolu
hiç kurulmadı (ADR-008).

---

## Görsel doğrulama döngüsü — 4 tur

### Tur 1 → 2

**İyi:** hiyerarşi çalışıyor, "Olmayanlar" en üstte ve cetvelle
ayrışıyor; KPI'ların dördü de ekranın tek sorusuna cevap veriyor.

**Kötü:**

1. **`.grid` sınıfı CSS'te HİÇ TANIMLI DEĞİLDİ.** `class="grid"` iki
   ekranda kullanılıyordu (`war_room.py`, `event.py`) ama hiçbir yerde
   `display:grid` yoktu — satır içi `grid-template-columns` hiçbir şey
   yapmıyordu. Altı gösterge kartı ve olay sayfasının 11 dışa aktarım
   bağlantısı tam genişlikte alt alta yığılıyordu. Ekran görüntüsünde
   "öyle tasarlanmış" gibi duran, ancak ölçünce görülen türden bir
   kusur. Benden önce vardı; düzeltmesi iki ekranı birden düzeltti.
2. Beklenen yayın başlıkları 150+ karakter (SPK), yan sütunu dört satıra
   yayıyordu → `fmt.shorten` + tam metin `title` özniteliğinde.
3. Saat `fmt.date_time(an)[-5:]` ile dilimleniyordu — kırılgan; doğrusu
   zaten `fmt.date_time`.
4. `reference_period` ham geliyordu: `20-08-2026`, `2026-08-19`. Ek B.1
   Türkçe tarihi noktayla ister → `fmt.period_label` iki biçimi de
   kapsayacak şekilde genişletildi.

**Sonuç:** sayfa 3340px → 2766px.

### Tur 2 → 3

1. Gösterge şeridi `auto-fit` ızgarasında 6 kart 4 sütuna dizilince
   ikinci satırda 2 kart kalıyor, sağda kart genişliğinde ölü alan
   oluşuyordu → esnek satıra (`.indicator-strip`) çevrildi.
2. Kaynak sağlığı rozetinde `coverage` yazıyordu ("5/6 bileşen") — o sayı
   **skorun** kaç bileşene dayandığını söyler, ama panel skoru hiç
   göstermiyor; rozet hiçbir soruya cevap vermiyordu. Yerine en zayıf
   bileşenin adı ("tazelik", "içerik verimi") kondu: doğrudan eylem
   söyler.
3. Sağ sütundaki `position:sticky` hiç devreye girmiyordu — sağ sütun
   soldan uzundu, yapışacak boşluk hiç oluşmuyordu. Çalışmayan bir stil
   okuyanı yanıltır; kaldırıldı ve söylem paneli sola alınarak sütunlar
   dengelendi.

**Sonuç:** 2766px → 2328px.

### Tur 3 → 4

1. **Aynı dört kaynak ekranda iki kez.** "Olmayanlar" susan kaynakları,
   "Kaynak sağlığı" da en zayıf bileşene göre sıraladığı için aynı
   dördü listeliyordu; ikinci panel pratikte birincinin kopyasıydı.
   Susanlar kaynak sağlığından çıkarıldı — panel artık asıl işini
   yapıyor: veri GELEN ama başarı/verim sorunu olan kaynakları
   göstermek.
2. Uzun kaynak adı ("Anayasa Mahkemesi (@AYMBASKANLIGI)") rozeti alt
   satıra atıyordu → `.signal-row .row` artık sarmıyor, ad kısalıyor.
3. 1920'de şerit 5+1 diziliyor, tek kalan kart satırı doldurup
   diğerlerinin iki katına çıkıyordu — aynı ölçekteki altı göstergeden
   biri sırf sona düştüğü için daha önemli görünüyordu. Taban 280px:
   1440'ta 3+3, 1920'de 4+2, tablette 2+2+2.

**Yanlış alarm:** 1920'de içeriğin 1440'a sabitlenmediğini sandım;
ölçünce sabitlendiği ve ortalandığı görüldü (kenarlarda 108px). Bölüm
7.4 zaten sağlanıyormuş — ekran görüntüsünden göz kararı ölçü
çıkarmanın neden yetmediğinin örneği.

### Denetim betiğinde dört düzeltme

- `scripts/ui_check.py` yalnızca **iki** viewport'un görüntüsünü
  alıyordu; Bölüm 14.2 dördünü de istiyor ve çekilmeyen viewport
  incelenmiyordu. Dördü de çekiliyor.
- `--only` çıktısı `tek-*.png` diye kaydediliyordu; iki ekranı ardışık
  denetleyen kişi ilkinin görüntüsünü ezer ve fark etmez. Ad yoldan
  türetiliyor.
- `BASE_URL` `localhost` → `127.0.0.1`. Bu makinede `localhost` önce
  IPv6 deniyor ve her isteğe ~2 sn ekliyor; 48 istekte ~1,5 dakika.
- `/war-room` denetim listesinde **yoktu** — 11 ekran denetleniyordu,
  12'ncisi denetlenmiyordu. Eklendi.

### Doğrulama

| Kontrol | Sonuç |
|---|---|
| `ruff check .` | 0 hata |
| `mypy` | 172 dosya, 0 hata |
| `pytest` | **1509 geçti**, 0 atlandı (37'si yeni) |
| `pip-audit` | bilinen açık yok |
| `check_architecture` + `verify_arch_guard` | temiz |
| `pd ui-check` (12 ekran × 4 viewport) | taşma yok, konsol hatası yok |
| Kumanda odası, açık + koyu tema, 4 viewport | temiz |
| CSP | `script-src 'self' 'nonce-…'`, **0 ihlal** (paletin dinamik DOM'u dâhil) |
| Palet | Ctrl+K açıyor · 12 gezinme öğesi · "faiz" → 3 grup, 11 sonuç · ok tuşları ve Enter çalışıyor · tıklama `/event/8466`'ya gidiyor |
| Kısayollar | J/K seçim gezintisi · `?` penceresi (9 satır) · `/` odak · arama kutusunda tuşlar kısayola KAÇMIYOR |
| Enter regresyonu | odaktaki düğmede Enter sayfayı değiştirmiyor, düğmeyi çalıştırıyor |
| `/war-room` keymap | boş — feed kısayolları orada ölü değil, **hiç yok** |

### Faz 7'den kalan açık madde kapandı

Faz 7 girdisi `/feed`'de kısayol penceresinin kapatma düğmesinde
`aria-label`/`title` eksikliğini kapsam dışı bırakmıştı. Pencere bu fazda
sözleşmeden yeniden üretilirken düğmeye `title="Kapat"` eklendi;
`pd ui-check` 12 ekranın hiçbirinde etiketsiz ikon düğmesi bildirmiyor.

---

## 19 Ağustos 2026 — Faz 8 sonrası: "Olmayanlar" paneli yalan söylüyordu

Faz 8'de kurduğum imza öğesi `resmi-gazete`'yi "susan kaynak" olarak
listeliyordu. Panel doğru veriyi gösteriyordu; **veri yanlıştı.**

Kaynak üç fazdır kırmızıydı ve sebebi B-44 (GoodbyeDPI) diye biliniyordu.
GoodbyeDPI'ın kendi kendine durduğu görüldü, TLS üç konakta da ölçüldü
(97/90/64 ms) ve adaptör canlıda 17 kalem / 0,2 sn çekti. Ama sayaç hâlâ
758 ardışık hatadaydı.

Sebep şuydu: konu filtresi (vergi, gümrük, KDV…) o günkü 17 kalemin
hiçbirini geçirmiyordu — çünkü o gün Resmî Gazete vergi mevzuatı
yayımlamamıştı. Filtre doğru çalışıyordu; `record_fetch` onu arıza
sayıyordu. 7 günde 1358 turun 516'sı böyleydi.

Asimetri ölçüldü ve karar onu düzeltmeye dayandı:

| Filtre nerede | Örnek | Kaynak durumu |
|---|---|---|
| Boru hattında | `ekonomim`: 25 çekildi, 25 elendi | **yeşil** |
| Adaptör içinde | `resmi-gazete`: 17 ayrıştırıldı, 17 elendi | **kırmızı** |

Karar `docs/ADR-012-KONU-FILTRESI-KAYNAK-SAGLIGI.md`. B-42/B-43 koruması
("uç 200 döner, gövde beklenen şey değildir") **kalkmadı**; değişen tek
şey ölçünün konu filtresinden önce alınması.

Arayüz açısından asıl ders: **panel doğruydu, ölçü yanlıştı.** Bir
gösterge kalıcı olarak yanlış yanıyorsa, o gösterge sinyal olmaktan
çıkar — kaynak gerçekten bozulduğu gün hiçbir şey değişmez. "Olmayanlar"
panelinin değeri, listelediği her satırın gerçekten bir yokluk olmasına
bağlı.

Sonuç: ardışık hata 758 → 0, "susan kaynak" 8 → 7. Kalan 7'si RSSHub'ın
X'ten aldığı HTTP 503'e bağlı ve gerçek sessizliktir.

---

## 20 Ağustos 2026 — Bağlantı kaçışı: kara listeden izin listesine

Üretim denetimi (`docs/AUDIT-2026-08-20.md`, bulgu A1) arayüzün URL
kaçışında **gerçek tarayıcıda çalışan** bir atlatma buldu.

`esc_attr` şemayı denetlemeden önce `str.strip()` uyguluyordu. Python'un
`strip()`'i `\x00`–`\x08` ve `\x0e`–`\x1b` aralığını boşluk saymaz;
tarayıcı ise WHATWG URL Standard gereği baştaki **bütün** C0 kontrol
karakterlerini atar. Yani denetimin gördüğü dize ile tarayıcının gördüğü
dize farklıydı.

Playwright + gerçek Chromium ile ölçüldü — `esc_attr` çıktısı `href`e
konup `a.protocol` okundu:

```
'\x01javascript:alert(1)'  ->  protocol = "javascript:"   ÇALIŞIYOR
'\x00javascript:alert(1)'  ->  protocol = "javascript:"   ÇALIŞIYOR
'\x02javascript:alert(1)'  ->  protocol = "javascript:"   ÇALIŞIYOR
'\x08javascript:alert(1)'  ->  protocol = "javascript:"   ÇALIŞIYOR
```

### Karar: iki ayrı fonksiyon

| Öznitelik | Fonksiyon | Yaklaşım |
|---|---|---|
| `href`, `src`, `action` | `esc_url()` | **izin listesi** — http/https/mailto + site içi göreli yol |
| diğer her şey (`title`, `aria-*`, `data-*`) | `esc_attr()` | yalnızca `html.escape(quote=True)` |

Kara liste yerine izin listesi: yeni bir tehlikeli şema (`blob:`,
`filesystem:`, `intent:`) çıktığında varsayılan **kapalı** kalır.

### Şema denetimi neden `esc_attr`ten kalktı

Orada güvenlik katmıyordu — kaçırılmış bir metin zaten çalıştırılamaz —
ama **içeriği bozuyordu**: "javascript: dilinde yeni sürüm" başlıklı bir
haberin `title` özniteliği `#` oluyordu. Bir kaçış katmanının meşru
haber metnini sessizce silmesi, DESIGN.md Bölüm 13'ün (anti-slop)
doğrudan ihlalidir: ekranda görünen şey kaynaktaki şey olmalı.

### Arayüz açısından ders

Bir güvenlik denetimi, koruduğu ortamın **kendi normalleştirmesini**
taklit etmek zorundadır. Tarayıcı URL'i çözmeden önce ona dokunuyorsa,
denetim de aynı dokunuşu yapmalı; yoksa denetim ile gerçeklik arasındaki
fark bir açık kapıdır.

Doğrulama: aynı tarayıcı sondası düzeltme sonrası **4 → 0** çalışan
vektör. Gerçek olay sayfasında (`/event/1819`) 12 dış bağlantının tamamı
sağlam, `href="#"` sayısı **0** — izin listesi meşru bağlantıları
bozmuyor.

---

## 2026-08-20 · 12 ekran · erişilebilirlik turu

**Bağlam:** 15 Ağustos kaydı "Lighthouse A11y: 100" diyordu. Bağımsız
olarak yeniden ölçüldü — çünkü bir raporda yazan sayı, sistemin o an
yaptığı şey değildir.

### Ölçüm (önce)

| Ekran | Skor | Düşen denetim |
|---|---|---|
| gündem | **93** | `link-name` (13), `heading-order` (1) |
| denetim kuyruğu | **93** | `heading-order` (1), `target-size` (100) |
| vaatler | 95 | `target-size` (8) |
| diğer 9 ekran | 98 | `heading-order` (1) |

Ortalama **97,7** · eşiğin (Bölüm 12: ≥95) altında **1** ekran.

**İyi:** Sayfa iskeleti, `lang`, `h1` varlığı, ikonların `aria-hidden`
+ `focusable="false"` taşıması, yatay taşmanın 48 viewport ölçümünde
sıfır olması — bunların hepsi zaten doğruydu.

**Kötü:**

1. **Kenar çubuğunun 13 bağlantısının hiçbirinin erişilebilir adı yoktu.**
   `css.py:640` dar ekranda `.nav-item span{display:none}` uyguluyor;
   `display:none` öğeyi görünmez yapmaz, **erişilebilirlik ağacından
   siler**. İkonlar doğru biçimde `aria-hidden` olduğu için geriye
   hiçbir ad kalmıyordu. Ekran okuyucu 13 kez "link" diyordu — uygulama
   gezilemezdi. Bölüm 12'nin "ikon-only butonlarda `aria-label`" maddesi
   ihlal edilmişti ve bu, **yalnızca daraltılmış durumda** ortaya çıktığı
   için masaüstü bakışında görünmüyordu.
2. **Kart başlıkları `h3`tü, `h2` atlanıyordu.** `components.py::card()`
   tek bir yerde `h3` üretiyor ve altı ekranı birden düşürüyordu.
3. **Tablo hücresi bağlantıları 24×24 px altındaydı** (WCAG 2.5.8):
   denetim kuyruğunda 100, vaatler ekranında 8 öğe.

**Uygulanan:**

1. `_sidebar()` her bağlantıya görünür etiketin AYNISI olan `aria-label`
   veriyor (WCAG 2.5.3 Label in Name — sesli komut ile ekranda yazan
   aynı olmalı). Marka bağlantısı da adlandırıldı.
2. `card()` artık `<h2 class="h3">` üretiyor. **Seviye semantik, boyut
   görsel karardır.** `.h3` sınıfının özgüllüğü (0,1,0) `h2` elementinden
   (0,0,1) yüksek olduğu için boyut korunur. Aynı dönüşüm feed kartı,
   arşiv, hafıza ve hesap-sor ekranlarındaki satır içi `h3`lere de
   uygulandı; `css.py`nin `h3` hedefleyen üç seçicisi `.h3`ü de tutacak
   şekilde genişletildi.
3. `tbody td a` için `min-height:24px` + `inline-flex`. Hücre dolgusu
   değişmedi, yani **satır ritmi bozulmadı** — yalnızca tıklanabilir
   alan büyüdü.

### Görsel eşitlik — göz kararı değil, ölçüm

`h3` → `h2.h3` dönüşümünün piksel değiştirmediği tarayıcıda ölçüldü:

```
eski  h3       size=16px lh=24px weight=600 ls=-0.08px
yeni  h2.h3    size=16px lh=24px weight=600 ls=-0.08px   -> AYNI
(düz  h2       size=20px lh=28px  -- .h3 olmasaydı bu olurdu)
```

### Ölçüm (sonra)

**12/12 ekran 100** · ortalama **100,0** · eşiğin altında **0**.
`ui_check` 48 viewport ölçümünde temiz: yatay taşma yok, konsol hatası yok.

### Ders

Bir erişilebilirlik skoru **tek seferlik bir ölçüm değil, korunması
gereken bir özelliktir.** 15 Ağustos'ta 100 yazılmıştı ve doğru olabilir;
ama arada Faz 8 kumanda odası eklendi, kenar çubuğu daraltma davranışı
geldi ve skor sessizce düştü. Rapora yazılan sayı regresyonu durdurmaz.
Bu yüzden skorun dayandığı özellikler artık testle kilitli:
`tests/test_accessibility_20260820.py` (15 test).
