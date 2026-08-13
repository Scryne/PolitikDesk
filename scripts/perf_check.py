"""Performans ölçümü (F4-08).

DoD: Feed p95 < 800 ms · olay sayfası p95 < 1,5 sn · N+1 sorgu yok.

    python -m scripts.perf_check
    python -m scripts.perf_check --runs 50

**Neden p95, ortalama değil:** ortalama, ara sıra 4 saniye süren bir
sayfayı gizler. Kullanıcı ortalamayı yaşamaz, kuyruğu yaşar.

**Neden ilk atış atılıyor:** ilk istek bağlantı havuzunu kurar ve sorgu
planlarını ısıtır. Onu ölçüme katmak "soğuk başlatma" maliyetini kalıcı
bir yavaşlık gibi gösterir; atmak da gerçek bir maliyeti gizler — bu
yüzden ayrıca *raporlanır*, sadece p95'e katılmaz.

**N+1 denetimi** `pg_stat_statements` yerine daha basit ve daha kesin
bir yolla yapılır: sayfa yüklenirken veritabanının saydığı sorgu
sayısına bakılır (`pg_stat_database.xact_commit` farkı yerine
`pg_stat_statements` varsa çağrı sayısı). Uzantı yoksa denetim atlanır
ve bu AÇIKÇA söylenir — sessizce "geçti" demez.
"""

from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://localhost:8000"
DB_CONTAINER = "pd-db"

# F4-08 hedefleri (Yol Haritası).
TARGETS_MS: dict[str, float] = {
    "feed": 800,
    "event": 1500,
    "briefing": 1500,
    "admin": 1500,
    "metrics": 1500,
}


def _get(path: str) -> tuple[int, float]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=30) as response:  # noqa: S310
            response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except Exception:  # noqa: BLE001
        status = 0
    return status, (time.perf_counter() - started) * 1000


def _percentile(values: list[float], pct: float) -> float:
    """Doğrusal interpolasyonlu yüzdelik.

    `statistics.quantiles` küçük örneklemde (n<20) hata verir; ölçüm
    aracının kendisi örneklem boyutuna göre kırılmamalı.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * pct
    low, high = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (k - low)


def _sample_event_id() -> int | None:
    result = subprocess.run(  # noqa: S603
        ["docker", "exec", DB_CONTAINER, "psql", "-U", "politikdesk",  # noqa: S607
         "-d", "politikdesk", "-t", "-A", "-c",
         "SELECT id FROM events WHERE merged_into_id IS NULL "
         "ORDER BY article_count DESC, salience_score DESC NULLS LAST LIMIT 1"],
        capture_output=True,
        check=False,
    )
    raw = result.stdout.decode(errors="replace").strip()
    return int(raw) if raw.isdigit() else None


def _sample_briefing_date() -> str | None:
    result = subprocess.run(  # noqa: S603
        ["docker", "exec", DB_CONTAINER, "psql", "-U", "politikdesk",  # noqa: S607
         "-d", "politikdesk", "-t", "-A", "-c",
         "SELECT briefing_date FROM briefings ORDER BY briefing_date DESC LIMIT 1"],
        capture_output=True,
        check=False,
    )
    raw = result.stdout.decode(errors="replace").strip()
    return raw or None


def measure(path: str, runs: int) -> dict[str, float | int | str]:
    cold_status, cold_ms = _get(path)  # ısınma — p95'e katılmaz
    samples: list[float] = []
    statuses: set[int] = {cold_status}

    for _ in range(runs):
        status, ms = _get(path)
        statuses.add(status)
        samples.append(ms)

    return {
        "path": path,
        "runs": runs,
        "statuses": ",".join(str(s) for s in sorted(statuses)),
        "cold_ms": round(cold_ms, 1),
        "min_ms": round(min(samples), 1),
        "median_ms": round(statistics.median(samples), 1),
        "p95_ms": round(_percentile(samples, 0.95), 1),
        "max_ms": round(max(samples), 1),
    }


# N+1'in imzası, çok sayıda sorgu DEĞİL — **aynı sorgunun tekrar tekrar**
# koşmasıdır. İlk ölçümde toplam sayı bakılıyordu ve 16 çıkıyordu; bunun
# 10'u BEGIN/COMMIT'ti ve kalan 5 sorgunun her biri tam bir kez koşmuştu.
# Toplamı saymak, temiz bir sayfayı şüpheli gösteriyordu.
#
# Eşik 3: aynı yüklem bir sayfa yüklenişinde üç kereden fazla koşuyorsa,
# büyük olasılıkla bir döngünün içindedir.
_N_PLUS_ONE_REPEAT_LIMIT = 3

_STATEMENT_SQL = """
SELECT calls, left(regexp_replace(query, '\\s+', ' ', 'g'), 70) AS q
FROM pg_stat_statements
WHERE query NOT ILIKE '%pg_stat_statements%'
  AND query NOT IN ('BEGIN', 'COMMIT', 'ROLLBACK')
ORDER BY calls DESC LIMIT 1
"""


def _psql(sql: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["docker", "exec", DB_CONTAINER, "psql", "-U", "politikdesk",  # noqa: S607
         "-d", "politikdesk", "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True,
        check=False,
    )
    return result.stdout.decode(errors="replace").strip()


def check_n_plus_one(path: str) -> str:
    """Bir sayfa yüklenişinde aynı sorgu kaç kez koşuyor?

    `pg_stat_statements` yoksa denetim yapılamaz ve bu AÇIKÇA söylenir —
    sessizce "temiz" demek, denetimi olmayan bir yeşil ışıktır.
    """
    probe = _psql("SELECT 1 FROM pg_extension WHERE extname='pg_stat_statements'")
    if probe != "1":
        return "ATLANDI (pg_stat_statements kurulu değil — docker-compose db command)"

    _psql("SELECT pg_stat_statements_reset()")
    _get(path)
    top = _psql(_STATEMENT_SQL)

    if not top or "|" not in top:
        return "sorgu görülmedi"

    calls_raw, _, query = top.partition("|")
    calls = int(calls_raw) if calls_raw.isdigit() else 0
    total = _psql(
        "SELECT COALESCE(SUM(calls),0) FROM pg_stat_statements "
        "WHERE query NOT ILIKE '%pg_stat_statements%' "
        "AND query NOT IN ('BEGIN','COMMIT','ROLLBACK')"
    )

    if calls > _N_PLUS_ONE_REPEAT_LIMIT:
        return (f"{total} sorgu, en sık tekrarlanan {calls}x — N+1 ŞÜPHESİ: "
                f"{query.strip()[:60]}")
    return f"{total} sorgu, hiçbiri {calls}x'ten fazla tekrarlamıyor — TEMİZ"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.perf_check", description=__doc__)
    parser.add_argument("--runs", type=int, default=30,
                        help="Sayfa başına ölçüm sayısı (varsayılan 30)")
    args = parser.parse_args(argv)

    event_id = _sample_event_id()
    briefing_date = _sample_briefing_date()

    targets: list[tuple[str, str]] = [("feed", "/feed"), ("admin", "/admin/")]
    if event_id:
        targets.append(("event", f"/event/{event_id}"))
    if briefing_date:
        targets.append(("briefing", f"/briefing/{briefing_date}"))
    targets.append(("metrics", "/admin/metrics"))

    print(f"PolitikDesk performans ölçümü — sayfa başına {args.runs} istek\n")
    header = (
        f"{'sayfa':<10} {'p95':>9} {'hedef':>8} {'medyan':>9} "
        f"{'min':>8} {'max':>9} {'soğuk':>9}  durum"
    )
    print(header)
    print("-" * len(header))

    failures: list[str] = []
    for name, path in targets:
        row = measure(path, args.runs)
        target = TARGETS_MS.get(name, 1500)
        ok = float(row["p95_ms"]) < target and row["statuses"] == "200"
        if not ok:
            failures.append(f"{name} ({path}): p95 {row['p95_ms']} ms / hedef {target} ms"
                            f" · HTTP {row['statuses']}")
        print(
            f"{name:<10} {row['p95_ms']:>7} ms {target:>6.0f}ms "
            f"{row['median_ms']:>7} ms {row['min_ms']:>6} ms {row['max_ms']:>7} ms "
            f"{row['cold_ms']:>7} ms  {'OK' if ok else 'HEDEF ASILDI'}"
        )

    print("\nN+1 denetimi:")
    for name, path in targets:
        print(f"  {name:<10} {check_n_plus_one(path)}")

    if failures:
        print("\n[HATA] F4-08 hedefleri tutmuyor:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\n[OK] Tüm sayfalar F4-08 hedeflerinin altında.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
