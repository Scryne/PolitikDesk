"""Phase 26: 500+ Adversarial Türkçe Haber Başlığı ile Stres Testi."""

from __future__ import annotations

import pytest

from politikdesk.analysis.taxonomy import classify_category, classify_region
from scripts.generate_taxonomy_500_confusion_matrix import generate_500_dataset


@pytest.fixture(scope="module")
def dataset_500():
    return generate_500_dataset()


def test_taxonomy_500_adversarial_accuracy(dataset_500) -> None:
    """500 zorlu Türkçe başlıkta kategori ve bölge doğruluğunun >= %95 olduğunu doğrular."""
    cat_correct = 0
    reg_correct = 0
    total = len(dataset_500)

    for title, summary, exp_cat, exp_reg in dataset_500:
        pred_cat = classify_category(title, summary)
        pred_reg = classify_region(title, summary)

        if pred_cat == exp_cat:
            cat_correct += 1
        if pred_reg == exp_reg:
            reg_correct += 1

    cat_acc = (cat_correct / total) * 100.0
    reg_acc = (reg_correct / total) * 100.0

    print(f"\n[TAXONOMY 500 REDTEAM] Kategori Doğruluğu: %{cat_acc:.2f} ({cat_correct}/{total})")
    print(f"[TAXONOMY 500 REDTEAM] Bölge Doğruluğu: %{reg_acc:.2f} ({reg_correct}/{total})")

    assert cat_acc >= 95.0, f"Kategori doğruluğu %95 eşiğinin altında: %{cat_acc:.2f}"
    assert reg_acc >= 95.0, f"Bölge doğruluğu %95 eşiğinin altında: %{reg_acc:.2f}"
