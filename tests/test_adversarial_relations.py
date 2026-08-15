"""S2 Adversarial & Edge Case İlişki Testleri (Spec v3.4 §8.3, §14.1).

Bu testler yanıltıcı benzerlikler, aktör çakışmaları, kapsam uyuşmazlıkları
ve zayıf kanıt senaryolarında sistemin FAIL-CLOSED davrandığını doğrular.
"""

from __future__ import annotations

from datetime import datetime

from politikdesk.political_memory.relation_engine import (
    EventData,
    evaluate_relation,
)


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def test_adversarial_same_person_different_institution() -> None:
    """Aynı isimli aktörün farklı kurumlardaki alakasız eylemleri bağlanmamalıdır."""
    src = EventData(
        event_id=201,
        title="Ahmet Yılmaz Belediye Başkanı Olarak Park Açılışı Yaptı",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        actor="Ahmet Yılmaz",
        institution="Belediye",
        topics=("belediye_yonetimi",),
        claims=({"claim_text": "Park açıldı", "claim_type": "fact"},),
    )
    tgt = EventData(
        event_id=202,
        title="Ahmet Yılmaz Özel Şirket Genel Müdürü Olarak Konkordato İlan Etti",
        published_at=_dt("2026-08-10T10:00:00+03:00"),
        actor="Ahmet Yılmaz",
        institution="Özel Şirket A.Ş.",
        topics=("ticaret",),
        claims=({"claim_text": "Konkordato ilan edildi", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt, semantic_similarity=0.35)
    assert not res.is_valid
    assert res.status == "unresolved"


def test_adversarial_same_institution_different_policy() -> None:
    """Aynı kurumun tamamen alakasız iki politikası yanlış eşleştirilmemelidir."""
    src = EventData(
        event_id=203,
        title="Çevre Bakanlığı: 81 İlde Fidan Dikim Seferberliği Başlıyor",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        institution="Çevre ve Şehircilik Bakanlığı",
        topics=("agaclandirma", "cevre"),
        claims=({"claim_text": "Fidan dikilecek", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=204,
        title="Çevre Bakanlığı: Riskli Bina Yıkım Ruhsatı Genelgesi Yayımlandı",
        published_at=_dt("2026-08-10T10:00:00+03:00"),
        institution="Çevre ve Şehircilik Bakanlığı",
        topics=("kentsel_donusum", "imar"),
        claims=({"claim_text": "Yıkım genelgesi yayımlandı", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt, semantic_similarity=0.40)
    assert not res.is_valid
    assert res.status == "unresolved"


def test_adversarial_identical_numbers_different_units() -> None:
    """Sayısal benzerlik olmasına rağmen birim/kapsam farklıysa eşleşmemelidir."""
    src = EventData(
        event_id=205,
        title="Hükümet: 1000 Yeni Sosyal Konut Yapılacak",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        institution="TOKİ",
        topics=("sosyal_konut",),
        claims=({"claim_text": "1000 konut yapılacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=206,
        title="Orman Genel Müdürlüğü: 1000 Hektar Orman Alanı Koruma Altına Alındı",
        published_at=_dt("2026-08-10T10:00:00+03:00"),
        institution="Orman Genel Müdürlüğü",
        topics=("orman_koruma",),
        claims=({"claim_text": "1000 hektar alan korundu", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt, semantic_similarity=0.30)
    assert not res.is_valid
    assert res.status == "unresolved"


def test_adversarial_geographic_scope_mismatch() -> None:
    """Farklı illerdeki benzer projeler birbirine bağlanmamalıdır."""
    src = EventData(
        event_id=207,
        title="Bursa Büyükşehir Belediyesi Hafif Raylı Sistem İhalesi",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        institution="Bursa Büyükşehir Belediyesi",
        topics=("belediye_yonetimi", "ulasim"),
        claims=({"claim_text": "Raylı sistem yapılacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=208,
        title="Antalya Büyükşehir Belediyesi Kavşak Düzenleme İhalesi",
        published_at=_dt("2026-08-10T10:00:00+03:00"),
        institution="Antalya Büyükşehir Belediyesi",
        topics=("belediye_yonetimi", "ulasim"),
        claims=({"claim_text": "Kavşak ihalesi yapıldı", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt, semantic_similarity=0.48)
    assert not res.is_valid
    assert res.status == "unresolved"


def test_adversarial_backward_chronology() -> None:
    """2024 yılı Sayıştay raporu 2026 yılı vaadiyle eşleşemez."""
    src = EventData(
        event_id=209,
        title="Gelecek Yıl Ulaşım Ücretlerine Zam Yapılmayacak",
        published_at=_dt("2026-08-15T10:00:00+03:00"),
        institution="Belediye",
        claims=({"claim_text": "Zam yapılmayacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=210,
        title="Sayıştay 2024 Denetim Raporu: Toplu Taşıma Sübvansiyon Açığı",
        published_at=_dt("2024-11-01T10:00:00+03:00"),
        institution="Belediye",
        claims=({"claim_text": "Sübvansiyon açığı var", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt, semantic_similarity=0.85)
    assert not res.is_valid
    assert res.status == "unresolved"
    assert "temporal_inversion" in res.evidence_payload.get("reason", "")


def test_adversarial_negation_statement_does_not_fulfil_promise() -> None:
    """Vaat edilen konunun yapılmayacağı/kaldırılmayacağı açıklaması fulfils değil contradicts olmalıdır."""
    src = EventData(
        event_id=301,
        title="Kamuda mülakat kaldırılacak",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        institution="Cumhurbaşkanlığı",
        claims=({"claim_text": "Kamuda mülakat kaldırılacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=302,
        title="Bakan açıkladı: Kamuda mülakat kaldırılmayacak",
        published_at=_dt("2026-08-10T10:00:00+03:00"),
        institution="Cumhurbaşkanlığı",
        claims=({"claim_text": "Mülakat kaldırılmayacak", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt, semantic_similarity=0.85)
    assert res.is_valid
    assert res.relation_type == "contradicts"


def test_adversarial_quoted_rejection_contradicts_promise() -> None:
    """Bakanın vaat iddiasını reddetmesi/yalanlaması çelişki olarak etiketlenmelidir."""
    src = EventData(
        event_id=303,
        title="Seçim vaadi: Mülakat kaldırılacak",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        institution="Cumhurbaşkanlığı",
        claims=({"claim_text": "Mülakat kaldırılacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=304,
        title="Bakanlık 'mülakat kaldırılacak' iddiasını reddetti",
        published_at=_dt("2026-08-10T10:00:00+03:00"),
        institution="Cumhurbaşkanlığı",
        claims=({"claim_text": "İddia yalanlandı", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt, semantic_similarity=0.85)
    assert res.is_valid
    assert res.relation_type == "contradicts"


def test_adversarial_sayistay_audit_fails_unkept_promise() -> None:
    """Tasarruf vaadi sonrası Sayıştay bütçe aşımı/zararı tespiti fails üretmelidir."""
    src = EventData(
        event_id=305,
        title="Kamu kurumlarında sıkı tasarruf tedbirleri uygulanacak",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        institution="Hazine ve Maliye Bakanlığı",
        claims=({"claim_text": "Tasarruf tedbirleri uygulanacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=306,
        title="Sayıştay Raporu: Bakanlıkta usulsüz harcama ve bütçe aşımı",
        published_at=_dt("2026-08-20T10:00:00+03:00"),
        institution="Sayıştay",
        claims=({"claim_text": "Bütçe aşımı tespit edildi", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt, semantic_similarity=0.85)
    assert res.is_valid
    assert res.relation_type == "fails"


def test_adversarial_institution_entity_fallback_flow() -> None:
    """Kurum doğrudan eşleşmese de target entity içinde varsa fallback çalışmalıdır."""
    src = EventData(
        event_id=307,
        title="Sağlık Bakanlığı 10 Bin Personel Alacak",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        institution="Sağlık Bakanlığı",
        claims=({"claim_text": "10 bin personel alınacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=308,
        title="Kamu Personel Alımı Resmi Gazetede Yayımlandı",
        published_at=_dt("2026-08-10T10:00:00+03:00"),
        entities=frozenset(["Sağlık Bakanlığı", "ÖSYM"]),
        claims=({"claim_text": "Kadro ilanı yayımlandı", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt, semantic_similarity=0.85)
    assert res.is_valid
    assert res.score_breakdown.institution_score == 1.0
    assert res.relation_type == "fulfils"
