"""F0-15 — veri şeması testleri.

DoD: "Tüm tablolar + indeksler + kısıtlar oluşuyor; editorial_profiles'ta
ideolojik alan yok (test ile doğrulanıyor)."

İki katman:
  * Statik testler — migration SQL metnini denetler, DB gerektirmez
  * @pytest.mark.db  — gerçek şemayı information_schema üzerinden denetler
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

MIGRATION = (MIGRATIONS_DIR / "0001_initial.sql").read_text(encoding="utf-8")

# Tüm migration'ların birleşimi — sonraki dosyalarda değişen kısıtlar için.
ALL_MIGRATIONS = "\n".join(
    p.read_text(encoding="utf-8") for p in sorted(MIGRATIONS_DIR.glob("*.sql"))
)

EXPECTED_TABLES = {
    "users",
    "sources",
    "articles",
    "events",
    "claims",
    "evidence",
    "entities",
    "event_entities",
    "article_entities",
    "event_relations",
    "scheduled_events",
    "drafts",
    "editorial_profiles",
    "audit_log",
    "metrics",
    "llm_calls",
}

# Faz 3'te (0004) eklenen tablolar. 0001'de tanımlı olmadıkları için
# `test_all_expected_tables_are_defined` onları aramaz; canlı şema
# testi ikisinin birleşimine bakar.
PHASE3_TABLES = {"briefings", "event_feedback", "user_activity"}

# P6 / KVKK m.6 — bu sözcükleri içeren bir sütun editorial_profiles'ta olamaz.
FORBIDDEN_PROFILE_TERMS = (
    "ideolog",
    "ideolo",
    "political",
    "politik",
    "siyasi",
    "parti",
    "party",
    "partisan",
    "leaning",
    "bias",
    "religion",
    "din_",
    "ethnic",
    "etnik",
    "vote",
    "oy_",
    "orientation",
)


# --------------------------------------------------------------------------
# Statik denetimler (DB gerektirmez)
# --------------------------------------------------------------------------
def test_all_expected_tables_are_defined() -> None:
    defined = set(re.findall(r"CREATE TABLE (\w+)", MIGRATION))
    missing = EXPECTED_TABLES - defined
    assert not missing, f"Migration'da eksik tablolar: {sorted(missing)}"


def test_embedding_dimension_is_1024() -> None:
    """Spec §11.1: boyut 1024'e sabitlendi (D16 benchmark'ı bu boyutu doğrular)."""
    vectors = re.findall(r"VECTOR\((\d+)\)", MIGRATION)
    assert vectors, "VECTOR sütunu bulunamadı"
    assert set(vectors) == {"1024"}, f"Beklenmeyen embedding boyutu: {set(vectors)}"


def test_excerpt_length_constraint_exists() -> None:
    """Spec §9.3 / D13: alıntı azami 300 karakter."""
    assert "char_length(excerpt) <= 300" in MIGRATION


def test_quote_span_length_constraint_exists() -> None:
    """Spec §7.3: kanıt alıntısı azami 200 karakter."""
    assert "char_length(quote_span) <= 200" in MIGRATION


def test_no_full_text_column() -> None:
    """Spec §9.3: tam metin hiçbir alanda saklanmaz."""
    columns = re.findall(r"^\s{2}(\w+)\s+TEXT", MIGRATION, flags=re.MULTILINE)
    banned = {"body_text", "full_text", "content", "article_body", "raw_text", "html"}
    found = banned & set(columns)
    assert not found, f"Tam metin saklayan sütun bulundu: {sorted(found)}"


def test_evidence_status_enum_matches_spec() -> None:
    """Spec §8.1'deki beş kategorik durum, ne eksik ne fazla."""
    block = re.search(
        r"evidence_status\s+TEXT\s+NOT NULL\s+CHECK \(evidence_status IN \((.*?)\)\)",
        MIGRATION,
        flags=re.DOTALL,
    )
    assert block, "evidence_status CHECK kısıtı bulunamadı"
    values = set(re.findall(r"'(\w+)'", block.group(1)))
    assert values == {
        "strongly_corroborated",
        "partially_corroborated",
        "single_source",
        "contradicted",
        "unverified",
    }


def test_prediction_claims_forced_unverified() -> None:
    """Spec §8.3 R0: tahmin tipi iddia HER ZAMAN unverified.

    R0 kural motorunun ilk bloğudur (kanıt kurallarından önce, kısa devre);
    bu CHECK onun ikinci savunma hattıdır.
    """
    assert "claims_prediction_always_unverified" in MIGRATION


def test_salience_score_is_capped_at_global_range() -> None:
    """Spec §8.4 (v3.1): saklanan skor GLOBAL kısımdır — üst sınır 90.

    Kişisel bileşen (0-10) bu sütuna yazılamaz; yazılırsa 90 üstü değer
    üretilir ve DB reddeder. B-34 / İtiraz-7.
    """
    assert "DROP CONSTRAINT events_salience_score_check" in ALL_MIGRATIONS, (
        "0001'in 0-100 kısıtı kaldırılmamış"
    )
    assert "events_salience_global_range" in ALL_MIGRATIONS
    assert "salience_score BETWEEN 0 AND 90" in ALL_MIGRATIONS


def test_editorial_profiles_has_no_ideological_column_in_sql() -> None:
    """P6 / KVKK m.6 — statik kontrol (DB olmadan da koşar)."""
    block = re.search(r"CREATE TABLE editorial_profiles \((.*?)\n\);", MIGRATION, flags=re.DOTALL)
    assert block, "editorial_profiles tanımı bulunamadı"
    body = block.group(1).lower()
    hits = [term for term in FORBIDDEN_PROFILE_TERMS if term in body]
    assert not hits, (
        f"editorial_profiles'ta yasaklı terim(ler): {hits}. "
        "Bu tabloda ideolojik/siyasi sınıflandırma alanı bulunamaz (P6, KVKK m.6)."
    )


def test_no_truth_score_column() -> None:
    """Spec §15 madde 13: tek sayısal 'doğruluk yüzdesi' şemada yoktur."""
    lowered = ALL_MIGRATIONS.lower()
    for banned in ("truth_score", "accuracy_score", "confidence_score", "trust_score"):
        assert banned not in lowered, f"Yasak sütun: {banned}"


# --------------------------------------------------------------------------
# Faz 3 (0004) kısıtları
# --------------------------------------------------------------------------
def test_phase3_tables_are_defined() -> None:
    defined = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", ALL_MIGRATIONS))
    missing = PHASE3_TABLES - defined
    assert not missing, f"0004'te eksik tablolar: {sorted(missing)}"


def test_grounding_result_is_separate_from_check_result() -> None:
    """Kapı G3 koşul 2 yalnızca grounding'i sayar.

    İkisi tek JSONB'de birleştirilseydi, sert kapının ölçümü yumuşak
    editoryal kontrollerin gürültüsüne karışırdı.
    """
    assert "drafts ADD COLUMN IF NOT EXISTS grounding_result" in ALL_MIGRATIONS
    assert "check_result" in MIGRATION  # 0001'de zaten var


def test_event_feedback_has_no_score_column() -> None:
    """ "Bu yanlış" bir DÜZELTME sinyalidir, bir güvenilirlik skoru değil."""
    block = re.search(
        r"CREATE TABLE IF NOT EXISTS event_feedback \((.*?)\n\);",
        ALL_MIGRATIONS,
        flags=re.DOTALL,
    )
    assert block, "event_feedback tanımı bulunamadı"
    body = block.group(1).lower()
    for banned in ("score", "rating", "confidence", "accuracy", "trust"):
        assert banned not in body, f"event_feedback'te yasak alan: {banned}"


def test_user_activity_is_documented_as_non_ranking_input() -> None:
    """Spec §15 madde 14: etkileşim gündemi sıralayamaz.

    Kısıt SQL yorumunda yazılıdır; `tests/test_metrics.py` kod
    tarafındaki karşılığını (evidence/ bu tabloyu okumaz) denetler.
    """
    assert "GÜNDEM SIRALAMASINA GİRDİ OLAMAZ" in ALL_MIGRATIONS
    assert "COMMENT ON TABLE user_activity" in ALL_MIGRATIONS


@pytest.mark.db
def test_editorial_profiles_still_has_no_ideological_column_after_0004(
    db_conn,  # noqa: ANN001
) -> None:
    """0004 bu tabloya `compiler_version` ekledi — kısıt korunmalı."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'editorial_profiles'
            """
        )
        columns = [r["column_name"].lower() for r in cur.fetchall()]
    assert "compiler_version" in columns
    offenders = [c for c in columns if any(t in c for t in FORBIDDEN_PROFILE_TERMS)]
    assert not offenders, f"editorial_profiles'ta ideolojik sütun(lar): {offenders}"


@pytest.mark.db
def test_briefing_slot_constraint_is_enforced(db_conn) -> None:  # noqa: ANN001
    """Yalnızca sabah/akşam — üçüncü bir slot sessizce eklenemez."""
    import psycopg

    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM users ORDER BY id LIMIT 1")
        user = cur.fetchone()
    if user is None:
        pytest.skip("Kullanıcı kaydı yok.")

    with db_conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation):
        cur.execute(
            """
            INSERT INTO briefings (user_id, briefing_date, slot, body_html,
                                   body_text, open_token)
            VALUES (%s, '2026-01-01', 'noon', '<p></p>', '', 'test-token-slot')
            """,
            (user["id"],),
        )
    db_conn.rollback()


# --------------------------------------------------------------------------
# Canlı şema denetimleri (Postgres gerektirir)
# --------------------------------------------------------------------------
@pytest.mark.db
def test_all_tables_exist_in_database(db_conn) -> None:  # noqa: ANN001
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        actual = {r["table_name"] for r in cur.fetchall()}
    missing = (EXPECTED_TABLES | PHASE3_TABLES) - actual
    assert not missing, f"Veritabanında eksik tablolar: {sorted(missing)}"


@pytest.mark.db
def test_editorial_profiles_columns_are_stylistic_only(db_conn) -> None:  # noqa: ANN001
    """F0-15 DoD'un asıl testi: canlı şemada ideolojik alan yok."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'editorial_profiles'
            """
        )
        columns = [r["column_name"].lower() for r in cur.fetchall()]

    assert columns, "editorial_profiles tablosu bulunamadı"
    offenders = [c for c in columns if any(term in c for term in FORBIDDEN_PROFILE_TERMS)]
    assert not offenders, (
        f"editorial_profiles'ta ideolojik sütun(lar): {offenders}. "
        "Spec §10.1 ve KVKK m.6 uyarınca bu şema alanı bulunamaz."
    )


@pytest.mark.db
def test_pgvector_extension_installed(db_conn) -> None:  # noqa: ANN001
    with db_conn.cursor() as cur:
        cur.execute("SELECT 1 AS ok FROM pg_extension WHERE extname = 'vector'")
        assert cur.fetchone(), "pgvector eklentisi kurulu değil"


@pytest.mark.db
def test_hnsw_indexes_exist(db_conn) -> None:  # noqa: ANN001
    """Spec §11.1: pgvector HNSW ile ANN sorgusu (F1-14 buna dayanır)."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname='public' AND indexdef ILIKE '%USING hnsw%'"
        )
        names = {r["indexname"] for r in cur.fetchall()}
    assert "idx_articles_embedding_hnsw" in names
    assert "idx_events_centroid_hnsw" in names


@pytest.mark.db
def test_salience_global_range_is_enforced_by_database(db_conn) -> None:  # noqa: ANN001
    """Spec §8.4: kişisel bileşen saklanan sütuna sızarsa DB reddetmeli.

    Global azami 90'dır. 95 yazmaya çalışan bir kod yolu (ör. global +
    kişisel toplamını kaydeden bir hata) sessizce yanlış sıralama üretmek
    yerine CheckViolation ile durur.
    """
    import psycopg

    with db_conn.cursor() as cur, pytest.raises(psycopg.errors.CheckViolation):
        cur.execute(
            """
            INSERT INTO events (title, salience_score, first_reported_at, last_update_at)
            VALUES ('Salience siniri testi', 95, now(), now())
            """
        )
    db_conn.rollback()

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO events (title, salience_score, first_reported_at, last_update_at)
            VALUES ('Salience siniri testi', 90, now(), now())
            RETURNING salience_score
            """
        )
        assert cur.fetchone()["salience_score"] == 90
    db_conn.rollback()


@pytest.mark.db
def test_excerpt_constraint_is_enforced_by_database(db_conn) -> None:  # noqa: ANN001
    """Kısıt yorum değil: 301 karakterlik alıntı DB tarafından reddedilmeli."""
    import psycopg

    # Slug `pytest-` ile başlar ve kaynak PASİF eklenir. İkisi de bilinçli:
    #
    #   * `db_conn` fixture'ı `autocommit=True` ile bağlanır, yani
    #     aşağıdaki `db_conn.rollback()` bu satırı geri ALMAZ. Temizlik
    #     tamamen `conftest.isolate_database_state`'in id-su-seviyesi
    #     süpürgesine kalır; o da her hatayı yutar (`except: pass`).
    #     Bir kez kaçan satır KALICI olur.
    #   * 18 Ağustos 2026 denetiminde tam olarak bu görüldü: `test-excerpt-src`
    #     canlı veritabanında AKTİF bir Tier-1 kaynak olarak duruyordu,
    #     boru hattı onu 5 dakikada bir çekmeye çalışıyor ve kaynak sağlık
    #     panosunda kalıcı kırmızı gösteriyordu.
    #
    # `pytest-` öneki süpürgenin `DELETE FROM sources WHERE slug LIKE
    # 'pytest%'` satırına takılır; `is_active = false` ise kaçsa bile
    # toplayıcının o kaynağa hiç dokunmamasını garanti eder.
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sources "
            "(name, slug, tier, kind, access_method, tos_status, is_active) "
            "VALUES ('Test', 'pytest-excerpt-src', 1, 'official', "
            "'official_feed', 'allowed', false) "
            "ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, "
            "is_active = false RETURNING id"
        )
        source_id = cur.fetchone()["id"]

        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO articles (source_id, canonical_url, title, excerpt, content_hash)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (source_id, "https://example.test/too-long", "Test", "x" * 301, "hash"),
            )
    db_conn.rollback()


# ==================================================================== I9
@pytest.mark.db
def test_editorial_profile_v2_and_claims_v3_constraints_enforced_by_database(db_conn) -> None:  # noqa: ANN001
    """I9: 0009 ve 0010 migration kısıtları (quote_habit, promise, attribution_verified) veritabanında doğrulanır."""
    import psycopg

    with db_conn.cursor() as cur:
        # 1. 0009: editorial_profiles quote_habit ve uncertainty_handling
        cur.execute(
            """
            INSERT INTO editorial_profiles (
                user_id, tone, sentence_length, emoji_usage, hashtag_usage,
                citation_habit, formality, avoid_list, topic_priorities,
                quote_habit, uncertainty_handling, compiled_prompt, compiler_version
            ) VALUES (
                1, '{"analytical"}', 'medium', 'none', 'none',
                'always_link', 3, '{}', '{}',
                'direct_quote', 'natural_concise', 'prompt', 'v2'
            )
            ON CONFLICT (user_id) DO UPDATE SET
                quote_habit = EXCLUDED.quote_habit,
                uncertainty_handling = EXCLUDED.uncertainty_handling
            RETURNING quote_habit, uncertainty_handling
            """
        )
        row = cur.fetchone()
        assert row["quote_habit"] == "direct_quote"
        assert row["uncertainty_handling"] == "natural_concise"

        # 2. 0010: claims promise tipi
        cur.execute(
            """
            INSERT INTO events (title, status, first_reported_at, last_update_at)
            VALUES ('Vaat Test Olayi', 'developing', now(), now())
            RETURNING id
            """
        )
        event_id = cur.fetchone()["id"]

        cur.execute(
            """
            INSERT INTO claims (event_id, claim_type, claim_text, evidence_status, status_reason, normalized_value)
            VALUES (%s, 'promise', '2027 sonuna kadar enflasyon tek haneye inecek.', 'attribution_verified', '{"rule": "R8"}', NULL)
            RETURNING id, claim_type, evidence_status
            """,
            (event_id,),
        )
        c_row = cur.fetchone()
        assert c_row["claim_type"] == "promise"
        assert c_row["evidence_status"] == "attribution_verified"

        # Geçersiz claim_type reddedilmeli
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO claims (event_id, claim_type, claim_text, evidence_status, status_reason)
                VALUES (%s, 'invalid_type', 'Gecersiz iddia metni.', 'unverified', '{"rule": "R7"}')
                """,
                (event_id,),
            )
    db_conn.rollback()
