"""`status_reason` -> insan dili (F3-04 · Spec §8.3, P4).

DoD: `status_reason` JSON'u insan diline çevriliyor; **kural adı ve
girdiler görünüyor.**

Bu modül P4'ün (şeffaflık > kesinlik) kullanıcıya bakan yüzüdür. Kanıt
motoru bir sonuç değil, bir **gerekçe** üretir; burası o gerekçeyi
okunur kılar. "Neden 🟢?" sorusuna "çünkü modelimiz öyle dedi" değil,
"çünkü R2: birincil kaynak + 4 bağımsız teyit, çelişki yok" cevabı
verilir.

⛔ MİMARİ KURAL: bu modül `politikdesk.llm` import EDEMEZ. Açıklama,
kararın kendisi kadar deterministiktir; bir model tarafından yeniden
yazılırsa gerekçe olmaktan çıkıp anlatıya dönüşür.
"""

from __future__ import annotations

from typing import Any, Final

# Kural adları rules.py'deki blok yapısını izler. Metinler kullanıcıya
# gösterilir; kural kodu ("R2") her zaman yanında durur ki denetlenebilsin.
RULE_TITLES: Final[dict[str, str]] = {
    "R0": "Tahmin — doğrulanamaz",
    "R1": "Çelişkili kaynaklar",
    "R2": "Birincil kaynak + bağımsız teyit",
    "R3": "Resmî sayısal yayın istisnası",
    "R4": "Kısmi teyit",
    "R5": "Tek kaynak",
    "R6": "Kanıt yok",
    "R7": "Yalnızca sosyal medya — tavan uygulandı",
    "R8": "Birincil kayıt ve beyan doğrulaması",
}

# Durum adları DÜZ METİNDİR. Eskiden emoji rozet taşıyorlardı; kaldırıldı
# çünkü bu dizeler ekrana çıkıyor ve emoji görünümü işletim sistemine göre
# değişir, renk token'ı almaz, ekran okuyucuda "yeşil daire" diye okunur
# (DESIGN.md Bölüm 13.4, gerekçe: web/ui/icons.py başlığı).
#
# Görsel rozet artık `web/ui/components.status_badge()` tarafından SVG ile
# çizilir; bu tablo yalnızca ADI verir.
STATUS_TITLES: Final[dict[str, str]] = {
    "strongly_corroborated": "Güçlü teyitli",
    "partially_corroborated": "Kısmen teyitli",
    "single_source": "Tek kaynaklı",
    "contradicted": "Çelişkili",
    "unverified": "Doğrulanmamış",
    "attribution_verified": "Beyan sabit",
}

KIND_LABELS: Final[dict[str, str]] = {
    "official": "Resmî", "wire": "Ajans", "media": "Medya", "social": "Sosyal",
}


def _breakdown_text(breakdown: dict[str, Any] | None) -> str:
    """{'official': 1, 'media': 3} -> 'Resmî 1 · Medya 3'"""
    if not breakdown:
        return "—"
    parts = [
        f"{KIND_LABELS.get(kind, kind)} {count}"
        for kind, count in sorted(breakdown.items())
        if count
    ]
    return " · ".join(parts) or "—"


def explain(status: str, reason: dict[str, Any] | None) -> dict[str, Any]:
    """Bir iddianın durumunu ve gerekçesini insan diline çevirir.

    Dönen sözlük hem HTML panelinde hem JSON ucunda kullanılır; ikisinin
    aynı metni göstermesi denetlenebilirliğin şartıdır.
    """
    reason = reason or {}
    rule = str(reason.get("rule") or "—")
    count = reason.get("independent_count")
    primary = reason.get("has_primary_source")
    contradictions = reason.get("contradictions") or 0
    breakdown = reason.get("breakdown")

    facts: list[tuple[str, str]] = []
    if count is not None:
        facts.append(("Bağımsız teyit", str(count)))
    if primary is not None:
        facts.append(("Birincil kaynak", "var" if primary else "yok"))
    if breakdown:
        facts.append(("Kaynak kırılımı", _breakdown_text(breakdown)))
    if contradictions:
        facts.append(("Çelişen kanıt", str(contradictions)))
    keys = reason.get("independence_keys")
    if keys:
        facts.append(("Bağımsızlık anahtarları", ", ".join(map(str, keys))))

    sentence = _sentence(rule, reason, count, primary, contradictions)

    # R7 bir TAVAN kısıtıdır: hangi kuralın sonucunu sınırladığı
    # gösterilmezse kullanıcı "neden 🟠?" sorusunun yarısını görür.
    if reason.get("capped_from"):
        sentence += (
            f" Sonuç {STATUS_TITLES.get(str(reason['capped_from']), reason['capped_from'])} "
            f"olacaktı; R7 tavanı ({reason.get('capped_by_rule', '—')} kuralının çıktısı) "
            "yalnızca sosyal medya kanıtı bulunduğu için düşürdü."
        )

    return {
        "status": status,
        "status_title": STATUS_TITLES.get(status, status),
        "rule": rule,
        "rule_title": RULE_TITLES.get(rule, "Bilinmeyen kural"),
        "sentence": sentence,
        "facts": [{"label": label, "value": value} for label, value in facts],
        "engine_version": reason.get("engine_version"),
        "computed_at": reason.get("computed_at"),
        "short_circuit": reason.get("short_circuit"),
    }


def _sentence(
    rule: str,
    reason: dict[str, Any],
    count: Any,
    primary: Any,
    contradictions: int,
) -> str:
    if rule == "R0":
        return (
            "Bu bir tahmindir. Gelecek hakkındaki iddialar kanıta bakılmadan "
            "doğrulanmamış sayılır (kural motoru kanıt kurallarını hiç "
            "çalıştırmadı). Bu bir kalite yargısı değil, tip kısıtıdır."
        )
    if rule == "R1":
        return (
            f"En az bir Tier 1-2 kaynak dahil olmak üzere {contradictions} çelişen "
            "kanıt var. Sistem taraf tutmaz: iki tarafı da gösterir."
        )
    if rule == "R2":
        return (
            f"Birincil kaynak var ve {count} bağımsız teyit bulundu; çelişen "
            "kanıt yok. Bağımsızlık, aynı yayın grubunun ve ajans kopyalarının "
            "tek sayılmasıyla hesaplanır (Spec §8.2)."
        )
    if rule == "R3":
        value = reason.get("normalized_value") or {}
        metric = value.get("metric", "veri")
        return (
            f"Sayısal veriyi kurumun kendisi yayımladı ({metric}). Resmî "
            "istatistik yayınında üç bağımsız teyit aranmaz — kaynağın kendisi "
            "birincil kayıttır."
        )
    if rule == "R4":
        if reason.get("partial_elements"):
            return (
                f"{count} bağımsız kaynak var ama iddianın bazı unsurları yalnızca "
                "tek kaynakta doğrulandı."
            )
        return (
            f"{count} bağımsız kaynak var ama birincil kaynak yok. Teyit gerçek, "
            "kayıt değil."
        )
    if rule == "R5":
        return (
            "Yalnızca bir bağımsız kaynak bu iddiayı bildiriyor. Yanlış olduğu "
            "anlamına gelmez; henüz teyit edilmediği anlamına gelir."
        )
    if rule == "R6":
        return "Bu iddiaya bağlanmış hiçbir kanıt bulunamadı."
    if rule == "R7":
        return "Kanıtın tamamı sosyal medyadan geliyor."
    if rule == "R8":
        return (
            "Aktarım veya beyan birincil resmî kayda (TBMM tutanağı, Resmî Gazete, "
            "Sayıştay raporu vb.) dayanıyor; sözün söylendiği ve kayda geçtiği sabittir."
        )
    primary_text = "birincil kaynak var" if primary else "birincil kaynak yok"
    return f"{count} bağımsız teyit, {primary_text}."


def explain_event_status(
    independent_count: int, has_primary_source: bool, groups: int
) -> str:
    """Olay başlığındaki kanıt bloğunun tek cümlelik özeti (Spec §14.3)."""
    primary = (
        "Birincil kaynak mevcut" if has_primary_source else "Birincil kaynak yok"
    )
    diversity = (
        f"{groups} farklı yayın grubu"
        if groups >= 2
        else "bu olay tek bir yayın grubundan raporlanıyor"
    )
    return f"{primary} · {independent_count} bağımsız teyit · {diversity}"


__all__ = ["KIND_LABELS", "RULE_TITLES", "STATUS_TITLES", "explain", "explain_event_status"]
