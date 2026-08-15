# PolitikDesk — Faz Faz Üretim Hazırlığı ve Eksiklerin Kapatılması Yol Haritası

**Belge sürümü:** 1.0  
**Tarih:** 15 Ağustos 2026  
**Kapsam:** Kullanıcının 15 Ağustos 2026 tarihli ölçüm raporunda tespit edilen tüm açıklar, hatalar, ölçüm borçları ve faz geçiş koşulları  
**Hedef:** PolitikDesk'i repo → CI → image → container → DB → veri kalitesi → G4′ → S3 → UI doğrulama zincirinde ölçülebilir, tekrarlanabilir ve denetlenebilir hale getirmek.

---

# 0. Bu Yol Haritasının Amacı

Bu belge yeni özellik geliştirme planı değildir.

Amaç, mevcut sistemde ölçülmüş olan:

- kod kalite problemlerini,
- CI kapısı problemlerini,
- Git/deployment senkronizasyon problemlerini,
- Docker packaging eksiklerini,
- canlı ingestion hatalarını,
- G4′ ön koşullarını,
- ölçüm borçlarını,
- UI doğrulama eksiklerini,
- kullanıcı tarafından yapılması gereken operasyonları,
- plan ile gerçek kod arasındaki sapmaları

**tek bir kontrollü kapanış programı içinde sıfırlamaktır.**

Bu belge tamamlanmadan yeni özellik eklemek yerine mevcut sistemin doğruluğu ve üretim güvenilirliği önceliklidir.

---

# 1. Ana İlke

PolitikDesk için dört farklı gerçeklik aynı anda kabul edilmeyecek:

```text
Git repository
      ↓
CI / Quality Gates
      ↓
Docker Image
      ↓
Running Containers
      ↓
Production Database
```

Her fazın amacı bu zinciri senkronize etmektir.

## Nihai hedef

```text
Clean Git checkout
        ↓
Green CI
        ↓
Reproducible Docker image
        ↓
Expected Git SHA / image identity
        ↓
All runtime assets present
        ↓
All adapters present
        ↓
All scheduled tasks present
        ↓
Healthy ingestion
        ↓
Validated production data
        ↓
G4′ PASS
        ↓
S3 General Politics
```

---

# 2. Değişmez Faz Geçiş Kuralları

Aşağıdaki kurallar bu yol haritasının tamamında geçerlidir.

## Kural 1 — G4′ kapanmadan S3 başlamaz

Genel siyaset dikeyine geçilmeyecek.

## Kural 2 — Deployment doğrulanmadan ölçüm sayacı başlamaz

Bayat image, eksik adapter veya eksik config ile geçen süre G4′ 7 günlük süreye dahil edilmez.

## Kural 3 — CI kırmızıysa faz kapanmaz

Aşağıdakilerin tamamı yeşil olmalıdır:

- ruff
- mypy
- pytest
- pip-audit
- architecture
- migrations
- packaging
- deployment checks

## Kural 4 — Rapor “PASS” kelimesini ancak tüm zorunlu kapılar geçtiğinde kullanır

Örneğin:

```text
pytest: PASS
mypy: PASS
ruff: FAIL
phase: FAIL
```

## Kural 5 — Production ölçümleri reproducible olmalıdır

Her ölçüm:

- tarih/saat,
- Git SHA,
- image identity,
- DB schema version,
- ölçüm penceresi,
- veri miktarı

ile ilişkilendirilebilir olmalıdır.

## Kural 6 — Yeni özellikler mevcut borçların üstüne eklenmez

Önce kırık zincir kapatılır.

---

# 3. Başlangıç Durumu — 15 Ağustos 2026

## 3.1 Kod

| Kapı | Durum |
|---|---|
| mypy | PASS — 0 hata / 140 dosya |
| pytest | PASS — 812 / 812 |
| pip-audit | PASS |
| architecture | PASS |
| ruff | FAIL — 404 hata |
| CI | FAIL |

## 3.2 Git

- Son commit: `31d7945`
- 84 değiştirilmiş dosya
- +8.332 / −4.414
- 1 silinmiş dosya
- 64 untracked path

## 3.3 Production

- 5 container ayakta
- Pipeline aşamaları çalışıyor
- Container kodu repo ile senkron değil
- Yasama dikeyi production'da fiilen çalışmıyor
- `sources_legislation.yml` image'larda eksik
- Beat'te `political-relations-every-15-minutes` eksik

## 3.4 Veri

- 95 makale
- 56 olay
- 171 iddia
- 182 kanıt
- 17 taslak
- 4 brifing
- 11 olay ilişkisi
- 16 kaynak

## 3.5 G4′

| Koşul | Sonuç |
|---|---|
| 7 gün kesintisiz akış | Bekliyor — 2,5 gün |
| Arıza ≤ %2 | FAIL — %9,60 |
| Correction ≤ %3 | Veri yetersiz |
| Diversity ≥ 2,5 | Veri yetersiz — 1,86 |
| Clustering | PASS |
| Numeric/date grounding | PASS |
| 14 briefing slot | FAIL/BEKLEMEDE — 4 üretildi, 0 gönderildi |

---

# FAZ 0 — Baseline Dondurma ve Envanter

**Durum:** Başlanacak  
**Öncelik:** P0  
**Amaç:** Mevcut sistemi değiştirmeden ölçüm sonuçlarını tekrar üretilebilir hale getirmek.

## 0.1 Git baseline

- [ ] `git status` kaydet.
- [ ] `git diff --stat` kaydet.
- [ ] untracked dosya listesini kaydet.
- [ ] mevcut branch'i kaydet.
- [ ] HEAD SHA'yı kaydet.
- [ ] değişikliklerin hangi faza ait olduğunu sınıflandır.
- [ ] rastgele dosya silme/taşıma yapma.

## 0.2 Runtime baseline

- [ ] çalışan container isimlerini kaydet.
- [ ] image ID/digest kaydet.
- [ ] container creation time kaydet.
- [ ] container environment/config özetini kaydet.
- [ ] çalışan Git SHA varsa kaydet.
- [ ] DB schema version kaydet.

## 0.3 Veri baseline

- [ ] makale sayısını kaydet.
- [ ] olay sayısını kaydet.
- [ ] claim sayısını kaydet.
- [ ] evidence sayısını kaydet.
- [ ] briefing sayısını kaydet.
- [ ] relation sayısını kaydet.
- [ ] kaynak sayısını kaydet.
- [ ] son 24 saat ingestion sonuçlarını kaydet.

## 0.4 Gate baseline

Aşağıdakilerin mevcut sonuçlarını tek raporda sakla:

```text
ruff
mypy
pytest
pip-audit
architecture
packaging
deployment
migration
```

### FAZ 0 çıkış kriteri

- [ ] Başlangıç ölçümleri kayıtlı.
- [ ] Git baseline kayıtlı.
- [ ] Production baseline kayıtlı.
- [ ] DB baseline kayıtlı.
- [ ] Her sonraki ölçüm karşılaştırılabilir.

---

# FAZ 1 — Release Identity ve Repo/Runtime Senkronizasyonu

**Öncelik:** P0  
**Amaç:** “Repo başka, container başka” problemini kalıcı olarak çözmek.

## 1.1 Release identity

Production uygulamasının şu bilgileri expose etmesi sağlanmalı:

```text
APP_VERSION
GIT_SHA
IMAGE_DIGEST
DB_SCHEMA_VERSION
DEPLOYED_AT
```

Önerilen endpoint:

```text
GET /version
```

veya mevcut health endpoint'inin genişletilmesi.

## 1.2 Deployment check

`check_deployment` aşağıdakileri doğrulamalı:

- [ ] beklenen Git SHA = çalışan Git SHA
- [ ] beklenen image = çalışan image
- [ ] DB schema uyumlu
- [ ] gerekli Python modülleri mevcut
- [ ] gerekli adapter'lar mevcut
- [ ] gerekli config dosyaları mevcut
- [ ] Beat task listesi beklenen listeyle eşleşiyor

## 1.3 Container içerik doğrulaması

Worker image içinde özellikle kontrol et:

- [ ] `politicaldesk/verticals/`
- [ ] `politicaldesk/political_memory/`
- [ ] `politicaldesk/web/ui/`
- [ ] `adapters/tbmm.py`
- [ ] `adapters/sayistay.py`
- [ ] Cumhurbaşkanlığı adapter'ı
- [ ] legislation config
- [ ] migration dosyaları
- [ ] gerekli prompt/config dosyaları

## 1.4 Temiz build

- [ ] cache davranışını kontrol et.
- [ ] clean rebuild yap.
- [ ] image'ı yeniden oluştur.
- [ ] container'ları recreate et.
- [ ] deployment check çalıştır.
- [ ] runtime module inspection çalıştır.

### FAZ 1 çıkış kriteri

```text
repo SHA
   =
image SHA
   =
container SHA
```

ve deployment check:

**PASS**

olmalı.

---

# FAZ 2 — Docker Packaging ve Statik Asset Güvenliği

**Öncelik:** P0  
**Amaç:** Repo'da bulunan ancak image'a girmeyen dosyaların tekrar oluşmasını engellemek.

## 2.1 legislation config

- [ ] `config/sources_legislation.yml` Dockerfile'a dahil et.
- [ ] runtime path'i doğrula.
- [ ] üç ilgili container'da dosyanın mevcut olduğunu doğrula.

## 2.2 Packaging testleri

`tests/test_packaging.py` genişletilmeli.

Testler en az şunları kapsamalı:

- [ ] `sources_legislation.yml`
- [ ] gerekli vertical dosyaları
- [ ] required adapters
- [ ] political_memory package
- [ ] web UI runtime assets
- [ ] gerekli prompt/config dosyaları

## 2.3 Eksik dosya regression testi

Test prensibi:

```text
Repo'da runtime için gerekli olan dosya
        ↓
Docker build
        ↓
Image içinde bulunmalı
```

## 2.4 Build sonrası smoke test

- [ ] container ayağa kalkıyor.
- [ ] config yükleniyor.
- [ ] adapter registry doğru.
- [ ] worker task discovery doğru.
- [ ] web uygulaması gerekli UI modüllerini buluyor.

### FAZ 2 çıkış kriteri

Bir runtime asset'i Docker image'a alınmadan CI geçememeli.

---

# FAZ 3 — Beat ve Task Registry Bütünlüğü

**Öncelik:** P0

## 3.1 Eksik görev

`political-relations-every-15-minutes`

- [ ] task tanımını doğrula.
- [ ] Celery registration'ı doğrula.
- [ ] Beat schedule'a ekle.
- [ ] worker tarafından keşfedildiğini doğrula.
- [ ] beat tarafından schedule edildiğini doğrula.

## 3.2 Test

`tests/test_tasks.py` şu invariant'ı zorunlu kılmalı:

```text
Tanımlı ve production'da çalışması gereken her scheduled task
→ Beat schedule'da bulunmalı.
```

## 3.3 Schedule drift

Deployment check:

- [ ] beklenen task sayısı
- [ ] gerçek task sayısı
- [ ] eksik task
- [ ] beklenmeyen task

raporlamalı.

### FAZ 3 çıkış kriteri

`15/15` değil, beklenen tüm görevlerin tamamı schedule'da olmalı.

---

# FAZ 4 — Canlı Ingestion Arızalarının Kapatılması

**Öncelik:** P0/P1

Amaç:

**%9,60 → ≤ %2**

---

## 4.1 Resmî Gazete

Mevcut:

```text
97 / 188 başarısız
ReadTimeout
```

Bu en büyük darboğazdır.

### Ölç

- [ ] request latency
- [ ] timeout süresi
- [ ] response size
- [ ] concurrency
- [ ] retry count
- [ ] endpoint
- [ ] fihrist boyutu
- [ ] pagination davranışı

### Çözüm sırası

1. [ ] concurrency profilini ölç.
2. [ ] timeout profilini ölç.
3. [ ] retry/backoff davranışını kontrol et.
4. [ ] fihristi kademeli çekmeyi değerlendir.
5. [ ] gereksiz paralelliği azalt.
6. [ ] tekrar ölç.

**Rastgele timeout artırma çözüm olarak kabul edilmez.**

---

## 4.2 Hazine

Mevcut:

```text
7 / 189
ConnectTimeout
```

- [ ] bağlantı timeout'unu ölç.
- [ ] retry/backoff kontrol et.
- [ ] endpoint health kontrol et.
- [ ] gerekiyorsa concurrency ayarla.
- [ ] tekrar ölç.

---

## 4.3 TÜİK

Mevcut:

```text
2 / 188
401 Unauthorized
```

- [ ] credential'ın geçerli olduğunu doğrula.
- [ ] token expiry davranışını kontrol et.
- [ ] refresh mekanizmasını kontrol et.
- [ ] environment/config aktarımını kontrol et.
- [ ] API request header'larını doğrula.
- [ ] başarılı authenticated request smoke test'i yap.

### Kullanıcı kararı

- [ ] TÜİK hesabı/belirteci alınacak mı?
- [ ] Alınacaksa credential lifecycle tanımlanacak.
- [ ] Alınmayacaksa ilgili entegrasyon davranışı açıkça belgelenmeli.

---

## 4.4 Kaynak bazlı hata raporu

Production metric:

```text
source
attempts
successes
failures
error_type
failure_rate
```

şeklinde tutulmalı.

### FAZ 4 çıkış kriteri

Son 24 saatlik ingestion failure rate:

**≤ %2**

olmalı.

---

# FAZ 5 — CI Kalite Kapısının Tamamen Yeşile Döndürülmesi

**Öncelik:** P1

## 5.1 Ruff

Başlangıç:

**404 hata**

- [ ] `ruff --fix` uygulanabilecekleri düzelt.
- [ ] unused imports temizle.
- [ ] import order düzelt.
- [ ] E501 satırlarını düzenle.
- [ ] yeni S1–S3 dosyalarını düzelt.
- [ ] `eval/generate_adversarial_v2.py` dosyasını düzelt.
- [ ] istisna gerekiyorsa bilinçli ve belgeli yap.

Hedef:

```text
ruff check .
0 errors
```

## 5.2 Mypy

Mevcut:

```text
0 / 140
```

- [ ] mevcut sonucu koru.
- [ ] Ruff düzeltmelerinden sonra tekrar çalıştır.

## 5.3 Pytest

Mevcut:

```text
812 passed
```

- [ ] DB açık koş.
- [ ] `PD_CI_REQUIRE_DB=1`.
- [ ] test sayısının değişimini kaydet.
- [ ] yeni packaging/task testlerini ekle.
- [ ] 0 failure.
- [ ] 0 skip.

## 5.4 pip-audit

- [ ] tekrar çalıştır.
- [ ] bilinen açık yok.

## 5.5 Architecture

- [ ] mevcut iki kural korunmalı.
- [ ] yeni package bağımlılıkları kontrol edilmeli.

## 5.6 Migration

- [ ] temiz DB migration.
- [ ] mevcut DB migration.
- [ ] upgrade/downgrade davranışı.
- [ ] migration drift.

## 5.7 Final CI

Tek komutla:

```text
pd ci
```

tamamen yeşil olmalı.

### FAZ 5 çıkış kriteri

```text
ruff       PASS
mypy       PASS
pytest     PASS
pip-audit  PASS
architecture PASS
migration  PASS
packaging  PASS
```

---

# FAZ 6 — Git Hygiene ve Parçalı Commit

**Öncelik:** P1

Amaç, mevcut 84 dosyalık karma değişikliği yönetilebilir hale getirmek.

## 6.1 Commit grupları

Önerilen sıra:

### Commit 1 — Tasarım sistemi

- design/
- DESIGN.md
- ilgili UI kit değişiklikleri

### Commit 2 — Vertical architecture

- verticals/

### Commit 3 — Political adapters

- TBMM
- Sayıştay
- Cumhurbaşkanlığı

### Commit 4 — Political Memory

- political_memory/
- migration'lar

### Commit 5 — Web screens

- yeni web ekranları

### Commit 6 — Tests / gates

- yeni testler
- gate runner'lar

### Commit 7 — Documentation

- README
- BACKLOG
- raporlar

## 6.2 Commit kuralı

Her commit:

- [ ] self-contained
- [ ] açıklanabilir
- [ ] mümkünse ilgili testleri içerir
- [ ] CI yeşil

olmalı.

## 6.3 Untracked dosya kontrolü

Sonunda:

```text
git status
```

temiz olmalı.

### FAZ 6 çıkış kriteri

Çalışma ağacı temiz ve tüm gerekli değişiklikler version control altında.

---

# FAZ 7 — Dokümantasyon ve Plan Gerçekliği

**Öncelik:** P1

## 7.1 README

Şunları güncelle:

- [ ] Spec v3.3 → v3.4
- [ ] kaynak sayısı 10 → 16
- [ ] test sayısı 690 → 812 veya güncel gerçek sayı
- [ ] MVP dikeyleri
- [ ] verticals/
- [ ] political_memory/
- [ ] yeni web ekranları
- [ ] güncel mimari ağacı

## 7.2 BACKLOG

Aşağıdakilerin durumunu gerçeğe eşitle:

- [ ] B-04
- [ ] B-15
- [ ] B-60
- [ ] B-97

Özellikle B-97:

`nlp/opinion_classifier.py`

kodda bulunuyor ancak pipeline'a bağlı değilse:

**“implemented” değil, “implemented but not integrated”**

olarak işaretlenmeli.

## 7.3 Phase reports

- [ ] S2 raporunun gerçek kapsamını düzelt.
- [ ] S3 raporunun plan S3 ile karıştırılmasını engelle.
- [ ] PASS/FAIL semantiğini standartlaştır.

### FAZ 7 çıkış kriteri

Dokümantasyon ile repository gerçeği arasında bilinen çelişki kalmamalı.

---

# FAZ 8 — Release Verification ve Production Smoke Test

**Öncelik:** P0

Bu faz önceki fazların birleşik doğrulamasıdır.

## 8.1 Temiz checkout

- [ ] temiz checkout.
- [ ] bağımlılık kurulumu.
- [ ] environment hazırlanması.

## 8.2 CI

- [ ] `pd ci`

## 8.3 Image

- [ ] clean Docker build.
- [ ] image digest kaydı.

## 8.4 Deployment

- [ ] container recreate.
- [ ] version endpoint.
- [ ] deployment check.

## 8.5 Runtime smoke

Her önemli kaynak için en az bir başarılı ingestion:

- [ ] Cumhurbaşkanlığı
- [ ] TBMM
- [ ] Sayıştay
- [ ] Resmî Gazete
- [ ] Hazine
- [ ] TÜİK

## 8.6 Data verification

DB'de:

- [ ] yeni makale
- [ ] yeni olay
- [ ] yeni claim
- [ ] evidence
- [ ] relation
- [ ] political memory

kontrol edilmeli.

### FAZ 8 çıkış kriteri

**Repo → Image → Container → DB zinciri doğrulanmış olmalı.**

---

# FAZ 9 — G4′ Sayaçlarının Sıfırdan Başlatılması

**Öncelik:** P0

Bu faz ancak Faz 8 başarıyla tamamlandıktan sonra başlar.

Önceki 2,5 günlük süre:

**yeni 7 günlük pencereye dahil edilmez.**

---

# G4′-1 — 7 Gün Kesintisiz Akış

Hedef:

**7 gün**

Kurallar:

- [ ] pipeline çalışmalı.
- [ ] kritik kaynaklar çalışmalı.
- [ ] yasama dikeyi çalışmalı.
- [ ] deployment drift olmamalı.
- [ ] container restart'ları ölçülmeli.
- [ ] veri birikmesi olmamalı.

Her gün snapshot:

```text
date
source health
pipeline health
failure rate
backlog
container SHA
DB schema
```

### PASS

7 gün boyunca kritik kesinti yok.

---

# G4′-2 — Toplama Arıza Oranı

Hedef:

**≤ %2**

Önceki:

**%9,60**

- [ ] Resmî Gazete düzeltildi.
- [ ] Hazine düzeltildi.
- [ ] TÜİK düzeltildi.
- [ ] 24 saatlik pencere yeniden ölçüldü.
- [ ] kaynak bazlı oranlar raporlandı.

### PASS

Toplam failure rate ≤ %2.

---

# G4′-3 — Correction Rate

Hedef:

**≤ %3**

Minimum:

**34 açılan olay**

Mevcut:

**7 olay / 1 feedback**

- [ ] Feed düzenli kullan.
- [ ] olayları incele.
- [ ] correction gerekiyorsa kaydet.
- [ ] feedback üret.
- [ ] en az 34 olay.
- [ ] correction oranını hesapla.

### PASS

Correction rate ≤ %3.

---

# G4′-4 — Diversity Ratio

Hedef:

**≥ 2,5**

Minimum:

**10 olay**

Mevcut:

**1,86**

Önce:

### B-82

Number typing.

- [ ] number tiplemesindeki kaçırmaları analiz et.
- [ ] düzelt.
- [ ] Golden Set ile ölç.
- [ ] diversity tekrar ölç.

Sonra gerekiyorsa:

### B-81

Cross-source claim matching.

**Golden Set precision ölçülmeden production'a alınmayacak.**

### PASS

Diversity ratio ≥ 2,5.

---

# G4′-5/7 — Clustering

Mevcut:

```text
precision = 1.000
recall = 0.824
false merge = 0
```

- [ ] mevcut değerleri koru.
- [ ] yeni değişikliklerden sonra regression test çalıştır.
- [ ] false merge = 0 korunmalı.

---

# G4′-8 — Numeric / Date Grounding

Mevcut:

**%0 hata**

- [ ] regression test korunmalı.
- [ ] yeni NLP/claim değişikliklerinden sonra tekrar çalıştırılmalı.

---

# G4′-9 — Briefing Delivery

Hedef:

**14 slot**

Mevcut:

**4 üretildi / 0 gönderildi**

## SMTP

- [ ] `PD_SMTP_HOST`
- [ ] gerekli username/password
- [ ] sender
- [ ] port
- [ ] TLS/SSL
- [ ] secret yönetimi

## Smoke test

- [ ] test mail gönder.
- [ ] delivery log doğrula.
- [ ] `send_error` temizlenmiş olmalı.

## 14 slot

- [ ] briefing generation
- [ ] briefing validation
- [ ] sending
- [ ] send result
- [ ] delivery record

### PASS

14 slotun beklenen şekilde üretilmesi ve gönderilmesi.

---

# FAZ 10 — Measurement Debt

**Öncelik:** P1/P2

---

## B-82 — Number Typing

**İlk yapılacak.**

- [ ] mevcut failure örneklerini çıkar.
- [ ] number extraction hatalarını sınıflandır.
- [ ] Golden Set'e ekle.
- [ ] precision/recall ölç.
- [ ] düzelt.
- [ ] regression test ekle.

---

## B-81 — Cross-Source Claim Matching

**B-82 sonrası.**

- [ ] Golden Set'i genişlet.
- [ ] 150 claim hedefini tamamla.
- [ ] precision ölç.
- [ ] false confirmation oranı ölç.
- [ ] threshold belirle.
- [ ] yalnızca kabul edilebilir precision seviyesinde entegre et.

**Kural:**

Yanlış teyit üretme riski varsa özellik production'a alınmaz.

---

# B-57 — Golden Set

Hedef:

**300 makale + 150 claim**

Mevcut:

**55 + 24**

Plan:

- [ ] 100 makale
- [ ] 200 makale
- [ ] 300 makale
- [ ] 50 claim
- [ ] 100 claim
- [ ] 150 claim

Her ekleme:

- [ ] kaynak çeşitliliği
- [ ] olay çeşitliliği
- [ ] sayı/tarih örnekleri
- [ ] farklı claim türleri
- [ ] siyasi içerik
- [ ] negatif örnekler

içermeli.

---

# B-75 — Production Gate Sample

Hedef:

**50 + 40 taslak**

- [ ] 50 üretim örneği
- [ ] 40 draft
- [ ] kalite ölçümü
- [ ] G3 koşullarının yeniden doğrulanması

---

# B-67 / B-68 — Provider Comparison ve Kota

Bekleyen:

`ANTHROPIC_API_KEY`

- [ ] API key.
- [ ] provider benchmark.
- [ ] kalite karşılaştırması.
- [ ] latency.
- [ ] maliyet.
- [ ] failure rate.
- [ ] aylık kota.
- [ ] hard ceiling.
- [ ] alert threshold.

## D18

Üretim modeli kararı:

**güven 🟡 → karar verilmiş ve ölçülmüş hale getirilmeli.**

---

# B-69 / B-52 — Metric Selection ve Numeric Guard

- [ ] metric selection accuracy.
- [ ] numeric guard false positive.
- [ ] ortak test seti.
- [ ] threshold.
- [ ] regression test.

---

# B-46 — Topic Filter

- [ ] false negative örnekleri.
- [ ] Golden Set.
- [ ] precision.
- [ ] recall.
- [ ] threshold.
- [ ] regression.

---

# B-63 — Source Existence Signal

Spec §11.4 semantiğini değiştirecekse:

- [ ] önce karar yazılı hale getir.
- [ ] Spec değişikliğini versionla.
- [ ] testleri güncelle.
- [ ] migration gerekiyorsa uygula.
- [ ] dokümantasyonu güncelle.

---

# B-42 / B-61 — Takvimler

## TÜİK publishing calendar

- [ ] resmi yayın takvimi kaynağı.
- [ ] authentication gereksinimi.
- [ ] config/calendar_2026.yml.
- [ ] 10 `verified: false` kaydı incele.
- [ ] kaynak kanıtı.
- [ ] verified=true yalnızca kanıtla.

## TCMB PPK calendar

- [ ] resmi kaynak.
- [ ] 2026 takvimi.
- [ ] doğrulama.
- [ ] config güncelleme.

### PASS

Takvimde kalan doğrulanmamış kayıtlar bilinçli olarak açıklanmış veya doğrulanmış olmalı.

---

# B-51 — Event Title Generation

Mevcut:

Tohum makalenin başlığı.

- [ ] olay başlığı üretim kriterleri belirle.
- [ ] LLM prompt'u.
- [ ] hallucination kontrolü.
- [ ] source-grounded title.
- [ ] Golden Set değerlendirmesi.
- [ ] regression.

---

# B-59 / B-76 — Haftalık Kalite Ritüeli

## B-59

Minimum:

**3 hafta**

Her hafta:

- [ ] ingestion health
- [ ] correction
- [ ] diversity
- [ ] clustering
- [ ] grounding
- [ ] briefing
- [ ] kullanıcı feedback

## B-76

**7 günlük briefing**

- [ ] generation
- [ ] delivery
- [ ] failures
- [ ] user feedback

---

# FAZ 11 — Editorial Stance

**Kullanıcı aksiyonu gerekir.**

`config/editorial_stance.md`

- [ ] `.example` dosyasından gerçek dosyayı oluştur.
- [ ] editoryal ilkeleri tanımla.
- [ ] attribution.
- [ ] fact/claim ayrımı.
- [ ] belirsizlik dili.
- [ ] kaynak güveni.
- [ ] siyasi aktör beyanları.
- [ ] correction dili.
- [ ] kanıt yoksa kesinlik kullanmama.
- [ ] prompt'a dahil olduğunu doğrula.
- [ ] test ile prompt block'un gerçekten uygulandığını doğrula.

---

# FAZ 12 — UI / Design DoD

**Paralel yürütülebilir.**

---

## 12.1 Yeni ekranlar

Tamamlanacak:

- [ ] `/hesap-sor`
- [ ] `/hafiza`
- [ ] `/vaatler`
- [ ] `/arsiv`

Her ekran:

- [ ] UI kit kullanıyor.
- [ ] ham hex yok.
- [ ] responsive.
- [ ] loading state.
- [ ] empty state.
- [ ] error state.
- [ ] accessibility.
- [ ] keyboard navigation.

---

## 12.2 ui_check

Mevcut:

**7 ekran**

Hedef:

**11 ekran**

- [ ] dört yeni ekranı `scripts/ui_check.py` içine ekle.
- [ ] UI smoke test.
- [ ] screenshot/visual regression gerekiyorsa ekle.

---

## 12.3 design decisions

`design/decisions.md`

- [ ] 14 Ağustos'tan sonraki kararları ekle.
- [ ] UI değişiklikleri belgeyle senkron.

---

## 12.4 Lighthouse

Hedef:

**Accessibility ≥95**

- [ ] dört yeni ekran.
- [ ] Lighthouse çalıştır.
- [ ] accessibility ≥95.
- [ ] ciddi performance/regression yok.

---

## 12.5 Keyboard

- [ ] Tab sırası.
- [ ] focus görünürlüğü.
- [ ] skip navigation.
- [ ] modal focus.
- [ ] form navigation.
- [ ] keyboard-only smoke test.

---

## 12.6 Design references

`design/refs/`

- [ ] referans görseller ekle.
- [ ] karakter/visual language kalibrasyonu.
- [ ] final UI review.

---

# FAZ 13 — S3 Öncesi Hukuki ve Editoryal Hazırlık

**G4′ kapanmadan S3'e geçme.**

G4′ PASS sonrası:

## S3-1 — Election Mode

- [ ] `is_enabled(vertical)` canlı test.
- [ ] genel siyaset davranışı.
- [ ] election mode default.
- [ ] feature flag.
- [ ] regression.

## S3-2 — Media Sources

- [ ] farklı çerçevelerden kaynaklar.
- [ ] farklı sahiplik grupları.
- [ ] kademeli ekleme.
- [ ] source diversity ölçümü.

## S3-3 — Party / Actor Sources

Kurallar:

- [ ] attribution için kullanılabilir.
- [ ] fact için birincil kaynak kabul edilmez.
- [ ] attribution açık.
- [ ] source type kayıtlı.

## S3-4 — Opinion Classifier

- [ ] haber/yorum ayrımı.
- [ ] Golden Set.
- [ ] precision.
- [ ] recall.
- [ ] pipeline integration.
- [ ] regression.

## S3-5 — Hukuki Çerçeve

Makro ekonomideki düşük risk varsayımı genel siyaset için geçerli kabul edilmeyecek.

- [ ] hukuki risk analizi.
- [ ] attribution.
- [ ] siyasi aktör içeriği.
- [ ] seçim içeriği.
- [ ] yorum/haber.
- [ ] kullanıcıya sunum biçimi.
- [ ] correction.
- [ ] kaynak gösterimi.

## S3-6 — Salience Calibration

- [ ] `NORM_VELOCITY_MAX` ölç.
- [ ] siyasi dikeyde ayırt ediciliği.
- [ ] `has_primary_source` ağırlığını ölç.
- [ ] Golden Set.
- [ ] before/after benchmark.
- [ ] regression.

---

# FAZ 14 — S3 Gate

S3 ancak şu koşullarla kapanabilir:

## Correction

**≤ %3**

## Diversity

**≥ 2,5**

## Attribution

En az:

**30 draft**

elle denetlenmiş.

Kontrol:

- [ ] source attribution
- [ ] fact/claim distinction
- [ ] opinion/news
- [ ] uncertainty
- [ ] primary source semantics

---

# FAZ 15 — Final Production Readiness

Bu faz tüm önceki fazların birleşik final kontrolüdür.

## Repository

- [ ] clean working tree
- [ ] tüm değişiklikler committed
- [ ] doğru branch/tag
- [ ] README güncel
- [ ] BACKLOG güncel

## CI

- [ ] ruff PASS
- [ ] mypy PASS
- [ ] pytest PASS
- [ ] pip-audit PASS
- [ ] architecture PASS
- [ ] migrations PASS
- [ ] packaging PASS

## Deployment

- [ ] clean build
- [ ] Git SHA doğrulandı
- [ ] image digest doğrulandı
- [ ] container doğrulandı
- [ ] DB schema doğrulandı
- [ ] task schedule doğrulandı
- [ ] runtime asset'ler doğrulandı

## Data

- [ ] ingestion ≤ %2
- [ ] correction ≤ %3
- [ ] diversity ≥ 2,5
- [ ] clustering regression PASS
- [ ] grounding PASS

## Briefing

- [ ] SMTP PASS
- [ ] 14 slot PASS
- [ ] delivery kayıtları mevcut

## UI

- [ ] 11 ekran
- [ ] ui_check PASS
- [ ] Lighthouse accessibility ≥95
- [ ] keyboard PASS
- [ ] visual review PASS

---

# 16. Kesinlikle Yapılmaması Gerekenler

## 16.1 G4′ kapanmadan genel siyasete geçmek

Yapılmayacak.

## 16.2 Bayat image ile 7 günlük sayaç başlatmak

Yapılmayacak.

## 16.3 Sadece pytest geçiyor diye fazı PASS saymak

Yapılmayacak.

## 16.4 B-81'i Golden Set olmadan production'a almak

Yapılmayacak.

## 16.5 Timeout problemini yalnızca timeout artırarak çözmek

Yapılmayacak.

## 16.6 Untracked dosyalarla production deploy etmek

Yapılmayacak.

## 16.7 README/BACKLOG'u “sonra güncelleriz” diye bırakmak

Yapılmayacak.

## 16.8 UI'da yalnızca kod testiyle DoD tamamlamak

Yapılmayacak.

---

# 17. Günlük Çalışma Protokolü

Her çalışma oturumunda:

```text
1. git status
2. mevcut gate durumu
3. tek bir problem alanı
4. değişiklik
5. ilgili test
6. pd ci
7. production etkisi varsa deploy-check
8. ölçüm
9. commit
10. changelog / report update
```

## Bir task tamamlandı demek için

Şunların hepsi olmalı:

```text
Code
+
Test
+
Measurement
+
Documentation
+
Git
```

---

# 18. Faz Durum Panosu

Bu dosya takip edilirken her faz:

```text
⬜ NOT STARTED
🟡 IN PROGRESS
🔴 BLOCKED
🟢 PASS
```

olarak işaretlenmeli.

Önerilen başlangıç:

| Faz | Durum |
|---|---|
| F0 Baseline | 🟢 ölçülmüş |
| F1 Release Identity | ⬜ |
| F2 Packaging | ⬜ |
| F3 Beat Integrity | ⬜ |
| F4 Ingestion | ⬜ |
| F5 CI | 🟡 kısmi |
| F6 Git Hygiene | 🔴 açık |
| F7 Documentation | 🔴 açık |
| F8 Release Verification | ⬜ |
| F9 G4′ | 🔴 bloklu |
| F10 Measurement Debt | ⬜ |
| F11 Editorial Stance | 🔴 kullanıcı aksiyonu |
| F12 UI DoD | 🟡 kısmi |
| F13 S3 Preparation | 🔴 G4′ bloklu |
| F14 S3 Gate | 🔴 bloklu |
| F15 Final Production Readiness | 🔴 bloklu |

---

# 19. En Kısa Uygulama Sırası

Eğer yalnızca sırayı görmek istersen:

```text
F0
 ↓
F1 Release Identity
 ↓
F2 Docker Packaging
 ↓
F3 Beat / Tasks
 ↓
F4 Production Ingestion
 ↓
F5 CI / Ruff
 ↓
F6 Git Hygiene
 ↓
F7 Docs
 ↓
F8 Clean Release Verification
 ↓
G4′ sayaçlarını sıfırla
 ↓
7 gün + ≤2% + correction + diversity + briefing
 ↓
F10 Measurement Debt
 ↓
G4′ PASS
 ↓
F13 S3 Preparation
 ↓
S3 General Politics
 ↓
S3 Gate
 ↓
Final Production Readiness
```

---

# 20. Nihai Definition of Done

PolitikDesk bu yol haritasına göre “tamamlandı” sayılabilmesi için:

> **Temiz bir Git checkout'undan yeniden üretilebilen, CI'sı tamamen yeşil, Docker image'ı eksiksiz, çalışan container'ı beklenen release identity ile eşleşen, DB schema'sı uyumlu, tüm scheduled task'ları çalışan, kritik kaynakları gerçekten ingest eden, son 24 saatte ≤%2 ingestion failure oranına sahip, G4′ kalite koşullarını sağlayan, briefing delivery'si çalışan, Golden Set ölçümleri tamamlanmış, dokümantasyonu gerçek kodla senkron ve UI DoD'si doğrulanmış bir sistem olmalıdır.**

Bu noktadan önce yapılacak işlerin amacı **özellik sayısını artırmak değil, sistemin güvenilirliğini artırmaktır.**

---

# 21. Final Kontrol Listesi

- [ ] Repo clean
- [ ] Untracked production dosyası yok
- [ ] Git SHA doğrulanıyor
- [ ] Image digest doğrulanıyor
- [ ] Container repo ile senkron
- [ ] legislation config image'da
- [ ] tüm adapter'lar image'da
- [ ] tüm scheduled task'lar Beat'te
- [ ] Ruff 0
- [ ] Mypy 0
- [ ] Pytest 0 failure / 0 skip
- [ ] pip-audit temiz
- [ ] architecture temiz
- [ ] migration temiz
- [ ] packaging temiz
- [ ] deployment check temiz
- [ ] Resmî Gazete düzeltilmiş
- [ ] Hazine düzeltilmiş
- [ ] TÜİK authentication düzeltilmiş
- [ ] ingestion ≤%2
- [ ] 7 günlük akış tamam
- [ ] ≥34 correction sample
- [ ] correction ≤%3
- [ ] diversity ≥2,5
- [ ] Golden Set 300 article / 150 claim
- [ ] B-82 ölçülmüş
- [ ] B-81 yalnızca precision kanıtıyla uygulanmış
- [ ] SMTP çalışıyor
- [ ] 14 briefing slot gönderilmiş
- [ ] editorial stance aktif
- [ ] README güncel
- [ ] BACKLOG güncel
- [ ] UI dört yeni ekran DoD'den geçmiş
- [ ] ui_check 11 ekran
- [ ] Lighthouse ≥95
- [ ] keyboard QA
- [ ] design decisions güncel
- [ ] G4′ PASS
- [ ] S3 başlamış
- [ ] S3-1…S3-6 tamam
- [ ] S3 gate PASS
- [ ] Final production readiness PASS

---

# 22. Yönetim Prensibi

Bu yol haritasının temel yaklaşımı:

**Önce doğruluk → sonra güvenilirlik → sonra ölçüm → sonra genişleme.**

PolitikDesk'in bundan sonraki geliştirme döngüsü:

```text
Ölç
 ↓
Sorunu izole et
 ↓
En küçük güvenli düzeltmeyi yap
 ↓
Test et
 ↓
CI çalıştır
 ↓
Production'da doğrula
 ↓
Metrik ile tekrar ölç
 ↓
Commit et
 ↓
Bir sonraki probleme geç
```

Yeni özellik ancak mevcut fazın çıkış kriterlerini bozmadan eklenmelidir.

**G4′ PASS olmadan S3 yoktur.  
S3 ölçülmeden genel siyaset genişlemesi yoktur.  
Measurement kanıtı olmadan “iyileşti” kabulü yoktur.  
CI/deployment doğrulanmadan “production hazır” kabulü yoktur.**
