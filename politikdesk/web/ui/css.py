"""Stylesheet — `tokens.py`'den TÜRETİLİR, elle yazılmaz.

Depoda tek bir CSS kaynağı vardır. Eskiden üç ayrı yerde (layout.py,
admin/router.py, admin/events.py) birbirinden habersiz üç stil bloğu
duruyordu; "her sayfa farklı görünüyor" şikayetinin tek nedeni buydu.

### Tema anahtarı

```
:root                                   → açık tema
@media (prefers-color-scheme: dark)     → sistem koyu ise, kullanıcı AÇIK
  :root:not([data-theme="light"])         demediyse koyu
[data-theme="dark"]                     → kullanıcı KOYU dediyse, sistem ne
                                          derse desin
```

`DESIGN.md` Bölüm 5.2'deki `@media (...), [data-theme="dark"]` yazımı geçerli
CSS değildir (medya sorgusu ile seçici tek listede birleşemez); yukarıdaki üç
katman aynı davranışı doğru sözdizimiyle verir.

### Signature — "kanıt cetveli"

Bu arayüzü akılda kalıcı yapan tek öğe (`design/refs/README.md`): her iddia
ve her olay kartı, sol kenarında kanıt durumunun rengini taşıyan **3px'lik
bir cetvel** ile işaretlenir; iddia metninin kontrastı da kanıt gücüyle
birlikte düşer. Teyitli iddia tam mürekkeple, doğrulanmamış iddia soluk
yazılmıştır — tıpkı bir editörün kenar notu gibi.

Bu bir dekorasyon değil, ürünün tek cümlelik sözleşmesinin tipografik
karşılığıdır: kanıt gücü *okunmadan önce* görülür. Rozeti kaldırırsan bilgi
kaybolmaz (metin etiketi durur); cetveli kaldırırsan ekranın karakteri
kaybolur.
"""

from __future__ import annotations

from politikdesk.web.ui.tokens import (
    DARK,
    FONT,
    LAYOUT,
    LIGHT,
    MOTION,
    RADIUS,
    SHADOW,
    SPACE,
    TEXT,
    WEIGHT,
)

# Google Fonts'un alt küme aralıkları. Türkçe için `latin-ext` şart:
# Ğ (U+011E), Ş (U+015E), İ (U+0130) ve ₺ (U+20BA) orada.
_RANGE_LATIN = (
    "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,"
    "U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,"
    "U+2212,U+2215,U+FEFF,U+FFFD"
)
_RANGE_LATIN_EXT = (
    "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,"
    "U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,"
    "U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF"
)

# (aile adı, dosya öneki, ağırlık bildirimi)
_FACES = (
    ("Inter Tight", "inter-tight", "400 600"),
    ("IBM Plex Mono", "ibm-plex-mono", "400"),
    ("Instrument Serif", "instrument-serif", "400"),
)


def _font_faces(base: str) -> str:
    """Kendi barındırdığımız woff2'ler. Harici CDN yok (BRIEF kırmızı çizgi)."""
    blocks: list[str] = []
    for family, slug, weight in _FACES:
        for subset, unicode_range in (
            ("latin", _RANGE_LATIN),
            ("latin-ext", _RANGE_LATIN_EXT),
        ):
            blocks.append(
                f"@font-face{{font-family:'{family}';font-style:normal;"
                f"font-weight:{weight};font-display:swap;"
                f"src:url({base}/fonts/{slug}-{subset}.woff2) format('woff2');"
                f"unicode-range:{unicode_range}}}"
            )
    return "".join(blocks)


def _vars(palette: dict[str, str]) -> str:
    return "".join(f"--{name}:{value};" for name, value in palette.items())


def _static_vars() -> str:
    """Temaya göre değişmeyen token'lar."""
    parts = [
        _vars(SPACE),
        _vars(RADIUS),
        _vars(SHADOW),
        _vars(FONT),
        _vars(WEIGHT),
        _vars(LAYOUT),
        _vars(MOTION),
    ]
    for name, (size, line, tracking) in TEXT.items():
        parts.append(f"--{name}:{size};--{name}-lh:{line};--{name}-ls:{tracking};")
    return "".join(parts)


def stylesheet(static_base: str = "/static") -> str:
    """Tam stylesheet. Sayfa kabuğu (`shell.page`) bunu satır içi basar."""
    return (
        _font_faces(static_base)
        + f"""
:root{{{_vars(LIGHT)}{_static_vars()}color-scheme:light}}
@media (prefers-color-scheme:dark){{
  :root:not([data-theme="light"]){{{_vars(DARK)}color-scheme:dark}}
}}
[data-theme="dark"]{{{_vars(DARK)}color-scheme:dark}}

/* ═══════════════════════════════════════════════════ temel */
*,*::before,*::after{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{
  margin:0;background:var(--color-bg);color:var(--color-fg);
  font-family:var(--font-body);font-size:var(--text-base);
  line-height:var(--text-base-lh);font-weight:var(--weight-normal);
  /* Bölüm 6.5: tabular figürler tüm arayüzde açık. Sayılar sütun halinde
     hizalanır ve canlı güncellemede zıplamaz. */
  font-variant-numeric:tabular-nums;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
}}
::selection{{background:var(--color-accent-subtle);color:var(--color-accent)}}

/* Focus: Bölüm 12 — `outline:none` yazılan HER yerde alternatif zorunlu.
   Burada hiç kaldırılmıyor, yalnızca fare tıklamasında gizleniyor. */
:focus-visible{{
  outline:2px solid var(--color-accent);outline-offset:2px;border-radius:2px;
}}

a{{color:var(--color-accent);text-decoration-color:color-mix(in srgb,currentColor 30%,transparent);
  text-underline-offset:2px}}
a:hover{{text-decoration-color:currentColor}}
a.plain{{color:inherit;text-decoration:none}}
a.plain:hover{{text-decoration:underline;text-decoration-color:currentColor}}

/* ═══════════════════════════════════════════════ tipografi */
h1,h2,h3,h4{{margin:0;font-weight:var(--weight-semibold)}}

/* Serif YALNIZ burada. Başka hiçbir yerde display font kullanılmaz —
   yön A'nın riski buydu ve tek savunması ölçülü kullanım. */
/* Bölüm 6.3 sayfa başlığını 24px verir; burada 30px kullanılıyor çünkü
   Instrument Serif OPTİK OLARAK küçük okunur (dar x-yüksekliği, ince
   gövde). 25px'te kart başlıklarıyla aynı ağırlıkta görünüyordu ve sayfa
   başlığı ekranın en belirgin öğesi olmalı (Bölüm 9.1). Ölçü sayısal
   değil ALGISAL eşitlenir. */
h1,.h1{{
  font-family:var(--font-display);font-weight:var(--weight-normal);
  font-size:var(--text-3xl);line-height:var(--text-3xl-lh);
  letter-spacing:var(--text-3xl-ls);
}}
h2,.h2{{font-size:var(--text-xl);line-height:var(--text-xl-lh);
  letter-spacing:var(--text-xl-ls)}}
h3,.h3{{font-size:var(--text-lg);line-height:var(--text-lg-lh);
  letter-spacing:var(--text-lg-ls)}}

/* Bölüm etiketi — CSS ile BÜYÜK HARFE ÇEVİRMEK YOK.
   Ek B.3: o dönüşüm Türkçede `i` harfini `I` yapar, `İ` olması gerekir
   ("iddia" -> "IDDIA"). Ayrım büyük harfle değil, letter-spacing + renk +
   ağırlık ile kuruluyor. Denetim: tests/test_design_tokens.py */
.eyebrow{{
  font-size:var(--text-xs);line-height:var(--text-xs-lh);
  letter-spacing:.06em;font-weight:var(--weight-semibold);
  color:var(--color-fg-subtle);margin:0;
}}
.muted{{color:var(--color-fg-muted)}}
.subtle{{color:var(--color-fg-subtle)}}
.mono{{font-family:var(--font-mono);font-size:var(--text-sm);
  letter-spacing:-.01em}}
.num{{font-variant-numeric:tabular-nums}}
.prose{{max-width:var(--prose-max)}}
.sr{{position:absolute;width:1px;height:1px;padding:0;margin:-1px;
  overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}}
.sr:focus,.sr:focus-visible{{position:fixed;left:var(--space-4);top:var(--space-4);z-index:1000;
  width:auto;height:auto;padding:var(--space-2) var(--space-4);margin:0;
  overflow:visible;clip:auto;clip-path:none;white-space:normal;
  background:var(--color-surface);color:var(--color-accent);
  border:2px solid var(--color-accent);border-radius:var(--radius-md);
  box-shadow:var(--shadow-md);font-weight:var(--weight-medium);
  text-decoration:none}}

/* ═══════════════════════════════════════════════════ kabuk */
.app{{display:grid;grid-template-columns:var(--sidebar-w) minmax(0,1fr);
  min-height:100vh}}

.side{{
  position:sticky;top:0;height:100vh;display:flex;flex-direction:column;
  background:var(--color-surface);border-right:1px solid var(--color-border);
}}
.side-head{{padding:var(--space-4) var(--space-4) var(--space-3)}}
.brand{{display:flex;align-items:center;gap:var(--space-2);
  text-decoration:none;color:var(--color-fg)}}
.brand-mark{{
  width:28px;height:28px;flex:none;border-radius:var(--radius-md);
  background:var(--color-accent);color:var(--color-fg-on-accent);
  display:grid;place-items:center;
  font-family:var(--font-display);font-size:var(--text-lg);line-height:1;
}}
.brand-name{{font-size:var(--text-base);font-weight:var(--weight-semibold);
  letter-spacing:-.01em}}
.brand-sub{{font-size:var(--text-xs);color:var(--color-fg-subtle);
  letter-spacing:.02em}}

.side-nav{{flex:1;overflow-y:auto;padding:0 var(--space-3) var(--space-3);
  display:flex;flex-direction:column;gap:var(--space-6)}}
.nav-group{{display:flex;flex-direction:column;gap:2px}}
/* Grup başlığı tıklanamaz ve seçilemez (Bölüm 7.2). */
.nav-group>.eyebrow{{padding:0 var(--space-2) var(--space-2);
  user-select:none;pointer-events:none}}
.nav-item{{
  display:flex;align-items:center;gap:10px;height:var(--nav-item-h);
  padding:0 10px;border-radius:var(--radius-md);text-decoration:none;
  color:var(--color-fg-muted);font-size:var(--text-base);
  transition:background var(--dur-hover) var(--ease-out);
}}
/* Hover'da YALNIZCA zemin değişir; metin rengi sabit (Bölüm 7.2). */
.nav-item:hover{{background:var(--color-surface-sunken)}}
/* Aktif öğe: zemin + ağırlık. Sol aksan çubuğu YOK — Bölüm 7.2 ikisini
   birden yapmayı yasaklıyor ve zemin tek başına yeterli sinyal. */
.nav-item[aria-current="page"]{{
  background:var(--color-surface-sunken);color:var(--color-fg);
  font-weight:var(--weight-medium);
}}
.nav-item .ic{{flex:none;color:var(--color-fg-subtle)}}
.nav-item[aria-current="page"] .ic{{color:var(--color-accent)}}
.nav-item .count{{margin-left:auto}}

.side-foot{{border-top:1px solid var(--color-border);padding:var(--space-3);
  display:flex;align-items:center;gap:var(--space-2)}}

/* ─── içerik ─── */
/* `overflow-x:clip` son savunma: tek bir geniş çocuk (uzun bir mono ID,
   taşan bir tablo) tüm sayfayı yatay kaydırılabilir yapmasın. `hidden`
   değil `clip` — `hidden` yapışkan konumlandırmayı (sağ ray) bozar. */
.main{{min-width:0;display:flex;flex-direction:column;overflow-x:clip}}
.content>*{{min-width:0}}
.topbar{{
  position:sticky;top:0;z-index:20;height:var(--topbar-h);flex:none;
  display:flex;align-items:center;gap:var(--space-3);
  padding:0 var(--content-pad-x);
  background:color-mix(in srgb,var(--color-bg) 88%,transparent);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--color-border);
}}
.content{{
  width:100%;max-width:var(--content-max);
  padding:var(--space-6) var(--content-pad-x) var(--space-12);
}}
/* Bölüm 7.4: ≥1920'de içerik 1440'ta sabitlenir ve ORTALANIR. */
@media (min-width:1920px){{.content{{margin-inline:auto}}}}

.crumbs{{display:flex;align-items:center;gap:var(--space-2);
  font-size:var(--text-xs);color:var(--color-fg-subtle);min-width:0}}
.crumbs a{{color:inherit;text-decoration:none}}
.crumbs a:hover{{color:var(--color-fg);text-decoration:underline}}
.crumbs .sep{{color:var(--color-border-strong)}}
.crumbs .here{{color:var(--color-fg-muted);overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}}

/* ─── sayfa başlığı (Bölüm 9.1) ─── */
.page-head{{display:flex;align-items:flex-start;gap:var(--space-4);
  margin-bottom:var(--space-6)}}
.page-head .lede{{margin:var(--space-2) 0 0;color:var(--color-fg-muted);
  max-width:var(--prose-max)}}
.page-head .actions{{margin-left:auto;display:flex;gap:var(--space-2);
  flex:none;align-items:center}}

/* ═══════════════════════════════════════════════ bileşenler */
/* Bölüm 5.5: panel kartı GÖLGE KULLANMAZ, 1px border yeter. */
.card{{background:var(--color-surface);border:1px solid var(--color-border);
  border-radius:var(--radius-lg);padding:var(--card-pad)}}
/* Gündem kartı standarttan YOĞUN: kullanıcı burada 40 kartı TARIYOR, bir
   kartı okumuyor. Tarama ekranı ile okuma ekranı aynı yoğunlukta olamaz —
   Bölüm 9.2'nin yoğunluk modu sayfa başına değil GÖREV başına sabittir. */
.feed-card>.card{{padding:var(--space-4)}}
.feed-card+.feed-card{{margin-top:var(--space-2)}}

/* İki sütun: anlatı solda, KARAR sağda.
   Sağ sütun sabit genişliktedir ve bu kasıtlıdır — 40 kartın "yazılabilir
   mi?" cevabı aynı dikey çizgide durur, göz yatay sıçrama yapmaz. Metin
   uzunluğuna göre kayan bir rozet, tarama ekranını okuma ekranına çevirir. */
.feed-card>.card{{display:grid;
  grid-template-columns:minmax(0,1fr) 148px;gap:var(--space-6)}}
.feed-main{{min-width:0}}
.feed-aside{{display:flex;flex-direction:column;align-items:flex-start;
  gap:var(--space-2);padding-left:var(--space-4);
  border-left:1px solid var(--color-border)}}
/* Kartın kendi ızgarası dar ekranda tek sütuna döner: 172px'lik bir yan
   sütun 375px'te anlatıyı 130px'e sıkıştırırdı. */
@media (max-width:900px){{
  .feed-card>.card{{grid-template-columns:minmax(0,1fr);gap:var(--space-3)}}
  .feed-aside{{flex-direction:row;align-items:center;flex-wrap:wrap;
    padding-left:0;border-left:0;padding-top:var(--space-3);
    border-top:1px solid var(--color-border)}}
}}
.card.flush{{padding:0;overflow:hidden}}
.card-head{{display:flex;align-items:center;gap:var(--space-3);
  margin-bottom:var(--space-3)}}
/* Kart başlığı `h2.h3`tir (seviye semantik, boyut görsel — components.py). */
.card-head h3,.card-head .h3{{min-width:0}}
.card-head .actions{{margin-left:auto;display:flex;gap:var(--space-2);
  align-items:center;flex:none}}

.stack{{display:flex;flex-direction:column;gap:var(--space-6)}}
.stack-sm{{display:flex;flex-direction:column;gap:var(--space-2)}}
.row{{display:flex;align-items:center;gap:var(--space-2);flex-wrap:wrap}}
.row.tight{{gap:var(--space-1)}}
.spacer{{margin-left:auto}}

/* Bölüm 7.3 — minmax(0,…) ZORUNLU, yoksa içerik grid'i patlatır. */
.split{{display:grid;grid-template-columns:minmax(0,2fr) minmax(320px,1fr);
  gap:var(--space-6);align-items:start}}
/* Bölüm 13.3: eşit olmayan kart yükseklikleri yasak. `stretch` burada
   kozmetik değil — "Ne biliyoruz / Ne bilmiyoruz" sütunlarının eşit olması
   ürünün tezi; kademeli duran iki sütun birini ikincil gösterir. */
.halves{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
  gap:var(--space-6);align-items:stretch}}
.halves>*{{height:100%}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
  gap:var(--space-4);align-items:stretch}}

/* ─── KPI kartı · Bölüm 8.1 varyant A (sade) ───
   Sıra HER ZAMAN: etiket → değer → delta. Tek varyant kullanılır;
   aynı satırda iki farklı KPI anatomisi amatör işaretidir. */
.kpi{{display:flex;flex-direction:column;gap:var(--space-2);height:100%}}
.kpi-label{{display:flex;align-items:center;gap:var(--space-2);
  font-size:var(--text-xs);letter-spacing:.02em;
  font-weight:var(--weight-medium);color:var(--color-fg-muted)}}
.kpi-value{{font-size:var(--text-3xl);line-height:var(--text-3xl-lh);
  letter-spacing:var(--text-3xl-ls);font-weight:var(--weight-semibold);
  display:flex;align-items:baseline;gap:6px}}
.kpi-unit{{font-size:var(--text-lg);color:var(--color-fg-subtle);
  font-weight:var(--weight-normal)}}
.kpi-delta{{display:flex;align-items:center;gap:6px;margin-top:auto;
  font-size:var(--text-xs);color:var(--color-fg-subtle)}}
.kpi-delta b{{font-weight:var(--weight-medium)}}
.kpi-delta.up b,.kpi-delta.up .ic{{color:var(--color-strong)}}
.kpi-delta.down b,.kpi-delta.down .ic{{color:var(--color-contra)}}
.kpi-delta.flat b,.kpi-delta.flat .ic{{color:var(--color-fg-muted)}}
/* Metrik kartı: grafik her zaman ALTTA hizalanır, yoksa notu kısa olan
   kartın grafiği yukarı kayar ve sekiz kart kademeli görünür. */
.card.metric{{display:flex;flex-direction:column}}
.card.metric>.chart,.card.metric>p:last-child{{margin-top:auto}}

/* ─── durum rozeti · Bölüm 8.4 ───
   radius 6px (pill DEĞİL — tablo içinde pill amatör durur), 22px yükseklik,
   ve metin HER ZAMAN yazılır: renk tek başına anlam taşımaz. */
.badge{{
  display:inline-flex;align-items:center;gap:5px;height:22px;
  padding:0 8px;border-radius:var(--radius-sm);
  font-size:var(--text-xs);font-weight:var(--weight-medium);
  white-space:nowrap;flex:none;
}}
.badge .ic{{flex:none}}
.badge.neutral{{background:var(--color-surface-sunken);color:var(--color-fg-muted)}}
.badge.outline{{background:transparent;border:1px solid var(--color-border);
  color:var(--color-fg-muted)}}
/* Olay durumu (gelişiyor/oturdu/çelişkili) kanıt skalasından AYRI bir
   eksendir ve onun renklerini KULLANAMAZ: "gelişiyor" amber ile "kısmen
   teyitli" amber yan yana durunca kullanıcı ikisini tek bir ölçek sanar.
   Bu rozet kenarlıklı ve nötr; yalnızca çelişki renklidir, çünkü çelişki
   her iki eksende de aynı şeyi söyler. */
.badge.event{{background:transparent;
  border:1px solid var(--color-border-strong);
  color:var(--color-fg-muted);font-weight:var(--weight-normal)}}
.badge.event.contra{{border-color:var(--color-contra);
  color:var(--color-contra)}}
.badge.strong{{background:var(--color-strong-subtle);color:var(--color-strong)}}
.badge.partial{{background:var(--color-partial-subtle);color:var(--color-partial)}}
.badge.single{{background:var(--color-single-subtle);color:var(--color-single)}}
.badge.contra{{background:var(--color-contra-subtle);color:var(--color-contra)}}
.badge.unverified{{background:var(--color-unverified-subtle);
  color:var(--color-unverified)}}
.badge.accent{{background:var(--color-accent-subtle);color:var(--color-accent)}}

/* Tier etiketi — kaynağın KATMANI (T1 resmî · T2 ajans · T3 yayın).
   Spec §8.5: bu bir siyasi konum göstergesi DEĞİLDİR ve olamaz. Katman,
   kaynağın türünü söyler; duruşu hakkında hiçbir şey söylemez. */
.tier{{display:inline-flex;align-items:center;height:18px;padding:0 5px;
  border:1px solid var(--color-border);border-radius:4px;
  font-family:var(--font-mono);font-size:11px;color:var(--color-fg-subtle);
  flex:none}}

.count{{display:inline-flex;align-items:center;justify-content:center;
  min-width:20px;height:18px;padding:0 6px;border-radius:var(--radius-sm);
  background:var(--color-surface-sunken);color:var(--color-fg-muted);
  font-size:var(--text-xs);font-weight:var(--weight-medium)}}
.count.attention{{background:var(--color-contra-subtle);color:var(--color-contra)}}

/* ─── SIGNATURE: kanıt cetveli ─── */
.ruled{{position:relative;padding-left:var(--space-4)}}
.ruled::before{{
  content:"";position:absolute;left:0;top:2px;bottom:2px;width:3px;
  border-radius:var(--radius-full);background:var(--color-border-strong);
}}
.ruled.strong::before{{background:var(--color-strong)}}
.ruled.accent::before{{background:var(--color-accent)}}
.ruled.partial::before{{background:var(--color-partial)}}
.ruled.single::before{{background:var(--color-single)}}
.ruled.contra::before{{background:var(--color-contra)}}
/* Doğrulanmamış: kesikli cetvel — renk değil DESEN ayırır (renk körlüğü). */
.ruled.unverified::before{{
  background:repeating-linear-gradient(var(--color-border-strong) 0 3px,
    transparent 3px 6px);
}}
/* İddia metninin kontrastı kanıt gücüyle birlikte düşer. */
.ruled.unverified>.claim-text,.ruled.single>.claim-text{{color:var(--color-fg-muted)}}

/* ─── buton · Bölüm 8.5 ───
   Sayfada TEK primary buton olur. Uppercase YOK. */
.btn{{
  display:inline-flex;align-items:center;justify-content:center;gap:6px;
  height:var(--control-h);padding:0 14px;border-radius:var(--radius-md);
  border:1px solid var(--color-border-strong);background:var(--color-surface);
  color:var(--color-fg);font:inherit;font-size:var(--text-base);
  font-weight:var(--weight-medium);cursor:pointer;text-decoration:none;
  white-space:nowrap;min-width:max-content;
  transition:background var(--dur-hover) var(--ease-out),
             border-color var(--dur-hover) var(--ease-out);
}}
.btn:hover:not(:disabled){{background:var(--color-surface-sunken)}}
.btn:active:not(:disabled){{transition-duration:var(--dur-press)}}
.btn.primary{{background:var(--color-accent);border-color:var(--color-accent);
  color:var(--color-fg-on-accent)}}
.btn.primary:hover:not(:disabled){{background:var(--color-accent-hover);
  border-color:var(--color-accent-hover)}}
.btn.ghost{{background:transparent;border-color:transparent;
  color:var(--color-fg-muted)}}
.btn.ghost:hover:not(:disabled){{background:var(--color-surface-sunken);
  color:var(--color-fg)}}
.btn.danger{{background:var(--color-contra);border-color:var(--color-contra);
  color:var(--color-fg-on-accent)}}
.btn.sm{{height:32px;padding:0 10px;font-size:var(--text-sm)}}
.btn.icon{{width:var(--control-h);padding:0;flex:none}}
.btn.icon.sm{{width:32px}}
/* Devre dışı: yalnız opaklık — RENK DEĞİŞTİRME (Bölüm 8.5). */
.btn:disabled{{opacity:.45;cursor:not-allowed}}
.btn-row{{display:flex;gap:var(--space-2);flex-wrap:wrap;align-items:center}}

/* ─── segment kontrolü · Bölüm 8.11 ─── */
/* 375px'te segment şeridi gövdeyi taşırıyordu (DoD: "yatay kaydırma yok").
   Şeridin KENDİSİ kaydırılır; sayfa kaydırılmaz. */
.segment{{display:flex;gap:2px;padding:3px;border-radius:var(--radius-md);
  background:var(--color-surface-sunken);max-width:100%;overflow-x:auto;
  scrollbar-width:none}}
.segment::-webkit-scrollbar{{display:none}}
/* Faz 7: filtre sekmeleri hiçbir yere gitmeyen sözde-URL taşıyan anchor'lardı.
   O şema CSP'nin script-src'si tarafından reddedilir; üstelik tıklamadan
   başka bir yere GİTMEYEN bir bağlantı yanlış semantikti (ekran okuyucu
   "bağlantı" diyordu, Enter/Space davranışı da anchor'ınkiydi). Artık
   `<button type="button">`. Görünüm birebir korunsun diye tüm kurallar
   ikisini de hedefler; buton varsayılanları (arka plan, kenarlık, yazı tipi)
   ayrıca sıfırlanır. */
.segment a,.segment button{{flex:none}}
.segment a,.segment button{{display:inline-flex;align-items:center;height:26px;padding:0 12px;
  border-radius:var(--radius-sm);font-size:var(--text-sm);
  color:var(--color-fg-muted);text-decoration:none;
  background:none;border:0;margin:0;cursor:pointer;
  font-family:inherit;line-height:1;white-space:nowrap;
  transition:background var(--dur-hover) var(--ease-out)}}
.segment a:hover,.segment button:hover{{color:var(--color-fg)}}
.segment a[aria-current],.segment button[aria-current]{{background:var(--color-surface);color:var(--color-fg);
  font-weight:var(--weight-medium);box-shadow:var(--shadow-sm)}}

/* ─── filtre çipi · Bölüm 8.10 ─── */
.chip{{display:inline-flex;align-items:center;gap:6px;height:32px;padding:0 10px;
  border:1px solid var(--color-border);border-radius:var(--radius-md);
  background:var(--color-surface);color:var(--color-fg-muted);
  font-size:var(--text-sm);text-decoration:none;
  transition:border-color var(--dur-hover) var(--ease-out)}}
.chip:hover{{border-color:var(--color-border-strong);color:var(--color-fg)}}
/* Aktif filtre görsel olarak AYRIŞIR — yoksa kullanıcı boş sonucu hata sanar. */
.chip[aria-pressed="true"]{{border-color:var(--color-accent);
  background:var(--color-accent-subtle);color:var(--color-accent);
  font-weight:var(--weight-medium)}}

/* ─── tablo · Bölüm 8.3 ───
   Zebra şerit YOK. Dikey ızgara YOK. Sayısal sütun sağa hizalı. */
.table-wrap{{overflow-x:auto;overscroll-behavior-x:contain}}
table{{width:100%;border-collapse:collapse;font-size:var(--text-sm)}}
thead th{{
  position:sticky;top:0;z-index:1;background:var(--color-surface-sunken);
  text-align:left;font-size:var(--text-xs);letter-spacing:.04em;
  font-weight:var(--weight-medium);color:var(--color-fg-subtle);
  padding:10px 12px;border-bottom:1px solid var(--color-border);
  white-space:nowrap;
}}
tbody td{{padding:12px;border-bottom:1px solid var(--color-border);
  vertical-align:top}}
tbody tr:last-child td{{border-bottom:0}}

/* Dokunma hedefi — WCAG 2.5.8 (AA) asgari 24x24 CSS px.
   Ölçüldü (20 Ağu 2026, Lighthouse `target-size`): denetim kuyruğunda 100,
   vaatler ekranında 8 bağlantı eşiğin altındaydı. Tablo hücresindeki olay
   kimliği (`a.mono`) ve aktör bağlantıları küçük punto olduğu için satır
   yüksekliği kadar tıklama alanı üretmiyordu — fare ile zor, dokunmatikte
   isabetsiz. Yükseklik hücre dolgusunu değiştirmeden büyütülür: satır
   ritmi bozulmaz, yalnızca tıklanabilir alan büyür. */
tbody td a{{
  display:inline-flex;align-items:center;
  min-height:24px;
}}
tbody tr{{transition:background 100ms var(--ease-out)}}
tbody tr:hover{{background:var(--color-surface-sunken)}}
th.num,td.num{{text-align:right;font-variant-numeric:tabular-nums}}
td .cell-sub{{margin-top:2px;font-size:var(--text-xs);color:var(--color-fg-subtle)}}

/* ─── açılır panel (details) ─── */
details.panel{{border:1px solid var(--color-border);border-radius:var(--radius-md);
  background:var(--color-surface);overflow:hidden}}
details.panel+details.panel{{margin-top:var(--space-2)}}
details.panel>summary{{
  display:flex;align-items:center;gap:var(--space-2);padding:10px 12px;
  cursor:pointer;list-style:none;font-size:var(--text-sm);
  transition:background var(--dur-hover) var(--ease-out);
}}
details.panel>summary::-webkit-details-marker{{display:none}}
details.panel>summary:hover{{background:var(--color-surface-sunken)}}
details.panel>summary .chev{{margin-left:auto;flex:none;
  color:var(--color-fg-subtle);
  transition:transform var(--dur-pop) var(--ease-spring)}}
details.panel[open]>summary .chev{{transform:rotate(90deg)}}
details.panel[open]>summary{{border-bottom:1px solid var(--color-border)}}
/* Sessiz varyant: kart içindeki İKİNCİL açılır panel. Kenarlığı ve zemini
   yok — yanındaki durum rozetiyle aynı görsel ağırlıkta durmamalı. Bir
   açılır panel bir eylem değil, bir dipnottur. */
details.panel.quiet{{border:0;background:transparent}}
details.panel.quiet>summary{{padding:0;color:var(--color-fg-muted);
  font-size:var(--text-xs)}}
details.panel.quiet>summary:hover{{background:transparent;color:var(--color-fg)}}
details.panel.quiet[open]>summary{{border-bottom:0;margin-bottom:var(--space-3)}}
details.panel.quiet .panel-body{{padding:0 0 0 var(--space-3);
  border-left:1px solid var(--color-border)}}
.panel-body{{padding:12px}}

/* ─── uyarı bloğu ─── */
.notice{{display:flex;gap:10px;padding:12px 14px;border-radius:var(--radius-md);
  background:var(--color-surface-sunken);font-size:var(--text-sm);
  border-left:3px solid var(--color-border-strong)}}
.notice .ic{{flex:none;margin-top:2px;color:var(--color-fg-subtle)}}
.notice.warn{{background:var(--color-partial-subtle);
  border-left-color:var(--color-partial)}}
.notice.warn .ic{{color:var(--color-partial)}}
.notice.bad{{background:var(--color-contra-subtle);
  border-left-color:var(--color-contra)}}
.notice.bad .ic{{color:var(--color-contra)}}
.notice.ok{{background:var(--color-strong-subtle);
  border-left-color:var(--color-strong)}}
.notice.ok .ic{{color:var(--color-strong)}}
.notice p{{margin:0}}
.notice p+p{{margin-top:6px}}

/* ─── form · Bölüm 8.6 ─── */
.field{{display:flex;flex-direction:column;gap:6px;max-width:480px}}
.field>label,.label{{font-size:var(--text-sm);
  font-weight:var(--weight-medium);color:var(--color-fg)}}
.field .hint{{font-size:var(--text-xs);color:var(--color-fg-subtle)}}
input[type=text],input[type=number],input[type=search],select,textarea{{
  width:100%;font:inherit;font-size:var(--text-base);
  padding:0 10px;height:var(--control-h);
  border:1px solid var(--color-border-strong);border-radius:var(--radius-md);
  background:var(--color-surface);color:var(--color-fg);
  transition:border-color var(--dur-hover) var(--ease-out),
             box-shadow var(--dur-hover) var(--ease-out);
}}
textarea{{height:auto;min-height:180px;padding:12px;line-height:1.6;resize:vertical}}
input:focus,select:focus,textarea:focus{{
  outline:none;border-color:var(--color-accent);
  box-shadow:0 0 0 3px var(--color-accent-subtle);
}}
input::placeholder,textarea::placeholder{{color:var(--color-fg-subtle)}}
input:disabled,textarea:disabled,select:disabled{{opacity:.55;
  cursor:not-allowed;background:var(--color-surface-sunken)}}
fieldset{{border:1px solid var(--color-border);border-radius:var(--radius-lg);
  margin:0;padding:var(--card-pad);background:var(--color-surface)}}
legend{{padding:0 6px;font-size:var(--text-base);
  font-weight:var(--weight-medium)}}
.opt{{display:flex;align-items:center;gap:var(--space-2);padding:6px 0;
  font-size:var(--text-base);cursor:pointer}}
.opt.inline{{display:inline-flex;margin-right:var(--space-4)}}
input[type=checkbox],input[type=radio]{{
  width:16px;height:16px;margin:0;flex:none;accent-color:var(--color-accent);
  cursor:pointer;
}}

/* ─── zaman çizelgesi · Bölüm 8.15 ─── */
.timeline{{list-style:none;margin:0;padding:0}}
.timeline li{{position:relative;padding:0 0 var(--space-4) var(--space-6);
  border-left:1px solid var(--color-border);margin-left:4px}}
.timeline li:last-child{{padding-bottom:0;border-left-color:transparent}}
.timeline li::before{{content:"";position:absolute;left:-4px;top:6px;
  width:7px;height:7px;border-radius:var(--radius-full);
  background:var(--color-surface);border:1.5px solid var(--color-border-strong)}}
.timeline .when{{font-size:var(--text-xs);color:var(--color-fg-subtle);
  font-family:var(--font-mono)}}

/* ─── sıralı dağılım listesi · Bölüm 8.12 ─── */
.dist{{display:flex;flex-direction:column;gap:var(--space-3)}}
.dist-row{{display:grid;grid-template-columns:minmax(0,35%) 1fr auto;
  align-items:center;gap:var(--space-3);font-size:var(--text-sm)}}
.dist-row .name{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  color:var(--color-fg-muted)}}
.track{{height:6px;border-radius:3px;background:var(--color-surface-sunken);
  overflow:hidden}}
.track>span{{display:block;height:100%;border-radius:3px;
  background:var(--color-chart-1)}}
.dist-row .val{{font-variant-numeric:tabular-nums;
  font-weight:var(--weight-medium)}}

/* ═══════════════════════════════════════════ durumlar · Bölüm 10 */
.empty{{
  display:flex;flex-direction:column;align-items:center;text-align:center;
  gap:var(--space-3);padding:var(--space-12) var(--space-6);
}}
.empty .ic{{color:var(--color-fg-subtle)}}
.empty h3{{font-weight:var(--weight-medium)}}
.empty p{{margin:0;max-width:44ch;color:var(--color-fg-muted);
  font-size:var(--text-sm)}}

/* Skeleton: shimmer DEĞİL — opaklık nabzı (Bölüm 10.3). */
.skeleton{{background:var(--color-surface-sunken);border-radius:var(--radius-sm);
  animation:pulse 1.5s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.55}}}}

/* ═══════════════════════════════════════════════════ grafik */
/* Genişlik İÇERİKTEN gelir, konteynerden değil: 2 günlük veri 2 çubuk
   kadar yer kaplar. `width:100%` verilseydi SVG kapsayıcıya gerilir ve
   viewBox ortalanarak grafiği kartın ortasına iterdi — "az veri var"
   bilgisi kaybolurdu. */
.chart{{display:block;max-width:100%;overflow:visible}}
.chart .grid{{stroke:var(--color-border);stroke-width:1;opacity:.6}}
.chart .axis{{fill:var(--color-fg-subtle);font-size:11px;
  font-family:var(--font-mono)}}
.chart .line{{fill:none;stroke:var(--color-chart-1);stroke-width:2;
  stroke-linecap:round;stroke-linejoin:round}}
.chart .area{{fill:url(#pd-area)}}
.chart .bar{{fill:var(--color-chart-1)}}
.chart .bar-track{{fill:var(--color-surface-sunken)}}
.spark{{display:block}}

/* ═══════════════════════════════════════════ responsive · 7.4 */
@media (max-width:1279px){{
  :root{{--sidebar-w:var(--sidebar-collapsed-w);
        --content-pad-x:var(--content-pad-x-dense)}}
  .side-head{{padding:var(--space-4) 10px}}
  .brand-text,.nav-item span,.nav-group>.eyebrow,.side-foot .who{{display:none}}
  .nav-item{{justify-content:center;padding:0}}
  .side-nav{{padding-inline:10px}}
  .split{{grid-template-columns:minmax(0,1fr)}}
}}
@media (max-width:767px){{
  .app{{grid-template-columns:minmax(0,1fr)}}
  /* Sidebar → yatay şerit. Mobilde dikey ray ekranın yarısını yer. */
  .side{{position:static;height:auto;flex-direction:row;align-items:center;
    border-right:0;border-bottom:1px solid var(--color-border);
    padding-right:var(--space-2);gap:var(--space-2)}}
  .side-head{{padding:10px var(--space-3)}}
  .side-nav{{flex-direction:row;overflow-x:auto;padding:10px 0;gap:var(--space-2);
    scrollbar-width:none}}
  .side-nav::-webkit-scrollbar{{display:none}}
  .nav-group{{flex-direction:row;gap:2px}}
  .side-foot{{border-top:0;padding:0 var(--space-2);flex:none}}
  .halves{{grid-template-columns:minmax(0,1fr)}}
  .page-head{{flex-direction:column;gap:var(--space-3)}}
  .page-head .actions{{margin-left:0;width:100%}}
  .content{{padding:var(--space-4) var(--space-4) var(--space-12)}}
  .topbar{{padding-inline:var(--space-4)}}
  /* Bölüm 7.4: tablo mobilde yatay kaydırmaya BIRAKILMAZ, karta döner. */
  .table-cards thead{{display:none}}
  .table-cards tbody tr{{display:block;padding:var(--space-3) 0;
    border-bottom:1px solid var(--color-border)}}
  .table-cards tbody td{{display:flex;gap:var(--space-3);padding:3px 0;
    border:0}}
  .table-cards tbody td::before{{content:attr(data-label);flex:none;
    width:38%;color:var(--color-fg-subtle);font-size:var(--text-xs)}}
}}

/* ═══════════════════════════════════════════════ ek bileşenler */
.search-wrap{{position:relative;display:flex;align-items:center;width:100%;max-width:360px}}
.search-wrap .ic{{position:absolute;left:10px;color:var(--color-fg-subtle);pointer-events:none}}
.search-wrap input{{padding-left:34px;height:34px;font-size:var(--text-sm)}}

.pulse-dot{{width:8px;height:8px;border-radius:var(--radius-full);background:var(--color-strong);
  display:inline-block;animation:pulse-glow 2s cubic-bezier(.4,0,.6,1) infinite}}
@keyframes pulse-glow{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.4;transform:scale(.85)}}}}
/* Canlı akıştan yeni kayıt geldiğinde. Renk JS'ten satır içi stille
   veriliyordu; token almıyordu ve koyu temada yanlış tona düşüyordu. */
.pulse-dot.flash{{background:var(--color-accent)}}

/* ── Kumanda odası sinyal satırı (Faz 8.1) ──────────────────────────
   Sapma, kaynak ve beklenen yayın panelleri aynı ritmi paylaşır: bir
   satır = bir sinyal. Ayırıcı olarak alt kenarlık; zebra şerit yasak
   (Bölüm 8.3). Son satırın kenarlığı yok — kart zaten orada bitiyor ve
   çift çizgi görüntüsü oluşurdu. */
.signal-row{{padding:var(--space-2) 0;border-bottom:1px solid var(--color-border)}}
.signal-row:last-of-type{{border-bottom:0;padding-bottom:0}}
/* Satır başlığı: ad esner, rozet esnemez. `.row`'un `flex-wrap` değeri
   uzun kaynak adlarında ("Anayasa Mahkemesi (@AYMBASKANLIGI)") rozeti
   alt satıra atıyor ve sinyal listesinin ritmi bozuluyordu. */
.signal-row .row{{flex-wrap:nowrap}}
.signal-row .row>:first-child{{min-width:0;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}}
.signal-row .row>:last-child{{flex:none}}

/* Gösterge şeridi — ızgara DEĞİL esnek satır.
   `grid` + `auto-fit` ile 6 kart 4 sütuna dizilince ikinci satırda 2 kart
   kalıyor ve sağda bir kart genişliğinde ölü alan oluşuyordu. Flex'te son
   satırdaki kartlar `flex-grow` ile satırı doldurur; seri sayısının sütun
   sayısına bölünmesi gerekmez ve kurum yeni bir seri yayımladığında
   yerleşim bozulmaz. */
.indicator-strip{{display:flex;flex-wrap:wrap;gap:var(--space-3)}}
/* Taban 280px: altı seri 1440'ta 3+3, 1920'de 4+2, tablette 2+2+2 diziliyor.
   220px'te 1920 ekranda 5+1 oluyordu ve tek başına kalan kart satırın
   tamamına yayılıp diğerlerinin iki katı genişliğe çıkıyordu — aynı
   ölçekteki altı göstergeden biri, sırf sona düştüğü için daha önemli
   görünüyordu. */
.indicator-strip>*{{flex:1 1 280px;min-width:0}}

/* "Olmayanlar" — ekranın imza öğesi. Diğer kartlardan AYRIŞMASI gerekir
   çünkü tek "yokluk" panelidir; ayrım gölgeyle değil (Bölüm 5.5) sol
   kenardaki cetvelle yapılır — arayüzün kanıt cetveliyle aynı dil. */
.card.absent{{border-left:3px solid var(--color-partial)}}
.card.absent .card-head h3,
.card.absent .card-head .h3{{color:var(--color-fg)}}

/* Sütun sayısını çağıran belirler (`grid-template-columns` satır içinde).
   Bu kural EKSİKTİ: `class="grid"` iki ekranda kullanılıyordu ama
   hiçbir yerde `display:grid` yoktu, dolayısıyla satır içi
   `grid-template-columns` HİÇBİR ŞEY yapmıyordu. Kumanda odasının altı
   gösterge kartı ve olay sayfasının kanıt ızgarası tam genişlikte alt
   alta yığılıyordu — ekran görüntüsünde "öyle tasarlanmış" gibi
   duran, ancak ölçünce görülen türden bir kusur. */
.grid{{display:grid;gap:var(--space-4)}}
.grid-auto{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:var(--space-4)}}

.toast{{
  position:fixed;bottom:var(--space-6);right:var(--space-6);z-index:999;
  padding:var(--space-3) var(--space-4);background:var(--color-fg);color:var(--color-bg);
  border-radius:var(--radius-md);box-shadow:var(--shadow-lg);
  font-size:var(--text-sm);font-weight:var(--weight-medium);
  display:flex;align-items:center;gap:var(--space-2);
  opacity:0;transform:translateY(12px);transition:all var(--dur-pop) var(--ease-spring);
  pointer-events:none;
}}
.toast.show{{opacity:1;transform:translateY(0);pointer-events:auto}}

.diff-del{{background:var(--color-contra-subtle);color:var(--color-contra);text-decoration:line-through;padding:1px 4px;border-radius:2px}}
.diff-ins{{background:var(--color-strong-subtle);color:var(--color-strong);padding:1px 4px;border-radius:2px}}

/* ═══════════════════════════════════ feed tweet & power UI */
.feed-card{{transition:border-color var(--dur-hover) var(--ease-out),box-shadow var(--dur-hover) var(--ease-out)}}
.feed-card.is-selected{{outline:2px solid var(--color-accent);box-shadow:var(--shadow-md)}}

.feed-tweet-box{{
  background:var(--color-surface-sunken);
  border:1px solid var(--color-border);
  border-radius:var(--radius-md);
  padding:var(--space-3) var(--space-4);
  margin-top:var(--space-3);
  transition:all var(--dur-hover) var(--ease-out);
}}
.feed-tweet-box:focus-within{{
  border-color:var(--color-accent);
}}
.feed-tweet-textarea{{
  width:100%;min-height:68px;resize:vertical;font-size:var(--text-sm);
  background:transparent;border:0;padding:0;outline:none;
  color:var(--color-fg);font-family:var(--font-body);line-height:1.55;
}}

/* Kompakt Liste Görünümü */
.feed-compact .feed-card{{padding:var(--space-2) var(--space-3)}}
.feed-compact .feed-card .claim-text{{display:none}}
.feed-compact .feed-card details.quiet{{display:none}}
/* Kart başlığı `h2.h3`tir (semantik seviye ile görsel boyut ayrı —
   bkz. feed.py). Seçici her ikisini de tutar ki sıkışık kip bozulmasın. */
.feed-compact .feed-main h3,
.feed-compact .feed-main .h3{{margin:2px 0 4px;font-size:var(--text-base)}}

/* Kısayol Modalı */
.shortcuts-backdrop{{
  position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:1000;
  display:none;align-items:center;justify-content:center;padding:var(--space-4);
  backdrop-filter:blur(2px);
}}
.shortcuts-backdrop.open{{display:flex}}
.shortcuts-modal{{
  background:var(--color-surface);border:1px solid var(--color-border);
  border-radius:var(--radius-lg);padding:var(--space-6);max-width:480px;width:100%;
  box-shadow:var(--shadow-lg);
}}
.shortcut-row{{display:flex;justify-content:space-between;align-items:center;padding:var(--space-2) 0;border-bottom:1px solid var(--color-border)}}
.shortcut-key{{background:var(--color-surface-sunken);border:1px solid var(--color-border);border-radius:var(--radius-sm);padding:2px 6px;font-family:var(--font-mono);font-size:var(--text-xs);font-weight:var(--weight-semibold)}}

/* ═══════════════════════════════════ komuta paleti (cmd+k) */
.cmd-backdrop{{
  position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:2000;
  display:none;align-items:flex-start;justify-content:center;padding:var(--space-12) var(--space-4);
  backdrop-filter:blur(3px);
}}
.cmd-backdrop.open{{display:flex}}
.cmd-box{{
  background:var(--color-surface);border:1px solid var(--color-border-strong);
  border-radius:var(--radius-lg);max-width:560px;width:100%;
  box-shadow:var(--shadow-lg);overflow:hidden;display:flex;flex-direction:column;
  animation:cmdFadeIn var(--dur-pop) var(--ease-spring);
}}
@keyframes cmdFadeIn{{
  from{{opacity:0;transform:scale(0.97) translateY(-8px)}}
  to{{opacity:1;transform:scale(1) translateY(0)}}
}}
.cmd-header{{
  display:flex;align-items:center;padding:var(--space-3) var(--space-4);
  border-bottom:1px solid var(--color-border);gap:var(--space-2);
}}
.cmd-header .ic{{color:var(--color-fg-subtle);flex:none}}
.cmd-input{{
  flex:1;background:transparent;border:0;outline:none;font-size:var(--text-base);
  color:var(--color-fg);font-family:var(--font-body);
}}
.cmd-body{{
  max-height:360px;overflow-y:auto;padding:var(--space-2);display:flex;flex-direction:column;gap:2px;
}}
.cmd-group-label{{
  font-size:var(--text-xs);font-weight:var(--weight-semibold);color:var(--color-fg-subtle);
  padding:var(--space-2) var(--space-3) var(--space-1);
}}
.cmd-item{{
  display:flex;align-items:center;justify-content:space-between;padding:var(--space-2) var(--space-3);
  border-radius:var(--radius-md);color:var(--color-fg);text-decoration:none;
  font-size:var(--text-sm);cursor:pointer;transition:background var(--dur-hover) var(--ease-out);
}}
.cmd-item:hover,.cmd-item.selected{{
  background:var(--color-surface-sunken);color:var(--color-accent);
}}
.cmd-item-left{{display:flex;align-items:center;gap:var(--space-2);min-width:0}}
/* Uzun iddia metni paleti yatay olarak patlatmasın: başlık kısalır,
   alt bilgi kısalmaz (asıl ayırt edici odur). */
.cmd-item-left span{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.cmd-item-hint{{
  font-size:var(--text-xs);color:var(--color-fg-subtle);
  flex:none;margin-left:var(--space-3);max-width:45%;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}}
.cmd-empty{{
  padding:var(--space-6) var(--space-4);text-align:center;
  color:var(--color-fg-subtle);font-size:var(--text-sm);
}}
.cmd-footer{{
  display:flex;align-items:center;justify-content:space-between;padding:var(--space-2) var(--space-4);
  border-top:1px solid var(--color-border);background:var(--color-surface-sunken);
  font-size:var(--text-xs);color:var(--color-fg-subtle);
}}

/* ═══════════════════════════════════ bilgi grafı (knowledge graph) */
.knowledge-graph{{transition:all var(--dur-hover) var(--ease-out)}}
.graph-node{{cursor:pointer;transition:transform var(--dur-hover) var(--ease-spring)}}
.graph-node:hover{{transform:scale(1.12)}}
.graph-node circle{{transition:stroke var(--dur-hover) var(--ease-out),filter var(--dur-hover) var(--ease-out)}}
.graph-node:hover circle{{stroke:var(--color-accent);filter:drop-shadow(0 2px 6px rgba(0,0,0,0.15))}}
.graph-links line{{transition:stroke var(--dur-hover) var(--ease-out),stroke-width var(--dur-hover) var(--ease-out)}}
.graph-links line:hover{{stroke:var(--color-accent);stroke-width:2.5;opacity:1}}

/* ═══════════════════════════════════ mobil uyum & duyarlı kartlar */
.mobile-menu-btn{{display:none}}
.side-backdrop{{display:none}}
.responsive-table{{display:block;width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}}
.indicator-card{{transition:border-color var(--dur-hover) var(--ease-out),box-shadow var(--dur-hover) var(--ease-out)}}
.indicator-card:hover{{border-color:var(--color-accent);box-shadow:var(--shadow-sm)}}

@media (max-width:768px){{
  .app{{display:block}}
  .side{{
    position:fixed;left:0;top:0;bottom:0;width:260px;z-index:1500;
    transform:translateX(-100%);transition:transform var(--dur-pop) var(--ease-out);
    box-shadow:none;background:var(--color-surface);
  }}
  .side.open{{transform:translateX(0);box-shadow:var(--shadow-lg)}}
  .side-backdrop{{
    position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:1400;
    opacity:0;pointer-events:none;transition:opacity var(--dur-pop) var(--ease-out);
    backdrop-filter:blur(2px);display:block;
  }}
  .side-backdrop.open{{opacity:1;pointer-events:auto}}
  .mobile-menu-btn{{display:inline-flex !important;margin-right:var(--space-2)}}
  .topbar{{padding:0 var(--space-3)}}
}}

@media (max-width:640px){{
  .content{{padding:var(--space-3) var(--space-2) !important}}
  .grid{{grid-template-columns:1fr !important;gap:var(--space-3) !important}}
  .btn{{min-height:44px;min-width:44px}}
  .btn.sm{{min-height:38px}}
  .table-cards thead{{display:none}}
  .table-cards tbody{{display:flex;flex-direction:column;gap:var(--space-3)}}
  .table-cards tr{{
    display:flex;flex-direction:column;background:var(--color-surface);
    border:1px solid var(--color-border);border-radius:var(--radius-md);
    padding:var(--space-3);gap:var(--space-2);
  }}
  .table-cards td{{padding:0 !important;border:0 !important}}
}}

/* ═══════════════════════════════════ GÜNDEM V3 — PRODUCTION UX & EDITORIAL INTELLIGENCE */
.feed-toolbar{{
  display:flex;flex-direction:column;gap:var(--space-3);margin-bottom:var(--space-4);
  background:var(--color-surface);border:1px solid var(--color-border);
  border-radius:var(--radius-lg);padding:var(--space-4);
}}
.feed-toolbar-row{{
  display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);flex-wrap:wrap;
}}
.feed-sort-group{{
  display:inline-flex;background:var(--color-surface-sunken);border:1px solid var(--color-border);
  border-radius:var(--radius-md);padding:2px;gap:2px;
}}
.feed-sort-btn{{
  display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:var(--radius-sm);
  border:0;background:transparent;color:var(--color-fg-muted);font-family:var(--font-body);
  font-size:var(--text-xs);font-weight:var(--weight-medium);cursor:pointer;
  transition:all var(--dur-hover) var(--ease-out);text-decoration:none;
}}
.feed-sort-btn:hover{{
  color:var(--color-fg);background:var(--color-surface);
}}
.feed-sort-btn[aria-current="true"]{{
  background:var(--color-surface);color:var(--color-accent);
  font-weight:var(--weight-semibold);box-shadow:var(--shadow-sm);
}}
.feed-mode-tagline{{
  display:flex;align-items:center;gap:6px;font-size:var(--text-xs);
  color:var(--color-fg-subtle);background:var(--color-surface-sunken);
  padding:4px 10px;border-radius:var(--radius-sm);border-left:3px solid var(--color-accent);
}}
.feed-discovery-bar{{
  display:flex;flex-direction:column;gap:var(--space-2);width:100%;
  border-top:1px solid var(--color-border);padding-top:var(--space-3);
}}
.feed-discovery-section{{
  display:flex;align-items:center;gap:var(--space-2);width:100%;
}}
.feed-discovery-label{{
  font-size:var(--text-xs);font-weight:var(--weight-semibold);
  color:var(--color-fg-subtle);letter-spacing:0.5px;
  min-width:74px;flex-shrink:0;display:flex;align-items:center;gap:4px;
}}
.feed-chip-group{{
  display:flex;align-items:center;gap:6px;overflow-x:auto;
  scrollbar-width:none;-webkit-overflow-scrolling:touch;padding:2px 0;width:100%;
}}
.feed-chip-group::-webkit-scrollbar{{
  display:none;
}}
.feed-chip{{
  display:inline-flex;align-items:center;gap:4px;padding:3px 9px;
  border-radius:var(--radius-full);border:1px solid var(--color-border);
  background:var(--color-surface-sunken);color:var(--color-fg-muted);
  font-family:var(--font-body);font-size:11px;font-weight:var(--weight-medium);
  white-space:nowrap;cursor:pointer;text-decoration:none;flex-shrink:0;
  transition:all var(--dur-hover) var(--ease-out);
}}
.feed-chip:hover{{
  color:var(--color-fg);background:var(--color-surface);border-color:var(--color-border-strong);
}}
.feed-chip[aria-current="true"], .feed-chip.active{{
  background:var(--color-accent);color:var(--color-fg-on-accent);
  border-color:var(--color-accent);font-weight:var(--weight-semibold);
  box-shadow:var(--shadow-sm);
}}
.feed-active-tray{{
  display:flex;align-items:center;gap:var(--space-2);flex-wrap:wrap;
  background:var(--color-surface-sunken);border:1px solid var(--color-border);
  border-radius:var(--radius-md);padding:6px 12px;margin-bottom:var(--space-3);
}}
.feed-active-tray-label{{
  font-size:var(--text-xs);font-weight:var(--weight-semibold);
  color:var(--color-fg-subtle);display:inline-flex;align-items:center;gap:4px;
}}
.feed-active-pill{{
  display:inline-flex;align-items:center;gap:6px;padding:2px 8px;
  background:var(--color-surface);border:1px solid var(--color-border-strong);
  border-radius:var(--radius-full);font-size:11px;color:var(--color-fg);
  font-weight:var(--weight-medium);box-shadow:var(--shadow-xs);
}}
.feed-active-pill-remove{{
  display:inline-flex;align-items:center;justify-content:center;
  background:transparent;border:0;padding:0;color:var(--color-fg-subtle);
  cursor:pointer;border-radius:50%;width:14px;height:14px;
  transition:color var(--dur-hover) var(--ease-out);
}}
.feed-active-pill-remove:hover{{
  color:var(--color-contra);
}}
.feed-filter-bar{{
  display:flex;align-items:center;gap:var(--space-2);flex-wrap:wrap;
}}
.feed-select{{
  background:var(--color-surface);border:1px solid var(--color-border-strong);
  border-radius:var(--radius-md);padding:5px 9px;font-family:var(--font-body);
  font-size:var(--text-xs);color:var(--color-fg);outline:none;cursor:pointer;
  transition:border-color var(--dur-hover) var(--ease-out);
}}
.feed-select:focus{{
  border-color:var(--color-accent);box-shadow:0 0 0 2px var(--color-accent-subtle);
}}
.feed-new-banner{{
  display:none;align-items:center;justify-content:center;gap:var(--space-2);
  background:var(--color-accent);color:var(--color-fg-on-accent);
  padding:var(--space-2) var(--space-4);border-radius:var(--radius-md);
  font-size:var(--text-xs);font-weight:var(--weight-semibold);cursor:pointer;
  box-shadow:var(--shadow-md);animation:bannerSlideDown var(--dur-pop) var(--ease-spring);
  margin-bottom:var(--space-3);text-align:center;border:0;width:100%;
}}
@keyframes bannerSlideDown{{
  from{{opacity:0;transform:translateY(-8px)}}
  to{{opacity:1;transform:translateY(0)}}
}}
.feed-new-banner:hover{{
  background:var(--color-accent-hover);
}}
.card-new-highlight{{
  animation:newCardPulse 1.8s var(--ease-out);
}}
@keyframes newCardPulse{{
  0%{{box-shadow:0 0 0 2px var(--color-accent), var(--shadow-md);transform:translateY(-2px)}}
  50%{{box-shadow:0 0 0 1px var(--color-accent-subtle), var(--shadow-sm);transform:translateY(0)}}
  100%{{box-shadow:none;transform:none}}
}}
.badge-new{{
  background:var(--color-strong);color:var(--color-fg-on-accent);
  font-size:10px;font-weight:var(--weight-bold);padding:1px 6px;
  border-radius:var(--radius-sm);letter-spacing:0.5px;
}}
.badge-category{{
  background:var(--color-surface-sunken);border:1px solid var(--color-border);
  color:var(--color-fg-muted);font-size:11px;font-weight:var(--weight-medium);
  padding:1px 6px;border-radius:var(--radius-sm);
}}
.badge-region{{
  background:var(--color-accent-subtle);color:var(--color-accent);
  font-size:11px;font-weight:var(--weight-semibold);padding:1px 6px;
  border-radius:var(--radius-sm);
}}

/* ═══════════════════════════════════ hareket · Bölüm 11.4 */
@media (prefers-reduced-motion:reduce){{
  *,*::before,*::after{{
    animation-duration:.01ms !important;animation-iteration-count:1 !important;
    transition-duration:.01ms !important;scroll-behavior:auto !important;
  }}
}}
@media print{{
  .side,.topbar,.btn,.actions,.search-wrap,#pd-theme{{display:none !important}}
  .app{{display:block !important}}
  .main{{display:block !important}}
  .content{{padding:0 !important;max-width:none !important}}
  .card{{border:1px solid var(--color-border) !important;box-shadow:none !important}}
}}
"""

    )
