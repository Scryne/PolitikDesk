# Sertifikasyon arşivi — Ağustos 2026

Bu klasördeki **163 dosya** 2026-08-27'de depo kökünden buraya taşındı.
Hiçbiri silinmedi; git geçmişi `git log --follow` ile takip edilebilir.

## Neden taşındılar

Kökte 179 markdown dosyası vardı ve bunların 163'ü rapor/sertifikasyon çıktısıydı:
`FAZ_15` → `FAZ_24`, `PHASE_25` → `PHASE_27`, `PHASE_C` → `PHASE_J`, `FINAL_*`,
`PRODUCTION_*_2026-08-23`, `SOURCE_*`, çeşitli `*_AUDIT` ve `*_GATE` dosyaları.

Aynı işin dokuzdan fazla kez "final sertifikasyon" başlığıyla belgelenmesi projeyi
yayına yaklaştırmadı; kök dizini okunamaz hale getirdi. ScryneOS'un kuralı bunu
adıyla anıyor:

> Bir projeyi "bitti" ilan eden doküman yazma; bitti kanıtı **kullanımdır**.

Bu klasör o kuralın uygulanmasıdır: geçmiş korunur, kök temizlenir.

## Kökte ne kaldı (16 dosya)

Referans ve işletim dokümanları — üretilen rapor değil, kullanılan belge:

`README.md` · `CLAUDE.md` · `DESIGN.md` · `DURUM.md` · `BACKLOG.md` ·
`PRODUCTION_RUNBOOK.md` · `PRODUCTION_SLO.md` · `CAPACITY_LIMITS.md` ·
`PolitikDesk_Master_Spec_v3.md` · `PolitikDesk-Ultimate-Production-Roadmap.md` ·
`POLITIKDESK-FAZ-FAZ-YOL-HARITASI.md` · `PolitikDesk_Yol_Haritasi_v1.md` ·
`PolitikDesk-Gorev-Listesi.md` · `yol-haritasi.md` · `yol-haritasi-g4-kapanisi.md` ·
`walkthrough.md`

## Rapor üreten betikler

Altı betik bu raporlardan bazılarını **yeniden üretiyordu ve köke yazıyordu**.
Çıktı yolları bu klasöre yönlendirildi, yoksa kök yeniden dolardı:

| Betik | Yazdığı dosya |
| --- | --- |
| `scripts/generate_phase25_baseline.py` | `PHASE_25_BASELINE.md` |
| `scripts/generate_performance_report.py` | `PHASE_25_PERFORMANCE_REPORT.md` |
| `scripts/db_forensic_audit.py` | `PHASE_26_DATABASE_FORENSIC_REPORT.md` |
| `scripts/generate_phase26_load_soak_report.py` | `PHASE_26_LOAD_TEST_REPORT.md` · `PHASE_26_SOAK_TEST_REPORT.md` |
| `scripts/generate_taxonomy_500_confusion_matrix.py` | `PHASE_26_TAXONOMY_REDTEAM_REPORT.md` |
| `scripts/verify_all_101_sources_adapters.py` | `PHASE_26_SOURCE_VALIDATION_REPORT.md` |

Betikler artık hedef klasörü kendileri oluşturuyor (`mkdir(parents=True)`).
