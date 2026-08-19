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
        self._parsed = 0

    def record_failure(self, target: str, exc: BaseException) -> None:
        self._failures.append(f"{target}: {type(exc).__name__}: {str(exc)[:200]}")

    def note_failure(self, message: str) -> None:
        """İstisna olmayan başarısızlık (ör. uç 200 döndü ama liste boş)."""
        self._failures.append(message)

    def note_parsed(self, count: int) -> None:
        """Kaynaktan AYRIŞTIRILAN ham kalem sayısı — konu filtresinden ÖNCE.

        Neden ayrı bir sayaç gerekti (19 Ağustos 2026):

        `record_fetch` "0 öğe → kaynak sağlıksız" kuralını uygular ve bu
        kural doğrudur; JS ile yüklenen bir sayfa aksi hâlde sonsuza dek
        yeşil görünür (B-42/B-43). Ama kural iki farklı durumu birbirine
        karıştırıyordu:

            sayfadan hiç kalem çıkmadı        → GERÇEK arıza
            kalemler çıktı, konu filtresi     → NORMAL sonuç
            hiçbirini geçirmedi

        Resmî Gazete günde onlarca kalem yayımlar ve çoğu gün hiçbiri
        vergi/gümrük konusunda değildir. Ölçüldü: 7 günde 1358 turun
        516'sı bu yüzden "arıza" sayılmış, ardışık hata sayacı 758'e
        çıkmış ve kaynak kalıcı kırmızıya düşmüştü. Roadmap Faz 2.3'ün
        yasağı tam olarak buydu: *"Alarm yanlış pozitif üretmemeli."*

        Yanlış alarmın asıl bedeli gürültü değil **körlük**: kaynak zaten
        hep kırmızıysa, gerçekten bozulduğu gün hiçbir şey değişmez.

        Boru hattı düzeyindeki konu filtresi bunu zaten doğru yapıyordu —
        `filtered_out` sayılıyor ama `items_fetched` düşmüyor, kaynak
        yeşil kalıyor. Bu sayaç, adaptör içi filtreyi aynı hizaya getirir.
        """
        self._parsed += max(0, int(count))

    def drain_failures(self) -> list[str]:
        """Biriken hataları döndürür ve defteri boşaltır.

        Boşaltma kasıtlı: adaptör örnekleri turlar arasında yeniden
        kullanılabilir; boşaltılmazsa bir turun hatası sonraki turda da
        raporlanır ve kaynak hiç düzelmemiş görünür.
        """
        drained = self._failures
        self._failures = []
        return drained

    def peek_parsed(self) -> int:
        """Sayacı SIFIRLAMADAN okur — adaptörün kendi karar mantığı için."""
        return self._parsed

    def drain_parsed(self) -> int:
        """Ayrıştırılan kalem sayısını döndürür ve sayacı sıfırlar.

        `drain_failures` ile aynı gerekçe: adaptör örnekleri turlar
        arasında yeniden kullanılabilir.
        """
        drained = self._parsed
        self._parsed = 0
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


def drain_parsed(adapter: object) -> int | None:
    """Adaptör ham kalem sayacı tutuyorsa boşaltır, yoksa `None`.

    `None` "bu adaptör ayrım yapmıyor" demektir ve eski davranış aynen
    korunur — 89 kaynağın 88'i konu filtresi kullanmıyor, onlar için
    `items_fetched` zaten ham sayının kendisidir.
    """
    drain = getattr(adapter, "drain_parsed", None)
    if callable(drain):
        return int(drain())
    return None


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

    ⚠️ **Üretimde kullanılan yol bu DEĞİLDİR.** `registry.get()` hiçbir
    yerden çağrılmıyor; `ingestion/pipeline.py::build_adapter` açık if
    dallarıyla çözümlüyor — çünkü her adaptörün kurucu argümanları farklı
    (RSS `feed_url` + `keyword_filter` ister, `tuik_sdmx` kendi HTTP
    istemcisini kurar, `wp_rest` `base_url` ister). Genel bir fabrika
    bunları veremez.

    Kayıt yine de tutuluyor çünkü hangi adaptör türlerinin var olduğunu
    tek yerde listeliyor. Ama **yeni adaptör eklemek için kayda satır
    eklemek YETMEZ** — `build_adapter`'a da dal eklenmelidir. Eskiden bu
    belge "yalnızca bir satır yeter" diyordu; canlı koşumda kaydın
    konteynerde `['fake']`'ten ibaret olduğu görüldü (kayıt yalnızca
    modül import edilirse oluşuyor) ve boru hattı yine de çalıştı,
    çünkü kayda hiç bakmıyor (F5-02 denetimi).
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

    def __init__(
        self, slug: str, items: list[RawItem] | None = None, error: Exception | None = None
    ) -> None:
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
