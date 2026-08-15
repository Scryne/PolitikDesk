"""Kümeleme turu (F2-01 orkestrasyonu).

Spec §11.3'ün 5. adımı: embedding ve varlık çıkarımı tamamlanan makaleler
olaylara atanır.
"""

from __future__ import annotations

from dataclasses import dataclass

from politikdesk.clustering import repository as repo
from politikdesk.clustering.assigner import Thresholds, decide
from politikdesk.config import get_settings
from politikdesk.observability import get_logger

log = get_logger(__name__)


@dataclass
class ClusterStats:
    processed: int = 0
    assigned: int = 0
    created: int = 0
    needs_review: int = 0
    numeric_conflicts: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "processed": self.processed,
            "assigned": self.assigned,
            "created": self.created,
            "needs_review": self.needs_review,
            "numeric_conflicts": self.numeric_conflicts,
            "errors": self.errors,
        }


def thresholds_from_settings() -> Thresholds:
    """D20 eşiklerini ayarlardan okur (F2-14 bunları kalibre eder)."""
    settings = get_settings()
    return Thresholds(t_high=settings.cluster_t_high, t_low=settings.cluster_t_low)


def run(limit: int = 50, thresholds: Thresholds | None = None) -> ClusterStats:
    """Bekleyen makaleleri kümeler.

    Makaleler **yayın zamanına göre sırayla** işlenir: kümeleme artımlıdır,
    sıra sonucu etkiler. Rastgele sırayla işlemek, bir olayın ikinci
    makalesini birinciden önce görmek demektir ve tekrar üretilemez sonuç
    doğurur (F2-16 eval koşucusu bunu ölçer).
    """
    th = thresholds or thresholds_from_settings()
    stats = ClusterStats()

    for row in repo.pending_clustering(limit):
        try:
            article = repo.load_features(row)
            if not article.embedding:
                log.warning("clustering_skipped_no_embedding", article_id=row["id"])
                continue

            decision = decide(article, repo.candidate_events(article), th)
            stats.processed += 1

            if decision.creates_event:
                created_id = repo.create_event(article, row)
                if created_id is not None:
                    stats.created += 1
            else:
                assigned = repo.assign_article(article, decision)
                if assigned:
                    stats.assigned += 1

            if decision.needs_review:
                stats.needs_review += 1
            if decision.numeric_conflicts:
                stats.numeric_conflicts += 1

        except Exception as exc:  # noqa: BLE001
            stats.errors += 1
            log.error(
                "clustering_failed",
                article_id=row["id"],
                error=type(exc).__name__,
                detail=str(exc)[:300],
            )

    log.info("clustering_run_complete", **stats.as_dict())
    return stats
