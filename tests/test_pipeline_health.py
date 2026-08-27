"""Boru hattı aşama sağlığı monitörü testleri (F4-05, B-78, S3).

Tüm boru hattı aşamalarının (embed, entities, cluster, claims, evidence, context,
political_relations, scheduler_match) ve nabızların (ingest, briefing, metrics, purge)
izleme bütünlüğünü ve çalışan işçilerle birebir SQL eşliğini test eder.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from politikdesk.evidence.rules import engine_version
from politikdesk.nlp.claims_pipeline import MAX_CLAIM_ATTEMPTS
from politikdesk.pipeline_health import (
    HEARTBEATS,
    STAGES,
    _classify,
    _heartbeat_report,
    check_and_log,
)
from politikdesk.political_memory.orchestrator import RELATION_ENGINE_VERSION


def test_stages_and_heartbeats_completeness() -> None:
    """Tüm kritik boru hattı adımları ve nabızları tanımlı olmalı."""
    stage_keys = [s.key for s in STAGES]
    expected_stages = [
        "embed",
        "entities",
        "cluster",
        "claims",
        "evidence",
        "context",
        "political_relations",
        "scheduler_match",
    ]
    assert stage_keys == expected_stages

    heartbeat_keys = [h.key for h in HEARTBEATS]
    expected_heartbeats = ["ingest", "briefing", "metrics", "purge", "backup", "recovery_drill"]
    assert heartbeat_keys == expected_heartbeats


def test_every_stage_and_heartbeat_has_hint_and_positive_threshold() -> None:
    for stage in (*STAGES, *HEARTBEATS):
        assert stage.key.strip(), "Aşama anahtarı boş olamaz"
        assert stage.label.strip(), f"{stage.key}: etiket boş"
        assert stage.hint.strip(), f"{stage.key}: ipucu boş"
        assert stage.threshold_hours > 0, f"{stage.key}: eşik sıfır veya negatif"


def test_claims_stage_predicate_parity_with_worker() -> None:
    """İzleyici claims yüklemi, nlp/claims_pipeline.py::PENDING_EVENTS_SQL ile tam uyumlu olmalı (F5-16)."""
    claims_stage = next(s for s in STAGES if s.key == "claims")

    # Temel SQL yapısı denetimi
    assert "e.merged_into_id IS NULL" in claims_stage.sql
    assert "e.article_count > 0" in claims_stage.sql
    assert "e.claims_attempted_at IS NULL" in claims_stage.sql
    assert "e.last_update_at > e.claims_attempted_at" in claims_stage.sql
    assert "NOT EXISTS (SELECT 1 FROM claims c WHERE c.event_id = e.id)" in claims_stage.sql
    assert "e.claims_attempt_count < %s" in claims_stage.sql

    # F5-16: NOT EXISTS (claims) bir AND dalı DEĞİL, OR'un içinde olmalıdır
    assert (
        "AND NOT EXISTS (SELECT 1 FROM claims c WHERE c.event_id = e.id)" not in claims_stage.sql
    ), "claims izleyicisinde F5-16 hatası: NOT EXISTS dış AND dalında olmamalı"

    assert claims_stage.get_params() == (MAX_CLAIM_ATTEMPTS,)


def test_claims_stage_age_is_worker_liveness_not_oldest_backlog_item() -> None:
    """İddia aşamasının yaş ölçütü `min(last_update_at)` OLMAMALI.

    18 Ağustos 2026 denetiminde aşama kırmızıydı ve "94.617 saattir
    bekliyor" diyordu; oysa iddia çıkarımı 16 dakika önce koşmuştu.
    İki sebep üst üste binmişti:

      1. `PENDING_EVENTS_SQL` kuyruğu `last_update_at DESC` işler — eski
         uç KASTEN en sonda bekler. Oraya bakan alarm, işçinin bilinçli
         önceliklendirmesini arıza sanar.
      2. Geriye dönük yüklenen Sayıştay/TBMM arşivinde `last_update_at`
         belgenin KENDİ tarihidir (2015). Yaş ölçüsü yapısal olarak
         eşiğin altına inemezdi.

    Modülün kendi kuralı: "Yanlış alarm veren bir alarm kapatılır."
    Kapanmış bir alarm gerçek kopmayı da gizler; bu yüzden ölçüt
    işçinin canlılığına (`claims_attempted_at`) bağlandı.
    """
    claims_stage = next(s for s in STAGES if s.key == "claims")

    assert "min(e.last_update_at)" not in claims_stage.sql, (
        "Yas olcutu yine kuyrugun eski ucuna baglanmis — arsiv yuklemesi "
        "alarmi kalici kirmiziya cakar."
    )
    assert "max(claims_attempted_at)" in claims_stage.sql
    # Hiç denenmemişse: satırın gerçek ekleniş anı, belgenin tarihi değil.
    assert "min(created_at)" in claims_stage.sql
    # Birikme sayısı bilgi olarak korunmalı.
    assert "AS backlog" in claims_stage.sql


def test_claims_stage_age_axis_tracks_worker_liveness_only() -> None:
    """YAŞ ekseni yalnızca "işçi koşuyor mu?"yu ölçer — kuyruk boyunu DEĞİL.

    Arşiv kuyruğu dolu ama işçi çalışıyorsa yaş ekseni yeşildir ve bu
    doğrudur: kopma yoktur. Kuyruğun kapanıp kapanmadığı AYRI bir
    eksenin işidir (`backlog_limit`) — aşağıdaki testlere bakın.
    """
    from politikdesk.pipeline_health import _classify

    claims_stage = next(s for s in STAGES if s.key == "claims")
    # İşçi 16 dakika önce koştu: kopma yok.
    assert _classify(0.27, claims_stage.threshold_hours) == "green"
    # İşçi 7 saattir hiç denemediyse gerçekten kopmuştur.
    assert _classify(7.0, claims_stage.threshold_hours) == "red"


def test_evidence_stage_predicate_parity_with_worker() -> None:
    """İzleyici evidence yüklemi, evidence/pipeline.py::score_claims ile tam uyumlu olmalı (F5-17)."""
    evidence_stage = next(s for s in STAGES if s.key == "evidence")

    assert "status_reason IS NULL" in evidence_stage.sql
    assert "status_reason->>'engine_version' IS DISTINCT FROM %s" in evidence_stage.sql
    assert "SELECT 1 FROM evidence ev" in evidence_stage.sql
    assert "ev.claim_id = c.id" in evidence_stage.sql
    assert "ev.created_at > (c.status_reason->>'computed_at')::timestamptz" in evidence_stage.sql

    # Dinamik engine_version kontrolü
    assert evidence_stage.get_params() == (engine_version(),)


def test_political_relations_stage_params() -> None:
    """Siyasi ilişkiler aşaması doğru motor sürüm parametrelerini almalı."""
    stage = next(s for s in STAGES if s.key == "political_relations")
    assert stage.get_params() == (RELATION_ENGINE_VERSION, RELATION_ENGINE_VERSION)


@pytest.mark.parametrize(
    ("age", "threshold", "expected"),
    [
        (None, 2.0, "green"),
        (0.0, 2.0, "green"),
        (0.9, 2.0, "green"),
        (1.0, 2.0, "amber"),  # threshold * 0.5
        (1.9, 2.0, "amber"),
        (2.0, 2.0, "red"),
        (5.0, 2.0, "red"),
    ],
)
def test_classification_logic(age: float | None, threshold: float, expected: str) -> None:
    assert _classify(age, threshold) == expected


def test_heartbeat_report_handles_missing_last_at() -> None:
    beat = HEARTBEATS[0]

    class _Cur:
        def execute(self, *_a: object, **_k: object) -> None:
            pass

        def fetchone(self) -> dict[str, object]:
            return {"last_at": None}

    report = _heartbeat_report(_Cur(), beat)
    assert report.status == "amber"
    assert report.oldest_hours is None
    assert "Hiç kayıt yok" in report.hint


def test_heartbeat_report_clips_future_timestamp() -> None:
    beat = HEARTBEATS[0]
    future = datetime.now(UTC) + timedelta(hours=5)

    class _Cur:
        def execute(self, *_a: object, **_k: object) -> None:
            pass

        def fetchone(self) -> dict[str, object]:
            return {"last_at": future}

    report = _heartbeat_report(_Cur(), beat)
    assert report.oldest_hours == 0.0
    assert report.status == "green"


def test_check_and_log_runs_cleanly(monkeypatch) -> None:  # noqa: ANN001
    """alarms() boşken veya doluyken check_and_log düzgün sözlük listesi döndürmeli."""
    from politikdesk.pipeline_health import StageReport

    sample_report = [
        StageReport(
            key="claims",
            label="İddia çıkarımı",
            status="red",
            backlog=15,
            oldest_hours=8.5,
            threshold_hours=6.0,
            hint="LLM bütçesi kontrolü",
            kind="backlog",
        )
    ]

    monkeypatch.setattr("politikdesk.pipeline_health.alarms", lambda: sample_report)
    logged = check_and_log()
    assert len(logged) == 1
    assert logged[0]["key"] == "claims"
    assert logged[0]["status"] == "red"


# ═══════════════ birikme ekseni: "kuyruk KAPANIYOR mu?" (20 Ağu 2026)
#
# Denetimde ölçülen kör nokta: yaş ekseni bu aşamada bilerek devre dışı
# (işçi canlılığını ölçer) ve birikme yalnızca BİLGİ olarak gösteriliyordu.
# Sonuç: işçi ayakta, aşama yeşil, kuyruk büyüyor ve bunu söyleyen hiçbir
# sinyal yok. Ölçüldü: varış ~29 olay/saat, işlem ~15 olay/saat; birikme
# aktif saatlerde saatte ~14 büyüyor ve 958'e ulaşmıştı.


def test_claims_stage_declares_a_backlog_limit() -> None:
    """Birikme eşiği KEYFİ değil, aşamanın tasarım hızından türer.

    Görev 10 dakikada bir 5 olay işler = 30 olay/saat. Alarm penceresi
    6 saat. 30 x 6 = 180: bunu aşan kuyruk, aşama tam tasarım hızında
    koşsa bile kendi penceresinde erimez.
    """
    claims_stage = next(s for s in STAGES if s.key == "claims")
    assert claims_stage.backlog_limit == 180


def test_growing_queue_is_red_even_while_the_worker_is_alive() -> None:
    """**Asıl regresyon.** İşçi canlıyken de kuyruk kapanmayabilir.

    Bu iki koşul birlikte gerçekleşti ve aşama YEŞİL göründü; bu test
    o davranış geri gelirse kırmızıya döner.
    """
    from politikdesk.pipeline_health import _classify, _classify_backlog, _worst

    stage = next(s for s in STAGES if s.key == "claims")
    yas = _classify(0.11, stage.threshold_hours)  # işçi 7 dk önce koştu
    birikme = _classify_backlog(958, stage.backlog_limit)  # ölçülen gerçek kuyruk

    assert yas == "green", "işçi canlı — yaş ekseni doğru şekilde yeşil"
    assert birikme == "red", "958 olay 6 saatte erimez"
    assert _worst(yas, birikme) == "red", "yeşil eksen kırmızıyı GİZLEYEMEZ"


@pytest.mark.parametrize(
    ("backlog", "expected"),
    [
        (0, "green"),
        (89, "green"),  # sınırın yarısının altı
        (90, "amber"),  # yarısı — bakılmalı
        (179, "amber"),
        (180, "red"),  # pencerede erimez
        (958, "red"),  # ölçüm anındaki gerçek değer
    ],
)
def test_backlog_classification(backlog: int, expected: str) -> None:
    from politikdesk.pipeline_health import _classify_backlog

    assert _classify_backlog(backlog, 180) == expected


def test_stages_without_a_limit_are_unaffected() -> None:
    """Ölçüt yalnızca sınır TANIMLI aşamalara uygulanır.

    Diğer aşamaların yaş ekseni sağlıklı çalışıyor; onlara sayı eşiği
    dayatmak, modülün kendi kuralını ("yanlış alarm veren alarm
    kapatılır") çiğnerdi.
    """
    from politikdesk.pipeline_health import _classify_backlog

    assert _classify_backlog(10_000, None) == "green"
    for stage in STAGES:
        if stage.key != "claims":
            assert stage.backlog_limit is None, f"{stage.key}: sayı eşiği ölçülmeden eklenmemeli"


def test_stages_age_axis_tracks_ingestion_latency_not_historical_pub_dates() -> None:
    """OPS-001 Regresyon Koruması:

    Arşivden yüklenen belgeler (Sayıştay 2021, TBMM 2015) sisteme yeni
    girmiş olsa bile `published_at` veya `e.last_update_at` yılları
    bulabilir. Aşama monitörünün yaş ekseni, belgenin geçmiş yayın
    tarihine DEĞİL, sistemdeki kuyruk bekleme süresine
    (`first_seen_at` ve `created_at`) bakmalıdır.
    """
    cluster_stage = next(s for s in STAGES if s.key == "cluster")
    assert "min(first_seen_at)" in cluster_stage.sql
    assert "published_at" not in cluster_stage.sql

    context_stage = next(s for s in STAGES if s.key == "context")
    assert "min(e.created_at)" in context_stage.sql
    assert "min(e.last_update_at)" not in context_stage.sql

    political_stage = next(s for s in STAGES if s.key == "political_relations")
    assert "min(e.created_at)" in political_stage.sql
    assert "min(e.last_update_at)" not in political_stage.sql
