"""Kaynak operasyonel kalite skoru testleri (Roadmap Faz 2.1).

Korunan sözleşme — üçü de bu depoda bedeli ödenmiş derslerden:

  1. Skor İÇERİĞE BAKMAZ. "Kaynak kalitesi" adlı bir sayının editoryal
     güvenilirliğe kayması, Spec §8.5'in (kaynağa siyasi konum etiketi
     yasağı) en kolay ihlal biçimidir.
  2. Ölçülemeyen bileşen SIFIR DEĞİL, `None`'dır. "Hiç turu yok" ile
     "hep başarısız" aynı şey değildir.
  3. Bakım sinyali yalnızca DÜZELTİLEBİLİR bileşenlerden gelir. Yapısal
     özellik (Tier 4 olmak) için alarm üretmek, alarmı hep açık bırakır
     ve hep açık alarm hiçbir şey söylemez.
"""

from __future__ import annotations

import ast
import inspect
from typing import Any

import pytest

from politikdesk.ingestion import source_quality as sq
from politikdesk.ingestion.source_quality import (
    OPERATIONAL_KEYS,
    QualityComponent,
    SourceQuality,
    report,
)


def _row(**over: Any) -> dict[str, Any]:
    """Tipik bir `report()` satırı."""
    temel: dict[str, Any] = {
        "slug": "ornek",
        "name": "Örnek Kaynak",
        "tier": 3,
        "adapter": "rss",
        "access_method": "rss",
        "independence_group": "media-ornek",
        "last_success_at": None,
        "group_size": 1,
        "run_count": 100,
        "success_count": 100,
        "items_fetched": 1000,
        "dupes": 100,
        "avg_ms": 250,
        "official_value_count": 0,
    }
    temel.update(over)
    return temel


def _quality(**over: Any) -> SourceQuality:
    row = _row(**over)
    return SourceQuality(
        slug=row["slug"],
        name=row["name"],
        tier=row["tier"],
        adapter=row["adapter"],
        independence_group=row["independence_group"],
        components=[build(row) for build in sq._BUILDERS],  # noqa: SLF001
    )


# ═══════════════════════════════ 1. skor içeriğe bakmaz (Spec §8.5)
def test_scoring_never_reads_article_content() -> None:
    """Hiçbir bileşen makale metnine dokunmamalı.

    Skor bir kez içeriğe bakmaya başlarsa "kaynak kalitesi" sessizce
    "kaynak güvenilirliği"ne dönüşür ve Spec §8.5'in yasakladığı şey
    tam olarak budur.
    """
    kaynak = inspect.getsource(sq)
    for yasak in ("title", "excerpt", "lead_paragraph", "claim_text", "summary"):
        assert f"a.{yasak}" not in kaynak, (
            f"Skor makale alanina bakiyor: {yasak}. Operasyonel skor "
            "icerikten bagimsiz kalmali (Spec §8.5)."
        )


def test_module_declares_that_it_is_not_a_credibility_judgement() -> None:
    """Kısıt kodda YAZILI kalmalı; yoksa bir sonraki geliştirici bilmez."""
    belge = sq.__doc__ or ""
    assert "GÜVENİLİRLİK YARGISI DEĞİLDİR" in belge
    assert "§8.5" in belge


def test_no_political_labels_leak_into_component_names() -> None:
    """Bileşen etiketleri siyasi konum dili taşımamalı."""
    yasakli = ("yanlı", "tarafsız", "muhalif", "iktidar yanlısı", "bias", "ideoloji")
    q = _quality()
    metin = " ".join(f"{c.key} {c.label} {c.detail}" for c in q.components).lower()
    assert not [k for k in yasakli if k in metin], metin


# ═══════════════════════════════ 2. ölçülemeyen ≠ sıfır
def test_no_runs_means_unmeasured_not_zero_reliability() -> None:
    """"Hiç turu yok" ile "hep başarısız" aynı şey değildir.

    Sıfır verilseydi yeni eklenen her kaynak, daha ilk turunu koşmadan
    "güvenilmez" görünürdü.
    """
    q = _quality(run_count=0, success_count=0)
    reli = next(c for c in q.components if c.key == "reliability")
    assert reli.value is None
    assert not reli.measured
    assert "ölçülemedi" in reli.detail


def test_unmeasured_components_are_excluded_from_the_average() -> None:
    tam = _quality()
    eksik = _quality(run_count=0, success_count=0)
    assert tam.coverage == "6/6"
    assert eksik.coverage == "5/6"
    # Ölçülemeyen bileşen 0 sayılsaydı skor düşerdi; dışlandığı için düşmez.
    assert eksik.score is not None
    ortalama_olculen = sum(
        float(c.value or 0) for c in eksik.measured_components
    ) / len(eksik.measured_components)
    assert eksik.score == pytest.approx(round(ortalama_olculen, 1))


def test_series_adapters_are_exempt_from_the_yield_component() -> None:
    """Seri adaptörü aynı gözlemi her turda çeker — bu tasarım gereğidir.

    Ceza verilseydi EVDS ve TÜİK SDMX yapısal olarak düşük skorlu
    görünürdü; oysa ürünün en değerli iki kaynağı onlar.
    """
    for adapter in ("evds", "tuik_sdmx"):
        q = _quality(adapter=adapter, items_fetched=3000, dupes=2999)
        verim = next(c for c in q.components if c.key == "yield")
        assert verim.value is None, adapter
        assert "seri adaptörü" in verim.detail


def test_missing_independence_group_is_unmeasured() -> None:
    q = _quality(independence_group=None)
    bag = next(c for c in q.components if c.key == "independence")
    assert bag.value is None


# ═══════════════════════════════ 3. bileşen davranışları
def test_shared_independence_group_reduces_the_score() -> None:
    """Aynı grupta ikinci kaynak `independent_count`'a katkı yapmaz."""
    tekil = _quality(group_size=1)
    paylasilan = _quality(group_size=2)
    a = next(c for c in tekil.components if c.key == "independence")
    b = next(c for c in paylasilan.components if c.key == "independence")
    assert a.value == 100.0
    assert b.value is not None and b.value < a.value


def test_never_fetched_source_has_zero_freshness_not_none() -> None:
    """Hiç başarılı çekim yoksa tazelik ÖLÇÜLMÜŞTÜR ve sıfırdır.

    `reliability`'den farkı: orada "kaç turun kaçı başarılı" sorusunun
    paydası yok. Burada ise soru "en son ne zaman veri geldi" ve cevap
    kesin: hiç.
    """
    q = _quality(last_success_at=None)
    taze = next(c for c in q.components if c.key == "freshness")
    assert taze.value == 0.0
    assert taze.measured


def test_freshness_budget_follows_the_source_rhythm() -> None:
    """Eşik takvime değil, kaynağın ritmine bağlı.

    Aylık yayımlanan bir gösterge serisi ile günlük haber akışı aynı
    tazelik bütçesine tabi tutulsaydı, seri adaptörleri sürekli bayat
    görünürdü.
    """
    assert sq.FRESHNESS_BUDGET_HOURS["rss"] < sq.FRESHNESS_BUDGET_HOURS["sayistay"]
    assert sq.FRESHNESS_BUDGET_HOURS["twitter"] > sq.FRESHNESS_BUDGET_HOURS["rss"]


def test_official_value_production_raises_authority_and_structuredness() -> None:
    """Kurumun makine okunur sayısını üreten kaynak R3'ü besler (Spec §8.3)."""
    yalin = _quality(tier=1, access_method="api")
    resmi = _quality(tier=1, access_method="api", official_value_count=42)
    for anahtar in ("authority", "structuredness"):
        a = next(c for c in yalin.components if c.key == anahtar)
        b = next(c for c in resmi.components if c.key == anahtar)
        assert b.value is not None and a.value is not None and b.value > a.value, anahtar


# ═══════════════════════════════ 4. bakım sinyali yapısal özellik için yanmaz
def test_attention_signal_ignores_structural_properties() -> None:
    """Tier 4 olmak bir arıza değildir.

    İlk uygulamada bakım listesi 24 kaynağın hepsini `authority`
    yüzünden işaretliyordu — yani sosyal kaynakları SOSYAL OLDUKLARI
    İÇİN. Hep açık bir alarm hiçbir şey söylemez; bu deponun tekrar
    eden dersi (`pipeline_health.py` iddia aşaması, `conftest.py` DB
    testleri, `.gitattributes` satır sonu) tam olarak budur.
    """
    assert set(OPERATIONAL_KEYS) == {"freshness", "reliability", "yield"}
    assert "authority" not in OPERATIONAL_KEYS
    assert "independence" not in OPERATIONAL_KEYS
    assert "structuredness" not in OPERATIONAL_KEYS


def test_attention_entries_carry_their_reason() -> None:
    """"Şu kaynak kötü" değil, "şu bileşeni şu değerde" denebilmeli."""
    imza = inspect.signature(sq.needs_attention)
    assert "threshold" in imza.parameters
    kaynak = inspect.getsource(sq.needs_attention)
    assert "sebepler" in kaynak, "Sebep dondurulmuyor; sinyal eyleme donusmez."


# ═══════════════════════════════ 5. mimari kısıt
def test_source_quality_does_not_import_llm() -> None:
    """⛔ Operasyonel skor deterministiktir; LLM'e ihtiyacı yoktur.

    Denetim AST üzerinden: yasağı anlatan docstring, yasağın ihlali
    değildir (`tests/test_design_tokens.py` ile aynı gerekçe).
    """
    agac = ast.parse(inspect.getsource(sq))
    moduller: set[str] = set()
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            moduller |= {a.name for a in dugum.names}
        elif isinstance(dugum, ast.ImportFrom) and dugum.module:
            moduller.add(dugum.module)
    assert not {m for m in moduller if m.startswith("politikdesk.llm")}


# ═══════════════════════════════ 6. canlı veri (db)
@pytest.mark.db
def test_report_runs_against_the_live_schema() -> None:
    """Sorgu gerçek şemayla uyumlu olmalı — sütun adı kayması yakalanır."""
    satirlar = report(window_days=7)
    assert satirlar, "Aktif kaynak yok; sorgu veya veri bozulmus olabilir."
    for q in satirlar:
        assert q.slug
        assert len(q.components) == 6
        assert q.score is None or 0.0 <= q.score <= 100.0


@pytest.mark.db
def test_report_is_sorted_with_unscored_sources_last() -> None:
    satirlar = report(window_days=7)
    skorlar = [q.score for q in satirlar]
    olculen = [s for s in skorlar if s is not None]
    assert olculen == sorted(olculen, reverse=True)
    ilk_none = next((i for i, s in enumerate(skorlar) if s is None), len(skorlar))
    assert all(s is None for s in skorlar[ilk_none:])


def test_component_dataclass_reports_measured_correctly() -> None:
    assert QualityComponent("k", "L", None, "d").measured is False
    assert QualityComponent("k", "L", 0.0, "d").measured is True
