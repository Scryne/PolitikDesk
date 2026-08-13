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
