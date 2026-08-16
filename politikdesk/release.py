"""Sistem sürümü ve release identity yönetimi (F1).

Repo → Build → Image → Container → DB zincirini doğrulanabilir ve
denetlenebilir kılmak için release kimliği tek noktadan üretilir ve sunulur.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from politikdesk import __version__
from politikdesk.config import get_settings

REPO_ROOT = Path(__file__).resolve().parent.parent
_STARTUP_TIME = datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class ReleaseInfo:
    app_version: str
    git_sha: str
    git_branch: str
    image_digest: str | None
    build_timestamp: str | None
    deployed_at: str
    db_schema_version: str | None
    env: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _detect_git_sha() -> str:
    """Git commit SHA'sını tespit eder.

    Önce `PD_GIT_SHA` ortam değişkenine bakar (Docker build anında enjekte edilir);
    yoksa ve `.git` dizini mevcutsa `git rev-parse HEAD` komutunu dener.
    """
    settings = get_settings()
    if settings.git_sha:
        return settings.git_sha

    env_sha = os.environ.get("PD_GIT_SHA", "").strip()
    if env_sha:
        return env_sha

    git_dir = REPO_ROOT / ".git"
    if git_dir.exists():
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],  # noqa: S603, S607
                capture_output=True,
                text=True,
                timeout=5,
                cwd=REPO_ROOT,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass

    return "unknown"


def _detect_git_branch() -> str:
    """Git branch adını tespit eder."""
    settings = get_settings()
    if settings.git_branch:
        return settings.git_branch

    env_branch = os.environ.get("PD_GIT_BRANCH", "").strip()
    if env_branch:
        return env_branch

    git_dir = REPO_ROOT / ".git"
    if git_dir.exists():
        try:
            res = subprocess.run(
                ["git", "branch", "--show-current"],  # noqa: S603, S607
                capture_output=True,
                text=True,
                timeout=5,
                cwd=REPO_ROOT,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass

    return "unknown"


def get_db_schema_version() -> str | None:
    """Canlı veritabanındaki en son uygulanan migration sürümünü döner."""
    try:
        from politikdesk.db import connection

        with connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
            row = cur.fetchone()
            if row and "version" in row:
                return str(row["version"])
    except Exception:  # noqa: BLE001
        pass
    return None


@lru_cache(maxsize=1)
def _get_static_release_meta() -> tuple[str, str, str | None, str | None, str]:
    """Süreç boyunca değişmeyen statik release meta verileri."""
    settings = get_settings()
    git_sha = _detect_git_sha()
    git_branch = _detect_git_branch()
    image_digest = settings.image_digest or os.environ.get("PD_IMAGE_DIGEST") or None
    build_timestamp = settings.build_timestamp or os.environ.get("PD_BUILD_TIMESTAMP") or None
    deployed_at = settings.deployed_at or os.environ.get("PD_DEPLOYED_AT") or _STARTUP_TIME
    return git_sha, git_branch, image_digest, build_timestamp, deployed_at


def get_release_info(include_db_schema: bool = True) -> ReleaseInfo:
    """Uygulamanın tam release kimliğini döner."""
    settings = get_settings()
    git_sha, git_branch, image_digest, build_timestamp, deployed_at = _get_static_release_meta()
    db_schema = get_db_schema_version() if include_db_schema else None

    return ReleaseInfo(
        app_version=__version__,
        git_sha=git_sha,
        git_branch=git_branch,
        image_digest=image_digest,
        build_timestamp=build_timestamp,
        deployed_at=deployed_at,
        db_schema_version=db_schema,
        env=settings.env,
    )
