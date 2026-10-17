from datetime import UTC, datetime

from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.models import ReportContent


def make_report(
    report_id: str,
    analyst_id: str,
    session_id: str,
    *,
    created_at: str | None = None,
) -> ReportContent:
    plan = validate_analysis_plan(
        {
            "status": "ready",
            "intent": "aggregate",
            "metric_id": "flight_count",
            "group_by": [],
            "filters": [],
            "time_range": None,
            "sort": None,
            "row_limit": 10,
            "chart_intent": "table",
            "clarification_question": None,
            "unsupported_reason": None,
        }
    )
    return ReportContent(
        report_id=report_id,
        analyst_id=analyst_id,
        session_id=session_id,
        question=f"How many flights are there for {report_id}?",
        analysis_plan=plan,
        result_payload={
            "columns": ["metric_value", "flight_count", "observation_count"],
            "rows": [{"metric_value": 42, "flight_count": 42, "observation_count": 42}],
            "scope": {"filters": [], "group_by": [], "period": "2013"},
            "join_coverage": {},
            "sample_counts": [{"flight_count": 42, "observation_count": 42}],
            "glossary": {},
        },
        narrative=f"42 flights were observed for {report_id}.",
        definitions={
            "metric": "Number of flight records.",
            "unit": "flights",
            "population": "Matching flight records.",
            "numerator": "Matching records",
            "denominator": "Not applicable",
            "period": "2013",
        },
        limitations=["Historical sample only."],
        snapshot_id="snapshot-id",
        created_at=created_at or datetime.now(UTC).isoformat(),
    )
