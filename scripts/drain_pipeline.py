"""Boru Hattı Boşaltma ve Hızlı İyileştirme Aracı (Pipeline Drain CLI).

Boru hattındaki tüm adımları sıralı ve bağımlılıklarına uygun olarak
kuyruklar sıfırlanana kadar çalıştırır:
  1. Embedding
  2. Varlık Çıkarımı (NER)
  3. Olay Kümeleme (Clustering)
  4. İddia Çıkarımı (Claims - LLM)
  5. Kanıt Puanlaması (Evidence)
  6. Tarihsel Bağlam (Context)
  7. Siyasi İlişkiler (Political Relations)
  8. Takvim Eşleştirmesi (Scheduled Events)

Kullanım:
    python -m scripts.drain_pipeline
    python -m scripts.drain_pipeline --skip-llm
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from politikdesk.config import load_env_file

# Windows konsol UTF-8 desteği
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _drain_stage(
    name: str,
    fn: Any,
    batch_size: int = 100,
    max_batches: int = 50,
    extract_count_fn: Any = None,
) -> int:
    """Tek bir aşamayı kuyruk bitene kadar döngüde çalıştırır."""
    print(f"[*] {name:<26} ", end="", flush=True)
    total = 0
    batches = 0
    t0 = time.perf_counter()

    while batches < max_batches:
        batches += 1
        try:
            res = fn(batch_size) if batch_size else fn()
        except Exception as e:  # noqa: BLE001
            print(f"HATA: {e}")
            return total

        if extract_count_fn:
            count = extract_count_fn(res)
        elif isinstance(res, int):
            count = res
        elif isinstance(res, dict):
            count = res.get("processed") or res.get("events_processed") or res.get("stored", 0)
        else:
            count = 0

        total += count
        if count == 0 or (batch_size and count < batch_size):
            break

    elapsed = time.perf_counter() - t0
    print(f"[OK] {total:5} öğe işlendi ({elapsed:.2f} sn, {batches} tur)")
    return total


def drain_all(*, skip_llm: bool = False, max_llm_events: int = 100) -> dict[str, int]:
    """Tüm boru hattını sırayla boşaltır."""
    load_env_file()

    print("=" * 65)
    print("POLITIKDESK - BORU HATTI BOŞALTMA VE SENKRONİZASYON")
    print("=" * 65)

    stats: dict[str, int] = {}

    # 1. Embedding
    from politikdesk.nlp import repository as nlp_repo
    from politikdesk.nlp.embedder import build_backend, embedding_text

    def _embed_batch(limit: int = 100) -> int:
        rows = nlp_repo.pending_embedding(limit)
        if not rows:
            return 0
        backend = build_backend()
        texts = [embedding_text(r["title"], r["excerpt"]) for r in rows]
        vectors = backend.embed(texts)
        return nlp_repo.save_embeddings(
            {row["id"]: vector for row, vector in zip(rows, vectors, strict=True)}
        )

    stats["embedded"] = _drain_stage("1. Embedding", _embed_batch, batch_size=100)

    # 2. Varlık Çıkarımı
    from politikdesk.nlp import entities as ner

    def _entities_batch(limit: int = 100) -> int:
        rows = nlp_repo.pending_entities(limit)
        if not rows:
            return 0
        processed = []
        for row in rows:
            try:
                found = ner.extract(row["title"], row["excerpt"])
                entity_ids = [
                    nlp_repo.upsert_entity(
                        e,
                        aliases=ner.INSTITUTIONS.get(e.canonical_name, ())
                        if e.entity_type == "institution"
                        else (),
                    )
                    for e in found
                ]
                nlp_repo.link_article_entities(row["id"], entity_ids)
                processed.append(row["id"])
            except Exception:  # noqa: BLE001
                pass
        nlp_repo.mark_entities_extracted(processed)
        return len(processed)

    stats["entities"] = _drain_stage("2. Varlık Çıkarımı (NER)", _entities_batch, batch_size=100)

    # 3. Kümeleme
    from politikdesk.clustering.pipeline import run as cluster_run

    stats["clustered"] = _drain_stage(
        "3. Olay Kümeleme",
        cluster_run,
        batch_size=100,
        extract_count_fn=lambda r: r.processed,
    )

    # 4. İddia Çıkarımı (LLM)
    if not skip_llm:
        from politikdesk.nlp.claims_pipeline import run as claims_run

        stats["claims"] = _drain_stage(
            "4. İddia Çıkarımı (LLM)",
            claims_run,
            batch_size=10,
            max_batches=max_llm_events // 10 if max_llm_events else 20,
            extract_count_fn=lambda r: r.events_processed,
        )
    else:
        print("[*] 4. İddia Çıkarımı (LLM)    [ATLANDI] (--skip-llm bayrağı)")
        stats["claims"] = 0

    # 5. Kanıt Puanlama
    from politikdesk.evidence.pipeline import run as evidence_run

    stats["evidence"] = _drain_stage(
        "5. Kanıt Puanlaması",
        evidence_run,
        batch_size=200,
        extract_count_fn=lambda r: r.claims_scored,
    )

    # 6. Tarihsel Bağlam
    from politikdesk.context.related import run as context_run

    stats["context"] = _drain_stage(
        "6. Tarihsel Bağlam",
        context_run,
        batch_size=100,
        extract_count_fn=lambda r: r.get("events_processed", 0),
    )

    # 7. Siyasi İlişkiler
    from politikdesk.political_memory.orchestrator import (
        process_pending_political_relations as pol_run,
    )

    stats["political_relations"] = _drain_stage(
        "7. Siyasi İlişkiler",
        pol_run,
        batch_size=100,
        extract_count_fn=lambda r: r.get("events_processed", 0),
    )

    # 8. Takvim Eşleştirme
    from politikdesk.context.scheduler_match import match_pending

    stats["scheduler_match"] = _drain_stage(
        "8. Takvim Eşleştirmesi",
        lambda _b=0: match_pending(),
        batch_size=0,
        extract_count_fn=lambda r: r.get("matched", 0),
    )

    # Sağlık Raporu
    print("\n" + "=" * 65)
    print("AŞAMA SAĞLIK DURUMU:")
    print("=" * 65)
    from politikdesk import pipeline_health as ph

    stages = ph.stage_report()
    all_green = True
    for s in stages:
        status_icon = "🟢" if s.status == "green" else ("🟡" if s.status == "amber" else "🔴")
        if s.status == "red":
            all_green = False
        oldest_str = f"{s.oldest_hours:.1f} sa" if s.oldest_hours is not None else "-"
        print(f" {status_icon} {s.label:<22} Bekleyen: {s.backlog:4} | En Eski: {oldest_str:>7}")

    print("=" * 65)
    if all_green:
        print("[SONUÇ] Boru hattı tümüyle sağlıklı ve akıyor.")
    else:
        print("[UYARI] Bazı aşamalarda hala birikme var; yukarıdaki detayları inceleyin.")

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="PolitikDesk boru hattı boşaltma aracı")
    parser.add_argument("--skip-llm", action="store_true", help="LLM iddia çıkarımını atla")
    parser.add_argument(
        "--max-llm-events", type=int, default=100, help="Azami LLM iddia çıkarımı olay sayısı"
    )
    args = parser.parse_args()

    drain_all(skip_llm=args.skip_llm, max_llm_events=args.max_llm_events)
    return 0


if __name__ == "__main__":
    sys.exit(main())
