"""Grounding doğrulayıcısı — programatik (F3-12 · Spec §11.5, §15 madde 1-2).

DoD: üretilen metindeki her **sayı**, **tarih** ve **tırnak içi alıntı**,
kanıt setinde aranır; bulunamayan varsa üretim işaretlenir.

**Kapı G3 koşul 2 yalnızca bu modüle bakar** ve hedefi %0'dır (sert kapı,
Spec §13.2). Bu yüzden modül iki tasarım kararına sadıktır:

1. **Prompt talimatı kanıt değildir.** `llm/client.py`'deki
   `GROUNDING_INSTRUCTION` modele "kanıtta olmayanı yazma" der; burası o
   talimatın tutulup tutulmadığını ölçer. Spec §11.5 bunu açıkça ayırır:
   "prompt talimatı yeterli değil; makine denetimi şart."

2. **Belirsizlikte kanıttan yana, modelden yana değil.** Türkçe sayı
   yazımı çok biçimlidir ("1.234,56" / "1,234.56" / "3,5 milyar"); bir
   sayının hangi okunuşu kastettiği metinden anlaşılmayabilir. Bu yüzden
   HER İKİ TARAF için de tüm makul okunuşlar üretilir ve kesişim aranır.
   Sonuç: aynı sayıyı farklı biçimde yazan model cezalandırılmaz.

   Bunun bedeli bilinçli kabul edildi: model "1.234" yazarken kanıtta
   "1,234" *başka bir şeyi* kastediyorsa denetim bunu kaçırır. Bu dar
   durumun alternatifi, doğru taslakların çoğunu bloke eden bir kapıdır.

Kapsam dışı (bilinçli):
  * Yazıyla yazılmış sayılar ("yüzde bir buçuk") — rakam aranır.
  * Sayının ANLAMININ doğruluğu — o F3-13'ün "sayısal eşleşme" kontrolü.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Final, Literal

from politikdesk.nlp.claims import fold_text

CHECKER_VERSION: Final[str] = "grounding-check@1.0.0"

IssueKind = Literal["number", "date", "quote"]

# ---------------------------------------------------------------- sayılar
# Sayı gövdesi: basamak grupları, ayırıcı olarak "." veya ",".
# Türkçe metinde ek kesme işaretiyle gelir ("%1,78'lik"); ek yakalanmaz.
_NUMBER_RE: Final[re.Pattern[str]] = re.compile(r"\d[\d.,]*\d|\d")

# Büyüklük çarpanları (katlanmış biçimleriyle).
_MAGNITUDES: Final[dict[str, Decimal]] = {
    "bin": Decimal(10) ** 3,
    "milyon": Decimal(10) ** 6,
    "milyar": Decimal(10) ** 9,
    "trilyon": Decimal(10) ** 12,
    "katrilyon": Decimal(10) ** 15,
}
_MAGNITUDE_RE: Final[re.Pattern[str]] = re.compile(r"^[^\w]{0,3}(" + "|".join(_MAGNITUDES) + r")\b")

# --------------------------------------------------------------- tarihler
_MONTHS_TR: Final[tuple[str, ...]] = (
    "ocak",
    "şubat",
    "mart",
    "nisan",
    "mayıs",
    "haziran",
    "temmuz",
    "ağustos",
    "eylül",
    "ekim",
    "kasım",
    "aralık",
)
# Ay adları KATLANMIŞ biçimde tutulur ("ağustos" -> "agustos"). Elle
# yazmak yerine `fold_text` ile üretilir: iki farklı katlama tanımı,
# sessizce eşleşmeyen bir sözlük demektir.
_MONTH_INDEX: Final[dict[str, int]] = {fold_text(name): i + 1 for i, name in enumerate(_MONTHS_TR)}
_MONTH_ALT: Final[str] = "|".join(sorted(_MONTH_INDEX, key=len, reverse=True))

# "12 Ağustos 2026" / "12 ağustosta" / "Ağustos 2026" / "ağustosta"
# Ek (-ta, -da, -'ta, -ında) yakalanır ve atılır.
_DATE_TEXT_RE: Final[re.Pattern[str]] = re.compile(
    rf"(?:(?P<day>\d{{1,2}})\s+)?"
    rf"\b(?P<month>{_MONTH_ALT})(?:[’'ʼ]?[a-zıi]{{0,5}})?"
    rf"(?:\s+(?P<year>\d{{4}}))?"
)
_DATE_NUMERIC_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?P<day>\d{1,2})[./](?P<month>\d{1,2})[./](?P<year>\d{4})\b"
)
_DATE_ISO_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?P<year>\d{4})-(?P<month>\d{2})(?:-(?P<day>\d{2}))?\b"
)
# "2026-Q1" ve Türkçe karşılıkları ("2026'nın birinci çeyreği").
_QUARTER_ISO_RE: Final[re.Pattern[str]] = re.compile(r"\b(?P<year>\d{4})-q(?P<q>[1-4])\b")
_HALF_ISO_RE: Final[re.Pattern[str]] = re.compile(r"\b(?P<year>\d{4})-h(?P<h>[12])\b")
_ORDINAL_TR: Final[dict[str, int]] = {
    "birinci": 1,
    "ilk": 1,
    "1": 1,
    "ikinci": 2,
    "2": 2,
    "3": 3,
    "ucuncu": 3,
    "4": 4,
    "dorduncu": 4,
}
_QUARTER_TR_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?P<ord>" + "|".join(_ORDINAL_TR) + r")[’'ʼ.]?\w{0,4}\s+ceyre\w*"
)
# Yalın yıl: tarih kalıplarına uymaz, sayı yolunda özel işlem görür.
_YEAR_RE: Final[re.Pattern[str]] = re.compile(r"(?:19|20)\d{2}")

# ---------------------------------------------------------------- alıntı
# Tırnak biçimleri: düz, tipografik, açılı. Kesme işareti (') KASITLI
# olarak yok: Türkçede ek ayırıcıdır ("TÜİK'in"), alıntı işareti değil.
_QUOTE_RE: Final[re.Pattern[str]] = re.compile(r"[\"“”]([^\"“”]{2,300})[\"“”]|«([^»]{2,300})»")
# Tek kelimelik "vurgu tırnağı" alıntı sayılmaz: hem yaygın bir üslup
# aracıdır hem de tek kelime kanıt metninde neredeyse her zaman geçer,
# yani denetleyici değeri sıfırdır.
MIN_QUOTE_WORDS: Final[int] = 3


@dataclass(frozen=True)
class GroundingIssue:
    """Kanıt setinde karşılığı bulunamayan tek bir öğe."""

    kind: IssueKind
    token: str
    snippet: str

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "token": self.token, "snippet": self.snippet}

    @property
    def message(self) -> str:
        labels = {"number": "sayı", "date": "tarih", "quote": "alıntı"}
        return f"Kanıtta bulunmayan {labels[self.kind]}: {self.token!r}"


@dataclass(frozen=True)
class GroundingReport:
    """Bir taslağın grounding karnesi."""

    issues: tuple[GroundingIssue, ...]
    numbers_checked: int = 0
    dates_checked: int = 0
    quotes_checked: int = 0
    checker_version: str = CHECKER_VERSION

    @property
    def ok(self) -> bool:
        """Kanıt dışı tek bir öğe bile taslağı düşürür (G3 #2 = %0)."""
        return not self.issues

    @property
    def checked(self) -> int:
        return self.numbers_checked + self.dates_checked + self.quotes_checked

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checker_version": self.checker_version,
            "numbers_checked": self.numbers_checked,
            "dates_checked": self.dates_checked,
            "quotes_checked": self.quotes_checked,
            "issues": [i.as_dict() for i in self.issues],
        }


@dataclass(frozen=True)
class GroundingContext:
    """Taslağın dayanmasına izin verilen kanıt evreni.

    `haystack` katlanmış tek bir metindir (alıntı araması için);
    `numbers` ve `dates` ise o metinden ve `normalized_value`
    alanlarından türetilmiş kanonik kümelerdir.
    """

    haystack: str
    numbers: frozenset[Decimal]
    dates: frozenset[str]

    @property
    def is_empty(self) -> bool:
        return not self.haystack.strip()


# --------------------------------------------------------------- yardımcılar
def _decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(raw).normalize()
    except (InvalidOperation, ValueError):
        return None


def _separator_readings(token: str) -> set[Decimal]:
    """Bir sayı gövdesinin tüm makul okunuşları.

    "1.234,56" -> {1234.56}          (iki ayırıcı: sonuncusu ondalıktır)
    "41,2"     -> {41.2}             (grup 3 basamak değil: ondalık)
    "1,234"    -> {1.234, 1234}      (belirsiz: hem ondalık hem binlik)
    "1.234.567"-> {1234567}          (tek tip, çok kez: binlik)
    """
    token = token.strip(".,")
    if not token:
        return set()
    if not re.search(r"[.,]", token):
        value = _decimal(token)
        return {value} if value is not None else set()

    dots, commas = token.count("."), token.count(",")
    readings: set[Decimal] = set()

    def _add(text: str) -> None:
        value = _decimal(text)
        if value is not None:
            readings.add(value)

    if dots and commas:
        # Sonuncusu ondalık ayırıcıdır; diğeri gruplayıcı.
        decimal_sep = "." if token.rfind(".") > token.rfind(",") else ","
        group_sep = "," if decimal_sep == "." else "."
        _add(token.replace(group_sep, "").replace(decimal_sep, "."))
        return readings

    sep = "." if dots else ","
    parts = token.split(sep)
    if len(parts) > 2:
        # Birden çok ayırıcı tek anlama gelir: binlik gruplama.
        _add("".join(parts))
        return readings

    head, tail = parts
    _add(f"{head}.{tail}")  # ondalık okunuşu her zaman makul
    if len(tail) == 3 and 1 <= len(head) <= 3:
        _add(head + tail)  # binlik okunuşu da makul — belirsiz
    return readings


def _number_candidates(text: str) -> list[tuple[str, set[Decimal]]]:
    """Metindeki her sayı geçişi için kabul edilebilir değer kümesi.

    Harfe BİTİŞİK rakamlar atlanır ("C1", "BIST100", "A101"). Bunlar
    veri değil, tanımlayıcıdır. Kıyaslama koşumunda gerçek bir yanlış
    pozitif olarak yakalandı: modelin metne yazdığı iddia referansı
    ("...öngörüyor (C1)") "kanıtta bulunmayan sayı: 1" diye
    işaretleniyordu — teşhis yanlış, sonuç yanıltıcıydı.

    Referansın gövdede yer alması yine de istenmez; onu doğru katman
    yakalar (F3-13 "bağlanamayan cümle"), grounding değil.
    """
    out: list[tuple[str, set[Decimal]]] = []
    for match in _NUMBER_RE.finditer(text):
        token = match.group(0)
        preceding = text[match.start() - 1] if match.start() else ""
        if preceding.isalpha():
            continue
        values = _separator_readings(token)
        if not values:
            continue

        # "3,5 milyar" hem 3.5 hem 3_500_000_000 olarak kabul edilir:
        # kanıt hangisini yazdıysa taslak diğerini yazabilsin.
        tail = text[match.end() : match.end() + 16]
        magnitude = _MAGNITUDE_RE.match(tail)
        if magnitude:
            scale = _MAGNITUDES[magnitude.group(1)]
            values = values | {(v * scale).normalize() for v in values}

        out.append((token, values))
    return out


@dataclass(frozen=True)
class _DateMention:
    """Metinde geçen tek bir tarih/dönem ifadesi.

    `tokens` ifadenin ürettiği TÜM çözünürlükleri taşır (kanıt evrenini
    kurarken kullanılır). `primary` ise ifadenin KENDİ çözünürlüğüdür ve
    denetim yalnızca ona bakar.

    Ayrım kritik: "12 Eylül 2026" ile "ağustos 2026" ifadelerinin ortak
    bir belirteci vardır ("2026"). Küme kesişimine bakan bir denetim,
    kanıtta ağustos varken taslağın eylül yazmasını YIL EŞLEŞTİĞİ İÇİN
    kabul ederdi. Bu gerçek bir hata olarak yakalandı; kural artık
    "en yüksek çözünürlük tutmalı".
    """

    raw: str
    tokens: frozenset[str]
    primary: str


def _date_mentions(text: str) -> list[_DateMention]:
    """Metindeki tarih/dönem ifadelerini çözer.

    "12 Ağustos 2026" -> tokens {"2026-08-12", "2026-08", "--08", "2026"}
                         primary "2026-08-12"
    "ağustosta"       -> tokens {"--08"}, primary "--08"
    """
    mentions: list[_DateMention] = []

    def _calendar(raw: str, year: str | None, month: int | None, day: int | None) -> None:
        tokens: set[str] = set()
        primary = ""
        if month is not None:
            tokens.add(f"--{month:02d}")
            primary = f"--{month:02d}"
        if year:
            tokens.add(year)
            primary = primary or year
        if year and month is not None:
            primary = f"{year}-{month:02d}"
            tokens.add(primary)
            if day is not None:
                primary = f"{year}-{month:02d}-{day:02d}"
                tokens.add(primary)
        if primary:
            mentions.append(_DateMention(raw, frozenset(tokens), primary))

    def _period(raw: str, year: str | None, letter: str, index: str) -> None:
        bare = f"{letter}{index}"
        tokens = {bare}
        primary = bare
        if year:
            primary = f"{year}-{letter}{index}"
            tokens.update({primary, year})
        mentions.append(_DateMention(raw, frozenset(tokens), primary))

    for m in _DATE_ISO_RE.finditer(text):
        _calendar(
            m.group(0),
            m.group("year"),
            int(m.group("month")),
            int(m.group("day")) if m.group("day") else None,
        )
    for m in _DATE_NUMERIC_RE.finditer(text):
        month = int(m.group("month"))
        if 1 <= month <= 12:
            _calendar(m.group(0), m.group("year"), month, int(m.group("day")))
    for m in _DATE_TEXT_RE.finditer(text):
        named_month = _MONTH_INDEX.get(m.group("month"))
        if named_month is None:
            continue
        day = int(m.group("day")) if m.group("day") else None
        _calendar(
            m.group(0).strip(),
            m.group("year"),
            named_month,
            day if day and 1 <= day <= 31 else None,
        )

    # Çeyrek ve yarıyıl: aya değil döneme çözülür.
    for m in _QUARTER_ISO_RE.finditer(text):
        _period(m.group(0), m.group("year"), "Q", m.group("q"))
    for m in _HALF_ISO_RE.finditer(text):
        _period(m.group(0), m.group("year"), "H", m.group("h"))
    for m in _QUARTER_TR_RE.finditer(text):
        # "ilk çeyrek" yıl taşımaz; kanıttaki "2026-Q1" de bare "Q1"
        # belirtecini üretir, o yüzden yılsız ifade kanıt dışı sayılmaz.
        _period(m.group(0), None, "Q", str(_ORDINAL_TR[m.group("ord")]))

    return mentions


def _date_tokens(text: str) -> set[str]:
    """Metnin ürettiği tüm tarih belirteçleri (kanıt evreni için)."""
    tokens: set[str] = set()
    for mention in _date_mentions(text):
        tokens |= mention.tokens
    return tokens


def _period_tokens(period: str) -> set[str]:
    """`normalized_value.period` (ISO) -> tarih belirteçleri."""
    period = (period or "").strip()
    if not period:
        return set()
    tokens = _date_tokens(fold_text(period))
    # `_date_tokens` yıl-çeyrek/yarıyılı katlanmış metinden yakalar;
    # yalın yıl ("2026") hiçbir kalıba uymaz, elle eklenir.
    if re.fullmatch(r"\d{4}", period):
        tokens.add(period)
    return tokens


def _quotes_in(text: str) -> list[str]:
    """Tırnak içindeki, en az `MIN_QUOTE_WORDS` kelimelik parçalar."""
    found: list[str] = []
    for match in _QUOTE_RE.finditer(text):
        body = (match.group(1) or match.group(2) or "").strip()
        if len(body.split()) >= MIN_QUOTE_WORDS:
            found.append(body)
    return found


def _snippet(text: str, token: str, width: int = 60) -> str:
    index = text.find(token)
    if index < 0:
        return text[:width]
    start = max(0, index - width // 2)
    return text[start : start + width].strip()


# ------------------------------------------------------------------ kamu API
def build_context(
    texts: Iterable[str],
    *,
    normalized_values: Sequence[dict[str, Any]] = (),
) -> GroundingContext:
    """Kanıt evrenini kurar.

    `texts`: iddia metinleri, kanıt alıntıları — yani üretime **girdi
    olarak verilen** her şey. Buraya modele verilmemiş bir metin koymak
    denetimi anlamsız kılar: model göremediği bir kaynağa dayanamaz.
    """
    parts = [t for t in texts if t]
    haystack = fold_text(" \n ".join(parts))

    numbers: set[Decimal] = set()
    for _token, values in _number_candidates(haystack):
        numbers |= values

    dates: set[str] = _date_tokens(haystack)

    # `normalized_value` kanıtın en kesin biçimidir: model metni farklı
    # yazsa bile değer ve dönem burada kanonik hâlde durur.
    for value in normalized_values:
        if value is None:
            continue
        raw = value.get("value")
        if isinstance(raw, int | float | str):
            parsed = _decimal(str(raw))
            if parsed is not None:
                numbers.add(parsed)
        dates |= _period_tokens(str(value.get("period") or ""))

    return GroundingContext(haystack=haystack, numbers=frozenset(numbers), dates=frozenset(dates))


def check(draft_text: str, context: GroundingContext) -> GroundingReport:
    """Taslağı kanıt evrenine karşı denetler (F3-12).

    Boş kanıt evreni + sayı/tarih içeren taslak = tamamı işaretlenir.
    Bu doğru davranıştır: kanıtsız üretim zaten P1 ile engellenir
    (F3-11), buraya düşmesi bir hata belirtisidir.
    """
    folded = fold_text(draft_text)
    issues: list[GroundingIssue] = []

    # --- tarihler önce: bir tarihin parçası olan sayılar ayrıca
    #     cezalandırılmasın diye sonuçları sayı yolunda kullanılır.
    mentions = _date_mentions(folded)
    grounded_dates = [m for m in mentions if m.primary in context.dates]

    for mention in mentions:
        if mention.primary not in context.dates:
            issues.append(GroundingIssue("date", mention.raw, _snippet(folded, mention.raw)))

    # --- sayılar
    numbers = _number_candidates(folded)
    for token, values in numbers:
        if values & context.numbers:
            continue
        # Yalın yıl ("2026") hiçbir tarih kalıbına uymaz ama kanıtta bir
        # dönem olarak durabilir (`normalized_value.period`). Sayı yolunda
        # cezalandırmak, doğru bir yılı uydurma saymak olurdu.
        if _YEAR_RE.fullmatch(token) and token in context.dates:
            continue
        # Bir tarihin parçası olan sayı (gün/ay/yıl) ayrıca sayı olarak
        # cezalandırılmaz — tarih yolunda zaten denetlendi. Yalnızca
        # KANITTA KARŞILIĞI BULUNAN tarihler bu muafiyeti verir.
        if any(token in m.raw for m in grounded_dates):
            continue
        issues.append(GroundingIssue("number", token, _snippet(folded, token)))

    # --- alıntılar (ham metinden: katlama tırnakları siler)
    quotes = _quotes_in(draft_text)
    for quote in quotes:
        folded_quote = fold_text(quote)
        if folded_quote not in context.haystack:
            issues.append(GroundingIssue("quote", quote[:120], _snippet(folded, folded_quote[:40])))

    return GroundingReport(
        issues=tuple(issues),
        numbers_checked=len(numbers),
        dates_checked=len(mentions),
        quotes_checked=len(quotes),
    )


def check_draft(
    draft_text: str,
    *,
    claim_texts: Sequence[str],
    quote_spans: Sequence[str] = (),
    normalized_values: Sequence[dict[str, Any]] = (),
    extra_texts: Sequence[str] = (),
) -> GroundingReport:
    """F3-10'un çıktısını, ona verilen kanıt setine karşı denetler."""
    context = build_context(
        [*claim_texts, *quote_spans, *extra_texts],
        normalized_values=normalized_values,
    )
    return check(draft_text, context)


__all__ = [
    "CHECKER_VERSION",
    "GroundingContext",
    "GroundingIssue",
    "GroundingReport",
    "build_context",
    "check",
    "check_draft",
]
