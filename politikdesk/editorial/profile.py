"""Editoryal Kimlik Kartı — 7 soruluk form ve alan sözlüğü (F3-08).

⛔ TASARIM KISITI (Spec §10.1, P6, KVKK m.6)
Bu formda **ideolojik soru yoktur ve eklenemez.** Siyasi düşünce özel
nitelikli kişisel veridir; sistemde onu kodlayacak bir alan bulunmaz.
Kısıt üç katmanda zorlanır:

  1. Şema      — `editorial_profiles`'ta alan yok (`migrations/0001`)
  2. Bu modül  — `QUESTIONS` beyaz listedir; derleyici başka alan okumaz
  3. Test      — `tests/test_editorial.py` hem soruları hem derlenmiş
                 promptu yasaklı terimlere karşı tarar

Form yanıtları **bir kez** derlenir ve `editorial_profiles.compiled_prompt`
alanında saklanır (F3-09). Her üretimde yeniden analiz yapılmaz — Spec
§10.2'nin token maliyeti optimizasyonu.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Literal

# Spec §10.1 sol kolon — öğrenilebilir/saklanabilir biçimsel öznitelikler.
# Sağ kolondan (asla çıkarılmaz) hiçbir şey burada YOKTUR.
Tone = Literal["direct", "analytical", "ironic", "formal"]

TONES: Final[tuple[str, ...]] = ("direct", "analytical", "ironic", "formal")
SENTENCE_LENGTHS: Final[tuple[str, ...]] = ("short", "medium", "long")
USAGE_LEVELS: Final[tuple[str, ...]] = ("none", "minimal", "frequent")
CITATION_HABITS: Final[tuple[str, ...]] = ("always_link", "sometimes", "never")

MAX_AVOID_ITEMS: Final[int] = 12
MAX_TOPIC_ITEMS: Final[int] = 12
MAX_ITEM_LEN: Final[int] = 80


@dataclass(frozen=True)
class Question:
    """Formdaki tek bir soru. `field` doğrudan şema sütununa karşılık gelir."""

    number: int
    field: str
    prompt: str
    kind: Literal["multi", "single", "scale", "list"]
    choices: tuple[tuple[str, str], ...] = ()
    help_text: str = ""


# Spec §10.2: "kullanıcı onboarding'de 7 soruluk bir formu doldurur".
# Soru sayısı sabittir; sekizinci soru eklemek Spec değişikliği gerektirir.
QUESTIONS: Final[tuple[Question, ...]] = (
    Question(
        number=1,
        field="tone",
        prompt="Yazarken hangi tonu kullanırsın?",
        kind="multi",
        choices=(
            ("direct", "Doğrudan — kısa, iddialı, süssüz"),
            ("analytical", "Analitik — veriyi açar, bağlam kurar"),
            ("ironic", "İronik — mesafeli, esprili"),
            ("formal", "Resmî — ölçülü, kurumsal"),
        ),
        help_text="Birden fazla seçebilirsin.",
    ),
    Question(
        number=2,
        field="sentence_length",
        prompt="Cümlelerin genelde ne uzunlukta?",
        kind="single",
        choices=(
            ("short", "Kısa — tek soluk, 10-15 kelime"),
            ("medium", "Orta — bağlaçlı, 15-25 kelime"),
            ("long", "Uzun — çok yan cümleli"),
        ),
    ),
    Question(
        number=3,
        field="emoji_usage",
        prompt="Emoji ve hashtag alışkanlığın nedir?",
        kind="single",
        choices=(
            ("none", "Hiç kullanmam"),
            ("minimal", "Nadiren, vurgu için"),
            ("frequent", "Sık kullanırım"),
        ),
        help_text="Hashtag için ayrıca sorulur; ikisi aynı alışkanlığın parçasıdır.",
    ),
    Question(
        number=4,
        field="citation_habit",
        prompt="Kaynak gösterme alışkanlığın nedir?",
        kind="single",
        choices=(
            ("always_link", "Her zaman link veririm"),
            ("sometimes", "Önemli olduğunda veririm"),
            ("never", "Metinde belirtirim, link vermem"),
        ),
    ),
    Question(
        number=5,
        field="formality",
        prompt="Biçimsellik düzeyin (1 = çok samimi, 5 = çok resmî)",
        kind="scale",
    ),
    Question(
        number=6,
        field="topic_priorities",
        prompt="Hangi konular önceliğin? (virgülle ayır)",
        kind="list",
        help_text="Örn: enflasyon, faiz, bütçe, kur. Feed sıralamasında "
        "kişisel bileşeni (0-10) besler; saklanan global skoru değiştirmez.",
    ),
    Question(
        number=7,
        field="avoid_list",
        prompt="Kaçınmamı istediğin kalıplar/kelimeler? (virgülle ayır)",
        kind="list",
        help_text="Örn: 'tarihi karar', 'çarpıcı', ünlem işareti. "
        "Bu senin kendi kuralın; sistem buna bir yargı yüklemez.",
    ),
)

# 3. soru iki sütun doldurur (emoji + hashtag aynı alışkanlığın parçası).
# Ayrı sütunlar tutulur çünkü Faz 5'in stil çıkarımı (B-01) ikisini
# bağımsız ölçebilir; form onları tek soruda topladığı için 7 kalır.
_LINKED_USAGE_FIELD: Final[str] = "hashtag_usage"

# Derleyicinin okumasına izin verilen alanlar. Bu bir beyaz listedir:
# `editorial_profiles`'a bir gün yanlışlıkla başka bir sütun eklenirse
# prompta sızmaz.
COMPILABLE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "tone",
        "sentence_length",
        "emoji_usage",
        "hashtag_usage",
        "citation_habit",
        "formality",
        "topic_priorities",
        "avoid_list",
    }
)


def _clean_list(raw: Any) -> list[str]:
    """Serbest metin listesini temizler: boşları at, kırp, sınırla."""
    if isinstance(raw, str):
        items = [part.strip() for part in raw.split(",")]
    elif isinstance(raw, list | tuple):
        items = [str(part).strip() for part in raw]
    else:
        return []
    return [item[:MAX_ITEM_LEN] for item in items if item]


def normalize_answers(raw: dict[str, Any]) -> dict[str, Any]:
    """Form yanıtlarını şema sütunlarına çevirir ve doğrular.

    Geçersiz bir seçim sessizce varsayılana düşürülmez — `ValueError`
    fırlatılır. Sessiz düşürme, kullanıcının cevabını değiştirmek olurdu.
    """
    tones = [t for t in _clean_list(raw.get("tone")) if t]
    unknown = [t for t in tones if t not in TONES]
    if unknown:
        raise ValueError(f"Bilinmeyen ton: {unknown}. Seçenekler: {list(TONES)}")

    def _one_of(field: str, allowed: tuple[str, ...]) -> str | None:
        value = raw.get(field)
        if value in (None, ""):
            return None
        if value not in allowed:
            raise ValueError(f"{field} için geçersiz değer: {value!r}. Seçenekler: {list(allowed)}")
        return str(value)

    formality_raw = raw.get("formality")
    formality: int | None = None
    if formality_raw not in (None, ""):
        formality = int(formality_raw)
        if not 1 <= formality <= 5:
            raise ValueError(f"formality 1-5 aralığında olmalı, {formality} verildi.")

    emoji = _one_of("emoji_usage", USAGE_LEVELS)
    # 3. soru tek soru, iki sütun: açıkça verilmediyse emoji cevabı miras alınır.
    hashtag = _one_of(_LINKED_USAGE_FIELD, USAGE_LEVELS) or emoji

    return {
        "tone": tones,
        "sentence_length": _one_of("sentence_length", SENTENCE_LENGTHS),
        "emoji_usage": emoji,
        "hashtag_usage": hashtag,
        "citation_habit": _one_of("citation_habit", CITATION_HABITS),
        "formality": formality,
        "topic_priorities": _clean_list(raw.get("topic_priorities"))[:MAX_TOPIC_ITEMS],
        "avoid_list": _clean_list(raw.get("avoid_list"))[:MAX_AVOID_ITEMS],
    }
