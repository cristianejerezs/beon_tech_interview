"""Explicit, default-off LangSmith tracing policy."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


def _enabled_value(environment: Mapping[str, str], name: str) -> bool:
    value = environment.get(name, "false").strip().lower()
    if value not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false.")
    return value == "true"


@dataclass(frozen=True)
class TracingConfig:
    enabled: bool
    maximum_charge_per_trace_usd: Decimal | None

    @classmethod
    def from_env(cls, environment: Mapping[str, str] | None = None) -> TracingConfig:
        values = os.environ if environment is None else environment
        requested = _enabled_value(values, "LANGSMITH_TRACING")
        disclosed = _enabled_value(values, "AIRPORT_LANGSMITH_DISCLOSURE_ENABLED")
        if not requested or not disclosed:
            return cls(enabled=False, maximum_charge_per_trace_usd=None)

        if not values.get("LANGSMITH_API_KEY"):
            raise ValueError("LANGSMITH_API_KEY is required when tracing is enabled.")
        raw_bound = values.get("AIRPORT_LANGSMITH_MAX_TRACE_CHARGE_USD", "")
        if not raw_bound:
            raise ValueError(
                "AIRPORT_LANGSMITH_MAX_TRACE_CHARGE_USD is required to bound metered tracing."
            )
        try:
            bound = Decimal(raw_bound)
        except InvalidOperation as exc:
            raise ValueError(
                "AIRPORT_LANGSMITH_MAX_TRACE_CHARGE_USD must be a decimal amount."
            ) from exc
        if not bound.is_finite() or bound < 0:
            raise ValueError(
                "AIRPORT_LANGSMITH_MAX_TRACE_CHARGE_USD must be finite and non-negative."
            )
        return cls(enabled=True, maximum_charge_per_trace_usd=bound)

    def apply(self) -> None:
        os.environ["LANGSMITH_TRACING"] = "true" if self.enabled else "false"
