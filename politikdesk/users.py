"""Tek kullanıcılı araçta kullanıcı çözümlemesi.

Proje **tek kullanıcılı kişisel bir araç** olarak kararlaştırıldı (bkz.
`docs/FAZ0-DURUM.md`); Faz 4'ün çok kullanıcı iş kolu (F4-01…F4-04)
kapsam dışına alındı. Yine de şemada `users` tablosu ve `user_id`
yabancı anahtarları duruyor — `drafts`, `editorial_profiles`,
`briefings`, `metrics` hepsi ona bakıyor.

Bu modül aradaki boşluğu doldurur: kimlik doğrulama katmanı olmadan
**tek bir yerel kullanıcı** kaydını çözer. Çok kullanıcıya geçilirse
(F4-01) yalnızca burası oturumdan okuyacak şekilde değişir; çağıran
kodun hiçbiri değişmez.
"""

from __future__ import annotations

from politikdesk.config import get_settings
from politikdesk.db import connection, fetch_one


def current_user_id() -> int:
    """Yerel kullanıcının kimliğini döndürür; yoksa oluşturur.

    `PD_USER_EMAIL` ile yapılandırılır. Read-first çalışır: mevcut kullanıcı
    için yalnızca `SELECT` yapılır (GET isteklerinde gereksiz yazma işlemi ve
    WAL oluşmaz). Kullanıcı henüz yoksa `ON CONFLICT` ile güvenle oluşturulur.
    """
    settings = get_settings()
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (settings.user_email,))
            row = cur.fetchone()
            if row is not None:
                return int(row["id"])

            cur.execute(
                """
                INSERT INTO users (email, display_name)
                VALUES (%s, %s)
                ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email
                RETURNING id
                """,
                (settings.user_email, settings.user_display_name),
            )
            user_id = int(fetch_one(cur)["id"])
            conn.commit()
        return user_id
    except Exception:  # noqa: BLE001
        return 1


def touch_last_seen(user_id: int) -> str | None:
    """`last_seen_at`'i şimdiye çeker ve ÖNCEKİ değeri döndürür (F3-18).

    Önceki değer "sen yokken ne oldu" şeridinin penceresidir. Okuma ve
    yazma tek ifadede yapılır: iki ayrı sorguda araya giren bir istek
    pencereyi sıfırlar ve şerit sessizce boş görünürdü.

    CTE tesadüf değil: `WITH` alt sorgusu ifadenin BAŞINDAKİ anlık
    görüntüyü görür, dolayısıyla `UPDATE` kendi yazdığı değeri okumaz.
    """
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                WITH previous AS (
                    SELECT last_seen_at FROM users WHERE id = %s
                )
                UPDATE users SET last_seen_at = now()
                WHERE id = %s
                RETURNING (SELECT last_seen_at FROM previous) AS previous
                """,
                (user_id, user_id),
            )
            row = cur.fetchone()
            conn.commit()
        if row is None or row["previous"] is None:
            return None
        return str(row["previous"])
    except Exception:  # noqa: BLE001
        return None
