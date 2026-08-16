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
        return self._sum(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))


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

    _VALID_INTERVALS = frozenset({"day", "month"})

    def _sum_since(self, sql_interval: str) -> float:
        if sql_interval not in self._VALID_INTERVALS:
            raise ValueError(
                f"Geçersiz SQL interval: {sql_interval!r}. "
                f"İzin verilenler: {sorted(self._VALID_INTERVALS)}"
            )
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
            raise BudgetExceeded(
                "Günlük", daily + estimated_cost_usd, self.settings.llm_daily_budget_usd
            )

        monthly = self.ledger.spent_this_month_usd()
        if monthly + estimated_cost_usd > self.settings.llm_monthly_budget_usd:
            raise BudgetExceeded(
                "Aylık", monthly + estimated_cost_usd, self.settings.llm_monthly_budget_usd
            )

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
        daily = self.ledger.spent_today_usd()
        monthly = self.ledger.spent_this_month_usd()
        daily_cap = self.settings.llm_daily_budget_usd
        monthly_cap = self.settings.llm_monthly_budget_usd
        return {
            "daily_spent_usd": daily,
            "daily_cap_usd": daily_cap,
            "daily_ratio": daily / daily_cap if daily_cap else 0.0,
            "monthly_spent_usd": monthly,
            "monthly_cap_usd": monthly_cap,
            "monthly_ratio": monthly / monthly_cap if monthly_cap else 0.0,
        }

    # -- alarm (F4-07) --------------------------------------------------------
    def alert_if_needed(self, *, notify: bool = True) -> dict[str, object]:
        """Eşik aşıldıysa bir kez uyarır (F4-07).

        `check()` çağrı ANINDA tavanı zorlar; bu ise çağrı olmasa bile
        eşiği görünür kılar. İkisi ayrı olmalı: ayın 20'sinde aylık
        tavanın %85'inde olduğunu, bir sonraki üretim denemesi
        `BudgetExceeded` ile düştüğünde değil, önceden bilmek gerekir.

        Tekrar bastırma denetim izinden okunur — aynı uyarı aynı dönemde
        (gün/ay) bir kez gönderilir. Gürültüye dönen alarm kapatılır.
        """
        from datetime import UTC, datetime

        from politikdesk import audit

        snap = self.snapshot()
        now = datetime.now(UTC)
        fired: list[dict[str, object]] = []

        periods = (
            ("günlük", "daily", now.strftime("%Y-%m-%d")),
            ("aylık", "monthly", now.strftime("%Y-%m")),
        )

        for label, key, bucket in periods:
            ratio = float(snap[f"{key}_ratio"])
            if ratio >= 1.0:
                level = "exceeded"
            elif ratio >= WARN_THRESHOLD:
                level = "warning"
            else:
                continue

            target = f"budget:{key}:{bucket}:{level}"
            if audit.exists_since("llm_budget_alert", target, hours=25):
                continue

            spent = float(snap[f"{key}_spent_usd"])
            cap = float(snap[f"{key}_cap_usd"])
            detail = {
                "period": key,
                "level": level,
                "ratio": round(ratio, 3),
                "spent_usd": round(spent, 4),
                "cap_usd": cap,
            }
            fired.append(detail)

            log.error(
                "llm_budget_alert",
                period=key,
                level=level,
                spent_usd=round(spent, 4),
                cap_usd=cap,
                ratio=round(ratio, 3),
            )
            audit.write("llm_budget_alert", target, payload=detail)

            if notify:
                self._notify(label, level, spent, cap, ratio)

        return {"snapshot": snap, "alerts": fired}

    @staticmethod
    def _notify(label: str, level: str, spent: float, cap: float, ratio: float) -> None:
        """Bildirim gönderilemezse alarm yine geçerlidir — log ve denetim
        izi zaten yazıldı; bu yalnızca haber vermenin ikinci yolu."""
        from politikdesk.briefing.mailer import send_notification

        headline = (
            f"LLM {label} bütçe TAVANI aşıldı — üretim duruyor"
            if level == "exceeded"
            else f"LLM {label} bütçesinin %{ratio * 100:.0f}'i kullanıldı"
        )
        body = (
            f"{headline}\n\n"
            f"Harcanan: {spent:.4f} $\n"
            f"Tavan:    {cap:.2f} $\n\n"
            "Tavan aşıldığında YALNIZCA LLM'e bağlı adımlar durur "
            "(iddia çıkarımı, taslak üretimi). Toplama, embedding, "
            "kümeleme ve kanıt motoru çalışmaya devam eder — hiçbiri "
            "LLM kullanmaz.\n\n"
            "Tavanı değiştirmek için: PD_LLM_DAILY_BUDGET_USD / "
            "PD_LLM_MONTHLY_BUDGET_USD"
        )
        send_notification(subject=f"PolitikDesk — {headline}", text_body=body)
