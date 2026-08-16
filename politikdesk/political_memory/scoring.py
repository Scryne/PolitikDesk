"""Siyasi Hafıza Puanlama ve Metin Normalizasyon Katmanı (Spec v3.4 §7.3, §8.3)."""

from __future__ import annotations

import re
from typing import Any

_LAW_NO_RE = re.compile(r"\b(\d{4})\s*sayılı\b", re.IGNORECASE)
_SAYISTAY_REPORT_RE = re.compile(
    r"\b(sayıştay|denetim raporu|kamu zararı|usulsüzlük|düzenlilik denetimi)\b", re.IGNORECASE
)

GENERIC_INST_TERMS = frozenset(
    {
        "bakanligi",
        "bakanlik",
        "belediyesi",
        "belediye",
        "mudurlugu",
        "mudurluk",
        "baskanligi",
        "baskanlik",
        "valiligi",
        "valilik",
        "kaymakamligi",
        "kaymakamlik",
        "buyuksehir",
        "t.c.",
        "tc",
        "genel",
        "dairesi",
        "turkiye",
        "kamu",
        "ozel",
        "kurumu",
        "kurum",
        "kurulu",
        "kurul",
        "odasi",
        "oda",
        "borsasi",
        "borsa",
        "birligi",
        "birlik",
        "dernegi",
        "dernek",
        "vakfi",
        "vakif",
        "federasyonu",
        "federasyon",
        "barosu",
        "baro",
        "partisi",
        "parti",
        "sirketi",
        "sirket",
        "yonetimi",
        "yonetim",
        "ajansi",
        "ajans",
        # Şehir / ilçe isimleri (kurum benzerliği için tekil şehir çakışmasını engelle)
        "adana",
        "adiyaman",
        "afyon",
        "agri",
        "amasya",
        "ankara",
        "antalya",
        "artvin",
        "aydin",
        "balikesir",
        "bilecik",
        "bingol",
        "bitlis",
        "bolu",
        "burdur",
        "bursa",
        "canakkale",
        "cankiri",
        "corum",
        "denizli",
        "diyarbakir",
        "edirne",
        "elazig",
        "erzincan",
        "erzurum",
        "eskisehir",
        "gaziantep",
        "giresun",
        "gumushane",
        "hakkari",
        "hatay",
        "isparta",
        "mersin",
        "istanbul",
        "izmir",
        "kars",
        "kastamonu",
        "kayseri",
        "kirklareli",
        "kirsehir",
        "kocaeli",
        "konya",
        "kutahya",
        "malatya",
        "manisa",
        "kahramanmaras",
        "mardin",
        "mugla",
        "mus",
        "nevsehir",
        "nigde",
        "ordu",
        "rize",
        "sakarya",
        "samsun",
        "siirt",
        "sinop",
        "sivas",
        "tekirdag",
        "tokat",
        "trabzon",
        "tunceli",
        "sanliurfa",
        "usak",
        "van",
        "yozgat",
        "zonguldak",
        "aksaray",
        "bayburt",
        "karaman",
        "kirikkale",
        "batman",
        "sirnak",
        "bartin",
        "ardahan",
        "igdir",
        "yalova",
        "karabuk",
        "kilis",
        "osmaniye",
        "duzce",
    }
)


def normalize_turkish_text(text: str) -> str:
    """Türkçe metni küçük harfe dönüştürür ve ASCII varyantlarını da ekleyerek toleranslı kılar."""
    lowered = text.casefold()
    char_map: dict[int, str | int | None] = {
        ord("ı"): "i",
        ord("ğ"): "g",
        ord("ü"): "u",
        ord("ş"): "s",
        ord("ö"): "o",
        ord("ç"): "c",
        ord("î"): "i",
        ord("â"): "a",
        ord("û"): "u",
    }
    ascii_equiv = lowered.translate(char_map)
    return f"{lowered} {ascii_equiv}"


def normalize_institution_name(name: str) -> str:
    """Kurum adlarındaki Türkçe karakterleri ve ekleri tekil ASCII köke normalize eder."""
    lowered = name.casefold()

    char_map: dict[int, str | int | None] = {
        ord("ı"): "i",
        ord("ğ"): "g",
        ord("ü"): "u",
        ord("ş"): "s",
        ord("ö"): "o",
        ord("ç"): "c",
        ord("î"): "i",
        ord("â"): "a",
        ord("û"): "u",
    }
    ascii_str = lowered.translate(char_map)
    replacements = {
        "bakanligi": "bakanlik",
        "bakanlig": "bakanlik",
        "baskanligi": "baskanlik",
        "baskanlig": "baskanlik",
        "mudurlugu": "mudurluk",
        "mudurlug": "mudurluk",
        "valiligi": "valilik",
        "valilig": "valilik",
        "kaymakamligi": "kaymakamlik",
        "kaymakamlig": "kaymakamlik",
        "belediyesi": "belediye",
        "defterdarligi": "defterdarlik",
        "rektorlugu": "rektorluk",
        "komutanligi": "komutanlik",
        "federasyonu": "federasyon",
        "buyuksehir": "belediye",
    }
    for old, new in replacements.items():
        ascii_str = ascii_str.replace(old, new)
    return ascii_str


def stem_token(w: str) -> str:
    """Türkçe çekim ve çokluk eklerini temel kök formuna indirger."""
    w = w.casefold()
    char_map: dict[int, str | int | None] = {
        ord("ı"): "i",
        ord("ğ"): "g",
        ord("ü"): "u",
        ord("ş"): "s",
        ord("ö"): "o",
        ord("ç"): "c",
        ord("î"): "i",
        ord("â"): "a",
        ord("û"): "u",
    }
    w = w.translate(char_map)
    suffixes = (
        "larindan",
        "lerinden",
        "larinda",
        "lerinde",
        "larinin",
        "lerinin",
        "larina",
        "lerine",
        "larini",
        "lerini",
        "larin",
        "lerin",
        "sindan",
        "sinden",
        "sinda",
        "sinde",
        "sinin",
        "sine",
        "sina",
        "sini",
        "indan",
        "inden",
        "inda",
        "inde",
        "unun",
        "larin",
        "lere",
        "lara",
        "leri",
        "lari",
        "dan",
        "den",
        "tan",
        "ten",
        "nin",
        "nun",
        "nda",
        "nde",
        "na",
        "ne",
        "ya",
        "ye",
        "yi",
        "yu",
        "da",
        "de",
        "ta",
        "te",
        "in",
        "un",
        "ler",
        "lar",
        "lik",
        "luk",
        "ci",
        "cu",
    )
    for sfx in suffixes:
        if len(w) >= len(sfx) + 4 and w.endswith(sfx):
            w = w[: -len(sfx)]
            break
    return w


def extract_fallback_keywords(
    title: str,
    claims: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
) -> frozenset[str]:
    """Başlık ve iddialardan stopword'süz ve köklenmiş anahtar kelimeleri çıkarır."""
    stopwords = frozenset(
        {
            "için",
            "olan",
            "dair",
            "daha",
            "gibi",
            "kadar",
            "veya",
            "tarafından",
            "ancak",
            "üzere",
            "bunun",
            "sonra",
            "önce",
            "olarak",
            "oldu",
            "olduğu",
            "olay",
            "ilgili",
            "konuda",
            "birlikte",
            "karşı",
            "göre",
            "eden",
            "edilen",
            "yeni",
            "biri",
            "birkaç",
            "tüm",
            "aynı",
            "farklı",
            "hem",
            "bile",
            "artık",
            "diye",
            "şekilde",
            "ardından",
            "çünkü",
            "böyle",
            "kendi",
            "şöyle",
        }
    )
    keys: set[str] = set()
    for c in claims:
        for w in c.get("claim_text", "").split():
            cleaned = w.strip(".,;:\"'()!?[]{}«»-").casefold()
            if len(cleaned) >= 4 and cleaned not in stopwords:
                keys.add(cleaned)
                keys.add(stem_token(cleaned))
    for w in title.split():
        cleaned = w.strip(".,;:\"'()!?[]{}«»-").casefold()
        if len(cleaned) >= 4 and cleaned not in stopwords:
            keys.add(cleaned)
            keys.add(stem_token(cleaned))
    return frozenset(keys)


def match_actor(s_act: str | None, t_act: str | None, all_target_entities: frozenset[str]) -> bool:
    """Aktör eşleşmesini belirteç/kelime sınırı hassasiyetiyle değerlendirir."""
    if not s_act:
        return False

    s_clean = s_act.casefold().strip()
    s_tokens = set(re.findall(r"\w+", s_clean))
    if not s_tokens:
        return False

    if t_act:
        t_clean = t_act.casefold().strip()
        t_tokens = set(re.findall(r"\w+", t_clean))
        if s_clean == t_clean:
            return True
        if len(s_tokens) >= 2 and s_tokens.issubset(t_tokens):
            return True
        if len(t_tokens) >= 2 and t_tokens.issubset(s_tokens):
            return True
        if len(s_tokens) == 1 and len(t_tokens) == 1 and s_tokens == t_tokens:
            return True

    for ent in all_target_entities:
        ent_tokens = set(re.findall(r"\w+", ent.casefold()))
        if len(s_tokens) >= 2 and s_tokens.issubset(ent_tokens):
            return True
        if len(s_tokens) == 1 and s_tokens == ent_tokens:
            return True

    return False
