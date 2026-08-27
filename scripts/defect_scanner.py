from __future__ import annotations

import os
import re

patterns: dict[str, re.Pattern[str]] = {
    "FIXME/XXX": re.compile(r"\b(FIXME|XXX)\b"),
    "TODO": re.compile(r"\bTODO\b"),
    "Bare Except": re.compile(r"except\s*:"),
    "Print Statement": re.compile(r"^\s*print\("),
    "NotImplemented": re.compile(r"raise\s+NotImplementedError"),
    "Hardcoded Secret": re.compile(r"""(api_key|secret|password)\s*=\s*['"][^'"]{8,}['"]"""),
}

findings: dict[str, list[tuple[str, int, str]]] = {k: [] for k in patterns}
src_dir = "politikdesk"

for root, _, files in os.walk(src_dir):
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            with open(p, encoding="utf-8", errors="ignore") as fp:
                for idx, line in enumerate(fp, 1):
                    for k, pat in patterns.items():
                        if pat.search(line):
                            findings[k].append((p, idx, line.strip()))

for k, items in findings.items():
    print(f"=== {k}: {len(items)} occurrences ===")
    for p, idx, line_str in items[:8]:
        print(f"  {p}:{idx} -> {line_str}")
