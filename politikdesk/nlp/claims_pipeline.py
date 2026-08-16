"""İddia çıkarımı turu ve kalıcılığı (F2-06, F2-09, F2-10 · DB tarafı).

Çıkarım **olay bazlı** koşar, makale bazlı değil: F2-09 aynı olayda aynı
iddianın iki kez kaydedilmemesini ister ve bu ancak olayın tüm makaleleri
birlikte görüldüğünde yapılabilir.

Akış:
  1. Olayın kümelenmiş makalelerini al
  2. Her makaleden LLM ile iddia çıkar (doğrulama katmanları `claims.py`'de)
  3. Olay düzeyinde tekilleştir
  4. `claims` satırlarını yaz; her iddiayı kaynağı olan makaleye
     `evidence` satırıyla bağla (`stance='supports'`, `quote_span`)

**Neden `stance` başlangıçta hep `supports`:** bir makaleden çıkarılan
iddia, o makale tarafından desteklenir — tanım gereği. `contradicts`
bağları, aynı olaydaki *başka* makalelerin aynı iddiaya karşı çıkması
durumunda kurulur; bu, sayısal çelişki bayrağından (F2-03) ve iddia
eşleştirmesinden gelir.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from politikdesk.db import connection
from politikdesk.llm.errors import LLMNotConfigured
from politikdesk.nlp.claims import (
    PROMPT_VERSION,
    ExtractedClaim,
    claim_signature,
    extract_claims,
)
from politikdesk.observability import get_logger

log = get_logger(__name__)


@dataclass
class ClaimStats:
    events_processed: int = 0
    claims_extracted: int = 0
    claims_rejected: int = 0
    evidence_links: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "events_processed": self.events_processed,
            "claims_extracted": self.claims_extracted,
            "claims_rejected": self.claims_rejected,
            "evidence_links": self.evidence_links,
            "errors": self.errors,
        }


# Bir olay bu kadar denendikten sonra, yeni makale gelmedikçe bırakılır.
# 3: ilk deneme + iki tekrar. Geçici bir sağlayıcı arızası bu pencerede
# düzelir; düzelmiyorsa sorun metinde, tekrar denemekte değil.
MAX_CLAIM_ATTEMPTS = 3

# Deneme sayacı dolmuş olay, olaya yeni makale katılırsa yeniden denenir
# (`last_update_at > claims_attempted_at`). Yeni malzeme yeni bir sonuç
# ihtimali demektir; aynı metni tekrar sormak değildir.
PENDING_EVENTS_SQL = """
    SELECT e.id FROM events e
    WHERE e.merged_into_id IS NULL
      AND e.article_count > 0
      AND (
            e.claims_attempted_at IS NULL
         OR e.last_update_at > e.claims_attempted_at
         OR (
              NOT EXISTS (SELECT 1 FROM claims c WHERE c.event_id = e.id)
              AND e.claims_attempt_count < %s
            )
      )
    ORDER BY e.last_update_at DESC
    LIMIT %s
"""


def pending_events(limit: int = 10) -> list[int]:
    """İddia çıkarımı bekleyen olaylar (en yeni önce).

    Üç ayrı durum vardır ve yüklem üçünü de ayırt etmek zorundadır:

      1. Hiç denenmemiş                    -> çıkar
      2. Denendikten SONRA yeni makale geldi -> YENİDEN çıkar (iddiası olsa da)
      3. Denendi, sıfır iddia döndü, yeni malzeme yok -> deneme hakkı
         bitene kadar tekrar dene, sonra bırak

    "İddiası olmayan" ile "iddia çıkarılamayan" farklıdır. Çıkarımın
    meşru şekilde sıfır iddia döndürmesi mümkündür — başlıktan ibaret
    bir duyuru, özeti olmayan bir bülten. Eski yüklem bu iki durumu
    ayırmıyordu ve sıfır iddia dönen olay listede sonsuza dek kalıyordu:
    13 Ağustos'ta üç olay 28 saat boyunca her 10 dakikada bir yeniden
    LLM'e gönderildi ve her seferinde aynı boş yanıt geldi (F4-05).

    **F5-16 düzeltmesi — 2. durum hiç çalışmıyordu.** F4-05'in eklediği
    `NOT EXISTS (claims)` koşulu bir AND dalıydı ve iddiası olan her olayı
    listeden tamamen çıkarıyordu; yanındaki
    `last_update_at > claims_attempted_at` koşulu böylece **ölü koddu**.

    Bedeli ürünün ana vaadiydi: teyit, doğası gereği "önce bir kaynak
    yazar, sonra diğerleri" diye oluşur. İkinci bağımsız kaynağın makalesi
    mevcut bir olaya katıldığında o makaleden HİÇ iddia çıkarılmıyor,
    dolayısıyla o kaynağın kanıt bağı hiç kurulmuyordu. `independent_count`
    1'i geçemiyor, hiçbir iddia 🟡/🟢 olamıyordu.

    Ölçülen (13 Ağu 2026, F5-04 sonrası): olay 686'da sekiz makale ve dört
    bağımsız grup vardı — rezerv haberini dunya, cnnturk ve haberturk ayrı
    ayrı veriyordu — ama iddialar yalnızca ilk çıkarımdaki iki makaleden
    geliyordu. Kaynak vardı, kod onu hiç okumuyordu.

    Bu, B-79 ile aynı aileden bir hatadır: ikisi de çapraz teyidi sessizce
    imkânsız kılıyordu, ikisi de "kaynak yok" diye yanlış teşhis edilebilirdi.
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(PENDING_EVENTS_SQL, (MAX_CLAIM_ATTEMPTS, limit))
        return [r["id"] for r in cur.fetchall()]


def _record_attempt(cur: Any, event_id: int) -> None:
    """Deneme damgasını basar.

    Sayaç, olaya yeni makale katıldığında sıfırlanır: `last_update_at`
    ilerlediyse önceki denemelerin konusu olan metin artık eksiktir.
    """
    cur.execute(
        """
        UPDATE events
        SET claims_attempted_at = now(),
            claims_attempt_count = CASE
                WHEN claims_attempted_at IS NULL
                  OR last_update_at > claims_attempted_at THEN 1
                ELSE claims_attempt_count + 1
            END
        WHERE id = %s
        """,
        (event_id,),
    )


def stale_events(prompt_version: str = PROMPT_VERSION) -> list[dict[str, Any]]:
    """İddiaları ESKİ prompt sürümüyle çıkarılmış olaylar (B-70).

    `evidence.extracted_by` "<model>+<prompt_version>" biçimindedir; sürüm
    son "+"tan sonra gelir. Prompt değiştiğinde eski kayıtlar yanlış
    değildir ama **karışıktır**: iki sürümün çıktısı aynı tabloda
    durduğunda kalite ölçümü hangi sürümü ölçtüğünü söyleyemez
    (Spec §11.5 "her prompt sürümlenir ve çıktıya işlenir").
    """
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.event_id,
                   count(DISTINCT c.id) AS claim_count,
                   array_agg(DISTINCT ev.extracted_by) AS versions
            FROM claims c
            JOIN evidence ev ON ev.claim_id = c.id
            WHERE split_part(ev.extracted_by, '+', 2) IS DISTINCT FROM %s
            GROUP BY c.event_id
            ORDER BY c.event_id
            """,
            (prompt_version,),
        )
        return [dict(r) for r in cur.fetchall()]


def reextract(event_ids: list[int], client: Any = None, *, actor: str = "user:admin") -> ClaimStats:
    """Belirtilen olayların iddialarını SİLER ve yeniden çıkarır (B-70).

    ⚠ Yıkıcı işlem. Çağıran katman onay almalıdır; `scripts/ingest.py`
    bunu `--yes` bayrağıyla zorlar.

    Silme `evidence`'ı da götürür (`ON DELETE CASCADE`). Her silme
    `audit_log`'a yazılır: bir iddianın neden kaybolduğu sorulabilir
    olmalıdır.
    """
    if not event_ids:
        return ClaimStats()

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM claims WHERE event_id = ANY(%s) RETURNING id, event_id",
            (event_ids,),
        )
        removed = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """
            INSERT INTO audit_log (actor, action, target, payload)
            VALUES (%s, 'claims_reextracted', %s, %s::jsonb)
            """,
            (
                actor,
                f"events/{','.join(map(str, event_ids))}",
                json.dumps(
                    {
                        "deleted_claims": len(removed),
                        "events": event_ids,
                        "new_prompt_version": PROMPT_VERSION,
                        "reason": "B-70 prompt sürümü birleştirme",
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        conn.commit()

    log.info("claims_deleted_for_reextract", count=len(removed), events=event_ids)
    return run(limit=len(event_ids), client=client)


def _articles_of(cur: Any, event_id: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT a.id, a.title, a.excerpt, a.published_at,
               s.name AS source_name, s.tier,
               COALESCE(a.vertical, s.vertical, 'macro_economy') AS vertical
        FROM articles a JOIN sources s ON s.id = a.source_id
        WHERE a.event_id = %s
        ORDER BY s.tier, a.published_at
        """,
        (event_id,),
    )
    return [dict(r) for r in cur.fetchall()]


def _existing_claims_by_signature(cur: Any, event_id: int) -> dict[str, int]:
    """Olayın kayıtlı iddialarını imzaya göre indeksler (F5-16).

    İmza, çıkarımın kendi tekilleştirmesiyle aynı fonksiyondan gelir —
    iki ayrı hesap, yeniden çıkarımda aynı iddianın "yeni" sanılmasına
    ve mükerrer kayda yol açardı.

    `quote_span` burada boş bırakılır: imzaya girmez (sayısal iddiada
    `metric:value:period`, diğerlerinde `claim_type` + sözcük kümesi).
    """
    cur.execute(
        "SELECT id, claim_text, claim_type, normalized_value FROM claims WHERE event_id = %s",
        (event_id,),
    )
    index: dict[str, int] = {}
    for row in cur.fetchall():
        signature = claim_signature(
            ExtractedClaim(
                claim_text=row["claim_text"],
                claim_type=row["claim_type"],
                quote_span="",
                normalized_value=row["normalized_value"],
            )
        )
        index.setdefault(signature, row["id"])
    return index


def _persist(
    cur: Any,
    event_id: int,
    claims: list[tuple[ExtractedClaim, list[tuple[int, str]]]],
    extracted_by: str,
) -> int:
    """İddiaları ve kanıt bağlarını yazar; kurulan bağ sayısını döndürür.

    Bir iddia, onu söyleyen HER makaleye bağlanır. Kanıt motorunun
    `independent_count`'u bu bağları sayar; tek bağ yazmak, çapraz
    teyidin hiç görülmemesi demektir (B-79).

    **Yeniden çıkarımda mükerrer yazmaz (F5-16).** Olaya yeni makale
    katıldığında çıkarım olayın TÜM makaleleri üzerinde yeniden koşar,
    yani zaten kayıtlı iddialar tekrar üretilir. Bunlar yeniden
    yazılsaydı aynı iddia iki satır olur ve kanıt bağları ikiye
    bölünürdü — `independent_count` her iki kayıtta da düşük kalır,
    yani düzeltmenin kendisi düzeltmeyi boşa çıkarırdı.

    Çözüm: mevcut iddialar `claim_signature` ile eşlenir (çıkarımın
    kendi tekilleştirmesiyle **aynı** hesap) ve eşleşen için yalnızca
    yeni kanıt bağı eklenir. `evidence`'taki
    `ON CONFLICT (claim_id, article_id) DO NOTHING` sayesinde tekrar
    koşum güvenlidir: işlem tümüyle idempotenttir.
    """
    existing = _existing_claims_by_signature(cur, event_id)

    links = 0
    for claim, sources in claims:
        signature = claim_signature(claim)
        claim_id = existing.get(signature)

        if claim_id is None:
            cur.execute(
                """
                INSERT INTO claims (event_id, claim_text, claim_type, normalized_value,
                                    evidence_status, status_reason, claim_signature)
                VALUES (%s, %s, %s, %s::jsonb, 'unverified', %s::jsonb, %s)
                ON CONFLICT (event_id, claim_signature)
                    WHERE claim_signature IS NOT NULL
                    DO NOTHING
                RETURNING id
                """,
                (
                    event_id,
                    claim.claim_text,
                    claim.claim_type,
                    json.dumps(claim.normalized_value, ensure_ascii=False)
                    if claim.normalized_value
                    else None,
                    # Başlangıç durumu: kanıt motoru henüz koşmadı. `unverified`
                    # güvenli varsayılandır — R0'ın tahmin kısıtıyla da uyumlu,
                    # ve DB CHECK'i ihlal etmez.
                    json.dumps({"rule": "pending", "engine_version": "not_yet_scored"}),
                    signature,
                ),
            )
            row = cur.fetchone()
            if row is None:
                # Yarış: bu iddiayı aramızda başka bir süreç yazdı (F5-18).
                # Python tarafındaki kontrol tek başına yetmez — iki süreç
                # de "yok" görüp ikisi de yazabilir. Kısıt bunu keser;
                # burada yalnızca kazananın kimliğini okuruz.
                cur.execute(
                    "SELECT id FROM claims WHERE event_id = %s AND claim_signature = %s",
                    (event_id, signature),
                )
                row = cur.fetchone()
            claim_id = row["id"]
            existing[signature] = claim_id

        for article_id, quote_span in sources:
            cur.execute(
                """
                INSERT INTO evidence (claim_id, article_id, stance, quote_span,
                                      extracted_by)
                VALUES (%s, %s, 'supports', %s, %s)
                ON CONFLICT (claim_id, article_id) DO NOTHING
                """,
                (claim_id, article_id, quote_span, extracted_by),
            )
            links += cur.rowcount
    return links


def run(limit: int = 10, client: Any = None) -> ClaimStats:
    """İddia çıkarımı turu.

    `client` verilmezse `LLMClient` kurulur — ANTHROPIC_API_KEY gerekir.
    """
    if client is None:
        from politikdesk.llm.client import LLMClient

        client = LLMClient()

    stats = ClaimStats()

    for event_id in pending_events(limit):
        try:
            with connection() as conn, conn.cursor() as cur:
                articles = _articles_of(cur, event_id)
                if not articles:
                    continue

                collected: list[tuple[ExtractedClaim, int]] = []
                extracted_by = f"unknown+{PROMPT_VERSION}"

                for article in articles:
                    result = extract_claims(
                        title=article["title"],
                        excerpt=article["excerpt"] or "",
                        source_name=article["source_name"],
                        tier=article["tier"],
                        published_at=str(article["published_at"] or ""),
                        client=client,
                        vertical=article.get("vertical", "macro_economy"),
                    )
                    extracted_by = result.extracted_by
                    stats.claims_rejected += len(result.rejected)

                    # B-97: Haber / Köşe Yazısı ayrımı (Spec v3.4 §5, §14.4).
                    # Köşe yazısı, kulis veya kişisel yorum içeren metinlerden
                    # çıkan iddialar doğrudan 'fact' veya 'number' olamaz;
                    # 'attribution' (aktör/yazar beyanı) olarak kaydedilir.
                    from politikdesk.nlp.opinion_classifier import classify_content_kind

                    classification = classify_content_kind(
                        title=article["title"],
                        text=article["excerpt"] or "",
                    )
                    if classification.is_opinion:
                        adjusted: list[ExtractedClaim] = []
                        for c in result.claims:
                            if c.claim_type in ("fact", "number"):
                                adjusted.append(
                                    ExtractedClaim(
                                        claim_text=c.claim_text,
                                        claim_type="attribution",
                                        quote_span=c.quote_span,
                                        normalized_value=None,
                                        problems=c.problems,
                                    )
                                )
                            else:
                                adjusted.append(c)
                        collected.extend((c, article["id"]) for c in adjusted)
                    else:
                        collected.extend((c, article["id"]) for c in result.claims)

                # B-81 & F2-09: Çapraz kaynak iddia eşleştirme ve tekilleştirme.
                # Aynı iddia farklı sözcüklerle aktarılsa bile semantik/sayısal
                # olarak eşleştirilir ve bağımsız kanıt bağları korunur.
                from politikdesk.nlp.cross_source_matcher import match_and_group_claims

                final = match_and_group_claims(collected)

                stats.evidence_links += _persist(cur, event_id, final, extracted_by)
                stats.claims_extracted += len(final)
                # Denemeyi, sonucu ne olursa olsun kaydet: sıfır iddia
                # dönmesi de bir sonuçtur. Aynı işlemde yazılır ki iddia
                # yazımı geri sarılırsa deneme damgası da geri sarılsın.
                _record_attempt(cur, event_id)
                conn.commit()

                if not final:
                    log.info(
                        "claim_extraction_empty",
                        event_id=event_id,
                        articles=len(articles),
                        hint="Metinde çıkarılabilir iddia yok. Olaya yeni "
                        "makale katılmadıkça yeniden denenmeyecek.",
                    )

            stats.events_processed += 1

        except LLMNotConfigured:
            # Yapılandırma eksikliği olay başına hata değildir; tur biter.
            # Deneme SAYILMAZ: anahtar gelince bu olaylar denenmelidir.
            raise
        except Exception as exc:  # noqa: BLE001
            stats.errors += 1
            log.error(
                "claim_extraction_failed",
                event_id=event_id,
                error=type(exc).__name__,
                detail=str(exc)[:300],
            )
            # Başarısız deneme de denemedir. Yazılmazsa kalıcı olarak
            # patlayan bir olay turu her seferinde baştan tıkar ve
            # arkasındaki olaylar hiç sıraya gelmez.
            try:
                with connection() as conn, conn.cursor() as cur:
                    _record_attempt(cur, event_id)
                    conn.commit()
            except Exception:  # noqa: BLE001 — damga yazılamadıysa tur sürsün
                log.warning("claim_attempt_stamp_failed", event_id=event_id)

    log.info("claim_extraction_complete", **stats.as_dict())
    return stats
