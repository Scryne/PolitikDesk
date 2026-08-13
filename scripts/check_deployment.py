"""Dağıtım kayması denetleyicisi (13 Ağustos 2026 arızası).

**Neden var.** `pd-beat` konteyneri Faz 1 imajıyla, `pd-worker` Faz 2
imajıyla koşarken `pd-api` Faz 3'e güncellenmişti. Beat'in elindeki
zamanlamada 13 görevin yalnızca 5'i vardı; kümeleme adımı hiç
koşmuyordu ve toplanan 29 makalenin 18'i askıda kalmıştı.

Depodaki kod doğruydu. Testler yeşildi. CI yeşildi. **Kayma kodda
değil, çalışan imajdaydı** — ve hiçbir test çalışan konteynere bakmaz.

Bu betik ona bakar: her konteynerin taşıdığı `politikdesk` kaynak
ağacını depodakiyle karşılaştırır ve beat'in zamanlama sayısını
doğrular.

    python -m scripts.check_deployment

Çıkış kodu 0 = konteynerler depoyla aynı; 1 = kayma var.

**Aynı sınıftan ikinci arıza (14 Ağustos 2026).** Kod ağacı birebir
aynıydı, zamanlama tamdı — ama `Dockerfile` `certs/` dizinini
kopyalamıyordu. `ca_bundle_path()` eksik dizini hata saymaz, sessizce
yalnız certifi'ye düşer; sonuç Resmî Gazete'de `CERTIFICATE_VERIFY_FAILED`
oldu. Yerelde geçen istek konteynerde düşüyordu. Ders: kayma yalnızca
`.py` dosyalarında olmuyor — **kodun okuduğu veri dosyaları da imaja
girmek zorunda.** `ASSET_DIRS` varlık denetimi onu kapatır.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = REPO_ROOT / "politikdesk"

# Konteyner -> depoda beklenen kod. `migrate` kısa ömürlüdür (koşar ve
# çıkar), bu yüzden denetlenmez.
CONTAINERS = ("pd-api", "pd-worker", "pd-beat")

# Konteyner içinde koşan hash betiği. Depodaki hesapla BİREBİR aynı
# olmalı — sıralama, kodlama ve ayraç dahil.
_HASH_SNIPPET = """
import hashlib, pathlib
root = pathlib.Path('/app/politikdesk')
h = hashlib.sha256()
for p in sorted(root.rglob('*.py')):
    h.update(str(p.relative_to(root)).replace('\\\\', '/').encode())
    h.update(p.read_bytes())
print(h.hexdigest())
"""

_SCHEDULE_SNIPPET = """
import json
from politikdesk.tasks import app
print(json.dumps(sorted(app.conf.beat_schedule)))
"""

# Kodun ÇALIŞMA ANINDA okuduğu, `.py` olmayan dosyalar. Bunlar imaja
# girmezse kod çalışır ama yanlış davranır (bkz. modül başlığı).
# Dizin adı -> depoda o dizini temsil eden dosya deseni.
ASSET_DIRS = {"certs": "*.pem", "config": "*.yml"}

# Konteynerde koşan liste betiği. Dizin adları `ASSET_DIRS`'ten türetilir;
# iki yerde ayrı ayrı yazılırsa biri güncellenip diğeri unutulur ve denetim
# sessizce eksik kalır — bu betiğin var olma sebebi tam olarak budur.
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
    """Konteynerde Python koşturur; konteyner yoksa None döner."""
    try:
        result = subprocess.run(  # noqa: S603
            ["docker", "exec", container, "python", "-c", snippet],  # noqa: S607
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


def main() -> int:
    expected = repo_hash()
    print(f"depo politikdesk/ ozeti : {expected[:16]}")
    print()

    drifted: list[str] = []
    missing: list[str] = []

    for container in CONTAINERS:
        actual = _docker_exec(container, _HASH_SNIPPET)
        if actual is None:
            print(f"  [ATLANDI] {container:<10} - konteyner calismiyor")
            missing.append(container)
            continue
        if actual == expected:
            print(f"  [OK]      {container:<10} - {actual[:16]}")
        else:
            print(f"  [KAYMA]   {container:<10} - {actual[:16]} (beklenen {expected[:16]})")
            drifted.append(container)

    # Beat'in zamanlaması ayrıca sayılır: asıl arıza burada görünmüştü.
    schedule_drift = False
    raw = _docker_exec("pd-beat", _SCHEDULE_SNIPPET)
    if raw is not None:
        want = expected_schedule()
        got = json.loads(raw)
        print()
        print(f"beat zamanlamasi        : {len(got)}/{len(want)} gorev")
        if got != want:
            schedule_drift = True
            for name in sorted(set(want) - set(got)):
                print(f"  [EKSIK]   {name}")
            for name in sorted(set(got) - set(want)):
                print(f"  [FAZLA]   {name}")

    # Varlık dosyaları: kod ağacı aynı olsa da imaja girmemiş olabilirler.
    asset_drift = False
    want_assets = expected_assets()
    print()
    for container in CONTAINERS:
        raw_assets = _docker_exec(container, _ASSET_SNIPPET)
        if raw_assets is None:
            continue
        got_assets = json.loads(raw_assets)
        for name, want_files in want_assets.items():
            got_files = got_assets.get(name)
            if got_files is None:
                asset_drift = True
                print(f"  [EKSIK]   {container:<10} - /app/{name}/ dizini imajda YOK")
            elif set(want_files) - set(got_files):
                asset_drift = True
                eksik = sorted(set(want_files) - set(got_files))
                print(f"  [EKSIK]   {container:<10} - /app/{name}/: {eksik}")
            else:
                print(f"  [OK]      {container:<10} - /app/{name}/ ({len(got_files)} dosya)")

    print()
    if drifted or schedule_drift or asset_drift:
        print("[HATA] Calisan konteyner(ler) depodaki koddan farkli.")
        print("       Duzeltme: docker compose --profile workers up -d --build")
        return 1
    if missing:
        print("[UYARI] Bazi konteynerler calismiyor; denetlenemedi.")
        return 0
    print("[OK] Tum konteynerler depodaki kodu tasiyor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
