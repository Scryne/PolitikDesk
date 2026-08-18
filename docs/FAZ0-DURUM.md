# Faz 0 — Durum Panosu

**Faz:** Karar, Doğrulama ve Zemin · **Son güncelleme:** 12 Ağustos 2026

---

## ⚠️ Kapsam kararı: kişisel araç

Proje **tek kullanıcılı kişisel bir araç** olarak kararlaştırılmıştır.
Bunun Faz 0'a üç etkisi vardır:

| Kalem | Karar |
|---|---|
| **F0-10 / F0-11 — Hukuk danışmanlığı** | ⛔ **Kaldırıldı.** Yapılmayacak. `docs/hukuk-notu.md` silindi; G0 koşul 4 düştü. |
| **F0-04 / F0-05 — Kullanıcı görüşmeleri** | ⛔ **Kaldırıldı.** Ürünün kullanıcısı = geliştiricisi. G0 koşul 2 düştü. DG-1 karar noktası geçersiz. |
| **D19 — Fiyatlandırma** | Geçersiz. Müşteri yok. |
| **F4-17…F4-22 — Kapalı beta** | Faz 4'te yeniden değerlendirilecek. |

**Kodda değişmeyenler** (bedava koruma oldukları için bırakıldı):
alıntı ≤300 karakter, tam metin saklanmaz, 30 gün TTL + otomatik purge,
`editorial_profiles`'ta ideolojik alan yok, `tos_status='forbidden'`
kaynaktan ingestion engelli.

---

## Kapı G0 — Çıkış Koşulları (güncellenmiş)

| # | Koşul | Kaynak | Durum |
|---|---|---|---|
| 1 | Spec dondurulmuş, tag mevcut | F0-02 | ✅ **Spec v3.1** — 4 itiraz kapatıldı |
| ~~2~~ | ~~≥10 kullanıcı görüşmesi~~ | — | ⛔ **Kapsam dışı** |
| 3 | Kaynakların `tos_status` kararı verilmiş; hiçbiri `forbidden` değil | F0-08, F0-09 | ✅ **7/7 karara bağlandı** |
| ~~4~~ | ~~Hukuk danışmanlığı~~ | — | ⛔ **Kapsam dışı** |
| 5 | Embedding modeli seçilmiş, ayrım gücü ölçülmüş | F0-13 | ✅ **`multilingual-e5-large`** — 3 aday, 60 gerçek çift |
| 6 | Golden Set ≥100 makale | F0-14 | 🔴 **0/100** |
| 7 | `docker compose up` tüm servisleri ayağa kaldırıyor | F0-12, F0-15 | ✅ **Doğrulandı** |
| 8a | Birim ekonomi: 100 kullanıcıda ≤ 8 $/kullanıcı/ay | F0-07 | ✅ **4,67 $** (modellendi) |
| 8b | Bütçe tavanı: toplam aylık maliyet | F0-07 | ✅ **22,94 $/ay (kişisel profil)** — tavanın çok altında |
| 9 | Mimari kural testi CI'da aktif | F0-16 | ✅ **Doğrulandı** |

**Kapı durumu: 🟡 6/7 sağlandı** — yalnızca Golden Set açık.

> Faz 1 ve Faz 2, Golden Set açıkken başlatıldı. Gerekçe: ingestion boru hattı,
> hem Golden Set'in hem embedding benchmark'ının ihtiyaç duyduğu **gerçek
> veriyi üreten** katmandır. Sırayı tersine çevirmek, aynı veriyi elle
> toplamak anlamına gelirdi.

---

## Görev durumu

| ID | Görev | Durum | Çıktı |
|---|---|---|---|
| F0-01 | Spec D1–D15 itirazları | ✅ | `docs/karar-itirazlari.md` — 7 itiraz, 2'si engelleyici |
| F0-02 | spec-freeze | ✅ | **Spec v3.1 donduruldu** — 4 itiraz kapatıldı, §0'a değişiklik bloğu ve §17'ye sürüm geçmişi eklendi |
| F0-03 | MVP konu sınırı | ✅ | `docs/mvp-konu-kapsami.md` — 10 konu; kodda `topics.py` ile zorlanıyor |
| F0-19 | Backlog | ✅ | `BACKLOG.md` |
| ~~F0-04~~ | ~~12 kullanıcı görüşmesi~~ | ⛔ | Kapsam dışı |
| ~~F0-05~~ | ~~Görüşme kılavuzu~~ | ⛔ | Kapsam dışı |
| F0-06 | X API fiyatlandırması | ✅ | MVP'de 0 $ (D7); Faz 5 senaryosu geçersiz (kişisel araç) |
| F0-07 | Maliyet modeli | ✅ | `docs/veri-maliyet-modeli.md` + `scripts/cost_model.py` |
| F0-20 | Rakip analizi | ✅ | `docs/rakip-analizi.md` — 8 ürün |
| F0-08 | Kaynak erişim + ToS | ✅ | 7 kaynak karara bağlandı; 4'ü canlı doğrulandı |
| F0-09 | Tier 3 kaynak isimleri (D17) | ✅ | **Dünya** + **BloombergHT** — ikisi de canlı RSS |
| ~~F0-10~~ | ~~Hukuk danışmanlığı~~ | ⛔ | Kapsam dışı |
| ~~F0-11~~ | ~~Kısıtları Spec'e işle~~ | ⛔ | Kapsam dışı |
| F0-12 | Repo, ortam, CI | ✅ | Docker Compose + GitHub Actions — doğrulandı |
| F0-13 | Embedding benchmark | ✅ | 60 gerçek çift + 3 aday koşuldu; **D16 = `multilingual-e5-large`** |
| F0-14 | Golden Set 100 makale | 🔴 | Araçlar hazır; **0/100** |
| F0-15 | Veri şeması | ✅ | `0001_initial.sql` + `0002_ingestion.sql` |
| F0-16 | Mimari kural testi | ✅ | Deneyle doğrulandı |
| F0-17 | LLM adapter + bütçe | ✅ | `politikdesk/llm/` |
| F0-18 | Gözlemlenebilirlik | ✅ | structlog JSON + Sentry + `metrics` |

**18 görevin 14'ü tamam**, 2'si kısmi, 4'ü kapsam dışı bırakıldı.

---

## D17 kararı — Tier 3 kaynakları (F0-09)

| Kaynak | Grup | Akış | Doğrulama |
|---|---|---|---|
| **Dünya Gazetesi** | `media-dunya` | `dunya.com/rss?dunya` | ✅ canlı, 25 öğe |
| **BloombergHT** | `media-bloomberght` | `bloomberght.com/rss` | ✅ canlı, 20 öğe |

Farklı yayın grubu ✓ · Farklı çerçeveleme ✓ (Dünya genel gündem ağırlıklı,
BloombergHT piyasa/veri ağırlıklı)

## Reuters düşürüldü

Açık RSS ucu yok, içerik lisansa tabi. `docs/kaynak-kayit-defteri.md`'deki
karar ağacının "lisans zorunlu, bütçe dışı → kaynak düşer" dalı işletildi.

**Sonuç:** 8 yerine **7 kaynak**. Uluslararası çapraz teyit rolü boşta.
Etkisi Faz 2'de `evidence_status` dağılımıyla ölçülmeli
(`docs/karar-itirazlari.md` İtiraz-2, `BACKLOG.md` B-37).

---

## Faz 0'da ortaya çıkan bulgular

| # | Bulgu | Durum |
|---|---|---|
| 1 | **R1 (çelişki) ile R8 (tahmin) kuralları çelişiyor** | ✅ Çözüldü — v3.1 §8.3: tahmin kısıtı R0 olarak başa alındı ve kısa devre yapıyor |
| 2 | **Salience formülü tek sütunlu şemaya sığmıyor** | ✅ Çözüldü — v3.1 §8.4: global (0–90) saklanır, kişisel (0–10) hesaplanır; DB kısıtı `events_salience_global_range` |
| 3 | Maliyet hedefi ölçek belirtmiyor | ✅ Kişisel araç kararıyla geçersizleşti |
| 4 | §11.5 sıcaklık disiplini modelde uygulanamıyor | ✅ `effort` ile uygulandı (B-36) |
| 5 | 8 kaynak / R2 eşiği etkileşimi ölçülmemiş | ⏳ Faz 2 (B-37) — Reuters düşünce daha da kritik |
| 6 | Embedding'in telif/KVKK statüsü | ⛔ Kişisel araç: konu dışı |
| 7 | Model taslak hacmine duyarlı | ✅ Kişisel profilde 30 taslak/ay varsayıldı |
| 8 | Embedding maliyeti ihmal edilebilir | ✅ D16 kaliteye göre seçilebilir |

**Bulgu 1 ve 2 kapatıldı** — ikisi de Spec v3.1'e işlendi (12 Ağu 2026).
Gerekçe belgesi: `docs/karar-itirazlari.md`.

---

## Kalan iş

| İş | Efor |
|---|---|
| ~~İtiraz-4 (R1/R8) ve İtiraz-7 (salience) Spec'te düzelt → `spec-v3.1`~~ | ✅ tamamlandı |
| ~~D16: 60 çift + benchmark koşumu~~ | ✅ tamamlandı |
| Golden Set 100 makale (artık boru hattından beslenebilir) | 2 PD |
