# Plan Raporu — Siyaset Dikeyine Geçiş ve Sağlık Denetimi

**Tarih:** 14 Ağustos 2026 · **Kapsam:** ürün yönü + mevcut durum denetimi + iyileştirme planı
**Durum:** öneri — hiçbir kalemi kodlanmadı. Kararlar Bölüm 11'de onay bekliyor.

---

## 0. Yönetici özeti

Talep şu: *"Proje ekonomiye kaydı, asıl olay siyasetti. Türkiye siyasetini muhalif
bir çizgide yorumlayıp X hesabımdan paylaşmak istiyorum."*

Denetimin ilk bulgusu, talebin kendi teşhisini düzeltiyor:

> **Proje ekonomiye "kaymadı" — ekonomi olarak *seçildi*.** Spec §5 / karar D4,
> makro ekonomiyi *hedef* olarak değil, **motorun kalibrasyon sahası** olarak
> seçmiş. Gerekçe kayıtlı: sayısal iddia doğrulanabilir, Tier-1 birincil kaynak
> yoğun, hukuki risk en düşük. Siyaset zaten planda — Faz 5'in dört adımlı
> genişleme sırasında (Yasama → Yargı → Dış politika → Genel siyaset) ve
> `BACKLOG.md` B-09…B-12'de duruyor.

Yani yapılacak iş bir *kurtarma* değil, **planlanmış genişlemenin öne alınması**.
Bunun beş sonucu var:

| # | Tespit | Sonuç |
|---|---|---|
| 1 | Genişlemenin ön koşulu **Kapı G4′**; bugün açık değil | 9 koşuldan 4'ü ölçülmemiş/tutmuyor. Dikey açmadan önce 2–3 haftalık bir kapatma turu gerekiyor (Bölüm 10, Aşama S0) |
| 2 | Kapsam filtresi ekonomi dışını **kod seviyesinde** eliyor | `ingestion/topics.py` — siyaset içeriği bugün boru hattına *giremez*. Tek satır ayar değil, dikey kavramının kodda karşılığı yok |
| 3 | Kanıt motoru **sayısal iddia** için kalibre | Siyasette iddiaların çoğu `attribution` (beyan). R2/R3 çalışmaz, her şey 🟠/⚪ olur → üretim kapısı her olayı bloke eder. R8 "beyan kaydı" kuralı gerekiyor (Bölüm 6.3) |
| 4 | "Muhalif yorum" ürün sözleşmesiyle **kısmen** çatışıyor | Çatışan şey ideoloji *saklamak* ve kaynağa siyasi etiket *vermek*. Kullanıcının kendi editoryal hattı çatışmıyor — ama bugün girecek yeri de yok. Çözüm Bölüm 4'te; DB şemasına dokunmadan |
| 5 | Kaynak tavanı (15) siyaset için **yetersiz** | Bugün 10 kaynak, 5 boş slot var. Siyaset dikeyi tek başına 8–12 kaynak ister. D6 "dikey başına tavan" olarak yeniden yazılmalı → Spec v3.4 |

**Önerilen ana hat:** 3 aşama, ~9 hafta. Önce kapıyı kapat (S0), sonra **Yasama/TBMM**
dikeyini aç (S1) — çünkü siyasetin *birincil kaynağı en yoğun* alanı burasıdır ve
kanıt motoru burada çalışır; ardından **hesap sorma katmanını** (vaat takibi, söylem
değişikliği) kur (S2). Genel siyaset (S3) en sonda ve Election Mode varsayılan açık
olarak gelir. Ayrıntı Bölüm 10.

---

## 1. Denetim — bugün ne çalışıyor

Bu koşumda ölçülenler (14 Ağustos 2026, yerel):

| Kontrol | Sonuç |
|---|---|
| `ruff check .` | ✅ temiz |
| `mypy` (96 dosya) | ✅ hata yok |
| `pytest -q` | ✅ **636 geçti, 54 atlandı** (atlananlar veritabanı testleri — Docker kapalıydı) |
| Mimari kural (`evidence/` → `llm/`) | ✅ testte kanıtlı |
| Ham hex / WCAG / Türkçe glif denetimi | ✅ `tests/test_design_tokens.py` yeşil |

Mimari sağlam. Faz 0–4 kapanmış, Faz 5'in ilk beş görevi (F5-01/02/04/15/20/21)
bitmiş. Kanıt motorunun deterministikliği, grounding kapısı, otomatik-yayın-yok
kısıtı ve tasarım sistemi hepsi **test tarafından zorlanıyor** — bu, dikey
genişletirken en çok işe yarayacak sermaye: yeni bir alan açarken hangi
sözleşmenin kırıldığını CI söyleyecek.

---

## 2. Denetim — bulgular

Önem sırasına göre. "P" = öncelik, P1 en yüksek.

### 2.1 Kapı ve ölçüm boşlukları

| P | Bulgu | Kanıt | Etkisi |
|---|---|---|---|
| **P1** | **G4′ kapısı açık değil.** Koşul 1 (7 gün kesintisiz akış), 3 (correction rate), 4 (diversity ratio ≥ 2,5), 7 (kümeleme regresyonu) ölçülmüş değil | Yol Haritası G4′; `BACKLOG.md` B-75/B-76 açık | Faz 5'in resmî ön koşulu. Kapıyı atlayarak dikey açmak, ürünün kendi disiplinini ilk kez *kendi kararıyla* çiğnemesi olur |
| **P1** | **B-81 açık — kaynaklar arası iddia eşleştirme.** `_claim_signature` sözcük tabanlı; aynı olguyu farklı kelimelerle söyleyen iki kaynak eşleşmiyor | `BACKLOG.md` B-81, ölçülmüş örnek olay 686 | `diversity_ratio` hedefinin (2,5) gerçek engeli. **Siyasette bu daha da kötüleşir**: aynı olay 8 kaynakta 8 farklı cümleyle anlatılır |
| **P2** | **B-82 denenmedi.** `number` tiplemesi kaçırılıyor; düzelirse B-81'e gerek kalmadan çapraz teyit kurulabilir | `BACKLOG.md` B-82 | B-81'den **ucuz ve risksiz**. Sıra bozulmuş: pahalı olan açık, ucuz olan denenmemiş |
| **P2** | **Golden Set eksik** (55 makale + 24 iddia; hedef 300 + 150) | B-57 | G2 koşul 3 buna bağlı. Siyaset dikeyi **ayrı** bir Golden Set daha isteyecek (150 makale) |
| **P2** | **Veri takvimi yarım.** TÜİK yayımlama takvimi ve TCMB PPK takvimi okunamıyor; `config/calendar_2026.yml`'de 10 kayıt `verified: false` | B-42, B-61 | "Beklenen gelişmeler" Spec §9.5'te *"MVP'nin gizli kozu"* diye geçiyor ve yarım duruyor. Siyasette karşılığı çok daha değerli: TBMM gündemi, komisyon takvimi, seçim takvimi |
| **P3** | **B-67/B-68 açık** — sağlayıcı karşılaştırması hiç koşulmadı (`ANTHROPIC_API_KEY` boş), aylık kota tavanı ölçülmedi | BACKLOG | Üretim modeli kararı (D18) kendi kaydında "🟡 zayıf" — iki aday ayrışmadı, karar gecikmeye dayandı. **Siyasi metinde Türkçe nüans ekonomiden zordur**; bu kararın yeniden ölçülmesi gerekiyor |
| **P3** | **B-60 açık** — `event_relations` yalnızca `same_thread`; `updates`/`contradicts` yok | BACKLOG | Söylem değişikliği takibinin (muhalif içeriğin en güçlü kozu) veri modeli eksik |

### 2.2 Kalite kapısının kendi zafiyetleri

| P | Bulgu | Kanıt | Neden önemli |
|---|---|---|---|
| **P1** | **Veritabanı testleri sessizce atlanıyor.** `PD_DATABASE_URL` yoksa `pytest.skip` — bu koşumda **54 test hiç koşmadı** ve paket yine "yeşil" göründü | `tests/conftest.py:36` | Atlananlar arasında şema CHECK kısıtları, merge/split geri alınabilirliği, canlı şema denetimi var — yani **pazarlık edilemez kısıtların bir kısmı**. Bu, B-77'nin (bayat imaj) kardeşi: *depoda yeşil, gerçekte koşmamış*. `pd ci` en az bir **uyarı** basmalı, tercihen `PD_CI_REQUIRE_DB=1` ile kırmalı |
| **P2** | **`make lint` mypy hatasını yutuyor:** `mypy \|\| true` | `Makefile:91` (HEAD'de de var) | B-40 tam olarak bunu kapatmıştı ve README hâlâ *"mypy, continue-on-error **değil** (B-40)"* diyor. `pd.cmd` doğru (`\|\| goto :fail`), GitHub CI doğru — **yalnız Makefile yanlış.** İki çalıştırıcının "birebir karşılık" olduğu iddiası bu satırda kırılıyor |
| **P3** | `pd ci` içinde son adım `pytest -q` **`\|\| goto :fail` almıyor** | `pd.cmd:236` | Çıkış kodu yine de yayılıyor (son komut), ama başarısızlıkta diğer adımların bastığı FAIL bandı görünmüyor ve bu adımdan sonra bir adım eklenirse hata sessizce yutulur |
| **P3** | `make ci` migration adımlarını içermiyor (GitHub CI içeriyor) | `Makefile:195` | Yerelde geçen bir değişiklik CI'da migration idempotensi yüzünden kırılabilir |

### 2.3 Güvenlik ve operasyon

| P | Bulgu | Neden önemli |
|---|---|---|
| **P1** | **`.env` OneDrive altında.** Depo kökü `OneDrive\Belgeler\Projeler\PolitikDesk`; `.env` `.gitignore`'da ama **buluta eşitleniyor** ve içinde canlı LLM anahtarı var | B-84'ün kendi gerekçesiyle **doğrudan çelişiyor**: *"BitLocker diski korur, OneDrive'ın Microsoft'taki kopyasını korumaz."* O gerekçe yedek dökümü için geçerliyse, canlı API anahtarı için daha da geçerli. Yedekler buluttan çıkarıldı, sır çıkarılmadı |
| **P2** | **Çalışma ağacında 27 dosyalık, commit edilmemiş büyük değişiklik** (+5.165 / −3.870), `web/layout.py` silinmiş, `politikdesk/web/ui/`, `DESIGN.md`, `design/`, `.claude/` izlenmiyor | Tek diskte, gözden geçirilmemiş, geri alınamaz durumda duran ~9.000 satır. Plan başlamadan önce **parçalı commit** edilmeli (Bölüm 10, S0-1) |
| **P3** | `_STANDALONE_NAME_RE` tanımlı ama hiç kullanılmıyor | `nlp/entities.py:152` — ölü kod. Zararsız ama siyaset dikeyinde *cazip* hale gelecek; kullanılırsa Bölüm 6.2'deki kapı patlaması riski doğar |

### 2.4 Dikey genişlemesini doğrudan engelleyen yapısal kısıtlar

Bunlar "hata" değil, **tasarım kararı**; ama siyaset dikeyinde yeniden karara
bağlanmaları gerekiyor.

| Kısıt | Nerede | Siyasette ne oluyor |
|---|---|---|
| Konu filtresi 10 ekonomi konusuna kilitli, ülke bağlamı + "olay değil" filtresi var | `ingestion/topics.py` | Siyaset içeriği **elenir**. `classify()` boş tuple döner → makale kaydedilmez |
| Kaynak tavanı 15, tek liste | `config/sources.yml`, `tests/test_sources_config.py` | 5 slot kaldı; siyaset 8–12 ister |
| Varlık sözlüğü ekonomi kurumları (48 kalem) | `nlp/entities.py` | Parti, lider, milletvekili, belediye, yargı kurumu **yok** |
| Unvan kalıbı 8 unvan (Bakan/Başkan/Genel Müdür/Müsteşar/Cumhurbaşkanı) | `nlp/entities.py:140` | "Milletvekili X", "Sözcü Y", "Belediye Başkanı Z" kısmen yakalanır; "Grup Başkanvekili", "Vali", "Savcı" yakalanmaz |
| R3 istisnası "kurumun kendi sayısı" | `evidence/rules.py` | Siyasi beyanda sayı yok; R3 hiç tetiklenmez |
| Üretim kapısı: isimli kişi + `unverified` → 409 | `editorial/guards.py` | Siyasette **her olayda** isimli kişi var. Kapı, kalibre edilmezse üretimi tümüyle durdurur |
| Election Mode varsayılan KAPALI, test bunu zorluyor | `config/election_mode.py`, `tests/test_election_mode.py::test_default_is_off` | Siyaset dikeyinde varsayılanın **dikeye bağlı** olması gerekir |
| Editoryal profilde ideolojik alan yok | `editorial/profile.py`, `migrations/0001`, `tests/test_schema.py` | Kullanıcının editoryal hattı girecek yer yok — Bölüm 4'ün konusu |

---

## 3. Stratejik çerçeve — "muhalif" ne demek, ne demek değil

Bu bölüm planın en kritik yeri, çünkü buradaki karışıklık ürünün ana vaadini
çürütebilir. İki ayrı şey var ve birbirine karıştırılıyor:

**(A) Sistemin siyasi yargı üretmesi.** Bir kaynağı "yandaş/muhalif" etiketlemek,
bir iddiaya "bu hükümet propagandası" demek, kullanıcının ideolojisini modelleyip
saklamak. Bunlar Spec §15 madde 4 ve 5 ile yasak, şema seviyesinde zorlanıyor.

> **Öneri: hiçbiri gevşetilmesin.** Sebep etik değil, **işlevsel**: ürünün tek
> ayırt edici özelliği "her cümlenin arkasında deterministik bir kanıt zinciri
> var" iddiası. Sistem siyasi yargı üretmeye başladığı an bu iddia çöker ve
> geriye kanıt katmanı olan bir LLM sarmalayıcısı kalır. Muhalif içeriğin gücü
> de tam olarak buradan gelir: **çürütülemez olmasından.** Kaynağa etiket
> yapıştıran bir metin tartışmayı kaynağa çeker; sayıya bağlı bir metin
> tartışmayı sayıda tutar.

**(B) Kullanıcının kendi editoryal hattı.** *"Ben ekonomi politikasını eleştiren
bir yazarım; metinlerim iktidarın kararlarını sorgular."* Bu bir **beyan**, bir
sınıflandırma değil; sistemin çıkarımı değil, yazarın sesi. Meşru ve ürünün
"AI senin daha iyi konuşabilmen için çalışır" sözleşmesiyle uyumlu.

Bugün (B)'nin girecek yeri yok. Editoryal Kimlik Kartı 7 soru ve hepsi *biçimsel*
(ton, cümle uzunluğu, emoji). "Eleştir" açısı var ama açıklaması şu:
*"Kanıttaki boşluğu, çelişkiyi veya eksik bağlamı sorgula. Eleştiri VERİYE
yöneliktir, kişiye değil."* — yani **veri eleştirisi**, siyasi eleştiri değil.

### 3.1 Boşluğu nasıl dolduracağız: üç seçenek

| Seçenek | Nasıl | Artı | Eksi |
|---|---|---|---|
| **A. Şemaya alan** — `editorial_profiles`'a `stance` sütunu | 8. soru | Kalıcı, tek yer | ⛔ Spec §10.1 / KVKK m.6 kısıtını doğrudan kırar, `tests/test_schema.py` kırmızıya döner, sürüm artışı + rıza metni gerektirir. **Kazancı bu maliyeti karşılamıyor** |
| **B. Oturumluk açı** — her üretimde kullanıcı serbest metin girer, saklanmaz | Draft ekranında kutu | KVKK'ya hiç dokunmaz | Her seferinde yeniden yazmak; tutarlılık yok |
| **C. ✅ Önerilen — dosya tabanlı Editoryal Hat** | `config/editorial_stance.md`, kullanıcının kendi yazdığı, **`.gitignore`'da**, DB'ye yazılmayan bir dosya. `profile_compiler` derlenmiş bloğun sonuna ekler | Kalıcı + tutarlı; şema kısıtı **harfiyen** korunur (veritabanında ideolojik alan yok, iddia doğru kalır); tek kullanıcılı araçta doğal yer; silmek = dosyayı silmek | Yedeğe girmez (kullanıcı ayrı saklamalı); LLM sağlayıcısına gider — bu `.env` gibi bir sır değil ama bilinçli olunmalı |

**Seçenek C'nin sınırları — kod ile zorlanacak:**

1. Hat bloğu **yalnızca üsluba** etki eder. `SYSTEM_PROMPT`'un grounding, sayı/tarih,
   kanıt durumu ve "kişiye değil karara" kuralları **hattın üstünde** kalır ve
   prompt'ta bu açıkça yazılır ("çatışırsa yukarısı kazanır" kalıbı zaten var).
2. Hat, **kanıt motoruna dokunamaz.** `evidence/` paketi bu dosyayı okuyamaz —
   `scripts/check_architecture.py`'a ikinci bir kural olarak eklenir.
3. Hat, **kaynak seçimine dokunamaz.** Sıralama `salience`'tan gelir; hat bir
   kaynağı öne çıkaramaz. Aksi hâlde ürün echo chamber üretir (Spec §10.3).
4. Boş dosya = bugünkü davranış. Regresyon testi bunu kanıtlar.

### 3.2 Yeni dördüncü açı: "Hesap Sor"

Üç açı (Bilgilendir / Analiz Et / Eleştir) siyaset için yetmiyor. Muhalif içeriğin
asıl formu **hesap sormadır** ve bunun kanıtlanabilir bir tanımı var:

> **Hesap Sor:** Bir vaadi/hedefi, gerçekleşmesiyle yan yana koyar. Girdi yine
> yalnızca `claims` + `evidence`'tır; fark, kanıt setine **geçmiş bir olayın**
> iddiasının da girmesidir (`event_relations` üzerinden).

Bu açı kanıt disiplinini gevşetmez, **sıkılaştırır**: "X, 2025'te enflasyonun %20
olacağını söylemişti; TÜİK Ağustos 2026'da %33,5 açıkladı" cümlesinin iki ucu da
kanıta bağlıdır. Bugünkü "Eleştir" açısının yapamadığı şey tam olarak budur ve
prompt'ta bu eksiklik açıkça itiraf edilmiş durumda (*"Daha fazla veri gerekiyor"
bir eleştiri değildir*).

**Ön koşulu:** `promise` iddia tipi + `event_relations.fulfils/contradicts`
(Bölüm 7). Yani "Hesap Sor" bir prompt işi değil, bir **veri modeli** işidir —
ve bu, planın en yüksek değerli parçasıdır.

---

## 4. Dikey kavramının kodda karşılığı

Bugün "dikey" yalnızca `sources.yml`'de bir etiket (`vertical: macro_economy`);
kod tarafında karşılığı yok. Genişlemeden önce bu kavram kodlanmalı, yoksa her
yeni dikey `topics.py`'a yeni kelime ekleme biçiminde birikir ve filtre çöker.

**Önerilen yapı:**

```
politikdesk/verticals/
├── __init__.py        registry: slug -> VerticalSpec
├── base.py            VerticalSpec (konu sözlüğü, ülke bağlamı, non-event kalıpları,
│                      varsayılan Election Mode, kanıt eşik profili)
├── macro_economy.py   bugünkü topics.py içeriği, aynen taşınır
└── legislation.py     yeni: yasama/TBMM
```

- `ingestion/topics.py` → ince bir cephe; `classify(text, vertical=...)`.
- Kaynak `vertical` alanı alır; bir kaynak birden çok dikeye yazabilir.
- `max_sources` **dikey başına** tanımlanır (öneri: dikey başına 12, toplam 30 —
  Yol Haritası zaten *"toplam kaynak 40'ı aşmaz"* diyor).
- Regresyon koruması: mevcut Golden Set `macro_economy` diki üzerinde koşar ve
  precision ≥ 0,88 kalmalı. Yeni dikeyin kendi Golden Set'i olur.

Bu, D6'nın yeniden yazılması demek → **Spec v3.4** (Bölüm 9).

---

## 5. Kaynak stratejisi

### 5.1 İlke: eleştirinin gücü kaynak seçiminden değil, kanıttan gelir

Muhalif içerik üretecek bir masaya yalnızca muhalif kaynak koymak sezgisel olarak
doğru görünür ve **ürünü bozar**. İki somut sebep:

1. **Bağımsız sayım şişer, teyit çürür.** `independent_count` yayın grubu sayar.
   Aynı çizgideki üç yayın aynı iddiayı aktarınca sistem "üç bağımsız kaynak
   doğruluyor" der — doğrulamıyorlar, aynı kaynağı aktarıyorlar. Spec §9.2 bunu
   *"teyit yokluğundan daha zararlı"* diye kaydetmiş.
2. **Metin çürütülebilir olur.** İktidara yakın yayının da aynı sayıyı verdiği bir
   iddia tartışılamaz; yalnızca muhalif yayında geçen bir iddia tartışmayı
   kaynağa çeker ve asıl mesele kaybolur.

> **Kural önerisi:** Siyaset dikeyinde her yeni Tier 3 kaynağı için **karşı
> çerçeveden** bir kaynak da eklenir. Ölçüt yayın çizgisi değil,
> `independence_group` çeşitliliğidir — bu, sisteme siyasi etiket sokmadan
> uygulanabilir (kayıt defterinde sahiplik yapısı yazılır, siyasi konum değil).

### 5.2 Aday kaynaklar

⚠️ **Hiçbiri doğrulanmış değildir.** Depo kuralı: `verified: true` ancak canlı
koşum sonrası yazılır (F5-04'te dört aday elenmişti). Aşağıdaki tablo **görev
listesidir**, kaynak listesi değil. Her aday için: akış var mı, gerçek haber mi
dönüyor, `robots.txt` ne diyor, ToS durumu, sahiplik grubu.

**Aşama S1 — Yasama/TBMM (Tier 1 ağırlıklı):**

| Aday | Rol | Not / doğrulanacak |
|---|---|---|
| TBMM — kanun teklifleri | Birincil | Teklif metni, komisyon durumu. Yasama sürecinin çıpası |
| TBMM — genel kurul tutanakları | Birincil | Beyanların **birebir** kaynağı; `attribution` iddialarının Tier 1 dayanağı |
| TBMM — komisyon gündemi | Takvim | `scheduled_events` için; Spec §9.5'in siyaset karşılığı |
| Cumhurbaşkanlığı — kararname/genelge/duyuru | Birincil | Yürütme kararlarının çıpası |
| Resmî Gazete (**mevcut**) | Birincil | Konu filtresi genişletilir: atama, kararname, yönetmelik |
| **Sayıştay denetim raporları** | Birincil | ⭐ Hesap sorma katmanının en değerli girdisi: kamu zararı bulguları, resmî ve alıntılanabilir. Yıllık/dönemsel yayın |
| KİK / Kamu İhale Bülteni | Birincil | İhale iddiaları için doğrulama zemini |

**Aşama S2/S3 — aktör beyanları ve medya:**

| Grup | Aday | Rol |
|---|---|---|
| Parti resmî kaynakları | İktidar ve muhalefet partilerinin **basın açıklaması akışları** | `attribution` için birincil, `fact` için **değil** (Bölüm 6.3) |
| Ajans | AA (mevcut, genel akışa geçiş), DHA, İHA | ⚠️ DHA ve mevcut CNN Türk **aynı sahiplik grubunda** olabilir — bağımsız sayımı şişirir, doğrulanmalı |
| Doğrulama | Teyit.org, Doğruluk Payı | ⭐ Çelişki tespitinde (R1) doğrudan işe yarar; ToS kontrolü şart |
| Medya — çerçeveleme çeşitliliği | Farklı sahiplik gruplarından, **her iki çerçeveden** en az ikişer yayın | Ölçüt: ayrı `independence_group`, gerçek haber (SEO dolgusu değil) |
| Uzman/düşünce kuruluşu | Bütçe ve politika analizi yapan bağımsız kuruluşlar | Tier 3; B-45'in (boş uluslararası çapraz teyit rolü) kısmi karşılığı |

**Kaynak sayısı bütçesi:** makro ekonomi 10 (mevcut) + yasama 7 + siyaset 8 = 25;
tavan dikey başına 12 / toplam 30. Kademe kuralı korunur: **tek adımda açılmaz** —
önce 4 kaynak, bir hafta ölçüm, regresyon yoksa devam.

---

## 6. Motor değişiklikleri

### 6.1 Konu filtresi (`topics.py` → `verticals/legislation.py`)

Yeni konu sözlüğü (ilk taslak, ölçümle kalibre edilecek):
`yasama_sureci` · `atama_ve_kadro` · `denetim_ve_yolsuzluk` · `butce_hakki` ·
`yargi_ve_hukuk` · `secim_ve_ysk` · `yerel_yonetim` · `ifade_ozgurlugu_ve_basin` ·
`sosyal_politika` · `dis_politika`.

Dikkat edilecekler (mevcut dosyanın kendi acı tecrübeleri, aynen geçerli):
- Kelime **başı sabit, sonek serbest** kalıbı korunur (`harç` → `harcandı` tuzağı).
- Kısa/çok anlamlı kısaltma alınmaz.
- `NON_EVENT_PATTERNS` genişletilir: anket sonucu listeleri, "kim kazanır" içerikleri,
  köşe yazısı akışları — bunlar konuya uyar ama **olay değildir**.
- ⚠️ **Yeni risk:** siyasette yorum/köşe yazısı oranı ekonomiden çok yüksek.
  Haber/yorum ayrımı bugün ingestion'da yok. Ölçülmeli; gerekirse kaynak bazında
  `content_kind` filtresi eklenmeli.

### 6.2 Varlık katmanı (`nlp/entities.py`)

- Kurum sözlüğü: partiler, TBMM organları, yargı kurumları (AYM, Yargıtay, Danıştay,
  HSK), YSK, Sayıştay, büyükşehir belediyeleri, valilikler.
- Unvan listesi: `Genel Başkanı`, `Genel Başkan Yardımcısı`, `Grup Başkanvekili`,
  `Milletvekili`, `Sözcüsü`, `Belediye Başkanı`, `Valisi`, `Başsavcı`.
- `KEY_ENTITIES` (kümeleme kısıtı) siyaset için yeniden düşünülmeli: bugün 6 ekonomi
  kurumu var; siyasette "ortak Tier-1 varlık" kuralı gevşek kalırsa yanlış birleşme
  patlar.

> ⚠️ **En yüksek riskli tek değişiklik burası.** `guards.py` isimli kişi kapısı
> `extract_people`'a bağlı. Bugün kapı yalnızca **unvanla anılan** isimleri
> görüyor ve bu bilinçli bir kısıt. Siyasette isimli kişi her olayda var;
> sözlük genişleyince kapı **her olayı 409'a** düşürebilir. Bu yüzden:
> **önce ölç, sonra genişlet** — 100 siyaset makalesinde kapının kaç olayı
> bloke ettiği, sözlük değişmeden önce ve sonra ölçülmeli (yeni görev B-90).
> `_STANDALONE_NAME_RE` (ölü kod) bu aşamada **kullanılmamalı**, silinmeli.

### 6.3 Kanıt motoru — R8 "beyan kaydı"

Siyasetin yapısal farkı: iddiaların çoğu `attribution` tipinde ve **iki ayrı soru**
var, bugün ayrılmıyorlar:

| Soru | Bugün | Olması gereken |
|---|---|---|
| Beyan **yapıldı mı?** | Kanıt kuralları buna bakmıyor | Tutanak/resmî kayıt varsa **doğrulanabilir** |
| Beyanın **içeriği doğru mu?** | Tek durum alanı ikisini karıştırıyor | Ayrı ölçülmeli; çoğu zaman ⚪ kalır |

**Öneri — R8 (yeni kural, R7 tavanının altında):**

> Bir `attribution` iddiası, beyanın **birincil kaydına** (TBMM tutanağı, kurumun
> kendi açıklaması, video/metin tam kaydı) bağlanmışsa `attribution_verified`
> durumunu alır. Bu durum "beyan sabittir, **içeriği doğrulanmamıştır**" anlamına
> gelir ve etiketi UI'da bu şekilde okunur.

Faydası doğrudan: bugünkü kurallarla siyasi bir olayda hemen her iddia 🟠/⚪ olur,
üretim kapısı kapanır ve **ürün siyasette hiç çalışmaz**. R8, kapıyı kanıt
disiplinini gevşetmeden açar — çünkü ölçtüğü şey gerçekten doğrulanmıştır: o kişi
gerçekten bunu söylemiştir.

Bu Spec §8.1 (durum listesi) ve §8.3 (kural sırası) değişikliğidir → **v3.4**.
DB'de `evidence_status` CHECK kısıtı ve `claims` şeması etkilenir → migration.

### 6.4 Salience kalibrasyonu

`velocity` bileşeni (ilk saatte 10 makale = tam puan) siyasette **her olayda**
doluyor; ayırt ediciliğini kaybeder. `NORM_VELOCITY_MAX` dikeye bağlı olmalı.
`has_primary_source` ise siyasette daha ayırt edici — ağırlığı artırılabilir.
**Ölçümle**, tahminle değil: mevcut breakdown alanı bunu zaten kaydediyor.

### 6.5 Election Mode

Siyaset dikeyinde varsayılan **AÇIK** olmalı (Spec §12.6'nın kendi mantığı bu).
Bugünkü `test_default_is_off` testi korunur ama anlamı değişir: *"makro ekonomi
dikeyinde varsayılan kapalı"*. Mod artık ortam değişkeni **ve** dikeyden okunur.

⚠️ Dikkat: Election Mode `single_source` iddiada üretimi durdurur. R8 olmadan
siyasette bu, üretimin tümüyle kapanması demektir. **Sıra önemli: önce R8, sonra
Election Mode.**

---

## 7. Hesap sorma katmanı — planın en yüksek değerli parçası

Kullanıcının asıl istediği ürün burada. Üç yapı taşı:

**1. `promise` iddia tipi.** Mevcut dört tip (`fact`/`number`/`attribution`/
`prediction`) vaadi taşımıyor. `prediction` "gelecek doğrulanamaz" diye R0'la
kısa devre yapıyor — ama bir **vaat** gelecekte doğrulanabilir hale gelir. Yeni
tip: `promise` — R0'a *girmez*, `unverified` başlar ve karşılığı geldiğinde
`event_relations` üzerinden bağlanır.

**2. `event_relations` genişlemesi (B-60'ın üstüne).** `same_thread` yanına:
`updates` · `contradicts` · `fulfils` · `fails`. `contradicts` özellikle kritik:
söylem değişikliğinin veri modeli budur.

**3. Political Memory v1 (B-15).** Sorgu: *"X kişisi/kurumu Y konusunda geçmişte
ne demişti?"* Veri zaten birikiyor (olay grafiği, iddialar, `first_reported_at`);
eksik olan sorgu arayüzü.

Bu üçü tamamlandığında "Hesap Sor" açısı (Bölüm 3.2) **kanıtla beslenir** ve
ürün, kullanıcının hedefine ChatGPT'nin yapısal olarak yapamayacağı bir şeyle
cevap verir: *kaynaklı, tarihli, çürütülemez bir vaat–gerçekleşme karşılaştırması.*

---

## 8. Hukuki ve platform riski

> Bu bölüm hukuki görüş **değildir**; depo zaten *"hukuki tavsiye içermez"* diyor
> ve F0-10 danışmanlık adımı "kişisel araç" kararıyla kapsam dışına alınmıştı.
> **Siyaset dikeyi bu kararı yeniden değerlendirmeyi gerektirir** — çünkü D4'ün
> gerekçe tablosunda makro ekonominin seçilme sebeplerinden biri açıkça
> *"hukuki risk profili: en düşük"* idi. Genel siyaset o tabloda "en yüksek".

Risk kullanıcının **yayınından** doğar, aracın kendisinden değil — ama araç
kullanıcının riskini azaltacak biçimde tasarlanmalı. Mevcut kapılar tam da bunun
için var ve siyaset dikeyinde **güçlendirilmeli**:

| Mevcut koruma | Siyasette ne yapılmalı |
|---|---|
| Grounding — kanıtta olmayan sayı/tarih/alıntı taslağı düşürür | Aynen korunur; siyasette daha da kritik |
| İsimli kişi + `unverified` → üretim yok | Kalibre edilir (6.2), **kaldırılmaz** |
| Pre-publish check (Spec §14.4, 6 kontrol) | **İsnat dili kontrolü** eklenir: "iddia edildi/yargı kararı var/soruşturma açıldı" ile "yaptı/çaldı/yolsuzluk yaptı" farkı — bir cümlenin *aktarım* mı *isnat* mı olduğunun kullanıcıya gösterilmesi |
| Kaynağa siyasi etiket yok | Korunur |
| Otomatik yayın yok — Web Intent | Korunur. `editorial/service.py:298` yalnızca **adres** üretiyor; X'e giden POST yolu yok. Bu, hesap askıya alma riskine karşı da en güvenli tasarım |

**Ek öneri:** taslak arşivinde her yayınlanan metin için hangi iddialara dayandığı
(`cited_claim_ids`) zaten saklanıyor. Siyaset dikeyinde bunu **kalıcı** yapmak —
"bu tweet'i neye dayanarak yazdım" sorusunun kanıtlı cevabı — hem editoryal hem
pratik bir koruma. (B-04 içerik arşivi, Faz 5.)

---

## 9. Spec v3.4 — gereken değişiklikler

Aşağıdakilerin her biri "pazarlık edilemez kısıt" tablosuna dokunuyor ve depo
kuralı gereği **sürüm artışı** istiyor. Spec bugün 🔒 v3.3'te dondurulmuş durumda;
bu plan onaylanırsa v3.4 açılır.

| # | Bölüm | Değişiklik | Gerekçe |
|---|---|---|---|
| 1 | §5 | MVP dikeyi → **çok dikey**; `verticals` kavramı, genişleme sırası öne alınır | Bölüm 4 |
| 2 | §9.2 / D6 | Kaynak tavanı: toplam 15 → **dikey başına 12, toplam 30** | Bölüm 5 |
| 3 | §9.1 | Yeni kaynak türü: `party` / `political_actor` — Tier 1 **değil**, `attribution` için birincil | Bölüm 5.2 |
| 4 | §8.1 / §8.3 | **R8 + `attribution_verified` durumu** | Bölüm 6.3 |
| 5 | §7.3 | Yeni iddia tipi `promise`; `event_relations` genişlemesi | Bölüm 7 |
| 6 | §14.3 | Dördüncü açı: **Hesap Sor** | Bölüm 3.2 |
| 7 | §10.1 | Editoryal Hat: **kullanıcının kendi beyanı**, şema dışı dosyada, sınıflandırma üretilmez | Bölüm 3.1 seçenek C |
| 8 | §12.6 | Election Mode varsayılanı **dikeye bağlı** | Bölüm 6.5 |
| 9 | §12 | Hukuki çerçevenin siyaset dikeyi için yeniden değerlendirilmesi | Bölüm 8 |

Değişmeyecekler (açıkça kayda geçsin): §15'in 14 maddesinin **hiçbiri**
gevşemiyor. Kaynağa siyasi etiket yok, ideoloji sınıflandırması yok, otomatik
yayın yok, doğruluk skoru yok, engagement girdisi yok.

---

## 10. Yol haritası

### Aşama S0 — Kapıyı kapat (2–3 hafta) · *dikey açılmadan önce*

| # | İş | Çıktı / DoD |
|---|---|---|
| S0-1 | Çalışma ağacındaki 27 dosyalık değişikliği **parçalı commit** et | UI/tasarım sistemi ayrı, refactor ayrı; her commit'te `pd ci` yeşil |
| S0-2 | `.env`'i bulut dışına taşı (B-84'ün kendi gerekçesi) | `%LOCALAPPDATA%\PolitikDesk\.env` + `PD_ENV_FILE`; anahtar rotasyonu |
| S0-3 | `Makefile:91` `mypy \|\| true` → zorunlu; `pd ci` pytest adımına `\|\| goto :fail` | İki çalıştırıcı gerçekten birebir |
| S0-4 | **DB testleri sessizce atlanmasın** | `PD_CI_REQUIRE_DB=1` ile kırar; atlanınca `pd ci` sonunda uyarı satırı |
| S0-5 | **B-82** — `number` tiplemesi (ucuz olan önce) | Golden Set'te `number` isabet oranı ölçülür |
| S0-6 | **B-81** — iddia eşleştirme, ancak B-82 yetmezse | ⚠️ Golden Set'te precision ölçülmeden **uygulanmaz** (yanlış teyit teyitsizlikten kötüdür) |
| S0-7 | G4′ ölçümü: 7 gün kesintisiz akış + `diversity_ratio` + correction rate | Kapı raporu `docs/FAZ5-KAPI.md` |
| S0-8 | Golden Set 300 makale + 150 iddiaya çıkar (B-57) | G2 koşul 3 kapanır |

**Kapı:** G4′'ün 9 koşulu. Tutmuyorsa S1 başlamaz.

### Aşama S1 — Yasama/TBMM dikeyi (3 hafta)

| # | İş |
|---|---|
| S1-1 | `politikdesk/verticals/` altyapısı; `macro_economy` aynen taşınır, regresyon testi |
| S1-2 | `legislation` konu sözlüğü + Türkiye bağlamı + non-event kalıpları |
| S1-3 | Kaynak adaptörleri: TBMM (teklif/tutanak/komisyon), Cumhurbaşkanlığı, Sayıştay · **kademeli: önce 4** |
| S1-4 | Varlık sözlüğü genişlemesi — **önce kapı ölçümü** (B-90), sonra genişletme |
| S1-5 | **R8 + `attribution_verified`** + migration + kural testleri |
| S1-6 | `claims.v3` prompt'u: `attribution` ve `promise` tiplerine duyarlı |
| S1-7 | Yasama Golden Set (150 makale) + kümeleme precision ölçümü |
| S1-8 | Komisyon/genel kurul takvimi → `scheduled_events` |

**Kapı:** kümeleme precision ≥ 0,88 (yeni set) · makro ekonomi metrikleri
regresyona uğramamış · üretim kapısının blokaj oranı ≤ %30.

### Aşama S2 — Hesap sorma katmanı (3 hafta)

| # | İş |
|---|---|
| S2-1 | `promise` iddia tipi + şema + R kuralları |
| S2-2 | `event_relations`: `updates`/`contradicts`/`fulfils`/`fails` (B-60) |
| S2-3 | Political Memory v1 — olay zinciri sorgusu (B-15) |
| S2-4 | **"Hesap Sor" açısı** + prompt + grounding testleri |
| S2-5 | **Editoryal Hat** (`config/editorial_stance.md`) + mimari kural + regresyon testi |
| S2-6 | Pre-publish check: isnat dili kontrolü |
| S2-7 | İçerik arşivi (B-04) — "bu metni neye dayanarak yazdım" |

**Kapı:** 20 taslakta kanıtta olmayan sayı/tarih = %0 · vaat–gerçekleşme
zincirinin en az 5 gerçek örnekte doğru kurulduğu elle doğrulanmış.

### Aşama S3 — Genel siyaset (3 hafta, en riskli)

| # | İş |
|---|---|
| S3-1 | Election Mode dikeye bağlı varsayılan + **canlı test** |
| S3-2 | Medya kaynakları — her iki çerçeveden, ayrı sahiplik grupları, kademeli |
| S3-3 | Parti/aktör kaynakları (`attribution` için birincil) |
| S3-4 | Haber/yorum ayrımı ölçümü ve gerekirse filtre |
| S3-5 | Hukuki çerçevenin yeniden değerlendirilmesi (Bölüm 8) |
| S3-6 | Salience yeniden kalibrasyonu |

**Kapı:** correction rate ≤ %3 · `diversity_ratio` ≥ 2,5 **genişlemeye rağmen** ·
üretilen 30 taslakta isnat dili bulgusu elle denetlenmiş.

### Paralel yürüyebilecekler
Arayüz işleri (dikey seçici, vaat takibi ekranı, hesap sorma akışı), model
yeniden ölçümü (B-67/B-68/D18), takvim kaynaklarının çözülmesi (B-42/B-61).

---

## 11. Karar bekleyen maddeler

| # | Karar | Öneri |
|---|---|---|
| K1 | G4′ kapısı kapatılmadan dikey açılsın mı? | **Hayır** — S0 önce. Kapıyı ilk kez kendi kararıyla atlamak, disiplinin kendisini geçersizleştirir |
| K2 | İlk dikey hangisi? | **Yasama/TBMM.** Birincil kaynak yoğun, kanıt motoru burada çalışır. Genel siyasete doğrudan girmek, motoru kalibre etmeden en zor sahaya çıkmaktır |
| K3 | Editoryal Hat nasıl saklansın? | **Seçenek C** — dosya tabanlı, DB dışı (Bölüm 3.1) |
| K4 | Karşı çerçeveden kaynak eklenecek mi? | **Evet** — eleştirinin çürütülemez olması buna bağlı (Bölüm 5.1) |
| K5 | Spec v3.4 açılsın mı? | **Evet** — 9 madde, hiçbiri §15'i gevşetmiyor |
| K6 | Hukuki danışmanlık kapsam dışı kalsın mı? | **Yeniden değerlendirilmeli** — D4'ün gerekçesi "en düşük hukuki risk"ti; genel siyaset o tablonun diğer ucu |

---

## 12. Yeni backlog kalemleri

`BACKLOG.md`'ye eklenecekler (son kayıtlı numara B-87):

| # | Kalem | Faz |
|---|---|---|
| B-88 | `.env` bulut eşitlemesi altında — B-84 gerekçesinin sırlara uygulanması | S0 |
| B-89 | DB testleri sessizce atlanıyor; `pd ci` yeşil görünüyor | S0 |
| B-90 | **Üretim kapısı blokaj oranının siyaset içeriğinde ölçülmesi** (sözlük genişletmeden önce) | S1 |
| B-91 | `verticals/` altyapısı — dikey kavramının kodda karşılığı | S1 |
| B-92 | R8 `attribution_verified` — beyan kaydı kuralı | S1 |
| B-93 | `promise` iddia tipi + vaat–gerçekleşme zinciri | S2 |
| B-94 | "Hesap Sor" açısı | S2 |
| B-95 | Editoryal Hat dosyası + mimari kural | S2 |
| B-96 | Pre-publish check: isnat dili kontrolü | S2 |
| B-97 | Haber/yorum ayrımı — siyaset kaynaklarında köşe yazısı oranı | S3 |
| B-98 | `Makefile` `mypy \|\| true`; `pd ci` pytest adımı `\|\| goto :fail` almıyor | S0 |
| B-99 | `_STANDALONE_NAME_RE` ölü kod — silinsin (siyasette kullanılması cazip ve tehlikeli) | S1 |
