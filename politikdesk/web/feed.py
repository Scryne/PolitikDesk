"""Gündem ekranı (F3-02, F3-07, F3-18 · Spec §14.1 kalem 1).

F3-02 DoD: salience sıralı olay kartları; her kartta durum rozeti, kaynak
sayısı kırılımı, son güncelleme; **30 sn'de bir sessiz yenileme.**

"Sessiz" burada teknik bir kısıttır: yenileme sırasında sayfa kaymaz,
kaydırma konumu korunur ve açık bir panel kapanmaz. Tam sayfa
`location.reload()` bunların üçünü de bozardı; kart listesi ayrı bir uçtan
(`/feed/cards`) çekilip yerine konur.

### Bu sayfanın tek işi (BRIEF `birincil_is`)

> "Şu an gündemde ne var ve hangisi hakkında GÜVENLE yazabilirim?"

Bu iki soru değil, tek sorudur — ve ekranın hiyerarşisi onu izler:

  1. **Yazıma hazır olay sayısı** en büyük tipografide, sol üstte. Sorunun
     cevabı bu. Sadece önemi gösteren bir feed ürünü haber okuyucusuna
     indirir; kanıt gücü aynı bakışta okunmalıdır.
  2. Filtre şeridi o cevabı **liste hâline getirir** — sayıya tıklanır.
  3. Kartlar salience sırasıyla; her kartın sol kenarında kanıt cetveli.

### Kanıt cetvelinin türetimi

Kart cetvelinin rengi (`ui/css.py` — signature öğesi) olayın iddialarının
kanıt durumlarının **görsel özetidir**, yeni bir skor değildir:

    çelişki var        → contra   (bir çelişki, teyit oranından önce gelir)
    hepsi teyitli      → strong
    kısmen teyitli     → partial
    iddia var, teyit yok → single
    iddia yok          → unverified (kesikli cetvel)

Kesin sayı **her zaman kartın metninde** yazılıdır ("6 iddiadan 5'i
teyitli"). Cetvel gestaltı taşır, metin olguyu; Spec §15 madde 13'ün
yasakladığı şey tek sayısal doğruluk skorudur ve burada öyle bir sayı
üretilmiyor.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from politikdesk.evidence.explain import KIND_LABELS
from politikdesk.users import current_user_id, touch_last_seen
from politikdesk.web import repository
from politikdesk.web.ui import (
    ACTIVITY_JS,
    button,
    esc,
    event_badge,
    filtered_empty_state,
    icon,
    kpi,
    page,
    page_head,
    panel,
    ruled,
    segment,
)
from politikdesk.web.ui import format as fmt

router = APIRouter(tags=["web"])

REFRESH_SECONDS = 30

# Salience şeffaflık popover'ı (F3-07). Anahtarlar `evidence/salience.py`
# çıktısındandır; etiketler Spec §8.4'ün bileşen adlarını Türkçeleştirir.
_COMPONENT_LABELS = {
    "independent_sources": "Bağımsız kaynak sayısı",
    "tier_weight": "Kaynak kalitesi (en iyi tier)",
    "velocity": "Yayılma hızı (ilk 60 dk)",
    "key_entity": "Anahtar varlık",
    "primary_source": "Birincil kaynak",
    "freshness": "Tazelik",
}

_PENALTY_LABELS = {
    "weak_evidence_and_stale": "Zayıf kanıt + bayatlama",
    "weak_evidence": "Zayıf kanıt",
    "stale": "Bayatlama",
}

# Filtreler URL'de tutulur (Bölüm 9.3) — yenilenince kaybolmaz, paylaşılabilir.
FILTERS: tuple[tuple[str, str], ...] = (
    ("all", "Tümü"),
    ("ready", "Yazıma hazır"),
    ("pending", "Teyit bekliyor"),
    ("review", "Denetimde"),
)


def _is_ready(row: dict[str, Any]) -> bool:
    """Üretim kapısının feed'den görülebilen iki koşulu (`guards.py`).

    Üçüncü koşul — isimli kişi hakkında doğrulanmamış iddia — NER verisi
    gerektirir ve 40 kart için N+1 sorgu demek olurdu. Bu yüzden kart
    "kanıta bağlı" der, "yazılabilir" demez; kesin karar olay sayfasında
    `service.can_generate` ile verilir ve buton oradan durum alır.
    """
    return bool(row.get("claim_count")) and bool(row.get("evidence_count"))


def _matches(row: dict[str, Any], selected: str) -> bool:
    if selected == "ready":
        return _is_ready(row)
    if selected == "pending":
        return bool(row.get("weak_claim_count")) or not row.get("claim_count")
    if selected == "review":
        return row.get("review_flag") == "needs_review"
    return True


def _evidence_tone(row: dict[str, Any]) -> str:
    """Kanıt cetvelinin durumu. Modül başlığındaki tabloyu uygular."""
    claims = int(row.get("claim_count") or 0)
    weak = int(row.get("weak_claim_count") or 0)
    if int(row.get("contradicted_count") or 0):
        return "contradicted"
    if not claims:
        return "unverified"
    if weak == 0:
        return "strongly_corroborated"
    if weak < claims:
        return "partially_corroborated"
    return "single_source"


def _breakdown_text(raw: dict[str, Any] | None) -> str:
    """`{'official':1,'media':3}` → `Resmî 1 · Medya 3`."""
    if not raw:
        return "kaynak kırılımı yok"
    return " · ".join(
        f"{KIND_LABELS.get(kind, kind)} {count}" for kind, count in sorted(raw.items()) if count
    )


def _evidence_line(row: dict[str, Any]) -> str:
    """Kanıt durumunun kesin ifadesi — cetvelin yanındaki OLGU."""
    claims = int(row.get("claim_count") or 0)
    weak = int(row.get("weak_claim_count") or 0)
    contra = int(row.get("contradicted_count") or 0)
    groups = int(row.get("independence_groups") or 0)

    # ⚠️ Ek uyumu (Ek B.3): sayıya EK GETİREN kalıp kurulmaz.
    # İlk sürüm `f"{n} iddiadan {m}'i teyitli"` yazıyordu ve m=2 için
    # "2'i teyitli" üretiyordu — doğrusu "2'si". Ek, sayının SON HECESİNE
    # göre değişir (1'i, 2'si, 3'ü, 5'i, 6'sı, 20'si…) ve bunu tabloyla
    # çözmek 10 satırlık bir kural motoru demek. Doğru çözüm kuralı
    # uygulamak değil, EKSİZ KALIP kurmaktır.
    parts: list[str] = []
    if not claims:
        parts.append("iddia çıkarılmadı")
    elif weak == 0:
        parts.append(f"{claims} iddia · tümü teyitli")
    else:
        parts.append(f"{claims} iddia · {claims - weak} teyitli")
    if contra:
        parts.append(f"{contra} çelişkili")
    if groups < 2:
        parts.append("tek yayın grubu")
    if row.get("review_flag") == "needs_review":
        parts.append("denetimde")
    return " · ".join(parts)


def _salience_panel(row: dict[str, Any]) -> str:
    """Skora tıklayınca açılan kırılım (F3-07).

    DoD'nin ikinci yarısı — "bu bir doğruluk skoru değildir" notu —
    kozmetik değil: Spec §15 madde 13 tek sayısal doğruluk yüzdesini
    yasaklar ve 0-100 arası bir skor, not olmadan öyle okunur.
    """
    breakdown = row.get("salience_breakdown") or {}
    components = breakdown.get("components") or {}

    rows = "".join(
        f"<tr><td>{esc(_COMPONENT_LABELS.get(key, key))}</td>"
        f"<td class='num mono'>{esc(fmt.number(float(value), 2))}</td></tr>"
        for key, value in sorted(components.items())
        if isinstance(value, int | float)
    )
    # Cezalar ayrı gösterilir: bir olayın skorunun NEDEN düştüğü, nasıl
    # yükseldiği kadar açıklanmalıdır (P4).
    rows += "".join(
        f"<tr><td>{esc(_PENALTY_LABELS.get(key, key))}</td>"
        f"<td class='num mono' style='color:var(--color-contra)'>"
        f"−{esc(fmt.number(float(value), 2))}</td></tr>"
        for key, value in sorted((breakdown.get("penalties") or {}).items())
        if isinstance(value, int | float)
    )

    body = f"""<table>
  <thead><tr><th>Bileşen</th><th class="num">Puan</th></tr></thead>
  <tbody>
  {rows or "<tr><td colspan='2' class='subtle'>Kırılım henüz hesaplanmadı.</td></tr>"}
  <tr><td><b>Global toplam</b> <span class="subtle">(0–90)</span></td>
      <td class="num mono"><b>{esc(fmt.number(row["global_salience"]))}</b></td></tr>
  <tr><td>Kişisel ayarlama <span class="subtle">(0–10, saklanmaz)</span></td>
      <td class="num mono">+{esc(fmt.number(row["personal_salience"]))}</td></tr>
  </tbody>
</table>
<p class="subtle" style="margin:12px 0 0;font-size:var(--text-xs)">
  Bu bir <b>önem</b> skorudur, <b>doğruluk skoru değildir.</b> Yüksek skor
  iddianın doğru olduğu anlamına gelmez; gündemde ne kadar yer tuttuğunu
  gösterir. Formül kural tabanlıdır ve beğeni/paylaşım gibi
  etkileşim girdisi içermez (Spec §8.4, §15 madde 14).</p>"""

    summary = (
        f"{icon('shield', 14)}<span>Önem "
        f'<b class="num">{esc(fmt.number(row["displayed_salience"]))}</b></span>'
        f'<span class="subtle">— kırılımı gör</span>'
    )
    return panel(summary, body, cls="quiet")


def _card(row: dict[str, Any]) -> str:
    """Gündem kartı — iki sütun: anlatı solda, KARAR sağda.

    Tek sütunlu ilk sürümde 1440px'te kartın sağ %45'i boştu ve her kartın
    "yazılabilir mi?" cevabı farklı bir x konumundaydı (metin uzunluğuna
    göre kayıyordu). Sağdaki sabit genişlikli sütun ikisini birden çözer:
    boşluk dolar ve **kullanıcı 40 kartı tek bir dikey çizgide tarar** —
    gözün yatay sıçraması ortadan kalkar. Bu sayfanın işi tarama, okuma
    değil (BRIEF `birincil_is`).
    """
    ready = _is_ready(row)
    verdict = (
        f'<span class="badge strong">{icon("check", 13)}kanıta bağlı</span>'
        if ready
        else f'<span class="badge neutral">{icon("clock", 13)}kanıt bekliyor</span>'
    )
    body = f"""
  <div class="feed-main">
    <div class="row" style="font-size:var(--text-xs);color:var(--color-fg-subtle)">
      {event_badge(row["status"])}
      <span>{esc(_breakdown_text(row.get("source_breakdown")))}</span>
      <span>· {esc(fmt.plural_count(int(row["article_count"] or 0), "makale"))}</span>
      <span>· {esc(fmt.plural_count(int(row["independent_count"] or 0), "bağımsız teyit"))}</span>
    </div>
    <h3 style="margin:8px 0 6px">
      <a class="plain" href="/event/{row["id"]}">{esc(row["title"])}</a></h3>
    <p class="claim-text" style="margin:0 0 10px;font-size:var(--text-sm);
       color:var(--color-fg-muted)">{esc(_evidence_line(row))}</p>
    {_salience_panel(row)}
  </div>
  <div class="feed-aside">
    {verdict}
    <span class="subtle" style="font-size:var(--text-xs)"
          title="{esc(fmt.precise(row["last_update_at"]))}">
      {esc(fmt.relative(row["last_update_at"]))}</span>
  </div>"""
    return ruled(_evidence_tone(row), f'<article class="card">{body}</article>', cls="feed-card")


def _summary_kpis(rows: list[dict[str, Any]]) -> str:
    """Sol üstteki cevap. Sıra hiyerarşiktir, alfabetik değil."""
    ready = sum(1 for row in rows if _is_ready(row))
    weak_claims = sum(int(row.get("weak_claim_count") or 0) for row in rows)
    lonely = sum(1 for row in rows if int(row.get("independence_groups") or 0) < 2)
    in_review = sum(1 for row in rows if row.get("review_flag") == "needs_review")

    return f"""<div class="kpis" style="margin-bottom:var(--space-6)">
{kpi("Yazıma hazır", fmt.number(ready), unit="olay", icon_name="shield")}
{kpi("Teyit bekleyen", fmt.number(weak_claims), unit="iddia", icon_name="clock")}
{kpi("Tek yayın grubu", fmt.number(lonely), unit="olay", icon_name="warning")}
{kpi("Denetimde", fmt.number(in_review), unit="olay", icon_name="review")}
</div>"""


def _strip(summary: dict[str, Any]) -> str:
    """ "Sen yokken ne oldu" şeridi (F3-18) — tek satır."""
    from politikdesk.web.ui import notice

    if not summary.get("available"):
        return notice(
            "<p><b>İlk ziyaretin.</b> Gündem salience sırasına göre dizilidir; "
            "skor önemi gösterir, doğruluğu değil.</p>"
        )
    total = summary.get("total", 0)
    if not total:
        return notice("<p>Son ziyaretinden bu yana yeni olay yok.</p>")

    top = summary.get("top_title")
    tail = f" En önemlisi: <b>{esc(top)}</b>." if top else ""
    return notice(
        f"<p>Sen yokken <b>{fmt.number(total)}</b> yeni olay eklendi, "
        f"<b>{fmt.number(summary.get('important', 0))}</b> tanesi önemli.{tail}</p>"
    )


def _cards_html(rows: list[dict[str, Any]], selected: str) -> str:
    """Kart listesi. `rows` çağıran taraftan gelir — sayfa ve KPI'lar aynı
    sorguyu paylaşır, iki kez çalıştırmaz (G3 #7: p95 < 1,5 sn)."""
    if not rows:
        # Boş durum (10.1) — bir davettir, hata değil.
        from politikdesk.web.ui import empty_state

        return empty_state(
            "Henüz olay yok",
            "Boru hattı her 5 dakikada bir toplar. İlk turu hemen çalıştırmak "
            "için terminalde `pd ingest` yaz; ardından `pd cluster` ile "
            "haberler olaya dönüşür.",
            action=button("Boru hattını gör", href="/admin/", variant="primary"),
        )

    visible = [row for row in rows if _matches(row, selected)]
    if not visible:
        # Filtre-boş (10.2) — 10.1 ile AYNI YAPILMAZ. Kullanıcı hangi
        # durumda olduğunu bilmeli: veri mi yok, filtresi mi tutmadı?
        label = dict(FILTERS).get(selected, selected)
        return filtered_empty_state(
            f"“{label}” filtresi {fmt.plural_count(len(rows), 'olayın')} hiçbiriyle "
            f"eşleşmedi. Gündem dolu — bu filtre şu an boş.",
            "/feed",
        )
    return "".join(_card(row) for row in visible)


@router.get("/", response_class=HTMLResponse)
@router.get("/feed", response_class=HTMLResponse)
def feed_page(
    limit: int = Query(default=40, ge=1, le=200),
    f: str = Query(default="all"),
) -> str:
    selected = f if f in dict(FILTERS) else "all"
    user_id = current_user_id()
    previous_visit = touch_last_seen(user_id)
    summary = repository.since_last_visit(user_id, previous_visit)
    rows = repository.feed(user_id, limit=limit)

    counts = {key: sum(1 for row in rows if _matches(row, key)) for key, _ in FILTERS}
    tabs = segment(
        tuple(
            (
                f"{label} · {fmt.number(counts[key])}",
                f"/feed?f={key}" + (f"&limit={limit}" if limit != 40 else ""),
                key == selected,
            )
            for key, label in FILTERS
        )
    )

    body = f"""
{
        page_head(
            "Gündem",
            lede="Makro ekonomi olayları, önem sırasıyla. Kanıt gücü her kartın sol "
            "kenarındaki cetvelde okunur.",
            actions=button("Yenile", icon_name="refresh", onclick="pdRefresh()"),
        )
    }
<div class="stack">
  {_strip(summary)}
  {_summary_kpis(rows)}
  <div class="row">
    {tabs}
    <span class="spacer subtle" style="font-size:var(--text-xs)"
          id="pd-refreshed" aria-live="polite">
      {esc(fmt.plural_count(REFRESH_SECONDS, "saniyede"))} bir sessizce yenilenir</span>
  </div>
  <div id="cards" class="stack-sm">{_cards_html(rows, selected)}</div>
</div>
"""

    js = (
        ACTIVITY_JS
        + f"""
var PD_URL = '/feed/cards?limit={limit}&f={selected}';

async function pdRefresh(){{
  var box = document.getElementById('cards');
  var note = document.getElementById('pd-refreshed');
  try {{
    var r = await fetch(PD_URL);
    if (!r.ok) throw new Error(r.status);
    // Sessiz yenileme: açık paneller korunur, sayfa kaymaz.
    var open = new Set([...box.querySelectorAll('details[open]')]
                       .map(function(d){{ return d.closest('article')
                              .querySelector('a').getAttribute('href'); }}));
    box.innerHTML = await r.text();
    box.querySelectorAll('article').forEach(function(a){{
      var link = a.querySelector('a');
      var panel = a.querySelector('details');
      if (link && panel && open.has(link.getAttribute('href'))) panel.open = true;
    }});
    note.textContent = new Date().toLocaleTimeString('tr-TR') + ' güncellendi';
  }} catch (e) {{
    // Ağ hatası sayfayı BOZMAZ: mevcut kartlar yerinde kalır, yalnızca
    // durum satırı söyler. Listeyi silip hata basmak, çalışan bir ekranı
    // geçici bir ağ kesintisi için boşaltmak olurdu.
    note.textContent = 'Yenilenemedi — bağlantı yok. Kartlar son hâliyle duruyor.';
  }}
}}

setInterval(function(){{ if (!document.hidden) pdRefresh(); }},
            {REFRESH_SECONDS * 1000});
"""
    )
    return page("Gündem", body, active="/feed", crumbs=(("Gündem", None),), extra_js=js)


@router.get("/feed/cards", response_class=HTMLResponse)
def feed_cards(
    limit: int = Query(default=40, ge=1, le=200),
    f: str = Query(default="all"),
) -> str:
    """Sessiz yenilemenin çektiği parça (tam sayfa değil)."""
    selected = f if f in dict(FILTERS) else "all"
    return _cards_html(repository.feed(current_user_id(), limit=limit), selected)
