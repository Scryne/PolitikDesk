# Araştırma: Olay Korelasyonu ve Kanıt Yakınsaması (Faz B6/B7)

**Tarih:** 20 Ağustos 2026
**Soru:** Resmî birincil kanıt ile bağımsız medya kapsamı, **yanlış olay
birleştirmesi üretmeden** daha doğru ilişkilendirilebilir mi?
**Sonuç:** Hayır — ölçülen hiçbir alternatif precision'ı koruyarak
iyileşme sağlamadı. **Kod değiştirilmedi.**

> Bu bir başarısızlık değildir. Üç hipotez kuruldu, üçü de gerçek üretim
> verisiyle ölçüldü ve **çürütüldü.** Ölçüm olmadan yapılacak değişiklik
> sistemi bozardı; aşağıdaki sayılar bunu gösteriyor.

---

## 1. Baseline (değişiklik öncesi)

HEAD `213dd99` · branch `audit/2026-08-18` · çalışma ağacı temiz ·
1.616 test.

**Baseline'da bir kapı kırığı bulundu ve düzeltildi** (bkz. §7):
`test_linking_is_idempotent` üretim verisi büyüdükçe kırılıyordu.

---

## 2. Kök neden — iki ayrı bariyer ölçüldü

Faz 0'ın sorusu: *resmî kaynak ile medya haberi aynı gerçek dünya olayını
temsil ettiği hâlde hangi teknik koşullar nedeniyle ayrı olaylara düşüyor?*

### Bariyer 1 — Aday penceresi duvar saatine bağlı

`clustering/repository.py::candidate_events`:

```sql
AND last_update_at > now() - make_interval(hours => 96)
```

Pencere **`now()`'a** göredir, makalenin `published_at` değerine göre
değil. Yayınından 96 saatten geç toplanan bir makale, kendi döneminin
olaylarını **aday listesinde hiç göremez**.

Ölçüm (6.497 makale):

| | Değer |
|---|---|
| Toplama gecikmesi > 96 saat | **415 makale (%6,4)** |
| Ortalama gecikme | 984,5 saat |

Tier 1 kaynaklarda gecikme:

| Kaynak | Makale | Ort. gecikme (saat) | 96h üstü |
|---|---|---|---|
| tcmb | 2 | 7.269 | 2 |
| **sbb** | 6 | **391** | **6 / 6** |
| hazine | 7 | 249 | 5 |
| resmi-gazete | 1 | 21 | 0 |
| sayistay / tuik / cb-kararname / tbmm / tcmb-evds | 81 | 0 | 0 |

**SBB'nin makalelerinin %100'ü bu bariyerin arkasında kaldı.** Yeni bir
kaynak eklendiğinde tüm arşivi tek seferde ve eski yayın tarihleriyle
gelir; bu, kaynak açılışına özgü bir etkidir.

### Bariyer 2 — 72 saatlik zaman kısıtı

`assigner._time_ok`: `|article.published_at − event.last_update_at| ≤ 72h`.

Aday listesine girseler bile: TÜİK'in TÜFE olayı 3 Ağustos, SBB'nin
yorumu 7 Ağustos → 96 saat > 72 saat → `time_reject`.

**İki bariyer bağımsızdır.** Yalnızca birini kaldırmak SBB/TÜİK vakasını
çözmez.

---

## 3. Hipotez 1 — "Zaman penceresini genişletmek yeterli" · **ÇÜRÜTÜLDÜ**

### 3.1 Benzerlik bu korpusta ayırt edici DEĞİL

14 gün içindeki tüm olay çiftleri (804.357 çift):

| Eşik | Çift | Pay |
|---|---|---|
| ortalama benzerlik | **0,8137** | — |
| ≥ 0,78 (`t_low`) | 704.547 | **%87,6** |
| ≥ 0,86 (`t_high`) | 59.891 | %7,4 |
| ≥ 0,90 | 7.145 | %0,9 |
| ≥ 0,93 | 1.149 | %0,14 |
| ≥ 0,95 | 369 | %0,05 |

**`t_low = 0,78` ortalama çift benzerliğinin ALTINDADIR.** Yani benzerlik
tek başına neredeyse hiçbir şey elemiyor; ayırt etme işini varlık, zaman
ve gösterge kısıtları yapıyor.

### 3.2 Pencereyi açmanın maliyeti ölçüldü

| Filtre | Çift |
|---|---|
| sim ≥ 0,86 · 14 gün | 59.891 |
| + ortak anahtar varlık | **1.525** (varlık kısıtı %97,5 eliyor) |
| + 72h penceresinin dışında | **714** ← pencere 14 güne açılırsa yeni birleşme |
| + sim ≥ 0,93 (en katı) | **21** |

### 3.3 En katı 21 aday elle hakemlendi — precision ≈ 0

Pencere genişletmenin **en güvenli** hâli budur. Sonuç:

| Çift | sim | Gerçek karar | Neden |
|---|---|---|---|
| 683 ↔ 7580 | **1,000** | **AYRI kalmalı** | TCMB `duy2026-32` vs `duy2026-24` — **farklı PPK toplantıları** |
| 8250 ↔ 8260 | 0,971 | **AYRI kalmalı** | Yurt İçi ÜFE vs **Tarım Ürünleri ÜFE** |
| 8251 ↔ 8260 | 0,963 | **AYRI kalmalı** | TÜFE vs Tarım ÜFE |
| 7688 ↔ 7748 | 0,960 | **AYRI kalmalı** | Erdoğan–DEM görüşmesi vs Filistin ziyareti |
| 7748 ↔ 7910/8041/7907 | 0,93+ | **AYRI kalmalı** | Filistin vs Özgür Özel / Bahçeli / Kılıçdaroğlu |
| 686 ↔ 1819/1808/8102/8481 | 0,93+ | **AYRI kalmalı** | Faiz kararı vs enflasyon raporu vs rezerv |
| 1808 ↔ 1817 | 0,932 | birleşebilir | Aynı enflasyon raporu, iki gün |
| 7666/7681 ↔ 7684 | 0,96+ | birleşebilir | Aynı TBMM düzenlemesi |

**En yüksek benzerlikli çift (1,000) DOĞRU şekilde ayrılmış.** Başlıklar
`clean_title` tarafından aynı noktadan kesildiği için ("Para Politikası
Kurulu Toplantı Özeti (2026") birebir aynı görünüyor; ayıran şey yalnızca
duyuru numarasıdır ve o embedding'e girmiyor.

> **Sonuç: benzerlik, "aynı olay" ile "aynı belge türü"nü ayırt edemiyor.**
> Pencereyi açmak 714 birleştirme üretir, en katı ayarda bile 21 adayın
> çoğu yanlıştır. Hipotez çürütüldü.

Bu ölçüm aynı zamanda **mevcut 72 saatlik pencerenin keyfî bir sınır
değil, çalışan bir precision koruması** olduğunu gösteriyor.

---

## 4. Hipotez 2 — "Resmî kaynak çapası (Official Anchor)" · **ÇÜRÜTÜLDÜ**

*Tier 1 kaynak varsa daha geniş korelasyon penceresi.*

Aynı 21 adaya bakıldığında bu kural ilk üç yanlış birleştirmeyi
(TCMB PPK ×2, TÜİK ÜFE ×2) **tam olarak tetikler** — çünkü hepsi Tier 1
resmî kaynaktır ve anahtar varlığı paylaşır.

Resmî kaynak olmak, **aynı olay olmak demek değildir**: TÜİK ayın
farklı günlerinde altı ayrı endeks yayımlar; TCMB yılda sekiz PPK özeti
çıkarır. Bu kural, en çok korumamız gereken yerde en çok zarar verir.

---

## 5. Hipotez 3 — "İkincil korelasyon (related_event)" · **UYGULANABİLİR AMA SPEC DEĞİŞİKLİĞİ**

Bu, hard-merge riskini taşımayan tek alternatif. Ve **mekanizma zaten var:**
`context/related.py::link_related` `event_relations` tablosuna
`same_thread` bağları yazıyor (canlıda 736 ilişki).

Eksik olan şey bağ değil, **kanıtın bu bağ üzerinden akması**.

Ama bu, doğrudan Spec §8.2/§8.3'ün çekirdeğine dokunur:

- `independent_count`, tek bir olayın kanıt kümesi üzerinden hesaplanır.
- İlişkili olaydan kanıt taşımak, bağımsız sayımı **olay sınırının
  dışına** genişletir.
- `same_thread` bağı 0,8+ benzerlikle kuruluyor ve §3.1'de ölçüldüğü gibi
  bu eşik bu korpusta **%87 çifti** geçiriyor.

Yani ilişki bağları üzerinden kanıt taşımak, R2'yi zayıflatmanın dolaylı
bir yolu olurdu. **Bu bir mühendislik kararı değil, epistemik politika
kararıdır ve Spec sürüm artışı gerektirir.**

Görev kuralı açıktır: *"R2 kuralları değişmemeli"*, *"independence_group
semantiği değişmemeli"*. Dolayısıyla bu alternatif **bu görevin kapsamı
dışındadır** ve ürün sahibine bırakılır.

---

## 6. Hipotez 4 — "Semantik olay parmak izi" · **ÖLÇÜLDÜ, ÖN KOŞULU YOK**

Fikir: entity + action + subject + numeric + temporal anchor üzerinden
parmak izi.

Ölçüm §3.3'te zaten cevabı veriyor: ayırt edici sinyal **duyuru
numarası** (`duy2026-32` vs `duy2026-24`) ve **gösterge adı** (Yurt İçi
ÜFE vs Tarım ÜFE) gibi alanlarda. Bunlar:

- Başlıkta var ama `clean_title` tarafından kesiliyor,
- Embedding'de temsil edilmiyor,
- `indicators_conflict` tarafından **kısmen** zaten yakalanıyor (ve
  çalışıyor: ÜFE/Tarım-ÜFE olayları ayrı kalmış).

Yani doğru yatırım "daha iyi benzerlik" değil, **daha iyi ayrıştırma**:
başlıktaki belge kimliğini (duyuru no, dönem, gösterge adı) yapısal alan
olarak çıkarmak. Bu, korelasyonu iyileştirmez — **yanlış korelasyonu
önler**. Ayrı ve daha büyük bir iştir; bu görevde ölçüldü, kayda geçti,
uygulanmadı.

---

## 7. Yan bulgu — kırık kapı düzeltildi

`tests/test_context.py::test_linking_is_idempotent` şunu iddia ediyordu:

```python
assert cur.fetchone()["n"] == 1
```

Bu sayı, veritabanında fixture'ın vektörüne benzeyen **başka olay
bulunmadığı** varsayımına dayanıyordu. `find_related` tüm `events`
tablosunu tarar; üretim verisi büyüdükçe eşleşme 1'i aştı ve test
**ürün kodu doğru çalıştığı hâlde** kırıldı (`assert 3 == 1`).

Kanıt: log iki koşumda da `count=3` diyor — yani **çift yazım yoktu**,
idempotans çalışıyordu.

Düzeltme testin gerçek sözleşmesini korur: *ikinci koşumdan sonra satır
sayısı değişmemeli.* Bu, veritabanının doluluğundan bağımsızdır.

---

## 8. Konu sözlüğü boşlukları — ölçüldü, değişiklik önerilmiyor (şimdilik)

`odemeler_dengesi` ve `dis_ticaret` taksonomide gerçekten **yok** ve
mevcut 10 slug'ın hiçbiri onları kapsamıyor (`buyume` GSYH'ye,
`kur_ve_rezervler` rezerv/kura bakıyor).

Etki ölçümü:

| Kavram | Saklanan makalede geçiş |
|---|---|
| "ödemeler dengesi" | **1** |
| "dış ticaret" | **2** |
| "cari açık/denge" | 3 |
| "ihracat/ithalat" | 11 |

6.497 makalede toplam ~17 (%0,26).

SBB özelinde etki daha belirgin: **10 kalemin 2'si** bu yüzden eleniyor.

**Neden şimdi eklenmiyor:**

1. Taksonomi 10 slug'a sabitlenmiş ve `eval/golden_set_tools.py::VALID_TOPICS`
   ile **eşleşmek zorunda**; ayrıca `verticals/macro_economy.py` ve
   golden set dosyaları etkilenir. Bağlı bir değişikliktir.
2. Kazanılacak makaleler §3–§5'te ölçülen darboğazı **değiştirmez**:
   daha fazla tek makaleli olay üretir, teyit üretmez.
3. Ölçülen hacim (SBB'de tur başına 2 kalem, ayda birkaç kez) bu riski
   karşılamıyor.

**Öneri:** ÇSGB/Ticaret Bakanlığı gibi dış ticaret üreten Tier 1
kaynaklar eklendiğinde birlikte değerlendirilsin — o zaman hacim ölçülüp
karar yeniden verilebilir.

---

## 9. Nerede kaldı darboğaz?

Sırayla elenen açıklamalar:

| Hipotez | Durum |
|---|---|
| Kaynak sayısı yetersiz | **Çürütüldü** (SBB eklendi, 🟢 değişmedi — ADR-013) |
| Tier 1 kanıt yetersiz | **Kısmen doğruydu, kapatıldı** (75 → 82 kanıt bağı) |
| Kümeleme bozuk / pencere dar | **Çürütüldü** (§3: pencereyi açmak 714 yanlış birleşme) |
| Benzerlik eşiği yüksek | **Çürütüldü** (§3.1: `t_low` ortalamanın altında) |

**Kalan gerçek darboğaz:** medya, resmî veri açıklamasının kendisini
işlemiyor. Temmuz TÜFE penceresinde ölçülen medya kapsamı, veri
açıklaması değil *"13 Ağustos'ta açıklanacak enflasyon raporu"* ve
*Merkez Bankası toplantısı* idi — bunlar farklı olaylardır.

Yani bu bir **extraction** ya da **correlation** problemi değil, bir
**kapsam** problemidir: R2'nin istediği "aynı olguyu 3 bağımsız kaynağın
yazması" durumu, Türkiye makro gündeminde resmî veri açıklamaları için
**nadiren gerçekleşiyor**.

Bunun doğru çözümü kümelemeyi gevşetmek değildir. Seçenekler:

1. **Kabul et:** 🟢 nadir bir durumdur ve bu epistemik olarak dürüsttür.
   R3 (resmî sayı doğrulaması) zaten çalışıyor ve iki 🟢'yi o üretti.
2. **R3'ü genişlet:** SBB gibi kaynaklardan `official_value` çıkar
   (şu an yalnızca `tuik_sdmx`/`evds` dolduruyor). Bu, R2'ye dokunmadan
   🟢 üretir ve **epistemik olarak daha güçlüdür** — sayı kurumun kendi
   yayınıyla doğrulanır.
3. **Ürün kararı:** 🟢 eşiğini değiştirmek (Spec sürüm artışı).

**En umut verici yol 2'dir** ve bu görevin kapsamı dışındadır; ayrı
ölçüm ve tasarım ister.

---

## 10. Sonuç

Hiçbir korelasyon değişikliği precision'ı koruyarak iyileşme sağlamadı.
Görev kuralı gereği **kod değiştirilmedi** (kırık test kapısı hariç).

Mevcut kümeleme sistemi bu ölçümlerde **doğru davrandı**: reddettiği
birleşmelerin neredeyse tamamı gerçekten ayrı olaylardı.
