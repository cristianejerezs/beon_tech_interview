from pathlib import Path

import pytest

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.analytics.query_compiler import CompiledQuery
from airport_analytics.errors import QueryExecutionError
from tests.unit.test_query_compiler import base_plan

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "exploration"


def test_executor_accepts_owned_cte_and_validates_declared_output(monkeypatch):
    plan = validate_analysis_plan(base_plan())
    main = CompiledQuery(
        sql="WITH source AS (SELECT 9 AS metric_value) "
        "SELECT metric_value, 9 AS flight_count, 9 AS observation_count FROM source",
        parameters=(),
        plan=plan,
        purpose="aggregate",
        kind="owned_cte",
        output_columns=("metric_value", "flight_count", "observation_count"),
    )
    scope = CompiledQuery(
        sql="SELECT NULL AS period_start, NULL AS period_end, 9 AS total",
        parameters=(),
        plan=plan,
        purpose="scope",
        kind="select",
        output_columns=("period_start", "period_end", "total"),
    )
    monkeypatch.setattr(
        "airport_analytics.analytics.execution.compile_analysis_plan",
        lambda _, evidence=None, **kwargs: scope if evidence == "scope" else main,
    )
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = executor.execute(plan)
        assert result.rows[0]["metric_value"] == 9
        invalid = CompiledQuery(
            sql="SELECT 9 AS wrong_name",
            parameters=(),
            plan=plan,
            purpose="aggregate",
            kind="select",
            output_columns=("expected_name",),
        )
        monkeypatch.setattr(
            "airport_analytics.analytics.execution.compile_analysis_plan", lambda *a, **kw: invalid
        )
        with pytest.raises(QueryExecutionError, match="output"):
            executor.execute(plan)
