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
