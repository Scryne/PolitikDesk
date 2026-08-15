# PolitikDesk — Phase 2 Uygulama ve Hardening Planı

## 0. Belgenin Amacı

Bu belge, Phase 1 Codebase Audit sonucunda tespit edilen doğrulanmış bulguların güvenli, kontrollü ve kanıtlanabilir biçimde giderilmesi için **uygulanabilir bir Phase 2 çalışma sözleşmesidir**.

Bu belgeyi uygulayan AI/ajan:

- yalnızca burada açıkça tanımlanan kapsam dahilinde değişiklik yapmalıdır,
- onaylanmamış bulguları düzeltmemelidir,
- varsayım yapmamalıdır,
- mevcut davranışın neden yanlış olduğunu doğrulamadan kod değiştirmemelidir,
- her değişiklikten sonra ilgili testleri ve en sonunda tüm proje gate'lerini çalıştırmalıdır,
- doğrulanmamış bir sonucu "tamamlandı" olarak raporlamamalıdır.

> **TEMEL PRENSİP:** Önce invariant'ı koru → sonra davranışı düzelt → sonra regression test ile kilitle → sonra doğrula.

---

# 1. Phase 1 Baseline

Phase 1 audit sırasında doğrulanan baseline:

```text
ruff check .                    → All checks passed!
mypy                            → Success: no issues found in 108 source files
scripts/check_architecture.py   → [OK]
pytest                          → 648 passed, 54 skipped
```

54 testin skip edilme nedeni:

```text
PD_DATABASE_URL unset
```

DB testleri Phase 2 sırasında mümkün olan en erken noktada gerçek bir test veritabanı ile çalıştırılmalıdır.

## 1.1 Phase 2 başlangıç koşulu

Kod değiştirmeden önce tekrar çalıştır:

```bash
ruff check .
mypy
python scripts/check_architecture.py
pytest
git status
git diff --stat
git diff
```

Baseline değişmişse bunu raporla ve mevcut çalışma ağacındaki değişiklikleri koru.

**Mevcut uncommitted değişiklikleri silme, resetleme, checkout etme veya ezme.**

---

# 2. Hard Rules

## 2.1 Onaysız değişiklik yok

Bu belge Phase 2 uygulama kapsamıdır.

Şunları yapma:

- opportunistic refactor,
- formatting-only değişiklikler,
- dependency upgrade,
- public API değişikliği,
- kapsam dışı bug fix,
- mimari yeniden yazım,
- "madem buradayım" temizliği,
- onaylanmamış improvement'ları defect fix'lerine eklemek.

## 2.2 Minimal correct change

Her bulguda:

1. Mevcut davranışı yeniden üret.
2. Hatanın gerçek nedenini doğrula.
3. En küçük doğru değişikliği yap.
4. Regression test ekle/güncelle.
5. İlgili testleri çalıştır.
6. Full gate çalıştır.
7. Diff'i incele.
8. Sonucu kaydet.

## 2.3 Yanlış teşhis çıkarsa DUR

Fix sırasında:

- Phase 1 teşhisinin yanlış olduğu,
- önerilen çözümün mevcut davranışı bozacağı,
- requirement'ın belirsiz olduğu,
- başka bir modülün incelenmesinin zorunlu olduğu

ortaya çıkarsa doğaçlama yapma.

**DUR, durumu raporla ve karar iste.**

## 2.4 Unreviewed scope

Phase 1 aşağıdaki alanları tam incelememiştir:

```text
clustering/
nlp/embedder
nlp/entities
nlp/search
nlp/claims_pipeline
ingestion/adapters/*
briefing/
admin/
editorial/checker
editorial/generator
editorial/grounding_check
eval/
most of scripts/
```

Bu alanlara yalnızca mevcut bir fix'in dependency trace'i gerçekten gerektiriyorsa targeted review yap.

---

# 3. Priority Model

## P0 — Önce

```text
D8
D7
L1
L3
```

## P1

```text
L2
L4
D12
D9
D10
```

## P2

```text
L5
L6
D13
D14
D15
D17
```

## P3

```text
D11
D16
```

## Improvements — defect fix'lerinden sonra

```text
I1
I2
I3
I4
I5
I6
I7
I8
I9
```

---

# 4. Uygulama Sırası

Aşağıdaki sıra değiştirilmemelidir; ancak bir bulgu için gerçek teknik engel ortaya çıkarsa DUR ve raporla.

```text
PHASE 0
Baseline + DB test environment
        ↓
BATCH A
D8 — stance git/docker boundary
        ↓
BATCH B
D7 — stance DB storage violation
        ↓
BATCH C
L1 — Celery timezone
        ↓
BATCH D
L3 — profile normalization / DB constraint
        ↓
BATCH E
L2 — vertical non-event/context filters
        ↓
BATCH F
L4 — attribution_verified
        ↓
BATCH G
D12 — API-level grounding enforcement
        ↓
BATCH H
D9 + D10 — LLM / HTTP retry discipline
        ↓
BATCH I
L5 — opinion classifier folding
        ↓
BATCH J
L6 — correction metric semantics
        ↓
BATCH K
D13 + D14 + D15
        ↓
BATCH L
D11 — accessibility
        ↓
BATCH M
D17 — compiler persistence
        ↓
BATCH N
D16 — dead feature/backlog reconciliation
        ↓
IMPROVEMENTS
I1–I9
        ↓
PHASE 2 VERIFICATION AUDIT
```

---

# 5. PHASE 0 — Baseline ve DB Test Altyapısı

## Amaç

Phase 2 boyunca gerçek regression evidence üretmek.

## Yapılacaklar

1. Baseline gate'lerini çalıştır.
2. `git status` ve diff'i kaydet.
3. DB testlerinin neden skip edildiğini doğrula.
4. Mevcut proje setup'ını kullanarak DB integration testlerinin çalışabileceği ortamı hazırla.
5. Migration `0009` ve `0010` testlerini çalıştır.
6. Test altyapısını değiştirirken production koduna gereksiz değişiklik yapma.

## Kabul kriteri

- Unit test baseline biliniyor.
- DB testlerinin nasıl çalıştırıldığı biliniyor.
- Migration testleri gerçek DB üzerinde çalıştırılabiliyor veya teknik engel açıkça raporlanıyor.

---

# 6. BATCH A — D8

## D8 — `config/editorial_stance.md` Git/Docker ignore

### Problem

`stance.py` dokümantasyonu gerçek stance dosyasının `.gitignore` içinde olduğunu söylüyor fakat dosya ignore edilmiyor.

Bu dosya kullanıcı siyasi/editoryal duruşu içerebilir.

### Dosyalar

```text
.gitignore
.dockerignore
config/editorial_stance.md
```

### Uygulama

`.gitignore` içine:

```text
config/editorial_stance.md
```

ekle.

`.dockerignore` içine de aynı path'i ekle.

### Test

Aşağıdaki invariant'ı test et:

```text
config/editorial_stance.md MUST be ignored by git.
```

Mevcut dosya tracked ise ayrıca bunu raporla; sessizce history manipülasyonu yapma.

### Kabul kriterleri

- `git check-ignore -v config/editorial_stance.md` başarılı.
- `.dockerignore` dosyayı dışlıyor.
- Regression test mevcut.
- `git diff` yalnızca D8 kapsamını içeriyor.

### Risk

Düşük.

---

# 7. BATCH B — D7

## D7 — Editorial stance DB'ye yazılmamalı

### Kritik invariant

Şu kesinlikle yasaktır:

```text
user editorial stance
        ↓
editorial_profiles.compiled_prompt
        ↓
database
```

Stance yalnızca generation-time composition sırasında kullanılmalıdır.

### Mevcut problem

Mevcut akış:

```text
config/editorial_stance.md
        ↓
stance.py
        ↓
compile_profile()
        ↓
compiled_prompt
        ↓
editorial_profiles
```

### Hedef akış

```text
stored profile
        +
runtime editorial stance
        ↓
generation prompt
```

Stance DB'ye yazılmamalıdır.

---

## D7.1 `compile_profile()`

`compile_profile()` yalnızca storage'a izin verilen profile alanlarını derlemelidir.

Stance block'u `compile_profile()` çıktısından çıkar.

---

## D7.2 Generation-time composition

`editorial/service.py` içinde stance'ı generation sırasında ekle.

Mantık:

```text
compiled_prompt_for(user_id)
+
runtime stance
=
LLM generation prompt
```

Bu composition DB'ye geri yazılmamalıdır.

---

## D7.3 Live stance semantics

Aşağıdaki regression mutlaka yazılmalıdır:

1. Profile DB'ye kaydedilir.
2. Stance dosyası A içerir.
3. Generation yapılır.
4. Stance A kullanılır.
5. Stance dosyası B olarak değiştirilir.
6. Profile yeniden save edilmeden generation tekrar yapılır.
7. Stance B kullanılmalıdır.

Bu, Phase 1 raporundaki second-order bug'ı kapatır.

---

## D7.4 Preview

Onboarding/profile preview DB'de gerçekten saklanan profile'ı göstermelidir.

Stance'ın storage preview'sinde görünmesi zorunlu değildir; tercihen görünmemelidir.

---

## D7.5 Existing leaked data

Mevcut DB kayıtlarında stance block'u bulunabileceği raporlanmıştır.

Kod fix'i yapmadan önce mevcut formatı doğrula.

Eski kayıtları temizlemek gerekiyorsa:

- önce mevcut formatları tespit et,
- cleanup'ın güvenli olduğunu test et,
- data migration gerekiyorsa migration olarak uygula,
- kör regex ile veri silme yapma.

---

## D7.6 Tests

En az:

### Test A

`compile_profile()` çıktısında stance yok.

### Test B

DB `compiled_prompt` içinde stance yok.

### Test C

Generation request içinde runtime stance var.

### Test D

Stance değişikliği profile re-save gerektirmiyor.

### Test E

CI'da gerçek stance fixture kullanıldığında storage invariant korunuyor.

---

## D7.7 Kabul kriterleri

- Stance DB'ye yazılmıyor.
- Stance generation-time'da kullanılabiliyor.
- Stance değişikliği yeni generation'a hemen yansıyor.
- Existing leaked data stratejisi uygulanmış veya açıkça raporlanmış.
- Regression testleri geçiyor.
- Full gate geçiyor.

---

# 8. BATCH C — L1

## L1 — Celery crontab timezone

### Problem

Mevcut:

```text
worker.py:
timezone = UTC
enable_utc = True
```

OS:

```text
TZ=Europe/Istanbul
```

olmasına rağmen Celery crontab UTC'ye göre çalışıyor.

### Sonuç

Beklenen:

```text
briefing-morning = 08:00 TRT
briefing-evening = 20:00 TRT
metrics-rollup-nightly = 23:50 TRT
llm-budget-check = 07:45 TRT
```

Mevcut davranış UTC'dir.

---

## L1.1 Single source of truth

Celery application timezone'ını application settings üzerinden yönet.

Default:

```text
Europe/Istanbul
```

OS `TZ` ile Celery schedule mantığını birbirine karıştırma.

---

## L1.2 Celery behavior verification

Kullandığın Celery sürümünün:

- `app.conf.timezone`
- `enable_utc`
- `crontab`

davranışını gerçek runtime üzerinde doğrula.

Varsayım yapma.

---

## L1.3 Schedule tests

Aşağıdaki schedule değerlerini test et:

```text
briefing-morning → 08:00
briefing-evening → 20:00
metrics-rollup-nightly → 23:50
llm-budget-check → 07:45
```

Test yalnızca task'ın schedule'da bulunmasını değil, saat ve timezone davranışını da doğrulamalıdır.

---

## L1.4 Date semantics

`metrics.py:404` içindeki `date.today()` davranışını local application date ile karşılaştır.

Özellikle:

```text
23:50 Europe/Istanbul
```

çalışan nightly task'ın doğru local günü yazdığını integration test ile kanıtla.

---

## L1.5 Beat state

Deploy sırasında persist edilen:

```text
celerybeat-schedule
```

state'inin timezone değişikliğinden etkilenip etkilenmediğini doğrula.

Gerekiyorsa deployment procedure'a schedule state reset'i ekle.

---

## Kabul kriterleri

- Celery logical timezone `Europe/Istanbul`.
- Morning briefing 08:00 local.
- Evening briefing 20:00 local.
- Nightly rollup doğru local date'i kullanıyor.
- Relevant schedule tests mevcut.
- Full gate geçiyor.

---

# 9. BATCH D — L3

## L3 — Profile normalization DB CHECK violation

### Problem

Şu branch:

```python
if hashtag is None and emoji is not None:
    hashtag = "rare" if emoji == "rare" or emoji == "minimal" else emoji
```

`emoji_usage="necessary"` durumunda:

```text
hashtag_usage="necessary"
```

üretiyor.

Fakat DB yalnızca:

```text
none
rare
minimal
topic_bound
frequent
```

kabul ediyor.

Sonuç HTTP 500.

---

## Karar

Bu planın önerdiği çözüm:

> **Derived hashtag value üretme branch'ini kaldır.**

Gerekçe:

- emoji tercihi ile hashtag tercihi ayrı kavramlardır,
- kullanıcı hashtag tercihi vermediyse `None` kalması daha doğru,
- proje kodundaki "kullanıcının cevabını sessizce değiştirme" ilkesi korunur.

Bu kararın eski payload compatibility etkisi varsa önce mevcut test/fixture geçmişini incele.

---

## L3.1 Normalization test matrix

En az:

```text
emoji=None,      hashtag=None       → None
emoji=necessary, hashtag=None       → None
emoji=frequent,  hashtag=None       → None
emoji=rare,      hashtag=None       → None
emoji=None,      hashtag=frequent   → frequent
invalid hashtag                         → ValueError
emoji=necessary, hashtag=rare       → rare
```

---

## L3.2 DB integration

Şu gerçek akışı test et:

```text
normalize_answers()
    ↓
compile_and_store()
    ↓
DB INSERT
    ↓
COMMIT
```

`PD_DATABASE_URL` ile gerçek schema constraint'i çalıştır.

---

## Kabul kriterleri

- Normal onboarding formu HTTP 500 üretmiyor.
- `emoji_usage=necessary`, `hashtag_usage` verilmediğinde DB constraint ihlal edilmiyor.
- Invalid values hâlâ reddediliyor.
- DB integration test mevcut.
- Full gate geçiyor.

---

# 10. BATCH E — L2

## L2 — Vertical non-event/context filters

### Problem

`VerticalSpec`:

```text
non_event_patterns
required_context_keywords
```

alanlarını tanımlıyor fakat `classify()` bunları kullanmıyor.

Legislation vertical'ında non-event içerikler pipeline'a girebiliyor.

---

## L2.1 Önce semantic contract

Filtre sırası açıkça tanımlanmalı:

```text
resolve vertical
    ↓
topic matching
    ↓
non-event filtering
    ↓
context filtering
    ↓
final classification
```

---

## L2.2 Generic mechanism

`VerticalSpec` alanlarının gerçekten generic olarak okunmasını sağla.

Macro economy'ye özel mevcut mekanizma ile vertical-specific mekanizmayı iki ayrı sistem halinde bırakma.

---

## L2.3 Legislation testleri

Testler önce topic match üretmeli, sonra non-event filtresinin çalıştığını kanıtlamalı.

Örnek:

```text
"Günün köşe yazıları: TBMM'de torba kanun"
→ topic match exists
→ non-event match
→ rejected
```

```text
"Son anket: Seçim kanunu değişikliğine destek"
→ topic match exists
→ non-event match
→ rejected
```

```text
"Burç yorumları: Meclis gündemi ne diyor"
→ topic match exists
→ non-event match
→ rejected
```

---

## L2.4 Positive recall tests

Filtre aşırı agresif olmamalı.

Örnek pozitifler:

```text
"TBMM'de yeni kanun teklifi"
→ yasama_sureci

"Meclis'te torba kanun görüşmeleri"
→ yasama_sureci
```

---

## L2.5 Context filter

`required_context_keywords` için ayrı pozitif/negatif testler yaz.

Non-event ve context kararlarını aynı assertion ile karıştırma.

---

## Kabul kriterleri

- Vertical-specific non-event patterns gerçekten uygulanıyor.
- Required context gerçekten uygulanıyor.
- Vacuous testler kaldırılıyor/değiştiriliyor.
- Positive recall testleri mevcut.
- Full gate geçiyor.

---

# 11. BATCH F — L4

## L4 — `attribution_verified` UI/evidence status

### Problem

R8 engine/schema'da var ancak UI token/label/title/explanation/sort katmanlarında eksik.

Sonuç:

```text
raw slug: attribution_verified
unverified styling
Bilinmeyen kural
wrong ordering
```

---

## L4.1 Exhaustive status search

Kod tabanında tüm evidence status switch noktalarını bul:

```text
EvidenceStatus
evidence_status
STATUS_TOKEN
STATUS_LABELS
STATUS_TITLES
RULE_TITLES
_STATUS_RANK
status_badge
```

Ayrıca:

```text
if status == ...
match status
CASE ...
```

pattern'lerini ara.

Özellikle Phase 1'de tam incelenmemiş alanları targeted review ile kontrol et.

---

## L4.2 UI contract

`attribution_verified` için eksiksiz:

```text
status token
status label
status title
rule title R8
icon
color
sort rank
explanation sentence
```

tanımla.

Önerilen Türkçe label:

```text
beyan sabit
```

Ancak mevcut ürün terminolojisiyle uyumlu olduğundan emin ol.

---

## L4.3 Design token

Yeni token/icon eklenirse:

- contrast,
- TEXT_PAIRS,
- icon registration,
- icon usage

testlerini güncelle.

---

## L4.4 Explanation

R8 için `explain()`:

- rule title göstermeli,
- inputs görünür olmalı,
- generic "Bilinmeyen kural" fallback'e düşmemeli.

---

## Kabul kriterleri

`attribution_verified` UI'da:

- Türkçe label,
- verified/positive token,
- doğru icon,
- doğru explanation,
- doğru ordering

ile görünmeli.

---

# 12. BATCH G — D12

## D12 — Publish/accept grounding gate

### Problem

Grounding yalnızca UI'daki disabled button ile korunuyor.

API/service doğrudan çağrıldığında invariant korunmuyor.

---

## Hedef

```text
UI gate
+
Service/API gate
```

---

## D12.1 Service

`publish_payload()` ve state-changing action path'lerinde `is_grounded` kontrolü yap.

Ungrounded durumda typed error üret.

---

## D12.2 API

Typed error'ı uygun HTTP status'a map et.

Önerilen:

```text
409 Conflict
```

Mevcut `GenerationBlocked` pattern'i ile tutarlı ol.

---

## D12.3 Tests

En az:

```text
ungrounded publish → 409
ungrounded accept → 409
grounded publish → success
grounded accept → success
```

UI disabled attribute testinin yanında doğrudan API/service testi bulunmalıdır.

---

## Kabul kriterleri

API doğrudan çağrılsa bile grounding invariant'ı korunuyor.

---

# 13. BATCH H — D9 + D10

# D9 — Anthropic timeout/retry configuration

### Problem

`llm_timeout_seconds` ve `llm_max_retries` default Anthropic backend'de kullanılmıyor.

### Önce

Anthropic SDK sürümünün gerçek constructor/API davranışını doğrula.

### Uygulama

Default backend config'i gerçekten SDK'ya aktar.

Ancak timeout default'unu körlemesine değiştirme.

Önce generation latency ölç:

```text
p50
p95
p99
```

Eğer mevcut default güvenli değilse bunu ayrıca raporla.

### Test

Config değiştirildiğinde backend'in gerçek client constructor'ına doğru değerlerin geçtiğini test et.

---

# D10 — Retry rate limiter

### Problem

Rate limiter yalnızca retry loop'un başında acquire ediliyor.

Sonuç:

```text
1 limiter slot
→ 4 HTTP request
```

olabiliyor.

### Hedef

Her gerçek HTTP attempt öncesi:

```text
acquire(host)
→ request
```

çalışmalı.

### Test

`max_retries=4` için limiter acquisition sayısını doğrula.

429 senaryosunu test et.

### Kabul kriterleri

Retry'lar rate limit budget'ını bypass etmiyor.

---

# 14. BATCH I — L5

## L5 — Opinion classifier keyword folding

### Problem

`fold_text()` Türkçe diacritics'i normalize ediyor fakat keyword literal'ları aynı dönüşümden geçirilmediği için bazı keyword'ler asla eşleşmiyor.

### Uygulama

Keyword tablolarını import sırasında fold et.

```text
raw keyword
→ fold_text(keyword)
→ runtime comparison
```

ASCII duplicate'larını gereksiz hale getiriyorsa kaldır.

### Test

Türkçe örnekler:

```text
Köşe Yazısı
Köşe Yazarları
Günün Yazısı
Başyazı
Başkent Kulisi
Gözlem
Değerlendirme
Bana göre
Benim gördüğüm
Şahsen
Köşemde
Düşünüyorum
```

### Önemli sınır

Keyword matching fix'i ile `is_opinion` threshold/policy değişikliğini aynı değişiklikte yapma.

---

# 15. BATCH J — L6

## L6 — Correction rate metric

### Tanım

Spec §13.3'e göre:

```text
correction_rate =
flags / opened events
```

Numerator ve denominator aynı event population'ını kullanmalı.

### Uygulama

1. Window içindeki opened event ID'lerini belirle.
2. Feedback'i bu event ID seti ile sınırla.
3. Ratio'yu hesapla.

### Invariant

```text
0 <= correction_rate <= 1
```

ve yüzde gösteriliyorsa:

```text
0% <= displayed rate <= 100%
```

### Test

- event window dışında açılmış fakat window içinde flag edilmiş event,
- window içinde açılmış ve flag edilmiş event,
- hiç flag olmayan event,
- çoklu feedback.

### Historical semantics

Eski metric rows ile yeni metric definition karışıyorsa önce mevcut history davranışını incele.

Metric versioning gerekiyorsa doğaçlama ekleme; DUR ve raporla.

---

# 16. BATCH K — D13 + D14 + D15

## D13 — `citation_habit="never"`

### Problem

`never`, `inline_short` ile aynı metne silently map ediliyor.

### Uygulama

Tercihen:

```text
never
```

değerini `CITATION_HABITS` içinden kaldır.

Böylece invalid/unsupported değer ValueError üretir.

### Test

```text
citation_habit=never → rejected
```

Mevcut stored profile'lar etkileniyorsa bunu raporla.

---

## D14 — Final retry'da gereksiz sleep

### Problem

Son attempt sonrası da backoff uygulanıyor.

### Uygulama

Son attempt'te:

```text
break / raise
```

öncesinde sleep yapma.

### Test

- final attempt,
- normal retry,
- Retry-After,
- capped Retry-After

senaryoları.

---

## D15 — Accepted record edit distance

### Problem

`accepted + final_body` değişmiş olsa bile:

```text
edit_distance = 0.0
```

kaydediliyor.

### Uygulama

`final_body != body` olduğunda action `accepted` olsa bile gerçek distance hesapla.

### Test

```text
accepted + same body → 0
accepted + changed body → >0
edited + changed body → >0
```

---

# 17. BATCH L — D11

## D11 — Skip link focus visibility

### Problem

`.sr` 1x1 clipped durumda kalıyor.

Focus olduğunda görünür hale gelmeli.

### Uygulama

Skip link için scoped focus style ekle.

Örneğin davranış:

```text
position: fixed
visible dimensions
padding
background
border
z-index
```

Mevcut design tokenlarını kullan.

### Test

Mümkünse Playwright/browser-level:

```text
Tab
→ skip link focused
→ bounding box visible
```

### Kabul kriteri

Keyboard user ilk tab stop'ta skip link'i görür.

---

# 18. BATCH M — D17

## D17 — Stale profile compiler persistence

### Problem

Compiler version mismatch olduğunda profile yeniden derleniyor fakat yeni sonuç DB'ye yazılmıyor.

### Önce araştır

Concurrency:

```text
two simultaneous generations
same profile
compiler version bump
```

senaryosunu değerlendir.

### Uygulama

Eğer güvenliyse:

```text
version mismatch
→ compile
→ persist
→ return
```

yap.

DB write'ın read path'e girmesinin transaction/concurrency etkilerini test et.

### Kabul kriteri

Compiler version bump sonrası profile:

- yeniden compile edilir,
- yeni compiled result persist edilir,
- sonraki generation slow path'e tekrar girmez.

---

# 19. BATCH N — D16

## D16 — Dead/partial features

Şunları incele:

```text
political_memory/
editorial/archive.py
nlp/opinion_classifier.py
```

Her biri için:

```text
caller?
persistence?
tests?
backlog item?
```

matrisi çıkar.

### Karar

Üç olasılık:

1. Gerçekten kullanılacak → staging olduğu açıkça belgelenir.
2. Kullanılmayacak → silinir.
3. Backlog "closed" fakat implementation eksik → backlog reopened.

**Silme kararını varsayma.**

D16 için intent belirsizse DUR ve karar iste.

---

# 20. Improvements — I1–I9

Bunlar defect değildir.

Defect batch'leri tamamlanmadan bunlara geçme.

## I1

`ca_bundle_path` için secure temporary file / `0600`.

## I2

RobotsCache TTL.

## I3

Vertical regex precomputation.

## I4

Election mode registry cleanup.

## I5

Translation aliases cleanup.

## I6

`format.precise()` docstring düzeltmesi.

## I7

LLM budget TOCTOU.

## I8

Architecture script duplicate package output.

## I9

Migration/DB test coverage.

### Improvement kuralı

Bir improvement'ın uygulanması başka bir davranış değişikliğine yol açıyorsa onu ayrı bir değişiklik olarak raporla.

---

# 21. Test Strategy

Her fix için uygun test seviyesi kullanılmalıdır.

## Unit

Pure functions:

```text
normalization
classification
metric calculation
retry decisions
compiler output
```

## Integration

```text
DB constraints
migrations
Celery configuration
API/service boundaries
LLM client construction
```

## Browser

```text
skip link
UI status badge
API-backed UI flows
```

---

# 22. Required Regression Invariants

## Privacy

```text
stance NOT in stored compiled_prompt
stance MAY be in runtime generation prompt
stance NOT tracked by git
stance NOT included in Docker context
```

## Scheduler

```text
timezone = Europe/Istanbul
morning = 08:00
evening = 20:00
nightly = 23:50
budget check = 07:45
```

## Profile

```text
normalized hashtag values ∈ DB CHECK set
```

## Evidence

Her registered evidence status için gerekli UI metadata mevcut olmalı.

Özellikle:

```text
attribution_verified
```

## Grounding

```text
ungrounded API publish/accept → rejected
```

## Metrics

```text
numerator and denominator refer to same event population
```

## Retry

```text
every HTTP attempt consumes rate-limit acquisition
final attempt does not sleep
```

---

# 23. Full Verification After Each Batch

Her batch sonrasında:

```bash
ruff check .
mypy
python scripts/check_architecture.py
pytest
```

Ayrıca:

```bash
git diff --check
git diff --stat
git status
```

Batch'e özgü testleri full suite'den önce çalıştır.

Örneğin D7:

```text
targeted editorial/profile tests
→ DB integration tests
→ full pytest
→ lint/type/architecture
```

---

# 24. Change Isolation

Her batch mantıksal olarak ayrı tutulmalı.

Önerilen commit yapısı:

```text
fix(security): ignore editorial stance file
fix(security): keep editorial stance out of stored profiles
fix(scheduler): evaluate Celery schedules in Europe/Istanbul
fix(profile): stop deriving hashtag usage from emoji preference
fix(verticals): apply per-vertical non-event filters
fix(evidence): render attribution_verified correctly
fix(editorial): enforce grounding at service boundary
fix(llm): honor timeout and retry configuration
fix(ingestion): rate-limit every HTTP retry
fix(nlp): fold opinion classifier keywords
fix(metrics): align correction rate populations
fix(editorial): reject unsupported citation habit
fix(ingestion): avoid sleeping after final retry
fix(metrics): measure accepted body edits
fix(a11y): expose skip link on focus
fix(editorial): persist stale compiled profiles
chore(backlog): reconcile dead feature status
```

Tek bir dev commit oluşturma:

```text
fix: phase 2 hardening
```

kullanma.

---

# 25. Definition of Done — Phase 2

Phase 2 ancak aşağıdaki şartlar sağlanırsa tamamlanmış kabul edilir.

## Correctness

- [ ] L1 kapatıldı.
- [ ] L2 kapatıldı.
- [ ] L3 kapatıldı.
- [ ] L4 kapatıldı.
- [ ] L5 kapatıldı.
- [ ] L6 kapatıldı.

## Privacy / Security

- [ ] D7 kapatıldı.
- [ ] D8 kapatıldı.
- [ ] Stance storage invariant regression test ile korunuyor.
- [ ] Git/Docker exclusion test ediliyor.

## Editorial/API

- [ ] D12 kapatıldı.
- [ ] D13 kapatıldı.
- [ ] D15 kapatıldı.
- [ ] D17 kapatıldı veya açıkça ertelendi.

## Infrastructure

- [ ] D9 kapatıldı.
- [ ] D10 kapatıldı.
- [ ] D14 kapatıldı.

## Accessibility

- [ ] D11 kapatıldı.

## Code integrity

- [ ] D16 için backlog/code reality reconciled.

## Improvements

- [ ] I1–I9 için karar verildi.
- [ ] Uygulanan improvement'lar defect fix'lerinden ayrı tutuldu.

## Gates

- [ ] `ruff check .`
- [ ] `mypy`
- [ ] `python scripts/check_architecture.py`
- [ ] `pytest`
- [ ] DB integration tests
- [ ] migration tests

başarılı.

---

# 26. Phase 2 Verification Audit

Tüm fix'lerden sonra ikinci bir read-only audit yapılmalıdır.

Her finding için:

| ID | Status | Verification |
|---|---|---|
| L1 | OPEN/CLOSED | evidence |
| L2 | OPEN/CLOSED | evidence |
| L3 | OPEN/CLOSED | evidence |
| L4 | OPEN/CLOSED | evidence |
| L5 | OPEN/CLOSED | evidence |
| L6 | OPEN/CLOSED | evidence |
| D7 | OPEN/CLOSED | evidence |
| D8 | OPEN/CLOSED | evidence |
| D9 | OPEN/CLOSED | evidence |
| D10 | OPEN/CLOSED | evidence |
| D11 | OPEN/CLOSED | evidence |
| D12 | OPEN/CLOSED | evidence |
| D13 | OPEN/CLOSED | evidence |
| D14 | OPEN/CLOSED | evidence |
| D15 | OPEN/CLOSED | evidence |
| D16 | OPEN/CLOSED | evidence |
| D17 | OPEN/CLOSED | evidence |

Her CLOSED finding için gerçek test/output/path evidence ver.

"Fixed" demek yeterli değildir.

---

# 27. Phase 2 Sonrası Unreviewed Scope Audit

Phase 1'de incelenmeyen yaklaşık 12k LOC ayrı audit kapsamıdır.

## Audit B1

```text
ingestion/
clustering/
nlp/embedder
nlp/entities
nlp/search
nlp/claims_pipeline
ingestion/adapters/*
```

## Audit B2

```text
briefing/
admin/
editorial/checker
editorial/generator
editorial/grounding_check
eval/
most of scripts/
```

Bu alanlar Phase 2 fix kapsamına otomatik olarak dahil değildir.

---

# 28. Final Reporting Format

Phase 2 sonunda aşağıdaki formatta rapor oluştur:

## Executive Summary

- toplam düzeltilen finding
- ertelenen finding
- yeni test sayısı
- full gate sonucu
- DB test sonucu

## Changes

Her finding:

```text
ID
Files changed
Root cause
Fix
Tests
Verification
```

## Remaining

```text
OPEN
DEFERRED
NEEDS DECISION
```

## Verification

Gerçek komut çıktıları.

## Working Tree

Değişen dosyalar ve diff özeti.

## Risks

Varsa kalan riskler.

---

# 29. AI Agent Operating Protocol

Bu belgeyi uygulayan AI şu protokole kesinlikle uymalıdır:

### Adım 1

Baseline al.

### Adım 2

Sıradaki batch'i oku.

### Adım 3

İlgili kodu yeniden oku.

### Adım 4

Phase 1 bulgusunu yeniden reproduce et.

### Adım 5

Fix'i uygula.

### Adım 6

Regression test ekle.

### Adım 7

Targeted tests.

### Adım 8

Full gates.

### Adım 9

Diff review.

### Adım 10

Batch raporu.

### Adım 11

Sonraki batch'e geç.

---

# 30. STOP Conditions

Aşağıdakilerden herhangi biri olursa otomatik olarak dur:

- Phase 1 teşhisi yanlış görünüyorsa,
- çözüm breaking API change gerektiriyorsa,
- mevcut DB datasının nasıl migrate edileceği belirsizse,
- privacy-sensitive verinin cleanup yöntemi belirsizse,
- unreviewed module'a kapsamlı değişiklik yapmak gerekiyorsa,
- test environment gerçeği doğrulamıyorsa,
- mevcut testlerin neden başarısız olduğu açıklanamıyorsa,
- iki farklı çözüm arasında ürün/semantik kararı gerekiyorsa,
- kullanıcı intent'i belirsizse.

Bu durumda:

```text
STOPPED

Finding:
Reason:
Evidence:
Decision required:
Proposed options:
Risk:
```

formatında raporla.

**Do not improvise.**

---

# 31. Final Principle

Bu Phase 2'nin amacı yalnızca mevcut 17 defect'i kapatmak değildir.

Ana hedef:

> Projede dokümantasyon, schema, UI ve yorumlarda ifade edilen kritik invariant'ların gerçekten kod ve test seviyesinde enforce edilmesini sağlamak.

Özellikle şu pattern ortadan kaldırılmalıdır:

```text
Documentation says X
        ↓
Code does not enforce X
        ↓
Tests do not exercise X
        ↓
System appears healthy
        ↓
Production behavior violates X
```

Hedef:

```text
Requirement
    ↓
Code invariant
    ↓
Regression test
    ↓
Integration verification
    ↓
CI gate
```

Phase 2 bu standarda ulaştığında tamamlanmış kabul edilir.
