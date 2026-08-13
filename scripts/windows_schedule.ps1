# PolitikDesk — Windows zamanlanmış görevleri (F4-06, F4-10)
#
# Celery beat boru hattını zamanlar, ama iki iş konteynerin İÇİNDEN
# yapılamaz:
#
#   1. Yedekleme  — `pg_dump`'ı `docker exec` ile db konteynerinde koşar;
#                   worker konteynerinin docker soketine erişimi yok
#                   (olması da istenmez: konteynerden host'a docker
#                   erişimi vermek yetki yükseltme yoludur).
#   2. Sağlık nöbeti — Docker Desktop kapalıysa beat de kapalıdır;
#                   "her şey durdu" durumunu ancak dışarıdan bir göz görür.
#
# Kurulum (YÖNETİCİ PowerShell'de bir kez):
#     powershell -ExecutionPolicy Bypass -File scripts\windows_schedule.ps1 -Install
#
# Kaldırma:
#     powershell -ExecutionPolicy Bypass -File scripts\windows_schedule.ps1 -Remove
#
# Durum:
#     powershell -ExecutionPolicy Bypass -File scripts\windows_schedule.ps1 -Status

param(
    [switch]$Install,
    [switch]$Remove,
    [switch]$Status
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackupTask  = 'PolitikDesk-GunlukYedek'
$HealthTask  = 'PolitikDesk-SaglikNobeti'

function Get-PythonPath {
    $venv = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    if (Test-Path $venv) { return $venv }
    $sys = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($sys) { return $sys }
    throw "Python bulunamadi. .venv kurulu mu? (make setup)"
}

function Install-Tasks {
    $python = Get-PythonPath
    Write-Host "Python: $python"
    Write-Host "Proje : $ProjectRoot"

    # --- Gunluk yedek: 03:30 ---
    # Boru hattinin en sakin saati. Purge 03:15'te kosuyor; yedek ondan
    # SONRA alinir ki yedek, saklama politikasi uygulanmis veriyi tasisin.
    $backupCmd = "-m scripts.backup create --label otomatik"
    $backupAction = New-ScheduledTaskAction -Execute $python `
        -Argument $backupCmd -WorkingDirectory $ProjectRoot
    $backupTrigger = New-ScheduledTaskTrigger -Daily -At 03:30

    # --- Eski yedekleri sil: haftalik, Pazar 03:45 ---
    $pruneAction = New-ScheduledTaskAction -Execute $python `
        -Argument "-m scripts.backup prune" -WorkingDirectory $ProjectRoot

    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -DontStopOnIdleEnd `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

    Register-ScheduledTask -TaskName $BackupTask `
        -Action @($backupAction, $pruneAction) `
        -Trigger $backupTrigger `
        -Settings $settings `
        -Description 'PolitikDesk gunluk veritabani yedegi (F4-06)' `
        -Force | Out-Null
    Write-Host "[OK] '$BackupTask' kuruldu - her gun 03:30"

    # --- Saglik nobeti: her 6 saatte bir ---
    # Konteynerler ayakta mi + boru hatti akiyor mu. Ciktisi
    # `backups\health.log`'a yazilir.
    $healthAction = New-ScheduledTaskAction -Execute $python `
        -Argument "-m scripts.watchdog" -WorkingDirectory $ProjectRoot
    $healthTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(6) `
        -RepetitionInterval (New-TimeSpan -Hours 6)

    Register-ScheduledTask -TaskName $HealthTask `
        -Action $healthAction `
        -Trigger $healthTrigger `
        -Settings $settings `
        -Description 'PolitikDesk saglik nobeti (F4-05/F4-10)' `
        -Force | Out-Null
    Write-Host "[OK] '$HealthTask' kuruldu - 6 saatte bir"

    Write-Host ""
    Write-Host "Docker Desktop'in acilista baslamasi da gerekir:"
    Write-Host "  Docker Desktop > Settings > General >"
    Write-Host "  'Start Docker Desktop when you sign in' isaretli olmali."
}

function Remove-Tasks {
    foreach ($name in @($BackupTask, $HealthTask)) {
        if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
            Write-Host "[OK] '$name' kaldirildi"
        } else {
            Write-Host "[--] '$name' zaten yok"
        }
    }
}

function Show-Status {
    foreach ($name in @($BackupTask, $HealthTask)) {
        $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($task) {
            $info = Get-ScheduledTaskInfo -TaskName $name
            Write-Host "$name : $($task.State)"
            Write-Host "    son kosum : $($info.LastRunTime)  (sonuc $($info.LastTaskResult))"
            Write-Host "    sonraki   : $($info.NextRunTime)"
        } else {
            Write-Host "$name : KURULU DEGIL"
        }
    }
}

if     ($Install) { Install-Tasks }
elseif ($Remove)  { Remove-Tasks }
elseif ($Status)  { Show-Status }
else {
    Write-Host "Kullanim: -Install | -Remove | -Status"
    Show-Status
}
