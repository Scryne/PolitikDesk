"""F5-02 — TÜİK belirteç edinimi (B-42'nin kimlik doğrulama parçası).

Belirteç **5 dakika** yaşıyor (`expires_in: 300`). İki uç davranış da
yanlıştır ve testler ikisini de kovalar:

  - her çağrıda yeniden almak  -> kimlik sunucusunu gereksiz yorar
  - bir kez alıp saklamak      -> tur ortasında 401'e düşer

Ağ çağrısı yapılmaz; sahte istemci kullanılır.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import pytest

from politikdesk.ingestion.tuik_auth import (
    CLIENT_ID,
    REFRESH_MARGIN_SECONDS,
    TOKEN_URL,
    TuikAuthError,
    TuikTokenProvider,
)


@dataclass
class _FakeResponse:
    payload: dict[str, Any]

    def json(self) -> dict[str, Any]:
        return self.payload


@dataclass
class _FakeClient:
    """`HttpClient` yerine geçer; çağrıları kaydeder."""

    ttl: int = 300
    calls: list[dict[str, Any]] = field(default_factory=list)
    token_value: str = "tok-1"

    def post(self, url: str, *, data: dict[str, str] | None = None,
             headers: dict[str, str] | None = None,
             source_slug: str = "") -> _FakeResponse:
        self.calls.append({"url": url, "data": data or {}})
        return _FakeResponse(
            {"access_token": f"{self.token_value}-{len(self.calls)}",
             "expires_in": self.ttl}
        )

    def close(self) -> None:  # pragma: no cover — sahte istemci
        pass


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PD_TUIK_API_KEY_ENV", "TUIK_TEST_KEY")
    monkeypatch.setenv("TUIK_TEST_KEY", "gizli-anahtar")


def test_token_request_uses_documented_protocol() -> None:
    """Protokol TÜİK'in kendi belgesinden çıkarıldı; alanlar birebir olmalı.

    Belge sunucudan okunabilen bir yerde YAYIMLANMIYOR — veriportali bir
    React SPA ve /swagger/v1/swagger.json bile "JavaScript gerekli"
    kabuğunu döndürüyor. Akış, uygulamanın JS paketine gömülü markdown
    içinden bulundu. Bu test o keşfi dondurur: alan adları değişirse
    sessizce 401 almak yerine test kırılır.
    """
    client = _FakeClient()
    provider = TuikTokenProvider(client=client)

    provider.token()

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == TOKEN_URL
    assert call["data"]["grant_type"] == "password"
    assert call["data"]["client_id"] == CLIENT_ID
    assert call["data"]["api_key"] == "gizli-anahtar"


def test_token_is_cached_between_calls() -> None:
    """Geçerli belirteç varken kimlik sunucusu yeniden çağrılmaz."""
    client = _FakeClient()
    provider = TuikTokenProvider(client=client)

    first = provider.token()
    second = provider.token()

    assert first == second
    assert len(client.calls) == 1


def test_token_is_refreshed_before_it_expires() -> None:
    """Ömrün SONUNU beklemez — payı kadar önce yeniler.

    Tam sınırda yenilemek, isteğin yolda ölmesi demektir: belirteç
    gönderilirken geçerli, sunucuya varınca değil.
    """
    client = _FakeClient(ttl=REFRESH_MARGIN_SECONDS + 10)
    provider = TuikTokenProvider(client=client)

    provider.token()
    # Pay düşüldükten sonra 10 saniyelik gerçek ömür kalır.
    provider._expires_at = time.time() - 1

    provider.token()
    assert len(client.calls) == 2


def test_missing_key_raises_without_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TUIK_TEST_KEY", raising=False)
    client = _FakeClient()
    provider = TuikTokenProvider(client=client)

    with pytest.raises(TuikAuthError) as err:
        provider.token()

    assert client.calls == []
    assert "TUIK_TEST_KEY" in str(err.value)


def test_transport_failure_does_not_leak_the_key() -> None:
    """Hata mesajı anahtarı İÇEREMEZ — sır istisnaya bile girmez."""

    class _Exploding(_FakeClient):
        def post(self, url: str, **kwargs: Any) -> _FakeResponse:
            raise RuntimeError(f"baglanti koptu: api_key=gizli-anahtar url={url}")

    provider = TuikTokenProvider(client=_Exploding())

    with pytest.raises(TuikAuthError) as err:
        provider.token()

    assert "gizli-anahtar" not in str(err.value)


def test_auth_header_is_bearer() -> None:
    provider = TuikTokenProvider(client=_FakeClient())
    assert provider.auth_header()["Authorization"].startswith("Bearer ")
