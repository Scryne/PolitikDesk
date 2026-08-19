# ADR-012: Konu Filtresinin Boşalttığı Tur Kaynak Arızası Değildir

**Durum:** Kabul Edildi (Accepted)
**Tarih:** 19 Ağustos 2026
**İlgili:** Roadmap Faz 2.3 ve Faz 0/O-01, `ingestion/repository.py`,
`ingestion/adapters/base.py`, `ingestion/adapters/resmi_gazete.py`,
`ingestion/pipeline.py`, `tests/test_resmi_gazete.py`

---

## 1. Bulgu

`resmi-gazete` üç fazdır kırmızıydı ve sebebi B-44 (GoodbyeDPI + eksik ara
sertifika) diye biliniyordu. 19 Ağustos'ta GoodbyeDPI servisinin kendi
kendine durduğu (`STATE: STOPPED`, çıkış kodu 1067) görüldü ve ağ tarafı
ölçüldü:

| Konak | TLS el sıkışma |
|---|---|
| `resmigazete.gov.tr` | OK, 97 ms |
| `sayistay.gov.tr` | OK, 90 ms |
| `tccb.gov.tr` | OK, 64 ms |

Adaptör canlıda **17 kalem / 0,2 sn** çekiyordu. Yani B-44 kapanmıştı —
ama kaynak hâlâ kırmızıydı ve ardışık hata sayacı **758**'di.

Sebep ağ değildi. Zincir şuydu:

```
adaptör fihristten 17 kalem ayrıştırıyor
  → konu filtresi (vergi, gümrük, KDV, asgari ücret, …) hiçbirini geçirmiyor
  → fetch() 0 öğe döndürüyor            ← DOĞRU davranış
  → record_fetch bunu ARIZA sayıyor     ← YANLIŞ yorum
  → consecutive_errors++
```

O günkü fihrist gerçekten vergi kalemi içermiyordu: "Nemrut Kalderası",
"İzmir Kavram MYO yönetmelikleri", "Yargıtay kararları", "Yapay Zekâ
Eylem Planı Genelgesi". Filtre doğru çalışıyordu.

### Ölçüm (7 gün, `source_fetch_log`)

| kaynak | tur | "başarılı" | bunların 0 öğe döndüreni | gerçek hata |
|---|---:|---:|---:|---:|
| `resmi-gazete` | 1358 | 736 | **516** | 622 |
| `tuik` | 1350 | 1279 | 188 | 71 |
| `sayistay` | 910 | 504 | 0 | 406 |

758 ardışık "hata"nın büyük kısmı, Resmî Gazete'nin o gün vergi mevzuatı
yayımlamamış olmasıydı. Boru hattı 5 dakikada bir koşuyor; Resmî Gazete
vergi düzenlemesini ayda birkaç kez yayımlıyor. 516 boş tur **beklenen**
sayıdır.

### Asimetri

Aynı semantik sonuç, filtrenin nerede olduğuna göre zıt sağlık verdiği
alıyordu:

| Filtre nerede | Örnek | `items_fetched` | Kaynak durumu |
|---|---|---:|---|
| Boru hattında | `ekonomim`: 25 çekildi, 25 elendi, 0 saklandı | 25 | **yeşil** |
| Adaptör içinde | `resmi-gazete`: 17 ayrıştırıldı, 17 elendi | 0 | **kırmızı** |

İkisi de "kaynak sağlıklı, bugün konumuzla ilgili bir şey yok" diyor.

---

## 2. Karar

`record_fetch` üretkenliği **konu filtresinden önceki** sayıyla ölçer:

```python
uretken = items_fetched > 0 or (items_parsed or 0) > 0
```

`items_parsed` adaptörden gelir (`FailureRecorder.note_parsed` /
`drain_parsed`). `None` = "bu adaptör ayrım yapmıyor" ve eski davranış
aynen korunur — 89 kaynağın 88'i konu filtresi kullanmıyor, onlar için
`items_fetched` zaten ham sayının kendisidir.

Mekanizma, deponun B-80'de kurduğu `drain_failures` desenini birebir
izler: adaptör kendi bildiğini deftere yazar, boru hattı turu kapatırken
boşaltır.

---

## 3. Neden bu şekilde, alternatifler neden değil

**Alternatif A — `resmi-gazete`'ye dar istisna.** Reddedildi: kuralı iki
yerde tutar. Bu deponun tekrar tekrar bedelini ödediği desen budur
(kısayol listesi üç kopya, palet listesi iki kopya — ikisi de Faz 8'de
temizlendi).

**Alternatif B — "0 öğe → arıza" kuralını tamamen kaldırmak.** Reddedildi
ve reddedilmesi bu ADR'nin en önemli kısmı. O kural B-42/B-43'ün
korumasıdır: **uç 200 döner, gövde beklenen şey değildir, tur sessizce
başarılı görünür.** EVDS'nin anahtarsız HTML yanıtı ve `/rss`'in RSS
olmayan gövdesi tam olarak buydu. Koruma DURUYOR; değişen tek şey ölçünün
hangi noktada alındığı.

**Alternatif C — konu filtresini boru hattına taşımak.** Görünüşte
asimetriyi kökten çözer, ama Resmî Gazete'de filtre bilinçli olarak
adaptörde: filtresiz toplama `articles` tablosunu üniversite
yönetmelikleriyle doldurur ve embedding maliyetini boşa harcar
(`tests/test_resmi_gazete.py::test_keyword_filter_keeps_only_relevant_items`).

---

## 4. Neden bu bir yanlış alarmdan fazlası

Roadmap Faz 2.3 tek bir şart koyuyor: *"Alarm yanlış pozitif üretmemeli."*
Gerekçe gürültü değil **körlük**:

> Kaynak zaten hep kırmızıysa, gerçekten bozulduğu gün hiçbir şey değişmez.

`resmi-gazete` 758 turdur kırmızıydı. Bu süre boyunca kaynak gerçekten
bozulsaydı — sayfa yapısı değişse, WAF gövdeyi değiştirse — hiçbir
gösterge kıpırdamazdı. Sinyal, sinyal olmaktan çıkmıştı.

Aynı ilke bu depoda daha önce üç kez uygulanmıştı: iddia çıkarımı alarmı
(kalıcı kırmızıydı), DB testleri (sessizce atlanıyordu), `git diff --check`
(yüzlerce sahte uyarı). Faz 2.1'de de kayıtlı: *"yapısal özellik alarm
üretmez"* — bir kaynağın Tier 4 olması bakım istemez.

---

## 5. Sonuç (ölçülmüş)

| | önce | sonra |
|---|---:|---:|
| `resmi-gazete` ardışık hata | 758 | **0** |
| `last_success_at` | 15 Ağu 20:59 | 19 Ağu 18:01 |
| Kumanda odası "susan kaynak" | 8 | **7** |

Kalan 7 susan kaynağın tamamı, RSSHub'ın X'ten aldığı yukarı akış
HTTP 503'üne bağlı X hesaplarıdır — onlar **gerçek** sessizliktir ve
kırmızı kalmaları doğrudur.

---

## 6. Denetim

`tests/test_resmi_gazete.py`:

| Test | Neyi kilitler |
|---|---|
| `test_topic_filter_emptying_the_round_is_not_a_source_failure` | Filtre boşalttı → ham sayaç kaynağın sağlıklı olduğunu söyler |
| `test_empty_index_is_still_a_source_failure` | **B-42/B-43 koruması kalkmadı** |
| `test_parsed_counter_is_drained_between_rounds` | Sayaç turlar arası taşınmaz |
| `test_health_rule_uses_parsed_count_not_filtered_count` | `record_fetch` sözleşmesi sabit |
| `test_adapters_without_the_counter_keep_the_old_behaviour` | 88 kaynak etkilenmez |

---

## 7. Bu kararı geri almak gerekirse

`record_fetch`'te `uretken` ifadesini `items_fetched > 0` yapmak yeter;
`items_parsed` parametresi geriye dönük uyumludur ve yok sayılabilir.
Ama geri almadan önce §4 okunmalıdır: geri alma, `resmi-gazete`'yi ayda
birkaç gün dışında kalıcı kırmızıya döndürür ve o kaynağın gerçek
arızalarını görünmez yapar.
