"""Mevcut iddialara imza yazar ve mükerrerleri BİRLEŞTİRİR (F5-18).

Migration 0006 sütunu ve tekil indeksi kurar ama satırları doldurmaz:
imza hesabı `nlp/claims.py::claim_signature` içindedir ve SQL'de yeniden
yazılması yasaktır (tek doğruluk kaynağı — 0006 başlığındaki gerekçe).

Bu betik iki iş yapar ve sırası önemlidir:

  1. Aynı olayda aynı imzaya sahip satırları TEKE İNDİRİR. Hayatta kalan
     en küçük kimliktir; diğerlerinin KANIT BAĞLARI hayatta kalana
     taşınır, sonra kendileri silinir.
  2. Kalan her satıra imzasını yazar.

**Bağlar neden taşınır, silinmez:** mükerrerliğin zararı zaten bağların
bölünmesiydi. Üç bağımsız kaynak aynı şeyi söylediğinde bağlar 2+1
dağılırsa `independent_count` hiçbir satırda 3'e ulaşmaz. Birleştirme
bağları toplamazsa arıza düzelmez, yalnızca gizlenir.

Yıkıcı olduğu için `--yes` ister ve her birleştirmeyi `audit_log`'a
yazar: bir iddianın neden kaybolduğu sorulabilir olmalıdır.

Kullanım:
    python -m scripts.backfill_claim_signatures            # kuru koşum
    python -m scripts.backfill_claim_signatures --yes      # uygula
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from politikdesk.db import connection
from politikdesk.nlp.claims import ExtractedClaim, claim_signature
from politikdesk.observability import get_logger

log = get_logger(__name__)


def _signature_of(row: dict) -> str:
    return claim_signature(
        ExtractedClaim(
            claim_text=row["claim_text"],
            claim_type=row["claim_type"],
            quote_span="",
            normalized_value=row["normalized_value"],
        )
    )


def run(*, apply: bool) -> dict[str, int]:
    stats = {"claims": 0, "duplicate_groups": 0, "merged_away": 0, "links_moved": 0}

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, event_id, claim_text, claim_type, normalized_value "
            "FROM claims ORDER BY id"
        )
        rows = [dict(r) for r in cur.fetchall()]
        stats["claims"] = len(rows)

        groups: dict[tuple[int, str], list[int]] = defaultdict(list)
        for row in rows:
            groups[(row["event_id"], _signature_of(row))].append(row["id"])

        for (event_id, signature), ids in groups.items():
            if len(ids) > 1:
                stats["duplicate_groups"] += 1
                survivor, *losers = sorted(ids)
                stats["merged_away"] += len(losers)

                if apply:
                    # Bağları taşı. Hayatta kalan aynı makaleye zaten
                    # bağlıysa çakışma olur; o bağ zaten var demektir.
                    cur.execute(
                        """
                        UPDATE evidence SET claim_id = %s
                        WHERE claim_id = ANY(%s)
                          AND article_id NOT IN (
                                SELECT article_id FROM evidence WHERE claim_id = %s
                          )
                        """,
                        (survivor, losers, survivor),
                    )
                    stats["links_moved"] += cur.rowcount

                    cur.execute(
                        """
                        INSERT INTO audit_log (actor, action, target, payload)
                        VALUES ('system:backfill', 'claims_deduplicated', %s, %s::jsonb)
                        """,
                        (
                            f"events/{event_id}",
                            json.dumps(
                                {
                                    "survivor": survivor,
                                    "merged_away": losers,
                                    "signature": signature,
                                },
                                ensure_ascii=False,
                            ),
                        ),
                    )
                    # Kalan bağlar (hayatta kalanda zaten olan makaleler)
                    # CASCADE ile gider.
                    cur.execute("DELETE FROM claims WHERE id = ANY(%s)", (losers,))

            if apply:
                cur.execute(
                    "UPDATE claims SET claim_signature = %s WHERE id = %s",
                    (signature, sorted(ids)[0]),
                )

        if apply:
            conn.commit()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="Değişiklikleri uygula")
    args = parser.parse_args()

    stats = run(apply=args.yes)

    mode = "UYGULANDI" if args.yes else "KURU KOŞUM (--yes ile uygulanır)"
    print(f"[{mode}]")
    print(f"  iddia                 : {stats['claims']}")
    print(f"  mukerrer grup         : {stats['duplicate_groups']}")
    print(f"  birlestirilip silinen : {stats['merged_away']}")
    print(f"  tasinan kanit bagi    : {stats['links_moved']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
