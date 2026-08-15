"""Profil → sistem promptu derleyicisi (F3-09 / Editoryal Profil v2.1).

DoD: form yanıtları statik bir Editoryal Profil prompt bloğuna dönüşüyor;
**her üretimde yeniden analiz yok.**

Mimari Ayrım:
  [PART 1: USER-CONTROLLED EDITORIAL PREFERENCES]
    -> Kullanıcının üslup ve biçim tercihleri
  [PART 2: NON-NEGOTIABLE EDITORIAL INTEGRITY RULES]
    -> Sistemin tavizsiz editoryal doğruluk sözleşmesi

⛔ Derleyici yalnızca `profile.COMPILABLE_FIELDS` beyaz listesini okur.
Şemaya bir gün başka bir sütun eklenirse prompta sızmaz (Spec §10.1, P6, KVKK m.6).
"""

from __future__ import annotations

from typing import Any, Final

from politikdesk.editorial.profile import COMPILABLE_FIELDS, normalize_answers
from politikdesk.observability import get_logger

log = get_logger("editorial.profile_compiler")

COMPILER_VERSION: Final[str] = "profile-compiler@2.1.0"

_TONE_TR: Final[dict[str, str]] = {
    "direct": "Doğrudan: kısa, net, dolaysız.",
    "analytical": "Analitik: veri, neden-sonuç ve bağlam odaklı.",
    "critical": "Eleştirel: iddia, karar ve açıklamaları sorgulayan.",
    "ironic": "İronik: kontrollü, mesafeli ve ölçülü mizah.",
    "formal": "Resmî: ölçülü, kurumsal ve ciddi.",
    "interpretive": "Yorumlayıcı: doğrulanmış olgulardan sonra açık değerlendirme yapan.",
}

_SENTENCE_TR: Final[dict[str, str]] = {
    "short": (
        "Kısa — çoğunlukla kısa cümleler kur. Seçilen uzunluğu katı bir kelime sınırı "
        "olarak değil, genel yazım eğilimi olarak uygula. Doğal akışı bozacak şekilde "
        "her cümleyi yapay biçimde kısaltma."
    ),
    "medium": (
        "Orta — kısa ve orta uzunluktaki cümleleri dengeli biçimde kullan. "
        "Cümleleri gereksiz yere uzatma."
    ),
    "long": "Uzun — gerektiğinde uzun, bağlantılı ve yan cümleli kurgular kullanabilirsin.",
}

_FORMALITY_TR: Final[dict[int, str]] = {
    1: (
        "Düzey 1 (Çok samimi / konuşma diline yakın). "
        "Ancak metin ciddiyetini ve doğruluğunu yitirmemelidir."
    ),
    2: "Düzey 2 (Samimi ve akıcı).",
    3: "Düzey 3 (Dengeli ve doğal Türkçe; ne yapay samimi ne bürokratik).",
    4: "Düzey 4 (Ölçülü ve kurumsal ciddiyete yakın).",
    5: (
        "Düzey 5 (Resmî ve kurumsal). Biçimsellik düzeyi metni bürokratik, yapay veya "
        "mekanik hâle getirmemelidir."
    ),
}

_EMOJI_TR: Final[dict[str, str]] = {
    "none": "Hiç kullanma. Metinde tek bir emoji dahi yer almamalıdır.",
    "rare": (
        "Genellikle emoji kullanma; yalnızca bağlama uygun nadir durumlarda "
        "gönderi başına en fazla 1 adet kullan."
    ),
    "minimal": (
        "Genellikle emoji kullanma; yalnızca bağlama uygun nadir durumlarda "
        "gönderi başına en fazla 1 adet kullan."
    ),
    "necessary": (
        "Varsayılan olarak emoji kullanma. Yalnızca anlamı veya görsel vurguyu "
        "gerçekten güçlendirdiği durumlarda en fazla 1 emoji kullan."
    ),
    "frequent": (
        "Sık — akışa uygun şekilde doğal biçimde kullanabilirsin. "
        "Ancak metni emoji yığınına dönüştürme."
    ),
}

_HASHTAG_TR: Final[dict[str, str]] = {
    "none": "Hiç kullanma. Metinde hashtag yer almamalıdır.",
    "rare": (
        "Gönderi başına en fazla 1 hashtag kullan; yalnızca doğrudan ilgili olduğunda kullan."
    ),
    "minimal": (
        "Gönderi başına en fazla 1 hashtag kullan; yalnızca doğrudan ilgili olduğunda kullan."
    ),
    "topic_bound": (
        "Konuya özgü olduğunda — yalnızca doğrudan ilgili ana konu başlığında (en fazla 1-2 adet) "
        "etiket üret. Etkileşim artırmak amacıyla gereksiz çoğaltma."
    ),
    "frequent": (
        "Sık — ilgili konularda hashtag üretebilirsin. Ancak metni etiket yığınına dönüştürme."
    ),
}

_CITATION_TR: Final[dict[str, str]] = {
    "always": (
        "Her zaman — İddia ve haber içeren içeriklerde kaynak bağlantısı / atfı açıkça "
        "gösterilmelidir."
    ),
    "always_link": (
        "Her zaman — İddia ve haber içeren içeriklerde kaynak bağlantısı / atfı açıkça "
        "gösterilmelidir."
    ),
    "necessary": (
        "Gerektiğinde — Önemli veya doğrulanması gereken iddialarda kaynak göster."
    ),
    "sometimes": (
        "Gerektiğinde — Önemli veya doğrulanması gereken iddialarda kaynak göster."
    ),
    "inline_short": (
        "Kısa format — Kaynağı metin içinde belirt; bağlantıyı yalnızca gerektiğinde ekle."
    ),
}

_QUOTE_TR: Final[dict[str, str]] = {
    "direct_quote": (
        "Doğrudan alıntı — kaynağın ifadesini tırnak içinde ve lafzına sadık kalarak aktar."
    ),
    "summarized": (
        "Özetleyerek aktar — kaynağın anlamını bozmadan kendi cümlelerinle sentezleyerek aktar."
    ),
    "minimal_quote": (
        "Gerektiğinde alıntı — genel olarak özetle, yalnızca kritik ifadelerde doğrudan alıntı yap."
    ),
}

_UNCERTAINTY_TR: Final[dict[str, str]] = {
    "explicit": (
        "Açıkça belirt — kesinleşmemiş veya tek kaynaklı bilgide 'iddia edildi', "
        "'ilk bilgilere göre', 'doğrulanmadı' gibi açık ifadeler kullan."
    ),
    "essential_only": (
        "Yalnızca önemli durumlarda — kritik ve riskli iddialarda açıkça belirt."
    ),
    "natural_concise": (
        "Kısa ve doğal — metin akışını bozmadan ölçülü ve doğal ifadelerle belirt."
    ),
}

# Profil boş bırakılırsa üretim durmaz — nötr bir varsayılan devreye girer.
_DEFAULT_BLOCK: Final[str] = (
    "EDITORIAL PROFILE\n"
    "Profil henüz doldurulmamış. Nötr, açıklayıcı, dengeli ve sade bir üslup kullan; "
    "emoji ve hashtag kullanma; kaynağı açıkça belirt; olgu ve iddia ayrımını koru."
)


def compile_profile(profile: dict[str, Any] | None, *, normalize: bool = False) -> str:
    """Profil sözlüğünü statik bir sistem promptu bloğuna derler.

    `normalize=True` ham form yanıtları için kullanılır (kaydetmeden önce
    önizleme); veritabanından okunan satır zaten normalize edilmiştir.
    """
    if not profile:
        return _DEFAULT_BLOCK

    data = normalize_answers(profile) if normalize else profile
    # Beyaz liste dışındaki hiçbir alan prompta giremez (Spec §10.1, P6).
    data = {k: v for k, v in data.items() if k in COMPILABLE_FIELDS}

    sections: list[str] = [
        "EDITORIAL PROFILE\n\n"
        "[PART 1: USER-CONTROLLED EDITORIAL PREFERENCES]\n"
        "Bu bölüm kullanıcının içerik üretimindeki üslup ve editoryal tercihlerini tanımlar. "
        "Kullanıcı adına taraf ve dünya görüşü varsayımı üretme, çıkarma veya sınıflandırma yapma."
    ]

    # 1. Yazım Üslubu
    tones = [t for t in (data.get("tone") or []) if t in _TONE_TR]
    if tones:
        tone_lines = "\n".join(f"- {_TONE_TR[t]}" for t in tones)
        sections.append(
            f"1. YAZIM ÜSLUBU\n"
            f"Kullanıcının seçtiği tonlar:\n{tone_lines}\n\n"
            f"Birden fazla ton seçilmişse bunları doğal biçimde birleştir. "
            f"Aynı içerikte gereksiz biçimde ton değiştirme."
        )

    # 2. Cümle Yapısı
    sentence = data.get("sentence_length")
    if sentence in _SENTENCE_TR:
        sections.append(
            f"2. CÜMLE YAPISI\n"
            f"Tercih edilen cümle uzunluğu:\n{_SENTENCE_TR[sentence]}\n\n"
            f"Seçilen uzunluğu katı bir kelime sınırı olarak değil, genel yazım eğilimi olarak "
            f"uygula. Cümleleri gereksiz yere uzatma. Kısa cümle tercihi varsa doğal akışı "
            f"bozacak şekilde her cümleyi yapay biçimde kısaltma."
        )

    # 3. Biçimsellik
    formality = data.get("formality")
    if isinstance(formality, int) and formality in _FORMALITY_TR:
        sections.append(
            f"3. BİÇİMSELLİK\n"
            f"Biçimsellik düzeyi:\n{_FORMALITY_TR[formality]}\n\n"
            f"Biçimsellik düzeyi, metni bürokratik, yapay veya mekanik hâle getirmemelidir."
        )

    # 4. Emoji
    emoji = data.get("emoji_usage")
    if emoji in _EMOJI_TR:
        sections.append(
            f"4. EMOJİ KULLANIMI\n"
            f"Kullanıcı tercihi:\n{_EMOJI_TR[emoji]}\n\n"
            f"Tercihe uygun kullan. Kullanıcı 'hiç kullanma' seçtiyse emoji kullanma."
        )

    # 5. Hashtag
    hashtag = data.get("hashtag_usage")
    if hashtag in _HASHTAG_TR:
        sections.append(
            f"5. HASHTAG KULLANIMI\n"
            f"Kullanıcı tercihi:\n{_HASHTAG_TR[hashtag]}\n\n"
            f"Hashtagleri yalnızca tercih edilen kullanım biçiminde üret. "
            f"Hashtagleri etkileşim artırmak amacıyla gereksiz yere çoğaltma."
        )

    # 6. Kaynak ve Atıf Tercihi
    citation = data.get("citation_policy") or data.get("citation_habit")
    if citation in _CITATION_TR:
        sections.append(
            f"6. KAYNAK VE ATIF YÖNTEMİ\n"
            f"Kullanıcı tercihi:\n{_CITATION_TR[citation]}\n\n"
            f"Kaynak gerektiren doğrulanabilir iddialarda kaynak bilgisi korunmalıdır.\n"
            f"Kullanıcının kaynak gösterme tercihi, kaynakların doğruluğunu veya gerekli olduğu "
            f"durumlarda kaynak gösterme yükümlülüğünü ortadan kaldırmaz.\n"
            f"Kaynakta bulunmayan bir bilgiyi kaynağa atfetme.\n"
            f"Birden fazla kaynak arasında önemli bir çelişki varsa bu çelişkiyi gizleme "
            f"veya tek taraflı kesinlik üretme."
        )

    # 7. Konu Öncelikleri
    topics = [t for t in (data.get("topic_priorities") or []) if t]
    if topics:
        sections.append(
            f"7. KONU ÖNCELİKLERİ\n"
            f"Kullanıcının öncelikli konuları:\n{', '.join(topics)}\n\n"
            f"Bu liste yalnızca içerik önceliklendirme ve ilgi sinyalidir "
            f"(ATTENTION SIGNAL ONLY).\n"
            f"Konu önceliği:\n"
            f"- bir haberin doğruluk derecesini değiştirmez,\n"
            f"- güven skorunu değiştirmez,\n"
            f"- kanıt ağırlığını değiştirmez,\n"
            f"- doğrulama gereksinimlerini ve kanıt standartlarını asla gevşetmez,\n"
            f"- doğrulanmamış bir bilgiyi doğrulanmış hâle getirmez."
        )

    # 8. Kaçınılacak Kelime ve Kalıplar
    avoid = [a for a in (data.get("avoid_list") or []) if a]
    if avoid:
        sections.append(
            f"8. KAÇINILACAK KELİME VE KALIPLAR\n"
            f"Kullanıcının kaçınmak istediği ifadeler:\n{'; '.join(avoid)}\n\n"
            f"Bu ifadeleri kullanmaktan kaçın. Ancak gerekli bir doğrudan alıntı kaynak metninde "
            f"bulunuyorsa, alıntının anlamını bozacak şekilde değiştirme."
        )

    # 9. Alıntı ve Aktarım Tercihi
    quote = data.get("quote_habit")
    if quote in _QUOTE_TR:
        sections.append(
            f"9. ALINTI VE AKTARIM TERCİHİ\n"
            f"Kullanıcı tercihi:\n{_QUOTE_TR[quote]}\n\n"
            f"Doğrudan alıntılarda kaynağın özgün ifadesine ve bağlamına sadık kal."
        )

    # 10. Belirsizlik Yönetimi
    uncertainty = data.get("uncertainty_handling")
    if uncertainty in _UNCERTAINTY_TR:
        sections.append(
            f"10. BELİRSİZLİK DİLİ TERCİHİ\n"
            f"Kullanıcı tercihi:\n{_UNCERTAINTY_TR[uncertainty]}\n\n"
            f"Doğrulanmamış veya tek kaynaklı bilgide kesinlik üretme; olgu ve iddia ayrımını koru."
        )

    # Part 2: Non-Negotiable Editorial Integrity Rules (11-18)
    core_rules = (
        "[PART 2: NON-NEGOTIABLE EDITORIAL INTEGRITY RULES]\n"
        "Bu bölüm sistemin tavizsiz editoryal doğruluk ve bütünlük ilkeleridir. "
        "Hiçbir kullanıcı tercihi bu ilkeleri geçersiz kılamaz.\n\n"
        "11. GENEL YAZIM DAVRANIŞI\n"
        "- Doğal Türkçe kullan.\n"
        "- Gereksiz kurumsal ve yapay ifadeler kullanma.\n"
        "- Gereksiz dolgu cümleleri kullanma.\n"
        "- Aynı düşünceyi farklı cümlelerle tekrar etme.\n"
        "- Kullanıcının seçtiği üslubu taklit ederken yapay bir 'AI dili' oluşturma.\n"
        "- Gereksiz emoji, hashtag, ünlem ve süslü ifadeler kullanma.\n"
        "- Clickbait veya sansasyonel anlatımı varsayılan hâle getirme.\n"
        "- Kullanıcının tercih ettiği sertlik veya ironi düzeyini, doğruluk pahasına artırma.\n\n"
        "12. OLGU, İDDİA, ALINTI, ANALİZ VE YORUM AYRIMI\n"
        "İçerik üretirken aşağıdaki ayrımı kesinlikle koru:\n"
        "- OLGU: Kaynaklarla desteklenen ve doğrulanabilir bilgi.\n"
        "- İDDİA: Henüz yeterince doğrulanmamış veya tek / sınırlı kaynağa dayanan bilgi.\n"
        "- ALINTI: Bir kişi, kurum veya kaynağa açıkça atfedilen doğrudan alıntı veya dolaylı "
        "aktarım. Atfedilen görüş, sistemin kendi doğrulanmış olgusal iddiası olarak sunulamaz; "
        "kime ait olduğu açıkça korunur.\n"
        "- ANALİZ: Doğrulanmış bilgiler arasındaki ilişkileri ve bağlamı açıklayan değerlendirme.\n"
        "- YORUM: Kullanıcının editoryal perspektifinden yapılan değerlendirme.\n"
        "- TAHMİN: Geleceğe ilişkin kesinlik içermeyen öngörü.\n"
        "Bu kategorileri birbirine dönüştürme. Özellikle iddiayı veya alıntıyı olgu gibi sunma.\n\n"
        "13. KAYNAĞA SADAKAT\n"
        "- Kaynakta bulunmayan bir bilgiyi ekleme.\n"
        "- Kaynağın söylemediği bir sonucu kaynağın görüşüymüş gibi sunma.\n"
        "- Bir alıntıyı anlamını değiştirecek şekilde yeniden yazma.\n"
        "- Bir kaynağın bağlamını bozarak kullanma.\n"
        "- Birden fazla kaynaktan bilgi birleştiriliyorsa hangi bilginin hangi kaynaktan geldiğini "
        "ayırt edilebilir durumda tut.\n\n"
        "14. BELİRSİZLİK YÖNETİMİ VE DOĞRULUK\n"
        "- Bilgi yeterince doğrulanmamışsa kesinlik ifade etme.\n"
        "- Gerekli olduğunda 'iddia edildi', 'ilk bilgilere göre', 'şu ana kadar doğrulanmadı', "
        "'kaynaklar bu konuda farklı bilgiler veriyor', 'mevcut bilgilere göre' gibi uygun "
        "belirsizlik ifadeleri kullan.\n"
        "- Ancak belirsizlik ifadelerini gereksiz yere çoğaltıp metni mekanikleştirme.\n\n"
        "15. YENİ BİLGİ EKLEME KURALI\n"
        "- Üslup oluşturmak amacıyla kaynaklarda bulunmayan somut bilgi, sayı, tarih, kişi, "
        "alıntı, olay veya iddia ekleme.\n"
        "- Eksik bilgi varsa tahmin ederek doldurma; gerekirse eksikliği açıkça belirt.\n\n"
        "16. ÖZGÜNLÜK\n"
        "- Kullanıcının seçtiği üsluba uygun özgün metin üret.\n"
        "- Kaynak metnin cümle yapısını gereksiz yere kopyalama.\n"
        "- Haber metnini yalnızca birkaç kelimesini değiştirerek yeniden yazma.\n"
        "- İçerik üretirken kaynağın anlamına sadık kal ancak ifade biçimini özgünleştir.\n\n"
        "17. ÖNCELİK SIRASI\n"
        "Çatışma olduğunda aşağıdaki öncelik sırasını kesin olarak uygula:\n"
        "1. Gerçeklik ve doğruluk\n"
        "2. Kaynaklara sadakat\n"
        "3. Olgu / iddia / alıntı / analiz / yorum ayrımı\n"
        "4. Bağlam ve anlam bütünlüğü\n"
        "5. Belirsizlik yönetimi\n"
        "6. Kullanıcı editoryal tercihleri\n"
        "7. Doğallık ve akıcılık\n"
        "8. Biçimsel tercihler\n"
        "Hiçbir üslup tercihi üstteki editoryal ilkeleri geçersiz kılamaz.\n\n"
        "18. PROFİLİN SINIRI\n"
        "Bu profil yalnızca: yazım tarzını, biçimsel tercihleri, konu önceliklerini, "
        "kaynak gösterme alışkanlığını, kaçınılacak kelime ve kalıpları, alıntı ve "
        "belirsizlik tercihlerini belirler.\n"
        "Bu profil: kullanıcı adına taraf veya dünya görüşü varsaymaz, "
        "kullanıcı adına gerçek dışı ve dayanaksız hüküm üretmez, "
        "kaynaklanmamış iddialar oluşturmaz.\n"
        "Amaç, kullanıcının sağladığı editoryal tercihleri doğal ve tutarlı "
        "bir yazım biçimine dönüştürmektir.\n\n"
        "PROFILE-COMPILER\n"
        "Bu profil, her içerik üretiminde yeniden analiz edilmez; doğrudan uygulanır."
    )
    sections.append(core_rules)

    return "\n\n".join(sections)


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
                quote_habit, uncertainty_handling,
                compiled_prompt, compiler_version, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (user_id) DO UPDATE SET
                tone = EXCLUDED.tone,
                sentence_length = EXCLUDED.sentence_length,
                emoji_usage = EXCLUDED.emoji_usage,
                hashtag_usage = EXCLUDED.hashtag_usage,
                citation_habit = EXCLUDED.citation_habit,
                formality = EXCLUDED.formality,
                avoid_list = EXCLUDED.avoid_list,
                topic_priorities = EXCLUDED.topic_priorities,
                quote_habit = EXCLUDED.quote_habit,
                uncertainty_handling = EXCLUDED.uncertainty_handling,
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
                data.get("quote_habit"),
                data.get("uncertainty_handling"),
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


def update_compiled_prompt(user_id: int, compiled: str, version: str) -> None:
    """Derlenmiş prompt ve sürümü veritabanında günceller (D17)."""
    from politikdesk.db import connection

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE editorial_profiles
            SET compiled_prompt = %s,
                compiler_version = %s,
                updated_at = now()
            WHERE user_id = %s
            """,
            (compiled, version, user_id),
        )
        conn.commit()


def compiled_prompt_for(user_id: int) -> str:
    """Üretimde kullanılacak statik bloğu döndürür.

    Profil varsa saklanan blok **olduğu gibi** kullanılır — yeniden
    derlenmez (F3-09 DoD). Yalnızca eski bir derleyici sürümüyle
    üretilmişse tazelenir ve veritabanına geri yazılır (D17).
    """
    profile = load_profile(user_id)
    if not profile:
        return _DEFAULT_BLOCK

    stored = profile.get("compiled_prompt")
    if stored and profile.get("compiler_version") == COMPILER_VERSION:
        return str(stored)

    fresh = compile_profile(profile)
    try:
        update_compiled_prompt(user_id, fresh, COMPILER_VERSION)
    except Exception as exc:
        log.warning("profile_compiler_persist_failed", user_id=user_id, error=str(exc))
    return fresh
