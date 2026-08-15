"""Golden Set doğrulayıcı ve etiketleme yardımcısı (F0-14, F1-20, F2-20).

Golden Set, Spec §13.1'in tanımladığı altın test setidir. Kalite kapıları
(§13.2) bu sete karşı ölçülür; set bozuksa ölçüm de bozuktur — bu yüzden
doğrulayıcı CI'da koşar.

Satır biçimi (eval/golden_set_v1.jsonl):
    {
      "article_id": "gs-0001",
      "source_slug": "tuik",
      "url": "https://...",
      "title": "...",
      "published_at": "2026-06-03T10:00:00Z",
      "event_id": "evt-tufe-2026-05",
      "topic": "enflasyon",
      "difficulty": "easy" | "hard",
      "notes": ""
    }

İddia seti (eval/golden_claims_v1.jsonl):
    {
      "claim_id": "gc-0001",
      "event_id": "evt-tufe-2026-05",
      "claim_text": "Mayıs ayı TÜFE aylık %X arttı.",
      "claim_type": "number",
      "expected_status": "strongly_corroborated",
      "expected_rule": "R3",
      "normalized_value": {"metric": "tufe_monthly", "value": 0.0,
                           "unit": "%", "period": "2026-05"},
      "notes": "kural elle uygulanarak belirlendi"
    }

Kullanım:
    python -m eval.golden_set_tools validate
    python -m eval.golden_set_tools stats
    python -m eval.golden_set_tools template > eval/golden_set_v1.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTICLES_PATH = REPO_ROOT / "eval" / "golden_set_v1.jsonl"
CLAIMS_PATH = REPO_ROOT / "eval" / "golden_claims_v1.jsonl"

# Spec §13.1 hedefleri ve faz kilometre taşları
TARGETS = {
    "F0-14": 100,  # Faz 0 çıkışı (G0 koşul 6: setin %33'ü)
    "F1-20": 200,  # Faz 1 çıkışı
    "F2-20": 300,  # Faz 2 çıkışı — tam set
}
CLAIMS_TARGET = 150

VALID_STATUSES = {
    "strongly_corroborated",
    "partially_corroborated",
    "single_source",
    "contradicted",
    "unverified",
}
VALID_CLAIM_TYPES = {"fact", "number", "attribution", "prediction"}
# Spec §8.3 (v3.1): R0 tip kısıtı (kanıttan önce, kısa devre) + R1-R6 kanıt
# kuralları + R7 tavan kısıtı. Toplam 8 kural; eski R8'in yerini R0 aldı.
VALID_RULES = {"R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"}

# Spec §5 — MVP dikeyinin 10 konusu
VALID_TOPICS = {
    "enflasyon",
    "politika_faizi",
    "kur_ve_rezervler",
    "butce_ve_hazine",
    "issizlik_ve_istihdam",
    "buyume",
    "asgari_ucret_ve_zamlar",
    "vergi_ve_harclar",
    "kamu_borclanmasi",
    "derecelendirme",
}

REQUIRED_ARTICLE_FIELDS = ("article_id", "source_slug", "title", "event_id", "topic")
REQUIRED_CLAIM_FIELDS = ("claim_id", "event_id", "claim_text", "claim_type", "expected_status")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path.name}:{lineno}: gecersiz JSON - {exc}") from exc
    return rows


def validate_articles(rows: list[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    seen_ids: set[str] = set()
    # Toplu kontroller yalnızca iyi biçimli satırlar üzerinde çalışır;
    # aksi halde eksik alanlı bir satır KeyError'a yol açar.
    well_formed: list[dict[str, Any]] = []

    for i, row in enumerate(rows, 1):
        missing = [f for f in REQUIRED_ARTICLE_FIELDS if not row.get(f)]
        if missing:
            problems.append(f"satir {i}: eksik alan(lar) {missing}")
            continue
        well_formed.append(row)

        if row["article_id"] in seen_ids:
            problems.append(f"satir {i}: yinelenen article_id {row['article_id']!r}")
        seen_ids.add(row["article_id"])

        if row["topic"] not in VALID_TOPICS:
            problems.append(
                f"satir {i}: '{row['topic']}' MVP konu listesinde yok "
                "(bkz. docs/mvp-konu-kapsami.md)"
            )
        if row.get("difficulty") not in (None, "easy", "hard"):
            problems.append(f"satir {i}: difficulty 'easy' veya 'hard' olmali")

    # Spec §13.1: set "zor kume" icermeli (yakin ama farkli olay)
    hard_events = {r["event_id"] for r in well_formed if r.get("difficulty") == "hard"}
    if well_formed and len(hard_events) < 5:
        problems.append(f"En az 5 'zor' kume gerekli (F0-14 DoD), {len(hard_events)} var.")

    # Tek makalelik olaylar kumeleme olcumune katki vermez
    counts = Counter(r["event_id"] for r in well_formed)
    singletons = [e for e, c in counts.items() if c == 1]
    if well_formed and len(singletons) > len(counts) * 0.5:
        problems.append(
            f"Olaylarin %50'sinden fazlasi tek makaleli ({len(singletons)}/{len(counts)}); "
            "kumeleme precision/recall olcumu anlamsizlasir."
        )
    return problems


def validate_claims(rows: list[dict[str, Any]], event_ids: set[str]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()

    for i, row in enumerate(rows, 1):
        missing = [f for f in REQUIRED_CLAIM_FIELDS if not row.get(f)]
        if missing:
            problems.append(f"iddia satir {i}: eksik alan(lar) {missing}")
            continue

        if row["claim_id"] in seen:
            problems.append(f"iddia satir {i}: yinelenen claim_id")
        seen.add(row["claim_id"])

        if row["claim_type"] not in VALID_CLAIM_TYPES:
            problems.append(f"iddia satir {i}: gecersiz claim_type {row['claim_type']!r}")
        if row["expected_status"] not in VALID_STATUSES:
            problems.append(f"iddia satir {i}: gecersiz expected_status {row['expected_status']!r}")
        if row.get("expected_rule") and row["expected_rule"] not in VALID_RULES:
            problems.append(f"iddia satir {i}: gecersiz expected_rule")

        # Spec §8.3 R0: tahmin her zaman unverified (tip kisiti, kanittan once)
        if row["claim_type"] == "prediction" and row["expected_status"] != "unverified":
            problems.append(
                f"iddia satir {i}: R0 ihlali - 'prediction' tipi iddia "
                "her zaman 'unverified' olmali."
            )
        # R0 kisa devre yapar: bir tahmin baska bir kuralla etiketlenemez.
        if (
            row["claim_type"] == "prediction"
            and row.get("expected_rule")
            and row["expected_rule"] != "R0"
        ):
            problems.append(
                f"iddia satir {i}: R0 kisa devre ihlali - 'prediction' tipi iddiada "
                f"beklenen kural {row['expected_rule']!r} olamaz, R0 olmali "
                "(Spec §8.3: tip kisiti kanit kurallarindan once calisir)."
            )
        # Sayisal iddialarin normalize degeri olmali (F2-08 olcumu buna dayanir)
        if row["claim_type"] == "number" and not row.get("normalized_value"):
            problems.append(f"iddia satir {i}: 'number' tipi iddiada normalized_value yok")

        if event_ids and row["event_id"] not in event_ids:
            problems.append(f"iddia satir {i}: event_id {row['event_id']!r} makale setinde yok")
    return problems


def cmd_validate() -> int:
    articles = load_jsonl(ARTICLES_PATH)
    claims = load_jsonl(CLAIMS_PATH)

    problems = validate_articles(articles)
    problems += validate_claims(claims, {r.get("event_id", "") for r in articles})

    if problems:
        print(f"[HATA] Golden Set {len(problems)} sorun iceriyor:", file=sys.stderr)
        for p in problems[:50]:
            print(f"  - {p}", file=sys.stderr)
        if len(problems) > 50:
            print(f"  ... ve {len(problems) - 50} sorun daha", file=sys.stderr)
        return 1

    print(f"[OK] Golden Set gecerli: {len(articles)} makale, {len(claims)} iddia.")
    return 0


def cmd_stats() -> int:
    articles = load_jsonl(ARTICLES_PATH)
    claims = load_jsonl(CLAIMS_PATH)

    print("Golden Set durumu")
    print("=" * 52)
    print(f"  Makale : {len(articles)}")
    print(f"  Olay   : {len({r.get('event_id') for r in articles})}")
    print(f"  Iddia  : {len(claims)}")
    print("")
    print("  Faz kilometre taslari (makale):")
    for task, target in TARGETS.items():
        pct = (len(articles) / target * 100) if target else 0
        mark = "[x]" if len(articles) >= target else "[ ]"
        print(f"    {mark} {task}: {len(articles)}/{target}  ({pct:.0f}%)")
    mark = "[x]" if len(claims) >= CLAIMS_TARGET else "[ ]"
    print(f"    {mark} F2-20 iddia: {len(claims)}/{CLAIMS_TARGET}")

    if articles:
        print("\n  Konu dagilimi:")
        for topic, count in Counter(r.get("topic") for r in articles).most_common():
            covered = "" if topic in VALID_TOPICS else "  <- MVP listesinde yok!"
            print(f"    {str(topic):<26} {count:>4}{covered}")

        missing_topics = VALID_TOPICS - {r.get("topic") for r in articles}
        if missing_topics:
            print(f"\n  Hic ornegi olmayan konular: {sorted(missing_topics)}")

        print("\n  Zorluk dagilimi:")
        for diff, count in Counter(r.get("difficulty", "easy") for r in articles).most_common():
            print(f"    {diff:<26} {count:>4}")
    return 0


TEMPLATE = """\
// Golden Set v1 - makale etiketleri (F0-14)
// Her satir bir makale. event_id ELLE atanir: ayni gercek-dunya gelismesini
// anlatan makaleler ayni event_id'yi paylasir.
// Kaldirmadan once bkz. eval/golden_set_tools.py dosya basi aciklamasi.
{"article_id": "gs-0001", "source_slug": "tuik", "url": "https://ORNEK", \
"title": "ORNEK BASLIK", "published_at": "2026-06-03T10:00:00Z", \
"event_id": "evt-tufe-2026-05", "topic": "enflasyon", "difficulty": "easy", "notes": ""}
"""


def cmd_template() -> int:
    print(TEMPLATE)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Golden Set araclari")
    parser.add_argument("command", choices=["validate", "stats", "template"])
    args = parser.parse_args()

    return {
        "validate": cmd_validate,
        "stats": cmd_stats,
        "template": cmd_template,
    }[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
