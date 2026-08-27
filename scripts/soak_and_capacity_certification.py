"""Sustained Soak Test & Resource Capacity Certification (Phase 28 / Phase F & H).

Measures:
1. RSS Memory growth (Initial -> Peak -> Final -> Growth rate).
2. Database connection pool checkin/checkout leak detection.
3. Concurrent API and search throughput under load.
4. Garbage collection and leak verification.
"""

from __future__ import annotations

import ctypes
import gc
import time
import tracemalloc
from ctypes import wintypes

from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.db import get_pool


def get_current_process_rss_mb() -> float:
    """Returns current process Working Set (RSS) in Megabytes via Windows API."""
    try:
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize / (1024.0 * 1024.0)
    except Exception:
        pass
    current, peak = tracemalloc.get_traced_memory()
    return current / (1024.0 * 1024.0)


def run_soak_benchmark(iterations: int = 150) -> dict[str, float]:
    """Runs a sustained workload across all core read/search endpoints and measures memory profile."""
    tracemalloc.start()
    client = TestClient(app)
    gc.collect()

    initial_rss = get_current_process_rss_mb()
    peak_rss = initial_rss
    t0 = time.perf_counter()

    endpoints = [
        "/feed",
        "/war-room",
        "/briefing",
        "/promises",
        "/accountability",
        "/memory",
        "/graph",
        "/archive",
        "/metrics",
        "/health/live",
        "/health/ready",
        "/static/manifest.webmanifest",
    ]

    print(f"[*] Starting Soak Run: {iterations} cycles across {len(endpoints)} endpoints ({iterations * len(endpoints)} requests)...")
    print(f"    Initial RSS Memory: {initial_rss:.2f} MB")

    total_requests = 0
    for i in range(iterations):
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code in (200, 307), f"Endpoint {ep} failed with {resp.status_code}"
            total_requests += 1

        current_rss = get_current_process_rss_mb()
        if current_rss > peak_rss:
            peak_rss = current_rss

        if (i + 1) % 50 == 0:
            print(f"    Cycle {i + 1}/{iterations} completed. Current RSS: {current_rss:.2f} MB | Peak: {peak_rss:.2f} MB")

    t1 = time.perf_counter()
    duration_sec = t1 - t0
    rps = total_requests / duration_sec if duration_sec > 0 else 0.0

    gc.collect()
    final_rss = get_current_process_rss_mb()
    growth_mb = final_rss - initial_rss
    leak_rate_kb_per_req = (growth_mb * 1024.0) / total_requests if total_requests > 0 else 0.0

    # Pool Health
    pool = get_pool()
    pool_stats = pool.get_stats()

    print("\n[*] Soak Test Completed:")
    print(f"    Duration: {duration_sec:.2f}s | Total Requests: {total_requests:,} | Throughput: {rps:.1f} RPS")
    print(f"    Initial RSS: {initial_rss:.2f} MB | Peak RSS: {peak_rss:.2f} MB | Final RSS: {final_rss:.2f} MB")
    print(f"    Net Memory Growth: {growth_mb:+.2f} MB ({leak_rate_kb_per_req:.3f} KB/request)")
    print(f"    Pool Stats: {pool_stats}")

    return {
        "duration_sec": round(duration_sec, 2),
        "total_requests": total_requests,
        "rps": round(rps, 1),
        "initial_rss_mb": round(initial_rss, 2),
        "peak_rss_mb": round(peak_rss, 2),
        "final_rss_mb": round(final_rss, 2),
        "growth_mb": round(growth_mb, 2),
        "leak_rate_kb_per_req": round(leak_rate_kb_per_req, 3),
        "pool_requests_waiting": pool_stats.get("requests_waiting", 0),
    }


if __name__ == "__main__":
    run_soak_benchmark(iterations=250)
