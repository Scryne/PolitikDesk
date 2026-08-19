"""Söylem değişikliği kalıcılaştırma testleri (Roadmap Faz 4.1).

Korunan sözleşme:

  1. KİMLİK BEŞ BOYUTLU. Olay çifti tek başına yetmez — aynı çiftte iki
     farklı aktör kayması olabilir ve canlı veride oluyor.
  2. İDEMPOTENT. Değişmeyen bir kayma her turda yeniden yazılmaz.
  3. GEÇMİŞ SİLİNMEZ. Artık üretilmeyen kayıt `superseded` olur.
  4. OKUMA YOLU HESAP YAPMAZ. İstek anında tespit koşulmaz.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from politikdesk.political_memory import shift_store as ss
from politikdesk.political_memory.shift_store import ENGINE_VERSION, signature


# ═══════════════════════════════ 1. kimlik beş boyutlu
def test_identity_includes_actor_not_just_the_event_pair() -> None:
    """**Ölçülmüş bir veri kaybının önlenmesi.**

    `event_relations` anahtarı `(from, to, relation)`. Söylem değişikliği
    aktör ve konu boyutu taşır; o anahtar altında aynı olay çiftindeki
    iki farklı aktör kayması TEK SATIRA iner.

    Canlı ölçüm (19 Ağu 2026): 37 kaymanın 2'si kaybolurdu. Örnek —
    olay 7700 → 8041 arasında hem Devlet Bahçeli hem Resmî Gazete kaydı.

    Faz 1.2'de 150 TÜİK kaydını sessizce yok eden hatanın aynısı.
    """
    a = signature("Devlet Bahçeli", 7700, 8041, "reversal", "Politika")
    b = signature("Resmî Gazete", 7700, 8041, "reversal", "Politika")
    assert a != b


def test_identity_includes_topic() -> None:
    a = signature("X", 1, 2, "reversal", "Faiz")
    b = signature("X", 1, 2, "reversal", "Enflasyon")
    assert a != b


def test_identity_includes_shift_type() -> None:
    a = signature("X", 1, 2, "reversal", "T")
    b = signature("X", 1, 2, "broken_promise", "T")
    assert a != b


def test_identity_is_stable_across_calls() -> None:
    """İdempotency'nin dayanağı: aynı kayma her turda aynı kimliği alır."""
    assert signature("X", 1, 2, "reversal", "T") == signature("X", 1, 2, "reversal", "T")


def test_event_pair_alone_would_not_be_unique() -> None:
    """Anahtarın neden beş boyutlu olduğunun doğrudan kanıtı."""
    kimlikler = {
        signature(aktor, 100, 200, "reversal", "Politika")
        for aktor in ("Aktör A", "Aktör B", "Aktör C")
    }
    assert len(kimlikler) == 3


# ═══════════════════════════════ 2. şema
def test_schema_declares_the_five_dimensional_identity() -> None:
    from pathlib import Path

    sema = (
        Path(__file__).resolve().parent.parent / "migrations" / "0018_stance_shifts.sql"
    ).read_text(encoding="utf-8")
    for sutun in ("actor_name", "shift_type", "topic_or_metric",
                  "earlier_event_id", "later_event_id", "signature"):
        assert sutun in sema, sutun


def test_schema_keeps_superseded_records_instead_of_deleting() -> None:
    """Geçmiş SİLİNMEZ: bir kayma dünkü veriyle doğruydu."""
    from pathlib import Path

    sema = (
        Path(__file__).resolve().parent.parent / "migrations" / "0018_stance_shifts.sql"
    ).read_text(encoding="utf-8")
    assert "'superseded'" in sema
    assert "WHERE status = 'open'" in sema, "Tekillestirme yalnizca ACIK kayitlar icin olmali"


def test_schema_forbids_self_referencing_shift() -> None:
    from pathlib import Path

    sema = (
        Path(__file__).resolve().parent.parent / "migrations" / "0018_stance_shifts.sql"
    ).read_text(encoding="utf-8")
    assert "earlier_event_id <> later_event_id" in sema


def test_engine_version_is_recorded_for_safe_recompute() -> None:
    """Motor sürümü bilinmeden yeniden hesaplama güvenli yapılamaz."""
    assert ENGINE_VERSION
    kaynak = inspect.getsource(ss.sync)
    assert "engine_version <> %s" in kaynak, "Surum degisimi eski kayitlari kapatmali"


# ═══════════════════════════════ 3. okuma yolu hesap yapmaz
def test_read_path_does_not_recompute_detection() -> None:
    """İstek anında tespit KOŞULMAZ.

    Ölçüm (19 Ağu 2026): istek anında hesap 645,6 ms, kalıcı kayıttan
    okuma 3,0 ms — 219 kat fark.
    """
    for fn in (ss.list_all, ss.for_actor, ss.for_event):
        kaynak = inspect.getsource(fn)
        assert "detect_stance_shifts_from_memory" not in kaynak, fn.__name__
        assert "SELECT" in kaynak, fn.__name__


def test_service_read_path_delegates_to_the_store() -> None:
    from politikdesk.political_memory import service as ms

    for fn in (ms.list_all_stance_shifts, ms.get_actor_stance_shifts):
        kaynak = inspect.getsource(fn)
        assert "shift_store" in kaynak, fn.__name__
        assert "detect_stance_shifts_from_memory" not in kaynak, fn.__name__


def test_graph_query_by_event_covers_both_directions() -> None:
    """"Bu olay hangi kaymaların parçası?" — kalıcılaştırmanın açtığı kapı."""
    kaynak = inspect.getsource(ss.for_event)
    assert "earlier_event_id = %s" in kaynak
    assert "later_event_id = %s" in kaynak


# ═══════════════════════════════ 4. mimari
def test_shift_store_does_not_import_llm() -> None:
    """⛔ Bir kaymanın var olup olmadığına yapay zekâ karar veremez."""
    agac = ast.parse(inspect.getsource(ss))
    moduller: set[str] = set()
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            moduller |= {a.name for a in dugum.names}
        elif isinstance(dugum, ast.ImportFrom) and dugum.module:
            moduller.add(dugum.module)
    assert not {m for m in moduller if m.startswith("politikdesk.llm")}


def test_sync_only_supersedes_scanned_actors() -> None:
    """Tarama sınırı dışındaki aktörün kayıtları kapatılmamalı.

    Aksi hâlde `actor_limit` değerini düşürmek, taranmayan aktörlerin
    geçmişini sessizce yok ederdi.
    """
    kaynak = inspect.getsource(ss.sync)
    assert "actor_name = ANY(%s)" in kaynak


def test_sync_is_bounded_by_an_actor_limit() -> None:
    """Tarama O(n²); sınırsız bırakmak arka plan işini saatlerce koşturur."""
    assert ss.DEFAULT_ACTOR_LIMIT > 0
    assert "actor_limit" in inspect.signature(ss.sync).parameters


# ═══════════════════════════════ 5. canlı veri
@pytest.mark.db
def test_sync_is_idempotent_against_live_data() -> None:
    ilk = ss.sync(actor_limit=10)
    ikinci = ss.sync(actor_limit=10)
    assert ikinci.inserted == 0, "Ikinci tur yeni kayit uretmemeli"
    assert ikinci.detected == ilk.detected


@pytest.mark.db
def test_persisted_shifts_carry_their_evidence() -> None:
    """Kayıt, üretildiği beyanları taşımalı — olay başlığı sonradan
    değişse bile "bu kayma neden üretildi?" yanıtlanabilsin."""
    for kayit in ss.list_all(limit=10):
        assert kayit["actor_name"]
        assert kayit["shift_type"] in {"reversal", "broken_promise", "numeric_divergence"}
        assert kayit["earlier_event_id"] != kayit["later_event_id"]
        assert kayit["engine_version"]


@pytest.mark.db
def test_summary_reports_type_distribution_and_superseded_count() -> None:
    ozet = ss.summary()
    for alan in ("by_type", "total", "actors", "superseded"):
        assert alan in ozet, alan
