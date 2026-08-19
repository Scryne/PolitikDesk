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

    last_run_yesterday = datetime.datetime(2026, 8, 13, 5, 0, tzinfo=datetime.UTC).astimezone(
        tz_ist
    )
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


# Beat zamanlamasının BEKLENEN girdileri, ad ad.
#
# Burada bir SAYI tutulmuyor ve bu bilinçli: eskiden `len(schedule) == 16`
# yazıyordu. Sayı tutan bir muhafız, görev eklendiğinde "16'yı 17 yap"
# refleksi doğurur; hangi girdinin eklendiğini veya yanlışlıkla
# silindiğini söylemez. Ad listesi ikisini de söyler ve yeni bir zamanlama
# eklemeyi bilinçli bir beyan hâline getirir.
EXPECTED_SCHEDULE_ENTRIES = {
    "ingest-every-5-minutes",
    "ingest-social-every-30-minutes",
    "embed-every-minute",
    "entities-every-2-minutes",
    "cluster-every-3-minutes",
    "claims-every-10-minutes",
    "evidence-every-5-minutes",
    "context-every-30-minutes",
    "political-relations-every-15-minutes",
    "official-calendar-twice-daily",
    "indicator-anomaly-twice-daily",
    "mark-delayed-hourly",
    "stance-shifts-every-20-minutes",
    "scheduler-match-hourly",
    "purge-daily",
    "health-check-hourly",
    "pipeline-health-hourly",
    "llm-budget-check",
    "briefing-morning",
    "briefing-evening",
    "metrics-rollup-nightly",
}


def test_beat_schedule_contains_exactly_the_declared_entries() -> None:
    """Zamanlama, beyan edilen girdi kümesiyle birebir örtüşmeli."""
    actual = set(app.conf.beat_schedule)
    assert actual == EXPECTED_SCHEDULE_ENTRIES, (
        f"Beklenmeyen girdi: {sorted(actual - EXPECTED_SCHEDULE_ENTRIES)} · "
        f"Eksik girdi: {sorted(EXPECTED_SCHEDULE_ENTRIES - actual)}"
    )


def test_all_beat_schedule_tasks_registered_and_executable() -> None:
    """Beat schedule içindeki tüm görevler Celery'ye kayıtlı ve çağrılabilir olmalı."""
    schedule = app.conf.beat_schedule
    for name, entry in schedule.items():
        task_name = entry["task"]
        assert task_name in app.tasks, (
            f"Schedule '{name}' için görev '{task_name}' app.tasks'ta kayıtlı değil."
        )
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
    """F3: Beat yeniden başlatıldığında / tasks modülü yeniden yüklendiğinde schedule korunur."""
    import importlib

    import politikdesk.tasks

    importlib.reload(politikdesk.tasks)
    reloaded_schedule = politikdesk.tasks.app.conf.beat_schedule
    assert set(reloaded_schedule) == EXPECTED_SCHEDULE_ENTRIES


def test_worker_app_imports_and_contains_full_beat_schedule() -> None:
    """Worker app doğrudan import edildiğinde de beat_schedule tam olmalıdır."""
    from politikdesk.worker import app as worker_app

    assert set(worker_app.conf.beat_schedule) == EXPECTED_SCHEDULE_ENTRIES



# ═════════════════════════ sosyal/çekirdek ayrımı (18 Ağustos 2026 denetimi)
def test_core_ingestion_excludes_bridge_backed_social_sources() -> None:
    """`ingest_all` sosyal kaynakları ÇEKMEMELİ.

    **Bu ayrımın var olma sebebi bir ölçümdür.**

    RSSHub köprüsünün önbellek ıskası 21–25 saniyedir (X'i canlı kazıyor;
    önbellek isabetinde aynı istek 4 ms). Adaptörün okuma zaman aşımı ise
    18 saniyeydi — yani eşik işin gerçek süresinin ALTINDA. Her ıska
    `ReadTimeout` oluyor, üç hatada devre kesici açılıyor ve o turdaki
    kalan sosyal kaynakların hepsi anında `CircuitOpenError` alıyordu:
    sağlık panosunda 9 kırmızı, 41 amber.

    Zaman aşımını tek başına yükseltmek çözüm değildi: toplama sıralıdır
    ve 46 sosyal kaynak × ~30 sn ≈ 23 dakika sürerdi; oysa çekirdek tur
    5 dakikada bir koşar. İki küme ayrıldı.
    """
    from politikdesk.ingestion.pipeline import SOCIAL_ADAPTERS, _selects
    from politikdesk.ingestion.repository import SourceRow

    def _row(slug: str, adapter: str) -> SourceRow:
        return SourceRow(
            id=1, slug=slug, name=slug, tier=1, kind="official",
            independence_group=None, access_method="rss", tos_status="allowed",
            adapter=adapter, base_url=None, feed_url=None, extra_feeds=None,
            keyword_filter=None, topics=None, is_active=True,
            is_wire_reference=False, vertical=None,
        )

    tcmb = _row("tcmb", "rss")
    x_tbmm = _row("x-tbmm", "twitter")

    assert _selects("core", tcmb) and not _selects("core", x_tbmm)
    assert _selects("social", x_tbmm) and not _selects("social", tcmb)
    assert _selects("all", tcmb) and _selects("all", x_tbmm)
    assert "twitter" in SOCIAL_ADAPTERS


def test_social_ingestion_is_scheduled_separately_and_less_often() -> None:
    """Sosyal tur çekirdek turdan SEYREK olmalı, aksi hâlde ayırmanın anlamı yok."""
    from politikdesk.tasks import (
        INGESTION_INTERVAL_SECONDS,
        SOCIAL_INGESTION_INTERVAL_SECONDS,
    )

    schedule = app.conf.beat_schedule
    assert schedule["ingest-social-every-30-minutes"]["task"] == "politikdesk.ingest_social"
    assert SOCIAL_INGESTION_INTERVAL_SECONDS > INGESTION_INTERVAL_SECONDS


def test_social_task_time_limits_fit_inside_its_own_interval() -> None:
    """Bir tur, bir sonraki tur başlamadan bitmeli — yoksa turlar üst üste biner."""
    from politikdesk.tasks import (
        SOCIAL_INGESTION_INTERVAL_SECONDS,
        SOCIAL_SOFT_TIME_LIMIT,
        SOCIAL_TIME_LIMIT,
    )

    assert SOCIAL_SOFT_TIME_LIMIT < SOCIAL_TIME_LIMIT < SOCIAL_INGESTION_INTERVAL_SECONDS


def test_bridge_read_timeout_exceeds_measured_cold_path_latency() -> None:
    """Okuma zaman aşımı, köprünün ölçülen en kötü gecikmesinin ÜSTÜNDE olmalı.

    18 Ağustos 2026 ölçümü: önbellek ıskasında 21,6 sn / 22,6 sn / 24,0 sn
    / 24,7 sn. Eşik bunun altında kalırsa her ıska hataya döner ve devre
    kesici tüm sosyal kaynakları düşürür.
    """
    from politikdesk.ingestion.adapters.twitter import (
        BRIDGE_READ_TIMEOUT,
        BRIDGE_TOTAL_TIMEOUT,
    )

    OLCULEN_EN_KOTU = 25.0
    assert BRIDGE_READ_TIMEOUT > OLCULEN_EN_KOTU
    assert BRIDGE_TOTAL_TIMEOUT >= BRIDGE_READ_TIMEOUT
