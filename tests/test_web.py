"""Arayüz katmanı testleri (F3-01 … F3-07, F3-21).

Kapı G3'ün iki kod-inceleme koşulu burada **otomatik** hâle getirilir:

  * **#8 — UI'da siyasi kaynak etiketi yok.** Göz denetimi bir kez
    yapılır ve unutulur; tarama her koşumda yapılır.
  * **#9 — Otomatik yayın kod yolu yok.** Depo genelinde X'e giden
    giden istek aranır.

Her ikisi de "kod incelemesi" olarak yazılmıştı; bir testle
karşılanmaları koşulu zayıflatmaz, sürdürülebilir kılar.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "politikdesk" / "web"

# Spec §8.5 / §15 madde 5: kaynağa siyasi konum etiketi verilemez.
# Aranan şey bu sözcüklerin BİR KAYNAĞA ATFEDİLMESİ; ürün metninde
# "siyasi" kelimesinin geçmesi (ör. yasağı açıklayan bir not) sorun
# değildir. Bu yüzden kalıp "etiket olarak kullanım"a odaklanır.
POLITICAL_LABELS = (
    "yandaş",
    "yandas",
    "muhalif medya",
    "hükümet yanlısı",
    "hukumet yanlisi",
    "sağcı",
    "sagci",
    "solcu",
    "iktidar medyası",
    "havuz medyası",
    "pro-government",
    "opposition media",
    "left-leaning",
    "right-leaning",
)

# Spec §15 madde 6 / P5: insan onayı olmadan yayın yoktur.
PUBLISH_CODE_PATHS = (
    "api.twitter.com",
    "api.x.com",
    "statuses/update",
    "/2/tweets",
    "tweepy",
    "twitter_api",
    "auto_publish",
    "autopublish",
)


def _python_sources() -> list[Path]:
    return [p for p in (REPO_ROOT / "politikdesk").rglob("*.py") if "__pycache__" not in p.parts]


def _emittable_strings(path: Path) -> list[str]:
    """Dosyadaki, ÇIKTIYA ULAŞABİLECEK dize sabitleri.

    Yorumlar ve docstring'ler dışlanır. Sebep somut: bu depoda kısıtlar
    koda yazılıyor ve `event.py`'nin docstring'i "yandaş/muhalif etiketi
    verilemez" diye YASAĞI açıklıyor. Ham metin taraması o açıklamayı
    ihlal sanardı — yani test, kendisini var eden disiplini cezalandırırdı.

    f-string parçaları `ast.JoinedStr` içinde `Constant` olarak durur ve
    bu yüzden taramaya dahildir.
    """
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            first = next(iter(getattr(node, "body", [])), None)
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docstrings.add(id(first.value))

    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


# ============================================================ G3 koşul 8
def test_ui_has_no_political_source_labels() -> None:
    """Arayüz kaynağa siyasi konum etiketi vermez (Spec §8.5, §15 madde 5)."""
    offenders: list[str] = []
    for path in WEB_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        blob = " ".join(_emittable_strings(path)).lower()
        offenders += [f"{path.name}: {label}" for label in POLITICAL_LABELS if label in blob]
    assert not offenders, (
        f"Arayüzde siyasi kaynak etiketi: {offenders}. "
        "Spec §8.5 framing dili kullanır, 'bias' değil."
    )


def test_source_table_shows_tier_not_political_position() -> None:
    """Kaynak tablosu yalnızca ad, tier ve yayın grubu gösterir."""
    source = (WEB_DIR / "event.py").read_text(encoding="utf-8")
    assert "tier_badge" in source
    assert "independence_group" in source
    assert "siyasi konum etiketi vermez" in source  # kısıt kodda yazılı


def test_briefing_email_has_no_political_labels() -> None:
    blob = " ".join(
        _emittable_strings(REPO_ROOT / "politikdesk" / "briefing" / "renderer.py")
    ).lower()
    assert not [label for label in POLITICAL_LABELS if label in blob]


# ============================================================ G3 koşul 9
def test_no_automatic_publish_code_path_anywhere() -> None:
    """Depoda X'e giden hiçbir gönderim kod yolu yoktur (P5)."""
    offenders: list[str] = []
    for path in _python_sources():
        lowered = path.read_text(encoding="utf-8").lower()
        offenders += [
            f"{path.relative_to(REPO_ROOT).as_posix()}: {needle}"
            for needle in PUBLISH_CODE_PATHS
            if needle in lowered
        ]
    assert not offenders, (
        f"Otomatik yayın kod yolu bulundu: {offenders}. "
        "Spec §15 madde 6: insan onayı olmadan yayın yapılmaz."
    )


def test_publish_bridge_only_produces_a_web_intent_url() -> None:
    from politikdesk.editorial.service import publish_payload

    source = (REPO_ROOT / "politikdesk" / "editorial" / "service.py").read_text(encoding="utf-8")
    # Fonksiyon gövdesinde yalnızca adres kurulur; ağ çağrısı yoktur.
    body = source.split("def publish_payload", 1)[1]
    assert "x.com/intent/tweet" in body
    assert "requires_human_send" in body
    assert not re.search(r"\b(httpx|requests|urlopen)\b", body)
    assert callable(publish_payload)


# ====================================================== salience şeffaflığı
def test_salience_popover_states_it_is_not_a_truth_score() -> None:
    """F3-07 DoD ve Spec §15 madde 13.

    0-100 arası bir skor, notu olmadan "doğruluk yüzdesi" olarak okunur.
    """
    source = (WEB_DIR / "feed.py").read_text(encoding="utf-8")
    assert "doğruluk skoru değildir" in source
    assert "etkileşim girdisi içermez" in source


def test_feed_does_not_store_personal_salience() -> None:
    """Kişisel bileşen (0-10) SAKLANMAZ (Spec §8.4/B, migration 0003).

    Ekran katmanı `salience` sütunlarına hiç dokunmamalıdır. (Aynı
    dosyada `review_flag` güncellemesi vardır — o F3-21'in denetim
    kuyruğudur ve skorla ilgisi yoktur; bu yüzden tarama tüm
    `UPDATE`'leri değil, salience yazımını arar.)
    """
    source = (WEB_DIR / "repository.py").read_text(encoding="utf-8")
    assert "personal_adjustment" in source

    writes = re.findall(
        r"(?:UPDATE\s+events\s+SET|INSERT\s+INTO\s+events)\s+([^\n]*)",
        source,
        flags=re.IGNORECASE,
    )
    for statement in writes:
        assert "salience" not in statement.lower(), (
            f"Ekran katmanı salience yazıyor: {statement!r}. "
            "Kişisel bileşen saklanamaz (Spec §8.4/B)."
        )


# ============================================================ canlı ekranlar
@pytest.fixture(scope="module")
def client():  # noqa: ANN201
    import os

    if not os.environ.get("PD_DATABASE_URL"):
        pytest.skip("PD_DATABASE_URL ayarlı değil — ekran testleri atlandı.")

    from politikdesk.api.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.db
@pytest.mark.parametrize(
    "path",
    ["/feed", "/feed/cards", "/briefing", "/onboarding/profile", "/admin/metrics", "/api/angles"],
)
def test_pages_render(client, path: str) -> None:  # noqa: ANN001
    response = client.get(path)
    assert response.status_code == 200, response.text[:300]


@pytest.mark.db
def test_feed_page_declares_silent_refresh(client) -> None:  # noqa: ANN001
    """F3-02 DoD: 30 sn'de bir sessiz yenileme."""
    body = client.get("/feed").text
    assert "/feed/cards" in body
    assert "30000" in body  # 30 sn


@pytest.mark.db
def test_onboarding_form_declares_no_ideology(client) -> None:  # noqa: ANN001
    body = client.get("/onboarding/profile").text
    assert "ideolojik soru yoktur" in body
    assert "KVKK m.6" in body


@pytest.mark.db
def test_generation_is_blocked_for_event_without_claims(client) -> None:  # noqa: ANN001
    """F3-11 DoD: API doğrudan çağrılsa da reddediyor."""
    from politikdesk.db import connection

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.id FROM events e
            WHERE e.merged_into_id IS NULL
              AND NOT EXISTS (SELECT 1 FROM claims c WHERE c.event_id = e.id)
            LIMIT 1
            """
        )
        row = cur.fetchone()

    if row is None:
        pytest.skip("İddiasız olay yok — kapı bu veriyle sınanamaz.")

    response = client.post(f"/api/events/{row['id']}/drafts", json={"angle": "inform"})
    assert response.status_code == 409
    assert response.json()["detail"]["reason"] in ("no_claims", "no_evidence")


@pytest.mark.db
def test_unknown_event_returns_404(client) -> None:  # noqa: ANN001
    assert client.get("/event/999999999").status_code == 404


def test_api_draft_action_and_publish_enforces_grounding(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:  # noqa: ANN001
    """D12: API seviyesinde grounding koruması (409 Conflict)."""
    from typing import Any

    from politikdesk.editorial import service

    mock_ungrounded = {
        "id": 201,
        "event_id": 1,
        "angle": "inform",
        "body": "Ungrounded body %999",
        "final_body": None,
        "is_grounded": False,
        "user_id": 1,
    }
    mock_grounded = {
        "id": 202,
        "event_id": 1,
        "angle": "inform",
        "body": "Grounded body",
        "final_body": None,
        "is_grounded": True,
        "user_id": 1,
    }

    def fake_get_draft(draft_id: int) -> dict[str, Any] | None:
        if draft_id == 201:
            return mock_ungrounded
        if draft_id == 202:
            return mock_grounded
        return None

    def fake_record_action(
        draft_id: int, action: str, stored_body: str | None, distance: float | None
    ) -> dict[str, Any]:
        return {"draft_id": draft_id, "action": action, "final_body": stored_body}

    monkeypatch.setattr(service.repository, "get_draft", fake_get_draft)
    monkeypatch.setattr(service.repository, "record_action", fake_record_action)

    # 1. Ungrounded accept -> 409
    res_accept_ungrounded = client.post("/api/drafts/201/action", json={"action": "accepted"})
    assert res_accept_ungrounded.status_code == 409
    assert res_accept_ungrounded.json()["detail"]["reason"] == "grounding_failed"

    # 2. Ungrounded publish -> 409
    res_publish_ungrounded = client.get("/api/drafts/201/publish")
    assert res_publish_ungrounded.status_code == 409
    assert res_publish_ungrounded.json()["detail"]["reason"] == "grounding_failed"

    # 3. Grounded accept -> 200
    res_accept_grounded = client.post("/api/drafts/202/action", json={"action": "accepted"})
    assert res_accept_grounded.status_code == 200
    assert res_accept_grounded.json()["action"] == "accepted"

    # 4. Grounded publish -> 200
    res_publish_grounded = client.get("/api/drafts/202/publish")
    assert res_publish_grounded.status_code == 200
    assert res_publish_grounded.json()["draft_id"] == 202


# ==================================================================== D11
def test_skip_link_has_visible_focus_styling() -> None:
    """D11: Ekran okuyucu / klavye kullanıcısı için skip-link focus olduğunda görünür olmalı."""
    from politikdesk.web.ui.css import stylesheet
    from politikdesk.web.ui.shell import page

    html = page("Test Sayfası", "<p>İçerik</p>")
    assert '<a class="sr" href="#main">İçeriğe atla</a>' in html

    css = stylesheet("/static")
    assert ".sr:focus" in css
    assert ".sr:focus-visible" in css
    assert "position:fixed" in css
    assert "clip:auto" in css
