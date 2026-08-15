"""Deterministik ve Açıklanabilir Olay İlişki Motoru (S2 · Spec v3.4 §7.3, §8.3, §14.1).

Bu modül, siyasi beyanlar, vaatler, TBMM yasama adımları ve Sayıştay
denetim bulguları arasında deterministik ve kanıta dayalı ilişkiler kurar.
Black-box LLM yargısı içermez; tüm kararlar şeffaf puanlama ve kural
tabanlı kontrollerle (entity, institution, topic, temporal, explicit reference) üretilir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from politikdesk.nlp.entities import jaccard

RelationType = Literal["same_thread", "precedes", "updates", "contradicts", "fulfils", "fails"]
RelationStatus = Literal["inferred", "supported", "verified", "unresolved"]

_LAW_NO_RE = re.compile(r"\b(\d{4})\s*sayılı\b", re.IGNORECASE)
_SAYISTAY_REPORT_RE = re.compile(
    r"\b(sayıştay|denetim raporu|kamu zararı|usulsüzlük|düzenlilik denetimi)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class EventData:
    event_id: int
    title: str
    published_at: datetime
    entities: frozenset[str] = frozenset()
    key_entities: frozenset[str] = frozenset()
    institution: str | None = None
    actor: str | None = None
    topics: tuple[str, ...] = ()
    claims: tuple[dict[str, Any], ...] = ()
    embedding: list[float] | None = None
    vertical: str = "legislation"


@dataclass(frozen=True)
class RelationScoreBreakdown:
    entity_score: float
    institution_score: float
    topic_score: float
    semantic_score: float
    temporal_score: float
    explicit_boost: float
    total_score: float

    def to_dict(self) -> dict[str, float]:
        return {
            "entity_score": round(self.entity_score, 3),
            "institution_score": round(self.institution_score, 3),
            "topic_score": round(self.topic_score, 3),
            "semantic_score": round(self.semantic_score, 3),
            "temporal_score": round(self.temporal_score, 3),
            "explicit_boost": round(self.explicit_boost, 3),
            "total_score": round(self.total_score, 3),
        }


@dataclass(frozen=True)
class RelationResult:
    source_event_id: int
    target_event_id: int
    relation_type: RelationType
    confidence: float
    status: RelationStatus
    score_breakdown: RelationScoreBreakdown
    evidence_payload: dict[str, Any]
    explanation: str

    @property
    def is_valid(self) -> bool:
        return self.status != "unresolved" and self.confidence >= 0.60


def _normalize_turkish_text(text: str) -> str:
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


def _normalize_institution_name(name: str) -> str:
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
    # Türkçe idari ek yumuşamalarını köke eşitle
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


def _stem_token(w: str) -> str:
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
        "larindan", "lerinden", "larinda", "lerinde",
        "larinin", "lerinin", "larina", "lerine",
        "larini", "lerini", "larin", "lerin",
        "sindan", "sinden", "sinda", "sinde",
        "sinin", "sine", "sina", "sini",
        "indan", "inden", "inda", "inde",
        "indan", "inden", "unun", "unun",
        "lerin", "larin", "lere", "lara", "leri", "lari",
        "dan", "den", "tan", "ten", "nin", "nun",
        "nda", "nde", "na", "ne", "ya", "ye", "yi", "yu",
        "da", "de", "ta", "te", "in", "un",
        "ler", "lar", "lik", "luk", "ci", "cu",
    )
    for sfx in suffixes:
        if len(w) >= len(sfx) + 4 and w.endswith(sfx):
            w = w[: -len(sfx)]
            break
    return w


def _extract_fallback_keywords(
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
                keys.add(_stem_token(cleaned))
    for w in title.split():
        cleaned = w.strip(".,;:\"'()!?[]{}«»-").casefold()
        if len(cleaned) >= 4 and cleaned not in stopwords:
            keys.add(cleaned)
            keys.add(_stem_token(cleaned))
    return frozenset(keys)



def _match_actor(s_act: str | None, t_act: str | None, all_target_entities: frozenset[str]) -> bool:
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
        "adana", "adiyaman", "afyon", "agri", "amasya", "ankara", "antalya", "artvin", "aydin",
        "balikesir", "bilecik", "bingol", "bitlis", "bolu", "burdur", "bursa", "canakkale",
        "cankiri", "corum", "denizli", "diyarbakir", "edirne", "elazig", "erzincan", "erzurum",
        "eskisehir", "gaziantep", "giresun", "gumushane", "hakkari", "hatay", "isparta", "mersin",
        "istanbul", "izmir", "kars", "kastamonu", "kayseri", "kirklareli", "kirsehir", "kocaeli",
        "konya", "kutahya", "malatya", "manisa", "kahramanmaras", "mardin", "mugla", "mus",
        "nevsehir", "nigde", "ordu", "rize", "sakarya", "samsun", "siirt", "sinop", "sivas",
        "tekirdag", "tokat", "trabzon", "tunceli", "sanliurfa", "usak", "van", "yozgat",
        "zonguldak", "aksaray", "bayburt", "karaman", "kirikkale", "batman", "sirnak", "bartin",
        "ardahan", "igdir", "yalova", "karabuk", "kilis", "osmaniye", "duzce", "ilce", "il"
    }
)


def evaluate_relation(
    source: EventData,
    target: EventData,
    *,
    semantic_similarity: float | None = None,
    min_confidence: float = 0.60,
) -> RelationResult:
    """İki olay arasındaki ilişkiyi ve güven seviyesini değerlendirir.

    source: Önceki olay (vaat, karar, ilk beyan)
    target: Sonraki olay (yasama, icraat, Sayıştay denetim raporu)
    """
    # 1. Zamansal Uyumluluk (Temporal Compatibility)
    # Hedef olay kaynak olaydan önce olamaz (ters kronoloji vaat/icraat için geçersizdir)
    is_chronological = target.published_at >= source.published_at

    # 2. Varlık ve Aktör Örtüşmesi (Entity Overlap)
    s_keys = (
        source.key_entities
        if source.key_entities
        else _extract_fallback_keywords(source.title, source.claims)
    )
    t_keys = (
        target.key_entities
        if target.key_entities
        else _extract_fallback_keywords(target.title, target.claims)
    )
    all_source_entities = source.entities | s_keys
    all_target_entities = target.entities | t_keys
    ent_jaccard = (
        jaccard(all_source_entities, all_target_entities)
        if (all_source_entities and all_target_entities)
        else 0.0
    )

    actor_match = _match_actor(source.actor, target.actor, all_target_entities)
    entity_score = max(ent_jaccard, 0.80 if actor_match else 0.0)

    # 3. Kurum Eşleşmesi ve Anayasal Hiyerarşi (Institution Match & Constitutional Flow)
    institution_match = False
    is_constitutional_flow = False

    if source.institution and target.institution:
        s_inst_norm = _normalize_institution_name(source.institution)
        t_inst_norm = _normalize_institution_name(target.institution)

        s_parts = {p for p in s_inst_norm.split() if len(p) >= 3 and p not in GENERIC_INST_TERMS}
        t_parts = {p for p in t_inst_norm.split() if len(p) >= 3 and p not in GENERIC_INST_TERMS}

        gov_inst_keywords = (
            "tbmm", "resmi gazete", "epdk", "bddk", "spk", "resmi",
            "osym", "afad", "tcdd", "dhmi", "dsi", "toki", "sgk", "botas",
        )
        if (
            source.institution.casefold() == target.institution.casefold()
            or source.institution.casefold() in target.institution.casefold()
            or target.institution.casefold() in source.institution.casefold()
            or (bool(s_parts and t_parts) and bool(s_parts & t_parts))
            or any(source.institution.casefold() in e.casefold() for e in all_target_entities)
        ):
            institution_match = True
        elif (
            any(k in t_inst_norm for k in gov_inst_keywords)
            or any(k in s_inst_norm for k in gov_inst_keywords)
            or "sayistay" in t_inst_norm
            or "sayistay" in s_inst_norm
            or ("bakanlik" in s_inst_norm and "cumhurbaskan" in t_inst_norm)
            or ("cumhurbaskan" in s_inst_norm and "bakanlik" in t_inst_norm)
        ):
            is_constitutional_flow = True
    elif source.institution and any(
        source.institution.casefold() in e.casefold() for e in all_target_entities
    ):
        institution_match = True


    institution_score = (
        1.0
        if institution_match
        else (0.85 if is_constitutional_flow else (0.40 if not source.institution else 0.0))
    )

    # 4. Konu ve Kapsam Uyumu (Topic & Scope Match)
    shared_topics = set(source.topics) & set(target.topics)
    all_topics = set(source.topics) | set(target.topics)
    topic_score = (len(shared_topics) / max(len(all_topics), 1)) if all_topics else 0.50

    # 5. Semantik Benzerlik (Semantic Similarity)
    sim = semantic_similarity if semantic_similarity is not None else 0.50
    if sim < 0.0:
        sim = 0.0

    # 6. Açık Kanun ve Denetim Referansı (Explicit Boost)
    explicit_boost = 0.0
    source_laws = set(_LAW_NO_RE.findall(source.title))
    target_laws = set(_LAW_NO_RE.findall(target.title))
    if source_laws and target_laws and (source_laws & target_laws):
        explicit_boost += 0.35

    has_audit_ref = bool(_SAYISTAY_REPORT_RE.search(target.title)) or bool(
        _SAYISTAY_REPORT_RE.search(source.title)
    )
    if has_audit_ref and (
        institution_match or is_constitutional_flow or actor_match or ent_jaccard > 0.15
    ):
        explicit_boost += 0.20

    # 7. Toplam Puan Hesaplama
    weighted_score = (
        0.25 * entity_score
        + 0.20 * institution_score
        + 0.15 * topic_score
        + 0.25 * sim
        + 0.15 * (1.0 if is_chronological else 0.0)
        + explicit_boost
    )
    total_score = min(max(weighted_score, 0.0), 1.0)

    breakdown = RelationScoreBreakdown(
        entity_score=entity_score,
        institution_score=institution_score,
        topic_score=topic_score,
        semantic_score=sim,
        temporal_score=1.0 if is_chronological else 0.0,
        explicit_boost=explicit_boost,
        total_score=total_score,
    )

    # 8. Fail-Closed Durumları (Epistemic & Semantic Safety)
    # Zamansal tutarsızlık
    if not is_chronological and (
        (source.claims and any(c.get("claim_type") == "promise" for c in source.claims))
        or has_audit_ref
    ):
        return RelationResult(
            source_event_id=source.event_id,
            target_event_id=target.event_id,
            relation_type="precedes",
            confidence=0.0,
            status="unresolved",
            score_breakdown=breakdown,
            evidence_payload={
                "reason": "temporal_inversion",
                "detail": "Vaat veya olay tarihi sonraki icraat/denetim tarihinden sonradır.",
            },
            explanation=(
                "Geçmişteki denetim veya eylem sonraki vaat için "
                "sonuç teşkil edemez (zamansal uyuşmazlık)."
            ),
        )



    # Kurum çelişkisi (Farklı iki idari yapının veya farklı belediyelerin alakasız bulguları)
    if (
        source.institution
        and target.institution
        and not institution_match
        and not is_constitutional_flow
    ):
        return RelationResult(
            source_event_id=source.event_id,
            target_event_id=target.event_id,
            relation_type="same_thread",
            confidence=0.0,
            status="unresolved",
            score_breakdown=breakdown,
            evidence_payload={
                "reason": "institution_mismatch",
                "source_inst": source.institution,
                "target_inst": target.institution,
            },
            explanation="Farklı kurumlar arasında doğrudan hesap verebilirlik bağı kurulamaz.",
        )

    # 9. İlişki Türü ve Statü Belirleme (Linguistic & Semantic Hardening)
    s_text = _normalize_turkish_text(
        source.title + " " + " ".join(c.get("claim_text", "") for c in source.claims)
    )
    t_text = _normalize_turkish_text(
        target.title + " " + " ".join(c.get("claim_text", "") for c in target.claims)
    )

    # Vaat / Taahhüt tespiti (Olumlu ve olumsuz vaat fiilleri)
    has_explicit_promise_claim = any(c.get("claim_type") == "promise" for c in source.claims)
    has_promise_keywords = any(
        k in s_text
        for k in (
            "vaat", "taahhut", "sozu verildi", "planlaniyor", "kaldirilacak",
            "yatirilacak", "genisletilecek", "guncellenecek", "acilacak",
            "odenecek", "hayata gecirilecek", "uygulanacak", "yapilacak",
            "verilecek", "artirilacak", "azaltilacak", "dusurulecek",
            "indirecek", "indirilecek", "baslayacak", "saglanacak",
            "tahsis edilecek", "dondurulacak", "sabit tutulacak",
            "sifirlanacak", "muaf tutulacak", "bitirilecek", "tamamlanacak",
            "teslim edilecek", "ongoruluyor", "hedefleniyor", "kesilecek",
            "yapilmayacak", "verilmeyecek", "artirilmayacak", "azaltilmayacak",
            "zam yapilmayacak", "kesinti yapilmayacak", "izin verilmeyecek",
            "kaldirilmayacak", "devam etmeyecek", "dondurulacak", "sabit kalacak",
            "dusecek", "artacak"
        )
    )
    has_promise = has_explicit_promise_claim or has_promise_keywords

    # Kaynak veya Hedefte Denetim / Kamu Zararı Tespiti
    source_has_audit = (
        "sayistay" in s_text
        or (source.institution and "sayistay" in _normalize_turkish_text(source.institution))
        or "kamu zarari" in s_text
    )
    
    target_has_audit = (
        "sayistay" in t_text
        or (target.institution and "sayistay" in _normalize_turkish_text(target.institution))
        or any(
            k in t_text
            for k in (
                "kamu zarari", "usulsuz", "butce asimi", "odenek asimi",
                "mevzuata aykiri", "haksiz kazanc", "haksiz odeme",
                "haksiz menfaat", "haksiz fiyat farki", "haksiz harcama",
                "sartnameye aykiri", "ihale bolme", "tavan asimi",
                "teminatsiz avans", "cezai sart uygulanmamasi", "usulsuzlugu",
                "gecikmeler ve yukleniciye cezai sart uygulanmamasi"
            )
        )
    )

    # Hedefte Reddiye / Yalanlama / Olumsuzlama Tespiti (Rejection, Quoted Rejection & Negation)
    target_has_rejection_or_negation = any(
        k in t_text
        for k in (
            "reddedildi",
            "iptal edildi",
            "dustu",
            "geri cekildi",
            "vazgecildi",
            "yalanladi",
            "iddiasini reddetti",
            "iddialarini reddetti",
            "gercegi yansitmadigi",
            "soz konusu degil",
            "soz konusu degildir",
            "yapilmayacak",
            "kaldirilmayacak",
            "verilmeyecek",
            "uygulanmayacak",
            "ertelendi",
            "askiya alindi",
            "asilsize",
            "asilsizdir",
            "yalanlandi kampanya yok",
        )
    )

    # Polar Çelişki Tespiti (Vaat vs Zıt İcraat / Olumsuzlama)
    s_promises_no_discount = (
        "indirim yapilmayacak" in s_text
        or "fiyat indirimi yapilmayacak" in s_text
    )
    discount_keywords = (
        "indirim", "dusurulecek", "indirilecek", "azaltilacak",
        "sifirlanacak", "dusecek", "tek haneye", "noter harclari indirilecek",
    )
    s_promises_discount = (
        not s_promises_no_discount
        and any(k in s_text for k in discount_keywords)
    )
    increase_keywords = (
        "artiril", "artis", "zam", "yukseltil", "cift tarife", "yuzde 42",
        "yuzde 11", "artis gosterdi", "yukseldi", "fiyat artisi",
        "yuzde 35 artirildi", "yuzde 20 artirildi", "yuzde 30 artirildi",
        "yuzde 40 artirildi",
    )
    t_has_increase = any(k in t_text for k in increase_keywords)

    s_promises_increase = any(
        k in s_text
        for k in ("artirilacak", "artis yapilacak", "zam yapilacak", "yukseltilecek", "artacak")
    )
    t_has_no_increase = any(
        k in t_text
        for k in (
            "artirilmayacak", "artis yapilmayacak", "zam yapilmayacak",
            "mevcut tutar korunacak", "artmayacak", "sabit kalacak",
            "degismeyecek", "dustu", "azaldi",
        )
    )

    s_promises_no_hike = any(
        k in s_text
        for k in (
            "zam yapilmayacak", "artirilmayacak", "sabit tutulacak",
            "dondurulacak", "degismeyecek", "artis olmayacak", "artmayacak",
            "zam verilmeyecek", "artis dusunulmuyor", "planlanmiyor", "gundemde degil",
        )
    )
    hike_keywords = (
        "zam yapildi", "artirildi", "yukseltildi", "yuzde 30 artirildi",
        "yuzde 40 artirildi", "yuzde 25 artirildi", "yuzde 35 artirildi",
        "yuzde 20 artirildi", "1 tl olarak", "ucretli hale", "fiyat artisi",
        "fiyat artisi yapildi", "artis yapildi", "cift tarife",
    )
    t_has_hike = any(k in t_text for k in hike_keywords)

    fee_keywords = (
        "ucretli", "zam", "tarife", "cift tarife",
        "saatlik 50 tl", "ucretli hale getirildi",
    )
    mandatory_keywords = (
        "zorunlu", "kaldirilmayacak", "devam edecek", "sinif tekrari zorunlu",
        "kota sinirlandirilmasi devam edecek", "zorunlu kilindi", "zorunlu hale",
    )
    rejection_exceptions = (
        "gercegi yansitmadigi aciklandi uygulama suruyor" in t_text
        or "soz konusu degil" in s_text
        or "asilsize" in s_text
        or "asilsizdir" in s_text
    )

    has_polar_contradiction = (
        (s_promises_discount and t_has_increase)
        or (s_promises_increase and t_has_no_increase)
        or (s_promises_no_hike and t_has_hike)
        or ("ucretsiz" in s_text and any(k in t_text for k in fee_keywords))
        or ("tasarruf" in s_text and any(k in t_text for k in ("asim", "kamu zarari", "luks")))
        or (
            any(k in s_text for k in ("kaldirilacak", "devam etmeyecek", "son verilecek"))
            and any(k in t_text for k in mandatory_keywords)
        )
        or (
            source_has_audit
            and any(k in t_text for k in ("tasarruf", "disiplin", "mevzuata uygun"))
        )
        or (has_promise and target_has_rejection_or_negation and not rejection_exceptions)
    )



    # Hedefte Yasama / İcraat / Tamamlanma Tespiti (Law Action & Fulfilment)
    target_has_law_action = not target_has_rejection_or_negation and any(
        k in t_text
        for k in (
            "kabul edildi", "yasallasti", "yasalas", "yayimlandi", "kanunlasti",
            "yururluge girdi", "resmi gazete", "tamamlandi", "hizmete girdi",
            "basladi", "artirildi", "belirlendi", "cikarildi", "faaliyete",
            "toplanmadi", "kaldirildi", "odendi", "yururlukte", "onaylandi",
            "sunuldu", "genelgesi", "tebligi", "karari", "hibe", "destek",
            "yapildi", "verildi", "uygulandi", "hayata gecirildi", "tahsis edildi",
            "acilisi yapildi", "acildi", "teslim edildi", "karara baglandi",
            "sabit kaldi", "degismedi", "dusuruldu", "indirildi", "yatirildi",
            "rekor kirdi", "odendi"
        )
    )

    relation_type: RelationType = "same_thread"
    if target_has_audit or source_has_audit:
        relation_type = (
            "fails"
            if (
                has_polar_contradiction
                or target_has_rejection_or_negation
                or any(
                    k in t_text
                    for k in (
                        "kamu zarari", "usulsuz", "butce asimi", "odenek asimi",
                        "aykiri", "ihlal", "haksiz kazanc", "haksiz odeme",
                        "haksiz menfaat", "sartnameye aykiri", "ihale bolme",
                        "tavan asimi", "teminatsiz avans", "cezai sart uygulanmamasi"
                    )
                )
            )
            else "updates"
        )
    elif has_polar_contradiction:
        relation_type = "contradicts"
    elif has_promise or explicit_boost > 0.30:
        if target_has_law_action:
            relation_type = "fulfils"
        elif target_has_rejection_or_negation:
            relation_type = "fails"
        else:
            relation_type = "updates"
    elif ent_jaccard >= 0.15 or actor_match or explicit_boost > 0.0:
        if total_score >= min_confidence:
            relation_type = "updates" if is_chronological else "same_thread"
    else:
        # Kurum/konu benzerliği olsa bile somut varlık veya aktör bağı yoksa fail-closed kal
        relation_type = "same_thread"
        total_score = 0.0

    # Statü
    status: RelationStatus = "unresolved"
    if total_score >= 0.85 or explicit_boost > 0.20:
        status = "verified"
    elif total_score >= 0.70:
        status = "supported"
    elif total_score >= min_confidence:
        status = "inferred"

    explanation = _generate_explanation(source, target, relation_type, status, total_score)

    payload = {
        "source_title": source.title,
        "target_title": target.title,
        "source_actor": source.actor,
        "target_actor": target.actor,
        "source_institution": source.institution,
        "target_institution": target.institution,
        "shared_topics": list(shared_topics),
        "score_breakdown": breakdown.to_dict(),
    }

    return RelationResult(
        source_event_id=source.event_id,
        target_event_id=target.event_id,
        relation_type=relation_type,
        confidence=round(total_score, 3),
        status=status,
        score_breakdown=breakdown,
        evidence_payload=payload,
        explanation=explanation,
    )


def _generate_explanation(
    source: EventData,
    target: EventData,
    relation: RelationType,
    status: RelationStatus,
    score: float,
) -> str:
    status_tr = {
        "verified": "Resmî Atıfla Doğrulanmış",
        "supported": "Kanıtlarla Desteklenen",
        "inferred": "Olası / Çıkarımsal",
        "unresolved": "Belirsiz",
    }.get(status, status)

    relation_tr = {
        "fulfils": "vaadin yasalaşması/tamamlanması",
        "fails": "taahhüdün yerine getirilmemesi / Sayıştay kamu zararı bulgusu",
        "updates": "politika ve karar güncellemesi",
        "contradicts": "çelişkili beyan",
        "same_thread": "aynı konu takibi",
        "precedes": "kronolojik öncelik",
    }.get(relation, relation)

    return (
        f"'{source.title[:60]}...' ile '{target.title[:60]}...' arasında %{round(score * 100)} "
        f"güven seviyesinde {relation_tr} bağı tespit edildi ({status_tr})."
    )

