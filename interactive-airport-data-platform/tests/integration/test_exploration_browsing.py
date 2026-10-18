import shutil

import pytest
from pydantic import ValidationError

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.interpretation import resolve_proposal
from airport_analytics.errors import AuthorizationError, DatasetUnavailableError
from airport_analytics.models import BrowsePage, RequestDraft
from tests.exploration_oracles import read_rows
from tests.integration.test_exploration_summaries import FIXTURES
from tests.unit.test_exploration_interpretation import proposal


def interpretation(executor, *, population="flights", **changes):
    flight = population == "flights"
    return resolve_proposal(
        RequestDraft(original_question="List records"),
        proposal(
            family="individual_records" if flight else "unique_entity_list",
            operation_id="flight_records" if flight else "entity_list",
            measure_ids=[],
            population=population,
            **changes,
        ),
        executor.entity_directory(),
        snapshot_id=executor.manifest.snapshot_id,
        context_id=executor.context.context_id,
    )[0]


def page(executor, resolved, **options):
    return executor.browse(
        resolved,
        analyst_id="owner",
        session_id="session",
        **options,
    )


def test_all_catalogue_airports_have_distinct_bidirectional_connections():
    airports = read_rows(FIXTURES / "nyc_airports.csv")
    flights = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    neighbours = {row["faa"]: set() for row in airports}
    for row in flights:
        origin, destination = row["origin"], row["dest"]
        if origin in {"", "NA"} or destination in {"", "NA"} or origin == destination:
            continue
        if origin in neighbours:
            neighbours[origin].add(destination)
        if destination in neighbours:
            neighbours[destination].add(origin)
    with DuckDBExecutor(str(FIXTURES)) as executor:
        resolved = interpretation(executor, population="airport_connections")
        result = page(executor, resolved, page_size=25)
        assert {row["code"]: row["connection_count"] for row in result.rows} == {
            code: len(values) for code, values in neighbours.items()
        }
        assert next(row for row in result.rows if row["code"] == "ZZZ")["connection_count"] == 0
        assert all(
            row["name"]
            == next(airport["name"] for airport in airports if airport["faa"] == row["code"])
            for row in result.rows
        )
        assert page(executor, resolved, sort_field="connection_count", direction="desc").rows == (
            sorted(result.rows, key=lambda row: (-row["connection_count"], row["code"]))
        )


def test_connection_pages_and_complete_export_are_not_truncated(tmp_path):
    import csv
    import io

    from airport_analytics.reports.export import (
        export_listing_csv,
        listing_export_selection,
    )
    from tests.integration.test_exploration_summaries import evidence, generate

    source = copy_flights(tmp_path, 18)
    path = source / "nyc_airports.csv"
    airports = read_rows(path)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(airports[0]))
        writer.writeheader()
        writer.writerows(airports)
        writer.writerows(airports[0] | {"faa": f"Z{index:04d}"} for index in range(510))
    with DuckDBExecutor(str(source)) as executor:
        outcome = generate(
            executor,
            family="unique_entity_list",
            operation_id="entity_list",
            measure_ids=[],
            population="airport_connections",
        )
        result = evidence(outcome)
        assert result.total_rows == len(airports) + 510
        assert len(result.rows) == 100
        resolved = outcome.report.sections[0].interpretation
        first = page(executor, resolved, page_size=500)
        second = page(executor, resolved, page_size=500, page_index=2, previous=first)
        assert len(first.rows) + len(second.rows) == result.total_rows
        assert len({row["code"] for row in first.rows + second.rows}) == result.total_rows
        selection = listing_export_selection(
            outcome.report,
            analyst_id="owner",
            session_id="session",
            allocation=result.total_rows,
        )
        data = export_listing_csv(
            outcome.report,
            executor,
            selection,
            analyst_id="owner",
            session_id="session",
        )
        exported = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        assert len(exported) == result.total_rows
        assert sum(row["connection_count"] == "0" for row in exported) >= 511


def test_connections_deduplicate_reverse_edges_and_exclude_self_connections(tmp_path):
    import csv

    source = copy_flights(tmp_path, 5)
    path = source / "nyc_flights_fixed.csv"
    rows = read_rows(path)
    edges = [("JFK", "LGA"), ("LGA", "JFK"), ("JFK", "LGA"), ("JFK", "JFK"), ("JFK", "XXX")]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(
            row | {"origin": origin, "dest": dest}
            for row, (origin, dest) in zip(rows, edges, strict=True)
        )
    with DuckDBExecutor(str(source)) as executor:
        result = page(executor, interpretation(executor, population="airport_connections"))
    counts = {row["code"]: row["connection_count"] for row in result.rows}
    assert counts["JFK"] == 2
    assert counts["LGA"] == 1
    assert counts["ZZZ"] == 0
    assert "XXX" not in counts


def test_connection_flight_scope_and_airport_scope_preserve_zero_catalogue_rows():
    from tests.integration.test_exploration_summaries import evidence, generate

    with DuckDBExecutor(str(FIXTURES)) as executor:
        outcome = generate(
            executor,
            family="unique_entity_list",
            operation_id="entity_list",
            measure_ids=[],
            population="airport_connections",
            scope_edits=[
                {"field_id": "origin", "action": "add", "operator": "eq", "value": "ZZZ"},
                {"field_id": "flight_year", "action": "add", "operator": "eq", "value": 1900},
            ],
        )
        result = evidence(outcome)
    assert result.total_rows == 1
    assert result.rows[0]["code"] == "ZZZ"
    assert result.rows[0]["connection_count"] == 0
    assert result.fields[-1].role == "numeric"
    assert result.definition.weighting == "distinct_neighbour"


def test_connection_date_scope_counts_arriving_neighbours():
    from airport_analytics.models import TimeRange

    with DuckDBExecutor(str(FIXTURES)) as executor:
        resolved = interpretation(executor, population="airport_connections")
        payload = resolved.model_dump(mode="json")
        payload["date_scope"] = TimeRange(start="2013-01-01", end="2013-01-01").model_dump(
            mode="json"
        )
        resolved = type(resolved).model_validate(payload)
        result = page(executor, resolved)
    flights = [row for row in read_rows(FIXTURES / "nyc_flights_fixed.csv") if row["day"] == "1"]
    for row in result.rows:
        expected = {
            dest if origin == row["code"] else origin
            for flight in flights
            for origin, dest in [(flight["origin"], flight["dest"])]
            if row["code"] in {origin, dest} and origin != dest
        }
        assert row["connection_count"] == len(expected)


@pytest.mark.parametrize(
    "population,column",
    [
        ("observed_origins", "origin"),
        ("observed_destinations", "dest"),
        ("observed_airlines", "carrier"),
        ("airport_reference", "faa"),
    ],
)
def test_entity_populations_are_exact_source_sets(population, column):
    rows = read_rows(
        FIXTURES
        / ("nyc_airports.csv" if population == "airport_reference" else "nyc_flights_fixed.csv")
    )
    expected = sorted({row[column] for row in rows if row[column] not in {"", "NA"}})
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = page(executor, interpretation(executor, population=population))
    assert result.total_rows == len(expected)
    assert [row["code"] for row in result.rows] == expected
    assert result.page_size == 100
    assert result.page_index == 1
    assert result.total_pages == 1
    assert result.first_identity == expected[0]
    if population == "observed_destinations":
        assert next(row for row in result.rows if row["code"] == "XXX")["reference_status"] == (
            "unmatched_reference"
        )
    if population == "airport_reference":
        assert "ZZZ" in expected


def copy_flights(tmp_path, count):
    source = tmp_path / "source"
    shutil.copytree(FIXTURES, source)
    import csv

    path = source / "nyc_flights_fixed.csv"
    original = read_rows(path)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(original[0]))
        writer.writeheader()
        writer.writerows(
            original[index % len(original)] | {"column00": str(index + 1)} for index in range(count)
        )
    return source


@pytest.mark.parametrize("size", [25, 50, 100, 500])
def test_three_consecutive_pages_match_ordered_source_identities(tmp_path, size):
    source = copy_flights(tmp_path, size * 3 + 1)
    with DuckDBExecutor(str(source)) as executor:
        resolved = interpretation(executor)
        previous = None
        actual = []
        for index in range(1, 4):
            result = page(executor, resolved, page_size=size, page_index=index, previous=previous)
            assert result.page_index == index
            assert result.total_rows == size * 3 + 1
            assert result.total_pages == 4
            actual += [row["source_row_id"] for row in result.rows]
            previous = result
        assert actual == list(range(1, size * 3 + 1))
        reset = page(executor, resolved, page_index=999, page_size=size, previous=previous)
        assert reset.page_index == 1
        assert reset.notice
        changed_size = 50 if size != 50 else 25
        reset = page(executor, resolved, page_size=changed_size, page_index=2, previous=previous)
        assert reset.page_index == 1
        assert reset.notice


def test_sort_ties_scope_reset_empty_and_binding_guards(tmp_path):
    source = copy_flights(tmp_path, 80)
    with DuckDBExecutor(str(source)) as executor:
        resolved = interpretation(executor)
        first = page(executor, resolved, page_size=25)
        with pytest.raises(AuthorizationError):
            executor.browse(resolved, analyst_id="other", session_id="session", previous=first)
        with pytest.raises(AuthorizationError):
            page(executor, resolved, previous=first.model_copy(update={"request_id": "stale"}))
        sorted_page = page(
            executor,
            resolved,
            previous=first,
            page_index=2,
            page_size=25,
            sort_field="departure_delay",
            direction="desc",
        )
        assert sorted_page.page_index == 1
        rows = read_rows(source / "nyc_flights_fixed.csv")
        expected = sorted(
            rows,
            key=lambda row: (
                row["dep_delay"] == "NA",
                -float(row["dep_delay"]) if row["dep_delay"] != "NA" else 0,
                int(row["column00"]),
            ),
        )[:25]
        assert [row["source_row_id"] for row in sorted_page.rows] == [
            int(row["column00"]) for row in expected
        ]
        empty = interpretation(
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
        result = page(executor, empty)
        assert result.total_pages == 0
        assert result.rows == []
        assert result.first_identity is None
        (source / "nyc_flights_fixed.csv").write_text("changed", encoding="utf-8")
        with pytest.raises(DatasetUnavailableError):
            page(executor, resolved, previous=first, page_index=2)


def test_browse_page_rejects_invalid_bounds_and_counts():
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = page(executor, interpretation(executor))
    for changes in [
        {"page_size": 10},
        {"page_index": 0},
        {"total_pages": 99},
        {"total_rows": 0},
        {"first_identity": "wrong"},
        {"rows": result.rows + result.rows},
        {"scope_hash": "bad"},
    ]:
        with pytest.raises(ValidationError):
            BrowsePage.model_validate(result.model_dump() | changes)


def test_count_and_page_share_filters_and_context_rechecked(tmp_path):
    source = copy_flights(tmp_path, 120)
    coverage = tmp_path / "coverage.json"
    with DuckDBExecutor(str(source), coverage_path=coverage) as executor:
        filters = [
            {"field_id": "origin", "action": "add", "operator": "eq", "value": "JFK"},
            {"field_id": "departure_delay", "action": "add", "operator": "gte", "value": 0},
        ]
        resolved = interpretation(executor, scope_edits=filters)
        expected = [
            int(row["column00"])
            for row in read_rows(source / "nyc_flights_fixed.csv")
            if row["origin"] == "JFK" and row["dep_delay"] != "NA" and float(row["dep_delay"]) >= 0
        ]
        result = page(executor, resolved)
        assert result.total_rows == len(expected)
        assert [row["source_row_id"] for row in result.rows] == expected
        amended = interpretation(executor, scope_edits=[filters[0]])
        amended = amended.model_copy(
            update={
                "request_id": resolved.request_id,
                "section_id": resolved.section_id,
            }
        )
        reset = page(executor, amended, previous=result, page_index=2)
        assert reset.page_index == 1
        assert "Scope" in reset.notice
        coverage.write_text("{}", encoding="utf-8")
        with pytest.raises(DatasetUnavailableError, match="context changed"):
            page(executor, resolved, previous=result)


def test_reference_population_rejects_inapplicable_scope_before_query():
    with DuckDBExecutor(str(FIXTURES)) as executor:
        with pytest.raises(ValueError, match="flight-date"):
            interpretation(
                executor,
                population="airport_reference",
                scope_edits=[
                    {
                        "field_id": "carrier",
                        "action": "add",
                        "operator": "eq",
                        "value": "AA",
                    }
                ],
            )
