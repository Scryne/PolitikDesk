"""Ingestion boru hattı — FETCH → NORMALIZE → DEDUP → STORE.

Spec §11.3 adım 1–3. Adım 4 (EMBED) ve sonrası ayrı görevlerdir.

Boru hattının sözleşmesi:
  * Bir kaynağın hatası diğerlerini düşürmez (F1-02 DoD)
  * Yasaklı/incelenmemiş kaynaktan toplama yapılmaz (F1-06)
  * Kapsam dışı içerik saklanmaz (maliyet + kalite)
  * Tam tekrar saklanmaz; yakın tekrar saklanır ama işaretlenir
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from politikdesk.ingestion import guard, repository, topics
from politikdesk.ingestion.adapters import base as adapter_base
from politikdesk.ingestion.adapters.base import SourceAdapter
from politikdesk.ingestion.adapters.official import (
    GenericHtmlAdapter,
    TuikAdapter,
    WordPressRestAdapter,
)
from politikdesk.ingestion.adapters.rss import RssAdapter
from politikdesk.ingestion.adapters.tuik_sdmx import TuikSdmxAdapter
from politikdesk.ingestion.dedup import classify as classify_duplicate
from politikdesk.ingestion.http import HttpClient
from politikdesk.ingestion.models import IngestionStats, RawItem
from politikdesk.ingestion.normalizer import normalize
from politikdesk.ingestion.repository import SourceRow
from politikdesk.observability import get_logger

log = get_logger(__name__)


def build_adapter(source: SourceRow, http: HttpClient | None = None) -> SourceAdapter:
    """Kaynak satırından uygun adaptörü kurar."""
    http = http or HttpClient()
    adapter_key = source.adapter or ("rss" if source.access_method == "rss" else "generic_html")

    if adapter_key == "rss":
        if not source.feed_url:
            raise ValueError(f"{source.slug}: rss adaptörü için feed_url gerekli")
        return RssAdapter(
            source.slug,
            source.feed_url,
            base_url=source.base_url or "",
            extra_feeds=list(source.extra_feeds or []),
            http=http,
            keyword_filter=list(source.keyword_filter or []),
        )

    if adapter_key == "tuik":
        return TuikAdapter(source.slug, http=http)

    if adapter_key == "tuik_sdmx":
        # Kendi HTTP istemcisini kurar: SDMX ve kimlik konakları el sıkışma
        # ORTASINDA düşebiliyor ve varsayılandan daha çok yeniden deneme
        # ister (F5-02). Ayrıca robots denetimi kapalıdır — kimliğimizle
        # çağırdığımız bir API ucu tarama sözleşmesinin konusu değildir.
        return TuikSdmxAdapter(slug=source.slug)

    if adapter_key == "wp_rest":
        if not source.feed_url:
            raise ValueError(f"{source.slug}: wp_rest adaptörü için feed_url gerekli")
        return WordPressRestAdapter(
            source.slug,
            api_url=source.feed_url,
            base_url=source.base_url or "",
            http=http,
        )

    if adapter_key == "generic_html":
        candidates = [source.feed_url] if source.feed_url else []
        if not candidates and source.base_url:
            candidates = [
                f"{source.base_url}/duyurular",
                f"{source.base_url}/haberler",
            ]
        return GenericHtmlAdapter(
            source.slug,
            index_urls=candidates,
            base_url=source.base_url or "",
            http=http,
        )

    raise ValueError(f"{source.slug}: bilinmeyen adaptör {adapter_key!r}")


@dataclass
class Pipeline:
    """Tek bir kaynağı veya tüm kaynakları işler."""

    http: HttpClient | None = None
    enforce_topic_scope: bool = True

    def run_all(self) -> IngestionStats:
        total = IngestionStats()
        for source in repository.list_sources(only_active=True):
            total.merge(self.run_source(source))
        log.info(
            "ingestion_cycle_complete",
            fetched=total.fetched, stored=total.stored,
            exact_dupes=total.exact_duplicates, near_dupes=total.near_duplicates,
            filtered=total.filtered_out, errors=total.errors,
        )
        return total

    def run_source(self, source: SourceRow) -> IngestionStats:
        stats = IngestionStats()
        started = time.perf_counter()
        error: str | None = None
        items: list[RawItem] = []
        # Adaptörün içeride yuttuğu hatalar (B-80). İstisna boru hattına
        # ulaşmadığı için tur "başarılı" görünürdü; artık ayrıca taşınıyor.
        failures: list[str] = []

        try:
            decision = guard.check(source.slug, source.tos_status,
                                   is_active=source.is_active)
            if not decision.allowed:
                return stats

            adapter = build_adapter(source, self.http)
            try:
                items = adapter.fetch()
            finally:
                # `finally`: fetch yarıda patlasa bile o ana kadar yutulmuş
                # hatalar kaydedilsin, adaptörün defteri boşalsın.
                failures = adapter_base.drain_failures(adapter)
            stats.fetched = len(items)
            stats = self._store_items(items, source, decision, stats)

        except guard.ForbiddenSourceError:
            # Yasaklı kaynak bir yapılandırma hatasıdır; yutulmaz.
            raise
        except guard.UnreviewedSourceError as exc:
            error = str(exc)
            stats.errors = 1
            log.warning("source_unreviewed", source=source.slug)
        except Exception as exc:  # noqa: BLE001 — bir kaynak diğerlerini düşürmez
            error = f"{type(exc).__name__}: {exc}"
            stats.errors = 1
            log.warning("source_fetch_failed", source=source.slug,
                        error=type(exc).__name__, detail=str(exc)[:300])

        # Hiç öğe gelmediyse ve adaptör içeride bir şey yuttuysa, bu tur
        # başarısızdır — `succeeded=true, 0 öğe` yazmak ham kaydı yalanlar.
        if error is None and stats.fetched == 0 and failures:
            error = "; ".join(failures)[:1000]
            stats.errors = 1
            log.warning("source_fetch_silent_failure", source=source.slug,
                        failures=len(failures), detail=error[:300])
        elif failures:
            # Kısmi başarısızlık: bazı akışlar düştü ama öğe geldi. Tur
            # başarılıdır; kaynağı kırmızıya çekmek yanlış alarm olurdu.
            log.info("source_fetch_partial_failure", source=source.slug,
                     failures=len(failures), fetched=stats.fetched)

        duration_ms = int((time.perf_counter() - started) * 1000)
        repository.record_fetch(
            source.id,
            duration_ms=duration_ms,
            items_fetched=stats.fetched,
            items_stored=stats.stored,
            exact_dupes=stats.exact_duplicates,
            near_dupes=stats.near_duplicates,
            filtered_out=stats.filtered_out,
            error=error,
            partial_failures=failures if error is None else [],
        )
        return stats

    # ------------------------------------------------------------------
    def _store_items(
        self,
        items: list[RawItem],
        source: SourceRow,
        decision: guard.GuardDecision,
        stats: IngestionStats,
    ) -> IngestionStats:
        if not items:
            return stats

        window = repository.load_dedup_window()

        for item in items:
            matched_topics = topics.classify(item.title, item.summary)
            if self.enforce_topic_scope and not matched_topics:
                stats.filtered_out += 1
                continue

            article = normalize(
                item,
                store_excerpt=decision.store_excerpt,
                topics=matched_topics,
            )
            article_text = f"{article.title} {article.excerpt or ''}"

            verdict = classify_duplicate(
                article.content_hash,
                article.simhash,
                existing_hashes=window.hashes,
                existing_simhashes=window.simhashes,
                text=article_text,
                existing_texts=window.texts,
            )

            if verdict.kind == "exact":
                stats.exact_duplicates += 1
                continue

            independence_key = (
                f"grp:{source.independence_group}"
                if source.independence_group
                else f"src:{source.slug}"
            )

            article_id = repository.insert_article(
                article,
                source_id=source.id,
                independence_key=independence_key,
                near_duplicate_of_id=verdict.matched_article_id
                if verdict.kind == "near" else None,
                simhash_distance=verdict.distance if verdict.kind == "near" else None,
            )

            if article_id is None:
                # canonical_url çakışması — başka bir turda eklenmiş
                stats.exact_duplicates += 1
                continue

            stats.stored += 1
            if verdict.kind == "near":
                stats.near_duplicates += 1

            # Aynı tur içindeki tekrarları da yakala
            window.remember(article_id, article.content_hash, article.simhash,
                            article_text)

        log.info(
            "source_ingested",
            source=source.slug, fetched=stats.fetched, stored=stats.stored,
            exact_dupes=stats.exact_duplicates, near_dupes=stats.near_duplicates,
            filtered=stats.filtered_out,
        )
        return stats
