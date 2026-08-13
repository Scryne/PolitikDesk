"""Dışarıdan sağlık nöbeti (F4-05, F4-10).

`pipeline_health` boru hattının içine bakar ama **konteynerin içinden**
koşar. Docker Desktop kapalıysa beat de kapalıdır ve o alarm hiç ötmez:
kendi ölümünü bildiremeyen bir alarm, alarm değildir.

Bu betik ana makinede, Windows Görev Zamanlayıcı ile 6 saatte bir koşar
ve dışarıdan üç soruyu sorar:

    1. Beklenen konteynerler ayakta mı?
    2. API yanıt veriyor mu?
    3. Boru hattının bir aşamasında birikme var mı?

Çıktı hem konsola hem `backups/health.log`'a yazılır. Çıkış kodu 0 =
sağlıklı, 1 = sorun var (Görev Zamanlayıcı "son sonuç" sütununda görünür).

    python -m scripts.watchdog
    python -m scripts.watchdog --quiet     # yalnızca sorun varsa yaz
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

EXPECTED_CONTAINERS = ("pd-db", "pd-redis", "pd-api", "pd-worker", "pd-beat")
API_URL = "http://localhost:8000/health/live"
LOG_PATH = Path("backups") / "health.log"
HTTP_TIMEOUT = 10


def _container_states() -> dict[str, str]:
    """Konteyner adı -> durum. Docker yoksa boş sözlük."""
    try:
        result = subprocess.run(  # noqa: S603
            ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.State}}"],  # noqa: S607
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}

    states: dict[str, str] = {}
    for line in result.stdout.decode(errors="replace").splitlines():
        if "\t" in line:
            name, _, state = line.partition("\t")
            states[name.strip()] = state.strip()
    return states


def check_containers() -> list[str]:
    states = _container_states()
    if not states:
        return ["Docker'a ulaşılamadı — Docker Desktop çalışıyor mu?"]

    problems: list[str] = []
    for name in EXPECTED_CONTAINERS:
        state = states.get(name)
        if state is None:
            problems.append(f"{name}: konteyner yok (make up / make workers)")
        elif state != "running":
            problems.append(f"{name}: {state}")
    return problems


def check_api() -> list[str]:
    try:
        with urllib.request.urlopen(API_URL, timeout=HTTP_TIMEOUT) as response:  # noqa: S310
            if response.status != 200:
                return [f"API {API_URL} -> HTTP {response.status}"]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return [f"API yanıt vermiyor ({type(exc).__name__}): {API_URL}"]
    return []


def check_pipeline() -> list[str]:
    """Aşama sağlığını API üzerinden sorar.

    Doğrudan veritabanına bağlanmak yerine API kullanılır: nöbetçinin
    ana makinede psycopg ve doğru DSN'e sahip olmasını gerektirmez, ve
    API'nin *kendisinin* veritabanını görebildiğini de kanıtlar.
    """
    try:
        with urllib.request.urlopen(  # noqa: S310
            "http://localhost:8000/admin/pipeline-health", timeout=HTTP_TIMEOUT
        ) as response:
            stages = json.loads(response.read())
    except Exception as exc:  # noqa: BLE001
        return [f"Aşama sağlığı okunamadı ({type(exc).__name__})"]

    return [
        f"{s['label']}: {s['backlog']} bekliyor, en eskisi {s['oldest_hours']} sa "
        f"(eşik {s['threshold_hours']} sa) — {s['hint']}"
        for s in stages
        if s["status"] == "red"
    ]


def run(quiet: bool = False) -> int:
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    problems: list[str] = []

    container_problems = check_containers()
    problems += container_problems

    # Konteynerler ayakta değilse API ve boru hattı zaten cevap vermez;
    # aynı arızayı üç kez raporlamak gerçek sebebi gizler.
    if not container_problems:
        api_problems = check_api()
        problems += api_problems
        if not api_problems:
            problems += check_pipeline()

    healthy = not problems
    header = f"[{stamp}] {'SAGLIKLI' if healthy else 'SORUN'}"
    lines = [header, *(f"  - {p}" for p in problems)]
    report = "\n".join(lines)

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(report + "\n")

    if not quiet or not healthy:
        # Konsol cp1254 olabilir; kodlanamayan karakter nöbetçiyi düşürmesin.
        sys.stdout.reconfigure(errors="replace")  # type: ignore[union-attr]
        print(report)

    return 0 if healthy else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.watchdog", description=__doc__)
    parser.add_argument("--quiet", action="store_true",
                        help="Yalnızca sorun varsa konsola yaz")
    args = parser.parse_args(argv)
    return run(quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
