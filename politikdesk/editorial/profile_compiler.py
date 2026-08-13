"""Profil → sistem promptu derleyicisi (F3-09).

DoD: form yanıtları statik prompt bloğuna dönüşüyor; **her üretimde
yeniden analiz yok.**

Neden derlenmiş bir blok: Spec §10.2 stil öğrenmeyi (500 tweet analizi)
MVP dışında bırakıp yerine formu koydu. Form yanıtlarını her taslak
üretiminde yeniden yorumlatmak, kaldırılan maliyeti geri getirirdi.
Derleme bir kez yapılır, `editorial_profiles.compiled_prompt`'a yazılır
ve üretimde olduğu gibi kullanılır.

⛔ Derleyici yalnızca `profile.COMPILABLE_FIELDS` beyaz listesini okur.
Şemaya bir gün başka bir sütun eklenirse prompta sızmaz (Spec §10.1).
"""

from __future__ import annotations

from typing import Any, Final

from politikdesk.editorial.profile import COMPILABLE_FIELDS, normalize_answers

COMPILER_VERSION: Final[str] = "profile-compiler@1.0.0"

_TONE_TR: Final[dict[str, str]] = {
    "direct": "doğrudan (kısa, iddialı, süssüz)",
    "analytical": "analitik (veriyi açan, bağlam kuran)",
    "ironic": "ironik (mesafeli, esprili)",
    "formal": "resmî (ölçülü, kurumsal)",
}

_SENTENCE_TR: Final[dict[str, str]] = {
    "short": "Kısa cümleler kur (10-15 kelime). Yan cümleden kaçın.",
    "medium": "Orta uzunlukta cümleler kur (15-25 kelime).",
    "long": "Uzun, yan cümleli kurgular kullanabilirsin.",
}

_EMOJI_TR: Final[dict[str, str]] = {
    "none": "Emoji KULLANMA.",
    "minimal": "Emojiyi yalnızca gerçekten gerekliyse ve en fazla bir kez kullan.",
    "frequent": "Emoji kullanabilirsin.",
}

_HASHTAG_TR: Final[dict[str, str]] = {
    "none": "Hashtag KULLANMA.",
    "minimal": "En fazla bir hashtag kullan.",
    "frequent": "Hashtag kullanabilirsin.",
}

_CITATION_TR: Final[dict[str, str]] = {
    "always_link": "Kaynağı her zaman açıkça belirt; metin bir link taşıyacak şekilde kurulsun.",
    "sometimes": "Kaynağı önemli sayısal iddialarda açıkça belirt.",
    "never": "Kaynağı metin içinde adıyla belirt; link biçimi kullanma.",
}

_FORMALITY_TR: Final[dict[int, str]] = {
    1: "Çok samimi bir dil kullan; konuşma diline yakın.",
    2: "Samimi ama derli toplu bir dil kullan.",
    3: "Nötr bir dil kullan; ne samimi ne resmî.",
    4: "Ölçülü ve resmiyete yakın bir dil kullan.",
    5: "Resmî bir dil kullan; argo ve kısaltma yok.",
}

# Profil boş bırakılırsa üretim durmaz — nötr bir varsayılan devreye girer.
# Alternatif (profil zorunlu) ilk kullanımda ürünü kilitlerdi.
_DEFAULT_BLOCK: Final[str] = (
    "EDİTORYAL KİMLİK\n"
    "Profil henüz doldurulmamış. Nötr, açıklayıcı ve sade bir üslup kullan; "
    "emoji ve hashtag kullanma; kaynağı açıkça belirt."
)


def compile_profile(profile: dict[str, Any] | None, *, normalize: bool = False) -> str:
    """Profil sözlüğünü statik bir sistem promptu bloğuna derler.

    `normalize=True` ham form yanıtları için kullanılır (kaydetmeden önce
    önizleme); veritabanından okunan satır zaten normalize edilmiştir.
    """
    if not profile:
        return _DEFAULT_BLOCK

    data = normalize_answers(profile) if normalize else profile
    # Beyaz liste dışındaki hiçbir alan prompta giremez (Spec §10.1).
    data = {k: v for k, v in data.items() if k in COMPILABLE_FIELDS}

    lines: list[str] = ["EDİTORYAL KİMLİK", "Kullanıcının biçimsel tercihleri:"]

    tones = [t for t in (data.get("tone") or []) if t in _TONE_TR]
    if tones:
        lines.append(f"- Ton: {', '.join(_TONE_TR[t] for t in tones)}.")

    for key, table in (
        ("sentence_length", _SENTENCE_TR),
        ("emoji_usage", _EMOJI_TR),
        ("hashtag_usage", _HASHTAG_TR),
        ("citation_habit", _CITATION_TR),
    ):
        value = data.get(key)
        if value in table:
            lines.append(f"- {table[value]}")

    formality = data.get("formality")
    if isinstance(formality, int) and formality in _FORMALITY_TR:
        lines.append(f"- {_FORMALITY_TR[formality]}")

    avoid = [a for a in (data.get("avoid_list") or []) if a]
    if avoid:
        lines.append(
            "- KAÇIN: aşağıdaki kalıpları kullanma — "
            + "; ".join(avoid)
            + ". Bu kullanıcının kendi kuralıdır."
        )

    topics = [t for t in (data.get("topic_priorities") or []) if t]
    if topics:
        lines.append(
            f"- Kullanıcının ilgi alanları: {', '.join(topics)}. "
            "Bu bilgi ÜSLUP içindir; kanıtta olmayan bir konuyu metne sokma."
        )

    # Bu satır, biçimsel tercihlerin grounding kuralını ezmesini engeller.
    # Test edilmiş bir gerçek: "iddialı yaz" talimatı olan modeller,
    # kanıtı olmayan bir cümleyi vurgu uğruna eklemeye daha yatkındır.
    lines.append(
        "\nBu tercihler yalnızca ÜSLUBU belirler. Hiçbiri, kanıta bağlı "
        "kalma kuralını gevşetmez: üslup uğruna kanıtta olmayan bir bilgi "
        "eklenemez."
    )

    return "\n".join(lines)


def compile_and_store(user_id: int, answers: dict[str, Any]) -> dict[str, Any]:
    """Form yanıtlarını doğrular, kaydeder ve derlenmiş bloğu yazar.

    Derleme kayıtla aynı işlemde yapılır: profil güncellenip promptu
    eski kalırsa, üretim sessizce eski üslupla koşardı.
    """
    import json

    from politikdesk.db import connection, fetch_one

    data = normalize_answers(answers)
    compiled = compile_profile(data)

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO editorial_profiles (
                user_id, tone, sentence_length, emoji_usage, hashtag_usage,
                citation_habit, formality, avoid_list, topic_priorities,
                compiled_prompt, compiler_version, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (user_id) DO UPDATE SET
                tone = EXCLUDED.tone,
                sentence_length = EXCLUDED.sentence_length,
                emoji_usage = EXCLUDED.emoji_usage,
                hashtag_usage = EXCLUDED.hashtag_usage,
                citation_habit = EXCLUDED.citation_habit,
                formality = EXCLUDED.formality,
                avoid_list = EXCLUDED.avoid_list,
                topic_priorities = EXCLUDED.topic_priorities,
                compiled_prompt = EXCLUDED.compiled_prompt,
                compiler_version = EXCLUDED.compiler_version,
                updated_at = now()
            RETURNING user_id
            """,
            (
                user_id,
                data["tone"],
                data["sentence_length"],
                data["emoji_usage"],
                data["hashtag_usage"],
                data["citation_habit"],
                data["formality"],
                data["avoid_list"],
                data["topic_priorities"],
                compiled,
                COMPILER_VERSION,
            ),
        )
        fetch_one(cur)
        cur.execute(
            """
            INSERT INTO audit_log (actor, action, target, payload)
            VALUES (%s, 'editorial_profile_updated', %s, %s::jsonb)
            """,
            (
                f"user:{user_id}",
                f"editorial_profiles/{user_id}",
                json.dumps({"compiler_version": COMPILER_VERSION}, ensure_ascii=False),
            ),
        )
        conn.commit()

    return {**data, "compiled_prompt": compiled, "compiler_version": COMPILER_VERSION}


def load_profile(user_id: int) -> dict[str, Any] | None:
    """Kaydedilmiş profili döndürür (yoksa `None`)."""
    from politikdesk.db import connection

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM editorial_profiles WHERE user_id = %s", (user_id,)
        )
        row = cur.fetchone()
    return dict(row) if row else None


def compiled_prompt_for(user_id: int) -> str:
    """Üretimde kullanılacak statik bloğu döndürür.

    Profil varsa saklanan blok **olduğu gibi** kullanılır — yeniden
    derlenmez (F3-09 DoD). Yalnızca eski bir derleyici sürümüyle
    üretilmişse tazelenir.
    """
    profile = load_profile(user_id)
    if not profile:
        return _DEFAULT_BLOCK

    stored = profile.get("compiled_prompt")
    if stored and profile.get("compiler_version") == COMPILER_VERSION:
        return str(stored)
    return compile_profile(profile)
