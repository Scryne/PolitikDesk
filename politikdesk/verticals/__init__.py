"""PolitikDesk Dikey Kayıt Defteri (B-91 · Spec v3.4 §5)."""

from __future__ import annotations

from typing import Final

from politikdesk.verticals.base import VerticalSpec
from politikdesk.verticals.legislation import LEGISLATION_VERTICAL
from politikdesk.verticals.macro_economy import MACRO_ECONOMY_VERTICAL

_REGISTRY: dict[str, VerticalSpec] = {
    MACRO_ECONOMY_VERTICAL.slug: MACRO_ECONOMY_VERTICAL,
    LEGISLATION_VERTICAL.slug: LEGISLATION_VERTICAL,
}

DEFAULT_VERTICAL: Final[str] = MACRO_ECONOMY_VERTICAL.slug


def register_vertical(spec: VerticalSpec) -> None:
    """Yeni bir dikey kaydeder."""
    _REGISTRY[spec.slug] = spec


def get_vertical(slug: str | None = None) -> VerticalSpec:
    """Slug'a karşılık gelen dikeyi döner. Yoksa varsayılan döner."""
    if not slug:
        return _REGISTRY[DEFAULT_VERTICAL]
    return _REGISTRY.get(slug, _REGISTRY[DEFAULT_VERTICAL])


def list_verticals() -> list[VerticalSpec]:
    """Kayıtlı tüm dikeyleri döner."""
    return list(_REGISTRY.values())


__all__ = [
    "DEFAULT_VERTICAL",
    "LEGISLATION_VERTICAL",
    "MACRO_ECONOMY_VERTICAL",
    "VerticalSpec",
    "get_vertical",
    "list_verticals",
    "register_vertical",
]
