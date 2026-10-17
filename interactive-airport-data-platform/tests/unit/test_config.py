import pytest

from airport_analytics.config import Settings
from airport_analytics.errors import CostUnboundedError


def test_unknown_provider_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("AIRPORT_MODEL_PROVIDER", "other")
    with pytest.raises(ValueError, match="AIRPORT_MODEL_PROVIDER"):
        Settings.from_env(load_file=False)


def test_hosted_provider_requires_credentials(monkeypatch) -> None:
    monkeypatch.setenv("AIRPORT_MODEL_PROVIDER", "openai")
    monkeypatch.delenv("AIRPORT_OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="AIRPORT_OPENAI_API_KEY"):
        Settings.from_env(load_file=False)


def test_paid_hosted_provider_requires_rates_and_extra_fee_bound(monkeypatch) -> None:
    monkeypatch.setenv("AIRPORT_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("AIRPORT_OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("AIRPORT_MODEL_NAME", "gpt-4o-mini")
    monkeypatch.delenv("AIRPORT_HOSTED_INPUT_USD_PER_MILLION", raising=False)
    monkeypatch.delenv("AIRPORT_HOSTED_OUTPUT_USD_PER_MILLION", raising=False)
    monkeypatch.delenv("AIRPORT_HOSTED_MAX_EXTRA_FEE_USD_PER_REQUEST", raising=False)
    with pytest.raises(CostUnboundedError):
        Settings.from_env(load_file=False)

    monkeypatch.setenv("AIRPORT_HOSTED_INPUT_USD_PER_MILLION", "0.15")
    monkeypatch.setenv("AIRPORT_HOSTED_OUTPUT_USD_PER_MILLION", "0.60")
    with pytest.raises(CostUnboundedError, match="fixed fee"):
        Settings.from_env(load_file=False)
    monkeypatch.setenv("AIRPORT_HOSTED_MAX_EXTRA_FEE_USD_PER_REQUEST", "0")
    settings = Settings.from_env(load_file=False)
    settings.validate_model_selection()
    assert settings.model_provider == "openai"


def test_monthly_budget_setting_cannot_exceed_ten_dollars(monkeypatch) -> None:
    monkeypatch.setenv("AIRPORT_DEPLOYMENT_MONTHLY_BUDGET_USD", "10.01")
    with pytest.raises(ValueError, match="USD 10"):
        Settings.from_env(load_file=False)


def test_shared_reuse_is_disabled_unless_explicitly_configured(monkeypatch) -> None:
    monkeypatch.delenv("AIRPORT_SHARED_REUSE_ENABLED", raising=False)
    monkeypatch.delenv("AIRPORT_PRODUCTION", raising=False)
    monkeypatch.delenv("AIRPORT_RETENTION_POLICY_APPROVED", raising=False)
    settings = Settings.from_env(load_file=False)
    assert not settings.shared_reuse_enabled
    assert not settings.production
    assert not settings.retention_policy_approved

    monkeypatch.setenv("AIRPORT_SHARED_REUSE_ENABLED", "true")
    monkeypatch.setenv("AIRPORT_PRODUCTION", "true")
    monkeypatch.setenv("AIRPORT_RETENTION_POLICY_APPROVED", "true")
    settings = Settings.from_env(load_file=False)
    assert settings.shared_reuse_enabled
    assert settings.production
    assert settings.retention_policy_approved

    monkeypatch.setenv("AIRPORT_PRODUCTION", "yes")
    with pytest.raises(ValueError, match="AIRPORT_PRODUCTION"):
        Settings.from_env(load_file=False)
