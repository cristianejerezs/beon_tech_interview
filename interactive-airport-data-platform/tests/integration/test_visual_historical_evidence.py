import json
from pathlib import Path

import pytest

from airport_analytics.errors import VisualEvidenceError
from airport_analytics.models import CompositeReportV2, ReportContent
from airport_analytics.reports.visual_evidence import prepare_visual_evidence

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visual_reporting"


def test_v1_snapshot_loss_does_not_query_catalogue_or_backfill_coverage(monkeypatch):
    from airport_analytics.analytics.execution import DuckDBExecutor
    from airport_analytics.data import catalog

    def forbidden(*args, **kwargs):
        pytest.fail("Visual adaptation must use only the saved evidence.")

    monkeypatch.setattr(DuckDBExecutor, "__init__", forbidden)
    monkeypatch.setattr(catalog, "METRICS", {})
    source = ReportContent.model_validate_json((FIXTURES / "legacy-v1.json").read_text())
    before = source.model_dump_json()
    visual = prepare_visual_evidence(source, "legacy")
    assert visual.shape == "scalar"
    assert visual.context_id is None
    assert visual.source_evidence_version == 1
    assert visual.payload.to_dict()["rows"][0]["metric_value"] == 42
    assert visual.coverage.to_dict()["status"] == "unknown"
    assert source.model_dump_json() == before


def test_old_v2_snapshot_without_calendar_details_never_invents_verified_buckets():
    source = CompositeReportV2.model_validate_json((FIXTURES / "historical-v2.json").read_text())
    before = source.model_dump_json()
    visual = prepare_visual_evidence(source, "section")
    assert visual.scope.to_dict()["coverage_status"] == "unknown"
    assert visual.coverage.to_dict()["intervals"] == []
    assert source.model_dump_json() == before


def test_v1_missing_definitions_or_numeric_columns_gets_explicit_missing_evidence():
    payload = json.loads((FIXTURES / "legacy-v1.json").read_text())
    del payload["definitions"]["unit"]
    with pytest.raises(VisualEvidenceError):
        prepare_visual_evidence(ReportContent.model_validate(payload), "legacy")


def test_v1_nonfinite_and_boolean_metric_are_not_plotted():
    source = ReportContent.model_validate_json((FIXTURES / "legacy-v1.json").read_text())
    for value in [True, float("inf"), "42"]:
        source.result_payload["rows"][0]["metric_value"] = value
        with pytest.raises(VisualEvidenceError):
            prepare_visual_evidence(source, "legacy")


def test_future_report_version_is_not_guessed_from_valid_rows():
    source = CompositeReportV2.model_validate_json((FIXTURES / "historical-v2.json").read_text())
    source.__dict__["report_version"] = 3
    with pytest.raises(VisualEvidenceError):
        prepare_visual_evidence(source, "section")


def test_reopened_owned_reports_are_never_written_during_visual_adaptation(tmp_path, monkeypatch):
    from airport_analytics.auth import AnalystIdentity
    from airport_analytics.history.repository import ReportRepository
    from airport_analytics.storage import Storage

    repository = ReportRepository(Storage(tmp_path / "reports.sqlite"))
    owner = AnalystIdentity("owner", "local", "owner")
    source = ReportContent.model_validate_json((FIXTURES / "legacy-v1.json").read_text())
    repository.save_report(source, owner)
    reopened = repository.get_report(owner, source.report_id)
    original = reopened.model_dump_json()

    def forbidden(*args, **kwargs):
        pytest.fail("Reading derived visual evidence must not write reports.")

    monkeypatch.setattr(repository, "save_report", forbidden)
    prepare_visual_evidence(reopened, "legacy")
    assert repository.get_report(owner, source.report_id).model_dump_json() == original


def test_new_temporal_report_saves_verified_intervals_but_old_report_stays_unknown(tmp_path):
    from airport_analytics.analytics.execution import DuckDBExecutor
    from tests.integration.test_exploration_daily_metrics import verified_coverage
    from tests.integration.test_exploration_summaries import FIXTURES as SOURCES
    from tests.integration.test_exploration_summaries import generate

    with DuckDBExecutor(str(SOURCES)) as executor:
        path = verified_coverage(tmp_path, executor)
        old_outcome = generate(executor, family="historical_trend", grouping=["flight_month"])
    with DuckDBExecutor(str(SOURCES), coverage_path=path) as executor:
        new_outcome = generate(executor, family="historical_trend", grouping=["flight_month"])
    assert old_outcome.status == new_outcome.status == "report"
    old = prepare_visual_evidence(old_outcome.report, old_outcome.report.sections[0].section_id)
    current = prepare_visual_evidence(new_outcome.report, new_outcome.report.sections[0].section_id)
    assert old.coverage.to_dict()["status"] == "unknown"
    covered = current.coverage.to_dict()
    assert covered["status"] == "verified_intervals"
    assert covered["snapshot_id"] == current.snapshot_id
    assert covered["context_id"] == current.context_id
    assert len(covered["declaration_sha256"]) == 64
    assert all(item["start"] == "2013-01-01" for item in covered["intervals"])
    assert all(item["end"] == "2013-01-07" for item in covered["intervals"])


@pytest.mark.parametrize(
    "changes,shape",
    [
        ({}, "scalar"),
        ({"family": "grouped_summary", "grouping": ["origin"]}, "category"),
        ({"family": "ranking", "grouping": ["origin"]}, "ranking"),
        ({"family": "historical_trend", "grouping": ["flight_month"]}, "time"),
        (
            {"family": "historical_trend", "grouping": ["flight_month", "origin"]},
            "time_series",
        ),
        ({"family": "grouped_summary", "grouping": ["origin", "carrier"]}, "two_category"),
        ({"family": "grouped_summary", "grouping": ["month_of_year"]}, "category"),
        (
            {
                "family": "distribution",
                "operation_id": "distribution",
                "measure_ids": ["departure_delay"],
            },
            "distribution",
        ),
        (
            {
                "family": "numeric_relationship",
                "operation_id": "flight_relationship",
                "measure_ids": ["departure_delay", "arrival_delay"],
                "pairing": {"x": "departure_delay", "y": "arrival_delay"},
            },
            "relationship",
        ),
        (
            {
                "family": "period_change",
                "operation_id": "period_change",
                "comparison": {
                    "baseline": {"start": "2012-12-30", "end": "2012-12-31"},
                    "comparison": {"start": "2013-01-01", "end": "2013-01-02"},
                },
            },
            "period_change",
        ),
        (
            {"operation_id": "daily_distinct_mean", "measure_ids": ["distinct_destination_count"]},
            "scalar",
        ),
        (
            {
                "family": "numeric_relationship",
                "operation_id": "weather_relationship",
                "measure_ids": ["mean_departure_delay"],
            },
            "weather",
        ),
        (
            {"family": "individual_records", "operation_id": "flight_records", "measure_ids": []},
            "listing",
        ),
    ],
    ids=[
        "scalar",
        "category",
        "ranking",
        "time",
        "series",
        "two-category",
        "pooled-month",
        "distribution",
        "relationship",
        "period-change",
        "daily-mean",
        "weather",
        "listing",
    ],
)
def test_all_result_kinds_are_projected_exactly_with_no_rerun(changes, shape, monkeypatch):
    from airport_analytics import models
    from airport_analytics.analytics.execution import DuckDBExecutor
    from airport_analytics.reports.generation import ExplorationReportGenerator
    from tests.integration.test_exploration_summaries import FIXTURES as SOURCES
    from tests.integration.test_exploration_summaries import SummaryClient

    client = SummaryClient(**changes)
    with DuckDBExecutor(str(SOURCES)) as executor:
        outcome = ExplorationReportGenerator(client, executor).generate(
            "Synthetic evidence projection",
            analyst_id="owner",
            session_id="session",
            session_state={},
        )
    assert outcome.status == "report", outcome.message
    source = outcome.report
    section = source.sections[0]
    result = (
        section.outcome.result
        if section.outcome.status == "completed"
        else section.outcome.evidence
    )
    expected = result.model_dump(mode="json")

    def forbidden(*args, **kwargs):
        pytest.fail("Projection must not resolve the current catalogue, query or call a provider.")

    monkeypatch.setattr(models, "exploration_definition", forbidden)
    monkeypatch.setattr(DuckDBExecutor, "__init__", forbidden)
    monkeypatch.setattr(client, "generate_intent", forbidden)
    visual = prepare_visual_evidence(source, section.section_id)
    assert visual.shape == shape
    assert visual.payload.to_dict() == expected
    assert visual.typed_result().model_dump(mode="json") == expected
    assert client.calls == 1
    if "month_of_year" in changes.get("grouping", []):
        assert visual.dimensions[0].role == "ordered_category"


@pytest.mark.parametrize("count", [500, 501])
def test_saved_coverage_interval_bound_never_silently_truncates(count):
    from dataclasses import replace
    from datetime import date, timedelta

    from airport_analytics.analytics.execution import DuckDBExecutor
    from airport_analytics.data.coverage import CoverageDeclaration
    from airport_analytics.reports.generation import _save_bucket_coverage
    from tests.integration.test_exploration_summaries import FIXTURES as SOURCES
    from tests.integration.test_exploration_summaries import generate

    with DuckDBExecutor(str(SOURCES)) as executor:
        outcome = generate(executor, family="historical_trend", grouping=["flight_month"])
        assert outcome.status == "report"
        evidence = outcome.report.sections[0].outcome.result
        executor.coverage = CoverageDeclaration(
            {
                "JFK": frozenset(
                    date(2013, 1, 1) + timedelta(days=2 * index) for index in range(count)
                )
            }
        )
        executor.context = replace(executor.context, coverage_sha256="c" * 64)
        current = _save_bucket_coverage(evidence, executor)
    assert evidence.bucket_coverage is None
    if count == 500:
        assert len(current.bucket_coverage.intervals) == 500
    else:
        assert current.bucket_coverage is None
        assert any("500-interval bound" in limitation for limitation in current.limitations)
