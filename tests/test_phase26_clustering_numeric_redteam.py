from politikdesk.clustering.numeric_guard import extract_numbers, find_conflicts

# ── ADVERSARIAL CLUSTERING TEST SET ──
CLUSTERING_TEST_PAIRS = [
    # 1. Aynı haber, farklı başlık (Beklenen: MERGE / SIMILAR)
    (
        "TCMB politika faizini yüzde 50 seviyesinde sabit tuttu",
        "Merkez Bankası Para Politikası Kurulu faiz kararını açıkladı: Politika faizi yüzde 50",
        True,
        "Aynı haber farklı başlık",
    ),
    (
        "TÜİK yıllık tüketici enflasyonunu yüzde 61,78 olarak açıkladı",
        "Temmuz ayı enflasyon rakamları belli oldu: Yıllık TÜFE yüzde 61,78",
        True,
        "Aynı haber resmi istatistik",
    ),
    # 2. Benzer fakat farklı olay (Beklenen: DO NOT MERGE)
    (
        "TCMB Para Politikası Kurulu politika faizini yüzde 50'de sabit tuttu",
        "Avrupa Merkez Bankası (ECB) faiz kararını açıkladı ve faiz yüzde 3,5 oldu",
        False,
        "Farklı merkez bankaları",
    ),
    (
        "Cumhurbaşkanı Erdoğan Ankara'da kabine toplantısına başkanlık etti",
        "Cumhurbaşkanı Erdoğan New York'ta BM Genel Kurulu'na hitap etti",
        False,
        "Aynı kişi, tamamen farklı olay ve mekan",
    ),
    (
        "İstanbul Büyükşehir Belediyesi yeni metro hattının temelini attı",
        "Ankara Büyükşehir Belediyesi yeni otobüs filosunu hizmete aldı",
        False,
        "Aynı kurum türü, farklı şehirler",
    ),
    # 3. Sayısal Çelişki / Farklı İstatistikler (Beklenen: DO NOT MERGE or CONFLICT)
    (
        "Merkez Bankası politika faizini yüzde 50 seviyesinde açıkladı",
        "Merkez Bankası politika faizini yüzde 45 seviyesinde açıkladı",
        False,
        "%50 vs %45 faiz çelişkisi",
    ),
    (
        "TÜİK yıllık enflasyon oranını yüzde 60 olarak duyurdu",
        "TÜİK yıllık enflasyon oranını yüzde 75 olarak duyurdu",
        False,
        "%60 vs %75 yıllık enflasyon çelişkisi",
    ),
    (
        "Türkiye ekonomisi yılın ilk çeyreğinde yüzde 5,7 büyüdü",
        "Türkiye ekonomisi yılın ilk çeyreğinde yüzde 2,1 büyüdü",
        False,
        "%5,7 vs %2,1 büyüme oranı çelişkisi",
    ),
    (
        "İşsizlik oranı geçen aya göre azalarak yüzde 8,5 oldu",
        "İşsizlik oranı geçen aya göre artarak yüzde 10,2 oldu",
        False,
        "%8,5 vs %10,2 işsizlik oranı çelişkisi",
    ),
]


def test_numeric_guard_adversarial_extraction() -> None:
    """Numeric Guard sayısal token çıkarımının doğruluğunu test eder."""
    # 1. Yüzde ifadeleri ve metrik bağlama
    nums_1 = extract_numbers("Merkez Bankası politika faizini yüzde 50 olarak açıkladı")
    assert len(nums_1) >= 1
    assert nums_1[0].metric == "policy_rate"
    assert nums_1[0].value == 50.0

    # 2. Yıllık TÜFE ve virgüllü değer
    nums_2 = extract_numbers("TÜİK verilerine göre yıllık enflasyon yüzde 61,78 seviyesinde gerçekleşti")
    assert len(nums_2) >= 1
    assert nums_2[0].metric == "cpi_annual"
    assert abs(nums_2[0].value - 61.78) < 0.01

    # 3. Büyüme oranı
    nums_3 = extract_numbers("Ekonomi yılın ikinci çeyreğinde yüzde 2,5 büyüdü")
    assert len(nums_3) >= 1
    assert nums_3[0].metric == "gdp_growth"
    assert abs(nums_3[0].value - 2.5) < 0.01


def test_numeric_guard_conflict_detection_pairs() -> None:
    """Sayısal olarak çelişen metinlerde NumericConflict üretildiğini doğrular."""
    conflict_pairs = [
        (
            "TCMB politika faizini yüzde 50 yaptı",
            "TCMB politika faizini yüzde 45 yaptı",
            "policy_rate",
        ),
        (
            "Yıllık enflasyon yüzde 60 oldu",
            "Yıllık enflasyon yüzde 70 oldu",
            "cpi_annual",
        ),
        (
            "Ekonomi yüzde 5 büyüdü",
            "Ekonomi yüzde 2 büyüdü",
            "gdp_growth",
        ),
        (
            "İşsizlik oranı yüzde 8,5 seviyesinde",
            "İşsizlik oranı yüzde 11 seviyesinde",
            "unemployment_rate",
        ),
    ]

    for text_a, text_b, expected_metric in conflict_pairs:
        conflicts = find_conflicts(text_a, text_b)
        assert len(conflicts) > 0, f"Çelişki bulunamadı: '{text_a}' vs '{text_b}'"
        assert conflicts[0].metric == expected_metric


def test_clustering_precision_recall_benchmark() -> None:
    """Hold-out adversarial kümeleme çiftlerinde Precision, Recall ve False Merge Rate ölçümü."""
    tp, fp, tn, fn = 0, 0, 0, 0

    for text_a, text_b, should_merge, _desc in CLUSTERING_TEST_PAIRS:
        # Sayısal çelişki kontrolü
        conflicts = find_conflicts(text_a, text_b)
        has_num_conflict = len(conflicts) > 0

        # Token ve simhash mesafesi
        toks_a = [w.lower() for w in text_a.split() if len(w) > 2]
        toks_b = [w.lower() for w in text_b.split() if len(w) > 2]

        # Jaccard & kelime örtüşmesi
        overlap = len(set(toks_a) & set(toks_b))
        union = len(set(toks_a) | set(toks_b))
        jaccard = overlap / union if union > 0 else 0.0

        predicted_merge = (jaccard > 0.35 or overlap >= 4) and not has_num_conflict

        if should_merge and predicted_merge:
            tp += 1
        elif not should_merge and predicted_merge:
            fp += 1
        elif not should_merge and not predicted_merge:
            tn += 1
        elif should_merge and not predicted_merge:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 1.0
    false_merge_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    false_split_rate = fn / (tp + fn) if (tp + fn) > 0 else 0.0

    print(f"\n[BENCHMARK] Precision: {precision:.3f} | Recall: {recall:.3f} | F1: {f1:.3f}")
    print(f"[BENCHMARK] False Merge Rate: {false_merge_rate:.3f} | False Split Rate: {false_split_rate:.3f}")

    assert precision >= 0.90, f"Precision düşük: {precision}"
    assert false_merge_rate <= 0.05, f"False merge oranı yüksek: {false_merge_rate}"
