# DURUM — PolitikDesk — politik istihbarat + deterministik kanıt motoru

> **Ne bu dosya:** sertifika değil **envanter**. 2026-08-27 denetiminde ölçülen gerçek durum.
> "Çalışmıyor" yazan satır kusur değil, kayıt. Kapanış standardı:
> `ScryneOS/🎯 100-Command-Center/Kapanis-Standardi.md`

**Ölçüm tarihi:** 2026-08-27
**Tek cümle:** **2711 test geçiyor ve tüm Docker yığını şu anda ayakta ve sağlıklı.** 359 dosya yıllardır commit edilmemişti.

## Ne çalışıyor

- **Test paketi: 2711 test geçti**, 0 başarısız, 53,85 sn. Depodaki en büyük test kütlesi.
- **Docker yığını canlı ölçüldü** — 7 konteyner çalışıyor:
  `pd-api` (healthy, 127.0.0.1:8000) · `pd-db` (healthy, 5432) · `pd-redis` (healthy, 6379) ·
  `pd-worker` · `pd-worker-llm` · `pd-beat` · `pd-rsshub` (1200). Hepsi ~1 saattir ayakta.
- **Kimlik doğrulama kapısı gerçekten çalışıyor:** `/`, `/docs`, `/web`, `/ui`, `/gundem`
  isteklerinin tümü **401** döndü, Türkçe hata mesajıyla:
  "Kimlik doğrulama gerekli. Authorization: Bearer <token> veya X-API-Token başlığı ekleyin."
- Web arayüzü kodda var (`politikdesk/web/ui`, `politikdesk/web/static`).

## Ne çalışmıyor / doğrulanmadı

- **Ekran hiç görülmedi.** Tüm uçlar auth arkasında; token olmadan arayüz doğrulanamadı.
- Bu denetimde giriş yapılmadı, yani "arayüz çalışıyor" **iddia edilemez**.

## Ne yarım

- **Kökte ~170 sertifikasyon dokümanı var** (`FAZ_15…FAZ_24`, `PHASE_C…PHASE_J`,
  `FINAL_*`, `PRODUCTION_*`). Vault'un kuralı bunu adıyla anıyor: sertifika döngüsü
  ilerleme hissi verir, ilerleme vermez. Proje hâlâ yayında değil.
- Bu denetimde commit edilen 359 dosyanın 269'u yeni: 48 test, 22 script, 21 kaynak,
  8 doküman, 3 migration ve ~165 kök seviyesinde rapor.

## Sonraki adım

Bir token al, arayüzü aç ve gerçekten baktığını buraya yaz. Sertifika dosyası yazma.
