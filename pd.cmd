@echo off
REM ===========================================================================
REM PolitikDesk - Windows komut calistirici (F4-10)
REM
REM `make` Windows'ta varsayilan olarak KURULU DEGILDIR ve bu makinede de
REM yoktu. README'nin tum akisi `make`e dayaniyordu; yani belgelenen
REM komutlarin hicbiri calismiyordu. Bu betik Makefile'in birebir
REM karsiligidir - ayni isler, ayni adlar.
REM
REM     pd help          komutlari listele
REM     pd start         yigini ayaga kaldir
REM     pd watchdog      saglik nobeti
REM
REM Makefile SILINMEDI: Linux/VPS'e tasindiginda gecerli kalir. Iki dosya
REM ayni komut adlarini tasir; birinde olan digerinde de olmali.
REM ===========================================================================
setlocal

REM Turkce cikti icin UTF-8. Varsayilan cp857/cp1254'te "İddia çıkarımı"
REM okunamaz hale geliyordu. PYTHONIOENCODING ayrica gerekli: chcp
REM konsolu cevirir ama Python'un stdout kodlamasini degistirmez.
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

set "ROOT=%~dp0"
cd /d "%ROOT%"

REM .venv varsa onu kullan; yoksa sistem python'u.
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

REM Release Identity (F1 / Madde 15): Git SHA ve branch otomatik tespiti
if not defined PD_GIT_SHA (
    for /f "tokens=*" %%i in ('git rev-parse HEAD 2^>nul') do set "PD_GIT_SHA=%%i"
)
if not defined PD_GIT_BRANCH (
    for /f "tokens=*" %%i in ('git branch --show-current 2^>nul') do set "PD_GIT_BRANCH=%%i"
)

if "%~1"=="" goto :help
goto :cmd_%~1 2>nul || goto :unknown

REM ------------------------------------------------------------------ yardim
:help
echo PolitikDesk - komutlar
echo.
echo   -- gunluk kullanim --
echo   pd start            Tum yigini ayaga kaldir
echo   pd stop             Yigini durdur
echo   pd restart          Yeniden KURARAK baslat (kod degistiyse)
echo   pd status           Konteyner durumu
echo   pd open             Feed'i tarayicida ac
echo.
echo   -- saglik --
echo   pd watchdog         Disaridan saglik nobeti
echo   pd pipeline-health  Hangi asamada birikme var?
echo   pd health           Kaynak saglik raporu
echo   pd deploy-check     Konteynerler depodaki kodu mu tasiyor?
echo   pd logs [servis]    Konteyner loglari
echo.
echo   -- yedek --
echo   pd backup           Yedek al
echo   pd backup-list      Yedekleri listele
echo   pd backup-verify ^<dosya^>   Yedek okunabilir mi?
echo   pd backup-restore ^<dosya^>  Ayri bir DB'ye geri yukle + dogrula
echo.
echo   -- boru hatti (elle) --
echo   pd ingest / embed / entities / cluster / claims / evidence / context
echo   pd briefing         Sabah brifingi uret
echo   pd metrics          Urun metriklerini topla
echo   pd sync             config/sources.yml -^> veritabani
echo.
echo   -- gelistirme --
echo   pd test             Test paketi
echo   pd lint             ruff + mypy
echo   pd audit            Bagimlilik guvenlik taramasi
echo   pd ci               lint + audit + mimari + test
echo   pd ui-check         Arayuz denetimi (tasma/konsol/a11y)
echo   pd migrate          Migration'lari uygula
echo.
echo   -- kurulum --
echo   pd setup            Bagimliliklari kur
echo   pd schedule-install Gunluk yedek + saglik nobetini Windows'a kur
echo   pd schedule-status  Zamanlanmis gorevlerin durumu
goto :eof

REM ---------------------------------------------------------- gunluk kullanim
:cmd_start
docker compose up -d db redis || goto :fail
docker compose run --rm migrate || goto :fail
docker compose up -d --build api || goto :fail
docker compose --profile workers up -d --build || goto :fail
"%PY%" -m scripts.check_deployment
echo.
echo PolitikDesk hazir:
echo   Feed       http://localhost:8000/feed
echo   Saglik     http://localhost:8000/admin/
echo   Metrikler  http://localhost:8000/admin/metrics
goto :eof

:cmd_stop
docker compose --profile workers down
goto :eof

:cmd_down
docker compose --profile workers down
goto :eof

:cmd_restart
call "%~f0" stop
call "%~f0" start
goto :eof

:cmd_up
docker compose up -d db redis || goto :fail
docker compose run --rm migrate || goto :fail
docker compose up -d --build api
goto :eof

:cmd_workers
docker compose --profile workers up -d --build || goto :fail
"%PY%" -m scripts.check_deployment
goto :eof

:cmd_status
docker ps -a --filter "name=pd-" --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
goto :eof

:cmd_open
start "" "http://localhost:8000/feed"
goto :eof

:cmd_logs
if "%~2"=="" (docker compose --profile workers logs --tail 80 -f) else (docker logs --tail 80 -f pd-%~2)
goto :eof

REM ------------------------------------------------------------------ saglik
:cmd_watchdog
"%PY%" -m scripts.watchdog
goto :eof

:cmd_pipeline-health
"%PY%" -c "from politikdesk import pipeline_health as p; [print(f'{r.status:6} {r.label:22} bekleyen={r.backlog:4} en_eski={r.oldest_hours} esik={r.threshold_hours}') for r in p.stage_report()]"
goto :eof

:cmd_health
"%PY%" -m scripts.ingest health
goto :eof

:cmd_deploy-check
"%PY%" -m scripts.check_deployment
goto :eof

REM ------------------------------------------------------------------- yedek
:cmd_backup
"%PY%" -m scripts.backup create
goto :eof

REM Yedek dizini bulut disindadir (B-84); tam yolu bu komut yazar.
:cmd_backup-list
"%PY%" -m scripts.backup list
goto :eof

:cmd_backup-verify
if "%~2"=="" (echo Kullanim: pd backup-verify ^<tam-yol^>.dump ^(yollari icin: pd backup-list^) & exit /b 1)
"%PY%" -m scripts.backup verify "%~2"
goto :eof

:cmd_backup-restore
if "%~2"=="" (echo Kullanim: pd backup-restore ^<tam-yol^>.dump ^(yollari icin: pd backup-list^) & exit /b 1)
"%PY%" -m scripts.backup restore "%~2" --into politikdesk_restore_test
goto :eof

REM -------------------------------------------------------------- boru hatti
:cmd_sync
"%PY%" -m scripts.ingest sync
goto :eof
:cmd_ingest
"%PY%" -m scripts.ingest run
goto :eof
:cmd_embed
"%PY%" -m scripts.ingest embed
goto :eof
:cmd_entities
"%PY%" -m scripts.ingest entities
goto :eof
:cmd_cluster
"%PY%" -m scripts.ingest cluster
goto :eof
:cmd_claims
"%PY%" -m scripts.ingest claims
goto :eof
:cmd_evidence
"%PY%" -m scripts.ingest evidence
goto :eof
:cmd_context
"%PY%" -m scripts.ingest context
goto :eof
:cmd_briefing
"%PY%" -m scripts.ingest briefing --slot morning --send
goto :eof
:cmd_metrics
"%PY%" -m scripts.ingest metrics
goto :eof
:cmd_eval
"%PY%" -m eval.run
goto :eof

REM -------------------------------------------------------------- gelistirme
:cmd_setup
"%PY%" -m pip install -e ".[dev]"
goto :eof

:cmd_test
"%PY%" -m pytest -v
goto :eof

:cmd_lint
"%PY%" -m ruff check .
"%PY%" -m mypy
goto :eof

:cmd_fmt
"%PY%" -m ruff format .
"%PY%" -m ruff check --fix .
goto :eof

:cmd_arch
"%PY%" -m scripts.check_architecture
goto :eof

REM B-83: bagimlilik guvenlik taramasi (CI'da zorunlu adim).
:cmd_audit
"%PY%" -m pip_audit --skip-editable
goto :eof

:cmd_ci
"%PY%" -m ruff check . || goto :fail
"%PY%" -m mypy || goto :fail
"%PY%" -m pip_audit --skip-editable || goto :fail
"%PY%" -m scripts.check_architecture || goto :fail
"%PY%" -m scripts.verify_arch_guard || goto :fail
"%PY%" -m pytest -q || goto :fail
goto :eof

:cmd_ui-check
REM DESIGN.md Bolum 14 denetimi. Test paketinden AYRI durur cunku ayakta
REM bir sunucu ister; `pd ci` Docker'siz de kosabilmeli.
"%PY%" -m playwright install chromium >nul 2>&1
"%PY%" "%ROOT%scripts\ui_check.py" --shots
goto :eof

:cmd_migrate
docker compose run --rm migrate
goto :eof

REM ----------------------------------------------------------------- kurulum
:cmd_schedule-install
powershell -ExecutionPolicy Bypass -File "%ROOT%scripts\windows_schedule.ps1" -Install
goto :eof

:cmd_schedule-status
powershell -ExecutionPolicy Bypass -File "%ROOT%scripts\windows_schedule.ps1" -Status
goto :eof

:cmd_schedule-remove
powershell -ExecutionPolicy Bypass -File "%ROOT%scripts\windows_schedule.ps1" -Remove
goto :eof

REM ------------------------------------------------------------------- hata
:unknown
echo Bilinmeyen komut: %~1
echo.
goto :help

:fail
echo.
echo [HATA] Komut basarisiz oldu.
exit /b 1
