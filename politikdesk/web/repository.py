"""Arayüzün okuma sorguları (F3-02 … F3-07, F3-18).

Yalnızca OKUR. Yazma yolları `editorial/`, `briefing/` ve `metrics`
modüllerindedir; ekran katmanının veri değiştirmesi, bir sayfa
yenilemesinin durum değiştirmesi demek olurdu.

Sorgular olay sayfası p95 < 1,5 sn koşulunu (G3 #7) hedefler: her bölüm
tek sorgudur ve N+1 yoktur — 20+ makalelik bir olayda zaman çizelgesi
tek `SELECT` ile gelir (F3-06 DoD).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from politikdesk.db import connection
from politikdesk.evidence.salience import personal_adjustment
from politikdesk.observability import get_logger

log = get_logger(__name__)


def _visible(alias: str = "e", *, cycle_id: int | None = None) -> str:
    """Feed'de gösterilecek olayların koşulu.

    Gizlenen iki durum: birleştirilmiş olay (kopya) ve denetimde
    reddedilmiş olay. `needs_review` GÖSTERİLİR ama rozetiyle.
    Aktif üretim döngüsü (cycle_id) izolasyonu enforce edilir.
    """
    base = f"{alias}.merged_into_id IS NULL AND COALESCE({alias}.review_flag,'') <> 'rejected'"
    if cycle_id is not None:
        return f"{base} AND {alias}.cycle_id = {int(cycle_id)}"
    return (
        f"{base} AND ({alias}.cycle_id = (SELECT id FROM publication_cycles WHERE status = 'active' LIMIT 1) "
        f"OR {alias}.cycle_id IS NULL)"
    )


_VISIBLE = _visible()


def _topic_priorities(user_id: int) -> list[str]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT topic_priorities FROM editorial_profiles WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    return list(row["topic_priorities"] or []) if row else []


def feed(
    user_id: int,
    *,
    limit: int = 40,
    offset: int = 0,
    vertical: str | None = None,
    sort: str = "important",
    category: str | None = None,
    topic: str | None = None,
    region: str | None = None,
    time_range: str | None = None,
    source_id: int | None = None,
    query: str | None = None,
    cycle_id: int | None = None,
) -> list[dict[str, Any]]:
    """Gündem V2 — Live Intelligence Feed sorgu motoru (Faz 21).

    Sıralama Modları:
      * 'important' (varsayılan): Gösterilen önem skoru (global + kişisel) azalan
      * 'newest': İlk keşif / yayın zamanı azalan (en yeni düşenler)
      * 'updated': Son güncelleme zamanı azalan (son gelişenler)
    """
    priorities = _topic_priorities(user_id)

    clauses = [_visible("e", cycle_id=cycle_id)]
    params: list[Any] = []

    if vertical and vertical != "all":
        clauses.append("e.vertical = %s")
        params.append(vertical)

    if category and category != "all":
        clauses.append("e.category = %s")
        params.append(category)

    if region and region != "all":
        clauses.append("e.region = %s")
        params.append(region)

    if topic and topic != "all":
        clauses.append("(%s = ANY(e.topic_tags) OR EXISTS (SELECT 1 FROM articles a_top WHERE a_top.event_id = e.id AND %s = ANY(a_top.topics)))")
        params.extend([topic, topic])

    if time_range and time_range != "all":
        if time_range == "15m":
            clauses.append("e.last_update_at > now() - interval '15 minutes'")
        elif time_range == "1h":
            clauses.append("e.last_update_at > now() - interval '1 hour'")
        elif time_range == "6h":
            clauses.append("e.last_update_at > now() - interval '6 hours'")
        elif time_range == "24h":
            clauses.append("e.last_update_at > now() - interval '24 hours'")
        elif time_range == "7d":
            clauses.append("e.last_update_at > now() - interval '7 days'")

    if source_id:
        clauses.append("EXISTS (SELECT 1 FROM articles a_src WHERE a_src.event_id = e.id AND a_src.source_id = %s)")
        params.append(source_id)

    if query and query.strip():
        q_str = f"%{query.strip()}%"
        clauses.append(
            "(e.title ILIKE %s OR COALESCE(e.summary,'') ILIKE %s OR "
            "EXISTS (SELECT 1 FROM claims c_q WHERE c_q.event_id = e.id AND c_q.claim_text ILIKE %s))"
        )
        params.extend([q_str, q_str, q_str])

    where_sql = " AND ".join(clauses)

    if sort == "newest":
        order_sql = "COALESCE(e.first_reported_at, e.created_at) DESC, e.last_update_at DESC"
    elif sort == "updated":
        order_sql = "e.last_update_at DESC, e.first_reported_at DESC"
    else:  # important
        order_sql = "e.salience_score DESC NULLS LAST, e.last_update_at DESC"

    params.extend([limit, offset])

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT e.id, e.title, e.summary, e.status, e.salience_score, e.salience_breakdown,
                   e.topic_tags, e.article_count, e.independent_count,
                   e.has_primary_source, e.review_flag, e.vertical,
                   COALESCE(e.category, 'ekonomi') AS category,
                   COALESCE(e.region, 'turkiye') AS region,
                   e.cycle_id,
                   e.first_reported_at, e.last_update_at, e.created_at,
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
                   (SELECT count(*) FROM claims c
                     WHERE c.event_id = e.id AND c.evidence_status = 'contradicted'
                   ) AS contradicted_count,
                   (SELECT count(*) FROM evidence ev JOIN claims c ON c.id = ev.claim_id
                     WHERE c.event_id = e.id) AS evidence_count,
                   (SELECT jsonb_build_object(
                      'id', d.id,
                      'angle', d.angle,
                      'body', COALESCE(d.final_body, d.body),
                      'is_grounded', d.is_grounded,
                      'user_action', d.user_action,
                      'created_at', d.created_at
                    )
                    FROM drafts d
                    WHERE d.event_id = e.id AND d.is_grounded = true
                    ORDER BY d.created_at DESC LIMIT 1) AS latest_draft
            FROM events e
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT %s OFFSET %s
            """,
            params,
        )
        rows = [dict(r) for r in cur.fetchall()]

    from datetime import UTC, datetime, timedelta
    now_utc = datetime.now(UTC)

    for row in rows:
        personal = personal_adjustment(list(row["topic_tags"] or []), priorities)
        row["personal_salience"] = personal
        row["global_salience"] = int(row["salience_score"] or 0)
        row["displayed_salience"] = row["global_salience"] + personal

        # Dinamik "is_new" hesaplaması: son 45 dakika içinde ilk kez görüldüyse
        first_dt = row.get("first_reported_at") or row.get("created_at")
        if first_dt and (now_utc - first_dt) < timedelta(minutes=45):
            row["is_new"] = True
        else:
            row["is_new"] = False

    if sort == "important":
        # İki geçişli sıralama: önce tazelik (azalan), sonra KARARLI biçimde
        # gösterilen skor (azalan).
        rows.sort(key=lambda r: r["last_update_at"], reverse=True)
        rows.sort(key=lambda r: r["displayed_salience"], reverse=True)
    elif sort == "newest":
        rows.sort(key=lambda r: r.get("first_reported_at") or r["last_update_at"], reverse=True)
    elif sort == "updated":
        rows.sort(key=lambda r: r["last_update_at"], reverse=True)

    return rows


def count_new_events(
    since_ts: str,
    *,
    vertical: str | None = None,
    category: str | None = None,
    region: str | None = None,
    cycle_id: int | None = None,
) -> int:
    """Belirli bir zaman damgasından sonra gelen yeni aktif olay sayısını döner."""
    if not since_ts:
        return 0
    since_val: Any = since_ts
    if isinstance(since_ts, str):
        try:
            clean_str = since_ts.strip().replace(" ", "+")
            since_val = datetime.fromisoformat(clean_str)
        except Exception:
            since_val = since_ts
    clauses = [_visible("e", cycle_id=cycle_id), "e.first_reported_at > %s"]
    params: list[Any] = [since_val]
    if vertical and vertical != "all":
        clauses.append("e.vertical = %s")
        params.append(vertical)
    if category and category != "all":
        clauses.append("e.category = %s")
        params.append(category)
    if region and region != "all":
        clauses.append("e.region = %s")
        params.append(region)

    where_sql = " AND ".join(clauses)
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM events e WHERE {where_sql}", params)
        row = cur.fetchone()
        return int(row["count"] or 0) if row else 0


def since_last_visit(user_id: int, since: str | None) -> dict[str, Any]:
    """ "Sen yokken ne oldu" şeridi (F3-18).
    Aktif döngüdeki yeni önemli olayları sayar.
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
            WHERE {_visible("e")} AND e.first_reported_at > %s
            """,
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



def claim_status_distribution(*, days: int = 7) -> list[tuple[str, int]]:
    """İddia kanıt durumlarının dağılımı (Roadmap Faz 5.1 · 8.1 "Claims").

    Sıra `STATUS_ORDER`'dır, sayıya göre DEĞİL: skala güçlüden zayıfa
    okunur ve o sıranın sabit kalması, iki farklı günde bakan kişinin
    aynı yerde aynı şeyi bulmasını sağlar. Sayıya göre sıralasaydık
    çubuklar her yenilemede yer değiştirirdi.

    ⛔ `contradicted` sonuçta **görünmez** çünkü hiç üretilmiyor
    (ADR-008: karşı kanıt yolu kurulmadı). Sıfır satırını çizmek yerine
    arayüz bunu açıkça yazar — sıfır bir çubuk olarak gösterilseydi
    "ölçüldü ve çıkmadı" diye okunurdu.
    """
    order = (
        "strongly_corroborated",
        "partially_corroborated",
        "attribution_verified",
        "single_source",
        "unverified",
        "contradicted",
    )
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT c.evidence_status AS status, count(*) AS n
              FROM claims c
              JOIN events e ON e.id = c.event_id
             WHERE {_VISIBLE}
               AND e.last_update_at > now() - make_interval(days => %s)
             GROUP BY 1
            """,  # noqa: S608 — `_VISIBLE` sabit
            (days,),
        )
        sayilar = {str(row["status"]): int(row["n"]) for row in cur.fetchall()}

    return [(status, sayilar[status]) for status in order if sayilar.get(status)]


def official_indicator_series(*, limit_per_metric: int = 6) -> list[dict[str, Any]]:
    """Kurumun KENDİ makine okunur yayınından gelen gösterge serileri.

    ⛔ Bu fonksiyon neden var: kumanda odasındaki gösterge kartları bir
    dönem **kodda sabitlenmiş** sayılarla dolduruluyordu ("TCMB Politika
    Faizi %45,00", kaynak etiketi "TCMB"). Ürünün en sert sözleşmesi
    (Spec §15/13 ve `editorial/grounding_check.py`) kanıtta bulunmayan
    hiçbir sayının ekrana çıkamayacağını söyler; uydurma bir sayıyı
    üstelik TÜİK/TCMB imzasıyla göstermek o sözleşmenin en ağır ihlaliydi.

    Kaynak `articles.official_value`'dur (migration 0007): adaptörün
    kurumdan ALDIĞI `{metric, value, unit, period}` dörtlüsü. Modelden
    değil, kurumdan gelir. Veri yoksa bu fonksiyon **boş liste** döner ve
    arayüz dürüst bir boş durum gösterir — tahmin üretmez.

    ⛔ GRUPLAMA `metric` DEĞİL, `series_code` İLEDİR (varsa).

    `metric` tek başına bir seriyi tekilleştirmiyor: TCMB EVDS'de hem
    USD/TRY hem EUR/TRY `exchange_rate` metriğini taşır. Metriğe göre
    gruplansaydı gösterge şeridi iki farklı büyüklüğün değerlerini
    **tek bir eğri** gibi çizerdi — yani ekranda var olmayan bir seri
    gösterirdi. Bu, D-01'de kaldırılan uydurma gösterge kusurunun veri
    tarafındaki karşılığı olurdu.

    `series_code` taşımayan kayıtlar (TÜİK SDMX) `metric`e düşer; onlarda
    metrik zaten seriyi tekilleştiriyor.

    Dönen her kayıt: `metric`, `label`, `unit`, `latest_value`,
    `latest_period`, `history` (eskiden yeniye sıralı), `source_name`.

    ⛔ BİRİNCİL KAYNAK `indicator_observations`'TIR.

    `articles.official_value` seri başına yalnızca **son** yayımı taşır;
    o yol tek başına kullanıldığında `history` tek noktaya, `previous_value`
    `None`'a düşüyordu. Sonuç: şerit her kart için "ilk gözlem" yazıyor ve
    sparkline düz bir nokta çiziyordu — 683 gerçek USD/TRY gözlemi
    veritabanında dururken. Faz 3'te kurulan zaman serisi deposu
    (`indicator_series` + `indicator_observations`) tam da bunun için var.

    `superseded_at IS NULL` şartı revize edilmiş gözlemleri eler: kurum bir
    dönemi yeniden yayımladığında ekranda **yürürlükteki** sayı durur.

    Zaman serisi deposunda karşılığı olmayan metrikler (TÜİK SDMX'ten gelen
    `employment_rate` gibi) eski `official_value` yoluna düşer — bu bir
    gerileme değil, kapsama farkıdır: o kaynaklar henüz seri olarak
    tanımlanmadı ve tek gözlem göstermek, hiç göstermemekten iyidir.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT series_key, metric, label, unit, period, value, source_name
            FROM (
                SELECT si.series_code            AS series_key,
                       si.metric                 AS metric,
                       si.label                  AS label,
                       si.unit                   AS unit,
                       io.period                 AS period,
                       io.value                  AS value,
                       s.name                    AS source_name,
                       row_number() OVER (
                           PARTITION BY si.id ORDER BY io.period DESC
                       ) AS rn
                FROM indicator_series si
                JOIN indicator_observations io ON io.series_id = si.id
                JOIN sources s ON s.id = si.source_id
                WHERE si.is_active
                  AND io.superseded_at IS NULL
            ) ranked
            WHERE rn <= %s
            ORDER BY series_key ASC, period ASC
            """,
            (limit_per_metric,),
        )
        seri_satirlari = [dict(r) for r in cur.fetchall()]
        kapsanan = {r["series_key"] for r in seri_satirlari}

        cur.execute(
            """
            SELECT series_key, metric, label, unit, period, value, source_name
            FROM (
                SELECT COALESCE(a.official_value->>'series_code',
                                a.official_value->>'metric')  AS series_key,
                       a.official_value->>'metric'            AS metric,
                       a.official_value->>'series_label'      AS label,
                       a.official_value->>'unit'              AS unit,
                       a.official_value->>'period'            AS period,
                       (a.official_value->>'value')::float8   AS value,
                       s.name                                 AS source_name,
                       row_number() OVER (
                           PARTITION BY COALESCE(a.official_value->>'series_code',
                                                 a.official_value->>'metric')
                           ORDER BY a.official_value->>'period' DESC
                       ) AS rn
                FROM articles a
                JOIN sources s ON s.id = a.source_id
                WHERE a.official_value IS NOT NULL
                  AND a.official_value ? 'metric'
                  AND a.official_value ? 'value'
                  AND a.official_value ? 'period'
            ) ranked
            WHERE rn <= %s
            ORDER BY series_key ASC, period ASC
            """,
            (limit_per_metric,),
        )
        # Zaman serisi deposunda zaten olan bir seriyi ikinci kez ekleme:
        # aynı gösterge iki kart olarak çıkardı.
        yedek = [r for r in (dict(x) for x in cur.fetchall())
                 if r["series_key"] not in kapsanan]

    rows = seri_satirlari + yedek

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row["series_key"]
        entry = grouped.setdefault(
            key,
            {
                "series_key": key,
                "metric": row["metric"],
                # Kaynağın kendi verdiği seri adı varsa o kullanılır
                # (ör. "ABD doları alış kuru"); yoksa metrik etiketine
                # düşülür ve çeviriyi sunum katmanı yapar.
                "label": row["label"] or None,
                "unit": row["unit"] or "",
                "source_name": row["source_name"] or "",
                "history": [],
                "periods": [],
            },
        )
        entry["history"].append(float(row["value"]))
        entry["periods"].append(row["period"])

    out: list[dict[str, Any]] = []
    for entry in grouped.values():
        entry["latest_value"] = entry["history"][-1]
        entry["latest_period"] = entry["periods"][-1]
        entry["previous_value"] = entry["history"][-2] if len(entry["history"]) >= 2 else None
        out.append(entry)

    out.sort(key=lambda e: str(e["series_key"]))
    return out


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
