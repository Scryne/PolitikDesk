# ADR-011: CSP `script-src` — `unsafe-inline` Kaldırıldı, İstek Başına Nonce

**Durum:** Kabul Edildi (Accepted) — Faz 7 CLOSED
**Tarih:** 19 Ağustos 2026
**İlgili:** Roadmap Faz 7, `web/ui/nonce.py`, `web/ui/shell.py`,
`web/ui/components.py`, `api/main.py`, `tests/test_csp_nonce.py`

---

## 1. Bulgu

Depoda bir CSP başlığı vardı ve `default-src 'self'`, `object-src 'none'`,
`connect-src 'self'` gibi gerçekten değerli direktifler taşıyordu. Ama
`script-src` şöyleydi:

```
script-src 'self' 'unsafe-inline'
```

**Bu, CSP'nin XSS'e karşı koruyan tek direktifini pratikte etkisiz
kılıyordu.** Gerekçe şuydu: arayüz sunucu tarafında üretiliyor ve davranış
satır içi `<script>` bloklarına gömülü (Ek A'nın uygulama katmanı kararı).

Gerekçe doğruydu ama sonucu şuydu: enjekte edilen bir `<script>` bloğu da
tam olarak "satır içi script"tir. Tarayıcı, sunucunun yazdığı satır içi
betikle saldırganın enjekte ettiğini **ayırt edemez**. `'unsafe-inline'`
varken CSP her ikisine de aynı cevabı verir: çalıştır.

Ölçülen yüzey:

| Ölçüm | Faz 7 öncesi |
|---|---|
| `script-src` | `'self' 'unsafe-inline'` |
| Satır içi `<script>` bloğu | 2 (ikisi de `shell.py::page()` içinde) |
| Satır içi olay işleyicisi (`onclick=` vb.) | **50** (12 dosya) |
| `javascript:void(0)` bağlantısı | 14 |
| Harici `.js` dosyası | 0 |

---

## 2. Karar

`script-src`'den `'unsafe-inline'` kaldırıldı; yerine **istek başına
üretilen nonce** kondu:

```
script-src 'self' 'nonce-<REQUEST_NONCE>'
```

Diğer direktiflerin hiçbirine dokunulmadı.

### 2.1 Nonce nasıl taşınıyor — ContextVar

Nonce'u `_SecurityHeadersMiddleware` üretir (yığının **en dışındaki**
middleware; en son `add_middleware` edilen en dışta koşar) ve `call_next`
çağrılmadan **önce** bir `ContextVar`'a yazar. `shell.page()` onu oradan
okur.

**Neden parametre değil:** `page()` depodaki her sayfayı üretir ve saf bir
fonksiyondur — `Request` görmez. Nonce'u parametre yapmak 30'dan fazla çağrı
yerini ve aradaki her yardımcıyı değiştirmeyi gerektirirdi. Daha kötüsü: bir
tanesi unutulduğunda arıza **sessiz** olurdu — betik nonce'suz basılır,
tarayıcı bloklar, sunucuda hiçbir iz kalmaz.

**Neden global değil:** `ContextVar` global bir değişken değildir; asyncio
her görev için bağlamın kendi kopyasını taşır. Eşzamanlı istekler birbirinin
değerini göremez. Middleware `finally` bloğunda `reset()` eder, böylece bir
isteğin nonce'u havuzdaki sonraki işe sızmaz.

Bu davranış **varsayılmadı, ölçüldü**: Starlette 1.6.0'da middleware içinde
set edilen ContextVar'ın rota işleyicisine ulaştığı ayrı bir deneyle
doğrulandı; ayrıca 12 paralel istekle 60/60 benzersiz nonce ölçüldü.

### 2.2 Satır içi olay işleyicileri — delegasyon dağıtıcısı

**Nonce, `onclick=` özniteliklerini KURTARMAZ.** Nonce yalnızca `<script>`
etiketine uygulanır; `'unsafe-inline'` kalktığı an satır içi öznitelik
işleyicileri tarayıcı tarafından çalıştırılmaz. Bu yüzden 50'sinin de
taşınması zorunluydu — isteğe bağlı bir temizlik değil.

Yerine `shell.py`'de `document` seviyesinde tek bir delegasyon dağıtıcısı
kondu:

```html
<button data-pd-click="quick-draft" data-pd-args="[123,&quot;inform&quot;]">
```

**Neden delegasyon, neden öğe başına `addEventListener` değil:**
`feed.py::pdRefresh` canlı yenilemede `box.innerHTML = await r.text()` ile
kart listesinin tamamını değiştirir. Yükleme anında tek tek bağlanan
dinleyiciler o noktada kaybolurdu ve yenilemeden sonra hiçbir kart düğmesi
çalışmazdı. `document` üzerindeki tek dinleyici DOM değişse de ayakta kalır.
Bu, ölçülen bir kısıttır: yenileme sonrası 151/151 düğmenin canlı kaldığı
ayrıca doğrulandı.

**Neden açık allowlist, neden `window[isim]` değil:** Eylem adını `window`
üzerinde çözmek gerçek bir CSP bypass'ı açardı — `data-pd-click="eval"` +
`data-pd-args='["...kod..."]'` yazabilen bir enjeksiyon, dağıtıcıyı kendi
kodunu çalıştıran bir gadget'a çevirirdi. `window.pdActions` prototipsiz
(`Object.create(null)`) bir kayıt defteridir; yalnızca `pdAction()` ile
açıkça kaydedilmiş adlar çağrılabilir. Argümanlar `JSON.parse` ile **veri**
olarak ayrıştırılır, hiçbir noktada `eval` edilmez.

### 2.3 Argüman sözleşmesi — 50 fonksiyon gövdesi neden değişmedi

```
fn.apply(öğe, [...data-pd-args] + [öğe, olay])
```

Veri argümanları önce, sonra öğe, en sonda olay. Bu sıra bilinçli seçildi:
eski `onclick="pdFilterAcc('all', this)"` çağrısı `('all', öğe, olay)` olur
ve `function(filterKey, btn)` imzası **hiç değişmeden** doğru argümanları
alır. Fazla argüman JavaScript'te yok sayılır.

Sonuç: 50 işleyici taşınırken tek bir fonksiyon gövdesi yeniden yazılmadı;
regresyon yüzeyi işaretlemeyle sınırlı kaldı. Tek istisna beş arama
kutusudur (`oninput="pdSearch(this.value)"`): onlar artık öğeyi alıp
`el.value` okur — çünkü `input` olayında ilk argüman veri değil öğedir.

### 2.4 `javascript:void(0)` bağlantıları → `<button>`

14 filtre sekmesi hiçbir yere gitmeyen sözde-URL taşıyan `<a>` etiketleriydi.
O şema da `script-src` tarafından reddedilir. Ayrıca semantik zaten yanlıştı:
ekran okuyucu "bağlantı" diyordu. Hepsi `<button type="button">` oldu; görünüm
birebir korunsun diye `css.py`'deki `.segment a` kuralları `.segment a,
.segment button` olarak genişletildi ve buton varsayılanları sıfırlandı.
Klavye erişilebilirliği (Enter ile tetikleme) tarayıcıda doğrulandı.

---

## 3. Bilinen sınırlamalar

### 3.1 `style-src 'unsafe-inline'` duruyor — kasıtlı

Faz 7 kapsamı dışıdır. Depo boyunca yüzlerce `style="..."` **özniteliği**
var ve **nonce öznitelik stillerini kapsamaz** — onlar için `'unsafe-hashes'`
gerekirdi ki bu ayrı ve daha büyük bir iştir. Stil enjeksiyonu script
yürütmez; risk sınıfı farklıdır. Gelecekte kapatılacaksa ayrı bir faz ister.

### 3.2 Tarayıcı nonce'u DOM'da gizler (nonce hiding)

`script.getAttribute('nonce')` tarayıcıda **boş döner**; gerçek değer
yalnızca `.nonce` IDL özelliğinde okunabilir. Bu bir arıza değil, CSP'nin
kendi güvenlik özelliğidir: nonce'un `script[nonce^="a"]` gibi CSS
seçicileriyle sızdırılmasını engeller.

Bu, Faz 7 doğrulamasında bir kez yanlış alarma yol açtı — nonce'lar
`getAttribute` ile aranınca 12 sayfanın hepsi "nonce'suz betik" bildirdi.
Ölçüm aracı düzeltildi. **Bu davranışı bilmeyen bir sonraki denetim aynı
yanlış alarmı üretecektir.**

### 3.3 Erişilebilirlik bulgusu — Faz 7 dışı, açık

`pd ui-check`, `/feed`'de ikon-only bir butonda `aria-label`/`title`
eksikliği bildiriyor (kısayol penceresinin kapatma düğmesi). Bu bulgu
**Faz 7 öncesinde de aynen vardı** — eski konteyner kodunda ölçülerek
doğrulandı. Faz 7 regresyonu değildir ve kapsam dışı olduğu için
düzeltilmemiştir. Düzeltmesi tek satırdır: `feed.py`'deki kapatma
düğmesine `title="Kapat"` eklemek.

---

## 4. Güvenlik invariantları (testle kilitli)

`tests/test_csp_nonce.py` — 64 test:

1. Her HTML isteği yeni nonce alır (12/12 benzersiz).
2. Aynı yanıtın CSP başlığı ile HTML script nonce'u aynıdır (12 ekran).
3. İki farklı istek aynı nonce'u kullanmaz; biri diğerinde geçersizdir.
4. Nonce HTTP bağlamı dışında üretilmez (`current_nonce() == ""`).
5. Nonce loglara girmez.
6. Nonce kullanıcı girdisinden türetilmez (aynı sorgu → farklı nonce).
7. Nonce'suz çalışan satır içi betik yoktur (12 ekran).
8. `unsafe-inline` ve `unsafe-eval` `script-src`'de bulunmaz.
9. Diğer 9 CSP direktifi değişmemiştir.
10. Üretilen HTML'de satır içi olay işleyicisi ve `javascript:` URL'i yoktur.
11. Dağıtıcı yalnızca kayıtlı eylemleri çağırır; `eval`/`new Function` yok.
12. İşaretlemedeki her eylem adının bir `pdAction()` kaydı vardır.

### Yüzey kapısı neden HTML üzerinden ölçülüyor

Kaynak kodu taramak **yanlış alarm üretir**: yorumlar, docstring'ler ve
`ingestion/adapters/sayistay.py`'deki *ayrıştırıcı* regex'i (dış siteden
`onclick` OKUR, üretmez) hepsi eşleşirdi. Önceki fazlarda yaşanan "hep açık
alarm" probleminin kaynağı tam olarak budur.

Üretilen HTML'i taramak bu sınıfı tamamen ortadan kaldırır: bir yorum sayfaya
basılmıyorsa zaten önemsizdir, basılıyorsa gerçekten oradadır. Ölçtüğümüz şey
tarayıcının gördüğü şeydir.

Kapı üç gerçek ihlalle sınandı (geri eklenen `onclick`, `script-src`'ye
konan `unsafe-inline`, nonce'suz `<script>`); üçünde de kırmızıya döndü,
ihlaller geri alınınca yeşile döndü.

---

## 5. Tarayıcı seviyesinde doğrulama

Gerçek Chromium, CSP'yi zorlayarak (konteyner üzerinde):

- 12 ekran: 0 CSP ihlali, 0 konsol hatası, 0 satır içi işleyici.
- Olay ve taslak sayfaları: 0 ihlal.
- **Saldırgan gözü:** nonce'suz enjekte betik → engellendi. Yanlış nonce'lu
  → engellendi. **Başka bir isteğin geçerli nonce'u** → engellendi.
- Etkileşim regresyonu yok: filtreler, arama, kısayol penceresi (iç tıklama
  kapatmıyor, arka plan kapatıyor), kompakt görünüm, tema anahtarı, komuta
  paleti (Ctrl+K), klavye ile filtre (Enter).
- Canlı yenileme sonrası 151/151 düğme çalışır durumda.

---

## 6. Performans

Ölçüldü (tahmin edilmedi):

| Ölçüm | Değer |
|---|---|
| Nonce üretimi (`token_urlsafe(32)`) | 0.483 µs/çağrı |
| ContextVar set + oku + reset | 0.185 µs/çağrı |
| **İstek başına toplam ek maliyet** | **0.669 µs** |
| Bellek | ~93 bayt/nonce, istek sonunda serbest |
| Eşzamanlılık (12 paralel × 60 istek) | 60/60 benzersiz nonce, çakışma yok |

Uçtan uca (konteyner, `127.0.0.1`):

| Uç | medyan | p95 |
|---|---:|---:|
| `/health/live` | 2.8 ms | 25.4 ms |
| `/feed` | 24.3 ms | 39.5 ms |

Nonce'un payı 0.669 µs, yani `/feed` medyanının **%0.003'ü**. Ölçülebilir bir
gecikme regresyonu yoktur.

> **Ölçüm tuzağı — bu makinede `localhost` kullanmayın.** İlk ölçüm turunda
> her uç ~2050 ms çıktı; `/health/live` gibi hiçbir iş yapmayan bir ucun da
> aynı sabit süreyi vermesi ölçümün kendisinden şüphelendirdi. Sebep sunucu
> değil, istemci tarafındaki ad çözümlemesiydi: bu Windows makinesinde
> `localhost` önce IPv6 (`::1`) denenip zaman aşımına uğradıktan sonra
> IPv4'e düşüyor ve her isteğe ~2 saniye sabit gecikme ekliyor. `127.0.0.1`
> ile aynı uç 2.8 ms. Sonraki ölçümler `127.0.0.1` kullanmalıdır.

---

## 7. Bu kararın geri alınma koşulu

`script-src`'ye `'unsafe-inline'` geri eklenirse Faz 7'nin tüm kazanımı
kaybolur — üstelik **sessizce**, çünkü sayfa çalışmaya devam eder. Aynı şey
tek bir `onclick=` için de geçerlidir: düğme tarayıcıda ölür, sunucuda hiçbir
iz kalmaz.

`tests/test_csp_nonce.py` bu iki durumu da kırmızıya çevirir ve `pd ci`'nin
parçasıdır. Kapıyı gevşetmek Spec'te sürüm artışı gerektirir.
