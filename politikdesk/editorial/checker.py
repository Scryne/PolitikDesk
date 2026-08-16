"""Pre-publish Check — yayın öncesi editoryal kontrol (F3-13 · Spec §14.4).

Spec §14.4'ün altı kontrolü, ekrandaki sırayla:

| # | Anahtar | Kontrol | En kötü durum |
|---|---|---|---|
| 1 | `source_link`   | Kaynak linki mevcut | ✗ hata |
| 2 | `numeric_match` | Tüm sayısal veriler kanıtla eşleşti | ✗ **ENGELLEYİCİ** |
| 3 | `news_opinion`  | Haber ile yorum ayrı işaretlendi | ⚠ uyarı |
| 4 | `single_source` | Tek kaynaklı iddia kullanımı | ⚠ uyarı |
| 5 | `unlinked`      | Hiçbir kanıta bağlanamayan cümle | ✗ hata (sayı içeriyorsa ENGELLEYİCİ) |
| 6 | `missing_context`| Eksik bağlam | ⓘ bilgi |

**Engelleyici durum** (Spec §14.4 son paragraf): kanıta bağlanamayan
*sayısal* iddia bulunursa "Yine de devam et" bir onay kutusu olmadan
etkinleşmez. Bu, Spec §12.1'in (TCK m. 217/A) UI karşılığıdır.

### F3-12 ile ilişkisi — ikisi aynı şey değildir

`grounding_check` **halüsinasyon savunmasıdır**: kanıtta olmayan bir sayı
metne girdi mi? Bu modül **editoryal kalitedir**: sayı kanıtta var ama
cümle hiçbir iddiaya bağlanmıyor mu, yorum haber gibi mi sunulmuş mu?

Bir taslak grounding'i geçip bu kontrolde takılabilir (tersi de olur).
İkisi ayrı kapılara bağlıdır: G3 koşul 2 grounding'e, koşul 3 buraya.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from politikdesk.editorial.generator import GeneratedDraft
from politikdesk.editorial.grounding_check import (
    GroundingReport,
    _number_candidates,
    build_context,
    check,
)
from politikdesk.editorial.guards import ClaimForGeneration
from politikdesk.nlp.claims import fold_text

CHECKER_VERSION: Final[str] = "prepublish-check@1.0.0"

Severity = Literal["ok", "warn", "error", "info"]

SEVERITY_MARK: Final[dict[str, str]] = {
    "ok": "✓",
    "warn": "⚠",
    "error": "✗",
    "info": "ⓘ",
}

# Cümle sınırı: nokta/ünlem/soru + boşluk + büyük harf veya tırnak.
# Sayı içindeki nokta ("13.704,98") boşlukla takip edilmediği için
# bölmez — Türkçe binlik ayırıcısıyla çalışan bir bölücünün ilk şartı.
_SENTENCE_SPLIT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<=[.!?…])\s+(?=[\"“«(\[]?[A-ZÇĞİÖŞÜ0-9%])"
)

# Bağlanabilirlik hesabında sayılmayan sözcükler. Kısa liste kasıtlı:
# uzun bir durak listesi, gerçekten boş bir cümleyi "bağlandı" gösterecek
# kadar az içerik sözcüğü bırakabilir.
_STOPWORDS: Final[frozenset[str]] = frozenset(
    {
        "ve",
        "ile",
        "ama",
        "fakat",
        "ancak",
        "veya",
        "ya",
        "de",
        "da",
        "ki",
        "bu",
        "şu",
        "o",
        "bir",
        "iki",
        "için",
        "gibi",
        "kadar",
        "daha",
        "en",
        "olarak",
        "olan",
        "oldu",
        "olduğu",
        "sonra",
        "önce",
        "göre",
        "her",
        "çok",
        "az",
        "yine",
        "ise",
        "hem",
        "tüm",
        "bütün",
        "kendi",
        "böyle",
        "yani",
        "ayrıca",
        "yaklaşık",
        "bazı",
        "diğer",
        "üzere",
    }
)
_MIN_TOKEN_LEN: Final[int] = 4

# Bir cümlenin kanıta bağlı sayılması için içerik sözcüklerinin en az bu
# oranı kanıt evreninde geçmelidir. Değer, G3 koşul 3'ün (yanlış-negatif
# ≤ %5) ölçüldüğü yerdir; `tests/test_editorial.py` sınırda örneklerle
# korur ve değiştirilirse yeniden ölçülmesi gerekir.
LINK_THRESHOLD: Final[float] = 0.4

# Yorum sinyalleri — "bu cümle haber değil, değerlendirme" göstergeleri.
# Liste bir yargı üretmez, yalnızca İŞARETLENMEMİŞ yorumu sorar.
_OPINION_MARKERS: Final[tuple[str, ...]] = (
    "bence",
    "kanımca",
    "görünüyor",
    "anlaşılıyor",
    "beklenebilir",
    "olabilir",
    "gerekir",
    "gerekiyor",
    "malesef",
    "maalesef",
    "ne yazık",
    "aslında",
    "muhtemelen",
    "büyük ihtimalle",
    "sürpriz değil",
    "dikkat çekici",
    "endişe verici",
    "olumlu",
    "olumsuz",
    "başarısız",
    "yetersiz",
    "riskli",
    "kritik",
    "önemli bir sinyal",
    "sorun",
)


@dataclass(frozen=True)
class CheckItem:
    """Altı kontrolden birinin sonucu."""

    key: str
    label: str
    severity: Severity
    detail: str = ""
    items: tuple[str, ...] = ()
    blocking: bool = False

    @property
    def mark(self) -> str:
        return SEVERITY_MARK[self.severity]

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "severity": self.severity,
            "mark": self.mark,
            "detail": self.detail,
            "items": list(self.items),
            "blocking": self.blocking,
        }


@dataclass(frozen=True)
class CheckReport:
    """Spec §14.4 ekranının veri karşılığı."""

    items: tuple[CheckItem, ...]
    checker_version: str = CHECKER_VERSION

    @property
    def is_blocking(self) -> bool:
        """ "Yine de devam et" onay kutusu gerektiriyor mu?"""
        return any(i.blocking for i in self.items)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.items)

    @property
    def passed(self) -> bool:
        return not self.has_errors and not self.is_blocking

    def as_dict(self) -> dict[str, Any]:
        return {
            "checker_version": self.checker_version,
            "is_blocking": self.is_blocking,
            "has_errors": self.has_errors,
            "passed": self.passed,
            "items": [i.as_dict() for i in self.items],
        }

    def render_text(self) -> str:
        """Spec §14.4'teki metin çıktısı (CLI ve testler için)."""
        lines = ["YAYIN ÖNCESİ KONTROL", ""]
        for item in self.items:
            line = f"{item.mark}  {item.label}"
            if item.detail:
                line = f"{line:<52}{item.detail}"
            lines.append(line)
            lines.extend(f"       → {entry}" for entry in item.items)
        if self.is_blocking:
            lines += [
                "",
                "ENGELLEYİCİ: kanıta bağlanamayan sayısal iddia var. "
                "'Yine de devam et' onay kutusu gerektirir.",
            ]
        return "\n".join(lines)


# ------------------------------------------------------------- yardımcılar
def split_sentences(text: str) -> list[str]:
    """Türkçe metni cümlelere böler (binlik ayırıcısına takılmadan)."""
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text.strip())]
    return [p for p in parts if p]


def _content_tokens(text: str) -> list[str]:
    tokens = re.findall(r"\w+", fold_text(text))
    return [
        t for t in tokens if len(t) >= _MIN_TOKEN_LEN and t not in _STOPWORDS and not t.isdigit()
    ]


def _link_ratio(sentence: str, haystack: str) -> float:
    """Cümlenin içerik sözcüklerinin kaçı kanıt evreninde geçiyor?

    Kök eşleştirme yapılmaz; Türkçe eklerin ilk 5 harfi genelde kökü
    taşır ve önek karşılaştırması, tam eşleşmenin kaçırdığı çekim
    biçimlerini ("faizi" / "faizin") yakalar.
    """
    tokens = _content_tokens(sentence)
    if not tokens:
        return 1.0  # içerik sözcüğü yoksa bağlanabilirlik iddiası da yok
    hits = sum(1 for t in tokens if t in haystack or t[:5] in haystack)
    return hits / len(tokens)


def _has_number(text: str) -> bool:
    return bool(_number_candidates(fold_text(text)))


def _opinion_markers(sentence: str) -> list[str]:
    folded = fold_text(sentence)
    return [m for m in _OPINION_MARKERS if fold_text(m) in folded]


# ------------------------------------------------------------- kontroller
def _check_source_link(draft: GeneratedDraft, cited: Sequence[ClaimForGeneration]) -> CheckItem:
    """1 — Kaynak linki mevcut."""
    urls = sorted(
        {str(e.get("canonical_url")) for c in cited for e in c.evidence if e.get("canonical_url")}
    )
    if urls:
        return CheckItem("source_link", "Kaynak linki mevcut", "ok", f"({len(urls)} link)")
    # Kanıt var ama URL yok: kaynak adları taşınıyorsa uyarı, hiç yoksa hata.
    named = [e.get("source_name") for c in cited for e in c.evidence if e.get("source_name")]
    if named:
        return CheckItem(
            "source_link",
            "Kaynak linki yok — kaynak yalnızca adıyla anılabiliyor",
            "warn",
            f"({len(set(map(str, named)))} kaynak)",
        )
    return CheckItem(
        "source_link",
        "Kaynak linki bulunamadı",
        "error",
        "(0 link)",
        ("Atıf yapılan iddiaların hiçbirinde kaynak bağlantısı yok.",),
    )


def _check_numeric_match(grounding: GroundingReport) -> CheckItem:
    """2 — Tüm sayısal veriler kanıtla eşleşti (ENGELLEYİCİ olabilir)."""
    bad = [i for i in grounding.issues if i.kind == "number"]
    total = grounding.numbers_checked
    matched = total - len(bad)

    if total == 0:
        return CheckItem("numeric_match", "Metinde sayısal veri yok", "ok", "(0/0)")
    if not bad:
        return CheckItem(
            "numeric_match",
            "Tüm sayısal veriler kanıtla eşleşti",
            "ok",
            f"({matched}/{total})",
        )
    return CheckItem(
        "numeric_match",
        f"{len(bad)} sayı kanıtla eşleşmedi",
        "error",
        f"({matched}/{total})",
        tuple(f"{i.token} — kanıt setinde yok" for i in bad),
        blocking=True,  # Spec §14.4: kanıta bağlanamayan sayısal iddia
    )


def _check_news_opinion(draft: GeneratedDraft, sentences: Sequence[str]) -> CheckItem:
    """3 — Haber ile yorum ayrı işaretlendi."""
    marked = {fold_text(s) for s in draft.commentary_sentences}
    unmarked: list[str] = []
    for sentence in sentences:
        folded = fold_text(sentence)
        if any(folded in m or m in folded for m in marked):
            continue
        markers = _opinion_markers(sentence)
        if markers:
            unmarked.append(f"{sentence[:110]} (sinyal: {', '.join(markers[:3])})")

    if unmarked:
        return CheckItem(
            "news_opinion",
            f"{len(unmarked)} cümle yorum gibi ama işaretlenmemiş",
            "warn",
            f"({len(marked)} işaretli)",
            tuple(unmarked[:4]),
        )
    if marked:
        return CheckItem(
            "news_opinion",
            "Haber ile yorum ayrı işaretlendi",
            "ok",
            f"({len(marked)} yorum cümlesi)",
        )
    return CheckItem("news_opinion", "Haber ile yorum ayrı işaretlendi", "ok", "(yorum yok)")


def _check_single_source(cited: Sequence[ClaimForGeneration]) -> CheckItem:
    """4 — Tek kaynaklı iddia kullanımı."""
    weak = [
        c for c in cited if c.evidence_status in ("single_source", "unverified", "contradicted")
    ]
    if not weak:
        return CheckItem(
            "single_source",
            "Kullanılan iddiaların hepsi teyitli",
            "ok",
            f"({len(cited)} iddia)",
        )

    labels = {
        "single_source": "yalnızca tek kaynaklı",
        "unverified": "doğrulanmamış",
        "contradicted": "çelişkili",
    }
    return CheckItem(
        "single_source",
        f"{len(weak)} iddia tam teyitli değil",
        "warn",
        f"({len(weak)}/{len(cited)})",
        tuple(f'"{c.claim_text[:90]}" — {labels[c.evidence_status]}' for c in weak[:4]),
    )


def _check_unlinked(draft: GeneratedDraft, sentences: Sequence[str], haystack: str) -> CheckItem:
    """5 — Hiçbir kanıta bağlanamayan cümle (sayı içeriyorsa ENGELLEYİCİ)."""
    marked = {fold_text(s) for s in draft.commentary_sentences}
    unlinked: list[str] = []
    numeric_unlinked: list[str] = []

    for sentence in sentences:
        if _link_ratio(sentence, haystack) >= LINK_THRESHOLD:
            continue
        folded = fold_text(sentence)
        is_marked_opinion = any(folded in m or m in folded for m in marked)

        if _has_number(sentence):
            # Yorum olarak işaretlenmiş olması sayıyı mazur GÖSTERMEZ:
            # Spec §14.4'ün engelleyici durumu "kanıta bağlanamayan
            # SAYISAL iddia"dır ve etiket onu ortadan kaldırmaz.
            numeric_unlinked.append(sentence[:120])
        elif not is_marked_opinion:
            unlinked.append(sentence[:120])

    if numeric_unlinked:
        return CheckItem(
            "unlinked",
            f"{len(numeric_unlinked) + len(unlinked)} cümle hiçbir kanıta bağlanamadı",
            "error",
            "(sayısal)",
            tuple(f"{s}  → sayı içeriyor, kanıta bağlanamadı" for s in numeric_unlinked)
            + tuple(unlinked[:2]),
            blocking=True,
        )
    if unlinked:
        return CheckItem(
            "unlinked",
            f"{len(unlinked)} cümle hiçbir kanıta bağlanamadı",
            "error",
            "",
            tuple(f"{s}  (Tahmin/yorum olarak etiketle?)" for s in unlinked[:4]),
        )
    return CheckItem(
        "unlinked",
        "Her cümle bir kanıta bağlanabiliyor",
        "ok",
        f"({len(sentences)} cümle)",
    )


def _check_missing_context(
    draft: GeneratedDraft, sentences: Sequence[str], prior_context: Sequence[str]
) -> CheckItem:
    """6 — Eksik bağlam."""
    notes: list[str] = []

    body_folded = fold_text(draft.body)
    for title in prior_context:
        tokens = _content_tokens(title)
        if not tokens:
            continue
        hits = sum(1 for t in tokens if t[:5] in body_folded)
        if hits / len(tokens) < LINK_THRESHOLD:
            notes.append(f"Önceki bağlam metne girmemiş: {title[:90]}")

    for item in draft.unresolved:
        notes.append(f"Kanıtta yok, açıkta kalıyor: {item[:90]}")

    if notes:
        return CheckItem(
            "missing_context",
            "Eksik bağlam",
            "info",
            f"({len(notes)} not)",
            tuple(notes[:4]),
        )
    return CheckItem("missing_context", "Bağlam yeterli", "ok")


# ------------------------------------------------------------------ kamu API
_EMOJI = re.compile("[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f900-\U0001f9ff⬀-⯿]")
_HASHTAG = re.compile(r"(?:^|\s)#\w+", re.UNICODE)

# Profil değeri -> izin verilen azami adet. `frequent` sınırsızdır.
_ALLOWANCE: dict[str, int | None] = {
    "none": 0,
    "rare": 1,
    "minimal": 1,
    "necessary": 2,
    "topic_bound": 2,
    "frequent": None,
}


def _check_profile_form(draft: GeneratedDraft, profile: dict[str, Any] | None) -> CheckItem:
    """Editoryal profilin BİÇİMSEL kuralları tutuluyor mu (F5-21).

    Profil, ürünün kullanıcıya verdiği bir sözdür: "emoji kullanma",
    "hashtag kullanma". Bu söz Faz 3'ten beri yalnızca **prompt'la**
    iletiliyordu ve hiçbir makine denetimi yoktu — oysa Spec §11.5 açıkça
    "prompt talimatı yeterli değil; programatik kontrol şart" diyor.

    Boşluk ölçümle görüldü (F5-15 model kıyaslaması): profil
    `emoji_usage: none` ve `hashtag_usage: none` derken
    `meta/llama-3.3-70b-instruct` taslağa "📊" ve "#Vergi #Ekonomi"
    ekledi. Grounding kontrolleri bunu görmez — kanıt açısından metin
    kusursuzdu, kullanıcının biçim tercihi açısından değil.

    Yalnızca OBJEKTİF olarak sayılabilen iki kural denetlenir. Cümle
    uzunluğu ve resmiyet gibi öznel eksenler bilinçli olarak dışarıda:
    ölçülemeyen bir kuralı kontrol diye göstermek, kontrolün kendisini
    değersizleştirir.
    """
    if not profile:
        return CheckItem("profile_form", "Editoryal biçim (profil yok)", "ok")

    problems: list[str] = []
    for label, pattern, field in (
        ("emoji", _EMOJI, "emoji_usage"),
        ("hashtag", _HASHTAG, "hashtag_usage"),
    ):
        allowance = _ALLOWANCE.get(str(profile.get(field) or "none"), 0)
        if allowance is None:
            continue
        found = pattern.findall(draft.body)
        if len(found) > allowance:
            problems.append(f"{label}: {len(found)} adet (profil azami {allowance})")

    if problems:
        return CheckItem(
            "profile_form",
            "Editoryal biçim tercihleri",
            "warn",
            detail="; ".join(problems),
            items=tuple(problems),
        )
    return CheckItem("profile_form", "Editoryal biçim tercihlerine uygun", "ok")


_IMPUTATION_WORDS: Final[tuple[str, ...]] = (
    "yolsuzluk yaptı",
    "rüşvet aldı",
    "rüşvet verdi",
    "zimmetine geçirdi",
    "hırsızlık yaptı",
    "dolandırdı",
    "vurgun yaptı",
    "sahtecilik yaptı",
    "suç işledi",
    "kamuyu zarara uğrattı",
)

_ATTRIBUTION_HEDGES: Final[tuple[str, ...]] = (
    "iddia edildi",
    "iddia ediliyor",
    "öne sürüldü",
    "öne sürülüyor",
    "raporunda yer aldı",
    "tutanakta yer aldı",
    "belirtildi",
    "soruşturma açıldı",
    "dava açıldı",
    "fezleke hazırlandı",
    "sayıştay raporuna göre",
    "tutanaklara göre",
    "ifade edildi",
)


def _check_imputation_language(sentences: Sequence[str]) -> CheckItem:
    """7 — İsnat Dili Kontrolü (B-96 · Spec v3.4 §14.4).

    Yargı kararı veya resmî tutanak kesinleşmeden doğrudan suç/fiil isnadı
    içeren ifadeler yerine aktarım/tutanak dili uyarısı üretir.
    """
    alerts: list[str] = []
    for s in sentences:
        s_folded = fold_text(s)
        for imp in _IMPUTATION_WORDS:
            if imp in s_folded and not any(hedge in s_folded for hedge in _ATTRIBUTION_HEDGES):
                alerts.append(f"Doğrudan isnat: '{imp}' (aktarım dili önerilir)")

    if alerts:
        return CheckItem(
            "imputation_language",
            f"{len(alerts)} cümlede doğrudan isnat dili tespit edildi",
            "warn",
            detail="Aktarım dili (iddia edildi/belirtildi) tercih edilmelidir.",
            items=tuple(alerts[:4]),
        )
    return CheckItem("imputation_language", "İsnat ve aktarım dili dengeli", "ok")


def run_checks(
    draft: GeneratedDraft,
    claims: Sequence[ClaimForGeneration],
    *,
    prior_context: Sequence[str] = (),
    grounding: GroundingReport | None = None,
    profile: dict[str, Any] | None = None,
) -> CheckReport:
    """Spec §14.4 kontrolleri + profil biçim ve isnat dili denetimi (F5-21, B-96).

    `claims`: üretime verilen TÜM iddialar (atıf yapılanları buradan
    süzülür). `prior_context`: olayın `same_thread` bağlarının başlıkları
    (F2-17 çıktısı) — 6. kontrolün girdisi. `profile`: editoryal profil
    satırı; verilmezse biçim denetimi atlanır.
    """
    cited_ids = set(draft.cited_claim_ids)
    cited = [c for c in claims if c.claim_id in cited_ids] or list(claims)

    evidence_texts = [
        *(c.claim_text for c in claims),
        *(str(e.get("quote_span") or "") for c in claims for e in c.evidence),
        *(str(e.get("source_name") or "") for c in claims for e in c.evidence),
    ]
    context = build_context(
        evidence_texts,
        normalized_values=[c.normalized_value for c in claims if c.normalized_value],
    )
    report = grounding if grounding is not None else check(draft.body, context)
    sentences = split_sentences(draft.body)

    return CheckReport(
        items=(
            _check_source_link(draft, cited),
            _check_numeric_match(report),
            _check_news_opinion(draft, sentences),
            _check_single_source(cited),
            _check_unlinked(draft, sentences, context.haystack),
            _check_missing_context(draft, sentences, prior_context),
            _check_profile_form(draft, profile),
            _check_imputation_language(sentences),
        )
    )


__all__ = [
    "CHECKER_VERSION",
    "LINK_THRESHOLD",
    "CheckItem",
    "CheckReport",
    "run_checks",
    "split_sentences",
]
