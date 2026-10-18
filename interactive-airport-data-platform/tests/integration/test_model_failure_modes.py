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


def test_adapter_logs_charge_overrun_without_private_content(tmp_path, monkeypatch, caplog):
    class ExpensiveUsageModel(FakeStructuredModel):
        def invoke(self, messages):
            result = super().invoke(messages)
            result["raw"] = SimpleNamespace(
                usage_metadata={"input_tokens": 2_000_000, "output_tokens": 2_000_000}
            )
            return result

    client, _, storage = _client(tmp_path, _hosted_settings(monkeypatch), ExpensiveUsageModel())
    state = {}
    mark_disclosed(state, client.provider)
    client.generate_plan("private-question", session_state=state)
    assert "Provider charge exceeded reservation" in caplog.text
    assert "private-question" not in caplog.text
    with pytest.raises(BudgetExceededError):
        client.generate_plan("another private-question", session_state=state)
    with storage.read() as connection:
        assert connection.execute("SELECT failure_reason FROM usage_reservations").fetchone()[
            "failure_reason"
        ]


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
        assert connection.execute("SELECT status FROM usage_reservations").fetchone()["status"] == (
            "released" if status == 429 else "reserved"
        )


class FlakyRateLimitModel(FakeStructuredModel):
    def __init__(self, failures: int, message: str, headers: dict[str, str] | None = None):
        super().__init__()
        self.failures = failures
        self.message = message
        self.headers = headers or {}

    def invoke(self, messages):
        if self.failures > 0:
            self.failures -= 1
            self.calls += 1
            response = httpx.Response(
                429,
                headers=self.headers,
                request=httpx.Request("POST", "https://api.groq.com/openai/v1"),
            )
            raise APIStatusError(self.message, response=response, body=None)
        return super().invoke(messages)


GROQ_TPM_MESSAGE = (
    "Rate limit reached for model `openai/gpt-oss-120b` on tokens per minute (TPM): "
    "Limit 8000, Used 3978, Requested 5598. Please try again in 11.82s."
)


def test_rate_limit_waits_provider_time_and_retries_once(tmp_path, monkeypatch) -> None:
    model = FlakyRateLimitModel(1, GROQ_TPM_MESSAGE)
    client, _, storage = _client(tmp_path, _groq_settings(monkeypatch), model)
    waits = []
    client._sleep = waits.append
    state = {}
    mark_disclosed(state, client.provider)

    client.generate_plan("Synthetic test question", session_state=state)

    assert model.calls == 2
    assert waits == [pytest.approx(12.32)]
    with storage.read() as connection:
        statuses = [
            row["status"]
            for row in connection.execute(
                "SELECT status FROM usage_reservations ORDER BY created_at"
            )
        ]
    assert statuses == ["released", "settled"]


def test_rate_limit_retry_header_and_second_failure_is_reported(tmp_path, monkeypatch) -> None:
    model = FlakyRateLimitModel(2, "secret-key private-question", headers={"retry-after": "7"})
    client, _, storage = _client(tmp_path, _groq_settings(monkeypatch), model)
    waits = []
    client._sleep = waits.append
    state = {}
    mark_disclosed(state, client.provider)

    with pytest.raises(ProviderError) as error:
        client.generate_plan("Synthetic test question", session_state=state)

    message = user_safe_message(error.value)
    assert model.calls == 2
    assert waits == [7.5]
    assert "HTTP 429" in message and "One automatic retry" in message
    assert "about 7 seconds" in message
    assert "secret" not in message and "private" not in message
    with storage.read() as connection:
        assert {
            row["status"] for row in connection.execute("SELECT status FROM usage_reservations")
        } == {"released"}


def test_rate_limit_with_long_or_unknown_wait_is_not_retried(tmp_path, monkeypatch) -> None:
    model = FlakyRateLimitModel(1, "Please try again in 2m5s.")
    client, _, _ = _client(tmp_path, _groq_settings(monkeypatch), model)
    client._sleep = lambda seconds: pytest.fail("must not wait beyond the bound")
    state = {}
    mark_disclosed(state, client.provider)

    with pytest.raises(ProviderError) as error:
        client.generate_plan("Synthetic test question", session_state=state)

    assert model.calls == 1
    assert "about 2 minutes" in user_safe_message(error.value)


def test_daily_token_limit_is_reported_as_daily_without_waiting(tmp_path, monkeypatch) -> None:
    model = FlakyRateLimitModel(
        1,
        "Rate limit reached for model `openai/gpt-oss-20b` on tokens per day (TPD): "
        "Limit 200000, Used 196513, Requested 5263. Please try again in 12m47.232s.",
    )
    client, _, storage = _client(tmp_path, _groq_settings(monkeypatch), model)
    client._sleep = lambda seconds: pytest.fail("must not wait for a daily reset")
    state = {}
    mark_disclosed(state, client.provider)

    with pytest.raises(ProviderError) as error:
        client.generate_plan("Synthetic test question", session_state=state)

    message = user_safe_message(error.value)
    assert model.calls == 1
    assert "daily limit" in message and "per minute" not in message
    assert "about 13 minutes" in message and "daily limits apply per model" in message
    with storage.read() as connection:
        assert connection.execute("SELECT status FROM usage_reservations").fetchone()["status"] == (
            "released"
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


def test_v2_clarification_rechecks_disclosure_and_has_no_hidden_invalid_output_repair(
    tmp_path,
    monkeypatch,
):
    from airport_analytics.errors import InvalidPlanError
    from tests.integration.test_exploration_provider import IntentModel, client_for
    from tests.unit.test_exploration_state import ambiguous

    model = IntentModel(payload={"intent_version": 2, "private": "invalid body"})
    client, storage = client_for(tmp_path, monkeypatch, model)
    with pytest.raises(DisclosureRequiredError):
        client.generate_clarification(
            "private question",
            "private answer",
            ambiguous(),
            1,
            session_state={},
        )
    assert model.calls == 0
    state = {}
    mark_disclosed(state, client.provider)
    with pytest.raises(InvalidPlanError):
        client.generate_clarification(
            "private question",
            "private answer",
            ambiguous(),
            1,
            session_state=state,
        )
    assert model.calls == 1
    with storage.read() as connection:
        rows = connection.execute("SELECT status FROM usage_reservations").fetchall()
        assert len(rows) == 1
        assert rows[0]["status"] == "settled"


class ReadyPlanModel(FakeStructuredModel):
    def invoke(self, messages):
        result = super().invoke(messages)
        result["parsed"].update(
            status="ready",
            intent="aggregate",
            metric_id="flight_count",
            chart_intent="table",
            unsupported_reason=None,
        )
        return result


@pytest.mark.parametrize(
    ("value", "seconds"),
    [("7.66s", 7.66), ("2m59.56s", 179.56), ("120ms", 0.12), ("12", 12.0), ("1h", 3600.0)],
)
def test_rate_limit_reset_durations_are_parsed(value, seconds) -> None:
    from airport_analytics.analytics.model_client import _duration_seconds

    assert _duration_seconds(value) == pytest.approx(seconds)


@pytest.mark.parametrize("value", [None, "", "soon", "5x", "-3"])
def test_unparseable_reset_durations_are_ignored(value) -> None:
    from airport_analytics.analytics.model_client import _duration_seconds

    assert _duration_seconds(value) is None


def test_token_pacer_waits_only_for_the_missing_refill() -> None:
    from airport_analytics.analytics.model_client import TokenRatePacer

    now = [0.0]
    pacer = TokenRatePacer(clock=lambda: now[0])
    key = ("groq", "openai/gpt-oss-120b")
    assert pacer.wait_seconds(key, 5000) == 0.0
    pacer.observe(
        key,
        {
            "X-RateLimit-Limit-Tokens": "8000",
            "X-RateLimit-Remaining-Tokens": "2000",
            "X-RateLimit-Reset-Tokens": "45s",
        },
    )
    # 6000 missing tokens refill over 45s (133.3/s); 3000 more are needed.
    assert pacer.wait_seconds(key, 5000) == pytest.approx(22.5)
    assert pacer.wait_seconds(key, 1500) == 0.0
    assert pacer.wait_seconds(key, 50_000) == pytest.approx(45.0)
    now[0] = 30.0
    assert pacer.wait_seconds(key, 5000) == 0.0
    assert pacer.wait_seconds(("groq", "openai/gpt-oss-20b"), 5000) == 0.0
    pacer.observe(key, {"x-ratelimit-remaining-tokens": "garbage"})
    assert pacer.wait_seconds(key, 5000) == 0.0


def test_groq_headers_pace_next_call_and_cached_tokens_are_recorded(tmp_path, monkeypatch) -> None:
    from langchain_openai import ChatOpenAI

    from airport_analytics.analytics.model_client import TokenRatePacer

    settings = _groq_settings(monkeypatch)
    plan = FakeStructuredModel().invoke([])["parsed"]
    payloads = []

    def provider_response(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={
                "x-ratelimit-limit-tokens": "8000",
                "x-ratelimit-remaining-tokens": "1000",
                "x-ratelimit-reset-tokens": "52.5s",
            },
            json={
                "id": "synthetic-response",
                "object": "chat.completion",
                "created": 0,
                "model": settings.model_name,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(plan)},
                    }
                ],
                "usage": {
                    "prompt_tokens": 4951,
                    "completion_tokens": 300,
                    "total_tokens": 5251,
                    "prompt_tokens_details": {"cached_tokens": 4608},
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(provider_response)) as http_client:
        model = ChatOpenAI(
            model=settings.model_name,
            api_key="test-only",
            base_url=settings.openai_base_url,
            max_tokens=settings.max_output_tokens,
            max_retries=0,
            include_response_headers=True,
            http_client=http_client,
        )
        storage = Storage(tmp_path / "budget.sqlite3")
        budget = BudgetLedger(storage, monthly_cap_usd=settings.deployment_monthly_budget_usd)
        client = LangChainPlanClient(
            settings, budget=budget, model=model, rate_pacer=TokenRatePacer(clock=lambda: 0.0)
        )
        waits = []
        client._sleep = waits.append
        state = {}
        mark_disclosed(state, client.provider)
        first = client.generate_plan("Synthetic question one", session_state=state)
        assert waits == []
        client.generate_plan("Synthetic question two", session_state=state)

    assert first.usage.cached_input_tokens == 4608
    assert len(payloads) == 2
    assert len(waits) == 1 and 0.25 < waits[0] <= 30.25
    with storage.read() as connection:
        cached = [
            row["cached_input_tokens"]
            for row in connection.execute("SELECT cached_input_tokens FROM usage_reservations")
        ]
    assert cached == [4608, 4608]


def test_pacer_does_not_block_beyond_the_bounded_wait(tmp_path, monkeypatch) -> None:
    from airport_analytics.analytics.model_client import TokenRatePacer

    pacer = TokenRatePacer(clock=lambda: 0.0)
    model = FakeStructuredModel()
    client, _, _ = _client(tmp_path, _groq_settings(monkeypatch), model)
    client._rate_pacer = pacer
    pacer.observe(
        client._rate_key,
        {
            "x-ratelimit-limit-tokens": "2000",
            "x-ratelimit-remaining-tokens": "0",
            "x-ratelimit-reset-tokens": "59s",
        },
    )
    client._sleep = lambda seconds: pytest.fail("must not wait beyond the bound")
    state = {}
    mark_disclosed(state, client.provider)
    client.generate_plan("Synthetic test question", session_state=state)
    assert model.calls == 1


def test_identical_ready_interpretation_is_reused_without_a_provider_call(
    tmp_path, monkeypatch
) -> None:
    from airport_analytics.analytics.model_client import InterpretationCache

    now = [0.0]
    model = ReadyPlanModel()
    settings = _groq_settings(monkeypatch)
    storage = Storage(tmp_path / "budget.sqlite3")
    budget = BudgetLedger(storage, monthly_cap_usd=settings.deployment_monthly_budget_usd)
    client = LangChainPlanClient(
        settings,
        budget=budget,
        model=model,
        interpretation_cache=InterpretationCache(ttl_seconds=3600, clock=lambda: now[0]),
    )
    state = {}
    mark_disclosed(state, client.provider)

    first = client.generate_plan("How many flights?", session_state=state)
    second = client.generate_plan("How many flights?", session_state=state)

    assert model.calls == 1
    assert second.plan == first.plan
    assert second.usage.input_tokens == 0 and second.budget_reservation_id is None
    with pytest.raises(DisclosureRequiredError):
        client.generate_plan("How many flights?", session_state={})
    client.generate_plan("How many flights from JFK?", session_state=state)
    assert model.calls == 2
    now[0] = 3601.0
    client.generate_plan("How many flights?", session_state=state)
    assert model.calls == 3
    with storage.read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM usage_reservations").fetchone()[0] == 3


def test_unsuccessful_interpretations_are_not_reused(tmp_path, monkeypatch) -> None:
    from airport_analytics.analytics.model_client import InterpretationCache

    model = FakeStructuredModel()
    settings = _groq_settings(monkeypatch)
    storage = Storage(tmp_path / "budget.sqlite3")
    budget = BudgetLedger(storage, monthly_cap_usd=settings.deployment_monthly_budget_usd)
    client = LangChainPlanClient(
        settings, budget=budget, model=model, interpretation_cache=InterpretationCache()
    )
    state = {}
    mark_disclosed(state, client.provider)
    client.generate_plan("Unsupported question", session_state=state)
    client.generate_plan("Unsupported question", session_state=state)
    assert model.calls == 2


def test_injected_models_do_not_share_the_process_interpretation_cache(
    tmp_path, monkeypatch
) -> None:
    client, _, _ = _client(tmp_path, _groq_settings(monkeypatch), ReadyPlanModel())
    assert client._interpretation_cache is None
