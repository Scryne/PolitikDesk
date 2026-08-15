# Referans Notları ve Tasarım Rehberi (Design References)

> `DESIGN.md` Bölüm 4, Bölüm 14 ve `CLAUDE.md` Zorunlu Tasarım İlkesi:
> PolitikDesk arayüzleri **sakin, hassas ve arşivsel** bir editoryal kayıt masasıdır.

---

## 1. Referans Analizleri ve Tasarım Kararları

### Ref 01 — FT Editorial & Bloomberg Data Density (Finansal Veri Masası)
- **ALIYORUM:** 
  - Yüksek veri yoğunluğu, kompakt tipografik hiyerarşi.
  - Tablo ve kartlarda 1px kenarlık ile yüzey ayrımı (`border: 1px solid var(--pd-color-border)`).
  - Sayısal değerlerin tabüler rakamlar (`tabular-nums`) ile sağa yaslı, sakin dizilimi.
- **ALMIYORUM:**
  - Kalabalık reklam alanları, parlak neon göstergeler ve animasyonlu canlı borsa sayaçları.

### Ref 02 — Linear & GitHub Decision Logs (Karar ve Denetim Kuyruğu)
- **ALIYORUM:**
  - Tek aksan rengi (`--pd-color-accent`) ve anlam odaklı durum rozetleri (`--pd-color-success`, `--pd-color-warning`, `--pd-color-error`).
  - Monospace font ile hash/ID/tarih etiketleri (JetBrains Mono / tabular layout).
  - Geniş ekranlarda 2-kolonlu / split-view denetim paneli.
- **ALMIYORUM:**
  - Aşırı gölgeler, neon efektler ve ağır blur katmanları.

### Ref 03 — Gov.uk & Resmî Gazete Archive (Arşiv ve Yasal Şeffaflık)
- **ALIYORUM:**
  - Tek `<h1>` semantik başlık yapısı, net erişilebilirlik (`lang="tr"`, WCAG AAA kontrast, aria-label zorunluluğu).
  - Kanıt çekmecesi ve yasal çekince bloklarının metin gövdesiyle bütünleşik ama net ayrılmış sunumu.
  - Sıfır yatay taşma (`scrollWidth == clientWidth`).
- **ALMIYORUM:**
  - Hantal ve eski tipik tablo düzenleri; responsive olmayan sabit genişlikler.

---

## 2. 11 Ekran Tipografik ve Görsel Standartları

| Ekran | Rota | Ana Görsel Odak | Epistemik Rozet / Durum |
|---|---|---|---|
| Gündem | `/feed` | Güncel Olay Kartları & Küme Özeti | 8/8 Pipeline Durumu, Canlı Kaynaklar |
| Brifingler | `/briefing` | Sabah/Akşam Editoryal Bülten | Dağıtım Durumu (`send_error=null`) |
| Editoryal Kimlik | `/onboarding/profile` | Tercih ve Odak Alanları | Konu & Sektör Filtreleri |
| Boru Hattı | `/admin/` | Sistem ve Sağlık Paneli | Servis & Worker Durumları |
| Metrikler | `/admin/metrics` | Ürün ve Kalite Metrikleri | G4′ Kapı İlerlemeleri |
| Denetim Kuyruğu | `/admin/review/` | Şüpheli Kümeleme & İddialar | Merge/Split/Reject Kararları |
| Beklenen Gelişmeler | `/admin/calendar/` | Resmî Takvim (TCMB, TÜİK vb.) | Doğrulanmış Tarihler |
| **Hesap Sor** | `/accountability` | Vaat-İcraat Zinciri & Sayıştay | `verified`, `supported`, `inferred` |
| **Siyasi Hafıza** | `/memory` | Aktör Kronolojisi & Beyan Ağı | Kronolojik Beyan Geçmişi |
| **Vaatler** | `/promises` | Siyasi Taahhütler & Yasama | `fulfils`, `fails`, `pending` |
| **Arşiv** | `/archive` | Tarihsel Olay ve Kanıt Deposu | Dizin & Tarih Filtreleri |

---

## 3. Doğrulama Döngüsü
Tüm 11 ekran, `scripts/ui_check.py --shots` ile 4 farklı viewport'ta (`mobil: 375px`, `tablet: 768px`, `masaustu: 1440px`, `genis: 1920px`) denetlenir ve ekran görüntüleri `design/shots/` altında saklanır.
