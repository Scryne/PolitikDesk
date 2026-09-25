"""Graf tabanlı kanıt erişimi testleri (Roadmap Faz 4.2).

Korunan sözleşme:

  1. LLM YOK. Erişimin hiçbir adımı yapay zekâ kullanmaz.
  2. Dönen şey bir CEVAP DEĞİL, bir KANIT KÜMESİDİR.
  3. Her atıf kökenini taşır; kaynaksız atıf atıf değildir.
  4. Bağımsızlık GİZLENMEZ ve tek opak sayıya çevrilmez.
  5. Gezinme sınırlıdır — sınırsız yayılma alakayı yok eder.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from politikdesk.analysis import graph_retrieval as gr
from politikdesk.analysis.graph_retrieval import (
    MAX_DEPTH,
    MAX_NODES,
    Citation,
    RetrievalResult,
    resolve_entities,
    retrieve,
    traverse,
)


# ═══════════════════════════════ 1. LLM sınırı
def test_retrieval_never_imports_llm() -> None:
    """⛔ LLM kanıt ÜRETMEZ. Erişimin hiçbir adımı ona dokunmaz."""
    agac = ast.parse(inspect.getsource(gr))
    moduller: set[str] = set()
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            moduller |= {a.name for a in dugum.names}
        elif isinstance(dugum, ast.ImportFrom) and dugum.module:
            moduller.add(dugum.module)
    assert not {m for m in moduller if m.startswith("politikdesk.llm")}


def test_module_declares_why_synthesis_is_not_wired() -> None:
    """Sentezin bağlanmaması bir eksiklik değil, bir karar — yazılı olmalı.

    Bu üründe üretilen her metin `grounding_check` sert kapısından geçer.
    Buraya ayrı bir üretim yolu açmak o kapıyı baypas eden ikinci bir
    yüzey açardı.
    """
    belge = gr.__doc__ or ""
    assert "grounding_check" in belge
    assert "LLM asla kanıt ÜRETMEZ" in belge


def test_result_is_a_citation_set_not_an_answer() -> None:
    from dataclasses import fields

    alanlar = {f.name for f in fields(RetrievalResult)}
    for yasak in ("answer", "summary", "conclusion", "interpretation", "cevap"):
        assert yasak not in alanlar, yasak
    assert "citations" in alanlar


# ═══════════════════════════════ 2. varlık çözümleme
def test_stopwords_are_not_resolved_as_entities() -> None:
    """ "ne oldu" gibi bir soru rastgele varlıklara çarpmamalı."""
    assert resolve_entities("ne oldu") == []
    assert resolve_entities("bu ve şu") == []


def test_short_terms_are_ignored() -> None:
    assert gr.MIN_TERM_LENGTH >= 3
    assert resolve_entities("ab cd") == []


def test_empty_question_yields_no_entities() -> None:
    for soru in ("", "   ", "?"):
        assert resolve_entities(soru) == []


def test_alias_resolution_is_supported() -> None:
    """**Ölçülmüş bir kusurun regresyon testi.**

    Kısaltmalar canonical adla eşleşmez: soru "TCMB" derken varlık
    "Türkiye Cumhuriyet Merkez Bankası"dır. Parçalı arama onu asla
    bulamaz; ilk uygulamada `TCMB faiz kararı` sorusu NER çöpü olan
    `'Kararı'` varlığına çarpıyor, TCMB'yi kaçırıyordu.
    """
    kaynak = inspect.getsource(resolve_entities)
    assert "ANY(aliases)" in kaynak, "Takma ad araması yok"
    assert '"alias"' in kaynak


def test_partial_match_is_word_boundary_anchored() -> None:
    """Sınırsız `%terim%` çöp varlıklara çarpıyordu."""
    kaynak = inspect.getsource(resolve_entities)
    assert "\\\\m" in kaynak or "\\m" in kaynak, "Kelime sınırı çıpası yok"


def test_resolution_ranks_exact_over_alias_over_partial() -> None:
    kaynak = inspect.getsource(resolve_entities)
    assert '"exact": 0' in kaynak
    assert '"alias": 1' in kaynak
    assert '"partial": 2' in kaynak


def test_key_entities_are_preferred_within_partial_matches() -> None:
    """566 varlığın yalnızca 14'ü anahtar — bayrak gerçek kalite sinyali."""
    assert "is_key_entity DESC" in inspect.getsource(resolve_entities)


# ═══════════════════════════════ 3. graf gezinme
def test_traversal_is_depth_limited() -> None:
    """Sınırsız yayılma 1557 olaylık grafta alakayı yok eder."""
    assert MAX_DEPTH == 2
    assert "g.depth < %s" in gr._TRAVERSE_SQL  # noqa: SLF001


def test_traversal_is_node_capped() -> None:
    """Bir "hub" olay üst sınır olmadan tüm grafı çeker."""
    assert MAX_NODES > 0
    assert "LIMIT %s" in gr._TRAVERSE_SQL  # noqa: SLF001


def test_traversal_reads_edges_in_both_directions() -> None:
    """Bir vaadin tutulup tutulmadığı iki yönden de bulunabilmeli."""
    sql = gr._TRAVERSE_SQL  # noqa: SLF001
    assert "from_event_id AS kaynak" in sql and "to_event_id   AS kaynak" in sql
    assert "earlier_event_id AS kaynak" in sql and "later_event_id   AS kaynak" in sql


def test_traversal_includes_stance_shift_edges() -> None:
    """Faz 4.1'in kalıcılaştırdığı kenarlar grafın parçası."""
    assert "stance_shifts" in gr._TRAVERSE_SQL  # noqa: SLF001
    assert "status = 'open'" in gr._TRAVERSE_SQL  # noqa: SLF001


def test_traversal_skips_merged_events() -> None:
    """Birleştirilmiş olay bir kopyadır; çekirdek olamaz."""
    assert "merged_into_id IS NULL" in gr._TRAVERSE_SQL  # noqa: SLF001


def test_empty_entity_list_returns_no_nodes() -> None:
    assert traverse([]) == []


# ═══════════════════════════════ 4. atıf ve köken
def test_citation_carries_full_provenance() -> None:
    from dataclasses import fields

    alanlar = {f.name for f in fields(Citation)}
    for gerekli in (
        "claim_id",
        "event_id",
        "source_name",
        "source_slug",
        "independence_group",
        "article_url",
        "published_at",
        "evidence_status",
        "depth",
    ):
        assert gerekli in alanlar, gerekli


def test_citations_are_ordered_by_evidence_strength() -> None:
    """Güçlü teyitli iddia atıf kümesinde önce gelmeli."""
    sql = gr._CITATION_SQL  # noqa: SLF001
    assert "strongly_corroborated' THEN 0" in sql
    assert "partially_corroborated' THEN 1" in sql


def test_independence_is_reported_not_collapsed_into_a_score() -> None:
    """12 atıfın tek gruptan gelmesi ile dört gruptan gelmesi çok farklı."""
    from dataclasses import fields

    alanlar = {f.name for f in fields(RetrievalResult)}
    assert "independence_groups" in alanlar
    assert "confidence" not in alanlar
    assert "score" not in alanlar


def test_single_group_result_is_flagged() -> None:
    kaynak = inspect.getsource(retrieve)
    assert "tek bağımsızlık grubundan" in kaynak


# ═══════════════════════════════ 5. canlı veri
@pytest.mark.live_data
@pytest.mark.db
def test_retrieval_runs_against_live_graph() -> None:
    sonuc = retrieve("Devlet Bahçeli")
    assert sonuc.entities, "Bilinen aktor cozumlenemedi"
    assert sonuc.traversed_event_ids
    assert len(sonuc.traversed_event_ids) <= MAX_NODES
    for c in sonuc.citations:
        assert c.claim_text
        assert 0 <= c.depth <= MAX_DEPTH


@pytest.mark.db
def test_unknown_question_returns_empty_set_with_a_note() -> None:
    """Bilinmeyen soru boş küme döner ve NEDEN boş olduğunu söyler."""
    sonuc = retrieve("zzzqqq bilinmeyen terim")
    assert sonuc.citations == []
    assert sonuc.notes


@pytest.mark.live_data
@pytest.mark.db
def test_alias_query_resolves_the_canonical_institution() -> None:
    sonuc = retrieve("SPK")
    adlar = [e.canonical_name for e in sonuc.entities]
    assert any("Sermaye Piyasas" in a for a in adlar), adlar


@pytest.mark.db
def test_temporal_filter_narrows_the_citation_set() -> None:
    from datetime import UTC, datetime

    genis = retrieve("Devlet Bahçeli")
    dar = retrieve("Devlet Bahçeli", since=datetime(2030, 1, 1, tzinfo=UTC))
    assert len(dar.citations) <= len(genis.citations)
