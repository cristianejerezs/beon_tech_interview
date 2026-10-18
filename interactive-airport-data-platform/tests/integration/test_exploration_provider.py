import json
from dataclasses import replace

import httpx
import pytest
from jsonschema import Draft202012Validator
from langchain_openai import ChatOpenAI

from airport_analytics.analytics.budget import BudgetLedger
from airport_analytics.analytics.model_client import LangChainPlanClient, _groq_output_schema
from airport_analytics.analytics.provider_policy import mark_disclosed
from airport_analytics.errors import (
    BudgetExceededError,
    DisclosureRequiredError,
    InvalidPlanError,
    ProviderError,
)
from airport_analytics.models import ResolvedInterpretation
from airport_analytics.storage import Storage
from tests.integration.test_model_failure_modes import FakeStructuredModel, _hosted_settings
from tests.unit.test_exploration_contracts import proposed_section
from tests.unit.test_exploration_results import scalar_report_payload


class IntentModel(FakeStructuredModel):
    def __init__(self, *, payload=None, failure=None):
        super().__init__(failure=failure)
        self.payload = payload or {
            "intent_version": 2,
            "status": "proposed",
            "shared_scope": {"edits": [], "dates": None},
            "sections": [proposed_section()],
            "selection_reason": None,
        }

    def invoke(self, messages):
        response = super().invoke(messages)
        self.messages = messages
        response["parsed"] = self.payload
        return response


def client_for(tmp_path, monkeypatch, model, *, provider="openai", budget="1.00"):
    settings = replace(_hosted_settings(monkeypatch, budget=budget), max_input_tokens=100000)
    if provider == "groq":
        settings = replace(
            settings,
            model_provider="groq",
            model_name="openai/gpt-oss-20b",
            openai_base_url="https://api.groq.com/openai/v1",
            hosted_free_plan=True,
        )
    if provider == "ollama":
        settings = replace(settings, model_provider="ollama", model_name="local")
    storage = Storage(tmp_path / "budget.sqlite")
    client = LangChainPlanClient(
        settings, budget=BudgetLedger(storage), model=model, contract_version=2
    )
    return client, storage


@pytest.mark.parametrize("provider", ["ollama", "openai", "groq"])
def test_projection_validates_examples_and_dispatches_once(tmp_path, monkeypatch, provider):
    model = IntentModel()
    client, _ = client_for(tmp_path, monkeypatch, model, provider=provider)
    Draft202012Validator.check_schema(model.output_schema)
    Draft202012Validator(model.output_schema).validate(model.payload)
    state = {}
    mark_disclosed(state, client.provider)
    assert client.generate_intent("Count flights", session_state=state).proposal.intent_version == 2
    assert model.calls == 1
    assert "$ref" not in json.dumps(model.output_schema)
    assert "allOf" not in model.output_schema
    assert client.contract_version == 2
    with pytest.raises(ValueError):
        client.generate_plan("Count flights", session_state=state)


def test_groq_120b_uses_existing_schema_budget_and_model_specific_disclosure(tmp_path, monkeypatch):
    from airport_analytics.analytics.provider_policy import ProviderDescriptor

    model = IntentModel()
    original, storage = client_for(tmp_path, monkeypatch, model, provider="groq")
    original_schema = model.output_schema
    settings = replace(original.settings, model_name="openai/gpt-oss-120b")
    client = LangChainPlanClient(
        settings,
        budget=BudgetLedger(storage),
        model=model,
        contract_version=2,
    )
    assert client.provider.model_id == "openai/gpt-oss-120b"
    assert model.output_schema == original_schema
    state = {}
    mark_disclosed(
        state,
        ProviderDescriptor(
            "groq",
            "openai/gpt-oss-20b",
            client.provider.product_improvement_terms,
        ),
    )
    with pytest.raises(DisclosureRequiredError):
        client.generate_intent("Count flights", session_state=state)
    assert model.calls == 0
    mark_disclosed(state, client.provider)
    assert client.generate_intent("Count flights", session_state=state).proposal.intent_version == 2
    assert model.calls == 1


@pytest.mark.parametrize("provider", ["groq", "openai", "ollama"])
def test_prompt_deduplication_preserves_catalog_semantics_and_schema_constraints(
    tmp_path,
    monkeypatch,
    provider,
):
    from airport_analytics.analytics.model_client import _intent_output_schema

    model = IntentModel()
    client, _ = client_for(tmp_path, monkeypatch, model, provider=provider)
    before = _intent_output_schema(client.schema, groq=provider == "groq")
    before["title"] = "airport_intent_v2"

    def without_titles(node):
        if isinstance(node, list):
            return [without_titles(item) for item in node]
        if not isinstance(node, dict):
            return node
        return {key: without_titles(value) for key, value in node.items() if key != "title"}

    assert without_titles(before) == without_titles(model.output_schema)
    assert model.output_schema["title"] == "airport_intent_v2"
    messages = client._intent_messages("Synthetic request", None)
    system = str(messages[0].content)
    if provider == "ollama":
        assert model.output_schema == before
        assert system.endswith(" Schema: " + client._schema_json)
    else:
        assert " Schema: " not in system
        assert client._schema_json not in system
        assert "schema is supplied separately in response_format" in system
        assert (
            without_titles(model.output_schema["properties"]) == model.output_schema["properties"]
        )
    assert "Catalog: " in system
    assert " Definitions: " in system
    assert "Complete clarification-envelope example" in system
    assert "A singular unnamed 'the airport' requires clarification" in system
    assert "population=airport_connections" in system
    assert model.calls == 0


def test_hosted_v2_token_reduction_exceeds_thirty_percent_without_reducing_safety_allowance(
    tmp_path,
    monkeypatch,
):
    import tiktoken
    from langchain_core.messages import SystemMessage

    from airport_analytics.analytics.model_client import _intent_output_schema

    client, _ = client_for(tmp_path, monkeypatch, IntentModel(), provider="groq")
    messages = client._intent_messages(
        "Determine the number of distinct destinations connected to the airport.",
        None,
    )
    previous_schema = _intent_output_schema(client.schema, groq=True)
    previous_schema["title"] = "airport_intent_v2"
    previous_json = json.dumps(previous_schema, separators=(",", ":"))
    previous_system = (
        str(messages[0].content).removesuffix(
            " The output JSON schema is supplied separately in response_format."
        )
        + " Schema: "
        + previous_json
    )
    encoding = tiktoken.get_encoding("o200k_harmony")
    previous_total = (
        sum(
            len(encoding.encode(str(message.content), disallowed_special=()))
            for message in [SystemMessage(content=previous_system), messages[1]]
        )
        + len(encoding.encode(previous_json))
        + 1024
        + 64
    )
    current_total = client._count_prompt_tokens(messages)
    assert current_total <= previous_total * 0.70
    assert current_total == (
        sum(
            len(encoding.encode(str(message.content), disallowed_special=()))
            for message in messages
        )
        + len(encoding.encode(client._schema_json))
        + 1024
        + 64
    )


def test_disclosure_and_budget_gate_v2_before_dispatch(tmp_path, monkeypatch):
    model = IntentModel()
    client, storage = client_for(tmp_path, monkeypatch, model, budget="0")
    with pytest.raises(DisclosureRequiredError):
        client.generate_intent("private wording", session_state={})
    state = {}
    mark_disclosed(state, client.provider)
    # Use the configured zero cap rather than BudgetLedger's default cap.
    client.budget = BudgetLedger(
        storage, monthly_cap_usd=client.settings.deployment_monthly_budget_usd
    )
    with pytest.raises(BudgetExceededError):
        client.generate_intent("private wording", session_state=state)
    assert model.calls == 0
    with storage.read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM usage_reservations").fetchone()[0] == 0


def test_invalid_intent_has_no_repair_or_fallback_call(tmp_path, monkeypatch):
    model = IntentModel(
        payload={
            "intent_version": 2,
            "status": "proposed",
            "shared_scope": {},
            "sections": [proposed_section(operation_id="execute_sql")],
            "selection_reason": None,
        }
    )
    client, storage = client_for(tmp_path, monkeypatch, model)
    state = {}
    mark_disclosed(state, client.provider)
    with pytest.raises(InvalidPlanError):
        client.generate_intent("private wording", session_state=state)
    assert model.calls == 1
    with storage.read() as connection:
        assert (
            connection.execute("SELECT status FROM usage_reservations").fetchone()[0] == "settled"
        )


def test_v2_uncertain_failure_preserves_reservation_and_redacts_logs(tmp_path, monkeypatch, caplog):
    model = IntentModel(failure=TimeoutError("raw secret provider body"))
    client, storage = client_for(tmp_path, monkeypatch, model)
    state = {}
    mark_disclosed(state, client.provider)
    with pytest.raises(ProviderError):
        client.generate_intent("private wording", session_state=state)
    assert model.calls == 1
    assert "raw secret provider body" not in caplog.text
    assert "private wording" not in caplog.text
    with storage.read() as connection:
        assert (
            connection.execute("SELECT status FROM usage_reservations").fetchone()[0] == "reserved"
        )


def test_v2_context_contains_only_active_semantics_not_saved_identity(tmp_path, monkeypatch):
    model = IntentModel()
    client, _ = client_for(tmp_path, monkeypatch, model, provider="ollama")
    payload = scalar_report_payload()["sections"][0]["interpretation"]
    payload.update(
        request_id="secret-request-id",
        section_id="secret-section-id",
        original_clause="private previous wording",
    )
    active = ResolvedInterpretation.model_validate(payload)
    client.generate_intent("By origin instead", session_state={}, follow_up_context=active)
    messages = " ".join(str(message.content) for message in model.messages)
    for private in [
        "secret-request-id",
        "secret-section-id",
        "private previous wording",
        "a" * 64,
        "b" * 64,
    ]:
        assert private not in messages
    context = json.loads(model.messages[1].content)["active_follow_up_context"]
    assert context["measure_ids"] == ["flight_count"]
    assert not {"snapshot_id", "context_id", "request_id", "original_clause"} & context.keys()


def test_composite_is_a_single_provider_call(tmp_path, monkeypatch):
    sections = [proposed_section(position=position) for position in range(1, 5)]
    model = IntentModel(
        payload={
            "intent_version": 2,
            "status": "proposed",
            "shared_scope": {},
            "sections": sections,
            "selection_reason": None,
        }
    )
    client, _ = client_for(tmp_path, monkeypatch, model, provider="ollama")
    result = client.generate_intent("Four requested analyses", session_state={})
    assert len(result.proposal.sections) == 4
    assert model.calls == 1


def test_weather_correlation_prompt_uses_one_fixed_panel_not_extra_measures(tmp_path, monkeypatch):
    model = IntentModel()
    model.payload["sections"] = [
        proposed_section(
            family="numeric_relationship",
            operation_id="weather_relationship",
            measure_ids=["mean_departure_delay"],
            grouping=[],
            pairing=None,
        )
    ]
    client, _ = client_for(tmp_path, monkeypatch, model, provider="groq")
    state = {}
    mark_disclosed(state, client.provider)
    result = client.generate_intent(
        "Analyze the correlation between departure delay and weather conditions by "
        "cross-referencing the departure delay data with the weather dataset.",
        session_state=state,
    )
    assert len(result.proposal.sections) == 1
    assert result.proposal.sections[0].measure_ids == ["mean_departure_delay"]
    system = str(model.messages[0].content)
    assert "operation_id=weather_relationship" in system
    assert "measure_ids=[mean_departure_delay]" in system
    assert "temp, wind_speed, precip and visib" in system
    assert "NOT extra measure_ids" in system
    fields = model.output_schema["properties"]["sections"]["items"]["properties"]
    assert "Set null for weather_relationship" in fields["pairing"]["description"]
    assert 'exactly ["mean_departure_delay"]' in fields["measure_ids"]["description"]
    invalid = model.payload | {
        "sections": [
            proposed_section(
                family="numeric_relationship",
                operation_id="weather_relationship",
                measure_ids=["mean_departure_delay", "departure_delay", "distance"],
            )
        ]
    }
    with pytest.raises(InvalidPlanError):
        client._validate_intent_payload(invalid)
    invalid_pairing = model.payload | {
        "sections": [
            proposed_section(
                family="numeric_relationship",
                operation_id="weather_relationship",
                measure_ids=["mean_departure_delay"],
                pairing={"x": "departure_delay", "y": "weather_precipitation_band"},
            )
        ]
    }
    with pytest.raises(InvalidPlanError):
        client._validate_intent_payload(invalid_pairing)
    assert model.calls == 1


@pytest.mark.parametrize(
    "question,grouping",
    [
        ("Identify the month with the highest accumulated departure delay.", "flight_month"),
        (
            "Identify the month of the year with the highest accumulated departure delay "
            "for all years",
            "month_of_year",
        ),
    ],
)
def test_accumulated_delay_prompt_maps_to_monthly_total_ranking_and_retains_sections(
    tmp_path,
    monkeypatch,
    question,
    grouping,
):
    model = IntentModel()
    model.payload["sections"] = [
        proposed_section(
            family="ranking",
            operation_id="departure_delay_total",
            measure_ids=["positive_delay_minutes"],
            grouping=[grouping],
            order={"field_id": "positive_delay_minutes", "direction": "desc"},
            bound=1,
        )
    ]
    client, _ = client_for(tmp_path, monkeypatch, model, provider="groq")
    state = {}
    mark_disclosed(state, client.provider)
    result = client.generate_intent(
        question,
        session_state=state,
    )
    assert result.proposal.sections[0].operation_id == "departure_delay_total"
    assert result.proposal.sections[0].grouping == [grouping]
    prompt = str(model.messages[0].content)
    assert "Accumulated/total departure delay means operation_id=departure_delay_total" in prompt
    assert "grouping=[flight_month]" in prompt
    assert "grouping=[month_of_year]" in prompt
    assert "January through December pooled across scoped years" in prompt
    assert "bound=1" in prompt
    assert "sections must contain 1..4 section objects, never []" in prompt
    invalid = model.payload | {"sections": []}
    with pytest.raises(InvalidPlanError):
        client._validate_intent_payload(invalid)
    assert model.calls == 1


@pytest.mark.parametrize("provider", ["ollama", "openai", "groq"])
def test_airport_connection_population_is_a_closed_provider_supported_listing(
    tmp_path,
    monkeypatch,
    provider,
):
    model = IntentModel()
    model.payload["sections"] = [
        proposed_section(
            family="unique_entity_list",
            operation_id="entity_list",
            measure_ids=[],
            population="airport_connections",
            order={"field_id": "connection_count", "direction": "desc"},
        )
    ]
    client, _ = client_for(tmp_path, monkeypatch, model, provider=provider)
    Draft202012Validator(model.output_schema).validate(model.payload)
    state = {}
    mark_disclosed(state, client.provider)
    result = client.generate_intent(
        "For all catalogue airports count distinct connections across arrivals and departures",
        session_state=state,
    )
    assert result.proposal.sections[0].population == "airport_connections"
    assert "population=airport_connections" in str(model.messages[0].content)
    assert model.calls == 1


def test_groq_filter_value_unions_do_not_overlap_integer_and_number(tmp_path, monkeypatch):
    model = IntentModel()
    client, _ = client_for(tmp_path, monkeypatch, model, provider="groq")

    def check_unions(node):
        if isinstance(node, dict):
            branches = node.get("anyOf", [])
            types = [branch.get("type") for branch in branches]
            assert not ("integer" in types and "number" in types)
            assert len(types) == len(set(types))
            for value in node.values():
                check_unions(value)
        elif isinstance(node, list):
            for value in node:
                check_unions(value)

    check_unions(model.output_schema)
    value_schema = model.output_schema["properties"]["sections"]["items"]["properties"][
        "scope_edits"
    ]["items"]["properties"]["value"]
    validator = Draft202012Validator(value_schema)
    for value in [None, "JFK", 2013, 1.5, ["JFK", 2013, 1.5, None]]:
        assert validator.is_valid(value)
    for value in [True, {"sql": "SELECT 1"}]:
        assert not validator.is_valid(value)
    # Provider projection must not weaken the authoritative local contract.
    local_value = client.schema["$defs"]["ScopeEdit"]["properties"]["value"]
    assert {"integer", "number"} <= {branch.get("type") for branch in local_value["anyOf"]}


def test_groq_numeric_union_projection_is_equivalent_and_idempotent():
    schema = {
        "anyOf": [
            {"type": "integer"},
            {"type": "number"},
            {"type": "string"},
            {"type": "null"},
        ],
    }
    projected = _groq_output_schema(schema)
    assert projected == {
        "anyOf": [{"type": "number"}, {"type": "string"}, {"type": "null"}],
    }
    assert _groq_output_schema(projected) == projected
    original = Draft202012Validator(schema)
    wire = Draft202012Validator(projected)
    for value in [0, -1, 1.25, "JFK", None, True, [], {}]:
        assert original.is_valid(value) == wire.is_valid(value)


def test_groq_string_enum_branches_merge_without_widening_valid_values():
    schema = {
        "anyOf": [
            {"type": "string", "enum": ["origin", "carrier"]},
            {"type": "string", "enum": ["flight_count", "origin"]},
            {"type": "null"},
        ],
    }
    projected = _groq_output_schema(schema)
    assert projected == {
        "anyOf": [
            {"type": "string", "enum": ["origin", "carrier", "flight_count"]},
            {"type": "null"},
        ],
    }
    assert _groq_output_schema(projected) == projected
    for value in ["origin", "carrier", "flight_count", "execute_sql", None, 1]:
        assert Draft202012Validator(schema).is_valid(value) == Draft202012Validator(
            projected
        ).is_valid(value)


def test_groq_clarification_prompt_teaches_required_null_envelope(tmp_path, monkeypatch):
    from airport_analytics.analytics.plan_schema import validate_intent_proposal

    model = IntentModel()
    client, _ = client_for(tmp_path, monkeypatch, model, provider="groq")
    system = str(
        client._intent_messages(
            "Determine the number of distinct destinations connected to the airport.", None
        )[0].content
    )
    marker = "Complete clarification-envelope example (illustrative, not the analyst's request): "
    example = json.loads(system.split(marker, 1)[1].split(" Catalog: ", 1)[0])
    assert "Required nullable fields must be present with JSON null, never omitted" in system
    assert "Set selection_reason=null unless status=requires_selection" in system
    assert example["selection_reason"] is None
    assert validate_intent_proposal(example).status == "needs_clarification"
    validator = Draft202012Validator(model.output_schema)
    validator.validate(example)
    # Reproduce the structural defect observed in the authorized Groq response.
    omitted = {key: value for key, value in example.items() if key != "selection_reason"}
    assert validator.is_valid(omitted)
    with pytest.raises(InvalidPlanError):
        validate_intent_proposal(omitted)
    assert model.calls == 0


@pytest.mark.parametrize("status", ["proposed", "needs_clarification", "unsupported"])
def test_groq_normalizes_only_unused_reason_after_full_local_validation(
    tmp_path,
    monkeypatch,
    caplog,
    status,
):
    section = proposed_section(status=status)
    if status == "needs_clarification":
        section["clarification"] = {
            "field_id": "origin",
            "question": "Which airport?",
            "choices": [],
        }
    elif status == "unsupported":
        section["unsupported_reason"] = "Unavailable concept"
    payload = {
        "intent_version": 2,
        "status": status,
        "shared_scope": {"edits": [], "dates": None},
        "sections": [section],
    }
    model = IntentModel(payload=payload)
    client, _ = client_for(tmp_path, monkeypatch, model, provider="groq")
    state = {}
    mark_disclosed(state, client.provider)
    with caplog.at_level("INFO"):
        result = client.generate_intent("Synthetic request", session_state=state)
    assert result.proposal.selection_reason is None
    assert result.proposal.status == status
    assert "normalized absent unused selection_reason" in caplog.text
    assert "selection_reason" not in payload
    assert model.calls == 1


@pytest.mark.parametrize("provider", ["groq", "openai", "ollama"])
@pytest.mark.parametrize(
    "defect", ["selection_required", "other_missing", "extra", "invalid_measure"]
)
def test_compatibility_does_not_repair_invalid_analytical_payloads(
    tmp_path,
    monkeypatch,
    provider,
    defect,
):
    payload = IntentModel().payload
    payload.pop("selection_reason")
    if defect == "selection_required":
        payload.update(status="requires_selection", sections=[])
    elif defect == "other_missing":
        payload.pop("shared_scope")
    elif defect == "extra":
        payload["sql"] = "not allowed"
    else:
        payload["sections"][0]["measure_ids"] = ["invented_measure"]
    model = IntentModel(payload=payload)
    client, _ = client_for(tmp_path, monkeypatch, model, provider=provider)
    state = {}
    mark_disclosed(state, client.provider)
    with pytest.raises(InvalidPlanError):
        client.generate_intent("Synthetic request", session_state=state)
    assert model.calls == 1


@pytest.mark.parametrize("provider", ["openai", "ollama"])
def test_other_providers_still_require_explicit_selection_reason(tmp_path, monkeypatch, provider):
    payload = IntentModel().payload
    payload.pop("selection_reason")
    model = IntentModel(payload=payload)
    client, _ = client_for(tmp_path, monkeypatch, model, provider=provider)
    assert not Draft202012Validator(model.output_schema).is_valid(payload)
    state = {}
    mark_disclosed(state, client.provider)
    with pytest.raises(InvalidPlanError):
        client.generate_intent("Synthetic request", session_state=state)


def test_real_groq_v2_adapter_sends_disjoint_wire_schema_and_validates_response(
    tmp_path,
    monkeypatch,
):
    payloads = []
    intent = IntentModel().payload
    intent["sections"][0]["scope_edits"] = [
        {"field_id": "flight_year", "action": "add", "operator": "in", "value": [2013, 2014]},
    ]

    def provider_response(request):
        payload = json.loads(request.content)
        payloads.append(payload)
        wire = payload["response_format"]["json_schema"]
        assert wire["strict"] is False
        assert "selection_reason" not in wire["schema"]["required"]
        assert wire["name"] == "airport_intent_v2"
        fields = wire["schema"]["properties"]["sections"]["items"]["properties"]
        numeric_types = [
            branch["type"]
            for branch in fields["scope_edits"]["items"]["properties"]["value"]["anyOf"]
        ]
        assert "number" in numeric_types
        assert "integer" not in numeric_types
        order = next(branch for branch in fields["order"]["anyOf"] if branch["type"] == "object")
        field_id = order["properties"]["field_id"]
        assert len(field_id["anyOf"]) == 1
        assert "source_row_id" in field_id["anyOf"][0]["enum"]
        Draft202012Validator(wire["schema"]).validate(intent)
        return httpx.Response(
            200,
            json={
                "id": "synthetic-response",
                "object": "chat.completion",
                "created": 0,
                "model": "openai/gpt-oss-20b",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    key: value
                                    for key, value in intent.items()
                                    if key != "selection_reason"
                                }
                            ),
                        },
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(provider_response)) as transport:
        model = ChatOpenAI(
            model="openai/gpt-oss-20b",
            api_key="test-only",
            base_url="https://api.groq.com/openai/v1",
            max_retries=0,
            http_client=transport,
        )
        client, _ = client_for(tmp_path, monkeypatch, model, provider="groq")
        state = {}
        mark_disclosed(state, client.provider)
        result = client.generate_intent("Count flights in 2013 and 2014", session_state=state)
    assert result.proposal.model_dump(mode="json") == intent
    assert len(payloads) == 1
