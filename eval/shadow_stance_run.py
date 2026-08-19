"""Faz 6 — gerçek veri üzerinde GÖLGE koşum. WRITE = FALSE.

⛔ HİÇBİR ŞEY VERİTABANINA YAZILMAZ.

Faz 6 yetkisi ilk gerçek veri koşumu için bunu şart koşuyor ve gerekçesi
açık: model çıktısı elle incelenmeden `evidence.stance` üzerine yazmak,
Faz 5'te ölü olduğu tespit edilen çelişki yolunu **güvenilmez** bir
kuralla doldurmak olurdu. Ölü kuraldan kötü olan tek şey, yanlış çalışan
kuraldır.

Bu betik yalnızca ölçer ve raporlar.

Kullanım:
    python -m eval.shadow_stance_run --limit 60
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time
from collections import Counter
from typing import Any

from eval.benchmark_stance import (
    PROMPT_VERSION,
    PROVIDERS,
    SCHEMA_VERSION,
    _parse,
)

OUT = pathlib.Path(__file__).resolve().parent / "_runs" / "shadow_stance.json"

# Örneklem: iddia + onu KAYNAKLAYAN makale. Bu çiftlerin çoğu yapı gereği
# `supports` olmalı — model bunu bulamıyorsa sorun modeldedir.
# Beklenmedik `contradicts` çıktısı ise ELLE incelenecek asıl sinyaldir.
SAMPLE_SQL = """
    SELECT cl.id AS claim_id, cl.claim_text, cl.evidence_status,
           ev.id AS evidence_id, ev.stance AS current_stance,
           a.id AS article_id, a.title, a.excerpt, s.slug
      FROM claims cl
      JOIN evidence ev ON ev.claim_id = cl.id
      JOIN articles a  ON a.id = ev.article_id
      JOIN sources s   ON s.id = a.source_id
     WHERE cl.claim_text IS NOT NULL AND a.excerpt IS NOT NULL
     ORDER BY cl.id DESC
     LIMIT %s
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=list(PROVIDERS), default="ollama")
    ap.add_argument("--model", default="qwen2.5:7b-instruct-q5_K_M")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--timeout", type=float, default=120.0)
    a = ap.parse_args()

    from politikdesk.db import connection

    with connection() as c, c.cursor() as cur:
        cur.execute(SAMPLE_SQL, (a.limit,))
        ciftler = [dict(r) for r in cur.fetchall()]

    print(f"GOLGE KOSUM — WRITE=FALSE · {len(ciftler)} cift · {a.provider}/{a.model}")

    fn = PROVIDERS[a.provider]
    sonuclar: list[dict[str, Any]] = []
    t0 = time.perf_counter()

    for i, cift in enumerate(ciftler, 1):
        kanit = f"{cift['title']} {cift['excerpt'] or ''}".strip()
        try:
            ham, ms = fn(cift["claim_text"], kanit, a.model, a.timeout)
            tahmin, gecerli = _parse(ham)
            hata = None
        except Exception as exc:  # noqa: BLE001
            tahmin, gecerli, ms, hata = None, False, 0.0, type(exc).__name__

        sonuclar.append(
            {
                # Köken: bir kararın sonradan açıklanabilmesi için gereken her şey
                "claim_id": cift["claim_id"],
                "evidence_id": cift["evidence_id"],
                "article_id": cift["article_id"],
                "source_slug": cift["slug"],
                "current_stance": cift["current_stance"],
                "predicted_stance": tahmin,
                "valid_schema": gecerli,
                "latency_ms": round(ms, 1),
                "error": hata,
                "provider": a.provider,
                "model": a.model,
                "prompt_version": PROMPT_VERSION,
                "schema_version": SCHEMA_VERSION,
                "claim_text": cift["claim_text"][:160],
                "evidence_text": kanit[:200],
            }
        )
        if i % 20 == 0:
            print(f"  {i}/{len(ciftler)}…")

    sure = time.perf_counter() - t0
    gecerliler = [s for s in sonuclar if s["valid_schema"]]
    dagilim = Counter(s["predicted_stance"] for s in gecerliler)

    # ANLAŞMAZLIK: mevcut kayıt 'supports' diyor, model başka bir şey diyor.
    # Bu, elle incelenmesi gereken kümedir.
    anlasmazlik = [
        s for s in gecerliler
        if s["current_stance"] == "supports" and s["predicted_stance"] != "supports"
    ]

    print(f"\n  sure          : {sure:.1f} sn ({len(ciftler)/sure:.2f} cift/sn)")
    print(f"  gecerli cikti : {len(gecerliler)}/{len(sonuclar)}")
    print(f"  dagilim       : {dict(dagilim)}")
    print(f"  ANLASMAZLIK   : {len(anlasmazlik)}/{len(gecerliler)} "
          f"({len(anlasmazlik)/max(len(gecerliler),1)*100:.1f}%)")

    celiski = [s for s in gecerliler if s["predicted_stance"] == "contradicts"]
    print(f"  'contradicts' : {len(celiski)}  <- ELLE INCELENECEK")
    for s in celiski[:5]:
        print(f"\n    iddia #{s['claim_id']} ({s['source_slug']})")
        print(f"      iddia : {s['claim_text'][:92]}")
        print(f"      kanit : {s['evidence_text'][:92]}")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "write_enabled": False,
                "provider": a.provider,
                "model": a.model,
                "prompt_version": PROMPT_VERSION,
                "schema_version": SCHEMA_VERSION,
                "pairs": len(sonuclar),
                "valid": len(gecerliler),
                "distribution": dict(dagilim),
                "disagreement_count": len(anlasmazlik),
                "duration_s": round(sure, 1),
                "results": sonuclar,
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
