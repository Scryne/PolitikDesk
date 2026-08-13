"""TÜİK SDMX servisi için belirteç edinimi (F5-02 · B-42'yi kapatır).

**Protokol nereden bilindiği:** TÜİK'in API belgesi sunucu tarafından
okunabilen bir yerde yayımlanmıyor — `veriportali` bir React SPA ve
`/swagger/v1/swagger.json` bile "JavaScript gerekli" kabuğunu döndürüyor.
Belge, uygulamanın JS paketinin (`/assets/main-*.js`) içine gömülü
markdown olarak bulundu ve akış oradan çıkarıldı:

    POST https://giris.tuik.gov.tr/realms/web/protocol/openid-connect/token
      Content-Type: application/x-www-form-urlencoded
      grant_type=password
      client_id=nsi-ws-consumer
      api_key=<API KEY>
    -> {"access_token": "...", "expires_in": 300}

    GET https://nsiws.tuik.gov.tr/rest/...
      Authorization: Bearer <access_token>

**Belirteç 5 DAKİKA yaşıyor** (`expires_in: 300`). Her çağrıda yeniden
almak da, bir kez alıp saklamak da yanlıştır: birincisi kimlik sunucusunu
gereksiz yorar, ikincisi tur ortasında 401'e düşer. Bu modül belirteci
önbellekler ve **süresinden önce** yeniler.

⛔ Anahtar ve belirteç loglanmaz. `politikdesk/audit.py` ile aynı kural:
sır, hata mesajına bile girmez.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from politikdesk.ingestion.http import HttpClient
from politikdesk.observability import get_logger

log = get_logger(__name__)

TOKEN_URL = "https://giris.tuik.gov.tr/realms/web/protocol/openid-connect/token"
CLIENT_ID = "nsi-ws-consumer"

# Belirteci ölümünden bu kadar saniye ÖNCE yenile. Bir tur birkaç saniye
# sürebilir; tam sınırda yenilemek, isteğin yolda ölmesi demektir.
REFRESH_MARGIN_SECONDS = 45


class TuikAuthError(RuntimeError):
    """Belirteç alınamadı. Mesaj anahtar İÇERMEZ."""


@dataclass
class TuikTokenProvider:
    """Belirteci alır, önbellekler ve süresi dolmadan yeniler."""

    client: HttpClient | None = None
    _token: str = field(default="", repr=False)
    _expires_at: float = 0.0

    def _api_key(self) -> str:
        var = os.environ.get("PD_TUIK_API_KEY_ENV", "TUIK_API_KEY")
        key = os.environ.get(var, "").strip()
        if not key:
            raise TuikAuthError(
                f"TÜİK API anahtarı yok: '{var}' ortam değişkeni boş. "
                ".env'e PD_TUIK_API_KEY_ENV ve anahtarı ekleyin."
            )
        return key

    def token(self) -> str:
        """Geçerli bir erişim belirteci döndürür; gerekiyorsa yeniler."""
        if self._token and time.time() < self._expires_at:
            return self._token

        # Anahtar TRY DIŞINDA çözülür. İçeride çözülseydi aşağıdaki geniş
        # `except` onu da yakalar ve "uç yanıt vermedi" diye yeniden
        # sarardı: anahtarı olmayan kullanıcı, ağ arızası sanıp yanlış
        # yerde arardı. Eksik yapılandırma ile ağ arızası ayrı şeylerdir.
        api_key = self._api_key()

        owns_client = self.client is None
        client = self.client or HttpClient(respect_robots=False)
        try:
            response = client.post(
                TOKEN_URL,
                data={
                    "grant_type": "password",
                    "client_id": CLIENT_ID,
                    "api_key": api_key,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                source_slug="tuik",
            )
        except Exception as exc:  # noqa: BLE001
            # Anahtar istisna metnine sızmasın diye tür adıyla yetinilir.
            raise TuikAuthError(
                f"TÜİK belirteç ucu yanıt vermedi: {type(exc).__name__}"
            ) from None
        finally:
            if owns_client:
                client.close()

        payload = response.json()
        token = payload.get("access_token", "")
        if not token:
            raise TuikAuthError("Belirteç yanıtında access_token yok.")

        ttl = int(payload.get("expires_in", 300))
        self._token = token
        self._expires_at = time.time() + max(ttl - REFRESH_MARGIN_SECONDS, 5)

        log.info("tuik_token_acquired", ttl_seconds=ttl)
        return token

    def auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}"}
