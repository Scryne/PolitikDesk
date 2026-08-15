"""Makro Ekonomi Dikey Tanımı (Spec §5 · D4).

Motorun kalibrasyon sahası olarak tasarlanan makro ekonomi dikeyinin
konu sözlükleri ve filtreleri.
"""

from __future__ import annotations

from typing import Final

from politikdesk.verticals.base import VerticalSpec

TOPIC_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "enflasyon": (
        "enflasyon", "tüfe", "tufe", "üfe", "ufe", "yi-üfe", "fiyat endeksi",
        "çekirdek enflasyon", "cekirdek enflasyon", "hayat pahalılığı",
    ),
    "politika_faizi": (
        "politika faizi", "ppk", "para politikası kurulu", "faiz kararı",
        "faiz oranı", "faiz indirimi", "faiz artırımı", "merkez bankası faiz",
        "faiz koridoru",
    ),
    "kur_ve_rezervler": (
        "rezerv", "döviz kuru", "doviz kuru", "swap", "net rezerv",
        "brüt rezerv", "dolar kuru", "euro kuru", "kur politikası",
    ),
    "butce_ve_hazine": (
        "bütçe", "butce", "bütçe açığı", "nakit dengesi", "bütçe gerçekleşme",
        "merkezi yönetim bütçe", "orta vadeli program", "ovp", "faiz dışı fazla",
    ),
    "issizlik_ve_istihdam": (
        "işsizlik", "issizlik", "istihdam", "işgücü", "isgucu", "atıl işgücü",
        "genç işsizlik", "işsizlik oranı",
    ),
    "buyume": (
        "büyüme", "buyume", "gsyh", "gayri safi yurt içi", "milli gelir",
        "ekonomik büyüme", "çeyrek büyüme", "resesyon",
    ),
    "asgari_ucret_ve_zamlar": (
        "asgari ücret", "asgari ucret", "memur maaş", "emekli maaş", "emekli zam",
        "memur zam", "toplu sözleşme", "refah payı", "maaş katsayı",
    ),
    "vergi_ve_harclar": (
        "vergi", "ötv", "kdv", "harç", "yeniden değerleme",
        "vergi affı", "yapılandırma", "gümrük vergisi", "damga vergisi",
        "stopaj", "matrah",
    ),
    "kamu_borclanmasi": (
        "borçlanma", "borclanma", "iç borç", "dış borç", "eurobond", "tahvil ihale",
        "hazine ihale", "borç stoku", "borç servisi",
    ),
    "derecelendirme": (
        "kredi notu", "derecelendirme", "moody", "fitch", "standard & poor",
        "s&p", "not artırım", "not indirim", "görünüm revize",
    ),
}

NON_EVENT_PATTERNS: Final[tuple[str, ...]] = (
    r"ne kadar oldu",
    r"kaç (tl|lira|dolar|euro)",
    r"güncel (kur|fiyat)",
    r"canlı (kur|borsa)",
    r"son dakika döviz",
    r"\balış satış\b",
    r"ne zaman açıklan",
)

TURKEY_SIGNALS: Final[tuple[str, ...]] = (
    "türkiye", "turkiye", "türk lirası", "tcmb", "tüik", "tuik", "hazine",
    "resmî gazete", "resmi gazete", "ankara", "istanbul",
    "bddk", "spk", "sgk", "tbmm", "bist", "borsa istanbul", "lira",
    "asgari ücret", "cumhurbaşkanı", "ppk",
)

MACRO_ECONOMY_VERTICAL: Final[VerticalSpec] = VerticalSpec(
    slug="macro_economy",
    name="Makro Ekonomi",
    description="Türkiye makro ekonomi politikası, para politikası, bütçe ve büyüme.",
    topic_keywords=TOPIC_KEYWORDS,
    non_event_patterns=NON_EVENT_PATTERNS,
    required_context_keywords=TURKEY_SIGNALS,
    default_election_mode=False,
    max_sources=12,
    key_entities=("tcmb", "tuik", "hazine", "resmi-gazete", "bddk", "spk"),
)
