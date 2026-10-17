import io
from datetime import UTC, datetime

import pytest
from pypdf import PdfReader

from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.models import ReportContent
from airport_analytics.reports.export import export_report_csv, export_report_pdf


def sample_report() -> ReportContent:
    plan = validate_analysis_plan(
        {
            "status": "ready",
            "intent": "aggregate",
            "metric_id": "mean_departure_delay",
            "group_by": [],
            "filters": [],
            "time_range": {"start": "2013-01-01", "end": "2013-12-31"},
            "sort": None,
            "row_limit": 10,
            "chart_intent": "table",
            "clarification_question": None,
            "unsupported_reason": None,
        }
    )
    return ReportContent(
        report_id="report-123",
        analyst_id="analyst-123",
        session_id="session-123",
        question="What was the mean departure delay?",
        analysis_plan=plan,
        result_payload={
            "columns": ["metric_value", "flight_count", "note", "missing_value"],
            "rows": [
                {
                    "metric_value": 10.25,
                    "flight_count": 100,
                    "note": "verified",
                    "missing_value": None,
                }
            ],
            "scope": {"filters": [], "group_by": [], "period": "2013"},
            "join_coverage": {},
            "sample_counts": [],
            "glossary": {},
        },
        narrative="Mean departure delay was 10.25 minutes across 100 records.",
        definitions={
            "metric": "Mean recorded departure delay.",
            "unit": "minutes",
            "population": "Records with a delay observation.",
            "numerator": "Sum of observed minutes.",
            "denominator": "Observed delay records.",
            "period": "2013-01-01 through 2013-12-31",
        },
        limitations=["Missing values are excluded."],
        snapshot_id="snapshot-hash",
        created_at=datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
    )


def test_csv_contains_only_current_result_table_with_stable_headers() -> None:
    content = export_report_csv(sample_report()).decode("utf-8-sig")
    lines = content.splitlines()
    assert lines[0] == "metric_value,flight_count,note,missing_value"
    assert lines[1] == "10.25,100,verified,"
    assert "analyst-123" not in content
    assert "What was the mean" not in content


def test_pdf_contains_complete_report_sections_and_result_data() -> None:
    content = export_report_pdf(sample_report())
    assert content.startswith(b"%PDF-")
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    for required in (
        "What was the mean departure delay?",
        "10.25 minutes across 100 records.",
        "Mean recorded departure delay.",
        "2013-01-01 through 2013-12-31",
        "flight_count",
        "verified",
        "Missing values are excluded.",
        "snapshot-hash",
    ):
        assert required in text


@pytest.mark.parametrize("value", [None, "", "2026-01-01"])
def test_csv_null_serialization_is_empty(value: str | None) -> None:
    report = sample_report()
    report.result_payload["rows"][0]["missing_value"] = value
    content = export_report_csv(report).decode("utf-8-sig")
    assert content.splitlines()[1].endswith(str(value) if value else "")
