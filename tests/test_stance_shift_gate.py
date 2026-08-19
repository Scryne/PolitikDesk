"""Söylem değişikliği yayın kapısı testleri (ADR-010).

Denetimde bulunan kusur: sistem, birbiriyle ilgisiz iki beyandan yola
çıkarak gerçek kişi ve kurumlara "U dönüşü" isnat ediyordu ve bu çıktı
kullanıcıya görünüyordu. Somut örnek — Cumhurbaşkanlığı'na, 42 dakika
arayla atılmış ve hiçbiri ona ait olmayan iki tweete dayanarak
atfedilen `reversal`.

Bu testler kapının kapalı kaldığını ve **atlanabilen bir yol
bırakmadığını** güvence altına alır. Bir kapı, her yolda kapalı değilse
kapı değildir.
"""

from __future__ import annotations

import ast
import inspect

from politikdesk.political_memory import shift_store


def test_publish_gate_is_closed() -> None:
    """ADR-010: kapı açılmadan önce §5'teki yedi şart ölçülmelidir."""
    assert shift_store.PUBLISH_GATE_OPEN is False, (
        "Kapi acilmis. ADR-010 §5 sartlari olculmeden acilmamali: konu "
        "eslestirmesi, aktor=konusan, gercek guven skoru, altin kume."
    )


def test_all_three_read_paths_respect_the_gate() -> None:
    """`list_all`, `for_actor`, `for_event` — üçü de kapıya bakmalı.

    Biri unutulursa yanlış isnat o yoldan sızar.
    """
    for ad in ("list_all", "for_actor", "for_event"):
        kaynak = inspect.getsource(getattr(shift_store, ad))
        assert "PUBLISH_GATE_OPEN" in kaynak, f"{ad}() kapiya bakmiyor"


def test_gate_closed_means_empty_reads() -> None:
    """Kapı kapalıyken okuma yolları veritabanına hiç gitmemeli."""
    assert shift_store.list_all() == []
    assert shift_store.for_actor("Cumhurbaşkanlığı") == []
    assert shift_store.for_event(1) == []


def test_memory_page_does_not_bypass_the_gate() -> None:
    """⛔ `/memory/{aktör}` dedektörü DOĞRUDAN çağırıyordu.

    Kapı yalnızca `shift_store`'a konsaydı, olay sayfası temizlenir ama
    hafıza sayfası "180° Zıt Beyan" kartlarını üretmeye devam ederdi —
    aynı yanlış isnat, ikinci yoldan.
    """
    from politikdesk.web import memory_view

    kaynak = inspect.getsource(memory_view)
    assert "detect_stance_shifts_from_memory" in kaynak
    assert "PUBLISH_GATE_OPEN" in kaynak, (
        "Hafiza sayfasi dedektoru kapiya sormadan cagiriyor."
    )


def test_withheld_records_are_not_deleted() -> None:
    """Kayıtlar saklanmalı: dedektör düzeltilince karşılaştırma gerekir."""
    kaynak = inspect.getsource(shift_store)
    agac = ast.parse(kaynak)
    silme = [
        n.value for n in ast.walk(agac)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and "DELETE FROM stance_shifts" in n.value.upper()
    ]
    assert not silme, "Kayitlar siliniyor; ADR-010 saklanmalarini sart kosuyor"


def test_summary_reports_withheld_separately() -> None:
    """**ölçülemedi ≠ sıfır.**

    Özet sessizce 0 dönseydi, "hiç kayma bulunmadı" ile "bulunanlar
    güvenilmez olduğu için yayınlanmadı" arasındaki fark silinirdi.
    """
    kaynak = inspect.getsource(shift_store.summary)
    assert "withheld" in kaynak
    assert "publish_gate_open" in kaynak


def test_detector_still_runs_while_gate_is_closed() -> None:
    """Ölçmek ile yayınlamak ayrı kararlar; yalnızca ikincisi durdu."""
    kaynak = inspect.getsource(shift_store._persist)
    assert "INSERT INTO stance_shifts" in kaynak
    assert "WITHHELD_STATUS" in kaynak


def test_uniqueness_covers_withheld_rows() -> None:
    """⛔ Kapıyı kapatmak idempotentliği kırabilirdi.

    0018'deki tekillik indeksi yalnızca `status='open'` satırlarını
    kapsıyordu. Dedektör `withheld` yazmaya başlayınca o indeks hiçbir
    yeni satırı görmez, `ON CONFLICT` hedefi eşleşmez ve her koşumda
    AYNI kayma tekrar eklenir.
    """
    kaynak = inspect.getsource(shift_store._persist)
    assert "status <> 'superseded'" in kaynak, (
        "ON CONFLICT hedefi hala 'open' ile sinirli; withheld satirlar "
        "tekillestirilmez ve her sync kopya uretir."
    )


def test_migration_0019_widens_the_unique_index() -> None:
    import pathlib

    yol = (
        pathlib.Path(shift_store.__file__).resolve().parents[2]
        / "migrations" / "0019_stance_shift_withheld.sql"
    )
    sql = yol.read_text(encoding="utf-8")
    assert "uq_stance_shifts_signature" in sql
    assert "status <> 'superseded'" in sql
    assert "'withheld'" in sql
    # Kayıtlar taşınır, silinmez.
    assert "DELETE FROM stance_shifts" not in sql.upper()
