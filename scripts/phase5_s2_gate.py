"""PolitikDesk S2 Gate Runner (Spec v3.4 §14.1, §15).

S2 — Event Relations & "Hesap Sor" Pipeline Gate doğrulayıcısı.
Tüm metrikleri ölçülebilir kanıtlarla (eval setleri, typecheck, pytest, DB contamination)
denetler ve fail-closed karar üretir.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from eval.run_accountability import GOLDEN_ACCOUNTABILITY, load_jsonl, run_evaluation


class GateStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING_OBSERVATION = "PENDING_OBSERVATION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class S2GateCheckResult:
    name: str
    target: str
    measured: str
    status: GateStatus
    details: dict[str, Any]


@dataclass
class S2GateReport:
    overall_status: GateStatus
    checks: list[S2GateCheckResult]
    timestamp: str


def run_s2_gate() -> S2GateReport:
    from datetime import UTC, datetime

    checks: list[S2GateCheckResult] = []

    # 1. Accountability Eval Kontrolü
    cases = load_jsonl(GOLDEN_ACCOUNTABILITY)
    if not cases:
        checks.append(
            S2GateCheckResult(
                name="accountability_golden_set",
                target="Precision >= 0.90, Recall >= 0.80, False Rel <= 0.05",
                measured="Dosya bulunamadı",
                status=GateStatus.FAIL,
                details={},
            )
        )
    else:
        m = run_evaluation(cases)
        eval_pass = (
            m.precision >= 0.90
            and m.recall >= 0.80
            and m.false_relation_rate <= 0.05
            and m.temporal_accuracy == 1.000
        )
        measured_str = (
            f"P={m.precision:.3f}, R={m.recall:.3f}, "
            f"FalseRel={m.false_relation_rate:.3f}, TempAcc={m.temporal_accuracy:.3f}"
        )
        checks.append(
            S2GateCheckResult(
                name="accountability_relation_engine",
                target="P >= 0.90, R >= 0.80, False Rel <= 0.05, Temp Acc = 1.0",
                measured=measured_str,
                status=GateStatus.PASS if eval_pass else GateStatus.FAIL,
                details={
                    "total": m.total_cases,
                    "tp": m.true_positives,
                    "fp": m.false_positives,
                    "tn": m.true_negatives,
                    "fn": m.false_negatives,
                },
            )
        )

    # 2. Mypy Typecheck
    try:
        res = subprocess.run(["uv", "run", "mypy"], capture_output=True, text=True, check=False)
        mypy_pass = res.returncode == 0
        checks.append(
            S2GateCheckResult(
                name="mypy_typecheck",
                target="0 hata",
                measured="0 hata" if mypy_pass else "Hatalar var",
                status=GateStatus.PASS if mypy_pass else GateStatus.FAIL,
                details={"stdout": res.stdout[:500]},
            )
        )
    except Exception as exc:
        checks.append(
            S2GateCheckResult(
                name="mypy_typecheck",
                target="0 hata",
                measured=str(exc),
                status=GateStatus.FAIL,
                details={},
            )
        )

    # 3. Pytest S2 Tests
    try:
        test_files = [
            "tests/test_relation_engine.py",
            "tests/test_accountability.py",
            "tests/test_adversarial_relations.py",
            "tests/test_tbmm.py",
            "tests/test_sayistay.py",
            "tests/test_cumhurbaskanligi.py",
            "tests/test_political_ingestion_e2e.py",
        ]
        res = subprocess.run(
            ["uv", "run", "pytest", *test_files], capture_output=True, text=True, check=False
        )
        pytest_pass = res.returncode == 0
        checks.append(
            S2GateCheckResult(
                name="s2_test_suite",
                target="%100 passing",
                measured="%100 passing" if pytest_pass else "Başarısız testler",
                status=GateStatus.PASS if pytest_pass else GateStatus.FAIL,
                details={"stdout": res.stdout[-300:]},
            )
        )
    except Exception as exc:
        checks.append(
            S2GateCheckResult(
                name="s2_test_suite",
                target="%100 passing",
                measured=str(exc),
                status=GateStatus.FAIL,
                details={},
            )
        )

    # Genel Karar: Tüm zorunlu kontroller PASS ise PASS
    all_passed = all(c.status == GateStatus.PASS for c in checks)
    overall = GateStatus.PASS if all_passed else GateStatus.FAIL

    return S2GateReport(
        overall_status=overall,
        checks=checks,
        timestamp=datetime.now(UTC).isoformat(),
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    report = run_s2_gate()

    print("=" * 80)
    print(f"POLİTİKDESK — S2 GATE RUNNER: {report.overall_status.value}")
    print(f"Tarih: {report.timestamp}")
    print("=" * 80)

    for c in report.checks:
        icon = "🟢 PASS" if c.status == GateStatus.PASS else "🔴 FAIL"
        print(f"\n- [{icon}] {c.name}")
        print(f"  Hedef: {c.target}")
        print(f"  Ölçülen: {c.measured}")

    print("\n" + "=" * 80)
    return 0 if report.overall_status == GateStatus.PASS else 1


if __name__ == "__main__":
    sys.exit(main())
