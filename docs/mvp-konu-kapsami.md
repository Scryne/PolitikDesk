# MVP Konu Kapsamı — Makro Ekonomi / Para Politikası

**Görev:** F0-03 · **Kaynak:** Spec §5 · **Bağımlılık:** F0-02 (spec-freeze)

> Bu belge MVP dikeyinin **konu sınırını** normatif olarak tanımlar. Sınır
> dışında kalan bir olay sisteme girmez, Golden Set'e etiketlenmez, feed'de
> görünmez. Sınırı genişletmek `BACKLOG.md` üzerinden ve faz kapısıyla olur.

**Makine-okunur karşılığı:** `eval/golden_set_tools.py` → `VALID_TOPICS`.
Bu listedeki 10 slug dışında bir `topic` değeri Golden Set doğrulayıcısı
tarafından **reddedilir** — kapsam kayması sessizce olamaz.

---

## Kapsam kuralı

Bir olay MVP kapsamındadır ancak ve ancak:

1. **Konu**, aşağıdaki 10 başlıktan birine düşüyorsa; **ve**
2. **Birincil kaynağı** Tier 1 bir kurumun yayını olabiliyorsa (fiilen olmasa
   bile — konu türü itibarıyla resmî bir çıpası bulunmalı); **ve**
3. İddiaların en az biri **sayısal veya kurumsal olarak doğrulanabilir**ise.

3. koşul kritiktir: Spec §5'in gerekçesi, motorun "doğru kümelendi mi",
"kanıt doğru eşlendi mi" sorularının **nesnel** olarak yanıtlanabildiği bir
alanda kalibre edilmesidir. "Ekonomi hakkında siyasi tartışma" bu koşulu
sağlamaz ve kapsam dışıdır.

### Sınırda kalan durumlar — karar tablosu

| Durum | Karar | Gerekçe |
|---|---|---|
| Bakanın enflasyon hakkında açıklaması | ✅ İçeride | `attribution` tipi iddia; kaynak ve söz doğrulanabilir |
| Bakanın açıklamasına muhalefetin tepkisi | ❌ Dışarıda | Genel siyaset dikeyi (B-12) |
| Ekonomist yorumu (Tier 4, kullanıcı içe aktarımı) | ✅ İçeride, kısıtlı | Yalnızca `single_source` tavanı (R7); asla 🟢 olamaz |
| Şirket bilanço/kâr haberi | ❌ Dışarıda | Mikro ekonomi; MVP makro dikeyi |
| Borsa endeks hareketi | ❌ Dışarıda | Piyasa fiyatı ≠ makro politika olayı |
| Kur hareketinin **kaynağı** TCMB kararı ise | ✅ İçeride | `kur_ve_rezervler` |
| Asgari ücret komisyonu toplantısı | ✅ İçeride | `asgari_ucret_ve_zamlar` |
| İşçi sendikası eylemi | ❌ Dışarıda | Toplumsal olay; ekonomik veri çıpası yok |
| IMF/Dünya Bankası Türkiye raporu | ✅ İçeride | `buyume` veya `derecelendirme`; kurumsal kaynak |
| Uluslararası emtia fiyatı (petrol, altın) | ❌ Dışarıda | Türkiye makro politikası değil |

---

## 10 konu

Her konu için: kapsam tanımı · birincil kaynak · yayın ritmi ·
`scheduled_events` üretiyor mu · örnek olaylar.

---

### 1. `enflasyon` — Enflasyon (TÜFE / ÜFE)

| | |
|---|---|
| **Kapsam** | Aylık ve yıllık TÜFE/ÜFE, çekirdek enflasyon, harcama grubu kırılımları, enflasyon raporu, TCMB enflasyon beklenti anketi |
| **Birincil kaynak** | TÜİK (veri), TCMB (rapor ve beklenti anketi) |
| **Ritim** | TÜFE/ÜFE her ayın **3'ünde 10:00** · Enflasyon Raporu yılda 4 · Beklenti Anketi aylık |
| **Takvim üretir mi** | ✅ Evet — `scheduled_events`in en yoğun kaynağı |
| **Tipik iddia tipleri** | `number` (baskın), `attribution`, `prediction` |

**Zor küme uyarısı:** Aynı ay için üç ayrı olay vardır ve **birleştirilmemelidir**:
(a) beklenti anketi, (b) veri açıklaması, (c) veri sonrası TCMB/Bakanlık
değerlendirmesi. Golden Set'in en değerli `hard` örnekleri buradan çıkar.

**Örnek olaylar** *(F0-08 sırasında akışlardan teyit edilecek)*

| # | Olay | Tarih | Kaynak | Teyit |
|---|---|---|---|---|
| 1 | TÜİK Temmuz 2026 TÜFE açıklaması | 3 Ağu 2026 | TÜİK | ☐ |
| 2 | TÜİK Haziran 2026 TÜFE açıklaması | 3 Tem 2026 | TÜİK | ☐ |

---

### 2. `politika_faizi` — Politika faizi ve PPK kararları

| | |
|---|---|
| **Kapsam** | PPK faiz kararı, karar metni, PPK özeti, faiz koridoru, TCMB başkanı sunumu |
| **Birincil kaynak** | TCMB |
| **Ritim** | PPK yılda 8 toplantı, tarihler yıl başında ilan edilir · Karar 14:00 · Özet 5 iş günü sonra |
| **Takvim üretir mi** | ✅ Evet |
| **Tipik iddia tipleri** | `number`, `attribution`, `prediction` |

**Zor küme uyarısı:** İki ardışık PPK kararı yüksek metin benzerliği taşır
(aynı kurum, aynı format, benzer dil). Kümeleme için **en zor** vaka budur —
zaman penceresi ve sayısal çelişki bayrağı (F2-03) burada test edilir.

| # | Olay | Tarih | Kaynak | Teyit |
|---|---|---|---|---|
| 1 | TCMB PPK faiz kararı (Temmuz toplantısı) | Tem 2026 | TCMB | ☐ |
| 2 | TCMB PPK toplantı özeti | Tem 2026 | TCMB | ☐ |

---

### 3. `kur_ve_rezervler` — Kur ve rezervler

| | |
|---|---|
| **Kapsam** | TCMB brüt/net rezervleri, swap hariç net rezerv, döviz alım-satım işlemleri, kur politikasına dair resmî açıklamalar |
| **Birincil kaynak** | TCMB (haftalık analitik bilanço) |
| **Ritim** | Haftalık (Perşembe) rezerv verisi |
| **Takvim üretir mi** | ✅ Evet |
| **Tipik iddia tipleri** | `number` |

**Kapsam sınırı:** Kurun *seviyesi* bir piyasa fiyatıdır, olay değildir.
Kur **politikasına** dair resmî karar/açıklama olaydır.

| # | Olay | Tarih | Kaynak | Teyit |
|---|---|---|---|---|
| 1 | TCMB haftalık rezerv verisi | Haftalık | TCMB | ☐ |
| 2 | Rezerv seviyesine dair TCMB/Bakanlık açıklaması | — | TCMB/Hazine | ☐ |

---

### 4. `butce_ve_hazine` — Bütçe ve hazine nakit dengesi

| | |
|---|---|
| **Kapsam** | Merkezi yönetim bütçe gerçekleşmeleri, hazine nakit dengesi, bütçe sunumu, OVP |
| **Birincil kaynak** | Hazine ve Maliye Bakanlığı |
| **Ritim** | Bütçe gerçekleşmeleri aylık (~15'i) · Nakit dengesi aylık · OVP yılda 1 (Eylül) |
| **Takvim üretir mi** | ✅ Evet |
| **Tipik iddia tipleri** | `number` |

| # | Olay | Tarih | Kaynak | Teyit |
|---|---|---|---|---|
| 1 | Temmuz 2026 merkezi yönetim bütçe gerçekleşmeleri | Ağu 2026 | Hazine | ☐ |
| 2 | Haziran 2026 hazine nakit dengesi | Tem 2026 | Hazine | ☐ |

---

### 5. `issizlik_ve_istihdam` — İşsizlik ve istihdam

| | |
|---|---|
| **Kapsam** | İşgücü istatistikleri, işsizlik oranı, atıl işgücü, istihdam oranı, genç işsizliği |
| **Birincil kaynak** | TÜİK |
| **Ritim** | Aylık işgücü istatistikleri (~10'u) |
| **Takvim üretir mi** | ✅ Evet |
| **Tipik iddia tipleri** | `number` |

| # | Olay | Tarih | Kaynak | Teyit |
|---|---|---|---|---|
| 1 | TÜİK işgücü istatistikleri (Haziran dönemi) | Ağu 2026 | TÜİK | ☐ |
| 2 | TÜİK işgücü istatistikleri (Mayıs dönemi) | Tem 2026 | TÜİK | ☐ |

---

### 6. `buyume` — Büyüme (GSYH)

| | |
|---|---|
| **Kapsam** | Çeyreklik GSYH, sektörel büyüme, harcama yöntemiyle GSYH, yıllık revizyonlar |
| **Birincil kaynak** | TÜİK |
| **Ritim** | Çeyreklik (dönem bitiminden ~2,5 ay sonra) |
| **Takvim üretir mi** | ✅ Evet |
| **Tipik iddia tipleri** | `number` |

**Zor küme uyarısı:** İlk açıklama ile sonraki **revizyon** ayrı olaylardır.
Aynı çeyreğe ait iki farklı rakam aynı olaya atanırsa sayısal çelişki bayrağı
(F2-03) tetiklenmelidir — bu bir Golden Set `hard` vakasıdır.

| # | Olay | Tarih | Kaynak | Teyit |
|---|---|---|---|---|
| 1 | 2026 1. çeyrek GSYH açıklaması | Haz 2026 | TÜİK | ☐ |
| 2 | 2026 2. çeyrek GSYH açıklaması | Eyl 2026 | TÜİK | ☐ |

---

### 7. `asgari_ucret_ve_zamlar` — Asgari ücret, memur ve emekli zamları

| | |
|---|---|
| **Kapsam** | Asgari Ücret Tespit Komisyonu süreci ve kararı, memur maaş katsayısı, toplu sözleşme zam oranları, SGK emekli aylık artışları, refah payı |
| **Birincil kaynak** | Resmî Gazete, Hazine ve Maliye Bakanlığı, TÜİK (enflasyon farkı hesabı) |
| **Ritim** | Asgari ücret Aralık · Memur/emekli zamları Ocak ve Temmuz · Toplu sözleşme yılda 1 |
| **Takvim üretir mi** | ✅ Evet (Ocak/Temmuz/Aralık yoğunlukları) |
| **Tipik iddia tipleri** | `number`, `attribution` |

| # | Olay | Tarih | Kaynak | Teyit |
|---|---|---|---|---|
| 1 | Temmuz 2026 memur/emekli zam oranı | Tem 2026 | Hazine / Resmî Gazete | ☐ |
| 2 | Asgari Ücret Tespit Komisyonu süreci | Ara 2026 | Resmî Gazete | ☐ |

---

### 8. `vergi_ve_harclar` — Vergi ve harç düzenlemeleri

| | |
|---|---|
| **Kapsam** | Vergi oranı değişiklikleri, ÖTV/KDV düzenlemeleri, yeniden değerleme oranı, harç tarifeleri, vergi affı/yapılandırma, Cumhurbaşkanı kararları |
| **Birincil kaynak** | Resmî Gazete (birincil), Hazine ve Maliye Bakanlığı |
| **Ritim** | Düzensiz — Resmî Gazete günlük taranır |
| **Takvim üretir mi** | ⚠️ Kısmen (yeniden değerleme oranı Kasım'da belli olur) |
| **Tipik iddia tipleri** | `fact`, `number` |

**Not:** Bu konu `scheduled_events` üretmediği için "beklenen gelişme"
özelliğine katkı vermez; ancak Resmî Gazete Tier 1 olduğundan R3 ile
doğrudan 🟢 üretebilen en güçlü konulardan biridir.

| # | Olay | Tarih | Kaynak | Teyit |
|---|---|---|---|---|
| 1 | ÖTV/KDV oranı değişikliği (Cumhurbaşkanı Kararı) | — | Resmî Gazete | ☐ |
| 2 | Vergi yapılandırma düzenlemesi | — | Resmî Gazete | ☐ |

---

### 9. `kamu_borclanmasi` — Kamu borçlanması

| | |
|---|---|
| **Kapsam** | İç/dış borçlanma ihaleleri, borçlanma stratejisi, iç borç stoku, eurobond ihraçları, borç servisi |
| **Birincil kaynak** | Hazine ve Maliye Bakanlığı |
| **Ritim** | Aylık iç borçlanma stratejisi (ay sonu) · İhaleler takvimli |
| **Takvim üretir mi** | ✅ Evet |
| **Tipik iddia tipleri** | `number` |

| # | Olay | Tarih | Kaynak | Teyit |
|---|---|---|---|---|
| 1 | Hazine aylık iç borçlanma stratejisi | Aylık | Hazine | ☐ |
| 2 | Eurobond ihracı duyurusu | — | Hazine | ☐ |

---

### 10. `derecelendirme` — Derecelendirme kuruluşu kararları

| | |
|---|---|
| **Kapsam** | Moody's / S&P / Fitch not ve görünüm kararları, gerekçe raporları, resmî kurum tepkileri |
| **Birincil kaynak** | Derecelendirme kuruluşunun kendi duyurusu (Tier 2 kabul edilir — Türkiye kurumu değil), Hazine (tepki) |
| **Ritim** | Kuruluş başına yılda ~2 planlı gözden geçirme; tarihler önceden ilan edilir |
| **Takvim üretir mi** | ✅ Evet |
| **Tipik iddia tipleri** | `fact`, `attribution` |

**Kaynak katmanı notu:** Bu konuda "birincil kaynak" bir Türkiye kurumu
değildir. R2'nin `has_primary_source` koşulu, kuruluşun kendi duyurusu
ajans üzerinden geldiğinde sağlanmayabilir. Bu, İtiraz-2'nin (bkz.
`docs/karar-itirazlari.md`) somut örneğidir ve Faz 2'de ölçülmelidir.

| # | Olay | Tarih | Kaynak | Teyit |
|---|---|---|---|---|
| 1 | Derecelendirme kuruluşu not/görünüm kararı | — | Kuruluş duyurusu + AA | ☐ |
| 2 | Karara ilişkin Hazine değerlendirmesi | — | Hazine | ☐ |

---

## Örnek olay teyidi — açık kalem

Yukarıdaki tablolarda **☐** işaretli satırlar, F0-03 DoD'un
*"her konu için son 3 aydan en az 2 gerçek örnek olay bulunmuş"* koşulunu
karşılamak üzere doldurulacaktır.

**Neden şimdi doldurulmadı:** Örnek olayların URL ve tarih düzeyinde teyidi,
kaynak akışlarına erişim gerektirir — bu erişim F0-08'de (kaynak kayıt
defteri) kurulur. İkisini aynı oturumda yapmak hem daha hızlı hem de daha
güvenilirdir: akış açıldığında son 3 ayın yayınları zaten listelenir.

**Yapılacak (≈45 dk):** F0-08'de her Tier 1 kaynağın akışı açıldığında,
son 3 ayın yayın listesinden konu başına 2 kayıt seçilip yukarıdaki
tablolara URL ve tarih ile işlenir. Aynı kayıtlar Golden Set'in
(F0-14) ilk tohumunu oluşturur — çift iş yapılmaz.

**Kabul ölçütü:** 20 satırın 20'si de ☑ ve her satırda çözülebilir bir URL.

---

## Kapsam dışı konular — bilinçli kararlar

| Konu | Neden dışarıda | Nerede |
|---|---|---|
| Şirket haberleri, bilançolar | Mikro ekonomi | Kapsam dışı |
| Borsa/piyasa fiyat hareketleri | Fiyat ≠ politika olayı | Kapsam dışı |
| Kripto varlıklar | Düzenleme haberi hariç makro değil | Kapsam dışı |
| Konut/emlak fiyat endeksleri | Değerlendirilebilir; MVP'de dışarıda | B-08 (kaynak genişlemesi) |
| Dış ticaret / cari açık | Makro ama 10 konuya girmedi; sert sınır korunuyor | B-08 |
| Enerji fiyatları / doğalgaz zamları | Vergi/harç boyutu varsa `vergi_ve_harclar` içinde | Kısmen içeride |
| TBMM'de ekonomi yasası görüşmesi | Yasama süreci; ayrı dikey | B-09 |

> **Sert sınır:** Bu listeye "makro ekonomi sayılır" gerekçesiyle 11. konu
> eklenemez. Konu sayısını artırmak `BACKLOG.md` B-08 üzerinden ve G4
> sonrası olur.
