"""PolitikDesk Otomatik Üretim Kapıları (Production Gates) — Faz H.

Tüm kritik üretim önkoşullarını otomatik olarak denetler ve herhangi bir
arızada sıfır olmayan çıkış kodu döner.

Kullanım:
    python -m scripts.production_gates
"""

from __future__ import annotations

import sys

# Windows konsolunda UTF-8 / cp1254 kodlama hatalarını önle
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run_gate(name: str, check_fn) -> bool:
    print(f"[*] Running Gate: {name}...", end=" ", flush=True)
    try:
        ok, msg = check_fn()
        if ok:
            print(f"[PASS] {msg}")
            return True
        else:
            print(f"[FAIL] {msg}")
            return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


# 1. Health & Database Gate (Hardened Field-Level Invariant Check)
def check_db_and_sources() -> tuple[bool, str]:
    from politikdesk.db import connection
    from politikdesk.ingestion.sources import load_all_configs

    cfgs = {s.slug: s for s in load_all_configs()}
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT slug, name, tier, kind, access_method, tos_status FROM sources;")
        db_sources = {row["slug"]: row for row in cur.fetchall()}

    if len(cfgs) != len(db_sources) or len(cfgs) != 101:
        return False, f"Source count mismatch: YAML={len(cfgs)}, DB={len(db_sources)}"

    mismatches = []
    for slug, y_src in cfgs.items():
        if slug not in db_sources:
            mismatches.append(f"Missing in DB: {slug}")
            continue
        d_src = db_sources[slug]
        if y_src.tier != d_src["tier"] or y_src.kind != d_src["kind"]:
            mismatches.append(f"{slug} attribute mismatch")
        if y_src.access_method != d_src["access_method"] or y_src.tos_status != d_src["tos_status"]:
            mismatches.append(f"{slug} access/tos mismatch")

    if mismatches:
        return False, f"Field mismatch in {len(mismatches)} sources: {mismatches[:3]}"

    return True, f"Reconciled {len(cfgs)} sources 1:1 with zero-diff field match."


# 2. Data Integrity & Orphan Gate
def check_data_integrity() -> tuple[bool, str]:
    from politikdesk.db import connection, fetch_one

    with connection() as conn, conn.cursor() as cur:
        # Check for orphan claims (claims with invalid event_id)
        cur.execute("""
            SELECT count(*) FROM claims c
            LEFT JOIN events e ON e.id = c.event_id
            WHERE e.id IS NULL;
        """)
        orphan_claims = int(fetch_one(cur)["count"])

        # Check for orphan evidence (evidence with invalid claim_id or article_id)
        cur.execute("""
            SELECT count(*) FROM evidence ev
            LEFT JOIN claims c ON c.id = ev.claim_id
            LEFT JOIN articles a ON a.id = ev.article_id
            WHERE c.id IS NULL OR a.id IS NULL;
        """)
        orphan_evidence = int(fetch_one(cur)["count"])

        # Check for orphan articles (articles with invalid source_id)
        cur.execute("""
            SELECT count(*) FROM articles a
            LEFT JOIN sources s ON s.id = a.source_id
            WHERE s.id IS NULL;
        """)
        orphan_articles = int(fetch_one(cur)["count"])

    if orphan_claims == 0 and orphan_evidence == 0 and orphan_articles == 0:
        return True, "Zero orphan claims, evidence, or articles found in database."
    return False, (
        f"Integrity failure: {orphan_claims} claims, {orphan_evidence} evidence, "
        f"{orphan_articles} articles."
    )


# 3. Observability Gate
def check_observability() -> tuple[bool, str]:
    from politikdesk.ingestion.source_anomalies import (
        classify_duplicate_spike,
        classify_empty_feed,
    )

    r1 = classify_empty_feed(
        slug="test", adapter="rss", items_in_window=0, historical_daily_mean=50.0
    )
    r2 = classify_duplicate_spike(
        slug="test", adapter="rss", fetched_count=100, accepted_count=10, duplicate_count=90
    )
    if r1.status == "EMPTY_ANOMALY" and r2.status == "ANOMALOUS":
        return True, "Anomaly classifiers active and functioning."
    return False, "Anomaly classifiers failed expected outputs."


# 4. Security & SSRF Gate
def check_security_ssrf() -> tuple[bool, str]:
    from politikdesk.ingestion.http import HttpClient, UnsafeUrlError

    client = HttpClient()
    blocked = False
    try:
        client.get("http://127.0.0.1:8000/readyz")
    except UnsafeUrlError:
        blocked = True
    except Exception:
        blocked = False

    if blocked:
        return True, "SSRF loopback protection active (UnsafeUrlError raised)."
    return False, "SSRF loopback protection failed to block 127.0.0.1"


# 5. Architecture Gate
def check_architecture_rules() -> tuple[bool, str]:
    from scripts.check_architecture import main as arch_main

    res = arch_main([])
    if res == 0:
        return True, "Clean architecture boundaries in politikdesk/evidence."
    return False, "Architecture guard reported violations."


# 6. Disaster Recovery & Backup Policy Gate (Hardened with Corruption Rejection Test)
def check_backup_and_dr() -> tuple[bool, str]:
    from pathlib import Path

    from politikdesk.backup_policy import default_backup_dir
    from scripts.backup import compute_sha256, verify

    target_dir = default_backup_dir()
    checksum = compute_sha256(Path("pyproject.toml"))

    # Test corruption rejection
    test_corrupt = Path("scratch/gate_corrupt_test.dump")
    test_corrupt.write_bytes(b"CORRUPTED_ARCHIVE_HEADER_INVALID")
    try:
        is_corrupt_rejected = not verify(test_corrupt)
    except Exception:
        is_corrupt_rejected = True
    finally:
        if test_corrupt.exists():
            test_corrupt.unlink()

    if target_dir and len(checksum) == 64 and is_corrupt_rejected:
        return (
            True,
            f"Backup policy valid ({target_dir.name}), SHA-256 active, fail-closed verified.",
        )
    return False, "Disaster recovery / backup engine failure."


# 7. Epistemic Grounding & Social Safety Gate
def check_grounding_and_safety_gates() -> tuple[bool, str]:
    from politikdesk.editorial.grounding_check import check_draft
    from politikdesk.editorial.social_publisher import evaluate_social_safety_gate

    g_rep = check_draft("Enflasyon yüzde 99.", claim_texts=["Enflasyon yüzde 50."])
    s_rep = evaluate_social_safety_gate("Büyük felaket gizleniyor ve tüm bankalar battı.")
    if (not g_rep.ok) and (not s_rep.passed):
        return True, "Grounding verifier and Social TCK 217/A safety gate active."
    return False, "Safety gate failed to reject invalid content."


def main():
    print("=" * 70)
    print("POLITIKDESK PRODUCTION READINESS GATES (PHASE 4 CERTIFICATION)")
    print("=" * 70)

    gates = [
        ("Source & Database Reconciliation Gate", check_db_and_sources),
        ("Data Integrity & Foreign Key Gate", check_data_integrity),
        ("Observability & Anomaly Model Gate", check_observability),
        ("Network Security & SSRF Guard Gate", check_security_ssrf),
        ("Architecture Boundary Isolation Gate", check_architecture_rules),
        ("Disaster Recovery & Backup Policy Gate", check_backup_and_dr),
        ("Epistemic Grounding & Social Safety Gate", check_grounding_and_safety_gates),
    ]

    passed = 0
    for name, fn in gates:
        if run_gate(name, fn):
            passed += 1

    print("=" * 70)
    print(f"GATES PASSED: {passed} / {len(gates)}")
    if passed == len(gates):
        print("[SUCCESS] All production gates passed.")
        sys.exit(0)
    else:
        print("[FAILURE] One or more production gates failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
