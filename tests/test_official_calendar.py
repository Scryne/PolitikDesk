"""Ulusal Veri Yayımlama Takvimi testleri (F2-18 · Roadmap Faz 1.2).

Ayrıştırma testleri **fixture tabanlıdır** (ağa çıkmaz); veritabanına
dokunanlar `db` işaretlidir.

Korunan sözleşme:
  1. HTTP 200 + HTML -> İSTİSNA (sessiz sıfır kayıt DEĞİL)
  2. Kimlik kaynağın `id`'sinden TÜRETİLMEZ — o alan benzersiz değil
  3. Saat dilimi Türkiye yereli varsayılır, UTC değil
  4. `occurred` durumu takvim turu tarafından geri alınamaz
  5. Kurum filtresi bilinçli ve dar
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from politikdesk.context.official_calendar import (
    CALENDAR_TZ,
    DEFAULT_INSTITUTIONS,
    PENDING_KEY,
    PUBLISHED_KEY,
    CalendarEntry,
    CalendarFetchError,
    build_external_id,
    parse_payload,
)


def _row(
    *,
    adi: str = "Tüketici Fiyat Endeksi",
    kurum: str = "TÜİK",
    gTarih: str = "2026-08-19T10:00:00",
    donemi: str | None = "Temmuz 2026",
    kayit_id: Any = 1234,
    link: str | None = "https://data.tuik.gov.tr/Bulten/Index?p=1",
) -> dict[str, Any]:
    return {
        "adi": adi,
        "sorumluKisaAd": kurum,
        "sorumluKurum": "Türkiye İstatistik Kurumu",
        "gTarih": gTarih,
        "donemi": donemi,
        "id": kayit_id,
        "link": link,
        "birimi": None,
        "dilId": 1,
    }


def _payload(yayimlanan: list[dict[str, Any]], bekleyen: list[dict[str, Any]]) -> str:
    return json.dumps({PUBLISHED_KEY: yayimlanan, PENDING_KEY: bekleyen}, ensure_ascii=False)


# ═════════════════════════════════ 1. HTML kabuğu — sessiz arıza koruması
def test_html_body_raises_instead_of_returning_zero_entries() -> None:
    """HTTP 200 + HTML **başarı değildir.**

    Bu depo aynı sessiz arızayı üç kez yaşadı: B-42 (TÜİK portalı),
    B-43 (Hazine duyuruları) ve EVDS'nin anahtarsız yanıtı. Üçünde de uç
    200 döndürüyor, gövde HTML, adaptör 0 öğe üretiyor ve tur "başarılı"
    görünüyor.
    """
    with pytest.raises(CalendarFetchError, match="HTML"):
        parse_payload("<!DOCTYPE html>\n<html><body>JS gerekli</body></html>")


def test_empty_and_malformed_bodies_raise() -> None:
    with pytest.raises(CalendarFetchError, match="boş gövde"):
        parse_payload("   ")
    with pytest.raises(CalendarFetchError, match="JSON"):
        parse_payload("{bozuk")
    with pytest.raises(CalendarFetchError, match="beklenen liste"):
        parse_payload(json.dumps({"baskaAlan": []}))


def test_missing_one_of_the_two_lists_raises() -> None:
    """İki liste de zorunlu: biri yoksa 'beklenen/gerçekleşen' ayrımı çöker."""
    with pytest.raises(CalendarFetchError, match="beklenen liste"):
        parse_payload(json.dumps({PUBLISHED_KEY: []}))


# ═══════════════════ 2. kimlik — kaynağın `id`'si benzersiz DEĞİL (regresyon)
def test_entries_sharing_one_source_id_are_kept_separate() -> None:
    """**Ölçülmüş bir veri kaybının regresyon testi.**

    19 Ağustos 2026: bekleyen listede 1.537 kayıt, yalnızca 1.388 tekil
    `id`. Fark tamamen TÜİK'ten geliyordu — 150 bekleyen yayının HEPSİ
    aynı `id`'yi taşıyor, oysa hepsi farklı yayın.

    İlk uygulamada kimlik `id`'den türetiliyordu ve benzersizlik kısıtı
    bu 150 kaydı **sessizce tek satıra indirdi**: veritabanında TÜİK'in
    hiç bekleyen yayını görünmüyordu.
    """
    bekleyen = [
        _row(
            adi="Tüketici Güven Endeksi",
            donemi="Aralık 2026",
            gTarih="2026-12-21T10:00:00",
            kayit_id=0,
        ),
        _row(
            adi="Dış Ticaret İstatistikleri",
            donemi="Kasım 2026",
            gTarih="2026-12-31T10:00:00",
            kayit_id=0,
        ),
        _row(
            adi="İşgücü İstatistikleri",
            donemi="Kasım 2026",
            gTarih="2026-12-30T10:00:00",
            kayit_id=0,
        ),
    ]
    entries = parse_payload(_payload([], bekleyen))

    assert len(entries) == 3
    assert len({e.external_id for e in entries}) == 3, (
        "Ayni `id`'yi paylasan farkli yayinlar tek kimlige indirgenmis — "
        "veritabaninda 150 kayit boyle kaybolmustu."
    )


def test_same_publication_keeps_a_stable_id_across_runs() -> None:
    """Idempotency'nin dayanağı: aynı yayın her turda aynı kimliği almalı."""
    satir = _row()
    ilk = parse_payload(_payload([], [satir]))[0]
    ikinci = parse_payload(_payload([], [satir]))[0]
    assert ilk.external_id == ikinci.external_id


def test_rescheduled_publication_keeps_its_identity() -> None:
    """Ertelenen yayın AYNI kayıt olmalı, ikinci bir satır doğmamalı.

    Bir yayının kimliği "hangi kurum, neyi, hangi dönem için yayımlıyor"
    sorusudur; tarih bunun bir özniteliğidir, parçası değil.
    """
    once = _row(gTarih="2026-08-19T10:00:00")
    sonra = _row(gTarih="2026-08-21T14:00:00")
    assert (
        parse_payload(_payload([], [once]))[0].external_id
        == parse_payload(_payload([], [sonra]))[0].external_id
    )


def test_publications_differing_only_by_period_get_distinct_ids() -> None:
    """Aynı yayının iki dönemi ayrı kayıttır (Temmuz TÜFE ≠ Ağustos TÜFE)."""
    a = parse_payload(_payload([], [_row(donemi="Temmuz 2026")]))[0]
    b = parse_payload(_payload([], [_row(donemi="Ağustos 2026")]))[0]
    assert a.external_id != b.external_id


def test_missing_period_falls_back_to_the_date_for_identity() -> None:
    a = build_external_id(
        "TÜİK", "Günlük İstatistik", None, datetime(2026, 8, 19, tzinfo=CALENDAR_TZ)
    )
    b = build_external_id(
        "TÜİK", "Günlük İstatistik", None, datetime(2026, 8, 20, tzinfo=CALENDAR_TZ)
    )
    assert a != b


# ═════════════════════════════════════════════════ 3. saat dilimi
def test_naive_timestamps_are_read_as_istanbul_local_not_utc() -> None:
    """Uç saat dilimi bildirmiyor; UTC varsayılsaydı her yayım 3 saat kayardı.

    `scheduler_match` ±3 saatlik pencerede çalışıyor — tam sınırda bir
    kayma, eşleşmeleri rastgele tutturur, rastgele kaçırırdı.
    """
    (entry,) = parse_payload(_payload([], [_row(gTarih="2026-08-19T10:00:00")]))
    assert entry.expected_at.tzinfo is not None
    assert entry.expected_at.utcoffset() == timedelta(hours=3)
    assert entry.expected_at.astimezone(ZoneInfo("UTC")).hour == 7


def test_unparseable_date_is_dropped_not_guessed() -> None:
    """Yanlış tarihli bir takvim kaydı, kayıt olmamasından kötüdür."""
    entries = parse_payload(_payload([], [_row(gTarih="19.08.2026"), _row()]))
    assert len(entries) == 1


# ═══════════════════════════════════ 4. yayımlanan / bekleyen ayrımı
def test_published_and_pending_are_distinguished_by_list_membership() -> None:
    """Ayrımı KURUM yapıyor; biz çıkarım yapmıyoruz.

    Bu, gecikme metriğini tahmine dayanmaktan kurtarır (Roadmap 1.2).
    """
    entries = parse_payload(
        _payload(
            [_row(adi="Yayımlanan", donemi="Haziran 2026")],
            [_row(adi="Bekleyen", donemi="Temmuz 2026")],
        )
    )
    yayimlanan = next(e for e in entries if e.title == "Yayımlanan")
    bekleyen = next(e for e in entries if e.title == "Bekleyen")

    assert yayimlanan.is_published and yayimlanan.published_at is not None
    assert not bekleyen.is_published and bekleyen.published_at is None


def test_entries_are_sorted_by_expected_time() -> None:
    entries = parse_payload(
        _payload(
            [],
            [
                _row(adi="Sonra", gTarih="2026-08-20T10:00:00", donemi="A"),
                _row(adi="Once", gTarih="2026-08-19T10:00:00", donemi="B"),
            ],
        )
    )
    assert [e.title for e in entries] == ["Once", "Sonra"]


# ═════════════════════════════════════════════════ 5. kurum filtresi
def test_institution_filter_is_applied_and_deliberately_narrow() -> None:
    """Filtresiz 31 kurumun 4.085 kaydı girerdi ve takvim okunamaz olurdu."""
    entries = parse_payload(
        _payload(
            [],
            [
                _row(kurum="TÜİK"),
                _row(kurum="KTB", adi="Turizm"),
                _row(kurum="UAB", adi="Ulaştırma"),
            ],
        )
    )
    assert [e.institution for e in entries] == ["TÜİK"]


def test_explicit_institution_set_overrides_the_default() -> None:
    entries = parse_payload(
        _payload([], [_row(kurum="TÜİK"), _row(kurum="KTB", adi="Turizm")]),
        institutions=frozenset({"KTB"}),
    )
    assert [e.institution for e in entries] == ["KTB"]


def test_default_institutions_cover_the_macro_vertical() -> None:
    """Ürünün dikeyindeki kurumlar filtrede bulunmalı."""
    for kurum in ("TÜİK", "TCMB", "HMB"):
        assert kurum in DEFAULT_INSTITUTIONS


# ═══════════════════════════════════════════════════ 6. veritabanı
@pytest.mark.db
def test_upsert_is_idempotent_and_preserves_matched_events(db_conn) -> None:  # noqa: ANN001
    """`occurred` bir KAZANIMDIR: boru hattımız olayı gerçekten gördü.

    Takvim turu 30 dakikada bir koşuyor; eşleştirmeyi ezseydi
    `scheduler_match`'in kurduğu bağ her turda silinir ve olay-takvim
    ilişkisi hiç kalıcı olmazdı.
    """
    from politikdesk.context.official_calendar import upsert_entries

    entry = CalendarEntry(
        external_id="pytest-takvim:kalicilik",
        title="pytest Takvim Kaydı",
        institution="TÜİK",
        institution_full="Türkiye İstatistik Kurumu",
        expected_at=datetime(2026, 8, 19, 10, 0, tzinfo=CALENDAR_TZ),
        reference_period="Temmuz 2026",
        url="https://example.test/bulten",
        is_published=False,
    )

    try:
        ilk = upsert_entries([entry])
        assert ilk["inserted"] == 1

        ikinci = upsert_entries([entry])
        assert ikinci["inserted"] == 0 and ikinci["updated"] == 1

        # Eşleştirme kurulmuş gibi davran, sonra takvim turunu tekrar koş.
        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE scheduled_events SET status = 'occurred' WHERE external_id = %s",
                (entry.external_id,),
            )

        upsert_entries([entry])

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM scheduled_events WHERE external_id = %s",
                (entry.external_id,),
            )
            assert cur.fetchone()["status"] == "occurred", (
                "Takvim turu `occurred` durumunu ezmis — eslesme her turda silinir."
            )
    finally:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM scheduled_events WHERE external_id LIKE 'pytest-takvim:%'")


@pytest.mark.db
def test_expected_on_answers_the_roadmap_question(db_conn) -> None:  # noqa: ANN001
    """Roadmap 1.2 çıkış ölçütü: "Bugün hangi resmî veri bekleniyor?" """
    from politikdesk.context.official_calendar import expected_on, upsert_entries

    gun = datetime(2026, 8, 19, 10, 0, tzinfo=CALENDAR_TZ)
    entry = CalendarEntry(
        external_id="pytest-takvim:bugun",
        title="pytest Günlük Yayın",
        institution="TCMB",
        institution_full="Türkiye Cumhuriyet Merkez Bankası",
        expected_at=gun,
        reference_period="Temmuz 2026",
        url=None,
        is_published=False,
    )
    try:
        upsert_entries([entry])
        satirlar = expected_on(gun.date())
        assert any(r["title"] == "pytest Günlük Yayın" for r in satirlar)

        # Kurum filtresi
        assert not [
            r
            for r in expected_on(gun.date(), institution="TÜİK")
            if r["title"] == "pytest Günlük Yayın"
        ]
    finally:
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM scheduled_events WHERE external_id LIKE 'pytest-takvim:%'")


def test_calendar_module_does_not_import_llm() -> None:
    """⛔ Takvim bir beklentidir, bir yargı değil — LLM'e ihtiyacı yoktur.

    Denetim AST üzerinden yapılır, ham metin üzerinden değil: yasağı
    ANLATAN docstring, yasağın ihlali değildir. Aynı gerekçe
    `tests/test_design_tokens.py::_emittable_strings` içinde de yazılı.
    """
    import ast
    import inspect

    from politikdesk.context import official_calendar

    agac = ast.parse(inspect.getsource(official_calendar))
    moduller: set[str] = set()
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            moduller |= {a.name for a in dugum.names}
        elif isinstance(dugum, ast.ImportFrom) and dugum.module:
            moduller.add(dugum.module)

    yasakli = {m for m in moduller if m.startswith("politikdesk.llm")}
    assert not yasakli, f"Takvim modulu LLM import ediyor: {sorted(yasakli)}"


# ═══════════════════════ 7. takvim ↔ eşleştirici bütünleşmesi (regresyon)
def test_matcher_considers_published_records_not_only_pending() -> None:
    """Takvimden gelen `published` kayıtlar eşleştiriciyi GÖRMELİ.

    **Ölçülmüş bir boşluğun regresyon testi.** Ulusal Veri Yayımlama
    Takvimi, kurumun zaten yayımladığı kayıtları `published` olarak
    getiriyor. `match_pending` yalnızca `status='pending'` tarıyordu;
    canlı ölçümde 286 yayımlanmış kaydın hepsi `eslesen=0` ile duruyordu.
    Ürünün en değerli sorusu — "kurum açıkladı, biz gördük mü?" — o
    hâliyle hiç sorulamıyordu. Düzeltmeden sonra 243 eşleşme kuruldu.
    """
    import inspect

    from politikdesk.context import scheduler_match

    kaynak = inspect.getsource(scheduler_match.match_pending)
    assert "IN ('pending', 'published')" in kaynak, (
        "Eslestirici yine yalnizca `pending` tariyor — takvimden gelen "
        "yayimlanmis kayitlar eslestirilmez."
    )


def test_published_records_are_never_auto_cancelled() -> None:
    """`cancelled` "beklenen şey hiç olmadı" demektir.

    Bir `published` kaydı için bu yanlıştır: kurum yayımladı, BİZ
    görmedik. İkisi karıştırılırsa `missed_report` — kaynak kadrosundaki
    kör noktayı gösteren tek sinyal — 48 saat sonra sessizce silinir.
    """
    import inspect

    from politikdesk.context import scheduler_match

    kaynak = inspect.getsource(scheduler_match.match_pending)
    assert 'item["status"] == "pending"' in kaynak, (
        "Iptal dali durum ayrimi yapmiyor; yayimlanmis kayitlar da "
        "iptal edilir ve kacirilan yayin sinyali kaybolur."
    )


def test_matcher_query_types_the_nullable_source_parameter() -> None:
    """`source_id` NULL olabilir ve tipsiz NULL parametresi PostgreSQL'de
    `IndeterminateDatatype` fırlatır.

    Hata gizliydi: o güne dek tüm takvim kayıtları elle girilmişti ve
    hepsinin kaynağı vardı. Ulusal takvimdeki 31 kurumun çoğu `sources`
    tablosunda yok — ilk gerçek NULL geldiğinde eşleştirme turu komple
    çöktü.
    """
    import inspect

    from politikdesk.context import scheduler_match

    kaynak = inspect.getsource(scheduler_match.match_pending)
    assert "%s::bigint IS NULL" in kaynak, (
        "Nullable `source_id` parametresi tiplenmemis — takvim kayitlarinda "
        "eslestirme turu IndeterminateDatatype ile duser."
    )
