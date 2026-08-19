"""Beklenen yayın motoru (Roadmap Faz 3.2).

Faz 1.2'de kurulan **Ulusal Veri Yayımlama Takvimi** üzerine oturur ve
onu tekrar etmez: kurum, beklenen zaman, yayımlandı/bekliyor bilgisi
zaten `scheduled_events` tablosundadır. Bu modül o veriye tek bir şey
ekler — **zamanın geçmesi**.

-----------------------------------------------------------------------
ÜÇ FARKLI ANLAM, ÜÇ FARKLI DURUM
-----------------------------------------------------------------------

Faz 3 yetkisinin en keskin şartı bu ve karıştırılmaları ürünü yanıltır:

    delayed     Kurum HENÜZ YAYIMLAMADI. Beklenen saat geçti, takvim
                hâlâ "bekliyor" diyor. Gecikme KURUMUNDUR.

    published   Kurum YAYIMLADI ama BİZ görmedik. Boru hattımız o yayını
                hiçbir kaynaktan yakalayamadı. Eksiklik BİZDEDİR ve
                kaynak kadrosundaki kör noktayı gösterir.

    occurred    Yayımlandı VE bizim olayımızla eşleşti. Gecikme varsa
                bizim GÖRME gecikmemizdir ve ölçülebilir.

`cancelled` bunlardan ayrıdır: beklenen şey hiç gerçekleşmedi.

⛔ FAZ 1.2 DEĞİŞMEZİ KORUNUR: `published != cancelled`. Kurumun
yayımladığı ama bizim görmediğimiz bir yayın, hiç gerçekleşmemiş bir
yayınla aynı kefeye konulamaz — konulursa `missed_report`, yani kaynak
kör noktasını gösteren tek sinyal, sessizce yok olur.

-----------------------------------------------------------------------
GECİKME NEREDEN ÖLÇÜLÜR
-----------------------------------------------------------------------

**Resmî beklenen zamandan.** Tahmin edilen bir zamandan değil; takvim
kaydının `expected_at` alanından. Bir makalenin ortaya çıkmamış olması
gecikme KANITI DEĞİLDİR — yalnızca bizim görmediğimizin kanıtıdır.

⛔ Bu modül `politikdesk.llm` import ETMEZ. Bir yayının gerçekleşip
gerçekleşmediğine yapay zekâ karar veremez.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final, Literal

from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)

ExpectationState = Literal[
    "expected", "delayed", "published", "occurred", "cancelled", "unavailable"
]

# Hoşgörü penceresi: kurumlar ilan ettikleri saati dakikası dakikasına
# tutturmaz. Bu süre geçmeden "gecikti" denmez.
#
# 2 saat, `scheduler_match.MATCH_WINDOW` (±3 sa) ile uyumlu seçildi:
# eşleştirici hâlâ arıyorken "gecikti" demek, kendi kendimizle çelişmek
# olurdu.
TOLERANCE: Final[timedelta] = timedelta(hours=2)

# Bu süreden sonra hâlâ ortada yoksa beklenti düşer.
# `official_calendar` zaten 48 saatte `cancelled` yapıyor; burada aynı
# eşik kullanılır ki iki modül aynı olayı farklı adlandırmasın.
ABANDON_AFTER: Final[timedelta] = timedelta(hours=48)


@dataclass(frozen=True)
class ExpectationSignal:
    """Beklenen bir yayına dair proaktif sinyal.

    Boyutlar AYRI tutulur: kaynak kalitesi, tazelik ve bağımsızlık tek
    bir opak "güven" sayısına çarpılmaz (Faz 3 yetkisi §SOURCE
    INTELLIGENCE INTEGRATION).
    """

    scheduled_id: int
    signal_type: str
    institution: str
    title: str
    expected_at: Any
    observed_at: Any
    delay_minutes: int | None
    state: ExpectationState
    reference_period: str | None
    url: str | None
    linked_event_id: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "scheduled_id": self.scheduled_id,
            "signal_type": self.signal_type,
            "institution": self.institution,
            "title": self.title,
            "expected_at": self.expected_at,
            "observed_at": self.observed_at,
            "delay_minutes": self.delay_minutes,
            "state": self.state,
            "reference_period": self.reference_period,
            "url": self.url,
            "linked_event_id": self.linked_event_id,
        }


def mark_delayed(*, tolerance: timedelta = TOLERANCE) -> dict[str, int]:
    """Beklenen saati hoşgörü penceresini aşan `pending` kayıtları
    `delayed` yapar.

    ⛔ Yalnızca `pending` dokunulur. `published` bir kayıt "gecikmiş"
    değildir — kurum onu yayımlamıştır; eksik olan bizim görmemizdir ve
    o ayrı bir sinyaldir (`observation_gap`).

    Geri dönüş de mümkündür: takvim turu bir kaydı `published` yaparsa
    durum ilerler; `delayed` bir çıkmaz sokak değildir.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE scheduled_events
               SET status = 'delayed'
             WHERE status = 'pending'
               AND expected_at < now() - %s
               AND expected_at > now() - %s
            """,
            (tolerance, ABANDON_AFTER),
        )
        gecikti = cur.rowcount
        conn.commit()

    if gecikti:
        log.info("expected_events_marked_delayed", count=gecikti)
    return {"delayed": gecikti}


def upcoming(*, hours: int = 24, limit: int = 50) -> list[ExpectationSignal]:
    """Önümüzdeki N saatte beklenen resmî yayınlar."""
    return _query(
        "se.status IN ('pending') AND se.expected_at BETWEEN now() AND now() + %s",
        (timedelta(hours=hours), limit),
        signal_type="upcoming_release",
        limit_at_end=True,
    )


def delayed(*, limit: int = 50) -> list[ExpectationSignal]:
    """Kurum beklenen saatte yayımlamadı."""
    return _query("se.status = 'delayed'", (limit,), signal_type="release_delayed",
                  limit_at_end=True)


def observation_gaps(*, days: int = 7, limit: int = 50) -> list[ExpectationSignal]:
    """Kurum yayımladı ama BİZ görmedik.

    Ürünün en rahatsız edici sorusu ve tam da bu yüzden değerli: kaynak
    kadrosundaki kör noktayı başka hiçbir gösterge bu kadar doğrudan
    söylemez.
    """
    return _query(
        "se.status = 'published' AND se.linked_event_id IS NULL "
        "AND se.expected_at > now() - %s",
        (timedelta(days=days), limit),
        signal_type="observation_gap",
        limit_at_end=True,
    )


def observed(*, days: int = 3, limit: int = 50) -> list[ExpectationSignal]:
    """Yayımlandı ve bizim olayımızla eşleşti — gecikmesiyle birlikte."""
    return _query(
        "se.status = 'occurred' AND se.expected_at > now() - %s",
        (timedelta(days=days), limit),
        signal_type="release_observed",
        limit_at_end=True,
    )


_SELECT = """
    SELECT se.id, se.title, se.institution, se.expected_at, se.status,
           se.reference_period, se.url, se.linked_event_id,
           e.first_reported_at AS observed_at
      FROM scheduled_events se
      LEFT JOIN events e ON e.id = se.linked_event_id
     WHERE {where}
     ORDER BY se.expected_at DESC
     LIMIT %s
"""

_STATE_MAP: Final[dict[str, ExpectationState]] = {
    "pending": "expected",
    "delayed": "delayed",
    "published": "published",
    "occurred": "occurred",
    "cancelled": "cancelled",
}


def _query(
    where: str, params: tuple[Any, ...], *, signal_type: str, limit_at_end: bool
) -> list[ExpectationSignal]:
    del limit_at_end  # imza okunabilirliği için; parametre sırası çağırandadır
    with connection() as conn, conn.cursor() as cur:
        cur.execute(_SELECT.format(where=where), params)  # noqa: S608 — `where` sabit
        satirlar = [dict(r) for r in cur.fetchall()]

    return [
        ExpectationSignal(
            scheduled_id=int(r["id"]),
            signal_type=signal_type,
            institution=str(r["institution"] or ""),
            title=str(r["title"]),
            expected_at=r["expected_at"],
            observed_at=r["observed_at"],
            delay_minutes=_delay_minutes(r["expected_at"], r["observed_at"]),
            state=_STATE_MAP.get(str(r["status"]), "unavailable"),
            reference_period=r["reference_period"],
            url=r["url"],
            linked_event_id=r["linked_event_id"],
        )
        for r in satirlar
    ]


def _delay_minutes(expected: Any, observed: Any) -> int | None:
    """Gecikme RESMÎ beklenen zamandan ölçülür.

    Gözlem yoksa gecikme **None**'dır, sıfır değil: "ne kadar geciktiği
    bilinmiyor" ile "hiç gecikmedi" aynı şey değildir.
    """
    if expected is None or observed is None:
        return None
    return int((observed - expected).total_seconds() // 60)


def summary(*, days: int = 7) -> dict[str, int]:
    """Beklenti motorunun özeti — panolar ve raporlar için."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT status, count(*) AS n
              FROM scheduled_events
             WHERE expected_at > now() - %s
             GROUP BY status
            """,
            (timedelta(days=days),),
        )
        sayim = {str(r["status"]): int(r["n"]) for r in cur.fetchall()}

        cur.execute(
            """
            SELECT count(*) AS n FROM scheduled_events
             WHERE status = 'published' AND linked_event_id IS NULL
               AND expected_at > now() - %s
            """,
            (timedelta(days=days),),
        )
        satir = cur.fetchone()
        sayim["observation_gap"] = int(satir["n"]) if satir else 0

    return sayim
