from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from threading import Barrier

import pytest

from airport_analytics.analytics.budget import BudgetLedger
from airport_analytics.errors import (
    BudgetExceededError,
    CostUnboundedError,
)
from airport_analytics.storage import Storage


def ledger(
    path: Path,
    cap: Decimal = Decimal("10.00"),
    *,
    request_limit: int = 100,
    token_limit: int = 100_000,
) -> BudgetLedger:
    return BudgetLedger(
        Storage(path),
        monthly_cap_usd=cap,
        free_monthly_request_limit=request_limit,
        free_monthly_token_limit=token_limit,
    )


def reserve(
    service: BudgetLedger,
    *,
    at: datetime | None = None,
    free: bool = False,
    rate: Decimal | None = Decimal("10"),
    extra: Decimal | None = Decimal("0"),
    input_tokens: int = 1000,
    output_tokens: int = 1000,
):
    return service.reserve(
        provider_id="test-provider",
        model_id="test-model",
        max_input_tokens=input_tokens,
        max_output_tokens=output_tokens,
        input_usd_per_million=rate,
        output_usd_per_million=rate,
        fee_fx_multiplier=Decimal("1"),
        maximum_extra_fee_usd=extra,
        free_plan=free,
        accepted_at=at,
    )


def test_provider_only_free_quota_preserves_usage_and_strict_restart(tmp_path):
    storage = Storage(tmp_path / "development.sqlite")
    development = BudgetLedger(
        storage,
        free_monthly_request_limit=1,
        free_monthly_token_limit=1,
        enforce_free_monthly_quotas=False,
    )
    first = reserve(development, free=True)
    development.mark_uncertain(first.reservation_id, "unknown acceptance")
    second = reserve(development, free=True)
    assert first.reservation_id != second.reservation_id
    strict = BudgetLedger(storage, free_monthly_request_limit=1, free_monthly_token_limit=1)
    with pytest.raises(BudgetExceededError):
        reserve(strict, free=True)


def test_provider_only_free_quota_does_not_disable_spending_guard(tmp_path):
    development = BudgetLedger(
        Storage(tmp_path / "spending.sqlite"),
        monthly_cap_usd=Decimal("0"),
        enforce_free_monthly_quotas=False,
    )
    with pytest.raises(BudgetExceededError):
        reserve(development, free=False)
    assert reserve(development, free=True).free_plan


def test_clarification_dispatch_respects_prior_month_uncertainty_after_restart(
    tmp_path,
    monkeypatch,
):
    from dataclasses import replace

    from airport_analytics.analytics.model_client import LangChainPlanClient
    from airport_analytics.analytics.provider_policy import mark_disclosed
    from tests.integration.test_exploration_provider import IntentModel
    from tests.integration.test_model_failure_modes import _hosted_settings
    from tests.unit.test_exploration_state import ambiguous

    path = tmp_path / "clarification-uncertainty.sqlite3"
    service = ledger(path)
    first = reserve(service, at=datetime(2025, 1, 31, tzinfo=UTC))
    service.mark_uncertain(first.reservation_id, "provider acceptance unknown")
    model = IntentModel()
    client = LangChainPlanClient(
        replace(_hosted_settings(monkeypatch), max_input_tokens=100000),
        budget=ledger(path),
        model=model,
        contract_version=2,
    )
    state = {}
    mark_disclosed(state, client.provider)
    with pytest.raises(CostUnboundedError):
        client.generate_clarification(
            "Count flights at the airport",
            "JFK",
            ambiguous(),
            1,
            session_state=state,
        )
    assert model.calls == 0
    with Storage(path).read() as connection:
        row = connection.execute(
            "SELECT period_start_utc, status FROM usage_reservations"
        ).fetchone()
        assert row["period_start_utc"] == "2025-01-01"
        assert row["status"] == "reserved"


def test_shared_cap_counts_reservations_and_settled_usage(tmp_path: Path) -> None:
    service = ledger(tmp_path / "usage.sqlite3", Decimal("0.05"))
    reserve(service)
    reserve(service)
    with pytest.raises(BudgetExceededError):
        reserve(service)


@pytest.mark.parametrize(
    "reported_input,reported_output,charged",
    [(10, 20, 30), (None, 20, 1020), (10, None, 1010), (None, None, 2000), (1500, 1000, 2500)],
)
def test_free_quota_uses_settled_usage_with_per_component_conservative_fallback(
    tmp_path,
    reported_input,
    reported_output,
    charged,
):
    path = tmp_path / "actual-free.sqlite3"
    service = ledger(path, token_limit=charged + 2000)
    first = reserve(service, free=True)
    service.settle(
        first.reservation_id,
        input_tokens=reported_input,
        output_tokens=reported_output,
    )
    reopened = ledger(path, token_limit=charged + 2000)
    reserve(reopened, free=True)
    with pytest.raises(BudgetExceededError):
        reserve(reopened, free=True, input_tokens=1, output_tokens=0)
    assert reopened.get_reservation(first.reservation_id).reserved_tokens == 2000


def test_free_quota_keeps_uncertain_reservations_and_request_count(tmp_path):
    service = ledger(tmp_path / "held-free.sqlite3", token_limit=2030, request_limit=3)
    first = reserve(service, free=True)
    service.mark_uncertain(first.reservation_id, "acceptance unknown")
    second = reserve(service, free=True, input_tokens=10, output_tokens=20)
    service.settle(second.reservation_id, input_tokens=0, output_tokens=0)
    third = reserve(service, free=True, input_tokens=10, output_tokens=20)
    service.settle(third.reservation_id, input_tokens=0, output_tokens=0)
    with pytest.raises(BudgetExceededError):
        reserve(service, free=True, input_tokens=0, output_tokens=0)
    assert service.get_reservation(first.reservation_id).status == "reserved"


def test_concurrent_reservations_cannot_exceed_shared_cap(tmp_path: Path) -> None:
    service = ledger(tmp_path / "concurrent.sqlite3", Decimal("0.05"))
    barrier = Barrier(5)

    def attempt(_: int) -> bool:
        barrier.wait()
        try:
            reserve(service)
            return True
        except BudgetExceededError:
            return False

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(attempt, range(5)))
    assert sum(results) == 2


def test_utc_month_rollover_uses_utc_acceptance_month(tmp_path: Path) -> None:
    service = ledger(tmp_path / "rollover.sqlite3")
    accepted = datetime(2026, 1, 31, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    reservation = reserve(service, at=accepted)
    assert reservation.period_start_utc == "2026-02-01"


def test_paid_request_rejects_unbounded_rates_and_fees(tmp_path: Path) -> None:
    service = ledger(tmp_path / "unbounded.sqlite3")
    with pytest.raises(CostUnboundedError):
        reserve(service, rate=None)
    with pytest.raises(CostUnboundedError):
        reserve(service, extra=None)


def test_reservation_includes_fees_taxes_and_fx_bound(tmp_path: Path) -> None:
    service = ledger(tmp_path / "fees.sqlite3")
    reservation = service.reserve(
        provider_id="test-provider",
        model_id="test-model",
        max_input_tokens=1000,
        max_output_tokens=1000,
        input_usd_per_million=Decimal("10"),
        output_usd_per_million=Decimal("10"),
        fee_fx_multiplier=Decimal("1.1"),
        maximum_extra_fee_usd=Decimal("0.03"),
        free_plan=False,
        accepted_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert reservation.reserved_usd == Decimal("0.06")


def test_late_invoice_settles_against_request_acceptance_month(tmp_path: Path) -> None:
    service = ledger(tmp_path / "late.sqlite3")
    reservation = reserve(service, at=datetime(2026, 1, 31, tzinfo=UTC))
    service.settle(
        reservation.reservation_id,
        input_tokens=500,
        output_tokens=500,
        settled_at=datetime(2026, 2, 2, tzinfo=UTC),
    )
    with service.storage.read() as connection:
        row = connection.execute(
            "SELECT period_start_utc, actual_usd FROM usage_reservations WHERE reservation_id = ?",
            (reservation.reservation_id,),
        ).fetchone()
    assert row["period_start_utc"] == "2026-01-01"
    assert Decimal(row["actual_usd"]) == Decimal("0.01")


def test_partial_response_settles_reported_usage_and_fees(tmp_path: Path) -> None:
    service = ledger(tmp_path / "partial.sqlite3")
    reservation = reserve(service)
    settlement = service.settle(
        reservation.reservation_id,
        input_tokens=500,
        output_tokens=250,
        provider_fees_usd=Decimal("0.01"),
        currency_conversion_usd=Decimal("0.02"),
    )
    assert settlement.actual_usd == Decimal("0.0375")
    assert settlement.over_reservation is True


def test_uncertain_reservation_is_held_until_reconciliation(tmp_path: Path) -> None:
    service = ledger(tmp_path / "uncertain.sqlite3", Decimal("0.03"))
    reservation = reserve(service)
    service.mark_uncertain(reservation.reservation_id, "provider acceptance unknown")
    with pytest.raises(BudgetExceededError):
        reserve(service)
    assert service.get_reservation(reservation.reservation_id).status == "reserved"


def test_uncertain_acceptance_blocks_paid_calls_even_with_ample_budget(tmp_path):
    service = ledger(tmp_path / "uncertain-ample.sqlite3")
    reservation = reserve(service, at=datetime(2026, 1, 31, tzinfo=UTC))
    service.mark_uncertain(reservation.reservation_id, "provider acceptance unknown")
    reopened = ledger(tmp_path / "uncertain-ample.sqlite3")
    with pytest.raises(CostUnboundedError):
        reserve(reopened, at=datetime(2026, 2, 1, tzinfo=UTC))
    reopened.release_confirmed_non_acceptance(
        reservation.reservation_id, provider_confirmed_non_acceptance=True
    )
    reserve(reopened, at=datetime(2026, 2, 1, tzinfo=UTC))


def test_release_requires_confirmed_non_acceptance(tmp_path: Path) -> None:
    service = ledger(tmp_path / "release.sqlite3", Decimal("0.02"))
    reservation = reserve(service)
    service.release_confirmed_non_acceptance(
        reservation.reservation_id,
        provider_confirmed_non_acceptance=True,
    )
    assert service.get_reservation(reservation.reservation_id).status == "released"
    reserve(service)


def test_over_reservation_charge_is_surfaced_and_blocks_future_calls(
    tmp_path: Path,
) -> None:
    service = ledger(tmp_path / "overrun.sqlite3", Decimal("0.05"))
    reservation = reserve(service)
    settlement = service.settle(
        reservation.reservation_id,
        actual_usd=Decimal("0.06"),
        input_tokens=1000,
        output_tokens=1000,
    )
    assert settlement.over_reservation
    assert settlement.operator_notice
    with pytest.raises(BudgetExceededError):
        reserve(service)


def test_free_plan_enforces_separate_request_and_token_quotas(tmp_path: Path) -> None:
    service = ledger(
        tmp_path / "free.sqlite3",
        request_limit=1,
        token_limit=1000,
    )
    reserve(service, free=True, rate=None, extra=None, input_tokens=600, output_tokens=400)
    with pytest.raises(BudgetExceededError):
        reserve(service, free=True, rate=None, extra=None, input_tokens=1, output_tokens=1)
