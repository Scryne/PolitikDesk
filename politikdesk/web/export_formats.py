"""Çok Kanallı (Omnichannel) Editoryal Dışa Aktarım Motoru.

PolitikDesk teyitli olaylarından farklı editoryal ve sosyal medya kanalları
için insan denetimli, kurala dayalı ve yapılandırılmış metinler üretir.
Otomatik yayın YAPMAZ; editörün kopyalayıp veya Web Intent ile inceleyip
yayımlaması için hazır taslaklar sunar (Spec §15/6).
"""

from __future__ import annotations

from typing import Any

# Markdown bağlantısı HTML kaçış katmanının DIŞINDADIR. `esc_url()` yalnızca
# sunucu-üretimi HTML'i korur; buradan çıkan metin Substack/e-bülten gibi
# başka bir işleyiciye gider ve orada bizim kaçışımız devrede değildir.
#
# İki ayrı risk kapatılır:
#   1. Şema — bağlantı `http`/`https` değilse hiç yazılmaz.
#   2. Sözdizimi kaçışı — başlıktaki `]` veya URL'deki `)` bağlantıyı
#      erken kapatıp arkasına serbest Markdown yazılmasına izin verirdi.
_SAFE_LINK_SCHEMES = ("http://", "https://")


def _safe_link_url(raw: object) -> str | None:
    """Markdown bağlantısına yazılabilir bir URL mi? Değilse `None`."""
    url = str(raw or "").strip()
    if not url.lower().startswith(_SAFE_LINK_SCHEMES):
        return None
    # Parantez ve boşluk bağlantı sözdizimini bozar; `<...>` biçimi de
    # `>` içeren bir URL'de kırılır, o yüzden doğrudan kodlanır.
    return url.replace("(", "%28").replace(")", "%29").replace(" ", "%20").replace(">", "%3E")


def _md_text(raw: object) -> str:
    """Markdown bağlantı ETİKETİ için: köşeli parantezleri etkisizleştirir."""
    return str(raw or "").replace("[", r"\[").replace("]", r"\]")


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


def to_bluesky_post(ev: dict[str, Any], claims: list[dict[str, Any]], articles: list[dict[str, Any]]) -> str:
    """Bluesky için azami 300 karakterlik teyitli gönderi metni."""
    title = str(ev.get("title", "Gelişme"))
    salience = ev.get("salience_score", 0)
    top_claim = claims[0].get("claim_text", "") if claims else ""
    status = claims[0].get("evidence_status", "unverified") if claims else "unverified"
    status_tag = STATUS_LABELS.get(status, "BİLGİ")

    post = f"POLİTİKDESK TEYİTLİ İSTİHBARAT\n\n{title}\n[{status_tag}] {top_claim}\n\nGündem Skoru: {salience}/90 · {len(articles)} Kaynak"
    if len(post) > 300:
        post = post[:297] + "…"
    return post


def to_mastodon_post(ev: dict[str, Any], claims: list[dict[str, Any]], articles: list[dict[str, Any]]) -> str:
    """Mastodon için azami 500 karakterlik yapılandırılmış açık kaynak istihbarat gönderisi."""
    title = str(ev.get("title", "Gelişme"))
    salience = ev.get("salience_score", 0)

    lines = [
        f"POLİTİKDESK DOĞRULANMIŞ İSTİHBARAT: {title}",
        f"Gündem Ağırlığı: {salience}/90 · Kaynak Sayısı: {len(articles)}",
        "",
        "Doğrulanan Temel İddialar:",
    ]
    for c in claims[:3]:
        status = c.get("evidence_status", "unverified")
        tag = STATUS_LABELS.get(status, "BİLGİ")
        lines.append(f"• [{tag}] {c.get('claim_text')}")

    src_names = [str(a.get("source_name") or a.get("slug") or "Kaynak") for a in articles[:3]]
    lines.extend([
        "",
        f"Kaynaklar: {', '.join(src_names)}",
        "#PolitikDesk #DoğrulanmışHaber #VeriGazeteciliği #MakroEkonomi",
    ])
    text = "\n".join(lines)
    if len(text) > 500:
        text = text[:497] + "…"
    return text


def to_newsletter_markdown(ev: dict[str, Any], claims: list[dict[str, Any]], articles: list[dict[str, Any]]) -> str:
    """Substack ve kurumsal e-bültenler için hazır, zengin biçimlendirilmiş Markdown bloğu."""
    title = str(ev.get("title", "Gelişme"))
    salience = ev.get("salience_score", 0)

    lines = [
        f"### {title}",
        "",
        f"> **Gündem Skoru:** `{salience}/90` | **Teyit Havuzu:** `{len(articles)} Bağımsız/Resmî Kaynak`",
        "",
        "**Doğrulanmış İddialar ve Kanıt Dökümü:**",
        "",
    ]
    for idx, c in enumerate(claims, start=1):
        status = c.get("evidence_status", "unverified")
        tag = STATUS_LABELS.get(status, "BİLGİ")
        lines.append(f"{idx}. **[{tag}]** {c.get('claim_text')}")

    lines.extend([
        "",
        "**Referans Alınan Kaynaklar:**",
        "",
    ])
    for a in articles:
        label = _md_text(a.get("title", ""))
        source_name = _md_text(a.get("source_name"))
        url = _safe_link_url(a.get("url"))
        if url:
            lines.append(f"- *{source_name}* — [{label}]({url})")
        else:
            # Bağlantı kullanılamıyor: kaynak ve başlık YİNE DE yazılır.
            # Kaynağın nereden geldiğini düşürmek, bozuk bir bağlantıyı
            # düşürmekten daha kötüdür (Spec §9.3 kaynak gösterimi).
            lines.append(f"- *{source_name}* — {label}")

    lines.append("\n---\n")
    return "\n".join(lines)


