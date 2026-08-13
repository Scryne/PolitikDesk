# Güvenlik Gözden Geçirmesi — F4-09

**Tarih:** 13 Ağustos 2026 · **Kapsam:** sır yönetimi, ağ maruziyeti, oran
sınırlama, girdi doğrulama, SSRF, XSS, SQL enjeksiyonu
**Tehdit modeli:** tek kullanıcılı kişisel araç, tek Windows makinesinde
Docker Compose ile koşuyor. İnternete açık değil; kimlik doğrulama katmanı
yok (kapsam kararı, `docs/FAZ0-DURUM.md`).

> **Bir cümlede sonuç:** Uygulama katmanı temizdi — SSRF, XSS ve SQL
> enjeksiyonuna karşı korumalar yerindeydi ve denetimde delik bulunmadı.
> **Tek gerçek açık ağ katmanındaydı:** Postgres ve Redis, makinenin
> katıldığı her ağa açıktı. Düzeltildi ve doğrulandı.

---

## 1. Bulunan açık: veritabanı ve kuyruk her ağa açıktı 🔴

`docker-compose.yml` portları kısayol biçimiyle yayımlıyordu:

```yaml
ports:
  - "5432:5432"    # -> 0.0.0.0:5432
  - "6379:6379"    # -> 0.0.0.0:6379
  - "8000:8000"    # -> 0.0.0.0:8000
```

Docker'ın bu kısayolu portu **tüm arayüzlere** bağlar. Ölçülen durum:

```
5432/tcp -> 0.0.0.0:5432      Postgres — politikdesk / politikdesk
6379/tcp -> 0.0.0.0:6379      Redis    — kimlik doğrulama YOK
8000/tcp -> 0.0.0.0:8000      API      — kimlik doğrulama YOK (tasarım)
```

**Neden bu bir dizüstü bilgisayarda ciddi:** makine sabit bir sunucu
değil. Kafe, otel, konferans veya ortak ofis Wi-Fi'ına katıldığı her an,
aynı ağdaki herkes varsayılan parolayla Postgres'e bağlanabilirdi —
toplanan makaleler, editoryal profil ve taslaklar dahil her şey okunur ve
yazılabilirdi. Redis'te parola bile yoktu.

### Düzeltme

```yaml
ports:
  - "127.0.0.1:5432:5432"
  - "127.0.0.1:6379:6379"
  - "127.0.0.1:8000:8000"
```

Konteynerler birbirine Docker ağı üzerinden (`db:5432`) bağlanır; bu
değişiklik onları etkilemez. Yalnızca **makine dışından** erişimi keser.

**Doğrulandı:**

| | Önce | Sonra |
|---|---|---|
| Bağlama | `0.0.0.0:5432` | `127.0.0.1:5432` |
| `localhost`tan erişim | ✅ | ✅ (`feed -> 200`, `db ok`) |
| Yerel ağdan erişim | ✅ **açık** | ⛔ kapalı |
| Test paketi | 538 geçti | 538 geçti |

### Kalan kabul edilen risk

Makinede oturum açmış **başka bir yerel kullanıcı** hâlâ `localhost`
üzerinden bağlanabilir. Tek kullanıcılı kişisel bir araç için bu kabul
edilebilir; makine paylaşılırsa parola değiştirilmeli ve Redis'e
`requirepass` eklenmelidir.

---

## 2. Sır yönetimi ✅

| Kontrol | Sonuç |
|---|---|
| Kodda gömülü API anahtarı | Yok (desen taraması temiz) |
| `.env` `.gitignore`'da | ✅ `.gitignore:14` |
| `.env` geçmişte commit edilmiş mi | **Hayır** — `git log --all -- .env` boş |
| Anahtarlar loglanıyor mu | Hayır; `load_env_file` yalnızca değişken **adlarını** döndürür |
| Yedekler depoya girer mi | Hayır — `backups/` `.gitignore`'a eklendi (F4-06) |

`PD_LLM_API_KEY_ENV` deseni not edilmeye değer: `.env` anahtarın
kendisini değil, anahtarın okunacağı **değişkenin adını** tutar. Bu,
sağlayıcı değiştirmeyi anahtarı taşımadan mümkün kılar.

⚠ **`backups/*.dump` şifresiz.** Makale alıntıları, editoryal profil ve
taslaklar içerir. Disk şifrelemesi (BitLocker) açık olmalıdır; yedekler
buluta senkronlanan bir klasöre konmamalıdır.

> Not: proje dizini `OneDrive` altında. `backups/` `.gitignore`'da ama
> OneDrive senkronu `.gitignore`'a bakmaz — yedekler buluta çıkar.
> Kabul edilebilir bir tercih olabilir (kişisel veri, kişisel bulut), ama
> **bilinçli** olmalı: istenmiyorsa `PD_BACKUP_DIR` ile OneDrive dışına
> alınabilir.

---

## 3. SSRF — manuel link içe aktarma ✅

Kullanıcının URL verdiği tek yer `adapters/manual.py`. `validate_url`
katmanları:

1. Şema beyaz listesi (`http`, `https`) — `file://`, `gopher://` reddedilir
2. `localhost`, `*.local` reddi
3. Doğrudan IP verilmişse özel/ayrılmış aralık reddi
4. **DNS çözümlemesi sonrası** tekrar kontrol — `evil.com -> 169.254.169.254`
   saldırısını kapatır

Dördüncü katman kritik: yalnızca metni denetleyen bir kontrol, buluttaki
metadata servisine yönlendiren bir alan adını yakalayamazdı.

`_is_private` şunları kapsar: `is_private`, `is_loopback`, `is_link_local`,
`is_reserved`, `is_multicast`, `is_unspecified`.

**Kalan boşluk (kabul edilen):** TOCTOU. DNS doğrulama ile istek arasında
kayıt değişirse (DNS rebinding) kontrol atlatılabilir. Tek kullanıcılı bir
araçta URL'yi veren kişi kullanıcının kendisidir; kendi kendine saldırı
senaryosu gerçekçi değil.

---

## 4. XSS ✅

Sunucu tarafı HTML, şablon motoru yok — kaçış disiplini elle uygulanıyor,
bu yüzden ayrıca denetlendi.

* `layout.esc()` tek kaçış noktası: `html.escape(str(...))`
* **Serbest metin taraması temiz:** başlık, `claim_text`, `excerpt`,
  `body`, kaynak adı, hata metni ve ipuçlarının HİÇBİRİ kaçışsız
  enterpolasyona girmiyor
* Kaçışsız enterpolasyonlar yalnızca **veritabanı denetimli** değerler:
  sayısal `id`, sayaçlar, `salience_score`, ve CHECK kısıtıyla sınırlı
  enum'lar (`slot`, `status`, `tier`)

Kaynak metinleri (RSS başlıkları) düşman girdisi sayılmalıdır ve
sayılıyor — hepsi `esc()`'ten geçiyor.

---

## 5. SQL enjeksiyonu ✅

Tüm sorgular psycopg parametre bağlama (`%s`) kullanıyor. Dize
birleştirmeli 10 yer `# noqa: S608` ile işaretli; her biri incelendi:

| Yer | Değerlendirme |
|---|---|
| `admin/router.py:78` dinamik `UPDATE` | Sütun adları **kod sabitinden** (`"tos_status = %s"`), değerler parametreli. Güvenli. |
| `web/repository.py`, `nlp/search.py`, `context/scheduler_match.py` vb. | Enterpole edilen parça sabit dizelerden seçiliyor; kullanıcı girdisi değil. |

Kullanıcı girdisinin sorgu **metnine** girdiği tek bir yer bulunamadı.

---

## 6. Giden istek disiplini (oran sınırlama) ✅

`ingestion/http.py` bir "kibar istemci":

* Kimliğini bildiren `User-Agent`
* Kaynak başına dakikalık oran penceresi (aşılırsa uyur)
* `robots.txt` saygısı (`RobotsDisallowed`); alınamazsa izin verilir —
  beyan edilmemiş kısıt yasak sayılmaz
* Üstel geri çekilme (4 deneme)
* `ingestion/guard.py`: `tos_status='forbidden'` kaynaktan toplama kod
  seviyesinde imkânsız

**Gelen** oran sınırlaması yok. Kabul edilen: servis yalnızca
`127.0.0.1`'e bağlı ve tek kullanıcı var; kendi kendini DoS etmek bir
tehdit modeli değil.

---

## 7. Girdi doğrulama ✅

* Tüm API gövdeleri Pydantic modelleri (`DraftRequest`, `SourceUpdate`…)
* Yol parametreleri `int` olarak tiplendirilmiş — FastAPI 422 döner
* `angle` gibi alanlar `Literal` ile kısıtlı
* Veritabanı seviyesinde CHECK kısıtları ikinci savunma hattı
  (`excerpt_len`, `quote_span_len`, `claims_prediction_always_unverified`)

Uygulama katmanı atlansa bile şema kısıtları tutuyor.

---

## 8. Bağımlılıklar

~~`pip-audit` bu denetimde koşulmadı (bağımlılık listesinde yok). Öneri:
CI'a eklenmesi.~~ Şimdilik `backups/` ve `.env` sızıntısı gibi doğrudan
kontrol edilebilir riskler kapatıldı.

**✅ Kapandı — B-83 (14 Ağustos 2026).** `pip-audit` `dev` ekstrasına ve
CI'a **zorunlu adım** olarak eklendi (`make audit`).

İlk koşumun ölçülen sonucu:

| Ortam | Sonuç |
|---|---|
| Üretim imajı (`pd-api` konteyneri) | ✅ **Bulgu yok** |
| Yerel geliştirme `.venv` | 🟡 `setuptools 78.1.0` — PYSEC-2025-49, PYSEC-2026-3447 |

`setuptools` bir **kurulum aracıdır**, çalışma zamanı bağımlılığı
değildir ve üretim imajında güncel sürümü bulunuyordu; bulgu yalnızca
yerel ortamdaydı ve yükseltilerek kapatıldı.

**Düzeltmesi olmayan bulgu çıkarsa:** adım `--ignore-vuln <ID>` ile
geçilebilir — ama **yazılı gerekçe** bu bölüme eklenerek, sessizce
değil. Gerekçesiz bir `ignore`, taramayı tümüyle anlamsızlaştırır.

---

## Özet

| Alan | Durum |
|---|---|
| Ağ maruziyeti | 🔴 açıktı → ✅ **düzeltildi ve doğrulandı** |
| Sır yönetimi | ✅ temiz (⚠ yedek şifrelemesi kullanıcı sorumluluğunda) |
| SSRF | ✅ dört katmanlı, DNS sonrası kontrol dahil |
| XSS | ✅ serbest metin taraması delik bulmadı |
| SQL enjeksiyonu | ✅ 10 `noqa: S608` yeri tek tek incelendi |
| Giden oran sınırlama | ✅ UA + oran + robots + geri çekilme |
| Girdi doğrulama | ✅ Pydantic + DB CHECK çift katman |
| Gelen oran sınırlama | ⚪ yok — loopback + tek kullanıcı gerekçesiyle kabul |

### Kullanıcıya düşen iki iş

1. **BitLocker açık olsun** — `backups/*.dump` şifresizdir.
2. **Yedeklerin OneDrive'a çıkmasını istemiyorsan** `PD_BACKUP_DIR` ile
   proje dışına al.
