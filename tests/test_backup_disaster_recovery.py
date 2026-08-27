"""Felaket Kurtarma (Disaster Recovery), Yedek Bütünlüğü ve DR Tatbikatı testleri (F4-06)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.backup import (
    BackupManifest,
    compute_sha256,
    drill,
    manifest_path_for,
    prune,
    read_manifest,
    validate_restored_db,
    verify,
)


@pytest.fixture
def mock_dump_file(tmp_path: Path) -> Path:
    """Geçici sahte dump dosyası üretir."""
    dump = tmp_path / "politikdesk-20260823T120000Z-test.dump"
    dump.write_bytes(b"PGDMP\x01\x02\x03FAKE_DUMP_CONTENT_FOR_TESTING")
    return dump


# ===========================================================================
# 1. SHA-256 ve Manifest Bütünlük Testleri
# ===========================================================================
def test_compute_sha256_deterministic(mock_dump_file: Path) -> None:
    """SHA-256 çıktısı deterministiktir."""
    hash1 = compute_sha256(mock_dump_file)
    hash2 = compute_sha256(mock_dump_file)
    assert len(hash1) == 64
    assert hash1 == hash2


def test_manifest_read_write(mock_dump_file: Path) -> None:
    """Manifest dosyası doğru biçimde yazılır ve okunur."""
    m_path = manifest_path_for(mock_dump_file)
    sha = compute_sha256(mock_dump_file)
    manifest = BackupManifest(
        dump_filename=mock_dump_file.name,
        sha256=sha,
        bytes=mock_dump_file.stat().st_size,
        created_at="2026-08-23T12:00:00Z",
        app_version="0.1.0",
        git_sha="abcdef123456",
        table_counts={"articles": 100, "events": 20},
        migration_count=22,
    )
    m_path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")

    loaded = read_manifest(mock_dump_file)
    assert loaded is not None
    assert loaded.dump_filename == mock_dump_file.name
    assert loaded.sha256 == sha
    assert loaded.table_counts["articles"] == 100
    assert loaded.migration_count == 22


def test_verify_rejects_tampered_backup(mock_dump_file: Path) -> None:
    """Manifestteki hash ile uyuşmayan değiştirilmiş dosya verify tarafından reddedilir."""
    m_path = manifest_path_for(mock_dump_file)
    manifest = BackupManifest(
        dump_filename=mock_dump_file.name,
        sha256="0000000000000000000000000000000000000000000000000000000000000000",
        bytes=mock_dump_file.stat().st_size,
        created_at="2026-08-23T12:00:00Z",
        app_version="0.1.0",
        git_sha="abcdef",
        table_counts={},
        migration_count=22,
    )
    m_path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")

    # verify sha uyuşmazlığında False dönmelidir
    assert verify(mock_dump_file) is False


def test_verify_checks_pg_restore_list(mock_dump_file: Path) -> None:
    """verify pg_restore --list çıktısını denetler."""
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = (
            b"1; 1259 16384 TABLE DATA public articles politikdesk\n"
            b"2; 1259 16385 TABLE DATA public events politikdesk\n"
        )
        mock_run.return_value = mock_proc

        assert verify(mock_dump_file) is True


def test_verify_fails_on_corrupted_archive(mock_dump_file: Path) -> None:
    """Bozuk arşivde pg_restore hata verince verify False döner."""
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = b"pg_restore: error: input file appears to be corrupted"
        mock_run.return_value = mock_proc

        assert verify(mock_dump_file) is False


# ===========================================================================
# 2. Geri Yükleme ve Şema Bütünlüğü Doğrulayıcısı (validate_restored_db)
# ===========================================================================
def test_validate_restored_db_all_checks_pass() -> None:
    """Tüm denetimler geçtiğinde validate_restored_db True döner."""
    with (
        patch("scripts.backup._psql"),
        patch("scripts.backup._migration_count", return_value=22),
        patch("scripts.backup._table_exists", return_value=True),
        patch("scripts.backup._query_scalar", return_value=0),  # FK ihlali 0
        patch("scripts.backup._counts", return_value={"articles": 10, "events": 2}),
    ):
        ok = validate_restored_db("test_db", expected_counts={"articles": 10, "events": 2})
        assert ok is True


def test_validate_restored_db_catches_missing_table() -> None:
    """Kritik tablo eksikse doğrulayıcı False döner."""

    def fake_table_exists(db: str, tbl: str) -> bool:
        return tbl != "claims"

    with (
        patch("scripts.backup._psql"),
        patch("scripts.backup._migration_count", return_value=22),
        patch("scripts.backup._table_exists", side_effect=fake_table_exists),
        patch("scripts.backup._counts", return_value={}),
    ):
        ok = validate_restored_db("test_db")
        assert ok is False


def test_validate_restored_db_catches_fk_violation() -> None:
    """Yetim kayıt (FK ihlali) varsa doğrulayıcı False döner."""
    with (
        patch("scripts.backup._psql"),
        patch("scripts.backup._migration_count", return_value=22),
        patch("scripts.backup._table_exists", return_value=True),
        patch("scripts.backup._query_scalar", return_value=5),  # 5 adet yetim kayıt!
        patch("scripts.backup._counts", return_value={}),
    ):
        ok = validate_restored_db("test_db")
        assert ok is False


# ===========================================================================
# 3. Felaket Kurtarma Tatbikatı (drill)
# ===========================================================================
def test_drill_successful_execution(mock_dump_file: Path) -> None:
    """drill komutu izole ortamda tatbikatı başarıyla yürütür ve audit log yazar."""
    with (
        patch("scripts.backup.verify", return_value=True),
        patch("scripts.backup.restore", return_value=True),
        patch("scripts.backup._psql"),
        patch("politikdesk.audit.write") as mock_audit,
    ):
        ok = drill(path=mock_dump_file)
        assert ok is True
        assert mock_audit.called
        assert mock_audit.call_args[0][0] == "recovery_drill_passed"


# ===========================================================================
# 4. Prune ve Listeleme Testleri
# ===========================================================================
def test_prune_deletes_old_dumps_and_manifests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """prune belirtilen adetten eski dump ve manifest dosyalarını siler."""
    monkeypatch.setattr("scripts.backup.backup_dir", lambda: tmp_path)

    for i in range(5):
        dump = tmp_path / f"politikdesk-20260823T0{i}0000Z.dump"
        dump.write_bytes(b"DATA")
        manifest = manifest_path_for(dump)
        manifest.write_text("{}", encoding="utf-8")

    assert len(list(tmp_path.glob("*.dump"))) == 5
    assert len(list(tmp_path.glob("*.json"))) == 5

    # En yeni 2 taneyi tut
    removed = prune(keep=2)
    assert removed == 3
    assert len(list(tmp_path.glob("*.dump"))) == 2
    assert len(list(tmp_path.glob("*.json"))) == 2
