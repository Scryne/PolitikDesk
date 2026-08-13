"""Faz 3 editoryal katman testleri (F3-08 … F3-15).

Bu dosya üç pazarlıksız kısıtı korur:

  1. **Editoryal profilde ideolojik alan yok** (Spec §10.1, P6, KVKK m.6)
     — form, derleyici ve derlenmiş prompt ayrı ayrı taranır.
  2. **Kanıtsız olayda üretim yok** (F3-11, Spec §14.1 kalem 15) — kapı
     LLM çağrısından önce durur.
  3. **Girdi yalnızca claims+evidence** (F3-10) — olay başlığı prompta
     sızarsa grounding denetiminin evreni ile modelin gördüğü ayrışır.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from politikdesk.editorial.checker import LINK_THRESHOLD, run_checks, split_sentences
from politikdesk.editorial.generator import (
    ANGLES,
    FORBIDDEN_FIELDS,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_schema,
    build_user_prompt,
    generate_draft,
)
from politikdesk.editorial.guards import (
    ClaimForGeneration,
    GenerationBlocked,
    generation_block_reason,
    require_generation_allowed,
)
from politikdesk.editorial.profile import QUESTIONS, normalize_answers
from politikdesk.editorial.profile_compiler import COMPILER_VERSION, compile_profile
from politikdesk.editorial.service import levenshtein, normalized_edit_distance

REPO_ROOT = Path(__file__).resolve().parent.parent

# tests/test_schema.py ile AYNI liste. İki dosyada iki farklı liste
# tutmak, birinde yakalanan bir terimin diğerinde kaçması demekti.
FORBIDDEN_PROFILE_TERMS = (
    "ideolog", "ideolo", "political", "politik", "siyasi", "parti", "party",
    "partisan", "leaning", "bias", "religion", "ethnic", "etnik", "vote",
    "orientation", "yandaş", "muhalif", "sağcı", "solcu",
)


# --------------------------------------------------------------- yardımcılar
def make_claim(
    claim_id: int = 1,
    text: str = "TCMB politika faizini yüzde 37'de sabit tuttu.",
    claim_type: str = "fact",
    status: str = "strongly_corroborated",
    with_evidence: bool = True,
    normalized_value: dict[str, Any] | None = None,
) -> ClaimForGeneration:
    evidence = (
        (
            {
                "stance": "supports",
                "quote_span": "politika faizini yüzde 37 seviyesinde sabit tutmuştur",
                "source_name": "TCMB",
                "source_slug": "tcmb",
                "tier": 1,
                "canonical_url": "https://tcmb.example/duyuru",
            },
        )
        if with_evidence
        else ()
    )
    return ClaimForGeneration(
        claim_id=claim_id,
        claim_text=text,
        claim_type=claim_type,
        evidence_status=status,
        status_rule="R2",
        normalized_value=normalized_value,
        evidence=evidence,
    )


class FakeResult:
    def __init__(self, data: dict[str, Any], model: str = "fake-model") -> None:
        self.data = data
        self.model = model
        self.raw_text = ""
        self.prompt_version = PROMPT_VERSION


class FakeClient:
    """`complete_json` sözleşmesini taklit eder; çağrıları kaydeder."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.calls: list[dict[str, Any]] = []

    def complete_json(self, **kwargs: Any) -> FakeResult:
        self.calls.append(kwargs)
        return FakeResult(self.data)


# ============================================================ F3-08 / F3-09
def test_form_has_exactly_seven_questions() -> None:
    """Spec §10.2: "7 soruluk bir form". Sekizinci soru spec değişikliğidir."""
    assert len(QUESTIONS) == 7
    assert [q.number for q in QUESTIONS] == [1, 2, 3, 4, 5, 6, 7]


def test_form_has_no_ideological_question() -> None:
    """P6 / KVKK m.6 — soru metinlerinde siyasi terim bulunamaz."""
    blob = " ".join(
        f"{q.field} {q.prompt} {q.help_text} "
        + " ".join(f"{k} {v}" for k, v in q.choices)
        for q in QUESTIONS
    ).lower()
    hits = [term for term in FORBIDDEN_PROFILE_TERMS if term in blob]
    assert not hits, f"Formda yasaklı terim(ler): {hits}"


def test_compiled_prompt_has_no_ideological_content() -> None:
    """Derlenmiş sistem promptu bloğu da taranır."""
    compiled = compile_profile(
        {
            "tone": ["direct", "analytical"],
            "sentence_length": "short",
            "emoji_usage": "none",
            "hashtag_usage": "none",
            "citation_habit": "always_link",
            "formality": 3,
            "topic_priorities": ["enflasyon", "faiz"],
            "avoid_list": ["tarihi karar"],
        }
    )
    lowered = compiled.lower()
    hits = [term for term in FORBIDDEN_PROFILE_TERMS if term in lowered]
    assert not hits, f"Derlenmiş promptta yasaklı terim(ler): {hits}"
    assert "enflasyon" in compiled
    assert "tarihi karar" in compiled


def test_compiler_ignores_fields_outside_whitelist() -> None:
    """Şemaya bir gün başka bir sütun eklenirse prompta SIZMAMALI.

    Beyaz listenin var olma sebebi budur: `editorial_profiles`'a
    yanlışlıkla eklenmiş bir alan, derleyiciden geçip modele ulaşırdı.
    """
    compiled = compile_profile(
        {
            "tone": ["direct"],
            "gizli_alan": "SIZMAMALI",
            "political_leaning": "SIZMAMALI",
        }
    )
    assert "SIZMAMALI" not in compiled


def test_compiled_prompt_reasserts_grounding_over_style() -> None:
    """Biçimsel tercihler grounding kuralını ezemez."""
    compiled = compile_profile({"tone": ["direct"], "formality": 1})
    assert "kanıta bağlı" in compiled.lower()


def test_empty_profile_compiles_to_neutral_default() -> None:
    """Profil doldurulmadan da üretim yapılabilmeli."""
    assert "Profil henüz doldurulmamış" in compile_profile(None)
    assert COMPILER_VERSION.startswith("profile-compiler@")


def test_invalid_answer_raises_instead_of_silently_defaulting() -> None:
    """Sessiz düşürme, kullanıcının cevabını değiştirmek olurdu."""
    with pytest.raises(ValueError, match="Bilinmeyen ton"):
        normalize_answers({"tone": ["marksist"]})
    with pytest.raises(ValueError, match="sentence_length"):
        normalize_answers({"sentence_length": "cok-uzun"})
    with pytest.raises(ValueError, match="formality"):
        normalize_answers({"formality": 9})


def test_hashtag_inherits_emoji_answer() -> None:
    """3. soru tek sorudur, iki sütun doldurur."""
    answers = normalize_answers({"emoji_usage": "none"})
    assert answers["hashtag_usage"] == "none"


# ==================================================================== F3-11
def test_event_without_claims_is_blocked() -> None:
    with pytest.raises(GenerationBlocked) as exc:
        require_generation_allowed([])
    assert exc.value.reason == "no_claims"


def test_claims_without_evidence_are_blocked() -> None:
    with pytest.raises(GenerationBlocked) as exc:
        require_generation_allowed([make_claim(with_evidence=False)])
    assert exc.value.reason == "no_evidence"


def test_unverified_claim_about_named_person_blocks_generation() -> None:
    """Spec §15 madde 10 — isimli kişi hakkında dayanaksız iddia."""
    claims = [
        make_claim(),
        make_claim(
            claim_id=2,
            text="Bakan Mehmet Şimşek ihaleyi yönlendirdi.",
            status="unverified",
        ),
    ]
    with pytest.raises(GenerationBlocked) as exc:
        require_generation_allowed(claims)
    assert exc.value.reason == "unverified_person_claim"
    assert "Mehmet Şimşek" in exc.value.message


def test_unverified_prediction_by_named_person_does_not_block() -> None:
    """R0 her tahmini `unverified` yapar — bu bir isnat değildir.

    Muafiyet olmasaydı "Bakan X enflasyonun düşeceğini öngördü" cümlesi
    tüm olayın üretimini bloke ederdi. Madde 10'un koruduğu şey
    SUÇLAMA'dır, bir kişinin kendi tahmininin aktarılması değil.
    """
    claims = [
        make_claim(),
        make_claim(
            claim_id=2,
            text="Bakan Mehmet Şimşek enflasyonun düşeceğini öngördü.",
            claim_type="prediction",
            status="unverified",
        ),
    ]
    require_generation_allowed(claims)  # fırlatmamalı


def test_block_reason_helper_matches_the_gate() -> None:
    """UI butonu ile API kararı aynı fonksiyondan gelmeli."""
    assert generation_block_reason([make_claim()]) is None
    blocked = generation_block_reason([])
    assert blocked is not None and blocked.reason == "no_claims"


def test_generator_does_not_call_the_model_when_blocked() -> None:
    """Kapı, maliyet oluşmadan durdurmalı."""
    client = FakeClient({"body": "x", "cited_claim_ids": [1]})
    with pytest.raises(GenerationBlocked):
        generate_draft(angle="inform", claims=[], client=client)
    assert client.calls == []


# ==================================================================== F3-10
def test_prompt_file_matches_code() -> None:
    """Sürümlü prompt belgesi ile kodun GÖNDERDİĞİ prompt aynı olmalı.

    `claims.v1`'de ikisi ayrışmıştı ve model belgede yazan rehberliği hiç
    görmedi; sapma ancak canlı koşumda ortaya çıktı (Spec §11.5).
    """
    doc = REPO_ROOT / "prompts" / f"{PROMPT_VERSION}.md"
    assert doc.is_file(), f"{doc.name} yok — prompt sürümü belgesiz olamaz"

    blocks = doc.read_text(encoding="utf-8").split("## SYSTEM", 1)
    assert len(blocks) == 2, f"{doc.name} içinde '## SYSTEM' bölümü yok"
    documented = blocks[1].split("```")[1].strip()
    assert documented == SYSTEM_PROMPT.strip(), (
        f"{doc.name} ile generator.py::SYSTEM_PROMPT ayrışmış. "
        "Prompt değiştiyse HEM kodu HEM belgeyi güncelleyin ve "
        "PROMPT_VERSION'ı artırın."
    )


def test_user_prompt_contains_only_claims_and_evidence() -> None:
    """F3-10 girdi sözleşmesi: olay başlığı/özeti prompta GİRMEZ.

    Sızarsa grounding evreni ile modelin gördüğü ayrışır ve doğru bir
    taslak "kanıtta yok" diye düşer.
    """
    prompt = build_user_prompt(
        angle="inform",
        claims=[make_claim()],
        profile_block="EDİTORYAL KİMLİK",
        max_chars=600,
    )
    assert "TCMB politika faizini yüzde 37" in prompt   # iddia metni
    assert "politika faizini yüzde 37 seviyesinde" in prompt  # kanıt alıntısı
    assert "Tier 1" in prompt                            # kaynak katmanı
    # Olay başlığı gibi kanıt seti dışı bir metin buraya konmadı:
    assert "olay başlığı" not in prompt.lower()
    assert "event_title" not in prompt


def test_prompt_shows_evidence_status_labels() -> None:
    """Durum etiketi gizlenemez (Spec §15 madde 3)."""
    prompt = build_user_prompt(
        angle="inform",
        claims=[make_claim(status="single_source")],
        profile_block="",
        max_chars=600,
    )
    assert "🟠 tek kaynaklı" in prompt


def test_output_schema_rejects_verdict_fields() -> None:
    """Şema `evidence_status` ve benzerlerini KABUL ETMEZ (Spec §8.1)."""
    schema = build_schema(600)
    assert schema["additionalProperties"] is False
    for banned in ("evidence_status", "confidence", "bias", "truth"):
        assert banned not in schema["properties"]


def test_forbidden_field_in_output_is_flagged() -> None:
    client = FakeClient(
        {"body": "TCMB faizi %37'de tuttu.", "cited_claim_ids": [1],
         "evidence_status": "strongly_corroborated"}
    )
    draft = generate_draft(angle="inform", claims=[make_claim()], client=client)
    assert not draft.is_usable
    assert any("evidence_status" in p for p in draft.problems)


def test_invented_claim_id_is_rejected() -> None:
    client = FakeClient(
        {"body": "TCMB faizi %37'de tuttu.", "cited_claim_ids": [1, 999]}
    )
    draft = generate_draft(angle="inform", claims=[make_claim()], client=client)
    assert draft.cited_claim_ids == (1,)
    assert any("uydurulmus iddia kimligi" in p for p in draft.problems)


def test_generation_uses_the_generation_task_not_extraction() -> None:
    """Spec §11.5: üretimde yüksek `effort`, çıkarımda düşük."""
    client = FakeClient({"body": "TCMB faizi %37'de tuttu.", "cited_claim_ids": [1]})
    generate_draft(angle="inform", claims=[make_claim()], client=client)
    assert client.calls[0]["task"] == "generation"
    assert client.calls[0]["prompt_version"] == PROMPT_VERSION
    assert client.calls[0]["purpose"] == "draft_generation"


def test_ungrounded_draft_is_not_usable() -> None:
    client = FakeClient(
        {"body": "TCMB faizi %37'de tuttu; kredi hacmi %12 daraldı.",
         "cited_claim_ids": [1]}
    )
    draft = generate_draft(angle="inform", claims=[make_claim()], client=client)
    assert not draft.is_grounded
    assert not draft.is_usable
    assert [i.token for i in draft.grounding.issues] == ["12"]


def test_three_angles_exist_with_spec_labels() -> None:
    """Spec §14.3 dil kararı: buton metni asla "Tweet Üret" olmaz."""
    assert set(ANGLES) == {"inform", "analyze", "critique"}
    labels = [label for label, _ in ANGLES.values()]
    assert labels == ["Bilgilendir", "Analiz Et", "Eleştir"]
    assert not any("tweet" in label.lower() for label in labels)


def test_forbidden_fields_list_covers_verdict_vocabulary() -> None:
    for banned in ("evidence_status", "confidence", "bias", "political_leaning"):
        assert banned in FORBIDDEN_FIELDS


# ==================================================================== F3-13
def _draft_with(body: str, **kwargs: Any):  # noqa: ANN202
    client = FakeClient({"body": body, "cited_claim_ids": [1], **kwargs})
    return generate_draft(angle="inform", claims=[make_claim()], client=client)


def test_check_report_has_all_six_checks() -> None:
    """Spec §14.4'ün altı kontrolü, eksiksiz."""
    draft = _draft_with("TCMB politika faizini yüzde 37'de sabit tuttu.")
    report = run_checks(draft, [make_claim()])
    assert [i.key for i in report.items] == [
        "source_link", "numeric_match", "news_opinion",
        "single_source", "unlinked", "missing_context",
    ]


def test_clean_draft_passes_all_checks() -> None:
    draft = _draft_with("TCMB politika faizini yüzde 37'de sabit tuttu.")
    report = run_checks(draft, [make_claim()])
    assert report.passed
    assert not report.is_blocking


def test_unmatched_number_is_blocking() -> None:
    """Spec §14.4: kanıta bağlanamayan SAYISAL iddia engelleyicidir."""
    draft = _draft_with("TCMB faizi %37'de tuttu. Kredi hacmi %12 daraldı.")
    report = run_checks(draft, [make_claim()])
    assert report.is_blocking
    assert not report.passed
    numeric = next(i for i in report.items if i.key == "numeric_match")
    assert numeric.blocking and numeric.severity == "error"


def test_unmarked_opinion_is_warned_not_blocked() -> None:
    draft = _draft_with(
        "TCMB politika faizini yüzde 37'de sabit tuttu. "
        "Bu karar endişe verici bir sinyal."
    )
    report = run_checks(draft, [make_claim()])
    opinion = next(i for i in report.items if i.key == "news_opinion")
    assert opinion.severity == "warn"
    assert not opinion.blocking


def test_marked_commentary_is_accepted() -> None:
    sentence = "Bu karar endişe verici bir sinyal."
    draft = _draft_with(
        f"TCMB politika faizini yüzde 37'de sabit tuttu. {sentence}",
        commentary_sentences=[sentence],
    )
    report = run_checks(draft, [make_claim()])
    opinion = next(i for i in report.items if i.key == "news_opinion")
    assert opinion.severity == "ok"


def test_marked_commentary_does_not_excuse_an_unmatched_number() -> None:
    """Yorum etiketi, kanıta bağlanmayan sayıyı mazur göstermez.

    Spec §14.4'ün engelleyici durumu "kanıta bağlanamayan SAYISAL
    iddia"dır; etiket onu ortadan kaldırmaz.
    """
    sentence = "Kredi hacmi yüzde 12 daralmış görünüyor."
    draft = _draft_with(
        f"TCMB faizi %37'de tuttu. {sentence}", commentary_sentences=[sentence]
    )
    report = run_checks(draft, [make_claim()])
    assert report.is_blocking


def test_weak_claim_usage_is_warned() -> None:
    weak = make_claim(status="single_source")
    draft = _draft_with("TCMB politika faizini yüzde 37'de sabit tuttu.")
    report = run_checks(draft, [weak])
    single = next(i for i in report.items if i.key == "single_source")
    assert single.severity == "warn"
    assert "tek kaynaklı" in " ".join(single.items)


def test_missing_prior_context_is_informational_only() -> None:
    draft = _draft_with("TCMB politika faizini yüzde 37'de sabit tuttu.")
    report = run_checks(
        draft, [make_claim()], prior_context=["Haziran ayı işsizlik verisi açıklandı"]
    )
    context_item = next(i for i in report.items if i.key == "missing_context")
    assert context_item.severity == "info"
    assert not context_item.blocking
    assert report.passed  # bilgi notu yayını engellemez


def test_sentence_splitter_survives_turkish_thousands_separator() -> None:
    """"13.704,98" cümle sonu değildir."""
    sentences = split_sentences(
        "BIST 100 endeksi 13.704,98 puandan başladı. Endeks günü yatay kapattı."
    )
    assert len(sentences) == 2
    assert "13.704,98" in sentences[0]


def test_link_threshold_is_documented_constant() -> None:
    """Eşik değiştirilirse G3 koşul 3 yeniden ölçülmelidir."""
    assert 0 < LINK_THRESHOLD < 1


def test_check_report_renders_spec_layout() -> None:
    draft = _draft_with("TCMB faizi %37'de tuttu. Kredi hacmi %12 daraldı.")
    text = run_checks(draft, [make_claim()]).render_text()
    assert text.startswith("YAYIN ÖNCESİ KONTROL")
    assert "ENGELLEYİCİ" in text


# ==================================================================== F3-14
def test_levenshtein_basics() -> None:
    assert levenshtein("", "") == 0
    assert levenshtein("abc", "abc") == 0
    assert levenshtein("abc", "abd") == 1
    assert levenshtein("abc", "") == 3


def test_normalized_edit_distance_is_bounded() -> None:
    assert normalized_edit_distance("aynı metin", "aynı metin") == 0.0
    assert normalized_edit_distance("", "") == 0.0
    assert normalized_edit_distance("abcd", "wxyz") == 1.0


def test_edit_distance_normalises_by_the_longer_text() -> None:
    """Kısa metne göre normalleştirmek, kısaltmayı 1'in üstüne taşırdı."""
    distance = normalized_edit_distance("uzun bir taslak metni", "uzun")
    assert 0 < distance <= 1.0


# ==================================================================== F3-15
def test_publish_module_has_no_outgoing_post_to_x() -> None:
    """Kapı G3 #9: otomatik yayın kod yolu YOK (Spec §15 madde 6, P5).

    `service.publish_payload` yalnızca bir Web Intent ADRESİ üretir.
    Bu test kaynak metnini tarar: bir gün biri "kolaylık olsun diye"
    gönderim eklerse CI kırılır.
    """
    source = (REPO_ROOT / "politikdesk" / "editorial" / "service.py").read_text(
        encoding="utf-8"
    )
    assert "intent/tweet" in source, "Web Intent adresi kaldırılmış"
    for banned in ("api.twitter.com", "api.x.com", "statuses/update", "tweepy"):
        assert banned not in source, f"Otomatik yayın kod yolu: {banned}"
