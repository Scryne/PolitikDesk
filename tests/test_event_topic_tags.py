"""`events.topic_tags` toplama testleri.

Denetimde bulundu (19 Ağustos 2026): `articles.topics` 5.631 makalenin
5.631'inde doluyken `events.topic_tags` 1.680 olayın **tamamında boş
diziydi**. Konu sinyali makale düzeyinde üretiliyor ama olay düzeyine
hiç taşınmıyordu.

Görünmeyen bedeli: `web/repository.py` kişiselleştirmeyi
`personal_adjustment(topic_tags, priorities)` ile hesaplıyor. Alan hep
boş geldiği için kullanıcının konu önceliklerinin sıralamaya etkisi
**sıfırdı** — özellik arayüzde duruyor, sessizce hiçbir şey yapmıyordu.
Sessizce çalışmayan bir özellik, olmayan bir özellikten daha kötüdür:
kullanıcı ayarı yapar ve sonucun doğru olduğunu sanır.
"""

from __future__ import annotations

import inspect

from politikdesk.clustering import merger, repository
from politikdesk.web.repository import personal_adjustment


def test_topic_tag_refresher_exists() -> None:
    assert callable(repository.refresh_topic_tags)


def test_refresher_rebuilds_from_member_articles() -> None:
    kaynak = inspect.getsource(repository.refresh_topic_tags)
    assert "UPDATE events" in kaynak
    assert "articles" in kaynak
    assert "unnest" in kaynak


def test_empty_result_is_written_as_empty_array_not_null() -> None:
    """NULL bırakmak 'hesaplanmadı' ile 'konu yok'u ayırt edilemez kılar."""
    kaynak = inspect.getsource(repository.refresh_topic_tags)
    assert "COALESCE(sub.tags, '{}')" in kaynak


def test_all_three_event_write_paths_refresh_topic_tags() -> None:
    """Olay yazan üç yol da toplayıcıyı çağırmalı.

    Biri unutulursa alan o yoldan gelen olaylarda yine boş kalır ve
    kusur kısmen geri döner.
    """
    olustur = inspect.getsource(repository.create_event)
    assert "refresh_topic_tags" in olustur, "create_event() konu etiketi yazmiyor"

    modul = inspect.getsource(repository)
    assert modul.count("refresh_topic_tags(cur") >= 2, (
        "Uye ekleme yolu konu etiketini tazelemiyor: yeni makale yeni konu getirebilir."
    )

    birlestir = inspect.getsource(merger._refresh_event)
    assert "refresh_topic_tags" in birlestir, (
        "Birlestirme/bolme uyelik kumesini degistirir; konu kumesi de yeniden kurulmali."
    )


def test_personalisation_is_inert_without_tags() -> None:
    """Kusurun neden görünmediğini gösteren test.

    Boş etiketle kişiselleştirme sessizce 0 döner — hata vermez, log
    yazmaz. Bu yüzden aylarca fark edilmedi.
    """
    assert personal_adjustment([], {"parti_ve_siyaset": 5}) == 0


def test_personalisation_responds_to_real_tags() -> None:
    assert personal_adjustment(["parti_ve_siyaset"], {"parti_ve_siyaset": 5}) > 0
