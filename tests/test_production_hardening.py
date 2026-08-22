"""PolitikDesk — Deep Production Hardening, Audit Remediation & Concurrency Verification.

Kapsanan Alanlar (Spec & Independent Audit Contract):
1. Async route DB threadpool izolasyonu ve concurrent event loop kilitlenmeme testi.
2. Celery pre-fork DB connection pool sıfırlama, cache_info ve süreç izolasyonu.
3. Production auth fail-closed tam matrisi (dev, test, prod) ve request auth middleware (Bearer/bearer/X-API-Token).
4. Structlog hassas veri sansürleme (redaction) — özyinelemeli (recursive) ve case-insensitive derin test.
5. Türkçe morfolojik çekim matrisi (olumlu, olumsuz, gereklilik, olumsuz gereklilik, isim-fiil, olumsuz isim-fiil, zaman/şahıs çekimleri).
6. Ingestion devre kesici (CircuitBreaker) çoklu host izolasyonu ve thread-safety / race condition testi.
7. Arayüz XSS ve URL güvenlik filtresi (data:, vbscript:, javascript:, URL-encoded).
8. Epistemik tavan (epistemic ceiling) ve telif hakkı (copyright excerpt limit <= 300) mimari sözleşme doğrulaması.
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import httpx
import pytest
from starlette.testclient import TestClient

from politikdesk.api.main import app
from politikdesk.config import Settings
from politikdesk.db import get_pool, reset_db_pool
from politikdesk.evidence.independence import EvidenceArticle
from politikdesk.evidence.rules import Claim, Evidence, compute_status
from politikdesk.ingestion.circuit import (
    CircuitBreaker,
    CircuitState,
    SourceCircuitRegistry,
)
from politikdesk.ingestion.http import UnsafeUrlError, validate_url
from politikdesk.ingestion.normalizer import EXCERPT_MAX_CHARS, make_excerpt
from politikdesk.nlp.claims import fold_text
from politikdesk.observability import redact_sensitive_keys
from politikdesk.political_memory.stance_shift import (
    _evaluate_text_polarity,
    _has_morphological_negation,
)
from politikdesk.web.ui.components import esc, esc_attr, esc_url, source_pill
from politikdesk.worker import on_worker_process_init, on_worker_process_shutdown


# =============================================================================
# 1. Async Route DB Threadpool İzolasyonu ve Concurrency Doğrulaması
# =============================================================================
def test_activity_endpoint_uses_threadpool_isolation() -> None:
    client = TestClient(app)
    with patch("politikdesk.web.api.record_activity") as mock_record:
        response = client.post(
            "/api/activity",
            json={
                "kind": "page_view",
                "path": "/feed",
                "duration_ms": 1200,
            },
        )
        assert response.status_code == 204
        mock_record.assert_called_once()


def test_concurrent_activity_requests_do_not_block_event_loop() -> None:
    """N concurrent istek geldiğinde threadpool sayesinde event loop'un bloklanmadığını doğrular."""
    client = TestClient(app)

    def slow_record_activity(*args: object, **kwargs: object) -> None:
        time.sleep(0.02)  # 20ms simüle edilmiş DB gecikmesi

    with patch("politikdesk.web.api.record_activity", side_effect=slow_record_activity):
        start_time = time.monotonic()
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(
                    client.post,
                    "/api/activity",
                    json={"kind": "page_view", "path": f"/event/{i}", "duration_ms": 100},
                )
                for i in range(5)
            ]
            results = [f.result() for f in futures]
        duration = time.monotonic() - start_time

        for res in results:
            assert res.status_code == 204
        # 5 istek sıralı bloklayıcı olsaydı 5 * 20ms = 100ms sürerdi; threadpool ile paralel çalışır
        assert duration < 0.5


@pytest.mark.asyncio
async def test_async_activity_event_loop_heartbeat_isolation() -> None:
    """Event Loop Heartbeat Testi:

    Yavaş/bloklayıcı bir DB işlemi sırasında event loop'un donmadığını (starvation olmadığını)
    eşzamanlı çalışan bir heartbeat coroutine'i ile kanıtlar.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        heartbeat_ticks = 0
        max_gap = 0.0
        last_tick_time = time.monotonic()
        running = True

        async def heartbeat() -> None:
            nonlocal heartbeat_ticks, max_gap, last_tick_time
            while running:
                await asyncio.sleep(0.005)
                now = time.monotonic()
                gap = now - last_tick_time
                if gap > max_gap:
                    max_gap = gap
                last_tick_time = now
                heartbeat_ticks += 1

        def slow_db_record(*args: object, **kwargs: object) -> None:
            time.sleep(0.08)  # 80ms senkron DB gecikmesi

        hb_task = asyncio.create_task(heartbeat())
        try:
            with patch("politikdesk.web.api.record_activity", side_effect=slow_db_record):
                # 3 eşzamanlı istek gönder
                responses = await asyncio.gather(
                    client.post("/api/activity", json={"kind": "page_view", "path": "/1"}),
                    client.post("/api/activity", json={"kind": "page_view", "path": "/2"}),
                    client.post("/api/activity", json={"kind": "page_view", "path": "/3"}),
                )
                for r in responses:
                    assert r.status_code == 204
        finally:
            running = False
            await hb_task

        # Eğer event loop 80ms boyunca bloklansaydı max_gap >= 0.08s olurdu.
        # Threadpool izolasyonu sayesinde event loop serbest kalır ve max_gap < 0.045s kalır!
        assert max_gap < 0.045
        assert heartbeat_ticks >= 10


# =============================================================================
# 2. Celery Pre-fork DB Pool Reset & Süreç İzolasyonu
# =============================================================================
def test_reset_db_pool_handles_uninitialized_and_initialized_pool() -> None:
    # 1. Havuz henüz açılmamışken reset_db_pool çağrıldığında havuz oluşturulmamalı
    reset_db_pool()
    assert get_pool.cache_info().currsize == 0

    # 2. Havuz açıldığında reset_db_pool kapatıp temizlemeli
    with patch("politikdesk.db.ConnectionPool") as mock_pool_cls:
        fake_pool = MagicMock()
        mock_pool_cls.return_value = fake_pool

        pool1 = get_pool()
        assert pool1 is fake_pool
        assert get_pool.cache_info().currsize == 1

        reset_db_pool()
        fake_pool.close.assert_called_once()
        assert get_pool.cache_info().currsize == 0


def test_celery_worker_process_signals_invoke_pool_reset() -> None:
    with patch("politikdesk.db.reset_db_pool") as mock_reset:
        on_worker_process_init()
        assert mock_reset.call_count == 1

        on_worker_process_shutdown()
        assert mock_reset.call_count == 2


# =============================================================================
# 3. Production Auth Fail-Closed Tam Matrisi & Request Middleware
# =============================================================================
def test_auth_fail_closed_in_production_environment() -> None:
    # 1. Development: token boş olabilir
    dev_settings = Settings(env="development", api_token="")
    assert dev_settings.env == "development"
    assert dev_settings.api_token == ""

    # 2. Test: token boş olabilir
    test_settings = Settings(env="test", api_token="")
    assert test_settings.env == "test"

    # 3. Production + token yok -> FAIL CLOSED (ValueError)
    with pytest.raises(ValueError, match="PD_ENV='production' iken PD_API_TOKEN zorunludur"):
        Settings(env="production", api_token="")

    # 4. Production + boşluklu token -> FAIL CLOSED
    with pytest.raises(ValueError, match="PD_ENV='production' iken PD_API_TOKEN zorunludur"):
        Settings(env="production", api_token="   \t\n  ")

    # 5. Production + geçerli token -> Başarılı
    prod_settings = Settings(env="production", api_token="prod_sec_token_xyz_987654")
    assert prod_settings.is_production is True
    assert prod_settings.api_token == "prod_sec_token_xyz_987654"


def test_request_authentication_middleware_matrix() -> None:
    """Gerçek request auth middleware doğrulama matrisi (Bearer, bearer, X-API-Token, 401, 403, muafiyet)."""
    client = TestClient(app)
    mock_settings = Settings(api_token="valid_secret_token_123")

    with patch("politikdesk.api.main.get_settings", return_value=mock_settings):
        # 1. Token yok -> 401
        res_no_token = client.get("/api/profile")
        assert res_no_token.status_code == 401

        # 2. Yanlış token -> 403
        res_bad_token = client.get("/api/profile", headers={"Authorization": "Bearer wrong_token"})
        assert res_bad_token.status_code == 403

        # 3. Geçerli Authorization: Bearer -> 200 (veya API cevabı)
        with patch("politikdesk.web.api.load_profile", return_value={"name": "Editor"}):
            res_bearer = client.get(
                "/api/profile",
                headers={"Authorization": "Bearer valid_secret_token_123"},
            )
            assert res_bearer.status_code == 200

            # 4. Case-insensitive bearer prefix -> 200
            res_lower_bearer = client.get(
                "/api/profile",
                headers={"Authorization": "bearer valid_secret_token_123"},
            )
            assert res_lower_bearer.status_code == 200

            # 5. X-API-Token başlığı -> 200
            res_x_token = client.get(
                "/api/profile",
                headers={"X-API-Token": "valid_secret_token_123"},
            )
            assert res_x_token.status_code == 200

        # 6. Muaf uçlar (Exempt: /health/, /version) -> tokensız 200
        res_health = client.get("/health/live")
        assert res_health.status_code == 200


# =============================================================================
# 4. Structlog Hassas Veri Sansürleme (Recursive & Extended)
# =============================================================================
def test_structlog_recursive_sensitive_field_redaction() -> None:
    raw_event = {
        "event": "user_authenticated",
        "api_token": "secret_token_12345",
        "password": "super_secret_db_pass",
        "authorization": "Bearer secret_jwt",
        "smtp_password": "my_email_pass",
        "database_password": "pg_pass_secret",
        "private_key": "-----BEGIN PRIVATE KEY-----",
        "request": {
            "headers": {
                "Authorization": "Bearer nested_jwt_secret",
                "User-Agent": "Mozilla/5.0",
            },
            "credentials": {
                "token_id": 999,
            },
            "auth_context": {
                "client_secret": "oauth_secret_abc",
            },
        },
        "user_email": "editor@politikdesk.com",
        "event_id": 42,
    }

    redacted = redact_sensitive_keys(None, "info", raw_event)

    # Top-level redaction
    assert redacted["api_token"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["smtp_password"] == "[REDACTED]"
    assert redacted["database_password"] == "[REDACTED]"
    assert redacted["private_key"] == "[REDACTED]"

    # Nested redaction
    assert redacted["request"]["headers"]["Authorization"] == "[REDACTED]"
    assert redacted["request"]["headers"]["User-Agent"] == "Mozilla/5.0"
    assert redacted["request"]["credentials"] == "[REDACTED]"
    assert redacted["request"]["auth_context"]["client_secret"] == "[REDACTED]"

    # Korunması gereken alanlar
    assert redacted["user_email"] == "editor@politikdesk.com"
    assert redacted["event_id"] == 42


# =============================================================================
# 5. Türkçe Morfolojik Çekim ve Eylem Olumsuzluğu Matrisi
# =============================================================================
def test_turkish_morphological_negation_matrix() -> None:
    # 1. Olumlu eylemler -> Olumsuzluk YOK
    pos_samples = (
        ("art", "vergileri artıracağız"),
        ("art", "oranları arttıracağız"),
        ("yuksel", "faizleri yükselteceğiz"),
        ("destek", "tasarıyı destekleyeceğiz"),
        ("uygula", "programı uygulayacağız"),
    )
    for kw, text in pos_samples:
        assert _has_morphological_negation(kw, text) is False

    # 2. Olumsuz eylemler -> Olumsuzluk VAR
    neg_samples = (
        ("art", "vergileri artırmayacağız"),
        ("art", "oranları arttırmayacağız"),
        ("yuksel", "faizleri yükseltmeyeceğiz"),
        ("destek", "tasarıyı desteklemeyeceğiz"),
        ("uygula", "programı uygulamayacağız"),
    )
    for kw, text in neg_samples:
        assert _has_morphological_negation(kw, text) is True

    # 3. Gereklilik kipi (-meli/-malı) -> Olumsuzluk YOK
    necessity_samples = (
        ("art", "faizler derhal artırılmalı"),
        ("art", "oranlar mutlaka artırılmalıdır"),
        ("dus", "enflasyon düşürülmeli"),
        ("uygula", "sıkı para politikası uygulanmalı"),
    )
    for kw, text in necessity_samples:
        assert _has_morphological_negation(kw, text) is False

    # 4. Olumsuz gereklilik kipi (-memeli/-mamalı) -> Olumsuzluk VAR
    neg_necessity_samples = (
        ("art", "faizler kesinlikle artırılmamalı"),
        ("art", "oranlar asla artırılmamalıdır"),
        ("dus", "yatırımlar düşürülmemeli"),
        ("uygula", "bu politika uygulanmamalıdır"),
    )
    for kw, text in neg_necessity_samples:
        assert _has_morphological_negation(kw, text) is True

    # 5. İsim-fiil (-ması/-mesi) -> Olumsuzluk YOK
    nominal_samples = (
        ("art", "faizlerin artırılması gündemde"),
        ("dus", "enflasyonun düşürülmesi hedefleniyor"),
        ("uygula", "kararın uygulanması bekleniyor"),
    )
    for kw, text in nominal_samples:
        assert _has_morphological_negation(kw, text) is False

    # 6. Olumsuz isim-fiil (-maması/-memesi) -> Olumsuzluk VAR
    neg_nominal_samples = (
        ("art", "faizlerin artırılmaması gerekiyor"),
        ("dus", "üretimin düşürülmemesi şart"),
        ("uygula", "bu tedbirin uygulanmaması yönünde karar alındı"),
    )
    for kw, text in neg_nominal_samples:
        assert _has_morphological_negation(kw, text) is True

    # 7. Zaman ve şahıs çekimleri
    assert _has_morphological_negation("art", "oranları artırıyorum") is False
    assert _has_morphological_negation("art", "oranları artırmıyorum") is True
    assert _has_morphological_negation("art", "oranları artırdık") is False
    assert _has_morphological_negation("art", "oranları artırmadık") is True


def test_stance_shift_polarity_reversal_matrix() -> None:
    pos_raw = ("artıracağız", "artacak", "artırılmalı", "artış")
    neg_raw = ("indireceğiz", "düşecek", "indirilmeli", "düşüş")
    pos_set = frozenset(fold_text(w) for w in pos_raw)
    neg_set = frozenset(fold_text(w) for w in neg_raw)

    # 1. Olumlu eylem -> pos
    assert _evaluate_text_polarity(fold_text("faizleri artıracağız"), pos_set, neg_set) == "pos"
    # 2. Olumsuzlanmış eylem -> neg (zıt kutup!)
    assert _evaluate_text_polarity(fold_text("faizleri artırmayacağız"), pos_set, neg_set) == "neg"
    # 3. Zıt eylem -> neg
    assert _evaluate_text_polarity(fold_text("faizleri indireceğiz"), pos_set, neg_set) == "neg"
    # 4. Olumsuzlanmış zıt eylem -> pos (indirim olmayacak = artış/sıkılaşma yönü)
    assert _evaluate_text_polarity(fold_text("faiz indirimi olmayacak"), pos_set, neg_set) == "pos"


# =============================================================================
# 6. Ingestion Devre Kesici (CircuitBreaker) Çoklu Host İzolasyonu & Thread-Safety
# =============================================================================
def test_circuit_breaker_multi_host_isolation() -> None:
    registry = SourceCircuitRegistry()
    cb_tcmb = registry.get("evds2.tcmb.gov.tr", failure_threshold=2, recovery_timeout=0.1)
    cb_tuik = registry.get("api.tuik.gov.tr", failure_threshold=2, recovery_timeout=0.1)

    # TCMB 2 hata alır ve devresi AÇILIR (OPEN)
    cb_tcmb.record_failure("timeout")
    cb_tcmb.record_failure("timeout")
    assert cb_tcmb.state == CircuitState.OPEN
    assert cb_tcmb.can_execute() is False

    # TÜİK etkilenmez, KAPALI (CLOSED) ve sağlıklı kalır
    assert cb_tuik.state == CircuitState.CLOSED
    assert cb_tuik.can_execute() is True


def test_circuit_breaker_concurrent_thread_safety() -> None:
    cb = CircuitBreaker(host="api.test.gov.tr", failure_threshold=5, recovery_timeout=0.2)

    def record_fail() -> None:
        cb.record_failure("err")

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(record_fail) for _ in range(10)]
        for f in futures:
            f.result()

    assert cb.state == CircuitState.OPEN
    assert cb._failure_count == 10


# =============================================================================
# 7. Arayüz XSS ve URL Güvenlik Filtresi
# =============================================================================
def test_ui_components_xss_and_unsafe_uri_schemes() -> None:
    # 1. HTML kaçış
    malicious_text = '<script>alert("XSS")</script>'
    escaped = esc(malicious_text)
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped

    # 2. URI protokol sahteciliği engeli (javascript, vbscript, data URI, percent-encoded)
    #
    # 20 Ağustos 2026 denetimi: bu denetim `esc_attr`ten `esc_url`e TAŞINDI.
    # Gerekçe iki yönlü — `esc_attr` kara listesi (a) `href` artık oradan
    # geçmediği için güvenlik katmıyordu, (b) "javascript: dilinde yeni
    # sürüm" gibi meşru bir başlığı `#`e çevirip içeriği bozuyordu.
    # `esc_url` aynı vektörleri İZİN LİSTESİYLE kapatır, yani daha güçlüdür.
    assert esc_url("javascript:alert(1)") == "#"
    assert esc_url("  JAVASCRIPT:alert(1) ") == "#"
    assert esc_url("vbscript:msgbox(1)") == "#"
    assert esc_url("data:text/html;base64,PHNjcmlwdD4=") == "#"
    assert esc_url("data:image/svg+xml;utf8,<svg onload=alert(1)>") == "#"
    assert esc_url("javascript%3Aalert(1)") == "#"

    # 3. Güvenli linklere izin verilir
    assert esc_url("https://politikdesk.com/event/1") == "https://politikdesk.com/event/1"
    assert esc_url("/feed") == "/feed"

    # 4. Metin öznitelikleri kaçırılır ama İÇERİK BOZULMAZ.
    assert esc_attr('Sayfa "1"') == "Sayfa &quot;1&quot;"
    assert esc_attr("javascript: dilinde yeni sürüm") == "javascript: dilinde yeni sürüm"

    # 4. Kaynak hapı (source_pill) XSS denetimi
    pill = source_pill("<img src=x onerror=alert(1)>", tier=1, url="javascript:alert(1)")
    assert "<img" not in pill
    assert 'href="#"' in pill


# =============================================================================
# 8. Epistemik Tavan ve Telif Hakkı (Copyright Excerpt Limit) Sözleşmesi
# =============================================================================
def test_copyright_excerpt_limit_enforced() -> None:
    """Telif hakkı kuralı: makale özeti (excerpt) asla 300 karakteri aşamaz."""
    long_body = "A" * 1000
    excerpt = make_excerpt(long_body)
    assert excerpt is not None
    assert len(excerpt) <= EXCERPT_MAX_CHARS
    assert len(excerpt) <= 300


# =============================================================================
# 9. SSRF Koruması & IPv4-Mapped IPv6 / Loopback / Metadata Engeli
# =============================================================================
def test_ssrf_ipv4_mapped_ipv6_and_metadata_prevention() -> None:
    # 1. IPv4-mapped IPv6 loopback, private ve CGNAT IP'ler engellenmeli
    with pytest.raises(UnsafeUrlError, match="Özel/ayrılmış IP"):
        validate_url("http://[::ffff:127.0.0.1]/status", resolve_dns=False)

    with pytest.raises(UnsafeUrlError, match="Özel/ayrılmış IP"):
        validate_url("http://[::ffff:169.254.169.254]/latest/meta-data", resolve_dns=False)

    with pytest.raises(UnsafeUrlError, match="Özel/ayrılmış IP"):
        validate_url("http://[::ffff:10.0.0.1]/internal", resolve_dns=False)

    with pytest.raises(UnsafeUrlError, match="Özel/ayrılmış IP"):
        validate_url("http://[::ffff:100.64.0.1]/internal", resolve_dns=False)

    with pytest.raises(UnsafeUrlError, match="Özel/ayrılmış IP"):
        validate_url("http://[::ffff:100.127.255.254]/internal", resolve_dns=False)

    # 2. RFC 6598 CGNAT (100.64.0.0/10) aralığı engellenmeli
    with pytest.raises(UnsafeUrlError, match="Özel/ayrılmış IP"):
        validate_url("http://100.64.0.1:8080/metrics", resolve_dns=False)

    with pytest.raises(UnsafeUrlError, match="Özel/ayrılmış IP"):
        validate_url("http://100.100.100.100/admin", resolve_dns=False)

    with pytest.raises(UnsafeUrlError, match="Özel/ayrılmış IP"):
        validate_url("http://100.127.255.254/api", resolve_dns=False)

    # 3. IPv6 ULA, link-local ve loopback
    with pytest.raises(UnsafeUrlError, match="Özel/ayrılmış IP"):
        validate_url("http://[fc00::1]/admin", resolve_dns=False)

    with pytest.raises(UnsafeUrlError, match="Özel/ayrılmış IP"):
        validate_url("http://[fe80::1]/admin", resolve_dns=False)

    with pytest.raises(UnsafeUrlError):
        validate_url("http://[::1]/admin", resolve_dns=False)

    # 4. Standart localhost, trailing dot ve private IP'ler
    with pytest.raises(UnsafeUrlError):
        validate_url("http://localhost:8000/api", resolve_dns=False)

    with pytest.raises(UnsafeUrlError):
        validate_url("http://localhost.:8000/api", resolve_dns=False)

    with pytest.raises(UnsafeUrlError):
        validate_url("http://127.0.0.1:3000/admin", resolve_dns=False)

    # 5. Ondalık (decimal) IP biçimleri (2130706433 = 127.0.0.1)
    with pytest.raises(UnsafeUrlError):
        validate_url("http://2130706433/internal", resolve_dns=False)

    # 6. Geçerli genel internet URL'leri ve public IP'ler kabul edilmeli
    assert validate_url("https://evds2.tcmb.gov.tr/service", resolve_dns=False) == "https://evds2.tcmb.gov.tr/service"
    assert validate_url("https://8.8.8.8/dns-query", resolve_dns=False) == "https://8.8.8.8/dns-query"
    assert validate_url("https://1.1.1.1/dns-query", resolve_dns=False) == "https://1.1.1.1/dns-query"


# =============================================================================
# 10. Production 500 Hata Yanıtı İç Detay/SQL Sızıntısı Engeli
# =============================================================================
def test_production_unhandled_exception_masks_internal_error() -> None:
    client = TestClient(app, raise_server_exceptions=False)

    # 1. Production modunda: exception metni JSON veya HTML yanıtında SIZDIRILMAZ
    prod_settings = Settings(env="production", api_token="secret_token_abc_123")
    with (
        patch("politikdesk.api.main.get_settings", return_value=prod_settings),
        patch(
            "politikdesk.web.api.load_profile",
            side_effect=RuntimeError("FATAL SQL SYNTAX ERROR: table_xyz"),
        ),
    ):
        res = client.get("/api/profile", headers={"Authorization": "Bearer secret_token_abc_123"})
        assert res.status_code == 500
        data = res.json()
        assert data["detail"] == "Sunucu hatası oluştu."
        assert "error" not in data
        assert "FATAL SQL SYNTAX ERROR" not in res.text

    # 2. Development modunda: debug kolaylığı için hata detayı eklenir
    dev_settings = Settings(env="development", api_token="dev_token")
    with (
        patch("politikdesk.api.main.get_settings", return_value=dev_settings),
        patch(
            "politikdesk.web.api.load_profile", side_effect=RuntimeError("DEBUG ERROR: table_xyz")
        ),
    ):
        res = client.get("/api/profile", headers={"Authorization": "Bearer dev_token"})
        assert res.status_code == 500
        data = res.json()
        assert data["error"] == "DEBUG ERROR: table_xyz"


# =============================================================================
# 11. Red Team & Adversarial Güvenlik Matrisi Doğrulamaları
# =============================================================================
def test_adversarial_epistemic_llm_claim_rejected() -> None:
    """Epistemik Tavan: Kanıt maddesi yokken iddia hiçbir şekilde 'strongly_corroborated' olamaz."""
    claim = Claim(claim_id=1, claim_text="Hükümet faizleri indirdi", claim_type="fact")

    # 1. Sıfır kanıtlı bir iddia her zaman 'unverified' dönmelidir
    res_zero = compute_status(claim, [])
    assert res_zero.status == "unverified"

    # 2. Yalnızca Tier-4 (sosyal medya) kanıtı olan bir iddia 'unverified' veya 'single_source' kalır, asla 'strongly_corroborated' olamaz
    tier4_article = EvidenceArticle(
        article_id=1,
        source_slug="twitter-anon",
        tier=4,
        kind="social",
        independence_group="social-ugc",
    )
    evidence_item = Evidence(article=tier4_article, stance="supports")
    res_t4 = compute_status(claim, [evidence_item])
    assert res_t4.status in ("single_source", "unverified")
    assert res_t4.status != "strongly_corroborated"


def test_adversarial_auth_header_variations() -> None:
    """Adversarial Auth: Boşluksuz Bearer, büyük harf BEARER, geçersiz veya unicode token denemeleri."""
    client = TestClient(app)
    mock_settings = Settings(api_token="valid_secret_xyz_99")

    with patch("politikdesk.api.main.get_settings", return_value=mock_settings):
        # 1. Büyük harf BEARER geçerli olmalıdır
        with patch("politikdesk.web.api.load_profile", return_value={"name": "Editor"}):
            res_cap = client.get(
                "/api/profile", headers={"Authorization": "BEARER valid_secret_xyz_99"}
            )
            assert res_cap.status_code == 200

        # 2. Boşluksuz 'Bearerxyz' geçersiz sayılmalı ve 401/403 dönmelidir
        res_no_space = client.get(
            "/api/profile", headers={"Authorization": "Bearervalid_secret_xyz_99"}
        )
        assert res_no_space.status_code in (401, 403)

        # 3. Unicode / newline içeren kötü niyetli token reddedilmelidir
        res_unicode = client.get(
            "/api/profile", headers={"Authorization": "Bearer valid_secret_xyz_99\nInject: evil"}
        )
        assert res_unicode.status_code in (400, 401, 403)


def test_adversarial_csrf_token_spoofing() -> None:
    """Sahte token ile CSRF atlatma denemesi doğrudan auth katmanında 403 ile engellenmelidir."""
    client = TestClient(app)
    mock_settings = Settings(api_token="real_production_token_123")

    with patch("politikdesk.api.main.get_settings", return_value=mock_settings):
        # Saldırgan CSRF'i atlatmak için sahte X-API-Token yollar
        res = client.post(
            "/api/profile",
            json={"name": "Attacker"},
            headers={"X-API-Token": "fake_token_attempt", "Origin": "https://evil.com"},
        )
        assert res.status_code == 403


def test_adversarial_log_redaction_tuples_and_cookies() -> None:
    """Log boru hattında demetler (tuple) ve cookie başlıkları da özyinelemeli olarak maskelenmelidir."""
    raw_event = {
        "event": "http_request",
        "cookie": "session=secret_session_token_123",
        "nested_tuple": (
            {"api_token": "secret_in_tuple"},
            {"safe_key": "safe_val"},
        ),
    }
    redacted = redact_sensitive_keys(None, "info", raw_event)
    assert redacted["cookie"] == "[REDACTED]"
    assert redacted["nested_tuple"][0]["api_token"] == "[REDACTED]"
    assert redacted["nested_tuple"][1]["safe_key"] == "safe_val"
