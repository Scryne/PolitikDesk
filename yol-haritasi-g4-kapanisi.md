# Yol Haritası — G4′ Kapanışı ve Belge/Gerçek Uyumu

**Kapsam:** 15 Ağustos 2026 tarihli ölçüm raporunda tespit edilen 24 kalemin tamamının kapatılması
**Başlangıç:** 15 Ağustos 2026, 13:00 UTC (G4′ sayacının sıfırlandığı an)
**Hedef kapanış:** 22 Ağustos 2026, 13:00 UTC (G4′-1 gözlem penceresinin dolduğu an) — bazı kalemler bu tarihten sonra da devam eder
**Bu belge nedir:** Mevcut FAZ 1–15 numaralandırmasının **yerine geçmez**; onu tamamlayan, yürütmeye dönük bir kapanış planıdır. Her AŞAMA, kaynak rapordaki madde numaralarına (1–24) açıkça bağlanır.

---

## 0. Nasıl kullanılır

- Her AŞAMA: **Amaç → Bağımlılık → Görevler → Sorumlu → Çıkış Kriteri → İlgili Madde** düzeninde.
- Görev kutucukları (`[ ]`) elle işaretlenir; bu dosya `docs/` altına konup ilerledikçe commit'lenmelidir.
- "Sorumlu" sütunu üç değer alır: **Kullanıcı** (senin elle yapman gereken iş), **Sistem** (kod/otomasyon), **Takvim** (bekleme, iş gerektirmez).
- AŞAMA 0 ve 1 **bugün, bağımlılıksız** başlar. AŞAMA 2–4 **paralel** yürür. AŞAMA 8, tüm gözlem ve kullanıcı kalemleri kapanmadan başlayamaz (Değişmez Kural 1).

---

## 1. Kritik Yol Özeti

```
Gün 0 (15 Ağu)  ──┬── AŞAMA 0: Belge düzeltmeleri (madde 19-24)         [engelsiz, ~1-2 saat]
                  ├── AŞAMA 1: SMTP + ANTHROPIC_API_KEY + GIT_SHA        [engelsiz, kullanıcı işi]
                  ├── AŞAMA 4: Correction rate incelemesi BAŞLAR         [34 olay, kullanıcı işi, 7 gün sürebilir]
                  └── AŞAMA 5: Golden Set genişletme BAŞLAR              [en büyük kalem, paralel, 7+ gün]

Gün 1 (16 Ağu 13:00 UTC) ── AŞAMA 3: 24h ingestion penceresi doldu → ölçüm

Gün 0-7 (15-22 Ağu) ── AŞAMA 2: Günlük G4′ snapshot'ları + brifing teslim takibi

Gün 7 (22 Ağu 13:00 UTC) ── AŞAMA 8: G4′ resmi kapanışı → S3 kapısı açılabilir

Gün 7+ ── AŞAMA 6, 7, 9, 10: Koşullu/uzun soluklu kalemler
```

**En kısa yol:** AŞAMA 0 ve 1 bugün bitirilirse, AŞAMA 2-4 hiçbir ek gecikme yaratmadan 22 Ağustos'ta AŞAMA 8'i tetikler. AŞAMA 5 (Golden Set) bu takvimi **bloklamaz** ama AŞAMA 6 ve S3'ün tam anlamıyla güvenilir sayılması için gereklidir.

---

## AŞAMA 0 — Belge Düzeltmeleri (Gün 0, bağımlılıksız)

**Amaç:** Rapordaki "yanlış bitti" kayıtlarını (madde 19-24) düzeltip, sonraki kararların bozuk verandanlar üzerine kurulmasını önlemek.
**Bağımlılık:** Yok. Bu, tüm listenin en ucuz ve en acil kalemidir çünkü **kod değil, dosya düzenlemesi**.
**Sorumlu:** Sistem (Claude/geliştirici, dosya düzenleme ile)

| # | Görev | Dosya | İlgili Madde |
|---|---|---|---|
| [x] | FAZ 14/15'te "correction ≤%3" ve "diversity ≥2,5" kutularının işaretini geri al; yerine gerçek ölçüm değerlerini (%25, 1,75) ve ölçüm tarihini yaz | yol-haritası ana dosyası | 19 |
| [x] | FAZ 15'teki "ingestion %0,00 (0/320 fetch)" ifadesini kaldır; yerine hem kısa pencere hem 24h gerçek pencere (%8,68) değerini, ölçüm penceresinin başlangıç/bitiş saatiyle birlikte yaz | yol-haritası ana dosyası | 20 |
| [x] | FAZ 13/14/15 durumunu 🟢 PASS'tan 🟡 IN PROGRESS / KOŞULLU'ya çevir; not olarak "Değişmez Kural 1 gereği FAZ 9 (G4′) kapanmadan bu fazlar nihai PASS sayılamaz" ekle | yol-haritası ana dosyası | 21 |
| [x] | "Mevcut faz: Faz 7" ifadesini güncel duruma (FAZ 9 / G4′ gözlem aşaması) çevir | README.md | 22 |
| [x] | B-97 durumunu "implemented but not integrated" → "implemented and integrated (politikdesk/nlp/claims_pipeline.py:382)" olarak düzelt | BACKLOG.md | 23 |
| [x] | B-61 durumunu (🔴 BLOKE) ile roadmap'teki "FAZ 10'da takvimler doğrulandı" ifadesi arasındaki çelişkiyi çöz — hangisi doğruysa diğerini güncelle, ikisi de kalamaz | BACKLOG.md + yol-haritası | 23 |
| [x] | §21 Final Kontrol Listesi'nin 43 maddesini gözden geçir; şu an doldurulabilecek olanları işaretle, geri kalanını AŞAMA 10'a referans ver | yol-haritası ana dosyası | 24 |

**Çıkış Kriteri:** Yol haritası, README ve BACKLOG dosyalarındaki hiçbir ifade, bu raporun ölçüm tablosuyla çelişmiyor.

---

## AŞAMA 1 — Ortam ve Kimlik Yapılandırması (Gün 0, bağımlılıksız)

**Amaç:** Sonraki tüm aşamaları bloklayan üç yapılandırma açığını kapatmak.
**Bağımlılık:** Yok.
**Sorumlu:** Kullanıcı (anahtarlar/şifreler) + Sistem (build/deploy değişikliği)

| # | Görev | Sorumlu | İlgili Madde |
|---|---|---|---|
| [ ] | `PD_SMTP_HOST`, `PORT`, `USER`, `PASSWORD`, `FROM` değerlerini `.env`'e gir | Kullanıcı | 5 (G4′-9) |
| [ ] | Test maili gönder, teslim edildiğini doğrula | Kullanıcı | 5 (G4′-9) |
| [x] | Anthropic sağlayıcısı kullanıcı kararıyla iptal edildi; proje NVIDIA NIM API (`openai_compat`) üzerinde sabitlendi | Kullanıcı + Sistem | 6 (B-67/68), 7 (B-51) |
| [x] | Dockerfile/CI'a `GIT_SHA` build-arg'ı ekle; `check_deployment` script'ini `app_version` yanında `git_sha` eşitliğini de doğrulayacak şekilde genişlet | Sistem | 15 |
| [x] | Deploy sonrası 3 container'ın (`pd-api`, `pd-worker`, `pd-beat`) `/version` cevabında gerçek SHA döndürdüğünü doğrula | Sistem | 15 |

**Çıkış Kriteri:** `.env` içinde SMTP yapılandırması tamam, test maili ulaştı; `/version` üç container'da da `git_sha=unknown` yerine gerçek kısa SHA döndürüyor; LLM sağlayıcısı NVIDIA NIM API olarak tescillendi.

---

## AŞAMA 2 — G4′ Günlük Gözlem Döngüsü (Gün 0–7, takvim zamanı)

**Amaç:** G4′-1 (7 gün kesintisiz akış) ve G4′-9 (14 brifing slotu) için gerekli günlük kayıtları biriktirmek.
**Bağımlılık:** AŞAMA 1'in SMTP kısmı tamamlanmadan G4′-9 sayaç ilerlemez.
**Sorumlu:** Takvim (otomatik) + Sistem (script çalıştırma)

| # | Görev | Sıklık | İlgili Madde |
|---|---|---|---|
| [ ] | `scripts/g4_snapshot.py` çalıştır → `docs/G4-SNAPSHOTS.md`'e ekle (gerçek `git_sha` ile, AŞAMA 1 sonrası) | Günde 1 | 1 (G4′-1) |
| [ ] | 7. snapshot'a ulaşınca (22 Ağu) pencereyi "tamamlandı" olarak işaretle | Tek seferlik | 1 (G4′-1) |
| [ ] | Her brifing slotunda teslim durumunu logla (`send_error` alanı boş olmalı) | Slot başına | 5 (G4′-9) |
| [ ] | 14 slotun tamamı SMTP üzerinden başarıyla gönderildiğinde kapıyı kapat | Tek seferlik | 5 (G4′-9) |

**Çıkış Kriteri:** `docs/G4-SNAPSHOTS.md`'de 7 kayıt, hepsinde geçerli Git SHA; 14/14 brifing slotu `send_error=null` ile teslim edilmiş.

---

## AŞAMA 3 — Ölçüm Yeniden Doğrulamaları (Gün 1'den itibaren)

**Amaç:** Sıfırlama öncesi kirlenmiş pencerelerin yol açtığı yanıltıcı sonuçları, temiz pencerelerle değiştirmek.
**Bağımlılık:** 16 Ağustos 13:00 UTC'den önce anlamlı değil (tam 24h post-reset pencere gerekli).
**Sorumlu:** Sistem

| # | Görev | Ne zaman | İlgili Madde |
|---|---|---|---|
| [ ] | 16 Ağu 13:00 UTC sonrası toplama arıza oranını tam 24h pencerede yeniden hesapla, kaynak bazlı tabloyu üret | 16 Ağu 13:00 UTC+ | 2 (G4′-2), 20 |
| [ ] | Oran ≤%2 ise kapıyı kapat; değilse arızalı kaynakları izole edip kök nedeni raporla | 16 Ağu 13:00 UTC+ | 2 (G4′-2) |
| [x] | B-82 (tarih regex) değişikliği sonrası `eval/run.py`'ı yeniden koştur; precision (1.000), false merge (0) ve grounding hatası (%0) değerlerinin korunduğunu doğrula | Bugün mümkün | 3 (G4′-5/7/8) |
| [x] | Aynı koşuda diversity ratio'yu da yeniden ölç (bkz. AŞAMA 6) — B-82'nin etkisi henüz ölçülmedi | Bugün mümkün | 9 (G4′-4) |

**Çıkış Kriteri:** İngestion arıza oranı tam 24h temiz pencerede ölçülmüş ve raporlanmış; `eval/run.py` B-82 sonrası en az bir kez daha koşmuş ve üç metrik de korunmuş.

---

## AŞAMA 4 — Correction Rate Kapanışı (Gün 0–7, kullanıcı işi, paralel)

**Amaç:** G4′-3 kapısını (≤%3, ≥34 incelenmiş olay) kapatmak. Şu an: %25, sample_size=4.
**Bağımlılık:** Yok — bugün başlayabilir.
**Sorumlu:** Kullanıcı

| # | Görev | İlgili Madde |
|---|---|---|
| [x] | Correction rate takip ve olay listeleme aracını (`scripts/correction_report.py`, `pd correction`) hazırla | 4 (G4′-3) |
| [ ] | Feed'i düzenli kullanmaya başla (günlük hedef: ~5 olay/gün × 7 gün = 34+) | 4 (G4′-3) |
| [ ] | Her incelenen olay için doğru/yanlış geri bildirimini sisteme işle | 4 (G4′-3) |
| [ ] | 34. olaya ulaşıldığında correction_rate'i yeniden hesapla | 4 (G4′-3) |
| [ ] | Oran ≤%3 değilse, hangi olay tiplerinde hata yoğunlaştığını kategorize edip B-57/B-81 önceliklendirmesine girdi olarak kullan | 4 (G4′-3) |

**Çıkış Kriteri:** `sample_size ≥ 34` ve `correction_rate ≤ %3`. Değilse, kapı açık kalır ve neden dokümante edilir — kapı kapatılamıyor diye rakam gizlenmez.

**Not:** Bu, raporun kendi önerdiği en kısa kritik yolun ikinci ayağıdır; AŞAMA 1 (SMTP/API key) ile birlikte **bugün başlarsa** 22 Ağustos'ta G4′ tek seferde kapanabilir.

---

## AŞAMA 5 — Golden Set Genişletme (Paralel, en büyük tek kalem)

**Amaç:** B-57'yi (300 makale + 150 iddia) kapatmak. Şu an: 55 makale + 24 iddia (%18 / %16 tamamlanma).
**Bağımlılık:** Yok, ama G2 koşul 3, B-75, B-52 ve B-81 bu kaleme bağımlı — yani bu, zincirleme olarak en çok şeyi bloklayan madde.
**Sorumlu:** Kullanıcı + Sistem (etiketleme araçları varsa)

| # | Görev | İlgili Madde |
|---|---|---|
| [x] | Mevcut 55 makale + 24 iddia için etiketleme/doğrulama sürecini gözden geçir, tekrarlanabilir bir iş akışı tanımla | 8 (B-57) |
| [x] | Haftalık hedef belirle (örn. 35-40 makale/hafta → ~7 haftada 300'e ulaşma) | 8 (B-57) |
| [ ] | Her makale eklendiğinde iddia sayısını da orantılı artır (150/300 = ~0,5 iddia/makale oranını koru) | 8 (B-57) |
| [x] | İlerlemeyi haftalık olarak `docs/GOLDEN-SET-PROGRESS.md` kütüğünde logla | 8 (B-57) |

**Çıkış Kriteri:** 300 makale + 150 iddia, kalite kontrolünden geçmiş. Bu kalem G4′ pencresini bloklamaz ama AŞAMA 6 ve S3'ün üretim kapısı kalitesini garanti eder.

---

## AŞAMA 6 — Üretim Kapısı ve Diversity (Koşullu, Golden Set'e bağımlı)

**Amaç:** G4′-4 (diversity ≥2,5) ve B-75 (üretim örneklemi) kapılarını kapatmak.
**Bağımlılık:** B-75, AŞAMA 5'in kısmi ilerlemesine; G4′-4'ün B-81 dalı ise Golden Set precision ölçümüne bağımlı.
**Sorumlu:** Sistem + Kullanıcı (taslak üretimi için feed kullanımı)

| # | Görev | İlgili Madde |
|---|---|---|
| [ ] | AŞAMA 3'teki B-82 sonrası diversity ölçümünü değerlendir: ≥2,5 ise kapıyı kapat | 9 (G4′-4) |
| [ ] | ≥2,5 değilse B-81'i (kaynaklar arası iddia eşleştirme) devreye al — **ama önce** Golden Set üzerinde precision ölçülmeden production'a alma (yanlış teyit riski) | 9 (G4′-4) |
| [ ] | Taslak sayısını 17'den 40'a çıkar (feed kullanımı + AŞAMA 4 ile doğal olarak artacak) | 10 (B-75) |
| [ ] | 50 üretim örneği + 40 taslak eşiğine ulaşınca üretim kapısı örneklemini kapat | 10 (B-75) |

**Çıkış Kriteri:** Diversity ≥2,5 (ölçümle kanıtlanmış) VEYA B-81 devreye alınıp Golden Set precision'ı ile doğrulanmış; 50/40 örneklem eşiği dolu.

---

## AŞAMA 7 — Görsel ve Erişilebilirlik Doğrulama

**Amaç:** 4 yeni ekranın (hesap-sor, hafıza, vaatler, arşiv) DESIGN.md Bölüm 14 döngüsünden geçmesi, Lighthouse ve klavye gezinme testlerinin yapılması.
**Bağımlılık:** Yok — teknik olarak bugün başlayabilir, ancak ekranlar stabilse yapılmalı.
**Sorumlu:** Sistem/Tasarım

| # | Görev | İlgili Madde |
|---|---|---|
| [ ] | `design/shots/` içine 4 yeni ekranın (hesap-sor, hafıza, vaatler, arşiv) görüntülerini ekle | 16 |
| [ ] | DESIGN.md Bölüm 14 doğrulama döngüsünü bu 4 ekran için koştur | 16 |
| [ ] | Lighthouse'u en az bir kez çalıştır, sonuçları `design/decisions.md`'ye ekle | 17 |
| [ ] | Klavye gezinmesini elle test et, sonucu dokümante et | 17 |
| [ ] | `design/refs/` klasörünü doldur (şu an sadece README.md var) — CLAUDE.md bunu her UI görevinde zorunlu kılıyor | 18 |

**Çıkış Kriteri:** 4 ekran için görsel doğrulama kaydı var; Lighthouse skoru raporlanmış; klavye testi sonucu yazılı; `design/refs/` boş değil.

---

## AŞAMA 8 — G4′ Resmi Kapanışı ve S3 Kapı Geçişi (22 Ağustos 2026, 13:00 UTC)

**Amaç:** Değişmez Kural 1'i ("G4′ kapanmadan S3 başlamaz") fiilen sağlamak.
**Bağımlılık:** AŞAMA 2, 3, 4'ün tamamı yeşil olmalı. AŞAMA 5/6/7 **şart değil** ama güçlü tavsiye edilir.
**Sorumlu:** Sistem + Kullanıcı (onay)

| # | Kapı | Hedef | Kaynak |
|---|---|---|---|
| [ ] | G4′-1 · 7 gün kesintisiz akış | 7/7 snapshot, hepsi geçerli Git SHA ile | AŞAMA 2 |
| [ ] | G4′-2 · Toplama arıza oranı | ≤%2, tam 24h temiz pencerede | AŞAMA 3 |
| [ ] | G4′-3 · Correction rate | ≤%3, sample_size≥34 | AŞAMA 4 |
| [ ] | G4′-4 · Diversity ratio | ≥2,5 (veya B-81 ile telafi) | AŞAMA 6 |
| [x] | G4′-5/7/8 · Kümeleme + grounding | precision 1.000, false merge 0, grounding hatası %0 korunmuş | AŞAMA 3 |
| [ ] | G4′-9 · 14 brifing slotu | 14/14 SMTP ile teslim edilmiş | AŞAMA 2 |

**Görevler:**
- [ ] Yukarıdaki 6 kapının tamamını tek bir tabloda topla, tarih/saat ve Git SHA ile damgala
- [ ] FAZ 9'u 🟡 IN PROGRESS'ten 🟢 PASS'a çevir (yalnızca tüm kapılar yeşilse)
- [ ] FAZ 13/14/15'in AŞAMA 0'da geri alınan işaretlerini, artık gerçek veriyle destekleniyorsa yeniden işaretle
- [ ] S3 fazının resmen başladığını yol haritasında ilan et

**Çıkış Kriteri:** 6/6 G4′ kapısı yeşil, Git SHA ile ilişkilendirilmiş kanıtla birlikte. Değişmez Kural 1 artık gerçekten (belge üzerinde değil, ölçümle) sağlanıyor.

---

## AŞAMA 9 — S3 Sonrası Kalan Ölçüm Borçları

**Amaç:** G4′ kapanışını bloklamayan ama üretim güvenilirliği için gereken kalemleri kapatmak.
**Bağımlılık:** AŞAMA 8 önerilir ama zorunlu değil; B-63 kendi başına bağımsız çalışabilir.
**Sorumlu:** Sistem + Kullanıcı (B-63 kararı)

| # | Görev | İlgili Madde |
|---|---|---|
| [x] | B-69/B-52: Metrik seçim doğruluğu ve numeric_guard yanlış-pozitif oranı için ortak test seti, eşik değeri ve regresyon testi oluştur (`tests/test_claims_accuracy.py`) | 11 |
| [x] | B-46: Konu filtresi için Golden Set üzerinde precision/recall ve dikey izolasyon testleri oluştur (`tests/test_topic_filter.py`) | 12 |
| [ ] | B-63: Spec §11.4 değişikliği için önce **yazılı karar** al ve Spec sürümünü artır; ancak sonra kod yaz | 13 |
| [x] | B-59/B-76: Haftalık kalite ritüelini `docs/HAFTALIK-KALITE-RITUELI.md` rehberine dönüştür | 14 |
| [ ] | B-59/B-76: 7 gün üst üste brifing teslimini (AŞAMA 2'den bağımsız, uzun vadeli) takip et | 14 |

**Çıkış Kriteri:** B-69/B-52/B-46 için test setleri ve ölçüm sonuçları var; B-63 için yazılı karar + Spec sürüm artışı kayıtlı (kod öncesi); haftalık ritüel ≥3 hafta kesintisiz loglandı.

---

## AŞAMA 10 — Final Kontrol Listesi Kapanışı (§21, 43 madde)

**Amaç:** Yol haritasının §21 bölümündeki 43 boş kutunun tamamını, gerçek duruma göre doldurmak.
**Bağımlılık:** AŞAMA 0-9'un çoğu; bu aşama bir **toplama/senkronizasyon** adımıdır, yeni ölçüm üretmez.
**Sorumlu:** Sistem

| # | Görev | İlgili Madde |
|---|---|---|
| [ ] | 43 maddenin her birini gözden geçir, hangi AŞAMA'nın kanıtıyla doldurulabileceğini eşleştir | 24 |
| [ ] | Kanıtı olmayan maddeleri boş bırakmak yerine "beklemede — bağımlı olduğu kalem: X" şeklinde açıkça işaretle | 24 |
| [ ] | Listeyi tamamen doldur, tarih ve Git SHA ile damgala | 24 |

**Çıkış Kriteri:** 43/43 madde ya kanıtla dolu ya da açık bağımlılık notuyla işaretli — hiçbiri sessizce boş kalmıyor.

---

## 2. Genel İzleme Tablosu (Madde → Aşama Eşlemesi)

| Rapor Maddesi | Konu | Aşama | Durum |
|---|---|---|---|
| 1 | G4′-1 · 7 gün akış | AŞAMA 2 | 🟡 |
| 2 | G4′-2 · Arıza oranı ≤%2 | AŞAMA 3 | 🟡 |
| 3 | G4′-5/7/8 · Kümeleme/grounding regresyonu | AŞAMA 3 | 🟢 |
| 4 | G4′-3 · Correction rate ≤%3 | AŞAMA 4 | 🟡 |
| 5 | G4′-9 · 14 brifing slotu | AŞAMA 1 + 2 | 🔴 |
| 6 | B-67/68 · Sağlayıcı karşılaştırma | AŞAMA 1 | 🟢 |
| 7 | B-51 · LLM başlık üretimi | AŞAMA 1 | 🟢 |
| 8 | B-57 · Golden Set 300+150 | AŞAMA 5 | 🟡 |
| 9 | G4′-4 · Diversity ≥2,5 | AŞAMA 6 | 🔴 |
| 10 | B-75 · Üretim kapısı örneklemi | AŞAMA 6 | 🔴 |
| 11 | B-69/52 · Metrik doğruluğu | AŞAMA 9 | 🟢 |
| 12 | B-46 · Konu filtresi | AŞAMA 9 | 🟢 |
| 13 | B-63 · Kaynak entity sinyali | AŞAMA 9 | 🔴 |
| 14 | B-59/76 · Haftalık ritüel | AŞAMA 9 | 🟡 |
| 15 | Release identity / GIT_SHA | AŞAMA 1 | 🟢 |
| 16 | 4 ekran görsel doğrulama | AŞAMA 7 | 🔴 |
| 17 | Lighthouse + klavye testi | AŞAMA 7 | 🔴 |
| 18 | design/refs/ boş | AŞAMA 7 | 🔴 |
| 19 | Roadmap yanlış işaretli kutular | AŞAMA 0 | 🟢 |
| 20 | Ingestion %0,00 erken PASS | AŞAMA 0 + 3 | 🟡 |
| 21 | FAZ 13/14/15 vs FAZ 9 çelişkisi | AŞAMA 0 + 8 | 🟡 |
| 22 | README bayat faz bilgisi | AŞAMA 0 | 🟢 |
| 23 | BACKLOG B-97/B-61 çelişkisi | AŞAMA 0 | 🟢 |
| 24 | §21 Final Kontrol Listesi boş | AŞAMA 0 + 10 | 🟡 |

*(Durum sütunu elle güncellenir: 🔴 Başlanmadı · 🟡 Devam Ediyor · 🟢 Tamamlandı)*

---

## 3. Sorumluluk Özeti

| Kim | Ne yapmalı | Aşama |
|---|---|---|
| **Kullanıcı** | SMTP + ANTHROPIC anahtarlarını gir, test maili gönder | AŞAMA 1 |
| **Kullanıcı** | Günlük ~5 olay incele, 34'e ulaş | AŞAMA 4 |
| **Kullanıcı** | Golden Set için makale/iddia etiketleme sürecine katıl | AŞAMA 5 |
| **Kullanıcı** | B-63 için karar ver (spec değişikliği onayı) | AŞAMA 9 |
| **Sistem** | Belge düzeltmeleri, günlük snapshot, ölçüm yeniden çalıştırma, GIT_SHA stamping | AŞAMA 0, 1, 2, 3 |
| **Takvim** | 7 günlük pencerenin dolması | AŞAMA 2, 8 |

---

## 4. Bugün (15 Ağustos 2026) Yapılacaklar — Kısa Liste

1. [x] AŞAMA 0: Belge düzeltmelerinin tamamını bitir (~1-2 saat, engelsiz)
2. [ ] AŞAMA 1: SMTP + ANTHROPIC_API_KEY + GIT_SHA build-arg
3. [ ] AŞAMA 4'ü başlat: bugünden itibaren olay incelemeye başla
4. [ ] AŞAMA 5'i başlat: Golden Set için haftalık hedef belirle
5. [ ] AŞAMA 3: B-82 sonrası `eval/run.py`'ı bugün bir kez koştur (24h beklemeye gerek yok)

Bu 5 adım bugün tamamlanırsa, 22 Ağustos 13:00 UTC'de AŞAMA 8 hiçbir ek gecikme olmadan tetiklenir.
