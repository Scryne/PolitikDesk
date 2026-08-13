# Faz 3 Sonrası Denetim — 13 Ağustos 2026

**Kapsam:** kod sağlığı, çalışan dağıtım, canlı veri, kaynak sağlığı
**Tetikleyici:** "her şeyin sorunsuz olduğundan emin ol"

> **Sonuç bir cümlede:** Kod sağlıklıydı, dağıtım değildi. Depodaki kod
> doğruydu, 467 test yeşildi, CI yeşildi — ama çalışan konteynerler eski
> imajlardaydı ve boru hattı kümeleme adımında sessizce kopmuştu.

---

## 1. Bulunan arıza: bayat imaj (B-77)

`pd-api` bugün yeniden kurulmuştu; `pd-worker` ve `pd-beat` kurulmamıştı.

| Konteyner | İmaj yaşı | Taşıdığı kod | Sonuç |
|---|---|---|---|
| `pd-api` | 8 dakika | Faz 3 | ✅ |
| `pd-worker` | 13 saat | **Faz 2** | `generate_briefing`, `rollup_metrics` yok |
| `pd-beat` | **24 saat** | **Faz 1** | 13 zamanlamadan **5'i** var |

Beat'in 13 saatlik kaydında (12 Ağu 20:58 → 13 Ağu 10:01) şunlar **bir kez
bile** gönderilmemiş: `cluster`, `claims`, `evidence`, `context`,
`scheduler-match`, `briefing-morning`, `briefing-evening`,
`metrics-rollup`.

**Ölçülen hasar:** 29 makalenin **18'i** (%62) gömülüp varlıkları
çıkarıldıktan sonra askıda kalmıştı (`event_id IS NULL`). 9 olayın 8'inde
iddia yoktu.

### Kök neden

`make up` worker/beat'e dokunmuyordu ve README'nin sürekli çalıştırma
komutu yeniden kurmuyordu:

```bash
docker compose --profile workers up -d      # mevcut imaj varsa YENİDEN KURMAZ
```

### Bunun plan üzerindeki etkisi

`docs/FAZ3-DURUM.md`'nin bir numaralı blokajı *"ingestion'ın haftalarca
birikmesi gerekiyor"* (B-57) idi. **Bu varsayım geçersizdi:** boru hattı
varlık adımından sonra kesildiği için beklemek yalnızca askıdaki makale
sayısını büyütürdü. G3 #5 (7 gün üst üste brifing) de kendiliğinden
hiçbir zaman gerçekleşemezdi — beat'te brifing görevi yoktu.

---

## 2. Yapılan düzeltmeler

| # | İş | Çıktı |
|---|---|---|
| 1 | Worker + beat `--build` ile yeniden kuruldu | beat 5 → **13** zamanlama; worker 11 → **13** görev |
| 2 | Askıdaki 18 makale işlendi | askıda **18 → 0** |
| 3 | Tuzağın tekrarı engellendi | `make workers`, `make deploy-check`, `scripts/check_deployment.py`, `tests/test_tasks.py` |
| 4 | Hazine kaynağı canlandırıldı (B-43) | yeni `wp_rest` adaptörü + 7 test |

### Boru hattının önü/sonrası

| | Önce | Sonra |
|---|---|---|
| makale | 29 | **37** |
| olay | 9 | **24** |
| iddia | 2 | **43** |
| kanıt bağı | 2 | **43** |
| askıda makale | **18** | **0** |
| iddiası olan olay | 1 | **21** |

---

## 3. İki denetleyici — neyi yakalar, neyi yakalamaz

Arıza *kodda* değil *imajda* olduğu için bir test onu yakalayamazdı. Bu
yüzden iki ayrı koruma kuruldu:

| Koruma | Yakaladığı | Yakalayamadığı |
|---|---|---|
| `tests/test_tasks.py` (4 test) | **Kod kayması** — görev eklenip zamanlaması unutulursa CI kırılır | Çalışan konteynerin eski kod taşıması |
| `scripts/check_deployment.py` | **İmaj kayması** — konteynerdeki `politikdesk/` ağacını depodakiyle karşılaştırır, beat zamanlamasını sayar | Konteyner çalışmıyorsa denetleyemez (uyarı verir) |

`verify_arch_guard` geleneğine uyularak denetleyici **kanıtlandı**: depoya
geçici bir dosya eklendiğinde üç konteyner için de `[KAYMA]` bildirdi ve
çıkış kodu 1 döndü; dosya silinince yeniden yeşile döndü.

> Yeşil ışığın anlamı, kırmızıya dönebildiğini gösterebildiğin kadardır.

---

## 4. Kaynak sağlığı — 3 ölü T1 kaynağın teşhisi

Üç Tier 1 kaynak Faz 1'den beri 0 öğe üretiyordu. Üçünün de sebebi
**farklı** çıktı; ikisinin backlog'daki tahmini **yanlıştı**.

### ✅ B-43 — Hazine: çözüldü

Duyuru sayfası bir React uygulaması; sunucu yalnızca *"You need to enable
JavaScript to run this app."* kabuğunu dönüyordu. HTML adaptörü bu kabukta
bağlantı bulamıyor, **HTTP 200 ile 0 öğe** üretiyordu.

Uygulamayı besleyen uç bir **WordPress REST** koleksiyonuymuş:

```
https://www.hmb.gov.tr/portal/v2/posts?per_page=20
```

`robots.txt`: `User-agent: * / Disallow:` (boş) — tüm yollar açık.

Yeni `WordPressRestAdapter` (`adapter: wp_rest`) yazıldı. Dikkat edilen
iki nokta:

* `link` alanı **arka uç konağını** (`api.hmb.gov.tr`) gösterir; kullanıcı
  açamaz. Genel adres `base_url` + `/duyuru/<slug>` ile kurulur ve
  çözüldüğü doğrulandı (HTTP 200).
* Tekilleştirme kimliği kalıcı `id`'den kurulur, `slug`'tan değil — slug
  düzenlenebilir.

**Canlı sonuç:** 20 çekildi, **5 saklandı**, 0 hata. Gelen içerik tam da
aranan T1 makro malzemesi: Merkezi Yönetim Borç Stoku, Vergi Dışı
Gelirler, KİT'ler, İç Borçlanma Stratejisi.

### 🔴 B-42 — TÜİK: kimlik bilgisi gerekiyor

* `veriportali.tuik.gov.tr` React SPA → "JavaScript Gerekli" kabuğu
* Klasik sitede de sunucu tarafı bülten listesi **yok**
  (`www.tuik.gov.tr/Bulten/Index` → 404; `/Kurumsal/Haberler`'de bülten
  bağlantısı yok)
* Veri servisi `https://nsiws.tuik.gov.tr/rest/...` (SDMX) ve
  `Authorization: Bearer {access_token}` **istiyor**; belirteç
  `giris.tuik.gov.tr` (Keycloak) hesabından alınıyor

**Kodla çözülemez.** Kullanıcı kararı: TÜİK hesabı açılsın mı?

### 🔴 B-44 — Resmî Gazete: ağ düzeyinde engel

Backlog'daki *"bot filtresi?"* tahmini **yanlıştı** — HTTP katmanına hiç
ulaşılmıyor, dolayısıyla User-Agent veya `robots.txt` ile ilgisi yok.

* DNS çözülüyor (212.174.186.1), TCP 443 **açılıyor**
* Sunucu ClientHello'dan hemen sonra bağlantıyı düşürüyor
  (`SSL: UNEXPECTED_EOF_WHILE_READING`)
* Denenip elenenler: TLS 1.2'ye sabitleme, `SECLEVEL=1`, eski yeniden
  anlaşma, sertifika doğrulamasını kapatma, `www`'suz alan adı, iki ayrı
  TLS yığını (Windows schannel + konteyner OpenSSL) — **hepsi aynı
  noktada** düşüyor

Farklı bir çıkış IP'si (TR) gerektirir.

> **Yan bulgu.** TÜİK bir ara aynı TLS hatasını verdi, sonra 90 saniyelik
> beklemenin ardından düzeldi. Hızlı ardışık istekler kenar sunucusunda
> (NetScaler) el sıkışma düşürmeyi tetikliyor. Bu, teşhisin kendisini
> kirletebilir: *ölçüm aracının kendisi arızayı üretebiliyordu.*

---

## 5. Kalan yapısal sorun: `diversity_ratio` = 1,0 (B-79)

43 iddianın tamamı `single_source` (R5) veya `unverified` (R0). **Tek bir
`corroborated` yok.**

| İddia tipi | Kanıt durumu | Adet |
|---|---|---|
| fact | single_source | 19 |
| attribution | single_source | 5 |
| number | single_source | 4 |
| prediction | unverified | 8 |

Bu bir motor hatası değil: çapraz teyit edecek **bağımsız kaynak yok**.
4 T1 kaynağın 2'si hâlâ ölü. G4′ #4 hedefi ≥ 2,5 ve bu hedef B-42/B-44
çözülmeden tutturulamaz.

---

## 6. Kod sağlığı — temiz

| Denetim | Sonuç |
|---|---|
| `ruff check .` | ✅ temiz |
| `mypy` | ✅ 83 dosya, sorun yok |
| `check_architecture` + `verify_arch_guard` | ✅ temiz + kanıtlandı |
| `pytest` (canlı DB) | ✅ **478 geçti**, 0 atlandı |
| `check_deployment` | ✅ 3/3 konteyner, 13/13 zamanlama |

**Not:** 38 test yerelde `PD_DATABASE_URL` yoksa atlanır. CI bu değişkeni
`ci.yml`'de tanımlar, yani CI'da gizli atlama yoktur — yerelde de
değişkeni vererek koşuldu ve tamamı geçti.

**Canlı doğrulama:** `/feed`, `/admin/`, `/admin/metrics`,
`/onboarding/profile`, `/briefing/{tarih}` → 200; olay sayfası 8,6 ms.
P1 kapısı canlı denendi: kanıtsız olayda taslak isteği **HTTP 409**.

---

## 7. Açılan kalemler

| # | Kalem | Faz |
|---|---|---|
| ~~B-77~~ | Bayat imaj arızası | ✅ kapandı |
| B-78 | Sessiz kopma alarmı — *aşama* sağlığı izlenmiyor | Faz 4 (F4-05) |
| B-79 | `diversity_ratio` = 1,0; hiç `corroborated` yok | Faz 4 (B-42/B-44'e bağlı) |
| B-80 | `source_fetch_log.succeeded` yanıltıcı — adaptörler istisnayı yutuyor | Faz 4 (F4-05) |

---

## 8. Fazın dersi

Faz 2'de eval koşucusu kanıt motorunda hata buldu. Faz 3'te üretim
kıyaslaması grounding doğrulayıcısında hata buldu. Bu denetimde de aynı
şey oldu, ama bir katman aşağıda:

**Testler kodu denetler, çalışan sistemi değil.** Üç faz boyunca yeşil
kalan bir test paketi, üretimde 13 saat boyunca boru hattının kopuk
olduğunu göremedi. Eksik olan test değil, *çalışan sistemi depoyla
karşılaştıran bir denetleyiciydi.*
