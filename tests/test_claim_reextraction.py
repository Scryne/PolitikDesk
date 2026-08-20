"""F5-16 / F5-17 — yukarıdaki aşama değişince aşağıdaki aşama yeniden koşar.

İki ayrı hata, tek bir yapısal körlük: bir aşama durumu değiştiriyor,
bir sonraki aşama bunu bilmiyor. İkisi birlikte çapraz teyidi imkânsız
kılıyordu ve ikisi de "kaynak yok" diye yanlış teşhis edilebilirdi.

  F5-16  Olaya yeni makale katıldı -> iddia çıkarımı yeniden koşmalı
  F5-17  İddiaya yeni kanıt bağı geldi -> kanıt motoru yeniden puanlamalı

F5-16 tek başına düzeltilseydi çapraz teyit veritabanında oluşur ama
ekranda hâlâ 🟠 `single_source` yazardı.

---

F5-16 — olaya yeni kaynak katıldığında iddia çıkarımı yeniden koşar.

Düzeltilen hata, ürünün ana vaadini sessizce imkânsız kılıyordu ve
B-79 ile aynı aileden:

    PENDING_EVENTS_SQL'deki `NOT EXISTS (claims)` bir AND dalıydı ve
    iddiası olan HER olayı listeden çıkarıyordu. Yanındaki
    `last_update_at > claims_attempted_at` koşulu böylece ölü koddu.

Teyit doğası gereği "önce bir kaynak yazar, sonra diğerleri" diye
oluşur. İkinci bağımsız kaynağın makalesi mevcut bir olaya katıldığında
o makale hiç okunmuyor, kanıt bağı hiç kurulmuyor, `independent_count`
1'i geçemiyordu. Yani hiçbir iddia 🟡/🟢 olamıyordu.

Bu dosyadaki testler eski davranış geri konulduğunda KIRMIZIYA döner.

Testler kendi verisini kurar ve siler; mevcut kayıtlara dokunmaz.
"""

from __future__ import annotations

import pytest

from politikdesk.nlp.claims import ExtractedClaim
from politikdesk.nlp.claims_pipeline import (
    MAX_CLAIM_ATTEMPTS,
    _persist,
    pending_events,
)

pytestmark = pytest.mark.db

TEST_SLUG = "pytest-reextract-src"
DIM = 1024


def _vec(seed: float) -> str:
    return "[" + ",".join(f"{seed + i * 1e-4:.6f}" for i in range(DIM)) + "]"


@pytest.fixture()
def fixtures(db_conn):  # noqa: ANN001, ANN201
    """İki kaynak (ayrı bağımsızlık grubu) ve üç boş olay kurar."""
    with db_conn.cursor() as cur:
        source_ids: list[int] = []
        for n in (1, 2):
            cur.execute(
                """
                INSERT INTO sources (name, slug, tier, kind, access_method,
                                     tos_status, independence_group)
                VALUES (%s, %s, 3, 'media', 'rss', 'allowed', %s)
                ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                (f"Pytest Kaynak {n}", f"{TEST_SLUG}-{n}", f"pytest-group-{n}"),
            )
            source_ids.append(cur.fetchone()["id"])

        event_ids: list[int] = []
        for n in range(3):
            cur.execute(
                """
                INSERT INTO events (title, vertical, centroid_embedding,
                                    first_reported_at, last_update_at, article_count)
                VALUES (%s, 'macro_economy', %s::vector, now(), now(), 1)
                RETURNING id
                """,
                (f"pytest reextract olay {n}", _vec(0.2 * (n + 1))),
            )
            event_ids.append(cur.fetchone()["id"])

        article_ids: list[int] = []
        for i, (event_id, source_id) in enumerate(
            [
                (event_ids[0], source_ids[0]),
                (event_ids[0], source_ids[1]),
                (event_ids[1], source_ids[0]),
                (event_ids[2], source_ids[0]),
            ]
        ):
            cur.execute(
                """
                INSERT INTO articles (source_id, canonical_url, title, content_hash,
                                      embedding, event_id, published_at)
                VALUES (%s, %s, %s, %s, %s::vector, %s, now())
                RETURNING id
                """,
                (
                    source_id,
                    f"https://pytest.test/reextract/{i}",
                    f"pytest reextract makale {i}",
                    f"hash-reextract-{i}",
                    _vec(0.2 * (i + 1)),
                    event_id,
                ),
            )
            article_ids.append(cur.fetchone()["id"])
    db_conn.commit()

    yield {"events": event_ids, "articles": article_ids, "sources": source_ids}

    with db_conn.cursor() as cur:
        cur.execute(
            "DELETE FROM evidence WHERE claim_id IN "
            "(SELECT id FROM claims WHERE event_id = ANY(%s))",
            (event_ids,),
        )
        cur.execute("DELETE FROM claims WHERE event_id = ANY(%s)", (event_ids,))
        cur.execute("DELETE FROM articles WHERE source_id = ANY(%s)", (source_ids,))
        cur.execute("DELETE FROM events WHERE id = ANY(%s)", (event_ids,))
        cur.execute("DELETE FROM sources WHERE id = ANY(%s)", (source_ids,))
    db_conn.commit()


def _add_claim(db_conn, event_id: int) -> int:  # noqa: ANN001
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO claims (event_id, claim_text, claim_type,
                                evidence_status, status_reason)
            VALUES (%s, 'pytest iddia', 'fact', 'unverified',
                    '{"rule": "pending"}'::jsonb)
            RETURNING id
            """,
            (event_id,),
        )
        claim_id = cur.fetchone()["id"]
    db_conn.commit()
    return claim_id


def _stamp(
    db_conn,
    event_id: int,
    *,
    attempted_ago: str,
    updated_ago: str,  # noqa: ANN001
    attempts: int = 1,
) -> None:
    """Deneme ve güncelleme damgalarını göreli olarak kurar."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE events
            SET claims_attempted_at = now() - %s::interval,
                last_update_at      = now() - %s::interval,
                claims_attempt_count = %s
            WHERE id = %s
            """,
            (attempted_ago, updated_ago, attempts, event_id),
        )
    db_conn.commit()


# --------------------------------------------------------------- pending
def test_event_with_claims_is_pending_when_new_article_arrives(db_conn, fixtures):  # noqa: ANN001
    """ASIL REGRESYON: iddiası olan olay, YENİ makale gelince yeniden sıraya girer.

    Eski kodda `NOT EXISTS (claims)` bu olayı listeden tamamen çıkarıyor
    ve ikinci bağımsız kaynağın kanıt bağı hiç kurulmuyordu.
    """
    event_id = fixtures["events"][0]
    _add_claim(db_conn, event_id)
    # Çıkarım 2 saat önce koştu, yeni makale 1 saat önce katıldı.
    _stamp(db_conn, event_id, attempted_ago="2 hours", updated_ago="1 hour")

    assert event_id in pending_events(limit=500), (
        "Olaya yeni makale katıldı ama yeniden çıkarım sıraya girmedi — "
        "ikinci kaynağın kanıt bağı hiç kurulmaz, çapraz teyit imkânsız olur."
    )


def test_event_with_claims_is_not_pending_without_new_material(db_conn, fixtures):  # noqa: ANN001
    """Yeni malzeme yoksa iddiası olan olay yeniden çıkarılmaz (LLM israfı)."""
    event_id = fixtures["events"][1]
    _add_claim(db_conn, event_id)
    # Çıkarım güncellemeden SONRA koştu.
    _stamp(db_conn, event_id, attempted_ago="1 hour", updated_ago="2 hours")

    assert event_id not in pending_events(limit=500)


def test_empty_event_stops_retrying_at_attempt_cap(db_conn, fixtures):  # noqa: ANN001
    """F4-05 korunuyor: sıfır iddia dönen olay sonsuza dek denenmez.

    13 Ağustos'ta üç olay 28 saat boyunca her 10 dakikada bir LLM'e
    gönderilmişti. F5-16 o korumayı gevşetmemelidir.
    """
    event_id = fixtures["events"][2]  # iddiası YOK
    _stamp(
        db_conn,
        event_id,
        attempted_ago="1 hour",
        updated_ago="2 hours",
        attempts=MAX_CLAIM_ATTEMPTS,
    )

    assert event_id not in pending_events(limit=500)


# --------------------------------------------------------------- persist
def test_reextraction_adds_evidence_link_without_duplicating_claim(db_conn, fixtures):  # noqa: ANN001
    """Yeniden çıkarım aynı iddiayı ikinci kez YAZMAZ, kanıt bağı EKLER.

    Mükerrer yazsaydı kanıt bağları iki kayda bölünür, `independent_count`
    her ikisinde de düşük kalırdı — düzeltme kendini boşa çıkarırdı.
    """
    event_id = fixtures["events"][0]
    first_article, second_article = fixtures["articles"][0], fixtures["articles"][1]
    claim = ExtractedClaim(
        claim_text="TCMB rezervleri 178,4 milyar dolara yukseldi",
        claim_type="fact",
        quote_span="rezervler 178,4 milyar dolar",
    )

    with db_conn.cursor() as cur:
        # 1. tur: yalnız ilk kaynak
        _persist(cur, event_id, [(claim, [(first_article, "ilk alinti")])], "test+claims.v2")
        db_conn.commit()

        # 2. tur: olaya ikinci bağımsız kaynak katıldı, çıkarım YENİDEN koşar
        # ve aynı iddiayı bu kez İKİ makaleyle üretir.
        _persist(
            cur,
            event_id,
            [(claim, [(first_article, "ilk alinti"), (second_article, "ikinci alinti")])],
            "test+claims.v2",
        )
        db_conn.commit()

        cur.execute("SELECT count(*) AS n FROM claims WHERE event_id = %s", (event_id,))
        claim_count = cur.fetchone()["n"]
        cur.execute(
            """
            SELECT count(*) AS n FROM evidence
            WHERE claim_id IN (SELECT id FROM claims WHERE event_id = %s)
            """,
            (event_id,),
        )
        evidence_count = cur.fetchone()["n"]

    assert claim_count == 1, f"iddia mukerrer yazildi ({claim_count} kayit)"
    assert evidence_count == 2, (
        f"ikinci kaynagin kanit bagi kurulmadi ({evidence_count} bag) — "
        "independent_count yukselemez"
    )


# ---------------------------------------------------------------- F5-17
def test_new_evidence_link_retriggers_scoring(db_conn, fixtures):  # noqa: ANN001
    """İDDİAYA YENİ KANIT BAĞI GELİNCE DURUM YENİDEN HESAPLANIR.

    `evidence_status` kanıt kümesinin fonksiyonudur ve o küme sonradan
    büyür. Eski kodda durum bir kez hesaplandıktan sonra iddia listeden
    düşüyordu: ikinci bağımsız kaynak bağlansa bile ekranda 🟠
    `single_source` kalıyordu.

    Eski davranış geri konulduğunda bu test KIRMIZIYA döner.
    """
    from politikdesk.evidence.pipeline import score_claims

    event_id = fixtures["events"][0]
    first_article, second_article = fixtures["articles"][0], fixtures["articles"][1]
    claim = ExtractedClaim(
        claim_text="Rezervler 178,4 milyar dolara yukseldi",
        claim_type="fact",
        quote_span="rezervler 178,4 milyar dolar",
    )

    with db_conn.cursor() as cur:
        _persist(cur, event_id, [(claim, [(first_article, "ilk alinti")])], "test+claims.v2")
    db_conn.commit()

    score_claims(limit=500)

    with db_conn.cursor() as cur:
        cur.execute("SELECT id, evidence_status FROM claims WHERE event_id = %s", (event_id,))
        row = cur.fetchone()
        claim_id, first_status = row["id"], row["evidence_status"]

        # Tek kaynak -> 🟠. Bu, düzeltmenin ölçüldüğü başlangıç noktasıdır.
        assert first_status == "single_source", first_status

        # İkinci BAĞIMSIZ kaynak aynı iddiayı doğruluyor.
        _persist(
            cur,
            event_id,
            [(claim, [(first_article, "ilk alinti"), (second_article, "ikinci alinti")])],
            "test+claims.v2",
        )
    db_conn.commit()

    score_claims(limit=500)

    with db_conn.cursor() as cur:
        cur.execute("SELECT evidence_status FROM claims WHERE id = %s", (claim_id,))
        final_status = cur.fetchone()["evidence_status"]

    assert final_status == "partially_corroborated", (
        f"yeni kanit bagi geldigi halde durum '{final_status}' kaldi — "
        "capraz teyit veritabaninda olusuyor ama urune yansimiyor"
    )


# ---------------------------------------------------------------- F5-18
def test_database_rejects_duplicate_claim_signature(db_conn, fixtures):  # noqa: ANN001
    """Aynı olayda aynı imza İKİ KEZ yazılamaz — kısıt veritabanında.

    Python tarafındaki "zaten var mı" kontrolü yarışta YETMEZ: iki süreç
    de "yok" görüp ikisi de yazabilir. 13 Ağustos'ta ölçülen buydu —
    124 iddianın 9'u mükerrerdi ve çiftler 20-30 saniye arayla yazılmıştı.

    Mükerrerliğin zararı, düzeltmeye çalıştığımız yerin tam kalbinde:
    kanıt bağları iki satıra bölünür, `independent_count` hiçbirinde
    eşiğe ulaşmaz, çapraz teyit sessizce çöker (B-79 / F5-16 ile aynı
    sonuç, farklı yol).
    """
    import psycopg

    event_id = fixtures["events"][1]

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO claims (event_id, claim_text, claim_type, evidence_status,
                                status_reason, claim_signature)
            VALUES (%s, 'pytest mukerrer', 'fact', 'unverified',
                    '{"rule": "pending"}'::jsonb, 'fact:pytest mukerrer imza')
            """,
            (event_id,),
        )
    db_conn.commit()

    # İkinci süreç aynı imzayı yazmayı denerse veritabanı reddeder.
    with db_conn.cursor() as cur, pytest.raises(psycopg.errors.UniqueViolation):
        cur.execute(
            """
            INSERT INTO claims (event_id, claim_text, claim_type, evidence_status,
                                status_reason, claim_signature)
            VALUES (%s, 'pytest mukerrer', 'fact', 'unverified',
                    '{"rule": "pending"}'::jsonb, 'fact:pytest mukerrer imza')
            """,
            (event_id,),
        )
    db_conn.rollback()


# ════════════════════ denemenin SONUCU kaydedilir (migration 0021)
#
# Denetimde ölçüldü: tavana vurmuş ve hâlâ iddiasız 430 olay (%21).
# Bunların ne kadarının MEŞRU ("metinde iddia yok") ne kadarının GERÇEK
# KAYIP (şema/ayrıştırma arızası) olduğu veriyle cevaplanamıyordu —
# iki yol da aynı sayaca yazıyor, fark yalnızca dönen logda kalıyordu.


def _outcome(db_conn, event_id: int) -> str | None:  # noqa: ANN001
    with db_conn.cursor() as cur:
        cur.execute("SELECT claims_last_outcome FROM events WHERE id = %s", (event_id,))
        return cur.fetchone()["claims_last_outcome"]


def test_successful_extraction_is_recorded_as_ok(db_conn, fixtures):  # noqa: ANN001
    from politikdesk.nlp.claims_pipeline import _record_attempt

    event_id = fixtures["events"][0]
    with db_conn.cursor() as cur:
        _record_attempt(cur, event_id, "ok")
    db_conn.commit()

    assert _outcome(db_conn, event_id) == "ok"


def test_legitimate_empty_extraction_is_distinguishable_from_failure(db_conn, fixtures):  # noqa: ANN001
    """**Turun asıl kazanımı:** `empty` ile arıza artık AYRI kayıtlar.

    İkisi de olayı iddiasız bırakır ve ikisi de sayacı ilerletir, ama
    epistemik anlamları zıttır: `empty` doğru cevaptır, `SchemaValidationError`
    kayıptır. Ayrım olmadan "%21 iddiasız" sayısı yorumlanamaz.
    """
    from politikdesk.nlp.claims_pipeline import _record_attempt

    bos, arizali = fixtures["events"][0], fixtures["events"][1]
    with db_conn.cursor() as cur:
        _record_attempt(cur, bos, "empty")
        _record_attempt(cur, arizali, "SchemaValidationError")
    db_conn.commit()

    assert _outcome(db_conn, bos) == "empty"
    assert _outcome(db_conn, arizali) == "SchemaValidationError"
    assert _outcome(db_conn, bos) != _outcome(db_conn, arizali)


def test_outcome_does_not_disturb_the_attempt_counter(db_conn, fixtures):  # noqa: ANN001
    """Sonuç kaydı F4-05'in tavan mantığını GEVŞETMEZ."""
    from politikdesk.nlp.claims_pipeline import _record_attempt

    event_id = fixtures["events"][2]
    _stamp(db_conn, event_id, attempted_ago="1 hour", updated_ago="2 hours", attempts=1)
    with db_conn.cursor() as cur:
        _record_attempt(cur, event_id, "SchemaValidationError")
    db_conn.commit()

    with db_conn.cursor() as cur:
        cur.execute("SELECT claims_attempt_count n FROM events WHERE id = %s", (event_id,))
        assert cur.fetchone()["n"] == 2, "arıza da bir denemedir; sayaç ilerlemeli"


def test_new_material_resets_counter_and_overwrites_outcome(db_conn, fixtures):  # noqa: ANN001
    """Yeni makale geldiyse eski denemenin sonucu artık geçerli değildir."""
    from politikdesk.nlp.claims_pipeline import _record_attempt

    event_id = fixtures["events"][0]
    with db_conn.cursor() as cur:
        _record_attempt(cur, event_id, "SchemaValidationError")
    db_conn.commit()
    # Olaya yeni makale katıldı: last_update_at, denemeden SONRAYA taşınır.
    _stamp(db_conn, event_id, attempted_ago="2 hours", updated_ago="1 hour", attempts=3)

    with db_conn.cursor() as cur:
        _record_attempt(cur, event_id, "ok")
    db_conn.commit()

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT claims_attempt_count n, claims_last_outcome o FROM events WHERE id = %s",
            (event_id,),
        )
        row = cur.fetchone()
    assert row["n"] == 1, "yeni malzeme sayacı sıfırlar (F4-05)"
    assert row["o"] == "ok"


# ═══════ sağlayıcı arızası deneme hakkını YAKMAZ (20 Ağu 2026 denetimi)
#
# F4-05'in tavanı şu varsayıma dayanıyordu: "geçici bir sağlayıcı arızası
# bu pencerede düzelir; düzelmiyorsa sorun metinde." Varsayım ÖLÇÜLDÜ ve
# yanlış çıktı: tavana vurup iddiasız kalmış 430 olaydan 25'lik rastgele
# örneğin **%92'si** bugün yeniden denendiğinde iddia ÜRETTİ. Kayıp
# metinden değil, saatlerce süren 429 fırtınasından geliyordu.


def test_provider_failure_does_not_burn_the_attempt_budget(db_conn, fixtures):  # noqa: ANN001
    """**Asıl regresyon.** 429 üç hakkı da yakıyordu ve olay bırakılıyordu."""
    from politikdesk.nlp.claims_pipeline import _record_transient

    event_id = fixtures["events"][0]
    _stamp(db_conn, event_id, attempted_ago="1 hour", updated_ago="2 hours", attempts=2)

    with db_conn.cursor() as cur:
        _record_transient(cur, event_id, "LLMHTTPError")
    db_conn.commit()

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT claims_attempt_count n, claims_last_outcome o FROM events WHERE id = %s",
            (event_id,),
        )
        row = cur.fetchone()
    assert row["n"] == 2, "sağlayıcı arızası hak yakmamalı — metin hakkında bilgi vermiyor"
    assert row["o"] == "LLMHTTPError", "yine de KAYDEDİLMELİ, yoksa ölçülemez"


def test_event_stays_in_queue_after_a_provider_failure(db_conn, fixtures):  # noqa: ANN001
    """Sağlayıcı düzeldiğinde olay hâlâ sırada olmalı."""
    from politikdesk.nlp.claims_pipeline import _record_transient

    event_id = fixtures["events"][1]
    _stamp(db_conn, event_id, attempted_ago="1 hour", updated_ago="2 hours", attempts=2)
    with db_conn.cursor() as cur:
        _record_transient(cur, event_id, "ReadTimeout")
    db_conn.commit()

    assert event_id in pending_events(limit=500), (
        "Sağlayıcı arızasından sonra olay kuyruktan düştü — kalıcı kayıp yolu açık."
    )


def test_provider_failure_still_advances_the_timestamp(db_conn, fixtures):  # noqa: ANN001
    """Damga ilerlemezse patlayan olay her turu baştan tıkar (F4-05)."""
    from politikdesk.nlp.claims_pipeline import _record_transient

    event_id = fixtures["events"][2]
    _stamp(db_conn, event_id, attempted_ago="5 hours", updated_ago="9 hours", attempts=1)
    with db_conn.cursor() as cur:
        _record_transient(cur, event_id, "LLMHTTPError")
    db_conn.commit()

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT now() - claims_attempted_at < interval '1 minute' AS taze "
            "FROM events WHERE id = %s",
            (event_id,),
        )
        assert cur.fetchone()["taze"] is True


@pytest.mark.parametrize(
    ("exc", "gecici"),
    [
        ("LLMHTTPError", True),  # 429 / 503 — sağlayıcı
        ("BudgetExceeded", True),  # bütçe tavanı — metin değil
        ("ReadTimeout", True),
        ("ConnectError", True),
        ("SoftTimeLimitExceeded", True),
        ("SchemaValidationError", False),  # modelin BU METNE yanıtı
        ("LLMRefusal", False),  # modelin BU METNİ reddi
        ("ValueError", False),
    ],
)
def test_failure_classification(exc: str, gecici: bool) -> None:
    """Taşıma arızası ile içerik arızası ayrımı — tavanın konusu ikincisidir."""
    from politikdesk.llm.errors import (
        BudgetExceeded,
        LLMHTTPError,
        LLMRefusal,
        SchemaValidationError,
    )
    from politikdesk.nlp.claims_pipeline import _is_transient

    ornekler: dict[str, BaseException] = {
        "LLMHTTPError": LLMHTTPError(429, "Too Many Requests"),
        "BudgetExceeded": BudgetExceeded("gunluk", 1.0, 0.5),
        "ReadTimeout": type("ReadTimeout", (Exception,), {})(),
        "ConnectError": type("ConnectError", (Exception,), {})(),
        "SoftTimeLimitExceeded": type("SoftTimeLimitExceeded", (Exception,), {})(),
        "SchemaValidationError": SchemaValidationError("gecersiz JSON"),
        "LLMRefusal": LLMRefusal("policy"),
        "ValueError": ValueError("x"),
    }
    assert _is_transient(ornekler[exc]) is gecici
