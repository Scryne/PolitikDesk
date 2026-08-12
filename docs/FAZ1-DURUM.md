# Faz 1 — Durum Panosu

**Faz:** Veri Omurgası · **Plan:** W4–W7 · 20 PD
**Son güncelleme:** 12 Ağustos 2026

> **Fazın felsefesi:** Zekâ katmanı kirli veri üzerine kurulursa hata kaynağı
> ayırt edilemez. Önce boru hattı, sonra zekâ.

---

## Kapı G1 — Çıkış Koşulları

| # | Koşul | Ölçüt | Durum |
|---|---|---|---|
| 1 | Kaynakların tamamı otomatik akışta | 72 sa kesintisiz, kaynak başına ≥1 makale/gün | 🟡 **4/7 akışta** |
| 2 | Tekilleştirme çalışıyor | tam tekrar %0; ajans kopyası ≥%80 | 🟡 Mekanizma çalışıyor, **200 makalelik ölçüm yok** |
| 3 | Saklama politikası uygulanıyor | Tam metin yok; purge işi çalıştı | ✅ **Doğrulandı** |
| 4 | Embedding + ANN hazır | 10.000 makale embed; komşu sorgusu < 50 ms | 🟡 Hat çalışıyor, **D16 kararı ve hacim yok** |
| 5 | Varlık çıkarımı ≥%85 | 50 makalelik denetim örneği | 🟡 Mekanizma çalışıyor, **ölçüm yok** |
| 6 | Admin paneli kullanılabilir | Kaynak ekleme, makale inceleme, sağlık | ✅ **Doğrulandı** |
| 7 | Golden Set 200 makale | `golden_set_v1.jsonl` | 🔴 **0/200** |
| 8 | Sistem maliyeti öngörü içinde | Aylık altyapı + embedding hesaplanmış | ✅ **22,94 $/ay** |

**Kapı durumu: 🟡 KISMİ** — 3 koşul sağlandı, 4 kısmi, 1 açık.

Kalan koşulların tamamı **veri hacmi** veya **dış akış erişimi** bekliyor;
kod tarafında eksik yok.

---

## Görev durumu

### İş Kolu A — Toplama

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F1-01 | Kaynak adaptör arayüzü | ✅ | `ingestion/adapters/base.py` — protokol + kayıt + `FakeAdapter` |
| F1-02 | RSS adaptörü | ✅ | `adapters/rss.py` — RSS 2.0 + Atom, göreli link çözümü, hatada çökmüyor |
| F1-03 | Resmî kurum adaptörleri | 🟡 | `adapters/official.py` — TCMB RSS ✅; TÜİK/Hazine/RG akış bulunamadı |
| F1-04 | Manuel içe aktarma | ✅ | `adapters/manual.py` + `POST /ingest/link` — SSRF korumalı |
| F1-05 | 5 dakikalık toplama döngüsü | ✅ | `tasks.py` + Celery Beat |
| F1-06 | ToS koruması | ✅ | `ingestion/guard.py` — yasaklı/incelenmemiş kaynakta istisna |
| F1-07 | Kibarlık katmanı | ✅ | `ingestion/http.py` — UA, oran sınırı, robots, üstel geri çekilme |

### İş Kolu B — Normalizasyon ve Tekilleştirme

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F1-08 | Normalizasyon | ✅ | `normalizer.py` — kanonik URL, UTC, HTML entity, NFC |
| F1-09 | Alıntı + saklama politikası | ✅ | ≤300 kr alıntı, 30 gün TTL, DB CHECK ile zorlanıyor |
| F1-10 | Tam tekrar (`content_hash`) | ✅ | `dedup.py` — canlı veride 2 tekrar yakalandı |
| F1-11 | Yakın tekrar (`simhash`) | ✅ | `dedup.py` + `independence.py` — **iki sinyalli** |
| F1-12 | Otomatik purge işi | ✅ | `repository.purge_expired_bodies` + Celery Beat + `audit_log` |

### İş Kolu C — Gömme ve Varlıklar

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F1-13 | Embedding üretim işi | ✅ | `nlp/embedder.py` — 5 sağlayıcı + yerel yedek; Celery retry |
| F1-14 | pgvector ANN katmanı | ✅ | `nlp/search.py` — HNSW `ef_search` ayarı + gecikme ölçer |
| F1-15 | Varlık çıkarımı (NER) | ✅ | `nlp/entities.py` — 20 kurum sözlüğü + unvan kalıbı |
| F1-16 | Alias çözümleme | ✅ | `EntityIndex` — "Merkez Bankası" = "TCMB" = tam ad |

### İş Kolu D — Admin ve İç Araçlar

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F1-17 | Kaynak yönetimi ekranı | ✅ | `GET/PATCH /admin/sources` + `audit_log` kaydı |
| F1-18 | Makale listesi + filtre | ✅ | `/admin/articles` — kaynak/konu/tekrar filtresi, ham veri |
| F1-19 | Sağlık paneli | ✅ | `/admin/` HTML panosu + `/admin/health` |
| F1-20 | Golden Set 200 makale | 🔴 | Araçlar hazır, veri yok |

**20 görevin 17'si tamamlandı**, 2'si kısmi, 1'i açık.

---

## Canlı doğrulama (12 Ağustos 2026)

Gerçek akışlara karşı koşturuldu — sahte veri değil.

```
Ingestion turu tamamlandi:
  cekilen         : 116
  saklanan        : 8
  tam tekrar      : 2      <- F1-10 calisti
  yakin tekrar    : 2      <- F1-11 calisti
  kapsam disi     : 106    <- konu + ulke filtresi
  hata            : 0
```

Sağlık paneli (F1-19 DoD: 6 saattir veri vermeyen kaynak kırmızı):

```
kaynak          tier  durum     24s   toplam
hazine          T1    red       0     0      <- akis bulunamadi
resmi-gazete    T1    red       0     0      <- baglanti reddedildi
tcmb            T1    green     6     6
tuik            T1    red       0     0      <- liste JS ile yukleniyor
aa-ekonomi      T2    green     1     1
bloomberght     T3    green     1     1
dunya           T3    green     0     0      <- cekti ama hepsi kapsam disi
```

API uçları:

```
GET  /health/ready   -> 200 {"postgres":true,"redis":true}
GET  /admin/stats    -> {"articles":8,"near_duplicates":2,
                         "coverage":{"embedded":8,"entities_done":8}}
POST /ingest/link (169.254.169.254) -> 400  <- SSRF korumasi
POST /ingest/link (kapsam disi)     -> 422  <- konu filtresi
```

**Test paketi:** 196 test geçiyor, ruff temiz.

---

## Canlı veride bulunan ve düzeltilen hatalar

Bunların hiçbiri birim testinde görünmedi; yalnızca gerçek akışlara karşı
koşturunca ortaya çıktı. Her biri için regresyon testi eklendi.

| # | Hata | Belirti | Düzeltme |
|---|---|---|---|
| 1 | **HTML entity'leri çözülmüyordu** | `Kara&rsquo;nın &ldquo;Türkiye` başlıkta ham görünüyordu | Elle yazılmış kısa liste yerine `html.unescape()` |
| 2 | **Kelime sınırı yoktu** | "AR-GE'ye ... **harcandı**" vergi konusuna düşüyordu ("harc" alt dizgesi) | Kalıplar `\b<kelime>\w*` biçiminde derleniyor — Türkçe ekleri kabul eder, alt dizgeyi etmez |
| 3 | **Ülke ayrımı yoktu** | "Almanya'da enflasyon", "Rusya'nın bütçe açığı", "Fed faiz kararı" kapsama giriyordu | Türkiye bağlamı zorunlu (Spec §5) |
| 4 | **"tl" kısaltması yanlış eşleşiyordu** | İki harflik dizge yabancı haberi Türkiye sanıyordu | Türkiye sinyallerinden çıkarıldı |
| 5 | **"merkez bankası" ülke belirtmiyor** | "**ABD merkez bankasının**" Türkiye bağlamı sayılıyordu | Ülkesiz ifadeler sinyal listesinden çıkarıldı; yabancı-sinyal-yoksa kuralı yeterli |
| 6 | **Fiyat listeleri olay sanılıyordu** | "Dolar ve Euro kuru bugün ne kadar oldu?" saklanıyordu | `NON_EVENT_PATTERNS` — kur seviyesi piyasa fiyatıdır, olay değil |
| 7 | **Boş `array_agg` NULL üretiyordu** | Kişi varlığı eklenirken `NotNullViolation` | `COALESCE(..., '{}')` |
| 8 | **0 öğe döndüren kaynak "yeşil"di** | JS ile yüklenen TÜİK sayfası sonsuza dek sağlıklı görünüyordu | `last_success_at` yalnızca `items_fetched > 0` iken güncellenir |
| 9 | **Ajansın kendi anahtarı kopyasınınkinden farklıydı** | Ajans `grp:wire-aa`, kopyası `wire:aa-ekonomi` → ayrı sayılıyordu | Ajans için de `wire:<slug>` |

### En önemlisi: simhash tek başına yetmiyor (F1-11)

Spec §8.2 iki sinyal tanımlıyor; ikisini de uygulamak **zorunlu** çıktı.

Ölçüm: ~40 kelimelik bir TCMB metnine kopyalayan sitenin eklediği tek bir
cümle, simhash'i **9 bit** kaydırdı — Spec'in eşiği 6.

Sebep yapısal: simhash uzun web belgeleri için tasarlanmıştır; biz
başlık + ≤300 karakter saklıyoruz. Kısa metinde küçük bir ekleme büyük
göreli değişimdir.

Çözüm, Spec'in kendi ikinci ölçütü: **ortak n-gram oranı ≥ 0,60**
(3-gram içerme oranı). Bir tarafın diğerinden uzun olmasına dayanıklıdır —
kopyala-yapıştır tam olarak bu biçimde görünür.

> **Bu, Risk R'nin (F1-11) gerçekleşmiş hâliydi.** Yakalanmasaydı kanıt
> motoru ajans kopyalarını bağımsız teyit sayacak ve Spec §8.2'nin
> tamamı sessizce yanlış çalışacaktı.

---

## Çözülmemiş: üç Tier 1 kaynağın akışı

| Kaynak | Sorun | Sonraki adım |
|---|---|---|
| **TÜİK** | RSS yayımlamıyor. Bülten listesi `veriportali.tuik.gov.tr` üzerinde **JavaScript ile** yükleniyor; HTML'de bağlantı yok. | Tarayıcı ağ sekmesinden liste JSON ucunu bul, `probe.candidates`'a ekle |
| **Hazine** | Ana sayfa JS ile yükleniyor; `/duyurular` ve `/haberler` aday yolları sonuç vermedi. | `scripts/discover_feeds hazine` yerelden koştur |
| **Resmî Gazete** | `/rss` ucu var (arama sonucu) ama bağlantı sıfırlanıyor (`WinError 10054`) — bot filtresi olabilir. | Yerel ağdan tarayıcı UA ile dene |

**Araç hazır:** `python -m scripts.discover_feeds` — aday URL'leri dener,
RSS otomatik keşfini (`<link rel="alternate">`) okur, çalışanı önerir.
Sandbox'tan farklı davranan siteler için yerelden koşturulmalıdır.

**Etki:** Bu üç kaynak Tier 1 omurgadır. Olmadan:
- R2 kuralı (`has_primary_source`) çoğu iddiada tetiklenmez → 🟢 nadir olur
- `scheduled_events` (Spec §9.5 "gizli koz") beslenmez
- Enflasyon/işsizlik/büyüme verisi yalnızca ajans üzerinden gelir

> Bu, `docs/karar-itirazlari.md` İtiraz-2'nin somutlaşmış hâlidir ve
> Faz 2'de `evidence_status` dağılımıyla ölçülmelidir.

---

## Mimari kararlar ve gerekçeleri

| Karar | Alternatif | Gerekçe |
|---|---|---|
| `feedparser` yerine stdlib `xml.etree` | Ek bağımlılık | İhtiyaç duyulan RSS/Atom alt kümesi küçük ve kararlı; ayrıştırma hataları bizim kontrolümüzde kalıyor |
| NER modeli yerine sözlük + unvan kalıbı | spaCy/BERT | MVP dikeyinde varlık evreni kapalı (~20 kurum). Model indirmesi, sürüm yönetimi ve tahmin edilemez çıktı getirirdi. Sözlük deterministik ve ölçülebilir. |
| Konu filtresi LLM değil anahtar kelime | LLM sınıflandırma | Filtre **her makalede** çalışır; LLM ile maliyetin en büyük kalemi olurdu (`docs/veri-maliyet-modeli.md`) |
| Yakın tekrar saklanıyor, silinmiyor | Silmek | Ajans kopyası ayrı bir yayındır ve kaynak tablosunda görünmelidir; yalnızca **bağımsız sayımda** tek sayılır |
| Yerel `hashing` embedder yedeği | API anahtarı zorunlu kılmak | D16 kararı verilmeden boru hattının uçtan uca koşturulabilmesi. `is_production_ready = False` ile işaretli ve loglarda uyarıyor. |
| Adaptörler DB'ye yazmaz | Her adaptör kendi kaydını yapsın | Saklama politikası (Spec §9.3) tek noktadan zorlanabilsin |

---

## Kalan iş

| İş | Efor | Not |
|---|---|---|
| TÜİK / Hazine / Resmî Gazete akışlarını bul | 1–2 PD | `scripts/discover_feeds` yerelden |
| D16 embedding kararı | 0,5 PD | 60 çift + benchmark koşumu |
| Golden Set 200 makale | 2 PD | Boru hattı artık veri üretiyor — etiketleme gerçek veriden yapılabilir |
| 72 saat kesintisiz akış doğrulaması | takvim | `docker compose --profile workers up -d` ile beat'i başlat |
| Varlık çıkarımı %85 denetimi | 0,5 PD | 50 makale gerekiyor |

---

## Faz 2'ye hazırlık durumu

Faz 2 (Olay Zekâsı) şunları bekliyor ve **hazır**:

- `articles.embedding` dolu ve HNSW indeksli → `clustering/assigner.py` aday getirebilir
- `nlp/search.nearest_events()` yazıldı → Spec §11.4 adım 1 hazır
- `entities.jaccard()` ve `has_common_key_entity()` → §11.4 varlık kısıtı hazır
- `independence.py` → §8.2 bağımsız sayım Faz 2'de `evidence/`ye taşınacak
- `config.cluster_t_high/t_low` → D20 kalibrasyonu için ayar noktası hazır

**Eksik:** D16 kararı. Yerel `hashing` embedder semantik yakınlık yakalamaz;
kümeleme kalitesi ancak gerçek bir embedding modeliyle ölçülebilir. G2'nin
sert kapısı (false merge ≤ %5) bu karar verilmeden denenemez.
