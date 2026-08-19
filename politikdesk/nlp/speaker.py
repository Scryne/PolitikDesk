"""Konuşan atfı — bir beyanın SAHİBİNİ deterministik olarak çıkarır.

⛔ BU MODÜL LLM KULLANMAZ.

Gerekçesi ADR-010 §6'da: "bu aktör görüş değiştirdi" gibi bir iddia,
kimin ne söylediği bilinmeden türetilemez. O bilgi veritabanında yoktu —
`claims.status_reason->>'speaker'` 4.542 iddianın **0'ında** doluydu,
buna karşılık beş modül onu okuyordu. Aktör ataması bu yüzden "olayın
herhangi bir makale başlığında adı geçiyor mu" gibi gevşek dallara
düşüyor ve bir olayda adı anılan aktör, o olaydaki **herkesin** beyanını
devralıyordu.

⛔ KESİNLİK ÖNCELİKLİDİR, KAPSAM DEĞİL.

Yanlış bir konuşan atfı, konuşan atfı olmamasından çok daha pahalıdır:
birincisi gerçek bir kişiye söylemediği bir sözü yükler. Kalıp
kesin değilse `None` döner. `None` dürüst bir cevaptır ("bilmiyorum");
tahmin değildir.

Desteklenen üç biçim (gerçek veriden çıkarıldı):

    Muhittin Böcek, ... söyledi.        → "Muhittin Böcek"
    Numan Kurtulmuş stated that ...     → "Numan Kurtulmuş"
    Sinan Burhan: Kılıçdaroğlu, ...     → "Sinan Burhan"

İkinci biçim bir yan bulgunun sonucudur: iddia çıkarımı Türkçe
kaynaklardan zaman zaman İngilizce cümle üretiyor. Bu ayrı bir kusurdur
ve burada düzeltilmez; ama var olduğu için tanınması gerekir.
"""

from __future__ import annotations

import re
from typing import Final

# Türkçe aktarma fiilleri. Yalnızca SÖYLEME bildirenler — "yaptı",
# "gitti" gibi eylem fiilleri bir beyan sahipliği kurmaz.
_TR_REPORTING: Final[tuple[str, ...]] = (
    "söyledi", "belirtti", "dedi", "açıkladı", "ifade etti", "kaydetti",
    "vurguladı", "aktardı", "duyurdu", "yineledi", "savundu", "iddia etti",
    "öne sürdü", "sözlerine ekledi", "dile getirdi", "çağrısında bulundu",
    "yanıt verdi", "uyardı", "hatırlattı", "anlattı", "konuştu",
)

_EN_REPORTING: Final[tuple[str, ...]] = (
    "stated", "said", "noted", "added", "claimed", "argued",
    "announced", "explained", "warned", "emphasized",
)

# Türkçe büyük harf kümesi — `İ` ve `Ş` ASCII `[A-Z]` içinde YOKTUR.
# Bu atlanırsa "İmamoğlu" ve "Şimşek" hiç eşleşmez.
_UPPER: Final[str] = "A-ZÇĞİÖŞÜ"
_LOWER: Final[str] = "a-zçğıöşü"

# Özel ad öbeği: büyük harfle başlayan 1-4 sözcük. Aradaki bağlaçlara
# ("ve", "ile") izin verilmez — iki ayrı kişiyi tek ada yapıştırırdı.
_NAME = rf"[{_UPPER}][{_LOWER}{_UPPER}']+(?:\s+[{_UPPER}][{_LOWER}{_UPPER}']+){{0,3}}"

# 1) "Ad Soyad, ... <aktarma fiili>"
_TR_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^\s*({_NAME}),\s+.*?\b(?:{'|'.join(_TR_REPORTING)})\b",
    re.DOTALL,
)

# 2) "Ad Soyad stated/said that ..."
_EN_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^\s*({_NAME})\s+(?:{'|'.join(_EN_REPORTING)})\b",
)

# 3) "Ad Soyad: ..." — iki nokta öncesi ad öbeğinden ibaret olmalı.
_COLON_PATTERN: Final[re.Pattern[str]] = re.compile(rf"^\s*({_NAME})\s*:\s*\S")

# Ad sanılabilecek ama kişi/kurum olmayan baş sözcükler. Bunlar
# olmadan "Ancak Bakan, ... dedi" cümlesinde konuşan "Ancak" olurdu.
_STOPWORDS: Final[frozenset[str]] = frozenset({
    "ancak", "fakat", "ayrıca", "bugün", "dün", "yarın", "böylece",
    "çünkü", "ayrica", "buna", "bunun", "şu", "bu", "o", "kabul",
    "butlanı", "the", "a", "an", "he", "she", "they", "it",
})

# Konuşan olamayacak jenerik ifadeler — ADR-010 §1'de "Adayı" ve
# "Resmî Gazete"nin aktör alanına sızdığı tespit edilmişti.
_NOT_A_SPEAKER: Final[frozenset[str]] = frozenset({
    "resmî gazete", "resmi gazete", "adayı", "aday", "genel başkanı",
    "sözcüsü", "bakanlığı açıklamasında",
})

MAX_NAME_WORDS: Final[int] = 4

# "Cumhurbaşkanlığı Açıklaması:" bir konuşan adı değil, başlık önekidir.
_HEADLINE_SUFFIX: Final[tuple[str, ...]] = ("açıklaması", "duyurusu", "bildirisi")


def _fold(s: str) -> str:
    """Türkçe duyarlı küçültme — `İ`/`I` ASCII `lower()` ile bozulur."""
    return s.replace("İ", "i").replace("I", "ı").lower().strip()


def _plausible(name: str) -> bool:
    """Çıkarılan öbek gerçekten bir konuşan adı olabilir mi?"""
    ad = name.strip(" '\"")
    if not ad or len(ad) < 3:
        return False
    if _fold(ad) in _NOT_A_SPEAKER:
        return False
    kelimeler = ad.split()
    if len(kelimeler) > MAX_NAME_WORDS:
        return False
    if _fold(kelimeler[-1]) in _HEADLINE_SUFFIX:
        return False
    # İlk sözcük bir bağlaç/zarf ise bu bir ad öbeği değildir.
    return _fold(kelimeler[0]) not in _STOPWORDS


def extract_speaker(
    claim_text: str, *, known_publications: frozenset[str] = frozenset()
) -> str | None:
    """Beyanın sahibini döndürür; emin değilse **None**.

    `None` bir başarısızlık değil, dürüst bir cevaptır: bu cümlede
    konuşanı belirten kesin bir kalıp yok. Tahmin üretmek, ADR-010'da
    kapatılan kusurun aynısını yeni bir yerden geri getirirdi.

    ⛔ `known_publications`: **bir yayın organı konuşan değildir.**

    "Halk TV: İBB davasında ikinci celse başlıyor" cümlesinde Halk TV
    haberi *aktaran* taraftır, beyanın sahibi değil. Bu ayrım ADR-010'un
    doğrudan bulgusudur — orada "Resmî Gazete"ye üç siyasi U dönüşü
    atfedilmişti. Çağıran taraf kaynak adlarını verir; modül veritabanına
    bağlanmaz, saf ve test edilebilir kalır.
    """
    if not claim_text or not claim_text.strip():
        return None

    yayinlar = {_fold(p) for p in known_publications}

    for kalip in (_COLON_PATTERN, _TR_PATTERN, _EN_PATTERN):
        m = kalip.match(claim_text)
        if m:
            ad = m.group(1).strip(" '\"")
            if _plausible(ad) and _fold(ad) not in yayinlar:
                return ad
    return None
