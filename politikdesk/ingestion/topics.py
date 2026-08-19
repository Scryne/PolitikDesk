"""MVP konu sınıflandırması (kapsam filtresi).

`docs/mvp-konu-kapsami.md`'deki 10 konu, anahtar kelime sözlükleriyle
eşlenir. Amaç sınıflandırma doğruluğu değil **kapsam filtresidir**:
makro ekonomi dışındaki içerik boru hattına girmemelidir.

Neden LLM değil: bu filtre her makalede çalışır. LLM ile yapılırsa
maliyetin en büyük kalemi olur ve `docs/veri-maliyet-modeli.md`'deki
çıkarım bütçesi ikiye katlanır. Anahtar kelime filtresi ucuz, deterministik
ve denetlenebilirdir; yanlış negatifler Golden Set üzerinden ölçülür.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Final

from politikdesk.verticals import get_vertical

# eval/golden_set_tools.py::VALID_TOPICS ile aynı 10 slug
TOPIC_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "enflasyon": (
        "enflasyon",
        "tüfe",
        "tufe",
        "üfe",
        "ufe",
        "yi-üfe",
        "fiyat endeksi",
        "çekirdek enflasyon",
        "cekirdek enflasyon",
        "hayat pahalılığı",
    ),
    "politika_faizi": (
        "politika faizi",
        "ppk",
        "para politikası kurulu",
        "faiz kararı",
        "faiz oranı",
        "faiz indirimi",
        "faiz artırımı",
        "merkez bankası faiz",
        "faiz koridoru",
    ),
    "kur_ve_rezervler": (
        "rezerv",
        "döviz kuru",
        "doviz kuru",
        "swap",
        "net rezerv",
        "brüt rezerv",
        "dolar kuru",
        "euro kuru",
        "kur politikası",
        # 19 Ağu 2026: TCMB EVDS adaptörü açıldığında bulunan sözlük
        # boşluğu. Kurumun kendi seri adı "(USD) ABD Doları (Döviz Alış)"
        # ve türetilen başlık "ABD doları alış kuru" — sözlükte "dolar
        # kuru" vardı ama "alış kuru" yoktu, dolayısıyla TCMB'nin KENDİ
        # kur verisi konu dışı sayılıp eleniyordu. Filtre doğru
        # çalışıyordu; eksik olan sözlüktü.
        "alış kuru",
        "satış kuru",
        "döviz alış",
        "döviz satış",
        "efektif alış",
        "efektif satış",
        # Parasal büyüklükler bu başlığın altındadır: M1/M2/M3 para arzı
        # kur ve rezervlerle birlikte para politikasının niceliksel
        # tarafını oluşturur.
        "para arzı",
        "parasal büyüklük",
    ),
    "butce_ve_hazine": (
        "bütçe",
        "butce",
        "bütçe açığı",
        "nakit dengesi",
        "bütçe gerçekleşme",
        "merkezi yönetim bütçe",
        "orta vadeli program",
        "ovp",
        "faiz dışı fazla",
    ),
    "issizlik_ve_istihdam": (
        "işsizlik",
        "issizlik",
        "istihdam",
        "işgücü",
        "isgucu",
        "atıl işgücü",
        "genç işsizlik",
        "işsizlik oranı",
    ),
    "buyume": (
        "büyüme",
        "buyume",
        "gsyh",
        "gayri safi yurt içi",
        "milli gelir",
        "ekonomik büyüme",
        "çeyrek büyüme",
        "resesyon",
    ),
    "asgari_ucret_ve_zamlar": (
        "asgari ücret",
        "asgari ucret",
        "memur maaş",
        "emekli maaş",
        "emekli zam",
        "memur zam",
        "toplu sözleşme",
        "refah payı",
        "maaş katsayı",
    ),
    "vergi_ve_harclar": (
        # "harc" (diyakritiksiz) BİLİNÇLİ OLARAK YOK: "harcandı", "harcama"
        # gibi sözcükleri vergi konusuna sokuyordu (canlı veride ölçüldü).
        "vergi",
        "ötv",
        "kdv",
        "harç",
        "yeniden değerleme",
        "vergi affı",
        "yapılandırma",
        "gümrük vergisi",
        "damga vergisi",
        "stopaj",
        "matrah",
    ),
    "kamu_borclanmasi": (
        "borçlanma",
        "borclanma",
        "iç borç",
        "dış borç",
        "eurobond",
        "tahvil ihale",
        "hazine ihale",
        "borç stoku",
        "borç servisi",
    ),
    "derecelendirme": (
        "kredi notu",
        "derecelendirme",
        "moody",
        "fitch",
        "standard & poor",
        "s&p",
        "not artırım",
        "not indirim",
        "görünüm revize",
    ),
}

# Kapsam dışı sinyaller: bunlardan biri varsa ve hiçbir konu eşleşmiyorsa
# makale erken elenir (maliyet tasarrufu).
OUT_OF_SCOPE_HINTS: Final[tuple[str, ...]] = (
    "maç",
    "gol",
    "transfer",
    "şampiyonlar ligi",
    "süper lig",
    "futbol",
    "basketbol",
    "dizi",
    "sinema",
    "film",
    "konser",
    "festival",
    "burç",
    "sağlık",
    "hava durumu",
    "deprem",
    "trafik kazası",
    "magazin",
)

# --------------------------------------------------------------------------
# ÜLKE BAĞLAMI — MVP dikeyi *Türkiye* makro ekonomisidir (Spec §5).
#
# Konu anahtar kelimeleri tek başına yetmez: "Almanya'da enflasyon yükseldi"
# enflasyon konusuna düşer ama Türkiye makro politikası değildir ve
# `docs/mvp-konu-kapsami.md` bunu kapsam dışı sayar.
#
# Kural: konu eşleşmesi VAR **ve** (Türkiye sinyali VAR **veya** yabancı
# sinyal YOK) ise kapsam içidir.
# --------------------------------------------------------------------------
# "tl" ve "türk" BİLİNÇLİ OLARAK YOK: iki harflik kısaltma ve kısa kök,
# yabancı haberleri Türkiye bağlamı sanıyordu (canlı veride ölçüldü).
#
# Ayrıca ÜLKESİZ İFADELER de yok:
#   "merkez bankası" -> "ABD merkez bankasının" ile eşleşiyordu
#   "bakanı" / "bakanlığı" -> "Almanya Maliye Bakanı" ile eşleşirdi
# Bunlar ülke belirtmez. Türkiye'yi işaret eden ifade kalmadığında
# `has_turkey_context` zaten "yabancı sinyal yoksa kapsam içi" kuralına
# düşer; yani "Merkez Bankası faiz kararı" yine de kapsamda kalır.
TURKEY_SIGNALS: Final[tuple[str, ...]] = (
    "türkiye",
    "turkiye",
    "türk lirası",
    "tcmb",
    "tüik",
    "tuik",
    "hazine",
    "resmî gazete",
    "resmi gazete",
    "ankara",
    "istanbul",
    "bddk",
    "spk",
    "sgk",
    "tbmm",
    "bist",
    "borsa istanbul",
    "lira",
    "asgari ücret",
    "cumhurbaşkanı",
    "ppk",
)

FOREIGN_SIGNALS: Final[tuple[str, ...]] = (
    "abd",
    "amerika",
    "almanya",
    "rusya",
    "çin",
    "japonya",
    "ingiltere",
    "fransa",
    "i̇talya",
    "hindistan",
    "brezilya",
    "avrupa birliği",
    "euro bölgesi",
    "fed",
    "federal rezerv",
    "ecb",
    "avrupa merkez bankası",
    "boj",
    "küresel",
    "dünya genelinde",
    "uluslararası piyasalar",
    "wall street",
    "nasdaq",
    "s&p 500",
    "dow jones",
)


# Fiyat listesi / servis sayfaları: konu eşleşse de OLAY değildir.
# docs/mvp-konu-kapsami.md: "Kurun seviyesi bir piyasa fiyatıdır, olay değildir."
NON_EVENT_PATTERNS: Final[tuple[str, ...]] = (
    r"ne kadar oldu",
    r"kaç (tl|lira|dolar|euro)",
    r"güncel (kur|fiyat)",
    r"canlı (kur|borsa)",
    r"son dakika döviz",
    r"\balış satış\b",
    r"ne zaman açıklan",
)
_NON_EVENT_RE: Final = re.compile("|".join(NON_EVENT_PATTERNS))


def _fold(text: str) -> str:
    """Türkçe'ye uygun küçültme + Unicode normalizasyonu."""
    normalized = unicodedata.normalize("NFC", text)
    return normalized.replace("İ", "i").replace("I", "ı").casefold()


@lru_cache(maxsize=64)
def _compile_keywords(keywords: tuple[str, ...]) -> re.Pattern[str]:
    """Kelime başına sabitlenmiş, ekleri kabul eden kalıp.

    Türkçe eklemeli bir dildir: "enflasyon" kalıbı "enflasyonun",
    "enflasyondaki" biçimlerini de yakalamalıdır. Bu yüzden sonek serbest
    (`\\w*`), ancak kelime BAŞI sabittir (`\\b`) — aksi halde "harç"
    kalıbı "harcandı" içinde eşleşir ve konu ataması bozulur.
    """
    alternatives = "|".join(re.escape(_fold(k)) for k in keywords)
    return re.compile(rf"\b(?:{alternatives})\w*")


_TOPIC_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    topic: _compile_keywords(keywords) for topic, keywords in TOPIC_KEYWORDS.items()
}


_TURKEY_RE: Final = _compile_keywords(TURKEY_SIGNALS)
_FOREIGN_RE: Final = _compile_keywords(FOREIGN_SIGNALS)


@lru_cache(maxsize=64)
def _compile_non_event(patterns: tuple[str, ...]) -> re.Pattern[str]:
    """Non-event kalıplarını derler (I3: lru_cache ile önceden derlenir)."""
    if not patterns:
        return re.compile(r"$^")
    folded = [_fold(p) for p in patterns]
    return re.compile("|".join(folded))


def has_turkey_context(
    title: str,
    summary: str | None = None,
    *,
    vertical: str | None = None,
) -> bool:
    """Metin Türkiye / dikey bağlamına mı ait?"""
    haystack = _fold(f"{title} {summary or ''}")
    v_spec = get_vertical(vertical) if vertical else None
    if v_spec and v_spec.slug != "macro_economy" and v_spec.required_context_keywords:
        context_re = _compile_keywords(v_spec.required_context_keywords)
        return bool(context_re.search(haystack))

    if _TURKEY_RE.search(haystack):
        return True
    return not _FOREIGN_RE.search(haystack)


def is_non_event(
    title: str,
    summary: str | None = None,
    *,
    vertical: str | None = None,
) -> bool:
    """Fiyat listesi / servis sayfası / dikey non-event kalıbı mı? (olay değil)"""
    haystack = _fold(f"{title} {summary or ''}")
    v_spec = get_vertical(vertical) if vertical else None
    if v_spec and v_spec.non_event_patterns:
        non_event_re = _compile_non_event(v_spec.non_event_patterns)
        if non_event_re.search(haystack):
            return True
    else:
        if _NON_EVENT_RE.search(haystack):
            return True
    return False


@lru_cache(maxsize=32)
def _get_vertical_patterns(vertical_slug: str | None) -> dict[str, re.Pattern[str]]:
    """Dikey için konu kalıplarını derler ve önbelleğe alır (IMP-03)."""
    if not vertical_slug:
        return _TOPIC_PATTERNS
    v_spec = get_vertical(vertical_slug)
    if not v_spec or v_spec.slug == "macro_economy":
        return _TOPIC_PATTERNS
    return {
        topic: _compile_keywords(keywords) for topic, keywords in v_spec.topic_keywords.items()
    }


def match_topics(
    title: str,
    summary: str | None = None,
    *,
    vertical: str | None = None,
) -> tuple[str, ...]:
    """Ülke bağlamına bakmadan yalnızca konu eşleşmesi (teşhis için)."""
    haystack = _fold(f"{title} {summary or ''}")
    patterns = _get_vertical_patterns(vertical)
    return tuple(topic for topic, pattern in patterns.items() if pattern.search(haystack))


def classify(
    title: str,
    summary: str | None = None,
    *,
    vertical: str | None = None,
) -> tuple[str, ...]:
    """Metne uyan dikey konularını döndürür. Boş tuple = kapsam dışı.

    Üç koşul birlikte sağlanmalıdır (Spec §5):
      1. En az bir dikey konusu eşleşiyor
      2. Türkiye / dikey bağlamı var
      3. Bir fiyat listesi / servis sayfası / non-event değil
    """
    matched = match_topics(title, summary, vertical=vertical)
    if not matched:
        return ()
    if not has_turkey_context(title, summary, vertical=vertical):
        return ()
    if is_non_event(title, summary, vertical=vertical):
        return ()
    return matched


def in_scope(
    title: str,
    summary: str | None = None,
    *,
    vertical: str | None = None,
) -> bool:
    """Makale dikey kapsamında mı? (Spec §5 konu sınırı)"""
    return bool(classify(title, summary, vertical=vertical))


def looks_out_of_scope(title: str, summary: str | None = None) -> bool:
    """Belirgin kapsam dışı sinyali var mı? (yalnızca teşhis/loglama için)"""
    haystack = _fold(f"{title} {summary or ''}")
    return any(hint in haystack for hint in OUT_OF_SCOPE_HINTS)
