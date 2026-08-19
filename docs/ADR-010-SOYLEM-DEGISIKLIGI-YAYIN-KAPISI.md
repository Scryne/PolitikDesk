# ADR-010: Söylem Değişikliği Tespiti — Yayından Çekildi

**Durum:** Kabul Edildi (Accepted) — `PUBLISH_GATE_OPEN = False`
**Tarih:** 19 Ağustos 2026
**İlgili:** Roadmap Faz 4.1, `political_memory/shift_store.py`,
`political_memory/stance_shift.py`, `web/event.py`, `web/memory_view.py`,
`migrations/0019_stance_shift_withheld.sql`, ADR-008

---

## 1. Bulgu

Faz 4.1'de söylem değişikliği tespiti kalıcılaştırıldı ve o iş **kayıt
sayısıyla** başarılı sayıldı: 219× okuma hızlanması, daha önce
görünmeyen 13 kayma. İçerik denetlenmedi. Denetim şimdi yapıldı ve
sonuç şu:

| Ölçüm | Sonuç |
|---|---|
| `topic_or_metric` dağılımı | **50/50 kayıt tek değerde**: "Politika / Tutum Beyanı" |
| `shift_type` dağılımı | **50/50 `reversal`** |
| `confidence` dağılımı | **50/50 tam olarak `0.85`** |
| Aynı gün "U dönüşü" | 14 kayıt |
| Aktör alanında sözcük parçası | "Adayı" (2 kayıt) |
| Aktör alanında yayın organı | "Resmî Gazete" (3 kayıt) |

Üç şeyi birden söylüyor:

1. **Konu eşleştirmesi yok.** Tek bir jenerik kova var. Yani sistem,
   tamamen farklı konulardaki iki beyanı "aynı konuda fikir değiştirdi"
   diye karşılaştırıyor.
2. **Güven skoru ölçülmüş değil.** Hep aynı olan bir sayı bir güven
   skoru değildir. Bu, Faz 5'te `evidence.stance`'ın sabit `'supports'`
   yazılmasıyla (ADR-008) **birebir aynı kusurdur**; orada bulundu,
   burada gözden kaçtı.
3. **Aktör çözümlemesi sızdırıyor.** "Adayı" bir aktör değil, Türkçe bir
   tamlamanın parçası.

### Somut örnek

```
actor_name  : Cumhurbaşkanlığı
shift_type  : reversal            confidence: 0.85
earlier     : @tv100 — "KILIÇDAROĞLU NE ÖZEL'İ NE DE İM…"   18:07
later       : @samiltayyar27 — "Erkan Mumcu'nun 2007'deki…"  18:49
time_span   : 0 gün
```

42 dakika arayla atılmış, biri Kılıçdaroğlu/Özel biri 2007'de Erkan
Mumcu hakkında olan, **hiçbiri Cumhurbaşkanlığı'nın beyanı olmayan** iki
tweet. Sistem bundan Cumhurbaşkanlığı'na bir U dönüşü çıkarıyor.

### Maruziyet

Bu çıktı **kullanıcıya görünüyordu**, üç yoldan:

- `/event/{id}` — "Söylem" kartı
- `/api/memory/stance-shifts` — 50 kaydın tamamı
- `/memory/{aktör}` — "180° Zıt Beyan" kartları (bu yol `shift_store`'u
  hiç kullanmıyor, dedektörü doğrudan çağırıyordu)

---

## 2. Neden bu en ağır kusur

Bu, adı geçen **gerçek kişi ve kurumlara yöneltilmiş, sistem tarafından
üretilmiş yanlış bir siyasi isnattır.** Kanıta dayalılık güvencesi veren
bir üründe verilebilecek en pahalı çıktıdır: yanlış bir sayı düzeltilir,
yanlış bir isnat düzeltilmez.

Ürünün kendi kısıtları da bunu zaten yasaklıyordu — Spec §8.5 kaynağa
siyasi konum etiketi verilmesini yasaklarken, sistemin bir aktöre
tutarsızlık isnat etmesi çok daha ileri bir iddiadır.

ADR-008'de kayda geçen ilke burada da geçerli:

> Ölü kuraldan kötü olan tek şey, yanlış çalışan kuraldır.

---

## 3. Karar

**Yayın kapısı kapatıldı.** `shift_store.PUBLISH_GATE_OPEN = False`.

| Ne | Nasıl |
|---|---|
| Mevcut 50 kayıt | `status='withheld'` (migration 0019) — **silinmedi** |
| Yeni tespitler | yazılmaya devam eder, `withheld` olarak |
| `list_all` / `for_actor` / `for_event` | kapı kapalıyken **boş liste** |
| `/memory/{aktör}` radarı | dedektörü artık kapıya sorarak çağırır |
| `summary()` | `withheld` sayısını **ayrı ve açık** raporlar |

**Kayıtlar neden silinmedi:** dedektör düzeltildiğinde aynı veriyle
öncesi/sonrası karşılaştırması yapılabilsin diye. Ölçmek ile yayınlamak
ayrı kararlardır; burada yalnızca ikincisi durduruldu.

**`summary()` neden sessizce 0 dönmüyor:** "hiç kayma bulunmadı" ile
"bulunanlar güvenilmez olduğu için yayınlanmadı" aynı şey değildir. Bu
projede tekrar tekrar ödenen bedel tam olarak budur — *ölçülemedi ≠ sıfır*.

### Yan bulgu: kapı, idempotentliği kırabilirdi

0018'deki tekillik indeksi yalnızca `status='open'` satırlarını
kapsıyordu. Dedektör `withheld` yazmaya başlayınca o indeks hiçbir yeni
satırı görmeyecek, `ON CONFLICT` hedefi eşleşmeyecek ve **her koşumda
aynı kayma tekrar eklenecekti.** Yani yayını kapatma hamlesi, farkında
olunmadan idempotentliği kıran bir hamleye dönüşürdü.

İndeksler `WHERE status <> 'superseded'` kapsamına genişletildi.
Doğrulandı: ikinci sync koşumunda 62 tespit, **0 yeni kayıt, 0 kopya imza**.

---

## 4. Kullanıcıya ne gösteriliyor

`/memory/{aktör}` sayfasında kart kaybolmuyor; şunu diyor:

> **Bu bölüm geçici olarak yayından kaldırıldı.**
> Söylem değişikliği tespiti denetlendiğinde, farklı konulardaki
> beyanları aynı konuymuş gibi karşılaştırdığı ve bir kişiye ait olmayan
> sözleri o kişiye atfedebildiği görüldü. Yanlış bir isnadı
> göstermektense hiçbir şey göstermemeyi seçiyoruz.

---

## 5. Kapının açılma şartları

`PUBLISH_GATE_OPEN = True` yapmak **tek başına yeterli değildir.** Şunlar
ölçülmeden değiştirilmemelidir:

1. **Konu eşleştirmesi.** İki beyan aynı konuda olmadıkça
   karşılaştırılmamalı. `topic_or_metric` gerçek bir konu taşımalı;
   tek kova kabul edilemez.
2. **Aktör = konuşan.** Aktör, metinde *geçen* varlık değil, beyanın
   *sahibi* olmalı. "Resmî Gazete"nin siyasi görüş değiştirmesi mümkün
   değildir.
3. **Varlık çözümlemesi temizliği.** "Adayı" gibi sözcük parçaları
   aktör olamaz.
4. **Gerçek güven skoru.** Sabit 0,85 kaldırılmalı; skor girdiye göre
   değişmeli ve neye dayandığı saklanmalı.
5. **Asgari zaman aralığı ve gerekçe.** Aynı gün içinde "U dönüşü"
   iddiası için çok daha sert bir eşik gerekir.
6. **Elle etiketlenmiş altın küme.** En az 100 aday çift, ikinci bir
   insan tarafından bağımsız etiketlenmiş, kappa ölçülmüş. Faz 6'daki
   `eval/golden_stance_v1.jsonl` deseni izlenebilir.
7. **Yanlış isnat oranı ≈ 0.** Bu üründe yanlış pozitif, kaçırılan
   pozitiften kat kat pahalıdır; hedef duyarlılık değil **kesinliktir**.

Bu iş, Faz 6'nın izlediği "ölç → kıyasla → karar ver" yordamına uygun
olarak **kendi roadmap maddesi** olarak ele alınmalıdır.

---

## 6. Ölçüm sonucu: kapı şu an AÇILAMAZ — önkoşul eksik

§5'i uygulamaya başlarken yapılan teşhis (`eval/diagnose_stance_shift.py`,
19 Ağustos 2026, hiçbir şey yazmadan) iki şey buldu.

### 6.1 Kavramların %79'u konu değil, içeriksiz duruş fiili

67 kalıcılaşmış kaymanın kaynağı:

| kavram çifti | kayma | tür |
|---|---:|---|
| `yasaklanmalı → serbest olmalı` | 32 | içeriksiz duruş fiili |
| `destekliyoruz → karşıyız` | 21 | içeriksiz duruş fiili |
| `faiz artırımı → indirimi` | **14** | **konusal** |
| `asla olmaz → müzakere edilebilir` | 0 | içeriksiz duruş fiili |

**53/67 (%79,1)** özneden bağımsız bir fiil eşleşmesinden geliyor.
"X'i destekliyoruz" ile "Y'ye karşıyız", X ≠ Y olsa da eşleşiyor.

Daha kötüsü, eşleşmeler çoğu zaman sözcük parçası düzeyinde: kayma #1'de
`yasak_serbest` çifti, *"üyeliğin **açıldığı**nı duyurduk"* cümlesindeki
"açıldı" ile serbestleşme kutbundaki "açılması"yı eşleştiriyor. Ortada
bir duruş yok, ortak bir kök var.

17/67 kayma aynı gün içinde "U dönüşü" iddia ediyor.

### 6.2 Belirleyici engel: `speaker` alanı hiç doldurulmuyor

§5'in 2. şartı "aktör = konuşan" diyor. Bunu uygulamak için gereken alan
`claims.status_reason->>'speaker'`. Ölçüm:

```
speaker dolu olan iddia : 0 / 4.542
status_reason yazan kod : YOK (depo geneli arama)
iddia çıkarım şemasında `speaker` alanı : YOK
```

Alan **beş yerde okunuyor** — `political_memory/candidate_filter.py`,
`political_memory/orchestrator.py`, `political_memory/service.py`,
`editorial/social_publisher.py` — ve **hiçbir yerde yazılmıyor.**

Sonuç: aktör ataması, `service.get_actor_memory()` sorgusundaki üç gevşek
dala düşüyor — iddia metninde ad geçiyorsa, **olayın herhangi bir makale
başlığında** geçiyorsa, ya da **olaya bağlı herhangi bir varlıkla**
eşleşiyorsa. Yani bir olayda yalnızca *adı anılan* aktör, o olaydaki
**herkesin** beyanını devralıyor.

§1'deki örneğin gerçek açıklaması budur: Cumhurbaşkanlığı'na Bahçeli'nin
ve Erkan Mumcu'nun sözlerinin atfedilmesi, dedektörün değil, **hafıza
sorgusunun** kusurudur.

### 6.3 Bunun anlamı

"Bu aktör görüş değiştirdi" iddiası, kimin ne söylediği bilinmeden
türetilemez. O bilgi veritabanında **yok**. Kutup eşleştiricisini ne
kadar iyileştirirsek iyileştirelim bu değişmez; eksik olan eşik değil,
**olgunun kendisi**.

Dolayısıyla ADR-010 §5 bu hâliyle uygulanamaz. Doğru sıra:

1. **Önce konuşan atfı (speaker attribution).** İddia çıkarımı, beyanın
   sahibini de üretmeli ve saklamalı. Bu tek başına `candidate_filter`,
   `orchestrator` ve `social_publisher`'ı da düzeltir — üçü de bugün boş
   bir alanı okuyor.
2. **Sonra** §5'in kalan şartları (konu örtüşmesi, gerçek güven skoru,
   asgari süre, altın küme) uygulanabilir hale gelir.

Konu örtüşmesi şartı için gereken araç bu arada hazırlandı:
`events.topic_tags` 19 Ağustos'ta doldurulmaya başlandı (1.664 olay),
öncesinde 1.680 olayın tamamında boştu.

**Kapı kapalı kalır.** Bu, ölçülmüş bir "henüz değil"dir.
