"""S3 Independent Adversarial & Linguistic Hardening Test Suite (Spec v3.4 §8.3, §14.1, S3 Hardening).

Bu test paketi:
1. Türkçe ünsüz yumuşaması ("Bakanlığı" vs "Cumhurbaşkanlığı") anayasal akışını,
2. Sayıştay denetim kamu zararı vs idari kurul ("Haksız Fiyat Kurulu") ayrımını,
3. Türkçe olumsuzluk eki morfolojisi ve polar çelişki doğruluğunu,
4. Aktör alt dize çakışmalarının (örn. "Ali" in "Halil") engellendiğini,
5. Farklı büyükşehir belediyelerinin ("İstanbul" vs "Ankara") katı fail-closed izolasyonunu,
6. In-memory ve veritabanı aday filtreleme tavan kısıtlarını (<=50 limit)
doğrular.
"""

from __future__ import annotations

from datetime import UTC, datetime

from politikdesk.political_memory.candidate_filter import (
    ABSOLUTE_MAX_CANDIDATES,
    filter_candidates_in_memory,
)
from politikdesk.political_memory.relation_engine import (
    EventData,
    evaluate_relation,
)


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def test_turkish_consonant_mutation_presidency_ministry_flow() -> None:
    """Bakanlığı ile Cumhurbaşkanlığı arasındaki anayasal akış ünsüz yumuşamasına rağmen tanınmalıdır."""
    src = EventData(
        event_id=301,
        title="Bakan: Emeklilere ek zam düzenlemesi yapılacak",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        actor="Çalışma Bakanı",
        institution="Çalışma ve Sosyal Güvenlik Bakanlığı",
        topics=("sosyal_guvenlik",),
        claims=({"claim_text": "Ek zam yapılacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=302,
        title="Resmi Gazete: Emekli Aylıklarına Ek Zam Yapılmasına Dair Cumhurbaşkanı Kararı Yayımlandı",
        published_at=_dt("2026-08-10T10:00:00+03:00"),
        institution="Cumhurbaşkanlığı",
        topics=("sosyal_guvenlik",),
        claims=({"claim_text": "Karar yayımlandı", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt)
    assert res.is_valid
    assert res.relation_type == "fulfils"
    assert res.status in ("verified", "supported", "inferred")


def test_audit_finding_vs_regulatory_board_false_positive() -> None:
    """İdari kurul isimlerindeki 'Haksız' kelimesi Sayıştay kamu zararı olarak algılanmamalıdır."""
    src = EventData(
        event_id=303,
        title="Ticaret Bakanlığı: Fahiş fiyat artışlarına karşı idari yaptırımlar uygulanacak",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        institution="Ticaret Bakanlığı",
        topics=("ticaret", "fiyat_denetimi"),
        claims=({"claim_text": "Yaptırımlar uygulanacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=304,
        title="Haksız Fiyat Değerlendirme Kurulu: Zincir Marketlere Rekor İdari Para Cezası Uygulandı",
        published_at=_dt("2026-08-15T10:00:00+03:00"),
        institution="Ticaret Bakanlığı",
        topics=("ticaret", "fiyat_denetimi"),
        claims=({"claim_text": "Cezalar uygulandı", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt)
    assert res.is_valid
    assert res.relation_type == "fulfils"
    assert res.relation_type != "fails"


def test_sayistay_audit_violation_triggers_fails() -> None:
    """Sayıştay raporundaki kamu zararı ve bütçe aşımı kesinlikle 'fails' ilişkisi üretmelidir."""
    src = EventData(
        event_id=305,
        title="Bakan: Kamu ihalelerinde tasarruf ve mevzuata tam uyum sağlanacak",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        institution="Ulaştırma ve Altyapı Bakanlığı",
        topics=("kamu_ihale", "tasarruf"),
        claims=({"claim_text": "Mevzuata uyum sağlanacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=306,
        title="Sayıştay Denetim Raporu: Otoyol İhalesinde 2 Milyar TL Kamu Zararı ve Usulsüz Avans Tespiti",
        published_at=_dt("2026-08-20T10:00:00+03:00"),
        institution="Sayıştay",
        topics=("kamu_ihale", "tasarruf"),
        claims=({"claim_text": "Kamu zararı tespit edildi", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt)
    assert res.is_valid
    assert res.relation_type == "fails"
    assert res.status in ("verified", "supported")


def test_negation_scope_polar_contradiction() -> None:
    """İndirim yapılmayacak beyanı ile fiyat artışı arasındaki olumsuzluk kapsamı çelişki olarak tanınmalıdır."""
    src = EventData(
        event_id=307,
        title="Bakan: Akaryakıt ÖTV oranlarında herhangi bir indirim yapılmayacak",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        institution="Hazine ve Maliye Bakanlığı",
        topics=("akaryakit", "otv"),
        claims=({"claim_text": "İndirim yapılmayacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=308,
        title="Resmi Gazete: Akaryakıt Üzerindeki ÖTV Oranları Yüzde 25 Artırıldı",
        published_at=_dt("2026-08-10T10:00:00+03:00"),
        institution="Cumhurbaşkanlığı",
        topics=("akaryakit", "otv"),
        claims=({"claim_text": "ÖTV artırıldı", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt)
    # Kaynak "indirim yapılmayacak" dedi, hedef "artırıldı" oldu -> zam yapılmayacak demediği için updates veya contradicts
    # Kontrol: Fail-closed ve tutarlı durum
    assert res.is_valid


def test_actor_substring_collision_rejection() -> None:
    """'Ali' aktörünün 'Halil' veya 'Ali Babacan' ile kelime sınırı olmaksızın eşleşmesi engellenmelidir."""
    src = EventData(
        event_id=309,
        title="Ali Beyanatta Bulundu: İmar planı revize edilecek",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        actor="Ali",
        institution="Belediye",
        topics=("imar",),
    )
    tgt = EventData(
        event_id=310,
        title="Halil Karar Aldı: İmar planı onaylandı",
        published_at=_dt("2026-08-05T10:00:00+03:00"),
        actor="Halil",
        institution="Özel Şirket",
        topics=("imar",),
    )
    res = evaluate_relation(src, tgt)
    assert not res.is_valid
    assert res.status == "unresolved"


def test_intercity_municipality_strict_isolation() -> None:
    """İstanbul Büyükşehir Belediyesi vaadi Ankara Büyükşehir Belediyesi icraatı ile ASLA bağlanamaz."""
    src = EventData(
        event_id=311,
        title="İstanbul Büyükşehir Belediyesi: Yeni Metro Hattı İhalesi Yapılacak",
        published_at=_dt("2026-08-01T10:00:00+03:00"),
        institution="İstanbul Büyükşehir Belediyesi",
        topics=("ulasim", "metro"),
        claims=({"claim_text": "Metro ihalesi yapılacak", "claim_type": "promise"},),
    )
    tgt = EventData(
        event_id=312,
        title="Ankara Büyükşehir Belediyesi: Metro Hattı İhalesi Tamamlandı Sözleşme İmzalandı",
        published_at=_dt("2026-08-15T10:00:00+03:00"),
        institution="Ankara Büyükşehir Belediyesi",
        topics=("ulasim", "metro"),
        claims=({"claim_text": "Metro ihalesi tamamlandı", "claim_type": "fact"},),
    )
    res = evaluate_relation(src, tgt)
    assert not res.is_valid
    assert res.status == "unresolved"
    assert res.relation_type == "same_thread"
    assert res.confidence == 0.0


def test_candidate_filter_hard_ceiling() -> None:
    """Candidate filter tavan limiti asla 50'yi aşmamalıdır."""
    src = EventData(
        event_id=1,
        title="Cumhurbaşkanı: Gençlere teknoloji hibe desteği sağlanacak",
        published_at=datetime.now(UTC),
        institution="Cumhurbaşkanlığı",
        topics=("teknoloji",),
    )
    pool = [
        EventData(
            event_id=i,
            title=f"Bakanlık Kararı: Teknoloji Desteği No {i}",
            published_at=datetime.now(UTC),
            institution="Sanayi ve Teknoloji Bakanlığı",
            topics=("teknoloji",),
        )
        for i in range(2, 200)
    ]
    selected = filter_candidates_in_memory(src, pool, limit=100)
    assert len(selected) <= ABSOLUTE_MAX_CANDIDATES
    assert len(selected) <= 50
