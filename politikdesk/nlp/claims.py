"""İddia çıkarımı (F2-06…F2-10).

DoD:
  F2-06  LLM her makaleden atomik iddialar çıkarıyor; JSON şema doğrulaması
         var; prompt sürümlü.
  F2-07  İddia tipi sınıflandırma (fact / number / attribution / prediction).
  F2-08  Sayısal değer normalizasyonu.
  F2-09  Aynı olayda semantik olarak aynı iddia iki kez kaydedilmiyor.
  F2-10  Kanıt eşleme: ≤200 karakter alıntı + `stance` + `extracted_by`.

**Bu modül LLM kullanır ve `evidence/` altında DEĞİLDİR.** Ayrım Spec
§8.1'in yasağıdır: LLM iddiayı *çıkarır*, durumunu *belirlemez*. Çıktı
şeması `evidence_status` alanını kabul etmez; şema doğrulaması bunu
zorlar.

Doğrulama katmanları (prompt talimatı tek başına yeterli değildir —
Spec §11.5 "programatik kontrol"):

  1. JSON şeması — model yapısal olarak yanlış çıktı veremez
  2. `validate_claim()` — tip/alan tutarlılığı, yasak alan taraması
  3. `verify_quote()` — alıntı kaynak metinde AYNEN geçiyor mu
  4. `dedupe_claims()` — aynı iddianın tekrarı
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from politikdesk.observability import get_logger

log = get_logger(__name__)

PROMPT_VERSION = "claims.v3"
MAX_QUOTE_LEN = 200  # migrations/0001: CONSTRAINT quote_span_len
MAX_CLAIM_LEN = 500

CLAIM_TYPES = ("fact", "number", "attribution", "prediction", "promise")

VALID_METRICS = (
    "tufe_monthly",
    "tufe_annual",
    "ufe_monthly",
    "ufe_annual",
    "policy_rate",
    "overnight_lending_rate",
    "overnight_borrowing_rate",
    "unemployment_rate",
    "employment_rate",
    "participation_rate",
    "gdp_growth_annual",
    "gdp_growth_quarterly",
    "industrial_production",
    "current_account_balance",
    "budget_balance",
    "trade_balance",
    "minimum_wage",
    "public_debt",
    "reserves",
    "exchange_rate",
    "other",
)

# Modelin ÜRETMESİ YASAK alanlar. Şemada yoklar; burada ikinci savunma
# hattı olarak da denetlenir (Spec §8.1).
FORBIDDEN_FIELDS = (
    "evidence_status",
    "status",
    "confidence",
    "confidence_score",
    "truth",
    "is_true",
    "accuracy",
    "bias",
    "sentiment",
    "political",
)

# ---------------------------------------------------------------- şema
CLAIMS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["claims"],
    "properties": {
        "claims": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim_text", "claim_type", "quote_span"],
                "properties": {
                    "claim_text": {"type": "string", "maxLength": MAX_CLAIM_LEN},
                    "claim_type": {"type": "string", "enum": list(CLAIM_TYPES)},
                    "quote_span": {"type": "string", "maxLength": MAX_QUOTE_LEN},
                    "normalized_value": {
                        "type": ["object", "null"],
                        "additionalProperties": False,
                        "required": ["metric", "value", "unit", "period"],
                        "properties": {
                            "metric": {"type": "string", "enum": list(VALID_METRICS)},
                            "value": {"type": "number"},
                            "unit": {"type": "string"},
                            "period": {"type": "string"},
                        },
                    },
                },
            },
        }
    },
}

# Dönem sözlüğü: yıl, ay, gün (tam tarih), çeyrek ve YARIYIL (B-82).
# Yarıyıl (`2026-H1`) ve tam tarih (`2026-08-15`) ekonomi ve politika
# verilerinde (günlük faiz, kur, bütçe bildirimi) mevcuttur.
_PERIOD_RE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?|-Q[1-4]|-H[12])?$")


@dataclass(frozen=True)
class ExtractedClaim:
    """Bir makaleden çıkarılmış atomik iddia."""

    claim_text: str
    claim_type: str
    quote_span: str
    normalized_value: dict[str, Any] | None = None
    problems: tuple[str, ...] = field(default=())

    @property
    def is_valid(self) -> bool:
        return not self.problems


# ------------------------------------------------------------- doğrulama
def fold_text(text: str) -> str:
    """Alıntı karşılaştırması için normalleştirme.

    Yayınlar tipografik tırnak, kesme işareti ve boşluk biçimlerinde
    tutarsızdır; modelin alıntıyı bunlardan biriyle vermesi uydurma
    değildir. Anlamı değiştiren fark aranır, biçimi değil.

    Kamuya açıktır: `editorial/grounding_check.py` (F3-12) aynı
    normalleştirmeyi kullanmak ZORUNDA. İki farklı katlama, iddia
    çıkarımında kabul edilen bir alıntının taslak denetiminde
    uydurma sayılmasına yol açardı.
    """
    text = text.replace("İ", "i").replace("I", "ı").lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    for ch in "“”\"'’‘`´":
        text = text.replace(ch, "")
    return re.sub(r"\s+", " ", text).strip()


def verify_quote(quote: str, source_text: str) -> bool:
    """Alıntı kaynak metinde AYNEN geçiyor mu (F2-10 halüsinasyon savunması).

    Prompt "birebir alıntıla" der; bu, o talimatın **programatik
    kontrolüdür** (Spec §11.5). Geçmeyen alıntı uydurulmuş sayılır ve
    iddia reddedilir.
    """
    if not quote:
        return False
    return fold_text(quote) in fold_text(source_text)


def validate_claim(raw: dict[str, Any], source_text: str) -> ExtractedClaim:
    """Bir iddiayı doğrular; sorunları `problems` alanında toplar."""
    problems: list[str] = []

    for banned in FORBIDDEN_FIELDS:
        if banned in raw:
            problems.append(f"yasak alan '{banned}': kanit durumu LLM ciktisi olamaz (Spec §8.1)")

    claim_text = (raw.get("claim_text") or "").strip()
    claim_type = raw.get("claim_type")
    quote = (raw.get("quote_span") or "").strip()
    value = raw.get("normalized_value")

    if not claim_text:
        problems.append("claim_text bos")
    if claim_type not in CLAIM_TYPES:
        problems.append(f"gecersiz claim_type: {claim_type!r}")
    if len(quote) > MAX_QUOTE_LEN:
        problems.append(f"quote_span {len(quote)} karakter (azami {MAX_QUOTE_LEN})")
    elif not verify_quote(quote, source_text):
        problems.append("quote_span kaynak metinde bulunamadi (uydurulmus alinti)")

    if claim_type == "number":
        if not value:
            problems.append("'number' tipinde normalized_value zorunlu (F2-08)")
        else:
            problems.extend(_validate_value(value))
    elif value:
        problems.append(f"normalized_value yalniz 'number' tipinde olur, '{claim_type}' degil")

    return ExtractedClaim(
        claim_text=claim_text[:MAX_CLAIM_LEN],
        claim_type=claim_type or "fact",
        quote_span=quote[:MAX_QUOTE_LEN],
        normalized_value=value,
        problems=tuple(problems),
    )


def _validate_value(value: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if value.get("metric") not in VALID_METRICS:
        problems.append(f"gecersiz metric: {value.get('metric')!r}")
    if not isinstance(value.get("value"), int | float):
        problems.append("normalized_value.value sayi olmali")
    if not value.get("unit"):
        problems.append("normalized_value.unit bos")
    period = value.get("period") or ""
    if not _PERIOD_RE.match(period):
        problems.append(f"gecersiz period: {period!r} (bekleniyor: 2026-07 / 2026-Q1 / 2026)")
    return problems


# ------------------------------------------------------- tekilleştirme
def claim_signature(claim: ExtractedClaim) -> str:
    """F2-09: aynı iddianın iki kez kaydedilmesini engelleyen imza.

    Sayısal iddialarda imza **normalize edilmiş değerdir**: "TÜFE aylık
    %1,78 arttı" ile "Aylık enflasyon yüzde 1,78 oldu" farklı cümlelerdir
    ama aynı iddiadır. Sözcük tabanlı bir imza bunları ayrı sayardı.

    Kamuya açıktır: `claims_pipeline._persist` aynı imzayı, **zaten
    kayıtlı** iddiaları tanımak için kullanır (F5-16). İki farklı imza
    hesabı, yeniden çıkarımda aynı iddianın ikinci kez yazılmasına ve
    kanıt bağlarının iki ayrı kayda bölünmesine yol açardı — yani
    `independent_count` yine hiç yükselmezdi.
    """
    if claim.claim_type == "number" and claim.normalized_value:
        v = claim.normalized_value
        return f"num:{v.get('metric')}:{v.get('value')}:{v.get('period')}"

    tokens = sorted(set(re.findall(r"\w+", fold_text(claim.claim_text))))
    return f"{claim.claim_type}:{' '.join(tokens)}"


def dedupe_claims(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    """Aynı imzalı iddiaları teke indirir; ilk görülen kazanır.

    ⚠ Kaynak bilgisi taşımaz. Bir iddianın KAÇ kaynakta geçtiği önemliyse
    `group_claims_by_source` kullanın — tekilleştirmenin attığı şey tam
    olarak o bilgidir (B-79).
    """
    seen: set[str] = set()
    out: list[ExtractedClaim] = []
    for claim in claims:
        signature = claim_signature(claim)
        if signature in seen:
            continue
        seen.add(signature)
        out.append(claim)
    return out


def group_claims_by_source(
    collected: list[tuple[ExtractedClaim, int]],
) -> list[tuple[ExtractedClaim, list[tuple[int, str]]]]:
    """Aynı iddiayı teke indirir ama **kaynaklarını biriktirir** (B-79).

    Bu fonksiyon bir hata düzeltmesidir ve düzelttiği hata ürünün ana
    vaadini sessizce çürütüyordu.

    Eskiden `run()` şunu yapıyordu:

        deduped = dedupe_claims([c for c, _ in collected])
        kept    = {id(c) for c in deduped}
        final   = [(c, aid) for c, aid in collected if id(c) in kept]

    Yani iki bağımsız kaynak aynı iddiayı söylediğinde, ikinci kaynağın
    (iddia, makale) çifti **tamamen atılıyordu** — yalnızca yinelenen
    iddia metni değil, o kaynağın KANIT BAĞI da. Sonuç: hiçbir iddia
    birden fazla kanıta ulaşamıyordu.

    Bunun bedeli ölçüldü (13 Ağustos 2026): 48 iddianın tamamı
    `single_source` ya da `unverified`; tek bir `corroborated` yok;
    `diversity_ratio` = 1,0. Backlog bunu "çapraz teyit edecek bağımsız
    kaynak yok" (B-79) diye teşhis etmişti. **Teşhis yanlıştı:** kaynak
    vardı, kod onu atıyordu. Sekiz kaynak da canlı olsa oran 1,0'da
    kalırdı, çünkü R2/R4'ün saydığı `independent_count` hiçbir zaman
    1'i geçemezdi.

    Sayısal iddialarda imza `metric:value:period`e normalize edilir —
    yani hata tam da **çapraz teyidin en net olduğu** yolda tetikleniyordu.

    Dönüş: her imza için (temsilci iddia, [(makale_id, alıntı), ...]).
    Alıntı makale başına ayrı tutulur: kanıt bağı, iddianın o kaynakta
    hangi sözlerle geçtiğini göstermelidir; başka bir makalenin cümlesini
    göstermek kanıtın kendisini yanlışlar.
    """
    order: list[str] = []
    groups: dict[str, tuple[ExtractedClaim, list[tuple[int, str]]]] = {}

    for claim, article_id in collected:
        signature = claim_signature(claim)
        if signature not in groups:
            groups[signature] = (claim, [])
            order.append(signature)

        _, sources = groups[signature]
        # Aynı makale aynı iddiayı iki kez üretebilir (LLM tekrarı);
        # kanıt bağı makale başına tektir.
        if any(existing_id == article_id for existing_id, _ in sources):
            continue
        sources.append((article_id, claim.quote_span))

    return [groups[sig] for sig in order]


# -------------------------------------------------------------- çıkarım
SYSTEM_PROMPT = """Sen bir haber metninden ATOMİK İDDİALARI çıkaran bir çıkarım aracısın.
Türkiye makro ekonomi gündemi üzerinde çalışıyorsun.

TEMEL KURAL — GROUNDING:
Yalnızca sana verilen metindeki bilgiyi kullan. Metinde olmayan hiçbir
olgu, sayı, tarih, isim veya alıntı ekleme. Metinden çıkarılamayan bir
alan varsa null bırak. Emin değilsen iddiayı hiç çıkarma.

ATOMİK İDDİA NEDİR:
Tek bir doğrulanabilir önerme. "TCMB faizi %37'de sabit tuttu ve
enflasyonun temmuzda yükseleceğini öngördü" İKİ iddiadır:
  1. (fact)       TCMB politika faizini yüzde 37'de sabit tuttu
  2. (prediction) TCMB enflasyonun temmuzda yükseleceğini öngördü

İDDİA TİPLERİ — tam olarak biri:
  fact        Gerçekleşmiş, doğrulanabilir olay. "Kurul faizi sabit tuttu."
  number      Sayısal bir büyüklük bildiren iddia. "TÜFE aylık yüzde 1,78 arttı."
  attribution Birinin söylediği/açıkladığı şey. "Bakan Şimşek dezenflasyonun
              sürdüğünü söyledi." Söylenmiş olması olgudur; içeriği ayrıdır.
  prediction  Gelecek hakkında genel tahmin/öngörü. "Enflasyonun düşmesi bekleniyor."
  promise     Bir aktörün resmî vaadi, taahhüdü veya hedefi. "Bakan 2026 sonunda
              enflasyonun yüzde 15'e ineceğini taahhüt etti."

TİP AYRIMINDA DİKKAT:
- Bir sayı içeriyor diye her iddia `number` değildir. `number`, iddianın
  ÖZÜ bir ölçüm ise kullanılır.
- Beklenti, genel tahmin "bekleniyor", "öngörülüyor" ifadeleri `prediction`'dır.
- Açık bir siyasi/kamusal taahhüt, vaat ve hedef bildiren beyanlar `promise`'tir.
- "X, Y olacağını söyledi" (öngörü ise) → `prediction`.
- "X, Y yapacağını taahhüt etti/söz verdi" → `promise`.
- "X, Y olduğunu söyledi" → `attribution`.

SAYISAL NORMALİZASYON (`number` tipinde ZORUNLU):
  metric  Ölçülen büyüklüğün kanonik adı (aşağıdaki listeden)
  value   Sayı (ondalık ayırıcı nokta: 1,78 -> 1.78)
  unit    "%", "TL", "USD", "kisi", "adet"
  period  Ölçüm dönemi ISO: "2026-07" (ay), "2026-Q1" (çeyrek),
          "2026-H1" (yarıyıl), "2026" (yıl)

İzinli metric değerleri:
  tufe_monthly, tufe_annual, ufe_monthly, ufe_annual,
  policy_rate, overnight_lending_rate, overnight_borrowing_rate,
  unemployment_rate, employment_rate, participation_rate,
  gdp_growth_annual, gdp_growth_quarterly, industrial_production,
  current_account_balance, budget_balance, trade_balance,
  minimum_wage, public_debt, reserves, exchange_rate, other

METRİK SEÇİMİ — ÖNEMLİ:
Ölçümü GERÇEKTEN karşılayan kodu seç. Hiçbiri karşılamıyorsa "other" yaz.
Yakın görünen ama farklı bir göstergeyi ASLA seçme: yanlış kod, birbiriyle
ilgisiz iki sayının çelişki sanılmasına yol açar. Örneğin AR-GE harcaması
"reserves" DEĞİLDİR; listede karşılığı yoksa "other"dır.

ALINTI (`quote_span`):
  Her iddia için metinden EN FAZLA 200 KARAKTER birebir alıntı ver.
  Alıntı metinde AYNEN geçmelidir; kısaltma veya düzeltme yapma.
  200 karakteri aşan bir dayanak varsa en özlü kısmını seç.

YAPMAYACAKLARIN:
- Doğruluk yargısı verme. İddianın doğru olup olmadığı senin işin değil.
- Kaynağa siyasi etiket verme.
- Metinde olmayan bağlam ekleme.
- Aynı iddiayı farklı sözcüklerle iki kez çıkarma."""

POLITICAL_PROMPT_VERSION = "claims.siyaset.v1"
POLITICAL_SYSTEM_PROMPT = """Sen bir haber metninden ATOMİK İDDİALARI çıkaran bir çıkarım aracısın.
Türkiye siyaset, yasama, meclis ve kamu politikaları gündemi üzerinde çalışıyorsun.

TEMEL KURAL — GROUNDING:
Yalnızca sana verilen metindeki bilgiyi kullan. Metinde olmayan hiçbir
olgu, sayı, tarih, isim veya alıntı ekleme. Metinden çıkarılamayan bir
alan varsa null bırak. Emin değilsen iddiayı hiç çıkarma.

ATOMİK İDDİA NEDİR:
Tek bir doğrulanabilir önerme veya siyasi beyan.
  1. (fact)        TBMM Genel Kurulu 9. Yargı Paketini kabul etti.
  2. (promise)     Genel Başkan Özel ilk 100 günde mülakatı kaldıracaklarını taahhüt etti.
  3. (attribution) Bakan Yerlikaya organize suç örgütlerine operasyon yapıldığını açıkladı.

İDDİA TİPLERİ — tam olarak biri:
  fact        Gerçekleşmiş yasama, yargı veya idari olay. "Kanun teklifi kabul edildi."
  number      Sayısal büyüklük bildiren iddia (ödenek, kadro, ceza, oy).
  attribution Siyasi aktörün beyanı, eleştirisi veya duruşu. "Lider X politikayı eleştirdi."
  prediction  Geleceğe dönük genel siyasi tahmin veya seçim öngörüsü.
  promise     Açık siyasi vaat, hedef veya taahhüt ("yapacağız", "kaldıracağız", "getireceğiz").

SİYASİ VAAT (PROMISE) ÖZEL DİKKAT:
- Bir aktör geleceğe dönük açık bir taahhütte bulunuyorsa ("seçilince...",
  "2026 sonuna kadar...", "kanun teklifi vereceğiz") tip 'promise' olmalıdır.
- Sadece gerçekleşmiş açıklamalar 'attribution', bağlayıcı sözler 'promise'tir.

ALINTI (`quote_span`):
  Her iddia için metinden EN FAZLA 200 KARAKTER birebir alıntı ver.

YAPMAYACAKLARIN:
- Yorum katma, tarafsızlığı bozma.
- İddianın haklılığına dair hüküm verme."""


def get_system_prompt(vertical: str = "macro_economy") -> tuple[str, str]:
    """Dikey için geçerli prompt ve sürüm bilgisini döndürür."""
    if vertical in {"legislation", "social"}:
        return POLITICAL_SYSTEM_PROMPT, POLITICAL_PROMPT_VERSION
    return SYSTEM_PROMPT, PROMPT_VERSION


def build_user_prompt(
    *, title: str, excerpt: str, source_name: str, tier: int, published_at: str
) -> str:
    return (
        f"KAYNAK: {source_name} (Tier {tier})\n"
        f"YAYIN TARİHİ: {published_at}\n\n"
        f"BAŞLIK: {title}\n\n"
        f"METİN: {excerpt}\n\n"
        "Bu metinden atomik iddiaları çıkar."
    )


@dataclass(frozen=True)
class ExtractionResult:
    claims: list[ExtractedClaim]
    rejected: list[ExtractedClaim]
    model: str
    prompt_version: str

    @property
    def extracted_by(self) -> str:
        """`evidence.extracted_by` alanına yazılır (denetlenebilirlik)."""
        return f"{self.model}+{self.prompt_version}"


def extract_claims(
    *,
    title: str,
    excerpt: str,
    source_name: str,
    tier: int,
    published_at: str,
    client: Any,
    vertical: str = "macro_economy",
) -> ExtractionResult:
    """Bir makaleden iddiaları çıkarır ve doğrular.

    `client`: `complete_json(...) -> LLMResult` sağlayan nesne. Testlerde
    sahte istemci verilir; üretimde `politikdesk.llm.client.LLMClient`.
    """
    source_text = f"{title} {excerpt}"
    system_prompt, prompt_ver = get_system_prompt(vertical)

    result = client.complete_json(
        purpose="claim_extraction",
        system=system_prompt,
        user=build_user_prompt(
            title=title,
            excerpt=excerpt,
            source_name=source_name,
            tier=tier,
            published_at=published_at,
        ),
        schema=CLAIMS_SCHEMA,
        task="extraction",
        prompt_version=prompt_ver,
    )

    validated = [validate_claim(raw, source_text) for raw in result.data.get("claims", [])]
    accepted = dedupe_claims([c for c in validated if c.is_valid])
    rejected = [c for c in validated if not c.is_valid]

    if rejected:
        log.warning(
            "claims_rejected",
            count=len(rejected),
            reasons=[p for c in rejected for p in c.problems][:5],
        )

    return ExtractionResult(
        claims=accepted,
        rejected=rejected,
        model=result.model,
        prompt_version=prompt_ver,
    )
