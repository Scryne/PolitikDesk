"""Eval koşucusu (F2-16).

DoD: Tek komutla Golden Set koşuluyor; precision/recall/false-merge/status
doğruluğu rapor ediliyor.

    python -m eval.run
    python -m eval.run --t-high 0.88 --t-low 0.80      # F2-14 eşik taraması
    python -m eval.run --sweep                          # eşik eğrisi

## Neden bu koşucu veritabanı kullanmaz

Kümeleme kararı `clustering/assigner.py` içinde **saf** tutuldu; bu koşucu
o saf fonksiyonu Golden Set üzerinde yeniden oynatır. Böylece:

  * F2-14 (eşik kalibrasyonu) her deneme için veritabanı kurmak zorunda
    değildir — yüzlerce eşik denemesi saniyeler sürer,
  * ölçüm **tekrar üretilebilirdir**: aynı girdi her zaman aynı sonucu
    verir, üretim veritabanının o anki durumundan bağımsız.

## Ölçülenler

| Metrik | Tanım | G2 hedefi |
|---|---|---|
| Pairwise precision | Aynı kümeye atanan çiftlerin kaçı gerçekten aynı olay | ≥ %90 |
| Pairwise recall | Aynı olaydaki çiftlerin kaçı aynı kümeye atandı | ≥ %80 |
| False merge (küme) | Birden çok gerçek olayı karıştıran küme oranı | ≤ %5 **pazarlıksız** |
| `evidence_status` doğruluğu | Kural motorunun elle etikete uyumu | ≥ %95 |
| Sayısal normalizasyon | `normalized_value` doğruluğu | ≥ %95 |
| **`evidence_status` dağılımı** | B-37 / İtiraz-2: 🟢 oranı %10 altındaysa
  kaynak portföyü sorunu | — |
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from politikdesk.clustering.assigner import (  # noqa: E402
    ArticleFeatures,
    EventCandidate,
    Thresholds,
    decide,
)
from politikdesk.clustering.centroid import add_member, cosine  # noqa: E402
from politikdesk.evidence.rules import compute_status  # noqa: E402

GOLDEN_ARTICLES = REPO_ROOT / "eval" / "golden_set_v1.jsonl"
GOLDEN_CLAIMS = REPO_ROOT / "eval" / "golden_claims_v1.jsonl"


# ------------------------------------------------------------------ veri
def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path.name}:{lineno} gecersiz JSON: {exc}") from exc
    return out


# ------------------------------------------------------------- kümeleme
@dataclass
class _Cluster:
    centroid: list[float]
    count: int
    entities: frozenset[str]
    key_entities: frozenset[str]
    last_update_at: Any
    text: str


def replay_clustering(
    articles: list[dict[str, Any]],
    embedder: Any,
    thresholds: Thresholds,
    *,
    review_as: str = "merge",
) -> tuple[dict[str, int], set[str]]:
    """Kümelemeyi Golden Set üzerinde yeniden oynatır.

    Makaleler **yayın zamanına göre** işlenir — üretimdeki sıranın aynısı.
    Sıra değişirse sonuç değişir; bu, kümelemenin artımlı olmasının doğal
    sonucudur ve ölçümün tekrar üretilebilir kalması için sabitlenir.

    `review_as` — denetim kuyruğuna düşen atamalar nasıl sayılsın:

      "merge"  (varsayılan) Kuyruk hiç işlenmemiş gibi: atama korunur.
               **Kötümser** ölçüm; sistemin kendi başına bıraktığı durum.
      "split"  İnsan hepsini reddetmiş gibi: makale yeni olay olur.

    İkisinin arası gerçek performanstır. `assign` (otomatik) atamalar her
    iki modda da aynıdır — G2'nin asıl ölçtüğü şey odur: sistemin
    **sormadan** verdiği kararların kalitesi.

    İkinci dönen değer, denetime düşen makalelerin kimlikleridir.
    """
    ordered = sorted(articles, key=lambda a: a.get("published_at", ""))
    texts = [f"{a['title']} {a.get('excerpt', '')}".strip() for a in ordered]
    vectors = embedder.embed(texts)

    clusters: dict[int, _Cluster] = {}
    assignment: dict[str, int] = {}
    reviewed: set[str] = set()
    next_id = 1

    for article, vector in zip(ordered, vectors, strict=True):
        entities = frozenset(article.get("entities", []))
        key_entities = frozenset(article.get("key_entities", []))
        published_at = article.get("published_at", "")

        features = ArticleFeatures(
            article_id=0,
            embedding=vector,
            entities=entities,
            key_entities=key_entities,
            published_at=_as_datetime(published_at),
            text=f"{article['title']} {article.get('excerpt', '')}",
        )
        candidates = [
            EventCandidate(
                event_id=cluster_id,
                similarity=cosine(vector, cluster.centroid),
                entities=cluster.entities,
                key_entities=cluster.key_entities,
                last_update_at=cluster.last_update_at,
                text_sample=cluster.text,
            )
            for cluster_id, cluster in clusters.items()
        ]

        result = decide(features, candidates, thresholds)
        if result.needs_review:
            reviewed.add(article["article_id"])

        forced_new = result.needs_review and review_as == "split"
        if result.creates_event or result.event_id is None or forced_new:
            clusters[next_id] = _Cluster(
                centroid=list(vector),
                count=1,
                entities=entities,
                key_entities=key_entities,
                last_update_at=features.published_at,
                text=features.text,
            )
            assignment[article["article_id"]] = next_id
            next_id += 1
        else:
            cluster = clusters[result.event_id]
            cluster.centroid = add_member(cluster.centroid, cluster.count, vector)
            cluster.count += 1
            cluster.entities = cluster.entities | entities
            cluster.key_entities = cluster.key_entities | key_entities
            cluster.last_update_at = max(cluster.last_update_at, features.published_at)
            assignment[article["article_id"]] = result.event_id

    return assignment, reviewed


def _as_datetime(value: str) -> Any:
    from datetime import UTC, datetime

    if not value:
        return datetime(2026, 1, 1, tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime(2026, 1, 1, tzinfo=UTC)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


# ------------------------------------------------------------- metrikler
@dataclass(frozen=True)
class ClusteringMetrics:
    articles: int
    gold_events: int
    predicted_clusters: int
    precision: float
    recall: float
    f1: float
    false_merge_rate: float
    impure_clusters: list[int]
    reviewed_articles: int = 0
    auto_precision: float = 0.0
    auto_pairs: int = 0


def clustering_metrics(
    articles: list[dict[str, Any]],
    assignment: dict[str, int],
    reviewed: set[str] | None = None,
) -> ClusteringMetrics:
    gold = {a["article_id"]: a["event_id"] for a in articles}
    ids = [a["article_id"] for a in articles if a["article_id"] in assignment]

    tp = fp = fn = 0
    for left, right in combinations(ids, 2):
        same_gold = gold[left] == gold[right]
        same_pred = assignment[left] == assignment[right]
        if same_pred and same_gold:
            tp += 1
        elif same_pred and not same_gold:
            fp += 1
        elif not same_pred and same_gold:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    # False merge: birden çok GERÇEK olayı karıştıran küme oranı.
    # Çift bazlı precision'dan ayrı raporlanır çünkü G2'nin pazarlıksız
    # koşulu küme seviyesindedir: bir kullanıcı yanlış birleştirilmiş TEK
    # bir olay sayfasında yanlış kanıtla karşılaşır.
    members: dict[int, set[str]] = defaultdict(set)
    for article_id in ids:
        members[assignment[article_id]].add(gold[article_id])
    impure = sorted(cid for cid, golds in members.items() if len(golds) > 1)
    false_merge = len(impure) / len(members) if members else 0.0

    # Otomatik (sorulmadan verilen) kararların precision'ı: denetime
    # düşen makaleleri içeren çiftler dışlanır. G2'nin asıl ölçtüğü budur —
    # denetim kuyruğuna düşen bir atama sistemin iddiası değil, sorusudur.
    reviewed = reviewed or set()
    auto_tp = auto_fp = 0
    for left, right in combinations(ids, 2):
        if left in reviewed or right in reviewed:
            continue
        if assignment[left] != assignment[right]:
            continue
        if gold[left] == gold[right]:
            auto_tp += 1
        else:
            auto_fp += 1
    auto_pairs = auto_tp + auto_fp
    auto_precision = auto_tp / auto_pairs if auto_pairs else 1.0

    return ClusteringMetrics(
        reviewed_articles=len(reviewed & set(ids)),
        auto_precision=auto_precision,
        auto_pairs=auto_pairs,
        articles=len(ids),
        gold_events=len(set(gold.values())),
        predicted_clusters=len(members),
        precision=precision,
        recall=recall,
        f1=f1,
        false_merge_rate=false_merge,
        impure_clusters=impure,
    )


@dataclass(frozen=True)
class ClaimMetrics:
    claims: int
    status_accuracy: float
    rule_accuracy: float
    numeric_accuracy: float
    status_distribution: dict[str, int]
    mismatches: list[dict[str, Any]]


def claim_metrics(claims: list[dict[str, Any]]) -> ClaimMetrics:
    """Kural motorunu elle verilmiş beklenen duruma karşı ölçer.

    Golden Set'te her iddia için `evidence` listesi bulunur; kural motoru
    aynı girdiyle koşturulur ve çıktısı `expected_status` ile karşılaştırılır.
    """
    from politikdesk.evidence.independence import EvidenceArticle
    from politikdesk.evidence.rules import Claim, Evidence

    status_hits = rule_hits = numeric_total = numeric_hits = 0
    distribution: Counter[str] = Counter()
    mismatches: list[dict[str, Any]] = []

    for row in claims:
        evidence = [
            Evidence(
                article=EvidenceArticle(
                    article_id=i,
                    source_slug=e["source_slug"],
                    tier=e["tier"],
                    kind=e.get("kind", "media"),
                    independence_group=e.get("independence_group"),
                    text=e.get("text", ""),
                ),
                stance=e["stance"],
            )
            for i, e in enumerate(row.get("evidence", []))
        ]
        claim = Claim(
            claim_id=0,
            claim_text=row["claim_text"],
            claim_type=row["claim_type"],
            normalized_value=row.get("normalized_value"),
            value_verified_against_source=row.get("value_verified_against_source", False),
        )
        result = compute_status(claim, evidence, partial_elements=row.get("partial", False))
        distribution[result.status] += 1

        if result.status == row["expected_status"]:
            status_hits += 1
        else:
            mismatches.append(
                {
                    "claim_id": row.get("claim_id"),
                    "expected": row["expected_status"],
                    "got": result.status,
                    "rule": result.rule,
                }
            )
        if row.get("expected_rule") and result.rule == row["expected_rule"]:
            rule_hits += 1

        if row["claim_type"] == "number":
            numeric_total += 1
            if row.get("normalized_value") == row.get(
                "gold_normalized_value", row.get("normalized_value")
            ):
                numeric_hits += 1

    n = len(claims) or 1
    ruled = sum(1 for r in claims if r.get("expected_rule")) or 1
    return ClaimMetrics(
        claims=len(claims),
        status_accuracy=status_hits / n,
        rule_accuracy=rule_hits / ruled,
        numeric_accuracy=numeric_hits / numeric_total if numeric_total else 1.0,
        status_distribution=dict(distribution),
        mismatches=mismatches[:20],
    )


# ------------------------------------------------------------------ rapor
G2_TARGETS = {
    "precision": 0.90,
    "recall": 0.80,
    "false_merge_rate": 0.05,
    "status_accuracy": 0.95,
    "numeric_accuracy": 0.95,
}


def render_report(
    clustering: ClusteringMetrics | None,
    claims: ClaimMetrics | None,
    thresholds: Thresholds,
) -> str:
    lines = ["# Eval Raporu (F2-16)", ""]
    lines.append(
        f"Eşikler: T_HIGH={thresholds.t_high} · T_LOW={thresholds.t_low} · "
        f"zaman penceresi={thresholds.time_window_hours}sa · "
        f"jaccard≥{thresholds.jaccard_min}"
    )
    lines.append("")

    if clustering is None:
        lines += ["## Kümeleme", "", "⏳ `eval/golden_set_v1.jsonl` yok — ölçüm yapılamadı.", ""]
    else:
        ok = lambda v, t, lower=True: "✅" if (v >= t if lower else v <= t) else "❌"  # noqa: E731
        lines += [
            "## Kümeleme",
            "",
            f"{clustering.articles} makale · {clustering.gold_events} gerçek olay · "
            f"{clustering.predicted_clusters} üretilen küme",
            "",
            "| Metrik | Değer | G2 hedefi | Durum |",
            "|---|---|---|---|",
            f"| Pairwise precision | {clustering.precision:.3f} | ≥ 0,90 | "
            f"{ok(clustering.precision, G2_TARGETS['precision'])} |",
            f"| Pairwise recall | {clustering.recall:.3f} | ≥ 0,80 | "
            f"{ok(clustering.recall, G2_TARGETS['recall'])} |",
            f"| F1 | {clustering.f1:.3f} | — | — |",
            f"| **Otomatik precision** | {clustering.auto_precision:.3f} | ≥ 0,90 | "
            f"{ok(clustering.auto_precision, G2_TARGETS['precision'])} |",
            f"| **False merge (küme)** | {clustering.false_merge_rate:.3f} | ≤ 0,05 | "
            f"{ok(clustering.false_merge_rate, G2_TARGETS['false_merge_rate'], lower=False)} |",
            "",
        ]
        lines.append(
            f"Denetime düşen makale: {clustering.reviewed_articles}/"
            f"{clustering.articles} · otomatik birleştirilen çift: "
            f"{clustering.auto_pairs}"
        )
        lines.append("")
        if clustering.impure_clusters:
            lines.append(f"Karışık kümeler: {clustering.impure_clusters}")
            lines.append("")

    if claims is None:
        lines += [
            "## İddia ve kanıt",
            "",
            "⏳ `eval/golden_claims_v1.jsonl` yok — ölçüm yapılamadı.",
            "",
        ]
    else:
        ok = lambda v, t: "✅" if v >= t else "❌"  # noqa: E731
        lines += [
            "## İddia ve kanıt",
            "",
            f"{claims.claims} iddia",
            "",
            "| Metrik | Değer | G2 hedefi | Durum |",
            "|---|---|---|---|",
            f"| `evidence_status` doğruluğu | {claims.status_accuracy:.3f} | ≥ 0,95 | "
            f"{ok(claims.status_accuracy, G2_TARGETS['status_accuracy'])} |",
            f"| Kural eşleşmesi | {claims.rule_accuracy:.3f} | — | — |",
            f"| Sayısal normalizasyon | {claims.numeric_accuracy:.3f} | ≥ 0,95 | "
            f"{ok(claims.numeric_accuracy, G2_TARGETS['numeric_accuracy'])} |",
            "",
            "### `evidence_status` dağılımı (B-37 / İtiraz-2)",
            "",
        ]
        total = sum(claims.status_distribution.values()) or 1
        for status in (
            "strongly_corroborated",
            "partially_corroborated",
            "single_source",
            "contradicted",
            "unverified",
        ):
            n = claims.status_distribution.get(status, 0)
            lines.append(f"- `{status}`: {n} (%{100 * n / total:.1f})")
        green = claims.status_distribution.get("strongly_corroborated", 0) / total
        lines.append("")
        if green < 0.10:
            lines.append(
                "> ⚠️ 🟢 oranı %10'un altında. İtiraz-2: bu bir kalite kapısı "
                "sorunu DEĞİL, bir **kaynak portföyü** sorunudur ve 9. kaynak "
                "kararının (Spec §9.2) girdisidir."
            )
        lines.append("")
        if claims.mismatches:
            lines += [
                "### Uyuşmayanlar",
                "",
                "| iddia | beklenen | çıkan | kural |",
                "|---|---|---|---|",
            ]
            lines += [
                f"| {m['claim_id']} | {m['expected']} | {m['got']} | {m['rule']} |"
                for m in claims.mismatches
            ]
            lines.append("")

    return "\n".join(lines)


# -------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    from politikdesk.config import load_env_file

    load_env_file()
    parser = argparse.ArgumentParser(description="PolitikDesk eval kosucusu (F2-16)")
    parser.add_argument("--articles", type=Path, default=GOLDEN_ARTICLES)
    parser.add_argument("--claims", type=Path, default=GOLDEN_CLAIMS)
    parser.add_argument("--t-high", type=float, default=None)
    parser.add_argument("--t-low", type=float, default=None)
    parser.add_argument(
        "--review-as",
        choices=["merge", "split"],
        default="merge",
        help="Denetim kuyrugundaki atamalar nasil sayilsin",
    )
    parser.add_argument(
        "--sweep", action="store_true", help="Esik taramasi (F2-14): T_HIGH icin egri cikarir"
    )
    parser.add_argument("--out", type=Path, help="Rapor markdown ciktisi")
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    from politikdesk.config import get_settings

    settings = get_settings()
    thresholds = Thresholds(
        t_high=args.t_high if args.t_high is not None else settings.cluster_t_high,
        t_low=args.t_low if args.t_low is not None else settings.cluster_t_low,
    )

    articles = load_jsonl(args.articles)
    claims = load_jsonl(args.claims)

    if not articles and not claims:
        print(
            "Golden Set bulunamadi.\n"
            f"  makale seti : {args.articles}\n"
            f"  iddia seti  : {args.claims}\n\n"
            "Etiketleme kilavuzu: eval/README.md\n"
            "F2-16 kosucusu hazir; olcum VERI bekliyor.",
            file=sys.stderr,
        )
        return 1

    clustering_result = None
    if articles:
        from politikdesk.nlp.embedder import build_backend

        embedder = build_backend()
        if not getattr(embedder, "is_production_ready", False):
            print(
                "UYARI: uretim disi embedder kullaniliyor (hashing). Kumeleme "
                "olcumleri D16 modeliyle tekrarlanmalidir.",
                file=sys.stderr,
            )
        if args.sweep:
            return _sweep(articles, embedder, thresholds)
        assignment, reviewed = replay_clustering(
            articles, embedder, thresholds, review_as=args.review_as
        )
        clustering_result = clustering_metrics(articles, assignment, reviewed)

    claim_result = claim_metrics(claims) if claims else None
    report = render_report(clustering_result, claim_result, thresholds)

    if args.out:
        args.out.write_text(report + "\n", encoding="utf-8")
        print(f"Rapor yazildi: {args.out}")
    print(report)
    return 0


def _sweep(articles: list[dict[str, Any]], embedder: Any, base: Thresholds) -> int:
    """F2-14: T_HIGH taraması — precision/recall eğrisi."""
    print(
        "| T_HIGH | T_LOW | precision | oto. precision | recall | F1 | "
        "false merge | denetime düşen |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for t_high in [round(0.70 + 0.02 * i, 2) for i in range(15)]:
        t_low = round(min(base.t_low, t_high - 0.02), 2)
        thresholds = Thresholds(t_high=t_high, t_low=t_low)
        assignment, reviewed = replay_clustering(articles, embedder, thresholds)
        metrics = clustering_metrics(articles, assignment, reviewed)
        print(
            f"| {t_high:.2f} | {t_low:.2f} | {metrics.precision:.3f} | "
            f"{metrics.auto_precision:.3f} | {metrics.recall:.3f} | "
            f"{metrics.f1:.3f} | {metrics.false_merge_rate:.3f} | "
            f"{metrics.reviewed_articles}/{metrics.articles} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
