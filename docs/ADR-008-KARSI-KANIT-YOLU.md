# ADR-008: Karşı Kanıt Yolu — Ölü Kural ve Neden Diriltilmedi

**Durum:** Kabul Edildi (Accepted) — boyut `unavailable` olarak işaretlendi
**Tarih:** 19 Ağustos 2026
**İlgili:** Roadmap Faz 5.2, `evidence/matrix.py`, `evidence/rules.py`,
`nlp/claims_pipeline.py`

---

## 1. Bulgu

Roadmap 5.2 iddia kanıt matrisinde şu boyutları istiyor:

```
Claim
├── Evidence +          ✅ 5.311 satır
├── Evidence −          ❌ 0 satır — YAPISAL
├── Counterclaim        ❌ türetilemiyor
└── ...
```

Ölçüm (19 Ağustos 2026, canlı veri):

| Ne | Sonuç |
|---|---|
| `evidence.stance` dağılımı | **5.311 satırın 5.311'i `'supports'`** |
| `stance='contradicts'` yazan kod yolu | **YOK** (depo geneli arama) |
| `evidence_status='contradicted'` | **4.333 iddianın 0'ı** |

Sebep tek satırda: `nlp/claims_pipeline.py` kanıt bağını **sabit kodlu**
`stance='supports'` ile yazıyor.

```sql
INSERT INTO evidence (claim_id, article_id, stance, quote_span, extracted_by)
VALUES (%s, %s, 'supports', %s, %s)
```

Sonuç: `evidence/rules.py::_r1_contradicted()` yazılmış, belgelenmiş ve
birim testleri olan bir kuraldır — ama **üretimde asla ateşleyemez.**
`e.supports == False` koşulunu sağlayan hiçbir satır üretilmiyor.

Bu, bu depoda ikinci kez görülen kalıptır. Birincisi migration 0007'de
kayıtlı:

> *"Kural yazılmıştı, ölüydü."* (R3 `verified_against_source`)

Fark şu: R3'ün ölü olduğu Faz 5'te fark edildi ve **düzeltildi** (kurumun
kendi sayısı `articles.official_value`'ya yazılmaya başlandı). R1 hâlâ ölü.

---

## 2. Değerlendirilen çıkış yolları

### 2.1 LLM'e `stance` çıkarttırmak

`nlp/claims.py` başlığındaki DoD zaten bunu öngörüyor:

> F2-10 Kanıt eşleme: ≤200 karakter alıntı + `stance` + `extracted_by`.

Yani `stance` **spesifikasyonda vardı**, uygulanmadı. Modelden bir
makalenin bir iddiayı destekleyip desteklemediğini istemek, Spec §8.1'i
(kanıt durumuna LLM karar veremez) ihlal etmez: `stance` tek bir
makale-iddia çifti hakkında bir GÖZLEMDİR, hüküm değil. Hükmü kural
motoru verir.

**Neden şimdi yapılmadı:** LLM şeması, prompt sürümü (`claims.v4`) ve
4.333 iddianın yeniden çıkarımı gerekir. Bu, bütçe ve doğrulama açısından
kendi başına bir iştir; yarım yapılırsa ölü kuralın yerine **güvenilmez**
bir kural gelir.

### 2.2 Deterministik sayısal çelişki (`numeric_guard`)

`clustering/numeric_guard.find_conflicts()` "aynı metrik, farklı değer"
tespiti yapar ve LLM kullanmaz. Kulağa doğru çözüm gibi geliyor.

**Ölçüldü, işe yaramadı:**

| Deney | Çift sayısı | Bulunan çelişki |
|---|---:|---:|
| İddia × kaynaklayan makale | 4.000 | **1** |
| İddia × kaynaklamayan makale (çapraz) | 20.000 | **0** |

Sebebi anlaşılır: kanıt bağları iddianın ÇIKTIĞI makaleye kurulur, yani
yapı gereği uyumludurlar. Çapraz karşılaştırmada ise iddia metinleri kısa,
alıntılar ≤300 karakter ve iddiaların çoğu sayısal değil (4.333'ün 63'ü
`number`, 2.013'ü `fact`, 1.892'si `attribution`).

Bu yolla matris boyutunu doldurmak, **iki satır üretmek için bir alt
sistem** yazmak olurdu.

---

## 3. Karar

**Karşı kanıt boyutu `unavailable` olarak işaretlendi — `0` olarak değil.**

Ayrım pazarlıksız ve bu depoda tekrar eden bir derstir:

* `0` = "aradık, bulamadık"
* `unavailable` = "bu boyut ölçülmüyor"

İkisini karıştırmak, kullanıcıya *"bu iddiaya karşı hiçbir kanıt yok"*
demektir — oysa doğru cümle *"karşı kanıt aranmıyor"*. Birincisi bir
güven beyanıdır ve yanlıştır.

Aynı ilke bu oturumda üç kez uygulandı: anomali tespitinde
`insufficient_history ≠ normal`, kaynak kalitesinde `ölçülemedi ≠ sıfır`,
takvimde `published ≠ cancelled`.

---

## 4. Yeniden açılma koşulu

`evidence/matrix.py::coverage_report()` içindeki
`contradiction_path_alive` alanı `true` döndüğünde bu ADR yeniden
değerlendirilir. O an geldiğinde:

1. `_r1_contradicted()` canlanır — mevcut testleri zaten var.
2. Matrisin iki boyutu `measured`'a geçer.
3. `evidence_status='contradicted'` ilk kez üretilebilir hâle gelir.

Bunu sağlayacak iş §2.1'dir (LLM `stance` çıkarımı) ve kendi fazını
hak eder.

---

## 5. Bu ADR neyi ENGELLİYOR

Karşı kanıt boyutunun arayüzde **"0"** olarak gösterilmesini. Bir kullanıcı
"Çelişen kanıt: 0" gördüğünde bunu bir doğrulama sinyali sayar; oysa sistem
hiç bakmamıştır. Boş bir sütunu dolu göstermek, yanlış bir sayı göstermekle
aynı sınıftadır — ve bu ürün 18 Ağustos denetiminde tam olarak bu yüzden
kumanda odasındaki uydurma göstergeleri kaldırmıştı.
