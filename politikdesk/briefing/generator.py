"""Sabah / akşam brifingi (F3-16 · Spec §14.1 kalem 12).

DoD: salience sıralı ilk 5-7 olay + beklenen gelişmeler + doğrulanmamış
iddialar bölümü.

### Karar: brifing DETERMİNİSTİKTİR — LLM kullanmaz

`docs/veri-maliyet-modeli.md` brifing başına ~2.500 girdi + 700 çıktı
token varsaymıştı (kullanıcı başına aylık 60 brifing). Uygulamada bunun
gereksiz olduğu görüldü: brifingin içerdiği her cümlenin kaynağı zaten
veritabanında hazır ve **doğrulanmış** hâlde duruyor — olay başlığı,
`evidence_status` etiketi, kaynak kırılımı, takvim kaydı.

Bu bilgiyi bir modele yeniden yazdırmanın üç bedeli olurdu:
  1. Halüsinasyon riski, hem de günde iki kez ve doğrudan e-postaya.
  2. Maliyet — kullanıcı başına aylık en büyük değişken kalem.
  3. Gecikme ve kırılganlık: 08:00'de model düşerse brifing gitmez.

Karşılığında kazanılacak tek şey akıcı bir üsluptu. Brifing bir tarama
aracıdır, bir yazı değil. **Taslak üretimi (F3-10) yaratıcıdır; brifing
bir dizindir.** Maliyet modeli bu kalemde fazla tahmin etmiştir ve
gerçekleşen maliyet 0'dır.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final, Literal

from politikdesk.config import get_settings
from politikdesk.db import connection, fetch_one
from politikdesk.observability import get_logger

log = get_logger(__name__)

Slot = Literal["morning", "evening"]

SLOT_LABELS: Final[dict[str, str]] = {
    "morning": "Sabah Brifingi",
    "evening": "Akşam Brifingi",
}

# Sabah brifingi bir önceki akşamdan, akşam brifingi sabahtan beri olanı
# özetler. Kapsamlar bilinçli olarak ÇAKIŞMAZ: aynı olayı iki kez
# göstermek "yeni gelişme" algısını bozar.
SLOT_WINDOW_HOURS: Final[dict[str, int]] = {"morning": 12, "evening": 12}

# Spec §8.1 durum etiketleri — brifingde de gizlenmez (§15 madde 3).
#
# Eskiden İKİ tablo vardı: `STATUS_BADGE` (emoji daireler 🟢🟡🟠🔴⚪) ve
# `STATUS_TEXT` (metin). Emoji kaldırılınca ikisi aynı bilgiyi yalnızca
# farklı harf düzeniyle taşır hâle geldi — iki tablo, tek anlam, sessizce
# ayrışma riski. Tek tablo bırakıldı.
#
# Emoji neden kalktı: görünümü e-posta istemcisinden istemciye değişir,
# renk token'ı almaz ve ekran okuyucuda "yeşil daire" diye okunur — durumu
# değil, şekli (DESIGN.md Bölüm 13.4). HTML gövdede rozet artık
# `renderer._status_dot()` ile token renginde bir nokta + BU METİN.
STATUS_TEXT: Final[dict[str, str]] = {
    "strongly_corroborated": "güçlü teyitli",
    "partially_corroborated": "kısmen teyitli",
    "single_source": "tek kaynaklı",
    "contradicted": "çelişkili",
    "unverified": "doğrulanmamış",
    "attribution_verified": "beyan sabit",
}

EVENT_STATUS_TEXT: Final[dict[str, str]] = {
    "developing": "GELİŞİYOR",
    "settled": "OTURDU",
    "contradicted": "ÇELİŞKİLİ",
}


@dataclass
class BriefingEvent:
    """Brifingde bir olayın satırı."""

    event_id: int
    title: str
    salience: int
    status: str
    article_count: int
    independent_count: int
    independence_groups: int
    has_primary_source: bool
    top_claim: str | None = None
    top_claim_status: str | None = None

    @property
    def diversity_note(self) -> str:
        """Spec §10.3 zorunlu çeşitlilik notu — koşul sağlanmıyorsa yazılır."""
        if self.independence_groups >= 2:
            return f"{self.independence_groups} farklı yayın grubu"
        return "Dikkat: bu olay tek bir yayın grubundan raporlanıyor."

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "salience": self.salience,
            "status": self.status,
            "article_count": self.article_count,
            "independent_count": self.independent_count,
            "independence_groups": self.independence_groups,
            "has_primary_source": self.has_primary_source,
            "top_claim": self.top_claim,
            "top_claim_status": self.top_claim_status,
            "diversity_note": self.diversity_note,
        }


@dataclass
class BriefingContent:
    """Brifingin tüm bölümleri (render'dan bağımsız veri)."""

    briefing_date: date
    slot: Slot
    events: list[BriefingEvent] = field(default_factory=list)
    upcoming: list[dict[str, Any]] = field(default_factory=list)
    unverified: list[dict[str, Any]] = field(default_factory=list)
    window_start: datetime | None = None

    @property
    def title(self) -> str:
        return f"{SLOT_LABELS[self.slot]} — {self.briefing_date:%d.%m.%Y}"

    @property
    def is_empty(self) -> bool:
        return not self.events and not self.upcoming

    def as_dict(self) -> dict[str, Any]:
        return {
            "briefing_date": str(self.briefing_date),
            "slot": self.slot,
            "title": self.title,
            "events": [e.as_dict() for e in self.events],
            "upcoming": self.upcoming,
            "unverified": self.unverified,
            "window_start": self.window_start.isoformat() if self.window_start else None,
        }


def _select_events(cur: Any, since: datetime, limit: int) -> list[BriefingEvent]:
    """Salience sıralı olaylar + kaynak çeşitliliği kırılımı."""
    cur.execute(
        """
        SELECT e.id, e.title, e.salience_score, e.status, e.article_count,
               e.independent_count, e.has_primary_source,
               (SELECT count(DISTINCT COALESCE(s.independence_group, s.slug))
                  FROM articles a JOIN sources s ON s.id = a.source_id
                 WHERE a.event_id = e.id) AS independence_groups
        FROM events e
        WHERE e.merged_into_id IS NULL
          AND e.last_update_at >= %s
          AND COALESCE(e.review_flag, '') <> 'rejected'
        ORDER BY e.salience_score DESC NULLS LAST, e.last_update_at DESC
        LIMIT %s
        """,
        (since, limit),
    )
    events = [
        BriefingEvent(
            event_id=r["id"],
            title=r["title"],
            salience=int(r["salience_score"] or 0),
            status=r["status"],
            article_count=r["article_count"],
            independent_count=r["independent_count"],
            independence_groups=int(r["independence_groups"] or 0),
            has_primary_source=bool(r["has_primary_source"]),
        )
        for r in cur.fetchall()
    ]
    if not events:
        return []

    # Olay başına en güçlü iddia: brifing "ne oldu"yu tek cümlede versin.
    cur.execute(
        """
        SELECT DISTINCT ON (event_id) event_id, claim_text, evidence_status
        FROM claims
        WHERE event_id = ANY(%s)
        ORDER BY event_id,
          CASE evidence_status
            WHEN 'strongly_corroborated' THEN 0
            WHEN 'attribution_verified' THEN 1
            WHEN 'partially_corroborated' THEN 2
            WHEN 'contradicted' THEN 3
            WHEN 'single_source' THEN 4
            ELSE 5
          END, id
        """,
        ([e.event_id for e in events],),
    )
    top = {r["event_id"]: (r["claim_text"], r["evidence_status"]) for r in cur.fetchall()}
    for event in events:
        if event.event_id in top:
            event.top_claim, event.top_claim_status = top[event.event_id]
    return events


def _select_upcoming(cur: Any, hours: int = 48) -> list[dict[str, Any]]:
    """Beklenen gelişmeler (Spec §9.5 — MVP'nin gizli kozu)."""
    cur.execute(
        """
        SELECT se.id, se.title, se.expected_at, s.name AS source_name
        FROM scheduled_events se
        LEFT JOIN sources s ON s.id = se.source_id
        WHERE se.status = 'pending'
          AND se.expected_at BETWEEN now() AND now() + make_interval(hours => %s)
        ORDER BY se.expected_at
        LIMIT 8
        """,
        (hours,),
    )
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "expected_at": r["expected_at"].isoformat() if r["expected_at"] else None,
            "expected_label": (f"{r['expected_at']:%d %b %H:%M}" if r["expected_at"] else "—"),
            "source_name": r["source_name"],
        }
        for r in cur.fetchall()
    ]


def _select_unverified(cur: Any, event_ids: list[int]) -> list[dict[str, Any]]:
    """Doğrulanmamış iddialar bölümü (F3-16 DoD).

    Bu bölüm brifingin en önemli parçasıdır: "henüz doğrulanmadı"
    demeyen bir özet, doğrulanmamışı doğrulanmış gibi sunar
    (Spec §15 madde 3).
    """
    if not event_ids:
        return []
    cur.execute(
        """
        SELECT c.id, c.event_id, c.claim_text, c.claim_type, c.evidence_status,
               c.status_reason->>'rule' AS rule, e.title AS event_title
        FROM claims c JOIN events e ON e.id = c.event_id
        WHERE c.event_id = ANY(%s)
          AND c.evidence_status IN ('unverified', 'single_source', 'contradicted')
        ORDER BY
          CASE c.evidence_status
            WHEN 'contradicted' THEN 0 WHEN 'single_source' THEN 1 ELSE 2
          END, c.id
        LIMIT 8
        """,
        (event_ids,),
    )
    return [
        {
            "claim_id": r["id"],
            "event_id": r["event_id"],
            "event_title": r["event_title"],
            "claim_text": r["claim_text"],
            "claim_type": r["claim_type"],
            "evidence_status": r["evidence_status"],
            "status": r["evidence_status"],
            "status_text": STATUS_TEXT.get(r["evidence_status"], r["evidence_status"]),
            "rule": r["rule"],
        }
        for r in cur.fetchall()
    ]


def build_content(
    slot: Slot, *, on: date | None = None, now: datetime | None = None
) -> BriefingContent:
    """Brifingin içeriğini veritabanından derler. LLM ÇAĞRISI YOK."""
    settings = get_settings()
    now = now or datetime.now(UTC)
    on = on or now.date()
    since = now - timedelta(hours=SLOT_WINDOW_HOURS[slot])

    with connection() as conn, conn.cursor() as cur:
        events = _select_events(cur, since, settings.briefing_max_events)

        # Pencerede yeterli olay yoksa geriye doğru genişletilir: boş bir
        # brifing göndermek, brifing göndermemekten kötüdür (açılma
        # oranını düşürür ve güveni aşındırır).
        if len(events) < settings.briefing_min_events:
            events = _select_events(cur, now - timedelta(hours=72), settings.briefing_max_events)

        upcoming = _select_upcoming(cur)
        unverified = _select_unverified(cur, [e.event_id for e in events])

    return BriefingContent(
        briefing_date=on,
        slot=slot,
        events=events,
        upcoming=upcoming,
        unverified=unverified,
        window_start=since,
    )


def generate(
    slot: Slot,
    *,
    user_id: int | None = None,
    on: date | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Brifingi üretir ve kaydeder (aynı gün/slot için üzerine yazar).

    Gönderim BURADA yapılmaz: üretim ile gönderim ayrıdır ki SMTP
    yapılandırılmamışken de brifing üretilsin ve `/briefing/{tarih}`
    sayfasında görünsün.
    """
    from politikdesk.briefing.renderer import render_html, render_text
    from politikdesk.users import current_user_id

    user_id = user_id if user_id is not None else current_user_id()
    content = build_content(slot, on=on, now=now)

    # İzleme belirteci gövdeden ÖNCE belirlenir: piksel adresi HTML'in
    # içine gömülüyor, dolayısıyla belirteci INSERT'e bırakmak gövdeyle
    # kaydın ayrışması demekti. Yeniden üretimde eski belirteç korunur,
    # yoksa daha önce gönderilmiş e-postadaki piksel ölürdü.
    existing = get_briefing(content.briefing_date, slot, user_id)
    token = str(existing["open_token"]) if existing else secrets.token_urlsafe(24)

    html_body = render_html(content, open_token=token)
    text_body = render_text(content)

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO briefings (
                user_id, briefing_date, slot, event_ids,
                body_html, body_text, open_token
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, briefing_date, slot) DO UPDATE SET
                event_ids = EXCLUDED.event_ids,
                body_html = EXCLUDED.body_html,
                body_text = EXCLUDED.body_text,
                generated_at = now()
            RETURNING id, open_token
            """,
            (
                user_id,
                content.briefing_date,
                slot,
                [e.event_id for e in content.events],
                html_body,
                text_body,
                token,
            ),
        )
        row = fetch_one(cur)
        conn.commit()

    log.info(
        "briefing_generated",
        briefing_id=row["id"],
        slot=slot,
        date=str(content.briefing_date),
        events=len(content.events),
        upcoming=len(content.upcoming),
        unverified=len(content.unverified),
    )
    return {
        "briefing_id": int(row["id"]),
        "open_token": row["open_token"],
        **content.as_dict(),
    }


def get_briefing(on: date, slot: Slot, user_id: int | None = None) -> dict[str, Any] | None:
    from politikdesk.users import current_user_id

    user_id = user_id if user_id is not None else current_user_id()
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM briefings
            WHERE user_id = %s AND briefing_date = %s AND slot = %s
            """,
            (user_id, on, slot),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def list_briefings(limit: int = 30, user_id: int | None = None) -> list[dict[str, Any]]:
    from politikdesk.users import current_user_id

    user_id = user_id if user_id is not None else current_user_id()
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, briefing_date, slot, array_length(event_ids, 1) AS event_count,
                   generated_at, sent_at, opened_at, send_error
            FROM briefings WHERE user_id = %s
            ORDER BY briefing_date DESC, slot DESC LIMIT %s
            """,
            (user_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def mark_opened(open_token: str) -> bool:
    """İzleme ucundan gelen açılma kaydı (F3-17 metriği).

    İlk açılış kazanır: `opened_at` bir kez yazılır. Aksi halde e-posta
    istemcisinin her ön-yüklemesi oranı şişirirdi.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE briefings SET opened_at = now()
            WHERE open_token = %s AND opened_at IS NULL
            RETURNING id, user_id
            """,
            (open_token,),
        )
        row = cur.fetchone()
        conn.commit()

    if row is None:
        return False

    from politikdesk import metrics

    metrics.record(
        "briefing_open",
        1.0,
        user_id=row["user_id"],
        dimensions={"briefing_id": row["id"]},
    )
    return True
