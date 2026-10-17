import os
from decimal import Decimal

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
