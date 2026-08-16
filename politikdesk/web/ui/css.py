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
.card-head h3{{min-width:0}}
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
.segment a{{flex:none}}
.segment a{{display:inline-flex;align-items:center;height:26px;padding:0 12px;
  border-radius:var(--radius-sm);font-size:var(--text-sm);
  color:var(--color-fg-muted);text-decoration:none;
  transition:background var(--dur-hover) var(--ease-out)}}
.segment a:hover{{color:var(--color-fg)}}
.segment a[aria-current]{{background:var(--color-surface);color:var(--color-fg);
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

/* ═══════════════════════════════════ hareket · Bölüm 11.4 */
@media (prefers-reduced-motion:reduce){{
  *,*::before,*::after{{
    animation-duration:.01ms !important;animation-iteration-count:1 !important;
    transition-duration:.01ms !important;scroll-behavior:auto !important;
  }}
}}
@media print{{
  .side,.topbar,.btn,.actions{{display:none}}
  .content{{padding:0;max-width:none}}
}}
"""
    )
