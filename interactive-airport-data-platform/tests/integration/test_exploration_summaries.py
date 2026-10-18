import csv
import io
import shutil
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.auth import AnalystIdentity
from airport_analytics.consent.repository import ConsentRepository
from airport_analytics.consent.service import ConsentService
from airport_analytics.errors import AuthorizationError, ConsentError
from airport_analytics.history.repository import ReportRepository
from airport_analytics.models import IntentProposalV2
from airport_analytics.reports.export import export_report_csv, export_report_pdf
from airport_analytics.reports.generation import ExplorationReportGenerator
from airport_analytics.storage import Storage
from tests.exploration_oracles import number, read_rows
from tests.unit.test_exploration_contracts import proposed_section

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "exploration"


class SummaryClient:
    def __init__(self, **changes):
        self.calls = 0
        self.proposal = IntentProposalV2.model_validate(
            {
                "intent_version": 2,
                "status": "proposed",
                "shared_scope": {},
                "sections": [proposed_section(**changes)],
                "selection_reason": None,
            }
        )

    def generate_intent(self, question, **kwargs):
        self.calls += 1
        return SimpleNamespace(proposal=self.proposal)


def generate(executor, **changes):
    return ExplorationReportGenerator(SummaryClient(**changes), executor).generate(
        "How many destinations?",
        analyst_id="owner",
        session_id="session",
        session_state={},
    )


def evidence(outcome):
    assert outcome.status == "report", outcome.message
    section = outcome.report.sections[0]
    return (
        section.outcome.result
        if section.outcome.status == "completed"
        else section.outcome.evidence
    )


def test_global_and_grouped_distinct_are_independent_source_sets():
    flights = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    expected = len({row["dest"] for row in flights})
    per_origin = {
        origin: len({row["dest"] for row in flights if row["origin"] == origin})
        for origin in {row["origin"] for row in flights}
    }
    with DuckDBExecutor(str(FIXTURES)) as executor:
        overall = evidence(generate(executor, measure_ids=["distinct_destination_count"]))
        grouped = evidence(
            generate(
                executor,
                measure_ids=["distinct_destination_count"],
                family="grouped_summary",
                grouping=["origin"],
            )
        )
    assert overall.value.value == expected
    actual = {
        row.identity[0].code: row.measures["distinct_destination_count"].value
        for row in grouped.values
    }
    assert actual == per_origin
    assert sum(actual.values()) != expected
    assert any(route["destination"] == "XXX" for route in overall.route_support)
    assert overall.missingness["filtered_flights"] == len(flights)
    assert overall.missingness["destination_reference_unmatched"] == 1


def test_connected_airports_count_both_directions_per_airport():
    flights = [
        row
        for row in read_rows(FIXTURES / "nyc_flights_fixed.csv")
        if row["origin"] and row["dest"] and row["origin"] != row["dest"]
    ]
    neighbours: dict[str, set[str]] = {}
    for row in flights:
        neighbours.setdefault(row["origin"], set()).add(row["dest"])
        neighbours.setdefault(row["dest"], set()).add(row["origin"])
    touching = {
        airport: sum(airport in {row["origin"], row["dest"]} for row in flights)
        for airport in neighbours
    }
    with DuckDBExecutor(str(FIXTURES)) as executor:
        grouped = evidence(
            generate(
                executor,
                measure_ids=["distinct_connected_airport_count"],
                family="grouped_summary",
                grouping=["airport"],
            )
        )
        overall = evidence(generate(executor, measure_ids=["distinct_connected_airport_count"]))
        flights_by_airport = evidence(
            generate(
                executor,
                measure_ids=["flight_count"],
                family="grouped_summary",
                grouping=["airport"],
            )
        )
    actual = {
        row.identity[0].code: row.measures["distinct_connected_airport_count"].value
        for row in grouped.values
    }
    assert actual == {airport: len(codes) for airport, codes in neighbours.items()}
    assert overall.value.value == len(set().union(*neighbours.values()))
    assert {
        row.identity[0].code: row.measures["flight_count"].value
        for row in flights_by_airport.values
    } == touching


def test_two_roles_and_calendar_groups_preserve_raw_values_and_exact_selection():
    flights = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = evidence(
            generate(
                executor,
                family="ranking",
                grouping=["origin", "carrier"],
                bound=1,
            )
        )
        daily = evidence(
            generate(
                executor,
                family="historical_trend",
                grouping=["flight_date"],
            )
        )
    expected = {}
    for row in flights:
        key = (row["origin"], row["carrier"])
        expected[key] = expected.get(key, 0) + 1
    assert result.selection.available == len(expected)
    assert result.selection.selected == 1
    assert result.selection.omitted == len(expected) - 1
    assert result.values[0].measures["flight_count"].value == max(expected.values())
    dates = [row.identity[0].code for row in daily.values]
    assert dates == sorted(dates)
    assert sum(row.measures["flight_count"].value for row in daily.values) == len(flights)


def test_empty_is_not_missing_measure_or_source_failure():
    with DuckDBExecutor(str(FIXTURES)) as executor:
        empty = generate(
            executor,
            scope_edits=[
                {
                    "field_id": "origin",
                    "action": "add",
                    "operator": "eq",
                    "value": "ZZZ",
                }
            ],
        )
        missing = generate(
            executor,
            measure_ids=["mean_departure_delay"],
            scope_edits=[
                {
                    "field_id": "destination",
                    "action": "add",
                    "operator": "eq",
                    "value": "XXX",
                }
            ],
        )
        assert empty.report.sections[0].outcome.status == "valid_empty"
        assert evidence(empty).value.value == 0
        value = evidence(missing)
        assert missing.report.sections[0].outcome.status == "completed"
        assert value.value.value is None
        assert value.value.absence == "no_known_values"
        assert value.missingness["filtered_flights"] == 1
        assert value.missingness["known_measure"] == 0
        executor.close()
        with pytest.raises(Exception, match="closed"):
            generate(executor)


def test_unresolved_or_invalid_proposal_runs_no_analytical_batch(monkeypatch):
    with DuckDBExecutor(str(FIXTURES)) as executor:

        def forbidden(*args, **kwargs):
            pytest.fail("Unresolved input reached analytical execution")

        monkeypatch.setattr(executor, "execute_summary", forbidden)
        invalid = generate(
            executor,
            entity_mentions=[
                {
                    "kind": "origin",
                    "text": "Never An Airport",
                    "code_candidate": None,
                }
            ],
        )
        assert invalid.status == "needs_clarification"
        client = SummaryClient()
        client.proposal = IntentProposalV2.model_validate(
            {
                "intent_version": 2,
                "status": "requires_selection",
                "shared_scope": {},
                "sections": [],
                "selection_reason": "Select up to four.",
            }
        )
        outcome = ExplorationReportGenerator(client, executor).generate(
            "Many questions",
            analyst_id="owner",
            session_id="session",
            session_state={},
        )
        assert outcome.status == "requires_selection"
        assert client.calls == 1


def test_manufacturer_model_identities_do_not_merge_same_named_models():
    with DuckDBExecutor(str(FIXTURES)) as executor:
        grouped = evidence(
            generate(
                executor,
                family="grouped_summary",
                grouping=["aircraft_model"],
            )
        )
    shared = [row for row in grouped.values if "/ Shared [" in row.identity[0].label]
    assert len(shared) == 2
    assert len({row.identity[0].code for row in shared}) == 2
    assert any(row.identity[0].status != "known" for row in grouped.values)


def test_v2_exports_use_saved_evidence_and_keep_precision_metadata_and_route_counts():
    with DuckDBExecutor(str(FIXTURES)) as executor:
        report = generate(
            executor,
            family="grouped_summary",
            grouping=["origin"],
            measure_ids=["distinct_destination_count"],
        ).report
    # Exports must work after the analytical connection is closed.
    csv_bytes = export_report_csv(report)
    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    assert {row["origin_code"] for row in rows} == {"JFK", "LGA"}
    assert {row["_meta_snapshot_id"] for row in rows} == {report.snapshot_id}
    assert {row["_meta_denominator_basis"] for row in rows} == {"not_applicable"}
    assert {row["_meta_total_count"] for row in rows} == {"2"}
    route_bytes = export_report_csv(report, supporting_routes=True)
    route_rows = list(csv.DictReader(io.StringIO(route_bytes.decode("utf-8-sig"))))
    assert len(route_rows) == 4
    assert {row["_meta_evidence_kind"] for row in route_rows} == {"routes"}
    pdf = export_report_pdf(report)
    text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    for expected in [
        "JFK",
        "LGA",
        "distinct_destination_count",
        "Semantic context",
        report.snapshot_id,
    ]:
        assert expected in text
    assert "Tagged PDF" in text


def test_v2_one_section_sharing_preserves_original_session_and_creation_eligibility(tmp_path):
    storage = Storage(tmp_path / "sharing.sqlite")
    repo = ReportRepository(storage)
    events = ConsentRepository(storage)
    service = ConsentService(repo, events, shared_reuse_enabled=True)
    identity = AnalystIdentity("owner", "local", "owner")
    state = {}
    service.set_consent(identity, "session", "faq", True, state, notice_version="test")
    with DuckDBExecutor(str(FIXTURES)) as executor:
        report = generate(executor).report
    # Creation after the consent grant is required, even if saving happens later.
    assert report.created_at <= datetime.now(UTC)
    repo.save_report(report, identity)
    artifact = service.create_shared_artifact(identity, report, "faq", state)
    assert artifact.content["summary_rows"][0]["flight_count"] == 9
    assert artifact.content["section_id"] == report.sections[0].section_id
    assert "owner" not in artifact.content
    with pytest.raises(AuthorizationError):
        service.create_shared_artifact(
            AnalystIdentity("other", "local", "other"), report, "faq", state
        )
    service.set_consent(identity, "session", "faq", False, state, notice_version="test")
    with pytest.raises(ConsentError):
        service.create_shared_artifact(identity, report, "faq", state)
    assert len(repo.list_shared_artifacts("faq")) == 1
    service.set_consent(identity, "session", "faq", True, state, notice_version="test")
    with pytest.raises(ConsentError):
        service.create_shared_artifact(identity, report, "faq", state)
    service.set_consent(identity, "new-session", "faq", True, state, notice_version="test")
    with pytest.raises(ConsentError):
        service.create_shared_artifact(identity, report, "faq", state)


@pytest.mark.parametrize(
    "measure, column",
    [
        ("mean_departure_delay", "dep_delay"),
        ("mean_arrival_delay", "arr_delay"),
        ("mean_distance", "distance"),
    ],
)
def test_all_numeric_summary_means_match_independent_known_flight_values(measure, column):
    flights = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    known = [number(row[column]) for row in flights if number(row[column]) is not None]
    expected = float(sum(known) / len(known))
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = evidence(generate(executor, measure_ids=[measure]))
    assert result.value.value == pytest.approx(expected, abs=1e-9, rel=1e-12)
    assert result.missingness["known_measure"] == len(known)
    assert result.missingness["missing_measure"] == len(flights) - len(known)


def test_aircraft_distinct_and_seat_means_use_reference_match_without_losing_source_scope():
    flights = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    planes = {row["tailnum"]: row for row in read_rows(FIXTURES / "nyc_planes.csv")}
    seats = [
        number(planes[row["tailnum"]]["seats"])
        for row in flights
        if row["tailnum"] in planes and number(planes[row["tailnum"]]["seats"]) is not None
    ]
    tails = {row["tailnum"] for row in flights if row["tailnum"] not in {"", "NA"}}
    with DuckDBExecutor(str(FIXTURES)) as executor:
        aircraft = evidence(generate(executor, measure_ids=["distinct_aircraft_count"]))
        capacity = evidence(generate(executor, measure_ids=["mean_seats"]))
    assert aircraft.value.value == len(tails)
    assert capacity.value.value == pytest.approx(float(sum(seats) / len(seats)))
    assert capacity.missingness["filtered_flights"] == len(flights)
    assert capacity.missingness["known_measure"] == len(seats)


def test_501_groups_and_routes_compute_full_population_before_500_row_selection(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(FIXTURES, source)
    flights_path = source / "nyc_flights_fixed.csv"
    original = read_rows(flights_path)
    flights = [
        original[0] | {"column00": str(index + 1), "dest": f"D{index:03d}"} for index in range(501)
    ]
    with flights_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(original[0]))
        writer.writeheader()
        writer.writerows(flights)
    with DuckDBExecutor(str(source)) as executor:
        grouped = evidence(
            generate(
                executor,
                family="ranking",
                grouping=["destination"],
                bound=500,
            )
        )
        scalar = evidence(generate(executor, measure_ids=["distinct_destination_count"]))
    assert grouped.selection.available == 501
    assert grouped.selection.selected == 500
    assert grouped.selection.omitted == 1
    assert grouped.selection.cutoff_tie is True
    assert grouped.missingness["filtered_flights"] == 501
    assert all(row.identity[0].status == "unmatched_reference" for row in grouped.values)
    assert scalar.value.value == 501
    assert len(scalar.route_support) == 500
    assert scalar.missingness["available_routes"] == 501
    assert scalar.missingness["omitted_routes"] == 1


def test_weather_context_summary_is_matched_flight_weighted_not_hour_weighted():
    flights = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    weather_keys = {
        (row["origin"], row["time_hour"]) for row in read_rows(FIXTURES / "nyc_weather.csv")
    }
    matched = [row for row in flights if (row["origin"], row["time_hour"]) in weather_keys]
    known = [number(row["dep_delay"]) for row in matched if number(row["dep_delay"]) is not None]
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = evidence(generate(executor, measure_ids=["weather_context_departure_delay"]))
    assert result.value.value == pytest.approx(float(sum(known) / len(known)))
    assert result.missingness["filtered_flights"] == len(flights)
    assert result.missingness["known_measure"] == len(known)
    assert result.missingness["weather_reference_unmatched"] == len(flights) - len(matched)


def test_executable_looking_filter_value_remains_bound_data():
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = generate(
            executor,
            scope_edits=[
                {"field_id": "tailnum", "action": "add", "operator": "eq", "value": "' OR 1=1 --"},
            ],
        )
        assert result.report.sections[0].outcome.status == "valid_empty"
        assert evidence(result).value.value == 0
        assert evidence(generate(executor)).value.value == 9
