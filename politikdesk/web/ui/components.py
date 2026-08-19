"""Bileşen kitaplığı — DESIGN.md Bölüm 8 spesifikasyonlarının kodu.

Bu depoda React/shadcn yok (Ek A); Bölüm 8'in her spesifikasyonu burada bir
fonksiyondur. Kural: **bir bileşen iki yerde ayrı yazılmaz.** Bir ekranda
"neredeyse aynı" bir parça gerekiyorsa buraya parametre eklenir, oraya kopya
yazılmaz.

Her fonksiyon HTML dizesi döner ve girdisini `esc()` ile kaçırır — kaynaklardan
ve kullanıcıdan gelen metin bu katmandan geçmeden ekrana çıkmaz.
"""

from __future__ import annotations

import html
import json
import urllib.parse
from collections.abc import Iterable, Sequence
from typing import Any

from politikdesk.web.ui import format as fmt
from politikdesk.web.ui.icons import icon, status_icon
from politikdesk.web.ui.tokens import STATUS_TOKEN


# ═══════════════════════════════════════════════════════ kaçış & güvenlik
class SafeString(str):
    """HTML olarak güvenli kabul edilen ve tekrar kaçırılmaması gereken dize."""

    __slots__ = ()


def mark_safe(value: object) -> SafeString:
    """Bir dizeyi güvenli HTML olarak işaretler."""
    if isinstance(value, SafeString):
        return value
    return SafeString(str(value if value is not None else ""))


def esc(value: object) -> str:
    """HTML kaçışı. Kaynaklardan ve kullanıcıdan gelen HER metin geçer.

    `SafeString` nesneleri çift kaçış (double-escaping) olmaması için
    olduğu gibi döner; diğer tüm nesneler `quote=True` ile kaçırılır.
    """
    if isinstance(value, SafeString):
        return value
    return html.escape(str(value if value is not None else ""), quote=True)


# Tarayıcı, bir URL'i çözümlemeden ÖNCE onu normalleştirir (WHATWG URL
# Standard). Şema denetimi bu normalleştirmeyi birebir taklit etmezse
# denetim ile tarayıcının gördüğü dize farklı olur — aradaki fark bir
# atlatma yoludur.
#
# İki kural geçerlidir:
#   1. Baştaki (ve sondaki) C0 kontrol karakterleri (U+0000–U+001F) ve
#      boşluk ATILIR.
#   2. Sekme (U+0009), LF (U+000A) ve CR (U+000D) URL'in HER YERİNDEN atılır.
#
# ⚠ Python'un `str.strip()`'i 1. kuralı KARŞILAMAZ: yalnızca boşluk
# saydığı karakterleri (`\t\n\v\f\r`, `\x1c`–`\x1f`, boşluk) soyar;
# `\x00`–`\x08` ve `\x0e`–`\x1b` aralığı elinde kalır. Ölçüldü (20 Ağustos
# 2026, gerçek Chromium): `esc_attr("\x01javascript:alert(1)")` eski
# sürümde dizeyi olduğu gibi geçiriyordu ve tarayıcı `a.protocol` değerini
# `javascript:` olarak çözüyordu — yani denetim bypass ediliyordu.
_URL_LEADING_STRIP = "".join(chr(c) for c in range(0x20)) + " "
_URL_INLINE_STRIP = str.maketrans("", "", "\t\n\r")

_DANGEROUS_SCHEMES = ("javascript:", "vbscript:", "data:")

# `href`/`src`/`action` için İZİN LİSTESİ. Kara liste yaklaşımı yeni bir
# tehlikeli şema (blob:, filesystem:, intent: …) çıktığında sessizce
# açık kalır; izin listesi varsayılan olarak kapalıdır.
_SAFE_URL_SCHEMES = ("http://", "https://", "mailto:")


def _browser_normalized_url(value: str) -> str:
    """Tarayıcının şemayı çözerken göreceği biçim (küçük harfli)."""
    return value.strip(_URL_LEADING_STRIP).translate(_URL_INLINE_STRIP).lower()


def _has_dangerous_scheme(value: str) -> bool:
    """Değer, tarayıcı gözüyle tehlikeli bir şemayla mı başlıyor?"""
    normalized = _browser_normalized_url(value)
    if normalized.startswith(_DANGEROUS_SCHEMES):
        return True
    # Yüzde kodlaması (`%6a%61%76%61script:`) tek geçişte çözülür.
    return urllib.parse.unquote(normalized).startswith(_DANGEROUS_SCHEMES)


def esc_attr(value: object) -> str:
    """URL TAŞIMAYAN HTML öznitelikleri için güvenli kaçış.

    `quote=True` ile tırnak, `<`, `>` ve `&` kaçırılır — yani değer
    özniteliğin dışına çıkamaz ve yeni bir öznitelik (`onerror=` gibi)
    açamaz. Bir metin özniteliği için güvenlik sınırı budur.

    **Şema kara listesi BURADAN KALDIRILDI (20 Ağustos 2026 denetimi).**

    Eskiden bu fonksiyon `javascript:`/`data:`/`vbscript:` ile başlayan
    değeri `#`e çeviriyordu, çünkü `href` de buradan geçiyordu. Artık
    `href`/`src`/`action` `esc_url()` kullanıyor ve denetim ORAYA,
    üstelik kara liste yerine İZİN LİSTESİ olarak taşındı.

    Kara listeyi burada bırakmak güvenlik katmıyordu (kaçırılmış bir metin
    zaten çalıştırılamaz) ama meşru içeriği bozuyordu: "javascript: dilinde
    yeni sürüm" başlıklı bir haberin `title` özniteliği `#` oluyordu.
    """
    return html.escape(str(value if value is not None else ""), quote=True)


def esc_url(value: object) -> str:
    """`href` / `src` / `action` için güvenli URL kaçışı (izin listesi).

    Kabul edilenler:
      * mutlak `http://`, `https://`, `mailto:`
      * site içi göreli yollar (`/feed`, `?sayfa=2`, `#bolum`)

    Geri kalan her şey `#`e düşer. Kaynaklardan gelen bir bağlantı
    `javascript:` ise ekranda tıklanabilir olmaması DOĞRU davranıştır:
    haberin kendisi görünmeye devam eder, yalnızca bağlantı ölür.
    """
    s = str(value if value is not None else "").strip()
    if not s:
        return ""
    if _has_dangerous_scheme(s):
        return "#"

    normalized = _browser_normalized_url(s)
    if normalized.startswith(_SAFE_URL_SCHEMES):
        return html.escape(s, quote=True)
    # Göreli yollar. `//evil.com` protokol-göreli bir MUTLAK adrestir;
    # site içi sayılmaz ve reddedilir.
    if normalized.startswith(("/", "?", "#")) and not normalized.startswith("//"):
        return html.escape(s, quote=True)
    return "#"


def script_json(value: Any) -> str:
    """`<script>` bloğunun İÇİNE gömülecek JSON.

    `json.dumps` tek başına yetmez: bir dize `"</script>"` içerirse
    tarayıcı JSON'ı ayrıştırmadan ÖNCE etiketi kapatır ve kalan her şey
    işaretlemeye döner. Bu, gömülü veriyle yaşanan klasik XSS yoludur ve
    `esc()`'in kapsamadığı bir bağlamdır — script gövdesi HTML değil,
    JavaScript'tir.

    `<` karakterinin tamamı değil yalnızca `</` dizisi kaçırılır; JSON'da
    `\\/` geçerli bir `/` kaçışıdır, yani ayrıştırılan değer aynı kalır.
    """
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def action_attrs(name: str | None, *args: Any, event: str = "click") -> str:
    """Eylem özniteliklerini üretir — satır içi işleyicinin yerine geçer (Faz 7).

    `onclick="pdFilterAcc('all', this)"` yerine
    `data-pd-click="filter-acc" data-pd-args="[&quot;all&quot;]"`.

    Neden gerekli: CSP'den `'unsafe-inline'` kalkınca satır içi öznitelik
    işleyicileri tarayıcıda çalışmaz ve nonce onları kurtarmaz (nonce
    yalnızca `<script>` etiketine uygulanır). Davranış `shell.py`'deki
    delegasyon dağıtıcısına taşındı; burası onun işaretleme tarafıdır.

    Argümanlar JSON olarak gömülür ve `esc_attr`'den geçer — yani içlerindeki
    tırnak, `<` ve `&` kaçırılır. Bu, eski `onclick` kuşağının canlı veriyle
    yaşadığı arızayı da kapatır: Türkçe kesme işareti (`Silivri'deki`) artık
    özniteliği erken kapatamaz, çünkü değer KOD değil VERİ olarak taşınır ve
    hiçbir noktada `eval` edilmez.

    `event` yalnızca `click` / `input` / `change` olabilir; dağıtıcı bu üç
    olayı dinler. Yazım hatasıyla dinlenmeyen bir olay adı üretmek sessiz
    bir arıza olurdu, o yüzden burada patlar.
    """
    if not name:
        return ""
    if event not in ("click", "input", "change"):
        raise ValueError(f"Desteklenmeyen eylem olayı: {event!r} (click/input/change)")
    out = f' data-pd-{event}="{esc_attr(name)}"'
    if args:
        out += f' data-pd-args="{esc_attr(json.dumps(list(args), ensure_ascii=False))}"'
    return out


def _attrs(**kwargs: Any) -> str:
    """`cls="x", title="y"` → ` class="x" title="y"`. `None` ve `False` atlanır."""
    out = []
    for key, value in kwargs.items():
        if value is None or value is False:
            continue
        name = {"cls": "class", "for_": "for"}.get(key, key.replace("_", "-"))
        if value is True:
            out.append(name)
        elif key in ("href", "action", "src"):
            # URL öznitelikleri izin listesinden geçer; gerisi yalnızca
            # kaçırılır (bir `title` içinde "javascript:" geçmesi meşrudur).
            out.append(f'{name}="{esc_url(value)}"')
        else:
            out.append(f'{name}="{esc_attr(value)}"')
    return (" " + " ".join(out)) if out else ""


# ═══════════════════════════════════ 8.4 durum rozeti
# Spec §8.1'in beş durumu. Etiketler Türkçe ve METİN HER ZAMAN YAZILIR —
# renk tek başına anlam taşımaz (Bölüm 12, Spec P4).
STATUS_LABELS: dict[str, str] = {
    "strongly_corroborated": "güçlü teyitli",
    "partially_corroborated": "kısmen teyitli",
    "single_source": "tek kaynaklı",
    "contradicted": "çelişkili",
    "unverified": "doğrulanmamış",
    "attribution_verified": "beyan sabit",
}

# Olay durumu (Spec §8.6) — iddia durumundan AYRI BİR EKSEN.
#
# Kanıt skalasının renklerini KULLANMAZ. İlk turda "gelişiyor" amber,
# "kısmen teyitli" de amber çiziliyordu; aynı kartta yan yana duran iki
# amber, kullanıcıya tek bir ölçek olduklarını söylüyordu. Oysa biri
# olayın OTURUP OTURMADIĞINI, diğeri iddianın NE KADAR SAĞLAM olduğunu
# anlatır ve bir olay "oturmuş ama zayıf kanıtlı" olabilir.
#
# `contradicted` istisnadır ve renklidir: çelişki her iki eksende de
# aynı şeyi söyler.
EVENT_STATUS: dict[str, tuple[str, str]] = {
    "developing": ("gelişiyor", "event"),
    "settled": ("oturdu", "event"),
    "contradicted": ("çelişkili", "event contra"),
}

TIER_LABELS: dict[int, str] = {
    1: "Resmî kaynak",
    2: "Ajans",
    3: "Yayın",
    4: "Sosyal",
}


def status_badge(status: str, *, size: int = 13) -> str:
    """Kanıt durumu rozeti (Bölüm 8.4).

    radius 6px — pill DEĞİL. İkon + metin birlikte; ikon renk körlüğünde
    ayırt edici siluet sağlar, metin ekran okuyucuya anlamı verir.
    """
    token = STATUS_TOKEN.get(status, "unverified")
    label = STATUS_LABELS.get(status, status)
    return f'<span class="badge {token}">{status_icon(status, size)}{esc(label)}</span>'


def event_badge(status: str) -> str:
    """Olay durumu rozeti — iddia rozetiyle karıştırılmasın diye kenarlıklı."""
    label, token = EVENT_STATUS.get(status, (status, "neutral"))
    return f'<span class="badge {token}">{esc(label)}</span>'


def tier_badge(tier: int | None) -> str:
    """Kaynak katmanı.

    ⛔ Bu bir SİYASİ KONUM etiketi değildir ve olamaz (Spec §8.5, §15/5).
    T1 "resmî kaynak" demektir; yayının duruşu hakkında hiçbir şey söylemez.
    """
    value = int(tier or 4)
    return f'<span class="tier" title="{esc(TIER_LABELS.get(value, ""))}">T{value}</span>'


# ═══════════════════════════════════════════ 9.1 sayfa iskeleti
def page_head(
    title: str,
    *,
    lede: str = "",
    actions: str = "",
    badges: str = "",
) -> str:
    """Bölüm 9.1: başlık → alt açıklama → sağ üstte TEK birincil eylem.

    `title` ham metin olarak geçilir ve burada kaçırılır; `lede`, `actions`
    ve `badges` HTML'dir (çağıran taraf kaçırmıştır).
    """
    badge_row = f'<div class="row tight">{badges}</div>' if badges else ""
    lede_html = f'<p class="lede">{lede}</p>' if lede else ""
    action_html = f'<div class="actions">{actions}</div>' if actions else ""
    return (
        f'<div class="page-head"><div><h1>{esc(title)}</h1>'
        f"{badge_row}{lede_html}</div>{action_html}</div>"
    )


def card(body: str, *, title: str = "", actions: str = "", cls: str = "") -> str:
    """Panel kartı (Bölüm 5.5) — 1px border, GÖLGE YOK.

    Başlık `h2` + `.h3` olarak üretilir: **seviye semantik, boyut görsel**
    karardır. Kart, sayfanın `h1`inden sonraki ilk bölümdür; `h3` yazmak
    `h2`yi atlıyordu ve Lighthouse `heading-order` denetimi altı ekranda
    birden düşüyordu (20 Ağustos 2026 ölçümü, DESIGN.md Bölüm 12:
    "başlık seviyeleri atlanmaz"). `.h3` sınıfı boyutu korur —
    özgüllüğü (0,1,0) `h2` elementinden (0,0,1) yüksektir.
    """
    head = ""
    if title or actions:
        head = (
            f'<div class="card-head">{f"<h2 class='h3'>{esc(title)}</h2>" if title else ""}'
            f"{f"<div class='actions'>{actions}</div>" if actions else ''}</div>"
        )
    return f'<section class="card {cls}">{head}{body}</section>'


def source_pill(name: str, tier: int | None = None, *, url: str = "") -> str:
    """Kaynak hapı (Bölüm 8.5) — T1-T4 katman rozeti ile birlikte."""
    t_html = tier_badge(tier) if tier else ""
    esc_name = esc(name)
    content = f"{t_html}<span>{esc_name}</span>"
    if url:
        return f'<a class="source-pill" href="{esc_url(url)}" target="_blank" rel="noopener noreferrer">{content}</a>'
    return f'<span class="source-pill">{content}</span>'


# ═══════════════════════════════════════════ 8.1 KPI kartı (varyant A)
def kpi(
    label: str,
    value: str,
    *,
    unit: str = "",
    delta: float | None = None,
    delta_note: str = "",
    higher_is_better: bool = True,
    icon_name: str | None = None,
) -> str:
    """Bölüm 8.1 varyant A: etiket → değer → delta. Sıra değişmez.

    `higher_is_better` delta rengini belirler: renk **iyi/kötü**yü anlatır,
    artış/azalışı değil. "Teyitsiz iddia sayısı arttı" kırmızıdır.
    """
    delta_html = ""
    if delta is not None:
        good = (delta > 0) == higher_is_better
        tone = "flat" if delta == 0 else ("up" if good else "down")
        arrow = "trend-flat" if delta == 0 else ("trend-up" if delta > 0 else "trend-down")
        # Bağlamsız yüzde değersizdir — karşılaştırma dönemi zorunlu.
        note = delta_note or "önceki döneme göre"
        delta_html = (
            f'<div class="kpi-delta {tone}">{icon(arrow, 14)}'
            f"<b>{esc(fmt.signed_percent(delta))}</b>"
            f"<span>{esc(note)}</span></div>"
        )
    unit_html = f'<span class="kpi-unit">{esc(unit)}</span>' if unit else ""
    icon_html = icon(icon_name, 14) if icon_name else ""
    return (
        f'<article class="card kpi">'
        f'<div class="kpi-label">{icon_html}{esc(label)}</div>'
        f'<div class="kpi-value">{esc(value)}{unit_html}</div>'
        f"{delta_html}</article>"
    )


# ═══════════════════════════════════════════════════ uyarı / not
def notice(body: str, *, tone: str = "", icon_name: str | None = None) -> str:
    """`tone`: "" | warn | bad | ok."""
    default_icon = {"warn": "warning", "bad": "warning", "ok": "check"}
    name = icon_name or default_icon.get(tone, "info")
    return f'<div class="notice {tone}">{icon(name, 16)}<div>{body}</div></div>'


# ═══════════════════════════════════════════════ 10.1–10.4 durumlar
def empty_state(title: str, body: str, *, action: str = "", icon_name: str = "inbox") -> str:
    """Boş durum (10.1) — bir DAVETTİR, bir hata değil.

    "Veri bulunamadı" yasak: ne olacağını ve nasıl başlanacağını söyle.
    """
    return (
        f'<div class="empty">{icon(icon_name, 32)}<h3>{esc(title)}</h3>'
        f"<p>{esc(body)}</p>{action}</div>"
    )


def filtered_empty_state(query_note: str, reset_href: str) -> str:
    """Filtre-boş (10.2) — 10.1 ile AYNI YAPILMAZ.

    Kullanıcı hangi durumda olduğunu bilmeli: hiç veri mi yok, yoksa
    filtresi mi tutmadı?
    """
    return (
        f'<div class="empty">{icon("filter-off", 32)}'
        f"<h3>Eşleşen kayıt yok</h3>"
        f"<p>{esc(query_note)}</p>"
        f'<a class="btn" href="{esc(reset_href)}">Filtreleri temizle</a></div>'
    )


def error_state(title: str, body: str, *, retry: str = "", code: str = "") -> str:
    """Hata (10.4): ne oldu → neden → nasıl çözülür. Teknik kod küçük ve altta."""
    code_html = f'<p class="mono subtle">{esc(code)}</p>' if code else ""
    return (
        f'<div class="empty">{icon("warning", 32)}<h3>{esc(title)}</h3>'
        f"<p>{esc(body)}</p>{retry}{code_html}</div>"
    )


def skeleton_rows(count: int = 5, *, height: int = 20) -> str:
    """Yükleniyor (10.3): skeleton, spinner DEĞİL. Gerçek içeriğin şekli."""
    return "".join(
        f'<div class="skeleton" style="height:{height}px;width:{width}%;margin-bottom:12px"></div>'
        for width in ([92, 78, 86, 70, 81] * ((count // 5) + 1))[:count]
    )


# ═══════════════════════════════════════════════ açılır panel
def panel(summary: str, body: str, *, open_: bool = False, cls: str = "") -> str:
    """`<details>` — klavyeyle açılır, JS gerektirmez, yazdırmada da çalışır.

    `cls="quiet"`: kart içindeki ikincil panel. Kenarlıksız ve zeminsiz
    çizilir — bir açılır panel bir eylem değil, bir dipnottur ve yanındaki
    durum rozetiyle aynı görsel ağırlıkta durmamalıdır.
    """
    return (
        f'<details class="panel {cls}"{" open" if open_ else ""}>'
        f'<summary>{summary}{icon("chevron-right", 14)}</summary>'
        f'<div class="panel-body">{body}</div></details>'
    )


# ═══════════════════════════════════════ SIGNATURE: kanıt cetveli
def ruled(status: str, body: str, *, cls: str = "") -> str:
    """Sol kenarında kanıt durumunun rengini taşıyan blok.

    Bu arayüzün imza öğesi (`ui/css.py` başlığı). `unverified` durumunda
    cetvel **kesikli** çizilir — renk körlüğünde ayrımı renk değil desen
    taşır.
    """
    token = STATUS_TOKEN.get(status, "unverified")
    return f'<div class="ruled {token} {cls}">{body}</div>'


# ═══════════════════════════════════════════════ 8.3 tablo
def table(
    headers: Sequence[tuple[str, str]],
    rows: Iterable[str],
    *,
    cards_on_mobile: bool = True,
    empty: str = "",
) -> str:
    """`headers`: (etiket, sınıf) çiftleri — sınıf `"num"` ise sağa hizalı.

    `cards_on_mobile`: Bölüm 7.4 gereği varsayılan **açık**. Tablo mobilde
    yatay kaydırmaya bırakılmaz, satırlar karta döner.
    """
    body = "".join(rows)
    if not body:
        return empty or empty_state("Kayıt yok", "Bu listede henüz kayıt bulunmuyor.")
    head = "".join(f"<th{_attrs(cls=cls or None)}>{esc(label)}</th>" for label, cls in headers)
    cls = "table-cards" if cards_on_mobile else ""
    return (
        f'<div class="table-wrap"><table class="{cls}"><thead><tr>{head}</tr>'
        f"</thead><tbody>{body}</tbody></table></div>"
    )


def cell(content: str, *, label: str, cls: str = "") -> str:
    """`data-label` mobilde kart görünümünde sütun adını basar."""
    return f"<td{_attrs(cls=cls or None, data_label=label)}>{content}</td>"


def relative_time(value: Any) -> str:
    """Göreli zaman + `title`'da tam tarih (Bölüm 8.3)."""
    return f'<span title="{esc(fmt.precise(value))}">{esc(fmt.relative(value))}</span>'


# ═══════════════════════════════════════ 8.12 sıralı dağılım listesi
def distribution(items: Sequence[tuple[str, float, str]]) -> str:
    """`(etiket, değer, gösterilecek metin)` — büyükten küçüğe SIRALANIR.

    Alfabetik sıralama bu bileşenin amacını yok eder. 5'ten fazla kategoride
    donut yerine bu kullanılır (her zaman daha okunaklıdır).
    """
    if not items:
        return '<p class="subtle">Dağılım verisi yok.</p>'
    ordered = sorted(items, key=lambda row: row[1], reverse=True)
    top = max(value for _, value, _ in ordered) or 1.0
    rows = "".join(
        f'<div class="dist-row"><span class="name" title="{esc(name)}">{esc(name)}</span>'
        f'<span class="track"><span style="width:{max(2, round(value / top * 100))}%">'
        f'</span></span><span class="val">{esc(text)}</span></div>'
        for name, value, text in ordered
    )
    return f'<div class="dist">{rows}</div>'


# ═══════════════════════════════════════════ 8.11 segment kontrolü
def segment(options: Sequence[tuple[str, str, bool]]) -> str:
    """`(etiket, href, aktif mi)`. Sekme DEĞİLDİR — aynı veriyi farklı gösterir."""
    return (
        '<div class="segment">'
        + "".join(
            f'<a href="{esc(href)}"{' aria-current="true"' if active else ""}>{esc(label)}</a>'
            for label, href, active in options
        )
        + "</div>"
    )


# ═══════════════════════════════════════════════ 8.5 buton
def button(
    label: str,
    *,
    href: str | None = None,
    variant: str = "",
    icon_name: str | None = None,
    action: str | None = None,
    action_args: Sequence[Any] = (),
    disabled: bool = False,
    title: str | None = None,
    id_: str | None = None,
    small: bool = False,
) -> str:
    """Bölüm 8.5. Sayfada **tek** `variant="primary"` bulunur.

    İkon-only buton (`label=""`) için `title` zorunludur — `aria-label`
    olarak da basılır (Bölüm 12).

    `action` / `action_args`: tıklamada çalışacak eylem (Faz 7). Eskiden
    `onclick=` bir JavaScript İFADESİ alıyordu; artık kayıt defterindeki bir
    eylemin ADI ve onun veri argümanları alınır — işaretlemeye kod gömülmez.
    """
    classes = ["btn", variant, "sm" if small else "", "icon" if not label else ""]
    graphic = icon(icon_name, 14 if small else 16) if icon_name else ""
    text = f"<span>{esc(label)}</span>" if label else ""
    if not label and not title:
        raise ValueError("İkon-only butonda `title` zorunlu (erişilebilirlik).")
    common = _attrs(
        cls=" ".join(c for c in classes if c),
        title=title,
        aria_label=title if not label else None,
        id=id_,
    )
    if href is not None:
        # Bağlantı olarak basılan bir butona eylem verilirse eylem SESSİZCE
        # düşerdi; düğme tıklanır, hiçbir şey olmaz. Sessiz kalmaktansa patla.
        if action:
            raise ValueError("`href` ve `action` birlikte kullanılamaz; biri seçilmeli.")
        return f'<a{common} href="{esc(href)}">{graphic}{text}</a>'
    behaviour = action_attrs(action, *action_args) + _attrs(disabled=disabled)
    return f"<button{common}{behaviour}>{graphic}{text}</button>"


def chip(label: str, href: str, *, active: bool = False, icon_name: str | None = None) -> str:
    """Filtre çipi (Bölüm 8.10). Aktif çip görsel olarak AYRIŞIR."""
    graphic = icon(icon_name, 14) if icon_name else ""
    return (
        f'<a class="chip" href="{esc(href)}" aria-pressed="{str(active).lower()}">'
        f"{graphic}{esc(label)}</a>"
    )


# ═══════════════════════════════════════════ 8.15 zaman çizelgesi
def timeline(items: Sequence[tuple[str, str]]) -> str:
    """`(zaman metni, gövde HTML)`."""
    if not items:
        return ""
    return (
        '<ul class="timeline">'
        + "".join(f'<li><div class="when">{esc(when)}</div>{body}</li>' for when, body in items)
        + "</ul>"
    )


def search_input(
    id_: str,
    placeholder: str = "Ara…",
    *,
    action: str | None = None,
    cls: str = "",
) -> str:
    """Arama kutusu — ikonlu ve erişilebilir.

    `action`: her tuş vuruşunda çalışacak eylemin adı (Faz 7). Dağıtıcı
    `input` olayını dinler ve eylemi `fn(öğe, olay)` olarak çağırır; arama
    metni `öğe.value`'dan okunur.
    """
    return (
        f'<div class="search-wrap {cls}">'
        f'{icon("search", 14)}'
        f'<input type="search" id="{esc(id_)}" placeholder="{esc(placeholder)}"'
        f"{action_attrs(action, event='input')}>"
        f"</div>"
    )

