from pathlib import Path
from types import SimpleNamespace

import pytest

from airport_analytics.analytics.budget import BudgetLedger
from airport_analytics.analytics.model_client import LangChainPlanClient
from airport_analytics.analytics.provider_policy import mark_disclosed
from airport_analytics.config import Settings
from airport_analytics.errors import (
    BudgetExceededError,
    DisclosureRequiredError,
    ProviderError,
)
from airport_analytics.storage import Storage


class FakeStructuredModel:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls = 0

    def with_structured_output(self, *args, **kwargs):
        return self

    def get_num_tokens_from_messages(self, messages) -> int:
        return 1

    def invoke(self, messages):
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return {
            "parsed": {
                "status": "unsupported",
                "intent": None,
                "metric_id": None,
                "group_by": [],
                "filters": [],
                "time_range": None,
                "sort": None,
                "row_limit": 10,
                "chart_intent": None,
                "clarification_question": None,
                "unsupported_reason": "No supported measure was requested.",
            },
            "raw": SimpleNamespace(usage_metadata={}),
            "parsing_error": None,
        }


def _hosted_settings(monkeypatch, *, budget: str = "1.00") -> Settings:
    values = {
        "AIRPORT_MODEL_PROVIDER": "openai",
        "AIRPORT_OPENAI_API_KEY": "test-only",
        "AIRPORT_MODEL_NAME": "gpt-4o-mini",
        "AIRPORT_HOSTED_INPUT_USD_PER_MILLION": "1",
        "AIRPORT_HOSTED_OUTPUT_USD_PER_MILLION": "1",
        "AIRPORT_HOSTED_MAX_EXTRA_FEE_USD_PER_REQUEST": "0",
        "AIRPORT_DEPLOYMENT_MONTHLY_BUDGET_USD": budget,
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return Settings.from_env(load_file=False)


def _client(tmp_path: Path, settings: Settings, model: FakeStructuredModel):
    storage = Storage(tmp_path / "budget.sqlite3")
    budget = BudgetLedger(storage, monthly_cap_usd=settings.deployment_monthly_budget_usd)
    return LangChainPlanClient(settings, budget=budget, model=model), budget, storage


def test_hosted_provider_requires_disclosure_before_reserving_or_calling(
    tmp_path: Path, monkeypatch
) -> None:
    settings = _hosted_settings(monkeypatch)
    model = FakeStructuredModel()
    client, _, storage = _client(tmp_path, settings, model)

    with pytest.raises(DisclosureRequiredError):
        client.generate_plan("What is the flight count?", session_state={})

    assert model.calls == 0
    with storage.read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM usage_reservations").fetchone()[0] == 0


def test_budget_exhaustion_blocks_hosted_dispatch(tmp_path: Path, monkeypatch) -> None:
    settings = _hosted_settings(monkeypatch, budget="0")
    model = FakeStructuredModel()
    client, _, _ = _client(tmp_path, settings, model)
    session_state: dict[str, object] = {}
    mark_disclosed(session_state, client.provider)

    with pytest.raises(BudgetExceededError):
        client.generate_plan("What is the flight count?", session_state=session_state)

    assert model.calls == 0


def test_uncertain_provider_failure_is_not_retried_or_released(tmp_path: Path, monkeypatch) -> None:
    settings = _hosted_settings(monkeypatch)
    model = FakeStructuredModel(failure=TimeoutError("unknown provider acceptance"))
    client, _, storage = _client(tmp_path, settings, model)
    session_state: dict[str, object] = {}
    mark_disclosed(session_state, client.provider)

    with pytest.raises(ProviderError):
        client.generate_plan("What is the flight count?", session_state=session_state)

    assert model.calls == 1
    with storage.read() as connection:
        row = connection.execute("SELECT status, failure_reason FROM usage_reservations").fetchone()
    assert row["status"] == "reserved"
    assert "acceptance is unknown" in row["failure_reason"]
