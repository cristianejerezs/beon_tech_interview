from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.analytics.query_compiler import compile_analysis_plan
from tests.unit.test_query_compiler import base_plan


def test_compiler_declares_purpose_schema_and_owns_lookahead_limit():
    plan = validate_analysis_plan(base_plan())
    main = compile_analysis_plan(plan)
    lookahead = compile_analysis_plan(plan, lookahead=True)
    assert main.purpose == "aggregate"
    assert main.kind == "select"
    assert main.output_columns == ("carrier", "metric_value", "flight_count", "observation_count")
    assert main.parameters == (50,)
    assert lookahead.parameters == (51,)
    assert main.sql == lookahead.sql
    scope = compile_analysis_plan(plan, evidence="scope")
    assert scope.purpose == "scope"
    assert scope.output_columns == ("period_start", "period_end", "total")
    assert scope.parameters == ()
