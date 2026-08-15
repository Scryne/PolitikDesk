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


def is_enabled(vertical: str | None = None) -> bool:
    """`PD_ELECTION_MODE` ortam değişkenine veya dikey varsayılanına bakar (B-16).

    Ortam değişkeni açıkça verilmişse her zaman önceliklidir (1=açık, 0=kapalı).
    Verilmemişse dikeyin kendi varsayılanını (macro_economy=kapalı) kullanır (Spec v3.4 §12.6).
    """
    env_val = os.environ.get(ENV_VAR, "").strip().lower()
    if env_val in {"1", "true", "yes", "on"}:
        return True
    if env_val in {"0", "false", "no", "off"}:
        return False

    from politikdesk.verticals import get_vertical

    v_spec = get_vertical(vertical) if vertical else None
    return v_spec.default_election_mode if v_spec else False


def current(vertical: str | None = None) -> ElectionModeConfig:
    """Yürürlükteki yapılandırma."""
    return ELECTION if is_enabled(vertical) else NORMAL


def banner() -> str:
    """Spec §12.6 madde 5: kullanıcıya görünür mod göstergesi.

    Kapalıyken boş string döner — normal modda banner göstermek,
    göstergeyi gürültüye çevirir ve açıldığında fark edilmez.
    """
    if not is_enabled():
        return ""
    # Stil `web/ui/css.py` token'larından gelir; ham hex ve emoji yok
    # (DESIGN.md Bölüm 5.1, 13.4). Bu blok arayüzün en üstünde durur ve
    # kabuğun kendi diliyle konuşmalıdır — ayrı görünen bir uyarı,
    # "sistemin bir parçası değil" gibi okunur ve ciddiye alınmaz.
    return (
        '<div class="notice warn" role="status">'
        '<svg class="ic" width="16" height="16" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true">'
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 '
        '0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>'
        "<div><p><b>ELECTION MODE — sıkı kanıt eşiği yürürlükte.</b></p>"
        "<p>Tek kaynaklı ve doğrulanmamış iddialardan taslak üretilmez; "
        "güçlü teyit için 4 bağımsız kaynak ve en az bir Tier 1 gerekir "
        "(Spec §12.6).</p></div></div>"
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
