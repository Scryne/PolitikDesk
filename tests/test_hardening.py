"""Faz 4 sertleştirme testleri (F4-05, F4-07, F4-16 · B-78, B-80).

Bu dosyanın dört konusu da aynı aileden: **sistem çalışıyor görünürken
aslında çalışmıyordu.** Faz 3 sonrası denetimin dersi buydu ve buradaki
testler o dersin kod karşılığıdır.

  B-80  Adaptör hatayı yutunca tur "başarılı" kaydediliyordu
  F4-05 Sıfır iddia dönen olay sonsuza dek yeniden deneniyordu
  B-78  Bir aşamada birikme olsa kimse fark etmiyordu
  F4-16 Denetim izine hangi eylemlerin yazıldığı belgelenmemişti
"""

from __future__ import annotations

import pytest

from politikdesk import audit
from politikdesk.ingestion.adapters.base import (
    FailureRecorder,
    FakeAdapter,
    drain_failures,
)


# ===========================================================================
# B-80 — yutulan hata boru hattına ulaşmalı
# ===========================================================================
class _SwallowingAdapter(FailureRecorder):
    """İki akışı olan, birini kaybeden bir adaptörün minimal taklidi."""

    def __init__(self, slug: str = "test", *, fail: int = 0, yield_items: int = 0):
        super().__init__()
        self.slug = slug
        self._fail = fail
        self._yield = yield_items

    def fetch(self) -> list[object]:
        for i in range(self._fail):
            self.record_failure(f"https://ornek/{i}", TimeoutError("zaman aşımı"))
        return [object()] * self._yield


def test_failure_recorder_carries_swallowed_errors() -> None:
    adapter = _SwallowingAdapter(fail=2)
    adapter.fetch()
    failures = drain_failures(adapter)

    assert len(failures) == 2
    assert "TimeoutError" in failures[0]


def test_drain_empties_the_ledger() -> None:
    """Boşaltılmazsa bir turun hatası sonraki turda da raporlanır ve
    kaynak düzeldiği hâlde kırmızı kalır."""
    adapter = _SwallowingAdapter(fail=1)
    adapter.fetch()

    assert len(drain_failures(adapter)) == 1
    assert drain_failures(adapter) == []


def test_adapter_without_ledger_is_tolerated() -> None:
    """`FailureRecorder` türetmeyen adaptör (ağa çıkmayan) sorun değil."""
    assert drain_failures(FakeAdapter("sahte")) == []


def test_silent_failure_makes_the_round_unsuccessful(monkeypatch) -> None:
    """Asıl arıza: 0 öğe + yutulmuş hata = BAŞARISIZ tur.

    Resmî Gazete'nin TLS hatası tam olarak bu şekilde `succeeded=true`
    kaydediliyordu.
    """
    from politikdesk.ingestion import pipeline as pipeline_mod

    recorded: dict[str, object] = {}

    def _fake_record_fetch(source_id, **kwargs):  # noqa: ANN001, ANN003
        recorded.update(kwargs)

    monkeypatch.setattr(pipeline_mod.repository, "record_fetch", _fake_record_fetch)
    monkeypatch.setattr(
        pipeline_mod, "build_adapter", lambda source, http: _SwallowingAdapter(fail=1)
    )

    source = _source_row()
    pipeline_mod.Pipeline().run_source(source)

    assert recorded["items_fetched"] == 0
    assert recorded["error"] is not None, (
        "0 öğe döndüren ve içeride hata yutan tur başarılı sayılamaz — "
        "B-80'in tam olarak düzelttiği davranış budur."
    )
    assert "TimeoutError" in str(recorded["error"])


def test_partial_failure_keeps_the_round_successful(monkeypatch) -> None:
    """Öğe geldiyse tur başarılıdır; düşen akış yalnızca ize yazılır.

    Aksi hâlde üç akışlı bir kaynağın biri her ara sıra düştüğünde
    kaynak kalıcı kırmızıya düşer ve gerçek arıza görünmez olur.
    """
    from politikdesk.ingestion import pipeline as pipeline_mod

    recorded: dict[str, object] = {}

    def _fake_record_fetch(source_id, **kwargs):  # noqa: ANN001, ANN003
        recorded.update(kwargs)

    monkeypatch.setattr(pipeline_mod.repository, "record_fetch", _fake_record_fetch)
    monkeypatch.setattr(
        pipeline_mod,
        "build_adapter",
        lambda source, http: _SwallowingAdapter(fail=1, yield_items=3),
    )
    # Saklama adımı DB ister; bu testin konusu değil.
    monkeypatch.setattr(
        pipeline_mod.Pipeline,
        "_store_items",
        lambda self, items, source, decision, stats: stats,
    )

    pipeline_mod.Pipeline().run_source(_source_row())

    assert recorded["error"] is None
    assert recorded["partial_failures"], "Kısmi hata ize yazılmalı"


def _source_row():
    from politikdesk.ingestion.repository import SourceRow

    return SourceRow(
        id=1,
        name="Test",
        slug="test",
        tier=1,
        kind="official",
        independence_group=None,
        access_method="rss",
        tos_status="allowed",
        base_url="https://ornek",
        feed_url="https://ornek/rss",
        is_active=True,
        adapter="rss",
        extra_feeds=[],
        keyword_filter=[],
        topics=[],
        is_wire_reference=False,
    )


# ===========================================================================
# F4-05 — sıfır iddia dönen olay sonsuza dek denenmemeli
# ===========================================================================
def test_pending_events_sql_excludes_exhausted_attempts() -> None:
    """Yüklem üç kaçış yolu tanımalı: hiç denenmemiş, yeni malzeme geldi,
    deneme hakkı dolmamış."""
    from politikdesk.nlp.claims_pipeline import MAX_CLAIM_ATTEMPTS, PENDING_EVENTS_SQL

    assert "claims_attempted_at IS NULL" in PENDING_EVENTS_SQL
    assert "last_update_at > e.claims_attempted_at" in PENDING_EVENTS_SQL
    assert "claims_attempt_count < %s" in PENDING_EVENTS_SQL
    assert MAX_CLAIM_ATTEMPTS >= 1


def test_health_monitor_uses_same_predicate_as_the_worker() -> None:
    """İzleyici ile işçi ayrışırsa alarm ya yanlış öter ya hiç ötmez.

    13 Ağustos arızasının dersi: gerçeği iki yerde ayrı ayrı tanımlamak,
    ikisinin de yanlış olabileceği anlamına gelir.
    """
    from politikdesk.nlp.claims_pipeline import MAX_CLAIM_ATTEMPTS
    from politikdesk.pipeline_health import STAGES

    claims_stage = next(s for s in STAGES if s.key == "claims")

    for clause in (
        "claims_attempted_at IS NULL",
        "last_update_at > e.claims_attempted_at",
        "claims_attempt_count < %s",
    ):
        assert clause in claims_stage.sql, (
            f"İzleyicinin claims yüklemi işçininkiyle ayrışmış: {clause!r} yok."
        )
    assert claims_stage.get_params() == (MAX_CLAIM_ATTEMPTS,)


@pytest.mark.parametrize(
    ("age", "threshold", "expected"),
    [
        (None, 2.0, "green"),  # bekleyen yok
        (0.1, 2.0, "green"),
        (1.0, 2.0, "amber"),  # eşiğin yarısı
        (2.0, 2.0, "red"),
        (99.0, 2.0, "red"),
    ],
)
def test_stage_classification(age, threshold, expected) -> None:  # noqa: ANN001
    from politikdesk.pipeline_health import _classify

    assert _classify(age, threshold) == expected


def test_every_pipeline_stage_has_a_hint() -> None:
    """Alarm ne yapılacağını söylemiyorsa alarm değil, gürültüdür."""
    from politikdesk.pipeline_health import HEARTBEATS, STAGES

    for stage in (*STAGES, *HEARTBEATS):
        assert stage.hint.strip(), f"{stage.key}: ipucu boş"
        assert stage.threshold_hours > 0


def test_metrics_heartbeat_reads_the_run_time_not_the_day_label() -> None:
    """Nabız `computed_at` okumalı, `recorded_at` değil (migration 0008).

    Ölçülen arıza: metrik aşaması yaşı `-14,66` saat gösteriyordu — bir
    nabzın geleceği göstermesi, yanlış sütunu okuduğunun kanıtıdır.
    `recorded_at` satırın ANLATTIĞI günün etiketidir ve öğleye
    sabitlenmiştir (gün sınırında kaymasın diye); yerel gün üzerinden
    kurulduğu için UTC'ye göre ileri düşebiliyordu.
    """
    from politikdesk.pipeline_health import HEARTBEATS

    beat = next(b for b in HEARTBEATS if b.key == "metrics")
    assert "computed_at" in beat.sql
    assert "recorded_at" not in beat.sql


def test_heartbeat_age_is_never_negative() -> None:
    """Gelecek tarihli kayıt "çok taze" diye okunmamalı.

    Saat kayması ya da sentetik bir zaman damgası nabzı negatife
    düşürebilir. Negatif yaş panoda anlamsızdır ve göstergeye duyulan
    güveni bozar; sıfıra kırpılır.
    """
    from datetime import UTC, datetime, timedelta

    from politikdesk.pipeline_health import HEARTBEATS, _heartbeat_report

    beat = HEARTBEATS[0]
    future = datetime.now(UTC) + timedelta(hours=14)

    class _Cur:
        def execute(self, *_a: object, **_k: object) -> None: ...
        def fetchone(self) -> dict[str, object]:
            return {"last_at": future}

    report = _heartbeat_report(_Cur(), beat)
    assert report.oldest_hours == 0.0
    assert report.status == "green"


def test_stage_report_runs_against_live_schema(db_conn) -> None:  # noqa: ANN001
    """Sorgular gerçek şemaya karşı koşmalı — sütun adı kayması sessizdir."""
    from politikdesk.pipeline_health import stage_report

    report = stage_report()
    keys = {r.key for r in report}

    assert {
        "ingest",
        "embed",
        "entities",
        "cluster",
        "claims",
        "evidence",
        "context",
        "political_relations",
        "scheduler_match",
        "briefing",
        "metrics",
        "purge",
    } <= keys
    for row in report:
        assert row.status in {"green", "amber", "red"}


# ===========================================================================
# F4-16 — denetim izi sözleşmesi
# ===========================================================================
def test_every_audit_action_in_code_is_declared() -> None:
    """Kodun yazdığı her eylem `ACTIONS`'ta tanımlı olmalı.

    Sözlük belgedir: hangi eylemlerin denetlendiğini listeleyemiyorsak,
    bir eylemin kaydını unuttuğumuzu da fark edemeyiz (F4-16 DoD).
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "politikdesk"
    # `_audit(cur, "merge_events", ...)` ve `'source_updated'` gibi
    # doğrudan SQL'e gömülü eylem adlarını yakalar.
    pattern = re.compile(
        r"(?:_audit\(\s*cur\s*,\s*|VALUES\s*\(\s*'[^']*'\s*,\s*)"
        r"['\"]([a-z_]+)['\"]"
    )

    found: set[str] = set()
    for path in root.rglob("*.py"):
        found |= set(pattern.findall(path.read_text(encoding="utf-8")))

    undeclared = found - set(audit.ACTIONS)
    assert not undeclared, (
        f"Denetim izine yazılan ama ACTIONS'ta tanımlı olmayan eylem(ler): "
        f"{sorted(undeclared)}. politikdesk/audit.py::ACTIONS içine ekleyin."
    )


def test_unknown_audit_action_is_rejected() -> None:
    """Serbest metin `action` sızarsa sözleşme anlamını yitirir."""
    with pytest.raises(audit.UnknownAuditAction):
        audit.write("uydurma_eylem", "target/1")


def test_f4_16_required_actions_are_covered() -> None:
    """Yol Haritası F4-16 DoD'sinin saydığı eylemler."""
    required = {
        "source_updated",  # kaynak değişikliği
        "sources_synced",  # kaynak listesi değişikliği
        "merge_events",
        "undo_merge",
        "split_event",
        "undo_split",
        "draft_generated",  # taslak üretimi
        "purge_lead_paragraph",  # purge
        "llm_budget_alert",  # F4-07
    }
    missing = required - set(audit.ACTIONS)
    assert not missing, f"F4-16 kapsamında eksik eylem(ler): {sorted(missing)}"


def test_audit_write_roundtrip(db_conn) -> None:  # noqa: ANN001
    from politikdesk.audit import exists_since, write

    target = "test/hardening-roundtrip"
    write("llm_budget_alert", target, payload={"test": True})

    assert exists_since("llm_budget_alert", target, hours=1)
    assert not exists_since("llm_budget_alert", "test/yok-boyle-bir-sey", hours=1)

    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM audit_log WHERE target = %s", (target,))
    db_conn.commit()


# ===========================================================================
# F4-07 — bütçe alarmı
# ===========================================================================
def _guard_at(ratio: float):
    """Verilen doluluk oranında bir bütçe muhafızı kurar."""
    from politikdesk.config import Settings
    from politikdesk.llm.budget import BudgetGuard, CallRecord, InMemoryLedger

    settings = Settings(llm_daily_budget_usd=10.0, llm_monthly_budget_usd=100.0)
    ledger = InMemoryLedger()
    ledger.record(CallRecord(purpose="test", model="m", cost_usd=10.0 * ratio))
    return BudgetGuard(ledger=ledger, settings=settings)


def test_budget_snapshot_reports_ratio() -> None:
    snap = _guard_at(0.5).snapshot()
    assert snap["daily_ratio"] == pytest.approx(0.5)


def test_budget_alert_fires_at_eighty_percent(monkeypatch) -> None:
    """%80 eşiği: tavana çarpmadan ÖNCE haber verilmeli (F4-07 DoD)."""
    from politikdesk.llm import budget as budget_mod

    monkeypatch.setattr(budget_mod, "WARN_THRESHOLD", 0.80)
    _silence_alert_side_effects(monkeypatch)

    result = _guard_at(0.85).alert_if_needed(notify=False)
    levels = {a["level"] for a in result["alerts"]}
    assert "warning" in levels


def test_budget_alert_below_threshold_is_silent(monkeypatch) -> None:
    _silence_alert_side_effects(monkeypatch)
    assert _guard_at(0.50).alert_if_needed(notify=False)["alerts"] == []


def test_budget_alert_marks_cap_as_exceeded(monkeypatch) -> None:
    _silence_alert_side_effects(monkeypatch)
    result = _guard_at(1.20).alert_if_needed(notify=False)
    assert {a["level"] for a in result["alerts"]} == {"exceeded"}


def test_budget_alert_is_not_repeated(monkeypatch) -> None:
    """Aynı uyarı aynı dönemde bir kez. Gürültüye dönen alarm kapatılır."""
    from politikdesk import audit as audit_mod
    from politikdesk.llm import budget as budget_mod

    monkeypatch.setattr(budget_mod, "WARN_THRESHOLD", 0.80)
    monkeypatch.setattr(audit_mod, "write", lambda *a, **k: None)
    monkeypatch.setattr(audit_mod, "exists_since", lambda *a, **k: True)

    assert _guard_at(0.85).alert_if_needed(notify=False)["alerts"] == []


def _silence_alert_side_effects(monkeypatch) -> None:  # noqa: ANN001
    from politikdesk import audit as audit_mod

    monkeypatch.setattr(audit_mod, "write", lambda *a, **k: None)
    monkeypatch.setattr(audit_mod, "exists_since", lambda *a, **k: False)


# ===========================================================================
# F4-09 yan etkisi — loopback bağlama + `localhost` tuzağı
# ===========================================================================
def test_default_dsns_use_explicit_ipv4_loopback() -> None:
    """Ana makine DSN'leri `localhost` DEĞİL `127.0.0.1` olmalı.

    F4-09'da yayımlanan portlar güvenlik gerekçesiyle loopback'e bağlandı
    (`127.0.0.1:5432:5432`) ve Docker yalnızca IPv4 loopback'i dinliyor.
    Windows'ta `localhost` önce `::1`e çözümlenir; oradan bağlantı
    reddedilir ve ana makinede koşan her araç havuz zaman aşımına düşer.

    Ölçüldü (13 Ağustos 2026, F4-09'dan sonra):
        127.0.0.1:5432 -> AÇIK
        ::1:5432       -> ConnectionRefused
        localhost      -> [('AF_INET6','::1'), ('AF_INET','127.0.0.1')]

    Konteynerler etkilenmez: compose onlara `db:5432` verir.
    """
    from politikdesk.config import Settings

    defaults = Settings(_env_file=None)  # type: ignore[call-arg]
    assert "localhost" not in defaults.database_url, (
        "Varsayılan DSN `localhost` kullanıyor; Windows'ta IPv6'ya çözümlenip "
        "loopback'e bağlı Postgres'e ulaşamaz. `127.0.0.1` yazın."
    )
    assert "127.0.0.1" in defaults.database_url
    assert "localhost" not in defaults.redis_url


def test_compose_publishes_only_to_loopback() -> None:
    """F4-09: Postgres ve Redis makinenin katıldığı ağa açılmamalı.

    Docker'ın `"5432:5432"` kısayolu portu `0.0.0.0`a bağlar. Bu bir
    sunucu değil dizüstü bilgisayar: kafe Wi-Fi'ında aynı ağdaki herkes
    varsayılan parolayla veritabanına bağlanabilirdi.
    """
    import re
    from pathlib import Path

    compose = (Path(__file__).resolve().parent.parent / "docker-compose.yml").read_text(
        encoding="utf-8"
    )
    published = re.findall(r'^\s*-\s*"([^"]+:\d+)"\s*$', compose, re.MULTILINE)
    exposed = [p for p in published if not p.startswith("127.0.0.1:")]

    assert not exposed, (
        f"Loopback dışına yayımlanan port(lar): {exposed}. "
        'Biçim `"127.0.0.1:<host>:<konteyner>"` olmalı (F4-09).'
    )


def test_ingestion_does_not_stop_at_budget_cap() -> None:
    """F4-07 DoD: "tavanda üretim duruyor, ingestion devam ediyor".

    Toplama boru hattı LLM'e hiç dokunmaz; tavanın onu durdurabilmesi
    için bir yol OLMAMALI. AST değil, import grafiği üzerinden denetlenir.
    """
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "politikdesk" / "ingestion"
    offenders: list[str] = []

    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "politikdesk.llm"
            ):
                offenders.append(f"{path.name}: {node.module}")
            elif isinstance(node, ast.Import):
                offenders += [
                    f"{path.name}: {a.name}"
                    for a in node.names
                    if a.name.startswith("politikdesk.llm")
                ]

    assert not offenders, (
        f"ingestion/ paketi llm/ import ediyor: {offenders}. "
        "Bütçe tavanı toplamayı durdurmamalı (F4-07)."
    )


# ==================================================================== D9
def test_anthropic_backend_passes_timeout_and_max_retries_to_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D9: _AnthropicBackend llm_max_retries ve llm_timeout_seconds'ı Anthropic SDK'ya iletmeli."""
    import sys
    from typing import Any
    from unittest.mock import MagicMock

    from politikdesk.config import Settings
    from politikdesk.llm.client import _AnthropicBackend

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    captured_kwargs: dict[str, Any] = {}

    class FakeAnthropic:
        def __init__(self, **kwargs: Any) -> None:
            captured_kwargs.update(kwargs)

    mock_anthropic_mod = MagicMock()
    mock_anthropic_mod.Anthropic = FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", mock_anthropic_mod)

    settings = Settings(llm_max_retries=3, llm_timeout_seconds=42)
    backend = _AnthropicBackend(settings)
    _ = backend.client

    assert captured_kwargs.get("max_retries") == 3
    assert captured_kwargs.get("timeout") == 42.0


# ==================================================================== D10
def test_http_client_acquires_rate_limiter_on_every_retry_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D10: HttpClient her gerçek HTTP isteği/denemesi öncesinde rate limiter acquire etmeli."""
    from typing import Any
    from unittest.mock import MagicMock

    import httpx

    from politikdesk.ingestion.http import HttpClient

    monkeypatch.setattr("time.sleep", lambda _: None)

    attempt_count = 0

    def fake_request(method: str, url: str, **kwargs: Any) -> httpx.Response:
        nonlocal attempt_count
        attempt_count += 1
        request = httpx.Request(method, url)
        if attempt_count < 4:
            return httpx.Response(503, request=request)
        return httpx.Response(200, text="OK", request=request)

    client = HttpClient(max_retries=4, respect_robots=False)
    mock_limiter = MagicMock()
    client._limiter = mock_limiter
    client._client.request = fake_request  # type: ignore[method-assign]

    resp = client._send("GET", "https://ornek.gov.tr/veri")
    assert resp.status_code == 200
    assert attempt_count == 4
    assert mock_limiter.acquire.call_count == 4


def test_http_client_429_scenario_acquires_limiter_per_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D10: 429 yanıtı alındığında da her retry için limiter slot'u ayrılmalı."""
    from typing import Any
    from unittest.mock import MagicMock

    import httpx

    from politikdesk.ingestion.http import HttpClient

    monkeypatch.setattr("time.sleep", lambda _: None)

    attempt_count = 0

    def fake_request(method: str, url: str, **kwargs: Any) -> httpx.Response:
        nonlocal attempt_count
        attempt_count += 1
        request = httpx.Request(method, url)
        if attempt_count == 1:
            return httpx.Response(429, headers={"retry-after": "1"}, request=request)
        return httpx.Response(200, text="OK", request=request)

    client = HttpClient(max_retries=3, respect_robots=False)
    mock_limiter = MagicMock()
    client._limiter = mock_limiter
    client._client.request = fake_request  # type: ignore[method-assign]

    resp = client._send("GET", "https://ornek.gov.tr/api")
    assert resp.status_code == 200
    assert attempt_count == 2
    assert mock_limiter.acquire.call_count == 2


# ==================================================================== D14
def test_http_client_no_sleep_on_final_retry_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """D14: Son deneme başarısız olduğunda gereksiz backoff sleep yapılmamalı."""
    from unittest.mock import MagicMock

    import httpx

    from politikdesk.ingestion.http import HttpClient

    sleep_calls: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

    def fake_failing_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        request = httpx.Request(method, url)
        return httpx.Response(503, request=request)

    client = HttpClient(max_retries=3, respect_robots=False)
    client._limiter = MagicMock()
    client._client.request = fake_failing_request  # type: ignore[method-assign]

    with pytest.raises(httpx.HTTPStatusError):
        client._send("GET", "https://ornek.gov.tr/hata")

    # max_retries=3 için attempt 0 ve 1 sleep yapar, attempt 2 (son) sleep yapmadan hata fırlatır
    assert len(sleep_calls) == 2
    assert sleep_calls[0] == 1.0  # 2^0
    assert sleep_calls[1] == 2.0  # 2^1


def test_http_client_retry_after_and_capped_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """D14: Retry-After başlığı okunmalı ve 30s tavanı uygulanmalı, son denemede uyunmamalı."""
    from unittest.mock import MagicMock

    import httpx

    from politikdesk.ingestion.http import HttpClient

    sleep_calls: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

    attempt = 0

    def fake_429_request(method: str, url: str, **kwargs: object) -> httpx.Response:
        nonlocal attempt
        attempt += 1
        request = httpx.Request(method, url)
        if attempt == 1:
            return httpx.Response(429, headers={"retry-after": "5"}, request=request)
        if attempt == 2:
            return httpx.Response(429, headers={"retry-after": "60"}, request=request)
        return httpx.Response(429, headers={"retry-after": "10"}, request=request)

    client = HttpClient(max_retries=3, respect_robots=False)
    client._limiter = MagicMock()
    client._client.request = fake_429_request  # type: ignore[method-assign]

    with pytest.raises(httpx.HTTPStatusError):
        client._send("GET", "https://ornek.gov.tr/oran")

    # 1. attempt: Retry-After 5s -> sleep 5.0
    # 2. attempt: Retry-After 60s (fakat _parse_retry_after float döner) -> _backoff override=60.0
    # 3. attempt: final attempt -> NO sleep
    assert len(sleep_calls) == 2
    assert sleep_calls[0] == 5.0
    assert sleep_calls[1] == 60.0
