"""Söylem değişikliklerinin kalıcılaştırılması (Roadmap Faz 4.1).

**Neden bu modül var — ölçülmüş bir maliyet.**

`service.list_all_stance_shifts()` her istekte 20 aktörün hafızasını
yeniden okuyup O(n²) tarama yapıyordu. 18 Ağustos denetiminde ölçülen
süre **5,2 saniyeydi**; kutup çıkarımını kayıt başına ön hesaba almak onu
0,66 saniyeye indirdi ama sorunun kökünü çözmedi: hesap hâlâ HER İSTEKTE
yeniden yapılıyor ve sonucu hiçbir yere yazılmıyordu.

Sonuç, roadmap 4.1'in saydığı üç kazanımın üçünün de olmamasıydı:

    tarihsel analiz   yok — dün hangi kaymalar vardı, bilinmiyor
    denetim izi       yok — bir kayma neden üretildi, sonradan bakılamıyor
    graf sorgusu      yok — "bu olaydan çıkan kaymalar" sorulamıyor

-----------------------------------------------------------------------
NEDEN `event_relations` DEĞİL
-----------------------------------------------------------------------

O tablonun anahtarı `(from_event_id, to_event_id, relation)`. Söylem
değişikliği ise **aktör** ve **konu** boyutu taşır; aynı olay çiftinde
iki farklı aktörün kayması o anahtar altında tek satıra iner.

Canlı ölçüm (19 Ağu 2026): 37 kaymanın **2'si kaybolurdu**. Örnek —
olay 7700 → 8041 arasında hem Devlet Bahçeli hem Resmî Gazete kaydı var.

Bu, Faz 1.2'de 150 TÜİK takvim kaydını sessizce tek satıra indiren
hatanın birebir aynısı; orada bedeli ödendi, burada önceden görüldü.

⛔ Bu modül `politikdesk.llm` import ETMEZ. Bir kaymanın var olup
olmadığına yapay zekâ karar veremez — tespit deterministiktir
(`stance_shift.detect_stance_shifts_from_memory`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Final

from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)

# Tespit mantığı değiştiğinde artırılır. Eski sürümle üretilmiş kayıtlar
# `superseded` yapılır; silinmez.
ENGINE_VERSION: Final[str] = "stance.v1"

# Tek turda kaç aktör taranacak. Tarama O(n²) olduğu için sınırsız
# bırakmak arka plan görevini saatlerce koşturabilir.
DEFAULT_ACTOR_LIMIT: Final[int] = 40

# ---------------------------------------------------------------------------
# ⛔ YAYIN KAPISI — KAPALI (19 Ağustos 2026, ADR-010)
# ---------------------------------------------------------------------------
# Dedektör çalışıyor ve kayıt üretiyor; ürettiği kayıtlar GÜVENİLİR DEĞİL.
# 50 kaydın tamamı denetlendiğinde konu eşleştirmesinin hiç olmadığı,
# güven skorunun sabit 0,85 olduğu ve aktör alanına "Adayı" gibi sözcük
# parçalarının sızdığı görüldü. Somut örnek: Cumhurbaşkanlığı'na, 42
# dakika arayla atılmış ve hiçbiri onun beyanı olmayan iki ilgisiz tweete
# dayanarak "U dönüşü" atfediliyordu.
#
# Gerçek kişi ve kurumlara yönelik yanlış siyasi isnat, bu ürünün
# verebileceği en pahalı çıktıdır. Kayıtlar SİLİNMEZ (dedektör
# düzeltildiğinde aynı veriyle yeniden ölçüm yapılabilsin diye), fakat
# okuma yolundan geçmez.
#
# Bu kapının açılma şartları ADR-010 §5'te yazılıdır. Kapıyı açmak için
# bu sabiti `True` yapmak YETMEZ; şartlar ölçülmeden değiştirilmemelidir.
PUBLISH_GATE_OPEN: Final[bool] = False

# Yayına uygun sayılan durum. Kapı açılana dek dedektör buraya yazmaz.
PUBLISHED_STATUS: Final[str] = "open"
WITHHELD_STATUS: Final[str] = "withheld"


def signature(
    actor: str, earlier_id: int, later_id: int, shift_type: str, topic: str
) -> str:
    """Kaymanın deterministik kimliği — BEŞ boyut birden.

    ⛔ Olay çifti tek başına YETMEZ. Aynı çiftte iki farklı aktörün
    kayması olabilir ve canlı veride oluyor da (ölçüldü: 37 kaydın
    2'si). Aktör ve konu kimliğin parçasıdır, özniteliği değil.
    """
    ham = f"{actor}|{earlier_id}|{later_id}|{shift_type}|{topic}"
    return hashlib.sha1(ham.encode("utf-8")).hexdigest()[:24]  # noqa: S324 — kriptografik değil


@dataclass
class SyncStats:
    actors: int = 0
    detected: int = 0
    inserted: int = 0
    unchanged: int = 0
    superseded: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "actors": self.actors,
            "detected": self.detected,
            "inserted": self.inserted,
            "unchanged": self.unchanged,
            "superseded": self.superseded,
            "errors": self.errors,
        }


def _persist(cur: Any, shift: dict[str, Any]) -> bool:
    """Tek bir kaymayı yazar. Yeni kayıt açıldıysa True döner."""
    imza = signature(
        str(shift["actor_name"]),
        int(shift["earlier_event_id"]),
        int(shift["later_event_id"]),
        str(shift["shift_type"]),
        str(shift["topic_or_metric"]),
    )
    # Kapı kapalıyken kayıt YAZILIR ama YAYINLANMAZ. Yazmayı büsbütün
    # durdurmak, dedektör düzeltildiğinde karşılaştırılacak veriyi de yok
    # ederdi; "ölçme" ile "yayınlama" ayrı kararlardır.
    durum = PUBLISHED_STATUS if PUBLISH_GATE_OPEN else WITHHELD_STATUS
    cur.execute(
        """
        INSERT INTO stance_shifts (
            actor_name, shift_type, topic_or_metric,
            earlier_event_id, later_event_id,
            earlier_event_title, earlier_claim_text, earlier_date,
            later_event_title, later_claim_text, later_date,
            time_span_days, confidence, evidence_summary, metadata,
            signature, engine_version, status
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
        ON CONFLICT (signature) WHERE status <> 'superseded' DO NOTHING
        RETURNING id
        """,
        (
            shift["actor_name"], shift["shift_type"], shift["topic_or_metric"],
            shift["earlier_event_id"], shift["later_event_id"],
            shift.get("earlier_event_title", ""), shift.get("earlier_claim_text", ""),
            shift.get("earlier_date", ""),
            shift.get("later_event_title", ""), shift.get("later_claim_text", ""),
            shift.get("later_date", ""),
            int(shift.get("time_span_days") or 0),
            float(shift.get("confidence") or 0),
            shift.get("evidence_summary", ""),
            __import__("json").dumps(shift.get("metadata") or {}, ensure_ascii=False),
            imza, ENGINE_VERSION, durum,
        ),
    )
    return cur.fetchone() is not None


def sync(*, actor_limit: int = DEFAULT_ACTOR_LIMIT) -> SyncStats:
    """Aktörleri tarar, kaymaları tespit eder ve idempotent yazar.

    ⛔ Artık üretilmeyen kayıtlar SİLİNMEZ, `superseded` yapılır. Bir
    kayma dünkü veriyle doğruydu; veri değiştiği için geçmişi yok
    saymak denetlenebilirliği ortadan kaldırır.
    """
    from politikdesk.political_memory import service as ms
    from politikdesk.political_memory.stance_shift import detect_stance_shifts_from_memory

    stats = SyncStats()
    gorulen: set[str] = set()

    try:
        aktorler = ms.search_actors(query="", limit=actor_limit).get("actors", [])
    except Exception as exc:  # noqa: BLE001
        log.error("stance_sync_actor_list_failed", error=type(exc).__name__)
        stats.errors += 1
        return stats

    with connection() as conn, conn.cursor() as cur:
        for kayit in aktorler:
            ad = kayit.get("name")
            if not ad:
                continue
            stats.actors += 1
            try:
                hafiza = ms.get_actor_memory(ad)
                kaymalar = detect_stance_shifts_from_memory(hafiza)
            except Exception as exc:  # noqa: BLE001 — bir aktör diğerlerini düşürmez
                log.warning(
                    "stance_sync_actor_failed",
                    actor=ad[:60],
                    error=type(exc).__name__,
                    detail=str(exc)[:160],
                )
                stats.errors += 1
                continue

            for kayma in (k.to_dict() for k in kaymalar):
                stats.detected += 1
                gorulen.add(
                    signature(
                        str(kayma["actor_name"]),
                        int(kayma["earlier_event_id"]),
                        int(kayma["later_event_id"]),
                        str(kayma["shift_type"]),
                        str(kayma["topic_or_metric"]),
                    )
                )
                if _persist(cur, kayma):
                    stats.inserted += 1
                else:
                    stats.unchanged += 1

        # Bu turda ARTIK üretilmeyen açık kayıtlar kapatılır.
        # Yalnızca taranan aktörlerin kayıtlarına dokunulur: tarama
        # sınırı dışında kalan bir aktörün kayıtları "üretilmedi" diye
        # kapatılsaydı, sınırı değiştirmek geçmişi bozardı.
        taranan = [k["name"] for k in aktorler if k.get("name")]
        if taranan:
            cur.execute(
                """
                UPDATE stance_shifts
                   SET status = 'superseded'
                 WHERE status = 'open'
                   AND actor_name = ANY(%s)
                   AND (signature <> ALL(%s) OR engine_version <> %s)
                """,
                (taranan, list(gorulen) or [""], ENGINE_VERSION),
            )
            stats.superseded = cur.rowcount
        conn.commit()

    log.info("stance_shift_sync_complete", **stats.as_dict())
    return stats


# ---------------------------------------------------------------------------
# Okuma yolu — istek anında HESAP YOK, yalnızca sorgu
# ---------------------------------------------------------------------------
_SELECT = """
    SELECT s.id, s.actor_name, s.shift_type, s.topic_or_metric,
           s.earlier_event_id, s.earlier_event_title, s.earlier_claim_text,
           s.earlier_date, s.later_event_id, s.later_event_title,
           s.later_claim_text, s.later_date, s.time_span_days,
           s.confidence, s.evidence_summary, s.metadata,
           s.detected_at, s.engine_version
      FROM stance_shifts s
     WHERE s.status = 'open' {extra}
     ORDER BY s.detected_at DESC, s.later_date DESC
     LIMIT %s
"""


def list_all(*, limit: int = 50, shift_type: str | None = None) -> list[dict[str, Any]]:
    """Tüm aktörlerin kaymaları — tek sorgu, hesap yok.

    Yayın kapısı kapalıyken **boş liste** döner (ADR-010).
    """
    if not PUBLISH_GATE_OPEN:
        return []
    ek = "AND s.shift_type = %s" if shift_type else ""
    params: list[Any] = [shift_type, limit] if shift_type else [limit]
    with connection() as conn, conn.cursor() as cur:
        cur.execute(_SELECT.format(extra=ek), params)  # noqa: S608 — `ek` sabit
        return [dict(r) for r in cur.fetchall()]


def for_actor(actor_name: str, *, limit: int = 50) -> list[dict[str, Any]]:
    """Bir aktörün kaymaları. Kapı kapalıyken boş (ADR-010)."""
    if not PUBLISH_GATE_OPEN:
        return []
    with connection() as conn, conn.cursor() as cur:
        cur.execute(_SELECT.format(extra="AND s.actor_name = %s"), (actor_name, limit))
        return [dict(r) for r in cur.fetchall()]


def for_event(event_id: int, *, limit: int = 50) -> list[dict[str, Any]]:
    """Bir olaya bağlı kaymalar — GRAF SORGUSU (her iki yön).

    Kalıcılaştırmanın açtığı kapı bu: "bu olay hangi söylem
    değişikliklerinin parçası?" sorusu, hesap yapmadan yanıtlanır.

    Yayın kapısı kapalıyken **boş liste** döner (ADR-010).
    """
    if not PUBLISH_GATE_OPEN:
        return []
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            _SELECT.format(extra="AND (s.earlier_event_id = %s OR s.later_event_id = %s)"),
            (event_id, event_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def summary() -> dict[str, Any]:
    """Tür ve aktör dağılımı — panolar için.

    ⛔ `withheld` sayısı AYRI raporlanır ve gizlenmez.

    Yayın kapısı kapatıldığında bu özet sessizce sıfır dönseydi, sistem
    "hiç kayma bulunmadı" ile "bulunanlar güvenilmez olduğu için
    yayınlanmadı" arasındaki farkı silerdi. Bu projede tekrar tekrar
    ödenen bedel tam olarak budur: *ölçülemedi ≠ sıfır*.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT shift_type, count(*) AS n FROM stance_shifts "
            "WHERE status = 'open' GROUP BY shift_type"
        )
        turler = {str(r["shift_type"]): int(r["n"]) for r in cur.fetchall()}

        cur.execute(
            "SELECT count(DISTINCT actor_name) AS n FROM stance_shifts WHERE status = 'open'"
        )
        aktor_satiri = cur.fetchone()

        cur.execute("SELECT count(*) AS n FROM stance_shifts WHERE status = 'superseded'")
        eski_satiri = cur.fetchone()

        cur.execute("SELECT count(*) AS n FROM stance_shifts WHERE status = 'withheld'")
        cekilen_satiri = cur.fetchone()

    return {
        "by_type": turler,
        "total": sum(turler.values()),
        "actors": int(aktor_satiri["n"]) if aktor_satiri else 0,
        "superseded": int(eski_satiri["n"]) if eski_satiri else 0,
        # Tespit edildi ama güvenilmez olduğu için yayınlanmadı.
        "withheld": int(cekilen_satiri["n"]) if cekilen_satiri else 0,
        "publish_gate_open": PUBLISH_GATE_OPEN,
    }
