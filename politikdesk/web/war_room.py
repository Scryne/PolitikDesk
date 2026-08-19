"""Kumanda Odası — canlı sinyal yüzeyi (Roadmap Faz 8.1, "War Room 2.0").

### Bu sayfanın tek işi (BRIEF `birincil_is`)

> "Olağandışı olan ne var — ve sırada ne var?"

Bu, `/feed`'in sorusu DEĞİLDİR ve olmaması bu ekranın var olma sebebidir.
Gündem masası "şu an ne var, hangisi hakkında güvenle yazabilirim" diye
sorar; orada birincil nesne **olay**tır. Burada birincil nesne
**beklentiden sapma**dır: eşiği aşan bir gösterge, gelmeyen bir resmî
yayın, susmuş bir kaynak.

Roadmap'in ilk sürümünde bu ekran bir haber listesiydi ve maddenin
kendisi bunu kusur olarak yazıyordu: *"War Room sadece haber listesi
olmaktan çıkarılmalı."* Olay listesi kaldırılmadı ama **ikinci sıraya**
indi; ilk sırada sapma ve sessizlik var.

### Roadmap'in altı hücresi ve buradaki karşılıkları

    Indicators       → gösterge şeridi + `_anomaly_panel`
    Emerging Events  → `_emerging_events`
    Claims           → `_claims_panel`
    Source Health    → `_source_health_panel`
    Relations        → `_relations_panel`   (ADR-010 kapısına tabi)
    Expected Events  → `_expected_publications`

Altısı **eşit altı kutu olarak dizilmedi.** Eşit ızgara, DESIGN.md
Bölüm 13.6'nın "bu kararı herhangi bir panel için de verir miydim?"
sorusuna "evet" cevabı verir. Sol sütun okunacak (derinlik ister), sağ
sütun taranacak (tek bakışta biter) şeyleri taşır.

### Signature öğe: "Olmayanlar"

Panellerin neredeyse tamamı OLANI gösterir. Bu ürünün farkı beklentiyi
bilmesidir: kurum ne zaman yayımlayacağını önceden ilan eder, kaynak
her N dakikada bir veri vermelidir. Gelmeyeni ayrı ve görünür bir
blokta toplamak, başka hiçbir panelin söylemediği şeyi söyler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

if TYPE_CHECKING:  # yalnızca tip için — çalışma zamanında içe aktarılmaz
    from politikdesk.analysis.expected_events import ExpectationSignal
    from politikdesk.ingestion.source_quality import QualityComponent, SourceQuality

from politikdesk.observability import get_logger
from politikdesk.users import current_user_id
from politikdesk.web import repository
from politikdesk.web.ui import format as fmt
from politikdesk.web.ui import keys
from politikdesk.web.ui.charts import economic_indicator_card
from politikdesk.web.ui.components import (
    card,
    distribution,
    esc,
    event_badge,
    kpi,
    page_head,
    status_badge,
)
from politikdesk.web.ui.icons import icon
from politikdesk.web.ui.shell import ACTIVITY_JS, page

log = get_logger(__name__)
router = APIRouter(tags=["war_room"])

# Bir olayın "yükselen" sayılması için gereken gündem skoru.
#
# ⛔ Bu bir DOĞRULUK eşiği değildir (Spec §15/13). Skor olayın kaç
# kaynakta, ne hızda ve ne genişlikte yayıldığını ölçer; iddiaların
# doğru olup olmadığı hakkında hiçbir şey söylemez.
RISING_THRESHOLD = 55

# Kaç saat ilerisi "sırada" sayılır. 48 saat, bir sonraki iş gününü de
# kapsayan en kısa penceredir: cuma akşamı bakan biri pazartesi sabahını
# görebilmeli.
HORIZON_HOURS = 48


def _war_room_js() -> str:
    return """
(function(){
  if (!window.EventSource) return;
  try {
    var sseSource = new EventSource('/api/events/stream');
    sseSource.addEventListener('event_updated', function(e){
      var data = JSON.parse(e.data || '{}');
      if (!data || !data.title) return;
      window.pdToast('Yeni gelişme: ' + data.title);
      var dot = document.getElementById('wr-live-dot');
      if (dot) {
        dot.classList.add('flash');
        setTimeout(function(){ dot.classList.remove('flash'); }, 2000);
      }
    });
  } catch (err) {}
})();
"""


# ═══════════════════════════════════════════════ veri toplayıcılar
#
# Her biri kendi hatasını yutar ve BOŞ döner. Gerekçe: bu ekran yedi
# ayrı alt sisteme bakıyor; birinin düşmesi sayfanın tamamını götürürse
# kullanıcı en çok ihtiyaç duyduğu anda hiçbir şey göremez (Bölüm 10.4:
# "kısmi hata: yalnızca o widget hata gösterir, sayfa çökmez").


def _safe(name: str, fn: Any, default: Any) -> Any:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        log.warning("war_room_panel_failed", panel=name, error=str(exc))
        return default


# ═══════════════════════════════════════════════ Indicators


def _indicator_strip() -> str:
    """Makro gösterge şeridi — **yalnızca kurumun kendi yayımladığı sayı.**

    ⛔ Buradaki sayılar bir dönem koda gömülüydü ve TÜİK/TCMB/Hazine
    imzasıyla gösteriliyordu. Ürünün sözleşmesi (Spec §15/13) kanıtta
    bulunmayan sayıyı yasaklar; kurum imzalı uydurma sayı bunun en ağır
    biçimiydi. Artık tek kaynak `articles.official_value`'dur.

    Veri yoksa **hiçbir sayı üretilmez**: boş durum, boru hattının
    henüz resmî bir sayısal yayın toplamadığını açıkça söyler.
    """
    series = _safe("indicators", repository.official_indicator_series, [])

    if not series:
        return (
            '<div class="notice">'
            f'<span class="ic">{icon("info", 16)}</span>'
            "<div><p><b>Resmî gösterge yayını beklemede.</b> Bu şerit yalnızca "
            "kurumun kendi makine okunur yayınından gelen sayıları gösterir "
            "(TÜİK SDMX, TCMB EVDS gibi). Boru hattı henüz böyle bir yayım "
            "toplamadı; tahmini veya örnek sayı gösterilmez.</p></div></div>"
        )

    cards = []
    for entry in series[:6]:
        history = [float(v) for v in entry["history"]]
        unit = str(entry.get("unit") or "")
        latest = float(entry["latest_value"])
        previous = entry.get("previous_value")

        value_text = fmt.percent(latest, 1) if unit == "%" else fmt.number(latest, 1)

        if previous is None:
            change_text = f"{fmt.period_label(entry.get('latest_period'))} · ilk gözlem"
        else:
            delta = latest - float(previous)
            delta_text = fmt.signed_percent(delta, 1) if unit == "%" else fmt.number(delta, 1)
            change_text = f"{fmt.period_label(entry.get('latest_period'))} · {delta_text}"

        # Kaynağın kendi seri adı varsa o gösterilir ("ABD doları alış
        # kuru"); yoksa metrik anahtarı Türkçeye çevrilir. Ham anahtar
        # ("exchange_rate") hiçbir koşulda ekrana çıkmaz.
        baslik = entry.get("label") or fmt.metric_label(entry.get("metric"))

        cards.append(
            economic_indicator_card(
                str(baslik),
                value_text,
                "" if unit == "%" else unit,
                history,
                change_text,
                source_name=str(entry.get("source_name") or ""),
            )
        )

    # Izgara DEĞİL esnek satır. `auto-fit` ile 6 kart 4 sütuna dizildiğinde
    # ikinci satırda 2 kart kalıyor ve sağda kart genişliğinde ölü alan
    # oluşuyordu (Bölüm 13.3: "amaçsız devasa boşluk"). Flex sarmasında
    # son satırdaki kartlar büyüyüp satırı doldurur; kart sayısı ile sütun
    # sayısının tutması gerekmez.
    return (
        '<div class="indicator-strip">' + "".join(cards) + "</div>"
        '<p class="subtle" style="margin:var(--space-3) 0 0;font-size:var(--text-xs)">'
        "Bu şerit yalnızca kurumun kendi makine okunur yayınından gelen değerleri "
        "gösterir; türetilmiş veya tahmini sayı içermez.</p>"
    )


def _anomaly_panel(kayitlar: list[dict[str, Any]]) -> str:
    """GÖSTERGE SAPMALARI (Roadmap Faz 3.1).

    ⛔ Bir anomali bir YORUM DEĞİLDİR. Kart yalnızca ölçümü gösterir:
    hangi seri, hangi dönem, ne kadar saptı, hangi yöntem, hangi eşik.
    "Sebebi şu" demez ve demeyecek — nedensellik kanıt ister.
    """
    if not kayitlar:
        return card(
            '<p class="subtle" style="margin:0;font-size:var(--text-sm)">'
            "İzlenen resmî göstergelerde açık sapma yok.</p>"
            '<p class="subtle" style="margin:var(--space-2) 0 0;font-size:var(--text-xs)">'
            "Sapma yokluğu doğruluk kanıtı değildir; yalnızca eşiğin "
            "aşılmadığını söyler.</p>",
            title="Gösterge sapmaları",
        )

    tonlar = {"critical": "bad", "high": "bad", "medium": "warn", "low": ""}
    satirlar = []
    for k in kayitlar:
        ton = tonlar.get(str(k["severity"]), "")
        birim = f" {k['unit']}" if k.get("unit") else ""
        oran = k.get("deviation_ratio")
        satirlar.append(
            f'<div class="signal-row">'
            f'<div class="row tight" style="justify-content:space-between;align-items:baseline">'
            f'<span style="font-size:var(--text-sm);font-weight:var(--weight-semibold)">'
            f"{esc(k['label'])}</span>"
            f'<span class="badge sm {ton}">sapma · {esc(str(k["severity"]))}</span></div>'
            f'<div class="mono" style="font-size:var(--text-xs);margin-top:2px">'
            f"{esc(fmt.period_label(k['period']))} · "
            f"{esc(fmt.number(float(k['observed_value']), 2))}{esc(birim)}"
            + (f" · {oran:+.1f}σ" if oran is not None else "")
            + "</div>"
            f'<div class="subtle" style="font-size:var(--text-xs)">'
            f"{esc(k['source_name'])} · {esc(k['series_code'])} · "
            f"yöntem {esc(k['detection_method'])}, eşik {esc(str(k['threshold']))}, "
            f"{esc(fmt.plural_count(int(k['baseline_size']), 'gözlem'))}</div>"
            f"</div>"
        )

    return card(
        "".join(satirlar)
        + '<p class="subtle" style="margin:var(--space-4) 0 0;font-size:var(--text-xs)">'
        "Sapma bir <b>ölçümdür</b>, yorum değil: bir gözlemin kendi geçmişine "
        "göre eşiği aştığını söyler. Sebebi hakkında hiçbir iddiada bulunmaz — "
        "nedensellik kanıt ister.</p>",
        title="Gösterge sapmaları",
        actions=f'<span class="subtle" style="font-size:var(--text-xs)">'
        f"{fmt.plural_count(len(kayitlar), 'açık sapma')}</span>",
    )


# ═══════════════════════════════════════════════ Emerging Events


def _emerging_events(events: list[dict[str, Any]]) -> str:
    """Gündem skoruna göre yükselen olaylar.

    `/feed`'in kopyası değil: orada olaylar okunmak ve hakkında
    yazılmak için durur, burada **yükseliyor olmaları** için durur.
    Bu yüzden sütunlar farklı — bağımsız grup sayısı burada birinci
    sınıf bir sütundur (Roadmap 2.2: "12 kaynak doğruladı" ile
    "4 bağımsız grup doğruladı" ayrılmalı).
    """
    if not events:
        from politikdesk.web.ui import empty_state

        return card(
            empty_state(
                "Henüz olay yok",
                "Boru hattı her 5 dakikada bir toplar. İlk turu hemen "
                "çalıştırmak için terminalde `pd ingest` yazın.",
            ),
            title="Yükselen olaylar",
        )

    yukselen = [e for e in events if (e.get("salience_score") or 0) >= RISING_THRESHOLD]
    gosterilecek = (yukselen or events)[:12]

    satirlar = []
    for ev in gosterilecek:
        sal = int(ev.get("salience_score") or 0)
        bagimsiz = int(ev.get("independent_count") or 0)
        satirlar.append(
            f"<tr>"
            f'<td class="num mono" data-label="Önem" '
            f'style="width:52px;color:var(--color-accent);'
            f'font-weight:var(--weight-semibold)">{sal}</td>'
            f'<td data-label="Olay">'
            f'<a href="/event/{int(ev["id"])}" class="plain" '
            f'style="font-weight:var(--weight-medium)">{esc(ev["title"])}</a>'
            f'<div class="subtle" style="font-size:var(--text-xs);margin-top:2px">'
            f"{esc(fmt.plural_count(int(ev.get('article_count') or 0), 'kaynak'))} · "
            f"{bagimsiz} bağımsız grup · "
            f"{esc(fmt.plural_count(int(ev.get('claim_count') or 0), 'iddia'))}</div></td>"
            f'<td data-label="Kanıt">{status_badge(ev.get("top_claim_status", "unverified"))}</td>'
            f'<td data-label="Aşama">{event_badge(ev.get("status", "developing"))}</td>'
            f"</tr>"
        )

    baslik = (
        f"{fmt.plural_count(len(yukselen), 'olay')} · önem {RISING_THRESHOLD}+"
        if yukselen
        else f"{RISING_THRESHOLD}+ eşiğini aşan olay yok — en güncel {len(gosterilecek)}"
    )

    return card(
        '<div class="table-wrap"><table class="table-cards"><thead><tr>'
        '<th class="num">Önem</th><th>Olay</th><th>Kanıt</th><th>Aşama</th>'
        "</tr></thead><tbody>" + "".join(satirlar) + "</tbody></table></div>"
        '<p class="subtle" style="margin:var(--space-3) 0 0;font-size:var(--text-xs)">'
        "Önem skoru bir <b>doğruluk</b> ölçüsü değildir: yayılma hızını ve "
        "genişliğini ölçer, iddiaların doğruluğunu değil.</p>",
        title="Yükselen olaylar",
        actions=f'<span class="subtle" style="font-size:var(--text-xs)">{esc(baslik)}</span>',
    )


# ═══════════════════════════════════════════════ Claims


def _claims_panel(dagilim: list[tuple[str, int]]) -> str:
    """İddia kanıt durumunun dağılımı (Roadmap Faz 5.1 · 8.1 "Claims").

    Tek tek iddia listelemek yerine DAĞILIM gösterilir. Gerekçe: bu
    ekranın sorusu "hangi iddia" değil, "iddia külliyatı ne durumda".
    Tek tek iddia okunacak yer olay sayfasıdır, çünkü orada iddia
    kanıtıyla birlikte durur — bu üründe iddia kanıtından ayrı
    gösterilmez.

    ⛔ `contradicted` her zaman sıfırdır ve bu bir veri bulgusu DEĞİL,
    bilinen bir boşluktur (ADR-008: karşı kanıt yolu yok). Sıfırı
    açıklamadan göstermek "hiç çelişki yok" diye okunur — ürünün
    verebileceği en yanıltıcı sinyallerden biri.
    """
    from politikdesk.web.ui.components import STATUS_LABELS

    toplam = sum(n for _, n in dagilim)
    if not toplam:
        return card(
            '<p class="subtle" style="margin:0;font-size:var(--text-sm)">'
            "Son 7 günde işlenmiş iddia yok.</p>",
            title="İddia kanıt durumu",
        )

    satirlar = [
        (
            STATUS_LABELS.get(durum, durum),
            float(n),
            f"{fmt.number(n)} · {fmt.percent(n / toplam * 100, 1)}",
        )
        for durum, n in dagilim
    ]

    tek_kaynakli = dict(dagilim).get("single_source", 0)
    oran = tek_kaynakli / toplam * 100

    return card(
        distribution(satirlar)
        + f'<p style="margin:var(--space-4) 0 0;font-size:var(--text-sm)">'
        f"<b>{esc(fmt.percent(oran, 0))}</b> tek kaynaklı — ikinci bir bağımsız "
        f"kaynak beklemekte.</p>"
        '<p class="subtle" style="margin:var(--space-2) 0 0;font-size:var(--text-xs)">'
        "<b>“Çelişkili” her zaman sıfırdır ve bu bir bulgu değildir:</b> karşı "
        "kanıt yolu henüz kurulmadı (ADR-008). Sıfırı “hiç çelişki yok” diye "
        "okumayın.</p>",
        title="İddia kanıt durumu",
        actions=f'<span class="subtle" style="font-size:var(--text-xs)">'
        f"{fmt.plural_count(toplam, 'iddia')} · 7 gün</span>",
    )


# ═══════════════════════════════════════════════ Source Health


def _source_health_panel(
    bakim: list[tuple[SourceQuality, list[QualityComponent]]],
    susan_slug: set[str],
) -> str:
    """Bakım isteyen kaynaklar (Roadmap Faz 2.1/2.3 · 8.1 "Source Health").

    ⛔ Buradaki skor bir GÜVENİLİRLİK yargısı değildir. Kaynağın
    haberciliği hakkında hiçbir şey söylemez; yalnızca akışın teknik
    sağlığını ölçer (Spec §8.5).

    ⛔ Yapısal özellik alarm üretmez. Bir kaynağın Tier 4 olması bakım
    istemez; 6 saattir veri vermemesi ister. Bu ayrımı `needs_attention`
    yapıyor — ilk uygulama 24 sosyal kaynağı "sosyal oldukları için"
    işaretliyordu ve o liste kimsenin bakmadığı bir liste olmuştu.

    **Susan kaynaklar burada TEKRAR EDİLMEZ.** Onlar "Olmayanlar"
    panelinde, kendi bağlamlarında duruyor; ikisi de en zayıf bileşene
    göre sıralandığı için aynı dört kaynak ekranda iki kez çıkıyordu ve
    bu panel pratikte diğerinin kopyası oluyordu. Ayırınca panel asıl
    işini yapıyor: veri GELEN ama başarısızlık veya verim sorunu olan
    kaynakları göstermek.
    """
    kalanlar = [(k, s) for k, s in bakim if k.slug not in susan_slug]

    if not kalanlar:
        return card(
            '<p class="subtle" style="margin:0;font-size:var(--text-sm)">'
            "Veri akan kaynaklarda eşiğin altına düşen işletimsel bileşen yok."
            + (
                " Susmuş kaynaklar “Olmayanlar” panelinde."
                if susan_slug
                else ""
            )
            + "</p>",
            title="Kaynak sağlığı",
        )

    satirlar = []
    for kalite, sebepler in kalanlar[:5]:
        sebep_metni = " · ".join(f"{c.label}: {c.detail}" for c in sebepler)
        # Rozet EN ZAYIF bileşenin adıdır, `coverage` değil. Önceki hâli
        # "5/6 bileşen" yazıyordu ve bu skorun kaç bileşene dayandığını
        # söyleyen bir sayıdır — ama bu panel skoru hiç göstermiyor, yani
        # rozet hiçbir soruya cevap vermiyordu. Bileşen adı ise doğrudan
        # eylem söyler: "tazelik" başka bir iş, "çekim başarısı" başka.
        en_zayif = min(sebepler, key=lambda c: float(c.value or 0))
        satirlar.append(
            f'<div class="signal-row">'
            f'<div class="row tight" style="justify-content:space-between;align-items:baseline">'
            f'<span style="font-size:var(--text-sm);font-weight:var(--weight-medium)">'
            f"{esc(kalite.name)}</span>"
            f'<span class="badge sm warn">{esc(en_zayif.label.lower())}</span></div>'
            f'<div class="subtle" style="font-size:var(--text-xs);margin-top:2px">'
            f"{esc(sebep_metni)}</div>"
            f"</div>"
        )

    kalan = len(kalanlar) - len(satirlar)
    kuyruk = (
        f'<p class="subtle" style="margin:var(--space-3) 0 0;font-size:var(--text-xs)">'
        f"{fmt.plural_count(kalan, 'kaynak daha')} eşiğin altında.</p>"
        if kalan > 0
        else ""
    )

    return card(
        "".join(satirlar)
        + kuyruk
        + '<p class="subtle" style="margin:var(--space-2) 0 0;font-size:var(--text-xs)">'
        "Bu ölçüm akışın <b>teknik</b> sağlığıdır; kaynağın haberciliği "
        "hakkında hiçbir şey söylemez.</p>",
        title="Kaynak sağlığı",
        actions=f'<span class="subtle" style="font-size:var(--text-xs)">'
        f"{fmt.plural_count(len(kalanlar), 'kaynak')}</span>",
    )


# ═══════════════════════════════════════════════ Relations


def _relations_panel(ozet: dict[str, Any] | None) -> str:
    """Söylem değişiklikleri (Roadmap Faz 4.1 · 8.1 "Relations").

    ⛔ ADR-010: yayın kapısı KAPALI. Dedektör kayıt üretiyor ama
    ürettiği kayıtlar denetlendiğinde yanlış siyasi isnat çıkardığı
    görüldü (konu eşleştirmesi yok, güven skoru sabit 0,85, aktör
    alanına sözcük parçaları sızmış).

    Bu panelin varlık sebebi tam olarak budur: kapalı kapıyı **boş bir
    panel** olarak göstermek, "hiç kayma bulunmadı" diye okunurdu.
    `shift_store.summary()` bilerek kapının ötesinden okur ve
    `withheld` sayısını ayrı raporlar — ölçülemedi ≠ sıfır.
    """
    from politikdesk.political_memory import shift_store

    if shift_store.PUBLISH_GATE_OPEN:
        acik = int((ozet or {}).get("total", 0))
        return card(
            f'<p style="margin:0;font-size:var(--text-sm)">'
            f"{esc(fmt.plural_count(acik, 'açık söylem değişikliği'))} kayıtlı.</p>"
            '<p class="subtle" style="margin:var(--space-2) 0 0;font-size:var(--text-xs)">'
            '<a href="/memory">Siyasi Hafıza</a> ekranında aktör bazında incelenir.</p>',
            title="Söylem değişiklikleri",
        )

    cekilen = int((ozet or {}).get("withheld", 0))
    return card(
        '<div class="notice warn" style="margin:0">'
        f'<span class="ic">{icon("warning", 16)}</span>'
        "<div><p><b>Yayın kapısı kapalı.</b> Söylem değişikliği dedektörü "
        f"çalışıyor ve {esc(fmt.plural_count(cekilen, 'kayıt'))} üretti, ama "
        "bu kayıtlar denetlendiğinde yanlış siyasi isnat ürettiği görüldü: "
        "konu eşleştirmesi yok ve güven skoru sabit.</p>"
        "<p>Kayıtlar silinmedi — dedektör düzeltildiğinde aynı veriyle "
        "yeniden ölçülebilsin diye saklanıyor. Okuma yolundan geçmiyor.</p>"
        "</div></div>"
        '<p class="subtle" style="margin:var(--space-3) 0 0;font-size:var(--text-xs)">'
        "Bu sayı <b>bulunan kayma sayısı değildir</b>; yayına uygun "
        "bulunmayan kayıt sayısıdır. Kapının açılma şartları ADR-010 §5'te.</p>",
        title="Söylem değişiklikleri",
        actions='<span class="badge sm warn">yayından çekildi</span>',
    )


# ═══════════════════════════════════════════════ Expected Events


def _expected_publications(bekleyen: list[ExpectationSignal]) -> str:
    """BEKLENEN RESMÎ YAYINLAR (Spec §9.5 · Roadmap Faz 1.2 / 3.2).

    Kaynak Ulusal Veri Yayımlama Takvimi'dir — kurumların kendi ilan
    ettiği program, tahmin değil. Ürünün "olacağı da bilmek" katmanı.
    """
    if not bekleyen:
        return card(
            '<p class="subtle" style="margin:0;font-size:var(--text-sm)">'
            f"Önümüzdeki {HORIZON_HOURS} saatte takvimde resmî yayın görünmüyor.</p>",
            title="Beklenen resmî yayınlar",
        )

    satirlar = []
    for sinyal in bekleyen[:6]:
        # SPK ve BDDK başlıkları 150 karakteri geçebiliyor ("Emeklilik ve
        # Menkul Kıymet Yatırım Fonlarının Katılma Paylarına İlişkin…").
        # Yan sütun TARANAN bir sütundur; dört satıra yayılan bir başlık
        # onu okunan sütuna çevirir. Tam metin `title`'da durur, yani
        # kısaltma bilgi kaybı değildir.
        tam = " ".join(str(sinyal.title).split())
        kisa = fmt.shorten(tam, 64)
        donem = (
            f'<div class="subtle" style="font-size:var(--text-xs)">'
            f"{esc(fmt.period_label(sinyal.reference_period))}</div>"
            if sinyal.reference_period
            else ""
        )
        satirlar.append(
            f'<div class="signal-row">'
            f'<div class="row tight" style="justify-content:space-between;align-items:baseline">'
            f'<span class="mono" style="font-size:var(--text-xs);color:var(--color-accent)">'
            f"{esc(fmt.date_time(sinyal.expected_at))}</span>"
            f'<span class="badge sm">{esc(sinyal.institution or "")}</span></div>'
            f'<div style="font-size:var(--text-sm);margin-top:2px" title="{esc(tam)}">'
            f"{esc(kisa)}</div>"
            f"{donem}</div>"
        )

    kalan = len(bekleyen) - len(satirlar)
    kuyruk = (
        f'<p class="subtle" style="margin:var(--space-3) 0 0;font-size:var(--text-xs)">'
        f'{fmt.plural_count(kalan, "yayın daha")} takvimde — '
        f'<a href="/admin/calendar/">tümünü gör</a>.</p>'
        if kalan > 0
        else ""
    )

    return card(
        "".join(satirlar) + kuyruk,
        title="Beklenen resmî yayınlar",
        actions=f'<span class="subtle" style="font-size:var(--text-xs)">'
        f"{fmt.plural_count(len(bekleyen), 'yayın')} · {HORIZON_HOURS} saat</span>",
    )


# ═══════════════════════════════════════════════ SIGNATURE: Olmayanlar


def _absent_panel(
    geciken: list[ExpectationSignal],
    kacirilan: list[ExpectationSignal],
    susan: list[tuple[SourceQuality, QualityComponent]],
) -> str:
    """Beklenip GELMEYEN şeyler — bu ekranın imza öğesi.

    Üç ayrı sessizlik türü tek blokta toplanır, çünkü kullanıcı
    açısından üçü de aynı soruyu doğurur: *"bir şeyi kaçırıyor muyum?"*

        geciken    → kurum ilan ettiği saatte yayımlamadı
        kaçırılan  → kurum yayımladı, hiçbir kaynağımız haberleştirmedi
        susan      → kaynak tazelik bütçesini aştı, hiç veri gelmiyor

    İkincisi en rahatsız edicisidir ve tam da bu yüzden değerlidir:
    kaynak kadrosundaki kör noktayı başka hiçbir gösterge bu kadar
    doğrudan söylemez.

    Boş durum bir başarı bildirimidir, bir hata değil — ama "her şey
    yolunda" DEMEZ: yalnızca bu üç ölçümde boşluk olmadığını söyler.
    """
    bloklar: list[str] = []

    def _blok(baslik: str, ton: str, maddeler: list[str], not_: str) -> str:
        return (
            f'<div style="margin-bottom:var(--space-4)">'
            f'<p class="eyebrow" style="margin:0 0 var(--space-2);color:var(--color-{ton})">'
            f"{esc(baslik)}</p>"
            f'<ul style="margin:0;padding-left:18px;font-size:var(--text-sm);'
            f'line-height:1.6">{"".join(maddeler)}</ul>'
            f'<p class="subtle" style="margin:var(--space-2) 0 0;font-size:var(--text-xs)">'
            f"{not_}</p></div>"
        )

    if geciken:
        bloklar.append(
            _blok(
                f"Gecikti — {fmt.plural_count(len(geciken), 'yayın')}",
                "partial",
                [
                    f"<li>{esc(s.institution or '')} — {esc(s.title[:70])} "
                    f'<span class="subtle">({esc(fmt.relative(s.expected_at))} '
                    f"bekleniyordu)</span></li>"
                    for s in geciken[:4]
                ],
                "Kurum kendi ilan ettiği saatte yayımlamadı.",
            )
        )

    if kacirilan:
        bloklar.append(
            _blok(
                f"Yayımlandı, biz görmedik — {fmt.plural_count(len(kacirilan), 'yayın')}",
                "contra",
                [
                    f"<li>{esc(s.institution or '')} — {esc(s.title[:70])}</li>"
                    for s in kacirilan[:4]
                ],
                "Kurum yayımladı ama hiçbir kaynağımız haberleştirmedi — "
                "kaynak kadrosunda kör nokta olabilir.",
            )
        )

    if susan:
        bloklar.append(
            _blok(
                f"Susan kaynak — {fmt.plural_count(len(susan), 'kaynak')}",
                "partial",
                [
                    f"<li>{esc(kalite.name)} "
                    f'<span class="subtle">({esc(sebep.detail)})</span></li>'
                    for kalite, sebep in susan[:4]
                ],
                "Tazelik bütçesi aşıldı; bu kaynaktan veri gelmiyor.",
            )
        )

    if not bloklar:
        govde = (
            '<p style="margin:0;font-size:var(--text-sm)">Beklenip gelmeyen bir şey yok: '
            "takvimdeki yayınlar zamanında geldi, yayımlanan her şey akışa girdi ve "
            "hiçbir kaynak tazelik bütçesini aşmadı.</p>"
            '<p class="subtle" style="margin:var(--space-2) 0 0;font-size:var(--text-xs)">'
            "Bu, “her şey yolunda” demek değildir — yalnızca bu üç ölçümde boşluk "
            "olmadığını söyler.</p>"
        )
    else:
        govde = "".join(bloklar).rstrip()

    return card(
        govde,
        cls="absent",
        title="Olmayanlar",
        actions='<span class="subtle" style="font-size:var(--text-xs)">'
        "beklenip gelmeyenler</span>",
    )


# ═══════════════════════════════════════════════════════════ sayfa


@router.get("/war-room", response_class=HTMLResponse)
@router.get("/radar", response_class=HTMLResponse, include_in_schema=False)
def war_room_page() -> str:
    """Canlı sinyal yüzeyi."""
    from politikdesk.analysis import expected_events
    from politikdesk.analysis.pipeline import open_anomalies
    from politikdesk.ingestion import source_quality
    from politikdesk.political_memory import shift_store

    user_id = current_user_id()

    events = _safe("feed", lambda: repository.feed(user_id=user_id, limit=30), [])
    sapmalar = _safe("anomalies", lambda: open_anomalies(limit=6), [])
    bekleyen = _safe(
        "expected", lambda: expected_events.upcoming(hours=HORIZON_HOURS, limit=8), []
    )
    geciken = _safe("delayed", lambda: expected_events.delayed(limit=8), [])
    # `official_calendar.missed_report` aynı bilgiyi sözlük olarak
    # döndürüyor; `expected_events` sürümü seçildi çünkü bu ekrandaki
    # diğer iki beklenti sinyali de oradan geliyor ve tek tip
    # (`ExpectationSignal`) olmaları `_absent_panel`'i tek kod yolunda
    # tutuyor.
    kacirilan = _safe(
        "missed", lambda: expected_events.observation_gaps(days=3, limit=5), []
    )
    iddia_dagilimi = _safe("claims", repository.claim_status_distribution, [])
    shift_ozet = _safe("relations", shift_store.summary, {})

    # Tek ölçüm, iki panel: `needs_attention()` yedi günlük çekim
    # günlüğünü tarar (~40 ms). İki kez çağırmak o maliyeti sebepsiz
    # ikiye katlardı.
    bakim = _safe("source_health", source_quality.needs_attention, [])
    # "Susmuş" = tazelik bileşeni SIFIR. `not sebep.value` yazılıyor,
    # `== 0.0` değil: bu dosyada kayan noktalı sabit bulunması yasak
    # (`test_war_room_indicators_never_come_from_hardcoded_numbers`) ve
    # yasak yerinde — gösterge sayılarının koda gömülmesini o test
    # engelliyor.
    susan = [
        (kalite, sebep)
        for kalite, sebepler in bakim
        for sebep in sebepler
        if sebep.key == "freshness" and not sebep.value
    ]

    yukselen = [e for e in events if (e.get("salience_score") or 0) >= RISING_THRESHOLD]
    sessizlik = len(geciken) + len(kacirilan) + len(susan)

    # Bölüm 8.1: en fazla 4 KPI. Dördü de bu ekranın tek sorusuna
    # ("olağandışı olan ne, sırada ne var") doğrudan cevap verir —
    # "toplam olay sayısı" gibi bağlamsız bir sayaç bilerek yok.
    kpis = (
        '<div class="kpis">'
        + kpi(
            "Açık sapma",
            fmt.number(len(sapmalar)),
            delta_note="ölçülen, yorumlanmamış",
            icon_name="zap",
        )
        + kpi(
            "Beklenen yayın",
            fmt.number(len(bekleyen)),
            delta_note=f"önümüzdeki {HORIZON_HOURS} saat",
            icon_name="calendar",
        )
        + kpi(
            "Beklenip gelmeyen",
            fmt.number(sessizlik),
            delta_note="geciken · kaçırılan · susan kaynak",
            icon_name="warning",
        )
        + kpi(
            "Yükselen olay",
            fmt.number(len(yukselen)),
            delta_note=f"önem {RISING_THRESHOLD} ve üzeri",
            icon_name="trend-up",
        )
        + "</div>"
    )

    body = f"""
{
        page_head(
            "Kumanda odası",
            lede="Olağandışı olan ne var, sırada ne var? Sapmalar, beklenen resmî "
            "yayınlar ve beklenip gelmeyenler tek yüzeyde.",
            badges='<span class="badge sm neutral">'
            '<span id="wr-live-dot" class="pulse-dot"></span>canlı</span>',
            actions='<a class="btn sm" href="/feed">'
            + icon("feed", 13)
            + "<span>Gündem masası</span></a>",
        )
    }

<div class="stack">
  {kpis}
  {_indicator_strip()}
  <!-- Sol sütun OKUNUR (derinlik ister), sağ sütun TARANIR (tek bakışta
       biter). Söylem değişiklikleri panelinin solda olmasının sebebi bu:
       kapalı yayın kapısını anlatan iki paragraflık bir gerekçe, taranan
       bir sütunda okunmaz. Sağ sütun `sticky` DEĞİL — bir dönem öyleydi
       ve hiç devreye girmiyordu, çünkü sağ sütun soldan uzundu ve
       yapışacak boşluk hiç oluşmuyordu. -->
  <div class="split">
    <div class="stack">
      {_absent_panel(geciken, kacirilan, susan)}
      {_anomaly_panel(sapmalar)}
      {_emerging_events(events)}
      {_claims_panel(iddia_dagilimi)}
      {_relations_panel(shift_ozet)}
    </div>
    <div class="stack">
      {_expected_publications(bekleyen)}
      {_source_health_panel(bakim, {k.slug for k, _ in susan})}
      {
        card(
            # Liste ELLE YAZILMAZ; `ui/keys.py` sözleşmesinden gelir (Faz 8.3).
            # Bu kart bir dönem J/K ve X'i de listeliyordu; o üçü `feed.py`
            # dinleyicisine bağlıydı ve bu ekranda hiçbir şey yapmıyordu.
            # Çalışmayan bir kısayol listesi, kısayol listesi olmamasından
            # kötüdür: kullanıcı tuşa basar, hiçbir şey olmaz, arayüzün
            # bozuk olduğunu sanır. Yönlendirme cümlesinde tuş ROZETİ
            # kullanılmaz — rozet "burada çalışır" demektir
            # (tests/test_keyboard_contract.py bunu ölçer).
            keys.guide_card_body(
                "/war-room",
                elsewhere=(
                    "Olaylar arası klavye gezintisi ve hızlı X taslağı "
                    '<a href="/feed">Gündem masası</a> ekranındadır.'
                ),
            ),
            title="Kumanda kılavuzu",
        )
    }
    </div>
  </div>
</div>
"""

    return page(
        "Kumanda odası",
        body,
        active="/war-room",
        crumbs=(("Kumanda odası", None),),
        extra_js=ACTIVITY_JS + _war_room_js(),
    )
