# Denetim Sonrası Yol Haritası — 20 Ağustos 2026

Bu haritadaki her madde, denetimde **ölçülmüş** bir gözleme dayanır.
Ölçüme dayanmayan fikirler §7'de ayrı tutulmuştur — orada oldukları
yerde kalmaları, buraya karışmamaları için.

Öncelik ölçütü tek: **ürünün merkezî vaadine ne kadar yakın.**
PolitikDesk'in vaadi "daha çok haber" değil, *kanıt derecelendirmesi*dir.

---

## Faz A — Kritik sertleştirme · **TAMAMLANDI (20 Ağu 2026)**

| # | İş | Durum |
|---|---|---|
| A1 | URL şema denetiminde C0 atlatması | ✅ `esc_url` izin listesi · tarayıcıda 4→0 |
| A2 | Makale bağlantısında şema doğrulaması | ✅ `http`/`https` dışı DB'ye giremiyor |
| A3 | Markdown dışa aktarımında bağlantı enjeksiyonu | ✅ |
| A4 | Dedup penceresinin kaynak başına yüklenmesi | ✅ tur başına 6,3 sn kazanç |
| A5 | HTTP gövde tavanı (sıkıştırma bombası) | ✅ 25 MB, akışta kesme |
| A6 | Celery zaman sınırı + beat `expires` | ✅ ölçüme dayalı (p95 80,8 sn) |
| A7 | Erişilebilirlik: 12 ekran | ✅ ort. 97,7 → **100** |

Kanıt: `docs/AUDIT-2026-08-20.md`, `design/decisions.md`.

---

## Faz B — Kanıt motorunu doyur ⭐ **EN YÜKSEK ÖNCELİK**

**Neden birinci sırada.** Ölçüldü: 🟢 `strongly_corroborated` iddia
sayısı **5.376'da 2**, ve R2'nin istediği bileşimi sağlayan iddia
sayısı **sıfır**. Ürünün amiral göstergesi çalışmıyor — kural kusuru
değil (kurallar bilinçli ve test edilmiş).

### ⚠ B1 UYGULANDI VE DARBOĞAZ YER DEĞİŞTİRDİ (20 Ağu 2026)

SBB eklendi (ADR-013). Ölçülen sonuç:

| | BEFORE | AFTER |
|---|---|---|
| Tier 1 kanıt bağı | 75 | **82** |
| Tier 1 kanıtı olan iddia | 70 | **77** |
| 🟢 | 2 | **2** |
| R2 uygun | 0 | **0** |

SBB, R2'nin **birinci ayağını (Tier 1 birincil kaynak) sağladı** —
7 iddiasının 6'sında `has_primary_source: true`. Ama **ikinci ayak
açık kaldı**: `independent_count = 1`, çünkü SBB'nin makaleleri kendi
olaylarında yalnız (6 olay oluştu, 0 atandı).

Kök neden ölçüldü (ADR-013 §4): **aynı makro hikâye kaynaklar arasında
ortak bir olayda buluşmuyor.** Medya, resmî veri açıklamasını değil
çevresindeki yorumu işliyor; resmî yayın ile yorum arasındaki gecikme
72 saatlik kümeleme penceresini aşabiliyor.

> **Sonuç: kaynak eklemeye devam etmek 🟢 üretmez.** Faz B'nin ağırlığı
> B2/B3'ten (yeni kaynak) B6/B7'ye (hikâye eşleşmesi) kaydı.

| # | İş | Değer | Karmaşıklık | Risk |
|---|---|---|---|---|
| ~~B1~~ | ~~SBB ekle~~ | ✅ **UYGULANDI** — Tier 1 ayağı açıldı | XS | — |
| **B6** | **Resmî yayın ↔ medya yorumu eşleştirme** | 🟢'nin ÖNÜNDEKİ ASIL ENGEL | **L** | kümeleme precision'ı riske atmadan |
| **B7** | **Kümeleme zaman penceresini konuya göre esnet** | Aylık veri açıklamaları 72 sa'e sığmıyor | M | yanlış birleştirme riski — ölçülmeli |
| B4 | Tier 1 konu filtresini gözden geçir | TCMB %80, Resmî Gazete %76 eleniyor | S | **editoryal kapsam kararı** |
| B8 | `odemeler_dengesi` + `dis_ticaret` konuları | SBB'nin en ayırt edici 2 kalemi eleniyor | S | kapsam kararı |
| B2 | YSK için HTML adaptörü | Seçim döneminin tek kritik kaynağı; R7 tavanında | M | seçim takvimine bağlı |
| B3 | ÇSGB adaptörü | `asgari_ucret_ve_zamlar` birincil kaynağı yok | M | — |
| B5 | `diversity_ratio` metriğini panoya bağla | Kıtlık erken görünür | S | — |

> B4 dikkat ister: filtre ADR-012'de bilinçli olarak dar tutuldu.
> Gevşetmek maliyeti ve gürültüyü artırır. Önce **ölçülmeli**: elenen
> Tier 1 kalemlerin kaçı gerçekten kapsam dışı?
>
> B6/B7 daha da dikkat ister: kümelemeyi gevşetmek yanlış birleştirme
> üretir ve bu, teyit yokluğundan **daha zararlıdır** (Spec §8.2). Her
> değişiklik Golden Set precision'ına karşı ölçülmelidir (hedef ≥0,88).

---

## Faz C — Güvenilirlik

| # | İş | Değer | Karmaşıklık |
|---|---|---|---|
| C1 | `ingest_all` için dağıtık kilit | Tur üst üste binerse yakın-tekrar işareti yarışır | S |
| C2 | HALF_OPEN devrede zaman aşımı | Nadir de olsa kalıcı bloke edilebilir host | S |
| C3 | DNS rebinding koruması (IP sabitleyen transport) | SSRF'in kalan açığı | M |
| C4 | Ölü mektup kuyruğu (dead-letter) | 10 kez düşen görev sessizce kayboluyor | M |

---

## Faz D — Veri zekâsı

| # | İş | Ön koşul | Değer |
|---|---|---|---|
| D1 | İddia evrimi (claim tracking) | **Faz B** | Aynı iddianın zaman içinde durumu nasıl değişti |
| D2 | Olay zaman tüneli | D1 | Hikâyenin gelişimi |
| D3 | Çelişki tespiti (kaynaklar arası) | Faz B | `contradicted` şu an neredeyse hiç üretilmiyor |
| D4 | Düzeltme takibi (correction tracking) | D1 | Kaynak haberi düzeltince ne olacak |

---

## Faz E — Siyasi zekâ

Mevcut temel güçlü: `political_memory`, `promise_tracker`, `stance_shifts`,
`relation_engine` zaten var ve çalışıyor (102 söylem kayması, 736 ilişki).

| # | İş | Ön koşul | Not |
|---|---|---|---|
| E1 | Aktör ilişki grafiği görselleştirme | mevcut veri | `graph_retrieval` hazır |
| E2 | Parti pozisyon takibi | **B1–B3** | parti resmî kaynağı YOK — önce o |
| E3 | Yasama takibi derinleştirme | mevcut | `verticals/legislation` var |

---

## Faz F — Ölçeklenebilirlik

Şu an **gerekmiyor** ve bu ölçüldü: darboğaz altyapı değil, ücretsiz
katman LLM kotası (eşzamanlılık 2→4 denendi, verim sabit kaldı, gecikme
%40 arttı — `docker-compose.yml` başlığında kayıtlı).

| # | Tetikleyici | İş |
|---|---|---|
| F1 | Dedup penceresi > 8.192 kayıt | `ngram_set` LRU önbelleği taşar, madde başına maliyet ~37× artar |
| F2 | `articles` > ~500k | Pencere sorgusuna kısmi indeks |
| F3 | LLM kotası büyürse | Eşzamanlılığı **yeniden ölçerek** artır |

> F1 gerçek bir eşiktir: pencere bugün 6.239, tavan 8.192. Yaklaşıldığında
> `lru_cache(maxsize=)` büyütülmeli — yoksa sessiz bir başarım uçurumu.

---

## Faz G — İleri AI

| # | İş | Risk |
|---|---|---|
| G1 | Çapraz kaynak iddia eşleme kalitesini yükselt | `cross_source_matcher` var; Golden Set'e karşı ölçülmeli |
| G2 | Yerel çıkarım (maliyet) | ADR-009'da **ölçüldü ve reddedildi** — yeniden açmadan önce donanım değişmeli |
| G3 | Prompt sürüm A/B ölçümü | mevcut `eval/` altyapısı yeterli |

---

## Faz H — Üretim mükemmelliği

| # | İş | Not |
|---|---|---|
| H1 | Lighthouse'u CI'a bağla | Skor bir kez ölçülüp yazıldı ve **sessizce geriledi** (100→93). Artık testle kilitli ama CI'da koşmuyor |
| H2 | `ui_check`'i CI'a bağla | Docker gerektiriyor; şu an elle |
| H3 | Yük altında dayanıklılık ölçümü | henüz hiç yapılmadı |

---

## 7. Ölçüme dayanmayan fikirler (bilerek ayrı)

Aşağıdakiler denetimde bir gözleme dayanmıyor; ürün sahibinin kararı
olmadan öncelik verilmemeli:

kişiselleştirilmiş panolar · kayıtlı aramalar · bildirim sistemi ·
webhook · genel API · coğrafi trend analizi · medya yanlılığı skoru ·
haftalık brifing varyantları · karşılaştırma ekranları (kaynak/olay/aktör).

Bunların hiçbiri kötü fikir değil. Ama Faz B kapanmadan hepsi **boş bir
kanıt derecesinin üstüne** kurulur.

---

## Tek cümlelik özet

> Sistem sağlam, güvenli ve gözlemlenebilir. Eksik olan şey kanıt
> yoğunluğu değil — **hikâye eşleşmesi**: resmî kaynak da medya da aynı
> gelişmeyi yazıyor, ama ortak bir olayda buluşmuyorlar. Sıradaki iş
> kaynak eklemek değil, bu buluşmayı sağlamaktır (B6/B7).

*20 Ağu 2026 güncellemesi: bu cümle SBB ölçümünden SONRA değişti. Önceki
teşhis "kanıt yoğunluğu" idi ve kısmen doğruydu (Tier 1 payı %1,8'di);
SBB o açığı kapattı ama 🟢 artmadı. Ölçüm teşhisi düzeltti.*
