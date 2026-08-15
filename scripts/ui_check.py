"""Görsel doğrulama döngüsü — DESIGN.md Bölüm 14'ün koşturulabilir hâli.

**Neden bir betik, neden elle bakış değil:** Bölüm 14 "ajan kendi çıktısını
görmeden görev bitmez" der ve dört viewport'ta screenshot ister. Elle
bakışın yakalayamadığı iki şey var ve ikisi de DoD maddesi:

  * **Yatay taşma** (`scrollWidth > clientWidth`). Bir ekran görüntüsünde
    taşma "sağda bir şey kesilmiş" gibi görünür ve kolayca "öyle
    tasarlanmış" sanılır. Ölçüldüğünde tartışma biter — ve TAŞIRAN ÖĞE
    de bulunur, ki asıl zor kısım odur.
  * **Konsol hatası.** Görüntüde hiç iz bırakmaz.

Kullanım:

    pd ui-check                 # tüm ekranlar, 4 viewport
    python scripts/ui_check.py --only /feed --shots

Çıkış kodu: taşma veya konsol hatası varsa 1.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHOTS_DIR = REPO_ROOT / "design" / "shots"

BASE_URL = "http://localhost:8000"

# Bölüm 14.2'nin zorunlu viewport'ları.
VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("mobil", 375, 812),
    ("tablet", 768, 1024),
    ("masaustu", 1440, 900),
    ("genis", 1920, 1080),
)

# Depodaki her ekran (11 ekran · FAZ 12.2). Yeni sayfa açan buraya bir satır
# ekler; eklemeyen sayfa denetlenmez ve denetlenmeyen sayfa bozulur.
PAGES: tuple[tuple[str, str], ...] = (
    ("gundem", "/feed"),
    ("brifingler", "/briefing"),
    ("editoryal-kimlik", "/onboarding/profile"),
    ("boru-hatti", "/admin/"),
    ("metrikler", "/admin/metrics"),
    ("denetim-kuyrugu", "/admin/review/"),
    ("beklenen-gelismeler", "/admin/calendar/"),
    ("hesap-sor", "/accountability"),
    ("hafiza", "/memory"),
    ("vaatler", "/promises"),
    ("arsiv", "/archive"),
)

# Taşmayı ÖLÇEN ve taşıran öğeyi BULAN betik. İkincisi olmadan bulgu
# "bir yerde taşma var" der ve saatlerce aranır.
_PROBE = """
() => {
  const doc = document.documentElement;
  const overflow = doc.scrollWidth - doc.clientWidth;
  const guilty = [];
  if (overflow > 0) {
    const limit = doc.clientWidth;
    document.querySelectorAll('body *').forEach(el => {
      const r = el.getBoundingClientRect();
      if (r.width === 0) return;
      if (r.right > limit + 1 || r.left < -1) {
        // Yalnızca EN DIŞTAKİ suçluyu bildir: taşan bir çocuğun tüm
        // ataları da taşmış görünür ve liste gürültüye boğulur.
        if (!guilty.some(g => g.el.contains(el))) {
          guilty.push({el: el, info:
            el.tagName.toLowerCase() +
            (el.id ? '#' + el.id : '') +
            (el.className && typeof el.className === 'string'
              ? '.' + el.className.trim().split(/\\s+/).join('.') : '') +
            '  [' + Math.round(r.left) + '..' + Math.round(r.right) + ']'});
        }
      }
    });
  }
  return {
    overflow: overflow,
    scrollWidth: doc.scrollWidth,
    clientWidth: doc.clientWidth,
    guilty: guilty.slice(0, 6).map(g => g.info),
    h1: document.querySelectorAll('h1').length,
    lang: doc.lang,
    iconButtonsWithoutLabel: [...document.querySelectorAll('button, a.btn')]
      .filter(b => !b.textContent.trim() &&
                   !b.getAttribute('aria-label') && !b.title).length,
  };
}
"""


class _ErrorCollector:
    """Bir sayfanın konsol hatalarını toplar.

    Uyarılar da toplanır, yalnız hatalar değil: React key uyarısı, kırık
    kaynak uyarısı ve `preload` uyarısı ekranda iz bırakmaz ama bir
    sorunun habercisidir (DESIGN.md Bölüm 14.3: "0 hata, 0 uyarı").
    """

    def __init__(self) -> None:
        self.messages: list[str] = []

    def on_console(self, message: object) -> None:
        kind = getattr(message, "type", "")
        if kind in ("error", "warning"):
            self.messages.append(f"console.{kind}: {getattr(message, 'text', '')}")

    def on_page_error(self, error: object) -> None:
        self.messages.append(f"pageerror: {error}")

    def __bool__(self) -> bool:
        return bool(self.messages)

    def __iter__(self):  # noqa: ANN204
        return iter(self.messages)


def main() -> int:
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser(description="DESIGN.md Bölüm 14 denetimi")
    parser.add_argument("--only", help="tek bir yol denetle (ör. /feed)")
    parser.add_argument("--shots", action="store_true", help="screenshot da al")
    parser.add_argument("--theme", default="dark", choices=["dark", "light"])
    parser.add_argument("--base", default=BASE_URL)
    args = parser.parse_args()

    pages = (("tek", args.only),) if args.only else PAGES
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)

    problems: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, path in pages:
            for label, width, height in VIEWPORTS:
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    color_scheme=args.theme,
                    locale="tr-TR",
                )
                page = context.new_page()

                # Dinleyiciler döngü değişkenine kapanmaz: her viewport için
                # yeni bir toplayıcı kurulur ve `errors` ona bağlanır.
                # (Lambda ile yazıldığında ruff B023 uyarıyordu ve haklıydı —
                # kapanış geç bağlanır, bir gün bir hata yanlış sayfaya
                # yazılır.)
                errors = _ErrorCollector()
                page.on("console", errors.on_console)
                page.on("pageerror", errors.on_page_error)

                page.goto(f"{args.base}{path}", wait_until="networkidle")
                result = page.evaluate(_PROBE)

                where = f"{path} @ {label} ({width}px)"
                if result["overflow"] > 0:
                    problems.append(
                        f"YATAY TASMA  {where}: "
                        f"{result['scrollWidth']} > {result['clientWidth']} "
                        f"(+{result['overflow']}px)\n"
                        + "".join(f"    tasiran: {g}\n" for g in result["guilty"])
                    )
                if errors:
                    problems.append(f"KONSOL  {where}:\n" + "".join(f"    {e}\n" for e in errors))
                if result["h1"] != 1:
                    problems.append(
                        f"BASLIK  {where}: sayfada {result['h1']} adet <h1> "
                        "var, tam 1 olmali (Bolum 12)."
                    )
                if result["lang"] != "tr":
                    problems.append(f"DIL  {where}: <html lang> = {result['lang']!r}")
                if result["iconButtonsWithoutLabel"]:
                    problems.append(
                        f"ERISILEBILIRLIK  {where}: "
                        f"{result['iconButtonsWithoutLabel']} ikon-only butonda "
                        "aria-label/title yok (Bolum 12)."
                    )

                if args.shots and label in ("mobil", "masaustu"):
                    page.screenshot(
                        path=str(SHOTS_DIR / f"{name}-{label}-{args.theme}.png"),
                        full_page=True,
                    )
                context.close()
                status = "ok" if not problems or where not in problems[-1] else "!!"
                print(f"  [{status}] {where}")
        browser.close()

    print()
    if problems:
        print("BULGULAR\n" + "=" * 60)
        for problem in problems:
            print(problem)
        return 1
    print("Temiz: yatay tasma yok, konsol hatasi yok, h1/lang/aria gecti.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
