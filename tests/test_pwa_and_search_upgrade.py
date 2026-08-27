"""Tests for PWA Manifest, Trigram Search Migration, and Broadcast Audio Briefing Compiler."""

from __future__ import annotations

from datetime import date

from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.briefing.audio_compiler import (
    AudioScript,
    compile_audio_script,
    expand_phonetic_acronyms,
)
from politikdesk.briefing.generator import (
    BriefingContent,
    BriefingEvent,
)
from politikdesk.db import connection


def test_pwa_manifest_and_icons() -> None:
    """PWA manifest, icons and Service Worker must be properly served."""
    client = TestClient(app)

    # 1. Manifest
    manifest_resp = client.get("/static/manifest.webmanifest")
    assert manifest_resp.status_code == 200
    manifest = manifest_resp.json()
    assert manifest["short_name"] == "PolitikDesk"
    assert manifest["display"] == "standalone"
    assert manifest["theme_color"] == "#0e1013"
    assert len(manifest["icons"]) >= 2

    # 2. Icons
    icon192_resp = client.get("/static/icon-192.svg")
    assert icon192_resp.status_code == 200
    assert "svg" in icon192_resp.headers.get("content-type", "")

    icon512_resp = client.get("/static/icon-512.svg")
    assert icon512_resp.status_code == 200
    assert "svg" in icon512_resp.headers.get("content-type", "")

    # 3. Service Worker
    sw_resp = client.get("/static/sw.js")
    assert sw_resp.status_code == 200
    assert "politikdesk-shell" in sw_resp.text


def test_shell_html_includes_pwa_tags() -> None:
    """HTML shell must contain manifest link, theme-color meta, and service worker registration."""
    client = TestClient(app)
    resp = client.get("/feed")
    assert resp.status_code == 200
    html = resp.text
    assert '<link rel="manifest" href="/static/manifest.webmanifest">' in html
    assert '<meta name="theme-color" content="#0E1013">' in html
    assert "navigator.serviceWorker.register('/static/sw.js')" in html


def test_pg_trgm_indexes_exist() -> None:
    """PostgreSQL pg_trgm extension and GIN indexes must exist in database."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'pg_trgm';")
        ext = cur.fetchone()
        assert ext is not None, "pg_trgm extension not installed"

        cur.execute(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'events' AND indexname = 'idx_events_title_trgm';
            """
        )
        idx = cur.fetchone()
        assert idx is not None, "idx_events_title_trgm index missing"


def test_phonetic_acronym_expansion() -> None:
    """Financial and institutional acronyms must be phonetically expanded for TTS."""
    raw = "TCMB PPK toplantısında TÜFE ve ÜFE hedefleri doğrultusunda karar aldı. TBMM ve BDDK izlemede."
    expanded = expand_phonetic_acronyms(raw)

    assert "Türkiye Cumhuriyet Merkez Bankası" in expanded
    assert "Para Politikası Kurulu" in expanded
    assert "Tüketici Fiyat Endeksi" in expanded
    assert "Üretici Fiyat Endeksi" in expanded
    assert "Türkiye Büyük Millet Meclisi" in expanded
    assert "Bankacılık Düzenleme ve Denetleme Kurumu" in expanded


def test_audio_script_compiler() -> None:
    """BriefingContent object must compile to structured AudioScript."""
    test_date = date(2026, 8, 25)
    mock_events = [
        BriefingEvent(
            event_id=101,
            title="TCMB Politika Faizini Yüzde 50 Seviyesinde Sabit Bıraktı",
            salience=85,
            status="settled",
            article_count=12,
            independent_count=4,
            independence_groups=3,
            has_primary_source=True,
            top_claim="Politika faizi yüzde 50 olarak korundu",
            top_claim_status="strongly_corroborated",
        )
    ]
    mock_upcoming = [
        {
            "id": 1,
            "title": "Ağustos Ayı Enflasyon Rakamları",
            "source_name": "TÜİK",
            "expected_at": "2026-08-25T10:00:00",
            "expected_label": "25 Ağu 10:00",
        }
    ]
    content = BriefingContent(
        briefing_date=test_date,
        slot="morning",
        events=mock_events,
        upcoming=mock_upcoming,
        unverified=[],
    )

    script: AudioScript = compile_audio_script(content)
    assert script.briefing_date == test_date
    assert script.slot == "morning"
    assert "Türkiye Cumhuriyet Merkez Bankası" in script.full_narration
    assert script.total_estimated_seconds > 10
    assert len(script.sections) >= 3

    # Dictionary serializability
    d = script.as_dict()
    assert d["slot"] == "morning"
    assert "Türkiye İstatistik Kurumu" in d["full_narration"] or "TÜİK" in d["full_narration"]


def test_briefing_audio_script_endpoint() -> None:
    """GET /api/briefing/{date}/audio-script must return 200 OK and valid json."""
    client = TestClient(app)
    resp = client.get("/api/briefing/2026-08-25/audio-script", params={"slot": "morning"})
    assert resp.status_code == 200
    data = resp.json()
    assert "full_narration" in data
    assert "sections" in data
    assert "total_estimated_seconds" in data
