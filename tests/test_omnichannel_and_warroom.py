"""Yeni eklenen Çok Kanallı İhracat ve Haber Masası Kumanda Odası testleri."""

from __future__ import annotations

from fastapi.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.web.export_formats import (
    to_audio_script,
    to_bluesky_post,
    to_instant_dispatch,
    to_linkedin_brief,
    to_mastodon_post,
    to_newsletter_markdown,
    to_x_thread,
)


def test_export_formats_generators() -> None:
    ev = {"id": 42, "title": "TCMB Politika Faizini %50 Seviyesinde Sabit Bıraktı", "salience_score": 75}
    claims = [
        {"claim_text": "Para Politikası Kurulu faizi değiştirmeme kararı aldı.", "evidence_status": "strongly_corroborated"},
        {"claim_text": "Enflasyon beklentilerinde belirgin bir düşüş gözlendi.", "evidence_status": "partially_corroborated"},
    ]
    articles = [
        {"source_name": "TCMB Resmî", "tier": 1},
        {"source_name": "Bloomberg HT", "tier": 2},
    ]

    # 1. X Thread
    tweets = to_x_thread(ev, claims, articles)
    assert len(tweets) >= 3
    for t in tweets:
        assert len(t) <= 280, f"Tweet 280 karakteri aşıyor: {len(t)}"

    # 2. LinkedIn Brief
    li = to_linkedin_brief(ev, claims, articles)
    assert "MAKRO GÜNDEM ÖZETİ" in li
    assert "TCMB Resmî" in li

    # 3. Instant Dispatch
    inst = to_instant_dispatch(ev, claims, articles)
    assert "POLİTİKDESK ANLIK BÜLTEN" in inst

    # 4. Audio Script
    audio = to_audio_script(ev, claims, articles)
    assert "PolitikDesk hızlı gündem bülteni" in audio

    # 5. Bluesky Post
    bsky = to_bluesky_post(ev, claims, articles)
    assert len(bsky) <= 300
    assert "POLİTİKDESK TEYİTLİ İSTİHBARAT" in bsky

    # 6. Mastodon Post
    masto = to_mastodon_post(ev, claims, articles)
    assert len(masto) <= 500
    assert "POLİTİKDESK DOĞRULANMIŞ İSTİHBARAT" in masto

    # 7. Newsletter Markdown
    nl = to_newsletter_markdown(ev, claims, articles)
    assert "### TCMB" in nl
    assert "Doğrulanmış İddialar" in nl


def test_war_room_endpoint() -> None:
    client = TestClient(app)
    res = client.get("/war-room")
    assert res.status_code == 200
    assert "Haber Masası" in res.text
    assert "Kumanda Odası" in res.text
    assert "wr-live-dot" in res.text


def test_war_room_indicators_never_come_from_hardcoded_numbers() -> None:
    """⛔ Ürünün en sert sözleşmesinin arayüz tarafındaki karşılığı.

    Kumanda odasının gösterge şeridi bir dönem **koda gömülü** sayılarla
    doluydu ve bunlar TÜİK/TCMB/Hazine imzasıyla gösteriliyordu
    ("TCMB Politika Faizi %45.00"). Spec §15/13 ve
    `editorial/grounding_check.py` kanıtta bulunmayan sayıyı yasaklar;
    kurum imzalı uydurma sayı bu yasağın en ağır ihlaliydi.

    Bu test kaynağı tarar, çıktıyı değil: veritabanı doluyken de boşken
    de geçmeli.
    """
    import ast
    import inspect

    from politikdesk.web import war_room

    tree = ast.parse(inspect.getsource(war_room))
    numeric_literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, float)
    ]
    assert not numeric_literals, (
        f"war_room.py'de kayan noktali sabit var: {numeric_literals}. "
        "Gosterge degerleri YALNIZCA repository.official_indicator_series() "
        "uzerinden, articles.official_value'dan gelir."
    )

    source = inspect.getsource(war_room)
    for banned in ("TÜFE", "Politika Faizi", "BIST", "Nakit Dengesi"):
        assert banned not in source, (
            f"war_room.py elle yazilmis gosterge adi tasiyor: {banned}. "
            "Etiketler fmt.metric_label() ile metrik anahtarindan turetilir."
        )


def test_indicator_strip_reads_the_timeseries_store_not_only_latest_article() -> None:
    """Gösterge şeridi `indicator_observations`'ı BİRİNCİL kaynak almalı.

    Gerileme: şerit yalnızca `articles.official_value`'dan okuduğunda seri
    başına tek satır dönüyordu; `history` tek noktaya, `previous_value`
    `None`'a düşüyor ve her kart "ilk gözlem" yazıyordu — Faz 3'te
    toplanan 1.803 gözlem veritabanında dururken. Yani ürün, sahip olduğu
    veriyi göstermiyordu.

    Kaynağı tarar, çıktıyı değil: veritabanı boşken de geçer.
    """
    import inspect

    from politikdesk.web import repository

    kaynak = inspect.getsource(repository.official_indicator_series)
    assert "indicator_observations" in kaynak, (
        "Sunum katmani zaman serisi deposunu kullanmiyor."
    )
    assert "superseded_at IS NULL" in kaynak, (
        "Revize edilmis gozlemler elenmiyor: ekranda yururlukten kalkmis "
        "sayi gorunebilir."
    )
    # Yedek yol korunmalı: seri olarak tanımlanmamış TÜİK metrikleri
    # (employment_rate gibi) hâlâ tek gözlemle de olsa görünmeli.
    assert "official_value" in kaynak


def test_indicator_metric_labels_cover_the_whole_metric_vocabulary() -> None:
    """Ekrana ham metrik anahtarı (`unemployment_rate`) çıkmamalı."""
    from politikdesk.nlp.claims import VALID_METRICS
    from politikdesk.web.ui.format import METRIC_LABELS

    missing = set(VALID_METRICS) - set(METRIC_LABELS)
    assert not missing, f"Turkce karsiligi olmayan metrik: {sorted(missing)}"
    extra = set(METRIC_LABELS) - set(VALID_METRICS)
    assert not extra, f"VALID_METRICS'te olmayan etiket: {sorted(extra)}"


def test_period_label_formats_sdmx_periods_in_turkish() -> None:
    from politikdesk.web.ui import format as fmt

    assert fmt.period_label("2026-06") == "Haziran 2026"
    assert fmt.period_label("2026-Q2") == "2026 2. çeyrek"
    assert fmt.period_label("2026") == "2026"
    assert fmt.period_label(None) == fmt.EMPTY
    # Tanınmayan biçim olduğu gibi döner — yanlış çevirmektense çevirme.
    assert fmt.period_label("2026-XYZ") == "2026-XYZ"


# ─────────────────────────────────────── kanal listesi ayrışma denetimi
def _api_export_formats() -> set[str]:
    """`export_event_dossier`'ın kabul ettiği `format` değerleri."""
    import typing

    from politikdesk.web.api import export_event_dossier

    hints = typing.get_type_hints(export_event_dossier)
    return set(typing.get_args(hints["format"]))


def test_every_api_export_format_is_reachable_from_the_ui() -> None:
    """API'de var olup arayüzde bağlantısı olmayan bir kanal, kullanıcı için
    YOKTUR.

    Bu test bir denetim bulgusundan doğdu: yedi kanal (x_thread, linkedin,
    instant, podcast, bluesky, mastodon, newsletter) API'de çalışıyordu ama
    olay sayfasında yalnızca üçünün bağlantısı vardı. `factsheet` bilinçli
    istisnadır — markdown dalının takma adıdır, ayrı bir çıktı değildir.
    """
    from politikdesk.web.event import EXPORT_CHANNELS

    ui_formats = {fmt for fmt, _, _, _ in EXPORT_CHANNELS}
    api_formats = _api_export_formats() - {"factsheet"}

    assert api_formats <= ui_formats, (
        "API'de olup arayuzde bagli olmayan disa aktarim bicimi: "
        f"{sorted(api_formats - ui_formats)}"
    )
    assert ui_formats <= _api_export_formats(), (
        "Arayuz API'nin tanimadigi bir bicime baglaniyor (404 uretir): "
        f"{sorted(ui_formats - _api_export_formats())}"
    )


def test_export_channel_table_has_no_duplicates_and_uses_known_icons() -> None:
    from politikdesk.web.event import EXPORT_CHANNELS
    from politikdesk.web.ui import icons

    keys = [fmt for fmt, _, _, _ in EXPORT_CHANNELS]
    assert len(keys) == len(set(keys)), f"Yinelenen kanal: {keys}"

    known = set(icons.names())
    unknown = {ic for _, _, ic, _ in EXPORT_CHANNELS if ic not in known}
    assert not unknown, f"icons.py'de olmayan ikon: {sorted(unknown)}"


def test_status_labels_have_a_single_source() -> None:
    """`web/api.py` kendi etiket tablosunu tutmamalı.

    Üç ayrı kopya vardı (SVG kartı, markdown dalı, export_formats). Kanıt
    skalasının Türkçe karşılığı ayrışırsa kullanıcı aynı iddiayı iki
    kanalda iki farklı etiketle görür.
    """
    from politikdesk.web import api as web_api
    from politikdesk.web.export_formats import STATUS_LABELS

    assert web_api.STATUS_LABELS is STATUS_LABELS
    assert "GÜÇLÜ TEYİTLİ" not in _source_of(web_api).replace(
        "from politikdesk.web.export_formats import STATUS_LABELS", ""
    ), "api.py hâlâ elle yazılmış bir kanıt etiketi taşıyor."


def _source_of(module: object) -> str:
    import inspect

    return inspect.getsource(module)  # type: ignore[arg-type]

