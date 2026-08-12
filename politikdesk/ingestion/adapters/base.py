"""Kaynak adaptör arayüzü (F1-01).

DoD: Arayüz `fetch() -> list[RawItem]`; sahte (fake) adaptörle test geçiyor.

Tasarım kuralı: adaptörler **veritabanına yazmaz**. Yalnızca ham öğe üretir.
Normalizasyon, tekilleştirme ve saklama boru hattının işidir. Bu ayrım
olmadan her adaptör kendi saklama politikasını uygular ve Spec §9.3
tek noktadan zorlanamaz hale gelir.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from politikdesk.ingestion.models import RawItem


@runtime_checkable
class SourceAdapter(Protocol):
    """Bir kaynaktan yayın birimi çeken bileşen."""

    slug: str

    def fetch(self) -> list[RawItem]:
        """Kaynaktan güncel öğeleri çeker.

        Hata durumunda istisna fırlatabilir; boru hattı yakalar, loglar ve
        diğer kaynaklarla devam eder (F1-02 DoD: "hatalı feed'de çökmüyor").
        """
        ...


class AdapterRegistry:
    """`adapter` alanına göre adaptör sınıfı çözümler.

    `config/sources.yml` içindeki `adapter: rss` gibi bir değer, burada
    kayıtlı bir fabrikaya eşlenir. Yeni bir adaptör türü eklemek, yalnızca
    bu kayda bir satır eklemeyi gerektirir.
    """

    def __init__(self) -> None:
        self._factories: dict[str, type] = {}

    def register(self, key: str, factory: type) -> None:
        if key in self._factories:
            raise ValueError(f"'{key}' adaptörü zaten kayıtlı")
        self._factories[key] = factory

    def get(self, key: str) -> type:
        try:
            return self._factories[key]
        except KeyError as exc:
            raise KeyError(
                f"'{key}' adaptörü kayıtlı değil. Bilinen: {sorted(self._factories)}"
            ) from exc

    def keys(self) -> list[str]:
        return sorted(self._factories)


registry = AdapterRegistry()


class FakeAdapter:
    """Test adaptörü (F1-01 DoD).

    Boru hattının tamamı ağ olmadan koşturulabilsin diye vardır.
    """

    def __init__(self, slug: str, items: list[RawItem] | None = None,
                 error: Exception | None = None) -> None:
        self.slug = slug
        self._items = items or []
        self._error = error
        self.fetch_count = 0

    def fetch(self) -> list[RawItem]:
        self.fetch_count += 1
        if self._error is not None:
            raise self._error
        return list(self._items)


registry.register("fake", FakeAdapter)
