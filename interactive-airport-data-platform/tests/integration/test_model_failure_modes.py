import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import APIStatusError

from airport_analytics.analytics.budget import BudgetLedger
from airport_analytics.analytics.model_client import LangChainPlanClient
from airport_analytics.analytics.provider_policy import mark_disclosed
from airport_analytics.config import Settings
from airport_analytics.errors import (
    BudgetExceededError,
    CostUnboundedError,
    DisclosureRequiredError,
    ProviderError,
    user_safe_message,
)
from airport_analytics.storage import Storage


class FakeStructuredModel:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls = 0

    def with_structured_output(self, *args, **kwargs):
        self.output_schema = args[0]
        self.output_options = kwargs
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
        "AIRPORT_HOSTED_FREE_PLAN": "false",
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


def _groq_settings(monkeypatch) -> Settings:
    return replace(
        _hosted_settings(monkeypatch),
        model_provider="groq",
        model_name="openai/gpt-oss-20b",
        openai_base_url="https://api.groq.com/openai/v1",
        hosted_free_plan=True,
        max_input_tokens=16000,
        max_output_tokens=4096,
    )


def test_groq_free_call_uses_harmony_validation_and_persistent_quota(tmp_path, monkeypatch) -> None:
    settings = _groq_settings(monkeypatch)
    model = FakeStructuredModel()
    # The OpenAI chat name/tokenizer path must not be used for GPT-OSS.
    model.get_num_tokens_from_messages = lambda _: pytest.fail("OpenAI tokenizer was used")
    client, budget, storage = _client(tmp_path, settings, model)
    state = {}
    with pytest.raises(DisclosureRequiredError):
        client.generate_plan("How many flights?", session_state=state)
    mark_disclosed(state, client.provider)
    outcome = client.generate_plan("How many flights?", session_state=state)
    assert outcome.plan.status == "unsupported"
    assert model.calls == 1
    assert budget.remaining_usd() == Decimal("1.00")
    with storage.read() as connection:
        row = connection.execute(
            "SELECT free_plan, reserved_tokens, status FROM usage_reservations"
        ).fetchone()
    assert row["free_plan"] == 1
    assert row["reserved_tokens"] == 20096
    assert row["status"] == "settled"


@pytest.mark.parametrize(
    "changes",
    [
        {"hosted_free_plan": False},
        {"openai_base_url": "https://another.example/v1"},
        {"model_name": "unverified-model"},
    ],
)
def test_groq_rejects_unsupported_configuration(tmp_path, monkeypatch, changes) -> None:
    with pytest.raises((ValueError, CostUnboundedError)):
        _client(tmp_path, replace(_groq_settings(monkeypatch), **changes), FakeStructuredModel())


def test_groq_input_limit_blocks_dispatch(tmp_path, monkeypatch) -> None:
    settings = replace(_groq_settings(monkeypatch), max_input_tokens=1)
    model = FakeStructuredModel()
    client, _, _ = _client(tmp_path, settings, model)
    state = {}
    mark_disclosed(state, client.provider)
    with pytest.raises(CostUnboundedError):
        client.generate_plan("How many flights?", session_state=state)
    assert model.calls == 0


def test_prompt_requires_airport_clarification_and_declares_metric_groupings(
    tmp_path, monkeypatch
) -> None:
    from airport_analytics.data.catalog import METRICS

    client, _, _ = _client(tmp_path, _groq_settings(monkeypatch), FakeStructuredModel())
    prompt = client._messages(
        "Determine the number of distinct destinations connected to the airport.", None
    )[0].content
    assert "ask which airport" in prompt
    catalog = json.loads(client._catalog_json)
    destination_metric = next(
        metric for metric in catalog["metrics"] if metric["id"] == "distinct_destination_count"
    )
    assert destination_metric["allowed_group_by"] == sorted(
        METRICS["distinct_destination_count"].allowed_dimensions
    )


def test_plan_rejection_guidance_is_safe_and_does_not_echo_arbitrary_details() -> None:
    from airport_analytics.errors import InvalidPlanError

    error = InvalidPlanError("The selected metric cannot be grouped by that dimension.")
    assert "unsupported metric/grouping" in user_safe_message(error)
    assert "No query was executed" in user_safe_message(error)
    assert "private-question" not in user_safe_message(InvalidPlanError("private-question"))


@pytest.mark.parametrize(
    ("time_range", "valid"),
    [
        (None, True),
        ({"start": "2013-01-01", "end": "2013-12-31"}, True),
        ({"start": "2013-01-01", "end": None}, False),
        ({"start": None, "end": "2013-12-31"}, False),
        ({"start": None, "end": None}, False),
        ({}, False),
        ({"start": "2013-01-01"}, False),
    ],
)
def test_groq_wire_schema_prevents_empty_date_ranges(
    tmp_path, monkeypatch, time_range, valid
) -> None:
    from jsonschema import Draft202012Validator

    client, _, _ = _client(tmp_path, _groq_settings(monkeypatch), FakeStructuredModel())
    schema = client.chat_model.output_schema["properties"]["time_range"]
    assert Draft202012Validator(schema).is_valid(time_range) is valid


def test_groq_wire_schema_uses_supported_subset_but_local_validation_remains(
    tmp_path, monkeypatch
) -> None:
    from airport_analytics.analytics.plan_schema import validate_analysis_plan
    from airport_analytics.errors import InvalidPlanError

    model = FakeStructuredModel()
    client, _, _ = _client(tmp_path, _groq_settings(monkeypatch), model)
    assert model.output_options["strict"] is True
    assert model.output_schema["title"] == "airport_analysis_plan"
    assert "allOf" not in model.output_schema
    assert "allOf" in client.schema
    assert "anyOf" in model.output_schema["properties"]["filters"]["items"]["properties"]["value"]
    assert "maxItems" not in model.output_schema["properties"]["group_by"]
    assert "maxItems" in client.schema["properties"]["group_by"]
    bad = model.invoke([])["parsed"]
    bad["row_limit"] = 999
    with pytest.raises(InvalidPlanError):
        validate_analysis_plan(bad)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 413, 422, 429, 500])
def test_provider_status_is_actionable_without_exposing_response_or_credentials(
    tmp_path, monkeypatch, status
) -> None:
    response = httpx.Response(status, request=httpx.Request("POST", "https://provider.example/v1"))
    failure = APIStatusError(
        "secret-key private-question private-response", response=response, body={"private": "data"}
    )
    model = FakeStructuredModel(failure=failure)
    client, _, storage = _client(tmp_path, _groq_settings(monkeypatch), model)
    state = {}
    mark_disclosed(state, client.provider)
    with pytest.raises(ProviderError) as error:
        client.generate_plan("Synthetic test question", session_state=state)
    message = user_safe_message(error.value)
    assert f"HTTP {status}" in message
    assert "secret-key" not in message
    assert "private" not in message
    assert model.calls == 1
    with storage.read() as connection:
        assert (
            connection.execute("SELECT status FROM usage_reservations").fetchone()["status"]
            == "reserved"
        )


@pytest.mark.parametrize("nested", [False, True])
def test_provider_400_reports_only_allowlisted_code_and_parameter(nested) -> None:
    from airport_analytics.analytics.model_client import _safe_provider_error

    detail = {
        "code": "json_validate_failed",
        "param": "response_format",
        "message": "secret-key private-question",
        "failed_generation": "private-response",
    }
    response = httpx.Response(400, request=httpx.Request("POST", "https://provider.example"))
    failure = APIStatusError(
        "private-response", response=response, body={"error": detail} if nested else detail
    )
    message = user_safe_message(_safe_provider_error(failure))
    assert "Code: json_validate_failed" in message
    assert "Rejected parameter: response_format" in message
    assert "private" not in message
    assert "secret" not in message


@pytest.mark.parametrize("unsafe", ["private-response", {"secret": "private-response"}, None])
def test_unknown_provider_details_are_not_echoed(unsafe) -> None:
    from airport_analytics.analytics.model_client import _safe_provider_error

    response = httpx.Response(400, request=httpx.Request("POST", "https://provider.example"))
    failure = APIStatusError("secret", response=response, body={"code": unsafe, "param": unsafe})
    message = user_safe_message(_safe_provider_error(failure))
    assert "private" not in message
    assert "secret" not in message
    assert "Code:" not in message
    assert "Rejected parameter:" not in message


@pytest.mark.parametrize("plan_kind", ["unsupported", "full_year", "open_ended"])
def test_real_langchain_adapter_sends_compatible_groq_schema(
    tmp_path, monkeypatch, plan_kind
) -> None:
    from langchain_openai import ChatOpenAI

    settings = _groq_settings(monkeypatch)
    payloads = []
    plan = FakeStructuredModel().invoke([])["parsed"]
    if plan_kind != "unsupported":
        plan.update(
            status="ready",
            intent="aggregate",
            metric_id="flight_count",
            filters=[{"field_id": "origin", "operator": "eq", "value": "EWR"}],
            chart_intent="table",
            unsupported_reason=None,
        )
        if plan_kind == "full_year":
            plan["time_range"] = {"start": "2013-01-01", "end": "2013-12-31"}
        else:
            plan["filters"].append(
                {"field_id": "flight_date", "operator": "gte", "value": "2013-06-01"}
            )

    def provider_response(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "synthetic-response",
                "object": "chat.completion",
                "created": 0,
                "model": settings.model_name,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(plan),
                        },
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(provider_response)) as http_client:
        model = ChatOpenAI(
            model=settings.model_name,
            api_key="test-only",
            base_url=settings.openai_base_url,
            max_tokens=settings.max_output_tokens,
            reasoning_effort="low",
            max_retries=0,
            http_client=http_client,
        )
        client, _, _ = _client(tmp_path, settings, model)
        state = {}
        mark_disclosed(state, client.provider)
        result = client.generate_plan("Synthetic question", session_state=state)
    assert result.plan.model_dump(mode="json") == plan
    assert len(payloads) == 1
    wire_schema = payloads[0]["response_format"]["json_schema"]
    assert wire_schema["name"] == "airport_analysis_plan"
    assert wire_schema["strict"] is True
    assert "allOf" not in wire_schema["schema"]
    date_schema = wire_schema["schema"]["properties"]["time_range"]
    assert "anyOf" not in date_schema
    assert date_schema["properties"]["start"]["type"] == "string"
    assert date_schema["properties"]["end"]["type"] == "string"
    assert payloads[0]["reasoning_effort"] == "low"
