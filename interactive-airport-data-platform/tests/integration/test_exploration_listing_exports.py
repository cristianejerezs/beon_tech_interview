import csv
import io

import pytest
from pydantic import ValidationError

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.errors import DatasetUnavailableError, QueryExecutionError
from airport_analytics.models import ExportSelection
from airport_analytics.reports.export import export_listing_csv, listing_export_selection
from airport_analytics.reports.generation import ExplorationReportGenerator
from tests.integration.test_exploration_browsing import copy_flights
from tests.integration.test_exploration_summaries import SummaryClient


def report(executor):
    outcome = ExplorationReportGenerator(
        SummaryClient(
            family="individual_records",
            operation_id="flight_records",
            measure_ids=[],
            population="flights",
        ),
        executor,
    ).generate("List flights", analyst_id="owner", session_id="session", session_state={})
    assert outcome.report is not None, outcome.message
    return outcome.report


@pytest.mark.parametrize("count", [9999, 10000, 10001])
def test_listing_export_exact_identities_and_bound_confirmation(tmp_path, count):
    source = copy_flights(tmp_path, count)
    with DuckDBExecutor(str(source)) as executor:
        saved = report(executor)
        selection = listing_export_selection(
            saved,
            analyst_id="owner",
            session_id="session",
            allocation=min(count, 10000),
        )
        if count > 10000:
            with pytest.raises(ValueError, match="confirm"):
                export_listing_csv(
                    saved, executor, selection, analyst_id="owner", session_id="session"
                )
        selection = selection.confirm()
        data = export_listing_csv(
            saved,
            executor,
            selection,
            analyst_id="owner",
            session_id="session",
        )
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        assert len(rows) == min(count, 10000)
        assert [int(row["source_row_id"]) for row in rows] == list(range(1, min(count, 10000) + 1))
        assert {row["_meta_total_rows"] for row in rows} == {str(count)}
        assert {row["_meta_exported_rows"] for row in rows} == {str(min(count, 10000))}
        assert data.startswith(b"\xef\xbb\xbf")
        for changes in [
            {"revision": saved.revision + 1},
            {"scope_hash": "f" * 64},
            {"order_hash": "e" * 64},
            {"context_id": "d" * 64},
            {"snapshot_id": "c" * 64},
            {
                "allocations": {
                    saved.sections[0].section_id: 1,
                }
            },
        ]:
            stale = ExportSelection.model_validate(selection.model_dump() | changes)
            with pytest.raises(ValueError):
                export_listing_csv(saved, executor, stale, analyst_id="owner", session_id="session")
    with pytest.raises(QueryExecutionError, match="closed"):
        export_listing_csv(saved, executor, selection, analyst_id="owner", session_id="session")


def test_export_selection_rejects_combined_listing_allocation_over_10000(tmp_path):
    source = copy_flights(tmp_path, 1)
    with DuckDBExecutor(str(source)) as executor:
        selected = listing_export_selection(
            report(executor),
            analyst_id="owner",
            session_id="session",
            allocation=1,
        )
        with pytest.raises(ValidationError):
            ExportSelection.model_validate(
                selected.model_dump()
                | {
                    "allocations": {"one": 6000, "two": 6000},
                    "total_rows": {"one": 6000, "two": 6000},
                }
            )
        for second in (3999, 4000):
            bounded = ExportSelection.model_validate(
                selected.model_dump()
                | {
                    "allocations": {"one": 6000, "two": second},
                    "total_rows": {"one": 6000, "two": 6000},
                }
            )
            with pytest.raises(ValueError, match="confirmation"):
                bounded.require_confirmation()
            bounded.confirm().require_confirmation()


def test_csv_null_empty_formula_escaping_and_saved_evidence_are_independent(tmp_path):
    import json

    from airport_analytics.reports.export import export_report_csv

    source = copy_flights(tmp_path, 9)
    airlines = source / "nyc_airlines.csv"
    rows = list(csv.DictReader(io.StringIO(airlines.read_text(encoding="utf-8"))))
    names = ["=SUM(1,2)", "'already", "", 'A,"quoted"\nline', " \t@formula"]
    flight_path = source / "nyc_flights_fixed.csv"
    flight_rows = list(csv.DictReader(io.StringIO(flight_path.read_text(encoding="utf-8"))))
    with flight_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(flight_rows[0]))
        writer.writeheader()
        writer.writerows(
            row | {"tailnum": names[index % len(names)]} for index, row in enumerate(flight_rows)
        )
    with airlines.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["carrier", "name"])
        writer.writeheader()
        writer.writerows(
            row | {"name": names[index % len(names)]} for index, row in enumerate(rows)
        )
    with DuckDBExecutor(str(source)) as executor:
        saved = report(executor)
        original = saved.model_dump_json()
        selection = listing_export_selection(
            saved, analyst_id="owner", session_id="session", allocation=9
        )
        data = export_listing_csv(
            saved, executor, selection, analyst_id="owner", session_id="session"
        )
        exported = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        evidence = saved.sections[0].outcome.result
        assert set(names).issubset({row["tailnum"] for row in evidence.rows})
        for expected, row in zip(evidence.rows, exported, strict=True):
            assert json.loads(row["_meta_null_fields"]) == [
                key for key, value in expected.items() if value is None
            ]
            for key, value in expected.items():
                actual = row[key]
                if isinstance(value, str):
                    if actual.startswith("'"):
                        actual = actual[1:]
                    assert actual == value
                elif value is not None:
                    assert actual == str(value)
        assert "\r\n" in data.decode("utf-8-sig")
        assert saved.model_dump_json() == original
        preview = list(csv.DictReader(io.StringIO(export_report_csv(saved).decode("utf-8-sig"))))
        assert {row["_meta_evidence_kind"] for row in preview} == {"saved_listing_preview"}
        (source / "nyc_flights_fixed.csv").unlink()
        with pytest.raises(DatasetUnavailableError, match="fingerprint"):
            export_listing_csv(saved, executor, selection, analyst_id="owner", session_id="session")
        assert export_report_csv(saved) == export_report_csv(saved)


def test_empty_listing_has_metadata_only_csv(tmp_path):
    from tests.integration.test_exploration_summaries import SummaryClient

    source = copy_flights(tmp_path, 9)
    with DuckDBExecutor(str(source)) as executor:
        client = SummaryClient(
            family="individual_records",
            operation_id="flight_records",
            measure_ids=[],
            population="flights",
            scope_edits=[
                {
                    "field_id": "origin",
                    "action": "add",
                    "operator": "eq",
                    "value": "ZZZ",
                }
            ],
        )
        saved = (
            ExplorationReportGenerator(client, executor)
            .generate(
                "List reference-only origin flights",
                analyst_id="owner",
                session_id="session",
                session_state={},
            )
            .report
        )
        assert saved.sections[0].outcome.status == "valid_empty"
        selection = listing_export_selection(
            saved, analyst_id="owner", session_id="session", allocation=0
        )
        data = export_listing_csv(
            saved, executor, selection, analyst_id="owner", session_id="session"
        )
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        assert len(rows) == 1
        assert rows[0]["_meta_row_kind"] == "metadata_only"
        assert rows[0]["_meta_total_rows"] == "0"
