"""Editoryal Taslakların X Paylaşımı ve Aşılmaz Güvenlik Kapısı (Spec §12.4, TCK 217/A).

İlkeler:
  - Hiçbir taslak, zorunlu Güvenlik Kapısından (`SocialSecurityGate`) geçmeden X'e gönderilemez.
  - TCK 217/A (Halkı Yanıltıcı Bilgiyi Alenen Yayma) ve Hakaret/İsnat denetimi zorunludur.
  - Epistemik bütünlük: Yalnızca teyitli veya açık 'attribution' şerhi taşıyan
    taslaklar yayınlanabilir.
  - Canlı X API kimlik bilgisi yoksa mock/dry-run modunda çalışır; test edilebilirdir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from politikdesk.observability import get_logger

log = get_logger(__name__)

# Yasaklı veya suç isnadı oluşturan hakaret ve dezenformasyon kalıpları
_DEFAMATION_PATTERNS = (
    r"\b(hain|vatan\s*haini|hırsız|şerefsiz|alçak|teröristtir)\b",
    r"\b(kesinlikle\s*suçlu|yargılanmadan\s*hüküm|rüşvetçi)\b",
)

# TCK 217/A dezenformasyon / infial tetikleyici panik ifadeleri
_PANIC_DISINFO_PATTERNS = (
    r"\b(büyük\s*felaket\s*gizleniyor|savaş\s*başladı|tüm\s*bankalar\s*battı)\b",
    r"\b(nükleer\s*sızıntı\s*var|seçimler\s*iptal\s*edildi|olağanüstü\s*hal\s*ilan\s*edildi)\b",
)


class UnsafeSocialPublicationError(Exception):
    """Güvenlik kapısını geçemeyen taslakların yayınlanmasını engelleyen istisna."""


@dataclass(frozen=True)
class SafetyGateResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    has_tck217a_risk: bool = False
    has_defamation_risk: bool = False
    epistemic_verified: bool = True


def evaluate_social_safety_gate(
    text: str,
    *,
    evidence_status: str = "strongly_corroborated",
    is_attribution: bool = False,
) -> SafetyGateResult:
    """Aşılmaz güvenlik kapısı: TCK 217/A, hakaret, isnat ve epistemik tavan denetimi."""
    reasons: list[str] = []
    has_defamation = False
    has_panic = False

    lowered = text.casefold()

    # 1. Hakaret ve isnat denetimi
    for pat in _DEFAMATION_PATTERNS:
        if re.search(pat, lowered):
            has_defamation = True
            reasons.append(f"Hakaret / hukuka aykırı isnat riski tespit edildi: {pat}")

    # 2. TCK 217/A panik ve dezenformasyon denetimi
    for pat in _PANIC_DISINFO_PATTERNS:
        if re.search(pat, lowered):
            has_panic = True
            reasons.append(f"TCK 217/A kamu barışını bozucu yanıltıcı bilgi riski: {pat}")

    # 3. Epistemik doğruluk denetimi
    epistemic_ok = True
    if evidence_status in ("unverified", "contradicted") and not is_attribution:
        epistemic_ok = False
        reasons.append(
            f"Kanıt durumu yetersiz ({evidence_status}); 'attribution' şerhi olmadan paylaşılamaz."
        )

    passed = (not has_defamation) and (not has_panic) and epistemic_ok

    return SafetyGateResult(
        passed=passed,
        reasons=reasons,
        has_tck217a_risk=has_panic,
        has_defamation_risk=has_defamation,
        epistemic_verified=epistemic_ok,
    )


def format_x_thread(
    title: str,
    lead: str,
    claims: list[dict[str, Any]],
    event_id: int,
    *,
    base_url: str = "https://politikdesk.com",
    max_tweet_len: int = 280,
) -> list[str]:
    """Editoryal taslağı X thread dizisine dönüştürür."""
    tweets: list[str] = []

    # Tweet 1: Ana başlık + özet + provenance linki
    event_url = f"{base_url}/event/{event_id}"
    tweet_1 = f"[Haber] {title}\n\n{lead[:140]}...\n\nDetay ve Kanit Kutugu: {event_url}"
    tweets.append(tweet_1[:max_tweet_len])

    # Tweet 2+: Atomik İddialar ve Kanıt Durumu
    for i, c in enumerate(claims, 1):
        status = c.get("evidence_status", "single_source")
        badge = (
            "[Dogrulandi]"
            if status == "strongly_corroborated"
            else ("[Kismen Dogrulandi]" if status == "partially_corroborated" else "[Beyan]")
        )
        claim_text = c.get("claim_text", "")
        speaker = c.get("speaker", "")
        speaker_prefix = f"{speaker}: " if speaker else ""
        src = c.get("source", "Resmi Kutuk")
        t = f'[{i}/{len(claims)}] {badge} {speaker_prefix}"{claim_text}"\n\nKaynak: {src}'
        tweets.append(t[:max_tweet_len])

    return tweets


class XPublisherClient:
    """X / Twitter API entegrasyonu (Mock / Üretim arayüzü)."""

    def __init__(self, api_key: str | None = None, api_secret: str | None = None) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.published_threads: list[list[str]] = []
        self.blocked_attempts: list[dict[str, Any]] = []

    def publish_thread(
        self,
        thread: list[str],
        *,
        gate_result: SafetyGateResult | None = None,
        evidence_status: str = "strongly_corroborated",
        is_attribution: bool = False,
    ) -> dict[str, Any]:
        """Güvenlik kapısını geçemeyen hiçbir taslağı yayınlamaz."""
        from politikdesk.feature_flags import is_social_publish_enabled

        if not is_social_publish_enabled():
            raise UnsafeSocialPublicationError(
                "Sosyal medya yayınlama özelliği sistem yöneticisi tarafından devre dışı bırakıldı."
            )

        combined_text = " ".join(thread)

        # 1. Aşama: Birleşik metin üzerinden zorunlu iç güvenlik kapısı değerlendirmesi
        internal_check = evaluate_social_safety_gate(
            combined_text,
            evidence_status=evidence_status,
            is_attribution=is_attribution,
        )

        # 2. Aşama: Dışarıdan iletilen gate_result varsa onunla tutarlılık kontrolü
        external_passed = gate_result.passed if gate_result is not None else True

        if not (internal_check.passed and external_passed):
            ext_reasons = gate_result.reasons if gate_result else []
            all_reasons = list(set(internal_check.reasons + ext_reasons))
            log.warning(
                "social_publish_blocked_by_safety_gate",
                reasons=all_reasons,
                tweet_count=len(thread),
                has_tck217a=internal_check.has_tck217a_risk,
                has_defamation=internal_check.has_defamation_risk,
            )
            self.blocked_attempts.append({
                "thread": thread,
                "reasons": all_reasons,
            })
            raise UnsafeSocialPublicationError(
                f"Güvenlik kapısı ihlali! Nedenler: {', '.join(all_reasons)}"
            )

        # Mock / Gerçek gönderim
        self.published_threads.append(thread)
        log.info("social_thread_published", tweet_count=len(thread))
        return {
            "status": "success",
            "tweet_count": len(thread),
            "thread_id": f"x-mock-{len(self.published_threads)}",
        }
