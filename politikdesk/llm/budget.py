"""LLM maliyet/bütçe sayacı (F0-17).

DoD: çağrı token'ları loglanıyor; günlük tavan aşılınca `BudgetExceeded`.

Tasarım notu: defter (ledger) bir protokoldür. Üretimde `PostgresLedger`
`llm_calls` tablosuna yazar; testlerde `InMemoryLedger` veritabanı
gerektirmez. Bütçe mantığı her iki durumda da aynıdır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from politikdesk.config import Settings, get_settings
from politikdesk.llm.errors import BudgetExceeded
from politikdesk.observability import get_logger

log = get_logger(__name__)

WARN_THRESHOLD = 0.80  # %80'de uyarı (F4-07 ile e-postaya bağlanacak)


@dataclass(frozen=True)
class CallRecord:
    purpose: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int | None = None
    prompt_version: str | None = None
    user_id: int | None = None
    succeeded: bool = True
    error_type: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class Ledger(Protocol):
    """Harcama defteri arayüzü."""

    def record(self, call: CallRecord) -> None: ...

    def spent_today_usd(self) -> float: ...

    def spent_this_month_usd(self) -> float: ...


class InMemoryLedger:
    """Test ve kuru-koşum (dry-run) için bellekte tutulan defter."""

    def __init__(self) -> None:
        self.calls: list[CallRecord] = []

    def record(self, call: CallRecord) -> None:
        self.calls.append(call)

    def _sum(self, since: datetime) -> float:
        return sum(c.cost_usd for c in self.calls if c.created_at >= since)

    def spent_today_usd(self) -> float:
        now = datetime.now(UTC)
        return self._sum(now.replace(hour=0, minute=0, second=0, microsecond=0))

    def spent_this_month_usd(self) -> float:
        now = datetime.now(UTC)
        return self._sum(
            now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        )


class PostgresLedger:
    """`llm_calls` tablosuna yazan üretim defteri."""

    def record(self, call: CallRecord) -> None:
        from politikdesk.db import connection

        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO llm_calls (
                    purpose, model, prompt_version,
                    input_tokens, output_tokens,
                    cache_read_tokens, cache_write_tokens,
                    cost_usd, latency_ms, user_id, succeeded, error_type, created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    call.purpose,
                    call.model,
                    call.prompt_version,
                    call.input_tokens,
                    call.output_tokens,
                    call.cache_read_tokens,
                    call.cache_write_tokens,
                    call.cost_usd,
                    call.latency_ms,
                    call.user_id,
                    call.succeeded,
                    call.error_type,
                    call.created_at,
                ),
            )
            conn.commit()

    def _sum_since(self, sql_interval: str) -> float:
        from politikdesk.db import connection

        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT COALESCE(SUM(cost_usd), 0) AS total FROM llm_calls "  # noqa: S608
                f"WHERE created_at >= date_trunc('{sql_interval}', now())"
            )
            row = cur.fetchone()
            return float(row["total"]) if row else 0.0

    def spent_today_usd(self) -> float:
        return self._sum_since("day")

    def spent_this_month_usd(self) -> float:
        return self._sum_since("month")


class BudgetGuard:
    """Çağrı öncesi tavan kontrolü, çağrı sonrası kayıt."""

    def __init__(self, ledger: Ledger | None = None, settings: Settings | None = None) -> None:
        self.ledger = ledger or PostgresLedger()
        self.settings = settings or get_settings()

    # -- kontrol -------------------------------------------------------------
    def check(self, *, estimated_cost_usd: float = 0.0) -> None:
        """Tavan aşılacaksa `BudgetExceeded` fırlatır.

        Tahmini maliyet dahil edilir; bir çağrının tavanı *aşarak*
        tamamlanması değil, başlamadan durması hedeflenir.
        """
        daily = self.ledger.spent_today_usd()
        if daily + estimated_cost_usd > self.settings.llm_daily_budget_usd:
            raise BudgetExceeded("Günlük", daily + estimated_cost_usd,
                                 self.settings.llm_daily_budget_usd)

        monthly = self.ledger.spent_this_month_usd()
        if monthly + estimated_cost_usd > self.settings.llm_monthly_budget_usd:
            raise BudgetExceeded("Aylık", monthly + estimated_cost_usd,
                                 self.settings.llm_monthly_budget_usd)

        self._maybe_warn(daily, self.settings.llm_daily_budget_usd, "günlük")
        self._maybe_warn(monthly, self.settings.llm_monthly_budget_usd, "aylık")

    def _maybe_warn(self, spent: float, cap: float, period: str) -> None:
        if cap > 0 and spent / cap >= WARN_THRESHOLD:
            log.warning(
                "llm_budget_threshold",
                period=period,
                spent_usd=round(spent, 4),
                cap_usd=cap,
                ratio=round(spent / cap, 3),
            )

    # -- kayıt ---------------------------------------------------------------
    def record(self, call: CallRecord) -> None:
        self.ledger.record(call)
        log.info(
            "llm_call",
            purpose=call.purpose,
            model=call.model,
            prompt_version=call.prompt_version,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            cache_read_tokens=call.cache_read_tokens,
            cost_usd=round(call.cost_usd, 6),
            latency_ms=call.latency_ms,
            succeeded=call.succeeded,
            error_type=call.error_type,
        )

    # -- rapor ---------------------------------------------------------------
    def snapshot(self) -> dict[str, float]:
        return {
            "daily_spent_usd": self.ledger.spent_today_usd(),
            "daily_cap_usd": self.settings.llm_daily_budget_usd,
            "monthly_spent_usd": self.ledger.spent_this_month_usd(),
            "monthly_cap_usd": self.settings.llm_monthly_budget_usd,
        }
