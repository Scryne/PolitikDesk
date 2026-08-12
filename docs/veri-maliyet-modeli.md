# Veri ve Maliyet Modeli

**Görevler:** F0-06 (X API fiyatlandırması), F0-07 (LLM + embedding + altyapı)
**Kapı koşulu:** G0 #8 · **Karar:** D19 (fiyatlandırma) · **Risk:** R6
**Hesaplayıcı:** `scripts/cost_model.py` — `make cost` · **CSV:** `veri-maliyet-modeli.csv`

> Bu belge bir tablo değil, **çalıştırılabilir bir modeldir.** Fiyat veya
> varsayım değiştiğinde `scripts/cost_model.py` içindeki `Assumptions`
> güncellenir ve model yeniden koşulur. LLM fiyatları tek kaynaktan
> (`politikdesk/llm/pricing.py`) okunur — iki yerde tutulmaz.

---

## Sonuç (12 Ağustos 2026 koşumu)

### Sabit maliyetler — tüm kullanıcılar arasında paylaşılır

| Kalem | Model | $/ay |
|---|---|---|
| İddia çıkarımı | claude-sonnet-5 | 20,81 |
| Olay özetleme | claude-sonnet-5 | 11,70 |
| Embedding | 0,06 $/M token | 0,19 |
| Altyapı (VPS + yedek + izleme) | — | 38,00 |
| **TOPLAM SABİT** | | **70,71** |

### Değişken maliyetler — kullanıcı başına

| Kalem | Model | $/kullanıcı/ay |
|---|---|---|
| Taslak üretimi | claude-opus-5 | 3,24 |
| Brifingler | claude-sonnet-5 | 0,72 |
| **TOPLAM DEĞİŞKEN** | | **3,96** |

### Kullanıcı başına aylık maliyet

| Kullanıcı | $/kullanıcı/ay | Toplam $/ay | Hedef ≤ 8 $ |
|---|---|---|---|
| **8 (kapalı beta)** | **12,80** | 102,39 | ✗ |
| 10 | 11,03 | 110,31 | ✗ |
| 18 (başabaş) | 7,89 | 142,04 | ✓ |
| 100 | 4,67 | 466,71 | ✓ |
| 1000 | 4,03 | 4.030,71 | ✓ |

---

## ⚠️ Bulgu: hedef beta ölçeğinde tutmuyor

**Başabaş noktası ~18 kullanıcıdır.** Kapalı beta 8 kullanıcı ile
planlandığı için (F4-17), G0 koşul 8 ve G4 koşul 7 mevcut haliyle
**beta boyunca sağlanamaz.**

Bu bir model hatası değil, ürünün gerçek ekonomisidir: ingestion, embedding,
kümeleme ve özetleme maliyeti **kullanıcı sayısından bağımsızdır**. 8
kullanıcıya bölününce kişi başına 8,84 $ yalnızca sabit taraftan gelir.

**Önerilen düzeltme** *(`docs/karar-itirazlari.md` İtiraz-1, `BACKLOG.md` B-35)*:

Kapı koşulu ikiye ayrılsın:

- **Birim ekonomi hedefi:** 100 aktif kullanıcı ölçeğinde ≤ 8 $/kullanıcı/ay
  → **✓ sağlanıyor (4,67 $)** — ürünün ölçeklenebilirlik kanıtı
- **Beta bütçe tavanı:** kapalı beta boyunca toplam aylık maliyet ≤ 150 $
  → **✓ sağlanıyor (102 $)** — nakit gerçekliği

Bu ayrım olmadan kapı ya otomatik olarak tutmaz ya da "öngörü" kelimesine
sığınılarak geçilir; ikisi de kötüdür.

**Fiyatlandırmaya (D19) etkisi:** Fiyat, **100 kullanıcı ölçeğindeki**
birim maliyete göre belirlenir (4,67 $ ≈ 190 TL/ay maliyet tabanı), beta
ölçeğindekine göre değil. Rakip analizi kullanıcının zaten $8–20/ay
mertebesinde ödeme yaptığını gösteriyor — marj mevcut.

---

## Varsayımlar

`scripts/cost_model.py` → `Assumptions`. Her biri değiştirilebilir;
model otomatik yeniden hesaplar.

### Hacim

| Varsayım | Değer | Gerekçe |
|---|---|---|
| Makale/gün | 200 | 8 kaynak × ~25 yayın/gün |
| Olay/gün | 35 | ~5–6 makale bir olayda birleşir |
| Tekrar oranı | %25 | Ajans kopyası + tam tekrar; LLM'e gitmez |

> **Tekilleştirme doğrudan maliyet azaltımıdır.** F1-10 ve F1-11 çalışmazsa
> çıkarım maliyeti ~%33 artar. Bu, `tests/test_cost_model.py` ile de
> gösterilmiştir.

### LLM kullanımı

| Varsayım | Değer | Gerekçe |
|---|---|---|
| Çıkarım modeli | claude-sonnet-5 | Ucuz model ile çıkarım (Spec §11.5, R6 azaltımı) |
| Üretim modeli | claude-opus-5 | Pahalı model yalnızca taslak üretiminde |
| Makale başına girdi | 1.200 token | başlık + lead + prompt |
| Makale başına çıktı | 400 token | yapılandırılmış iddia JSON'u |
| Önbellek isabet oranı | %85 | statik sistem promptu önbellekten okunur |
| Olay başına girdi/çıktı | 3.000 / 500 | kanıt listesi → TL;DR + ne biliyoruz/bilmiyoruz |

> **Prompt önbelleği önemli bir kalemdir:** %85 isabetle çıkarım maliyeti
> yaklaşık üçte bir oranında düşüyor. Bu, sistem promptunun **dondurulmuş**
> tutulmasını gerektirir — içine tarih/kullanıcı adı gibi değişken bir şey
> yazılırsa önbellek her çağrıda geçersizleşir ve maliyet sessizce artar.

### Kullanıcı başına kullanım

| Varsayım | Değer | Gerekçe |
|---|---|---|
| Taslak/ay | 60 | ~2/gün |
| Yeniden üretim oranı | %35 | taslakların bir kısmı bir kez yeniden üretilir |
| Taslak girdi/çıktı | 4.000 / 800 | kanıt seti + editoryal profil bloğu |
| Brifing/ay | 60 | sabah + akşam × 30 gün |
| Brifing girdi/çıktı | 2.500 / 700 | ilk 5–7 olay |

### Embedding

| Varsayım | Değer | Not |
|---|---|---|
| Fiyat | 0,06 $/M token | **F0-13 sonucuna göre güncellenecek** |
| Token/makale | 700 | başlık + lead |

> Embedding, toplam maliyetin **%0,3'ünden azı**. Bu, F0-13'te modeli
> **fiyata göre değil kaliteye göre** seçmeyi mümkün kılar — self-host
> seçeneğinin operasyon yükünü haklı çıkaracak bir tasarruf yok.
> Bu, benchmark kararı için önemli bir girdidir.

### Altyapı

| Kalem | $/ay |
|---|---|
| VPS (Hetzner/DO sınıfı) | 30,00 |
| Yedekleme + izleme (Sentry, uptime) | 8,00 |

---

## X API — F0-06

**MVP'de maliyet: 0 $.**

Spec §9.4 / D7 gereği X API kullanılmıyor. MVP'de X entegrasyonu:

| | |
|---|---|
| ❌ X API ile okuma | Kullanılmaz |
| ❌ Resmî API dışı otomasyon | Hiçbir fazda kullanılmaz |
| ✅ Kullanıcı-tetikli içe aktarma | Link yapıştırma → oEmbed/meta veri (F1-04) |
| ✅ Yayın köprüsü | Pano + X Web Intent — API gerektirmez |

### Faz 5 yeniden değerlendirmesi — açık kalem

Spec §9.4 doğrulama notu, v2'nin aktardığı rakamların (Şubat 2026 kullanım
bazlı faturalama, Enterprise eşiği aylık 42.000 $'dan başlıyor) **hızla
değişebileceğini** belirtiyor ve F0-06'da doğrudan geliştirici portalından
teyit edilmesini istiyor.

**Bu teyit yapılmamıştır** — canlı portal erişimi gerektirir.

| Senaryo | İzlenen hesap | Okuma/gün | $/ay | Teyit |
|---|---|---|---|---|
| Dar | 10 | — | ☐ | ☐ |
| Orta | 50 | — | ☐ | ☐ |
| Geniş | 165 | — | ☐ | ☐ |

**Yapılması gereken (~30 dk):** X geliştirici portalından güncel katman ve
fiyatları al, `scripts/cost_model.py` → `Assumptions.x_api_scenarios`
alanına işle, modeli yeniden koş.

**MVP kararına etkisi: yok.** API zaten kullanılmıyor (Spec §9.4:
"MVP kararı bu rakamlardan bağımsız olarak geçerlidir"). Bu rakamlar
yalnızca `BACKLOG.md` B-17/B-18'in (yarı-otomasyon, X API okuma) giriş
koşulunu değerlendirmek için gerekir.

---

## Maliyet kontrol mekanizmaları (uygulanmış)

Risk R6 ("LLM maliyeti öngörülemez büyür") azaltımları — Faz 0'da kod
seviyesinde hazır:

| Mekanizma | Nerede | Durum |
|---|---|---|
| Her çağrının token/maliyeti kaydediliyor | `llm_calls` tablosu | ✅ |
| Günlük bütçe tavanı → `BudgetExceeded` | `llm/budget.py` | ✅ |
| Aylık bütçe tavanı | `llm/budget.py` | ✅ |
| %80'de uyarı logu | `llm/budget.py` | ✅ |
| Tahmini maliyet çağrı öncesi kontrole dahil | `BudgetGuard.check()` | ✅ |
| Bilinmeyen model sessizce 0 maliyet üretmiyor | `pricing.py` → `UnknownModelError` | ✅ |
| Ucuz model / pahalı model ayrımı | `config.py` | ✅ |
| Prompt önbelleği | `llm/client.py` (`cache_control`) | ✅ |
| Tavanda üretim durur, ingestion devam eder | `BudgetExceeded` docstring'i | ✅ tasarım · ⏳ F4-07'de tam uygulama |
| %80'de uyarı **e-postası** | — | ⏳ F4-07 |

---

## Duyarlılık

Hangi varsayım yanlışsa ne olur:

| Varsayım 2× artarsa | Kullanıcı başına etki (100 kullanıcı) |
|---|---|
| Makale/gün (200 → 400) | +0,33 $ — sabit taraf, dağılıyor |
| Taslak/ay (60 → 120) | **+3,24 $** — en duyarlı kalem |
| Taslak token'ları | +3,24 $ |
| Tekrar oranı %25 → %0 | +0,07 $ |
| VPS maliyeti | +0,30 $ |

**Sonuç:** Model **taslak üretim hacmine** duyarlıdır, ingestion hacmine
değil. Kullanıcı günde 4 taslak üretirse birim maliyet ~7,9 $'a çıkar ve
hedef 100 kullanıcı ölçeğinde bile sınıra dayanır.

**Bu, bir ürün kararına dönüşür:** Ücretlendirme katmanlarında (B-19)
taslak sayısı bir kota olarak tanımlanmalıdır — sınırsız taslak birim
ekonomiyi öngörülemez kılar. Ayrıca "yeniden üret" butonu ücretsiz
görünse de en pahalı etkileşimdir; F3-14'te kullanıcıya sayaç gösterilmesi
düşünülebilir.

---

## Modeli yeniden koşma

```bash
make cost
# veya
python -m scripts.cost_model --csv docs/veri-maliyet-modeli.csv
```

Aylık maliyet incelemesi ritüelinde (Yol Haritası §3, Faz 1'den itibaren
aylık 30 dk) bu model gerçek `llm_calls` verisiyle karşılaştırılır.
Sapma %30'u aşarsa varsayımlar güncellenir.
