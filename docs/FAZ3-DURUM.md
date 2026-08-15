# Faz 3 — Durum Panosu

**Faz:** Editoryal Katman ve Arayüz · **Plan:** W13–W17 · 25 PD
**Son güncelleme:** 13 Ağustos 2026

> **Fazın amacı:** Faz 2'nin ürettiği zekâyı kullanıcıya sunmak ve Core
> Loop'u DRAFT + REVIEW adımlarıyla kapatmak. Bu fazın sonunda ürün uçtan
> uca çalışır.

---

## Özet

**21 görevin 21'i kodlandı.** Uçtan uca akış canlı veritabanında
doğrulandı: feed → olay → taslak → pre-publish check → panoya kopyala.

Kapı G3'ün 9 koşulundan **6'sı sağlandı**, 1'i kısmi, 2'si **örneklem
hacmi bekliyor** — Faz 2'nin F2-20'siyle aynı blokaj: ingestion'ın
haftalarca birikmesi gerekiyor.

Fazın en önemli çıktısı yine kod değil **ölçüm**: üretim modeli
kıyaslaması (B-71) grounding doğrulayıcısında gerçek bir yanlış pozitif
ve Golden Set'te bir fikstür kirliliği ortaya çıkardı.

---

## Görev durumu

### İş Kolu A — Çekirdek Arayüz

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F3-01 | Frontend iskeleti | ✅ | `web/layout.py` — **Next.js değil, sunucu tarafı HTML** (İtiraz-8) |
| F3-02 | Live Feed | ✅ | `web/feed.py` — salience sıralı, 30 sn sessiz yenileme |
| F3-03 | Olay Sayfası | ✅ | `web/event.py` — Spec §14.3'ün her bölümü |
| F3-04 | "Neden bu durum?" | ✅ | `evidence/explain.py` — kural adı + girdiler görünüyor |
| F3-05 | Kaynak karşılaştırma + framing | ✅ | Siyasi etiket yok — `tests/test_web.py` tarıyor |
| F3-06 | Zaman çizelgesi | ✅ | Tek sorgu, N+1 yok |
| F3-07 | Salience şeffaflık popover'ı | ✅ | Bileşen + ceza kırılımı; "doğruluk skoru değildir" notu |

### İş Kolu B — Editoryal Üretim

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F3-08 | Editoryal Kimlik Kartı (10 soru) | ✅ | `editorial/profile.py` + `/onboarding/profile` |
| F3-09 | Profil → sistem promptu derleyicisi | ✅ | `editorial/profile_compiler.py` — beyaz listeli |
| F3-10 | Taslak üretimi — 3 açı | ✅ | `editorial/generator.py` + `prompts/draft.v1.md` |
| F3-11 | P1 zorlaması | ✅ | `editorial/guards.py` — **409, kapı LLM çağrısından önce** |
| F3-12 | Grounding doğrulayıcısı | ✅ | `editorial/grounding_check.py` — 19 test |
| F3-13 | Pre-publish Check | ✅ | `editorial/checker.py` — 6 kontrol + engelleyici durum |
| F3-14 | Taslak düzenleme + aksiyon kaydı | ✅ | `edit_distance` canlı ölçüldü: 0,686 |
| F3-15 | Yayın köprüsü | ✅ | Pano + X Web Intent · **otomatik gönderim kod yolu yok** |

### İş Kolu C — Brifingler

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F3-16 | Brifing üretici | ✅ | `briefing/generator.py` — **deterministik, LLM yok** |
| F3-17 | E-posta + uygulama içi sayfa | ✅ | `briefing/mailer.py` + `/briefing/{tarih}` + izleme pikseli |
| F3-18 | "Sen yokken ne oldu" | ✅ | Feed üstünde şerit; `users.last_seen_at` |

### İş Kolu D — Ölçüm Altyapısı

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F3-19 | Ürün metrik toplama | ✅ | `metrics.py` — 8 metriğin tamamı; 7'si canlı veriyle doğrulandı |
| F3-20 | Metrik panosu | ✅ | `/admin/metrics` — **Metabase/Grafana değil** (gerekçe aşağıda) |
| F3-21 | "Bu yanlış" geri bildirim | ✅ | `event_feedback` + `needs_review` kuyruğu; canlı denendi |

---

## Kapı G3 — ölçülen durum

| # | Koşul | Hedef | Ölçülen | Durum |
|---|---|---|---|---|
| 1 | Uçtan uca akış | Kesintisiz | feed → olay → taslak → kontrol → kopyala **çalıştı** | ✅ |
| 2 | Taslakta kanıtta olmayan sayı/tarih | **%0** | Üretimde **0/2**; kıyaslamada 21 taslakta 1 gerçek ihlal | 🟡 **örneklem 2/50** |
| 3 | Pre-publish yanlış-negatifi | ≤ %5 | — | 🔴 **40 taslaklık test yapılamadı** |
| 4 | Kanıtsız olayda üretim | Engelleniyor | API **409**, UI butonu devre dışı | ✅ |
| 5 | Brifing 7 gün üst üste | Log kontrolü | 1 gün (2 brifing) | 🔴 **takvim** |
| 6 | 8 ürün metriği akıyor | Panoda görünüyor | **8/8 hesaplanıyor**, 7'sinde canlı veri | ✅ |
| 7 | Olay sayfası yükleme | < 1,5 sn (p95) | **28 ms** (n=20) | ✅ |
| 8 | UI'da siyasi kaynak etiketi yok | Kod incelemesi | **0** — `tests/test_web.py` otomatik tarıyor | ✅ |
| 9 | Otomatik yayın kod yolu yok | Kod incelemesi | **0** — depo geneli taranıyor | ✅ |

**Kapı durumu: 🟡 AÇILMADI.** Koşul 2 ve 3 örneklem hacmi, koşul 5
takvim bekliyor. Ayrıntı "Açık kalan üç kalem"de.

> Koşul 8 ve 9 Yol Haritası'nda "kod incelemesi" olarak yazılmıştı.
> İkisi de teste bağlandı: göz denetimi bir kez yapılıp unutulur, tarama
> her koşumda yapılır. Koşul zayıflamadı, sürdürülebilir hâle geldi.

---

## Fazın bulguları

### 1. Kıyaslama, grounding doğrulayıcısında gerçek bir hata yakaladı

Faz 2'de eval koşucusu kanıt motorunda bir hata bulmuştu; Faz 3'te aynısı
üretim kıyaslamasında oldu.

`gpt-oss-120b` taslak gövdesine iddia referansı yazdı:

```
...cari işlemler açığı 4 milyar 918 2 milyon dolar seviyesinde olacak (C1).
```

`grounding_check` bunu **"kanıtta bulunmayan sayı: 1"** diye işaretledi —
`C1` içindeki rakamı sayı sanıyordu. Teşhis yanlıştı: `C1` bir veri
değil, bir tanımlayıcıdır.

Düzeltme: harfe bitişik rakam (`C1`, `BIST100`, `A101`) sayı sayılmaz.
Düzeltmeden sonra o modelin iki "ihlali" de ortadan kalktı (3/3 → %100).

> Bu tam olarak B-71'in var olma sebebidir. Hata birim testlerinde
> görünmüyordu çünkü testler kendi kurdukları senaryoyu doğruluyordu;
> canlı model çıktısı sentetik testin akla getirmediği bir biçim üretti.

### 2. Golden Set'in kanıt metinleri noktalamasız — sayısal grounding orada ölçülemez

`deepseek-v4-flash`'in üç "ihlalinin" üçü de aynı sayıydı: `918,2`.
Kanıt metni şöyleydi:

```
...cari islemler hesabinin 4 milyar 918 2 milyon dolar acik verecegini...
```

Model **doğru okudu** (`918 2` → `918,2`); denetleyici kanıtta iki ayrı
sayı gördü.

Ölçüldü: **43 kanıt metninin 43'ünde de virgül yok.** `evidence[].text`
alanları aksansız ve noktalamasız normalleştirilmiş.

**Denetleyici bunun için gevşetilmedi** — üretimde `evidence.quote_span`
gerçek makale metninden gelir ve `verify_quote` birebir geçtiğini zaten
doğrular. Ama Golden Set'in bu sürümü sayısal grounding ölçümü için
kullanılamaz. Yeni kalem: **B-73**.

### 3. Üretim modeli kararı zayıf çıktı — ölçüm iki adayı ayıramadı

Kirlenmemiş olaylarda dört adayın da grounding'i %100. İlk iki aday
güvenilirlikte de eşit (8/9). Karar ikincil ölçütlere düştü: gecikme
(19 sn vs 42 sn) ve operasyonel teklik (çıkarımla aynı model).

`nvidia/nemotron-3-super-120b-a12b` seçildi ve karar **🟡 zayıf** olarak
işaretlendi. Ayrıntı: `docs/llm-generation-benchmark.md` (D18).

### 4. Brifing LLM kullanmıyor — maliyet modeli bu kalemde fazla tahmin etmişti

`docs/veri-maliyet-modeli.md` brifing başına ~2.500 girdi + 700 çıktı
token varsayıyordu (kullanıcı başına aylık 60 brifing). Uygulamada
gereksiz olduğu görüldü: brifingin her cümlesinin kaynağı zaten
veritabanında **doğrulanmış** hâlde duruyor.

Bir modele yeniden yazdırmanın bedeli üçtü — halüsinasyon riski (günde
iki kez, doğrudan e-postaya), maliyet ve kırılganlık (08:00'de model
düşerse brifing gitmez). Karşılığında kazanılacak tek şey akıcı üsluptu.

**Taslak üretimi yaratıcıdır; brifing bir dizindir.** Gerçekleşen brifing
maliyeti **0 $**. Bir AST testi bu kararı sabitliyor.

### 5. Spec §15 madde 10'un uygulanması bir yorum gerektirdi

*"İsimli kişi hakkında `unverified` iddia varsa taslak üretimi
engellenir"* — harfiyen uygulandığında **her olayı** bloke ediyor.

Sebep R0: tahmin tipindeki her iddia, kanıt yokluğundan değil **tip
kısıtından** `unverified`'dır. "Bakan X enflasyonun düşeceğini öngördü"
cümlesi, hakkında hiçbir isnat bulunmayan bir kişi yüzünden üretimi
durduruyordu.

Uygulanan kural: **tahmin tipi muaf.** Madde 10'un koruduğu şey "belirli
kişilere yönelik SUÇLAMA"dır; bir kişinin kendi tahminini aktarmak
suçlama değildir. Yorum Spec'te harfiyen yazılı olmadığı için **B-72**
olarak açıldı (v3.2'ye işlenmeli).

---

## Tasarım kararları ve gerekçeleri

| Karar | Alternatif | Gerekçe |
|---|---|---|
| Arayüz **sunucu tarafı HTML** | Next.js + Tailwind + shadcn (F3-01) | Magic link/korumalı rota, kapsam dışı bırakılmış çok kullanıcı iş koluna aitti; ayrı araç zinciri G3 #8/#9'u CI dışına taşırdı (İtiraz-8) |
| Metrik panosu **uygulama içi** | Metabase/Grafana konteyneri | Sekiz sayı için ayrı servis; pano tanımı sürüm kontrolü dışında kalırdı. Ham veri `metrics` tablosunda — Grafana istenirse bağlanır |
| Brifing **deterministik** | LLM ile özetleme | Halüsinasyon riski günde iki kez doğrudan e-postaya; kazanç yalnızca üslup |
| TL;DR **iddialardan birleştirilir** | LLM ile özet | Spec §14.3 "yalnızca doğrulanmış unsurlardan kurulur" — prompt talimatına indirgemek kısıtı kaybetmekti |
| Girdi **yalnızca claims+evidence** | Olay başlığını da vermek | Grounding evreni ile modelin gördüğü ayrışırsa doğru taslak haksız yere düşer |
| Grounding'i düşen taslak **kaydedilir** | Silmek | G3 #2 bir ORANDIR; düşenleri silmek paydayı yok eder ve oran her koşulda %0 çıkar |
| `grounding_result` ile `check_result` **ayrı sütun** | Tek JSONB | Sert kapının ölçümü yumuşak kontrollerin gürültüsüne karışırdı |
| Sayı belirsizliğinde **tüm okunuşlar** kabul | Tek yorum | Türkçe sayı yazımı çok biçimli; katı yorum doğru taslakların çoğunu bloke ederdi |
| Tarihte **en yüksek çözünürlük** tutmalı | Küme kesişimi | Kesişim, kanıtta ağustos varken "12 Eylül 2026"yı YIL EŞLEŞTİĞİ İÇİN kabul ediyordu (test edildi) |
| Yorum etiketi **sayıyı mazur göstermez** | İşaretliyse geç | Spec §14.4'ün engelleyici durumu "kanıta bağlanamayan SAYISAL iddia"dır |
| Kapılar **guards.py'de**, API'de değil | Uç noktada kontrol | İkinci bir çağıran (worker, betik) kapıyı sessizce atlardı (F3-11 DoD) |
| Aktivite izi **`sendBeacon`** | `fetch` | Sayfa kapanırken `fetch` gitmez; oturum sonu ölçümü kaybolurdu |
| Brifing belirteci **gövdeden önce** üretilir | INSERT'te üretmek | Piksel adresi HTML'in içinde; belirteci sonra üretmek gövdeyle kaydı ayrıştırırdı |

---

## Canlı doğrulama (13 Ağustos 2026)

Gerçek veritabanında (29 makale, 9 olay) uçtan uca:

```
B-70 yeniden çıkarım : 4 iddia silindi (claims.v1) -> 2 iddia (claims.v2), 0 hata
kanıt motoru         : {'claims_scored': 2, 'events_scored': 9, 'errors': 0}
üretim (Eleştir)     : draft_id=2, grounding temiz, kontrol geçti
düzenleme aksiyonu   : edit_distance = 0,686
brifing              : 6 olay, 2 doğrulanmamış iddia, SMTP yok -> gönderim atlandı
açılma takibi        : piksel çağrıldı -> opened_at yazıldı
geri bildirim        : olay needs_review kuyruğuna düştü
metrik toplama       : 8 metrik, 7'sinde veri
```

**Üretilen taslak (canlı, `nemotron-3-super`):**

> VDK'nin yapay zeka destekli risk analiz sistemi 'MİHENK' devrede ve
> transfer fiyatlandırması, emsallere uygunluk ve kazancın ilişkili
> kişiler arasında fiyatlama yoluyla aktarılmasına yönelik risklerin
> belirlenmesini güçlendirecek şeklinde ifade edildi. **Tek kaynağa göre**
> bu sistemin işlevselliği ve etkileri hakkında daha fazla veri ve
> bağımsız değerlendirme gerekli.

Model, `single_source` iddiayı **çekinceyle** aktardı (Spec §15 madde 3),
yorum cümlesini işaretledi ve kanıtta olmayan hiçbir sayı üretmedi.

### Canlı veride bulunan hatalar

| # | Hata | Belirti | Düzeltme |
|---|---|---|---|
| 1 | **Tarih eşleştirmesi küme kesişimine bakıyordu** | Kanıtta ağustos varken "12 Eylül 2026" geçiyordu (ortak belirteç: "2026") | En yüksek çözünürlük kuralı; `_DateMention.primary` |
| 2 | **Harfe bitişik rakam sayı sanılıyordu** | `(C1)` -> "kanıtta bulunmayan sayı: 1" | Önceki karakter harfse atla (B-71 koşumu) |
| 3 | **Brifing belirteci gövdeden sonra üretiliyordu** | İzleme pikselinin adresi kayıtla ayrışırdı | Belirteç önce çözülür, yeniden üretimde korunur |

---

## Açık kalan üç kalem

### G3 koşul 2 ve 3 — örneklem hacmi (B-57 ile aynı blokaj)

Kapı 50 taslaklık (koşul 2) ve 40 taslaklık (koşul 3) denetim istiyor.
Veritabanında **iddiası olan tek bir olay** var (2 iddia) — çünkü 29
makalelik veritabanında kümeleme sonrası iddia çıkarımı bu kadar veriyor.

Bu, Faz 2'nin F2-20'siyle **aynı** blokajdır: ingestion'ın haftalarca
birikmesi gerekiyor. Kıyaslama koşumu 21 taslak üretti (4 model) ve
üretim kod yolunu kullandı, ama o taslaklar Golden Set fikstürü üzerinde
üretildi (bkz. bulgu 2) ve kapı ölçümü sayılamaz.

**Etkisi:** koşul 2 ve 3 bu boyutta *karara bağlanamaz.* Ölçüm bir
**yön** gösterir, kapı kararı değil.

### G3 koşul 5 — brifing 7 gün üst üste

`beat` zamanlaması kuruldu (08:00 / 20:00, `TZ=Europe/Istanbul`).
**Takvim zamanı gerektirir**; kodla kapatılamaz.

### B-67 — Claude karşılaştırması

`ANTHROPIC_API_KEY` `.env`'de **boş.** İki Claude modeliyle koşum
denendi; 18 çağrının 18'i `LLMNotConfigured` ile düştü. Anahtar
geldiğinde tek komut:

```bash
python -m scripts.generation_benchmark --provider anthropic \
    --models claude-sonnet-5,claude-opus-5 --events 3
```

---

## Kalan iş

| İş | Efor | Durum |
|---|---|---|
| Golden Set'i 300 makaleye çıkar (B-57) | 3–4 PD | 🔴 Ingestion birikimi bekliyor |
| G3 #2/#3 denetimi (50 + 40 taslak) | 1 PD | 🔴 **B-57'ye bağlı** |
| Golden Set kanıt metinlerine noktalama (B-73) | 0,5 PD | 🔴 **Yeni** — sayısal grounding ölçümünü açar |
| B-71'i temiz fikstürle yeniden ölç (B-74) | 0,3 PD | 🔴 **Yeni** — B-73'e bağlı |
| Claude karşılaştırması (B-67) | 0,2 PD | 🔴 Anahtar bekliyor |
| Spec §15 madde 10 muafiyetini Spec'e işle (B-72) | 0,2 PD | 🔴 **Yeni** — v3.2 |
| Brifing 7 gün üst üste (G3 #5) | 7 gün | 🔴 Takvim |
| Haftalık kalite ritüeli (B-59) | 3 hafta | 🔴 Takvim |
| Gösterge ayırıcısı (B-62) | 1,0 PD | 🔴 Faz 2'den devrediyor |
