import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.reports.export import export_report_csv, export_report_pdf
from airport_analytics.reports.generation import ReportGenerator
from airport_analytics.reports.rendering import build_figure
from tests.integration.test_report_evidence import base_plan


@pytest.fixture(scope="module")
def executor():
    with DuckDBExecutor(str(Path(__file__).resolve().parents[2] / "source_data")) as instance:
        yield instance


def report_for(executor, **changes):
    payload = base_plan()
    payload.update(changes)
    plan = validate_analysis_plan(payload)
    client = SimpleNamespace(generate_plan=lambda *args, **kwargs: SimpleNamespace(plan=plan))
    return (
        ReportGenerator(client, executor)
        .generate(
            "Synthetic evidence question",
            analyst_id="analyst",
            session_id="session",
            session_state={},
        )
        .report
    )


def test_month_filter_period_and_pdf_scope(executor):
    report = report_for(
        executor,
        metric_id="flight_count",
        group_by=[],
        sort=None,
        time_range=None,
        filters=[
            {"field_id": "origin", "operator": "eq", "value": "EWR"},
            {"field_id": "flight_month_number", "operator": "eq", "value": 6},
        ],
    )
    assert report.definitions["period"] == "2013-06-01 through 2013-06-30"
    text = "\n".join(
        page.extract_text() for page in PdfReader(io.BytesIO(export_report_pdf(report))).pages
    )
    assert "origin = EWR" in text
    assert "flight month number = 6" in text


def test_join_coverage_matches_filtered_population(executor):
    report = report_for(
        executor,
        metric_id="mean_aircraft_seats",
        group_by=[],
        sort=None,
        filters=[{"field_id": "origin", "operator": "eq", "value": "EWR"}],
    )
    coverage = report.result_payload["join_coverage"]["aircraft"]
    assert coverage["total"] == report.result_payload["rows"][0]["flight_count"] == 113385
    assert coverage["matched"] + coverage["unmatched"] == coverage["total"]
    independently_matched = executor._connection.execute(
        "SELECT COUNT(p.tailnum) FROM flights f LEFT JOIN planes p ON f.tailnum=p.tailnum "
        "WHERE f.origin='EWR'"
    ).fetchone()[0]
    assert coverage["matched"] == independently_matched


def test_connectivity_has_complete_supporting_routes(executor):
    report = report_for(
        executor,
        metric_id="distinct_destination_count",
        group_by=[],
        sort=None,
        filters=[{"field_id": "origin", "operator": "eq", "value": "EWR"}],
    )
    evidence = report.result_payload["routes"]
    assert evidence["complete"]
    assert (
        len({row["destination"] for row in evidence["rows"]})
        == (report.result_payload["rows"][0]["metric_value"])
    )
    assert "route_origin,destination,flights" in export_report_csv(
        report, supporting_routes=True
    ).decode("utf-8-sig")
    text = "\n".join(
        page.extract_text() for page in PdfReader(io.BytesIO(export_report_pdf(report))).pages
    )
    assert "Supporting routes" in text


def test_chart_period_and_units_are_labelled(executor):
    report = report_for(executor)
    title = build_figure(report).layout.title.text
    assert report.definitions["period"] in title
    assert "minutes" in title


def test_grouped_pdf_contains_carrier_airport_and_date_scope(executor):
    report = report_for(
        executor,
        filters=[
            {"field_id": "origin", "operator": "eq", "value": "EWR"},
            {"field_id": "carrier", "operator": "eq", "value": "UA"},
        ],
        time_range={"start": "2013-06-01", "end": "2013-06-30"},
    )
    text = "\n".join(
        page.extract_text() for page in PdfReader(io.BytesIO(export_report_pdf(report))).pages
    )
    for label in ("origin = EWR", "carrier = UA", "2013-06-01", "2013-06-30", "group_by"):
        assert label in text


def test_weather_coverage_is_scoped_before_weather_exclusions(executor):
    report = report_for(
        executor,
        metric_id="mean_delay_by_weather_context",
        group_by=["weather_precipitation_band"],
        sort=None,
        filters=[{"field_id": "origin", "operator": "eq", "value": "EWR"}],
        time_range={"start": "2013-06-01", "end": "2013-06-30"},
    )
    total, matched = executor._connection.execute(
        "SELECT COUNT(*),COUNT(w.origin) FROM flights f LEFT JOIN weather w "
        "ON f.origin=w.origin AND f.time_hour=w.time_hour WHERE f.origin='EWR' "
        "AND make_date(f.year,f.month,f.day) BETWEEN DATE '2013-06-01' AND DATE '2013-06-30'"
    ).fetchone()
    coverage = report.result_payload["join_coverage"]["weather_origin_time_exact"]
    assert coverage["total"] == total
    assert coverage["matched"] == matched
    assert coverage["unmatched"] == total - matched


def test_bounded_route_evidence_discloses_incompleteness(executor):
    report = report_for(
        executor,
        metric_id="distinct_destination_count",
        group_by=["flight_month"],
        filters=[],
        sort=None,
    )
    assert len(report.result_payload["routes"]["rows"]) == 500
    assert not report.result_payload["routes"]["complete"]
    assert any("incomplete" in line for line in report.limitations)


def test_tie_at_top_one_is_disclosed(executor):
    with executor._lock:
        executor._connection.execute("CREATE TEMP TABLE saved_flights AS SELECT * FROM flights")
        try:
            executor._connection.execute("DELETE FROM flights")
            executor._connection.execute(
                "INSERT INTO flights SELECT * FROM saved_flights "
                "WHERE carrier IN ('AA', 'UA') QUALIFY ROW_NUMBER() OVER "
                "(PARTITION BY carrier ORDER BY column00) = 1"
            )
            report = report_for(
                executor,
                metric_id="flight_count",
                filters=[],
                sort={"field_id": "flight_count", "direction": "desc"},
                row_limit=1,
            )
            assert report.result_payload["ranking"]["cutoff_tie"]
            assert any("additional tied groups" in line for line in report.limitations)
            assert report.result_payload["rows"][0]["carrier"] == "AA"
        finally:
            executor._connection.execute("DELETE FROM flights")
            executor._connection.execute("INSERT INTO flights SELECT * FROM saved_flights")
            executor._connection.execute("DROP TABLE saved_flights")
