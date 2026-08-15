"""Taslak üretimi — 3 açı (F3-10 · Spec §14.1 kalem 9, §14.3).

DoD: girdi yalnızca `claims`+`evidence`; grounding talimatı promptta;
`cited_claim_ids` doluyor.

**Girdinin "yalnızca claims+evidence" olması bir kısıttır, kolaylık
değil.** Olay başlığı, özeti veya makale metni prompta girmez. Sebep
F3-12 ile birliktedir: grounding doğrulayıcısı, modele verilen kanıt
evrenine karşı ölçer. Prompta kanıt seti dışında bir metin sızarsa,
model ondan bir sayı alıp yazdığında denetim "kanıtta yok" der ve
taslak haksız yere düşer — ya da denetim gevşetilir ve kapı anlamını
yitirir. İki kötü seçenekten kaçınmanın yolu girdiyi dar tutmaktır.

Üç açı (Spec §14.3 "Dil kararı"): `Bilgilendir` / `Analiz Et` /
`Eleştir`. Buton metni asla "Tweet Üret" olmaz.

Doğrulama katmanları (Spec §11.5 "prompt talimatı yeterli değil"):
  1. JSON şeması            — yapısal olarak yanlış çıktı üretilemez
  2. `_validate_output()`   — yasak alan, boş gövde, uzunluk
  3. `cited_claim_ids`      — verilmemiş bir iddia kimliği uydurulamaz
  4. `grounding_check`      — kanıtta olmayan sayı/tarih/alıntı (F3-12)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from politikdesk.config import get_settings
from politikdesk.editorial.grounding_check import GroundingReport, build_context, check
from politikdesk.editorial.guards import ClaimForGeneration, require_generation_allowed
from politikdesk.observability import get_logger

log = get_logger(__name__)

PROMPT_VERSION: Final[str] = "draft.v2"

# Spec §14.3 dil kararı — anahtar, etiket, açıklama (v3.4: 4. Açı eklendi).
ANGLES: Final[dict[str, tuple[str, str]]] = {
    "inform": (
        "Bilgilendir",
        "Ne olduğunu aktar. Yorum katma; yalnızca kanıtlanmış unsurları yaz.",
    ),
    "analyze": (
        "Analiz Et",
        "Bunun ne anlama geldiğini açıkla. Çıkarımlarını kanıta bağla ve "
        "yorum olan cümleleri ayrıca işaretle.",
    ),
    "critique": (
        "Eleştir",
        "Kanıttaki boşluğu, çelişkiyi veya eksik bağlamı sorgula. "
        "Eleştiri VERİYE yöneliktir, kişiye değil.",
    ),
    "accountability": (
        "Hesap Sor",
        "Vaat ve hedefleri gerçekleşmesiyle veya geçmiş beyanları güncel durumla "
        "yan yana koy. Her iki ucu da doğrudan kanıta ve kayda bağla.",
    ),
}

# Modelin ÜRETMESİ YASAK alanlar (Spec §8.1). Şemada yoklar; ikinci
# savunma hattı olarak çıktıda da aranır — `nlp/claims.py` ile aynı deyim.
FORBIDDEN_FIELDS: Final[tuple[str, ...]] = (
    "evidence_status", "status", "confidence", "confidence_score",
    "truth", "is_true", "accuracy", "bias", "sentiment", "political",
    "source_bias", "political_leaning",
)

MAX_CITED_CLAIMS: Final[int] = 12
MAX_COMMENTARY: Final[int] = 6
MAX_UNRESOLVED: Final[int] = 5

# Durum etiketleri — kullanıcıya ve modele GÖSTERİLEN dil.
# Renkler Spec §8.1'den; etiket gizlenemez (Spec §15 madde 3).
STATUS_LABELS: Final[dict[str, str]] = {
    "strongly_corroborated": "🟢 güçlü teyitli",
    "partially_corroborated": "🟡 kısmen teyitli",
    "single_source": "🟠 tek kaynaklı",
    "contradicted": "🔴 çelişkili",
    "unverified": "⚪ doğrulanmamış",
    "attribution_verified": "🔵 beyan sabit",
}

TYPE_LABELS: Final[dict[str, str]] = {
    "fact": "olgu",
    "number": "sayısal",
    "attribution": "aktarım",
    "prediction": "tahmin",
    "promise": "vaat/taahhüt",
}

# Yalnızca bu durumlar "biliniyor" gibi yazılabilir. Diğerleri çekinceyle
# aktarılır ve etiketi metinde görünür (Spec §15 madde 3).
ASSERTABLE_STATUSES: Final[frozenset[str]] = frozenset(
    {"strongly_corroborated", "partially_corroborated"}
)


def build_schema(max_chars: int) -> dict[str, Any]:
    """Çıktı şeması. `evidence_status` ve benzeri alanları KABUL ETMEZ."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["body", "cited_claim_ids"],
        "properties": {
            "body": {"type": "string", "minLength": 20, "maxLength": max_chars},
            "cited_claim_ids": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_CITED_CLAIMS,
                "items": {"type": "integer"},
            },
            "commentary_sentences": {
                "type": "array",
                "maxItems": MAX_COMMENTARY,
                "items": {"type": "string", "maxLength": 300},
            },
            "unresolved": {
                "type": "array",
                "maxItems": MAX_UNRESOLVED,
                "items": {"type": "string", "maxLength": 200},
            },
        },
    }


SYSTEM_PROMPT = """Sen bir editoryal ARAŞTIRMA ORTAĞISIN. Türkiye makro ekonomi
gündeminde çalışan bir yazarın taslağını hazırlıyorsun.

Bir metin üreticisi değilsin: yazarın yerine konuşmuyorsun, onun daha iyi
konuşabilmesi için kanıtı derli toplu bir taslağa çeviriyorsun.

TEMEL KURAL — GROUNDING:
Yalnızca sana verilen KANIT SETİ'ndeki bilgiyi kullan. Kanıtta olmayan
hiçbir olgu, sayı, tarih veya alıntı ekleme. Bir bilgi kanıtta yoksa
metne koyma; gerekiyorsa "unresolved" alanına yaz.

Bu kural üsluptan önce gelir. Metin daha akıcı olacak diye kanıtta
olmayan bir sayı, oran, tarih veya isim EKLENEMEZ.

SAYILAR VE TARİHLER — EN SIKI KURAL:
Yazdığın her sayı ve her tarih, kanıt setinde AYNEN geçmelidir.
- Kendi hesabını yapma. İki oranı toplama, farkını alma, yüzde değişim
  türetme. Kanıtta "yüzde 41,2" varsa yazabileceğin sayı odur.
- Kaynak sayısı, makale sayısı gibi sayıları uydurma.
- Yuvarlama yapma. "yaklaşık 41" yazma; kanıt "41,2" diyorsa "41,2" yaz.
- Kanıtta yalnızca ay varsa gün ekleme.

ALINTI:
Tırnak içine aldığın her ifade, kanıt setindeki bir alıntıda AYNEN
geçmelidir. Kendi cümleni tırnak içine alma.

KANIT DURUMU — GİZLENEMEZ:
Her iddianın yanında bir durum etiketi var. Bu etiketi sen üretmedin ve
değiştiremezsin; deterministik bir kural motoru hesapladı.
  🟢 güçlü teyitli / 🟡 kısmen teyitli -> doğrudan aktarılabilir
  🟠 tek kaynaklı  -> "tek kaynağa göre", "X'in aktardığına göre" gibi
                      bir çekinceyle aktarılır
  🔴 çelişkili     -> iki tarafı da yazılır, biri seçilmez
  ⚪ doğrulanmamış -> ya yazılmaz ya da "henüz doğrulanmadı" denerek yazılır
Doğrulanmamış bir iddiayı doğrulanmış gibi sunmak yasaktır.

TAHMİN:
`tahmin` tipindeki iddialar gelecek hakkındadır ve doğrulanamaz. Bunları
olmuş bitmiş gibi yazma; kimin beklentisi olduğunu belirt.

KİŞİLER:
Kimseye suçlama, isnat veya niyet atfetme. Bir kişi hakkında yalnızca
kanıtta ne varsa o yazılır. "Eleştir" açısında bile eleştiri VERİYE ve
KARARA yöneliktir, kişiye değil.

KAYNAKLARA SİYASİ ETİKET YOK:
Hiçbir yayını "yandaş", "muhalif", "sağ", "sol" gibi bir konumla anma.
Kaynaklar adı ve katmanıyla (Tier) anılır.

YAZIM — TASLAĞI KULLANILABİLİR YAPAN BÖLÜM:
Yukarıdaki kurallar taslağın DOĞRU olmasını sağlar; bu bölüm
KULLANILABİLİR olmasını. Çatışırlarsa yukarısı kazanır.

1. KAYNAĞIN CÜMLESİNİ KOPYALAMA.
   Kanıttaki OLGU değişmez: sayı, tarih, özel ad ve tırnak içi ifade
   aynen kalır. Ama kaynağın CÜMLE KURULUŞU senin değil. Kurum metinleri
   uzun, edilgen ve terim yüklüdür; taslak öyle yazılmaz. Olguyu al,
   cümleyi yeniden kur.
   Yeniden kurmak bilgi EKLEMEK DEĞİLDİR: aynı olguyu daha az kelimeyle
   söylemektir. Kanıtta olmayan bir niteleme ekliyorsan durdur.
   Kötü: "...kazancın ilişkili kişiler arasında fiyatlama yoluyla
         aktarılmasına yönelik risklerin belirlenmesini güçlendirecek."
   İyi:  "Sistem, şirketler arası kâr aktarımı riskini izleyecek."

2. İLK CÜMLE EN ÖNEMLİ OLGUYU TAŞIR.
   Varsa sayıyı ilk cümleye koy. Isınma cümlesi kurma, konuya gir.
   Kötü: "Hazine ve Maliye Bakanlığı tarafından açıklanan verilere göre..."
   İyi:  "Merkezi yönetim borç stoku 14.992,5 milyar TL'ye çıktı."

3. ÇEKİNCEYİ SONA EKLEME, CÜMLEYE DOK.
   🟠 tek kaynaklı bir iddiada çekince ayrı bir cümle olarak sona
   yapıştırılmaz; iddiayı taşıyan cümlenin içine girer.
   Kötü: "X oldu. Tek kaynağa göre bu veri açıklandı."
   İyi:  "Hazine'nin açıklamasına göre X oldu."
   Tek kaynaklı olduğu böylece görünür, cümle de bozulmaz.

4. HER SAYI BİR ANLAM TAŞIMALI.
   Sayıları arka arkaya sıralama. Bir sayı yazıyorsan, kanıtta karşılığı
   olan bir kıyas veya bağlam da ver: önceki dönem, toplam içindeki payı,
   hedefe uzaklığı. Kanıtta kıyas YOKSA sayıyı yalın bırak ve eksik olanı
   "unresolved" alanına yaz — kıyası UYDURMA.

5. "ELEŞTİR" AÇISI SOMUT OLMAK ZORUNDA.
   "Daha fazla veri ve bağımsız değerlendirme gerekiyor" bir eleştiri
   değildir; her metne yazılabilir, dolayısıyla hiçbir şey söylemez.
   Eleştiri kanıt setindeki BELİRLİ bir boşluğu gösterir: hangi sayı
   yok, hangi dönem kıyaslanmamış, hangi taraf konuşmamış.
   Somut bir boşluk BULAMIYORSAN düz bir olgu cümlesi yazıp geçme —
   bu, açının işini hiç yapmamaktır. Bunun yerine kanıt setinin
   yanıtlamadığı SORUYU açıkça yaz ve aynı soruyu "unresolved"
   alanına da koy.
   Kötü: "X, en çok vergi ödeyen isimlerden biri oldu." (bu bir haber
         cümlesi, eleştiri değil)
   İyi:  "Liste kimin ne kadar ödediğini göstermiyor; kanıtta tutar yok."

6. UZUNLUK VE RİTİM EDİTORYAL KİMLİK BLOĞUNDAN GELİR.
   Blok "kısa cümle" diyorsa 25 kelimelik kurum cümlesi yazılmaz.
   Blok ile kaynağın üslubu çatışırsa BLOK kazanır.

7. EMOJİ VE HASHTAG: KARAR SENİN DEĞİL.
   Editoryal kimlik bloğu "Emoji KULLANMA" diyorsa metinde TEK BİR emoji
   bile olamaz. "Hashtag KULLANMA" diyorsa metin # işaretiyle başlayan
   hiçbir sözcük içeremez.
   Bu bir üslup önerisi değil, kullanıcının açık tercihidir; metni daha
   canlı yapacağını düşünsen bile EKLEME. Eklersen taslak denetimden
   uyarı ile döner ve kullanıcı onu elle silmek zorunda kalır.

ÇIKTI ALANLARI:
  body                 Taslak metin. Tek parça, yayına hazır.
  cited_claim_ids      Metnin dayandığı iddia kimlikleri. YALNIZCA sana
                       verilen kimliklerden seç; kimlik uydurma.
  commentary_sentences body içindeki YORUM cümleleri birebir. Haber olan
                       cümleleri buraya koyma. Yorum yoksa boş bırak.
  unresolved           Kanıtta olmayan ve bilinmesi gereken şeyler.

YAPMAYACAKLARIN:
- Doğruluk skoru, güven yüzdesi veya benzeri bir yargı alanı üretme.
- Kanıt durumunu değiştirme veya gizleme.
- Hashtag/emoji kurallarını editoryal kimlik bloğu belirler; kendin karar verme.
- Metni "Tweet" olarak adlandırma."""


def _format_claim(claim: ClaimForGeneration) -> str:
    """Bir iddiayı prompta girecek biçimde yazar."""
    type_label = TYPE_LABELS.get(claim.claim_type, claim.claim_type)
    status_label = STATUS_LABELS.get(claim.evidence_status, claim.evidence_status)
    header = f"[C{claim.claim_id}] ({type_label} · {status_label}"
    if claim.status_rule:
        header += f" · kural {claim.status_rule}"
    header += ")"

    lines = [header, f"  İddia: {claim.claim_text}"]

    value = claim.normalized_value or {}
    if value:
        lines.append(
            f"  Değer: {value.get('metric')} = {value.get('value')} "
            f"{value.get('unit', '')} (dönem {value.get('period')})"
        )

    if claim.evidence:
        lines.append("  Kanıt:")
        for item in claim.evidence:
            stance = {"supports": "destekler", "contradicts": "çelişir",
                      "partial": "kısmen"}.get(str(item.get("stance")), "—")
            quote = str(item.get("quote_span") or "").strip()
            source = item.get("source_name") or item.get("source_slug") or "kaynak"
            lines.append(
                f"    - {source} (Tier {item.get('tier', '?')}, {stance})"
                + (f': "{quote}"' if quote else "")
            )
    else:
        lines.append("  Kanıt: yok")

    return "\n".join(lines)


def build_user_prompt(
    *,
    angle: str,
    claims: Sequence[ClaimForGeneration],
    profile_block: str,
    max_chars: int,
) -> str:
    """Kanıt seti + açı + editoryal kimlik. BAŞKA HİÇBİR ŞEY."""
    label, instruction = ANGLES[angle]
    blocks = "\n\n".join(_format_claim(c) for c in claims)

    assertable = [c for c in claims if c.evidence_status in ASSERTABLE_STATUSES]
    weak = [c for c in claims if c.evidence_status not in ASSERTABLE_STATUSES]

    return (
        f"{profile_block}\n\n"
        "KANIT SETİ — bu listenin dışında hiçbir bilgi kullanılamaz:\n\n"
        f"{blocks}\n\n"
        f"ÖZET: {len(assertable)} iddia doğrudan aktarılabilir, "
        f"{len(weak)} iddia çekince gerektiriyor.\n\n"
        f"AÇI: {label}\n"
        f"{instruction}\n\n"
        f"UZUNLUK: en fazla {max_chars} karakter.\n"
        "Şimdi taslağı üret."
    )


@dataclass(frozen=True)
class GeneratedDraft:
    """Üretilmiş ve doğrulanmış bir taslak."""

    angle: str
    body: str
    cited_claim_ids: tuple[int, ...]
    commentary_sentences: tuple[str, ...]
    unresolved: tuple[str, ...]
    grounding: GroundingReport
    model: str
    prompt_version: str
    problems: tuple[str, ...] = ()

    @property
    def is_grounded(self) -> bool:
        return self.grounding.ok

    @property
    def is_usable(self) -> bool:
        """Kullanıcıya sunulabilir mi?

        Grounding ihlali taslağı DÜŞÜRÜR (Spec §15 madde 1). Kayıt yine
        de saklanır: G3 koşul 2 denetimi üretilmiş taslakların tamamını
        sayar, yalnızca hayatta kalanları değil.
        """
        return self.is_grounded and not self.problems

    def as_dict(self) -> dict[str, Any]:
        return {
            "angle": self.angle,
            "angle_label": ANGLES[self.angle][0],
            "body": self.body,
            "cited_claim_ids": list(self.cited_claim_ids),
            "commentary_sentences": list(self.commentary_sentences),
            "unresolved": list(self.unresolved),
            "grounding": self.grounding.as_dict(),
            "model": self.model,
            "prompt_version": self.prompt_version,
            "problems": list(self.problems),
            "is_usable": self.is_usable,
        }


def _string_list(raw: Any, limit: int) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    return tuple(str(item).strip() for item in raw[:limit] if str(item).strip())


def _validate_output(data: dict[str, Any], allowed_ids: set[int]) -> list[str]:
    """Şemanın yakalayamadığı sözleşme ihlallerini toplar."""
    problems: list[str] = []

    for banned in FORBIDDEN_FIELDS:
        if banned in data:
            problems.append(
                f"yasak alan '{banned}': doğruluk yargısı LLM çıktısı olamaz (Spec §8.1)"
            )

    if not str(data.get("body") or "").strip():
        problems.append("body bos")

    raw_ids = data.get("cited_claim_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        problems.append("cited_claim_ids bos — kaynaksiz taslak kabul edilmez (F3-10)")
    else:
        invented = sorted({int(i) for i in raw_ids if isinstance(i, int)} - allowed_ids)
        if invented:
            problems.append(f"uydurulmus iddia kimligi: {invented}")

    return problems


def generate_draft(
    *,
    angle: str,
    claims: Sequence[ClaimForGeneration],
    client: Any,
    profile_block: str = "",
    max_chars: int | None = None,
    user_id: int | None = None,
) -> GeneratedDraft:
    """Bir olaydan tek açılı taslak üretir ve doğrular.

    `client`: `complete_json(...) -> LLMResult`. Testlerde sahte istemci,
    üretimde `politikdesk.llm.client.LLMClient`.

    Kapılar (F3-11, Spec §15 madde 10) LLM çağrısından ÖNCE koşar:
    engellenmiş bir olayda maliyet oluşmaz.
    """
    if angle not in ANGLES:
        raise ValueError(f"Bilinmeyen açı: {angle!r}. Seçenekler: {sorted(ANGLES)}")

    require_generation_allowed(claims)

    max_chars = max_chars or get_settings().draft_max_chars

    result = client.complete_json(
        purpose="draft_generation",
        system=SYSTEM_PROMPT,
        user=build_user_prompt(
            angle=angle, claims=claims, profile_block=profile_block, max_chars=max_chars
        ),
        schema=build_schema(max_chars),
        task="generation",
        prompt_version=PROMPT_VERSION,
        user_id=user_id,
    )

    data = result.data
    allowed_ids = {c.claim_id for c in claims}
    problems = _validate_output(data, allowed_ids)

    body = str(data.get("body") or "").strip()[:max_chars]
    cited = tuple(
        sorted({int(i) for i in (data.get("cited_claim_ids") or []) if isinstance(i, int)}
               & allowed_ids)
    )

    # Grounding evreni, modele GERÇEKTEN verilen kanıt setidir.
    grounding = check(
        body,
        build_context(
            [
                *(c.claim_text for c in claims),
                *(
                    str(e.get("quote_span") or "")
                    for c in claims
                    for e in c.evidence
                ),
                *(
                    str(e.get("source_name") or "")
                    for c in claims
                    for e in c.evidence
                ),
            ],
            normalized_values=[c.normalized_value for c in claims if c.normalized_value],
        ),
    )

    draft = GeneratedDraft(
        angle=angle,
        body=body,
        cited_claim_ids=cited,
        commentary_sentences=_string_list(data.get("commentary_sentences"), MAX_COMMENTARY),
        unresolved=_string_list(data.get("unresolved"), MAX_UNRESOLVED),
        grounding=grounding,
        model=result.model,
        prompt_version=PROMPT_VERSION,
        problems=tuple(problems),
    )

    if not draft.is_usable:
        log.warning(
            "draft_rejected",
            angle=angle,
            grounding_issues=[i.token for i in grounding.issues][:5],
            problems=problems[:3],
        )

    return draft


__all__ = [
    "ANGLES",
    "PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "GeneratedDraft",
    "build_schema",
    "build_user_prompt",
    "generate_draft",
]
