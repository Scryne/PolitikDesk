"""KAP (Kamuyu Aydınlatma Platformu) erişimini yoklar (Roadmap Faz 1.3).

**Bu betik bir adaptör DEĞİL, bir ölçüm aracıdır** ve bilinçli olarak
öyle bırakılmıştır.

19 Ağustos 2026'da KAP'a erişim ölçüldü ve sonuç şuydu: bildirimlere
ulaşan doğrulanabilir, sunucudan okunabilir bir uç **bulunamadı**. Bu
depoda doğrulanmamış bir uca adaptör yazmak yasaktır — aynı kural
`adapters/evds.py`'de seri kodları için uygulanıyor ve gerekçesi
oradadır: doğrulanmamış kaynak, sessizce yanlış veri üretir.

Betik ölçümü YENİDEN KOŞULABİLİR kılar. KAP'ın erişim politikası
değişirse (ya da Veri Yayın Servisi aboneliği alınırsa) bu betik
saniyeler içinde yeni durumu söyler ve ADR-007 buna göre güncellenir.

Ölçülen dört şey:
    1. Site ayakta mı?
    2. robots.txt okunabiliyor mu?     (izin beyanı var mı)
    3. Bildirim ucu yanıt veriyor mu?
    4. Sayfanın sunucu yükünde bildirim var mı?

Kullanım:
    python -m scripts.probe_kap
"""

from __future__ import annotations

import sys
from typing import Any

import httpx

BASE = "https://www.kap.org.tr"

# Tarayıcı benzeri başlık BİLİNÇLİ kullanılıyor: amaç engel aşmak değil,
# "engel bota mı özel, herkese mi?" sorusunu yanıtlamak. 19 Ağustos
# ölçümünde iki başlık da AYNI sonucu verdi — yani hedefli bir bot
# engeli yok, uç herkese kapalı.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

BOT_HEADERS = {"User-Agent": "PolitikDesk/1.0 (+arastirma)"}

# 19 Ağustos 2026'da denenen uçlar ve alınan yanıtlar.
CANDIDATE_ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("bildirim ucu", "/tr/api/disclosures"),
    ("bildirim listesi", "/tr/api/disclosure/list"),
    ("sorgu ucu", "/tr/api/disclosure/query"),
    ("üye filtresi", "/tr/api/member/filter/bist-sirket"),
)


def _dene(client: httpx.Client, url: str) -> str:
    try:
        r = client.get(url)
        ct = r.headers.get("content-type", "?")[:28]
        return f"HTTP {r.status_code:>3}  {len(r.text):>8}b  {ct}"
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}"


def main() -> int:
    bulgular: dict[str, Any] = {}

    with httpx.Client(timeout=30.0, follow_redirects=True, headers=BROWSER_HEADERS) as c:
        print("1) Site ayakta mi?")
        for ad, yol in (("ana sayfa", "/tr/"), ("bildirim sorgu", "/tr/bildirim-sorgu")):
            sonuc = _dene(c, BASE + yol)
            print(f"   {ad:16} {sonuc}")
            bulgular[ad] = sonuc

        print("\n2) robots.txt okunabiliyor mu? (izin beyani)")
        for ad, h in (("bot UA", BOT_HEADERS), ("tarayici UA", BROWSER_HEADERS)):
            try:
                r = httpx.get(f"{BASE}/robots.txt", headers=h, timeout=20.0)
                durum = f"HTTP {r.status_code}"
                okunabilir = r.status_code == 200 and "user-agent" in r.text.lower()
            except Exception as exc:  # noqa: BLE001
                durum, okunabilir = type(exc).__name__, False
            print(f"   {ad:16} {durum:16} okunabilir={okunabilir}")
            bulgular[f"robots/{ad}"] = durum

        print("\n3) Bildirim uclari yanit veriyor mu?")
        json_donen = 0
        for ad, yol in CANDIDATE_ENDPOINTS:
            sonuc = _dene(c, BASE + yol)
            print(f"   {ad:16} {sonuc}")
            bulgular[ad] = sonuc
            if "application/json" in sonuc:
                json_donen += 1

        print("\n4) Sunucu yukunde bildirim var mi?")
        try:
            html = c.get(f"{BASE}/tr/bildirim-sorgu").text
            isaretler = {k: html.count(k) for k in ("publishDate", "disclosureIndex", "kapTitle")}
            print(f"   bildirim alanlari: {isaretler}")
            ssr_var = any(isaretler.values())
        except Exception as exc:  # noqa: BLE001
            print(f"   okunamadi: {type(exc).__name__}")
            ssr_var = False

    print("\n" + "=" * 62)
    if json_donen and ssr_var:
        print("SONUC: Bildirim verisi ERISILEBILIR gorunuyor.")
        print("       ADR-007 yeniden degerlendirilmeli; adaptor yazilabilir.")
        return 0

    print("SONUC: Bildirimlere ulasan dogrulanabilir bir uc BULUNAMADI.")
    print()
    print("  Bu, 19 Agustos 2026 olcumuyle ayni sonuctur (bkz. ADR-007).")
    print("  Adaptor YAZILMAZ: dogrulanmamis uca adaptor yazmak, bu depoda")
    print("  `adapters/evds.py`'de seri kodlari icin de yasakli olan seydir.")
    print()
    print("  Erisim degistiginde bu betigi yeniden kosun.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
