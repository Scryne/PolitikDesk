"""Arayüzün okuma sorguları (F3-02 … F3-07, F3-18).

Yalnızca OKUR. Yazma yolları `editorial/`, `briefing/` ve `metrics`
modüllerindedir; ekran katmanının veri değiştirmesi, bir sayfa
yenilemesinin durum değiştirmesi demek olurdu.

Sorgular olay sayfası p95 < 1,5 sn koşulunu (G3 #7) hedefler: her bölüm
tek sorgudur ve N+1 yoktur — 20+ makalelik bir olayda zaman çizelgesi
tek `SELECT` ile gelir (F3-06 DoD).
"""

from __future__ import annotations

from typing import Any

from politikdesk.db import connection
from politikdesk.evidence.salience import personal_adjustment
from politikdesk.observability import get_logger

log = get_logger(__name__)


def _visible(alias: str = "e") -> str:
    """Feed'de gösterilecek olayların koşulu.

    Gizlenen iki durum: birleştirilmiş olay (kopya) ve denetimde
    reddedilmiş olay. `needs_review` GÖSTERİLİR ama rozetiyle —
    belirsizliği gizlemek P4'e aykırıdır.
    """
    return f"{alias}.merged_into_id IS NULL AND COALESCE({alias}.review_flag,'') <> 'rejected'"


_VISIBLE = _visible()


def _topic_priorities(user_id: int) -> list[str]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT topic_priorities FROM editorial_profiles WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    return list(row["topic_priorities"] or []) if row else []


def feed(user_id: int, *, limit: int = 40, vertical: str | None = None) -> list[dict[str, Any]]:
    """Salience sıralı olay kartları (F3-02).

    Kişisel bileşen (0-10) **burada** hesaplanır ve saklanmaz
    (Spec §8.4/B, migration 0003). Sıralama gösterilen skora göredir;
    saklanan `salience_score` yalnızca global kısımdır.
    """
    priorities = _topic_priorities(user_id)
    vertical_clause = "AND e.vertical = %s" if vertical and vertical != "all" else ""
    params: list[Any] = [limit] if not vertical_clause else [vertical, limit]

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT e.id, e.title, e.status, e.salience_score, e.salience_breakdown,
                   e.topic_tags, e.article_count, e.independent_count,
                   e.has_primary_source, e.review_flag, e.vertical,
                   e.first_reported_at, e.last_update_at,
                   (SELECT count(DISTINCT COALESCE(s.independence_group, s.slug))
                      FROM articles a JOIN sources s ON s.id = a.source_id
                     WHERE a.event_id = e.id) AS independence_groups,
                   (SELECT jsonb_object_agg(kind, n) FROM (
                      SELECT s.kind, count(*) AS n
                        FROM articles a JOIN sources s ON s.id = a.source_id
                       WHERE a.event_id = e.id GROUP BY s.kind
                    ) k) AS source_breakdown,
                   (SELECT count(*) FROM claims c WHERE c.event_id = e.id) AS claim_count,
                   (SELECT count(*) FROM claims c
                     WHERE c.event_id = e.id
                       AND c.evidence_status IN ('unverified','single_source','contradicted')
                   ) AS weak_claim_count,
                   -- Çelişkili iddia AYRI sayılır: "zayıf" kümesinin içinde
                   -- kaybolmamalı. Bir olayda çelişki varsa kartın taşıması
                   -- gereken sinyal odur, teyit oranı değil.
                   (SELECT count(*) FROM claims c
                     WHERE c.event_id = e.id AND c.evidence_status = 'contradicted'
                   ) AS contradicted_count,
                   -- Üretim kapısının iki koşulundan ikincisi (guards.py:
                   -- "no_evidence"). Kartın "kanıta bağlı" etiketi bundan
                   -- türer; üçüncü koşul (isimli kişi hakkında doğrulanmamış
                   -- iddia) NER gerektirir ve olay sayfasında sorulur.
                   (SELECT count(*) FROM evidence ev JOIN claims c ON c.id = ev.claim_id
                     WHERE c.event_id = e.id) AS evidence_count
            FROM events e
            WHERE {_VISIBLE} {vertical_clause}
            ORDER BY e.salience_score DESC NULLS LAST, e.last_update_at DESC
            LIMIT %s
            """,  # noqa: S608 — _VISIBLE sabit bir dize
            params,
        )
        rows = [dict(r) for r in cur.fetchall()]

    for row in rows:
        personal = personal_adjustment(list(row["topic_tags"] or []), priorities)
        row["personal_salience"] = personal
        row["global_salience"] = int(row["salience_score"] or 0)
        row["displayed_salience"] = row["global_salience"] + personal

    # İki geçişli sıralama: önce tazelik (azalan), sonra KARARLI biçimde
    # gösterilen skor (azalan). Tek geçişte tarihi ters çevirmek mümkün
    # değil (datetime negatiflenemez) ve eşit skorlu olaylarda eskisi
    # üste çıkardı.
    rows.sort(key=lambda r: r["last_update_at"], reverse=True)
    rows.sort(key=lambda r: r["displayed_salience"], reverse=True)
    return rows


def since_last_visit(user_id: int, since: str | None) -> dict[str, Any]:
    """ "Sen yokken ne oldu" şeridi (F3-18).

    Tek satır: son girişten bu yana N önemli olay. Eşik salience 30'dur —
    her yeni olayı "önemli" saymak şeridi gürültüye çevirirdi.
    """
    if not since:
        return {"available": False}

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE e.salience_score >= 30) AS important,
                   max(e.salience_score) AS top_salience,
                   (SELECT e2.title FROM events e2
                     WHERE {_visible("e2")} AND e2.first_reported_at > %s
                     ORDER BY e2.salience_score DESC NULLS LAST LIMIT 1) AS top_title
            FROM events e
            WHERE {_VISIBLE} AND e.first_reported_at > %s
            """,  # noqa: S608
            (since, since),
        )
        row = cur.fetchone()

    if row is None or not row["total"]:
        return {"available": True, "total": 0, "important": 0}
    return {
        "available": True,
        "since": since,
        "total": int(row["total"]),
        "important": int(row["important"] or 0),
        "top_title": row["top_title"],
        "top_salience": int(row["top_salience"] or 0),
    }


def event_page(event_id: int, user_id: int) -> dict[str, Any] | None:
    """Olay sayfasının tüm bölümleri (Spec §14.3, F3-03…F3-07)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT e.*,
                   (SELECT count(DISTINCT COALESCE(s.independence_group, s.slug))
                      FROM articles a JOIN sources s ON s.id = a.source_id
                     WHERE a.event_id = e.id) AS independence_groups
            FROM events e WHERE e.id = %s AND {_VISIBLE}
            """,  # noqa: S608
            (event_id,),
        )
        event = cur.fetchone()
        if event is None:
            return None
        event = dict(event)
        event.pop("centroid_embedding", None)  # 1024 sayı sayfaya girmez

        # --- kaynaklar / framing paneli (F3-05) + zaman çizelgesi (F3-06)
        cur.execute(
            """
            SELECT a.id, a.title, a.canonical_url, a.excerpt, a.published_at,
                   a.first_seen_at, a.near_duplicate_of_id, a.cluster_score,
                   s.name AS source_name, s.slug AS source_slug, s.tier, s.kind,
                   s.independence_group
            FROM articles a JOIN sources s ON s.id = a.source_id
            WHERE a.event_id = %s
            ORDER BY COALESCE(a.published_at, a.first_seen_at), a.id
            """,
            (event_id,),
        )
        articles = [dict(r) for r in cur.fetchall()]

        # --- iddialar + kanıt sayısı (ne biliyoruz / ne bilmiyoruz)
        cur.execute(
            """
            SELECT c.id, c.claim_text, c.claim_type, c.evidence_status,
                   c.status_reason, c.normalized_value, c.computed_at,
                   (SELECT count(*) FROM evidence ev WHERE ev.claim_id = c.id)
                     AS evidence_count
            FROM claims c WHERE c.event_id = %s
            ORDER BY
              CASE c.evidence_status
                WHEN 'strongly_corroborated' THEN 0
                WHEN 'attribution_verified' THEN 1
                WHEN 'partially_corroborated' THEN 2
                WHEN 'contradicted' THEN 3
                WHEN 'single_source' THEN 4
                ELSE 5
              END, c.id
            """,
            (event_id,),
        )
        claims = [dict(r) for r in cur.fetchall()]

        # --- önceki bağlam (F2-17 çıktısı)
        cur.execute(
            """
            SELECT e.id, e.title, e.first_reported_at, r.similarity, r.relation
            FROM event_relations r JOIN events e ON e.id = r.to_event_id
            WHERE r.from_event_id = %s AND e.merged_into_id IS NULL
            ORDER BY r.similarity DESC NULLS LAST LIMIT 6
            """,
            (event_id,),
        )
        related = [dict(r) for r in cur.fetchall()]

        # --- sıradaki beklenen (Spec §9.5)
        cur.execute(
            """
            SELECT se.id, se.title, se.expected_at, s.name AS source_name
            FROM scheduled_events se LEFT JOIN sources s ON s.id = se.source_id
            WHERE se.status = 'pending' AND se.expected_at >= now()
            ORDER BY se.expected_at LIMIT 4
            """
        )
        upcoming = [dict(r) for r in cur.fetchall()]

        # --- varlıklar
        cur.execute(
            """
            SELECT en.canonical_name, en.entity_type, en.is_key_entity
            FROM event_entities ee JOIN entities en ON en.id = ee.entity_id
            WHERE ee.event_id = %s
            ORDER BY en.is_key_entity DESC, en.canonical_name
            """,
            (event_id,),
        )
        entities = [dict(r) for r in cur.fetchall()]

        # --- açık geri bildirim (F3-21)
        cur.execute(
            "SELECT count(*) AS n FROM event_feedback WHERE event_id = %s AND resolved_at IS NULL",
            (event_id,),
        )
        feedback_row = cur.fetchone()

    personal = personal_adjustment(list(event["topic_tags"] or []), _topic_priorities(user_id))
    event["global_salience"] = int(event["salience_score"] or 0)
    event["personal_salience"] = personal
    event["displayed_salience"] = event["global_salience"] + personal

    return {
        "event": event,
        "articles": articles,
        "claims": claims,
        "related": related,
        "upcoming": upcoming,
        "entities": entities,
        "open_feedback": int(feedback_row["n"]) if feedback_row else 0,
    }


def add_feedback(
    *, event_id: int, user_id: int, note: str | None = None, claim_id: int | None = None
) -> dict[str, Any]:
    """ "Bu yanlış" işareti (F3-21).

    İki şey yapar: olayı **insan denetim kuyruğuna** düşürür ve
    `correction_rate` metriğini besler. Bir "güvenilirlik skoru"
    hesaplamaz — böyle bir alan şemada yoktur (Spec §15 madde 13).
    """
    from politikdesk.db import fetch_one

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO event_feedback (event_id, user_id, note, claim_id, scope)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
            """,
            (
                event_id,
                user_id,
                (note or "")[:500] or None,
                claim_id,
                "claim" if claim_id else "event",
            ),
        )
        feedback_id = int(fetch_one(cur)["id"])

        # Denetim kuyruğu: zaten `verified` işaretlenmiş bir olay bile
        # kullanıcı itiraz ettiğinde yeniden bakılmalıdır.
        cur.execute(
            "UPDATE events SET review_flag = 'needs_review' WHERE id = %s",
            (event_id,),
        )
        cur.execute(
            """
            INSERT INTO audit_log (actor, action, target, payload)
            VALUES (%s, 'event_flagged_by_user', %s, %s::jsonb)
            """,
            (f"user:{user_id}", f"events/{event_id}", f'{{"feedback_id": {feedback_id}}}'),
        )
        conn.commit()

    from politikdesk import metrics

    metrics.record(
        "event_flagged",
        1.0,
        user_id=user_id,
        dimensions={"event_id": event_id, "feedback_id": int(feedback_id)},
    )
    log.info("event_feedback", event_id=event_id, feedback_id=int(feedback_id))
    return {"feedback_id": int(feedback_id), "event_id": event_id, "review_flag": "needs_review"}
