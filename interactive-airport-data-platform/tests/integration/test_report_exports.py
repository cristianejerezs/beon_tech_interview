import io
from datetime import UTC, datetime

import pytest
from pypdf import PdfReader

from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.models import CompositeReportV2, ReportContent
from airport_analytics.reports.export import export_report_csv, export_report_pdf
from tests.unit.test_exploration_results import scalar_report_payload


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


@pytest.mark.parametrize("version", [1, 2])
def test_pdf_second_heading_is_the_submitted_question(monkeypatch, version):
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    report = (
        sample_report()
        if version == 1
        else CompositeReportV2.model_validate(scalar_report_payload())
    )
    report.question = "Which destinations have <10 flights & why?"
    if version == 2:
        reader = PdfReader(io.BytesIO(export_report_pdf(report)))
        lines = [line.strip() for line in reader.pages[0].extract_text().splitlines()]
        assert "Airport" in lines[0]
        assert lines[1] == report.question
        top = reader.trailer["/Root"]["/StructTreeRoot"]["/K"]
        document = (top[0] if isinstance(top, list) else top).get_object()
        assert document["/S"] == "/Document"
        roles = [kid.get_object()["/S"] for kid in document["/K"]]
        assert roles[:2] == ["/H1", "/H2"]
        return
    paragraphs = []
    original = SimpleDocTemplate.build

    def capture(document, story, *args, **kwargs):
        paragraphs.extend(item for item in story if isinstance(item, Paragraph))
        return original(document, story, *args, **kwargs)

    monkeypatch.setattr(SimpleDocTemplate, "build", capture)
    content = export_report_pdf(report)

    assert "Airport" in paragraphs[0].getPlainText()
    assert paragraphs[1].getPlainText() == report.question
    assert paragraphs[1].style.parent.name == "Heading2"
    first_page = PdfReader(io.BytesIO(content)).pages[0].extract_text()
    assert report.question in first_page


@pytest.mark.parametrize("value", [None, "", "2026-01-01"])
def test_csv_null_serialization_is_empty(value: str | None) -> None:
    report = sample_report()
    report.result_payload["rows"][0]["missing_value"] = value
    content = export_report_csv(report).decode("utf-8-sig")
    assert content.splitlines()[1].endswith(str(value) if value else "")
