"""Test Concurrency and Worker Safety under parallel extraction."""

import concurrent.futures
from unittest.mock import MagicMock

from politikdesk.nlp import claims_pipeline
from politikdesk.nlp.claims import ExtractedClaim


def test_concurrent_worker_persist_idempotency() -> None:
    """Aynı olay için 5 eşzamanlı worker çalıştığında mükerrer iddia veya kanıt oluşmamalıdır."""
    event_id = 99999
    claim1 = ExtractedClaim("Test eşzamanlı iddia 1", "fact", "", None)
    claim2 = ExtractedClaim("Test eşzamanlı iddia 2", "fact", "", None)
    claims_with_sources = [
        (claim1, [(1001, "metin 1"), (1002, "metin 2")]),
        (claim2, [(1001, "metin 1")]),
    ]

    def worker_run(i: int) -> int:
        mock_cur = MagicMock()
        mock_cur.rowcount = 1
        mock_cur.fetchall.return_value = []
        mock_cur.fetchone.side_effect = [{"id": 501}, {"id": 502}]
        return claims_pipeline._persist(mock_cur, event_id, claims_with_sources, f"test-model+v{i}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker_run, i) for i in range(5)]
        results = [f.result() for f in futures]

    assert all(r == 3 for r in results)
