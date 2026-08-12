"""ToS koruması (F1-06).

DoD: `tos_status='forbidden'` kaynak eklendiğinde toplama denemesi
exception fırlatıyor.

Spec §12.4 / §15 madde 12: yasaklı kaynaktan ingestion **kod seviyesinde**
engellidir. Bu, bir yapılandırma tercihi değil ürün sözleşmesidir — bu
yüzden kontrol boru hattının en başında ve atlanamaz konumdadır.
"""

from __future__ import annotations

from dataclasses import dataclass

from politikdesk.observability import get_logger

log = get_logger(__name__)

# Toplama yapılabilecek durumlar. Liste genişletilirse gerekçesi yazılmalı.
_ALLOWED_STATUSES = frozenset({"allowed", "restricted"})

# `restricted`: yalnızca meta veri + link saklanır, alıntı üretilmez
# (Spec §9.3 öncelik sırası madde 3'ün daraltılmış hali).
RESTRICTED = "restricted"


class ForbiddenSourceError(RuntimeError):
    """Yasaklı bir kaynaktan toplama denendi."""

    def __init__(self, slug: str, status: str) -> None:
        self.slug = slug
        self.status = status
        super().__init__(
            f"'{slug}' kaynağından toplama yapılamaz (tos_status={status!r}). "
            "Spec §12.4 / §15 madde 12: yasaklı kaynaktan ingestion "
            "kod seviyesinde engellidir."
        )


class UnreviewedSourceError(RuntimeError):
    """ToS incelemesi yapılmamış bir kaynaktan toplama denendi."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        super().__init__(
            f"'{slug}' kaynağının ToS incelemesi yapılmamış "
            "(tos_status='pending_review'). Kapı G0 #3 sağlanmadan bu "
            "kaynaktan toplama yapılamaz."
        )


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    store_excerpt: bool
    """`restricted` kaynaklarda alıntı saklanmaz — yalnızca meta veri + link."""


def check(slug: str, tos_status: str, *, is_active: bool = True) -> GuardDecision:
    """Bir kaynaktan toplama yapılabilir mi?

    Yasaklıysa veya incelenmemişse **istisna fırlatır** — sessizce
    atlamaz. Sessiz atlama, yasağın fark edilmeden aşılmasına yol açar.
    """
    if tos_status == "forbidden":
        raise ForbiddenSourceError(slug, tos_status)
    if tos_status == "pending_review":
        raise UnreviewedSourceError(slug)
    if tos_status not in _ALLOWED_STATUSES:
        raise ForbiddenSourceError(slug, tos_status)

    if not is_active:
        log.info("source_inactive_skipped", source=slug)
        return GuardDecision(allowed=False, store_excerpt=False)

    return GuardDecision(allowed=True, store_excerpt=tos_status != RESTRICTED)
