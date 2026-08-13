"""Election Mode — feature flag ve konfigürasyon şeması (F4-15, Spec §12.6).

**Bu mod UYGULANMAZ, HAZIRLANIR.** Spec §12.6'nın sözü şudur:

    "Bu mod Faz 1'de bir feature flag + konfigürasyon şeması olarak
    hazırlanır (uygulanmaz), böylece ihtiyaç anında haftalar değil
    saatler içinde açılabilir."

Buradaki "hazırlanır" ciddi bir taahhüt: eşiklerin *nereden okunduğu*
bugün doğru olmalı ki, flag açıldığında tek bir yerin değişmesi yetsin.
Bu yüzden mod bir `if` yığını değil, **eşik sağlayıcısı**dır — kanıt
motoru ve üretim kapısı eşiği zaten buradan sorar, sadece bugün gevşek
değerler dönüyor.

Spec §12.6'nın beş maddesi ve karşılıkları:

    1. `single_source`/`unverified` iddiada üretim devre dışı
       -> BLOCKED_STATUSES  (kapalıyken yalnızca `unverified`)
    2. 🟢 için independent_count >= 4 VE Tier 1 zorunlu
       -> strongly_corroborated_min_sources / requires_tier1
    3. Her taslakta zorunlu kaynak linki
       -> requires_source_link
    4. Yarı-otomasyonun tamamı kapalı
       -> semi_automation_allowed  (MVP'de zaten yok; flag onu da kilitler)
    5. Kullanıcıya görünür mod göstergesi
       -> banner()

⚠️ **Varsayılan KAPALI.** Açmak bilinçli bir karardır ve bir seçim
dönemi dışında açılması ürünü gereksiz yere kısıtlar.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Final

# Spec §8.3 R6: `strongly_corroborated` için normal eşik. Election Mode
# bunu 4'e çıkarır ve ayrıca Tier 1 kaynak şartı koyar.
NORMAL_STRONG_MIN_SOURCES: Final[int] = 3
ELECTION_STRONG_MIN_SOURCES: Final[int] = 4

ENV_VAR: Final[str] = "PD_ELECTION_MODE"


@dataclass(frozen=True)
class ElectionModeConfig:
    """Sıkı modun tüm ayarları tek yerde.

    `frozen`: mod ayarları çalışma zamanında değişmemeli. Bir isteğin
    ortasında eşiğin kayması, aynı olayın iki iddiasının farklı kurala
    göre puanlanması demektir.
    """

    enabled: bool = False

    # --- Spec §12.6 madde 2: kanıt eşiği yükselir ---
    strongly_corroborated_min_sources: int = NORMAL_STRONG_MIN_SOURCES
    requires_tier1_for_strong: bool = False

    # --- madde 1: üretim engeli genişler ---
    # Kapalıyken yalnızca `unverified` engeller (guards.UNVERIFIED_STATUSES).
    # Açıkken `single_source` da engeller: seçim döneminde tek kaynağa
    # dayanan bir iddiadan içerik üretmek, hatanın maliyetinin en yüksek
    # olduğu anda en zayıf dayanağı kullanmaktır.
    blocked_statuses: frozenset[str] = field(
        default_factory=lambda: frozenset({"unverified"})
    )

    # --- madde 3 ve 4 ---
    requires_source_link: bool = False
    semi_automation_allowed: bool = False  # MVP'de zaten yok; mod kilitler

    @property
    def label(self) -> str:
        return "Election Mode AÇIK" if self.enabled else "normal mod"


# Kapalı (varsayılan) ve açık yapılandırmalar. İkisi de sabit: modun
# "ne yapacağı" kodun okunmasıyla görülebilmeli.
NORMAL = ElectionModeConfig()

ELECTION = ElectionModeConfig(
    enabled=True,
    strongly_corroborated_min_sources=ELECTION_STRONG_MIN_SOURCES,
    requires_tier1_for_strong=True,
    blocked_statuses=frozenset({"unverified", "single_source"}),
    requires_source_link=True,
    semi_automation_allowed=False,
)


def is_enabled() -> bool:
    """`PD_ELECTION_MODE` ortam değişkenine bakar.

    Ayar bilerek `Settings`'te DEĞİL: Election Mode bir uygulama ayarı
    değil, bir **operasyon kararıdır**. `.env`'e yazılıp unutulmaması,
    açıkça verilmesi gerekir. Ayrıca `Settings` `lru_cache`'lidir;
    modu açmak için uygulamayı yeniden başlatmak gerekirdi.
    """
    return os.environ.get(ENV_VAR, "").strip().lower() in {"1", "true", "yes", "on"}


def current() -> ElectionModeConfig:
    """Yürürlükteki yapılandırma."""
    return ELECTION if is_enabled() else NORMAL


def banner() -> str:
    """Spec §12.6 madde 5: kullanıcıya görünür mod göstergesi.

    Kapalıyken boş string döner — normal modda banner göstermek,
    göstergeyi gürültüye çevirir ve açıldığında fark edilmez.
    """
    if not is_enabled():
        return ""
    return (
        '<div style="background:#8250df;color:#fff;padding:.5rem .9rem;'
        'border-radius:6px;margin-bottom:1rem;font-weight:600">'
        "⚠ ELECTION MODE — sıkı kanıt eşiği yürürlükte. "
        "Tek kaynaklı ve doğrulanmamış iddialardan taslak üretilmez; "
        "🟢 için 4 bağımsız kaynak ve en az bir Tier 1 gerekir "
        "(Spec §12.6)."
        "</div>"
    )


__all__ = [
    "ELECTION",
    "ELECTION_STRONG_MIN_SOURCES",
    "ENV_VAR",
    "NORMAL",
    "NORMAL_STRONG_MIN_SOURCES",
    "ElectionModeConfig",
    "banner",
    "current",
    "is_enabled",
]
