from pathlib import Path
from types import SimpleNamespace

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.models import ProviderUsage
from airport_analytics.reports.generation import ReportGenerator

WORKSPACE = Path(__file__).resolve().parents[2]


class FakePlanClient:
    def __init__(self, plan):
        self.plan = plan
        self.calls = 0

    def generate_plan(self, question, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            plan=self.plan,
            usage=ProviderUsage(),
            budget_reservation_id=None,
            trace_reservation_id=None,
        )


def base_plan() -> dict:
    return {
        "status": "ready",
        "intent": "compare",
        "metric_id": "mean_departure_delay",
        "group_by": ["carrier"],
        "filters": [{"field_id": "carrier", "operator": "eq", "value": "F9"}],
        "time_range": {"start": "2013-01-01", "end": "2013-12-31"},
        "sort": {"field_id": "mean_departure_delay", "direction": "desc"},
        "row_limit": 5,
        "chart_intent": "bar",
        "clarification_question": None,
        "unsupported_reason": None,
    }


def test_report_evidence_definitions_and_narrative_match_query_results() -> None:
    client = FakePlanClient(validate_analysis_plan(base_plan()))
    with DuckDBExecutor(str(WORKSPACE / "source_data")) as executor:
        outcome = ReportGenerator(client, executor).generate(
            "Which carrier had the highest mean departure delay?",
            analyst_id="analyst-id",
            session_id="session-id",
            session_state={},
        )

    assert outcome.status == "report"
    report = outcome.report
    assert report is not None
    assert report.definitions["unit"] == "minutes"
    assert "non-missing departure delay" in report.definitions["population"]
    assert "Sum of non-missing departure-delay minutes" == report.definitions["numerator"]
    assert "Count of matching records" in report.definitions["denominator"]
    assert report.result_payload["rows"][0]["carrier"] == "F9"
    assert report.result_payload["rows"][0]["metric_value"] == 20.08976377952756
    assert report.result_payload["rows"][0]["observation_count"] == 635
    assert "20.09 minutes" in report.narrative
    assert "635 metric observations" in report.narrative
    assert "not a statistical significance test" in report.narrative
    assert report.snapshot_id


def test_empty_scope_does_not_create_or_return_a_report() -> None:
    plan = base_plan()
    plan["filters"] = [{"field_id": "carrier", "operator": "eq", "value": "NOT_A_CARRIER"}]
    client = FakePlanClient(validate_analysis_plan(plan))
    with DuckDBExecutor(str(WORKSPACE / "source_data")) as executor:
        outcome = ReportGenerator(client, executor).generate(
            "Show mean delay for this carrier.",
            analyst_id="analyst-id",
            session_id="session-id",
            session_state={},
        )
    assert outcome.status == "empty"
    assert outcome.report is None
    assert "No records match" in outcome.message


def test_weather_context_reports_exact_join_coverage_and_non_causality() -> None:
    plan = base_plan()
    plan.update(
        metric_id="mean_delay_by_weather_context",
        group_by=["weather_precipitation_band"],
        filters=[{"field_id": "origin", "operator": "eq", "value": "EWR"}],
        sort=None,
    )
    client = FakePlanClient(validate_analysis_plan(plan))
    with DuckDBExecutor(str(WORKSPACE / "source_data")) as executor:
        outcome = ReportGenerator(client, executor).generate(
            "Compare departure delays by matched weather context at EWR.",
            analyst_id="analyst-id",
            session_id="session-id",
            session_state={},
        )
    assert outcome.status == "report"
    report = outcome.report
    assert report is not None
    coverage = report.result_payload["join_coverage"]["weather_origin_time_exact"]
    assert coverage["total"] == 113385
    assert coverage["matched"] + coverage["unmatched"] == 113385
    assert coverage["unmatched"] > 0
    assert "weather_association" in report.result_payload["glossary"]
    assert any("causation" in item for item in report.limitations)
