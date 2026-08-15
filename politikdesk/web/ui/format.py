"""Türkçe biçimlendirme (DESIGN.md Ek B.1, Ek B.3).

Arayüzde geçen **hiçbir sayı, tarih veya oran elle biçimlendirilmez.**
`f"{v:.1f}%"` her seferinde yanlış çıkar: ondalık ayırıcı nokta olur,
yüzde işareti arkaya gider ve binlik ayırıcı kaybolur.

| Tür | Doğru | Yanlış |
|---|---|---|
| Sayı | `184.392` | `184,392` |
| Ondalık | `12,4` | `12.4` |
| Yüzde | `%12,4` — işaret **önde** | `12.4%` |
| Para | `₺1.234,56` | `$1,234.56` |
| Tarih | `25 Tem 2026` | `07/25/2026` |
| Saat | `14:32` | `2:32 PM` |
| Büyük sayı | `1,2 mn` · `184 b` | `1.2M` · `184K` |

`locale` modülü kullanılmaz: süreç genelinde global durum değiştirir ve
konteynerde `tr_TR.UTF-8` kurulu olacağına güvenilemez. Biçimlendirme
elle ama **tek yerde** yapılır.

### Ek uyumu

Değişken içeren metinlerde Türkçe ek uyumu kırılır (`{name}'in` → sesli/
sessiz uyumu bozulur). Kural: **ek gerektirmeyen kalıp kur.** Bu modül
sayı üretir, cümle üretmez; cümle kuran çağıran taraftır ve
`"Bulunan kayıt: 12"` gibi eksiz kalıplar seçer.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

# Türkçe kısa ay adları. `%b` locale'e bağlıdır ve konteynerde İngilizce
# döner — bu yüzden tablo elle tutulur.
MONTHS_SHORT: tuple[str, ...] = (
    "Oca", "Şub", "Mar", "Nis", "May", "Haz",
    "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
)
MONTHS_LONG: tuple[str, ...] = (
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)
DAYS_SHORT: tuple[str, ...] = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")

EMPTY = "—"  # em-dash: "veri yok" için tek işaret, "-" veya "N/A" değil


def number(value: float | int | None, decimals: int = 0) -> str:
    """`184392` → `184.392` · `12.4` → `12,4` (decimals=1)."""
    if value is None:
        return EMPTY
    text = f"{float(value):,.{decimals}f}"
    # İngilizce biçimden Türkçeye: önce ayırıcıları takasla, sonra yerleştir.
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def percent(value: float | None, decimals: int = 0) -> str:
    """`12.4` → `%12,4`. İşaret **önde** — Türkçede kural budur."""
    if value is None:
        return EMPTY
    return f"%{number(value, decimals)}"


def signed_percent(value: float | None, decimals: int = 1) -> str:
    """Delta için: `+%12,4` / `−%3,1`. Eksi işareti U+2212, tire değil."""
    if value is None:
        return EMPTY
    sign = "+" if value > 0 else ("−" if value < 0 else "")
    return f"{sign}%{number(abs(value), decimals)}"


def compact(value: float | int | None) -> str:
    """`1_240_000` → `1,2 mn` · `184_392` → `184 b`.

    Kısaltmalar Türkçedir: `b` (bin), `mn` (milyon), `mr` (milyar).
    `K`/`M` yazmak Ek B.1 ihlalidir.
    """
    if value is None:
        return EMPTY
    n = float(value)
    for limit, suffix in ((1e9, "mr"), (1e6, "mn"), (1e3, "b")):
        if abs(n) >= limit:
            scaled = n / limit
            # 10'un altında bir ondalık anlamlı, üstünde gürültü.
            return f"{number(scaled, 1 if abs(scaled) < 10 else 0)} {suffix}"
    return number(n)


def money(value: float | None, decimals: int = 2) -> str:
    """`1234.5` → `₺1.234,56`.

    Not: birim sayıdan **daha küçük ve muted** gösterilmelidir (Bölüm 6.5);
    onu çağıran taraf yapar — bu fonksiyon düz metin döner.

    Bu üründe henüz para gösteren bir ekran yok; fonksiyon Ek B.1'in
    biçimini TEK YERDE sabitlemek için duruyor, ilk tutar ekrana çıktığında
    doğru biçim aranmasın diye.
    """
    if value is None:
        return EMPTY
    return f"₺{number(value, decimals)}"


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return None


def day_month(value: Any) -> str:
    """`25 Tem` — liste ve eksen etiketleri için."""
    moment = _as_datetime(value)
    if moment is None:
        return EMPTY
    return f"{moment.day} {MONTHS_SHORT[moment.month - 1]}"


def full_date(value: Any) -> str:
    """`25 Tem 2026`."""
    moment = _as_datetime(value)
    if moment is None:
        return EMPTY
    return f"{moment.day} {MONTHS_SHORT[moment.month - 1]} {moment.year}"


def date_time(value: Any) -> str:
    """`25 Tem 14:32` — saat 24 saat biçiminde."""
    moment = _as_datetime(value)
    if moment is None:
        return EMPTY
    return f"{moment.day} {MONTHS_SHORT[moment.month - 1]} {moment:%H:%M}"


def precise(value: Any) -> str:
    """`Per, 25 Temmuz 2026 14:32` — `title` özniteliği için tam tarih.

    Bölüm 8.3: göreli zaman gösteren her hücrenin `title`'ında tam tarih
    bulunur. Göreli zaman okunaklıdır ama denetlenebilir değildir.
    """
    moment = _as_datetime(value)
    if moment is None:
        return EMPTY
    return (
        f"{DAYS_SHORT[moment.weekday()]}, {moment.day} "
        f"{MONTHS_LONG[moment.month - 1]} {moment.year} {moment:%H:%M}"
    )


def relative(value: Any) -> str:
    """`2 dakika önce` · `3 saat önce` · `dün` · `25 Tem`.

    Eşik: 7 günden eskisi mutlak tarihe döner. "42 gün önce" okunabilir
    ama işe yaramaz — kullanıcı yine takvime bakmak zorunda kalır.
    """
    moment = _as_datetime(value)
    if moment is None:
        return EMPTY

    now = datetime.now(moment.tzinfo or UTC)
    if moment.tzinfo is None:
        now = now.replace(tzinfo=None)

    seconds = (now - moment).total_seconds()
    if seconds < 0:
        return date_time(moment)  # gelecek: göreli ifade yanıltıcı olur
    if seconds < 60:
        return "az önce"
    if seconds < 3600:
        return f"{int(seconds // 60)} dakika önce"
    if seconds < 86400:
        return f"{int(seconds // 3600)} saat önce"
    if seconds < 172800:
        return "dün"
    if seconds < 604800:
        return f"{int(seconds // 86400)} gün önce"
    return full_date(moment)


def duration_ms(value: float | None) -> str:
    """`2100` → `2,10 sn` · `450` → `450 ms`."""
    if value is None:
        return EMPTY
    return f"{number(value / 1000, 2)} sn" if value >= 1000 else f"{number(value)} ms"


def plural_count(count: int, noun: str) -> str:
    """`12, "olay"` → `12 olay`.

    Türkçede sayıdan sonra çoğul eki **kullanılmaz** ("12 olaylar" yanlış).
    Bu fonksiyon var çünkü İngilizce alışkanlığıyla `+ "s"` yazmak yaygın
    bir hatadır; tek doğru biçimi burada sabitliyoruz.
    """
    return f"{number(count)} {noun}"
