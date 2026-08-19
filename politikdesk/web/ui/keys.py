"""Klavye kısayolu sözleşmesi (Roadmap Faz 8.3).

**Neden bir modül, neden her sayfa kendi listesini yazmıyor.**

Bu depoda kısayollar üç ayrı yerde yaşıyordu ve üçü birbirinden habersizdi:

    1. `feed.py` içindeki `keydown` dinleyicisi   → GERÇEKTE ÇALIŞAN
    2. `feed.py` içindeki kısayol penceresi       → elle yazılmış 7 satır
    3. `war_room.py` içindeki kılavuz kartı       → elle yazılmış paragraf

Üçüncüsü bir kez yanlış yazıldı: kumanda odası ekranı J/K/X kısayollarını
listeliyordu ama o tuşlar `feed.py`'nin dinleyicisine bağlıydı ve o ekranda
hiçbir şey yapmıyordu. Kullanıcı tuşa basar, hiçbir şey olmaz, arayüzün
bozuk olduğunu düşünür. **Çalışmayan bir kısayol listesi, kısayol listesi
olmamasından kötüdür.**

Düzeltme o gün elle yapıldı — ama elle yapılan düzeltme aynı hatanın
tekrarını engellemez. Bu modül tek kaynağı kurar:

    beyan (burası)  →  JS kaydı (pdKey)  →  ekranda görünen tuş

Üçü de buradan türer ve `tests/test_keyboard_contract.py` üçünün
birbirini tuttuğunu **her koşumda** ölçer: beyan edilip uygulanmayan bir
kısayol da, uygulanıp beyan edilmeyen bir kısayol da testi kırar.

### Rota bazlı olmasının sebebi

Roadmap 8.3: *"J / K / X gibi kısayollar gerçekten hangi sayfada aktifse
UI'da sadece orada gösterilmeli."* `PAGE` sözlüğünde satırı olmayan bir
rota yalnızca genel kısayolları gösterir — varsayılan susmaktır.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from politikdesk.web.ui.components import esc, script_json


@dataclass(frozen=True)
class Shortcut:
    """Tek bir kısayol.

    `action`  — `window.pdKey(<action>, fn)` ile kaydedilen davranışın adı.
                `None` ise kısayolu kabuk kendi içinde uygular (Ctrl+K
                komuta paletini açar, Esc açık pencereyi kapatır); bu
                ikisi bir sayfa eylemi değil, kabuk davranışıdır.
    `keys`    — `KeyboardEvent.key` değerleri. Büyük/küçük harf AYRI
                yazılır: Caps Lock açıkken tarayıcı `"J"` gönderir ve
                yalnız `"j"` dinleyen bir kısayol sessizce ölür.
    `display` — kullanıcıya gösterilen metin. `keys`'in kendisi
                gösterilemez: kullanıcıya "ArrowDown" değil "J" denir.
    `label`   — ne yaptığı, Türkçe, cümle düzeninde (Ek B.2).
    """

    action: str | None
    keys: tuple[str, ...]
    display: str
    label: str


# ── Her ekranda geçerli olanlar ────────────────────────────────────────
#
# İkisinin de `action`'ı yok: Ctrl+K paleti, Esc açık pencereyi kabuk
# katmanında yönetir (`shell._CMD_JS`, `shell._DRAWER_JS`). Bir sayfa
# eylemi olmadıkları için `pdKey` kaydına girmezler — ama kullanıcı
# açısından kısayoldurlar ve listede görünmeleri gerekir.
GLOBAL: Final[tuple[Shortcut, ...]] = (
    Shortcut(None, ("k",), "Ctrl + K", "Komuta paleti ve hızlı arama"),
    Shortcut(None, ("Escape",), "Esc", "Açık pencereyi kapat"),
)

# ── Rota bazlı ─────────────────────────────────────────────────────────
PAGE: Final[dict[str, tuple[Shortcut, ...]]] = {
    "/feed": (
        Shortcut("next-event", ("j", "J", "ArrowDown"), "J", "Sonraki olay"),
        Shortcut("prev-event", ("k", "K", "ArrowUp"), "K", "Önceki olay"),
        # Etiketler ekranın geri kalanıyla AYNI sözcüğü kullanır ("X Tweeti").
        # Ek B.2: bir eylem baştan sona aynı adı taşır.
        Shortcut("draft-x", ("x", "X", "t", "T"), "X veya T", "X Tweeti hazırla / odaklan"),
        Shortcut("copy-selected", ("c", "C"), "C", "Seçili tweeti / başlığı kopyala"),
        Shortcut("open-event", ("Enter", "o", "O"), "Enter veya O", "Olay detayını aç"),
        Shortcut("focus-search", ("/",), "/", "Gündemde anlık arama"),
        Shortcut("toggle-shortcuts", ("?",), "?", "Kısayol penceresini aç/kapat"),
    ),
}


def for_route(route: str) -> tuple[Shortcut, ...]:
    """Bir rotanın sayfaya özel kısayolları. Tanımsız rota → boş."""
    return PAGE.get(route, ())


def all_for_route(route: str) -> tuple[Shortcut, ...]:
    """Genel + sayfaya özel, gösterim sırasıyla.

    Sayfaya özel olanlar ÖNDE: kullanıcı bu ekrana özgü olanı arıyordur,
    Ctrl+K'yı zaten biliyor.
    """
    return for_route(route) + GLOBAL


# ═══════════════════════════════════════════════════════ JS tarafı


def keymap_js(route: str) -> str:
    """`window.pdKeymap` — dağıtıcının okuduğu tablo.

    Yalnızca `action`'ı olan kısayollar girer; kabuğun kendi yönettiği
    Ctrl+K ve Esc buraya yazılsaydı iki dinleyici aynı tuşa basardı.

    Tablo VERİDİR, kod değil: içinde çalıştırılabilir hiçbir ifade yok,
    yalnızca tuş adları ve eylem adları var. Eylem adı `pdKeyActions`
    kayıt defterinde aranır ve orada yoksa hiçbir şey olmaz — `window`
    üzerinde çözülmez (aynı gerekçe `shell._DISPATCH_JS` başlığında).
    """
    entries = [
        {"keys": list(item.keys), "action": item.action}
        for item in for_route(route)
        if item.action
    ]
    return f"window.pdKeymap = {script_json(entries)};\n"


# Tuş dağıtıcısı. `keymap_js` ile birlikte çalışır.
#
# ### Odaklanmış öğe koruması — bu bir hata düzeltmesidir
#
# Eski dinleyici yalnızca `INPUT` ve `TEXTAREA`'yı atlıyordu. Odaktaki bir
# düğmede Enter'a basmak hem düğmeyi çalıştırıyor hem de seçili olayın
# bağlantısına gidiyordu; kullanıcı bastığı düğmenin sonucunu göremeden
# başka sayfaya düşüyordu. Klavyeyle gezen biri için bu, arayüzün
# kullanılamaz olması demektir (Bölüm 12: "her etkileşimli öğe klavye ile
# erişilebilir").
DISPATCH_JS: Final[str] = """
window.pdKeyActions = Object.create(null);
window.pdKey = function(name, fn){ window.pdKeyActions[name] = fn; };
window.pdKeymap = window.pdKeymap || [];
(function(){
  function blocked(e){
    var el = document.activeElement;
    if (!el || el === document.body) return false;
    var tag = el.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
    if (el.isContentEditable) return true;
    // Enter ve boşluk odaktaki düğmeyi/bağlantıyı tetikler; kısayol onu çalamaz.
    if ((e.key === 'Enter' || e.key === ' ') &&
        (tag === 'BUTTON' || tag === 'A' || tag === 'SUMMARY')) return true;
    return false;
  }
  document.addEventListener('keydown', function(e){
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (blocked(e)) return;
    for (var i = 0; i < window.pdKeymap.length; i++) {
      var entry = window.pdKeymap[i];
      if (!entry.keys || entry.keys.indexOf(e.key) === -1) continue;
      var fn = window.pdKeyActions[entry.action];
      if (typeof fn !== 'function') return;
      e.preventDefault();
      fn(e);
      return;
    }
  });
})();
"""


# ═══════════════════════════════════════════════════════ görünen taraf


def _rows(items: tuple[Shortcut, ...]) -> str:
    return "".join(
        f'<div class="shortcut-row"><span>{esc(item.label)}</span>'
        f'<kbd class="shortcut-key">{esc(item.display)}</kbd></div>'
        for item in items
    )


def help_rows(route: str) -> str:
    """Kısayol penceresinin gövdesi — sözleşmeden üretilir, elle yazılmaz."""
    page_items = for_route(route)
    out = _rows(page_items)
    if page_items:
        out += (
            '<p class="eyebrow" style="margin:var(--space-4) 0 var(--space-1)">'
            "Her ekranda</p>"
        )
    return out + _rows(GLOBAL)


def guide_card_body(route: str, *, elsewhere: str = "") -> str:
    """Yan sütuna sığan kompakt kılavuz (kumanda odası tipi ekranlar).

    `elsewhere`: bu ekranda ÇALIŞMAYAN ama kullanıcının arayabileceği
    kısayolların nerede olduğunu söyleyen bir cümle. Boş bırakılabilir;
    yanlış yazılamaz, çünkü çalışan kısayollar listesi sözleşmeden gelir.
    """
    items = all_for_route(route)
    rows = "".join(
        f'<div class="shortcut-row"><span>{esc(item.label)}</span>'
        f'<kbd class="shortcut-key">{esc(item.display)}</kbd></div>'
        for item in items
    )
    tail = (
        f'<p class="subtle" style="margin:var(--space-3) 0 0;font-size:var(--text-xs)">'
        f"{elsewhere}</p>"
        if elsewhere
        else ""
    )
    return f'<div style="font-size:var(--text-xs)">{rows}{tail}</div>'
