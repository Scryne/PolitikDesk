"""Yedeğin NEREYE yazılacağı kuralı (B-84).

**Karar: yedekler bulut eşitlemesi dışında tutulur; şifreleme zorunlu
değildir.** Gerekçe aşağıda, çünkü bu karar bir tercih değil bir risk
değerlendirmesidir ve sonradan tersine çevrilmek istenirse neyin
tartışıldığı bilinmelidir.

## Neden BitLocker yetmiyor

BitLocker **diski** korur: makine çalınırsa veri okunamaz. Ama
`backups/` OneDrive altındayken dosyalar Microsoft'un sunucularına
**kopyalanır** ve orada BitLocker'ın hükmü yoktur. Yani asıl maruziyet
"disk çalınırsa" değil, "veri zaten üçüncü tarafta" hâlidir.

Yedeğin içinde ne var: makale alıntıları, **editoryal profil**
(kullanıcının kendi yayın duruşu) ve **taslaklar**. Kişisel bir siyasi
istihbarat aracı için bu, sızmaması gereken kümenin ta kendisidir.
Ayrıca `.gitignore` bu dizini korur ama **OneDrive `.gitignore` okumaz**
— yani depo koruması burada yanıltıcı bir güven veriyordu.

## Neden şifreleme ZORUNLU değil

Şifreleme anahtar yönetimi getirir ve **anahtar kaybı = yedek kaybı**.
Tek kullanıcılı bir araçta, dosyalar buluttan çıkarılıp BitLocker'lı bir
birime alındıktan sonra şifrelemenin marjinal kazancı, yedeği tümden
kaybetme riskinin altındadır. Yedeğin birinci işlevi *kurtarmaktır*;
kurtarılamayan bir yedek, şifreli olsa da işe yaramaz.

Şifreleme isteğe bağlı olarak eklenebilir (harici birim + `age`/GPG),
ama ürün onu zorunlu kılmaz ve kullanıcıya anahtar saklama yükü bindirmez.

## Neden bu dosya var (belge değil, KOD)

Asıl tuzak varsayılandı: `PD_BACKUP_DIR` yokken yol `"backups"` idi ve
bu, depo kökünün altı — yani OneDrive'ın içi. Kimse yanlış bir şey
yapmadı; **varsayılan yanlıştı.** Bu yüzden düzeltme belgeye değil koda
yazılır: varsayılan bulut dışına alınır *ve* bulut altındaki bir yol
verilirse komut reddeder.
"""

from __future__ import annotations

import os
from pathlib import Path

# Bulut eşitleme kökünü ilan eden ortam değişkenleri. İsim eşlemesinden
# daha güveniliridir: kullanıcı OneDrive klasörünü yeniden adlandırmış
# olabilir.
_CLOUD_ENV_VARS = (
    "OneDrive",
    "OneDriveCommercial",
    "OneDriveConsumer",
    "Dropbox",
    "iCloudDrive",
)

# Ortam değişkeni yoksa yol adından tanı. Küçük harfe indirgenmiş parça
# eşlemesi; "OneDrive - Firma" gibi türevleri de yakalasın diye `in`.
_CLOUD_PATH_MARKERS = (
    "onedrive",
    "dropbox",
    "google drive",
    "googledrive",
    "icloud",
    "yandexdisk",
    "yandex.disk",
    "pcloud",
    "mega",
    "box sync",
    "sync.com",
)

# Kaçış kapısı. Bilerek buluta yazmak isteyen (örneğin yedeği zaten
# şifreleyen) kullanıcı bunu 1 yapar — ama sessizce değil, açıkça.
ALLOW_CLOUD_ENV = "PD_BACKUP_ALLOW_CLOUD"

BACKUP_DIR_ENV = "PD_BACKUP_DIR"


class BackupLocationError(RuntimeError):
    """Yedek dizini bulut eşitlemesi altında."""


def default_backup_dir() -> Path:
    """Bulutun eşitlemediği, kullanıcıya özel yerel dizin.

    Windows'ta `%LOCALAPPDATA%` bilinçli seçimdir: OneDrive'ın "Bilinen
    Klasör Taşıma" özelliği Belgeler/Masaüstü/Resimler'i ele geçirebilir
    ama `AppData\\Local`'a dokunmaz.
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "PolitikDesk" / "backups"

    xdg = os.environ.get("XDG_DATA_HOME")
    base_path = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base_path / "politikdesk" / "backups"


def cloud_sync_reason(path: Path) -> str | None:
    """Yol bir bulut eşitleme kökü altındaysa gerekçeyi döndürür.

    Eşleşme yoksa `None`. Gerekçe metni kullanıcıya gösterilir — "neden
    reddedildi" sorusunun yanıtı hata mesajında olmalı.
    """
    try:
        resolved = path.expanduser().resolve()
    except (OSError, RuntimeError):
        resolved = path.expanduser().absolute()

    for var in _CLOUD_ENV_VARS:
        root = os.environ.get(var)
        if not root:
            continue
        try:
            root_path = Path(root).expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        if resolved == root_path or root_path in resolved.parents:
            return f"{var} ortam degiskeninin gosterdigi dizinin altinda ({root_path})"

    lowered = [part.casefold() for part in resolved.parts]
    for part in lowered:
        for marker in _CLOUD_PATH_MARKERS:
            if marker in part:
                return f"yol parcasi bulut eslemesine isaret ediyor ({part!r})"
    return None


def resolve_backup_dir(raw: str | None = None) -> Path:
    """`PD_BACKUP_DIR`'i okur, doğrular ve mutlak yol döndürür.

    Bulut altındaki bir yol `BackupLocationError` ile REDDEDİLİR —
    `PD_BACKUP_ALLOW_CLOUD=1` verilmedikçe. Uyarı yazıp devam etmek
    yeterli değildi: uyarılar okunmaz, yedek yıllarca buluta akar.
    """
    value = raw if raw is not None else os.environ.get(BACKUP_DIR_ENV)
    target = Path(value).expanduser() if value else default_backup_dir()
    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()

    reason = cloud_sync_reason(target)
    if reason is None:
        return target

    if os.environ.get(ALLOW_CLOUD_ENV, "").strip() in {"1", "true", "yes"}:
        return target

    raise BackupLocationError(
        f"Yedek dizini bulut eslemesi altinda: {target}\n"
        f"  Sebep: {reason}\n"
        "  Yedek makale alintisi, editoryal profil ve taslak icerir;\n"
        "  bulut kopyasini BitLocker KORUMAZ (B-84).\n"
        f"  Cozum: {BACKUP_DIR_ENV} degiskenini bulut disina alin, ornegin\n"
        f"    {default_backup_dir()}\n"
        f"  Bilerek buluta yaziyorsaniz: {ALLOW_CLOUD_ENV}=1"
    )
