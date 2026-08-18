"""TCMB EVDS erişimini ve seri kodlarını uçtan uca doğrular (Faz 1.1).

**Bu betiğin var olma sebebi bir kuraldır:** `adapters/evds.py` yalnızca
`verified=True` işaretli serileri yayımlar ve o bayrak elle açılmaz.
Yanlış bir seri kodunun tehlikesi 404 almak değildir — o zaten görünür.
Tehlike, kodun **başka bir büyüklüğü** döndürmesidir: etiket "politika
faizi" der, sayı başka bir şeydir ve kimse fark etmez.

Betik üç şeyi ayrı ayrı sınar ve nerede koptuğunu söyler:

    1. Anahtar var mı?            (yapılandırma)
    2. Uç JSON mu döndürüyor?     (EVDS anahtarsız istekte HTTP 200 ile
                                   HTML SPA kabuğu döndürüyor — bu depo
                                   aynı sessiz arızayı B-42 ve B-43'te
                                   iki kez yaşadı)
    3. Kod gerçekten O seriyi mi getiriyor?
                                  (seri adı `expected_name_contains` ile
                                   karşılaştırılır)

Çıktısı bir KARAR DEĞİL, bir öneridir: hangi satırların
`verified=True` yapılabileceğini yazdırır. Uygulamayı insan yapar.

⛔ API anahtarı ekrana basılmaz.

Kullanım:
    python -m scripts.probe_evds
"""

from __future__ import annotations

import json
import sys
import unicodedata

from politikdesk.config import load_env_file
from politikdesk.ingestion.adapters.evds import (
    EVDS_BASE,
    TRACKED,
    EvdsAdapter,
    EvdsAuthError,
    EvdsResponseError,
    EvdsSeries,
    api_key,
    normalize_period,
    parse_value,
)
from politikdesk.ingestion.http import HttpClient


def fold(text: str) -> str:
    """Aksan ve büyük/küçük farkını siler — Türkçe `İ`/`ı` tuzağı dâhil.

    `nlp/claims.py::fold_text` ile aynı deyim; ad karşılaştırması
    "Politika Faizi" ile "politika faizi"ni aynı saymalı.
    """
    decomposed = unicodedata.normalize("NFKD", text.replace("İ", "i").replace("I", "ı"))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _seri_adi(client: HttpClient, spec: EvdsSeries, key: str) -> str | None:
    """Serinin TCMB'deki resmî adını okur.

    EVDS meta ucu seri adını Türkçe ve İngilizce döndürür. Hangi alan
    adının geleceği belgelenmemiş, bu yüzden birkaç aday taranır.
    """
    url = f"{EVDS_BASE}/serieList/type=json&code={spec.code}"
    try:
        response = client.get(url, headers={"key": key}, source_slug="tcmb-evds")
    except Exception as exc:  # noqa: BLE001
        print(f"      meta ucu yanit vermedi: {type(exc).__name__}")
        return None

    govde = (response.text or "").strip()
    if govde.lstrip()[:40].lower().startswith(("<!doctype html", "<html")):
        return None
    try:
        payload = json.loads(govde)
    except json.JSONDecodeError:
        return None

    kayitlar = payload if isinstance(payload, list) else payload.get("items") or []
    for kayit in kayitlar if isinstance(kayitlar, list) else []:
        if not isinstance(kayit, dict):
            continue
        for alan in ("SERIE_NAME", "SERIE_NAME_ENG", "serieName", "DATAGROUP_NAME"):
            if kayit.get(alan):
                return str(kayit[alan])
    return None


def main() -> int:
    load_env_file()

    # ------------------------------------------------------- 1. anahtar
    print("1) API anahtari")
    try:
        key = api_key()
    except EvdsAuthError as exc:
        print(f"   [YOK] {exc}")
        print()
        print("   EVDS anahtari evds2.tcmb.gov.tr uzerinden UCRETSIZ alinir.")
        print("   Sonra .env'e:")
        print("       PD_EVDS_API_KEY_ENV=EVDS_API_KEY")
        print("       EVDS_API_KEY=<anahtar>")
        return 1
    print(f"   [OK] anahtar bulundu ({len(key)} karakter, icerigi basilmaz)")
    print()

    adapter = EvdsAdapter()
    assert adapter.http is not None
    client = adapter.http

    dogrulanan: list[str] = []
    reddedilen: list[str] = []

    # ------------------------------------------------- 2-3. seri seri sina
    print(f"2) {len(TRACKED)} seri sinaniyor")
    for spec in TRACKED:
        durum = "dogrulanmis" if spec.verified else "dogrulanmamis"
        print(f"\n   {spec.code}  ({spec.label}) [{durum}]")

        url = adapter.data_url(spec)
        try:
            response = client.get(url, headers={"key": key}, source_slug="tcmb-evds")
        except Exception as exc:  # noqa: BLE001
            print(f"      [HATA] istek basarisiz: {type(exc).__name__}: {str(exc)[:90]}")
            reddedilen.append(spec.code)
            continue

        # Sozlesme denetimi — HTML kabugu burada yakalanir.
        try:
            gozlemler = adapter._parse_payload(response.text, spec)  # noqa: SLF001
        except EvdsResponseError as exc:
            print(f"      [HATA] {exc}")
            reddedilen.append(spec.code)
            continue

        if not gozlemler:
            print("      [HATA] gozlem yok — kod dogru olabilir ama seri bos donuyor")
            reddedilen.append(spec.code)
            continue

        period, value = gozlemler[-1]
        print(f"      son gozlem : {period} = {value}  ({len(gozlemler)} gozlem)")

        # Kod gercekten O seriyi mi getiriyor?
        ad = _seri_adi(client, spec, key)
        if ad is None:
            print("      [SUPHELI] seri adi okunamadi — kod DOGRULANMIS SAYILMAZ")
            reddedilen.append(spec.code)
            continue

        print(f"      TCMB adi   : {ad}")
        if fold(spec.expected_name_contains) in fold(ad):
            print(f"      [OK] ad beklenen parcayi iceriyor: '{spec.expected_name_contains}'")
            dogrulanan.append(spec.code)
        else:
            print(
                f"      [RED] ad beklenen parcayi ICERMIYOR "
                f"('{spec.expected_name_contains}' aranmisti). "
                "Kod baska bir buyuklugu getiriyor olabilir."
            )
            reddedilen.append(spec.code)

    adapter.close()

    # ---------------------------------------------------------- 4. ozet
    print()
    print("3) Sonuc")
    print(f"   dogrulanan : {len(dogrulanan)}/{len(TRACKED)}")
    print(f"   reddedilen : {len(reddedilen)}/{len(TRACKED)}")

    if dogrulanan:
        print()
        print("   adapters/evds.py icinde asagidaki serilerde verified=True yapilabilir:")
        for kod in dogrulanan:
            print(f"       {kod}")
    if reddedilen:
        print()
        print("   Su seriler DOGRULANMADI ve verified=False kalmali:")
        for kod in reddedilen:
            print(f"       {kod}")
        print()
        print("   Dogru kodu bulmak icin EVDS veri gruplarina bakin:")
        print(f"       {EVDS_BASE}/datagroups/mode=0&type=json")

    # Cikis kodu: en az bes seri dogrulanmadikca Faz 1.1'in cikis olcutu
    # saglanmis sayilmaz (roadmap: "en az 5 gosterge guvenilir sekilde").
    return 0 if len(dogrulanan) >= 5 else 2


if __name__ == "__main__":
    # `normalize_period` ve `parse_value` burada kullanilmiyor ama
    # disari acik sozlesmenin parcasi; import edilmeleri, adaptor
    # yeniden duzenlenirse bu betigin de kirilmasini saglar.
    _ = (normalize_period, parse_value)
    sys.exit(main())
