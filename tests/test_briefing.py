"""Brifing testleri (F3-16, F3-17, F3-18).

Korunan iki karar:

  * **Brifing deterministiktir** — LLM kullanmaz. Günde iki kez e-postaya
    giden bir metnin halüsinasyon riski taşımaması, üslup akıcılığından
    önce gelir. Bir AST taraması bu kararı sabitler.
  * **E-postadaki linkler MUTLAK** — göreli adres e-posta istemcisinde
    hiçbir şeye çözülmez (F3-17 DoD).
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from politikdesk.briefing.generator import (
    SLOT_LABELS,
    STATUS_TEXT,
    BriefingContent,
    BriefingEvent,
)
from politikdesk.briefing.mailer import build_message, is_configured
from politikdesk.briefing.renderer import render_html, render_text
from politikdesk.config import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent
BRIEFING_DIR = REPO_ROOT / "politikdesk" / "briefing"


@pytest.fixture
def content() -> BriefingContent:
    return BriefingContent(
        briefing_date=date(2026, 8, 13),
        slot="morning",
        events=[
            BriefingEvent(
                event_id=42,
                title="TCMB politika faizini sabit tuttu",
                salience=78,
                status="developing",
                article_count=6,
                independent_count=4,
                independence_groups=3,
                has_primary_source=True,
                top_claim="Politika faizi yüzde 37'de sabit kaldı.",
                top_claim_status="strongly_corroborated",
            ),
            BriefingEvent(
                event_id=43,
                title="Tek gruptan raporlanan olay",
                salience=31,
                status="developing",
                article_count=2,
                independent_count=1,
                independence_groups=1,
                has_primary_source=False,
            ),
        ],
        upcoming=[
            {
                "id": 1,
                "title": "TÜİK enflasyon verisi",
                "expected_at": "2026-09-03T10:00:00+03:00",
                "expected_label": "03 Eyl 10:00",
                "source_name": "TÜİK",
            }
        ],
        unverified=[
            {
                "claim_id": 9,
                "event_id": 42,
                "event_title": "TCMB",
                "claim_text": "Piyasa beklentisi yüzde 36 idi.",
                "claim_type": "number",
                "evidence_status": "single_source",
                "status_text": "tek kaynaklı",
                "rule": "R5",
            }
        ],
    )


# ============================================================ deterministiklik
def test_briefing_package_makes_no_llm_calls() -> None:
    """Brifing üretimi `politikdesk.llm` import etmez.

    Bu, `evidence/` için konan mimari kuralın aynı gerekçeyle brifinge
    uygulanmasıdır: e-postaya giden metin, doğrulanmış veriden kurulur.
    """
    for path in BRIEFING_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert not name.startswith("politikdesk.llm"), (
                    f"{path.name} LLM import ediyor. Brifing deterministiktir "
                    "(bkz. briefing/generator.py modül başlığı)."
                )


# ================================================================== F3-16
def test_content_has_all_three_sections(content: BriefingContent) -> None:
    """DoD: olaylar + beklenen gelişmeler + doğrulanmamış iddialar."""
    text = render_text(content)
    assert "GÜNDEM" in text
    assert "BEKLENEN GELİŞMELER" in text
    assert "DOĞRULANMAMIŞ İDDİALAR" in text


def test_unverified_section_warns_against_sharing(content: BriefingContent) -> None:
    """Spec §15 madde 3: doğrulanmamışı doğrulanmış gibi sunma.

    Uyarı hem düz metinde hem HTML'de bulunmalı; cümle başındaki büyük
    harf farkı anlamlı değildir, bu yüzden karşılaştırma büyük/küçük
    harfe duyarsızdır.
    """
    warning = "doğrulanmış gibi paylaşılmamalıdır"
    assert warning in render_text(content).lower()
    assert warning in render_html(content).lower()


def test_single_group_event_carries_the_diversity_warning(
    content: BriefingContent,
) -> None:
    """Spec §10.3: koşul sağlanamıyorsa UI açıkça yazar."""
    # İşaret emoji değil, sözcük: "Dikkat:" (DESIGN.md Bölüm 13.4).
    # Korunan kısıt aynı — uyarı AÇIKÇA yazılıyor, sezdirilmiyor.
    assert content.events[1].diversity_note.startswith("Dikkat:")
    assert "tek bir yayın grubundan" in render_text(content)
    # Çok gruplu olayda uyarı YOK, sayı var:
    assert content.events[0].diversity_note == "3 farklı yayın grubu"


def test_status_badges_are_not_hidden(content: BriefingContent) -> None:
    """Spec §15 madde 3: kanıt durumu brifingde de gizlenmez.

    Rozet artık emoji değil, token renginde bir nokta + METİN ETİKETİ
    (DESIGN.md Bölüm 13.4 — emoji ikon olarak kullanılmaz). Kısıt aynı:
    durumun okunabilir olması. Değişen yalnızca gösterim.
    """
    html = render_html(content)
    assert STATUS_TEXT["strongly_corroborated"] in html
    assert STATUS_TEXT["single_source"] in html
    # Renk TEK BAŞINA taşıyıcı olmamalı: nokta varsa metin de var.
    assert html.count("border-radius:50%") <= html.count("teyitli") + html.count(
        "kaynaklı"
    ) + html.count("çelişkili") + html.count("doğrulanmamış")


# ================================================================== F3-17
def test_email_links_are_absolute(content: BriefingContent) -> None:
    """Göreli adres e-posta istemcisinde çözülmez (F3-17 DoD)."""
    html = render_html(content)
    assert 'href="http' in html
    assert 'href="/event' not in html
    assert "/event/42" in html


def test_open_tracking_pixel_is_embedded_when_token_given(
    content: BriefingContent,
) -> None:
    html = render_html(content, open_token="abc123")
    assert "/briefing/open/abc123.gif" in html
    assert 'width="1" height="1"' in html
    # Belirteç verilmezse piksel de yok:
    assert ".gif" not in render_html(content)


def test_smtp_is_optional() -> None:
    """SMTP yoksa brifing yine üretilir; gönderim atlanır."""
    assert not is_configured(Settings(env="test", smtp_host="", smtp_from="", smtp_user=""))
    assert is_configured(Settings(env="test", smtp_host="smtp.example", smtp_from="a@b.c"))


def test_message_is_multipart_with_text_first() -> None:
    message = build_message(
        subject="Sabah Brifingi",
        to="user@example.test",
        html_body="<p>merhaba</p>",
        text_body="merhaba",
        sender="bot@example.test",
    )
    assert message["Subject"] == "Sabah Brifingi"
    types = [part.get_content_type() for part in message.walk()]
    assert "text/plain" in types
    assert "text/html" in types


def test_slot_labels_cover_both_slots() -> None:
    assert set(SLOT_LABELS) == {"morning", "evening"}


def test_title_includes_date_and_slot(content: BriefingContent) -> None:
    assert content.title == "Sabah Brifingi — 13.08.2026"


def test_html_escapes_hostile_titles() -> None:
    """Kaynak başlıkları dış veridir; e-postaya ham girmez."""
    hostile = BriefingContent(
        briefing_date=date(2026, 8, 13),
        slot="morning",
        events=[
            BriefingEvent(
                event_id=1,
                title='<script>alert("x")</script>',
                salience=10,
                status="developing",
                article_count=1,
                independent_count=1,
                independence_groups=1,
                has_primary_source=False,
            )
        ],
    )
    html = render_html(hostile)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
