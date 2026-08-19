"""Olay Sayfası (F3-03 … F3-07, F3-11, F3-21 · Spec §14.3).

Spec §14.3'ün ekran taslağındaki her bölüm burada karşılığını bulur:

| Taslaktaki bölüm | Görev | Uygulama |
|---|---|---|
| Salience 84 ⓘ | F3-07 | `_meta_line` |
| TL;DR | F3-03 | `_tldr` — **deterministik**, LLM yok |
| NE BİLİYORUZ / NE BİLMİYORUZ | F3-03 | `_knowledge_columns` |
| KANIT + [Neden 🟢?] | F3-04 | `_evidence_block` + `evidence/explain.py` |
| KAYNAKLAR (çerçeve farkı) | F3-05 | `_sources_table` |
| ZAMAN ÇİZELGESİ | F3-06 | `_timeline` |
| ÖNCEKİ BAĞLAM | F3-03 | `_related` |
| SIRADAKİ BEKLENEN | F3-03 | `_upcoming` |
| EDİTORYAL FIRSATLAR | F3-11 | `_editorial_panel` |

### Bu sayfanın tek işi (BRIEF `birincil_is`)

> "Bu olayda ne biliyoruz, ne bilmiyoruz — ve nereden biliyoruz?"

Yerleşim bunu izler: **ne biliyoruz / ne bilmiyoruz** iki eşit sütun olarak
sayfanın en üstünde durur, çünkü ürünün ayırt edici vaadi bilinmeyeni
bilinen kadar görünür kılmaktır (Spec §15 madde 3). Editoryal eylemler sağ
rayda ve **yapışkandır** — kullanıcı kanıtı okurken buton hep görünür kalır.

### TL;DR neden LLM'siz

Spec §14.3: *"2-3 cümle özet. **Yalnızca doğrulanmış unsurlardan
kurulur.**"* Bu cümle bir üslup tercihi değil, bir kısıttır. Doğrulanmış
iddiaların metni zaten veritabanında duruyor ve `verify_quote` ile kaynağa
bağlanmış durumda. Onları bir modele yeniden yazdırmak, kısıtı koruyan tek
şeyi (metnin kanıttan gelmesi) bir prompt talimatına indirgerdi. Özet, en
güçlü iddialardan **birleştirilir**.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from politikdesk.editorial.generator import ANGLES
from politikdesk.editorial.service import can_generate
from politikdesk.evidence.explain import KIND_LABELS, explain, explain_event_status
from politikdesk.users import current_user_id
from politikdesk.web import repository
from politikdesk.web.ui import (
    ACTIVITY_JS,
    action_attrs,
    button,
    card,
    cell,
    distribution,
    esc,
    event_badge,
    icon,
    notice,
    page,
    page_head,
    panel,
    relative_time,
    ruled,
    skeleton_rows,
    status_badge,
    table,
    tier_badge,
    timeline,
)
from politikdesk.web.ui import format as fmt

router = APIRouter(tags=["web"])

# "Ne biliyoruz" sütununa girecek durumlar. Diğerleri "ne bilmiyoruz"
# sütunundadır — bilinmeyeni bilinen gibi göstermek Spec §15 madde 3'ün
KNOWN_STATUSES = (
    "strongly_corroborated",
    "partially_corroborated",
    "attribution_verified",
)

MAX_TLDR_CLAIMS = 3


def _tldr(claims: list[dict[str, Any]]) -> str:
    """2-3 cümle özet — yalnızca doğrulanmış iddialardan (Spec §14.3)."""
    verified = [c for c in claims if c["evidence_status"] in KNOWN_STATUSES]
    if not verified:
        return notice(
            "<p>Bu olayda henüz teyit edilmiş iddia yok. Özet yalnızca "
            "doğrulanmış unsurlardan kurulur; teyit gelmeden özet de "
            "üretilmez.</p>",
            tone="warn",
        )
    sentences = [c["claim_text"].strip().rstrip(".") + "." for c in verified[:MAX_TLDR_CLAIMS]]
    summary_text = " ".join(sentences)
    copy_action = (
        f'<button class="btn sm ghost" type="button"{action_attrs("copy", summary_text, "Özet")}>'
        f'{icon("copy", 13)}<span>Özeti Kopyala</span></button>'
    )
    return card(
        f'<p class="prose" style="margin:0;font-size:var(--text-lg);'
        f'line-height:var(--text-lg-lh)">{" ".join(esc(s) for s in sentences)}</p>'
        f'<p class="subtle" style="margin:12px 0 0;font-size:var(--text-xs)">'
        f"Özet yalnızca teyit edilmiş iddialardan kurulur; bir model tarafından "
        f"yeniden yazılmaz.</p>",
        title="TL;DR Doğrulanmış Özet",
        actions=copy_action,
    )


def _claim_row(claim: dict[str, Any]) -> str:
    """Tek iddia — SIGNATURE: sol kenarda kanıt cetveli.

    İddia metninin kontrastı da kanıt gücüyle düşer (`ui/css.py`); teyitli
    iddia tam mürekkeple, doğrulanmamış iddia soluk yazılır.
    """
    body = (
        f'<div class="claim-text" style="font-size:var(--text-sm)">'
        f"{esc(claim['claim_text'])}</div>"
        f'<div class="row tight subtle" style="margin-top:6px;'
        f'font-size:var(--text-xs)">{status_badge(claim["evidence_status"])}'
        f"<span>· {esc(claim['claim_type'])}</span>"
        f"<span>· {esc(fmt.plural_count(int(claim['evidence_count'] or 0), 'kanıt bağı'))}"
        f"</span></div>"
    )
    return ruled(claim["evidence_status"], body, cls="stack-sm")


def _knowledge_columns(claims: list[dict[str, Any]]) -> str:
    """NE BİLİYORUZ / NE BİLMİYORUZ (Spec §14.3).

    İki sütun **eşit genişliktedir**. Bilinmeyeni daha dar bir sütuna
    koymak onu ikincil gösterirdi; bu ürünün tezi tam tersi.
    """
    known = [c for c in claims if c["evidence_status"] in KNOWN_STATUSES]
    unknown = [c for c in claims if c["evidence_status"] not in KNOWN_STATUSES]

    def column(title: str, items: list[dict[str, Any]], empty: str, hint: str) -> str:
        rows = (
            "".join(_claim_row(c) for c in items)
            if items
            else f'<p class="subtle" style="margin:0">{esc(empty)}</p>'
        )
        return card(
            f'<div class="stack-sm" style="gap:var(--space-3)">{rows}</div>',
            title=f"{title} · {len(items)}",
            actions=f'<span class="subtle" style="font-size:var(--text-xs)">{esc(hint)}</span>',
        )

    return (
        '<div class="halves">'
        + column("Ne biliyoruz", known, "Teyit edilmiş iddia yok.", "en az iki bağımsız kaynak")
        + column("Ne bilmiyoruz", unknown, "Açık kalan iddia yok.", "teyit bekliyor veya çelişkili")
        + "</div>"
    )


def _why_panel(claim: dict[str, Any]) -> str:
    """ "Neden bu durum?" — `status_reason` insan diline çevrilir (F3-04).

    Kural adı ve girdiler AÇIKÇA görünür: bir gerekçe, doğrulanabilir
    olmadıkça gerekçe değildir (P4).
    """
    detail = explain(claim["evidence_status"], claim.get("status_reason"))
    facts = "".join(
        f"<tr><td>{esc(f['label'])}</td><td class='num mono'>{esc(f['value'])}</td></tr>"
        for f in detail["facts"]
    )
    summary = (
        f"{status_badge(claim['evidence_status'])}"
        f'<b style="font-size:var(--text-sm)">{esc(detail["rule"])}'
        f" · {esc(detail['rule_title'])}</b>"
        f'<span class="subtle" style="overflow:hidden;text-overflow:ellipsis;'
        f'white-space:nowrap">{esc(claim["claim_text"][:70])}</span>'
    )
    body = f"""
<p style="margin:0 0 12px">{esc(detail["sentence"])}</p>
<table><tbody>
{facts or "<tr><td class='subtle'>Girdi kaydı yok.</td></tr>"}
</tbody></table>
<p class="subtle" style="margin:12px 0 0;font-size:var(--text-xs)">
  Kural motoru <span class="mono">{esc(detail["engine_version"] or "—")}</span> ·
  hesaplandı {esc(detail["computed_at"] or "—")} ·
  <b>bu durum bir LLM çıktısı DEĞİLDİR</b> (Spec §8.1).</p>"""
    return panel(summary, body)


def _evidence_block(data: dict[str, Any]) -> str:
    """KANIT bloğu + "Neden bu durum?" açılır panelleri (F3-04)."""
    event = data["event"]
    articles = data["articles"]

    # Kaynak kırılımı bir DAĞILIMDIR ve öyle gösterilir (Bölüm 8.12).
    # "Resmî 3 · Medya 1" tek satır metni sayıları okutur ama ORANI
    # okutmaz; oysa buradaki soru "kaç tane" değil, "ağırlık nerede".
    # Sıralama büyükten küçüğe — alfabetik sıralama bu bileşenin amacını
    # yok eder.
    kinds: dict[str, int] = {}
    for article in articles:
        kinds[article["kind"]] = kinds.get(article["kind"], 0) + 1
    breakdown = distribution(
        [
            (KIND_LABELS.get(kind, kind), float(count), fmt.number(count))
            for kind, count in kinds.items()
        ]
    )

    panels = "".join(_why_panel(claim) for claim in data["claims"]) or (
        '<p class="subtle" style="margin:0">Henüz iddia çıkarılmamış.</p>'
    )

    verdict = explain_event_status(
        int(event["independent_count"] or 0),
        bool(event["has_primary_source"]),
        int(event["independence_groups"] or 0),
    )
    return card(
        f'<p style="margin:0 0 var(--space-4)">{esc(verdict)}</p>'
        f'<p class="eyebrow" style="margin-bottom:var(--space-2)">'
        f"Kaynak dağılımı</p>{breakdown}"
        f'<div style="margin-top:var(--space-6)">{panels}</div>',
        title="Kanıt",
        actions='<span class="subtle" style="font-size:var(--text-xs)">'
        "her satır bir kural kararı</span>",
    )


def _sources_table(data: dict[str, Any]) -> str:
    """KAYNAKLAR + çerçeve farkı paneli (F3-05).

    ⛔ Bu tabloda **siyasi etiket yoktur ve olamaz** (Spec §8.5, §15 madde
    5). Kaynaklar yalnızca adı, katmanı (tier) ve yayın grubuyla anılır;
    "yandaş/muhalif" gibi bir sütun eklemek ürün sözleşmesinin ihlalidir ve
    `tests/test_web.py` bunu tarar. Tabloya renkli bir şerit veya "eğilim"
    göstergesi eklemek de aynı ihlaldir — görsel etiket de etikettir.
    """
    articles = data["articles"]
    if not articles:
        return card(
            '<p class="subtle" style="margin:0">Bu olaya bağlı makale yok.</p>',
            title="Kaynaklar",
        )

    rows = []
    for a in articles:
        duplicate = (
            '<div class="cell-sub">↳ yakın tekrar — bağımsız sayılmaz</div>'
            if a["near_duplicate_of_id"]
            else ""
        )
        link = (
            button(
                "",
                href=a["canonical_url"],
                icon_name="external",
                small=True,
                title=f"{a['source_name']} — kaynakta aç",
            )
            if a["canonical_url"]
            else '<span class="subtle">—</span>'
        )
        rows.append(
            "<tr>"
            + cell(
                f'<div class="row tight"><b>{esc(a["source_name"])}</b>'
                f"{tier_badge(a['tier'])}</div>"
                f'<div class="cell-sub">{esc(a["independence_group"] or a["source_slug"])}'
                f"</div>",
                label="Kaynak",
            )
            + cell(f"{esc(a['title'])}{duplicate}", label="Başlık")
            + cell(relative_time(a["published_at"] or a["first_seen_at"]), label="Saat")
            + cell(link, label="Bağlantı")
            + "</tr>"
        )

    groups = int(data["event"]["independence_groups"] or 0)
    note = (
        notice(f"<p>Bu olay <b>{fmt.number(groups)} farklı yayın grubundan</b> raporlanıyor.</p>")
        if groups >= 2
        else notice(
            "<p><b>Bu olay tek bir yayın grubundan raporlanıyor.</b> Farklı bir "
            "kaynaktan teyit aramadan kesin konuşma.</p>",
            tone="warn",
        )
    )

    return card(
        '<p class="subtle" style="margin:0 0 var(--space-4);font-size:var(--text-xs)">'
        "Başlıklar yan yana durur; farkı sen değerlendirirsin. Sistem hiçbir "
        "yayına siyasi konum etiketi vermez (Spec §8.5).</p>"
        + table(
            (("Kaynak", ""), ("Başlık", ""), ("Saat", ""), ("", "")),
            rows,
        )
        + f'<div style="margin-top:var(--space-4)">{note}</div>',
        title="Kaynaklar",
        actions='<span class="subtle" style="font-size:var(--text-xs)">çerçeve farkı</span>',
        cls="",
    )


def _blindspot_block(data: dict[str, Any]) -> str:
    """MEDYA KAPSAMI VE KÖR NOKTA RADARI."""
    from politikdesk.evidence.blindspot import analyze_blindspot

    event = data["event"]
    articles = data["articles"]
    source_names = [a.get("source_name") or a.get("source_slug", "") for a in articles]
    report = analyze_blindspot(event_id=event["id"], covered_sources=source_names)

    tier_b = report.tier_breakdown
    dist_items = [
        ("T1 Resmî / Birincil", float(tier_b.tier1_official), f"{tier_b.tier1_official} kaynak"),
        ("T2 Ajans / Ana Akım", float(tier_b.tier2_mainstream), f"{tier_b.tier2_mainstream} kaynak"),
        ("T3 Bağımsız / Sektörel", float(tier_b.tier3_independent), f"{tier_b.tier3_independent} kaynak"),
    ]
    dist_html = distribution(dist_items)

    severity_tones = {
        "balanced": "ok",
        "mainstream_only": "warn",
        "independent_only": "bad",
        "single_source": "warn",
        "minimal": "warn",
    }
    tone = severity_tones.get(report.severity, "")
    badge_html = f'<span class="badge {tone}">{esc(report.summary_label)}</span>' if tone else f'<span class="badge">{esc(report.summary_label)}</span>'

    return card(
        f'<div class="row tight" style="margin-bottom:var(--space-3)">{badge_html}</div>'
        f'<p style="margin:0 0 var(--space-4);font-size:var(--text-sm)">{esc(report.description)}</p>'
        f'<p class="eyebrow" style="margin-bottom:var(--space-2)">Medya Kademesi Dağılımı</p>'
        f'{dist_html}'
        f'<p class="subtle" style="margin:var(--space-3) 0 0;font-size:var(--text-xs)">'
        f'{len(report.covered_sources)} kaynak haberi geçti, {len(report.missing_sources)} kaynak henüz haberleştirmedi.</p>',
        title="Medya Kapsamı ve Kör Nokta Radarı",
        actions=f'<span class="subtle" style="font-size:var(--text-xs)">%{int(report.coverage_ratio*100)} kapsama</span>',
    )


# Dışa aktarım kanalları: (format, etiket, ikon, açıklama).
#
# Bu tablo `web/api.py::export_event_dossier`'ın `format` Literal'ıyla
# BİREBİR aynı olmalıdır; `tests/test_omnichannel_and_warroom.py` ayrışmayı
# yakalar. Ayrışmanın maliyeti somut: yedi kanal (x_thread, linkedin,
# instant, podcast, bluesky, mastodon, newsletter) API'de aylarca
# çalışır durumdaydı ama arayüzde hiçbir bağlantısı yoktu — yani kullanıcı
# için var olmuyorlardı.
EXPORT_CHANNELS: tuple[tuple[str, str, str, str], ...] = (
    ("markdown", "Markdown dosyası", "download", "Kanıt zinciriyle tam dosya"),
    ("text", "Düz metin", "copy", "Biçimsiz, her yere yapışır"),
    ("json", "JSON kanıt verisi", "external", "Programatik kullanım"),
    ("svg", "SVG kanıt kartı", "download", "Paylaşılabilir görsel kart"),
    ("x_thread", "X zinciri", "share", "280 karaktere bölünmüş dizi"),
    ("bluesky", "Bluesky gönderisi", "share", "Azami 300 karakter"),
    ("mastodon", "Mastodon gönderisi", "share", "Azami 500 karakter"),
    ("linkedin", "LinkedIn bilgi notu", "share", "Kurumsal özet biçimi"),
    ("instant", "Telegram / WhatsApp", "share", "Madde işaretli anlık bülten"),
    ("newsletter", "E-bülten bloğu", "external", "Substack uyumlu Markdown"),
    ("podcast", "Seslendirme metni", "external", "60 saniyelik konuşma dili"),
)


def _export_block(event_id: int) -> str:
    """ÇOK KANALLI DIŞA AKTARIM (Spec §15/6).

    ⛔ Burada "yayınla" düğmesi YOKTUR ve olmayacaktır. Her bağlantı bir
    METİN üretir; nereye, ne zaman ve gönderilip gönderilmeyeceğine karar
    veren daima kullanıcıdır. Otomatik yayın kod yolu bu üründe yoktur.
    """
    items = "".join(
        f'<a class="btn sm ghost" style="justify-content:flex-start;text-align:left" '
        f'href="/api/events/{event_id}/export?format={fmt_key}" '
        f'target="_blank" rel="noopener noreferrer" title="{esc(hint)}">'
        f"{icon(icon_name, 13)}<span>{esc(label)}</span></a>"
        for fmt_key, label, icon_name, hint in EXPORT_CHANNELS
    )
    return card(
        f'<div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(190px,1fr));'
        f'gap:var(--space-2)">{items}</div>'
        f'<p class="subtle" style="margin:var(--space-4) 0 0;font-size:var(--text-xs)">'
        f"Her biçim yalnızca <b>metin üretir</b>. Gönderme kararı ve gönderme "
        f"eylemi sende kalır — bu üründe otomatik yayın kod yolu yoktur.</p>",
        title="Dışa aktarım kanalları",
        actions=f'<span class="subtle" style="font-size:var(--text-xs)">'
        f"{len(EXPORT_CHANNELS)} biçim</span>",
    )



def _timeline_block(data: dict[str, Any]) -> str:
    """ZAMAN ÇİZELGESİ (F3-06) — 20+ makalede de tek sorgu, tek liste."""
    articles = data["articles"]
    if not articles:
        return ""
    items = tuple(
        (
            fmt.date_time(a["published_at"] or a["first_seen_at"]),
            f'<div class="row tight"><b style="font-size:var(--text-sm)">'
            f"{esc(a['source_name'])}</b>{tier_badge(a['tier'])}</div>"
            f'<div class="muted" style="font-size:var(--text-sm);margin-top:2px">'
            f"{esc((a['excerpt'] or a['title'])[:180])}</div>",
        )
        for a in articles
    )
    return card(
        panel(
            f"{icon('clock', 14)}<span>{fmt.plural_count(len(articles), 'adım')} — genişlet</span>",
            timeline(items),
            open_=len(articles) <= 6,
        ),
        title="Zaman çizelgesi",
    )


def _stance_shifts(event_id: int) -> str:
    """SÖYLEM DEĞİŞİKLİĞİ ZİNCİRİ (Roadmap Faz 4.1).

    Bu kartın var olabilmesi kalıcılaştırmanın doğrudan sonucudur.
    Kaymalar her istekte yeniden hesaplanırken "bu olay hangi söylem
    değişikliklerinin parçası?" sorusu **sorulamıyordu** — hesap
    aktörden başlıyordu, olaydan değil. Kalıcı kayıt her iki yönde de
    indekslidir; sorgu ölçülen süreyle 1,8 ms.

    ⛔ Kart bir YORUM sunmaz: iki beyanı ve aradaki süreyi gösterir,
    "neden değişti" demez. Nedensellik kanıt ister.
    """
    from politikdesk.political_memory import shift_store

    try:
        kaymalar = shift_store.for_event(event_id, limit=6)
    except Exception:  # noqa: BLE001 — kart isteğe bağlıdır, sayfa düşmez
        return ""

    if not kaymalar:
        return ""

    tur_etiketi = {
        "reversal": "Yön değişikliği",
        "broken_promise": "Tutulmayan vaat",
        "numeric_divergence": "Sayısal sapma",
    }

    items = []
    for k in kaymalar:
        onceki_bu_mu = int(k["earlier_event_id"]) == event_id
        diger_id = k["later_event_id"] if onceki_bu_mu else k["earlier_event_id"]
        diger_baslik = k["later_event_title"] if onceki_bu_mu else k["earlier_event_title"]
        yon = "sonrasında" if onceki_bu_mu else "öncesinde"
        items.append(
            f'<li style="margin-bottom:12px">'
            f'<div class="row tight" style="align-items:baseline">'
            f'<b style="font-size:var(--text-sm)">{esc(k["actor_name"])}</b>'
            f'<span class="badge sm">{esc(tur_etiketi.get(str(k["shift_type"]), "Değişiklik"))}'
            f"</span></div>"
            f'<div class="subtle" style="font-size:var(--text-xs);margin-top:2px">'
            f'Bu olayın {yon} · {esc(fmt.plural_count(int(k["time_span_days"] or 0), "gün"))} ara'
            f"</div>"
            f'<a href="/event/{diger_id}" style="font-size:var(--text-sm)">'
            f"{esc(str(diger_baslik)[:80])}</a></li>"
        )

    return card(
        f'<ul style="margin:0;padding-left:18px">{"".join(items)}</ul>'
        f'<p class="subtle" style="margin:var(--space-4) 0 0;font-size:var(--text-xs)">'
        f"Bu kart iki beyan arasındaki <b>ölçülmüş</b> zıtlığı gösterir; "
        f"değişikliğin sebebi hakkında bir iddiada bulunmaz.</p>",
        title="Söylem değişikliği zinciri",
        actions=f'<span class="subtle" style="font-size:var(--text-xs)">'
        f"{fmt.plural_count(len(kaymalar), 'kayma')}</span>",
    )


def _related(data: dict[str, Any]) -> str:
    """ÖNCEKİ BAĞLAM (F2-17 çıktısı)."""
    related = data["related"]
    if not related:
        return ""
    items = "".join(
        f'<li style="margin-bottom:10px">'
        f'<a href="/event/{r["id"]}">{esc(r["title"])}</a>'
        f'<div class="subtle" style="font-size:var(--text-xs)">'
        f"{esc(fmt.full_date(r['first_reported_at']))} · {esc(r['relation'])} · "
        f'benzerlik <span class="mono">{esc(fmt.number(float(r["similarity"] or 0) * 100, 1))}'
        f"</span></div></li>"
        for r in related
    )
    return card(
        f'<ul style="margin:0;padding-left:18px">{items}</ul>',
        title="Önceki bağlam",
    )


def _upcoming(data: dict[str, Any]) -> str:
    """SIRADAKİ BEKLENEN (Spec §9.5)."""
    upcoming = data["upcoming"]
    if not upcoming:
        return ""
    items = "".join(
        f'<li style="margin-bottom:10px">{esc(u["title"])}'
        f'<div class="subtle" style="font-size:var(--text-xs)">'
        f"{esc(fmt.date_time(u['expected_at']))}"
        f"{' · ' + esc(u['source_name']) if u['source_name'] else ''}</div></li>"
        for u in upcoming
    )
    return card(
        f'<ul style="margin:0;padding-left:18px">{items}</ul>',
        title="Sıradaki beklenen",
    )


def _editorial_panel(event_id: int) -> str:
    """EDİTORYAL FIRSATLAR + P1 zorlaması (F3-11).

    Buton durumu ile API kararı **aynı fonksiyondan** gelir
    (`service.can_generate`). Ayrışsalardı kullanıcı tıklanabilen ama her
    seferinde 409 dönen bir buton görürdü.
    """
    gate = can_generate(event_id)

    if not gate["allowed"]:
        buttons = "".join(
            button(label, disabled=True, title="Kanıtsız olayda üretim yapılmaz")
            for label, _ in ANGLES.values()
        )
        reason = notice(f"<p>{esc(gate['message'])}</p>", tone="bad")
        return card(
            f'<div class="btn-row">{buttons}</div>'
            f'<div style="margin-top:var(--space-4)">{reason}</div>'
            f'<p class="subtle" style="margin:12px 0 0;font-size:var(--text-xs)">'
            f"Bu bir arayüz kısıtı değil: API doğrudan çağrılsa da "
            f'<span class="mono">409</span> döner (Spec §14.1 kalem 15, P1).</p>',
            title="Editoryal fırsatlar",
        )

    # Sayfada TEK primary buton (Bölüm 8.5) — ilk açı birincil, diğerleri
    # ikincil. Üç eşit primary buton, "hangisi varsayılan" sorusunu
    # cevapsız bırakırdı.
    keys = list(ANGLES)
    buttons = "".join(
        button(
            ANGLES[key][0],
            variant="primary" if index == 0 else "",
            action="generate",
            action_args=(key,),
            icon_name="edit" if index == 0 else None,
        )
        for index, key in enumerate(keys)
    )
    return card(
        f'<div class="btn-row">{buttons}</div>'
        f'<p class="subtle" style="margin:12px 0 0;font-size:var(--text-xs)">'
        f"{icon('check', 12)} Kanıta bağlı üretim · "
        f"{esc(fmt.plural_count(gate['claim_count'], 'iddia'))}, "
        f"{esc(fmt.plural_count(gate['evidence_count'], 'kanıt bağı'))}</p>"
        f'<div id="draft-out" style="margin-top:var(--space-4)"></div>',
        title="Editoryal fırsatlar",
    )


def _feedback_panel(open_count: int) -> str:
    """ "Bu yanlış" geri bildirim butonu (F3-21)."""
    note = (
        f'<p class="subtle" style="margin:10px 0 0;font-size:var(--text-xs)">'
        f"{esc(fmt.plural_count(open_count, 'açık işaret'))} var — denetim "
        f"kuyruğunda.</p>"
        if open_count
        else '<p class="subtle" style="margin:10px 0 0;font-size:var(--text-xs)">'
        "İşaretlediğinde olay insan denetimi kuyruğuna düşer.</p>"
    )
    return card(
        button("Bu yanlış", icon_name="flag", action="flag") + note,
        title="Geri bildirim",
    )


def _meta_line(event: dict[str, Any]) -> str:
    return (
        f'<span title="Global {event["global_salience"]} + kişisel '
        f'{event["personal_salience"]}">Önem '
        f'<b class="num">{esc(fmt.number(event["displayed_salience"]))}</b></span>'
        f'<span class="subtle">·</span>'
        f"<span>İlk rapor {esc(fmt.date_time(event['first_reported_at']))}</span>"
        f'<span class="subtle">·</span>'
        f"<span>Son güncelleme {esc(fmt.relative(event['last_update_at']))}</span>"
        f'<span class="subtle">·</span>'
        f"<span>{esc(fmt.plural_count(int(event['article_count'] or 0), 'makale'))}</span>"
        f'<span class="subtle">·</span>'
        f"<span>{esc(fmt.plural_count(int(event['independent_count'] or 0), 'bağımsız teyit'))}"
        f"</span>"
    )


# Yükleniyor durumu (Bölüm 10.3) — skeleton, spinner DEĞİL.
#
# Taslak üretimi bu üründeki TEK gerçekten yavaş etkileşimdir (LLM çağrısı,
# saniyeler); sunucu tarafında üretilen diğer ekranlarda istemci yükleme
# durumu yoktur ve olmamalıdır (300ms'den kısa yüklemede hiçbir şey
# gösterilmez).
#
# Şekil `components.skeleton_rows()`'tan gelir, JS içinde elle yazılmaz:
# skeleton'ın nabız süresi ve rengi token'a bağlı ve iki yerde tanımlanan
# bir şey bir gün ayrışır.
_SKELETON_JS = (
    "var PD_SKELETON = "
    + json.dumps(
        skeleton_rows(3, height=14)
        + '<p class="subtle" style="margin:12px 0 0;font-size:var(--text-xs)" '
        'aria-live="polite">Kanıt setinden üretiliyor…</p>'
    )
    + ";"
)

_EVENT_JS = (
    _SKELETON_JS
    + """
function pdEventId(){ return document.body.dataset.eventId; }

async function pdGenerate(angle){
  var out = document.getElementById('draft-out');
  // Yükleniyor (Bölüm 10.3): skeleton, spinner değil. LLM çağrısı saniyeler
  // sürer — burada gerçekten gösterilmesi gereken bir durum var.
  out.innerHTML = PD_SKELETON;
  try {
    var r = await fetch('/api/events/' + pdEventId() + '/drafts', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({angle: angle})
    });
    var data = await r.json();
    if (r.status === 409) {
      out.innerHTML = '<div class="notice bad"><div><p>' +
        (data.detail && data.detail.message ? data.detail.message : data.detail) +
        '</p></div></div>';
      return;
    }
    if (!r.ok) {
      out.innerHTML = '<div class="notice bad"><div><p>Taslak üretilemedi. ' +
        'Model yanıt vermedi veya günlük bütçe doldu — birkaç dakika sonra ' +
        'tekrar dene.</p></div></div>';
      return;
    }
    location.href = '/draft/' + data.draft_id;
  } catch (e) {
    out.innerHTML = '<div class="notice bad"><div><p>Sunucuya ulaşılamadı. ' +
      'Bağlantını kontrol edip tekrar dene.</p></div></div>';
  }
}

async function pdFlag(){
  var note = prompt('Ne yanlış? (isteğe bağlı)');
  if (note === null) return;
  var r = await fetch('/api/events/' + pdEventId() + '/feedback', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({note: note})
  });
  alert(r.ok ? 'İşaretlendi. Olay denetim kuyruğuna alındı.'
             : 'Kaydedilemedi. Bağlantını kontrol edip tekrar dene.');
  if (r.ok) location.reload();
}

// time-to-understanding: "Anladım" tıklamasına kadar geçen süre (F3-19)
function pdUnderstood(btn){
  window.pdPing('understood', {duration_ms: Date.now() - window.pdOpenedAt});
  btn.disabled = true;
  btn.querySelector('span').textContent = 'Anlaşıldı olarak işaretlendi';
}

async function pdCopyEventDossier(){
  try {
    var r = await fetch('/api/events/' + pdEventId() + '/export?format=text');
    if (!r.ok) throw new Error(r.status);
    var txt = await r.text();
    window.pdCopy(txt, 'Kanıt Dosyası');
  } catch (e) {
    window.pdToast('Dosya kopyalanamadı: ' + e.message);
  }
}

window.pdAction('generate', pdGenerate);
window.pdAction('flag', pdFlag);
window.pdAction('understood', pdUnderstood);
window.pdAction('copy-dossier', pdCopyEventDossier);
"""
)


@router.get("/event/{event_id}", response_class=HTMLResponse)
@router.get("/events/{event_id}", response_class=HTMLResponse, include_in_schema=False)
def event_page(event_id: int) -> str:
    try:
        user_id = current_user_id()
        data = repository.event_page(event_id, user_id)
    except Exception:  # noqa: BLE001
        data = None

    if data is None:
        raise HTTPException(status_code=404, detail=f"Olay yok: {event_id}")

    event = data["event"]
    review = (
        notice(
            "<p><b>Bu olayın kümeleme kararı belirsiz ve insan denetimi "
            "bekliyor.</b> İçerik üretmeden önce doğrula.</p>",
            tone="warn",
        )
        if event.get("review_flag") == "needs_review"
        else ""
    )

    actions_html = (
        f'<div class="row tight">'
        f'<button class="btn sm ghost" type="button"{action_attrs("copy-dossier")} title="Kanıt dosyasını kopyala">'
        f'{icon("copy", 13)}<span>Metin Kopyala</span></button>'
        f'<a class="btn sm ghost" href="/api/events/{event_id}/evidence-card.svg" target="_blank" rel="noopener noreferrer" title="SVG Kanıt Kartını Gör / İndir">'
        f'{icon("download", 13)}<span>SVG Kart</span></a>'
        f'<a class="btn sm ghost" href="/api/events/{event_id}/export?format=markdown" target="_blank" rel="noopener noreferrer" title="Markdown Olarak İndir">'
        f'{icon("external", 13)}<span>Markdown</span></a>'
        f'{button("Anladım", icon_name="check", action="understood")}'
        f'</div>'
    )

    body = f"""
{
        page_head(
            event["title"],
            lede="",
            badges=event_badge(event["status"]),
            actions=actions_html,
        )
    }
<div class="row subtle" style="font-size:var(--text-xs);
     margin:-16px 0 var(--space-6)">{_meta_line(event)}</div>
{f'<div style="margin-bottom:var(--space-6)">{review}</div>' if review else ""}

<div class="split">
  <div class="stack">
    {_tldr(data["claims"])}
    {_knowledge_columns(data["claims"])}
    {_evidence_block(data)}
    {_sources_table(data)}
    {_blindspot_block(data)}
    {_timeline_block(data)}
    {_export_block(event_id)}
  </div>
  <div class="stack" style="position:sticky;top:calc(var(--topbar-h) + 24px)">
    {_editorial_panel(event_id)}
    {_stance_shifts(event_id)}
    {_related(data)}
    {_upcoming(data)}
    {_feedback_panel(data["open_feedback"])}
  </div>
</div>
"""

    html = page(
        event["title"][:70],
        body,
        active="/feed",
        crumbs=(("Gündem", "/feed"), (event["title"][:60], None)),
        extra_js=ACTIVITY_JS + _EVENT_JS,
        # `data-event-id` gövdeye yazılır: izleme ve JS uçları onu okur.
        body_attrs=f' data-event-id="{event_id}"',
    )
    return html
