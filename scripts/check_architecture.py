"""Mimari kural denetleyicisi (F0-16).

Spec §11.2: `evidence/` modülü `llm/` modülünü import EDEMEZ.
Bu, P4'ün (şeffaflık > kesinlik) derleme-zamanı garantisidir: kanıt
durumu asla bir LLM çıktısı olamaz (Spec §8.1).

Denetim iki katmanlıdır:
  1. AST taraması — `import x` / `from x import y` ifadeleri
  2. Metin taraması — `importlib.import_module("...")` gibi dinamik kaçışlar

Kullanım:
    python -m scripts.check_architecture           # repo kökünü denetle
    python -m scripts.check_architecture <yol>     # verilen kökü denetle

Çıkış kodu 0 = temiz, 1 = ihlal var (CI'ı kırar).
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Rule:
    """Bir paketin import etmesi yasak olan modülleri tanımlar."""

    package: str  # repo köküne göre paket dizini
    forbidden: tuple[str, ...]  # yasak modül önekleri (nokta ayrımlı)
    reason: str


RULES: tuple[Rule, ...] = (
    Rule(
        package="politikdesk/evidence",
        forbidden=("politikdesk.llm",),
        reason=(
            "Spec §11.2 / §8.1: kanıt motoru deterministiktir. evidence_status "
            "hiçbir koşulda bir LLM çağrısının çıktısı olamaz."
        ),
    ),
    Rule(
        package="politikdesk/evidence",
        forbidden=("politikdesk.editorial",),
        reason=(
            "Spec §10.1 / B-95: kanıt motoru editoryal duruş veya profilden "
            "tamamen izoledir; kullanıcı tercihi kanıt durumunu etkileyemez."
        ),
    ),
)


@dataclass(frozen=True)
class Violation:
    file: Path
    line: int
    imported: str
    rule: Rule

    def render(self, root: Path) -> str:
        rel = self.file.relative_to(root).as_posix()
        return (
            f"{rel}:{self.line}: '{self.package_label}' paketi "
            f"'{self.imported}' modülünü import edemez.\n"
            f"    Gerekçe: {self.rule.reason}"
        )

    @property
    def package_label(self) -> str:
        return self.rule.package


def _is_forbidden(name: str | None, rule: Rule) -> bool:
    if not name:
        return False
    return any(name == f or name.startswith(f + ".") for f in rule.forbidden)


def _scan_ast(path: Path, rule: Rule) -> list[Violation]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        raise SystemExit(f"Ayrıştırma hatası: {path}: {exc}") from exc

    found: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden(alias.name, rule):
                    found.append(Violation(path, node.lineno, alias.name, rule))
        # `from . import x` (level>0) paket içidir; yasak modül dışarıdadır.
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and _is_forbidden(node.module, rule)
        ):
            found.append(Violation(path, node.lineno, node.module or "", rule))
    return found


def _scan_dynamic(path: Path, rule: Rule) -> list[Violation]:
    """`importlib.import_module("politikdesk.llm...")` gibi kaçışları yakalar."""
    found: list[Violation] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.split("#", 1)[0]
        for forbidden in rule.forbidden:
            for quote in ('"', "'"):
                if f"{quote}{forbidden}" in stripped:
                    found.append(Violation(path, lineno, forbidden, rule))
    return found


def check(root: Path = REPO_ROOT, rules: tuple[Rule, ...] = RULES) -> list[Violation]:
    violations: list[Violation] = []
    for rule in rules:
        package_dir = root / rule.package
        if not package_dir.is_dir():
            continue
        for py_file in sorted(package_dir.rglob("*.py")):
            violations.extend(_scan_ast(py_file, rule))
            violations.extend(_scan_dynamic(py_file, rule))
    return violations


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else REPO_ROOT
    violations = check(root)

    if not violations:
        checked = ", ".join(dict.fromkeys(r.package for r in RULES))
        print(f"[OK] Mimari kurallar temiz ({checked}).")
        return 0

    print(f"[HATA] {len(violations)} mimari kural ihlali:\n", file=sys.stderr)
    for v in violations:
        print(v.render(root), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
