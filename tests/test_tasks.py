"""Zamanlayıcı testleri (F1-05, F2-*, F3-16/19).

**Bu dosyanın var olma sebebi bir arızadır (13 Ağustos 2026).**

Canlı denetimde `pd-beat` konteynerinin Faz 1 imajıyla koştuğu görüldü:
13 zamanlanmış görevin yalnızca 5'i vardı. `cluster`, `claims`,
`evidence`, `context`, brifing ve metrik görevleri **hiç
gönderilmiyordu.** Sonuç: 29 makalenin 18'i gömülüp varlıkları
çıkarıldıktan sonra askıda kaldı — boru hattı kümeleme adımında sessizce
kopmuştu. Ne test ne CI bunu yakaladı, çünkü `tasks.py`'yi denetleyen
hiçbir test yoktu.

Buradaki testler *kod* kaymasını yakalar: yeni bir görev eklenip
zamanlanması unutulursa CI kırılır. *İmaj* kaymasını (çalışan
konteynerin eski kodu taşıması) testler yakalayamaz; onun denetleyicisi
`scripts/check_deployment.py`'dir.
"""

from __future__ import annotations

from politikdesk.tasks import app

# `ping` bilerek zamanlanmaz: worker'ın ayakta olduğunu elle doğrulamaya
# yarayan tanı görevidir, periyodik bir iş değildir.
UNSCHEDULED_BY_DESIGN = {"politikdesk.ping"}


def _registered_tasks() -> set[str]:
    return {name for name in app.tasks if name.startswith("politikdesk.")}


def _scheduled_tasks() -> set[str]:
    return {entry["task"] for entry in app.conf.beat_schedule.values()}


def test_every_registered_task_is_scheduled() -> None:
    """Tanımlanan her görev zamanlanmış olmalı.

    Asıl arızanın testi budur: `tasks.py`'ye görev eklenip
    `beat_schedule`'a yazılmazsa görev hiç koşmaz ve boru hattı sessizce
    kopar. Sessiz kopma, gürültülü hatadan daha pahalıdır.
    """
    unscheduled = _registered_tasks() - _scheduled_tasks() - UNSCHEDULED_BY_DESIGN
    assert not unscheduled, (
        f"Zamanlanmamış görev(ler): {sorted(unscheduled)}. "
        "Görev `beat_schedule`'a eklenmeli ya da bilerek zamanlanmıyorsa "
        "`UNSCHEDULED_BY_DESIGN`'a yazılıp gerekçesi belirtilmeli."
    )


def test_every_scheduled_task_exists() -> None:
    """Zamanlanan her görev gerçekten kayıtlı olmalı.

    Ters yön: bir görev silinir/yeniden adlandırılır ama zamanlama
    kalırsa beat her turda var olmayan bir görev gönderir ve iş
    kuyrukta düşer.
    """
    missing = _scheduled_tasks() - _registered_tasks()
    assert not missing, f"Zamanlamada olup kayıtlı olmayan görev(ler): {sorted(missing)}"


def test_pipeline_stages_are_all_scheduled() -> None:
    """Spec §11.3'ün boru hattı adımlarının tamamı zamanlanmış olmalı.

    Yukarıdaki iki test yapısal tutarlılığı denetler; bu test *isim
    isim* sayar. Bir adımın tamamı (görev + zamanlama) birlikte
    silinirse ilk iki test yine yeşil kalırdı — bu test kalmaz.
    """
    required = {
        "politikdesk.ingest_all",  # 1. toplama
        "politikdesk.embed_pending",  # 2. gömme
        "politikdesk.extract_entities_pending",  # 3. varlık
        "politikdesk.cluster_pending",  # 4. kümeleme  <- kopma noktasıydı
        "politikdesk.extract_claims_pending",  # 5. iddia
        "politikdesk.score_evidence",  # 6. kanıt
        "politikdesk.link_historical_context",  # 7. bağlam
        "politikdesk.generate_briefing",  # F3-16
        "politikdesk.rollup_metrics",  # F3-19
        "politikdesk.purge_expired_bodies",  # Spec §9.3
        "politikdesk.check_source_health",  # F1-14
    }
    assert required <= _scheduled_tasks()


def test_briefing_scheduled_twice() -> None:
    """Sabah ve akşam brifingi ayrı zamanlanmış olmalı (Spec §14.1 kalem 12).

    `generate_briefing` tek görevdir ama iki kez zamanlanır; `slot`
    farkı `kwargs`'tadır. Biri düşerse G3 #5 ("7 gün üst üste") yarım
    ölçülür.
    """
    slots = [
        entry.get("kwargs", {}).get("slot")
        for entry in app.conf.beat_schedule.values()
        if entry["task"] == "politikdesk.generate_briefing"
    ]
    assert sorted(slots) == ["evening", "morning"]


# ==================================================================== L1 (B-90)
def test_celery_app_timezone_is_europe_istanbul() -> None:
    """L1: Celery uygulama saat dilimi Europe/Istanbul olmalıdır."""
    assert app.conf.timezone == "Europe/Istanbul"
    assert app.conf.enable_utc is True


def test_crontab_schedules_and_hours() -> None:
    """L1: Zamanlanmış crontab saat ve dakikalarının doğrulanması."""
    schedule = app.conf.beat_schedule

    # briefing-morning: 08:00
    bm = schedule["briefing-morning"]["schedule"]
    assert 8 in bm.hour
    assert 0 in bm.minute

    # briefing-evening: 20:00
    be = schedule["briefing-evening"]["schedule"]
    assert 20 in be.hour
    assert 0 in be.minute

    # metrics-rollup-nightly: 23:50
    mr = schedule["metrics-rollup-nightly"]["schedule"]
    assert 23 in mr.hour
    assert 50 in mr.minute

    # llm-budget-check: 07:45 ve 15:45
    bc = schedule["llm-budget-check"]["schedule"]
    assert {7, 15} <= bc.hour
    assert 45 in bc.minute


def test_crontab_is_due_evaluates_in_europe_istanbul() -> None:
    """L1: 08:00 Europe/Istanbul crontab zamanlaması 05:00 UTC'de (08:00 TSİ) tetiklenir."""
    import datetime
    import zoneinfo

    from celery.schedules import crontab

    tz_ist = zoneinfo.ZoneInfo("Europe/Istanbul")
    s = crontab(hour=8, minute=0, app=app)
    assert s.tz == "Europe/Istanbul" or s.tz == tz_ist

    # 08:00 TSİ = 05:00 UTC
    dt_due = datetime.datetime(2026, 8, 14, 5, 0, tzinfo=datetime.UTC).astimezone(tz_ist)
    dt_early = datetime.datetime(2026, 8, 14, 4, 59, tzinfo=datetime.UTC).astimezone(tz_ist)
    dt_later = datetime.datetime(2026, 8, 14, 8, 0, tzinfo=datetime.UTC).astimezone(tz_ist)

    last_run_yesterday = datetime.datetime(2026, 8, 13, 5, 0, tzinfo=datetime.UTC).astimezone(tz_ist)
    last_run_today = datetime.datetime(2026, 8, 14, 5, 0, tzinfo=datetime.UTC).astimezone(tz_ist)

    # 1. 08:00 TSİ (05:00 UTC) anında: tetiklenmeli (is_due == True)
    s_due = crontab(hour=8, minute=0, nowfun=lambda: dt_due, app=app)
    assert s_due.is_due(last_run_yesterday).is_due is True

    # 2. 07:59 TSİ (04:59 UTC) anında: henüz vakti gelmedi (is_due == False)
    s_early = crontab(hour=8, minute=0, nowfun=lambda: dt_early, app=app)
    assert s_early.is_due(last_run_yesterday).is_due is False

    # 3. 11:00 TSİ (08:00 UTC) anında ve bugün 08:00'de zaten çalıştıysa: tekrar tetiklenmemeli (is_due == False)
    s_later = crontab(hour=8, minute=0, nowfun=lambda: dt_later, app=app)
    assert s_later.is_due(last_run_today).is_due is False


def test_political_relations_task_scheduled_and_registered() -> None:
    """F3: Siyasi ilişkiler görevi (political-relations) hem kayıtlı hem zamanlanmış olmalı."""
    schedule = app.conf.beat_schedule
    assert "political-relations-every-15-minutes" in schedule, (
        "political-relations-every-15-minutes beat schedule içinde eksik."
    )
    entry = schedule["political-relations-every-15-minutes"]
    assert entry["task"] == "politikdesk.link_political_relations"
    assert entry["schedule"] == 900.0  # 15 dakika = 900 saniye
    assert "politikdesk.link_political_relations" in app.tasks, (
        "politikdesk.link_political_relations görevi Celery app.tasks içinde kayıtlı değil."
    )


def test_all_16_beat_schedule_tasks_registered_and_executable() -> None:
    """F3: Beat schedule içindeki 16/16 tüm görevler Celery'ye kayıtlı ve çağrılabilir olmalı."""
    schedule = app.conf.beat_schedule
    assert len(schedule) == 16, f"Beklenen 16 zamanlanmış görev, bulunan: {len(schedule)}"
    for name, entry in schedule.items():
        task_name = entry["task"]
        assert task_name in app.tasks, f"Schedule '{name}' için görev '{task_name}' app.tasks'ta kayıtlı değil."
        task_fn = app.tasks[task_name]
        assert callable(task_fn), f"Görev '{task_name}' çağrılabilir bir fonksiyon değil."


def test_worker_ping_task_executes_synchronously() -> None:
    """F3: Celery worker görevi (ping) senkron olarak hatasız sonuç üretir."""
    from politikdesk.worker import ping

    res = ping.apply()
    assert res.get() == "pong"


def test_daily_rollup_uses_application_timezone_date(monkeypatch) -> None:
    """L1: daily_rollup timezone'a duyarlı gün belirler."""
    import zoneinfo
    from datetime import datetime

    from politikdesk import metrics

    recorded_day = None

    def fake_compute(day, window_days=7):
        nonlocal recorded_day
        recorded_day = day
        return []

    monkeypatch.setattr(metrics, "compute_metrics", fake_compute)

    # 23:50 Istanbul = 20:50 UTC
    metrics.daily_rollup()
    tz = zoneinfo.ZoneInfo("Europe/Istanbul")
    expected_today = datetime.now(tz).date()
    assert recorded_day == expected_today


def test_beat_schedule_persists_on_fresh_app_instance() -> None:
    """F3: Beat yeniden başlatıldığında / tasks modülü yeniden yüklendiğinde schedule 16/16 korunur."""
    import importlib
    import politikdesk.tasks

    importlib.reload(politikdesk.tasks)
    reloaded_schedule = politikdesk.tasks.app.conf.beat_schedule
    assert len(reloaded_schedule) == 16
    assert "political-relations-every-15-minutes" in reloaded_schedule
    assert "briefing-morning" in reloaded_schedule
    assert "briefing-evening" in reloaded_schedule


