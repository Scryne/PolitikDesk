"""Kaynak yapılandırmasını yükler ve veritabanıyla senkronize eder.

`config/sources.yml` tek gerçek kaynaktır (single source of truth).
Veritabanındaki `sources` tablosu bu dosyadan doldurulur; admin
ekranından yapılan `tos_status` değişiklikleri korunur (F1-17).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from politikdesk.observability import get_logger

log = get_logger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "sources.yml"


@dataclass(frozen=True)
class SourceConfig:
    slug: str
    name: str
    tier: int
    kind: str
    access_method: str
    tos_status: str
    adapter: str
    independence_group: str | None = None
    base_url: str | None = None
    feed_url: str | None = None
    extra_feeds: list[str] = field(default_factory=list)
    keyword_filter: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    produces_scheduled_events: bool = False
    is_wire_reference: bool = False
    verified: bool = False
    probe: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    @property
    def is_ingestable(self) -> bool:
        """Bu kaynaktan şu an veri çekilebilir mi?"""
        return self.tos_status in {"allowed", "restricted"} and bool(
            self.feed_url or self.probe or self.adapter in {"tuik", "generic_html"}
        )


def load_config(path: Path = CONFIG_PATH) -> tuple[list[SourceConfig], dict[str, Any]]:
    """`config/sources.yml`'yi okur ve doğrular."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    max_sources = int(data.get("max_sources", 8))
    raw_sources = data.get("sources", [])

    if len(raw_sources) > max_sources:
        raise ValueError(
            f"{len(raw_sources)} kaynak tanımlı ama sert sınır {max_sources} "
            "(Spec §9.2 / D6). Kaynak eklemek Faz 4 kalite hedeflerine bağlıdır."
        )

    configs = [
        SourceConfig(
            slug=s["slug"],
            name=s["name"],
            tier=int(s["tier"]),
            kind=s["kind"],
            access_method=s["access_method"],
            tos_status=s["tos_status"],
            adapter=s.get("adapter") or _infer_adapter(s),
            independence_group=s.get("independence_group"),
            base_url=s.get("base_url"),
            feed_url=s.get("feed_url"),
            extra_feeds=list(s.get("extra_feeds") or []),
            keyword_filter=list(s.get("keyword_filter") or []),
            topics=list(s.get("topics") or []),
            produces_scheduled_events=bool(s.get("produces_scheduled_events")),
            is_wire_reference=bool(s.get("is_wire_reference")),
            verified=bool(s.get("verified")),
            probe=dict(s.get("probe") or {}),
            notes=s.get("notes", "") or "",
        )
        for s in raw_sources
    ]
    return configs, data


def _infer_adapter(raw: dict[str, Any]) -> str:
    if raw.get("access_method") == "rss":
        return "rss"
    if raw.get("slug") == "tuik":
        return "tuik"
    return "generic_html"


def sync_to_database(configs: list[SourceConfig] | None = None) -> dict[str, int]:
    """Yapılandırmayı `sources` tablosuna yazar.

    `tos_status` ve `is_active` **veritabanında değiştirilmişse korunur** —
    admin ekranındaki (F1-17) kararlar bir dosya senkronizasyonuyla
    geri alınmamalıdır.
    """
    from politikdesk.db import connection

    configs = configs if configs is not None else load_config()[0]
    inserted = updated = 0

    with connection() as conn, conn.cursor() as cur:
        for cfg in configs:
            cur.execute("SELECT id FROM sources WHERE slug = %s", (cfg.slug,))
            existing = cur.fetchone()

            if existing is None:
                cur.execute(
                    """
                    INSERT INTO sources (
                        name, slug, tier, kind, independence_group, access_method,
                        tos_status, base_url, feed_url, adapter, extra_feeds,
                        keyword_filter, topics, is_wire_reference
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        cfg.name, cfg.slug, cfg.tier, cfg.kind, cfg.independence_group,
                        cfg.access_method, cfg.tos_status, cfg.base_url, cfg.feed_url,
                        cfg.adapter, cfg.extra_feeds, cfg.keyword_filter, cfg.topics,
                        cfg.is_wire_reference,
                    ),
                )
                inserted += 1
            else:
                # tos_status ve is_active bilinçli olarak GÜNCELLENMEZ.
                cur.execute(
                    """
                    UPDATE sources SET
                        name = %s, tier = %s, kind = %s, independence_group = %s,
                        access_method = %s, base_url = %s, feed_url = %s,
                        adapter = %s, extra_feeds = %s, keyword_filter = %s,
                        topics = %s, is_wire_reference = %s
                    WHERE slug = %s
                    """,
                    (
                        cfg.name, cfg.tier, cfg.kind, cfg.independence_group,
                        cfg.access_method, cfg.base_url, cfg.feed_url, cfg.adapter,
                        cfg.extra_feeds, cfg.keyword_filter, cfg.topics,
                        cfg.is_wire_reference, cfg.slug,
                    ),
                )
                updated += 1
        conn.commit()

    log.info("sources_synced", inserted=inserted, updated=updated)
    return {"inserted": inserted, "updated": updated}
