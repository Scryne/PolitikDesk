"""Çok Kanallı (Omnichannel) Editoryal Dışa Aktarım Motoru.

PolitikDesk teyitli olaylarından farklı editoryal ve sosyal medya kanalları
için insan denetimli, kurala dayalı ve yapılandırılmış metinler üretir.
Otomatik yayın YAPMAZ; editörün kopyalayıp veya Web Intent ile inceleyip
yayımlaması için hazır taslaklar sunar (Spec §15/6).
"""

from __future__ import annotations

from typing import Any

STATUS_LABELS: dict[str, str] = {
    "strongly_corroborated": "GÜÇLÜ TEYİTLİ",
    "partially_corroborated": "KISMEN TEYİTLİ",
    "single_source": "TEK KAYNAKLI",
    "contradicted": "ÇELİŞKİLİ",
    "unverified": "DOĞRULANMAMIŞ",
    "attribution_verified": "BEYAN SABİT",
}


def to_x_thread(ev: dict[str, Any], claims: list[dict[str, Any]], articles: list[dict[str, Any]]) -> list[str]:
    """Olayı X/Twitter için 280 karakter sınırına uyumlu zincir (flood) tweetlerine böler."""
    title = str(ev.get("title", "Gelişme"))
    salience = ev.get("salience_score", 0)
    tweets: list[str] = []

    # 1. Başlık Tweeti (Giriş)
    t1 = f"POLİTİKDESK DOĞRULANMIŞ İSTİHBARAT\n\n{title}\n\nGündem Skoru: {salience}/90 · Kaynak Sayısı: {len(articles)}"
    if len(t1) > 275:
        t1 = t1[:272] + "…"
    tweets.append(t1)

    # 2. İddia ve Kanıt Tweetleri (Her biri max 280 karakter)
    for idx, c in enumerate(claims[:5], start=1):
        status = c.get("evidence_status", "unverified")
        status_tag = STATUS_LABELS.get(status, "BİLGİ")
        raw_text = str(c.get("claim_text", "")).strip()

        tweet_body = f"[{status_tag}] {raw_text}"
        if len(tweet_body) > 240:
            tweet_body = tweet_body[:237] + "…"

        tweet = f"({idx}/{min(len(claims), 5)}) {tweet_body}"
        tweets.append(tweet)

    # 3. Kapanış ve Kaynakça Tweeti
    src_names = [str(a.get("source_name") or a.get("slug") or "Kaynak") for a in articles[:4]]
    src_str = " · ".join(src_names) if src_names else "Resmî ve Bağımsız Kaynaklar"
    t_end = f"Doğrulanmış Kaynaklar: {src_str}\n\nDetaylı kanıt dosyası ve geçmiş hafıza PolitikDesk çalışma masasında."
    if len(t_end) > 275:
        t_end = t_end[:272] + "…"
    tweets.append(t_end)

    return tweets


def to_linkedin_brief(ev: dict[str, Any], claims: list[dict[str, Any]], articles: list[dict[str, Any]]) -> str:
    """C-Level yöneticiler ve finans profesyonelleri için yapılandırılmış LinkedIn bilgi notu."""
    title = str(ev.get("title", "Gelişme"))
    salience = ev.get("salience_score", 0)

    lines: list[str] = [
        f"MAKRO GÜNDEM ÖZETİ: {title}",
        "═" * 45,
        f"Gündem Ağırlığı: {salience}/90 | Doğrulama Durumu: {len(articles)} Bağımsız Kaynak",
        "",
        "DOĞRULANMIŞ GELİŞMELER & KANIT ZİNCİRİ:",
    ]

    for c in claims[:4]:
        status = c.get("evidence_status", "unverified")
        tag = STATUS_LABELS.get(status, "BİLGİ")
        lines.append(f"• [{tag}] {c.get('claim_text')}")

    lines.extend([
        "",
        "PİYASA & POLİTİKA ETKİSİ:",
        "Ekonomik aktörlerin beyanları ve kurumsal veriler arasındaki korelasyon PolitikDesk yapay zeka ve kanıt motoru tarafından izlenmektedir.",
        "",
        "KAYNAKÇA:",
    ])

    for a in articles[:4]:
        lines.append(f"- {a.get('source_name')} ({a.get('title', '')})")

    lines.extend(["", "#PolitikDesk #MakroEkonomi #SiyasiHafıza #EkonomiPolitik #VeriOdaklıAnaliz"])
    return "\n".join(lines)


def to_instant_dispatch(ev: dict[str, Any], claims: list[dict[str, Any]], articles: list[dict[str, Any]]) -> str:
    """Telegram ve WhatsApp bültenleri için hızlı, yalın ve madde işaretli anlık haber metni."""
    title = str(ev.get("title", "Gelişme"))
    salience = ev.get("salience_score", 0)

    lines = [
        f"POLİTİKDESK ANLIK BÜLTEN (#{ev.get('id', '')})",
        f"*{title}*",
        f"_Gündem Skoru: {salience}/90 · {len(articles)} Kaynak_",
        "",
        "*Doğrulanan İddialar:*",
    ]

    for c in claims[:4]:
        status = c.get("evidence_status", "unverified")
        tag = STATUS_LABELS.get(status, "BİLGİ")
        lines.append(f"▫️ [{tag}] {c.get('claim_text')}")

    src_names = [str(a.get("source_name") or a.get("slug") or "Kaynak") for a in articles[:4]]
    lines.extend(["", f"*Teyit Eden Kaynaklar:* {', '.join(src_names)}"])
    return "\n".join(lines)


def to_audio_script(ev: dict[str, Any], claims: list[dict[str, Any]], articles: list[dict[str, Any]]) -> str:
    """Sabah podcasti veya sesli brifingler için 60 saniyelik doğal konuşma dili seslendirme metni."""
    title = str(ev.get("title", "Gelişme"))
    claim_sentences = []
    for c in claims[:3]:
        claim_sentences.append(f"{c.get('claim_text')}.")

    claims_spoken = " ".join(claim_sentences) if claim_sentences else "Gelişmeye dair ilk teyitli bilgiler sisteme ulaştı."
    src_count = len(articles)

    script = (
        f"PolitikDesk hızlı gündem bülteni. {title}. "
        f"Çalışma masamıza ulaşan {src_count} bağımsız kaynak verisine göre: {claims_spoken} "
        "Gelişmeler ve siyasi hafıza eşleşmeleri PolitikDesk çalışma masasında güncellenmeye devam ediyor."
    )
    return script
