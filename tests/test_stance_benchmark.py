"""Duruş sınıflandırma benchmark araçları testleri (Roadmap Faz 6).

⛔ HİÇBİR TEST AĞA ÇIKMAZ. Sağlayıcı çağrıları sahte fonksiyonlarla
değiştirilir; amaç modeli değil, ARACI ve SÖZLEŞMEYİ sınamaktır.

Korunan sözleşme:
  1. Etiket sözlüğü mevcut domeni bozmaz.
  2. Şema doğrulaması gevşetilmez — etiket dışı çıktı geçersizdir.
  3. Model güven skoru / siyasi hüküm / nedensellik ÜRETEMEZ.
  4. Köken (provider, model, prompt, şema sürümü) her sonuçta bulunur.
  5. Gölge koşum HİÇBİR ŞEY YAZMAZ.
"""

from __future__ import annotations

import ast
import inspect
import json
import pathlib

import pytest

from eval import benchmark_stance as bs
from eval.benchmark_stance import (
    LABELS,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    SYSTEM_PROMPT,
    Outcome,
    RunReport,
    _parse,
    confusion,
    load_gold,
    metrics,
)

GOLD = load_gold()


def _rapor(ciftler: list[tuple[str, str]], *, gecikme: float = 100.0) -> RunReport:
    r = RunReport("test", "test-model", "test-runtime", 1)
    r.outcomes = [
        Outcome(f"g{i}", beklenen, tahmin, tahmin in LABELS, gecikme)
        for i, (beklenen, tahmin) in enumerate(ciftler)
    ]
    return r


# ═══════════════════════════════ 1. şema doğrulama
def test_valid_label_parses() -> None:
    assert _parse('{"stance": "supports"}') == ("supports", True)


def test_label_outside_vocabulary_is_invalid() -> None:
    """Model uydurduğu bir etiketi kabul ettiremez."""
    etiket, gecerli = _parse('{"stance": "kesinlikle_dogru"}')
    assert not gecerli
    assert etiket == "kesinlikle_dogru"


def test_malformed_json_is_invalid_not_crashing() -> None:
    for bozuk in ("", "   ", "{bozuk", "sadece metin", "[]", "null"):
        etiket, gecerli = _parse(bozuk)
        assert not gecerli, bozuk


def test_fenced_json_block_is_tolerated() -> None:
    """Modeller sık sık ```json bloğu sarar; bu bir hata değil biçimdir."""
    assert _parse('```json\n{"stance": "contradicts"}\n```') == ("contradicts", True)


def test_extra_prose_around_json_is_tolerated() -> None:
    ham = 'Düşünüyorum... İşte cevap: {"stance": "partial"} umarım yardımcı olur.'
    assert _parse(ham) == ("partial", True)


def test_case_is_normalised() -> None:
    assert _parse('{"stance": "SUPPORTS"}') == ("supports", True)


# ═══════════════════════════════ 2. etiket sözlüğü domeni bozmaz
def test_label_set_covers_the_database_vocabulary() -> None:
    """DB yalnızca üç etiket tanır; üçü de model sözlüğünde olmalı."""
    import typing

    from politikdesk.evidence.rules import Stance

    db = set(typing.get_args(Stance))
    assert db <= set(LABELS), f"DB sozlugu model sozlugunde yok: {db - set(LABELS)}"


def test_extra_labels_are_explicitly_non_persisting() -> None:
    """`unrelated`/`insufficient_evidence` DB'de YOK ve olmamalı.

    Onlar için `partial` yazmak yanlış olurdu: `partial` "kısmen
    destekliyor" demektir, "ilgisiz" demek değil. Eşleme belgede yazılı.
    """
    import typing

    from politikdesk.evidence.rules import Stance

    db = set(typing.get_args(Stance))
    ekstra = set(LABELS) - db
    assert ekstra == {"unrelated", "insufficient_evidence"}
    assert "KAYIT AÇILMAZ" in (bs.__doc__ or "")


def test_no_new_taxonomy_was_invented() -> None:
    """Domen sözlüğü ölçülmeden yeni taksonomi icat edilmedi."""
    assert set(LABELS) >= {"supports", "contradicts", "partial"}
    assert len(LABELS) == 5


# ═══════════════════════════════ 3. model hüküm veremez
def test_prompt_forbids_truth_judgement() -> None:
    assert "DOĞRU olup olmadığına karar VERME" in SYSTEM_PROMPT


def test_prompt_forbids_confidence_and_causality() -> None:
    assert "güven skoru" in SYSTEM_PROMPT
    assert "sebep" in SYSTEM_PROMPT.lower()


def test_prompt_forbids_world_knowledge() -> None:
    """Kanıtta olmayan bilgi kullanılamaz — halüsinasyon kapısı."""
    assert "Dünya bilgini KULLANMA" in SYSTEM_PROMPT


def test_prompt_states_absence_is_not_contradiction() -> None:
    """Kanıtın olmaması ÇELİŞKİ DEĞİLDİR — yetkinin sert kuralı."""
    assert "olmaması ÇELİŞKİ DEĞİLDİR" in SYSTEM_PROMPT


def test_schema_has_no_confidence_field() -> None:
    """Şema yalnızca `stance` bekler; güven yüzdesi kabul edilmez."""
    etiket, gecerli = _parse('{"stance": "supports", "confidence": 0.93}')
    assert gecerli and etiket == "supports"
    # Fazla alan tolere edilir ama HİÇBİR YERDE kullanılmaz:
    assert "confidence" not in inspect.getsource(bs.metrics)


# ═══════════════════════════════ 4. metrikler
def test_accuracy_and_macro_f1_are_computed() -> None:
    r = _rapor([("supports", "supports"), ("contradicts", "contradicts"),
                ("supports", "contradicts")])
    m = metrics(r)
    assert m["accuracy"] == pytest.approx(2 / 3, abs=0.01)
    assert 0.0 <= m["macro_f1"] <= 1.0


def test_metrics_do_not_crash_on_zero_valid_output() -> None:
    """**Ölçüm aracı, ölçtüğü şey başarısız olduğunda çökmemeli.**

    İlk koşumda uzak sağlayıcı 0 geçerli çıktı döndürdü ve araç
    `StatisticsError` ile düştü.
    """
    r = RunReport("test", "m", "rt", 1)
    r.outcomes = [Outcome("g1", "supports", None, False, 0.0, error="HTTPStatusError")]
    m = metrics(r)
    assert m["macro_f1"] == 0.0
    assert m["accuracy"] == 0.0
    assert m["error_rate"] == 1.0


def test_false_contradiction_rate_counts_only_non_contradiction_gold() -> None:
    """Bu ürün için en tehlikeli hata: var olmayan bir çatışma üretmek."""
    r = _rapor([("supports", "contradicts"), ("supports", "supports"),
                ("contradicts", "contradicts")])
    assert metrics(r)["false_contradiction_rate"] == pytest.approx(0.5)


def test_false_support_rate_counts_only_non_support_gold() -> None:
    r = _rapor([("insufficient_evidence", "supports"), ("unrelated", "unrelated")])
    assert metrics(r)["false_support_rate"] == pytest.approx(0.5)


def test_contradiction_recall_is_reported_separately() -> None:
    """R1 için kritik metrik ayrı raporlanmalı."""
    r = _rapor([("contradicts", "contradicts"), ("contradicts", "supports")])
    assert metrics(r)["contradiction_recall"] == pytest.approx(0.5)


def test_confusion_matrix_rows_are_expected_labels() -> None:
    r = _rapor([("supports", "contradicts")])
    km = confusion(r)
    assert km["supports"]["contradicts"] == 1


def test_latency_percentiles_are_reported() -> None:
    r = _rapor([("supports", "supports")] * 10, gecikme=500.0)
    m = metrics(r)
    for k in ("p50_ms", "p95_ms", "p99_ms", "mean_ms", "cold_ms"):
        assert k in m


# ═══════════════════════════════ 5. köken ve yeniden üretilebilirlik
def test_metrics_carry_full_provenance() -> None:
    m = metrics(_rapor([("supports", "supports")]))
    for alan in ("provider", "model", "runtime", "concurrency",
                 "prompt_version", "schema_version"):
        assert m.get(alan) is not None, alan


def test_prompt_and_schema_versions_are_declared() -> None:
    assert PROMPT_VERSION and SCHEMA_VERSION


def test_temperature_is_zero_for_reproducibility() -> None:
    """Örnekleme açık olsaydı benchmark tekrarlanamazdı."""
    assert bs.TEMPERATURE == 0.0


def test_rate_limit_hits_are_reported_separately_from_latency() -> None:
    """Hız sınırı beklemesi gecikmeye sayılmamalı — ayrı işletim boyutu."""
    kaynak = inspect.getsource(bs.call_remote)
    assert "RATE_LIMIT_HITS" in kaynak
    assert "gecikmeye" in kaynak.lower() or "GECIKMEYE" in kaynak


# ═══════════════════════════════ 6. altın küme
def test_gold_dataset_covers_required_categories() -> None:
    kategoriler = {g["category"] for g in GOLD}
    for gerekli in ("negation", "turkish_morphology", "turkish_abbrev",
                    "numeric_contradiction", "temporal_contradiction",
                    "hallucination_bait", "conditional", "reported_speech",
                    "quotation", "missing_context", "unrelated", "partial"):
        assert gerekli in kategoriler, gerekli


def test_gold_labels_are_within_the_vocabulary() -> None:
    for g in GOLD:
        assert g["expected_label"] in LABELS, g["id"]


def test_gold_items_carry_review_metadata() -> None:
    """Etiketler model üretimi olamaz; kim/ne zaman incelediği yazılı olmalı."""
    for g in GOLD:
        assert g["reviewer"] and g["reviewed_at"] and g["dataset_version"]
        assert g["rationale"], g["id"]


def test_gold_dataset_has_no_political_opinion_as_ground_truth() -> None:
    """Altın etiket METİN İLİŞKİSİ hakkındadır, siyasi görüş değil."""
    for g in GOLD:
        assert g["expected_label"] in LABELS
    # Gerekçeler metin ilişkisine atıf yapmalı, siyasi yargıya değil.
    yasakli = ("haklı", "haksız", "iyi politika", "kötü politika", "yanlış hükümet")
    blob = " ".join(g["rationale"] for g in GOLD).lower()
    assert not [y for y in yasakli if y in blob]


def test_gold_has_both_clear_and_ambiguous_cases() -> None:
    zorluklar = {g["difficulty"] for g in GOLD}
    assert {"kolay", "zor"} <= zorluklar


def test_gold_is_large_enough_to_be_meaningful() -> None:
    assert len(GOLD) >= 30


# ═══════════════════════════════ 7. izolasyon ve güvenlik
def test_benchmark_is_outside_the_application_package() -> None:
    """⛔ Ollama üretim koduna sokulmadan ölçülür (Faz 6.7 şartı)."""
    yol = pathlib.Path(bs.__file__).resolve()
    assert "eval" in yol.parts
    assert "politikdesk" not in yol.parts


def test_application_package_does_not_import_an_ollama_sdk() -> None:
    """Domen katmanı Ollama'ya **bağımlı** olmamalı.

    Dikkat: `:11434` dizesinin üretim kodunda bulunması bir ihlal DEĞİLDİR.
    `llm/client.py` jenerik bir OpenAI-uyumlu istemcidir ve taban adresin
    portuna bakarak sağlayıcıyı yalnızca *maliyet muhasebesi* için
    etiketler. Bağımlılık "Ollama"ya değil, "OpenAI-uyumlu uç nokta"ya
    kuruludur; sağlayıcı yapılandırmayla değişir. İhlal, satıcıya özel bir
    SDK'nın içeri alınmasıdır.
    """
    kok = pathlib.Path(bs.__file__).resolve().parent.parent / "politikdesk"
    suphe: list[str] = []
    for py in kok.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        agac = ast.parse(py.read_text(encoding="utf-8", errors="ignore"), str(py))
        for n in ast.walk(agac):
            adlar: list[str] = []
            if isinstance(n, ast.Import):
                adlar = [x.name for x in n.names]
            elif isinstance(n, ast.ImportFrom):
                adlar = [n.module or ""]
            if any(a.split(".")[0] in {"ollama", "llama_cpp"} for a in adlar):
                suphe.append(py.name)
    assert not suphe, f"Uretim kodunda saticiya ozel SDK: {suphe}"


def test_provider_is_selected_by_configuration_not_hardcoded() -> None:
    """Yerel sağlayıcıya geçmek kod değişikliği değil, ayar değişikliği olmalı."""
    from politikdesk import config

    kaynak = inspect.getsource(config)
    assert "PD_LLM_BASE_URL" in kaynak


def test_shadow_run_declares_write_disabled() -> None:
    """İlk gerçek veri koşumu HİÇBİR ŞEY YAZMAZ (Faz 6 şartı)."""
    from eval import shadow_stance_run as sr

    kaynak = inspect.getsource(sr)
    assert "WRITE = FALSE" in (sr.__doc__ or "")
    assert '"write_enabled": False' in kaynak

    agac = ast.parse(kaynak)
    yazma = [
        n for n in ast.walk(agac)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and any(k in n.value.upper() for k in ("INSERT INTO", "UPDATE ", "DELETE FROM"))
    ]
    assert not yazma, "Golge kosumda yazma SQL'i var"


def test_shadow_run_records_provenance_per_pair() -> None:
    from eval import shadow_stance_run as sr

    kaynak = inspect.getsource(sr.main)
    for alan in ("claim_id", "evidence_id", "provider", "model",
                 "prompt_version", "schema_version"):
        assert f'"{alan}"' in kaynak, alan


# ═══════════════════════════════ 8. mimari kısıt
def test_benchmark_does_not_bypass_the_grounding_gate() -> None:
    """Benchmark METİN ÜRETMEZ — ikinci bir üretim yolu açmaz.

    Yalnızca sınıflandırma yapar; `grounding_check`'in konusu olan
    taslak metni burada üretilmez.
    """
    kaynak = inspect.getsource(bs)
    assert "draft" not in kaynak.lower()
    assert "grounding" not in kaynak.lower() or "grounding_check" not in kaynak


def test_result_files_are_written_outside_the_package() -> None:
    assert "eval" in bs.RESULTS_DIR.parts
    assert "politikdesk" not in bs.RESULTS_DIR.parts


@pytest.mark.parametrize("seviye", [1, 2, 4, 8])
def test_concurrency_is_a_supported_parameter(seviye: int) -> None:
    """Doyum noktası ölçülebilmeli."""
    assert "concurrency" in inspect.signature(bs.run).parameters
    assert seviye > 0


def test_gold_file_is_valid_jsonl() -> None:
    yol = pathlib.Path(bs.GOLD)
    for satir in yol.read_text(encoding="utf-8").splitlines():
        if satir.strip():
            assert isinstance(json.loads(satir), dict)
