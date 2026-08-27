# PolitikDesk — Otomatik Tweet Üretimi ve Telegram Entegrasyon Kılavuzu

Bu kılavuz, PolitikDesk'e düşen her doğrulanmış haber için **arka planda otomatik olarak X (Twitter) tweeti hazırlanmasını** ve anında **Telegram hesabınıza tek tıkla paylaşım butonlarıyla iletilmesini** nasıl kullanacağınızı açıklar.

---

## 1. 30 Saniyede Telegram Botu Kurulumu

Telegram bildirimlerini almak için yalnızca bir Telegram Bot Token'ı ve Chat ID'niz gerekir:

### Adım 1: Bot Token Alma
1. Telegram uygulamanızda arama kutusuna **`@BotFather`** yazın ve resmi bota girin.
2. **/newbot** komutunu gönderin.
3. Botunuz için bir isim (örn. `PolitikDesk Haber`) ve kullanıcı adı (örn. `benim_politikdesk_bot`) belirleyin.
4. BotFather size `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ` şeklinde bir **HTTP API Token** verecektir.

### Adım 2: Chat ID Öğrenme
1. Telegram'da **`@userinfobot`** veya **`@raw_data_bot`** botuna gidin ve `/start` deyin.
2. Bot size sayısal **Id** değerinizi (örn. `1234567890`) yazacaktır.

### Adım 3: Kendi Botunuzu Başlatma (Çok Önemli!)
* 1. Adımda oluşturduğunuz kendi botunuza Telegram'dan gidin ve **/start** butonuna basın (Telegram kuralı gereği kullanıcı bota mesaj atmadan bot kullanıcıya mesaj gönderemez).

---

## 2. PolitikDesk `.env` Dosyasına Ekleme

Projenin ana dizinindeki `.env` dosyanızı açın ve aldığınız bilgileri yazın:

```env
# --- Otomatik Tweet Üretimi (Auto-Draft) & Telegram Bildirimleri ---
PD_AUTO_DRAFT_ENABLED=true
PD_AUTO_DRAFT_MIN_SALIENCE=30
PD_AUTO_DRAFT_ANGLE=inform
PD_AUTO_DRAFT_MAX_EVENTS_PER_CYCLE=5

PD_TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
PD_TELEGRAM_CHAT_ID=1234567890
PD_TELEGRAM_NOTIFY_DRAFTS=true
```

---

## 3. Bağlantıyı Test Etme

Kurulumun doğru çalıştığını test etmek için terminalde şu komutu çalıştırın:

```powershell
pd telegram-test
```
*(veya Linux/macOS için `make telegram-test`)*

Telegram uygulamanıza anında örnek bir haber ve hazır tweet içeren test mesajı gelecektir!

---

## 4. Sistem Nasıl Çalışır?

1. **Otomatik Toplama ve Doğrulama:**
   PolitikDesk 101 farklı resmi kaynaktan (TCMB, Resmî Gazete, TÜİK, Meclis, haber ajansları vb.) haberleri toplar ve çapraz teyit eder.
2. **Otomatik Tweet Üretimi:**
   Bir olay teyit zincirinden başarıyla geçtiğinde (`score_evidence`), Celery LLM worker'ı arkaplanda editoryal kimlik profilinize uygun Türkçe tweeti hazırlar ve halüsinasyon/grounding kontrolünden geçirir.
3. **Telegram Anlık Bildirimi:**
   Tweet hazır olduğu an Telegram'ınıza şu formatta düşer:

```text
🚨 YENİ DOĞRULANMIŞ GELİŞME | Ekonomi

📌 TCMB Politika Faizini %50 Seviyesinde Sabit Bıraktı
⭐ Gündem Skoru: 88/90 · Durum: 🟢 Doğrulandı (3/3 teyitli iddia)

✍️ Hazır X (Twitter) Tweeti:
TCMB Para Politikası Kurulu, politika faizini beklentiler doğrultusunda %50 seviyesinde sabit tuttu. Kurul, enflasyonda belirgin düşüş sağlanana kadar sıkı para politikası duruşunun korunacağını vurguladı. #Ekonomi #TCMB

[ 🚀 X'te Aç ve Paylaş ]   [ 📊 Olayı İncele ]
```

4. **Tek Tıkla Paylaşım:**
   Mesajın altındaki **`[ 🚀 X'te Aç ve Paylaş ]`** butonuna bastığınızda, telefonunuzda veya tarayıcınızda doğrudan X uygulaması açılır, tweet metni hazır yazılmış kutuda bekler; sadece **Gönder** tuşuna basmanız yeterlidir.

---

## 5. İsteğe Bağlı Komutlar

* **Elle Otomatik Üretimi Tetikleme:**
  ```powershell
  pd auto-draft
  ```
* **Konteynerleri Yeniden Başlatma:**
  ```powershell
  pd restart
  ```
