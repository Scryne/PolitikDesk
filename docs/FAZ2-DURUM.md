# Faz 2 — Durum Panosu

**Faz:** Olay Zekâsı · **Plan:** W8–W12 · 25 PD
**Son güncelleme:** 12 Ağustos 2026 (akşam: doğrulama denetimi)

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
| F2-06 | İddia çıkarım promptu + şema | ✅ | `nlp/claims.py`, `prompts/claims.v2.md` — belge/kod eşitliği artık testle korunuyor |
| F2-07 | İddia tipi sınıflandırma | 🟡 | **Canlı koşuldu** (13 Ağu, D17 modeli): 9 olay, 0 hata, alıntı sadakati %100. %90 DoD'nin *sayısal* ölçümü hâlâ Golden Set hacmine bağlı (B-57) |
| F2-08 | Sayısal değer normalizasyonu | ✅ | 21 metrik, ISO dönem doğrulaması (yarıyıl dahil); eval: **1,000** |
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

### 3. ~~Kalan precision açığının tamamı varlıksız makalelerden geliyor~~ — **bu teşhis yanlıştı**

> **Düzeltme (12 Ağustos 2026, akşam denetimi).** B-56 uygulandıktan sonra
> ölçüldü: teşhis tutmuyor. Aşağıdaki özgün metin kayıt için bırakıldı.

Özgün teşhis şuydu: *55 makalenin 21'inde (%38) tanınan varlık yok; bu
makalelerde varlık kısıtı uygulanamıyor (`inconclusive` yolu) ve
precision'ı taşıyan tek şey benzerlik kalıyor. Varlık sözlüğü kapsamı
(B-56) genişletilirse `inconclusive` yolu boşalır.*

**Ölçülen sonuç.** Sözlük 20 → 48 kuruma çıkarıldı (bakanlıklar,
düzenleyici kurullar, kamu bankaları). Varlıksız oran %38 → **%29**'a
indi. Kümeleme metrikleri **hiç değişmedi**:

| | B-56 öncesi | B-56 sonrası |
|---|---|---|
| Pairwise precision | 0,875 | 0,875 |
| Recall | 0,824 | 0,824 |
| False merge | 0,026 | 0,026 |
| Denetime düşen | 7/55 | 7/55 |

**Gerçek kök neden.** Yanlış eşleşen 4 çiftin tamamı **tek bir karışık
kümeden** (küme 26) geliyor ve varlıksızlıkla ilgisi yok:

```
"TÜİK haziran ayı dış ticaret endekslerini açıkladı"     [varlık VAR: TÜİK]
"Sanayi Üretimi Haziran'da yıllık yüzde 1,4 azaldı"      [aynı olay değil]
```

İkisi de TÜİK'in **aynı gün** yayımladığı **farklı göstergeye** ait
bültenler. Varlık kümeleri **özdeş** olduğu için varlık kısıtı bunları
ayıramaz — sözlüğü ne kadar genişletirsek genişletelim ayıramaz. Bu,
`docs/embedding-benchmark.md`'de tanımlanan **şablonlu resmî duyuru
ailesidir** (B-49): metin de varlıklar da aynıdır.

Doğru ilaç sözlük değil, **gösterge (metrik) ayırıcısıdır**: iki makale
farklı metrik taşıyorsa (dış ticaret endeksi ≠ sanayi üretimi) bu ayrı
olay kanıtıdır. `clustering/numeric_guard.py` metrik sözlüğü zaten var
ama şu an yalnızca *çelişki* işaretliyor, *ayırma* yapmıyor. Yeni kalem:
**B-62**.

**Yine de sistem doğru davranıyor:** bu 4 çiftin **dördü de denetim
kuyruğunda.** Otomatik precision 1,000 kalıyor — sistem bunu iddia
etmiyor, soruyor.

**B-56 neden yine de tutuldu:** varlık kapsamı salience'ın
`varlik_onemi` bileşenini ve gelecekteki veride `varlik_ok` kısıtını
besliyor; hiçbir regresyon üretmedi. Ama *precision açığının kök nedeni
değildi.*

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

> ⚠️ **Bu koşum `hashing` embedder ile yapılmıştı.** B-53 sonrası e5 ile
> yeniden koşuldu — aşağıya bakınız.

### e5 ile yeniden koşum (B-53, 12 Ağustos 2026 akşamı)

```
kümeleme : {'processed': 11, 'assigned': 2, 'created': 9, 'needs_review': 1, 'errors': 0}
kanıt    : {'claims_scored': 0, 'events_scored': 9, 'errors': 0}
bağlam   : {'events_processed': 9, 'relations_created': 1}
```

e5, hashing'in ayıramadığı bir çifti doğru birleştirdi (10 olay → **9**)
ve belirsiz bir atamayı denetim kuyruğuna gönderdi. Bağlam bağı aynı ve
doğru: Enflasyon Raporu 2026-III → 2026-II, benzerlik **0,953**.

Bu koşum **gizli bir Faz 2 hatasını ortaya çıkardı** (aşağıdaki tabloda
4 numara): `same_thread` eşiği hashing'in düşük benzerlik dağılımıyla
"çalışıyor gibi" duruyordu.

Merge/split geri alınabilirliği canlı doğrulandı: merge → undo → split →
undo turunda tüm durum bit düzeyinde geri geldi, her adımda merkez
`mean(members)` ile tutarlı kaldı.

### Canlı veride bulunan hatalar

| # | Hata | Belirti | Düzeltme |
|---|---|---|---|
| 4 | **`same_thread` eşiği (0,80) kalibrasyondan sonra güncellenmemiş** | e5'e geçince 9 olay **22** bağ üretti — "Ulaştırma yatırımı" ↔ "AR-GE harcaması" 0,884 | Eşik `cluster_t_high`'tan türetiliyor; 22 → **1** bağ (B-65) |
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

| İş | Efor | Durum |
|---|---|---|
| ~~Varlık sözlüğü kapsamı (B-56)~~ | 0,5 PD | ✅ 20 → 48 kurum; varlıksız %38 → %29. **Metrikleri değiştirmedi** |
| ~~Worker imajına `embed-local` (B-54)~~ | 0,5 PD | ✅ `ARG PD_EXTRAS` + CPU torch; konteynerde doğrulandı |
| ~~Makaleleri e5 ile yeniden embed et (B-53)~~ | 0,3 PD | ✅ Koşuldu; gizli bir eşik hatası yakalandı (B-65) |
| Gösterge ayırıcısı (B-62) | 1,0 PD | 🔴 **Yeni** — kalan precision açığının gerçek kök nedeni |
| Golden Set'i 300 makaleye çıkar (B-57) | 3–4 PD | 🔴 Ingestion birikimi bekliyor |
| Canlı LLM koşumu (B-58) | 0,2 PD | 🔴 `ANTHROPIC_API_KEY` bekliyor |
| Haftalık ritüel (B-59) | 3 hafta | 🔴 Takvim |
