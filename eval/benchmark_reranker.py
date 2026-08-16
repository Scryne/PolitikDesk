"""TurkishPoliticalReranker Gecikme ve Ölçeklenebilirlik Ölçüm Betiği."""

from __future__ import annotations

import time

from politikdesk.clustering.reranker import TurkishPoliticalReranker


def run_reranker_benchmark(iterations: int = 1000, candidate_count: int = 50) -> float:
    reranker = TurkishPoliticalReranker()

    article_text = "TBMM Adalet Komisyonunda 9. Yargı Paketi ve Anayasa Mahkemesi kararları ele alındı."
    article_entities = frozenset(["TBMM Adalet Komisyonu", "9. Yargı Paketi", "Yılmaz Tunç", "AYM"])
    article_topics = ("kanun_teklifleri", "yargi")

    candidates = [
        {
            "event_id": i,
            "similarity": 0.70 + (i % 25) * 0.01,
            "entities": [f"Kurum_{i}", "Yılmaz Tunç"] if i % 2 == 0 else [f"Kurum_{i}"],
            "topics": ["kanun_teklifleri"] if i % 3 == 0 else ["ekonomi"],
        }
        for i in range(candidate_count)
    ]

    started = time.perf_counter()
    for _ in range(iterations):
        reranker.rerank(article_text, article_entities, article_topics, candidates)
    elapsed = time.perf_counter() - started

    avg_ms = (elapsed / iterations) * 1000
    print(f"Reranker Benchmark: {iterations} döngü, {candidate_count} aday olay.")
    print(f"Toplam Süre: {elapsed:.4f} sn | Makale Başına Ortalama Gecikme: {avg_ms:.4f} ms")
    return avg_ms


if __name__ == "__main__":
    run_reranker_benchmark()
