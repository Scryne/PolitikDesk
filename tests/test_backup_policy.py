"""Yedek konum kuralı testleri (B-84).

Karar: **yedekler bulut eşitlemesi dışında tutulur.** Gerekçe
`politikdesk/backup_policy.py` başlığında; özeti şu: BitLocker diski
korur, OneDrive'ın Microsoft sunucularındaki kopyasını korumaz. Yedek
makale alıntısı, editoryal profil ve taslak içerir.

Asıl tuzak **varsayılandı**: `PD_BACKUP_DIR` yokken yol `"backups"`,
yani depo kökünün altı — ve depo OneDrive'ın içindeydi. Kimse yanlış bir
şey yapmadı, varsayılan yanlıştı. Bu yüzden kural belgeye değil koda
yazıldı; buradaki testler kuralın gerçekten *reddettiğini* doğrular.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from politikdesk.backup_policy import (
    ALLOW_CLOUD_ENV,
    BACKUP_DIR_ENV,
    BackupLocationError,
    cloud_sync_reason,
    default_backup_dir,
    resolve_backup_dir,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Geliştiricinin gerçek bulut değişkenleri testlere sızmasın."""
    for var in (
        "OneDrive",
        "OneDriveCommercial",
        "OneDriveConsumer",
        "Dropbox",
        "iCloudDrive",
        BACKUP_DIR_ENV,
        ALLOW_CLOUD_ENV,
    ):
        monkeypatch.delenv(var, raising=False)


def test_default_is_not_cloud_synced() -> None:
    """Varsayılanın kendisi kuralı ihlal etmemeli.

    Eski varsayılan (`"backups"`) tam olarak bunu yapıyordu.
    """
    assert cloud_sync_reason(default_backup_dir()) is None


def test_repo_relative_backups_under_onedrive_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """B-84'ün ta kendisi: OneDrive altındaki depo + `backups`."""
    onedrive = tmp_path / "OneDrive"
    (onedrive / "Projeler" / "PolitikDesk" / "backups").mkdir(parents=True)
    monkeypatch.setenv("OneDrive", str(onedrive))

    target = onedrive / "Projeler" / "PolitikDesk" / "backups"
    with pytest.raises(BackupLocationError) as excinfo:
        resolve_backup_dir(str(target))

    message = str(excinfo.value)
    assert "OneDrive" in message
    # Hata mesajı ne yapılacağını söylemeli, yalnızca "hayır" dememeli.
    assert BACKUP_DIR_ENV in message
    assert str(default_backup_dir()) in message


def test_cloud_detected_by_path_name_without_env_var(tmp_path: Path) -> None:
    """Ortam değişkeni yoksa ad da yeter — klasör taşınmış olabilir."""
    for name in ("OneDrive", "Dropbox", "Google Drive", "OneDrive - Firma"):
        assert cloud_sync_reason(tmp_path / name / "backups") is not None


def test_plain_local_path_is_accepted(tmp_path: Path) -> None:
    assert cloud_sync_reason(tmp_path / "veri" / "backups") is None
    resolved = resolve_backup_dir(str(tmp_path / "veri" / "backups"))
    assert resolved == (tmp_path / "veri" / "backups")


def test_escape_hatch_requires_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Bilerek buluta yazmak mümkün olmalı — ama sessizce değil."""
    cloud = tmp_path / "OneDrive" / "backups"
    monkeypatch.setenv("OneDrive", str(tmp_path / "OneDrive"))

    with pytest.raises(BackupLocationError):
        resolve_backup_dir(str(cloud))

    monkeypatch.setenv(ALLOW_CLOUD_ENV, "1")
    assert resolve_backup_dir(str(cloud)) == cloud


def test_env_var_is_read_when_no_argument(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(BACKUP_DIR_ENV, str(tmp_path / "yedek"))
    assert resolve_backup_dir() == tmp_path / "yedek"


def test_relative_path_becomes_absolute(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Göreli yol çalışma dizinine göre çözülmeli.

    Çözülmezse kural, `cwd` neredeyse ona göre farklı karar verir —
    yani nöbetçi bulunduğu yere göre fikir değiştirir.
    """
    monkeypatch.chdir(tmp_path)
    resolved = resolve_backup_dir("backups")
    assert resolved.is_absolute()
    assert resolved == (tmp_path / "backups").resolve()


def test_backup_script_uses_the_policy() -> None:
    """`scripts/backup.py` kendi yolunu kurmamalı.

    İki yerde ayrı ayrı karar verilirse biri güncellenip diğeri unutulur.
    """
    source = Path(__file__).resolve().parent.parent / "scripts" / "backup.py"
    text = source.read_text(encoding="utf-8")
    assert "resolve_backup_dir" in text
    assert 'os.environ.get("PD_BACKUP_DIR"' not in text
