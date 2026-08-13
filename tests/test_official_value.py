"""F5-19 — R3'ün `verified_against_source` bayrağı (Spec §8.3).

**R3 TEK KAYNAĞA 🟢 verir** — ürünün en güçlü etiketi. Bu yüzden buradaki
testlerin çoğu "çalışıyor mu"yu değil, **"yanlışlıkla tetiklenmiyor mu"**yu
kovalar. Gevşek bir doğrulama, kanıt motorunun en çok güvendiği kaynağa
yalan söyletir.

Bulunan arıza: bayrağı hiçbir şey yazmıyordu. `evidence/pipeline.py`
`normalized_value.verified_against_source` alanını okuyordu ama iddia
çıkarımının JSON şeması böyle bir alanı KABUL ETMİYOR (ve etmemeli —
Spec §8.1: kanıt durumuna dair yargı LLM çıktısı olamaz). Yani R3
üretimde ölü koddu ve bu, resmî sayısal kaynak olmadığı için (B-42)
Faz 5'e kadar görünmedi.

Doğrulama artık iki BAĞIMSIZ yolun buluşmasıdır: kurumun makine okunur
yayını (`articles.official_value`) ile modelin metinden çıkarımı.
"""

from __future__ import annotations

import json

import pytest

from politikdesk.evidence.pipeline import _same_number, _verified_against_official

pytestmark = pytest.mark.db

TEST_SLUG = "pytest-official-src"
DIM = 1024

OFFICIAL = {"metric": "unemployment_rate", "value": 7.6, "unit": "%", "period": "2026-06"}


def _vec(seed: float) -> str:
    return "[" + ",".join(f"{seed + i * 1e-4:.6f}" for i in range(DIM)) + "]"


@pytest.fixture()
def fixtures(db_conn):  # noqa: ANN001, ANN201
    """Resmî değeri olan bir makale + ona bağlı bir iddia kurar."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sources (name, slug, tier, kind, access_method,
                                 tos_status, independence_group)
            VALUES ('Pytest TUIK', %s, 1, 'official', 'api', 'allowed', 'pytest-official')
            ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            (TEST_SLUG,),
        )
        source_id = cur.fetchone()["id"]

        cur.execute(
            """
            INSERT INTO events (title, vertical, centroid_embedding,
                                first_reported_at, last_update_at, article_count)
            VALUES ('pytest resmi deger olayi', 'macro_economy', %s::vector,
                    now(), now(), 1)
            RETURNING id
            """,
            (_vec(0.3),),
        )
        event_id = cur.fetchone()["id"]

        cur.execute(
            """
            INSERT INTO articles (source_id, canonical_url, title, content_hash,
                                  embedding, event_id, published_at, official_value)
            VALUES (%s, 'https://pytest.test/official/1', 'pytest resmi', 'hash-official-1',
                    %s::vector, %s, now(), %s::jsonb)
            RETURNING id
            """,
            (source_id, _vec(0.3), event_id, json.dumps(OFFICIAL)),
        )
        article_id = cur.fetchone()["id"]
    db_conn.commit()

    yield {"event": event_id, "article": article_id, "source": source_id}

    with db_conn.cursor() as cur:
        cur.execute(
            "DELETE FROM evidence WHERE claim_id IN "
            "(SELECT id FROM claims WHERE event_id = %s)", (event_id,),
        )
        cur.execute("DELETE FROM claims WHERE event_id = %s", (event_id,))
        cur.execute("DELETE FROM articles WHERE source_id = %s", (source_id,))
        cur.execute("DELETE FROM events WHERE id = %s", (event_id,))
        cur.execute("DELETE FROM sources WHERE id = %s", (source_id,))
    db_conn.commit()


def _claim_with_evidence(db_conn, fixtures, normalized: dict | None) -> int:  # noqa: ANN001
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO claims (event_id, claim_text, claim_type, normalized_value,
                                evidence_status, status_reason)
            VALUES (%s, 'pytest sayisal iddia', 'number', %s::jsonb, 'unverified',
                    '{"rule": "pending"}'::jsonb)
            RETURNING id
            """,
            (fixtures["event"],
             json.dumps(normalized) if normalized is not None else None),
        )
        claim_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO evidence (claim_id, article_id, stance, quote_span, extracted_by)
            VALUES (%s, %s, 'supports', 'alinti', 'test+claims.v2')
            """,
            (claim_id, fixtures["article"]),
        )
    db_conn.commit()
    return claim_id


def _verified(db_conn, claim_id: int, normalized: dict | None) -> bool:  # noqa: ANN001
    with db_conn.cursor() as cur:
        return _verified_against_official(cur, claim_id, normalized)


# ------------------------------------------------------------ tetiklenir
def test_exact_match_verifies(db_conn, fixtures) -> None:  # noqa: ANN001
    """Metric + value + period üçü de tutuyorsa bayrak kalkar."""
    value = dict(OFFICIAL)
    claim_id = _claim_with_evidence(db_conn, fixtures, value)
    assert _verified(db_conn, claim_id, value) is True


def test_float_noise_still_verifies(db_conn, fixtures) -> None:  # noqa: ANN001
    """`7.5999999999` ile `7.6` aynı sayıdır; kuyruk basamak doğrulamayı bozmaz."""
    value = {**OFFICIAL, "value": 7.5999999999}
    claim_id = _claim_with_evidence(db_conn, fixtures, value)
    assert _verified(db_conn, claim_id, value) is True


# --------------------------------------------------- YANLIŞLIKLA tetiklenmez
@pytest.mark.parametrize(
    ("bozulan", "deger"),
    [
        ("value", 8.4),                    # farklı sayı
        ("period", "2026-05"),             # farklı dönem
        ("metric", "employment_rate"),     # farklı gösterge
    ],
)
def test_partial_match_does_not_verify(db_conn, fixtures, bozulan, deger) -> None:  # noqa: ANN001
    """Kısmi eşleşme doğrulama DEĞİLDİR.

    Aynı metriğin farklı dönemi ya da farklı metriğin aynı değeri, R3'ün
    aradığı şey değildir. Biri bile tutmuyorsa iddia normal kurallara
    tabidir ve 🟢 alamaz.
    """
    value = {**OFFICIAL, bozulan: deger}
    claim_id = _claim_with_evidence(db_conn, fixtures, value)
    assert _verified(db_conn, claim_id, value) is False


def test_claim_without_normalized_value_does_not_verify(db_conn, fixtures) -> None:  # noqa: ANN001
    claim_id = _claim_with_evidence(db_conn, fixtures, None)
    assert _verified(db_conn, claim_id, None) is False


def test_article_without_official_value_does_not_verify(db_conn, fixtures) -> None:  # noqa: ANN001
    """Resmî değeri olmayan makale doğrulama sağlayamaz.

    Bir medya haberi aynı sayıyı yazmış olabilir; bu, kurumun kendi
    yayınıyla doğrulama değildir ve R3'ü tetiklememelidir.
    """
    with db_conn.cursor() as cur:
        cur.execute(
            "UPDATE articles SET official_value = NULL WHERE id = %s",
            (fixtures["article"],),
        )
    db_conn.commit()

    value = dict(OFFICIAL)
    claim_id = _claim_with_evidence(db_conn, fixtures, value)
    assert _verified(db_conn, claim_id, value) is False


def test_contradicting_evidence_does_not_verify(db_conn, fixtures) -> None:  # noqa: ANN001
    """Yalnızca DESTEKLEYEN kanıt doğrulama sağlar.

    İddiayı çürüten bir makalenin resmî değeri, o iddiayı doğrulamaz.
    """
    value = dict(OFFICIAL)
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO claims (event_id, claim_text, claim_type, normalized_value,
                                evidence_status, status_reason)
            VALUES (%s, 'pytest celisen', 'number', %s::jsonb, 'unverified',
                    '{"rule": "pending"}'::jsonb)
            RETURNING id
            """,
            (fixtures["event"], json.dumps(value)),
        )
        claim_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO evidence (claim_id, article_id, stance, quote_span, extracted_by)
            VALUES (%s, %s, 'contradicts', 'alinti', 'test+claims.v2')
            """,
            (claim_id, fixtures["article"]),
        )
    db_conn.commit()

    assert _verified(db_conn, claim_id, value) is False


# ------------------------------------------------------------ sayı eşitliği
@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (48.9, 48.89999999999999, True),
        (7.6, 7.6, True),
        (48.9, 49.0, False),
        (7.6, 8.4, False),
        (None, 7.6, False),
        ("abc", 7.6, False),
    ],
)
def test_same_number(left, right, expected) -> None:  # noqa: ANN001
    assert _same_number(left, right) is expected
