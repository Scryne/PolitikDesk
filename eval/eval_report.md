# Eval Raporu (F2-16)

Eşikler: T_HIGH=0.92 · T_LOW=0.88 · zaman penceresi=72sa · jaccard≥0.25

## Kümeleme

55 makale · 36 gerçek olay · 38 üretilen küme

| Metrik | Değer | G2 hedefi | Durum |
|---|---|---|---|
| Pairwise precision | 0.875 | ≥ 0,90 | ❌ |
| Pairwise recall | 0.824 | ≥ 0,80 | ✅ |
| F1 | 0.848 | — | — |
| **Otomatik precision** | 1.000 | ≥ 0,90 | ✅ |
| **False merge (küme)** | 0.026 | ≤ 0,05 | ✅ |

Denetime düşen makale: 7/55 · otomatik birleştirilen çift: 15

Karışık kümeler: [26]

## İddia ve kanıt

24 iddia

| Metrik | Değer | G2 hedefi | Durum |
|---|---|---|---|
| `evidence_status` doğruluğu | 1.000 | ≥ 0,95 | ✅ |
| Kural eşleşmesi | 1.000 | — | — |
| Sayısal normalizasyon | 1.000 | ≥ 0,95 | ✅ |

### `evidence_status` dağılımı (B-37 / İtiraz-2)

- `strongly_corroborated`: 5 (%20.8)
- `partially_corroborated`: 5 (%20.8)
- `single_source`: 7 (%29.2)
- `contradicted`: 2 (%8.3)
- `unverified`: 5 (%20.8)


