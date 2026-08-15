"""Basit, ileri-yönlü SQL migration koşucusu (F0-15).

Alembic yerine düz SQL: Spec §7.3 şemayı SQL olarak tanımlıyor ve kanıt
motorunun kısıtları (CHECK'ler) SQL seviyesinde okunabilir kalmalı.

Kullanım:
    python -m scripts.migrate up       # bekleyen migration'ları uygula
    python -m scripts.migrate status   # hangileri uygulanmış göster
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

from politikdesk.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

_BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version    TEXT PRIMARY KEY,
  checksum   TEXT NOT NULL,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()[:16]


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """migrations/*.sql dosyalarını dosya adına göre sıralı döndürür."""
    files = sorted(directory.glob("*.sql"))
    return [Migration(version=f.stem, path=f, sql=f.read_text(encoding="utf-8")) for f in files]


def _applied(conn: psycopg.Connection) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version, checksum FROM schema_migrations")
        return dict(cur.fetchall())


def up(dsn: str) -> int:
    migrations = discover()
    if not migrations:
        print("Uygulanacak migration bulunamadı.")
        return 0

    applied_count = 0
    with psycopg.connect(dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(_BOOTSTRAP)
        conn.commit()

        applied = _applied(conn)

        for m in migrations:
            if m.version in applied:
                if applied[m.version] != m.checksum:
                    raise RuntimeError(
                        f"{m.version}: uygulanmış migration dosyası değişmiş "
                        f"(kayıtlı {applied[m.version]}, dosya {m.checksum}). "
                        "Geçmiş migration düzenlenemez — yeni bir dosya ekleyin."
                    )
                continue

            print(f"-> uygulaniyor: {m.version}")
            with conn.cursor() as cur:
                cur.execute(m.sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                    (m.version, m.checksum),
                )
            conn.commit()
            applied_count += 1

    print(f"Tamam. {applied_count} migration uygulandı.")
    return applied_count


def status(dsn: str) -> None:
    migrations = discover()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(_BOOTSTRAP)
        conn.commit()
        applied = _applied(conn)

    for m in migrations:
        mark = "[x]" if m.version in applied else "[ ]"
        print(f"{mark} {m.version}")


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "up"
    dsn = get_settings().database_url

    if command == "up":
        up(dsn)
    elif command == "status":
        status(dsn)
    else:
        print(f"Bilinmeyen komut: {command}. Kullanım: migrate [up|status]", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
