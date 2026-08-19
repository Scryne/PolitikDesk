"""Söylem değişikliği dedektörünün TEŞHİSİ (ADR-010 §5 · ölçüm adımı).

⛔ HİÇBİR ŞEY YAZILMAZ. Bu betik yalnızca ölçer.

Sorulan soru tek: **hangi kavram çifti kaç kayma üretiyor ve o kavram
gerçekten bir KONU mu, yoksa içeriksiz bir duruş fiili mi?**

Hipotez (koda bakarak kurulan, ölçümle sınanacak):
`POLARITY_PAIRS`'in 4 çiftinden yalnızca birincisi (para politikası:
faiz artırımı -> indirimi) konusal. Diğer üçü — destekliyoruz↔karşıyız,
yasaklanmalı↔serbest olmalı, asla olmaz↔müzakere edilebilir — özneden
bağımsız duruş belirteçleri. "X'i destekliyoruz" ile "Y'ye karşıyız"
X≠Y olsa da eşleşir; kaymanın yanlış çıkmasının sebebi budur.

Kullanım:
    python -m eval.diagnose_stance_shift
"""

from __future__ import annotations

import json
import pathlib
from collections import Counter
from typing import Any

from politikdesk.db import connection
from politikdesk.political_memory.stance_shift import (
    POLARITY_PAIRS,
    _evaluate_text_polarity,
    fold_text,
)

OUT = pathlib.Path(__file__).resolve().parent / "_runs" / "stance_shift_diagnosis.json"

# Kavramlara insan tarafından okunabilir ad ve "konusal mı" yargısı.
# Bu yargı koda değil, kavramın ne ölçtüğüne dayanır.
KAVRAM_ADI = (
    ("para_politikasi", True, "faiz artırımı -> indirimi"),
    ("genel_destek", False, "destekliyoruz -> karşıyız"),
    ("yasak_serbest", False, "yasaklanmalı -> serbest olmalı"),
    ("kesin_ret", False, "asla olmaz -> müzakere edilebilir"),
)


def main() -> int:
    # Kalıcılaşmış kaymaların dayandığı iddia metinlerini yeniden değerlendir.
    with connection() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT id, actor_name, earlier_claim_text, later_claim_text,
                   earlier_event_id, later_event_id, time_span_days, status
              FROM stance_shifts
             WHERE status <> 'superseded'
             ORDER BY id
            """
        )
        kayitlar = [dict(r) for r in cur.fetchall()]

    print(f"TESHIS — {len(kayitlar)} kalicilasmis kayma\n")

    kavram_sayaci: Counter[str] = Counter()
    ayrinti: list[dict[str, Any]] = []

    for k in kayitlar:
        f1 = fold_text(k["earlier_claim_text"] or "")
        f2 = fold_text(k["later_claim_text"] or "")
        eslesenler = []
        for idx, (pos, neg) in enumerate(POLARITY_PAIRS):
            p1 = _evaluate_text_polarity(f1, pos, neg)
            p2 = _evaluate_text_polarity(f2, pos, neg)
            if p1 is not None and p2 is not None and p1 != p2:
                eslesenler.append(idx)

        ad = KAVRAM_ADI[eslesenler[0]][0] if eslesenler else "ESLESME_YOK"
        kavram_sayaci[ad] += 1
        ayrinti.append(
            {
                "id": k["id"],
                "actor_name": k["actor_name"],
                "matched_concepts": eslesenler,
                "primary_concept": ad,
                "time_span_days": k["time_span_days"],
                "earlier": (k["earlier_claim_text"] or "")[:150],
                "later": (k["later_claim_text"] or "")[:150],
            }
        )

    print("KAVRAM DAGILIMI:")
    konusal_toplam = 0
    for ad, konusal, aciklama in KAVRAM_ADI:
        n = kavram_sayaci.get(ad, 0)
        etiket = "KONUSAL" if konusal else "iceriksiz duruş fiili"
        if konusal:
            konusal_toplam += n
        print(f"  {ad:18} {n:>4}  [{etiket}]  {aciklama}")
    yok = kavram_sayaci.get("ESLESME_YOK", 0)
    if yok:
        print(f"  {'ESLESME_YOK':18} {yok:>4}  (metin degismis ya da kutup kaybolmus)")

    toplam = len(kayitlar) or 1
    print(f"\n  konusal kavramdan gelen : {konusal_toplam}/{toplam} "
          f"({konusal_toplam/toplam*100:.1f}%)")
    print(f"  iceriksiz fiilden gelen : {toplam - konusal_toplam - yok}/{toplam} "
          f"({(toplam-konusal_toplam-yok)/toplam*100:.1f}%)")

    # Aynı gün "U dönüşü" iddiaları ayrıca sayılır: bir aktörün saatler
    # içinde politika değiştirmesi olağan değildir.
    ayni_gun = [a for a in ayrinti if (a["time_span_days"] or 0) == 0]
    print(f"  aynı gün icinde 'U donusu': {len(ayni_gun)}/{toplam}")

    print("\nORNEKLER (iceriksiz fiilden gelenler):")
    for a in [x for x in ayrinti if x["primary_concept"] not in ("para_politikasi", "ESLESME_YOK")][:4]:
        print(f"\n  #{a['id']} · {a['actor_name']} · {a['primary_concept']} · {a['time_span_days']} gun")
        print(f"    onceki: {a['earlier'][:110]}")
        print(f"    sonraki: {a['later'][:110]}")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "write_enabled": False,
                "total": len(kayitlar),
                "by_concept": dict(kavram_sayaci),
                "topical_count": konusal_toplam,
                "same_day_count": len(ayni_gun),
                "details": ayrinti,
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
