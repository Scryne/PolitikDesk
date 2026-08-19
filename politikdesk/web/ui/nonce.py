"""İstek başına CSP nonce'u (Faz 7).

### Neden bir ContextVar, neden parametre değil

`shell.page()` depodaki HER sayfayı üretir ve saf bir fonksiyondur: `Request`
nesnesini görmez. Nonce'u parametre olarak geçirmek 30'dan fazla çağrı yerini
ve aradaki her yardımcı fonksiyonun imzasını değiştirmeyi gerektirirdi —
üstelik bir tanesi unutulduğunda hata SESSİZ olurdu: script nonce'suz basılır,
tarayıcı onu bloklar, sunucu tarafında hiçbir iz kalmaz.

ContextVar bu riski kapatır: değeri middleware yazar, kabuk okur, arada kalan
katmanlar hiçbir şey bilmez.

### Neden global değil

`ContextVar` bir global değişken DEĞİLDİR. asyncio her görev (task) için
bağlamın kendi kopyasını taşır; eşzamanlı iki istek birbirinin değerini
göremez. `_CSPNonceMiddleware` her istekte `set()` eder ve `finally` içinde
`reset()` ile bağlamı eski hâline döndürür — böylece bir isteğin nonce'u
havuzdaki bir sonraki isteğe sızmaz.

Varsayılanın boş dize olması bilinçlidir: HTTP isteği dışında (Celery
görevleri, testler, brifing e-postası üreten kod yolları) `page()` çağrılırsa
nonce özniteliği HİÇ basılmaz. Yanlış/bayat bir nonce basmaktansa hiç
basmamak doğrudur — o çıktı zaten tarayıcıya bir CSP başlığıyla birlikte
servis edilmiyordur.

### Neden `token_urlsafe`

CSP nonce'u base64 alfabesinde olmalıdır. `token_urlsafe` `[A-Za-z0-9_-]`
üretir; `'` ve `;` gibi başlığı ya da HTML özniteliğini kırabilecek hiçbir
karakter içermez, dolayısıyla enjeksiyon yüzeyi yoktur. 32 bayt entropi
(~256 bit) tahmin edilebilirliği ortadan kaldırır.
"""

from __future__ import annotations

import contextvars
import secrets
from typing import Final

#: Nonce'un bayt cinsinden entropisi. 16 bayt (128 bit) CSP için yeterli
#: kabul edilir; 32 bayt maliyeti ölçülemeyecek kadar küçük olduğu için
#: (bkz. ADR-011 performans ölçümü) daha geniş tarafta duruyoruz.
NONCE_BYTES: Final[int] = 32

_csp_nonce: contextvars.ContextVar[str] = contextvars.ContextVar("pd_csp_nonce", default="")


def new_nonce() -> str:
    """Kriptografik olarak güvenli, tahmin edilemez yeni bir nonce üretir."""
    return secrets.token_urlsafe(NONCE_BYTES)


def set_nonce(value: str) -> contextvars.Token[str]:
    """Geçerli bağlama nonce'u yazar; `reset_nonce` için jeton döner."""
    return _csp_nonce.set(value)


def reset_nonce(token: contextvars.Token[str]) -> None:
    """Bağlamı `set_nonce` öncesindeki hâline döndürür."""
    _csp_nonce.reset(token)


def current_nonce() -> str:
    """Bu isteğin nonce'u; HTTP bağlamı dışında boş dize."""
    return _csp_nonce.get()


def nonce_attr() -> str:
    """`<script>` etiketine eklenecek öznitelik parçası.

    Nonce alfabesi `[A-Za-z0-9_-]` olduğu için kaçış gerekmez; yine de
    üretim yerinden başka hiçbir yerde dize birleştirilmesin diye tek
    kapı buradadır.
    """
    value = current_nonce()
    return f' nonce="{value}"' if value else ""
