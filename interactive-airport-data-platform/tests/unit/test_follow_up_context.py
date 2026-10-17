import json

from langchain_core.messages import HumanMessage, SystemMessage

from airport_analytics.analytics.model_client import FollowUpContext, LangChainPlanClient
from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.config import Settings


def test_follow_up_context_contains_only_prior_question_and_validated_plan(monkeypatch) -> None:
    previous_plan = validate_analysis_plan(
        {
            "status": "ready",
            "intent": "aggregate",
            "metric_id": "mean_departure_delay",
            "group_by": [],
            "filters": [{"field_id": "origin", "operator": "eq", "value": "EWR"}],
            "time_range": None,
            "sort": None,
            "row_limit": 1,
            "chart_intent": "table",
            "clarification_question": None,
            "unsupported_reason": None,
        }
    )
    context = FollowUpContext("Mean delay for EWR.", previous_plan)
    client = object.__new__(LangChainPlanClient)
    monkeypatch.setenv("AIRPORT_MODEL_PROVIDER", "ollama")
    client.settings = Settings.from_env(load_file=False)
    client._catalog_json = "{}"
    client._schema_json = "{}"
    messages = client._messages("How about JFK?", context)
    assert all(isinstance(item, (SystemMessage, HumanMessage)) for item in messages)
    human_payload = json.loads(messages[1].content)
    assert human_payload["question"] == "How about JFK?"
    assert human_payload["active_follow_up_context"]["previous_question"] == ("Mean delay for EWR.")
    assert "private report history" not in json.dumps(human_payload).lower()
    assert "analyst_id" not in json.dumps(human_payload)
