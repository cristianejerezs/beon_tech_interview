"""Validated application settings and explicit provider selection."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from airport_analytics.errors import CostUnboundedError


def _decimal_env(name: str, default: str | None) -> Decimal | None:
    value = os.getenv(name, default)
    if value is None or value == "":
        return None
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a decimal number.") from exc
    if not number.is_finite() or number < 0:
        raise ValueError(f"{name} must be a finite non-negative number.")
    return number


def _int_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return value


def _bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name, str(default).lower()).strip().lower()
    if raw_value not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false.")
    return raw_value == "true"


@dataclass(frozen=True)
class Settings:
    model_provider: str
    model_name: str
    ollama_base_url: str
    openai_api_key: str | None
    openai_base_url: str | None
    hosted_input_usd_per_million: Decimal | None
    hosted_output_usd_per_million: Decimal | None
    hosted_free_plan: bool
    hosted_product_improvement_terms: str
    provider_fees_fx_multiplier: Decimal
    max_extra_fee_usd_per_request: Decimal | None
    max_input_tokens: int
    max_output_tokens: int
    free_monthly_request_limit: int
    free_monthly_token_limit: int
    deployment_monthly_budget_usd: Decimal
    database_path: Path
    source_data_dir: Path
    query_timeout_seconds: int
    model_timeout_seconds: int
    shared_reuse_enabled: bool
    production: bool
    retention_policy_approved: bool
    development_sign_in: bool = False

    @classmethod
    def from_env(cls, *, env_file: str | Path | None = ".env", load_file: bool = True) -> Settings:
        if load_file and env_file is not None:
            load_dotenv(dotenv_path=env_file, override=False)

        provider = os.getenv("AIRPORT_MODEL_PROVIDER", "ollama").strip().lower()
        if provider not in {"ollama", "openai"}:
            raise ValueError("AIRPORT_MODEL_PROVIDER must be 'ollama' or 'openai'.")

        free_plan = os.getenv("AIRPORT_HOSTED_FREE_PLAN", "false").strip().lower()
        if free_plan not in {"true", "false"}:
            raise ValueError("AIRPORT_HOSTED_FREE_PLAN must be true or false.")
        hosted_free_plan = free_plan == "true"

        api_key = os.getenv("AIRPORT_OPENAI_API_KEY") or None
        if provider == "openai" and not api_key:
            raise ValueError("AIRPORT_OPENAI_API_KEY is required for the openai provider.")

        budget = _decimal_env("AIRPORT_DEPLOYMENT_MONTHLY_BUDGET_USD", "10.00")
        if budget is None or budget > Decimal("10.00"):
            raise ValueError("The deployment monthly budget must be between zero and USD 10.")

        fee_multiplier = _decimal_env("AIRPORT_HOSTED_PROVIDER_FEES_FX_MULTIPLIER", "1.0")
        if fee_multiplier is None or fee_multiplier < 1:
            raise ValueError("AIRPORT_HOSTED_PROVIDER_FEES_FX_MULTIPLIER must be at least 1.")

        input_rate = _decimal_env("AIRPORT_HOSTED_INPUT_USD_PER_MILLION", None)
        output_rate = _decimal_env("AIRPORT_HOSTED_OUTPUT_USD_PER_MILLION", None)
        extra_fee = _decimal_env("AIRPORT_HOSTED_MAX_EXTRA_FEE_USD_PER_REQUEST", None)
        if provider == "openai" and not hosted_free_plan:
            if input_rate is None or output_rate is None:
                raise CostUnboundedError(
                    "Hosted input and output rates are required before paid use."
                )
            if extra_fee is None:
                raise CostUnboundedError(
                    "A maximum fixed fee/tax bound is required before paid hosted use."
                )

        production = _bool_env("AIRPORT_PRODUCTION")
        development_sign_in = _bool_env("AIRPORT_DEV_SIGN_IN_ENABLED")
        if production and development_sign_in:
            raise ValueError("Development sign-in is prohibited when AIRPORT_PRODUCTION=true.")

        return cls(
            model_provider=provider,
            model_name=os.getenv(
                "AIRPORT_MODEL_NAME",
                (
                    "llama3.1:8b"
                    if provider == "ollama"
                    else os.getenv("AIRPORT_OPENAI_MODEL_NAME", "")
                ),
            ).strip(),
            ollama_base_url=os.getenv("AIRPORT_OLLAMA_BASE_URL", "http://localhost:11434").strip(),
            openai_api_key=api_key,
            openai_base_url=os.getenv("AIRPORT_OPENAI_BASE_URL") or None,
            hosted_input_usd_per_million=input_rate,
            hosted_output_usd_per_million=output_rate,
            hosted_free_plan=hosted_free_plan,
            hosted_product_improvement_terms=os.getenv(
                "AIRPORT_HOSTED_PRODUCT_IMPROVEMENT_TERMS", "unknown"
            ).strip(),
            provider_fees_fx_multiplier=fee_multiplier,
            max_extra_fee_usd_per_request=extra_fee,
            max_input_tokens=_int_env("AIRPORT_HOSTED_MAX_INPUT_TOKENS", 4000),
            max_output_tokens=_int_env("AIRPORT_HOSTED_MAX_OUTPUT_TOKENS", 1000),
            free_monthly_request_limit=_int_env("AIRPORT_HOSTED_FREE_MONTHLY_REQUEST_LIMIT", 1000),
            free_monthly_token_limit=_int_env("AIRPORT_HOSTED_FREE_MONTHLY_TOKEN_LIMIT", 1_000_000),
            deployment_monthly_budget_usd=budget,
            database_path=Path(os.getenv("AIRPORT_DATABASE_PATH", "var/airport_analytics.sqlite3")),
            source_data_dir=Path(os.getenv("AIRPORT_SOURCE_DATA_DIR", "source_data")),
            query_timeout_seconds=_int_env("AIRPORT_QUERY_TIMEOUT_SECONDS", 30),
            model_timeout_seconds=_int_env("AIRPORT_MODEL_TIMEOUT_SECONDS", 60),
            shared_reuse_enabled=_bool_env("AIRPORT_SHARED_REUSE_ENABLED"),
            production=production,
            retention_policy_approved=_bool_env("AIRPORT_RETENTION_POLICY_APPROVED"),
            development_sign_in=development_sign_in,
        )

    def validate_model_selection(self) -> None:
        if not self.model_name:
            raise ValueError("AIRPORT_MODEL_NAME must be configured for the selected provider.")
