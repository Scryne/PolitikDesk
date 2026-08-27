from __future__ import annotations

from unittest.mock import MagicMock

from politikdesk.political_memory import service as mem_service
from politikdesk.political_memory.service import ActorMemory, MemoryEntry
from politikdesk.political_memory.stance_shift import detect_stance_shifts_from_memory


def test_detect_shift_from_relation_chain():
    mem = ActorMemory(
        actor_name="Mehmet Şimşek",
        total_claims=2,
        promises=[
            MemoryEntry(
                event_id=1,
                event_title="Enflasyon Hedefi Açıklaması",
                claim_id=10,
                claim_text="Yıl sonu enflasyon %20 olacak",
                claim_type="promise",
                evidence_status="strongly_corroborated",
                first_reported_at="2026-01-10T10:00:00Z",
                speaker="Test Konusan",
                topic_tags=("para_politikasi",),
                attribution_strength="strong",
            )
        ],
        attributions=[],
        facts_and_numbers=[],
        relation_chains=[
            {
                "from_event_id": 1,
                "to_event_id": 2,
                "from_title": "Enflasyon Hedefi Açıklaması",
                "to_title": "TÜİK Yıl Sonu Enflasyonu %45 Açıkladı",
                "relation": "fails",
                "confidence": 0.95,
                "evidence_payload": {
                    "topic": "Enflasyon",
                    "source_claim": "Hedef %20",
                    "target_claim": "Gerçekleşen %45",
                },
            }
        ],
    )

    shifts = detect_stance_shifts_from_memory(mem)
    assert len(shifts) == 1
    s = shifts[0]
    assert s.actor_name == "Mehmet Şimşek"
    assert s.shift_type == "broken_promise"
    assert s.earlier_event_id == 1
    assert s.later_event_id == 2
    assert s.confidence == 0.95
    assert "Enflasyon" in s.topic_or_metric


def test_detect_reversal_from_polar_keywords():
    mem = ActorMemory(
        actor_name="Ahmet Yılmaz",
        total_claims=2,
        promises=[],
        attributions=[
            MemoryEntry(
                event_id=10,
                event_title="Faiz Politikası Açıklaması 2025",
                claim_id=101,
                claim_text="Faiz oranları derhal indirilmeli ve parasal gevşeme başlamalı",
                claim_type="attribution",
                evidence_status="strongly_corroborated",
                first_reported_at="2025-06-01T10:00:00Z",
                speaker="Test Konusan",
                topic_tags=("para_politikasi",),
                attribution_strength="strong",
            ),
            MemoryEntry(
                event_id=11,
                event_title="Faiz Politikası Açıklaması 2026",
                claim_id=102,
                claim_text="Enflasyonla mücadele için faiz artırılmalı ve parasal sıkılaşma sürmeli",
                claim_type="attribution",
                evidence_status="strongly_corroborated",
                first_reported_at="2026-02-01T10:00:00Z",
                speaker="Test Konusan",
                topic_tags=("para_politikasi",),
                attribution_strength="strong",
            ),
        ],
        facts_and_numbers=[],
        relation_chains=[],
    )

    shifts = detect_stance_shifts_from_memory(mem)
    assert len(shifts) == 1
    s = shifts[0]
    assert s.actor_name == "Ahmet Yılmaz"
    assert s.shift_type == "reversal"
    assert s.earlier_event_id == 10
    assert s.later_event_id == 11
    assert s.time_span_days > 200


def test_detect_numeric_divergence():
    mem = ActorMemory(
        actor_name="Cevdet Yılmaz",
        total_claims=2,
        promises=[
            MemoryEntry(
                event_id=20,
                event_title="Büyüme Hedefi OVP",
                claim_id=201,
                claim_text="2026 yılı büyüme hedefimiz %40 seviyesindedir",
                claim_type="promise",
                evidence_status="strongly_corroborated",
                first_reported_at="2026-01-01T10:00:00Z",
                speaker="Test Konusan",
                topic_tags=("para_politikasi",),
                attribution_strength="strong",
            ),
            MemoryEntry(
                event_id=21,
                event_title="Büyüme Revizyonu",
                claim_id=202,
                claim_text="Büyüme tahminimiz %15 olarak revize edilmiştir",
                claim_type="promise",
                evidence_status="strongly_corroborated",
                first_reported_at="2026-07-01T10:00:00Z",
                speaker="Test Konusan",
                topic_tags=("para_politikasi",),
                attribution_strength="strong",
            ),
        ],
        attributions=[],
        facts_and_numbers=[],
        relation_chains=[],
    )

    shifts = detect_stance_shifts_from_memory(mem)
    assert len(shifts) == 1
    s = shifts[0]
    assert s.shift_type == "numeric_divergence"
    assert s.earlier_event_id == 20
    assert s.later_event_id == 21
    d = s.to_dict()
    assert d["shift_type"] == "numeric_divergence"
    assert "Sayısal Gösterge" in d["topic_or_metric"]


def test_stance_sync_honours_the_search_actors_contract(monkeypatch) -> None:
    """DEF-02 Regresyon Testi: senkron yolu `search_actors` sözleşmesindeki
    `actors` ve `name` alanlarını işlemelidir."""
    mock_search = MagicMock(
        return_value={
            "actors": [
                {"id": 1, "name": "Ahmet Yılmaz", "entity_type": "person", "is_key_entity": True}
            ],
            "total": 1,
            "limit": 20,
            "offset": 0,
            "has_more": False,
        }
    )
    monkeypatch.setattr(mem_service, "search_actors", mock_search)

    mock_mem = ActorMemory(
        actor_name="Ahmet Yılmaz",
        total_claims=2,
        promises=[],
        attributions=[
            MemoryEntry(
                event_id=10,
                event_title="Faiz İndirimi",
                claim_id=101,
                claim_text="Faiz indirilmeli ve parasal gevşeme başlamalı",
                claim_type="attribution",
                evidence_status="strongly_corroborated",
                first_reported_at="2025-06-01T10:00:00Z",
                speaker="Test Konusan",
                topic_tags=("para_politikasi",),
                attribution_strength="strong",
            ),
            MemoryEntry(
                event_id=11,
                event_title="Faiz Artırımı",
                claim_id=102,
                claim_text="Faiz artırılmalı ve parasal sıkılaşma sürmeli",
                claim_type="attribution",
                evidence_status="strongly_corroborated",
                first_reported_at="2026-02-01T10:00:00Z",
                speaker="Test Konusan",
                topic_tags=("para_politikasi",),
                attribution_strength="strong",
            ),
        ],
        facts_and_numbers=[],
        relation_chains=[],
    )
    monkeypatch.setattr(mem_service, "get_actor_memory", MagicMock(return_value=mock_mem))

    # DEF-02 sözleşmesi artık OKUMA yolunda değil, SENKRON yolunda
    # geçerli: tespit arka planda koşar ve `list_all_stance_shifts`
    # yalnızca kalıcı kayıttan okur (Roadmap Faz 4.1). Bu yüzden
    # sözleşme, tarayan tarafta sınanır.
    yazilan: list[dict[str, object]] = []
    monkeypatch.setattr(
        "politikdesk.political_memory.shift_store._persist",
        lambda _cur, shift: yazilan.append(shift) or True,  # type: ignore[func-returns-value]
    )

    class _SahteCursor:
        rowcount = 0

        def execute(self, *_: object, **__: object) -> None:
            pass

        def fetchone(self) -> None:
            return None

        def __enter__(self) -> _SahteCursor:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    class _SahteConn:
        def cursor(self) -> _SahteCursor:
            return _SahteCursor()

        def commit(self) -> None:
            pass

        def __enter__(self) -> _SahteConn:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr("politikdesk.political_memory.shift_store.connection", lambda: _SahteConn())

    from politikdesk.political_memory.shift_store import sync

    stats = sync(actor_limit=10)
    assert stats.actors == 1, "search_actors sozlesmesindeki 'actors'/'name' islenmedi"
    assert stats.detected == 1
    assert yazilan[0]["actor_name"] == "Ahmet Yılmaz"
    assert yazilan[0]["shift_type"] == "reversal"


def test_detect_reversal_with_turkish_diacritics_and_multiword_phrases() -> None:
    """DEF-03 Regresyon Testi: Boşluklu ifadeler ve Türkçe diyakritikler (kırmızı çizgi, kabul edilemez vs.) eşleşmelidir."""
    mem = ActorMemory(
        actor_name="Parti Sözcüsü",
        total_claims=4,
        promises=[],
        attributions=[
            # Çift 1: Kırmızı çizgi vs Müzakere edilebilir
            MemoryEntry(
                event_id=30,
                event_title="İlk Beyan",
                claim_id=301,
                claim_text="Bu teklif bizim için kırmızı çizgimizdir ve kesinlikle olmaz",
                claim_type="attribution",
                evidence_status="strongly_corroborated",
                first_reported_at="2025-05-01T10:00:00Z",
                speaker="Test Konusan",
                topic_tags=("para_politikasi",),
                attribution_strength="strong",
            ),
            MemoryEntry(
                event_id=31,
                event_title="İkinci Beyan",
                claim_id=302,
                claim_text="Şartlar olgunlaşırsa her madde müzakere edilebilir ve mutabakat sağlandı",
                claim_type="attribution",
                evidence_status="strongly_corroborated",
                first_reported_at="2026-01-01T10:00:00Z",
                speaker="Test Konusan",
                topic_tags=("para_politikasi",),
                attribution_strength="strong",
            ),
            # Çift 2: Yasaklanmalı vs Serbest olmalı
            MemoryEntry(
                event_id=32,
                event_title="Üçüncü Beyan",
                claim_id=303,
                claim_text="Bu platformlar derhal yasaklanmalı ve kapatılmalıdır",
                claim_type="attribution",
                evidence_status="strongly_corroborated",
                first_reported_at="2025-06-01T10:00:00Z",
                speaker="Test Konusan",
                topic_tags=("para_politikasi",),
                attribution_strength="strong",
            ),
            MemoryEntry(
                event_id=33,
                event_title="Dördüncü Beyan",
                claim_id=304,
                claim_text="Bu platformların kullanımı serbest olmalı ve açılması desteklenmelidir",
                claim_type="attribution",
                evidence_status="strongly_corroborated",
                first_reported_at="2026-03-01T10:00:00Z",
                speaker="Test Konusan",
                topic_tags=("para_politikasi",),
                attribution_strength="strong",
            ),
        ],
        facts_and_numbers=[],
        relation_chains=[],
    )

    shifts = detect_stance_shifts_from_memory(mem)
    assert len(shifts) == 2
    shift_events = {(s.earlier_event_id, s.later_event_id) for s in shifts}
    assert (30, 31) in shift_events
    assert (32, 33) in shift_events


def test_non_matching_unrelated_claims_do_not_produce_false_positives() -> None:
    """DEF-03 Regresyon Testi: Zıtlık taşımayan veya alakasız iddialar yanlış pozitif üretmemelidir."""
    mem = ActorMemory(
        actor_name="Bakan",
        total_claims=2,
        promises=[],
        attributions=[
            MemoryEntry(
                event_id=40,
                event_title="Bütçe Sunumu",
                claim_id=401,
                claim_text="Bakanlığımızın 2026 yılı bütçe görüşmeleri komisyonda tamamlandı",
                claim_type="attribution",
                evidence_status="strongly_corroborated",
                first_reported_at="2025-11-01T10:00:00Z",
                speaker="Test Konusan",
                topic_tags=("para_politikasi",),
                attribution_strength="strong",
            ),
            MemoryEntry(
                event_id=41,
                event_title="Ziyaret Açıklaması",
                claim_id=402,
                claim_text="Heyetimiz bölgedeki sanayi tesislerini ziyaret etti ve bilgi aldı",
                claim_type="attribution",
                evidence_status="strongly_corroborated",
                first_reported_at="2026-02-01T10:00:00Z",
                speaker="Test Konusan",
                topic_tags=("para_politikasi",),
                attribution_strength="strong",
            ),
        ],
        facts_and_numbers=[],
        relation_chains=[],
    )

    shifts = detect_stance_shifts_from_memory(mem)
    assert len(shifts) == 0


def test_polarity_is_evaluated_once_per_entry_not_once_per_pair(monkeypatch) -> None:
    """Tarama O(n²) çifttir; kutup çıkarımı O(n) olmalıdır.

    Ön hesap yokken her kaydın metni ve kutbu, o kaydın girdiği HER çift
    için yeniden hesaplanıyordu. Ölçülen bedel gerçekti:
    `/api/memory/stance-shifts` 5,2 saniye sürüyordu (olay sayfası hedefi
    p95 < 1,5 sn). Ön hesapla 0,7 saniyeye indi ve çıktı birebir aynı
    kaldı — bu test o değişikliğin geri alınmasını engeller.
    """
    from politikdesk.political_memory import stance_shift

    calls = {"n": 0}
    original = stance_shift._evaluate_text_polarity

    def counting(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(stance_shift, "_evaluate_text_polarity", counting)

    entry_count = 12
    mem = ActorMemory(
        actor_name="Ölçüm Aktörü",
        total_claims=entry_count,
        promises=[],
        attributions=[
            MemoryEntry(
                event_id=100 + i,
                event_title=f"Beyan {i}",
                claim_id=1000 + i,
                claim_text=f"Bütçe görüşmeleri {i}. oturumda tamamlandı",
                claim_type="attribution",
                evidence_status="strongly_corroborated",
                first_reported_at=f"2026-01-{i + 1:02d}T10:00:00Z",
            )
            for i in range(entry_count)
        ],
        facts_and_numbers=[],
        relation_chains=[],
    )

    stance_shift.detect_stance_shifts_from_memory(mem)

    pair_count = entry_count * (entry_count - 1) // 2
    linear_budget = entry_count * len(stance_shift.POLARITY_PAIRS)

    assert calls["n"] == linear_budget, (
        f"Kutup cikarimi {calls['n']} kez cagrildi; kayit basina bir kez, "
        f"yani {linear_budget} cagri beklenir. Cift basina hesaplanirsa "
        f"{pair_count * len(stance_shift.POLARITY_PAIRS)} cagriya cikar."
    )
