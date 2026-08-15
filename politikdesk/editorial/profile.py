"""Editoryal Kimlik Kartı — 10 soruluk editoryal profil ve alan sözlüğü (F3-08).

⛔ TASARIM KISITI (Spec §10.1, P6, KVKK m.6)
Bu formda **ideolojik soru yoktur ve eklenemez.** Siyasi düşünce özel
nitelikli kişisel veridir; sistemde onu kodlayacak bir alan bulunmaz.
Kısıt üç katmanda zorlanır:

  1. Şema      — `editorial_profiles`'ta alan yok (`migrations/0001`, `0009`)
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

# Spec §10.1 sol kolon — öğrenilebilir/saklanabilir editoryal ve biçimsel öznitelikler.
# Sağ kolondan (asla çıkarılmaz / ideolojik) hiçbir şey burada YOKTUR.
Tone = Literal["direct", "analytical", "critical", "ironic", "formal", "interpretive"]

TONES: Final[tuple[str, ...]] = (
    "direct",
    "analytical",
    "critical",
    "ironic",
    "formal",
    "interpretive",
)
SENTENCE_LENGTHS: Final[tuple[str, ...]] = ("short", "medium", "long")
EMOJI_LEVELS: Final[tuple[str, ...]] = (
    "none",
    "rare",
    "minimal",
    "necessary",
    "frequent",
)
HASHTAG_LEVELS: Final[tuple[str, ...]] = (
    "none",
    "rare",
    "minimal",
    "topic_bound",
    "frequent",
)
USAGE_LEVELS: Final[tuple[str, ...]] = (
    "none",
    "rare",
    "minimal",
    "necessary",
    "topic_bound",
    "frequent",
)
CITATION_HABITS: Final[tuple[str, ...]] = (
    "always",
    "always_link",
    "necessary",
    "sometimes",
    "inline_short",
)
QUOTE_HABITS: Final[tuple[str, ...]] = (
    "direct_quote",
    "summarized",
    "minimal_quote",
)
UNCERTAINTY_HANDLINGS: Final[tuple[str, ...]] = (
    "explicit",
    "essential_only",
    "natural_concise",
)

MAX_AVOID_ITEMS: Final[int] = 16
MAX_TOPIC_ITEMS: Final[int] = 16
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


# Editoryal Profil Kartı — 10 soruluk tam editoryal mimari:
# Yazım tonu, cümle yapısı, biçimsellik, emoji, hashtag, kaynak tercihi,
# konu öncelikleri, kaçınılacak ifadeler, alıntı tercihi, belirsizlik yönetimi.
QUESTIONS: Final[tuple[Question, ...]] = (
    Question(
        number=1,
        field="tone",
        prompt="Yazarken hangi tonu kullanırsın?",
        kind="multi",
        choices=(
            ("direct", "Doğrudan — kısa, net, dolaysız"),
            ("analytical", "Analitik — neden-sonuç ve bağlam odaklı"),
            ("critical", "Eleştirel — iddiaları ve kararları sorgulayan"),
            ("ironic", "İronik — kontrollü, mesafeli mizah"),
            ("formal", "Resmî — ölçülü ve kurumsal"),
            ("interpretive", "Yorumlayıcı — olgudan sonra açık değerlendirme yapan"),
        ),
        help_text="Birden fazla seçebilirsin.",
    ),
    Question(
        number=2,
        field="sentence_length",
        prompt="Cümle yapısı tercihin nedir?",
        kind="single",
        choices=(
            ("short", "Kısa — çoğunlukla kısa cümleler"),
            ("medium", "Orta — kısa ve orta cümleleri dengeler"),
            ("long", "Uzun — gerektiğinde uzun, bağlantılı cümleler"),
        ),
        help_text="Katı kelime sayısı yerine genel yazım eğilimi olarak uygulanır.",
    ),
    Question(
        number=3,
        field="formality",
        prompt="Biçimsellik düzeyin (1 = çok samimi, 5 = çok resmî)",
        kind="scale",
        help_text="1 = konuşma dili, 3 = dengeli ve doğal, 5 = resmî ve kurumsal.",
    ),
    Question(
        number=4,
        field="emoji_usage",
        prompt="Emoji kullanım alışkanlığın nedir?",
        kind="single",
        choices=(
            ("none", "Hiç — emoji kullanma"),
            ("rare", "Nadiren — yalnızca çok gerektiğinde"),
            ("necessary", "Gerektiğinde — yalnızca vurgu ve bağlam için"),
            ("frequent", "Sık — doğal akışta serbestçe"),
        ),
    ),
    Question(
        number=5,
        field="hashtag_usage",
        prompt="Hashtag kullanım alışkanlığın nedir?",
        kind="single",
        choices=(
            ("none", "Hiç — hashtag kullanma"),
            ("rare", "Nadiren — en fazla 1 adet"),
            ("topic_bound", "Konuya özgü olduğunda — yalnızca doğrudan ilgili etiketler"),
            ("frequent", "Sık — ilgili konularda serbestçe"),
        ),
        help_text="Etkileşim artırmak amacıyla gereksiz çoğaltılmaz.",
    ),
    Question(
        number=6,
        field="citation_policy",
        prompt="Kaynak gösterme tercihin nedir?",
        kind="single",
        choices=(
            ("always_link", "Her zaman — İddia/haber içeren içeriklerde kaynak bağlantısı göster"),
            ("sometimes", "Gerektiğinde — Önemli/doğrulanması gereken iddialarda kaynak göster"),
            (
                "inline_short",
                "Kısa format — Kaynağı metinde belirt; bağlantıyı yalnızca gerektiğinde ekle",
            ),
        ),
        help_text="Tercihin ne olursa olsun doğrulanabilir iddialarda kaynak şeffaflığı korunur.",
    ),
    Question(
        number=7,
        field="topic_priorities",
        prompt="Hangi konular önceliğin? (virgülle ayır)",
        kind="list",
        help_text="Örn: Ekonomi, enflasyon, faiz, bütçe, kamu harcamaları. Feed sıralamasında "
        "kişisel bileşeni (0-10) besler; saklanan global skoru ve kanıt ağırlığını değiştirmez.",
    ),
    Question(
        number=8,
        field="avoid_list",
        prompt="Kaçınmamı istediğin kalıplar ve kelimeler? (virgülle ayır)",
        kind="list",
        help_text="Örn: 'tarihi karar', 'çarpıcı', 'şok', 'skandal', gereksiz ünlem. "
        "Bu senin tercihindir; doğrudan alıntıların özgün anlamı hariç bu ifadelerden kaçınılır.",
    ),
    Question(
        number=9,
        field="quote_habit",
        prompt="Alıntı ve haber aktarım tercihin nedir?",
        kind="single",
        choices=(
            ("direct_quote", "Doğrudan alıntı — kaynağın ifadesini tırnak içinde koru"),
            ("summarized", "Özetleyerek aktar — anlamı koruyarak kendi cümlelerinle aktar"),
            (
                "minimal_quote",
                "Gerektiğinde alıntı — yalnızca kritik ifadelerde doğrudan alıntı yap",
            ),
        ),
        help_text="Doğrudan alıntılarda kaynağın özgün ifadesine ve bağlamına sadık kalınır.",
    ),
    Question(
        number=10,
        field="uncertainty_handling",
        prompt="Doğrulanmamış veya tek kaynaklı bilgide belirsizlik dili tercihin nedir?",
        kind="single",
        choices=(
            (
                "explicit",
                "Açıkça belirt — 'iddia edildi', 'ilk bilgilere göre', 'doğrulanmadı' gibi",
            ),
            (
                "essential_only",
                "Yalnızca önemli durumlarda — kritik ve riskli iddialarda açıkça belirt",
            ),
            (
                "natural_concise",
                "Kısa ve doğal — metin akışını bozmadan ölçülü ve doğal ifadelerle",
            ),
        ),
        help_text=(
            "Yeterince doğrulanmamış bilgilerde kesinlik üretilmez; olgu ve iddia ayrımı korunur."
        ),
    ),
)

# Derleyicinin okumasına izin verilen alanlar. Bu bir beyaz listedir:
# `editorial_profiles`'a bir gün yanlışlıkla başka bir sütun eklenirse
# prompta sızmaz.
COMPILABLE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "tone",
        "sentence_length",
        "formality",
        "emoji_usage",
        "hashtag_usage",
        "citation_habit",
        "citation_policy",
        "topic_priorities",
        "avoid_list",
        "quote_habit",
        "uncertainty_handling",
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

    emoji = _one_of("emoji_usage", EMOJI_LEVELS)
    hashtag = _one_of("hashtag_usage", HASHTAG_LEVELS)

    # citation_policy ana alandır; citation_habit geriye dönük uyumluluk içindir.
    if raw.get("citation_policy") not in (None, ""):
        citation_val = _one_of("citation_policy", CITATION_HABITS)
    else:
        citation_val = _one_of("citation_habit", CITATION_HABITS)

    return {
        "tone": tones,
        "sentence_length": _one_of("sentence_length", SENTENCE_LENGTHS),
        "formality": formality,
        "emoji_usage": emoji,
        "hashtag_usage": hashtag,
        "citation_habit": citation_val,
        "citation_policy": citation_val,
        "topic_priorities": _clean_list(raw.get("topic_priorities"))[:MAX_TOPIC_ITEMS],
        "avoid_list": _clean_list(raw.get("avoid_list"))[:MAX_AVOID_ITEMS],
        "quote_habit": _one_of("quote_habit", QUOTE_HABITS),
        "uncertainty_handling": _one_of("uncertainty_handling", UNCERTAINTY_HANDLINGS),
    }
