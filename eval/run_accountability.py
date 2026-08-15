"""Hesap Sor & Event Relations Değerlendirme Koşucusu (S2 · Spec v3.4 §14.1).

DoD: Tek komutla `golden_set_accountability_v1.jsonl` üzerinden
ilişki hassasiyeti (precision), duyarlılığı (recall), false relation oranı ve
grounding tutarlılığını ölçer.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from eval.run import load_jsonl
from politikdesk.political_memory.relation_engine import EventData, evaluate_relation

GOLDEN_ADVERSARIAL_V1 = Path(__file__).resolve().parent / "golden_set_adversarial_v1.jsonl"
GOLDEN_ACCOUNTABILITY_V2 = Path(__file__).resolve().parent / "golden_set_accountability_v2.jsonl"
GOLDEN_ACCOUNTABILITY_V1 = Path(__file__).resolve().parent / "golden_set_accountability_v1.jsonl"
GOLDEN_ACCOUNTABILITY = (
    GOLDEN_ADVERSARIAL_V1
    if GOLDEN_ADVERSARIAL_V1.exists()
    else (
        GOLDEN_ACCOUNTABILITY_V2 if GOLDEN_ACCOUNTABILITY_V2.exists() else GOLDEN_ACCOUNTABILITY_V1
    )
)


@dataclass
class AccountabilityMetrics:
    total_cases: int
    positive_cases: int
    negative_cases: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    false_relation_rate: float
    temporal_accuracy: float
    category_results: dict[str, dict[str, int]]


def run_evaluation(cases: list[dict[str, Any]]) -> AccountabilityMetrics:
    if not cases:
        return AccountabilityMetrics(0, 0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, {})

    tp = 0
    fp = 0
    tn = 0
    fn = 0
    pos_count = 0
    neg_count = 0
    correct_temporal_blocks = 0
    total_temporal_negatives = 0
    category_results: dict[str, dict[str, int]] = {}

    for c in cases:
        src_raw = c["source_event"]
        tgt_raw = c["target_event"]
        is_pos = c.get("is_positive", True)
        category = c.get("category", "general")
        sim = c.get("semantic_similarity")  # Leakage-free: None if not in dataset

        if category not in category_results:
            category_results[category] = {"total": 0, "correct": 0}
        category_results[category]["total"] += 1

        src = EventData(
            event_id=src_raw["event_id"],
            title=src_raw["title"],
            published_at=datetime.fromisoformat(src_raw["published_at"]),
            actor=src_raw.get("actor"),
            institution=src_raw.get("institution"),
            entities=frozenset(src_raw.get("entities", [])),
            topics=tuple(src_raw.get("topics", [])),
            claims=tuple(src_raw.get("claims", [])),
        )

        tgt = EventData(
            event_id=tgt_raw["event_id"],
            title=tgt_raw["title"],
            published_at=datetime.fromisoformat(tgt_raw["published_at"]),
            actor=tgt_raw.get("actor"),
            institution=tgt_raw.get("institution"),
            entities=frozenset(tgt_raw.get("entities", [])),
            topics=tuple(tgt_raw.get("topics", [])),
            claims=tuple(tgt_raw.get("claims", [])),
        )

        res = evaluate_relation(src, tgt, semantic_similarity=sim)

        if is_pos:
            pos_count += 1
            # Pozitif vaka: geçerli bir ilişki tespit edildi mi ve beklenen ilişki ile uyumlu mu?
            if res.is_valid and res.relation_type == c.get("expected_relation"):
                tp += 1
                category_results[category]["correct"] += 1
            else:
                fn += 1
        else:
            neg_count += 1
            # Negatif vaka: unresolved olarak elendi mi?
            if not res.is_valid:
                tn += 1
                category_results[category]["correct"] += 1
            else:
                fp += 1

            if "temporal" in category:
                total_temporal_negatives += 1
                if not res.is_valid:
                    correct_temporal_blocks += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    false_rel_rate = fp / len(cases) if cases else 0.0
    temp_acc = (
        (correct_temporal_blocks / total_temporal_negatives)
        if total_temporal_negatives > 0
        else 1.0
    )

    return AccountabilityMetrics(
        total_cases=len(cases),
        positive_cases=pos_count,
        negative_cases=neg_count,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        false_relation_rate=false_rel_rate,
        temporal_accuracy=temp_acc,
        category_results=category_results,
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Hesap Sor & Event Relations Eval Koşucusu")
    parser.add_argument("--file", type=Path, default=GOLDEN_ACCOUNTABILITY)
    args = parser.parse_args()

    cases = load_jsonl(args.file)
    print("=" * 80)
    print("POLİTİKDESK — HESAP SOR & EVENT RELATIONS EVAL RAPORU (S3)")
    print(f"Değerlendirme Dosyası: {args.file.name} ({len(cases)} vaka)")
    print("=" * 80)

    if not cases:
        print("❌ HATA: Değerlendirme veri seti bulunamadı veya boş.")
        return 1

    m = run_evaluation(cases)

    print("\n## İlişki ve Hesap Verebilirlik Metrikleri\n")
    print(
        f"Toplam Vaka: {m.total_cases} ({m.positive_cases} pozitif, {m.negative_cases} negatif kontrol)"
    )
    print(f"Doğru Eşleşme (TP): {m.true_positives} · Yanlış Eşleşme (FP): {m.false_positives}")
    print(f"Doğru Red (TN): {m.true_negatives} · Kaçırılan (FN): {m.false_negatives}\n")

    print("| Metrik | Değer | Hedef (S3) | Durum |")
    print("|---|---|---|---|")
    print(
        f"| **Relation Precision** | {m.precision:.3f} | ≥ 0,85 | {'✅ PASS' if m.precision >= 0.85 else '❌ FAIL'} |"
    )
    print(
        f"| **Relation Recall** | {m.recall:.3f} | ≥ 0,75 | {'✅ PASS' if m.recall >= 0.75 else '❌ FAIL'} |"
    )
    print(f"| **F1 Score** | {m.f1:.3f} | ≥ 0,80 | {'✅ PASS' if m.f1 >= 0.80 else '❌ FAIL'} |")
    print(
        f"| **False Relation Rate** | {m.false_relation_rate:.3f} | ≤ 0,05 | {'✅ PASS' if m.false_relation_rate <= 0.05 else '❌ FAIL'} |"
    )
    print(
        f"| **Temporal Compatibility** | {m.temporal_accuracy:.3f} | 1.000 | {'✅ PASS' if m.temporal_accuracy == 1.0 else '❌ FAIL'} |\n"
    )

    print("## Kategori Bazlı Başarı Oranları\n")
    for cat, stats in m.category_results.items():
        acc = (stats["correct"] / stats["total"]) * 100 if stats["total"] > 0 else 0.0
        print(f"- **{cat}**: {stats['correct']}/{stats['total']} (%{acc:.1f})")

    success = (
        m.precision >= 0.85
        and m.recall >= 0.75
        and m.f1 >= 0.80
        and m.false_relation_rate <= 0.05
        and m.temporal_accuracy == 1.0
    )
    print("\n" + "=" * 80)
    if success:
        print("GENEL SONUÇ: 🟢 TÜM S3 EVALUATION HEDEFLERİ SAĞLANDI.")
        return 0
    else:
        print("GENEL SONUÇ: ❌ S3 EVALUATION KRİTERLERİ KARŞILANMADI.")
        return 1

    print("| Metrik | Değer | Hedef (S2) | Durum |")
    print("|---|---|---|---|")
    print(
        f"| **Relation Precision** | {m.precision:.3f} | ≥ 0,90 | {'✅ PASS' if m.precision >= 0.90 else '❌ FAIL'} |"
    )
    print(
        f"| **Relation Recall** | {m.recall:.3f} | ≥ 0,80 | {'✅ PASS' if m.recall >= 0.80 else '❌ FAIL'} |"
    )
    print(f"| **F1 Score** | {m.f1:.3f} | — | — |")
    print(
        f"| **False Relation Rate** | {m.false_relation_rate:.3f} | ≤ 0,05 | {'✅ PASS' if m.false_relation_rate <= 0.05 else '❌ FAIL'} |"
    )
    print(
        f"| **Temporal Compatibility** | {m.temporal_accuracy:.3f} | 1.000 | {'✅ PASS' if m.temporal_accuracy == 1.0 else '❌ FAIL'} |"
    )
    print("\n" + "=" * 80)

    passed = (
        m.precision >= 0.90
        and m.recall >= 0.80
        and m.false_relation_rate <= 0.05
        and m.temporal_accuracy == 1.0
    )
    if passed:
        print("GENEL SONUÇ: 🟢 TÜM S2 HEDEFLERİ SAĞLANDI.")
        return 0
    else:
        print("GENEL SONUÇ: ❌ BAZI HEDEFLERİN ALTINDA KALINDI.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
