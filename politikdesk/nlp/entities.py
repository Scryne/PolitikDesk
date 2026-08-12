"""Varlık çıkarımı — kişi ve kurum (F1-15) + alias çözümleme (F1-16).

F1-15 DoD: TCMB, TÜİK, Hazine, bakan isimleri doğru çıkarılıyor;
50 makalelik örnekte ≥%85 doğruluk.
F1-16 DoD: "Merkez Bankası" = "TCMB" = "Türkiye Cumhuriyet Merkez Bankası"
tek varlığa çözülüyor.

**Neden model değil sözlük:** MVP dikeyinde varlık evreni küçük ve
kapalıdır — ~30 kurum ve unvanla anılan kişiler. Bir NER modeli bu
kümede sözlükten daha iyi sonuç vermez, ama model indirmesi, sürüm
yönetimi ve tahmin edilemez çıktı getirir. Sözlük + unvan kalıbı
deterministiktir, test edilebilir ve Golden Set'e karşı ölçülebilir.

Dikey genişlerken (Faz 5) bu karar yeniden değerlendirilir.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Final

# --------------------------------------------------------------------------
# Kurum sözlüğü: kanonik ad -> alias'lar (F1-16)
# --------------------------------------------------------------------------
INSTITUTIONS: Final[dict[str, tuple[str, ...]]] = {
    "Türkiye Cumhuriyet Merkez Bankası": (
        "tcmb", "merkez bankası", "merkez bankasi", "türkiye cumhuriyet merkez bankası",
        "turkiye cumhuriyet merkez bankasi", "cumhuriyet merkez bankası",
        "central bank of the republic of türkiye",
    ),
    "Türkiye İstatistik Kurumu": (
        "tüik", "tuik", "türkiye istatistik kurumu", "turkiye istatistik kurumu",
        "istatistik kurumu", "turkstat",
    ),
    "Hazine ve Maliye Bakanlığı": (
        "hazine ve maliye bakanlığı", "hazine ve maliye bakanligi", "hazine bakanlığı",
        "hazine", "maliye bakanlığı", "hmb",
    ),
    "Resmî Gazete": ("resmî gazete", "resmi gazete"),
    "Para Politikası Kurulu": ("ppk", "para politikası kurulu", "para politikasi kurulu"),
    "Bankacılık Düzenleme ve Denetleme Kurumu": (
        "bddk", "bankacılık düzenleme ve denetleme kurumu",
    ),
    "Sermaye Piyasası Kurulu": ("spk", "sermaye piyasası kurulu"),
    "Sosyal Güvenlik Kurumu": ("sgk", "sosyal güvenlik kurumu"),
    "Türkiye Büyük Millet Meclisi": ("tbmm", "meclis", "büyük millet meclisi"),
    "Borsa İstanbul": ("borsa istanbul", "bist"),
    "Uluslararası Para Fonu": ("imf", "uluslararası para fonu", "international monetary fund"),
    "Dünya Bankası": ("dünya bankası", "dunya bankasi", "world bank"),
    "Avrupa Merkez Bankası": ("ecb", "avrupa merkez bankası"),
    "Federal Rezerv": ("fed", "federal rezerv", "federal reserve"),
    "Moody's": ("moody's", "moodys", "moody"),
    "Fitch Ratings": ("fitch", "fitch ratings"),
    "S&P Global Ratings": ("s&p", "standard & poor's", "sp global", "s&p global"),
    "Türkiye İş Kurumu": ("işkur", "iskur", "türkiye iş kurumu"),
    "Asgari Ücret Tespit Komisyonu": ("asgari ücret tespit komisyonu",),
    "Cumhurbaşkanlığı": ("cumhurbaşkanlığı", "cumhurbaskanligi"),
}

# Salience formülünün "varlik_onemi" bileşeni (Spec §8.4) için anahtar varlıklar
KEY_ENTITIES: Final[frozenset[str]] = frozenset({
    "Türkiye Cumhuriyet Merkez Bankası",
    "Türkiye İstatistik Kurumu",
    "Hazine ve Maliye Bakanlığı",
    "Resmî Gazete",
    "Para Politikası Kurulu",
    "Cumhurbaşkanlığı",
})

# --------------------------------------------------------------------------
# Kişi çıkarımı: unvan kalıbı
# --------------------------------------------------------------------------
# "Hazine ve Maliye Bakanı Mehmet Şimşek", "TCMB Başkanı Fatih Karahan"
_TITLES = (
    "Bakanı", "Bakan", "Başkanı", "Başkan", "Başkan Yardımcısı",
    "Genel Müdürü", "Genel Müdür", "Müsteşarı", "Cumhurbaşkanı",
)
_TITLE_ALT = "|".join(sorted(_TITLES, key=len, reverse=True))
_NAME_PART = r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+"
_PERSON_RE = re.compile(
    rf"(?:{_TITLE_ALT})\s+((?:{_NAME_PART}\s+){{0,2}}{_NAME_PART})"
)

# "Mehmet Şimşek, ..." biçiminde tekrar geçen isimler için ikinci geçiş
_STANDALONE_NAME_RE = re.compile(rf"\b({_NAME_PART}\s+{_NAME_PART})\b")


def _fold(text: str) -> str:
    """Türkçe'ye uygun küçültme + Unicode normalizasyonu."""
    normalized = unicodedata.normalize("NFC", text)
    return normalized.replace("İ", "i").replace("I", "ı").casefold().strip()


@dataclass(frozen=True)
class ExtractedEntity:
    canonical_name: str
    entity_type: str  # person | institution
    matched_text: str
    is_key_entity: bool = False


@dataclass
class EntityIndex:
    """Alias -> kanonik ad eşlemesi (F1-16)."""

    aliases: dict[str, str] = field(default_factory=dict)

    @classmethod
    def build(cls, institutions: dict[str, tuple[str, ...]] | None = None) -> EntityIndex:
        index = cls()
        for canonical, alias_list in (institutions or INSTITUTIONS).items():
            index.aliases[_fold(canonical)] = canonical
            for alias in alias_list:
                index.aliases[_fold(alias)] = canonical
        return index

    def resolve(self, text: str) -> str | None:
        return self.aliases.get(_fold(text))


_DEFAULT_INDEX = EntityIndex.build()


def _alias_pattern(index: EntityIndex) -> re.Pattern[str]:
    # Uzun alias'lar önce denenmeli ("merkez bankası" > "merkez")
    alternatives = sorted(index.aliases, key=len, reverse=True)
    escaped = "|".join(re.escape(a) for a in alternatives)
    return re.compile(rf"(?<!\w)({escaped})(?!\w)")


_ALIAS_RE = _alias_pattern(_DEFAULT_INDEX)


def extract_institutions(text: str, index: EntityIndex | None = None) -> list[ExtractedEntity]:
    """Metindeki kurumları kanonik adlarına çözerek döndürür."""
    index = index or _DEFAULT_INDEX
    pattern = _ALIAS_RE if index is _DEFAULT_INDEX else _alias_pattern(index)

    folded = _fold(text)
    found: dict[str, ExtractedEntity] = {}

    for match in pattern.finditer(folded):
        canonical = index.resolve(match.group(1))
        if not canonical or canonical in found:
            continue
        found[canonical] = ExtractedEntity(
            canonical_name=canonical,
            entity_type="institution",
            matched_text=match.group(1),
            is_key_entity=canonical in KEY_ENTITIES,
        )
    return list(found.values())


def extract_people(text: str) -> list[ExtractedEntity]:
    """Unvanla anılan kişileri çıkarır.

    Yalnızca unvan kalıbıyla eşleşenler alınır. Bu bilinçli bir kısıttır:
    unvansız her iki büyük harfli sözcüğü kişi saymak, kurum ve yer
    adlarını kişiye dönüştürür ve doğruluğu düşürür.
    """
    found: dict[str, ExtractedEntity] = {}

    for match in _PERSON_RE.finditer(text):
        name = " ".join(match.group(1).split())
        if len(name) < 5 or name in found:
            continue
        # Kurum adının parçası mı? ("Merkez Bankası Başkanı" -> isim değil)
        if _DEFAULT_INDEX.resolve(name):
            continue
        found[name] = ExtractedEntity(
            canonical_name=name, entity_type="person", matched_text=name
        )
    return list(found.values())


def extract(title: str, excerpt: str | None = None) -> list[ExtractedEntity]:
    """Bir makaleden tüm varlıkları çıkarır (F1-15)."""
    text = f"{title}. {excerpt or ''}"
    return [*extract_institutions(text), *extract_people(text)]


def entity_set(entities: list[ExtractedEntity]) -> frozenset[str]:
    """Kümeleme kısıtı için varlık kümesi (Spec §11.4 `varlik_ok`)."""
    return frozenset(e.canonical_name for e in entities)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Spec §11.4: `jaccard(article.entities, aday.entity_set) >= 0.25`."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def has_common_key_entity(a: list[ExtractedEntity], b: list[ExtractedEntity]) -> bool:
    """Spec §11.4: "VEYA en az 1 ortak Tier-1 varlık"."""
    key_a = {e.canonical_name for e in a if e.is_key_entity}
    key_b = {e.canonical_name for e in b if e.is_key_entity}
    return bool(key_a & key_b)
