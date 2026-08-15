"""Kapı G4′ — Faz 5 Otomatik Ölçüm ve Denetim Koşucusu (G4.4).

Bu betik, 9 kapı koşulunun tamamını canlı veritabanı, fetch logları,
metrik tabloları ve Golden Set eval harness üzerinden otomatik ve fail-closed
biçimde ölçer. Eksik veya sıfır veri durumunda asla yapay PASS üretmez.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from eval.run import (
    GOLDEN_ARTICLES,
    Thresholds,
    clustering_metrics,
    load_jsonl,
    replay_clustering,
)
from politikdesk.config import get_settings
from politikdesk.db import connection


class GateStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING_OBSERVATION = "PENDING_OBSERVATION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"



@dataclass
class GateResult:
    num: int
    name: str
    target: str
    measured: str
    status: GateStatus
    evidence: str

    @property
    def passed(self) -> bool:
        return self.status == GateStatus.PASS


def check_continuity(cur: Any) -> GateResult:
    """1. Kesintisiz uçtan uca akış (Hedef: 7 gün)."""
    cur.execute("""
        SELECT min(first_seen_at) as min_ts, max(first_seen_at) as max_ts, count(*) as count
        FROM articles;
    """)
    row = cur.fetchone()
    if not row or not row["min_ts"] or not row["max_ts"] or (row["count"] or 0) == 0:
        return GateResult(
            1,
            "Kesintisiz uçtan uca akış",
            "7 gün",
            "0 gün (veri yok)",
            GateStatus.FAIL,
            "Articles tablosu boş veya veri bulunamadı",
        )

    min_ts: datetime = row["min_ts"]
    max_ts: datetime = row["max_ts"]
    span = (max_ts - min_ts).total_seconds() / 86400.0
    measured = f"{span:.1f} gün ({row['count']} makale)"
    evidence = f"{min_ts.strftime('%Y-%m-%d')} -> {max_ts.strftime('%Y-%m-%d')}"

    if span >= 7.0:
        return GateResult(
            1, "Kesintisiz uçtan uca akış", "7 gün", measured, GateStatus.PASS, evidence
        )
    return GateResult(
        1, "Kesintisiz uçtan uca akış", "7 gün", measured, GateStatus.PENDING_OBSERVATION, evidence
    )


def check_collection_failures(cur: Any, hours: int = 24) -> GateResult:
    """2. Toplama arıza oranı (Hedef: <= %2, min 100 fetch)."""
    cur.execute(
        """
        SELECT
            count(*) as total,
            count(*) FILTER (WHERE NOT succeeded) as failed
        FROM source_fetch_log
        WHERE started_at >= now() - make_interval(hours => %s);
        """,
        (hours,),
    )
    row = cur.fetchone()
    total = row["total"] or 0
    failed = row["failed"] or 0

    if total < 100:
        return GateResult(
            2,
            "Toplama arıza oranı",
            "≤ %2",
            f"%0 ({total} fetch)",
            GateStatus.INSUFFICIENT_DATA,
            f"Son {hours} saatte minimum 100 fetch gerekli (mevcut: {total})",
        )

    rate = (failed * 100.0) / total
    status = GateStatus.PASS if rate <= 2.0 else GateStatus.FAIL
    measured = f"%{rate:.2f}"
    evidence = f"Son {hours} saat: {failed}/{total} arıza"
    return GateResult(2, "Toplama arıza oranı", "≤ %2", measured, status, evidence)


def check_correction_rate(cur: Any) -> GateResult:
    """3. Correction / Düzeltme oranı (Hedef: <= %3, min 34 açılan olay)."""
    cur.execute("""
        WITH opened AS (
            SELECT DISTINCT event_id
            FROM user_activity
            WHERE kind = 'event_open' AND event_id IS NOT NULL
        )
        SELECT
            (SELECT count(DISTINCT ef.event_id)
             FROM event_feedback ef
             JOIN opened o ON o.event_id = ef.event_id) as feedback_count,
            count(*) as opened_count
        FROM opened;
    """)
    row = cur.fetchone()
    opened = row["opened_count"] or 0
    feedback = row["feedback_count"] or 0

    if opened < 34:
        rate_str = f"%{(feedback * 100.0 / opened):.1f}" if opened > 0 else "%0"
        evidence_msg = (
            f"İstatistiki anlamlılık için min 34 açılan olay gerekli "
            f"(mevcut: {opened}, feedback: {feedback})"
        )
        return GateResult(
            3,
            "Correction oranı",
            "≤ %3",
            f"{rate_str} ({opened} açılan olay)",
            GateStatus.INSUFFICIENT_DATA,
            evidence_msg,
        )


    rate = (feedback * 100.0) / opened
    status = GateStatus.PASS if rate <= 3.0 else GateStatus.FAIL
    measured = f"%{rate:.2f}"
    evidence = f"{feedback}/{opened} açılan olaya editoryal düzeltme/itiraz geldi"
    return GateResult(3, "Correction oranı", "≤ %3", measured, status, evidence)


def check_diversity_ratio(cur: Any) -> GateResult:
    """4. Diversity ratio (Hedef: >= 2.5, min 10 açılan olay)."""
    cur.execute("""
        SELECT avg(groups) AS val, count(*) AS n FROM (
            SELECT ua.event_id,
                   count(DISTINCT COALESCE(s.independence_group, s.slug)) AS groups
            FROM user_activity ua
            JOIN articles a ON a.event_id = ua.event_id
            JOIN sources s ON s.id = a.source_id
            WHERE ua.kind = 'event_open' AND ua.event_id IS NOT NULL
            GROUP BY ua.event_id
        ) seen;
    """)
    row = cur.fetchone()
    val = row["val"]
    n = row["n"] or 0

    if n < 10 or val is None:
        return GateResult(
            4,
            "Diversity ratio",
            "≥ 2,5",
            f"{val or 0.0:.2f} ({n} açılan olay)",
            GateStatus.INSUFFICIENT_DATA,
            f"Minimum 10 açılan olay gereklidir (mevcut: {n})",
        )

    status = GateStatus.PASS if val >= 2.5 else GateStatus.FAIL
    measured = f"{val:.2f}"
    evidence = f"{n} açılan olay üzerinden hesaplanan bağımsız kaynak grubu ortalaması"
    return GateResult(4, "Diversity ratio", "≥ 2,5", measured, status, evidence)


def check_clustering_golden_set() -> tuple[GateResult, GateResult, GateResult]:
    """5-7. Kümeleme Hassasiyeti, Duyarlılığı ve False Merge."""
    golden_path = Path(GOLDEN_ARTICLES)
    if not golden_path.is_file() or golden_path.stat().st_size == 0:
        fail_res = GateResult(
            5,
            "Pairwise precision (kümeleme)",
            "≥ 0,90",
            "0.000",
            GateStatus.FAIL,
            "Golden Set dosyası bulunamadı",
        )
        return (
            fail_res,
            GateResult(
                6,
                "Pairwise recall (kümeleme)",
                "≥ 0,80",
                "0.000",
                GateStatus.FAIL,
                "Golden Set dosyası bulunamadı",
            ),
            GateResult(
                7,
                "False merge (küme karıştırma)",
                "≤ 0,05",
                "1.000",
                GateStatus.FAIL,
                "Golden Set dosyası bulunamadı",
            ),
        )

    articles = load_jsonl(GOLDEN_ARTICLES)
    if not articles:
        return (
            GateResult(
                5,
                "Pairwise precision (kümeleme)",
                "≥ 0,90",
                "0.000",
                GateStatus.FAIL,
                "Golden Set boş",
            ),
            GateResult(
                6,
                "Pairwise recall (kümeleme)",
                "≥ 0,80",
                "0.000",
                GateStatus.FAIL,
                "Golden Set boş",
            ),
            GateResult(
                7,
                "False merge (küme karıştırma)",
                "≤ 0,05",
                "1.000",
                GateStatus.FAIL,
                "Golden Set boş",
            ),
        )

    from politikdesk.nlp.embedder import EmbeddingBackend, LocalEmbedder, build_backend

    embedder: EmbeddingBackend
    try:
        embedder = LocalEmbedder("intfloat/multilingual-e5-large")
    except Exception:
        embedder = build_backend()

    thresholds = Thresholds(t_high=0.92, t_low=0.88)
    assignment, reviewed = replay_clustering(articles, embedder, thresholds)
    metrics = clustering_metrics(articles, assignment, reviewed)

    # 5. Precision
    p_passed = metrics.precision >= 0.90
    g5 = GateResult(
        5,
        "Pairwise precision (kümeleme)",
        "≥ 0,90",
        f"{metrics.precision:.3f}",
        GateStatus.PASS if p_passed else GateStatus.FAIL,
        f"Golden Set v1 ({metrics.articles} makale, {metrics.gold_events} gerçek olay)",
    )

    # 6. Recall
    r_passed = metrics.recall >= 0.80
    g6 = GateResult(
        6,
        "Pairwise recall (kümeleme)",
        "≥ 0,80",
        f"{metrics.recall:.3f}",
        GateStatus.PASS if r_passed else GateStatus.FAIL,
        f"F1: {metrics.f1:.3f}",
    )

    # 7. False Merge
    fm_passed = metrics.false_merge_rate <= 0.05
    g7 = GateResult(
        7,
        "False merge (küme karıştırma)",
        "≤ 0,05",
        f"{metrics.false_merge_rate:.3f}",
        GateStatus.PASS if fm_passed else GateStatus.FAIL,
        f"{len(metrics.impure_clusters)} karışan küme / {metrics.predicted_clusters} toplam küme",
    )

    return g5, g6, g7


def check_grounding_rate(cur: Any) -> GateResult:
    """8. Sayı/tarih grounding hatası (Hedef: %0)."""
    cur.execute("""
        SELECT
            count(*) as total_drafts,
            count(*) FILTER (
                WHERE user_action IN ('accepted', 'edited', 'published')
            ) as accepted_drafts,
            count(*) FILTER (
                WHERE user_action IN ('accepted', 'edited', 'published') AND is_grounded = false
            ) as ungrounded_drafts
        FROM drafts;
    """)
    row = cur.fetchone()
    total = row["total_drafts"] or 0
    accepted = row["accepted_drafts"] or 0
    ungrounded = row["ungrounded_drafts"] or 0

    if accepted == 0:
        return GateResult(
            8,
            "Sayı/tarih grounding hatası",
            "%0",
            "0 kabul taslak",
            GateStatus.PENDING_OBSERVATION,
            f"Toplam {total} taslak üretildi, henüz kabul edilmiş taslak yok",
        )

    rate = ungrounded * 100.0 / accepted
    status = GateStatus.PASS if ungrounded == 0 else GateStatus.FAIL
    measured = f"%{rate:.1f}"
    evidence = (
        f"{accepted} kabul edilen taslaktan {ungrounded} tanesi dayanaksız (grounding engelli)"
    )
    return GateResult(8, "Sayı/tarih grounding hatası", "%0", measured, status, evidence)


def check_briefing_delivery(cur: Any) -> GateResult:
    """9. Brifing akışı ve dağıtım (Hedef: 14 beklenen slot)."""
    cur.execute("""
        SELECT
            count(*) as total,
            count(*) FILTER (WHERE sent_at IS NOT NULL) as sent,
            count(*) FILTER (WHERE send_error IS NOT NULL) as errors
        FROM briefings;
    """)
    row = cur.fetchone()
    total = row["total"] or 0
    sent = row["sent"] or 0
    errors = row["errors"] or 0

    settings = get_settings()

    if total < 14:
        obs_msg = (
            f"7 günlük dağıtım penceresi için 14 slot gereklidir "
            f"(mevcut: {total}, gönderilen: {sent})"
        )
        return GateResult(
            9,
            "Brifing akışı ve dağıtım",
            "7 gün (14 slot)",
            f"{total} brifing",
            GateStatus.PENDING_OBSERVATION,
            obs_msg,
        )


    status = GateStatus.PASS if (sent == total and errors == 0) else GateStatus.FAIL
    measured = f"{sent}/{total} gönderildi"
    evidence = f"SMTP Host: '{settings.smtp_host or 'yapılandırılmadı'}', Hatalar: {errors}"
    return GateResult(9, "Brifing akışı ve dağıtım", "7 gün (14 slot)", measured, status, evidence)


def run_all_checks() -> list[GateResult]:
    results: list[GateResult] = []
    with connection() as conn, conn.cursor() as cur:
        results.append(check_continuity(cur))
        results.append(check_collection_failures(cur, hours=24))
        results.append(check_correction_rate(cur))
        results.append(check_diversity_ratio(cur))

    g5, g6, g7 = check_clustering_golden_set()
    results.extend([g5, g6, g7])

    with connection() as conn, conn.cursor() as cur:
        results.append(check_grounding_rate(cur))
        results.append(check_briefing_delivery(cur))

    return results


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Kapı G4′ Faz 5 Doğrulama Koşucusu")
    parser.add_argument("--strict", action="store_true", help="Tüm koşullar geçmezse exit(1)")
    args = parser.parse_args()

    print("=" * 80)
    print("POLİTİKDESK — KAPI G4′ FAZ 5 TEKNİK VE OPERASYONEL DENETİM RAPORU")
    print(f"Tarih: {datetime.now(UTC):%Y-%m-%d %H:%M:%S UTC}")
    print("=" * 80)

    results = run_all_checks()

    print(f"{'#':<3} | {'Koşul':<35} | {'Hedef':<12} | {'Ölçülen':<22} | {'Durum':<20} | {'Kanıt'}")
    print("-" * 125)
    all_passed = True
    for r in results:
        status_label = {
            GateStatus.PASS: "🟢 PASS",
            GateStatus.FAIL: "❌ FAIL",
            GateStatus.PENDING_OBSERVATION: "🟡 PENDING_OBS",
            GateStatus.INSUFFICIENT_DATA: "⚪ INSUFFICIENT",
        }.get(r.status, str(r.status))

        if r.status != GateStatus.PASS:
            all_passed = False
        line = (
            f"{r.num:<3} | {r.name:<35} | {r.target:<12} | "
            f"{r.measured:<22} | {status_label:<20} | {r.evidence}"
        )
        print(line)


    print("=" * 80)
    if all_passed:
        print("GENEL SONUÇ: 🟢 TÜM KOŞULLAR GEÇTİ — G4′ KAPISI RESMEN KAPATILDI.")
        return 0
    else:
        print("GENEL SONUÇ: 🟡 BAZI KOŞULLAR PENDING_OBSERVATION / INSUFFICIENT_DATA DURUMUNDA.")
        if args.strict:
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(main())
