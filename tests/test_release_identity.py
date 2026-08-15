"""Release identity ve sürüm bütünlüğü testleri (Faz 1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from politikdesk import __version__
from politikdesk.release import (
    ReleaseInfo,
    _detect_git_branch,
    _detect_git_sha,
    get_release_info,
)
from scripts.check_deployment import (
    expected_assets,
    expected_schedule,
    get_repo_migrations,
    repo_hash,
)


def test_release_info_dataclass() -> None:
    """ReleaseInfo modelinin alanları ve dict dönüşümü doğrulanır."""
    rel = ReleaseInfo(
        app_version="0.1.0",
        git_sha="abcdef123456",
        git_branch="main",
        image_digest="sha256:123456",
        build_timestamp="2026-08-15T12:00:00Z",
        deployed_at="2026-08-15T12:05:00Z",
        db_schema_version="0010_politics_vertical_v34",
        env="development",
    )
    d = rel.to_dict()
    assert d["app_version"] == "0.1.0"
    assert d["git_sha"] == "abcdef123456"
    assert d["git_branch"] == "main"
    assert d["image_digest"] == "sha256:123456"
    assert d["db_schema_version"] == "0010_politics_vertical_v34"
    assert d["env"] == "development"


def test_detect_git_sha_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ortam değişkeni ayarlandığında git_sha oradan okunur."""
    monkeypatch.setenv("PD_GIT_SHA", "test_commit_sha_12345")
    from politikdesk.config import get_settings

    get_settings.cache_clear()
    assert _detect_git_sha() == "test_commit_sha_12345"
    get_settings.cache_clear()


def test_detect_git_branch_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ortam değişkeni ayarlandığında git_branch oradan okunur."""
    monkeypatch.setenv("PD_GIT_BRANCH", "release/v1.0")
    from politikdesk.config import get_settings

    get_settings.cache_clear()
    assert _detect_git_branch() == "release/v1.0"
    get_settings.cache_clear()


def test_get_release_info_defaults() -> None:
    """Varsayılan get_release_info çağrısı geçerli alanlar döndürür."""
    rel = get_release_info(include_db_schema=False)
    assert rel.app_version == __version__
    assert isinstance(rel.git_sha, str)
    assert len(rel.git_sha) > 0
    assert rel.env in ("development", "test", "production")


def test_version_endpoint_returns_json() -> None:
    """GET /version ve GET /health/version uçları 200 döner ve release bilgisi içerir."""
    from politikdesk.api.main import app

    with TestClient(app) as client:
        res1 = client.get("/version")
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["app_version"] == __version__
        assert "git_sha" in data1
        assert "env" in data1

        res2 = client.get("/health/version")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["app_version"] == __version__


def test_health_live_includes_release_meta() -> None:
    """GET /health/live sürüm, git_sha ve ortam bilgisini içerir."""
    from politikdesk.api.main import app

    with TestClient(app) as client:
        res = client.get("/health/live")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["version"] == __version__
        assert "git_sha" in data
        assert "env" in data


def test_version_endpoint_is_auth_exempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """PD_API_TOKEN ayarlı olduğunda bile /version ucu token istemez (monitoring serbestliği)."""
    monkeypatch.setenv("PD_API_TOKEN", "secret-token-12345")
    from politikdesk.api.main import app
    from politikdesk.config import get_settings

    get_settings.cache_clear()

    with TestClient(app) as client:
        # Korumalı uç 401 döner
        res_protected = client.get("/admin/sources")
        assert res_protected.status_code == 401

        # /version muaf olmalıdır
        res_version = client.get("/version")
        assert res_version.status_code == 200
        assert res_version.json()["app_version"] == __version__

        # /health/live muaf olmalıdır
        res_live = client.get("/health/live")
        assert res_live.status_code == 200

    get_settings.cache_clear()


def test_deployment_check_helpers() -> None:
    """check_deployment betiğindeki beklenti çıkarıcıların doğruluğu."""
    h = repo_hash()
    assert isinstance(h, str)
    assert len(h) == 64

    assets = expected_assets()
    assert "certs" in assets
    assert "config" in assets
    assert len(assets["config"]) > 0

    schedule = expected_schedule()
    assert isinstance(schedule, list)
    assert len(schedule) >= 15

    migrations = get_repo_migrations()
    assert isinstance(migrations, list)
    assert len(migrations) >= 10
    assert "0001_initial" in migrations
