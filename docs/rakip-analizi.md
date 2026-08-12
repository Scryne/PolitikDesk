# Rakip ve Emsal Analizi

**Görev:** F0-20 · **Kaynak:** Spec §3.2, §3.3

> Bu belgenin işlevi rakip saymak değil, **"zaten X var" itirazına isim isim
> cevap vermektir.** Spec §3.2'ye göre bu, ürünün cevaplaması gereken tek
> gerçek sorudur.

**⚠️ Fiyat teyidi:** Aşağıdaki fiyatlar kamuya açık fiyatlandırma sayfalarından
alınan mertebe tahminleridir ve **hızla değişir**. Rakamlar bir karara girdi
olacaksa (özellikle D19 fiyatlandırma), önce ilgili ürünün sayfasından teyit
edilmelidir. Teyit sütunu bunun içindir.

---

## Farklılaşma testi (Spec §3.2)

Her ürün üç maddeye karşı ölçülür:

1. **Pull vs. push** — sorulmadan izliyor mu, yoksa sorulunca mı cevap veriyor?
2. **Süreksiz vs. birikimli** — bilgi oturum kapanınca kayboluyor mu?
3. **Metin vs. kanıt yapısı** — cümlenin arkasındaki kaynak *yapısal* mı?

| # | Ürün | Kategori | Push | Birikimli | Kanıt yapısı | Fiyat (mertebe) | Teyit |
|---|---|---|---|---|---|---|---|
| 1 | Ground News | Perspektif karşılaştırması | ✅ | ⚠️ | ⚠️ | ~$10/ay | ☐ |
| 2 | Perplexity | Genel amaçlı arama/asistan | ❌ | ❌ | ⚠️ | ~$20/ay | ☐ |
| 3 | ChatGPT / Claude | Genel amaçlı asistan | ❌ | ❌ | ❌ | ~$20/ay | ☐ |
| 4 | Feedly (+AI) | RSS okuyucu | ✅ | ❌ | ❌ | ~$8–18/ay | ☐ |
| 5 | Buffer / Hootsuite | İçerik kuyruğu | ❌ | ❌ | ❌ | ~$6–99/ay | ☐ |
| 6 | Medya izleme platformları (TR) | B2B medya takibi | ✅ | ✅ | ❌ | Kurumsal, teklif usulü | ☐ |
| 7 | NewsWhip / Memri sınıfı | Haber istihbaratı (B2B) | ✅ | ✅ | ⚠️ | Kurumsal | ☐ |
| 8 | Teyit / Doğruluk Payı (TR) | Fact-checking kurumu | ✅ | ✅ | ✅ | Ücretsiz (kâr amacı gütmeyen) | ☐ |

**Hiçbiri üç maddeyi birden karşılamıyor.** PolitikDesk'in konumu bu boşluktur.

---

## 1. Ground News

| | |
|---|---|
| **Ne yapıyor** | Aynı haberin farklı yayınlardaki sunumunu yan yana gösteriyor; kaynaklara siyasi eğilim (left/center/right) etiketi veriyor; "blindspot" (bir tarafın hiç yazmadığı haber) özelliği sunuyor. |
| **PolitikDesk farkı** | ① Ground News **kaynağa siyasi etiket verir**; PolitikDesk bunu Spec §8.5 ve §15 madde 5 ile **açıkça yasaklar** — yalnızca çerçeveleme farkını gözlem olarak gösterir. ② Ground News haber gösterir, **iddia/kanıt ayrıştırması yapmaz**. ③ Editoryal üretim katmanı yok. ④ Türkiye kaynak kapsamı zayıf. |
| **Öğrenilecek** | Yan yana başlık sunumu güçlü bir UX kalıbı — Spec §14.3'teki kaynak tablosu bunu doğru yakalıyor. "Blindspot" fikri MVP'nin "tek yayın grubundan raporlanıyor" uyarısıyla aynı ihtiyacı çözüyor ama daha çarpıcı sunuyor. |
| **Dikkat** | Siyasi etiketleme onların *ana özelliği*, bizim *yasağımız*. Bu farkı kullanıcıya anlatmak konumlandırmanın en kritik cümlesi olacak. |

---

## 2. Perplexity

| | |
|---|---|
| **Ne yapıyor** | Kaynak gösteren AI arama; sorulan soruya web taramasıyla cevap veriyor, dipnot bağlantıları koyuyor. |
| **PolitikDesk farkı** | ① **Pull.** Sormazsan çalışmaz; gündemi senin adına izlemez. ② **Süreksiz.** Aynı konuyu 6 ay sonra sorduğunda geçmişi hatırlamaz. ③ Dipnot ≠ kanıt yapısı: kaç bağımsız kaynak, hangi tier, çelişki var mı — bunların hiçbiri yapısal değil. ④ Üretilen metin yayınlanabilir bir editoryal taslak değil. |
| **Öğrenilecek** | Dipnot yerleşimi ve kaynak güveni sunumu iyi çözülmüş. Cevap içinde kaynağa dokunma etkileşimi Spec §14.3'ün kanıt bloğu için referans. |
| **Dikkat** | En ciddi "zaten var" itirazının kaynağı bu ürün. Cevap, özellik listesi değil **üç maddedir**. |

---

## 3. ChatGPT / Claude (genel amaçlı asistanlar)

| | |
|---|---|
| **Ne yapıyor** | Web araması ile güncel bilgiye erişip özet ve metin üretiyor. |
| **PolitikDesk farkı** | Perplexity'nin farklarının tamamı, artı: kanıt zinciri **hiç** yapısal değil; halüsinasyon riskine karşı programatik doğrulama yok. PolitikDesk'te üretilen her sayı ve tarih kanıt setinde aranır (F3-12) ve bulunmazsa üretim işaretlenir. |
| **Öğrenilecek** | Bu ürünler PolitikDesk'in *motorudur*, rakibi değil. Rekabet, ürünün etrafındaki kanıt yapısı ve birikimli grafiktedir. |
| **Dikkat** | Kullanıcının zihnindeki karşılaştırma budur. Demo'da fark **yan yana** gösterilmeli: aynı olay için asistan çıktısı vs. olay sayfası. |

---

## 4. Feedly (+ AI özellikleri)

| | |
|---|---|
| **Ne yapıyor** | RSS okuyucu; AI ile konu takibi ve önceliklendirme, tekrar azaltma. |
| **PolitikDesk farkı** | ① **Makale gösterir, olay göstermez.** Aynı gelişmenin 11 haberi 11 satır olarak kalır. ② Özet verir, kanıt zinciri kurmaz. ③ Tarihsel bağlam yok. ④ Editoryal üretim yok. |
| **Öğrenilecek** | Okuma listesi ergonomisi ve "kaçırdıklarım" akışı olgun. F3-18'in ("sen yokken ne oldu") referansı. |
| **Dikkat** | Fiyat aralığı (~$8–18/ay) PolitikDesk'in fiyat beklentisi için gerçekçi bir çıpa — kullanıcı zaten bu mertebede ödeme yapıyor. |

---

## 5. Buffer / Hootsuite (içerik kuyruğu)

| | |
|---|---|
| **Ne yapıyor** | Sosyal medya gönderilerini zamanlama, kuyruklama, yayın takvimi. |
| **PolitikDesk farkı** | Kuyruk bir **çıktıdır**, ürünün merkezi değil (Spec §3.3). PolitikDesk'in merkezi kanıt katmanıdır; kuyruk özelliği bilinçli olarak Faz 5'e ertelenmiştir (`BACKLOG.md` B-02). Ayrıca bu araçlar **otomatik yayın** yapar; PolitikDesk'te otomatik yayın **kod yolu bile yoktur** (P5). |
| **Öğrenilecek** | Yayın öncesi önizleme ve karakter sayacı gibi küçük ergonomiler F3-14'te ucuz kazanç. |
| **Dikkat** | Bu kategoriye kayma, ürünü "araştırma masası"ndan "zamanlama aracına" düşürür. Kapsam savunmasının en olası kırılma noktası. |

---

## 6. Medya izleme platformları (Türkiye — B2B)

| | |
|---|---|
| **Ne yapıyor** | Kurumlar için basın/sosyal medya takibi, marka izleme, raporlama. Genellikle teklif usulü kurumsal fiyatlandırma. |
| **PolitikDesk farkı** | ① **ICP farkı:** kurumsal iletişim birimi vs. tek çalışan içerik üreticisi. ② Marka izleme ≠ olay grafiği. ③ Editoryal aksiyona bağlı çıktı yok — rapor üretir, taslak üretmez. ④ Fiyatlandırma bireysel kullanıcı için ulaşılmaz. |
| **Öğrenilecek** | Kaynak kapsamı ve arşiv derinliği bu ürünlerin gücü — Faz 6 Team Workspace'in (B-30) gerçek rakibi bunlar olacak. |
| **Dikkat** | B2B'ye erken kayma cazibesi (DG-6). MVP'de bilinçli olarak dışarıda. |

---

## 7. NewsWhip / Memri sınıfı haber istihbaratı

| | |
|---|---|
| **Ne yapıyor** | Haber ve sosyal medya sinyallerini toplayıp yayılma/etkileşim tahmini yapıyor; gazeteciler ve kurumlar için erken uyarı. |
| **PolitikDesk farkı** | ① Bu ürünler **etkileşim tahmini** yapar; PolitikDesk'in salience formülünde **engagement girdisi yasaktır** (Spec §15 madde 14). ② Sinyal verir, kanıt zinciri kurmaz. ③ Kurumsal fiyat. |
| **Öğrenilecek** | Yayılma hızı ölçümü (ilk 60 dk içindeki makale sayısı) salience formülünün bileşenlerinden biri — bu kategoriden gelen doğru bir fikir. |
| **Dikkat** | "Etkileşim tahmini ekleyelim" fikri periyodik olarak gelecektir. Prensip düzeyinde reddedilir (R11 riski). |

---

## 8. Teyit / Doğruluk Payı (Türkiye — fact-checking)

| | |
|---|---|
| **Ne yapıyor** | Belirli iddiaları elle araştırıp "doğru/yanlış/karma" hükmü veren, kâr amacı gütmeyen doğrulama kuruluşları. |
| **PolitikDesk farkı** | ① **Hüküm vermez.** Spec §1: fact-checker/hakem değil, *evidence synthesizer* — kanıtı gösterir, kararı kullanıcıya bırakır. ② İnsan gücüyle seçilmiş birkaç iddia vs. sürekli otomatik akış. ③ Editoryal üretim yok. ④ Ürün değil, yayın. |
| **Öğrenilecek** | **En yakın felsefi akraba.** Kanıt sunum biçimi, alıntı disiplini ve şeffaflık standartları doğrudan örnek alınabilir. Metodoloji sayfalarının şeffaflığı, Spec §14.3'teki "Neden 🟢?" bileşeni için iyi bir referans. |
| **Dikkat** | Kullanıcılar PolitikDesk'i bir doğrulama otoritesi sanabilir. Arayüz dili bu yanlış anlamayı **aktif olarak** engellemeli — kalıcı uyarı bileşeni (F4-14) bunun için var. |

---

## Sentez

### Boşluk

| Eksen | Mevcut ürünler | PolitikDesk |
|---|---|---|
| Kim için | Kurum (B2B) veya genel tüketici | **Tek çalışan içerik üreticisi** |
| Birim | Makale veya soru-cevap | **Olay** |
| Kanıt | Dipnot / link | **Yapısal iddia-kanıt zinciri + deterministik durum** |
| Zaman | Anlık | **Birikimli olay grafiği** |
| Çıktı | Okuma veya özet | **Kaynaklı editoryal taslak + yayın öncesi kontrol** |
| Hüküm | Ya etiket verir ya hiç | **Kanıtı gösterir, hüküm vermez** |

### Moat teyidi

Spec §1'in savunulabilir değer tezi bu analizle **doğrulanıyor**: hiçbir
rakip **birikimli olay grafiği + kanıt zinciri + tarihsel bağlam arşivi**
kombinasyonunu tutmuyor. Ground News çerçeveyi, Perplexity kaynağı,
Feedly akışı, Teyit kanıt disiplinini ayrı ayrı çözüyor; hiçbiri dördünü
birleştirip editoryal aksiyona bağlamıyor.

**Ama:** Bu moat *zamanla* birikir. 6. ayda ürünün rakiplere üstünlüğü
sınırlıdır; 18. ayda arşiv taklit edilemez hale gelir. Bu, veri modelinin
(Spec §7) neden "önce doğru kur" mantığıyla tasarlandığını açıklar ve
Faz 1'de ingestion'ın neden zekâdan önce geldiğini haklı çıkarır.

### Fiyatlandırmaya girdi (D19)

Kullanıcının zaten ödeme yaptığı mertebe **$8–20/ay** (Feedly, Perplexity).
`docs/veri-maliyet-modeli.md`'ye göre 100 kullanıcı ölçeğinde birim maliyet
**~4,67 $/ay**. Bu aralık makul bir marj bırakıyor — ancak nihai karar
F0-04 görüşmelerindeki S4 (ödeme beyanı) verisine bağlıdır.

### Açık kalemler

- [ ] 8 ürünün güncel fiyatı kendi sayfasından teyit edilsin (~45 dk)
- [ ] Ground News'ın Türkiye kaynak kapsamı fiilen test edilsin (bir enflasyon
      olayı aranarak) — kapsam güçlüyse konumlandırma keskinleşmeli
- [ ] Türkiye'de doğrudan emsal bir ürün olup olmadığı taransın (bu liste
      uluslararası ağırlıklı; yerel bir emsal atlanmış olabilir)
