"""Söylem kaymasi kapılarının DETERMİNİSTİK değerlendirmesi (ADR-010 §5).

⛔ HİÇBİR ŞEY YAZILMAZ. LLM KULLANILMAZ. Aynı girdi → aynı çıktı.

Ölçülen: üç kapının (atıf sağlamlığı, konu örtüşmesi, zaman) her biri
kaç adayı eliyor ve geriye ne kalıyor. Amaç bir "iyileştirme yüzdesi"
duyurmak değil; **kalan kümenin elle incelenebilecek kadar küçük ve
gerekçeli** olduğunu göstermek.

Kullanım:
    python -m eval.evaluate_stance_gates
"""

from __future__ import annotations

import json
import pathlib
from collections import Counter
from typing import Any

from politikdesk.political_memory.service import get_actor_memory
from politikdesk.political_memory.stance_shift import (
    MIN_DAYS_FOR_REVERSAL,
    MIN_TOPIC_OVERLAP,
    POLARITY_PAIRS,
    _calc_days_between,
    _evaluate_text_polarity,
    _topic_overlap,
    detect_stance_shifts_from_memory,
    fold_text,
)

OUT = pathlib.Path(__file__).resolve().parent / "_runs" / "stance_gate_eval.json"


def _actors(limit: int) -> list[str]:
    from politikdesk.db import connection

    with connection() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT speaker, count(*) AS n
              FROM claims WHERE speaker IS NOT NULL
             GROUP BY 1 HAVING count(*) >= 2
             ORDER BY 2 DESC LIMIT %s
            """,
            (limit,),
        )
        return [r["speaker"] for r in cur.fetchall()]


def main(limit: int = 40) -> int:
    aktorler = _actors(limit)
    print(f"KAPI DEGERLENDIRMESI — {len(aktorler)} aktor "
          f"(esik: ortusme>={MIN_TOPIC_OVERLAP}, sure>={MIN_DAYS_FOR_REVERSAL}g)\n")

    sayac: Counter[str] = Counter()
    kalanlar: list[dict[str, Any]] = []

    for aktor in aktorler:
        mem = get_actor_memory(aktor)
        kayitlar = mem.promises + mem.attributions + mem.facts_and_numbers
        kayitlar.sort(key=lambda e: e.first_reported_at or "")

        guclu = [e for e in kayitlar if e.attribution_strength == "strong"]
        sayac["kayit_toplam"] += len(kayitlar)
        sayac["kayit_guclu"] += len(guclu)

        # Kutupları önden hesapla (dedektörle aynı yordam).
        kutuplar = [
            tuple(
                _evaluate_text_polarity(fold_text(e.claim_text), p, n)
                for p, n in POLARITY_PAIRS
            )
            for e in guclu
        ]

        for i in range(len(guclu)):
            for j in range(i + 1, len(guclu)):
                e1, e2 = guclu[i], guclu[j]
                if e1.event_id == e2.event_id:
                    continue
                # Kutup zıtlığı var mı? Yoksa bu bir aday bile değil.
                if not any(
                    a is not None and b is not None and a != b
                    for a, b in zip(kutuplar[i], kutuplar[j], strict=True)
                ):
                    continue

                sayac["aday"] += 1
                ortak = _topic_overlap(e1.topic_tags, e2.topic_tags)
                gun = _calc_days_between(e1.first_reported_at, e2.first_reported_at)

                if ortak < MIN_TOPIC_OVERLAP:
                    sayac["elenen_konu"] += 1
                    continue
                if gun < MIN_DAYS_FOR_REVERSAL:
                    sayac["elenen_sure"] += 1
                    continue
                sayac["gecen"] += 1

        for s in detect_stance_shifts_from_memory(mem):
            if s.shift_type == "reversal":
                kalanlar.append(
                    {
                        "actor": s.actor_name,
                        "concept": s.topic_or_metric,
                        "confidence": s.confidence,
                        "days": s.time_span_days,
                        "shared_topics": (s.metadata or {}).get("shared_topics"),
                        "earlier": s.earlier_claim_text[:130],
                        "later": s.later_claim_text[:130],
                    }
                )

    aday = sayac["aday"] or 1
    print(f"  hafiza kaydi          : {sayac['kayit_toplam']}")
    print(f"  atifi SAGLAM olan     : {sayac['kayit_guclu']} "
          f"({sayac['kayit_guclu']/max(sayac['kayit_toplam'],1)*100:.1f}%)")
    print(f"\n  kutup zitligi olan aday: {sayac['aday']}")
    print(f"    konu kapisinda elenen: {sayac['elenen_konu']} "
          f"({sayac['elenen_konu']/aday*100:.1f}%)")
    print(f"    sure kapisinda elenen: {sayac['elenen_sure']} "
          f"({sayac['elenen_sure']/aday*100:.1f}%)")
    print(f"    UCUNU DE GECEN       : {sayac['gecen']} "
          f"({sayac['gecen']/aday*100:.1f}%)")

    print(f"\n  dedektor ciktisi (reversal): {len(kalanlar)}")
    if kalanlar:
        guvenler = sorted({k["confidence"] for k in kalanlar})
        print(f"  farkli guven degeri: {len(guvenler)} -> {guvenler[:6]}")
        print(f"  kavram dagilimi: {dict(Counter(k['concept'] for k in kalanlar))}")
        print("\n  KALAN KAYMALAR (elle incelenecek):")
        for k in kalanlar[:10]:
            print(f"\n   {k['actor']} · {k['concept']} · guven={k['confidence']} "
                  f"· {k['days']} gun · konu={k['shared_topics']}")
            print(f"     onceki : {k['earlier'][:112]}")
            print(f"     sonraki: {k['later'][:112]}")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "write_enabled": False,
                "actors": len(aktorler),
                "thresholds": {
                    "min_topic_overlap": MIN_TOPIC_OVERLAP,
                    "min_days": MIN_DAYS_FOR_REVERSAL,
                },
                "counters": dict(sayac),
                "surviving": kalanlar,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n  -> {OUT}  (HICBIR SEY YAZILMADI)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
