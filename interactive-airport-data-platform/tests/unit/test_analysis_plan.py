from copy import deepcopy

import pytest

from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.errors import InvalidPlanError


def ready_plan() -> dict:
    return {
        "status": "ready",
        "intent": "aggregate",
        "metric_id": "mean_departure_delay",
        "group_by": ["carrier"],
        "filters": [],
        "time_range": None,
        "sort": None,
        "row_limit": 50,
        "chart_intent": "bar",
        "clarification_question": None,
        "unsupported_reason": None,
    }


def test_valid_plan_matches_schema_and_catalog() -> None:
    plan = validate_analysis_plan(ready_plan())
    assert plan.metric_id == "mean_departure_delay"
    assert plan.group_by == ["carrier"]


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ("metric_id", "arbitrary_sql"),
        ("group_by", ["users"]),
        (
            "filters",
            [{"field_id": "carrier", "operator": "drop table", "value": "UA"}],
        ),
        ("row_limit", 501),
        ("unexpected_property", "SELECT * FROM flights"),
    ],
)
def test_schema_rejects_unapproved_plan_shapes(change: str, value: object) -> None:
    plan = ready_plan()
    if change == "unexpected_property":
        plan[change] = value
    else:
        plan[change] = value
    with pytest.raises(InvalidPlanError):
        validate_analysis_plan(plan)


def test_catalog_rejects_wrong_filter_value_type() -> None:
    plan = ready_plan()
    plan["filters"] = [{"field_id": "carrier", "operator": "eq", "value": 7}]
    with pytest.raises(InvalidPlanError):
        validate_analysis_plan(plan)


def test_catalog_rejects_metric_incompatible_dimension() -> None:
    plan = ready_plan()
    plan["metric_id"] = "distinct_destination_count"
    plan["group_by"] = ["aircraft_model"]
    with pytest.raises(InvalidPlanError):
        validate_analysis_plan(plan)


def test_clarification_and_unsupported_outcomes_are_not_ready_queries() -> None:
    clarification = ready_plan()
    clarification.update(
        status="needs_clarification",
        intent=None,
        metric_id=None,
        clarification_question="Which period do you mean?",
    )
    unsupported = deepcopy(clarification)
    unsupported.update(
        status="unsupported",
        clarification_question=None,
        unsupported_reason="The requested field is not available.",
    )
    assert validate_analysis_plan(clarification).status == "needs_clarification"
    assert validate_analysis_plan(unsupported).status == "unsupported"
