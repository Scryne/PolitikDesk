"""Denetim izi — tek giriş noktası (F4-16).

Spec §12 ve Yol Haritası F4-16: kaynak değişikliği, merge/split, taslak
üretimi, purge ve bütçe alarmı denetim izine düşmelidir.

Neden merkezî bir yardımcı: `audit_log`'a yazan on bir ayrı çağrı yeri
vardı ve her biri kendi INSERT'ünü kuruyordu. Bu, iki şeyi imkânsız
kılıyordu — hangi eylemlerin kayıtlı olduğunu *listelemek* ve bir
eylemin kaydını unutmayı *yakalamak*. `ACTIONS` sözlüğü artık
sözleşmedir; `tests/test_audit.py` sözleşmeyi denetler.

Bu modül veritabanına yazar ama iş mantığı içermez: neyin denetlenmeye
değer olduğu çağıranın kararıdır, biçimi buranın.
"""

from __future__ import annotations

import json
from typing import Any

from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)

SYSTEM_ACTOR = "system"
USER_ACTOR = "user"

# Denetlenen eylemler ve bir cümlelik anlamları. Yeni bir eylem eklemek,
# buraya bir satır eklemeyi gerektirir — `write()` bilinmeyen eylemi
# reddeder, böylece serbest metin `action` değerleri sızmaz ve izin
# kapsamı belgelenmiş kalır.
ACTIONS: dict[str, str] = {
    # --- kaynak yönetimi ---
    "source_updated": "Kaynak alanları değiştirildi",
    "sources_synced": "config/sources.yml veritabanına uygulandı",
    # --- olay yaşam döngüsü ---
    "merge_events": "İki olay birleştirildi",
    "undo_merge": "Birleştirme geri alındı",
    "split_event": "Olay bölündü",
    "undo_split": "Bölme geri alındı",
    "resolve_review": "İnceleme bayrağı bir kararla kapatıldı",
    "flag_needs_review": "Olay incelemeye işaretlendi",
    "event_flagged_by_user": "Kullanıcı olayı işaretledi",
    "link_same_thread": "Olaylar arasında same_thread bağı kuruldu",
    "reset_derived_state": "Türetilmiş durum sıfırlandı (yeniden embed/kümeleme)",
    # --- iddia ve kanıt ---
    "claims_reextracted": "İddialar güncel prompt sürümüyle yeniden çıkarıldı",
    "political_relations_evaluated": "Siyasi olay ilişkileri deterministik motorla değerlendirildi",
    "context_evaluated": "Tarihsel bağlam ilişkileri değerlendirildi",
    # --- editoryal ---
    "editorial_profile_updated": "Editoryal Kimlik Kartı güncellendi",
    "draft_generated": "Taslak üretildi (LLM çağrısı yapıldı)",
    "draft_action": "Taslak üzerinde kullanıcı eylemi (kabul/düzenle/reddet)",
    # --- saklama ve operasyon ---
    "purge_lead_paragraph": "Süresi dolmuş lead_paragraph alanları silindi",
    "llm_budget_alert": "LLM bütçe eşiği aşıldı veya tavana ulaşıldı",
    "backup_created": "Veritabanı yedeği alındı",
    "backup_restored": "Veritabanı yedekten geri yüklendi",
}


class UnknownAuditAction(ValueError):
    """`ACTIONS` içinde tanımlı olmayan bir eylem yazılmaya çalışıldı."""


def write(
    action: str,
    target: str,
    *,
    actor: str = SYSTEM_ACTOR,
    payload: dict[str, Any] | None = None,
    cursor: Any = None,
) -> None:
    """Denetim izine bir satır yazar.

    `cursor` verilirse o imleç kullanılır ve **commit edilmez** — çağıran
    zaten bir işlem (transaction) içindedir ve denetim kaydı o işlemin
    parçası olmalıdır. Merge/split gibi geri alınabilir işlemlerde bu
    şarttır: işlem geri sarılırsa denetim kaydı da geri sarılmalıdır,
    yoksa iz gerçekleşmemiş bir olayı anlatır.
    """
    if action not in ACTIONS:
        raise UnknownAuditAction(
            f"Bilinmeyen denetim eylemi: {action!r}. politikdesk/audit.py::ACTIONS içine ekleyin."
        )

    params = (actor, action, target, json.dumps(payload or {}, ensure_ascii=False))
    sql = "INSERT INTO audit_log (actor, action, target, payload) VALUES (%s,%s,%s,%s::jsonb)"

    if cursor is not None:
        cursor.execute(sql, params)
        return

    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        conn.commit()


def recent(limit: int = 50, action: str | None = None) -> list[dict[str, Any]]:
    """Son denetim kayıtları (admin panosu için)."""
    sql = "SELECT id, actor, action, target, payload, created_at FROM audit_log"
    params: tuple[Any, ...] = ()
    if action is not None:
        sql += " WHERE action = %s"
        params = (action,)
    sql += " ORDER BY created_at DESC LIMIT %s"
    params = (*params, limit)

    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def exists_since(action: str, target: str, *, hours: float) -> bool:
    """Bu eylem bu hedef için son N saatte kaydedilmiş mi?

    Alarm tekrarını bastırmak için: aynı bütçe uyarısını her kontrolde
    yeniden göndermek, uyarıyı gürültüye çevirir ve gürültü kapatılır.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM audit_log
            WHERE action = %s AND target = %s
              AND created_at > now() - make_interval(secs => %s)
            LIMIT 1
            """,
            (action, target, hours * 3600),
        )
        return cur.fetchone() is not None
