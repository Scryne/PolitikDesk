"""PolitikDesk Dikey Tanımı ve Temel Sınıfları (B-91 · Spec v3.4 §5).

Her dikey (macro_economy, legislation, politics vb.) kendi konu sözlüğünü,
non-event filtrelerini, varsayılan Election Mode ayarını ve kaynak tavanını
tanımlar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VerticalSpec:
    """Bir analitik ve editoryal dikeyin yapılandırma sözleşmesi."""

    slug: str
    name: str
    description: str
    topic_keywords: dict[str, tuple[str, ...]]
    non_event_patterns: tuple[str, ...] = ()
    required_context_keywords: tuple[str, ...] = ()
    default_election_mode: bool = False
    max_sources: int = 12
    key_entities: tuple[str, ...] = ()
    extra_config: dict[str, Any] = field(default_factory=dict)
