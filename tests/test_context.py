"""Faz 2 İş Kolu D — bağlam ve takvim (F2-17, F2-18, F2-19).

Veritabanı gerektirir: her iki bileşenin de sözleşmesi kalıcı ilişkilerin
doğru kurulmasıdır.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest

from politikdesk.context.related import find_related, link_related
from politikdesk.context.scheduler_match import add_scheduled, match_pending

pytestmark = pytest.mark.db  # not: son testin DB gereksinimi yok

SLUG = "pytest-context-src"
DIM = 1024


def _direction(rng: random.Random) -> list[float]:
    """Rastgele bir yön — sabit vektör DEĞİL.

    **Neden (20 Ağustos 2026 denetimi).** Fixture eskiden her boyutu aynı
    sayı olan bir vektör kuruyordu (`[0.3, 0.3, ...]`). İki sabit pozitif
    vektörün kosinüs benzerliği **her zaman tam 1.0'dır**: yön aynıdır,
    yalnızca uzunluk değişir. Yani bu turun `[0.30…]`'u ile ÖNCEKİ bir
    koşumdan kalan `[0.30…]` birbirinden ayırt edilemiyordu.

    Sonuç: `find_related` benzerliği 1.0 olan bir yığın aday buluyor,
    `LIMIT` bu turun fixture'ını dışarıda bırakıyor ve test **veritabanı
    hacmine bağlı** olarak düşüyordu. Ölçüldü: veritabanında aynı yöne
    bakan, geçmiş koşumlardan kalmış dokuz olay vardı ve `link_related`
    beş ilişkinin BEŞİNİ de onlarla kurdu — fixture'la hiçbirini.

    Rastgele bir yön fixture'ı kendi koşumuna hapseder: 1024 boyutta iki
    bağımsız rastgele yönün kosinüsü ~0'dır, dolayısıyla ne geçmiş
    artıklar ne de gerçek üretim olayları yarışabilir.
    """
    return [rng.uniform(-1.0, 1.0) for _ in range(DIM)]


def _fmt(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


@pytest.fixture()
def fixtures(db_conn):  # noqa: ANN001, ANN201
    """İki ilişkili olay (aynı seri, farklı ay) + bir alakasız olay."""
    now = datetime.now(UTC)
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sources (name, slug, tier, kind, access_method, tos_status)
            VALUES ('Pytest Context', %s, 1, 'official', 'official_feed', 'allowed')
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name RETURNING id
            """,
            (SLUG,),
        )
        source_id = cur.fetchone()["id"]

        # Bu koşuma ÖZGÜ yönler. `random.Random()` tohumsuz kurulur:
        # her koşum farklı yöne bakar, böylece bir önceki koşumdan artık
        # kalsa bile bu turun fixture'ıyla yarışamaz.
        rng = random.Random()
        yakin = _direction(rng)
        # "Aynı seri": aynı yön, ölçülemeyecek kadar küçük sapmayla.
        yakin_komsu = [v + rng.uniform(-1e-4, 1e-4) for v in yakin]
        # "Alakasız": bağımsız yön — 1024 boyutta kosinüs ~0.
        uzak = _direction(rng)

        # İki olay birbirine çok yakın (aynı seri), üçüncü uzak.
        specs = [
            ("pytest enflasyon haziran", yakin, now - timedelta(days=60)),
            ("pytest enflasyon temmuz", yakin_komsu, now - timedelta(days=30)),
            ("pytest alakasiz olay", uzak, now - timedelta(days=45)),
        ]
        event_ids = []
        for title, vec, at in specs:
            cur.execute(
                """
                INSERT INTO events (title, vertical, centroid_embedding,
                                    first_reported_at, last_update_at, article_count)
                VALUES (%s, 'macro_economy', %s::vector, %s, %s, 1)
                RETURNING id
                """,
                (title, _fmt(vec), at, at),
            )
            event_ids.append(cur.fetchone()["id"])
    db_conn.commit()

    yield {"events": event_ids, "source_id": source_id, "now": now}

    with db_conn.cursor() as cur:
        cur.execute(
            "DELETE FROM event_relations WHERE from_event_id = ANY(%s) OR to_event_id = ANY(%s)",
            (event_ids, event_ids),
        )
        cur.execute("DELETE FROM scheduled_events WHERE source_id = %s", (source_id,))
        cur.execute(
            "DELETE FROM audit_log WHERE target = ANY(%s)", ([f"events/{e}" for e in event_ids],)
        )
        cur.execute("DELETE FROM articles WHERE source_id = %s", (source_id,))
        cur.execute("DELETE FROM events WHERE id = ANY(%s)", (event_ids,))
        cur.execute("DELETE FROM sources WHERE id = %s", (source_id,))
    db_conn.commit()


# ==========================================================================
# F2-17 — tarihsel bağlam
# ==========================================================================
def test_similar_past_event_is_found(db_conn, fixtures) -> None:  # noqa: ANN001
    """DoD: bir enflasyon olayı, önceki ayın enflasyon olayına bağlanıyor."""
    older, newer, _unrelated = fixtures["events"]
    related = find_related(newer)
    assert older in [r.event_id for r in related]


def test_unrelated_event_is_not_linked(db_conn, fixtures) -> None:  # noqa: ANN001
    _older, newer, unrelated = fixtures["events"]
    assert unrelated not in [r.event_id for r in find_related(newer)]


def test_context_only_looks_backwards(db_conn, fixtures) -> None:  # noqa: ANN001
    """Tarihsel bağlam geriye bakar; ileriye bakan bağ diğer uçtan kurulur."""
    older, newer, _ = fixtures["events"]
    assert newer not in [r.event_id for r in find_related(older)]


def test_link_related_writes_same_thread_relation(db_conn, fixtures) -> None:  # noqa: ANN001
    older, newer, _ = fixtures["events"]
    assert link_related(newer) >= 1
    db_conn.commit()

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT relation, similarity FROM event_relations "
            "WHERE from_event_id = %s AND to_event_id = %s",
            (newer, older),
        )
        row = cur.fetchone()
    db_conn.commit()

    assert row is not None
    assert row["relation"] == "same_thread"
    assert row["similarity"] > 0.8


def test_linking_is_idempotent(db_conn, fixtures) -> None:  # noqa: ANN001
    """İkinci koşum yeni satır üretmemeli — beat tekrar tekrar koşar.

    **Sözleşme İDEMPOTANSTIR, bağ sayısı değil.** Eskiden bu test
    `count == 1` diyordu ve o sayı, veritabanında fixture'ın vektörüne
    benzeyen BAŞKA olay bulunmadığı varsayımına dayanıyordu.

    `find_related` tüm `events` tablosunu tarar; fixture'ın sabit
    vektörü (`[0.3001, …]`) gerçek gömme vektörlerine de benzeyebilir.
    Üretim verisi büyüdükçe eşleşme sayısı 1'i aştı ve test, ürün kodu
    doğru çalıştığı hâlde kırıldı (20 Ağu 2026: `assert 3 == 1`; log
    iki koşumda da `count=3` diyordu, yani çift yazım YOKTU).

    Doğru ölçüt: ikinci koşumdan sonra satır sayısı DEĞİŞMEMELİ.
    Bu, veritabanının ne kadar dolu olduğundan bağımsızdır.
    """
    _older, newer, _ = fixtures["events"]

    link_related(newer)
    db_conn.commit()
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM event_relations WHERE from_event_id = %s",
            (newer,),
        )
        ilk = cur.fetchone()["n"]
    db_conn.commit()
    assert ilk >= 1, "İlk koşum en az bir ilişki kurmalıydı"

    link_related(newer)
    db_conn.commit()
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM event_relations WHERE from_event_id = %s",
            (newer,),
        )
        ikinci = cur.fetchone()["n"]
    db_conn.commit()

    assert ikinci == ilk, f"İkinci koşum {ikinci - ilk} yeni satır üretti — idempotans bozuk"


# ==========================================================================
# F2-18 / F2-19 — takvim ve eşleştirme
# ==========================================================================
def test_scheduled_event_matches_the_event_at_that_time(db_conn, fixtures) -> None:  # noqa: ANN001
    """F2-19 DoD: takvimdeki kayıt, o saatte gelen olayı otomatik alır."""
    _older, newer, _ = fixtures["events"]
    with db_conn.cursor() as cur:
        cur.execute("SELECT first_reported_at FROM events WHERE id = %s", (newer,))
        expected_at = cur.fetchone()["first_reported_at"]
        # Olayın kaynak koşulunu sağlaması için bir makale gerekir.
        # Dinamik URL/hash: testler ardışık veya farklı sırayla koştuğunda tekillik çakışmasını önler.
        now = fixtures.get("now") or datetime.now(UTC)
        dyn_url = f"https://pytest.test/ctx/{newer}_{int(now.timestamp())}"
        dyn_hash = f"h-ctx-{newer}_{int(now.timestamp())}"
        cur.execute(
            """
            INSERT INTO articles (source_id, canonical_url, title, content_hash, event_id)
            VALUES (%s, %s, 'pytest makale', %s, %s)
            """,
            (fixtures["source_id"], dyn_url, dyn_hash, newer),
        )
    db_conn.commit()

    scheduled_id = add_scheduled(
        title="pytest beklenen enflasyon verisi",
        expected_at=expected_at + timedelta(minutes=20),
        source_slug=SLUG,
    )
    match_pending()

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT linked_event_id, status FROM scheduled_events WHERE id = %s",
            (scheduled_id,),
        )
        row = cur.fetchone()
    db_conn.commit()

    assert row["linked_event_id"] == newer
    assert row["status"] == "occurred"


def test_event_from_another_source_is_not_matched(db_conn, fixtures) -> None:  # noqa: ANN001
    """Yalnız zamana bakan eşleştirme, o saatteki alakasız haberi bağlardı."""
    _older, newer, _ = fixtures["events"]
    with db_conn.cursor() as cur:
        cur.execute("SELECT first_reported_at FROM events WHERE id = %s", (newer,))
        expected_at = cur.fetchone()["first_reported_at"]
        cur.execute("SELECT id FROM sources WHERE slug = 'tcmb'")
        other = cur.fetchone()
    db_conn.commit()
    if other is None:
        pytest.skip("tcmb kaynağı yok — kaynak ayrımı testi atlandı")

    scheduled_id = add_scheduled(
        title="pytest baska kaynagin beklenen verisi",
        expected_at=expected_at,
        source_slug="tcmb",
    )
    match_pending()

    with db_conn.cursor() as cur:
        cur.execute("SELECT linked_event_id FROM scheduled_events WHERE id = %s", (scheduled_id,))
        linked = cur.fetchone()["linked_event_id"]
        cur.execute("DELETE FROM scheduled_events WHERE id = %s", (scheduled_id,))
    db_conn.commit()

    assert linked != newer


def test_unknown_source_slug_is_rejected(db_conn) -> None:  # noqa: ANN001
    with pytest.raises(ValueError, match="Kaynak bulunamadı"):
        add_scheduled(title="pytest", expected_at=datetime.now(UTC), source_slug="yok-boyle")


# ------------------------------------------------------------------ B-53
def test_same_thread_threshold_never_falls_below_clustering() -> None:
    """`same_thread` eşiği kümeleme T_HIGH'ının altına düşemez.

    Bu bir stil tercihi değil, F2-17'nin tanımı: `same_thread` adayı,
    **kümelenecek kadar benzeyen ama zaman penceresi yüzünden
    kümelenemeyen** olaydır. Eşik T_HIGH'ın altına düşerse modül "aynı
    olay bile sayılmayacak kadar farklı" olayları geçmiş diye bağlar.

    Gerçek olay (B-53 canlı koşumu): sabit 0,80 idi — Spec §11.4'ün eski
    T_HIGH tahminine (0,86) göre yazılmış, F2-14 eşikleri 0,92/0,88'e
    kalibre ederken güncellenmemişti. Hashing embedder'la görünmüyordu;
    e5'e geçince 9 olay 22 bağ üretti ("Ulaştırma yatırımı" ↔ "AR-GE
    harcaması" 0,884). Bu test o sessiz kaymayı imkânsız kılar.
    """
    from politikdesk.config import Settings
    from politikdesk.context.related import same_thread_min_similarity

    assert same_thread_min_similarity() >= Settings().cluster_t_high
