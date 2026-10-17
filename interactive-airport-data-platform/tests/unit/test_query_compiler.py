from copy import deepcopy

import pytest

from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.analytics.query_compiler import compile_analysis_plan
from airport_analytics.errors import InvalidPlanError
from airport_analytics.models import AnalysisPlan


def base_plan() -> dict:
    return {
        "status": "ready",
        "intent": "aggregate",
        "metric_id": "flight_count",
        "group_by": ["carrier"],
        "filters": [],
        "time_range": None,
        "sort": None,
        "row_limit": 50,
        "chart_intent": "table",
        "clarification_question": None,
        "unsupported_reason": None,
    }


def test_compiler_emits_only_parameterized_select_and_limit() -> None:
    plan = validate_analysis_plan(base_plan())
    compiled = compile_analysis_plan(plan)
    assert compiled.sql.startswith("SELECT ")
    assert " LIMIT ?" in compiled.sql
    assert "flight_count" in compiled.sql
    assert compiled.parameters == (50,)


def test_injection_shaped_filter_is_bound_as_data() -> None:
    plan = base_plan()
    payload = "UA' OR 1=1; DROP TABLE flights;--"
    plan["filters"] = [{"field_id": "carrier", "operator": "eq", "value": payload}]
    compiled = compile_analysis_plan(validate_analysis_plan(plan))
    assert payload not in compiled.sql
    assert compiled.parameters == (payload, 50)
    assert compiled.sql.startswith("SELECT ")
    assert "DROP TABLE" not in compiled.sql


def test_model_sql_is_rejected_as_a_plan() -> None:
    with pytest.raises(InvalidPlanError):
        validate_analysis_plan("SELECT * FROM flights")


def test_unknown_identifiers_never_compile() -> None:
    plan = base_plan()
    plan["group_by"] = ["secret_table"]
    with pytest.raises(InvalidPlanError):
        validate_analysis_plan(plan)


def test_compiler_revalidates_manually_constructed_model() -> None:
    plan_data = deepcopy(base_plan())
    plan_data["group_by"] = ["not_in_catalog"]
    plan = AnalysisPlan.model_validate(plan_data)
    with pytest.raises(InvalidPlanError):
        compile_analysis_plan(plan)
