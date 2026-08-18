"""Tasarım token'ları — TEK KAYNAK (DESIGN.md Bölüm 5-6, Yön A "Mürekkep").

⛔ **Bu dosya dışında hiçbir `.py` dosyasında ham hex bulunmaz.**
Denetimi `tests/test_design_tokens.py` yapar ve CI adımıdır. Bir rengi
değiştirmek isteyen burayı değiştirir; stylesheet (`ui/css.py`) buradan
*türetilir*, elle yazılmaz.

### Görsel yön: "Mürekkep"

Bir araştırmacının dosyası. Sıcak kağıt zemini üzerine mürekkeple yazılmış
bir kayıt. Gerekçesi ve elenen iki alternatif `design/decisions.md`'de.

### Neden aksan rengi bu kadar sessiz

Bu projeye özel tek karar budur ve tüm paletin dayanağıdır:

    Ekrandaki EN DOYGUN ŞEY `evidence_status` skalası olmalıdır.

Ürünün tek cümlelik sözleşmesi "her iddia kanıta bağlanır"dır. Jenerik bir
panelde marka aksanı en yüksek sesle konuşur; burada konuşursa "bu iddia ne
kadar sağlam" sorusuyla *yarışır* ve kullanıcı rengi marka sanar. Bu yüzden
aksan derin bir mürekkep mavisidir (`#1E3A5F`) — küçük punto'da neredeyse
metin gibi okunur, doygunluğu kanıt skalasına bırakır.

Somut sonuç: bir ekranda parlak renk görüyorsan o bir kanıt durumudur.
İstisnası yoktur.

### Renk körlüğü

Kanıt skalası yeşil→sarı→turuncu→kırmızı ilerler ve kırmızı-yeşil renk
körlüğünde tek başına okunamaz. Bu yüzden `components.status_badge`
renkle BİRLİKTE her zaman **metin etiketi ve ayırt edici bir işaret**
basar (DESIGN.md Bölüm 8.4, Spec P4). Renk hiçbir yerde tek taşıyıcı değildir.
"""

from __future__ import annotations

from typing import Final

# ═══════════════════════════════════════════════════════════ 5.2 RENK
# Anahtarlar CSS değişken adlarıdır (`--` öneki `css.py`'de eklenir).
# Her satırın sonundaki oran, o rengin `bg` üzerindeki WCAG kontrastıdır;
# `tests/test_design_tokens.py` bunları YENİDEN HESAPLAR — yorum değil,
# doğrulanan bir iddia.

LIGHT: Final[dict[str, str]] = {
    # ── Yüzeyler (3 seviye) ──
    "color-bg": "#FBFAF8",  # kağıt — sıcak nötr, krem DEĞİL
    "color-surface": "#FFFFFF",  # kart, panel
    "color-surface-sunken": "#F3F1ED",  # fihrist: tablo başlığı, input arkası
    "color-overlay": "#FFFFFF",  # modal, popover
    # ── Kenarlıklar (2 seviye) ──
    "color-border": "#E3E0DA",  # dekoratif: kart, ayırıcı, satır
    "color-border-strong": "#94908A",  # ETKİLEŞİMLİ: input, checkbox — ≥3:1
    # ── Metin (4 seviye) ──
    "color-fg": "#16181D",  # mürekkep            · 17,0:1
    "color-fg-muted": "#52565E",  # arşiv grisi         ·  7,1:1
    "color-fg-subtle": "#676B72",  # etiket, placeholder ·  5,1:1
    "color-fg-on-accent": "#FFFFFF",
    # ── Aksan (TEK renk) ──
    "color-accent": "#1E3A5F",  # mürekkep mavisi     · 11,0:1
    "color-accent-hover": "#162C48",
    "color-accent-subtle": "#EBF0F6",  # düz renk — alpha DEĞİL (üst üste binme)
    # ── Kanıt skalası (Spec §8.1) ──
    # İsimler durum adlarıdır, renk adları değil: `evidence_status` beş
    # değerlidir ve bileşenler o beş değeri arar.
    "color-strong": "#15803D",  # güçlü teyitli
    "color-strong-subtle": "#F0F7F1",
    "color-partial": "#A16207",  # kısmen teyitli
    "color-partial-subtle": "#FCF6E9",
    "color-single": "#C2410C",  # tek kaynaklı
    "color-single-subtle": "#FDF1EA",
    "color-contra": "#B91C1C",  # çelişkili
    "color-contra-subtle": "#FBECEC",
    # `unverified` kasıtlı olarak RENKSİZDİR — doğrulanmamış bir iddiaya
    # renk vermek ona olmadığı bir ağırlık yükler.
    "color-unverified": "#676B72",
    "color-unverified-subtle": "#F3F1ED",
    # ── Grafik (sıralı, renk körü güvenli) ──
    # Tek hue'nun (mürekkep mavisi) açıklık rampası + iki ayırt edici ton.
    # Kategorik değil SIRALI seçildi: bu üründe grafiklerin çoğu bir
    # metriğin zaman içindeki seyri, kategorilerin karşılaştırması değil.
    "color-chart-1": "#1E3A5F",
    "color-chart-2": "#3D6491",
    "color-chart-3": "#5B87BE",
    "color-chart-4": "#A16207",
    "color-chart-5": "#15803D",
    "color-chart-6": "#94908A",
}

# DESIGN.md 5.2: koyu tema AYNI isimlerle, ayrı blokta.
#   · saf siyah yasak — `#0E1013` sıcaklığı korur (nötr griye kaçmaz)
#   · derinliği gölge değil YÜZEY AÇIKLIĞI verir
#   · aksan light'takinden ~%10 daha açık ve daha az doygun
DARK: Final[dict[str, str]] = {
    "color-bg": "#0E1013",  # gece mürekkebi
    "color-surface": "#16181C",
    "color-surface-sunken": "#1C1F24",
    "color-overlay": "#1C1F24",
    "color-border": "#282B31",
    "color-border-strong": "#6E7279",
    "color-fg": "#F4F2EE",  # sıcak beyaz — kağıdın hatırası
    "color-fg-muted": "#A9ACB2",
    "color-fg-subtle": "#8A8E95",
    "color-fg-on-accent": "#0E1013",
    "color-accent": "#7DA6D9",
    "color-accent-hover": "#9BBCE6",
    "color-accent-subtle": "#182430",
    "color-strong": "#5CBE7E",
    "color-strong-subtle": "#16251C",
    "color-partial": "#D9A441",
    "color-partial-subtle": "#251E12",
    "color-single": "#F08A54",
    "color-single-subtle": "#271811",
    "color-contra": "#F07171",
    "color-contra-subtle": "#2A1516",
    "color-unverified": "#8A8E95",
    "color-unverified-subtle": "#1C1F24",
    "color-chart-1": "#7DA6D9",
    "color-chart-2": "#5B85B8",
    "color-chart-3": "#B7CFEA",
    "color-chart-4": "#D9A441",
    "color-chart-5": "#5CBE7E",
    "color-chart-6": "#6E7279",
}

# Kanıt durumu -> token öneki. Bileşenler durumu buradan renge çevirir;
# hiçbir bileşen kendi eşlemesini tutmaz.
STATUS_TOKEN: Final[dict[str, str]] = {
    "strongly_corroborated": "strong",
    "partially_corroborated": "partial",
    "single_source": "single",
    "contradicted": "contra",
    "unverified": "unverified",
    "attribution_verified": "accent",
}

# ═══════════════════════════════════════════════════════ 5.3 SPACING
# 4px tabanlı, 7 değer. Ara değer (5, 10, 13, 18, 22px) YASAK — bir şey
# "biraz kaymış" görünüyorsa çözüm ara değer değil, yapıyı düzeltmektir.
SPACE: Final[dict[str, str]] = {
    "space-1": "4px",  # ikon-metin arası
    "space-2": "8px",  # kart içi sıkı gruplar
    "space-3": "12px",  # form alanı içi
    "space-4": "16px",  # yoğun kart padding, kart arası (yoğun)
    "space-6": "24px",  # kart arası (standart), içerik dikey ritmi
    "space-8": "32px",  # bölüm arası
    "space-12": "48px",  # sayfa bölgeleri arası
}

# ═══════════════════════════════════════════════════════ 5.4 RADIUS
# Karakter: 12px = modern, ölçülü. 4px teknik/keskin, 20px+ oyuncaklı olurdu.
RADIUS: Final[dict[str, str]] = {
    "radius-sm": "6px",  # rozet, tag, çip
    "radius-md": "8px",  # input, buton, nav öğesi
    "radius-lg": "12px",  # kart, panel  ← ana karakter
    "radius-xl": "16px",  # modal
    "radius-full": "9999px",  # avatar, nokta
}

# ═══════════════════════════════════════════════════════ 5.5 GÖLGE
# Panel kartları gölge KULLANMAZ — 1px border yeter. Gölge yalnızca
# "yüzeyin üstünde yüzen" şeyler içindir. Her karta gölge = ucuz görünüm.
SHADOW: Final[dict[str, str]] = {
    "shadow-sm": "0 1px 2px 0 rgb(22 24 29 / .04), 0 1px 3px 0 rgb(22 24 29 / .06)",
    "shadow-md": "0 4px 12px -2px rgb(22 24 29 / .08), 0 2px 6px -2px rgb(22 24 29 / .04)",
    "shadow-lg": "0 12px 32px -8px rgb(22 24 29 / .16)",  # SADECE modal/popover
}

# ═══════════════════════════════════════════════════ 6.2 TİPOGRAFİ
# Türkçe glif kontrolü yapıldı ve TESTLE korunuyor:
# `tests/test_design_tokens.py::test_fonts_cover_turkish_glyphs` woff2
# dosyalarının cmap'ini okur. İ ı Ğ ğ Ş ş Ç ç Ö ö Ü ü — üçünde de tam.
#
# Instrument Serif'te ₺ (U+20BA) YOK — sorun değil, serif yalnızca sayfa
# H1'inde kullanılır ve H1'de para birimi geçmez. Tutarların geçtiği her
# yer body veya mono ile dizilir; ikisinde de ₺ var.
#
# Harici CDN yok (BRIEF kırmızı çizgi): woff2'ler `web/static/fonts/`
# altından servis edilir.
FONT: Final[dict[str, str]] = {
    "font-display": "'Instrument Serif', Georgia, 'Times New Roman', serif",
    "font-body": (
        "'Inter Tight', -apple-system, BlinkMacSystemFont, 'Segoe UI', "
        "Roboto, Helvetica, Arial, sans-serif"
    ),
    "font-mono": "'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
}

# 6.3 Ölçek — 7+1 adım. Kural: yazı büyüdükçe letter-spacing AZALIR.
# (boyut, satır yüksekliği, letter-spacing)
TEXT: Final[dict[str, tuple[str, str, str]]] = {
    "text-xs": ("12px", "16px", ".01em"),  # etiket, tablo başlığı
    "text-sm": ("13px", "20px", "0"),  # tablo hücresi, ikincil
    "text-base": ("14px", "22px", "0"),  # UI varsayılanı
    "text-lg": ("16px", "24px", "-.005em"),  # kart başlığı
    "text-xl": ("20px", "28px", "-.01em"),  # bölüm başlığı
    "text-2xl": ("25px", "32px", "-.015em"),  # sayfa başlığı (serif)
    "text-3xl": ("30px", "36px", "-.02em"),  # KPI değeri
    "text-4xl": ("40px", "44px", "-.025em"),  # yalnız boş/hata durumu ikonu
}

# 6.4 Sadece 3 ağırlık. 700+ yok (hero yok), 300 hiç yok (ekranda zayıf).
WEIGHT: Final[dict[str, str]] = {
    "weight-normal": "400",
    "weight-medium": "500",
    "weight-semibold": "600",
}

# ═══════════════════════════════════════════════════ 7.1 LAYOUT
LAYOUT: Final[dict[str, str]] = {
    "sidebar-w": "264px",
    "sidebar-collapsed-w": "64px",
    "topbar-h": "56px",
    "content-max": "1440px",
    "content-pad-x": "32px",
    "content-pad-x-dense": "24px",
    "prose-max": "68ch",  # okunabilir metin bloğu
    # BRIEF yogunluk: "dengeli" — TÜM sayfalarda aynı kalır.
    "card-pad": "20px",
    "row-h": "48px",
    "nav-item-h": "36px",
    "control-h": "36px",
}

# ═══════════════════════════════════════════════ 11.1 HAREKET
# 300ms'yi geçen hiçbir UI animasyonu yok. Kapanış her zaman açılıştan hızlı.
MOTION: Final[dict[str, str]] = {
    "ease-out": "cubic-bezier(0, 0, .2, 1)",
    "ease-spring": "cubic-bezier(.16, 1, .3, 1)",
    "dur-hover": "120ms",
    "dur-press": "80ms",
    "dur-pop": "160ms",
    "dur-modal": "220ms",
}


# ═════════════════════════════════════════════ WCAG yardımcıları
def _srgb_to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """WCAG 2.x bağıl parlaklık. Girdi `#RRGGBB`."""
    raw = hex_color.lstrip("#")
    r, g, b = (int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """İki rengin WCAG kontrast oranı (1.0 – 21.0).

    `tests/test_design_tokens.py` bunu kullanarak paletin TAMAMINI her
    koşumda yeniden doğrular — palet bir iddia değil, ölçülen bir olgudur.
    """
    a, b = relative_luminance(fg), relative_luminance(bg)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)
