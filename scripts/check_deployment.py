"""Dağıtım ve Sürüm Bütünlüğü Denetleyicisi (F1 — Release Identity & Deployment Gate).

Repo → CI → Image → Container → DB zincirinin doğruluğunu ve senkronizasyonunu
garanti altına alır.

Denetimler:
  1. Konteyner varlığı ve çalışma durumu (pd-api, pd-worker, pd-beat)
  2. Kaynak kod ağacı senkronizasyonu (SHA256 hash karşılaştırması)
  3. Release Identity doğrulaması (app_version, git_sha, env)
  4. Gerekli çalışma zamanı modülleri ve adaptör kayıtları (tbmm, sayistay, cumhurbaskanligi...)
  5. Statik varlık ve yapılandırma dosyaları (/app/certs/, /app/config/)
  6. Celery Beat zamanlanmış görev bütünlüğü (16/16 görev)
  7. Veritabanı migration uyumluluğu ve bekleyen şema değişiklikleri
  8. LLM uçlarının worker'ın kendi ağ görüntüsünden erişilebilirliği (ADR-009 §7)

Kullanım:
    python -m scripts.check_deployment

Çıkış kodu:
    0: Tüm kapılar geçti, konteynerler depoyla tam senkron.
    1: Herhangi bir kayma, eksik veya uyumsuzluk tespit edildi.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

# Windows konsolunda UTF-8 / cp1254 kodlama hatalarını önle
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPO_ROOT / "politikdesk"
MIGRATIONS_DIR = REPO_ROOT / "migrations"

# Denetlenecek zorunlu servis konteynerleri.
#
# `pd-worker-llm` 20 Ağustos 2026'da eklendi: LLM görevleri ayrı bir
# kuyrukta koşar, yoksa 6–100 saniyelik çıkarım çağrıları saniyelik
# veritabanı görevlerini açlığa düşürüyordu. Bu kapı onu da denetler —
# aksi hâlde LLM işçisi bayat kodla koşarken kapı yeşil görünürdü ve
# B-77'nin (beat eski imajla koşuyordu, 13 saat sessiz durma) aynısı
# tekrarlanırdı.
CONTAINERS = ("pd-api", "pd-worker", "pd-worker-llm", "pd-beat")

# Konteyner içinde koşan hash betiği
_HASH_SNIPPET = """
import hashlib, pathlib
root = pathlib.Path('/app/politikdesk')
h = hashlib.sha256()
for p in sorted(root.rglob('*.py')):
    h.update(str(p.relative_to(root)).replace('\\\\', '/').encode())
    h.update(p.read_bytes())
print(h.hexdigest())
"""

# Release identity denetim betiği
_RELEASE_SNIPPET = """
import json
from politikdesk.release import get_release_info
print(json.dumps(get_release_info(include_db_schema=False).to_dict()))
"""

# Beat zamanlama denetim betiği
_SCHEDULE_SNIPPET = """
import json
from politikdesk.worker import app
print(json.dumps(sorted(app.conf.beat_schedule)))
"""

# Çalışma zamanı modül ve adaptör denetim betiği
_MODULES_SNIPPET = """
import json, sys
res = {"modules": {}, "adapters": {}}
for mod in ["politikdesk.verticals", "politikdesk.political_memory", "politikdesk.web.ui"]:
    try:
        __import__(mod)
        res["modules"][mod] = "ok"
    except Exception as e:
        res["modules"][mod] = str(e)

try:
    from politikdesk.ingestion.pipeline import ADAPTER_REGISTRY as ADAPTERS
    required = ["cumhurbaskanligi", "tbmm", "sayistay", "resmi_gazete", "tuik_sdmx"]
    missing = [a for a in required if a not in ADAPTERS]
    res["adapters"]["status"] = "ok" if not missing else f"missing: {missing}"
    res["adapters"]["registered"] = sorted(list(ADAPTERS.keys()))
except Exception as e:
    res["adapters"]["status"] = f"error: {e}"


print(json.dumps(res))
"""

# Varlık dizinleri ve desenleri
ASSET_DIRS = {"certs": "*.pem", "config": "*.yml"}

_ASSET_SNIPPET = f"""
import json, pathlib
out = {{}}
for name in {sorted(ASSET_DIRS)!r}:
    root = pathlib.Path('/app') / name
    out[name] = sorted(p.name for p in root.iterdir()) if root.is_dir() else None
print(json.dumps(out))
"""


def expected_assets() -> dict[str, list[str]]:
    """Depodaki varlık dosyalarının dizin başına adları."""
    return {
        name: sorted(p.name for p in (REPO_ROOT / name).glob(pattern))
        for name, pattern in ASSET_DIRS.items()
    }


def repo_hash() -> str:
    """Depodaki `politikdesk/` ağacının özeti."""
    h = hashlib.sha256()
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        h.update(str(path.relative_to(PACKAGE_DIR)).replace("\\", "/").encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def _docker_exec(container: str, snippet: str) -> str | None:
    """Konteynerde Python koşturur; konteyner yoksa veya hata verirse None döner."""
    try:
        result = subprocess.run(
            ["docker", "exec", container, "python", "-c", snippet],  # noqa: S603, S607
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def expected_schedule() -> list[str]:
    from politikdesk.tasks import app

    return sorted(app.conf.beat_schedule)


def get_repo_migrations() -> list[str]:
    """Depodaki migration versiyon listesi."""
    return sorted(p.stem for p in MIGRATIONS_DIR.glob("*.sql"))


def check_db_migrations() -> tuple[bool, list[str], list[str]]:
    """DB migration senkronizasyonunu denetler."""
    repo_migrations = get_repo_migrations()
    try:
        # pd-db konteynerinde psql ile sorgula
        res = subprocess.run(
            [  # noqa: S603, S607
                "docker",
                "exec",
                "pd-db",
                "psql",
                "-U",
                "politikdesk",
                "-d",
                "politikdesk",
                "-t",
                "-A",
                "-c",
                "SELECT version FROM schema_migrations ORDER BY version;",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode != 0:
            return False, repo_migrations, ["DB sorgulanamadi"]
        applied = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        pending = sorted(set(repo_migrations) - set(applied))
        return (len(pending) == 0, applied, pending)
    except Exception as e:  # noqa: BLE001
        return False, repo_migrations, [str(e)]


# Worker'in ICINDEN kosar: yapilandirilan LLM ucuna TCP baglantisi kurulabiliyor mu.
#
# ⛔ Bu adim neden var (19 Agu 2026, ADR-009 §7). `.env` cikarimi yerel bir
# uca (127.0.0.1:11434) yonlendirmisti. O uc hicbir zaman calismazdi: ortamda
# Ollama yoktu ve olsaydi bile 127.0.0.1 KONTEYNERIN KENDISIDIR. Sistem hata
# vermedi — her cagri once orada 180 sn asildi, sonra yedege dustu. Cikarim
# 6,5 kat yavas calisti ve bunu hicbir test, hicbir kapi yakalamadi.
#
# `.env` git'te olmadigi icin bu sapma statik olarak denetlenemez; yalnizca
# CALISMA ZAMANINDA, worker'in kendi ag goruntusunden olculebilir. Adimin
# tamami bu yuzden `docker exec` ile konteyner icinde kosar.
#
# Yalnizca TCP erisimi olculur, model cagrilmaz: kapi bir saglik kontrolu,
# bir kalite olcumu degil ve API kotasi harcamamalidir.
_LLM_ENDPOINT_SNIPPET = """
import json, socket, urllib.parse
from politikdesk.config import get_settings
s = get_settings()
uclar = {
    'extraction': s.llm_extraction_base_url or s.llm_base_url,
    'generation': s.llm_generation_base_url or s.llm_base_url,
}
out = {}
for ad, url in uclar.items():
    if not url:
        out[ad] = {'url': '', 'durum': 'tanimsiz'}
        continue
    p = urllib.parse.urlparse(url)
    port = p.port or (443 if p.scheme == 'https' else 80)
    try:
        with socket.create_connection((p.hostname, port), timeout=5):
            out[ad] = {'url': url, 'durum': 'ok'}
    except Exception as exc:
        out[ad] = {'url': url, 'durum': type(exc).__name__}
print(json.dumps(out))
"""


def check_llm_endpoints(container: str = "pd-worker") -> list[str]:
    """Worker'in yapilandirilan LLM uclarina gercekten ulasip ulasamadigi."""
    ham = _docker_exec(container, _LLM_ENDPOINT_SNIPPET)
    if ham is None:
        return [f"[ATLANDI]      {container} calismiyor — uc denetimi yapilamadi"]
    try:
        sonuc = json.loads(ham)
    except Exception as exc:  # noqa: BLE001
        return [f"[HATA]         uc denetimi okunamadi: {exc}"]

    satirlar = []
    for ad, bilgi in sonuc.items():
        url = bilgi["url"] or "(tanimsiz)"
        if bilgi["durum"] == "ok":
            satirlar.append(f"[OK]           {ad:<11} - {url}")
        elif bilgi["durum"] == "tanimsiz":
            satirlar.append(f"[OK]           {ad:<11} - genel yapilandirmaya dusuyor")
        else:
            satirlar.append(
                f"[ULASILAMIYOR] {ad:<11} - {url} ({bilgi['durum']}). "
                f"Cikarim/uretim bu uca gidemez; cagrilar zaman asimina ugrar."
            )
    return satirlar


def main() -> int:
    print("=" * 70)
    print("POLITIKDESK - DAGITIM VE SURUM BUTUNLUGU DENETIMI (FAZ 1 GATE)")
    print("=" * 70)

    expected = repo_hash()
    print(f"Depo politikdesk/ kaynak kodu ozeti: {expected[:16]}")

    from politikdesk.release import get_release_info

    repo_rel = get_release_info(include_db_schema=False)
    repo_sha_short = repo_rel.git_sha[:12] if repo_rel.git_sha else "unknown"
    print(f"Depo surumu: {repo_rel.app_version} | Git SHA: {repo_sha_short}")
    print()

    has_error = False

    # 1. Konteyner Varlığı ve Kod Özeti
    print("[1/7] Konteyner Calisma ve Kod Senkronizasyonu:")
    for container in CONTAINERS:
        actual = _docker_exec(container, _HASH_SNIPPET)
        if actual is None:
            print(f"  [KAPALI/EKSIK] {container:<10} - konteyner calismiyor veya erisilemiyor")
            has_error = True
            continue
        if actual == expected:
            print(f"  [OK]           {container:<10} - kod ozeti: {actual[:16]}")
        else:
            print(
                f"  [KAYMA]        {container:<10} - "
                f"kod ozeti: {actual[:16]} (beklenen: {expected[:16]})"
            )
            has_error = True

    # 2. Release Identity Kontrolü
    print("\n[2/7] Release Identity ve Surum Butunlugu:")
    for container in CONTAINERS:
        raw_rel = _docker_exec(container, _RELEASE_SNIPPET)
        if raw_rel is None:
            print(f"  [EKSIK] {container:<10} - release identity okunamadi")
            has_error = True
            continue
        try:
            c_rel = json.loads(raw_rel)
            version_ok = c_rel.get("app_version") == repo_rel.app_version
            c_sha = c_rel.get("git_sha", "unknown")
            if repo_rel.git_sha and repo_rel.git_sha != "unknown":
                sha_ok = (
                    (c_sha == repo_rel.git_sha)
                    or (len(c_sha) >= 7 and repo_rel.git_sha.startswith(c_sha))
                    or (len(repo_rel.git_sha) >= 7 and c_sha.startswith(repo_rel.git_sha[:12]))
                )
            else:
                sha_ok = True

            if version_ok and sha_ok:
                print(
                    f"  [OK]    {container:<10} - "
                    f"version={c_rel.get('app_version')} git_sha={c_sha[:12]}"
                )
            else:
                if not version_ok:
                    print(
                        f"  [KAYMA] {container:<10} - "
                        f"version={c_rel.get('app_version')} (beklenen: {repo_rel.app_version})"
                    )
                if not sha_ok:
                    print(
                        f"  [KAYMA] {container:<10} - "
                        f"git_sha={c_sha[:12]} (beklenen: {repo_sha_short})"
                    )
                has_error = True

        except Exception as e:  # noqa: BLE001
            print(f"  [HATA]  {container:<10} - JSON parse hatasi: {e}")
            has_error = True

    # 3. Çalışma Zamanı Modülleri ve Adaptör Kayıtları
    print("\n[3/7] Modul ve Adaptor Butunlugu (pd-worker):")
    raw_mod = _docker_exec("pd-worker", _MODULES_SNIPPET)
    if raw_mod is not None:
        try:
            mod_data = json.loads(raw_mod)
            for mod_name, status in mod_data.get("modules", {}).items():
                if status == "ok":
                    print(f"  [OK]    Modul: {mod_name}")
                else:
                    print(f"  [HATA]  Modul: {mod_name} -> {status}")
                    has_error = True

            adapter_status = mod_data.get("adapters", {}).get("status", "")
            if adapter_status == "ok":
                print(f"  [OK]    Adaptorler: {mod_data.get('adapters', {}).get('registered', [])}")
            else:
                print(f"  [HATA]  Adaptorler eksik/hatali: {adapter_status}")
                has_error = True
        except Exception as e:  # noqa: BLE001
            print(f"  [HATA]  Modul ciktisi islenemedi: {e}")
            has_error = True
    else:
        print("  [ATLANDI] pd-worker erisilemedigi icin modul/adaptor testi yapilamadi")
        has_error = True

    # 4. Celery Beat Zamanlama Bütünlüğü
    print("\n[4/7] Celery Beat Zamanlanmis Gorevler:")
    want_sched = expected_schedule()
    raw_sched = _docker_exec("pd-beat", _SCHEDULE_SNIPPET)
    if raw_sched is not None:
        try:
            got_sched = json.loads(raw_sched)
            print(f"  Zamanlama Gorev Sayisi: {len(got_sched)} / {len(want_sched)}")
            if got_sched == want_sched:
                print("  [OK]    Tum zamanlanmis gorevler Beat schedule'da mevcut.")
            else:
                has_error = True
                for name in sorted(set(want_sched) - set(got_sched)):
                    print(f"  [EKSIK GOREV] {name}")
                for name in sorted(set(got_sched) - set(want_sched)):
                    print(f"  [FAZLA GOREV] {name}")
        except Exception as e:  # noqa: BLE001
            print(f"  [HATA]  Beat schedule parse hatasi: {e}")
            has_error = True
    else:
        print("  [ATLANDI] pd-beat calismadigi icin zamanlama kontrol edilemedi")
        has_error = True

    # 5. Statik Varlık ve Konfigürasyon Dosyaları
    print("\n[5/7] Statik Varlik ve Yapilandirma Dosyalari:")
    want_assets = expected_assets()
    for container in CONTAINERS:
        raw_assets = _docker_exec(container, _ASSET_SNIPPET)
        if raw_assets is None:
            continue
        try:
            got_assets = json.loads(raw_assets)
            for name, want_files in want_assets.items():
                got_files = got_assets.get(name)
                if got_files is None:
                    has_error = True
                    print(f"  [EKSIK DIZIN] {container:<10} - /app/{name}/ dizini imajda YOK")
                elif set(want_files) - set(got_files):
                    has_error = True
                    eksik = sorted(set(want_files) - set(got_files))
                    print(f"  [EKSIK DOSYA] {container:<10} - /app/{name}/: {eksik}")
                else:
                    print(
                        f"  [OK]          {container:<10} - "
                        f"/app/{name}/ ({len(got_files)} dosya tam)"
                    )
        except Exception as e:  # noqa: BLE001
            print(f"  [HATA]  {container:<10} - Varlik JSON parse hatasi: {e}")
            has_error = True

    # 6. Veritabanı Migration Senkronizasyonu
    print("\n[6/7] Veritabani Sema ve Migration Uyumlulugu:")
    mig_ok, applied_migs, pending_migs = check_db_migrations()
    if mig_ok:
        last_mig = applied_migs[-1] if applied_migs else "Yok"
        print(
            f"  [OK]    Veritabani guncel. "
            f"Uygulanan: {len(applied_migs)} migration (Son: {last_mig})"
        )
    else:
        print(f"  [KAYMA] Bekleyen/Uygulanmamis migration'lar var: {pending_migs}")
        has_error = True

    # 7. LLM uçlarının worker'dan GERÇEKTEN erişilebilir olması
    print("\n[7/7] LLM Uc Erisilebilirligi (worker icinden):")
    for satir in check_llm_endpoints():
        print(f"  {satir}")
        if "[ULASILAMIYOR]" in satir:
            has_error = True

    print("\n" + "=" * 70)
    if has_error:
        print("[SONUC] [FAIL] DAGITIM VE SURUM BUTUNLUGU KAPISI BASARISIZ OLDU.")
        print("        Konteynerler depodaki kod/yapilandirma/sema ile senkron degil.")
        print(
            "        Duzeltme: docker compose --profile workers up -d --build "
            "&& python -m scripts.migrate up"
        )
        return 1

    print("[SONUC] [PASS] DAGITIM VE SURUM BUTUNLUGU KAPISI BASARIYLA GECTI.")
    print("        Tum servisler, moduller, zamanlamalar ve semalar depoyla tam senkron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
