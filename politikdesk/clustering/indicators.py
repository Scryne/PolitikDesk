"""Gösterge (indicator) ayırıcısı — B-62.

**Neden var.** `docs/FAZ2-DURUM.md` bulgu 3: kalan kümeleme precision
açığının tamamı tek bir hata ailesinden geliyordu — *aynı kurumun aynı
gün yayımladığı farklı göstergeler.* TÜİK bir sabah hem sanayi üretimini
hem dış ticaret endekslerini açıklar; iki metin de "TÜİK", "haziran",
"endeks", "açıkladı" der, varlıkları aynıdır, gömme uzayında komşudur.
Benzerlik ve varlık kısıtı ikisini de geçirir, olay birleşir.

Bu bir *benzerlik* sorunu değil, bir *konu* sorunudur: sanayi üretimi ile
dış ticaret endeksi aynı olay değildir, ne kadar benzer yazılırlarsa
yazılsınlar.

**`numeric_guard`'dan farkı.** O modül "aynı metrik, farklı değer"
sorar (çelişki) ve sayıya bağlıdır. Bu modül "hangi göstergeden
bahsediyor" sorar ve sayıya bağlı DEĞİLDİR: "TÜİK işsizlik oranını
açıkladı" cümlesinde hiç sayı yoktur ama gösterge bellidir.

**Boş küme semantiği.** `_entity_check`'in dersi burada da geçerlidir
(Spec §11.4, B-55): bir taraf göstergesizse kısıt *uygulanamamıştır*.
Uygulanamayan kısıt reddetmez — reddetmek, sözlüğün tanımadığı her
makaleyi sonsuza dek tek başına bırakırdı. Yalnızca **iki taraf da
doluysa ve kesişim boşsa** ayırma kararı verilir.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

# Gösterge sözlüğü. Anahtar: kanonik gösterge ailesi. Değer: fold edilmiş
# kalıplar.
#
# Aile seçimi Golden Set'in gerçek olaylarından türetildi, uydurulmadı:
# TÜİK istatistik yayımları (evt-007/008/021/024/026/027/028) tam olarak
# bu hata ailesini oluşturuyor.
#
# ⚠️ Kalıplar KÖK biçiminde tutulur ("konut satis"), çünkü Türkçe eklemeli
# bir dildir: "satışları", "satışlarında" hepsi aynı köke iner.
INDICATOR_PATTERNS: Final[dict[str, tuple[str, ...]]] = {
    "cpi": ("tufe", "tuketici fiyat", "enflasyon"),
    "ppi": ("yi-ufe", "yi ufe", "uretici fiyat", "ufe"),
    "unemployment": ("issizlik", "isgucu", "istihdam", "isgucune katilma"),
    "gdp": ("gsyh", "buyume", "milli gelir", "buyudu"),
    "industrial_production": ("sanayi uretim",),
    "foreign_trade": ("dis ticaret", "ihracat", "ithalat"),
    "house_sales": ("konut satis",),
    "current_account": ("cari islemler", "cari acik", "cari denge", "cari fazla"),
    "policy_rate": (
        "politika faizi",
        "faiz karari",
        "faiz oranlarina iliskin",
        "para politikasi kurulu",
        "haftalik repo",
    ),
    "retail_sales": ("perakende satis",),
    "capacity_utilization": ("kapasite kullanim",),
    "confidence_index": ("guven endeksi",),
    "budget_balance": ("butce dengesi", "butce acigi", "merkezi yonetim butce"),
    "debt_stock": ("borc stoku",),
}


def _fold(text: str) -> str:
    """Aksanları ve büyük/küçük farkını siler.

    Türkçe'ye özgü tuzak: `İ` (U+0130) NFKD'de `I` + birleşen noktaya
    ayrışır; `casefold` öncesi ayrıştırmak "İŞSİZLİK" ile "işsizlik"in
    aynı kökene inmesini sağlar.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.replace("ı", "i").replace("İ", "i").casefold()


def detect_indicators(text: str) -> frozenset[str]:
    """Metnin bahsettiği gösterge ailelerini döndürür.

    Sayı aranmaz: gösterge adının geçmesi yeterlidir.
    """
    if not text:
        return frozenset()

    folded = _fold(text)
    found = {
        indicator
        for indicator, patterns in INDICATOR_PATTERNS.items()
        for pattern in patterns
        if re.search(rf"\b{re.escape(pattern)}", folded)
    }
    return frozenset(found)


def indicators_conflict(left_text: str, right_text: str) -> bool:
    """İki metin **farklı** göstergelerden mi bahsediyor?

    `True` yalnızca iki taraf da gösterge içeriyor VE hiç ortak gösterge
    yoksa döner. Bir taraf boşsa `False` — kanıt yokluğu, çelişki kanıtı
    değildir.
    """
    left = detect_indicators(left_text)
    right = detect_indicators(right_text)
    if not left or not right:
        return False
    return not (left & right)
