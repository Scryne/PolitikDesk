"""Sayısal çelişki bayrağı (F2-03).

DoD: "Faiz %40" ve "faiz %42" içeren makaleler aynı olaya atanırsa
`needs_review` işaretleniyor.

**Neden bu var.** Kümeleme benzerliğe bakar; iki metin "TCMB faizi %40'a
çekti" ve "TCMB faizi %42'ye çekti" birbirine çok benzer ve aynı olaya
atanır. Ama biri yanlıştır — ya da iki farklı olaydır (karar ile revizyon).
İkisi de sessizce birleştirilmemelidir: kullanıcı yanlış sayıyı kanıt
diye kullanır (Spec §13.2, false merge'ün asıl zararı).

Bu modül **hüküm vermez**: hangi sayının doğru olduğunu söylemez, yalnızca
çeliştiğini işaretler ve olayı insan denetimine düşürür (Spec §11.4
"zorunlu kaçış valfleri").

Tasarım kısıtı: deterministik, LLM yok. Sayısal iddiaların LLM ile
normalizasyonu ayrı bir görevdir (F2-08) ve `claims` tablosuna yazar;
bu modül ondan **önce**, ham metin üzerinde çalışır.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final

# --------------------------------------------------------------------------
# Metrik sözlüğü — MVP dikeyinin ölçülebilir büyüklükleri (Spec §5)
# --------------------------------------------------------------------------
# Anahtar: kanonik metrik adı. Değer: metni tanıyan kalıplar (fold edilmiş).
# Yalnızca **karşılaştırılabilir** büyüklükler girer: aynı metrik iki
# metinde farklı değer alırsa bu bir çelişkidir.
METRIC_PATTERNS: Final[dict[str, tuple[str, ...]]] = {
    "policy_rate": (
        "politika faizi", "bir hafta vadeli repo", "haftalik repo",
        "repo ihale faiz", "politika faizini", "politika faizinin",
    ),
    "overnight_lending_rate": ("gecelik vadede borc verme", "gecelik borc verme"),
    "overnight_borrowing_rate": ("gecelik vadede borclanma", "gecelik borclanma"),
    "cpi_annual": (
        "yillik enflasyon", "yillik tufe", "tufe yillik", "enflasyon yillik",
        "tuketici enflasyonu yillik", "yillik bazda enflasyon",
    ),
    "cpi_monthly": (
        "aylik enflasyon", "aylik tufe", "tufe aylik", "enflasyon aylik",
        "tuketici enflasyonu aylik", "aylik bazda enflasyon",
    ),
    "ppi_annual": ("yi-ufe", "yi ufe", "uretici fiyat", "ufe yillik", "yillik ufe"),
    "unemployment_rate": ("issizlik orani", "issizlik oranindaki", "issizlik"),
    "gdp_growth": ("buyume orani", "buyudu", "gsyh", "buyume"),
    "industrial_production": ("sanayi uretimi", "sanayi uretim endeksi"),
    "employment_rate": ("istihdam orani",),
    "participation_rate": ("isgucune katilma orani", "isgucune katilim orani"),
}

# Sayı + yüzde biçimleri: "%37", "yüzde 37", "yüzde 35,5", "%1,78"
_NUM = r"(\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+(?:\.\d+)?)"
_PERCENT_RE: Final[re.Pattern[str]] = re.compile(
    rf"(?:%\s*{_NUM}|yuzde\s+{_NUM})", re.IGNORECASE
)

# Bir yüzdenin hangi metriğe ait olduğunu ararken bakılacak pencere.
# Türkçede niteleyen ifade genellikle sayıdan ÖNCE gelir ("politika faizi ...
# yüzde 37"), ama "yüzde 2,5 büyüdü" gibi sonra gelen biçimler de vardır.
CONTEXT_BEFORE: Final[int] = 90
CONTEXT_AFTER: Final[int] = 40

# İki değerin "aynı" sayılacağı tolerans. Yuvarlama farkı çelişki değildir.
TOLERANCE: Final[float] = 0.001


def _fold(text: str) -> str:
    """Karşılaştırma için normalleştirir: küçük harf + aksan sadeleştirme.

    Türkçe'ye özgü: 'İ' -> 'i', 'ı' -> 'i' (NFKD tek başına bunu yapmaz).
    """
    lowered = text.replace("İ", "i").replace("I", "ı").lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.replace("ı", "i")


def _to_float(raw: str) -> float | None:
    """Türkçe sayı biçimini float'a çevirir: '35,5' -> 35.5, '1.234,5' -> 1234.5."""
    cleaned = raw.replace(".", "").replace(",", ".") if "," in raw else raw
    try:
        return float(cleaned)
    except ValueError:
        return None


@dataclass(frozen=True)
class NumericMention:
    """Metinde geçen, bir metriğe bağlanabilmiş yüzdesel değer."""

    metric: str
    value: float
    unit: str
    raw: str


@dataclass(frozen=True)
class NumericConflict:
    """İki metnin aynı metrik için farklı değer vermesi."""

    metric: str
    left: float
    right: float
    unit: str

    def describe(self) -> str:
        return (
            f"{self.metric}: {self.left:g}{self.unit} ile "
            f"{self.right:g}{self.unit} çelişiyor"
        )


def _metric_at(folded: str, start: int, end: int) -> str | None:
    """Sayının etrafındaki pencerede bir metrik adı arar.

    Birden çok metrik eşleşirse **sayıya en yakın** olan kazanır; aksi halde
    "politika faizi ... gecelik borç verme faizi yüzde 40" cümlesinde ilk
    metrik tüm sayıları yutardı.
    """
    before = folded[max(0, start - CONTEXT_BEFORE):start]
    after = folded[end:end + CONTEXT_AFTER]

    best: tuple[int, str] | None = None
    for metric, patterns in METRIC_PATTERNS.items():
        for pattern in patterns:
            pos = before.rfind(pattern)
            if pos >= 0:
                distance = len(before) - (pos + len(pattern))
                if best is None or distance < best[0]:
                    best = (distance, metric)
            pos = after.find(pattern)
            if pos >= 0:
                # Sonradan gelen niteleyici ("yüzde 2,5 büyüdü") biraz
                # cezalandırılır: önceki niteleyici daha güvenilirdir.
                distance = pos + 10
                if best is None or distance < best[0]:
                    best = (distance, metric)
    return best[1] if best else None


def extract_numbers(text: str) -> list[NumericMention]:
    """Metindeki metriğe bağlanabilen yüzdesel değerleri çıkarır.

    Metriğe bağlanamayan sayılar **atılır**: "23 çeyrektir büyüdü" ile
    "yüzde 23 büyüdü" karıştırılırsa bayrak gürültüye boğulur.
    """
    if not text:
        return []

    folded = _fold(text)
    out: list[NumericMention] = []
    for match in _PERCENT_RE.finditer(folded):
        raw = next(g for g in match.groups() if g is not None)
        value = _to_float(raw)
        if value is None:
            continue
        metric = _metric_at(folded, match.start(), match.end())
        if metric is None:
            continue
        out.append(NumericMention(metric=metric, value=value, unit="%", raw=raw))
    return out


def find_conflicts(
    left_text: str, right_text: str
) -> list[NumericConflict]:
    """İki metin arasındaki sayısal çelişkileri bulur.

    Çelişki tanımı: **aynı metrik**, iki metinde de geçiyor ve değerler
    tolerans dışında farklı. Bir metinde olup diğerinde olmayan metrik
    çelişki DEĞİLDİR (eksik bilgi ≠ çelişkili bilgi).

    Bir metin aynı metrik için birden çok değer içerebilir (örn. bir haberde
    hem eski hem yeni faiz). Bu durumda değer **kümeleri** karşılaştırılır:
    kesişim varsa çelişki yoktur.
    """
    left = _group(extract_numbers(left_text))
    right = _group(extract_numbers(right_text))

    conflicts: list[NumericConflict] = []
    for metric in sorted(left.keys() & right.keys()):
        lvals, rvals = left[metric], right[metric]
        if any(
            abs(a - b) <= TOLERANCE for a in lvals for b in rvals
        ):
            continue  # ortak değer var -> çelişki yok
        conflicts.append(
            NumericConflict(
                metric=metric,
                left=sorted(lvals)[0],
                right=sorted(rvals)[0],
                unit="%",
            )
        )
    return conflicts


def _group(mentions: list[NumericMention]) -> dict[str, set[float]]:
    grouped: dict[str, set[float]] = {}
    for m in mentions:
        grouped.setdefault(m.metric, set()).add(m.value)
    return grouped
