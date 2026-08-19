"""Faz 6.3-6.8 — duruş sınıflandırma karşılaştırması (yerel vs uzak).

⛔ BU BİR BENCHMARK ARACIDIR, ÜRETİM KODU DEĞİLDİR.

Ollama üretim koduna sokulmadan ölçülür (Faz 6.7 şartı). Bu dosya
`politikdesk/` paketinin dışındadır ve uygulama katmanı buradan hiçbir
şey import etmez.

GÖREV TANIMI (Faz 6.1)
----------------------
Girdi : bir iddia metni + bir kanıt metni
Çıktı : {"stance": <etiket>}  — yapılandırılmış, şema doğrulamalı

ETİKET SÖZLÜĞÜ — MEVCUT DOMEN KORUNUR

Veritabanı kısıtı yalnızca üç etiket tanır:

    CHECK (stance IN ('supports', 'contradicts', 'partial'))

Model dört etiket üretir; dördüncüsü kalıcılaştırma için DEĞİL, yanlış
pozitifi önlemek içindir:

    supports              -> DB 'supports'
    contradicts           -> DB 'contradicts'
    partial               -> DB 'partial'
    unrelated             -> KAYIT AÇILMAZ (kanıt bağı kurulmaz)
    insufficient_evidence -> KAYIT AÇILMAZ

`unrelated`/`insufficient_evidence` için `partial` yazmak YANLIŞ olurdu:
`partial` "kısmen destekliyor" demektir, "ilgisiz" demek değil. Yeni
etiket icat etmek yerine, o çiftler için hiç bağ kurulmaz — şema
değişmez, sözlük korunur.

⛔ MODEL ŞUNLARI ÜRETMEZ: doğruluk skoru, güven yüzdesi, siyasi hüküm,
nedensellik. Şema bu alanları KABUL ETMEZ.

Kullanım:
    python -m eval.benchmark_stance --provider ollama
    python -m eval.benchmark_stance --provider remote
    python -m eval.benchmark_stance --provider ollama --concurrency 4
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import httpx

GOLD = pathlib.Path(__file__).resolve().parent / "golden_stance_v1.jsonl"
RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "_runs"

PROMPT_VERSION = "stance.v1"
SCHEMA_VERSION = "stance.schema.v1"

LABELS = ("supports", "contradicts", "partial", "unrelated", "insufficient_evidence")

# Sıcaklık 0: aynı girdi aynı çıktıyı vermeli (Faz 6 yeniden üretilebilirlik
# şartı). Örnekleme açık bırakılsaydı benchmark tekrarlanamazdı.
TEMPERATURE = 0.0

# Uzak saglayicida kac kez HTTP 429 alindi (isletim boyutu).
RATE_LIMIT_HITS: list[int] = []

SYSTEM_PROMPT = """Sen bir metin ilişkisi sınıflandırıcısısın.

Sana bir İDDİA ve bir KANIT metni verilir. Görevin YALNIZCA şudur:
verilen KANIT metni, verilen İDDİA'yı destekliyor mu, çürütüyor mu,
kısmen mi destekliyor, ilgisiz mi, yoksa iddiayı kurmaya yetmiyor mu?

KURALLAR:
1. SADECE verilen kanıt metnine bak. Dünya bilgini KULLANMA.
2. Kanıt metninde iddiaya dair bilgi yoksa "insufficient_evidence" de.
3. Kanıt tamamen başka bir konudaysa "unrelated" de.
4. Kanıtın olmaması ÇELİŞKİ DEĞİLDİR.
5. Koşullu ifade ("olabilir", "yaklaşırsa") kesin eylem bildirmez.
6. Soru cümlesi bir iddia değildir.
7. İddianın DOĞRU olup olmadığına karar VERME. Sadece metin ilişkisini söyle.
8. Siyasi yorum, güven skoru veya sebep AÇIKLAMA.

Etiketler: supports, contradicts, partial, unrelated, insufficient_evidence

Yanıtın SADECE şu JSON olsun: {"stance": "<etiket>"}"""

USER_TEMPLATE = """İDDİA:
{claim}

KANIT:
{evidence}

JSON:"""


@dataclass
class Outcome:
    gold_id: str
    expected: str
    predicted: str | None
    valid_schema: bool
    latency_ms: float
    error: str | None = None
    raw: str = ""


@dataclass
class RunReport:
    provider: str
    model: str
    runtime: str
    concurrency: int
    outcomes: list[Outcome] = field(default_factory=list)
    cold_ms: float = 0.0

    @property
    def valid(self) -> list[Outcome]:
        return [o for o in self.outcomes if o.valid_schema and o.predicted]


# ---------------------------------------------------------------------------
# Sağlayıcılar — benchmark için, üretim için değil
# ---------------------------------------------------------------------------
def _parse(raw: str) -> tuple[str | None, bool]:
    """Modelin çıktısını şemaya göre doğrular.

    Şema dışı alan (güven, açıklama, sebep) YOK SAYILMAZ — varlığı
    geçersizlik sayılmaz ama etiket dışı bir değer geçersizdir.
    """
    metin = (raw or "").strip()
    if metin.startswith("```"):
        metin = metin.strip("`").lstrip("json").strip()
    basla, bitir = metin.find("{"), metin.rfind("}")
    if basla == -1 or bitir == -1:
        return None, False
    try:
        veri = json.loads(metin[basla : bitir + 1])
    except json.JSONDecodeError:
        return None, False
    if not isinstance(veri, dict):
        return None, False
    etiket = str(veri.get("stance", "")).strip().lower()
    return (etiket, True) if etiket in LABELS else (etiket or None, False)


def call_ollama(claim: str, evidence: str, model: str, timeout: float) -> tuple[str, float]:
    t0 = time.perf_counter()
    r = httpx.post(
        "http://127.0.0.1:11434/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(claim=claim, evidence=evidence)},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": TEMPERATURE, "num_predict": 40},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["message"]["content"], (time.perf_counter() - t0) * 1000


def call_remote(claim: str, evidence: str, model: str, timeout: float) -> tuple[str, float]:
    """Uzak sağlayıcı — mevcut yapılandırmadan okunur, yeni bağımlılık yok."""
    import os

    from politikdesk.config import get_settings, load_env_file

    load_env_file()
    s = get_settings()
    base = (s.llm_generation_base_url or s.llm_base_url or "").rstrip("/")
    key_env = s.llm_generation_api_key_env or s.llm_api_key_env or ""
    key = os.environ.get(key_env, "") if key_env else ""
    if not base:
        raise RuntimeError("Uzak saglayici yapilandirilmamis (PD_LLM_*_BASE_URL yok)")

    govde = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(claim=claim, evidence=evidence)},
        ],
        "temperature": TEMPERATURE,
        # 40 degil 600: uzak saglayicida yapilandirilmis model bir AKIL
        # YURUTME modeli (nemotron) ve dusunce zincirini `content` icinde
        # uretiyor. 40 token onu cumlenin ortasinda kesiyordu ve JSON hic
        # gelmiyordu — bu bir model kusuru degil, benim olcum hatamdi.
        "max_tokens": 600,
    }

    # HTTP 429 YENIDEN DENENIR ve bekleme suresi GECIKMEYE SAYILMAZ.
    #
    # Olculdu (19 Agu 2026): ucretsiz NVIDIA NIM katmani hiz siniri
    # uyguluyor ve 35 istegi arka arkaya gonderince 429 doner. Uretim
    # telemetrisindeki %7 hata orani (585 LLMHTTPError / 8380) da bunun
    # ayni belirtisi.
    #
    # Bekleme suresi gecikmeye eklenseydi uzak model haksiz yere yavas
    # gorunurdu; hiz siniri ayri bir isletim boyutudur ve raporda ayri
    # gosterilir.
    son: Exception | None = None
    for deneme in range(5):
        t0 = time.perf_counter()
        try:
            r = httpx.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}"} if key else {},
                json=govde,
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            son = exc
            time.sleep(2.0 * (deneme + 1))
            continue
        if r.status_code == 429:
            RATE_LIMIT_HITS.append(1)
            time.sleep(5.0 * (deneme + 1))
            continue
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"], (time.perf_counter() - t0) * 1000

    raise son or RuntimeError("HTTP 429 — hiz siniri, 5 denemede asilamadi")


PROVIDERS = {"ollama": call_ollama, "remote": call_remote}


# ---------------------------------------------------------------------------
# Koşum
# ---------------------------------------------------------------------------
def load_gold() -> list[dict[str, Any]]:
    return [json.loads(satir) for satir in GOLD.read_text(encoding="utf-8").splitlines() if satir]


def run(provider: str, model: str, *, concurrency: int = 1,
        timeout: float = 120.0, limit: int | None = None) -> RunReport:
    gold = load_gold()[: limit or None]
    fn = PROVIDERS[provider]
    rapor = RunReport(provider=provider, model=model,
                      runtime="ollama-local" if provider == "ollama" else "remote-http",
                      concurrency=concurrency)

    # Soğuk çağrı ayrı ölçülür: model yükleme maliyeti sıcak gecikmeye
    # karışırsa p50 anlamsız çıkar.
    try:
        _, rapor.cold_ms = fn(gold[0]["claim_text"], gold[0]["evidence_text"], model, timeout)
    except Exception as exc:  # noqa: BLE001
        print(f"  [soguk cagri basarisiz] {type(exc).__name__}: {str(exc)[:90]}")

    def bir(g: dict[str, Any]) -> Outcome:
        try:
            ham, ms = fn(g["claim_text"], g["evidence_text"], model, timeout)
        except Exception as exc:  # noqa: BLE001
            return Outcome(g["id"], g["expected_label"], None, False, 0.0,
                           error=type(exc).__name__)
        tahmin, gecerli = _parse(ham)
        return Outcome(g["id"], g["expected_label"], tahmin, gecerli, ms, raw=ham[:120])

    if concurrency <= 1:
        rapor.outcomes = [bir(g) for g in gold]
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            rapor.outcomes = list(ex.map(bir, gold))
    return rapor


# ---------------------------------------------------------------------------
# Metrikler
# ---------------------------------------------------------------------------
def metrics(rapor: RunReport) -> dict[str, Any]:
    gecerli = rapor.valid
    dogru = [o for o in gecerli if o.predicted == o.expected]

    # Sınıf bazlı precision/recall
    per: dict[str, dict[str, float]] = {}
    for etiket in LABELS:
        tp = sum(1 for o in gecerli if o.predicted == etiket and o.expected == etiket)
        fp = sum(1 for o in gecerli if o.predicted == etiket and o.expected != etiket)
        fn_ = sum(1 for o in gecerli if o.predicted != etiket and o.expected == etiket)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn_) if tp + fn_ else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        per[etiket] = {"precision": round(p, 3), "recall": round(r, 3),
                       "f1": round(f1, 3), "support": tp + fn_}

    gecikmeler = [o.latency_ms for o in rapor.outcomes if o.latency_ms > 0]
    sirali = sorted(gecikmeler)

    def yuzdelik(p: float) -> float:
        if not sirali:
            return 0.0
        return round(sirali[min(int(len(sirali) * p), len(sirali) - 1)], 1)

    # Yanlış çelişki oranı: ÇELİŞKİ OLMAYAN bir çifte 'contradicts' demek.
    # Bu ürün için en tehlikeli hata türü — var olmayan bir çatışma üretir.
    celiski_olmayan = [o for o in gecerli if o.expected != "contradicts"]
    yanlis_celiski = sum(1 for o in celiski_olmayan if o.predicted == "contradicts")
    destek_olmayan = [o for o in gecerli if o.expected != "supports"]
    yanlis_destek = sum(1 for o in destek_olmayan if o.predicted == "supports")

    return {
        "provider": rapor.provider,
        "model": rapor.model,
        "runtime": rapor.runtime,
        "concurrency": rapor.concurrency,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "n": len(rapor.outcomes),
        "valid_output": len(gecerli),
        "invalid_output_rate": round(1 - len(gecerli) / max(len(rapor.outcomes), 1), 3),
        "error_rate": round(
            sum(1 for o in rapor.outcomes if o.error) / max(len(rapor.outcomes), 1), 3
        ),
        "accuracy": round(len(dogru) / max(len(gecerli), 1), 3),
        # Bos kume ortalamasi COKMEZ: gecerli cikti yoksa macro F1 0'dir.
        # Ilk kosumda uzak saglayici 0 gecerli cikti dondurdu ve arac
        # StatisticsError ile dustu — olcum araci, olctugu sey basarisiz
        # oldugunda cokmemeli.
        "macro_f1": round(
            statistics.mean(destekli) if (destekli := [
                per[e]["f1"] for e in LABELS if per[e]["support"]
            ]) else 0.0,
            3,
        ),
        "contradiction_recall": per["contradicts"]["recall"],
        "false_contradiction_rate": round(
            yanlis_celiski / max(len(celiski_olmayan), 1), 3
        ),
        "false_support_rate": round(yanlis_destek / max(len(destek_olmayan), 1), 3),
        "per_class": per,
        "cold_ms": round(rapor.cold_ms, 1),
        "p50_ms": yuzdelik(0.50),
        "p95_ms": yuzdelik(0.95),
        "p99_ms": yuzdelik(0.99),
        "mean_ms": round(statistics.mean(gecikmeler), 1) if gecikmeler else 0.0,
        "rate_limit_hits": len(RATE_LIMIT_HITS),
    }


def confusion(rapor: RunReport) -> dict[str, dict[str, int]]:
    m: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(LABELS, 0))
    for o in rapor.valid:
        if o.predicted in LABELS:
            m[o.expected][o.predicted] += 1
    return {k: dict(v) for k, v in m.items()}


def by_category(rapor: RunReport, gold: list[dict[str, Any]]) -> dict[str, str]:
    kat = {g["id"]: g["category"] for g in gold}
    toplam: Counter[str] = Counter()
    dogru: Counter[str] = Counter()
    for o in rapor.valid:
        k = kat.get(o.gold_id, "?")
        toplam[k] += 1
        if o.predicted == o.expected:
            dogru[k] += 1
    return {k: f"{dogru[k]}/{toplam[k]}" for k in sorted(toplam)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=list(PROVIDERS), default="ollama")
    ap.add_argument("--model", default="")
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    model = a.model or (
        "qwen2.5:7b-instruct-q5_K_M" if a.provider == "ollama"
        else "nvidia/nemotron-3-super-120b-a12b"
    )

    print(f"[{a.provider}] {model} · es zamanlilik={a.concurrency} · prompt={PROMPT_VERSION}")
    rapor = run(a.provider, model, concurrency=a.concurrency,
                timeout=a.timeout, limit=a.limit or None)
    m = metrics(rapor)

    print(f"\n  n={m['n']} gecerli={m['valid_output']} "
          f"gecersiz_oran={m['invalid_output_rate']} hata_oran={m['error_rate']}")
    print(f"  dogruluk={m['accuracy']} macro_f1={m['macro_f1']}")
    print(f"  CELISKI recall={m['contradiction_recall']} "
          f"yanlis_celiski={m['false_contradiction_rate']} "
          f"yanlis_destek={m['false_support_rate']}")
    print(f"  soguk={m['cold_ms']}ms p50={m['p50_ms']}ms "
          f"p95={m['p95_ms']}ms ort={m['mean_ms']}ms")
    print(f"  hiz siniri (HTTP 429) isabeti: {m['rate_limit_hits']}")
    print("\n  sinif bazli:")
    for e in LABELS:
        c = m["per_class"][e]
        if c["support"]:
            print(f"    {e:24} P={c['precision']:.2f} R={c['recall']:.2f} "
                  f"F1={c['f1']:.2f} (n={c['support']})")

    print("\n  karisiklik matrisi (satir=beklenen):")
    km = confusion(rapor)
    print(f"    {'':24} " + " ".join(f"{e[:6]:>7}" for e in LABELS))
    for beklenen in LABELS:
        satir = km.get(beklenen, dict.fromkeys(LABELS, 0))
        print(f"    {beklenen:24} " + " ".join(f"{satir.get(e,0):>7}" for e in LABELS))

    print("\n  kategori bazli dogruluk:")
    for k, v in by_category(rapor, load_gold()).items():
        print(f"    {k:26} {v}")

    RESULTS_DIR.mkdir(exist_ok=True)
    yol = RESULTS_DIR / f"stance_{a.provider}_{a.concurrency}.json"
    yol.write_text(
        json.dumps(
            {"metrics": m, "confusion": confusion(rapor),
             "outcomes": [
                 {"id": o.gold_id, "expected": o.expected, "predicted": o.predicted,
                  "valid": o.valid_schema, "ms": round(o.latency_ms, 1),
                  "error": o.error, "raw": o.raw}
                 for o in rapor.outcomes
             ]},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n  ayrinti -> {yol}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
