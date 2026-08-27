# Operational Runbook: Database Corruption & Disaster Recovery (`database-recovery.md`)

## 1. Symptom (Belirti)
- PostgreSQL veritabanı açılamıyor, veri bozulması (corruption) var veya kritik bir tablo/veri kazara silindi (`DELETE FROM articles` vb.).
- `pd-api` ve `pd-worker` loglarında `psycopg.OperationalError: could not connect to server` veya `FATAL: data directory is corrupted` hataları var.
- `/health/ready` uç noktası HTTP 503 ve `{"postgres": false}` dönüyor.

---

## 2. Detection (Tespit)
- **Sağlık Kontrolü:** `GET /health/ready` ➔ HTTP 503
- **Docker Konteyner Durumu:**
  ```powershell
  docker compose ps pd-db
  ```
- **Postgres Logları:**
  ```powershell
  docker compose logs --tail 100 pd-db
  ```

---

## 3. Diagnosis (Teşhis)
1. **Postgres Konteyneri Ayakta mı?**
   ```powershell
   docker exec -it pd-db pg_isready -U politikdesk -d politikdesk
   ```
2. **Tablo ve Şema Bütünlüğü:**
   ```powershell
   python -c "from politikdesk.db import ping; print('DB Ping:', ping())"
   ```
3. **Mevcut Yedekleri Listeleyin:**
   ```powershell
   python -m scripts.backup list
   ```

---

## 4. Immediate Mitigation (Acil Güvenli Duruma Alma)
1. **Yazma Akışını Durdurun (İşçileri ve Beat'i Kapatın):**
   ```powershell
   docker compose stop worker worker-llm beat api
   ```
2. **En Güncel Sağlıklı Yedeği Seçin ve Bütünlüğünü Doğrulayın:**
   ```powershell
   python -m scripts.backup verify <yedek_dosya_yolu>
   ```

---

## 5. Recovery (Kurtarma Adımları)

### Senaryo A — Tablo veya Veri Kaybı / Bozulması (Canlı DB Ayakta Ama Veri Bozuk):
1. **Yedeği Önce Geçici Bir Veritabanında Doğrulayın:**
   ```powershell
   python -m scripts.backup restore <yedek_dosya_yolu> --into politikdesk_recovery_test
   ```
2. **Doğrulama Başarılıysa Üretim Veritabanını Yeniden Oluşturun:**
   ```powershell
   python -m scripts.backup restore <yedek_dosya_yolu> --into politikdesk --force
   ```
3. **Migration Durumunu Doğrulayın:**
   ```powershell
   python -m scripts.migrate status
   ```

### Senaryo B — PostgreSQL Veri Dizini Tamamen Bozuldu / Docker Volume Kaybı:
1. **Postgres Konteynerini ve Bozuk Volume'ü Temizleyin:**
   ```powershell
   docker compose down -v
   docker compose up -d db redis
   ```
2. **Veritabanının Hazır Olmasını Bekleyin:**
   ```powershell
   docker exec -it pd-db pg_isready -U politikdesk -d politikdesk
   ```
3. **En Güncel Yedeği Yükleyin:**
   ```powershell
   python -m scripts.backup restore <yedek_dosya_yolu> --into politikdesk --force
   ```
4. **Gerekiyorsa Kalan Migration'ları Çalıştırın:**
   ```powershell
   python -m scripts.migrate up
   ```

---

## 6. Verification (Doğrulama)
1. **Şema ve İlişkisel Bütünlük Kontrolü:**
   ```powershell
   python -m scripts.backup drill
   ```
2. **Tüm Servisleri Ayağa Kaldırın:**
   ```powershell
   docker compose up -d
   ```
3. **Uçtan Uca Sağlık Kontrolü:**
   ```powershell
   python -m scripts.check_deployment
   python -m scripts.watchdog
   ```

---

## 7. Postmortem Checklist (Olay Sonrası Kontrol Listesi)
- [ ] Veri kaybı penceresi (RPO - Recovery Point Objective) kaç dakikaydı?
- [ ] Geri yükleme süresi (RTO - Recovery Time Objective) kaç dakikada tamamlandı?
- [ ] `audit_log` üzerinde `backup_restored` kaydı doğrulandı mı?
- [ ] Yeni bir temel yedek oluşturuldu mu (`python -m scripts.backup create --label post-recovery`)?
