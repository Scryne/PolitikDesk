"""F0-16 — mimari kural testi.

DoD: "Yasağı ihlal eden bir commit CI'ı kırıyor (deneyle doğrulanmış)."

İki test bunu birlikte kanıtlar:
  * test_repo_has_no_violations — mevcut repo temiz
  * test_checker_catches_violation — denetleyici gerçekten yakalıyor
    (yapay bir paketle deney; repo kirletilmez)
"""

from __future__ import annotations

from pathlib import Path

from scripts.check_architecture import REPO_ROOT, RULES, Rule, check


def test_repo_has_no_violations() -> None:
    violations = check(REPO_ROOT)
    assert violations == [], "\n".join(v.render(REPO_ROOT) for v in violations)


def test_evidence_llm_rule_is_registered() -> None:
    """Kuralın varlığı kazara silinmesin."""
    rule = next(r for r in RULES if r.package == "politikdesk/evidence")
    assert "politikdesk.llm" in rule.forbidden


def _make_fake_repo(tmp_path: Path, source: str) -> Path:
    package = tmp_path / "politikdesk" / "evidence"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "rules.py").write_text(source, encoding="utf-8")
    return tmp_path


def test_checker_catches_plain_import(tmp_path: Path) -> None:
    root = _make_fake_repo(tmp_path, "import politikdesk.llm.client\n")
    violations = check(root)
    assert len(violations) == 1
    assert violations[0].imported == "politikdesk.llm.client"


def test_checker_catches_from_import(tmp_path: Path) -> None:
    root = _make_fake_repo(tmp_path, "from politikdesk.llm.client import LLMClient\n")
    assert check(root), "from-import yakalanmadı"


def test_checker_catches_dynamic_import(tmp_path: Path) -> None:
    """AST'yi atlatmaya çalışan dinamik import da yakalanmalı."""
    root = _make_fake_repo(
        tmp_path,
        'import importlib\nm = importlib.import_module("politikdesk.llm.client")\n',
    )
    assert check(root), "dinamik import yakalanmadı"


def test_checker_allows_clean_module(tmp_path: Path) -> None:
    root = _make_fake_repo(
        tmp_path,
        "from politikdesk.db import connection\n\n\ndef compute() -> int:\n    return 1\n",
    )
    assert check(root) == []


def test_rule_dataclass_is_extensible(tmp_path: Path) -> None:
    """Kural tablosu yeni sınırlar için genişletilebilir olmalı."""
    package = tmp_path / "politikdesk" / "nlp"
    package.mkdir(parents=True)
    (package / "x.py").write_text("import politikdesk.editorial\n", encoding="utf-8")

    custom = (
        Rule(package="politikdesk/nlp", forbidden=("politikdesk.editorial",), reason="deney"),
    )
    assert check(tmp_path, custom)
