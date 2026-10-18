import os
from decimal import Decimal

import pytest

from airport_analytics.analytics.model_client import LangChainPlanClient
from airport_analytics.config import Settings
from airport_analytics.observability.tracing import TracingConfig
from app import tracing_acknowledged


def test_hosted_or_trace_context_is_not_acknowledged_by_default() -> None:
    tracing = TracingConfig(enabled=True, maximum_charge_per_trace_usd=Decimal("0.01"))

    assert not tracing_acknowledged(tracing, {})
    assert tracing_acknowledged(tracing, {"airport_langsmith_disclosure_acknowledged": True})
    assert tracing_acknowledged(TracingConfig(False, None), {})


def test_default_configuration_keeps_langsmith_tracing_off(monkeypatch) -> None:
    for name in (
        "LANGSMITH_TRACING",
        "LANGSMITH_API_KEY",
        "AIRPORT_LANGSMITH_DISCLOSURE_ENABLED",
        "AIRPORT_LANGSMITH_MAX_TRACE_CHARGE_USD",
    ):
        monkeypatch.delenv(name, raising=False)

    tracing = TracingConfig.from_env()
    tracing.apply()

    assert not tracing.enabled
    assert os.environ["LANGSMITH_TRACING"] == "false"


def test_private_question_call_runs_with_tracing_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AIRPORT_MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("AIRPORT_MODEL_NAME", "test-local-model")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    tracing = TracingConfig.from_env({})

    class LocalModel:
        tracing_during_call: str | None = None

        def with_structured_output(self, *args, **kwargs):
            return self

        def invoke(self, messages):
            self.tracing_during_call = os.environ["LANGSMITH_TRACING"]
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
                "raw": None,
                "parsing_error": None,
            }

    model = LocalModel()
    client = LangChainPlanClient(
        Settings.from_env(load_file=False),
        model=model,
        tracing=tracing,
    )
    client.generate_plan("Private analyst question", session_state={})

    assert model.tracing_during_call == "false"


@pytest.mark.parametrize("enabled", [False, True])
def test_clarification_trace_policy_and_operational_logs_are_separate(
    tmp_path,
    monkeypatch,
    caplog,
    enabled,
):
    from dataclasses import replace

    from airport_analytics.analytics.budget import BudgetLedger
    from airport_analytics.analytics.provider_policy import mark_disclosed
    from airport_analytics.errors import ProviderError
    from airport_analytics.storage import Storage
    from tests.integration.test_exploration_provider import IntentModel
    from tests.integration.test_model_failure_modes import _hosted_settings
    from tests.unit.test_exploration_state import ambiguous

    class ObservedModel(IntentModel):
        def invoke(self, messages):
            self.tracing_during_call = os.environ["LANGSMITH_TRACING"]
            return super().invoke(messages)

    model = ObservedModel(failure=TimeoutError("private-response secret-key"))
    storage = Storage(tmp_path / "trace-clarification.sqlite")
    client = LangChainPlanClient(
        replace(_hosted_settings(monkeypatch), max_input_tokens=100000),
        model=model,
        budget=BudgetLedger(storage),
        contract_version=2,
        tracing=TracingConfig(enabled, Decimal("0.01") if enabled else None),
    )
    state = {}
    mark_disclosed(state, client.provider)
    with pytest.raises(ProviderError):
        client.generate_clarification(
            "private-question",
            "private-answer",
            ambiguous(),
            1,
            session_state=state,
        )
    assert model.tracing_during_call == str(enabled).lower()
    for private in ["private-question", "private-answer", "private-response", "secret-key"]:
        assert private not in caplog.text
    with storage.read() as connection:
        traces = connection.execute(
            "SELECT status FROM usage_reservations WHERE provider_id='langsmith-tracing'"
        ).fetchall()
        assert len(traces) == int(enabled)
        if enabled:
            assert traces[0]["status"] == "settled"
