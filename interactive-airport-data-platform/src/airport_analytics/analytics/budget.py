"""Transactional deployment-wide monthly hosted-inference and tracing budget."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from sqlite3 import Connection, Row

from airport_analytics.errors import (
    BudgetExceededError,
    CostUnboundedError,
)
from airport_analytics.storage import Storage

CENT = Decimal("0.01")
MILLION = Decimal("1000000")


def _as_decimal(value: Decimal | str | int | float | None, name: str) -> Decimal:
    if value is None:
        raise CostUnboundedError(f"{name} is required to bound this hosted request.")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise CostUnboundedError(f"{name} must be a valid decimal.") from exc
    if not number.is_finite() or number < 0:
        raise CostUnboundedError(f"{name} must be finite and non-negative.")
    return number


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Budget timestamps must include a timezone.")
    return value.astimezone(UTC)


def _period_start(value: datetime | None) -> str:
    instant = _utc(value)
    return date(instant.year, instant.month, 1).isoformat()


def _round_reservation(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_CEILING)


@dataclass(frozen=True)
class BudgetReservation:
    reservation_id: str
    provider_id: str
    model_id: str
    period_start_utc: str
    reserved_usd: Decimal
    reserved_tokens: int
    status: str
    free_plan: bool


@dataclass(frozen=True)
class Settlement:
    reservation_id: str
    actual_usd: Decimal
    over_reservation: bool
    budget_exhausted: bool
    operator_notice: str | None


class BudgetLedger:
    def __init__(
        self,
        storage: Storage,
        *,
        monthly_cap_usd: Decimal = Decimal("10.00"),
        free_monthly_request_limit: int = 1000,
        free_monthly_token_limit: int = 1_000_000,
    ) -> None:
        cap = _as_decimal(monthly_cap_usd, "monthly_cap_usd")
        if cap > Decimal("10.00"):
            raise ValueError("The deployment-wide monthly cap cannot exceed USD 10.")
        if free_monthly_request_limit < 1 or free_monthly_token_limit < 1:
            raise ValueError("Free-provider quotas must be positive.")
        self.storage = storage
        self.monthly_cap_usd = cap
        self.free_monthly_request_limit = free_monthly_request_limit
        self.free_monthly_token_limit = free_monthly_token_limit

    @staticmethod
    def _from_row(row: Row) -> BudgetReservation:
        return BudgetReservation(
            reservation_id=row["reservation_id"],
            provider_id=row["provider_id"],
            model_id=row["model_id"],
            period_start_utc=row["period_start_utc"],
            reserved_usd=Decimal(row["reserved_usd"]),
            reserved_tokens=int(row["reserved_tokens"]),
            status=row["status"],
            free_plan=bool(row["free_plan"]),
        )

    @staticmethod
    def _sum_period(connection: Connection, period_start: str) -> Decimal:
        rows = connection.execute(
            "SELECT reserved_usd, actual_usd, status FROM usage_reservations "
            "WHERE period_start_utc = ? AND status != 'released'",
            (period_start,),
        ).fetchall()
        total = Decimal("0")
        for row in rows:
            amount = row["actual_usd"] if row["actual_usd"] is not None else row["reserved_usd"]
            total += Decimal(amount)
        return total

    def _authorize(
        self,
        connection: Connection,
        *,
        period_start: str,
        reservation_usd: Decimal,
        reserved_tokens: int,
        free_plan: bool,
    ) -> None:
        spent_and_reserved = self._sum_period(connection, period_start)
        if spent_and_reserved + reservation_usd > self.monthly_cap_usd:
            raise BudgetExceededError("The shared deployment monthly spending cap is exhausted.")

        if free_plan:
            usage = connection.execute(
                """
                SELECT COUNT(*) AS request_count, COALESCE(SUM(reserved_tokens), 0) AS tokens
                FROM usage_reservations
                WHERE period_start_utc = ? AND free_plan = 1 AND status != 'released'
                """,
                (period_start,),
            ).fetchone()
            if (
                int(usage["request_count"]) + 1 > self.free_monthly_request_limit
                or int(usage["tokens"]) + reserved_tokens > self.free_monthly_token_limit
            ):
                raise BudgetExceededError("The configured free-provider quota is exhausted.")

    def reserve(
        self,
        *,
        provider_id: str,
        model_id: str,
        max_input_tokens: int,
        max_output_tokens: int,
        input_usd_per_million: Decimal | None,
        output_usd_per_million: Decimal | None,
        fee_fx_multiplier: Decimal,
        maximum_extra_fee_usd: Decimal | None,
        free_plan: bool = False,
        accepted_at: datetime | None = None,
    ) -> BudgetReservation:
        if max_input_tokens < 0 or max_output_tokens < 0:
            raise ValueError("Token ceilings must be non-negative.")
        period_start = _period_start(accepted_at)
        reserved_tokens = max_input_tokens + max_output_tokens

        if free_plan:
            input_rate = Decimal("0")
            output_rate = Decimal("0")
            fee_multiplier = Decimal("1")
            extra_fee = Decimal("0")
            reserved_usd = Decimal("0")
        else:
            input_rate = _as_decimal(input_usd_per_million, "input token rate")
            output_rate = _as_decimal(output_usd_per_million, "output token rate")
            fee_multiplier = _as_decimal(fee_fx_multiplier, "fee and currency multiplier")
            if fee_multiplier < 1:
                raise CostUnboundedError("The fee/FX multiplier must be at least 1.")
            extra_fee = _as_decimal(maximum_extra_fee_usd, "maximum request fees and taxes")
            maximum_token_cost = (
                Decimal(max_input_tokens) * input_rate + Decimal(max_output_tokens) * output_rate
            ) / MILLION
            reserved_usd = _round_reservation(maximum_token_cost * fee_multiplier + extra_fee)

        reservation_id = str(uuid.uuid4())
        now = _utc(accepted_at).isoformat()
        with self.storage.transaction() as connection:
            self._authorize(
                connection,
                period_start=period_start,
                reservation_usd=reserved_usd,
                reserved_tokens=reserved_tokens,
                free_plan=free_plan,
            )
            connection.execute(
                """
                INSERT INTO usage_reservations (
                    reservation_id, provider_id, model_id, period_start_utc,
                    reserved_usd, input_usd_per_million, output_usd_per_million,
                    fee_fx_multiplier, maximum_extra_fee_usd, free_plan,
                    max_input_tokens, max_output_tokens, reserved_tokens,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'reserved', ?)
                """,
                (
                    reservation_id,
                    provider_id,
                    model_id,
                    period_start,
                    str(reserved_usd),
                    str(input_rate) if not free_plan else None,
                    str(output_rate) if not free_plan else None,
                    str(fee_multiplier),
                    str(extra_fee),
                    int(free_plan),
                    max_input_tokens,
                    max_output_tokens,
                    reserved_tokens,
                    now,
                ),
            )
        return BudgetReservation(
            reservation_id=reservation_id,
            provider_id=provider_id,
            model_id=model_id,
            period_start_utc=period_start,
            reserved_usd=reserved_usd,
            reserved_tokens=reserved_tokens,
            status="reserved",
            free_plan=free_plan,
        )

    def reserve_cost(
        self,
        *,
        provider_id: str,
        model_id: str,
        maximum_charge_usd: Decimal,
        accepted_at: datetime | None = None,
    ) -> BudgetReservation:
        amount = _as_decimal(maximum_charge_usd, "maximum trace charge")
        period_start = _period_start(accepted_at)
        reservation_id = str(uuid.uuid4())
        now = _utc(accepted_at).isoformat()
        with self.storage.transaction() as connection:
            self._authorize(
                connection,
                period_start=period_start,
                reservation_usd=amount,
                reserved_tokens=0,
                free_plan=False,
            )
            connection.execute(
                """
                INSERT INTO usage_reservations (
                    reservation_id, provider_id, model_id, period_start_utc,
                    reserved_usd, fee_fx_multiplier, maximum_extra_fee_usd,
                    max_input_tokens, max_output_tokens, reserved_tokens, status, created_at
                ) VALUES (?, ?, ?, ?, ?, '1', '0', 0, 0, 0, 'reserved', ?)
                """,
                (reservation_id, provider_id, model_id, period_start, str(amount), now),
            )
        return BudgetReservation(
            reservation_id=reservation_id,
            provider_id=provider_id,
            model_id=model_id,
            period_start_utc=period_start,
            reserved_usd=amount,
            reserved_tokens=0,
            status="reserved",
            free_plan=False,
        )

    def get_reservation(self, reservation_id: str) -> BudgetReservation:
        with self.storage.read() as connection:
            row = connection.execute(
                "SELECT * FROM usage_reservations WHERE reservation_id = ?",
                (reservation_id,),
            ).fetchone()
        if row is None:
            raise ValueError("Unknown budget reservation.")
        return self._from_row(row)

    def mark_uncertain(self, reservation_id: str, reason: str) -> None:
        with self.storage.transaction() as connection:
            cursor = connection.execute(
                "UPDATE usage_reservations SET failure_reason = ? "
                "WHERE reservation_id = ? AND status = 'reserved'",
                (reason, reservation_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Only an in-flight reservation can be marked uncertain.")

    def release_confirmed_non_acceptance(
        self,
        reservation_id: str,
        *,
        provider_confirmed_non_acceptance: bool,
        settled_at: datetime | None = None,
    ) -> None:
        if not provider_confirmed_non_acceptance:
            raise ValueError("A reservation can be released only after confirmed non-acceptance.")
        with self.storage.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE usage_reservations
                SET status = 'released', actual_usd = '0', settled_at = ?,
                    failure_reason = 'provider confirmed request was not accepted'
                WHERE reservation_id = ? AND status = 'reserved'
                """,
                (_utc(settled_at).isoformat(), reservation_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Only an in-flight reservation can be released.")

    def release_before_dispatch(self, reservation_id: str) -> None:
        """Release a reservation when application code proves no provider call was sent."""
        with self.storage.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE usage_reservations
                SET status = 'released', actual_usd = '0', settled_at = ?,
                    failure_reason = 'request was not dispatched'
                WHERE reservation_id = ? AND status = 'reserved'
                """,
                (datetime.now(UTC).isoformat(), reservation_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Only an in-flight reservation can be released.")

    def settle(
        self,
        reservation_id: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        provider_fees_usd: Decimal | None = None,
        currency_conversion_usd: Decimal | None = None,
        actual_usd: Decimal | None = None,
        settled_at: datetime | None = None,
    ) -> Settlement:
        if input_tokens is not None and input_tokens < 0:
            raise ValueError("Reported input tokens cannot be negative.")
        if output_tokens is not None and output_tokens < 0:
            raise ValueError("Reported output tokens cannot be negative.")
        fees = Decimal("0")
        if provider_fees_usd is not None:
            fees += _as_decimal(provider_fees_usd, "provider fees and taxes")
        if currency_conversion_usd is not None:
            fees += _as_decimal(currency_conversion_usd, "currency conversion charges")

        settled_time = _utc(settled_at).isoformat()
        with self.storage.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM usage_reservations WHERE reservation_id = ?",
                (reservation_id,),
            ).fetchone()
            if row is None or row["status"] != "reserved":
                raise ValueError("Only an in-flight reservation can be settled.")

            reserved = Decimal(row["reserved_usd"])
            if actual_usd is not None:
                actual = _as_decimal(actual_usd, "actual provider charge")
            elif row["input_usd_per_million"] is None:
                actual = reserved
            else:
                input_rate = Decimal(row["input_usd_per_million"])
                output_rate = Decimal(row["output_usd_per_million"])
                multiplier = Decimal(row["fee_fx_multiplier"])
                if input_tokens is None:
                    input_tokens = int(row["max_input_tokens"])
                if output_tokens is None:
                    output_tokens = int(row["max_output_tokens"])
                token_cost = (
                    Decimal(input_tokens) * input_rate + Decimal(output_tokens) * output_rate
                ) / MILLION
                if provider_fees_usd is None and currency_conversion_usd is None:
                    fees = Decimal(row["maximum_extra_fee_usd"])
                actual = token_cost * multiplier + fees

            over_reservation = actual > reserved
            notice = None
            if over_reservation:
                notice = f"Settled provider charge USD {actual} exceeded reserved USD {reserved}."
            connection.execute(
                """
                UPDATE usage_reservations
                SET actual_usd = ?, input_tokens = ?, output_tokens = ?,
                    status = 'settled', settled_at = ?, failure_reason = ?
                WHERE reservation_id = ?
                """,
                (
                    str(actual),
                    input_tokens,
                    output_tokens,
                    settled_time,
                    notice,
                    reservation_id,
                ),
            )
            period_start = row["period_start_utc"]
            after_settlement = self._sum_period(connection, period_start)
            budget_exhausted = after_settlement >= self.monthly_cap_usd

        return Settlement(
            reservation_id=reservation_id,
            actual_usd=actual,
            over_reservation=over_reservation,
            budget_exhausted=budget_exhausted,
            operator_notice=notice,
        )

    def remaining_usd(self, at: datetime | None = None) -> Decimal:
        period_start = _period_start(at)
        with self.storage.read() as connection:
            spent = self._sum_period(connection, period_start)
        return max(Decimal("0"), self.monthly_cap_usd - spent)
