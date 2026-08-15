"""Maliyet modeli (F0-06, F0-07).

Kullanıcı başına aylık maliyeti hesaplar ve G0 koşul 8'i (≤ 8 $/kullanıcı/ay)
denetler. Fiyatlar `politikdesk/llm/pricing.py`den okunur — tek kaynak.

Modelin kritik ayrımı:
  * SABİT maliyetler (ingestion, embedding, kümeleme, özetleme) tüm
    kullanıcılar arasında PAYLAŞILIR. Kullanıcı arttıkça kişi başı düşer.
  * DEĞİŞKEN maliyetler (taslak üretimi, brifing) kullanıcı başınadır.

Kullanım:
    python -m scripts.cost_model                 # tabloyu yazdır
    python -m scripts.cost_model --csv out.csv   # CSV olarak da kaydet
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from politikdesk.llm.pricing import estimate_cost_usd

DAYS_PER_MONTH = 30.4

# Hedef: Spec §13.3 / G0 koşul 8
COST_TARGET_PER_USER_USD = 8.0


@dataclass(frozen=True)
class Assumptions:
    """Model girdileri. Değiştirmek isteyen buradan değiştirir; hesap otomatik güncellenir."""

    # --- Hacim (8 kaynak, MVP dikeyi) ---
    articles_per_day: int = 200  # 8 kaynak × ~25 yayın/gün
    events_per_day: int = 35  # ~5-6 makale bir olayda birleşir
    dedup_rate: float = 0.25  # tekrar/ajans kopyası oranı (LLM'e gitmez)

    # --- Sabit: makale başına çıkarım (ucuz model) ---
    extraction_model: str = "claude-sonnet-5"
    tokens_in_per_article: int = 1_200  # başlık + lead + prompt
    tokens_out_per_article: int = 400  # yapılandırılmış iddia JSON'u
    cache_hit_ratio: float = 0.85  # sistem promptu önbellekten okunur

    # --- Sabit: olay başına özetleme (ucuz model) ---
    tokens_in_per_event: int = 3_000  # kanıt listesi
    tokens_out_per_event: int = 500  # TL;DR + ne biliyoruz/bilmiyoruz

    # --- Sabit: embedding ---
    embedding_usd_per_million: float = 0.06  # F0-13 sonucuna göre güncellenir
    tokens_per_embedding: int = 700

    # --- Sabit: altyapı ---
    vps_usd_per_month: float = 30.0  # Hetzner/DO sınıfı tek VPS
    backup_and_monitoring_usd: float = 8.0

    # --- Değişken: kullanıcı başına (pahalı model) ---
    generation_model: str = "claude-opus-5"
    drafts_per_user_per_month: int = 60  # ~2/gün
    tokens_in_per_draft: int = 4_000
    tokens_out_per_draft: int = 800
    regeneration_rate: float = 0.35  # taslakların %35'i bir kez yeniden üretiliyor

    briefings_per_user_per_month: int = 60  # sabah + akşam × 30 gün
    tokens_in_per_briefing: int = 2_500
    tokens_out_per_briefing: int = 700

    # --- Senaryolar ---
    # Ürün tek kullanıcılı kişisel bir araç olarak kararlaştırıldı; birinci
    # senaryo gerçek kullanım, diğerleri yalnızca ölçek referansıdır.
    user_scenarios: tuple[int, ...] = (1, 10, 100)

    # --- X API (Spec §9.4 / D7: MVP'de KULLANILMIYOR → 0 $) ---
    # Faz 5 yeniden değerlendirmesi için hesap tablosu; rakamlar X geliştirici
    # portalından TEYİT EDİLMELİDİR (F0-06 açık kalemi).
    # (izlenen hesap sayısı, aylık $ — 0.0 = henüz doğrulanmadı)
    x_api_scenarios: tuple[tuple[int, float], ...] = ((10, 0.0), (50, 0.0), (165, 0.0))

    @classmethod
    def personal(cls) -> Assumptions:
        """Tek kullanıcılı kişisel kullanım profili.

        Sabit maliyetler bölünecek kullanıcı olmadığı için maliyet
        düşürmenin tek yolu sabit tarafı küçültmektir:
          * VPS yerine yerel makine / mevcut sunucu  -> 0 $
          * Ücretli izleme yerine dosya logu + Sentry ücretsiz katmanı -> 0 $
          * Resmî Gazete konu filtresi ile makale hacmi düşer
          * Tek kişi günde 2 değil ~1 taslak üretir
        """
        return cls(
            articles_per_day=120,
            events_per_day=25,
            vps_usd_per_month=0.0,
            backup_and_monitoring_usd=0.0,
            drafts_per_user_per_month=30,
            briefings_per_user_per_month=30,  # yalnızca sabah brifingi
            user_scenarios=(1,),
        )


@dataclass(frozen=True)
class CostBreakdown:
    fixed_extraction: float
    fixed_summarization: float
    fixed_embedding: float
    fixed_infra: float
    variable_drafts: float
    variable_briefings: float

    @property
    def fixed_total(self) -> float:
        return (
            self.fixed_extraction
            + self.fixed_summarization
            + self.fixed_embedding
            + self.fixed_infra
        )

    @property
    def variable_per_user(self) -> float:
        return self.variable_drafts + self.variable_briefings

    def per_user(self, n_users: int) -> float:
        return self.fixed_total / n_users + self.variable_per_user


def compute(a: Assumptions) -> CostBreakdown:
    processed = a.articles_per_day * (1 - a.dedup_rate) * DAYS_PER_MONTH

    # Önbellek: sistem promptunun büyük kısmı her çağrıda tekrar okunur.
    cached_in = int(a.tokens_in_per_article * a.cache_hit_ratio)
    fresh_in = a.tokens_in_per_article - cached_in

    fixed_extraction = processed * estimate_cost_usd(
        a.extraction_model,
        input_tokens=fresh_in,
        cache_read_tokens=cached_in,
        output_tokens=a.tokens_out_per_article,
    )

    events = a.events_per_day * DAYS_PER_MONTH
    fixed_summarization = events * estimate_cost_usd(
        a.extraction_model,
        input_tokens=a.tokens_in_per_event,
        output_tokens=a.tokens_out_per_event,
    )

    fixed_embedding = processed * a.tokens_per_embedding / 1_000_000 * a.embedding_usd_per_million
    fixed_infra = a.vps_usd_per_month + a.backup_and_monitoring_usd

    drafts = a.drafts_per_user_per_month * (1 + a.regeneration_rate)
    variable_drafts = drafts * estimate_cost_usd(
        a.generation_model,
        input_tokens=a.tokens_in_per_draft,
        output_tokens=a.tokens_out_per_draft,
    )

    variable_briefings = a.briefings_per_user_per_month * estimate_cost_usd(
        a.extraction_model,
        input_tokens=a.tokens_in_per_briefing,
        output_tokens=a.tokens_out_per_briefing,
    )

    return CostBreakdown(
        fixed_extraction=fixed_extraction,
        fixed_summarization=fixed_summarization,
        fixed_embedding=fixed_embedding,
        fixed_infra=fixed_infra,
        variable_drafts=variable_drafts,
        variable_briefings=variable_briefings,
    )


def render(a: Assumptions, b: CostBreakdown) -> str:
    lines: list[str] = []
    add = lines.append

    add("PolitikDesk - Maliyet Modeli (F0-06 / F0-07)")
    add("=" * 62)
    add("")
    add("SABIT MALIYETLER (tum kullanicilar arasinda paylasilir, $/ay)")
    add(f"  Iddia cikarimi   ({a.extraction_model:>18}) : {b.fixed_extraction:8.2f}")
    add(f"  Olay ozetleme    ({a.extraction_model:>18}) : {b.fixed_summarization:8.2f}")
    add(
        f"  Embedding        ({a.embedding_usd_per_million:>9.3f} $/M tok) : "
        f"{b.fixed_embedding:8.2f}"
    )
    add(f"  Altyapi (VPS + yedek + izleme)          : {b.fixed_infra:8.2f}")
    add(f"  {'TOPLAM SABIT':<40}: {b.fixed_total:8.2f}")
    add("")
    add("DEGISKEN MALIYETLER (kullanici basina, $/ay)")
    add(f"  Taslak uretimi   ({a.generation_model:>18}) : {b.variable_drafts:8.2f}")
    add(f"  Brifingler       ({a.extraction_model:>18}) : {b.variable_briefings:8.2f}")
    add(f"  {'TOPLAM DEGISKEN':<40}: {b.variable_per_user:8.2f}")
    add("")
    add("KULLANICI BASINA AYLIK MALIYET")
    add(f"  {'Kullanici':>10} | {'$/kullanici/ay':>16} | {'Toplam $/ay':>12} | Hedef <= 8 $")
    add("  " + "-" * 60)
    for n in a.user_scenarios:
        per_user = b.per_user(n)
        total = b.fixed_total + b.variable_per_user * n
        verdict = "GECER" if per_user <= COST_TARGET_PER_USER_USD else "KALIR"
        add(f"  {n:>10} | {per_user:>16.2f} | {total:>12.2f} | {verdict}")
    add("")
    add("X API (Spec §9.4 / D7: MVP'de KULLANILMIYOR -> 0 $)")
    add("  Faz 5 yeniden degerlendirmesi icin rakamlar X gelistirici")
    add("  portalindan teyit edilmelidir. Bkz. docs/veri-maliyet-modeli.md")
    return "\n".join(lines)


def to_csv(a: Assumptions, b: CostBreakdown, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["kalem", "tip", "usd_ay"])
        w.writerow(["iddia_cikarimi", "sabit", round(b.fixed_extraction, 2)])
        w.writerow(["olay_ozetleme", "sabit", round(b.fixed_summarization, 2)])
        w.writerow(["embedding", "sabit", round(b.fixed_embedding, 2)])
        w.writerow(["altyapi", "sabit", round(b.fixed_infra, 2)])
        w.writerow(["taslak_uretimi", "degisken_kullanici_basina", round(b.variable_drafts, 2)])
        w.writerow(["brifingler", "degisken_kullanici_basina", round(b.variable_briefings, 2)])
        w.writerow([])
        w.writerow(["kullanici_sayisi", "usd_kullanici_ay", "usd_toplam_ay"])
        for n in a.user_scenarios:
            w.writerow(
                [n, round(b.per_user(n), 2), round(b.fixed_total + b.variable_per_user * n, 2)]
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="PolitikDesk maliyet modeli")
    parser.add_argument("--csv", type=Path, help="Sonucu CSV olarak da kaydet")
    parser.add_argument(
        "--profile",
        choices=["default", "personal"],
        default="personal",
        help="personal = tek kullanicili kisisel kullanim (varsayilan)",
    )
    args = parser.parse_args()

    assumptions = Assumptions.personal() if args.profile == "personal" else Assumptions()
    breakdown = compute(assumptions)
    print(render(assumptions, breakdown))

    if args.profile == "personal":
        print("")
        print("KARSILASTIRMA - varsayilan profil (VPS + tam hacim):")
        base = compute(Assumptions())
        print(f"  Tek kullanici: {base.per_user(1):.2f} $/ay")
        print(f"  Kisisel profil tasarrufu: {base.per_user(1) - breakdown.per_user(1):.2f} $/ay")

    if args.csv:
        to_csv(assumptions, breakdown, args.csv)
        print(f"\nCSV yazildi: {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
