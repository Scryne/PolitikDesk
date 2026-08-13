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


class FailureRecorder:
    """Adaptörün *yuttuğu* hataları boru hattına taşıyan defter (B-80).

    Adaptörler bilerek hata yutar: bir kaynağın üç akışından biri düşerse
    diğer ikisi yine toplanmalıdır (F1-02). Ama yutulan hata boru hattına
    hiç ulaşmadığı için `run_source` istisna görmüyor ve turu
    `succeeded=true, 0 öğe` diye kaydediyordu. Resmî Gazete'nin TLS
    hatası ham kayıtta "başarılı" görünüyordu.

    Çözüm: hata yutulmaya devam eder ama **kaydedilir**. Boru hattı
    `drain_failures()` ile alır ve turun gerçekten başarılı olup
    olmadığına buna bakarak karar verir.
    """

    def __init__(self) -> None:
        self._failures: list[str] = []

    def record_failure(self, target: str, exc: BaseException) -> None:
        self._failures.append(f"{target}: {type(exc).__name__}: {str(exc)[:200]}")

    def note_failure(self, message: str) -> None:
        """İstisna olmayan başarısızlık (ör. uç 200 döndü ama liste boş)."""
        self._failures.append(message)

    def drain_failures(self) -> list[str]:
        """Biriken hataları döndürür ve defteri boşaltır.

        Boşaltma kasıtlı: adaptör örnekleri turlar arasında yeniden
        kullanılabilir; boşaltılmazsa bir turun hatası sonraki turda da
        raporlanır ve kaynak hiç düzelmemiş görünür.
        """
        drained = self._failures
        self._failures = []
        return drained


def drain_failures(adapter: object) -> list[str]:
    """Adaptör hata defteri tutuyorsa boşaltır; tutmuyorsa boş liste döner.

    `SourceAdapter` protokolü hata defterini zorunlu kılmaz — ağa hiç
    çıkmayan bir adaptörün yutacak hatası da yoktur.
    """
    drain = getattr(adapter, "drain_failures", None)
    if callable(drain):
        return list(drain())
    return []


@runtime_checkable
class SourceAdapter(Protocol):
    """Bir kaynaktan yayın birimi çeken bileşen."""

    slug: str

    def fetch(self) -> list[RawItem]:
        """Kaynaktan güncel öğeleri çeker.

        Hata durumunda istisna fırlatabilir; boru hattı yakalar, loglar ve
        diğer kaynaklarla devam eder (F1-02 DoD: "hatalı feed'de çökmüyor").

        İstisnayı *yutan* adaptör (birden çok akışı olanlar) `FailureRecorder`
        türetir ve yuttuğunu kaydeder — yoksa boru hattı boş turu başarılı
        sanar (B-80).
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
