"""TÜİK SDMX erişimini uçtan uca doğrular (F5-02 · B-42).

**Protokol nereden bulundu:** TÜİK'in API belgesi sunucudan okunabilen
bir yerde yayımlanmıyor — `veriportali` bir React SPA ve
`/swagger/v1/swagger.json` bile "JavaScript gerekli" kabuğunu döndürüyor
(B-42'nin üç fazdır açık kalmasının sebebi buydu). Belge, uygulamanın JS
paketine (`/assets/main-*.js`) gömülü markdown içinde bulundu:

    POST giris.tuik.gov.tr/realms/web/protocol/openid-connect/token
      grant_type=password & client_id=nsi-ws-consumer & api_key=<KEY>
    -> access_token (expires_in: 300)

    GET nsiws.tuik.gov.tr/rest/... + Authorization: Bearer <token>

Bu betik o zinciri koşar ve nerede koptuğunu söyler.

**Aralıklı TLS arızası beklenen bir durumdur:** `giris` ve `nsiws`
konakları zaman zaman el sıkışma ortasında bağlantıyı düşürüyor
(`UNEXPECTED_EOF_WHILE_READING` — Resmî Gazete'nin B-44'teki semptomuyla
aynı sınıf, ama burada kalıcı değil). `HttpClient` bunu yeniden dener;
tek bir hata "kaynak ölü" demek DEĞİLDİR.

⛔ Anahtar ve belirteç ekrana basılmaz.

Kullanım:
    python -m scripts.probe_tuik
"""

from __future__ import annotations

import re

from politikdesk.config import load_env_file
from politikdesk.ingestion.http import HttpClient
from politikdesk.ingestion.tuik_auth import TuikAuthError, TuikTokenProvider

DATAFLOW_URL = "https://nsiws.tuik.gov.tr/rest/dataflow/TR/all/latest"

# MVP konularına karşılık gelen akışlar (docs/mvp-konu-kapsami.md).
INTERESTING = ("UFE", "ISGUCU", "GSYH")


def probe() -> int:
    load_env_file()

    with HttpClient(respect_robots=False, timeout=90.0) as client:
        provider = TuikTokenProvider(client=client)

        try:
            header = provider.auth_header()
        except TuikAuthError as exc:
            print(f"[HATA] Belirtec alinamadi: {exc}")
            print()
            print("Yapilacak: .env dosyasina su iki satiri ekleyin")
            print("    PD_TUIK_API_KEY_ENV=TUIK_API_KEY")
            print("    TUIK_API_KEY=<anahtariniz>")
            return 1

        print(f"[OK] Belirtec alindi ({len(header['Authorization'])} karakter).")

        try:
            response = client.get(DATAFLOW_URL, headers=header, source_slug="tuik")
        except Exception as exc:  # noqa: BLE001
            print(f"[HATA] SDMX cagrisi basarisiz: {type(exc).__name__}")
            return 2

        body = response.text
        flows = re.findall(
            r'<structure:Dataflow[^>]*\bid="([^"]+)"[^>]*>(.*?)</structure:Dataflow>',
            body, re.DOTALL,
        )
        print(f"[OK] SDMX {response.status_code} — {len(body):,} karakter, "
              f"{len(flows)} veri akisi.")
        print()
        print("MVP konularina yakin akislar:")
        shown = 0
        for flow_id, inner in flows:
            if not any(k in flow_id.upper() for k in INTERESTING):
                continue
            name = re.search(r'<common:Name xml:lang="tr">(.*?)</common:Name>',
                             inner, re.DOTALL)
            print(f"  {flow_id:44} {(name.group(1).strip() if name else '')[:58]}")
            shown += 1
            if shown >= 12:
                break

        print()
        print("NOT: TUFE (tuketici fiyat endeksi) bu listede YOKTUR — 'TR'")
        print("ajansi yalnizca URETICI fiyat endekslerini (UFE) ve isgucu/GSYH")
        print("serilerini yayimliyor. Enflasyonun TUFE ayagi bu API'den gelmez.")
        return 0


if __name__ == "__main__":
    raise SystemExit(probe())
