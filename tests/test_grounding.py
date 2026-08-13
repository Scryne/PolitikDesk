"""F3-12 — grounding doğrulayıcısı testleri.

**Kapı G3 koşul 2 bu modüle dayanır ve hedefi %0'dır** (sert kapı,
Spec §13.2). Testler iki yönü de korur:

  * Yanlış NEGATİF (kaçırılan halüsinasyon) — kapıyı anlamsız kılar
  * Yanlış POZİTİF (doğru taslağın düşmesi) — ürünü kullanılmaz kılar

Türkçe sayı ve tarih yazımının çok biçimliliği (`1.234,56` / `%41,2` /
`3,5 milyar` / `ağustosta` / `2026-Q1`) bu iki hatanın ana kaynağıdır;
her biçim için ayrı bir test vardır.
"""

from __future__ import annotations

import pytest

from politikdesk.editorial.grounding_check import (
    GroundingContext,
    build_context,
    check,
    check_draft,
)

CLAIMS = (
    "TÜİK, ağustos ayı TÜFE verisini açıkladı: aylık enflasyon yüzde 1,78 oldu.",
    "Yıllık TÜFE ağustosta yüzde 41,2 seviyesinde gerçekleşti.",
    "TCMB politika faizini yüzde 37'de sabit tuttu.",
    "Cari açık 2026 yılının ilk çeyreğinde 3,5 milyar dolar oldu.",
)
QUOTES = ('Bakan Şimşek, "dezenflasyon süreci kararlılıkla sürüyor" dedi.',)
VALUES = (
    {"metric": "tufe_monthly", "value": 1.78, "unit": "%", "period": "2026-08"},
    {"metric": "tufe_annual", "value": 41.2, "unit": "%", "period": "2026-08"},
    {"metric": "policy_rate", "value": 37, "unit": "%", "period": "2026-08"},
    {"metric": "current_account_balance", "value": 3.5, "unit": "USD",
     "period": "2026-Q1"},
)


@pytest.fixture(scope="module")
def context() -> GroundingContext:
    return build_context([*CLAIMS, *QUOTES], normalized_values=list(VALUES))


# --------------------------------------------------------------- temiz metin
@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            "TÜİK verisine göre ağustosta aylık enflasyon %1,78, yıllık %41,2 oldu.",
            id="ayni-bicim",
        ),
        pytest.param(
            "Yıllık enflasyon yüzde 41,20 seviyesinde.",
            id="ondalik-sifir-eklenmis",
        ),
        pytest.param(
            "Cari açık ilk çeyrekte 3.500.000.000 dolar oldu.",
            id="milyar-acilmis",
        ),
        pytest.param(
            "Veri 2026-08 dönemine ait; aylık TÜFE %1,78.",
            id="iso-donem",
        ),
        pytest.param(
            "Ağustos 2026'da TÜFE %41,2 oldu.",
            id="ay-yil",
        ),
        pytest.param(
            "Enflasyon beklentilerin üzerinde geldi; gevşeme sinyali yok.",
            id="sayisiz-yorum",
        ),
        pytest.param(
            'Bakan Şimşek "dezenflasyon süreci kararlılıkla sürüyor" dedi.',
            id="birebir-alinti",
        ),
    ],
)
def test_grounded_drafts_pass(context: GroundingContext, text: str) -> None:
    """Kanıta dayanan metin, biçimi farklı olsa da geçmelidir.

    Yanlış pozitif burada ölçülür: aynı sayıyı başka biçimde yazan bir
    model cezalandırılırsa kapı, ürünü kullanılmaz hâle getirir.
    """
    report = check(text, context)
    assert report.ok, [i.message for i in report.issues]


# --------------------------------------------------------- halüsinasyon
def test_invented_number_is_caught(context: GroundingContext) -> None:
    report = check(
        "Aylık enflasyon %1,78 oldu; çekirdek enflasyon ise %33,4 seviyesinde.",
        context,
    )
    assert not report.ok
    assert [i.token for i in report.issues if i.kind == "number"] == ["33,4"]


def test_invented_month_is_caught_even_when_year_matches(
    context: GroundingContext,
) -> None:
    """Kanıtta ağustos varken taslağın eylül yazması yakalanmalıdır.

    Bu gerçek bir hata olarak bulundu: küme KESİŞİMİNE bakan ilk sürüm,
    "12 Eylül 2026" ile "ağustos 2026"nın ortak belirtecini ("2026")
    görüp kabul ediyordu. Kural artık "en yüksek çözünürlük tutmalı".
    """
    report = check("TÜİK verisi 12 Eylül 2026 tarihinde açıklandı.", context)
    assert not report.ok
    assert any(i.kind == "date" and "eylul" in i.token for i in report.issues)


def test_invented_day_is_caught_when_evidence_has_only_month(
    context: GroundingContext,
) -> None:
    """Kanıt ay düzeyindeyken gün uydurmak kanıt dışıdır."""
    report = check("Veri 12 Ağustos 2026'da açıklandı.", context)
    assert not report.ok
    assert any(i.kind == "date" for i in report.issues)


def test_fabricated_quote_is_caught(context: GroundingContext) -> None:
    report = check(
        'Bakan Şimşek "faiz indirimi eylülde başlayacak" açıklamasını yaptı.',
        context,
    )
    assert not report.ok
    assert any(i.kind == "quote" for i in report.issues)


def test_derived_arithmetic_is_caught(context: GroundingContext) -> None:
    """Model kendi hesabını yaparsa yakalanmalı.

    "41,2 - 1,78 = 39,42" gibi bir türetme kanıtta yoktur; promptta
    yasaklıdır ama yasak tek başına savunma değildir (Spec §11.5).
    """
    report = check("Aradaki fark 39,42 puan.", context)
    assert not report.ok
    assert [i.token for i in report.issues] == ["39,42"]


# ------------------------------------------------------------- sınır durumlar
def test_empty_context_flags_every_number() -> None:
    """Kanıt evreni boşken sayı içeren taslağın tamamı işaretlenir.

    Bu duruma normalde gelinmez (F3-11 kapısı engeller); gelinirse
    sessizce geçmemelidir.
    """
    report = check("Enflasyon %41,2 oldu.", build_context([]))
    assert not report.ok


def test_single_word_quote_is_not_treated_as_citation(
    context: GroundingContext,
) -> None:
    """Tek kelimelik vurgu tırnağı alıntı sayılmaz.

    Hem yaygın bir üslup aracıdır hem de tek kelime kanıtta neredeyse
    her zaman geçer; denetleyici değeri sıfırdır ve yanlış pozitif
    üretir.
    """
    report = check('TCMB faizi "sabit" tuttu; oran %37.', context)
    assert report.quotes_checked == 0
    assert report.ok


def test_identifiers_are_not_treated_as_data(context: GroundingContext) -> None:
    """Harfe bitişik rakam veri değil, tanımlayıcıdır.

    Kıyaslama koşumunda gerçek bir yanlış pozitif olarak yakalandı: bir
    model iddia referansını gövdeye yazdı ("...öngörüyor (C1)") ve
    denetim bunu "kanıtta bulunmayan sayı: 1" diye işaretledi. Teşhis
    yanlıştı; referansın gövdede olmaması gerektiğini söyleyen kontrol
    F3-13'tür, grounding değil.
    """
    report = check("TCMB faizi %37'de tuttu (C1). BIST100 endeksi izleniyor.", context)
    assert report.ok, [i.message for i in report.issues]


def test_number_after_punctuation_is_still_checked(context: GroundingContext) -> None:
    """Muafiyet yalnızca HARFE bitişik rakam içindir."""
    assert not check("Oran %88,8 oldu.", context).ok
    assert not check("Değer (77,7) olarak açıklandı.", context).ok


def test_check_draft_helper_matches_manual_context() -> None:
    report = check_draft(
        "TCMB politika faizini yüzde 37'de sabit tuttu.",
        claim_texts=list(CLAIMS),
        quote_spans=list(QUOTES),
        normalized_values=list(VALUES),
    )
    assert report.ok
    assert report.numbers_checked == 1


def test_report_serialises_for_storage(context: GroundingContext) -> None:
    """`drafts.grounding_result` JSONB'ye yazılabilir olmalı."""
    import json

    report = check("Enflasyon %99,9 oldu.", context)
    payload = report.as_dict()
    assert json.loads(json.dumps(payload, ensure_ascii=False))["ok"] is False
    assert payload["issues"][0]["kind"] == "number"
    assert payload["checker_version"].startswith("grounding-check@")
