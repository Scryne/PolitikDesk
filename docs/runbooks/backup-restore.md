# Operational Runbook: Backup & Restore Operations (`backup-restore.md`)

## 1. Amacı ve İlkeleri
- Bu runbook, PolitikDesk veritabanının güvenli yedeklenmesi, SHA-256 bütünlük doğrulaması, saklama (retention) politikası ve geri yükleme adımlarını tanımlar.
- **Kural 1 (B-84):** Yedekler bulut eşitleme dizinlerinin (OneDrive, Dropbox vb.) DIŞINDA tutulur (`%LOCALAPPDATA%\PolitikDesk\backups`).
- **Kural 2:** Geri yükleme denemeleri asla doğrudan canlı üretim veritabanının üzerine yapılmaz; izole hedef veritabanları kullanılır.

---

## 2. Standart Operasyonel Komutlar

### 2.1 Manuel Yedek Alma:
```powershell
python -m scripts.backup create --label manuel
```
*Bu komut `.dump` dosyasıyla birlikte bir `.dump.meta.json` manifest dosyası üretir.*

### 2.2 Mevcut Yedekleri ve Manifest Durumlarını Listeleme:
```powershell
python -m scripts.backup list
```

### 2.3 Yedek Dosyası Bütünlük ve Checksum Doğrulama:
```powershell
python -m scripts.backup verify <dosya_yolu>
```

### 2.4 Otomatik Felaket Kurtarma Tatbikatı (DR Drill):
```powershell
python -m scripts.backup drill
```
*İzole geçici bir veritabanı açar, geri yükler, pgvector/FK/şema kontrolü yapar, smoke test çalıştırır ve geçici veritabanını temizler.*

### 2.5 Eski Yedekleri Silme (Retention Prune):
```powershell
python -m scripts.backup prune --keep 14
```

---

## 3. Geri Yükleme (Restore) Prosedürü

### Adım 1 — Yedeği Doğrulayın:
```powershell
python -m scripts.backup verify C:\Users\<kullanici>\AppData\Local\PolitikDesk\backups\politikdesk-<tarih>.dump
```

### Adım 2 — Test Ortamına Yükleyin ve İnceleyin:
```powershell
python -m scripts.backup restore <dosya_yolu> --into politikdesk_restore_test
```
*Script satır sayılarını, pgvector fonksiyonelliğini ve yabancı anahtar bütünlüğünü otomatik doğrular.*

### Adım 3 — Üretim Veritabanına Geri Yükleme (Felaket Durumunda):
```powershell
# 1. Servisleri durdurun
docker compose stop api worker worker-llm beat

# 2. Üretim üzerine zorla yazın
python -m scripts.backup restore <dosya_yolu> --into politikdesk --force

# 3. Servisleri başlatın
docker compose up -d
```

---

## 4. Zamanlanmış Otomasyon (Windows Scheduled Tasks)

Windows üzerinde günlük yedekleme ve nöbetçi görevlerini kurmak veya kontrol etmek için:

```powershell
# Durum Kontrolü:
powershell -ExecutionPolicy Bypass -File scripts\windows_schedule.ps1 -Status

# Yeniden Kurulum:
powershell -ExecutionPolicy Bypass -File scripts\windows_schedule.ps1 -Install
```

---

## 5. Sorun Giderme (Troubleshooting)
- **Hata: `BackupLocationError`:** Verilen yedek dizini OneDrive/Dropbox altında. `PD_BACKUP_DIR` ortam değişkenini bulut dışı yerel bir dizine ayarlayın.
- **Hata: `pg_restore: error: input file appears to be corrupted`:** Dump dosyası hasarlı veya aktarım sırasında kesintiye uğramış. Önceki tarihli yedeğe geçin.
- **Hata: `SHA-256 uyuşmazlığı`:** Dosya içeriği manifest oluşturulduktan sonra değiştirilmiş veya bozulmuş.
