"""Yedekleme ve geri yükleme (F4-06).

DoD: günlük otomatik yedek + geri yükleme prosedürü; test ortamına
geri yükleme başarıyla denenmiş ve belgelenmiş.

    python -m scripts.backup create              # yedek al
    python -m scripts.backup list                # yedekleri listele
    python -m scripts.backup verify <dosya>      # yedek okunabilir mi?
    python -m scripts.backup restore <dosya> --into politikdesk_restore_test
    python -m scripts.backup prune               # saklama süresini uygula

**Neden `pg_dump` konteynerin İÇİNDE koşuyor:** ana makinede bir
PostgreSQL istemcisi kurulu olmayabilir ve olsa bile sürümü sunucudan
eski olabilir (`pg_dump: server version mismatch`). `pd-db` konteynerinde
sunucuyla aynı sürüm zaten var. Yedek dosyası ana makineye yazılır ki
konteyner silinince yedek de gitmesin.

**Geri yükleme asla üretim veritabanının üzerine yazmaz.** `--into` ile
verilen yeni bir veritabanına yüklenir; hedef adı üretimle aynıysa komut
reddeder. Yedeği "denenmiş" saymanın tek yolu onu gerçekten geri
yüklemektir, ama geri yükleme denemesi verinin kendisini riske atmamalı.

**Yedeğin NEREYE yazıldığı `politikdesk/backup_policy.py`'nin kararıdır
(B-84).** Varsayılan bulut eşitlemesinin dışıdır; OneDrive/Dropbox gibi
bir dizin verilirse komut reddeder. Gerekçe o modülün başlığında.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from politikdesk.backup_policy import BackupLocationError, resolve_backup_dir

DB_CONTAINER = "pd-db"
# Saklama: 14 günlük + 8 haftalık. Tek kullanıcılı bir araçta daha uzunu
# disk yer; daha kısası "geçen hafta neyi bozdum" sorusunu yanıtlayamaz.
KEEP_DAILY = 14
RESTORE_DB_SUFFIX_RE = re.compile(r"^[a-z0-9_]+$")


@lru_cache(maxsize=1)
def backup_dir() -> Path:
    """Yedek dizini — `backup_policy` kararına göre (B-84).

    Varsayılan bulut eşitlemesi dışıdır ve bulut altındaki bir yol
    REDDEDİLİR. Eski varsayılan (`"backups"` = depo kökü = OneDrive içi)
    yedekleri sessizce üçüncü tarafa kopyalıyordu.

    İçe aktarma anında değil ÇAĞRI anında çözülür: modül seviyesinde
    hata fırlatmak `--help`'i bile ham bir yığın izine çevirirdi.
    """
    return resolve_backup_dir()


def _dsn() -> str:
    from politikdesk.config import get_settings

    return get_settings().database_url


def _db_name(dsn: str | None = None) -> str:
    return urlparse(dsn or _dsn()).path.lstrip("/") or "politikdesk"


def _db_user(dsn: str | None = None) -> str:
    return urlparse(dsn or _dsn()).username or "politikdesk"


def _docker(*args: str, capture: bool = False) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603
        ["docker", *args],  # noqa: S607
        check=False,
        capture_output=capture,
    )


def _container_running() -> bool:
    result = _docker("inspect", "-f", "{{.State.Running}}", DB_CONTAINER, capture=True)
    return result.returncode == 0 and result.stdout.strip() == b"true"


# --------------------------------------------------------------------- create
def create(label: str = "") -> Path:
    """`pg_dump -Fc` ile sıkıştırılmış özel biçimde yedek alır.

    Özel biçim (`-Fc`) düz SQL yerine seçildi: `pg_restore` ile tek tek
    tablo geri yüklenebiliyor ve dosya kendiliğinden sıkışıyor.
    """
    if not _container_running():
        raise SystemExit(
            f"'{DB_CONTAINER}' konteyneri çalışmıyor. Önce: make up"
        )

    target_dir = backup_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"-{label}" if label else ""
    target = target_dir / f"politikdesk-{stamp}{suffix}.dump"

    with target.open("wb") as fh:
        result = subprocess.run(  # noqa: S603
            ["docker", "exec", DB_CONTAINER,  # noqa: S607
             "pg_dump", "-U", _db_user(), "-d", _db_name(), "-Fc", "--no-owner"],
            stdout=fh,
            check=False,
        )

    if result.returncode != 0 or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise SystemExit(f"pg_dump başarısız (çıkış {result.returncode}).")

    size_mb = target.stat().st_size / 1_048_576
    print(f"[OK] Yedek: {target}  ({size_mb:.2f} MB)")

    # Yedeğin kendisi denetlenebilir bir olaydır (F4-16).
    try:
        from politikdesk import audit

        audit.write("backup_created", str(target),
                    payload={"bytes": target.stat().st_size})
    except Exception as exc:  # noqa: BLE001 — denetim izi yedeği geçersiz kılmaz
        print(f"[UYARI] Denetim izine yazılamadı: {type(exc).__name__}: {exc}")

    return target


# --------------------------------------------------------------------- verify
def verify(path: Path) -> bool:
    """Yedeği açmadan içindekileri listeler.

    Alınamamış bir yedekle alınmış ama bozuk bir yedek arasındaki fark,
    ancak ihtiyaç anında görülür — o an geç. `pg_restore --list` dosyayı
    okur ve içindekileri sayar; hiçbir şeye yazmaz.
    """
    if not path.is_file():
        print(f"[HATA] Dosya yok: {path}")
        return False

    result = subprocess.run(  # noqa: S603
        ["docker", "exec", "-i", DB_CONTAINER, "pg_restore", "--list"],  # noqa: S607
        stdin=path.open("rb"),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"[HATA] Yedek okunamadı: {result.stderr.decode(errors='replace')[:300]}")
        return False

    lines = [ln for ln in result.stdout.decode(errors="replace").splitlines()
             if ln and not ln.startswith(";")]
    tables = sum(1 for ln in lines if " TABLE DATA " in ln)
    print(f"[OK] Yedek okunabilir: {len(lines)} nesne, {tables} tablo verisi")
    return tables > 0


# -------------------------------------------------------------------- restore
def restore(path: Path, into: str, *, force: bool = False) -> bool:
    """Yedeği AYRI bir veritabanına geri yükler ve doğrular.

    Üretim veritabanının üzerine yazmaz: `into` üretimle aynı adı
    taşıyorsa komut reddeder. Amaç yedeğin *çalıştığını kanıtlamak*,
    veriyi riske atmak değil.
    """
    production = _db_name()
    if into == production and not force:
        raise SystemExit(
            f"'{into}' üretim veritabanı. Geri yükleme ayrı bir hedefe "
            f"yapılır: --into {production}_restore_test\n"
            "Gerçekten üzerine yazmak istiyorsanız --force verin."
        )
    if not RESTORE_DB_SUFFIX_RE.match(into):
        raise SystemExit(f"Geçersiz veritabanı adı: {into!r}")
    if not path.is_file():
        raise SystemExit(f"Dosya yok: {path}")

    user = _db_user()
    print(f"-> Hedef veritabanı hazırlanıyor: {into}")
    _psql(f'DROP DATABASE IF EXISTS "{into}"')
    _psql(f'CREATE DATABASE "{into}"')
    # pgvector uzantısı dump'ta CREATE EXTENSION olarak var ama şema
    # yüklenmeden önce hazır olması daha güvenli.
    _psql("CREATE EXTENSION IF NOT EXISTS vector", database=into)

    result = subprocess.run(  # noqa: S603
        ["docker", "exec", "-i", DB_CONTAINER,  # noqa: S607
         "pg_restore", "-U", user, "-d", into, "--no-owner", "--exit-on-error"],
        stdin=path.open("rb"),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"[HATA] Geri yükleme başarısız:\n"
              f"{result.stderr.decode(errors='replace')[:800]}")
        return False

    ok = _compare(production, into)
    if ok:
        try:
            from politikdesk import audit

            audit.write("backup_restored", str(path),
                        payload={"into": into, "verified": True})
        except Exception:  # noqa: BLE001, S110
            pass
    return ok


def _psql(sql: str, *, database: str = "postgres") -> None:
    result = _docker(
        "exec", DB_CONTAINER, "psql", "-U", _db_user(), "-d", database,
        "-v", "ON_ERROR_STOP=1", "-c", sql, capture=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"psql başarısız: {result.stderr.decode(errors='replace')[:300]}"
        )


_COUNT_SQL = """
SELECT 'articles' AS t, count(*) AS n FROM articles
UNION ALL SELECT 'events', count(*) FROM events
UNION ALL SELECT 'claims', count(*) FROM claims
UNION ALL SELECT 'evidence', count(*) FROM evidence
UNION ALL SELECT 'drafts', count(*) FROM drafts
UNION ALL SELECT 'sources', count(*) FROM sources
ORDER BY 1
"""


def _counts(database: str) -> dict[str, int]:
    result = _docker(
        "exec", DB_CONTAINER, "psql", "-U", _db_user(), "-d", database,
        "-t", "-A", "-F", "|", "-c", _COUNT_SQL, capture=True,
    )
    out: dict[str, int] = {}
    for line in result.stdout.decode(errors="replace").splitlines():
        if "|" in line:
            name, _, value = line.partition("|")
            out[name.strip()] = int(value.strip())
    return out


def _compare(production: str, restored: str) -> bool:
    """Geri yükleme "hata vermedi" ile "veri geldi" aynı şey değildir."""
    live = _counts(production)
    copy = _counts(restored)

    # Windows konsolu (cp1254) ✓/✗ basamıyor; işaretler ASCII tutuluyor.
    print(f"\n{'tablo':<12} {'uretim':>8} {'geri yuklenen':>14}")
    all_match = True
    for table in sorted(set(live) | set(copy)):
        a, b = live.get(table, -1), copy.get(table, -1)
        mark = "OK" if a == b else "FARKLI"
        if a != b:
            all_match = False
        print(f"{table:<12} {a:>8} {b:>14}  {mark}")

    if all_match:
        print(f"\n[OK] Geri yükleme doğrulandı: '{restored}' üretimle birebir aynı.")
    else:
        print("\n[HATA] Satır sayıları tutmuyor — yedek eksik.")
    return all_match


# ----------------------------------------------------------------- list/prune
def list_backups() -> list[Path]:
    directory = backup_dir()
    if not directory.is_dir():
        print(f"Yedek dizini yok: {directory}")
        return []
    files = sorted(directory.glob("politikdesk-*.dump"), reverse=True)
    if not files:
        print(f"Yedek yok: {directory}")
        return files

    # Dizin başlıkta yazılır: `verify`/`restore` tam yol ister ve yedekler
    # artık depo altında değil (B-84), yani kullanıcı yolu tahmin edemez.
    print(f"Dizin: {directory}\n")
    for f in files:
        print(f"{f.name:<45} {f.stat().st_size / 1_048_576:>8.2f} MB")
    return files


def prune(keep: int = KEEP_DAILY) -> int:
    """En yeni `keep` yedeği bırakır, gerisini siler."""
    files = sorted(backup_dir().glob("politikdesk-*.dump"), reverse=True)
    removed = 0
    for old in files[keep:]:
        old.unlink()
        print(f"silindi: {old.name}")
        removed += 1
    print(f"[OK] {len(files) - removed} yedek tutuldu, {removed} silindi.")
    return removed


# ------------------------------------------------------------------------ cli
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.backup", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Yedek al")
    p_create.add_argument("--label", default="", help="Dosya adına eklenecek etiket")

    sub.add_parser("list", help="Yedekleri listele")

    p_verify = sub.add_parser("verify", help="Yedek okunabilir mi?")
    p_verify.add_argument("path", type=Path)

    p_restore = sub.add_parser("restore", help="Ayrı bir veritabanına geri yükle")
    p_restore.add_argument("path", type=Path)
    p_restore.add_argument("--into", required=True, help="Hedef veritabanı adı")
    p_restore.add_argument("--force", action="store_true",
                           help="Üretim veritabanının üzerine yazmayı zorla")

    p_prune = sub.add_parser("prune", help="Eski yedekleri sil")
    p_prune.add_argument("--keep", type=int, default=KEEP_DAILY)

    args = parser.parse_args(argv)

    # Konum kuralı (B-84) burada yakalanır: kullanıcı ham yığın izi değil,
    # ne yapacağını söyleyen bir mesaj görsün.
    try:
        backup_dir()
    except BackupLocationError as exc:
        print(f"[HATA] {exc}", file=sys.stderr)
        return 2

    if args.command == "create":
        create(args.label)
    elif args.command == "list":
        list_backups()
    elif args.command == "verify":
        return 0 if verify(args.path) else 1
    elif args.command == "restore":
        return 0 if restore(args.path, args.into, force=args.force) else 1
    elif args.command == "prune":
        prune(args.keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
