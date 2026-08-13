# Faz 4 — Sertleştirme · Durum

**13 Ağustos 2026** · Kapsam: İş Kolu C (F4-05…F4-10) + F4-15, F4-16
İş Kolu A (çok kullanıcı), B (hukuk/KVKK) ve D (beta) kapsam dışı —
kişisel araç kararı (Yol Haritası Faz 4 kapsam notu, Spec v3.2 §14.1).

> **Fazın bir cümlesi:** Sertleştirme işleri, sertleştirilmesi gereken
> şeyin ne olduğunu ölçerek buldu. Kurulan üç ölçüm aracının **üçü de**
> ilk koşuşlarında gerçek arıza yakaladı — ve biri, üç fazdır yanlış
> teşhis edilmiş bir hatanın kök nedenini ortaya çıkardı.

---

## Görev durumu

| ID | Görev | Durum |
|---|---|---|
| F4-05 | Hata dayanıklılığı, zarif bozulma | ✅ |
| F4-06 | Yedekleme ve geri yükleme | ✅ denendi ve doğrulandı |
| F4-07 | Maliyet tavanı ve alarm | ✅ |
| F4-08 | Performans optimizasyonu | ✅ hedeflerin 24–70 katı altında |
| F4-09 | Güvenlik gözden geçirmesi | ✅ 1 açık bulundu, kapatıldı |
| F4-10 | Çalıştırma ortamı (yerel Windows) | ✅ |
| F4-15 | Election Mode feature flag | ✅ hazırlandı, varsayılan kapalı |
| F4-16 | Denetim izi tamamlama | ✅ |

**Test:** 487 → **547** (+60) · ruff temiz · mypy 86 dosya temiz ·
mimari koruma kanıtlandı · `deploy-check` 3/3 konteyner, 15/15 zamanlama.

---

## Ölçüm araçlarının bulduğu dört arıza

Fazın en önemli çıktısı kod değil, **görünürlük**. Her araç ilk
koşuşunda bir şey buldu.

### 1. Sonsuz yeniden deneme döngüsü (F4-05) 🔴

`pipeline_health` kurulur kurulmaz kırmızı yandı: üç olay **28,5
saattir** iddia çıkarımı bekliyordu.

Ama bu bir kopma değildi, daha sinsisiydi. Görev her 10 dakikada bir
çalışıyor, üç olayı LLM'e gönderiyor, her seferinde **0 iddia** alıyor
(`output_tokens: 9` — boş yanıt) ve olaylar listeden hiç düşmüyordu.
Tur başına ~4 dakika. **Kalıcı olarak, sonsuza kadar.**

Kök neden: `pending_events` "iddiası olmayan olay" diyordu. Çıkarımın
meşru şekilde sıfır iddia döndürmesi mümkündür (başlıktan ibaret bir
duyuru) ve bu durum "henüz denenmedi"den ayırt edilmiyordu.

**Düzeltme:** `events.claims_attempted_at` + `claims_attempt_count`
(migration 0005). Yeniden deneme ölçütü artık "iddia yok" değil,
**"olaya yeni malzeme geldi"**.

**Kanıtlandı:** tur 1→3 sayaç 1→3 ilerledi, tur 4 **0 olay** işledi,
nöbetçi yeşile döndü.

### 2. Veritabanı yeniden başlayınca API 500 (F4-05) 🔴

`pg_stat_statements` için `pd-db` yeniden kuruldu; API ayaktaydı ve
havuzdaki bağlantılar koptu. Havuz onları **kontrol etmeden dağıttı**:

```
psycopg.errors.AdminShutdown: terminating connection due to
administrator command   ->  GET /feed 500
```

**Düzeltme:** `ConnectionPool(check=ConnectionPool.check_connection,
max_lifetime=3600, timeout=10)`.

**Kanıtlandı:** `docker restart pd-db` sonrası `/feed` beş istekte de
**200**. Maliyeti ölçüldü: p95 26 ms → 24 ms (fark gürültü içinde),
hedefin hâlâ 33 katı altında.

### 3. Veritabanı ve Redis her ağa açıktı (F4-09) 🔴

```
5432/tcp -> 0.0.0.0:5432    Postgres — politikdesk / politikdesk
6379/tcp -> 0.0.0.0:6379    Redis    — kimlik doğrulama YOK
```

Docker'ın `"5432:5432"` kısayolu portu tüm arayüzlere bağlar. Bu bir
sunucu değil **dizüstü bilgisayar**: kafe, otel veya ortak ofis
Wi-Fi'ına katıldığı her an aynı ağdaki herkes varsayılan parolayla
veritabanına bağlanabilirdi.

**Düzeltme:** `127.0.0.1:5432:5432`. Konteynerler Docker ağı üzerinden
konuşur, etkilenmez.

**Kanıtlandı:** bağlama değişti, `feed -> 200`, `db ok`, 538 test geçti.

Ayrıntı: [`guvenlik-notu.md`](guvenlik-notu.md).

### 4. B-79'un teşhisi yanlıştı (en önemlisi) 🔴

Üç fazdır `diversity_ratio` = 1,0: hiçbir iddia `corroborated` değil.
Faz 3 denetimi bunu **"çapraz teyit edecek bağımsız kaynak yok"** diye
teşhis etmiş ve ölü T1 kaynaklara (B-42, B-44) bağlamıştı.

**Teşhis yanlıştı. Kaynak vardı; kod onu atıyordu:**

```python
deduped = dedupe_claims([c for c, _ in collected])
kept    = {id(c) for c in deduped}
final   = [(c, aid) for c, aid in collected if id(c) in kept]
```

İki bağımsız kaynak aynı iddiayı söylediğinde ikinci `(iddia, makale)`
çifti **tamamen** düşüyordu — yalnızca yinelenen metin değil, o
kaynağın **kanıt bağı** da. `independent_count` hiçbir zaman 1'i
geçemiyordu.

Sayısal iddialarda imza `metric:value:period`e normalize edilir — yani
hata tam da **çapraz teyidin en net olduğu** yolda tetikleniyordu.
**Sekiz kaynak da canlı olsa oran 1,0'da kalırdı.**

**Düzeltme:** `group_claims_by_source` — iddia teke iner, kaynakları
birikir, her kaynağa kendi alıntısıyla ayrı kanıt bağı yazılır.

**Kanıtlandı:** `tests/test_corroboration.py` (9 test). Eski davranış
geri konulduğunda 3 test kırmızıya döndü.

---

## Kalan engel: iddia eşleştirme (B-81) — bilinçli olarak yapılmadı

Düzeltme yolu açtı ama canlı veride oran **hâlâ 1,0**. Yeniden çıkarım
sonrası ölçülen (olay 686, iki bağımsız kaynak):

| Kaynak | Tip | İddia |
|---|---|---|
| AA | `attribution` | "TCMB Başkanı Karahan, 2026 yıl sonu enflasyon tahminini…" |
| Dünya | `fact` | "Merkez Bankası'nın yıl sonu enflasyon tahmini belli oldu" |

Aynı olgu, iki bağımsız kaynak — ama hem sözcükler hem `claim_type`
farklı. Sözcük tabanlı imza eşleşmiyor.

**Neden semantik eşleştirici yazılmadı:** gevşek eşleştirme **yanlış
teyit** üretir — sistem "iki kaynak aynı şeyi söylüyor" derken
söylemiyorlardır. Bu, teyit yokluğundan çok daha zararlıdır; ürünün ana
vaadini (Spec §1, §8.2) doğrudan çürütür. Golden Set üzerinde precision
ölçülmeden uygulanmamalı ve Spec §8.2'yi etkilediği için sürüm artışı
gerektirir.

B-82 daha ucuz bir hipotez öneriyor ve **önce denenmeli**: yukarıdaki
iddia aslında `number` olmalıydı; öyle olsaydı imza değere normalize
olacak ve semantik eşleştirmeye gerek kalmadan teyit kurulacaktı. Bu
bir prompt iyileştirmesi — risksiz ve ölçülebilir.

---

## Ölçümler

### Performans (F4-08) — hedeflerin çok altında

| Sayfa | p95 | Hedef | Pay | N+1 |
|---|---|---|---|---|
| feed | **23,8 ms** | 800 ms | 34× | 5 sorgu, tekrar yok ✅ |
| olay | **24,0 ms** | 1500 ms | 62× | 11 sorgu, tekrar yok ✅ |
| admin | **23,2 ms** | 1500 ms | 65× | 11 sorgu, tekrar yok ✅ |
| brifing | **20,9 ms** | 1500 ms | 72× | 2 sorgu, tekrar yok ✅ |
| metrik | **20,7 ms** | 1500 ms | 72× | 10 sorgu, tekrar yok ✅ |

> **N+1 dedektörünün kendisi de düzeltildi.** İlk sürüm toplam sorgu
> sayısına bakıyor ve 16 görüp "şüpheli" diyordu; bunun 10'u
> BEGIN/COMMIT'ti ve kalan 5 sorgunun her biri **tam bir kez**
> koşuyordu. N+1'in imzası çok sorgu değil, **aynı sorgunun
> tekrarıdır**. Dedektör buna göre yeniden yazıldı.

### Yedekleme (F4-06) — geri yükleme fiilen denendi

```
yedek     : 0,36 MB, 216 nesne, 21 tablo verisi
geri yükle: politikdesk_restore_test
```

| tablo | üretim | geri yüklenen | |
|---|---|---|---|
| articles | 44 | 44 | ✅ |
| claims | 48 | 48 | ✅ |
| drafts | 2 | 2 | ✅ |
| events | 28 | 28 | ✅ |
| evidence | 48 | 48 | ✅ |
| sources | 7 | 7 | ✅ |

Geri yükleme **asla üretimin üzerine yazmaz**; hedef üretimle aynıysa
komut reddeder (`--force` olmadan). Bu da denendi ve reddetti.

---

## Kurulan görünürlük katmanları

Üç ayrı katman, üç ayrı kör noktayı kapatıyor:

| Katman | Neye bakar | Neyi göremez |
|---|---|---|
| `check_source_health` (F1-19) | Boru hattının **girişi** — kaynak veri veriyor mu | İçeride birikme |
| `pipeline_health` (B-78) | Boru hattının **içi** — aşamada birikme var mı | Docker kapalıysa kendisi de kapalıdır |
| `scripts/watchdog.py` (F4-10) | **Dışarıdan** — konteyner + API + aşama | — |

Nöbetçi ana makinede Windows Görev Zamanlayıcı ile 6 saatte bir koşar:
kendi ölümünü bildiremeyen bir alarm, alarm değildir.

---

## Election Mode (F4-15) — hazırlandı, uygulanmadı

Spec §12.6'nın beş maddesinin karşılığı `config/election_mode.py`'de.
Varsayılan **kapalı** ve bu her koşumda test edilir.

Açıldığında (`PD_ELECTION_MODE=true`):

| Madde | Etki |
|---|---|
| 1 | Üretim engeli `single_source`'a genişler |
| 2 | 🟢 eşiği 3 → **4** bağımsız kaynak; R3 resmî sayı istisnası **kapanır** |
| 3/4 | Kaynak linki zorunlu; yarı-otomasyon kilitli (zaten yok) |
| 5 | Her sayfada mor uyarı bandı |

Bir incelik: `engine_version()` moda göre `+election` eki alır. Bu,
`score_claims`'in "sürümü farklı olanı yeniden puanla" yüklemini
kendiliğinden tetikler — yoksa mod açıkken ekranda eski **gevşek**
etiketler kalırdı: göstergesi açık, koruması kapalı bir mod.

---

## Yan düzeltme: üç farklı motor sürümü

`ENGINE_VERSION` üç yerde tanımlıydı ve biri bayat bir iskele değeriydi
(`evidence-engine@0.1.0-scaffold`, Faz 0'dan kalma). `pipeline.py` ise
sürümü SQL'e elle gömüyordu. Sürüm artırılsa `score_claims` yeniden
puanlamayı sessizce atlardı. Tek kaynağa indirildi ve teste bağlandı.

---

## G4′ karşısındaki durum

| # | Koşul | Hedef | Durum |
|---|---|---|---|
| 1 | Uçtan uca akış 7 gün kesintisiz | — | ⏳ takvim zamanı (B-76) |
| 2 | Taslakta kanıtta olmayan sayı/tarih | %0 | ⏳ 50 taslak gerekiyor (B-75) |
| 3 | Correction rate | ≤ %3 | ⏳ kullanım gerekiyor |
| 4 | Diversity ratio | ≥ 2,5 | 🔴 **1,0** — engel artık kaynak değil, iddia eşleştirme (B-81/B-82) |
| 5 | Aylık maliyet | ≤ 30 $ | ✅ **0 $** (NVIDIA NIM ücretsiz katman) |
| 6 | Kritik hata (P0/P1) | 0 açık | ✅ |
| 7 | G2 kümeleme kapıları | regresyon yok | ✅ precision 1,000 · recall 0,824 |
| 8 | Yedekleme + geri yükleme denenmiş | belgelenmiş | ✅ **bu faz** |
| 9 | Günlük yedek ve maliyet alarmı | çalışıyor | ✅ **bu faz** |

**8 ve 9 bu fazda kapandı.** 4 numaranın önündeki engelin ne olduğu
artık **doğru** biliniyor — bu fazın en değerli çıktısı bu.

---

## Fazın dersi

Faz 2'de eval koşucusu kanıt motorunda hata buldu. Faz 3'te üretim
kıyaslaması grounding doğrulayıcısında hata buldu. Faz 3 denetimi
çalışan sistemle depo arasındaki kaymayı buldu. Bu fazda da aynı şey
oldu, ama bir kez daha derinde:

**Faz 3 denetimi doğru soruyu sordu ama yanlış cevabı kabul etti.**
`diversity_ratio` = 1,0 görüldü, makul bir açıklama bulundu ("kaynak
yok") ve dışsal bir engele bağlandı. Açıklama makuldü, tutarlıydı ve
**yanlıştı** — üç faz boyunca bir kod hatasını gizledi.

> Bir metriğin neden kötü olduğuna dair makul bir açıklamanız varsa,
> açıklamayı da ölçün. Dışsal bir sebebe bağlanan arıza, aranmayan bir
> arızadır.
