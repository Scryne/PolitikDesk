# Faz 2 — Durum Panosu

**Faz:** Olay Zekâsı · **Plan:** W8–W12 · 25 PD
**Son güncelleme:** 12 Ağustos 2026

> **Fazın felsefesi:** Bu fazda hiçbir şey "iyi çalışıyor gibi" duruyor diye
> kabul edilmez. Her bileşen Golden Set'e karşı sayısal olarak ölçülür.

---

## Özet

**21 görevin 19'u tamamlandı**, 1'i kısmi, 1'i takvim zamanı bekliyor.
Kapı G2'nin 9 koşulundan **5'i sağlandı**, 2'si kısmi, 2'si veri bekliyor.

Fazın en önemli çıktısı kod değil **ölçüm**: eval koşucusu (F2-16) ilk
koşumunda kanıt motorunda gerçek bir hata yakaladı ve eşik kalibrasyonu
(F2-14) false merge oranını %10,7'den %2,6'ya indirdi.

---

## Görev durumu

### İş Kolu A — Olay Kümeleme

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F2-01 | Kümeleme algoritması v1 | ✅ | `clustering/assigner.py` + `repository.py` + `pipeline.py` |
| F2-02 | Olay merkezi güncelleme | ✅ | `clustering/centroid.py` — drift < 1e-9, geri alınabilir |
| F2-03 | Sayısal çelişki bayrağı | ✅ | `clustering/numeric_guard.py` — 11 metrik sözlüğü |
| F2-04 | İnsan denetim kuyruğu | ✅ | `/admin/review/` + `merger.review_queue` |
| F2-05 | Merge / Split kaçış valfleri | ✅ | `clustering/merger.py` — canlı doğrulandı |
| F2-14 | Eşik kalibrasyonu (D20) | ✅ | `eval/threshold_report.md` — **0,92 / 0,88** |

### İş Kolu B — İddia Çıkarımı

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F2-06 | İddia çıkarım promptu + şema | ✅ | `nlp/claims.py`, `prompts/claims.v1.md` |
| F2-07 | İddia tipi sınıflandırma | 🟡 | Kod + şema hazır; **%90 DoD ölçümü canlı koşum bekliyor** |
| F2-08 | Sayısal değer normalizasyonu | ✅ | 21 metrik, ISO dönem doğrulaması; eval: **1,000** |
| F2-09 | İddia tekilleştirme | ✅ | Sayısal iddiada imza = normalize değer |
| F2-10 | Kanıt eşleme + alıntı doğrulama | ✅ | `verify_quote` — uydurma alıntı reddediliyor |

### İş Kolu C — Kanıt Motoru (Deterministik)

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F2-11 | Bağımsız kanıt sayımı | ✅ | `evidence/independence.py` — Spec §8.2'nin **3 kuralı da** |
| F2-12 | Kural motoru R0–R7 | ✅ | `evidence/rules.py` — 8 kural, 8 test; CI'da LLM yasağı |
| F2-13 | `status_reason` üretimi | ✅ | Makine-okunur; R0'da kısa devre kaydı |
| F2-15 | Salience skoru | ✅ | `evidence/salience.py` — global 0–90 + kişisel 0–10 |

### İş Kolu D — Bağlam ve Takvim

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F2-17 | Tarihsel bağlam | ✅ | `context/related.py` → `same_thread` |
| F2-18 | ScheduledEvent + admin | ✅ | `/admin/calendar/` + `config/calendar_2026.yml` (17 kayıt) |
| F2-19 | Beklenen → gerçekleşen eşleştirme | ✅ | `context/scheduler_match.py` |

### İş Kolu E — Değerlendirme

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F2-16 | Eval koşucusu | ✅ | `eval/run.py` + `eval/eval_report.md` |
| F2-20 | Golden Set (300 makale + 150 iddia) | 🟡 | **55 makale + 24 iddia** — gerçek veri, hedefin altında |
| F2-21 | Haftalık kalite ritüeli (≥3 hafta) | 🔴 | **Takvim zamanı gerektirir** — kodla kapatılamaz |

---

## Kapı G2 — ölçülen durum

`python -m eval.run` · 55 makale · 36 gerçek olay · 24 iddia

| # | Koşul | Hedef | Ölçülen | Durum |
|---|---|---|---|---|
| 1 | Kümeleme precision | ≥ %90 | **%87,5** | 🟡 |
| 2 | Kümeleme recall | ≥ %80 | **%82,4** | ✅ |
| 3 | **Yanlış birleştirme** | ≤ %5 | **%2,6** | ✅ **pazarlıksız koşul tutuyor** |
| 4 | `evidence_status` doğruluğu | ≥ %95 | **%100** | ✅ |
| 5 | Uydurulmuş iddia oranı | ≤ %2 | — | ⏳ canlı LLM koşumu yok |
| 6 | Sayısal normalizasyon | ≥ %95 | **%100** | ✅ |
| 7 | `evidence/` içinde LLM çağrısı | 0 | **0** | ✅ CI + AST testi |
| 8 | Merge/split geri alınabilir | %100 | **%100** | ✅ canlı + test |
| 9 | Haftalık ritüel | ≥3 hafta | 0 | 🔴 takvim |

**Ek ölçüm: otomatik precision %100.** Sistemin denetim kuyruğuna
sormadan verdiği kararların hiçbiri yanlış değil. Belirsizlik doğru yere
yönlendiriliyor: 55 makalenin 7'si (%13) denetime düşüyor.

**Kapı durumu: 🟡 AÇILMADI.** Koşul 1 sınırda, 5 ve 9 ölçülemedi.
Ayrıntı aşağıda.

---

## Fazın bulguları

### 1. Eval koşucusu kanıt motorunda gerçek bir hata yakaladı

İlk koşumda `gc-024` uyuşmadı: ajans haberi ile **aynı yayın grubundaki**
kopyası iki bağımsız kaynak sayılıyordu.

Bu, Faz 1'de yakalanan hatanın **ikinci biçimiydi.** Faz 1'de kopya
simhash ile tespit ediliyordu ve ajansın anahtarını `wire:<slug>` olarak
sabitlemek çözüyordu. Kopya *yayın grubuyla* eşleştiğinde aynı çözüm
hatayı geri getiriyordu: ajans `wire:aa-ekonomi`, kopyası `grp:wire-aa`.

Düzeltme: yayın grubu her zaman öncelikli (Spec §8.2 kural 1), ajans
dahil. Simhash kopyası da ajansın **gerçek anahtarını** miras alır.
`evidence_status` doğruluğu %95,8 → **%100**.

> Bu tam olarak F2-16'nın var olma sebebidir. Hata birim testlerinde
> görünmüyordu çünkü testler kendi kurdukları senaryoyu doğruluyordu;
> Golden Set gerçek kaynak kompozisyonunu getirdi.

### 2. Eşik kalibrasyonu false merge'ü dörtte bire indirdi

Spec §11.4'ün tahminleri (0,86 / 0,78) Golden Set üzerinde false merge
%10,7 veriyordu — G2'nin pazarlıksız koşulu tutmuyordu.

| | 0,86 / 0,78 | **0,92 / 0,88** |
|---|---|---|
| Pairwise precision | 0,515 | **0,875** |
| False merge | 0,107 ❌ | **0,026** ✅ |
| Denetime düşen | 14/55 | **7/55** |

Ayrıntı ve tarama tabloları: `eval/threshold_report.md`.

### 3. Kalan precision açığının tamamı varlıksız makalelerden geliyor

55 makalenin **21'inde** (%38) tanınan varlık yok. Bu makalelerde varlık
kısıtı uygulanamıyor (`inconclusive` yolu) ve precision'ı taşıyan tek
şey benzerlik kalıyor.

Eşik ayarıyla kapatılacak bir açık değil: varlık sözlüğü kapsamı sorunu
(B-56). Bakanlıklar, kurullar ve şirket adları sözlüğe girdiğinde
`inconclusive` yolu boşalır.

### 4. Ölçümün kendisi iki farklı soruyu ayırmalı

Koşucu precision'ı iki kez raporlar:

* **Pairwise precision** — denetim kuyruğu hiç işlenmemişken kalan durum
* **Otomatik precision** — sistemin *sormadan* verdiği kararların kalitesi

Denetim kuyruğuna düşen bir atama sistemin iddiası değil, sorusudur.
Bu ayrım yapılmadan ölçülen precision (0,515) sistemi haksız yere
suçluyordu; otomatik precision 0,950 idi.

---

## Canlı doğrulama (12 Ağustos 2026)

11 gerçek makale üzerinde uçtan uca:

```
kümeleme : {'processed': 11, 'assigned': 1, 'created': 10, 'errors': 0}
kanıt    : {'claims_scored': 0, 'events_scored': 10, 'errors': 0}
bağlam   : {'events_processed': 10, 'relations_created': 1}
takvim   : 17 kayıt yüklendi
```

Bağlam bağı doğru: Enflasyon Raporu 2026-III → 2026-II (`same_thread`).

Merge/split geri alınabilirliği canlı doğrulandı: merge → undo → split →
undo turunda tüm durum bit düzeyinde geri geldi, her adımda merkez
`mean(members)` ile tutarlı kaldı.

### Canlı veride bulunan hatalar

| # | Hata | Belirti | Düzeltme |
|---|---|---|---|
| 1 | **`SET LOCAL hnsw.ef_search = %s` çalışmıyor** | 11 makalenin 11'i düştü | Postgres'te `SET` bind parametresi kabul etmez → `set_config(...)` |
| 2 | **Varlıksız makaleler hiç kümelenemiyor** | 0,9997 benzerlikli aynı olay ayrı düştü | `jaccard(∅,∅)=0`; kısıt üç durumlu yapıldı |
| 3 | **Ajans ile grup kopyası ayrı sayılıyor** | `gc-024` eval uyuşmazlığı | Yayın grubu önceliği (yukarıda) |

> 1 numaralı hata bir **Faz 1** hatasıydı: `nlp/search.py` F1-14'te
> "✅ doğrulandı" işaretlenmişti ama kod yolu canlı veritabanına karşı hiç
> koşmamıştı.

---

## Tasarım kararları ve gerekçeleri

| Karar | Alternatif | Gerekçe |
|---|---|---|
| Karar mantığı **saf** (`decide()` DB'ye dokunmaz) | Repository içinde karar | F2-14'ün 15 eşik denemesi saniyeler sürüyor; DB'ye bağlı olsa pratikte koşulamazdı |
| Merkez **normalize edilmemiş** ortalama | Her adımda L2 normalize | `centroid = mean(members)` bozulursa `remove_member` bozulur ve merge/split geri alınamaz (G2 #8) |
| Merge/split'te merkez **yeniden hesaplanır** | Artımlı düzeltme | Birkaç turdan sonra kayan nokta birikimi; yeniden hesaplama özdeşliği tazeler |
| Varlık kısıtı **üç durumlu** | İki durumlu (Spec §11.4 harfiyen) | Boş küme çelişki kanıtı değil, kanıt yokluğudur; harfiyen uygulama recall'ı öldürüyordu |
| Sayısal çelişki **atamayı engellemez**, işaretler | Ayrı olay saymak | Çelişki "farklı olay" demek değil, "biri yanlış olabilir" demektir |
| İddia çıkarımı **olay bazlı** koşar | Makale bazlı | F2-09 tekilleştirmesi olayın tüm makaleleri görülmeden yapılamaz |
| Çıktı şeması `evidence_status`'u **kabul etmez** | Prompt'ta yasaklamak | Prompt talimatı yeterli değil (Spec §11.5); şema + ikinci savunma hattı |
| Alıntı kaynak metinde **programatik doğrulanır** | Modele güvenmek | Uydurma alıntı sessizce kanıt olurdu |
| `same_thread` dışındaki ilişkiler **otomatik kurulmaz** | `updates`/`contradicts` de üretmek | O ikisi **yargı** içerir; `same_thread` yalnızca benzerlik gözlemidir (P4) |
| Takvim **elle** girilir | Kazıyıcı yazmak | TÜİK takvimi JS ile yükleniyor ve yılda bir değişiyor; 12 aylık liste kırılgan kazıyıcıdan ucuz |
| Takvim eşleştirmesinde **kaynak koşulu zorunlu** | Yalnız zamana bakmak | Aynı saatte gelen alakasız haber bağlanırdı |

---

## Açık kalan üç kalem

### F2-20 — Golden Set hedefin altında (55/300 makale, 24/150 iddia)

Set **gerçek** veridir: TCMB duyuruları + 13 haber sitesinden verbatim
toplandı, olay etiketleri `pairs_tr.jsonl`'deki elle verilmiş "aynı olay"
etiketlerinin geçişli kapanışından türetildi (çelişki kontrolü geçti).
İddia setinin beklenen durumları Spec §8.3 **elle uygulanarak** verildi —
kural motorunun çıktısından türetilmedi.

300 makaleye çıkmak için ingestion'ın haftalarca birikmesi gerekir; 11
makalelik canlı veritabanından üretilemez.

**Etkisi:** G2 koşul 3 (false merge ≤ %5) bu boyutta *karara bağlanamaz.*
36 olay / ~37 küme varken tek bir karışık küme oranı 2,7 puan oynatıyor;
kapı 2 kümeye denk geliyor. Ölçüm bir **yön** gösterir, kapı kararı değil.

### F2-07 / G2 koşul 5 — canlı LLM koşumu yapılmadı

`ANTHROPIC_API_KEY` tanımlı değil. İddia çıkarımının **doğrulama
katmanları** sahte istemciyle test edildi (28 test), ama şu ikisi ölçüm
bekliyor:

* F2-07 DoD: 100 iddialık örnekte ≥%90 doğru tip
* G2 koşul 5: uydurulmuş/hatalı iddia oranı ≤ %2

Anahtar geldiğinde `make claims` yeterli.

### F2-21 — haftalık ritüel

≥3 hafta üst üste, haftada 10 olay denetimi. **Takvim zamanı gerektirir**;
kodla kapatılamaz. Ritüelin aracı hazır (`/admin/review/`).

---

## Kalan iş

| İş | Efor | Not |
|---|---|---|
| Golden Set'i 300 makaleye çıkar (B-57) | 3–4 PD | Ingestion birikimi bekliyor |
| Varlık sözlüğü kapsamı (B-56) | 0,5 PD | Precision açığının kök nedeni |
| Makaleleri e5 ile yeniden embed et (B-53) | 0,3 PD | Mevcut veri `hashing` ile gömülü |
| Worker imajına `embed-local` (B-54) | 0,5 PD | torch + model ~2,5 GB |
| Canlı LLM koşumu | 0,2 PD | `ANTHROPIC_API_KEY` bekliyor |
| Haftalık ritüel | 3 hafta | Takvim |
