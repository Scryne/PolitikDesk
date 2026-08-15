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

## Ölçüler

| | |
|---|---|
| Sayfa süresi (G3 #7 hedefi p95 < 1,5 sn) | `/feed` 0,21 sn · `/event/{id}` 0,21 sn |
| Font yükü | 6 woff2, ~195 KB (latin + latin-ext) |
| Stylesheet | tek kaynak, satır içi (~36 KB) |
| Test | 690 geçti · 72'si tasarım sistemi |
| Ekran × viewport denetimi | 7 × 4 = 28, hepsi temiz |
