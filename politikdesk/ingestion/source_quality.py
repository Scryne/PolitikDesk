"""Kaynak operasyonel kalite skoru (Roadmap Faz 2.1).

-----------------------------------------------------------------------
⛔ BU BİR GÜVENİLİRLİK YARGISI DEĞİLDİR
-----------------------------------------------------------------------

Buradaki skor **kaynağın haberciliği hakkında hiçbir şey söylemez.**
Yalnızca şunu ölçer: *bu akış teknik olarak sağlıklı mı ve ürüne ne tür
veri veriyor?*

Ayrım pazarlıksızdır çünkü Spec §8.5 kaynağa siyasi konum etiketi
verilmesini yasaklar ve `tests/test_web.py` bunu tarar. "Kaynak kalitesi"
adı taşıyan bir sayının editoryal güvenilirliğe kayması, o yasağın en
kolay ihlal biçimidir: skor bir kez "X kaynağı 42 puan" diye okunmaya
başladığında, kimse onun yalnızca HTTP başarı oranı olduğunu hatırlamaz.

Bu yüzden:
  * Bileşenlerin hiçbiri içeriğe bakmaz. Hiçbiri.
  * `reliability` = ÇEKİM başarı oranı, haber doğruluğu değil.
  * Skor tek bir sayı olarak değil, **bileşenleriyle birlikte** döner;
    çağıran taraf hangi girdiden geldiğini görebilir.
  * Sıralama yardımcısıdır: "hangi akış bakım istiyor?" sorusunu
    yanıtlar, "hangi kaynağa inanayım?" sorusunu DEĞİL.

-----------------------------------------------------------------------
VERİ NEREDEN GELİYOR
-----------------------------------------------------------------------

Hepsi ölçülmüş, hiçbiri varsayılmamıştır:

    source_fetch_log   tur başına başarı, süre, çekilen/saklanan/tekrar
    sources            tier, kind, adapter, independence_group, son başarı
    articles           official_value üretimi (yapılandırılmışlık kanıtı)

Ölçülemeyen bir bileşen **uydurulmaz**: veri yoksa o bileşen `None`
döner ve ortalamaya girmez. Bir kaynağın hiç turu yoksa `reliability`
sıfır DEĞİL, bilinmeyendir — ikisi çok farklı şeylerdir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

from politikdesk.db import connection
from politikdesk.observability import get_logger

log = get_logger(__name__)

# Değerlendirme penceresi. 7 gün, haftalık ritmi olan kaynakları
# (Sayıştay, bazı TCMB serileri) en az bir kez yakalar.
DEFAULT_WINDOW_DAYS: Final[int] = 7

# Tazelik eşiği kaynağın RİTMİNE bağlıdır, takvime değil. Günlük yayın
# yapan bir haber akışı 12 saattir susuyorsa arıza; aylık bir gösterge
# serisi için aynı süre normaldir.
#
# `sources` tablosunda beklenen ritim alanı YOK; bu yüzden adaptör
# türünden türetiliyor. Tahmin değil, tasarım bilgisi: `evds`/`tuik_sdmx`
# seri adaptörleridir ve seyrek yayımlanan gözlemleri tekrar tekrar
# çeker, `rss` ise akış adaptörüdür.
FRESHNESS_BUDGET_HOURS: Final[dict[str, float]] = {
    "rss": 12.0,
    "twitter": 48.0,
    "tuik_sdmx": 24.0,
    "evds": 24.0,
    "resmi_gazete": 48.0,
    "sayistay": 168.0,
    "tbmm": 72.0,
    "cumhurbaskanligi": 72.0,
    "wp_rest": 48.0,
    "generic_html": 48.0,
}
DEFAULT_FRESHNESS_BUDGET_HOURS: Final[float] = 24.0

# Yapılandırılmışlık: verinin makine okunur olma derecesi. Bu, kanıt
# motorunun R3 kuralı için doğrudan anlamlıdır — `official_value` üreten
# bir kaynak tek başına 🟢 sağlayabilir (Spec §8.3).
STRUCTUREDNESS_BY_ACCESS: Final[dict[str, int]] = {
    "api": 90,
    "official_feed": 70,
    "rss": 50,
    "social": 20,
}
DEFAULT_STRUCTUREDNESS: Final[int] = 40

# Otorite: kanıt zincirindeki konum. `tier` Spec §9.1'in kademesidir.
AUTHORITY_BY_TIER: Final[dict[int, int]] = {1: 95, 2: 70, 3: 55, 4: 25}
DEFAULT_AUTHORITY: Final[int] = 40


@dataclass(frozen=True)
class QualityComponent:
    """Tek bir bileşen. `value is None` = ÖLÇÜLEMEDİ (sıfır değil)."""

    key: str
    label: str
    value: float | None
    detail: str

    @property
    def measured(self) -> bool:
        return self.value is not None


@dataclass
class SourceQuality:
    """Bir kaynağın operasyonel kalite profili."""

    slug: str
    name: str
    tier: int
    adapter: str | None
    independence_group: str | None
    components: list[QualityComponent] = field(default_factory=list)

    @property
    def measured_components(self) -> list[QualityComponent]:
        return [c for c in self.components if c.measured]

    @property
    def score(self) -> float | None:
        """Bileşenlerin ortalaması. Ölçülemeyenler ortalamaya GİRMEZ.

        Ağırlıklandırma yok ve bu bilinçli: ağırlık seçmek, bileşenlerin
        göreli önemi hakkında savunulamayan bir iddiadır. Eşit ağırlık
        en azından dürüsttür ve bileşenler ayrı ayrı döndüğü için
        okuyan taraf kendi önceliğini uygulayabilir.
        """
        olculen = self.measured_components
        if not olculen:
            return None
        return round(sum(float(c.value or 0) for c in olculen) / len(olculen), 1)

    @property
    def coverage(self) -> str:
        """Skorun kaç bileşene dayandığı — sayının ne kadar güvenilir
        okunabileceğini söyler."""
        return f"{len(self.measured_components)}/{len(self.components)}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "tier": self.tier,
            "adapter": self.adapter,
            "independence_group": self.independence_group,
            "score": self.score,
            "coverage": self.coverage,
            "components": [
                {"key": c.key, "label": c.label, "value": c.value, "detail": c.detail}
                for c in self.components
            ],
        }


def _authority(row: dict[str, Any]) -> QualityComponent:
    """Kanıt zincirindeki konum — tier + resmî sayı üretimi.

    İçeriğe BAKMAZ. Tier, Spec §9.1'in kademe tanımıdır (resmî kurum /
    ajans / bağımsız yayın) ve editoryal bir not değildir.
    """
    tier = int(row["tier"] or 0)
    puan = float(AUTHORITY_BY_TIER.get(tier, DEFAULT_AUTHORITY))
    detay = f"Tier {tier}"

    if row.get("official_value_count"):
        # Kurumun kendi makine okunur sayısını üreten kaynak, kanıt
        # motorunun R3 kuralını besler; bu ölçülebilir bir farktır.
        puan = min(100.0, puan + 5.0)
        detay += f" · {row['official_value_count']} resmî değer"
    return QualityComponent("authority", "Otorite", puan, detay)


def _independence(row: dict[str, Any]) -> QualityComponent:
    """Bağımsızlık grubunu kaç kaynak paylaşıyor?

    Aynı grupta ikinci bir kaynak, `independent_count` sayımına KATKI
    YAPMAZ (Spec §8.2). Grubu paylaşan kaynak değersiz değildir — ama
    bağımsızlık açısından yeni bir şey getirmez ve skor bunu söyler.
    """
    grup = row.get("independence_group")
    if not grup:
        return QualityComponent(
            "independence", "Bağımsızlık", None, "grup atanmamış — ölçülemedi"
        )
    paylasan = int(row.get("group_size") or 1)
    puan = 100.0 if paylasan == 1 else round(100.0 / paylasan, 1)
    detay = f"{grup} · {paylasan} kaynak paylaşıyor" if paylasan > 1 else f"{grup} · tekil"
    return QualityComponent("independence", "Bağımsızlık", puan, detay)


def _freshness(row: dict[str, Any]) -> QualityComponent:
    """Son başarılı çekimden bu yana geçen süre, kaynağın ritmine göre."""
    son = row.get("last_success_at")
    if son is None:
        return QualityComponent(
            "freshness", "Tazelik", 0.0, "hiç başarılı çekim yok"
        )

    butce = FRESHNESS_BUDGET_HOURS.get(
        (row.get("adapter") or "").strip().lower(), DEFAULT_FRESHNESS_BUDGET_HOURS
    )
    yas = (datetime.now(UTC) - son).total_seconds() / 3600
    oran = max(0.0, 1.0 - (yas / butce))
    return QualityComponent(
        "freshness",
        "Tazelik",
        round(oran * 100, 1),
        f"{yas:.1f} sa önce · bütçe {butce:.0f} sa",
    )


def _reliability(row: dict[str, Any]) -> QualityComponent:
    """ÇEKİM başarı oranı — haberciliğin değil, HTTP'nin güvenilirliği."""
    tur = int(row.get("run_count") or 0)
    if tur == 0:
        # Sıfır tur, sıfır güvenilirlik DEĞİLDİR. Ölçülemedi.
        return QualityComponent(
            "reliability", "Çekim başarısı", None, "pencerede tur yok — ölçülemedi"
        )
    basarili = int(row.get("success_count") or 0)
    oran = basarili / tur
    return QualityComponent(
        "reliability",
        "Çekim başarısı",
        round(oran * 100, 1),
        f"{basarili}/{tur} tur başarılı",
    )


def _structuredness(row: dict[str, Any]) -> QualityComponent:
    """Verinin makine okunur olma derecesi."""
    yontem = (row.get("access_method") or "").strip().lower()
    puan = float(STRUCTUREDNESS_BY_ACCESS.get(yontem, DEFAULT_STRUCTUREDNESS))
    detay = yontem or "bilinmiyor"
    if row.get("official_value_count"):
        puan = min(100.0, puan + 10.0)
        detay += " · makine okunur sayı üretiyor"
    return QualityComponent("structuredness", "Yapılandırılmışlık", puan, detay)


def _yield_consistency(row: dict[str, Any]) -> QualityComponent:
    """Çekilen öğenin ne kadarı gerçekten yeni içerik?

    Yüksek tekrar oranı bir ARIZA DEĞİLDİR: seri adaptörleri (EVDS,
    TÜİK SDMX) aynı gözlemi her turda yeniden çeker ve bu tasarım
    gereğidir. Bu yüzden bileşen "verim" olarak adlandırılıyor, "israf"
    olarak değil, ve seri adaptörlerinde ölçülmüyor — orada anlamsız
    bir ceza üretirdi.
    """
    adapter = (row.get("adapter") or "").strip().lower()
    if adapter in {"evds", "tuik_sdmx"}:
        return QualityComponent(
            "yield", "İçerik verimi", None,
            "seri adaptörü — tekrar beklenen davranış, ölçülmüyor",
        )

    cekilen = int(row.get("items_fetched") or 0)
    if cekilen == 0:
        return QualityComponent(
            "yield", "İçerik verimi", None, "pencerede öğe yok — ölçülemedi"
        )

    tekrar = int(row.get("dupes") or 0)
    yeni_oran = max(0.0, 1.0 - (tekrar / cekilen))
    return QualityComponent(
        "yield",
        "İçerik verimi",
        round(yeni_oran * 100, 1),
        f"{cekilen} çekildi · {tekrar} tekrar",
    )


_BUILDERS = (_authority, _independence, _freshness, _reliability, _structuredness,
             _yield_consistency)


def report(*, window_days: int = DEFAULT_WINDOW_DAYS) -> list[SourceQuality]:
    """Aktif kaynakların operasyonel kalite profili, skora göre sıralı."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            WITH grup AS (
                SELECT independence_group, count(*) AS n
                FROM sources
                WHERE is_active AND independence_group IS NOT NULL
                GROUP BY independence_group
            ),
            tur AS (
                SELECT source_id,
                       count(*)                          AS run_count,
                       count(*) FILTER (WHERE succeeded) AS success_count,
                       sum(items_fetched)                AS items_fetched,
                       sum(exact_dupes + near_dupes)     AS dupes,
                       round(avg(duration_ms))           AS avg_ms
                FROM source_fetch_log
                WHERE started_at > now() - %s * interval '1 day'
                GROUP BY source_id
            ),
            resmi AS (
                SELECT source_id, count(*) AS official_value_count
                FROM articles
                WHERE official_value IS NOT NULL
                GROUP BY source_id
            )
            SELECT s.slug, s.name, s.tier, s.adapter, s.access_method,
                   s.independence_group, s.last_success_at,
                   COALESCE(g.n, 1)                    AS group_size,
                   COALESCE(t.run_count, 0)            AS run_count,
                   COALESCE(t.success_count, 0)        AS success_count,
                   COALESCE(t.items_fetched, 0)        AS items_fetched,
                   COALESCE(t.dupes, 0)                AS dupes,
                   t.avg_ms                            AS avg_ms,
                   COALESCE(r.official_value_count, 0) AS official_value_count
            FROM sources s
            LEFT JOIN grup  g ON g.independence_group = s.independence_group
            LEFT JOIN tur   t ON t.source_id = s.id
            LEFT JOIN resmi r ON r.source_id = s.id
            WHERE s.is_active
            ORDER BY s.tier, s.slug
            """,
            (window_days,),
        )
        rows = [dict(r) for r in cur.fetchall()]

    out = [
        SourceQuality(
            slug=row["slug"],
            name=row["name"],
            tier=int(row["tier"] or 0),
            adapter=row["adapter"],
            independence_group=row["independence_group"],
            components=[build(row) for build in _BUILDERS],
        )
        for row in rows
    ]
    # Skorsuz kaynaklar (hiç ölçülememiş) sona; aralarında slug sırası.
    out.sort(key=lambda q: (q.score is None, -(q.score or 0), q.slug))
    return out


# Bakım sinyali YALNIZCA işletimsel bileşenlerden gelir.
#
# `authority`, `independence` ve `structuredness` kaynağın YAPISAL
# özellikleridir: bir X hesabının Tier 4 olması bir arıza değil, R7
# epistemik tavanının gereğidir. Bunları bakım eşiğine dâhil etmek, 46
# sosyal kaynağı "sosyal oldukları için" kalıcı olarak işaretlerdi —
# yani hep açık, dolayısıyla hiçbir şey söylemeyen bir alarm.
#
# Bu deponun tekrar eden dersi: yanlış alarm veren bir alarm kapatılır,
# kapatılmış alarm gerçek arızayı gizler (bkz. `pipeline_health.py`
# iddia aşaması, `conftest.py` DB testleri, `.gitattributes` satır sonu).
OPERATIONAL_KEYS: Final[frozenset[str]] = frozenset({"freshness", "reliability", "yield"})


def needs_attention(
    *, window_days: int = DEFAULT_WINDOW_DAYS, threshold: float = 60.0
) -> list[tuple[SourceQuality, list[QualityComponent]]]:
    """Bakımı GEREKEN kaynaklar ve sebepleri.

    Ölçüt genel skor değil, **düzeltilebilir** bileşenlerdir: tazelik,
    çekim başarısı ve içerik verimi. Bir kaynağın Tier 4 olması bakım
    istemez; 6 saattir veri vermemesi ister.

    Her kayıt sebebiyle birlikte döner — "şu kaynak kötü" değil, "şu
    kaynağın şu bileşeni şu değerde" denebilsin diye.
    """
    out: list[tuple[SourceQuality, list[QualityComponent]]] = []
    for q in report(window_days=window_days):
        sebepler = [
            c
            for c in q.components
            if c.key in OPERATIONAL_KEYS and c.measured and float(c.value or 0) < threshold
        ]
        if sebepler:
            out.append((q, sebepler))

    # En zayıf işletimsel bileşene göre sırala: en acil olan başta.
    out.sort(key=lambda pair: min(float(c.value or 0) for c in pair[1]))
    return out
