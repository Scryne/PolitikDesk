"""Faz 21 — Production Cycle CLI Yönetim Aracı Testleri."""

from __future__ import annotations

import pytest

from scripts.production_cycle import get_active_cycle, get_cycle_counts, main


@pytest.mark.db
def test_production_cycle_get_active_and_counts(db_conn) -> None:
    """get_active_cycle ve get_cycle_counts fonksiyonlarının çalıştığını doğrular."""
    active = get_active_cycle(db_conn)
    assert active is not None, "Aktif bir üretim döngüsü bulunmalı"
    assert active["status"] == "active"

    counts = get_cycle_counts(active["id"], db_conn)
    assert "articles" in counts
    assert "events" in counts
    assert "claims" in counts
    assert "evidence" in counts


@pytest.mark.db
def test_production_cycle_cli_status(capsys) -> None:
    """'python -m scripts.production_cycle status' komutunu test eder."""
    code = main(["status"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "POLİTİKDESK PRODUCTION DATA LIFECYCLE STATUS" in captured
    assert "AKTİF DÖNGÜ:" in captured


@pytest.mark.db
def test_production_cycle_cli_list(capsys) -> None:
    """'python -m scripts.production_cycle list' komutunu test eder."""
    code = main(["list"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "ACTIVE" in captured or "ARCHIVED" in captured


@pytest.mark.db
def test_production_cycle_cli_create_dry_run(capsys) -> None:
    """'python -m scripts.production_cycle create --name ... --dry-run' komutunu test eder."""
    code = main(["create", "--name", "Test Döngüsü", "--dry-run"])
    assert code == 0
    captured = capsys.readouterr().out
    assert "[DRY-RUN]" in captured
