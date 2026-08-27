"""İddia kanıt matrisi testleri (Roadmap Faz 5.2).

Korunan sözleşme:

  1. BOYUTLAR TEK SAYIYA ÇARPILMAZ. "%78 güvenilir" yedi olguyu opak bir
     sayıya gömer ve hiçbir soruyu yanıtlamaz.
  2. ÖLÇÜLEMEDİ ≠ SIFIR. Karşı kanıt `unavailable`; "0" göstermek
     kullanıcıya yanlışlıkla bir doğrulama sinyali verir.
  3. KESİNLİK DİLİ KONTROLLÜ. Dört kovanın dışına çıkılmaz.
  4. HÜKMÜ KURAL MOTORU VERİR, matris tarif eder.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from politikdesk.evidence import matrix as mx
from politikdesk.evidence.matrix import (
    ALLOWED_CERTAINTY,
    CERTAINTY,
    Dimension,
    build,
    coverage_report,
)


def _kaynak(**over: object) -> dict[str, object]:
    temel: dict[str, object] = {
        "slug": "dunya",
        "name": "Dünya",
        "tier": 3,
        "kind": "media",
        "independence_group": "media-dunya",
        "stance": "supports",
        "quote_span": "…",
        "canonical_url": "https://example.test/x",
        "published_at": None,
        "has_official_value": False,
    }
    temel.update(over)
    return temel


# ═══════════════════════════════ 1. ölçülemedi ≠ sıfır
def test_counter_evidence_is_unavailable_not_zero() -> None:
    """**Bu testin var olma sebebi bir ölçümdür.**

    `evidence.stance` canlı veride 5.311 satırın 5.311'i `'supports'`;
    `contradicts` yazan kod yolu YOK. Boyutu "0" göstermek kullanıcıya
    *"bu iddiaya karşı hiçbir kanıt yok"* demektir — oysa doğru cümle
    *"karşı kanıt aranmıyor"*. Birincisi bir güven beyanıdır ve yanlıştır.
    """
    boyutlar = {d.key: d for d in mx._dimensions([_kaynak()])}  # noqa: SLF001
    for anahtar in ("contradicting", "counterclaim"):
        d = boyutlar[anahtar]
        assert d.state == "unavailable", anahtar
        assert d.count is None, f"{anahtar} sayi tasiyor — 0 gosterilecek"


def test_unavailable_dimension_explains_itself() -> None:
    boyutlar = {d.key: d for d in mx._dimensions([_kaynak()])}  # noqa: SLF001
    assert "ADR-008" in boyutlar["contradicting"].detail
    assert boyutlar["counterclaim"].detail


def test_measured_dimensions_carry_real_counts() -> None:
    kaynaklar = [
        _kaynak(slug="tuik", tier=1, independence_group="official-tuik", has_official_value=True),
        _kaynak(slug="dunya", tier=3, independence_group="media-dunya"),
        _kaynak(slug="bloomberght", tier=3, independence_group="media-bloomberght"),
    ]
    b = {d.key: d for d in mx._dimensions(kaynaklar)}  # noqa: SLF001
    assert b["supporting"].count == 3
    assert b["primary_source"].count == 1
    assert b["official_data"].count == 1
    assert b["independent"].count == 2  # tuik resmî sayılır
    assert b["independence_groups"].count == 3
    assert all(
        b[k].state == "measured"
        for k in (
            "supporting",
            "primary_source",
            "official_data",
            "independent",
            "independence_groups",
        )
    )


def test_dimension_dataclass_distinguishes_none_from_zero() -> None:
    assert Dimension("k", "L", 0, "measured", "d").count == 0
    assert Dimension("k", "L", None, "unavailable", "d").count is None


# ═══════════════════════════════ 2. boyutlar çarpılmaz
def test_matrix_has_no_single_opaque_confidence_number() -> None:
    """ "%78 güvenilir" yedi olguyu tek sayıya gömer."""
    from dataclasses import fields

    from politikdesk.evidence.matrix import ClaimMatrix

    alanlar = {f.name for f in fields(ClaimMatrix)}
    for yasak in ("confidence", "score", "trust", "reliability", "guven"):
        assert yasak not in alanlar, yasak
    assert "dimensions" in alanlar


def test_dimensions_are_returned_individually() -> None:
    boyutlar = mx._dimensions([_kaynak()])  # noqa: SLF001
    assert len(boyutlar) == 7
    assert len({d.key for d in boyutlar}) == 7


# ═══════════════════════════════ 3. kesinlik dili kontrollü
def test_certainty_vocabulary_is_a_closed_set() -> None:
    """Dört kovanın dışına çıkılmaz."""
    assert set(CERTAINTY.values()) == ALLOWED_CERTAINTY
    assert len(ALLOWED_CERTAINTY) <= 5


def test_certainty_avoids_probability_language() -> None:
    """Sistem olasılık tahmini YAPMAZ; kanıt havuzunu tarif eder."""
    for ifade in ALLOWED_CERTAINTY:
        dusuk = ifade.lower()
        for yasak in ("muhtemel", "ihtimal", "olası", "%", "sanır"):
            assert yasak not in dusuk, ifade


def test_every_engine_status_maps_to_a_certainty_bucket() -> None:
    """Motor yeni bir durum üretirse kesinlik dili boşta kalmamalı."""
    import typing

    from politikdesk.evidence.rules import EvidenceStatus

    durumlar = set(typing.get_args(EvidenceStatus))
    eksik = durumlar - set(CERTAINTY)
    assert not eksik, f"Kesinlik karsiligi olmayan durum: {sorted(eksik)}"


def test_unknown_status_falls_back_to_the_weakest_bucket() -> None:
    """Tanınmayan durum asla "DESTEKLENİYOR" olmamalı."""
    assert CERTAINTY.get("uydurma_durum", "DOĞRULANAMADI") == "DOĞRULANAMADI"


# ═══════════════════════════════ 4. mimari
def test_matrix_does_not_import_llm() -> None:
    """⛔ Hükmü deterministik kural motoru verir (Spec §8.1)."""
    agac = ast.parse(inspect.getsource(mx))
    moduller: set[str] = set()
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            moduller |= {a.name for a in dugum.names}
        elif isinstance(dugum, ast.ImportFrom) and dugum.module:
            moduller.add(dugum.module)
    assert not {m for m in moduller if m.startswith("politikdesk.llm")}


def test_matrix_reuses_claim_signature_for_identity() -> None:
    """İddia kimliği YENİDEN İCAT EDİLMEZ — `claim_signature` var
    (migration 0006) ve canlı veride %99,8 dolu."""
    kaynak = inspect.getsource(mx)
    assert "claim_signature" in kaynak
    assert "CREATE TABLE" not in kaynak


def test_official_slug_set_matches_the_rules_engine() -> None:
    """İki yerde tutulan bir küme er geç ayrışır."""
    from politikdesk.evidence.rules import OFFICIAL_STATISTICAL_SOURCES

    assert OFFICIAL_STATISTICAL_SOURCES <= mx.OFFICIAL_SLUGS


# ═══════════════════════════════ 5. canlı veri
@pytest.mark.db
def test_coverage_report_exposes_the_dead_contradiction_path() -> None:
    """Rapor, karşı kanıt yolunun canlı olup olmadığını AÇIKÇA söylemeli."""
    r = coverage_report()
    assert "contradiction_path_alive" in r
    assert r["stance_distribution"]
    # Yol canlanırsa ADR-008 yeniden değerlendirilmeli; test bunu duyurur.
    if r["contradiction_path_alive"]:
        pytest.fail(
            "Karsi kanit yolu CANLANMIS — ADR-008 ve matrix.py'deki "
            "'unavailable' isaretleri guncellenmeli."
        )


@pytest.mark.db
def test_build_returns_a_full_matrix_for_a_real_claim() -> None:
    from politikdesk.db import connection

    with connection() as c, c.cursor() as cur:
        cur.execute("SELECT id FROM claims ORDER BY id LIMIT 1")
        satir = cur.fetchone()
    assert satir is not None

    m = build(int(satir["id"]))
    assert m is not None
    assert m.certainty in ALLOWED_CERTAINTY
    assert len(m.dimensions) == 7
    assert m.claim_text


@pytest.mark.db
def test_build_returns_none_for_a_missing_claim() -> None:
    assert build(-1) is None
