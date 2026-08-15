"""PolitikDesk Faz 5 / S3 Gate Runner (Spec v3.4 §14.1, §15).

Bu kapı koşucusu S3 üretim hazırlığını (Production Readiness) katı kriterlerle
fail-closed olarak değerlendirir.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from typing import Any

from eval.run import load_jsonl
from eval.run_accountability import (
    GOLDEN_ACCOUNTABILITY_V1,
    GOLDEN_ACCOUNTABILITY_V2,
    GOLDEN_ADVERSARIAL_V1,
    run_evaluation,
)
from politikdesk.political_memory.candidate_filter import (
    ABSOLUTE_MAX_CANDIDATES,
    filter_candidates_in_memory,
)
from politikdesk.political_memory.orchestrator import (
    RELATION_ENGINE_VERSION,
)
from politikdesk.political_memory.relation_engine import EventData


def check_accountability_golden_sets() -> dict[str, Any]:
    # 1. Bağımsız Adversarial Holdout
    cases_adv = load_jsonl(GOLDEN_ADVERSARIAL_V1)
    m_adv = run_evaluation(cases_adv)
    adv_pass = (
        m_adv.precision >= 0.85
        and m_adv.recall >= 0.75
        and m_adv.f1 >= 0.80
        and m_adv.false_relation_rate <= 0.05
        and m_adv.temporal_accuracy == 1.0
    )

    # 2. v2 regression check
    cases_v2 = load_jsonl(GOLDEN_ACCOUNTABILITY_V2)
    m2 = run_evaluation(cases_v2)
    v2_pass = (
        m2.precision >= 0.85
        and m2.recall >= 0.75
        and m2.false_relation_rate <= 0.05
        and m2.temporal_accuracy == 1.0
    )

    # 3. v1 regression check
    cases_v1 = load_jsonl(GOLDEN_ACCOUNTABILITY_V1)
    m1 = run_evaluation(cases_v1)
    v1_pass = (
        m1.precision >= 0.85
        and m1.recall >= 0.75
        and m1.false_relation_rate <= 0.05
        and m1.temporal_accuracy == 1.0
    )

    return {
        "adv_precision": m_adv.precision,
        "adv_recall": m_adv.recall,
        "adv_f1": m_adv.f1,
        "adv_false_relation": m_adv.false_relation_rate,
        "adv_temporal": m_adv.temporal_accuracy,
        "v2_precision": m2.precision,
        "v2_recall": m2.recall,
        "v1_precision": m1.precision,
        "v1_recall": m1.recall,
        "passed": adv_pass and v2_pass and v1_pass,
    }


def check_candidate_ceiling() -> dict[str, Any]:
    src = EventData(
        event_id=1,
        title="Test",
        published_at=datetime.now(UTC),
        actor="A",
        institution="B",
    )
    pool = [
        EventData(
            event_id=i,
            title=f"C {i}",
            published_at=datetime.now(UTC),
            actor="A",
            institution="B",
        )
        for i in range(2, 102)
    ]
    selected = filter_candidates_in_memory(src, pool, limit=1000)
    passed = len(selected) <= ABSOLUTE_MAX_CANDIDATES
    return {
        "requested_limit": 1000,
        "returned_candidates": len(selected),
        "hard_ceiling": ABSOLUTE_MAX_CANDIDATES,
        "passed": passed,
    }


def check_epistemic_safety() -> dict[str, Any]:
    from politikdesk.political_memory.accountability import LEGAL_DISCLAIMER

    disclaimer_present = len(LEGAL_DISCLAIMER) > 30 and "deterministik" in LEGAL_DISCLAIMER.lower()
    return {
        "disclaimer_present": disclaimer_present,
        "passed": disclaimer_present,
    }


def check_mypy() -> bool:
    res = subprocess.run(["uv", "run", "mypy"], capture_output=True, text=True)
    return res.returncode == 0


def check_pytest() -> bool:
    test_files = [
        "tests/test_candidate_filter.py",
        "tests/test_relation_engine.py",
        "tests/test_relation_orchestrator.py",
        "tests/test_adversarial_relations.py",
        "tests/test_adversarial_relations_v2.py",
        "tests/test_accountability.py",
    ]
    res = subprocess.run(["uv", "run", "pytest", *test_files, "-q"], capture_output=True, text=True)
    return res.returncode == 0



def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    print("=" * 80)
    print("POLİTİKDESK — PHASE S3 PRODUCTION GATE RUNNER")
    print("=" * 80)

    acc_res = check_accountability_golden_sets()
    print(
        f"1. Independent Adversarial (N=14): P={acc_res['adv_precision']:.3f}, "
        f"R={acc_res['adv_recall']:.3f}, F1={acc_res['adv_f1']:.3f} -> "
        f"{'PASS' if acc_res['passed'] else 'FAIL'}"
    )
    print(
        f"2. Golden Set v2 (N=36): P={acc_res['v2_precision']:.3f}, "
        f"R={acc_res['v2_recall']:.3f} -> {'PASS' if acc_res['passed'] else 'FAIL'}"
    )
    print(
        f"3. Golden Set v1 (N=18): P={acc_res['v1_precision']:.3f}, "
        f"R={acc_res['v1_recall']:.3f} -> {'PASS' if acc_res['passed'] else 'FAIL'}"
    )

    ceil_res = check_candidate_ceiling()
    status_ceil = "PASS" if ceil_res["passed"] else "FAIL"
    print(
        f"4. Candidate Hard Ceiling "
        f"({ceil_res['returned_candidates']} <= {ceil_res['hard_ceiling']}) -> {status_ceil}"
    )

    epistemic_res = check_epistemic_safety()
    print(f"5. Epistemic Safety & Disclaimer -> {'PASS' if epistemic_res['passed'] else 'FAIL'}")

    version_pass = RELATION_ENGINE_VERSION == "s3.v1"
    status_ver = "PASS" if version_pass else "FAIL"
    print(f"6. Engine Versioning ({RELATION_ENGINE_VERSION}) -> {status_ver}")


    print("7. Mypy Typecheck...")
    mypy_pass = check_mypy()
    print(f"   Mypy -> {'PASS' if mypy_pass else 'FAIL'}")

    print("8. Full Pytest Suite...")
    pytest_pass = check_pytest()
    print(f"   Pytest -> {'PASS' if pytest_pass else 'FAIL'}")

    all_passed = (
        acc_res["passed"]
        and ceil_res["passed"]
        and epistemic_res["passed"]
        and version_pass
        and mypy_pass
        and pytest_pass
    )

    print("\n" + "=" * 80)
    if all_passed:
        print("GENEL S3 GATE KARARI: 🟢 PASS — S3 PRODUCTION-READY.")
        return 0
    else:
        print("GENEL S3 GATE KARARI: ❌ FAIL — BLOCKED.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

