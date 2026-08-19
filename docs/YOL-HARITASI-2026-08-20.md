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
sayısı **5.262'de 2**, ve R2'nin istediği bileşimi sağlayan iddia
sayısı **sıfır**. Ürünün amiral göstergesi çalışmıyor — kural kusuru
değil, **girdi kıtlığı** (Tier 1, kanıt havuzunun %1,8'i).

Bu faz tamamlanmadan aşağıdaki hiçbir zekâ katmanı gerçek değer üretmez:
hepsi kanıt derecesinin üstüne kurulur.

| # | İş | Değer | Veri gereksinimi | Karmaşıklık | Risk |
|---|---|---|---|---|---|
| B1 | SBB kaynağını ekle (`max_sources` 21→22) | R2 için Tier 1 birincil kaynak | yok — besleme canlı doğrulandı | **XS** | Spec §9.2 kararı gerekir |
| B2 | YSK için HTML adaptörü | Seçim döneminin tek kritik kaynağı; şu an R7 tavanında | adaptör | M | seçim takvimine bağlı |
| B3 | ÇSGB adaptörü | `asgari_ucret_ve_zamlar` konusunun birincil kaynağı yok | adaptör | M | — |
| B4 | Tier 1 konu filtresini gözden geçir | TCMB %80, Resmî Gazete %76 eleniyor | yok | S | **editoryal kapsam kararı** |
| B5 | `diversity_ratio` metriğini panoya bağla | Kıtlık erken görünür | mevcut | S | — |

> B4 dikkat ister: filtre ADR-012'de bilinçli olarak dar tutuldu.
> Gevşetmek maliyeti ve gürültüyü artırır. Önce **ölçülmeli**: elenen
> Tier 1 kalemlerin kaçı gerçekten kapsam dışı?

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

> Sistem sağlam, güvenli ve gözlemlenebilir. Eksik olan şey **kanıt
> yoğunluğu**; sıradaki iş özellik eklemek değil, motoru doyurmaktır.
