"""Kanonik Kategori ve Bölge Taksonomisi (Faz 21 · Gündem V2).

Gündem V2 için deterministik, test edilebilir ve genişletilebilir
kategori ve bölge sınıflandırıcısı.

⛔ Kırmızı Çizgiler:
  * Bu modülde hiçbir LLM çağrısı YOKTUR — sınıflandırma kural tabanlı,
    ucuz ve deterministiktir.
  * Siyasi kutuplaşma/taraf etiketi ÜRETİLMEZ (Spec §8.5, P6).
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Final

# --------------------------------------------------------------------------
# 1. Kanonik Kategoriler
# --------------------------------------------------------------------------
CATEGORIES: Final[tuple[tuple[str, str], ...]] = (
    ("all", "Tüm Kategoriler"),
    ("ekonomi", "Ekonomi & Finans"),
    ("politika", "İç Politika"),
    ("dis_politika", "Dış Politika & Diplomasi"),
    ("guvenlik", "Güvenlik & Savunma"),
    ("hukuk", "Hukuk & Yargı"),
    ("enerji", "Enerji & İklim"),
    ("teknoloji", "Teknoloji & Sanayi"),
    ("saglik_toplum", "Sağlık & Toplum"),
    ("yerel", "Yerel Yönetimler"),
    ("diger", "Genel & Diğer"),
)

CATEGORY_MAP: Final[dict[str, str]] = dict(CATEGORIES)

# --------------------------------------------------------------------------
# 2. Kanonik Bölgeler
# --------------------------------------------------------------------------
REGIONS: Final[tuple[tuple[str, str], ...]] = (
    ("all", "Tüm Bölgeler"),
    ("turkiye", "Türkiye"),
    ("abd", "ABD"),
    ("avrupa", "Avrupa & AB"),
    ("orta_dogu", "Orta Doğu"),
    ("rusya_ukrayna", "Rusya & Ukrayna"),
    ("asya_pasifik", "Asya-Pasifik"),
    ("kuresel", "Küresel / Uluslararası"),
)

REGION_MAP: Final[dict[str, str]] = dict(REGIONS)


# --------------------------------------------------------------------------
# 3. Kategori Anahtar Kelimeleri & Konu Eşlemeleri
# --------------------------------------------------------------------------
_CATEGORY_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "ekonomi": (
        "enflasyon", "tüfe", "üfe", "faiz", "ppk", "tcmb", "merkez bankası",
        "döviz", "dolar", "euro", "kur", "rezerv", "swap", "bütçe", "hazine",
        "vergi", "ötv", "kdv", "harç", "borçlanma", "tahvil", "eurobond",
        "istihdam", "işsizlik", "maaş", "asgari ücret", "zam", "büyüme",
        "gsyh", "milli gelir", "ihracat", "ithalat", "cari açık", "bddk", "spk",
        "borsa", "bist", "kredi notu", "fitch", "moody", "s&p", "banka", "finans",
        "pmi", "cds", "sukuk", "konut satış", "imalat pmi", "sanayi odası",
        "kapasite kullanım", "kko", "varlık fonu", "üretim endeksi", "ciro endeksi",
        "imalat sanayi", "imalat sanayii",
    ),
    "politika": (
        "tbmm", "meclis", "seçim", "parti", "hükümet", "cumhurbaşkanı",
        "cumhurbaşkanlığı", "kabine", "bakan", "muhalefet", "chp", "ak parti",
        "mhp", "iyi parti", "dem parti", "grup toplantısı", "genel kurul",
        "kanun teklifi", "gensoru", "ittifak", "anket", "oy oranı",
        "milletvekili", "koalisyon", "cumhurbaşkanı kararı", "atama kararları",
        "kamu yöneticisi atama", "merkezi yönetim bütçe takvimi", "bütçe takvimi",
        "tbmm komisyonu", "meclis komisyonu", "tbmm adalet komisyonu", "komisyon başkanı",
        "uzlaşı", "uzlaştı",
    ),
    "dis_politika": (
        "dışişleri", "dışişleri bakanlığı", "diplomasi", "büyükelçi", "konsolosluk", "zirve", "bm",
        "birleşmiş milletler", "nato", "avrupa birliği", "ab", "müzakere",
        "antlaşma", "protokol", "ziyaret", "ikili görüşme", "dış politika",
        "heyet", "uluslararası", "yunanistan", "ermenistan", "azerbaycan",
        "avrupa parlamentosu", "g20", "türk devletleri teşkilatı", "balkan barış",
        "şanghay işbirliği", "ateşkes", "filistin'i resmi olarak tanıma",
        "stratejik işbirliği", "diplomatik uzlaşı", "mutabakat", "akpm",
        "serbest ticaret anlaşması", "diplomatik temas", "hükümetlerarası zirve",
        "diplomatik kınama", "vize serbestisi", "ilerleme raporu", "geri kabul",
    ),
    "guvenlik": (
        "tsk", "savunma", "milli savunma", "msb", "mit", "istihbarat",
        "operasyon", "terör", "pkk", "ypg", "deaş", "fırat kalkanı",
        "zeytin dalı", "barış pınarı", "pençe", "suriye", "ırak", "asker",
        "şehit", "aselsan", "roketsan", "tusaş", "baykar", "iha", "siha",
        "s-400", "f-16", "f-35", "mavi vatan", "sahil güvenlik", "jandarma",
        "emniyet", "sınır güvenliği", "kara kuvvetleri", "deniz kuvvetleri",
        "hava kuvvetleri", "savunma sanayii", "tatbikat", "askeri tatbikat",
        "nükleer kuvvetler", "donanma", "ordu", "cephe", "savunma hattı",
        "havelsan", "milden", "denizaltı", "pentagon", "centcom", "hava harekatı",
    ),
    "hukuk": (
        "yargı", "mahkeme", "dava", "savcı", "hakim", "hsk", "yargıtay",
        "danıştay", "sayıştay", "anayasa mahkemesi", "aym", "ceza", "tahliye",
        "tutuklama", "iddianame", "karar", "kanun", "yasa", "mevzuat",
        "hukuk", "yargılama", "adliye", "baro", "avukat", "resmi gazete",
        "arabuluculuk", "noter", "icra", "haciz", "istinaf", "aihm",
        "sulh ceza", "kvkk", "tüketici mahkemesi", "uluslararası ceza mahkemesi", "ucm",
        "vergi mahkemesi", "mali yargı", "idare mahkemesi", "iş mahkemesi",
        "başsavcılık", "cumhuriyet başsavcılığı", "uluslararası adalet divanı",
        "temyiz", "hak ihlali", "soykırım davası", "yargı paketi", "yargı reformu",
        "adalet komisyonu",
    ),
    "enerji": (
        "enerji", "petrol", "doğalgaz", "gaz", "botaş", "tpao", "nükleer",
        "akkuyu", "elektrik", "epdk", "epiaş", "maden", "kömür", "rüzgar",
        "güneş", "yenilenebilir", "sondaj", "karadeniz gazı", "boru hattı",
        "iklim", "karbon", "çevre", "emisyon", "opec", "hidrokarbon",
        "hidroelektrik", "hes", "jeotermal", "kuzey akım", "cop29",
    ),
    "teknoloji": (
        "teknoloji", "yapay zeka", "yazılım", "donanım", "çip", "yarı iletken",
        "türksat", "tubitak", "uzay", "sanayi", "üretim", "fabrika",
        "otomasyon", "dijital", "siber", "5g", "telekom", "ar-ge",
        "openai", "microsoft", "apple", "google", "nvidia", "kuantum",
        "asml", "togg", "meta", "llama", "tsmc", "3d yazıcı", "katmanlı imalat",
        "muhakeme modeli",
    ),
    "saglik_toplum": (
        "sağlık", "hastane", "ilaç", "doktor", "tabip", "ttb",
        "eğitim", "öğrenci", "öğretmen", "üniversite", "yök", "milli eğitim",
        "meb", "sgk", "emekli", "nüfus", "göç", "mülteci", "sosyal yardım",
        "sosyal hizmetler", "aile ve sosyal", "engelli", "kyk", "burs",
        "afad", "kızılay", "afet", "deprem", "ekpss", "tisk", "hak-iş",
        "kültür ve turizm", "kültür ve turizm bakanlığı", "müze", "ösym", "mhrs", "huzurevi", "who",
        "diyanet", "hac", "umre", "kütüphane", "vakıf", "vakıflar", "yeşilay",
        "yedam", "bağımlılık",
        "iş sağlığı", "meslek hastalığı",
    ),
    "yerel": (
        "belediye", "büyükşehir", "ibb", "abb", "belediye başkanı", "meclis üyesi",
        "ulaşım", "metro", "imar", "kentsel dönüşüm", "su", "iski", "aski",
        "valilik", "kaymakamlık", "yerel", "muhtar", "zabıt", "izsu", "tarımsal sulama",
        "orman yangını", "belediye desteği", "giriş yasağı",
    ),
}

# --------------------------------------------------------------------------
# 4. Bölge Anahtar Kelimeleri & Varlık Eşlemeleri
# --------------------------------------------------------------------------
_REGION_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "turkiye": (
        "türkiye", "turkiye", "türk", "ankara", "istanbul", "izmir", "tcmb",
        "tüik", "tbmm", "hazine", "resmi gazete", "bddk", "spk", "bist",
        "tsk", "afad", "meb", "kızılay", "aselsan", "roketsan", "tusaş",
        "botaş", "baykar", "havelsan", "diyanet",
    ),
    "abd": (
        "abd", "amerika birleşik devletleri", "washington", "beyaz saray", "pentagon", "fed",
        "federal rezerv", "biden", "trump", "abd kongresi", "senato",
        "openai", "microsoft", "apple", "google", "nvidia", "meta", "centcom",
    ),
    "avrupa": (
        "avrupa", "ab", "avrupa birliği", "brüksel", "almanya", "fransa",
        "ingiltere", "londra", "berlin", "paris", "ecb", "euro bölgesi", "italya",
        "hollanda", "ispanya", "yunanistan", "irlanda", "norveç", "strazburg",
        "balkan", "saraybosna", "madrid", "dublin", "asml", "baltık",
        "isviçre", "macaristan", "roma", "lahey", "atina", "üsküp", "bürgenstock",
    ),
    "orta_dogu": (
        "orta doğu", "ortadoğu", "israil", "filistin", "gazze", "iran",
        "ırak", "irak", "suriye", "lübnan", "suudi", "riyad", "tahran",
        "şam", "bağdat", "katar", "bae", "dubai", "yemen", "mısır", "kahire",
        "sudan", "amman", "ürdün", "doha", "batı şeria", "kızıldeniz",
    ),
    "rusya_ukrayna": (
        "rusya", "ukrayna", "moskova", "kiev", "putin", "zelenskiy", "zelensky",
        "kremlin", "donbas", "kırım", "zaporijya", "kursk",
    ),
    "asya_pasifik": (
        "çin", "pekin", "japonya", "tokyo", "hindistan", "yeni delhi",
        "güney kore", "seul", "tayvan", "avustralya", "asya", "boj",
        "kuzey kore", "taipei", "pyongyang", "semerkant", "tsmc",
    ),
    "kuresel": (
        "küresel", "uluslararası", "birleşmiş milletler", "bm", "un", "imf",
        "dünya bankası", "g20", "g7", "who", "dünya sağlık örgütü", "wto", "oecd",
        "opec", "şanghay işbirliği", "cop29", "mercosur", "güney amerika", "latin amerika",
        "brezilya", "arjantin", "uluslararası adalet divanı",
    ),
}


def _fold(text: str) -> str:
    """Türkçe ve uluslararası uyumlu küçük harf normalizasyonu."""
    normalized = unicodedata.normalize("NFC", text)
    return (
        normalized.replace("İ", "i")
        .replace("I", "i")
        .replace("ı", "i")
        .casefold()
    )


@lru_cache(maxsize=128)
def _compile_keywords(keywords: tuple[str, ...]) -> re.Pattern[str]:
    # 4 veya daha az harfli kısa kökler/kısaltmalar/özel isimler için katı kelime sınırı (\b),
    # uzunlar için ek toleransı (\w*) uygulanır.
    exact_short = [re.escape(_fold(k)) for k in keywords if len(k) <= 4]
    prefix_long = [re.escape(_fold(k)) for k in keywords if len(k) > 4]
    parts: list[str] = []
    if exact_short:
        parts.append(rf"\b(?:{'|'.join(exact_short)})\b")
    if prefix_long:
        parts.append(rf"\b(?:{'|'.join(prefix_long)})\w*")
    return re.compile("|".join(parts))


_CATEGORY_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    cat: _compile_keywords(kws) for cat, kws in _CATEGORY_KEYWORDS.items()
}

_REGION_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    reg: _compile_keywords(kws) for reg, kws in _REGION_KEYWORDS.items()
}


def classify_category(
    title: str,
    summary: str | None = None,
    *,
    topic_tags: list[str] | tuple[str, ...] | None = None,
    vertical: str | None = None,
) -> str:
    """Metin ve konu etiketlerinden kanonik kategori belirler.

    Varsayılan: 'ekonomi' (macro_economy dikeyinde) veya 'politika' (legislation dikeyinde).
    """
    haystack = _fold(f"{title} {summary or ''}")

    # 1. Konu etiketlerinden doğrudan eşleme
    if topic_tags:
        for tag in topic_tags:
            tag_folded = _fold(tag)
            if tag_folded in ("enflasyon", "politika_faizi", "kur_ve_rezervler", "butce_ve_hazine",
                              "issizlik_ve_istihdam", "buyume", "asgari_ucret_ve_zamlar",
                              "vergi_ve_harclar", "kamu_borclanmasi", "derecelendirme"):
                return "ekonomi"
            if tag_folded in ("kanun_teklifi", "genel_kurul_tutanak", "cb_kararname"):
                return "politika"
            if tag_folded in ("denetim_ve_yolsuzluk", "yargi", "mahkeme"):
                return "hukuk"

    # 2. Anahtar kelime eşleştirmesi (puanlama tabanlı)
    scores: dict[str, int] = {}
    for cat, pattern in _CATEGORY_PATTERNS.items():
        matches = len(pattern.findall(haystack))
        if matches > 0:
            scores[cat] = matches

    if scores:
        # En yüksek eşleşen kategori
        best_cat = max(scores.items(), key=lambda item: item[1])[0]
        return best_cat

    # 3. Dikey varsayılanı
    vertical_map = {
        "macro_economy": "ekonomi",
        "politics": "politika",
        "legislation": "politika",
        "diplomacy": "dis_politika",
        "security": "guvenlik",
        "law": "hukuk",
        "energy": "enerji",
        "technology": "teknoloji",
        "health": "saglik_toplum",
        "local": "yerel",
        "other": "diger",
    }
    if vertical and vertical in vertical_map:
        return vertical_map[vertical]
    return "ekonomi"


def classify_region(
    title: str,
    summary: str | None = None,
    *,
    entities: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Metin ve varlıklardan kanonik bölge belirler.

    Varsayılan: 'turkiye'.
    """
    haystack = _fold(f"{title} {summary or ''}")
    if entities:
        haystack += " " + " ".join(_fold(e) for e in entities)

    # Puanlama tabanlı bölge tespiti
    scores: dict[str, int] = {}
    for reg, pattern in _REGION_PATTERNS.items():
        matches = len(pattern.findall(haystack))
        if matches > 0:
            scores[reg] = matches

    if not scores:
        return "turkiye"

    # Eğer yabancı bölge puanı varsa ve Türkiye'den fazlaysa onu seç
    non_tr_scores = {r: s for r, s in scores.items() if r != "turkiye"}
    if non_tr_scores:
        top_foreign = max(non_tr_scores.items(), key=lambda item: item[1])
        tr_score = scores.get("turkiye", 0)
        if top_foreign[1] > tr_score:
            return top_foreign[0]

    return "turkiye"
