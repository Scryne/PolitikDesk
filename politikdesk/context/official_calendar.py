"""Ulusal Veri Yayımlama Takvimi adaptörü (F2-18 · Roadmap Faz 1.2).

**F2-18 üç fazdır açıktı ve gerekçesi yanlıştı.**

Kayıtlı teşhis şuydu: "TÜİK'in takvim sayfası React SPA, sunucudan
okunamıyor" (B-42'nin aynısı). Sayfa gerçekten SPA — ama takvimin kendisi
başka bir konakta ve **kimlik doğrulama istemeyen bir JSON ucunda**
duruyor. 19 Ağustos 2026'da SPA'nın JS paketi okunarak bulundu; yöntem
`tuik_auth.py`'de TÜİK SDMX protokolünün bulunuş yöntemiyle aynıdır:

    takvim.tuik.gov.tr/ulusaltakvim/index.js  ->  içinde:
        coreUrl = "/Kurumsal/GetYillikHaberBulteniListesi?yil=" + yil

    GET https://takvim.tuik.gov.tr/Kurumsal/GetYillikHaberBulteniListesi?yil=2026
    -> {"yayindaOlanlarList": [...], "yayindaOlmayanlarList": [...]}

Bu yalnızca TÜİK takvimi DEĞİLDİR: 2026 için 4.085 kayıt, **31 kurumdan**
(TCMB 1061, BDDK 343, SPK 325, TÜİK 245, HMB 150, EPDK, ETKB, STB…).
Spec §9.5'in "MVP'nin gizli kozu" dediği katmanın gerçek veri kaynağı
budur; elle bakımlı `config/calendar_2026.yml` 17 kayıt taşıyordu.

-----------------------------------------------------------------------
TASARIMIN İKİ DAYANAK NOKTASI
-----------------------------------------------------------------------

**1. "Beklenen" ile "gerçekleşen" ayrımını KURUM yapıyor.**

Uç iki ayrı liste döndürür: yayımlananlar ve yayımlanmayanlar. Yani
`published_at`'i biz çıkarım yaparak bulmuyoruz — ölçüyoruz. Bu, gecikme
metriğini (Roadmap 1.2) tahmine dayanmaktan kurtarır.

**2. Takvim bir OLAY DEĞİLDİR, bir BEKLENTİDİR.**

Bu modül `articles` tablosuna hiçbir şey yazmaz ve `RawItem` üretmez.
Takvim kaydı bir haber değildir; haber geldiğinde `scheduler_match`
ikisini birbirine bağlar. Karıştırılsaydı kanıt havuzuna "TÜİK yarın
enflasyon açıklayacak" diye bir kaynak girerdi — henüz var olmayan bir
veri, kanıt sayılamaz.

⛔ Bu modül `politikdesk.llm` import ETMEZ.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from zoneinfo import ZoneInfo

from politikdesk.db import connection
from politikdesk.ingestion.http import HttpClient
from politikdesk.observability import get_logger

log = get_logger(__name__)

CALENDAR_URL: Final[str] = (
    "https://takvim.tuik.gov.tr/Kurumsal/GetYillikHaberBulteniListesi?yil={year}"
)

# Takvim saatleri Türkiye yerel saatidir ve uç saat dilimi BİLDİRMEZ
# ("2026-08-19T10:00:00"). UTC varsayılsaydı her yayım 3 saat kayardı ve
# `scheduler_match`'in ±3 saatlik penceresi tam sınırda çalışırdı — yani
# eşleşmeler rastgele tutar, rastgele kaçardı.
CALENDAR_TZ: Final[ZoneInfo] = ZoneInfo("Europe/Istanbul")

PUBLISHED_KEY: Final[str] = "yayindaOlanlarList"
PENDING_KEY: Final[str] = "yayindaOlmayanlarList"

# Hangi kurumların yayınları takvime alınacak.
#
# Boş bırakılsaydı 31 kurumun 4.085 kaydı girerdi ve takvim ekranı
# okunamaz hâle gelirdi. Bu liste ürünün dikeyiyle sınırlıdır: makro
# ekonomi ve kamu maliyesi. Genişletmek tek satırlık bir karardır ama
# BİLİNÇLİ bir karar olmalıdır.
DEFAULT_INSTITUTIONS: Final[frozenset[str]] = frozenset(
    {"TÜİK", "TUIK", "TCMB", "HMB", "BDDK", "SPK", "EPDK"}
)


class CalendarFetchError(RuntimeError):
    """Takvim ucu beklenen sözleşmeyi döndürmedi."""


@dataclass(frozen=True)
class CalendarEntry:
    """Takvimden gelen tek bir yayım kaydı."""

    external_id: str
    title: str
    institution: str
    institution_full: str
    expected_at: datetime
    reference_period: str | None
    url: str | None
    is_published: bool

    @property
    def published_at(self) -> datetime | None:
        """Yayımlanmış kayıtlarda gerçekleşen an.

        Kurum yayımlananları ayrı listede verdiği için `gTarih` o
        kayıtlarda GERÇEKLEŞEN andır. Bekleyen kayıtlarda aynı alan
        beklenen andır — bu yüzden liste üyeliği anlamı belirler.
        """
        return self.expected_at if self.is_published else None

    @property
    def delay_minutes(self) -> int | None:
        """Şu an için hep 0 döner ve bu DOĞRUDUR.

        Uç, yayımlanan kayıtta beklenen ve gerçekleşen anı ayrı ayrı
        vermiyor; tek bir `gTarih` var. Gecikmeyi uydurmak yerine
        ölçülemediğini söylüyoruz. Gerçek gecikme, `published_at` ile
        BİZİM boru hattımızın olayı gördüğü an arasından hesaplanır
        (`scheduler_match` bağlantısı kurulduğunda) — o ölçüm
        `delivery_lag_report()` içindedir.
        """
        return 0 if self.is_published else None


def _parse_datetime(raw: Any) -> datetime | None:
    """`2026-08-19T10:00:00` -> saat dilimi farkında datetime.

    Saat dilimi taşımayan değer Türkiye yereli sayılır (bkz. CALENDAR_TZ).
    Tanınmayan biçimde **None** döner ve kayıt atlanır — yanlış tarihli
    bir takvim kaydı, kayıt olmamasından kötüdür.
    """
    if isinstance(raw, datetime):
        moment = raw
    else:
        text = str(raw or "").strip()
        if not text:
            return None
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            return None
    return moment.replace(tzinfo=CALENDAR_TZ) if moment.tzinfo is None else moment


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def build_external_id(
    institution: str, title: str, reference_period: str | None, expected_at: datetime
) -> str:
    """Takvim kaydının KALICI kimliği.

    ⛔ Kaynağın kendi `id` alanı kullanılamaz ve bu ölçülmüş bir sonuçtur.

    19 Ağustos 2026: bekleyen listede 1.537 kayıt var ama yalnızca 1.388
    tekil `id`. Fark tamamen TÜİK'ten geliyor — TÜİK'in 150 bekleyen
    yayınının HEPSİ aynı `id`'yi taşıyor, oysa hepsi farklı yayın
    (farklı tarih, farklı başlık, farklı dönem: "Tüketici Güven Endeksi /
    Aralık 2026", "Dış Ticaret İstatistikleri / Kasım 2026"…).

    İlk uygulamada kimlik `id`'den türetiliyordu ve benzersizlik kısıtı
    bu 150 kaydı **sessizce tek satıra indirdi** — veritabanında TÜİK'in
    hiç bekleyen yayını görünmüyordu. Sessiz veri kaybı, bu depodaki
    diğer sessiz arızalarla (B-42, B-43) aynı sınıftadır.

    Kimlik bunun yerine YAYININ KENDİSİNDEN türetilir: hangi kurum, neyi,
    hangi dönem için yayımlıyor. Tarih bilerek DIŞARIDA: bir yayın
    ertelenirse aynı kayıt güncellenmeli, ikinci bir satır doğmamalı.
    Dönem yoksa tarihe düşülür — o zaman tarih kimliğin parçasıdır.
    """
    import hashlib

    cekirdek = reference_period or expected_at.date().isoformat()
    ham = f"{institution}|{title}|{cekirdek}"
    ozet = hashlib.sha1(ham.encode("utf-8")).hexdigest()[:20]  # noqa: S324 — kriptografik değil
    return f"tuik-takvim:{ozet}"


def parse_payload(
    body: str,
    *,
    institutions: frozenset[str] | None = None,
) -> list[CalendarEntry]:
    """Takvim JSON'ını `CalendarEntry` listesine çevirir.

    HTML gövdesi **istisnaya** dönüşür. Bu depo aynı sessiz arızayı üç kez
    yaşadı (B-42 TÜİK portalı, B-43 Hazine, EVDS anahtarsız yanıtı): uç
    200 döndürür, gövde HTML'dir, adaptör 0 öğe üretir ve tur "başarılı"
    görünür. Sessiz sıfır yerine gürültülü hata.
    """
    text = (body or "").strip()
    if not text:
        raise CalendarFetchError("Takvim ucu boş gövde döndürdü.")

    if text.lstrip()[:200].lower().startswith(("<!doctype html", "<html")):
        raise CalendarFetchError(
            "Takvim ucu HTML döndürdü (beklenen JSON). Uç adresi değişmiş "
            "olabilir; JS paketinden yeniden çıkarılmalı: "
            "takvim.tuik.gov.tr/ulusaltakvim/index.js"
        )

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CalendarFetchError(f"Takvim yanıtı JSON değil: {str(exc)[:120]}") from exc

    if not isinstance(payload, dict):
        raise CalendarFetchError("Takvim yanıtı beklenen nesne değil.")

    missing = [k for k in (PUBLISHED_KEY, PENDING_KEY) if k not in payload]
    if missing:
        raise CalendarFetchError(
            f"Takvim yanıtında beklenen liste(ler) yok: {missing} "
            f"(gelen alanlar: {sorted(payload)[:8]})"
        )

    allowed = DEFAULT_INSTITUTIONS if institutions is None else institutions
    entries: list[CalendarEntry] = []
    atlanan_tarih = 0

    for key, is_published in ((PUBLISHED_KEY, True), (PENDING_KEY, False)):
        rows = payload.get(key) or []
        if not isinstance(rows, list):
            raise CalendarFetchError(f"'{key}' bir liste değil.")

        for row in rows:
            if not isinstance(row, dict):
                continue

            kurum = _clean(row.get("sorumluKisaAd")) or ""
            if allowed and kurum not in allowed:
                continue

            baslik = _clean(row.get("adi"))
            if not baslik:
                continue

            beklenen = _parse_datetime(row.get("gTarih"))
            if beklenen is None:
                atlanan_tarih += 1
                continue

            donem = _clean(row.get("donemi"))

            entries.append(
                CalendarEntry(
                    external_id=build_external_id(kurum, baslik, donem, beklenen),
                    title=baslik,
                    institution=kurum,
                    institution_full=_clean(row.get("sorumluKurum")) or kurum,
                    expected_at=beklenen,
                    reference_period=donem,
                    url=_clean(row.get("link")),
                    is_published=is_published,
                )
            )

    if atlanan_tarih:
        log.warning("calendar_unparsed_dates", count=atlanan_tarih)

    entries.sort(key=lambda e: e.expected_at)
    return entries


@dataclass
class OfficialCalendarFetcher:
    """Takvimi çeker ve `scheduled_events`'e idempotent olarak yazar."""

    http: HttpClient | None = None
    institutions: frozenset[str] | None = None
    _owns_http: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.http is None:
            # 1,3 MB'lık tek bir yanıt; robots denetimi kapalı çünkü bu
            # bir tarama değil, kurumun kendi veri ucuna yapılan çağrı.
            self.http = HttpClient(respect_robots=False, timeout=90.0, max_retries=3)
            self._owns_http = True

    def fetch_year(self, year: int) -> list[CalendarEntry]:
        assert self.http is not None
        url = CALENDAR_URL.format(year=year)
        response = self.http.get(url, source_slug="tuik")
        return parse_payload(response.text, institutions=self.institutions)

    def close(self) -> None:
        if self._owns_http and self.http is not None:
            self.http.close()


def upsert_entries(
    entries: list[CalendarEntry], *, vertical: str = "macro_economy"
) -> dict[str, int]:
    """Takvim kayıtlarını idempotent yazar.

    ⛔ `linked_event_id` ve `occurred` durumu **KORUNUR**. Takvim turu her
    30 dakikada koşar; eşleştirmeyi ezseydi `scheduler_match`'in kurduğu
    bağ her turda silinir ve olay-takvim ilişkisi hiç kalıcı olmazdı.

    Durum geçişi yalnızca tek yönlüdür: pending -> published. Geri dönüş
    yoktur; kurum bir yayını "yayımlanmadı"ya çeviremez.
    """
    if not entries:
        return {"inserted": 0, "updated": 0, "unchanged": 0}

    inserted = updated = 0
    with connection() as conn, conn.cursor() as cur:
        for entry in entries:
            cur.execute(
                """
                INSERT INTO scheduled_events (
                    title, expected_at, vertical, status,
                    external_id, institution, reference_period, url, published_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (external_id) WHERE external_id IS NOT NULL
                DO UPDATE SET
                    title            = EXCLUDED.title,
                    expected_at      = EXCLUDED.expected_at,
                    institution      = EXCLUDED.institution,
                    reference_period = EXCLUDED.reference_period,
                    url              = EXCLUDED.url,
                    published_at     = COALESCE(scheduled_events.published_at,
                                                EXCLUDED.published_at),
                    -- `occurred` bir KAZANIMDIR: boru hattımız olayı
                    -- gerçekten gördü. Takvim turu onu geri alamaz.
                    status = CASE
                        WHEN scheduled_events.status = 'occurred' THEN 'occurred'
                        WHEN EXCLUDED.status = 'published'        THEN 'published'
                        ELSE scheduled_events.status
                    END
                RETURNING (xmax = 0) AS is_insert
                """,
                (
                    entry.title,
                    entry.expected_at,
                    vertical,
                    "published" if entry.is_published else "pending",
                    entry.external_id,
                    entry.institution,
                    entry.reference_period,
                    entry.url,
                    entry.published_at,
                ),
            )
            row = cur.fetchone()
            if row and row.get("is_insert"):
                inserted += 1
            else:
                updated += 1
        conn.commit()

    stats = {"inserted": inserted, "updated": updated, "total": len(entries)}
    log.info("official_calendar_upserted", **stats)
    return stats


def sync(
    years: tuple[int, ...] | None = None,
    *,
    institutions: frozenset[str] | None = None,
) -> dict[str, int]:
    """Takvimi çeker ve veritabanına yazar (Celery görevinin giriş noktası)."""
    now = datetime.now(CALENDAR_TZ)
    # İçinde bulunulan yıl her zaman; yıl sonuna iki aydan az kaldıysa
    # gelecek yıl da — aksi hâlde Aralık'ta "sırada ne var" boşalırdı.
    target = years or ((now.year, now.year + 1) if now.month >= 11 else (now.year,))

    fetcher = OfficialCalendarFetcher(institutions=institutions)
    toplam = {"inserted": 0, "updated": 0, "total": 0, "years": 0}
    try:
        for year in target:
            try:
                entries = fetcher.fetch_year(year)
            except Exception as exc:  # noqa: BLE001 — bir yıl diğerini düşürmez
                log.error(
                    "official_calendar_year_failed",
                    year=year,
                    error=type(exc).__name__,
                    detail=str(exc)[:200],
                )
                continue
            stats = upsert_entries(entries)
            toplam["inserted"] += stats["inserted"]
            toplam["updated"] += stats["updated"]
            toplam["total"] += stats["total"]
            toplam["years"] += 1
    finally:
        fetcher.close()

    return toplam


# ---------------------------------------------------------------------------
# Sorgular — Roadmap 1.2 çıkış ölçütü
# ---------------------------------------------------------------------------
def expected_on(
    day: Any = None, *, institution: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    """"Bugün hangi resmî veri açıklanması bekleniyor?"

    Roadmap 1.2'nin çıkış ölçütü budur ve cevabı **deterministiktir**:
    kurumun kendi yayımladığı takvimden gelir, tahmin içermez.
    """
    hedef = day or datetime.now(CALENDAR_TZ).date()
    kurum_kosulu = "AND se.institution = %s" if institution else ""
    params: list[Any] = [hedef, hedef]
    if institution:
        params.append(institution)
    params.append(limit)

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT se.id, se.title, se.institution, se.expected_at,
                   se.reference_period, se.url, se.status, se.published_at,
                   se.linked_event_id, e.title AS linked_event_title
            FROM scheduled_events se
            LEFT JOIN events e ON e.id = se.linked_event_id
            WHERE (se.expected_at AT TIME ZONE 'Europe/Istanbul')::date
                  BETWEEN %s AND %s
              {kurum_kosulu}
            ORDER BY se.expected_at
            LIMIT %s
            """,  # noqa: S608 — `kurum_kosulu` sabit iki değerden biri
            params,
        )
        return [dict(r) for r in cur.fetchall()]


def upcoming(*, hours: int = 48, limit: int = 50) -> list[dict[str, Any]]:
    """Önümüzdeki N saatte beklenen resmî yayınlar."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT se.id, se.title, se.institution, se.expected_at,
                   se.reference_period, se.url, se.status
            FROM scheduled_events se
            WHERE se.status = 'pending'
              AND se.expected_at BETWEEN now() AND now() + %s
            ORDER BY se.expected_at
            LIMIT %s
            """,
            (timedelta(hours=hours), limit),
        )
        return [dict(r) for r in cur.fetchall()]


def delivery_lag_report(*, days: int = 30, limit: int = 50) -> list[dict[str, Any]]:
    """Kurum yayımladı — biz ne kadar sonra gördük? (Roadmap 1.2 gecikme metriği)

    Ölçülen şey kurumun gecikmesi DEĞİLDİR; bizim boru hattımızın
    tepki süresidir. Kurumun kendi gecikmesi bu uçtan hesaplanamıyor
    (yayımlanan kayıtta beklenen ve gerçekleşen an ayrı verilmiyor) ve
    hesaplanamayan bir şeyi hesaplıyormuş gibi göstermiyoruz.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT se.institution,
                   count(*)                                   AS yayim_sayisi,
                   count(se.linked_event_id)                  AS eslesen,
                   round(avg(EXTRACT(EPOCH FROM
                        (e.first_reported_at - se.expected_at)) / 60)::numeric, 1)
                                                              AS ort_gecikme_dk
            FROM scheduled_events se
            LEFT JOIN events e ON e.id = se.linked_event_id
            WHERE se.expected_at >= now() - %s
              AND se.status IN ('published', 'occurred')
            GROUP BY se.institution
            ORDER BY yayim_sayisi DESC
            LIMIT %s
            """,
            (timedelta(days=days), limit),
        )
        return [dict(r) for r in cur.fetchall()]


def missed_report(*, days: int = 7, limit: int = 50) -> list[dict[str, Any]]:
    """Kurum yayımladı ama BİZ görmedik.

    Ürünün en rahatsız edici sorusu ve tam da bu yüzden değerli:
    beklenen bir resmî yayın gerçekleşti, hiçbir kaynağımız haberleştirmedi
    ve boru hattımız onu hiç görmedi. Kaynak kadrosundaki kör noktayı
    başka hiçbir gösterge bu kadar doğrudan söylemez.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT se.id, se.title, se.institution, se.expected_at,
                   se.reference_period, se.url
            FROM scheduled_events se
            WHERE se.status = 'published'
              AND se.linked_event_id IS NULL
              AND se.expected_at BETWEEN now() - %s AND now()
            ORDER BY se.expected_at DESC
            LIMIT %s
            """,
            (timedelta(days=days), limit),
        )
        return [dict(r) for r in cur.fetchall()]


def _now_utc() -> datetime:
    return datetime.now(UTC)
