from pathlib import Path

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.errors import InvalidPlanError

WORKSPACE = Path(__file__).resolve().parents[2]


def _plan() -> dict:
    return {
        "status": "ready",
        "intent": "aggregate",
        "metric_id": "flight_count",
        "group_by": ["carrier"],
        "filters": [],
        "time_range": None,
        "sort": {"field_id": "flight_count", "direction": "desc"},
        "row_limit": 3,
        "chart_intent": "table",
        "clarification_question": None,
        "unsupported_reason": None,
    }


def test_bounded_local_query_preserves_rows_and_snapshot_provenance() -> None:
    with DuckDBExecutor(str(WORKSPACE / "source_data")) as executor:
        result = executor.execute(validate_analysis_plan(_plan()))
    assert len(result.rows) == 3
    assert result.rows[0]["carrier"] == "UA"
    assert result.rows[0]["metric_value"] == 55802
    assert result.snapshot_id == result.manifest.snapshot_id


def test_filter_values_are_parameters_and_cannot_change_query_shape() -> None:
    payload = "UA' OR 1=1; DROP TABLE flights;--"
    plan_data = _plan()
    plan_data["filters"] = [{"field_id": "carrier", "operator": "eq", "value": payload}]
    plan = validate_analysis_plan(plan_data)
    with DuckDBExecutor(str(WORKSPACE / "source_data")) as executor:
        result = executor.execute(plan)
        count_plan = validate_analysis_plan(
            {
                **_plan(),
                "group_by": [],
                "sort": None,
                "filters": [{"field_id": "carrier", "operator": "eq", "value": "UA"}],
            }
        )
        unchanged = executor.execute(count_plan)
    assert result.rows == ()
    assert unchanged.rows[0]["metric_value"] == 55802


def test_unready_plan_cannot_reach_execution() -> None:
    plan = _plan()
    plan.update(
        status="unsupported",
        intent=None,
        metric_id=None,
        unsupported_reason="Not available.",
    )
    with DuckDBExecutor(str(WORKSPACE / "source_data")) as executor:
        try:
            executor.execute(validate_analysis_plan(plan))
        except InvalidPlanError:
            pass
        else:
            raise AssertionError("Unsupported plan must not run a query.")
