"""TÜİK SDMX servisinin kimlik doğrulama şemasını tespit eder (F5-02).

B-42'nin kalan parçası. Teşhis şuydu: bülten listesi `veriportali` ve
`data.tuik.gov.tr` üzerinde React SPA olarak yükleniyor (sunucu yalnızca
"JavaScript gerekli" kabuğu döndürüyor; `/swagger/v1/swagger.json` bile
aynı kabuğu döndürür — gerçek bir spec değildir). Sunucu tarafından
okunabilen tek uç **SDMX servisidir**:

    https://nsiws.tuik.gov.tr/rest/...

Bu uç kimlik doğrulama ister ve 401'i `WWW-Authenticate` başlığı
OLMADAN döndürür — yani şema ilan edilmiyor. Anahtarın hangi biçimde
gönderileceği ancak denenerek bulunur. Bu betik onu yapar.

⛔ **Anahtar hiçbir koşulda ekrana basılmaz.** Yalnızca hangi şemanın
kaç döndürdüğü yazılır. Anahtar `.env`'den, dolaylı desenle okunur:
`PD_TUIK_API_KEY_ENV` hangi ortam değişkeninin anahtarı taşıdığını
söyler (`PD_LLM_API_KEY_ENV` ile aynı deyim, B-64).

Kullanım:
    python -m scripts.probe_tuik
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from politikdesk.config import load_env_file

BASE = "https://nsiws.tuik.gov.tr/rest"
# Şema keşfi için en ucuz uç: veri değil, veri akışı listesi.
PROBE_PATH = "/dataflow"

UA = "PolitikDesk/1.0 (+kişisel araştırma aracı)"


@dataclass
class Attempt:
    label: str
    status: int
    detail: str


def _schemes(key: str) -> list[tuple[str, dict[str, str], dict[str, str]]]:
    """(etiket, başlıklar, sorgu parametreleri) — denenecek şemalar."""
    return [
        ("Authorization: Bearer", {"Authorization": f"Bearer {key}"}, {}),
        ("Authorization: ApiKey", {"Authorization": f"ApiKey {key}"}, {}),
        ("Authorization: <ham>", {"Authorization": key}, {}),
        ("X-API-Key", {"X-API-Key": key}, {}),
        ("apikey", {"apikey": key}, {}),
        ("sorgu: api_key", {}, {"api_key": key}),
        ("sorgu: apiKey", {}, {"apiKey": key}),
    ]


def probe() -> int:
    load_env_file()

    var = os.environ.get("PD_TUIK_API_KEY_ENV", "TUIK_API_KEY")
    key = os.environ.get(var, "").strip()

    if not key:
        print(f"[EKSIK] Anahtar bulunamadi. '{var}' ortam degiskeni bos.")
        print()
        print("Yapilacak: .env dosyasina su iki satiri ekleyin")
        print()
        print("    PD_TUIK_API_KEY_ENV=TUIK_API_KEY")
        print("    TUIK_API_KEY=<anahtariniz>")
        print()
        print("Anahtari sohbete YAZMAYIN; yalnizca .env'e koyun.")
        return 1

    print(f"Anahtar '{var}' degiskeninde bulundu ({len(key)} karakter).")
    print(f"Sonda ucu: {BASE}{PROBE_PATH}")
    print()

    results: list[Attempt] = []
    with httpx.Client(timeout=25.0, follow_redirects=True) as client:
        for label, headers, params in _schemes(key):
            try:
                r = client.get(
                    f"{BASE}{PROBE_PATH}",
                    headers={"User-Agent": UA, "Accept": "application/json", **headers},
                    params=params,
                )
                detail = "" if r.status_code == 200 else r.text[:80].replace("\n", " ")
                results.append(Attempt(label, r.status_code, detail))
            except Exception as exc:  # noqa: BLE001
                results.append(Attempt(label, 0, f"{type(exc).__name__}: {exc}"[:80]))

    ok = [a for a in results if a.status == 200]
    for a in results:
        mark = "[OK]  " if a.status == 200 else "[--]  "
        print(f"  {mark}{a.label:24} {a.status}  {a.detail}")

    print()
    if ok:
        print(f"CALISAN SEMA: {ok[0].label}")
        print("Adaptor bu semayla yazilacak (F5-02).")
        return 0

    print("Hicbir sema 200 dondurmedi.")
    print("Olasiliklar: anahtar farkli bir servise ait, sureli bir belirtec")
    print("gerekiyor (giris.tuik.gov.tr / Keycloak), ya da IP kisiti var.")
    return 2


if __name__ == "__main__":
    raise SystemExit(probe())
