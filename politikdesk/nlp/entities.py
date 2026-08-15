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
    # ----------------------------------------------------------------- B-56
    # Bakanlıklar, düzenleyici kurullar ve kamu bankaları. Faz 2 ölçümü
    # Golden Set'in %38'inde hiç varlık tanınmadığını gösterdi; bu makaleler
    # `varlik_ok` kısıtını uygulayamadığı için `inconclusive` yolunu
    # yüklüyor ve precision'ı yalnızca benzerliğe bırakıyordu.
    #
    # ⚠ Alias seçim kuralı: kısa ve çok anlamlı kısaltmalar (tim, kik, ...)
    # ALINMAZ. `_ALIAS_RE` sözcük sınırıyla eşleşir; "tim" gibi bir alias
    # sıradan metinde yanlış-pozitif üretir. Kapsam genişlerken precision
    # düşerse bu kural gevşetilmiş demektir.
    "Ticaret Bakanlığı": ("ticaret bakanlığı", "ticaret bakanligi"),
    "Ulaştırma ve Altyapı Bakanlığı": (
        "ulaştırma ve altyapı bakanlığı", "ulastirma ve altyapi bakanligi",
        "ulaştırma bakanlığı",
    ),
    "Tarım ve Orman Bakanlığı": (
        "tarım ve orman bakanlığı", "tarim ve orman bakanligi", "tarım bakanlığı",
    ),
    "Sanayi ve Teknoloji Bakanlığı": (
        "sanayi ve teknoloji bakanlığı", "sanayi ve teknoloji bakanligi",
    ),
    "Enerji ve Tabii Kaynaklar Bakanlığı": (
        "enerji ve tabii kaynaklar bakanlığı", "enerji bakanlığı",
    ),
    "Çalışma ve Sosyal Güvenlik Bakanlığı": (
        "çalışma ve sosyal güvenlik bakanlığı", "çalışma bakanlığı",
    ),
    "Vergi Denetim Kurulu": ("vergi denetim kurulu", "vdk"),
    "Gelir İdaresi Başkanlığı": ("gelir idaresi başkanlığı", "gelir idaresi"),
    "Rekabet Kurumu": ("rekabet kurumu", "rekabet kurulu"),
    "Enerji Piyasası Düzenleme Kurumu": (
        "epdk", "enerji piyasası düzenleme kurumu",
    ),
    "Sigortacılık ve Özel Emeklilik Düzenleme ve Denetleme Kurumu": (
        "seddk", "sigortacılık ve özel emeklilik düzenleme ve denetleme kurumu",
    ),
    "Tasarruf Mevduatı Sigorta Fonu": ("tmsf", "tasarruf mevduatı sigorta fonu"),
    "Kamu İhale Kurumu": ("kamu ihale kurumu",),
    "Türkiye Varlık Fonu": ("türkiye varlık fonu", "turkiye varlik fonu"),
    "Türkiye Bilimsel ve Teknolojik Araştırma Kurumu": (
        "tübitak", "tubitak", "türkiye bilimsel ve teknolojik araştırma kurumu",
    ),
    "Küçük ve Orta Ölçekli İşletmeleri Geliştirme İdaresi": (
        "kosgeb", "küçük ve orta ölçekli işletmeleri geliştirme idaresi",
    ),
    "Türkiye İhracatçılar Meclisi": ("türkiye ihracatçılar meclisi",),
    "Türkiye Odalar ve Borsalar Birliği": (
        "tobb", "türkiye odalar ve borsalar birliği",
    ),
    "Türkiye Bankalar Birliği": ("türkiye bankalar birliği",),
    "Ziraat Bankası": ("ziraat bankası", "ziraat bankasi", "t.c. ziraat bankası"),
    "Türkiye Halk Bankası": ("halkbank", "türkiye halk bankası"),
    "Türkiye Vakıflar Bankası": ("vakıfbank", "vakifbank", "türkiye vakıflar bankası"),
    "Türkiye İş Bankası": ("türkiye iş bankası", "iş bankası"),
    "Türk Eximbank": ("eximbank", "türk eximbank"),
    "Türkiye Kalkınma ve Yatırım Bankası": (
        "türkiye kalkınma ve yatırım bankası",
    ),
    "Ekonomik İşbirliği ve Kalkınma Örgütü": (
        "oecd", "ekonomik işbirliği ve kalkınma örgütü",
    ),
    "Avrupa İmar ve Kalkınma Bankası": (
        "ebrd", "avrupa imar ve kalkınma bankası",
    ),
    "Dünya Ticaret Örgütü": ("dünya ticaret örgütü", "world trade organization"),
    # --- Yasama, Yargı ve Siyaset Kurumları (Spec v3.4 §5) ---
    "Sayıştay": ("sayıştay", "sayistay", "sayıştay başkanlığı"),
    "Anayasa Mahkemesi": ("anayasa mahkemesi", "aym"),
    "Yargıtay": ("yargıtay", "yargitay", "yargıtay cumhuriyet başsavcılığı"),
    "Danıştay": ("danıştay", "danistay"),
    "Hâkimler ve Savcılar Kurulu": (
        "hsk", "hâkimler ve savcılar kurulu", "hakimler ve savcilar kurulu",
    ),
    "Yüksek Seçim Kurulu": ("ysk", "yüksek seçim kurulu", "yuksek secim kurulu"),
    "Adalet Bakanlığı": ("adalet bakanlığı", "adalet bakanligi"),
    "İçişleri Bakanlığı": ("içişleri bakanlığı", "icisleri bakanligi"),
    "Dışişleri Bakanlığı": ("dışişleri bakanlığı", "disisleri bakanligi"),
    "Millî Savunma Bakanlığı": ("millî savunma bakanlığı", "milli savunma bakanlığı", "msb"),
    "İletişim Başkanlığı": ("iletişim başkanlığı", "iletisim baskanligi"),
    "Radyo ve Televizyon Üst Kurulu": ("rtük", "rtuk", "radyo ve televizyon üst kurulu"),
    "Bilgi Teknolojileri ve İletişim Kurumu": ("btk", "bilgi teknolojileri ve iletişim kurumu"),
    # --- Siyasi Partiler ---
    "Adalet ve Kalkınma Partisi": ("ak parti", "akp", "adalet ve kalkınma partisi"),
    "Cumhuriyet Halk Partisi": ("chp", "cumhuriyet halk partisi"),
    "Milliyetçi Hareket Partisi": ("mhp", "milliyetçi hareket partisi"),
    "Halkların Eşitlik ve Demokrasi Partisi": (
        "dem parti", "dem", "halkların eşitlik ve demokrasi partisi",
    ),
    "İYİ Parti": ("iyi parti", "i̇yi parti"),
    "Saadet Partisi": ("saadet partisi", "saadet"),
    "Demokrasi ve Atılım Partisi": ("deva partisi", "deva"),
    "Gelecek Partisi": ("gelecek partisi", "gelecek"),
    "Türkiye İşçi Partisi": ("tip", "türkiye işçi partisi", "turkiye isci partisi"),
    "Yeniden Refah Partisi": ("yrp", "yeniden refah partisi", "yeniden refah"),
    "Zafer Partisi": ("zafer partisi",),
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

POLITICAL_KEY_ENTITIES: Final[frozenset[str]] = frozenset({
    "Türkiye Büyük Millet Meclisi",
    "Sayıştay",
    "Anayasa Mahkemesi",
    "Yüksek Seçim Kurulu",
    "Cumhurbaşkanlığı",
})

# --------------------------------------------------------------------------
# Kişi çıkarımı: unvan kalıbı
# --------------------------------------------------------------------------
# "Hazine ve Maliye Bakanı Mehmet Şimşek", "TBMM Başkanı Numan Kurtulmuş"
_TITLES = (
    "Cumhurbaşkanı Yardımcısı", "Cumhurbaşkanı",
    "TBMM Başkanı", "Meclis Başkanı",
    "Grup Başkanvekili", "Grup Başkan Vekili",
    "Genel Başkan Yardımcısı", "Genel Başkanı", "Genel Başkan",
    "Bakan Yardımcısı", "Bakanı", "Bakan",
    "Milletvekili",
    "Parti Sözcüsü", "Sözcüsü", "Sözcü",
    "Büyükşehir Belediye Başkanı", "Belediye Başkanı",
    "Cumhuriyet Başsavcısı", "Başsavcısı", "Başsavcı",
    "Valisi", "Vali",
    "Başkan Vekili", "Başkanvekili", "Başkan Yardımcısı", "Başkanı", "Başkan",
    "Genel Müdürü", "Genel Müdür", "Müsteşarı",
)
_TITLE_ALT = "|".join(sorted(_TITLES, key=len, reverse=True))
_NAME_PART = r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+"
_PERSON_RE = re.compile(
    rf"(?:{_TITLE_ALT})\s+((?:{_NAME_PART}\s+){{0,2}}{_NAME_PART})"
)


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
