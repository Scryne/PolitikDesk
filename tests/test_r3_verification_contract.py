"""R3 resmî doğrulama sözleşmesi — 20 Ağustos 2026 denetimi.

**Bu dosya SÖZLEŞMEYİ korur, implementasyonu değil.** Test adları
"hangi fonksiyon çağrılıyor"u değil, *"hangi koşulda doğrulama olur /
olmaz"*ı anlatır.

Denetimde ölçülen boşluk: `_verified_against_official` `metric` +
`period` + `value` üçlüsüne bakıyor, `unit`'i hiç okumuyordu. Yani
"yüzde 48,9" ile "48,9 kişi" aynı resmî değer sayılıyordu.

Aktif arıza değildi (üretimdeki iki 🟢'nin dört alanı da eşleşiyor) ama
yol gerçekti: `other` yakalama-hepsi metriğini 53 iddia kullanıyor ve
birimleri `TL`/`%`/`USD` diye karışık.
"""

from __future__ import annotations

from typing import Any

import pytest

from politikdesk.evidence.pipeline import _verified_against_official


class _TekSatirCursor:
    """Kanıt kümesinde tek bir resmî değer varmış gibi davranır."""

    def __init__(self, *official: dict[str, Any] | None) -> None:
        self._rows = [{"official_value": o} for o in official if o is not None]

    def execute(self, *args: Any, **kwargs: Any) -> None:
        return None

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


def _dogrula(official: dict[str, Any] | None, claim: dict[str, Any] | None) -> bool:
    return _verified_against_official(_TekSatirCursor(official), 1, claim)


# TÜİK'in gerçek üretim kaydı (articles.official_value, 20 Ağu 2026).
TUIK_ISSIZLIK = {"metric": "unemployment_rate", "value": 7.6, "unit": "%", "period": "2026-06"}
# EVDS'in gerçek üretim kaydı — `series_code` taşır, birimi doludur.
EVDS_KUR = {
    "metric": "exchange_rate",
    "value": 47.8293,
    "unit": "TRY",
    "period": "2026-08-19",
    "series_code": "TP.DK.USD.A.YTL",
}
# EVDS'in birimi BOŞ bıraktığı gerçek kayıt.
EVDS_REZERV = {"metric": "reserves", "value": 208670.9, "unit": "", "period": "2026-05"}


# ════════════════════════════════════════════════ olumlu yol (regresyon)


def test_claim_is_verified_when_metric_value_unit_and_period_all_match() -> None:
    """Üretimdeki iki 🟢'nin dayandığı yol — kırılmamalı."""
    assert _dogrula(TUIK_ISSIZLIK, dict(TUIK_ISSIZLIK)) is True


def test_claim_is_verified_despite_floating_point_noise() -> None:
    """48,9 ile 48,89999999 aynı sayıdır."""
    iddia = {**TUIK_ISSIZLIK, "value": 7.599999999}
    assert _dogrula(TUIK_ISSIZLIK, iddia) is True


# ═══════════════════════════════════════════ fail-closed: alan uyuşmazlığı


def test_claim_is_not_verified_when_official_metric_differs() -> None:
    assert _dogrula(TUIK_ISSIZLIK, {**TUIK_ISSIZLIK, "metric": "employment_rate"}) is False


def test_claim_is_not_verified_when_official_value_differs() -> None:
    assert _dogrula(TUIK_ISSIZLIK, {**TUIK_ISSIZLIK, "value": 7.7}) is False


def test_claim_is_not_verified_when_official_period_differs() -> None:
    """Aynı metrik ve aynı sayı, FARKLI dönem — doğrulama değildir.

    İşsizlik ocakta da temmuzda da %7,6 olabilir; dönem eşleşmezse
    bu iki ayrı olgudur.
    """
    assert _dogrula(TUIK_ISSIZLIK, {**TUIK_ISSIZLIK, "period": "2026-01"}) is False


def test_claim_is_not_verified_when_period_format_differs() -> None:
    """`2026-6` ile `2026-06` eşleşmez — dönem normalizasyonu yoktur."""
    assert _dogrula(TUIK_ISSIZLIK, {**TUIK_ISSIZLIK, "period": "2026-6"}) is False


@pytest.mark.parametrize("eksik", ["metric", "value", "period"])
def test_claim_is_not_verified_when_a_required_field_is_missing(eksik: str) -> None:
    iddia = {k: v for k, v in TUIK_ISSIZLIK.items() if k != eksik}
    assert _dogrula(TUIK_ISSIZLIK, iddia) is False


def test_claim_is_not_verified_without_any_official_value() -> None:
    assert _dogrula(None, dict(TUIK_ISSIZLIK)) is False


def test_claim_without_normalized_value_is_not_verified() -> None:
    assert _dogrula(TUIK_ISSIZLIK, None) is False


# ═══════════════════════════════════════════════ BULGU: birim kısıtı


@pytest.mark.parametrize("iddia_birimi", ["kisi", "oran", "TL", "USD", "puan"])
def test_claim_is_not_verified_when_official_unit_differs(iddia_birimi: str) -> None:
    """**Denetimin kapattığı boşluk.**

    `metric`, `period` ve `value` aynı iken birim farklıysa doğrulama
    OLMAMALI: "yüzde 48,9" ile "48,9 kişi" aynı olgu değildir.

    Düzeltmeden önce bu senaryo `True` dönüyordu.
    """
    assert _dogrula(TUIK_ISSIZLIK, {**TUIK_ISSIZLIK, "unit": iddia_birimi}) is False


def test_unit_comparison_ignores_case_and_whitespace() -> None:
    """Birim kısıtı biçime değil ANLAMA bakar."""
    assert _dogrula(TUIK_ISSIZLIK, {**TUIK_ISSIZLIK, "unit": " % "}) is True
    assert _dogrula(EVDS_KUR, {**EVDS_KUR, "unit": "try"}) is True


def test_turkish_lira_is_the_same_unit_as_try() -> None:
    """EVDS serisi `TRY` yazar, Türkçe haber metni `TL` der.

    Bunları ayrı saymak MEŞRU bir doğrulamayı engellerdi.
    """
    assert _dogrula(EVDS_KUR, {**EVDS_KUR, "unit": "TL"}) is True


# ══════════════════════════════ eksik birim: BİLİNÇLİ olarak fail-open


def test_missing_unit_does_not_block_verification() -> None:
    """Birim yoksa kısıt UYGULANAMAZ — "yanlış" demek değildir.

    Gerçek veride EVDS'in `reserves` ve `other` kayıtlarının birimi
    boştur. Eksik birimde reddetmek, bugün doğru çalışan doğrulamaları
    sebepsiz kırardı. Aynı ayrım `_entity_check`'in `inconclusive`
    sonucunda da vardır: kanıt yokluğu, çelişki kanıtı değildir.
    """
    # Resmî tarafta birim boş (gerçek EVDS kaydı)
    assert _dogrula(EVDS_REZERV, {**EVDS_REZERV, "unit": "milyon USD"}) is True
    # İddia tarafında birim yok
    iddia = {k: v for k, v in TUIK_ISSIZLIK.items() if k != "unit"}
    assert _dogrula(TUIK_ISSIZLIK, iddia) is True


def test_missing_unit_still_requires_metric_period_and_value() -> None:
    """Birim eksikliği diğer kısıtları GEVŞETMEZ."""
    iddia = {k: v for k, v in TUIK_ISSIZLIK.items() if k != "unit"}
    assert _dogrula(TUIK_ISSIZLIK, {**iddia, "period": "2026-01"}) is False
    assert _dogrula(TUIK_ISSIZLIK, {**iddia, "value": 9.9}) is False


# ══════════════════════════════════ gerçek üretim biçimleri (regresyon)


def test_real_tuik_record_shape_verifies() -> None:
    """TÜİK SDMX kaydı `series_code` taşımaz; doğrulama yine çalışır."""
    assert "series_code" not in TUIK_ISSIZLIK
    assert _dogrula(TUIK_ISSIZLIK, dict(TUIK_ISSIZLIK)) is True


def test_real_evds_record_shape_verifies() -> None:
    """EVDS kaydı `series_code` taşır; fazladan alan doğrulamayı bozmaz."""
    iddia = {k: v for k, v in EVDS_KUR.items() if k != "series_code"}
    assert _dogrula(EVDS_KUR, iddia) is True


def test_verification_scans_all_supporting_official_values() -> None:
    """Kanıt kümesinde birden çok resmî kayıt varsa hepsi taranır."""
    cur = _TekSatirCursor(EVDS_REZERV, TUIK_ISSIZLIK)
    assert _verified_against_official(cur, 1, dict(TUIK_ISSIZLIK)) is True


# ══════════════════════════ semantik izolasyon: ölçüm ≠ beklenti
#
# `metric` bir gösterge AİLESİDİR. `TP.ENFBEK.PKA12ENF` "12 ay sonrası
# enflasyon BEKLENTİSİ"dir (piyasa anketi) ama `metric="tufe_annual"`
# taşır — yani gerçekleşmiş yıllık TÜFE ile aynı ad.
#
# Karşı-olgusal ölçüldü: düzeltme öncesi, gerçekleşmiş enflasyon iddiası
# değeri ve dönemi tutunca bu beklenti serisiyle DOĞRULANIYORDU.

# Gerçek üretim kaydı (articles.official_value, 20 Ağu 2026).
EVDS_BEKLENTI = {
    "metric": "tufe_annual",
    "value": 23.95,
    "unit": "%",
    "period": "2026-07",
    "series_code": "TP.ENFBEK.PKA12ENF",
}
# Sistemde henüz yok; gerçekleşmiş TÜFE serisi eklenirse böyle görünür.
EVDS_GERCEKLESMIS = {**EVDS_BEKLENTI, "series_code": "TP.FG.J0", "semantic": "measurement"}


def test_claim_is_not_verified_against_an_expectation_series() -> None:
    """**Bir anket beklentisi, olmuş bir olguyu doğrulayamaz.**

    R3'ün verdiği 🟢 ürünün en güçlü etiketidir; beklentiyle doğrulamak
    tam anlamıyla lastik damga olurdu.
    """
    iddia = {k: v for k, v in EVDS_BEKLENTI.items() if k != "series_code"}
    assert _dogrula(EVDS_BEKLENTI, iddia) is False


def test_expectation_series_is_rejected_even_without_a_semantic_field() -> None:
    """Eski kayıtlar `semantic` alanı taşımaz — `series_code` yetmeli.

    Veritabanında hâlihazırda duran kayıt bu biçimdedir; migration
    gerekmeden kapsanmalıdır.
    """
    assert "semantic" not in EVDS_BEKLENTI
    iddia = {k: v for k, v in EVDS_BEKLENTI.items() if k != "series_code"}
    assert _dogrula(EVDS_BEKLENTI, iddia) is False


def test_expectation_series_is_rejected_when_semantic_field_says_so() -> None:
    """Yeni kayıtlarda beyan doğrudan okunur."""
    kayit = {**EVDS_BEKLENTI, "semantic": "expectation"}
    iddia = {k: v for k, v in kayit.items() if k not in ("series_code", "semantic")}
    assert _dogrula(kayit, iddia) is False


def test_measurement_series_still_verifies() -> None:
    """Semantik kısıt DOĞRU serileri düşürmemeli."""
    iddia = {k: v for k, v in EVDS_GERCEKLESMIS.items() if k not in ("series_code", "semantic")}
    assert _dogrula(EVDS_GERCEKLESMIS, iddia) is True


def test_expectation_is_filtered_before_ambiguity_check() -> None:
    """Beklenti elenince geriye tek ölçüm serisi kalır — belirsizlik yok.

    Yani semantik kısıt, seri belirsizliği kısıtını gereksiz yere
    tetiklemez; ikisi birlikte doğru çalışır.
    """
    cur = _TekSatirCursor(EVDS_BEKLENTI, EVDS_GERCEKLESMIS)
    iddia = {k: v for k, v in EVDS_GERCEKLESMIS.items() if k not in ("series_code", "semantic")}
    assert _verified_against_official(cur, 1, iddia) is True


def test_tuik_records_without_series_code_are_treated_as_measurements() -> None:
    """TÜİK SDMX kayıtları `series_code` taşımaz ve hepsi gerçekleşmiş veridir.

    Burada fail-open bilinçlidir: aksi hâlde üretimdeki iki R3 🟢'si
    sebepsiz kırılırdı.
    """
    assert "series_code" not in TUIK_ISSIZLIK
    assert "semantic" not in TUIK_ISSIZLIK
    assert _dogrula(TUIK_ISSIZLIK, dict(TUIK_ISSIZLIK)) is True


def test_expectation_series_list_is_derived_from_source_config() -> None:
    """Liste elle tutulmaz; kaynak yapılandırmasından türetilir."""
    from politikdesk.evidence.pipeline import _non_measurement_series
    from politikdesk.ingestion.adapters.evds import TRACKED

    kodlar = _non_measurement_series()
    assert "TP.ENFBEK.PKA12ENF" in kodlar
    beklenen = {s.code for s in TRACKED if s.semantic != "measurement"}
    assert kodlar == beklenen
    # Ölçüm serileri listede OLMAMALI.
    assert "TP.DK.USD.A.YTL" not in kodlar


def test_evds_expectation_series_declares_its_semantic() -> None:
    """Kaynak tarafı ne yayımladığını BEYAN etmeli (kod sözleşmesi)."""
    from politikdesk.ingestion.adapters.evds import TRACKED

    beklenti = [s for s in TRACKED if s.code == "TP.ENFBEK.PKA12ENF"]
    assert beklenti, "Beklenti serisi yapılandırmadan kalkmış"
    assert beklenti[0].semantic == "expectation"
    # Geri kalan her seri varsayılan olarak ölçümdür.
    assert all(s.semantic == "measurement" for s in TRACKED if s.code != "TP.ENFBEK.PKA12ENF")


# ═══════════════════════════════════ seri belirsizliği: fail-closed
#
# Bir metrik birden çok resmî SERİYE karşılık gelebilir. EVDS'te
# `exchange_rate` altında hem USD hem EUR serisi vardır ve ikisi de aynı
# `unit` (TRY) ve `period` ile gelir; ayıran tek alan `series_code`'dur.
# İddia şemasında böyle bir alan YOKTUR.


def test_claim_is_verified_when_its_value_identifies_exactly_one_series() -> None:
    """Değer tek seriyi belirliyorsa doğrulama SAĞLAMDIR.

    USD 47,8293 ile EUR 55,366 farklı sayılardır; iddia 47,8293 diyorsa
    USD serisini kastettiği değerin kendisinden bellidir.
    """
    evds_eur = {**EVDS_KUR, "value": 55.366, "series_code": "TP.DK.EUR.A.YTL"}
    iddia_usd = {k: v for k, v in EVDS_KUR.items() if k != "series_code"}
    cur = _TekSatirCursor(EVDS_KUR, evds_eur)
    assert _verified_against_official(cur, 1, iddia_usd) is True


def test_claim_is_not_verified_when_its_value_matches_two_different_series() -> None:
    """**Belirsizlik doğrulama değildir.**

    İki seri aynı `metric`+`unit`+`period` ile AYNI değeri taşıyorsa,
    iddianın hangisini kastettiği bilinemez. Rastgele birini seçmek
    yerine fail-closed davranılır.
    """
    usd = {**EVDS_KUR, "series_code": "TP.DK.USD.A.YTL"}
    eur = {**EVDS_KUR, "series_code": "TP.DK.EUR.A.YTL"}  # aynı değer
    iddia = {k: v for k, v in EVDS_KUR.items() if k != "series_code"}
    cur = _TekSatirCursor(usd, eur)
    assert _verified_against_official(cur, 1, iddia) is False


def test_duplicate_records_without_series_code_still_verify() -> None:
    """`series_code` taşımayan iki AYNI kayıt belirsizlik değildir.

    TÜİK kayıtlarında `series_code` yoktur; aynı gözlemin iki kez kanıt
    kümesine girmesi doğrulamayı düşürmemeli.
    """
    cur = _TekSatirCursor(dict(TUIK_ISSIZLIK), dict(TUIK_ISSIZLIK))
    assert _verified_against_official(cur, 1, dict(TUIK_ISSIZLIK)) is True


def test_ambiguity_check_does_not_weaken_other_constraints() -> None:
    """Seri kısıtı diğer kısıtları GEVŞETMEZ."""
    usd = {**EVDS_KUR, "series_code": "TP.DK.USD.A.YTL"}
    iddia = {k: v for k, v in EVDS_KUR.items() if k != "series_code"}
    assert _verified_against_official(_TekSatirCursor(usd), 1, {**iddia, "period": "2026-01-01"}) is False
    assert _verified_against_official(_TekSatirCursor(usd), 1, {**iddia, "unit": "USD"}) is False


def test_wrong_series_value_does_not_verify_when_unit_or_value_differs() -> None:
    """EUR ve USD serisi aynı `metric`+`unit`+`period` taşır (gerçek veri).

    Bugün ayıran tek şey DEĞERDİR: 47,8293 (USD) ≠ 55,366 (EUR).
    Bu test o ayrımın çalıştığını kilitler.

    ⚠ Bilinen sınır: iddia yanlış seriyi kastedip DOĞRU seriyi eşleştiren
    bir değer taşırsa sözleşme bunu ayırt edemez — `series_code` iddia
    şemasında yoktur. Denetimde ölçüldü: bugün `exchange_rate` metrikli
    iddia YOK ve aynı `metric`+`period`i taşıyan iki resmî kaydı bir arada
    gören iddia da YOK. Dormant olarak kayda geçti
    (docs/ARASTIRMA-R3-VERIFICATION-CONTRACT-2026-08-20.md).
    """
    evds_eur = {**EVDS_KUR, "value": 55.366, "series_code": "TP.DK.EUR.A.YTL"}
    iddia_usd_degeri = {k: v for k, v in EVDS_KUR.items() if k != "series_code"}
    assert _dogrula(evds_eur, iddia_usd_degeri) is False
