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
from pathlib import Path
from typing import Any, Final

import yaml


def _load_entities_config() -> dict[str, Any]:
    """`config/entities.yml` dosyasından varlık sözlüklerini yükler."""
    candidates = (
        Path(__file__).resolve().parent.parent.parent / "config" / "entities.yml",
        Path("config/entities.yml"),
    )
    for path in candidates:
        if path.is_file():
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:  # noqa: BLE001
                pass
    return {}


_CONFIG_DATA: Final[dict[str, Any]] = _load_entities_config()

# --------------------------------------------------------------------------
# Kurum sözlüğü: kanonik ad -> alias'lar (F1-16)
# --------------------------------------------------------------------------
INSTITUTIONS: Final[dict[str, tuple[str, ...]]] = {
    str(k): tuple(str(x) for x in v)
    for k, v in _CONFIG_DATA.get("institutions", {}).items()
}

# --------------------------------------------------------------------------
# Siyasi Aktörler Kataloğu: Kanonik Kişi Adı -> Alias'lar (Spec v3.5 §5)
# --------------------------------------------------------------------------
POLITICAL_ACTORS: Final[dict[str, tuple[str, ...]]] = {
    str(k): tuple(str(x) for x in v)
    for k, v in _CONFIG_DATA.get("political_actors", {}).items()
}

# Salience formülünün "varlik_onemi" bileşeni (Spec §8.4) için anahtar varlıklar
KEY_ENTITIES: Final[frozenset[str]] = frozenset(
    str(x) for x in _CONFIG_DATA.get(
        "key_entities",
        [
            "Türkiye Cumhuriyet Merkez Bankası",
            "Türkiye İstatistik Kurumu",
            "Hazine ve Maliye Bakanlığı",
            "Resmî Gazete",
            "Para Politikası Kurulu",
            "Cumhurbaşkanlığı",
        ],
    )
)

POLITICAL_KEY_ENTITIES: Final[frozenset[str]] = frozenset(
    str(x) for x in _CONFIG_DATA.get(
        "political_key_entities",
        [
            "Türkiye Büyük Millet Meclisi",
            "Sayıştay",
            "Anayasa Mahkemesi",
            "Yüksek Seçim Kurulu",
            "Cumhurbaşkanlığı",
            "Recep Tayyip Erdoğan",
            "Özgür Özel",
            "Devlet Bahçeli",
            "Ekrem İmamoğlu",
            "Mansur Yavaş",
        ],
    )
)

# --------------------------------------------------------------------------
# Kişi çıkarımı: unvan kalıbı + Siyasi Aktörler İndeksi
# --------------------------------------------------------------------------
_TITLES: tuple[str, ...] = tuple(
    str(x) for x in _CONFIG_DATA.get(
        "titles",
        [
            "Cumhurbaşkanı Yardımcısı",
            "Cumhurbaşkanı",
            "TBMM Başkanı",
            "Meclis Başkanı",
            "Grup Başkanvekili",
            "Grup Başkan Vekili",
            "Grup Başkanı",
            "Eş Genel Başkanı",
            "Eş Genel Başkan",
            "Genel Başkan Yardımcısı",
            "Genel Başkanı",
            "Genel Başkan",
            "Bakan Yardımcısı",
            "Bakanı",
            "Bakan",
            "Milletvekili",
            "Parti Sözcüsü",
            "Sözcüsü",
            "Sözcü",
            "Büyükşehir Belediye Başkanı",
            "İl Belediye Başkanı",
            "Belediye Başkanı",
            "Cumhuriyet Başsavcısı",
            "Başsavcısı",
            "Başsavcı",
            "Valisi",
            "Vali",
            "Başkan Vekili",
            "Başkanvekili",
            "Başkan Yardımcısı",
            "Başkanı",
            "Başkan",
            "Genel Müdürü",
            "Genel Müdür",
            "Müsteşarı",
        ],
    )
)
_TITLE_ALT = "|".join(sorted(_TITLES, key=len, reverse=True))
_NAME_PART = r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+"
_PERSON_RE = re.compile(rf"(?:{_TITLE_ALT})\s+((?:{_NAME_PART}\s+){{0,2}}{_NAME_PART})")


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
    def build(cls, mapping: dict[str, tuple[str, ...]] | None = None) -> EntityIndex:
        index = cls()
        for canonical, alias_list in (mapping or INSTITUTIONS).items():
            index.aliases[_fold(canonical)] = canonical
            for alias in alias_list:
                index.aliases[_fold(alias)] = canonical
        return index

    def resolve(self, text: str) -> str | None:
        return self.aliases.get(_fold(text))


_DEFAULT_INDEX = EntityIndex.build(INSTITUTIONS)
_POLITICAL_ACTORS_INDEX = EntityIndex.build(POLITICAL_ACTORS)


def _alias_pattern(index: EntityIndex) -> re.Pattern[str]:
    # Uzun alias'lar önce denenmeli ("merkez bankası" > "merkez")
    alternatives = sorted(index.aliases, key=len, reverse=True)
    escaped = "|".join(re.escape(a) for a in alternatives)
    return re.compile(rf"(?<!\w)({escaped})(?!\w)")


_ALIAS_RE = _alias_pattern(_DEFAULT_INDEX)
_ACTOR_ALIAS_RE = _alias_pattern(_POLITICAL_ACTORS_INDEX)


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
            is_key_entity=canonical in KEY_ENTITIES or canonical in POLITICAL_KEY_ENTITIES,
        )
    return list(found.values())


def extract_political_actors(text: str, index: EntityIndex | None = None) -> list[ExtractedEntity]:
    """Metindeki kilit siyasi aktörleri kanonik adlarına çözerek döndürür."""
    index = index or _POLITICAL_ACTORS_INDEX
    pattern = _ACTOR_ALIAS_RE if index is _POLITICAL_ACTORS_INDEX else _alias_pattern(index)

    folded = _fold(text)
    found: dict[str, ExtractedEntity] = {}

    for match in pattern.finditer(folded):
        canonical = index.resolve(match.group(1))
        if not canonical or canonical in found:
            continue
        found[canonical] = ExtractedEntity(
            canonical_name=canonical,
            entity_type="person",
            matched_text=match.group(1),
            is_key_entity=canonical in POLITICAL_KEY_ENTITIES,
        )
    return list(found.values())


def extract_people(text: str) -> list[ExtractedEntity]:
    """Unvanla anılan kişileri ve siyasi aktör kataloğundaki figürleri çıkarır.

    Önce siyasi aktörler kataloğu çözümlenir, ardından unvan kalıbı uygulanır.
    """
    found: dict[str, ExtractedEntity] = {}

    # 1. Tanımlı siyasi aktörler kataloğundan çıkar
    for actor in extract_political_actors(text):
        found[actor.canonical_name] = actor

    # 2. Unvan kalıbıyla anılan diğer kişileri çıkar
    for match in _PERSON_RE.finditer(text):
        raw_name = " ".join(match.group(1).split())
        if len(raw_name) < 5:
            continue
        # Kurum adının parçası mı? ("Merkez Bankası Başkanı" -> isim değil)
        if _DEFAULT_INDEX.resolve(raw_name):
            continue
        # Siyasi aktör alias'ı olarak çözümlenebiliyor mu?
        canonical = _POLITICAL_ACTORS_INDEX.resolve(raw_name) or raw_name
        if canonical not in found:
            found[canonical] = ExtractedEntity(
                canonical_name=canonical,
                entity_type="person",
                matched_text=raw_name,
                is_key_entity=canonical in POLITICAL_KEY_ENTITIES,
            )
    return list(found.values())


# B-63 (Spec v3.5 §11.4): Tier 1 resmî kaynakların doğal varlık sinyali
SOURCE_PRIMARY_ENTITIES: Final[dict[str, str]] = {
    "tuik": "Türkiye İstatistik Kurumu",
    "tuik_sdmx": "Türkiye İstatistik Kurumu",
    "tcmb": "Türkiye Cumhuriyet Merkez Bankası",
    "resmigazete": "Resmî Gazete",
    "resmi-gazete": "Resmî Gazete",
    "hazine": "Hazine ve Maliye Bakanlığı",
    "bddk": "Bankacılık Düzenleme ve Denetleme Kurumu",
    "spk": "Sermaye Piyasası Kurulu",
    "sayistay": "Sayıştay",
    "tbmm": "Türkiye Büyük Millet Meclisi",
    "cumhurbaskanligi": "Cumhurbaşkanlığı",
    "cb-kararname": "Cumhurbaşkanlığı",
}


def extract(
    title: str, excerpt: str | None = None, source_slug: str | None = None
) -> list[ExtractedEntity]:
    """Bir makaleden tüm varlıkları çıkarır (F1-15, B-63 & Spec v3.5)."""
    text = f"{title}. {excerpt or ''}"
    entities = [*extract_institutions(text), *extract_people(text)]

    # B-63: Tier 1 resmî kaynak bültenlerinde kaynak adının kendisi birincil varlıktır
    if source_slug and source_slug in SOURCE_PRIMARY_ENTITIES:
        canonical = SOURCE_PRIMARY_ENTITIES[source_slug]
        if not any(e.canonical_name == canonical for e in entities):
            entities.append(
                ExtractedEntity(
                    canonical_name=canonical,
                    entity_type="institution",
                    matched_text=canonical,
                    is_key_entity=canonical in KEY_ENTITIES or canonical in POLITICAL_KEY_ENTITIES,
                )
            )

    # Tekilleştir (aynı kanonik isimden birden fazla nesne kalmasın)
    seen: set[str] = set()
    deduped: list[ExtractedEntity] = []
    for e in entities:
        if e.canonical_name not in seen:
            seen.add(e.canonical_name)
            deduped.append(e)
    return deduped


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


def resolve_entity(text: str) -> ExtractedEntity | None:
    """Verilen metni (unvan, takma ad, kısaltma) kanonik varlığa çözümler."""
    if not text or not text.strip():
        return None

    # 1. Siyasi aktörlerde ara
    actor_canonical = _POLITICAL_ACTORS_INDEX.resolve(text)
    if actor_canonical:
        return ExtractedEntity(
            canonical_name=actor_canonical,
            entity_type="person",
            matched_text=text,
            is_key_entity=actor_canonical in POLITICAL_KEY_ENTITIES,
        )

    # 2. Kurumlarda ara
    inst_canonical = _DEFAULT_INDEX.resolve(text)
    if inst_canonical:
        return ExtractedEntity(
            canonical_name=inst_canonical,
            entity_type="institution",
            matched_text=text,
            is_key_entity=(
                inst_canonical in KEY_ENTITIES
                or inst_canonical in POLITICAL_KEY_ENTITIES
            ),
        )
    return None
