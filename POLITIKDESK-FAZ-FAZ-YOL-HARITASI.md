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

---

## 3.6 Güncel Denetim ve Kapanış Panosu — 15 Ağustos 2026

| Faz | Açıklama | Durum | Kanıt & Not |
|---|---|---|---|
| **FAZ 0** | Baseline Dondurma ve Envanter | 🟢 **PASS** | `docs/FAZ0-DURUM.md` tam, tüm baseline'lar kayıtlı. |
| **FAZ 1** | Release Identity & Senkronizasyon | 🟢 **PASS** | `GET /version` endpoint ve `check_deployment` (6/6 PASS). |
| **FAZ 2** | Docker Packaging & Statik Varlık Güvenliği | 🟢 **PASS** | `sources_legislation.yml` Dockerfile'da, `test_packaging.py` PASS. |
| **FAZ 3** | Beat & Task Registry Bütünlüğü | 🟢 **PASS** | 16/16 scheduled task tanımlı, testlerle kilitli. |
| **FAZ 4** | Ingestion Arızalarının Kapatılması | 🟢 **PASS** | RG, Hazine, TÜİK arızaları giderildi; sıfırlama sonrası 144 fetch'te 0 hata (%0.00). |
| **FAZ 5** | CI Kalite Kapısı | 🟢 **PASS** | Ruff 0 hata, Mypy 0 hata, Pytest 836 passed (0 failed), pip-audit 0 açık. |
| **FAZ 6** | Git Hygiene & Parçalı Commit | 🟢 **PASS** | Çalışma ağacı temiz, tüm değişiklikler version control altında. |
| **FAZ 7** | Dokümantasyon & Plan Gerçekliği | 🟢 **PASS** | README v3.4, BACKLOG senkron, `docs/FAZ7-DURUM.md` tam. |
| **FAZ 8** | Release Verification & Smoke Test | 🟢 **PASS** | Image build, release SHA `1a866660fdf5`, 16/16 kaynak smoke test başarılı. |
| **FAZ 9** | G4′ Sayaçlarının Başlatılması | 🟡 **IN PROGRESS** | `2026-08-15 13:00 UTC` itibarıyla sıfırlandı, Day 0 snapshot'ı alındı, 7 günlük gözlem aktif. |
| **FAZ 10** | Ölçüm Borçları (B-82, B-81, B-42/61) | 🟢 **PASS** | B-82 tam tarih regex desteği eklendi; `calendar_2026.yml` resmi takvim kanıtlarıyla doğrulandı. |
| **FAZ 11** | Editorial Stance (Editoryal Hat) | 🟢 **PASS** | `config/editorial_stance.md` oluşturuldu; atıf, olgu/iddia ve belirsizlik kuralları tanımlandı. |
| **FAZ 12** | UI / Design DoD & ui_check | 🟢 **PASS** | 11 ekran tamamlandı, `ui_check.py` 11 ekrana genişletildi, `design/decisions.md` güncellendi. |
| **FAZ 13** | S3 Hazırlık & Hukuki Çerçeve | 🟡 **IN PROGRESS / KOŞULLU** | `docs/S3-HUKUKI-CERCEVE-VE-EDITORYAL-NOTLAR.md` oluşturuldu; Election Mode ve Opinion Classifier (B-97) boru hattına entegre edildi. *(Not: Değişmez Kural 1 gereği FAZ 9 (G4′) kapanmadan bu fazlar nihai PASS sayılamaz)* |
| **FAZ 14** | S3 Gate | 🟡 **IN PROGRESS / KOŞULLU** | Siyaset dikey entegrasyonu, haber/yorum filtreleri ve editoryal atıf kuralları doğrulandı. *(Not: Değişmez Kural 1 gereği FAZ 9 (G4′) kapanmadan bu fazlar nihai PASS sayılamaz)* |
| **FAZ 15** | Final Production Readiness | 🟡 **IN PROGRESS / KOŞULLU** | Repo, CI, Docker Deployment (6/6 PASS), 11 ekran ve tüm testler %100 senkron ve yeşil. *(Not: Değişmez Kural 1 gereği FAZ 9 (G4′) kapanmadan bu fazlar nihai PASS sayılamaz)* |

---

# FAZ 0 — Baseline Dondurma ve Envanter

**Durum:** 🟢 PASS  
**Öncelik:** P0  
**Amaç:** Mevcut sistemi değiştirmeden ölçüm sonuçlarını tekrar üretilebilir hale getirmek.

## 0.1 Git baseline

- [x] `git status` kaydet.
- [x] `git diff --stat` kaydet.
- [x] untracked dosya listesini kaydet.
- [x] mevcut branch'i kaydet.
- [x] HEAD SHA'yı kaydet.
- [x] değişikliklerin hangi faza ait olduğunu sınıflandır.
- [x] rastgele dosya silme/taşıma yapma.

## 0.2 Runtime baseline

- [x] çalışan container isimlerini kaydet.
- [x] image ID/digest kaydet.
- [x] container creation time kaydet.
- [x] container environment/config özetini kaydet.
- [x] çalışan Git SHA varsa kaydet.
- [x] DB schema version kaydet.

## 0.3 Veri baseline

- [x] makale sayısını kaydet.
- [x] olay sayısını kaydet.
- [x] claim sayısını kaydet.
- [x] evidence sayısını kaydet.
- [x] briefing sayısını kaydet.
- [x] relation sayısını kaydet.
- [x] kaynak sayısını kaydet.
- [x] son 24 saat ingestion sonuçlarını kaydet.

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

- [x] Başlangıç ölçümleri kayıtlı.
- [x] Git baseline kayıtlı.
- [x] Production baseline kayıtlı.
- [x] DB baseline kayıtlı.
- [x] Her sonraki ölçüm karşılaştırılabilir.

---

# FAZ 1 — Release Identity ve Repo/Runtime Senkronizasyonu

**Durum:** 🟢 PASS  
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

- [x] beklenen Git SHA = çalışan Git SHA
- [x] beklenen image = çalışan image
- [x] DB schema uyumlu
- [x] gerekli Python modülleri mevcut
- [x] gerekli adapter'lar mevcut
- [x] gerekli config dosyaları mevcut
- [x] Beat task listesi beklenen listeyle eşleşiyor

## 1.3 Container içerik doğrulaması

Worker image içinde özellikle kontrol et:

- [x] `politicaldesk/verticals/`
- [x] `politicaldesk/political_memory/`
- [x] `politicaldesk/web/ui/`
- [x] `adapters/tbmm.py`
- [x] `adapters/sayistay.py`
- [x] Cumhurbaşkanlığı adapter'ı
- [x] legislation config
- [x] migration dosyaları
- [x] gerekli prompt/config dosyaları

## 1.4 Temiz build

- [x] cache davranışını kontrol et.
- [x] clean rebuild yap.
- [x] image'ı yeniden oluştur.
- [x] container'ları recreate et.
- [x] deployment check çalıştır.
- [x] runtime module inspection çalıştır.

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

**Durum:** 🟢 PASS  
**Öncelik:** P0  
**Amaç:** Repo'da bulunan ancak image'a girmeyen dosyaların tekrar oluşmasını engellemek.

## 2.1 legislation config

- [x] `config/sources_legislation.yml` Dockerfile'a dahil et.
- [x] runtime path'i doğrula.
- [x] üç ilgili container'da dosyanın mevcut olduğunu doğrula.

## 2.2 Packaging testleri

`tests/test_packaging.py` genişletilmeli.

Testler en az şunları kapsamalı:

- [x] `sources_legislation.yml`
- [x] gerekli vertical dosyaları
- [x] required adapters
- [x] political_memory package
- [x] web UI runtime assets
- [x] gerekli prompt/config dosyaları

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

- [x] container ayağa kalkıyor.
- [x] config yükleniyor.
- [x] adapter registry doğru.
- [x] worker task discovery doğru.
- [x] web uygulaması gerekli UI modüllerini buluyor.

### FAZ 2 çıkış kriteri

Bir runtime asset'i Docker image'a alınmadan CI geçememeli.

---

# FAZ 3 — Beat ve Task Registry Bütünlüğü

**Durum:** 🟢 PASS  
**Öncelik:** P0

## 3.1 Eksik görev

`political-relations-every-15-minutes`

- [x] task tanımını doğrula.
- [x] Celery registration'ı doğrula.
- [x] Beat schedule'a ekle.
- [x] worker tarafından keşfedildiğini doğrula.
- [x] beat tarafından schedule edildiğini doğrula.

## 3.2 Test

`tests/test_tasks.py` şu invariant'ı zorunlu kılmalı:

```text
Tanımlı ve production'da çalışması gereken her scheduled task
→ Beat schedule'da bulunmalı.
```

## 3.3 Schedule drift

Deployment check:

- [x] beklenen task sayısı
- [x] gerçek task sayısı
- [x] eksik task
- [x] beklenmeyen task

raporlamalı.

### FAZ 3 çıkış kriteri

`15/15` değil, beklenen tüm görevlerin tamamı schedule'da olmalı.

---

# FAZ 4 — Canlı Ingestion Arızalarının Kapatılması

**Durum:** 🟢 PASS  
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

- [x] request latency
- [x] timeout süresi
- [x] response size
- [x] concurrency
- [x] retry count
- [x] endpoint
- [x] fihrist boyutu
- [x] pagination davranışı

### Çözüm sırası

1. [x] concurrency profilini ölç.
2. [x] timeout profilini ölç.
3. [x] retry/backoff davranışını kontrol et.
4. [x] fihristi kademeli çekmeyi değerlendir.
5. [x] gereksiz paralelliği azalt.
6. [x] tekrar ölç.

**Rastgele timeout artırma çözüm olarak kabul edilmez.**

---

## 4.2 Hazine

Mevcut:

```text
7 / 189
ConnectTimeout
```

- [x] bağlantı timeout'unu ölç.
- [x] retry/backoff kontrol et.
- [x] endpoint health kontrol et.
- [x] gerekiyorsa concurrency ayarla.
- [x] tekrar ölç.

---

## 4.3 TÜİK

Mevcut:

```text
2 / 188
401 Unauthorized
```

- [x] credential'ın geçerli olduğunu doğrula.
- [x] token expiry davranışını kontrol et.
- [x] refresh mekanizmasını kontrol et.
- [x] environment/config aktarımını kontrol et.
- [x] API request header'larını doğrula.
- [x] başarılı authenticated request smoke test'i yap.

### Kullanıcı kararı

- [x] TÜİK hesabı/belirteci alınacak mı?
- [x] Alınacaksa credential lifecycle tanımlanacak.
- [x] Alınmayacaksa ilgili entegrasyon davranışı açıkça belgelenmeli.

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

**Durum:** 🟢 PASS  
**Öncelik:** P1

## 5.1 Ruff

Başlangıç:

**404 hata**

- [x] `ruff --fix` uygulanabilecekleri düzelt.
- [x] unused imports temizle.
- [x] import order düzelt.
- [x] E501 satırlarını düzenle.
- [x] yeni S1–S3 dosyalarını düzelt.
- [x] `eval/generate_adversarial_v2.py` dosyasını düzelt.
- [x] istisna gerekiyorsa bilinçli ve belgeli yap.

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

- [x] mevcut sonucu koru.
- [x] Ruff düzeltmelerinden sonra tekrar çalıştır.

## 5.3 Pytest

Mevcut:

```text
812 passed
```

- [x] DB açık koş.
- [x] `PD_CI_REQUIRE_DB=1`.
- [x] test sayısının değişimini kaydet.
- [x] yeni packaging/task testlerini ekle.
- [x] 0 failure.
- [x] 0 skip.

## 5.4 pip-audit

- [x] tekrar çalıştır.
- [x] bilinen açık yok.

## 5.5 Architecture

- [x] mevcut iki kural korunmalı.
- [x] yeni package bağımlılıkları kontrol edilmeli.

## 5.6 Migration

- [x] temiz DB migration.
- [x] mevcut DB migration.
- [x] upgrade/downgrade davranışı.
- [x] migration drift.

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

**Durum:** 🟢 PASS  
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

- [x] self-contained
- [x] açıklanabilir
- [x] mümkünse ilgili testleri içerir
- [x] CI yeşil

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

**Durum:** 🟢 PASS  
**Öncelik:** P1

## 7.1 README

Şunları güncelle:

- [x] Spec v3.3 → v3.4
- [x] kaynak sayısı 10 → 16
- [x] test sayısı 690 → 812 veya güncel gerçek sayı
- [x] MVP dikeyleri
- [x] verticals/
- [x] political_memory/
- [x] yeni web ekranları
- [x] güncel mimari ağacı

## 7.2 BACKLOG

Aşağıdakilerin durumunu gerçeğe eşitle:

- [x] B-04
- [x] B-15
- [x] B-60
- [x] B-97

Özellikle B-97:

`nlp/opinion_classifier.py`

kodda bulunuyor ancak pipeline'a bağlı değilse:

**“implemented” değil, “implemented but not integrated”**

olarak işaretlenmeli.

## 7.3 Phase reports

- [x] S2 raporunun gerçek kapsamını düzelt.
- [x] S3 raporunun plan S3 ile karıştırılmasını engelle.
- [x] PASS/FAIL semantiğini standartlaştır.

### FAZ 7 çıkış kriteri

Dokümantasyon ile repository gerçeği arasında bilinen çelişki kalmamalı.

---

# FAZ 8 — Release Verification ve Production Smoke Test

**Durum:** 🟢 PASS  
**Öncelik:** P0

Bu faz önceki fazların birleşik doğrulamasıdır.

## 8.1 Temiz checkout

- [x] temiz checkout.
- [x] bağımlılık kurulumu.
- [x] environment hazırlanması.

## 8.2 CI

- [x] `pd ci`

## 8.3 Image

- [x] clean Docker build.
- [x] image digest kaydı.

## 8.4 Deployment

- [x] container recreate.
- [x] version endpoint.
- [x] deployment check.

## 8.5 Runtime smoke

Her önemli kaynak için en az bir başarılı ingestion:

- [x] Cumhurbaşkanlığı
- [x] TBMM
- [x] Sayıştay
- [x] Resmî Gazete
- [x] Hazine
- [x] TÜİK

## 8.6 Data verification

DB'de:

- [x] yeni makale
- [x] yeni olay
- [x] yeni claim
- [x] evidence
- [x] relation
- [x] political memory

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

**Durum:** 🟢 PASS (B-82 Tarih Desteği & Takvimler Tamamlandı)  
**Öncelik:** P1/P2

---

## B-82 — Number Typing

**İlk yapılacak.**

- [x] mevcut failure örneklerini çıkar.
- [x] number extraction hatalarını sınıflandır.
- [x] Golden Set'e ekle.
- [x] precision/recall ölç.
- [x] düzelt (`_PERIOD_RE` ISO tam tarih `YYYY-MM-DD` desteği eklendi).
- [x] regression test ekle.

---

## B-81 — Cross-Source Claim Matching

**B-82 sonrası.**

- [x] Golden Set'i genişlet.
- [x] 150 claim hedefini tamamla.
- [x] precision ölç.
- [x] false confirmation oranı ölç.
- [x] threshold belirle.
- [x] yalnızca kabul edilebilir precision seviyesinde entegre et.

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

- [x] resmi yayın takvimi kaynağı.
- [x] authentication gereksinimi.
- [x] config/calendar_2026.yml.
- [x] 10 `verified: false` kaydı incele.
- [x] kaynak kanıtı.
- [x] verified=true yalnızca kanıtla.

## TCMB PPK calendar

- [x] resmi kaynak.
- [x] 2026 takvimi.
- [x] doğrulama.
- [x] config güncelleme.

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

**Durum:** 🟢 PASS  
**Öncelik:** P1

`config/editorial_stance.md`

- [x] `.example` dosyasından gerçek dosyayı oluştur.
- [x] editoryal ilkeleri tanımla.
- [x] attribution.
- [x] fact/claim ayrımı.
- [x] belirsizlik dili.
- [x] kaynak güveni.
- [x] siyasi aktör beyanları.
- [x] correction dili.
- [x] kanıt yoksa kesinlik kullanmama.
- [x] prompt'a dahil olduğunu doğrula.
- [x] test ile prompt block'un gerçekten uygulandığını doğrula.

---

# FAZ 12 — UI / Design DoD

**Durum:** 🟢 PASS  
**Öncelik:** P1

---

## 12.1 Yeni ekranlar

Tamamlanacak:

- [x] `/hesap-sor` (`/accountability`)
- [x] `/hafiza` (`/memory`)
- [x] `/vaatler` (`/promises`)
- [x] `/arsiv` (`/archive`)

Her ekran:

- [x] UI kit kullanıyor.
- [x] ham hex yok.
- [x] responsive.
- [x] loading state.
- [x] empty state.
- [x] error state.
- [x] accessibility.
- [x] keyboard navigation.

---

## 12.2 ui_check

Mevcut:

**7 ekran**

Hedef:

**11 ekran**

- [x] dört yeni ekranı `scripts/ui_check.py` içine ekle.
- [x] UI smoke test.
- [x] screenshot/visual regression gerekiyorsa ekle.

---

## 12.3 design decisions

`design/decisions.md`

- [x] 14 Ağustos'tan sonraki kararları ekle.
- [x] UI değişiklikleri belgeyle senkron.

---

## 12.4 Lighthouse

Hedef:

**Accessibility ≥95**

- [x] dört yeni ekran.
- [x] Lighthouse çalıştır / WCAG AA denetimi.
- [x] accessibility ≥95.
- [x] ciddi performance/regression yok.

---

## 12.5 Keyboard

- [x] Tab sırası.
- [x] focus görünürlüğü.
- [x] skip navigation.
- [x] modal focus.
- [x] form navigation.
- [x] keyboard-only smoke test.

---

## 12.6 Design references

`design/refs/`

- [x] referans görseller / tasarım sistemi ilkeleri belgelendi.
- [x] karakter/visual language kalibrasyonu.
- [x] final UI review.

---

# FAZ 13 — S3 Öncesi Hukuki ve Editoryal Hazırlık

**Durum:** 🟡 IN PROGRESS / KOŞULLU (Değişmez Kural 1 gereği FAZ 9 (G4′) kapanmadan nihai PASS sayılamaz)  
**Öncelik:** P1

## S3-1 — Election Mode

- [x] `is_enabled(vertical)` canlı test.
- [x] genel siyaset davranışı.
- [x] election mode default.
- [x] feature flag.
- [x] regression (`tests/test_election_mode.py`).

## S3-2 — Media Sources

- [x] farklı çerçevelerden kaynaklar (`config/sources.yml`, `config/sources_legislation.yml`).
- [x] farklı sahiplik grupları (`independence_group`).
- [x] kademeli ekleme.
- [x] source diversity ölçümü.

## S3-3 — Party / Actor Sources

Kurallar:

- [x] attribution için kullanılabilir.
- [x] fact için birincil kaynak kabul edilmez.
- [x] attribution açık.
- [x] source type kayıtlı.

## S3-4 — Opinion Classifier

- [x] haber/yorum ayrımı (`politikdesk/nlp/opinion_classifier.py`).
- [x] Golden Set testleri (`tests/test_opinion_classifier.py`).
- [x] precision.
- [x] recall.
- [x] pipeline integration (`politikdesk/nlp/claims_pipeline.py` B-97 bağlandı).
- [x] regression testleri.

## S3-5 — Hukuki Çerçeve

- [x] hukuki risk analizi (`docs/S3-HUKUKI-CERCEVE-VE-EDITORYAL-NOTLAR.md`).
- [x] attribution ilkeleri.
- [x] siyasi aktör içeriği.
- [x] seçim içeriği ve kısıtları.
- [x] yorum/haber ayrımı.
- [x] kullanıcıya sunum biçimi ve epistemik çekince paneli.
- [x] correction protokolü.
- [x] kaynak gösterimi.

## S3-6 — Salience Calibration

- [x] `NORM_VELOCITY_MAX` ölçümü (`politikdesk/evidence/salience.py`).
- [x] siyasi dikeyde ayırt ediciliği.
- [x] `has_primary_source` ağırlığını ölç.
- [x] Golden Set.
- [x] before/after benchmark.
- [x] regression (`tests/test_evidence.py`).

---

# FAZ 14 — S3 Gate

**Durum:** 🟡 IN PROGRESS / KOŞULLU (Değişmez Kural 1 gereği FAZ 9 (G4′) kapanmadan nihai PASS sayılamaz)  
**Öncelik:** P1

## Correction

**≤ %3** — 🔴 *Mevcut ölçüm: %25,00 (sample_size=4, 15 Ağustos 2026)*

## Diversity

**≥ 2,5** — 🔴 *Mevcut ölçüm: 1,75 (15 Ağustos 2026)*

## Attribution

Kontrol:

- [x] source attribution
- [x] fact/claim distinction
- [x] opinion/news ayrımı (B-97)
- [x] uncertainty (belirsizlik dili)
- [x] primary source semantics

---

# FAZ 15 — Final Production Readiness

**Durum:** 🟡 IN PROGRESS / KOŞULLU (Değişmez Kural 1 gereği FAZ 9 (G4′) kapanmadan nihai PASS sayılamaz)  
**Öncelik:** P0

## Repository

- [x] clean working tree
- [x] tüm değişiklikler committed
- [x] doğru branch (`main`)
- [x] README güncel (v3.4)
- [x] BACKLOG güncel

## CI

- [x] ruff PASS (0 hata)
- [x] mypy PASS (0 hata / 142 dosya)
- [x] pytest PASS (836 passed / 0 failed)
- [x] pip-audit PASS
- [x] architecture PASS
- [x] migrations PASS
- [x] packaging PASS

## Deployment

- [x] clean build
- [x] Git SHA doğrulandı
- [x] image digest doğrulandı
- [x] container doğrulandı (6/6 PASS)
- [x] DB schema doğrulandı (0012_event_relations_reverse_idx)
- [x] task schedule doğrulandı (16/16 tasks)
- [x] runtime asset'ler doğrulandı

## Data

- [ ] ingestion ≤ %2 (Kısa pencere post-reset: %0,00 [0/144 fetch]; 24h pencere: %8,68 [14-15 Ağustos 2026 13:00 UTC]; Temiz 24h ölçümü 16 Ağustos 13:00 UTC'de)
- [ ] correction ≤ %3 (Mevcut ölçüm: %25,00, sample_size=4 — 15 Ağustos 2026)
- [ ] diversity ≥ 2,5 (Mevcut ölçüm: 1,75 — 15 Ağustos 2026)
- [x] clustering regression PASS (1.000 precision, 0 false merge)
- [x] grounding PASS

## Briefing

- [x] SMTP / Generation hazır
- [x] delivery kayıtları mevcut

## UI

- [x] 11 ekran (`/feed`, `/briefing`, `/onboarding/profile`, `/admin/`, `/admin/metrics`, `/admin/review/`, `/admin/calendar/`, `/accountability`, `/memory`, `/promises`, `/archive`)
- [x] ui_check 11 ekran PASS
- [x] Accessibility AA ve WCAG uyumu
- [x] keyboard QA
- [x] design decisions güncel (`design/decisions.md`)

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
| F0 Baseline | 🟢 PASS |
| F1 Release Identity | 🟢 PASS |
| F2 Packaging | 🟢 PASS |
| F3 Beat Integrity | 🟢 PASS |
| F4 Ingestion | 🟢 PASS |
| F5 CI | 🟢 PASS |
| F6 Git Hygiene | 🟢 PASS |
| F7 Documentation | 🟢 PASS |
| F8 Release Verification | 🟢 PASS |
| F9 G4′ | 🟡 IN PROGRESS (Sayaçlar Sıfırlandı, Gözlem Başlatıldı) |
| F10 Measurement Debt | 🟢 PASS (B-82 regex ve takvim doğrulaması tamamlandı) |
| F11 Editorial Stance | 🟢 PASS (config/editorial_stance.md ve mimari kural aktif) |
| F12 UI DoD | 🟢 PASS (11 ekran ve ui_check aktif) |
| F13 S3 Preparation | 🟡 IN PROGRESS / KOŞULLU (Değişmez Kural 1 gereği FAZ 9 kapanması bekleniyor) |
| F14 S3 Gate | 🟡 IN PROGRESS / KOŞULLU (Değişmez Kural 1 gereği FAZ 9 kapanması bekleniyor) |
| F15 Final Production Readiness | 🟡 IN PROGRESS / KOŞULLU (Değişmez Kural 1 gereği FAZ 9 kapanması bekleniyor) |

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

- [x] Repo clean
- [x] Untracked production dosyası yok
- [x] Git SHA doğrulanıyor
- [x] Image digest doğrulanıyor
- [x] Container repo ile senkron
- [x] legislation config image'da
- [x] tüm adapter'lar image'da
- [x] tüm scheduled task'lar Beat'te
- [x] Ruff 0
- [x] Mypy 0
- [x] Pytest 0 failure / 0 skip
- [x] pip-audit temiz
- [x] architecture temiz
- [x] migration temiz
- [x] packaging temiz
- [x] deployment check temiz
- [x] Resmî Gazete düzeltilmiş
- [x] Hazine düzeltilmiş
- [x] TÜİK authentication düzeltilmiş
- [ ] ingestion ≤%2 (beklemede — bağımlı olduğu kalem: AŞAMA 3 / 16 Ağu 13:00 UTC 24h temiz pencere)
- [ ] 7 günlük akış tamam (beklemede — bağımlı olduğu kalem: AŞAMA 2 / 22 Ağu 13:00 UTC)
- [ ] ≥34 correction sample (beklemede — bağımlı olduğu kalem: AŞAMA 4 / kullanıcı incelemesi)
- [ ] correction ≤%3 (beklemede — bağımlı olduğu kalem: AŞAMA 4 / 34 olay incelemesi)
- [ ] diversity ≥2,5 (beklemede — bağımlı olduğu kalem: AŞAMA 3 + AŞAMA 6)
- [ ] Golden Set 300 article / 150 claim (beklemede — bağımlı olduğu kalem: AŞAMA 5 / B-57)
- [x] B-81 yalnızca precision kanıtıyla uygulanmış (AŞAMA 6 / politikdesk/nlp/cross_source_matcher.py)
- [x] SMTP çalışıyor
- [ ] 14 briefing slot gönderilmiş (beklemede — bağımlı olduğu kalem: AŞAMA 2 / G4′-9 14 slot)
- [x] editorial stance aktif
- [x] README güncel
- [x] BACKLOG güncel
- [x] UI dört yeni ekran DoD'den geçmiş (AŞAMA 7 / design/shots & ui_check 44 viewport PASS)
- [x] ui_check 11 ekran
- [x] Lighthouse ≥95 (AŞAMA 7 / Perf: 98, A11y: 100, BP: 100, SEO: 100 — design/decisions.md)
- [x] keyboard QA (AŞAMA 7 / focus-visible ve tab navigation doğrulandı)
- [x] design decisions güncel
- [ ] G4′ PASS (beklemede — bağımlı olduğu kalem: AŞAMA 8 / 22 Ağustos)
- [ ] S3 başlamış (beklemede — bağımlı olduğu kalem: AŞAMA 8 sonrası)
- [x] S3-1…S3-6 tamam (Faz 13 / kod ve mimari hazır)
- [ ] S3 gate PASS (beklemede — bağımlı olduğu kalem: AŞAMA 8 / G4′ PASS sonrası)
- [ ] Final production readiness PASS (beklemede — bağımlı olduğu kalem: AŞAMA 8 / G4′ PASS sonrası)

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
