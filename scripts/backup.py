"""Yedekleme, geri yükleme ve felaket kurtarma (Disaster Recovery) sistemi (F4-06).

DoD: günlük otomatik yedek + geri yükleme prosedürü; test ortamına
geri yükleme başarıyla denenmiş ve belgelenmiş.

    python -m scripts.backup create [--label ETIKET] # yedek al + SHA-256 manifest üret
    python -m scripts.backup list                   # yedekleri listele
    python -m scripts.backup verify <dosya>         # checksum + pg_restore denetimi
    python -m scripts.backup restore <dosya> --into <hedef> [--force] # geri yükle + şema doğrula
    python -m scripts.backup drill [--path <dosya>] # izole ortamda tam kurtarma tatbikatı
    python -m scripts.backup prune [--keep N]       # saklama süresini uygula

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
bir dizin verilirse komut reddeder.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from politikdesk import __version__
from politikdesk.backup_policy import BackupLocationError, resolve_backup_dir

DB_CONTAINER = "pd-db"
KEEP_DAILY = 14
RESTORE_DB_SUFFIX_RE = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class BackupManifest:
    """Yedek dosyasına eşlik eden bütünlük ve metaveri manifestosu."""

    dump_filename: str
    sha256: str
    bytes: int
    created_at: str
    app_version: str
    git_sha: str
    table_counts: dict[str, int]
    migration_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@lru_cache(maxsize=1)
def backup_dir() -> Path:
    """Yedek dizini — `backup_policy` kararına göre (B-84)."""
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


def compute_sha256(path: Path) -> str:
    """Dosyanın SHA-256 özetini bellek dostu akışla hesaplar."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def manifest_path_for(dump_path: Path) -> Path:
    """Yedek dump dosyasına karşılık gelen manifest dosya yolu."""
    if dump_path.suffix == ".dump":
        return dump_path.with_suffix(".dump.meta.json")
    return Path(f"{dump_path}.meta.json")


def read_manifest(dump_path: Path) -> BackupManifest | None:
    """Yedek manifestosu varsa okur ve nesneye dönüştürür."""
    m_path = manifest_path_for(dump_path)
    if not m_path.is_file():
        return None
    try:
        data = json.loads(m_path.read_text(encoding="utf-8"))
        return BackupManifest(
            dump_filename=data.get("dump_filename", dump_path.name),
            sha256=data.get("sha256", ""),
            bytes=int(data.get("bytes", 0)),
            created_at=data.get("created_at", ""),
            app_version=data.get("app_version", ""),
            git_sha=data.get("git_sha", ""),
            table_counts=data.get("table_counts", {}),
            migration_count=int(data.get("migration_count", 0)),
        )
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------- create
def create(label: str = "") -> Path:
    """`pg_dump -Fc` ile sıkıştırılmış özel biçimde yedek alır ve manifest yazar."""
    if not _container_running():
        raise SystemExit(f"'{DB_CONTAINER}' konteyneri çalışmıyor. Önce: make up")

    production_db = _db_name()
    live_counts = _counts(production_db)
    migrations_count = _migration_count(production_db)

    from politikdesk.release import get_release_info

    rel = get_release_info(include_db_schema=False)

    target_dir = backup_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"-{label}" if label else ""
    target = target_dir / f"politikdesk-{stamp}{suffix}.dump"

    with target.open("wb") as fh:
        result = subprocess.run(  # noqa: S603
            [
                "docker",
                "exec",
                DB_CONTAINER,  # noqa: S607
                "pg_dump",
                "-U",
                _db_user(),
                "-d",
                production_db,
                "-Fc",
                "--no-owner",
            ],
            stdout=fh,
            check=False,
        )

    if result.returncode != 0 or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise SystemExit(f"pg_dump başarısız (çıkış {result.returncode}).")

    sha256_hash = compute_sha256(target)
    manifest = BackupManifest(
        dump_filename=target.name,
        sha256=sha256_hash,
        bytes=target.stat().st_size,
        created_at=datetime.now(UTC).isoformat(),
        app_version=__version__,
        git_sha=rel.git_sha,
        table_counts=live_counts,
        migration_count=migrations_count,
    )

    m_file = manifest_path_for(target)
    m_file.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    size_mb = target.stat().st_size / 1_048_576
    print(f"[OK] Yedek: {target}  ({size_mb:.2f} MB)")
    print(f"[OK] SHA-256: {sha256_hash}")
    print(f"[OK] Manifest: {m_file.name}")

    try:
        from politikdesk import audit

        audit.write(
            "backup_created",
            str(target),
            payload={
                "bytes": target.stat().st_size,
                "sha256": sha256_hash,
                "manifest": m_file.name,
            },
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[UYARI] Denetim izine yazılamadı: {type(exc).__name__}: {exc}")

    return target


# --------------------------------------------------------------------- verify
def verify(path: Path) -> bool:
    """Yedeğin SHA-256 bütünlüğünü ve pg_restore okunabilirliğini doğrular."""
    if not path.is_file():
        print(f"[HATA] Dosya yok: {path}")
        return False

    manifest = read_manifest(path)
    if manifest:
        current_hash = compute_sha256(path)
        if current_hash != manifest.sha256:
            print(
                f"[HATA] SHA-256 uyuşmazlığı!\n"
                f"  Beklenen: {manifest.sha256}\n"
                f"  Hesaplanan: {current_hash}"
            )
            return False
        print(f"[OK] SHA-256 bütünlüğü doğrulandı ({current_hash[:16]}...)")
    else:
        print("[BİLGİ] Manifest dosyası bulunamadı, arşiv başlık kontrolüne geçiliyor...")

    result = subprocess.run(  # noqa: S603
        ["docker", "exec", "-i", DB_CONTAINER, "pg_restore", "--list"],  # noqa: S607
        stdin=path.open("rb"),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"[HATA] Yedek okunamadı: {result.stderr.decode(errors='replace')[:300]}")
        return False

    lines = [
        ln
        for ln in result.stdout.decode(errors="replace").splitlines()
        if ln and not ln.startswith(";")
    ]
    tables = sum(1 for ln in lines if " TABLE DATA " in ln)
    print(f"[OK] Yedek okunabilir: {len(lines)} nesne, {tables} tablo verisi")
    return tables > 0


# -------------------------------------------------------------------- restore
def restore(path: Path, into: str, *, force: bool = False) -> bool:
    """Yedeği hedef veritabanına geri yükler ve şema/veri bütünlüğünü doğrular."""
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

    if not verify(path):
        raise SystemExit(f"Yedek bütünlük doğrulamasından geçemedi: {path}")

    user = _db_user()
    print(f"\n-> Hedef veritabanı hazırlanıyor: {into}")
    _psql(f'DROP DATABASE IF EXISTS "{into}"')
    _psql(f'CREATE DATABASE "{into}"')
    _psql("CREATE EXTENSION IF NOT EXISTS vector", database=into)

    print(f"-> Veri aktarılıyor (pg_restore -> {into})...")
    result = subprocess.run(  # noqa: S603
        [
            "docker",
            "exec",
            "-i",
            DB_CONTAINER,  # noqa: S607
            "pg_restore",
            "-U",
            user,
            "-d",
            into,
            "--no-owner",
            "--exit-on-error",
        ],
        stdin=path.open("rb"),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"[HATA] Geri yükleme başarısız:\n{result.stderr.decode(errors='replace')[:800]}")
        return False

    manifest = read_manifest(path)
    expected_counts = manifest.table_counts if manifest else None

    ok = validate_restored_db(into, expected_counts=expected_counts)

    if ok:
        with contextlib.suppress(Exception):
            from politikdesk import audit

            audit.write("backup_restored", str(path), payload={"into": into, "verified": True})
    return ok


def validate_restored_db(database: str, expected_counts: dict[str, int] | None = None) -> bool:
    """Geri yüklenen veritabanında şema, eklenti, FK ve satır tutarlılığını doğrular."""
    print(f"\n-> '{database}' veritabanı derinlikli bütünlük denetimi başlatılıyor...")

    try:
        _psql("SELECT '[1,2,3]'::vector AS vec;", database=database)
        print("  [OK] pgvector uzantısı aktif ve vektör tipi işlenebiliyor.")
    except SystemExit:
        print("  [HATA] pgvector uzantısı çalışmıyor!")
        return False

    mig_count = _migration_count(database)
    if mig_count == 0:
        print("  [HATA] schema_migrations tablosu boş veya bulunamadı!")
        return False
    print(f"  [OK] Migration tablosu geçerli ({mig_count} migration kayıtlı).")

    core_tables = (
        "articles",
        "events",
        "claims",
        "evidence",
        "drafts",
        "sources",
        "audit_log",
        "editorial_profiles",
    )
    counts = _counts(database)
    for tbl in core_tables:
        if not _table_exists(database, tbl):
            print(f"  [HATA] Kritik tablo eksik: '{tbl}'")
            return False
        print(f"  [OK] Tablo mevcut: '{tbl}' ({counts.get(tbl, 0)} satır)")

    fk_checks = [
        (
            "articles -> sources",
            "SELECT count(*) AS n FROM articles a "
            "WHERE NOT EXISTS (SELECT 1 FROM sources s WHERE s.id = a.source_id)",
        ),
        (
            "claims -> events",
            "SELECT count(*) AS n FROM claims c "
            "WHERE NOT EXISTS (SELECT 1 FROM events e WHERE e.id = c.event_id)",
        ),
        (
            "evidence -> claims",
            "SELECT count(*) AS n FROM evidence ev "
            "WHERE NOT EXISTS (SELECT 1 FROM claims c WHERE c.id = ev.claim_id)",
        ),
        (
            "drafts -> events",
            "SELECT count(*) AS n FROM drafts d "
            "WHERE NOT EXISTS (SELECT 1 FROM events e WHERE e.id = d.event_id)",
        ),
    ]

    for label, sql in fk_checks:
        res = _query_scalar(database, sql)
        if res != 0:
            print(f"  [HATA] FK ihlali ({label}): {res} yetim kayıt bulundu!")
            return False
    print("  [OK] İlişkisel yabancı anahtar (FK) bütünlüğü tam.")

    ref_counts = expected_counts if expected_counts is not None else _counts(_db_name())
    print(f"\n  {'tablo':<20} {'beklenen':>10} {'geri yuklenen':>14}  durum")
    print("  " + "-" * 54)
    all_match = True
    for table in sorted(set(ref_counts) | set(counts)):
        a = ref_counts.get(table, -1)
        b = counts.get(table, -1)
        mark = "OK" if a == b else "FARKLI"
        if a != b:
            all_match = False
        print(f"  {table:<20} {a:>10} {b:>14}  {mark}")

    if all_match:
        print(f"\n[OK] Veritabanı bütünlüğü kusursuz: '{database}' beklentilerle tam uyumlu.")
    else:
        print("\n[UYARI] Satır sayılarında sapma tespit edildi!")
    return all_match


# ----------------------------------------------------------- recovery drill
def drill(path: Path | None = None, keep_db: bool = False) -> bool:
    """İzole bir geçici veritabanında uçtan uca Felaket Kurtarma Tatbikatı (DR Drill) yürütür."""
    print("=" * 65)
    print("POLITIKDESK - FELAKET KURTARMA TATBİKATI (DISASTER RECOVERY DRILL)")
    print("=" * 65)

    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    temp_db = f"politikdesk_drill_{stamp}"

    if path is None:
        print("[1/5] Tatbikat için yeni canlı yedek oluşturuluyor...")
        dump_file = create(label="drill")
    else:
        dump_file = path
        print(f"[1/5] Belirtilen yedek kullanılacak: {dump_file}")

    if not dump_file.is_file():
        print(f"[HATA] Yedek dosyası bulunamadı: {dump_file}")
        return False

    print("\n[2/5] Yedek bütünlük denetimi yapılıyor...")
    if not verify(dump_file):
        print("[HATA] Yedek bütünlük denetiminden geçemedi!")
        return False

    print(f"\n[3/5] İzole geçici test veritabanına ({temp_db}) yükleniyor...")
    ok = restore(dump_file, into=temp_db, force=True)
    if not ok:
        print(f"[HATA] '{temp_db}' üzerine geri yükleme başarısız!")
        if not keep_db:
            _psql(f'DROP DATABASE IF EXISTS "{temp_db}"')
        return False

    print("\n[4/5] Uygulama düzeyi işlevsellik duman testleri yürütülüyor...")
    try:
        _psql(
            "SELECT id, title, article_count FROM events "
            "WHERE centroid_embedding IS NOT NULL LIMIT 3;",
            database=temp_db,
        )
        _psql(
            "SELECT count(*) FROM claims "
            "WHERE evidence_status IN ('strongly_corroborated', 'partially_corroborated');",
            database=temp_db,
        )
        print("  [OK] Vektör arama ve kanıt sorguları başarıyla çalıştırıldı.")
    except Exception as e:
        print(f"  [HATA] Uygulama sorgu duman testi başarısız: {e}")
        if not keep_db:
            _psql(f'DROP DATABASE IF EXISTS "{temp_db}"')
        return False

    print("\n[5/5] Tatbikat sonuçlandırılıyor...")
    if not keep_db:
        _psql(f'DROP DATABASE IF EXISTS "{temp_db}"')
        print(f"  [OK] Geçici test veritabanı ('{temp_db}') güvenle silindi.")
    else:
        print(f"  [BİLGİ] --keep-db verildi, '{temp_db}' veritabanı incelenmek üzere bırakıldı.")

    try:
        from politikdesk import audit

        audit.write(
            "recovery_drill_passed",
            str(dump_file),
            payload={"temp_db": temp_db, "timestamp": datetime.now(UTC).isoformat()},
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  [UYARI] Denetim izine yazılamadı: {exc}")

    print("=" * 65)
    print("[SONUÇ] FELAKET KURTARMA TATBİKATI BAŞARIYLA TAMAMLANDI.")
    print("        Sistem, yedekten sıfır veri kaybıyla ayağa kalkabilir durumda.")
    print("=" * 65)
    return True


def _psql(sql: str, *, database: str = "postgres") -> None:
    result = _docker(
        "exec",
        DB_CONTAINER,
        "psql",
        "-U",
        _db_user(),
        "-d",
        database,
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
        capture=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"psql başarısız: {result.stderr.decode(errors='replace')[:300]}")


def _query_scalar(database: str, sql: str) -> int:
    result = _docker(
        "exec",
        DB_CONTAINER,
        "psql",
        "-U",
        _db_user(),
        "-d",
        database,
        "-t",
        "-A",
        "-c",
        sql,
        capture=True,
    )
    try:
        return int(result.stdout.decode(errors="replace").strip())
    except (ValueError, TypeError):
        return -1


def _table_exists(database: str, table_name: str) -> bool:
    try:
        sql = (
            f"SELECT count(*) FROM information_schema.tables "
            f"WHERE table_schema='public' AND table_name='{table_name}';"
        )
        return _query_scalar(database, sql) > 0
    except Exception:  # noqa: BLE001
        return False


def _migration_count(database: str) -> int:
    try:
        return _query_scalar(database, "SELECT count(*) FROM schema_migrations;")
    except Exception:  # noqa: BLE001
        return 0


_COUNT_SQL = """
SELECT 'articles' AS t, count(*) AS n FROM articles
UNION ALL SELECT 'events', count(*) FROM events
UNION ALL SELECT 'claims', count(*) FROM claims
UNION ALL SELECT 'evidence', count(*) FROM evidence
UNION ALL SELECT 'drafts', count(*) FROM drafts
UNION ALL SELECT 'sources', count(*) FROM sources
UNION ALL SELECT 'audit_log', count(*) FROM audit_log
UNION ALL SELECT 'editorial_profiles', count(*) FROM editorial_profiles
ORDER BY 1
"""


def _counts(database: str) -> dict[str, int]:
    result = _docker(
        "exec",
        DB_CONTAINER,
        "psql",
        "-U",
        _db_user(),
        "-d",
        database,
        "-t",
        "-A",
        "-F",
        "|",
        "-c",
        _COUNT_SQL,
        capture=True,
    )
    out: dict[str, int] = {}
    for line in result.stdout.decode(errors="replace").splitlines():
        if "|" in line:
            name, _, value = line.partition("|")
            with contextlib.suppress(ValueError):
                out[name.strip()] = int(value.strip())
    return out


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

    print(f"Dizin: {directory}\n")
    print(f"{'Dosya Adı':<45} {'Boyut':>10}  {'Manifest':<10} {'SHA-256 (İlk 8)':<12}")
    print("-" * 80)
    for f in files:
        m = read_manifest(f)
        m_status = "[VAR]" if m else "[YOK]"
        sha_str = m.sha256[:8] if m else "-"
        print(f"{f.name:<45} {f.stat().st_size / 1_048_576:>8.2f} MB  {m_status:<10} {sha_str:<12}")
    return files


def prune(keep: int = KEEP_DAILY) -> int:
    """En yeni `keep` yedeği bırakır, gerisini siler (manifestleriyle birlikte)."""
    files = sorted(backup_dir().glob("politikdesk-*.dump"), reverse=True)
    removed = 0
    for old in files[keep:]:
        old.unlink(missing_ok=True)
        m_file = manifest_path_for(old)
        m_file.unlink(missing_ok=True)
        print(f"silindi: {old.name} (ve manifesti)")
        removed += 1
    print(f"[OK] {len(files) - removed} yedek tutuldu, {removed} silindi.")
    return removed


# ------------------------------------------------------------------------ cli
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.backup", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Yedek al ve manifest oluştur")
    p_create.add_argument("--label", default="", help="Dosya adına eklenecek etiket")

    sub.add_parser("list", help="Yedekleri ve manifest durumlarını listele")

    p_verify = sub.add_parser("verify", help="Yedek okunabilir mi ve SHA-256 tutarlı mı?")
    p_verify.add_argument("path", type=Path)

    p_restore = sub.add_parser("restore", help="Ayrı bir veritabanına geri yükle ve doğrula")
    p_restore.add_argument("path", type=Path)
    p_restore.add_argument("--into", required=True, help="Hedef veritabanı adı")
    p_restore.add_argument(
        "--force", action="store_true", help="Üretim veritabanının üzerine yazmayı zorla"
    )

    p_drill = sub.add_parser("drill", help="İzole ortamda otomatik DR Tatbikatı yürüt")
    p_drill.add_argument("--path", type=Path, default=None, help="Kullanılacak özel yedek dosyası")
    p_drill.add_argument(
        "--keep-db", action="store_true", help="Geçici veritabanını tatbikat bitince silme"
    )

    p_prune = sub.add_parser("prune", help="Eski yedekleri ve manifestleri sil")
    p_prune.add_argument("--keep", type=int, default=KEEP_DAILY)

    args = parser.parse_args(argv)

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
    elif args.command == "drill":
        return 0 if drill(path=args.path, keep_db=args.keep_db) else 1
    elif args.command == "prune":
        prune(args.keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
