# PolitikDesk — S3 Genel Siyaset Hukuki Çerçeve ve Editoryal Risk Analizi (Spec v3.4 §5, §14.4 · S3-5)

**Tarih:** 15 Ağustos 2026  
**Kapsam:** Genel Siyaset Dikeyinde Hukuki Riskler, Epistemik Disiplin ve Editoryal Güvenlik Sınırları

---

## 1. Giriş ve Risk Matrisi

Makro ekonomi dikeyindeki düşük hukuki risk varsayımı (yalnızca resmi istatistik bültenleri ve piyasa verileri), **Genel Siyaset dikeyinde geçerli değildir**. Siyasi aktörlerin açıklamaları, meclis tartışmaları, seçim beyannameleri ve kamu harcaması iddiaları doğrudan cezai ve hukuki sorumluluk doğurabilir.

| Risk Alanı | Yasal Dayanak | Risk Tanımı | PolitikDesk Savunma Hattı |
|---|---|---|---|
| **Yanıltıcı Bilgiyi Yayma** | TCK m. 217/A | Gerçeğe aykırı bir bilgiyi kamu barışını bozmaya elverişli şekilde yayma. | Doğrulanmamış hiçbir iddiaya kesinlik dili verilmez. Yalnızca resmi tutanak ve çoklu bağımsız kaynakla desteklenen iddialar işlenir. |
| **Kişilik Hakları & İtibar** | TMK m. 24, TCK m. 125 | Siyasi aktörlere yönelik haksız itham, kişisel kusur veya suç isnadı. | Epistemik çekince paneli (`LEGAL_DISCLAIMER`); iddialar kişiye değil, kamuya açık beyan ve tutanağa atfedilir. |
| **Haber/Yorum Karmaşası** | Basın Kanunu m. 3 | Köşe yazısı, kulis dedikodusu veya yorumların haber gibi sunulması. | `opinion_classifier.py` filtresi ile köşe yazılarından çıkan iddialar otomatik olarak `attribution` türüne dönüştürülür. |
| **Seçim Dönemi Kısıtları** | 298 Sayılı Kanun | Seçim yasakları, kamuoyu araştırmaları manipülasyonu ve taraflılık. | `Election Mode` sıkılaştırması: Tek kaynaklı üretim engeli, Tier 1 zorunluluğu, ≥4 bağımsız kaynak şartı. |

---

## 2. Epistemik İlkeler ve Programatik Koruma

### 2.1 Atıf ve Kaynak Ayrımı (Attribution Principle)
- Siyasi parti sözcüsü, genel başkan veya bakan beyanları **olgu (fact) değil, aktör iddiasıdır (attribution)**.
- Sistem bu beyanları asla nesnel bir gerçeklik gibi başlığa veya metne taşımaz; mutlaka "... iddia etti", "... öne sürdü" veya "... taahhüt etti" fiilleriyle sunar.

### 2.2 Olgu / İddia / Kanıt Hiyerarşisi
```text
Resmî Tutanak / Kanun (TBMM, Resmî Gazete, Sayıştay)
        ↓  [En Yüksek Güvenilirlik - Tier 1]
Çok Kaynaklı Doğrulanmış İddia (≥3 Bağımsız Grup)
        ↓  [Strongly Corroborated - 🟢]
Tek Kaynaklı Beyan / Haber (Tier 2 / Media)
        ↓  [Single Source - ⚪]
Köşe Yazısı / Kulis / Spekülasyon
        ↓  [Attribution Only - Yorum Olarak İşaretli]
```

### 2.3 Belirsizlik ve İhtiyat Dili
- Teyit edilmemiş veya çelişkili durumlarda model prompt'larında ve taslak üretiminde "kesinleşti", "ispatlandı", "yolsuzluk yapıldı" gibi hüküm bildiren ifadeler **programatik olarak engellenir** (`editorial/guards.py`).

---

## 3. Düzeltme ve Tekzip Protokolü (Correction Protocol)

1. Bir siyasi aktörün beyanı resmi veriyle çeliştiğinde sistem çelişkiyi (`contradicts`) gösterir, ancak aktörü "yalan söylemekle" itham etmez; "Resmî veri ile beyan arasında uyumsuzluk bulunmaktadır" ifadesi kullanılır.
2. Olay hakkında resmi bir düzeltme, tekzip veya yeni kanun teklifi geldiğinde `updates` ilişkisiyle olay kartı güncellenir ve revizyon geçmişi `audit_log` içinde korunur.

---

## 4. Mimari Kısıtlar (Spec §15)

- Bu editoryal ve hukuki güvenlik çerçevesi deterministiktir.
- Kullanıcı tercihlerinden veya LLM serbestliğinden etkilenmez; `evidence/rules.py` ve `editorial/guards.py` tarafından zorunlu kılınır.
