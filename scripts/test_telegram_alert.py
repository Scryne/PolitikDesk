"""PolitikDesk Telegram Bot Bildirim Test Betiği.

Kullanım:
    python scripts/test_telegram_alert.py
    python scripts/test_telegram_alert.py --token <BOT_TOKEN> --chat-id <CHAT_ID>
"""

from __future__ import annotations

import argparse
import sys

from politikdesk.config import get_settings
from politikdesk.telegram_notifier import send_telegram_test_message


def main() -> int:
    parser = argparse.ArgumentParser(description="PolitikDesk Telegram Bildirim Testi")
    parser.add_argument("--token", default=None, help="Telegram Bot Token")
    parser.add_argument("--chat-id", default=None, help="Telegram Chat ID")
    args = parser.parse_args()

    settings = get_settings()
    token = args.token or settings.telegram_bot_token
    chat_id = args.chat_id or settings.telegram_chat_id

    print("=" * 65)
    print("POLİTİKDESK - TELEGRAM BOT VE ANLIK BİLDİRİM TESTİ")
    print("=" * 65)

    if not token or not chat_id:
        print("\n[UYARI] Telegram yapılandırması henüz tamamlanmamış!")
        print("Mevcut Durum:")
        print(f"  * PD_TELEGRAM_BOT_TOKEN : {'[DOLU]' if token else '[BOŞ]'}")
        print(f"  * PD_TELEGRAM_CHAT_ID   : {'[DOLU]' if chat_id else '[BOŞ]'}")
        print("\nNasıl Kurulur? (30 Saniye):")
        print("  1. Telegram'da @BotFather botuna gidin ve /newbot komutu verin.")
        print("  2. Size verilen API Token'ı .env dosyasına PD_TELEGRAM_BOT_TOKEN=... olarak yazın.")
        print("  3. Telegram'da @userinfobot veya @raw_data_bot botuna mesaj atarak Chat ID'nizi öğrenin.")
        print("  4. Chat ID'nizi .env dosyasına PD_TELEGRAM_CHAT_ID=... olarak ekleyin.")
        print("  5. Oluşturduğunuz bota Telegram'dan en az bir kez /start mesajı atın.")
        print("\nDetaylı rehber için: docs/TELEGRAM_VE_OTOMATIK_TWEET_KILAVUZU.md")
        return 1

    print(f"Hedef Chat ID: {chat_id}")
    print(f"Bot Token    : {token[:6]}...{token[-4:] if len(token) > 10 else ''}")
    print("Test mesajı gönderiliyor...")

    result = send_telegram_test_message(bot_token=token, chat_id=chat_id)
    if result.get("success"):
        print(f"\n[BAŞARILI] Test mesajı Telegram hesabınıza iletildi! (Mesaj ID: {result.get('message_id')})")
        print("Telegram uygulamanızı kontrol edin. Mesaj altındaki [ 🚀 X'te Aç ve Paylaş ] butonunu deneyebilirsiniz.")
        return 0
    else:
        print(f"\n[HATA] Mesaj iletilemedi: {result.get('error')}")
        if result.get("status_code") == 400:
            print("İpucu: Botunuza Telegram'da henüz /start dememiş olabilirsiniz veya Chat ID hatalı olabilir.")
        elif result.get("status_code") == 401 or result.get("status_code") == 404:
            print("İpucu: Bot Token hatalı veya geçersiz.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
