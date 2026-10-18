from collections import defaultdict

import pytest

from airport_analytics.analytics.execution import DuckDBExecutor
from tests.exploration_oracles import read_rows
from tests.integration.test_exploration_summaries import FIXTURES, evidence, generate


def test_airline_ranking_counts_distinct_numbers_within_carrier(tmp_path):
    import csv
    import io

    from pypdf import PdfReader

    from airport_analytics.analytics.plan_schema import validate_intent_proposal
    from airport_analytics.reports.export import export_report_csv, export_report_pdf
    from tests.integration.test_exploration_browsing import copy_flights
    from tests.unit.test_exploration_contracts import proposed_section

    source = copy_flights(tmp_path, 6)
    validate_intent_proposal(
        {
            "intent_version": 2,
            "status": "proposed",
            "shared_scope": {},
            "sections": [
                proposed_section(
                    family="ranking",
                    measure_ids=["distinct_flight_number_count"],
                    grouping=["carrier"],
                    order={"field_id": "distinct_flight_number_count", "direction": "desc"},
                    bound=100,
                )
            ],
            "selection_reason": None,
        }
    )
    path = source / "nyc_flights_fixed.csv"
    rows = read_rows(path)
    observations = [
        ("AA", "101", "1", "JFK", "BOS"),
        ("AA", "101", "2", "EWR", "LAX"),
        ("AA", "102", "1", "JFK", "BOS"),
        ("AA", "NA", "1", "JFK", "BOS"),
        ("UA", "101", "1", "EWR", "BOS"),
        ("UA", "101", "2", "EWR", "BOS"),
    ]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(
            row
            | {
                "carrier": carrier,
                "flight": flight,
                "day": day,
                "origin": origin,
                "dest": destination,
            }
            for row, (carrier, flight, day, origin, destination) in zip(
                rows, observations, strict=True
            )
        )
    with DuckDBExecutor(str(source)) as executor:
        outcome = generate(
            executor,
            family="ranking",
            measure_ids=["distinct_flight_number_count"],
            grouping=["carrier"],
            order={"field_id": "distinct_flight_number_count", "direction": "desc"},
            bound=100,
        )
        result = evidence(outcome)
        overall = evidence(generate(executor, measure_ids=["distinct_flight_number_count"]))
        ordinary = evidence(
            generate(
                executor,
                family="grouped_summary",
                measure_ids=["flight_count"],
                grouping=["carrier"],
            )
        )
    assert [
        (row.identity[0].code, row.measures["distinct_flight_number_count"].value)
        for row in result.values
    ] == [("AA", 2), ("UA", 1)]
    assert overall.value.value == 3
    assert result.missingness["missing_measure"] == 1
    assert {
        row.identity[0].code: row.measures["flight_count"].value for row in ordinary.values
    } == {"AA": 4, "UA": 2}
    assert b"distinct_flight_number_count" in export_report_csv(outcome.report)
    pdf = PdfReader(io.BytesIO(export_report_pdf(outcome.report)))
    assert "distinct_flight_number_count" in "\n".join(page.extract_text() for page in pdf.pages)


def test_highest_accumulated_month_uses_positive_totals_not_means_or_net(tmp_path):
    import csv

    from tests.integration.test_exploration_browsing import copy_flights

    source = copy_flights(tmp_path, 6)
    path = source / "nyc_flights_fixed.csv"
    rows = read_rows(path)
    # January wins accumulated positive delay; February wins mean and net delay.
    months = [(1, 60), (1, 60), (1, -200), (2, 100), (2, 0), (2, "NA")]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(
            row | {"month": str(month), "day": "1", "dep_delay": str(delay)}
            for row, (month, delay) in zip(rows, months, strict=True)
        )
    with DuckDBExecutor(str(source)) as executor:
        result = evidence(
            generate(
                executor,
                family="ranking",
                operation_id="departure_delay_total",
                measure_ids=["positive_delay_minutes"],
                grouping=["flight_month"],
                order={"field_id": "positive_delay_minutes", "direction": "desc"},
                bound=1,
            )
        )
        net = evidence(
            generate(
                executor,
                family="ranking",
                operation_id="departure_delay_total",
                measure_ids=["net_delay_minutes"],
                grouping=["flight_month"],
                order={"field_id": "net_delay_minutes", "direction": "desc"},
                bound=1,
            )
        )
    assert result.values[0].identity[0].code == "2013-01"
    assert result.values[0].measures["positive_delay_minutes"].value == 120
    assert net.values[0].identity[0].code == "2013-02"
    assert net.values[0].measures["net_delay_minutes"].value == 100
    assert result.missingness["missing_measure"] == 1


def test_aircraft_frequency_counts_distinct_observed_tails_not_flights():
    flights = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    planes = {row["tailnum"]: row for row in read_rows(FIXTURES / "nyc_planes.csv")}
    expected = defaultdict(set)
    for row in flights:
        if row["tailnum"] in planes:
            manufacturer = planes[row["tailnum"]]["manufacturer"]
            expected[None if manufacturer == "NA" else manufacturer].add(row["tailnum"])
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = evidence(
            generate(
                executor,
                family="ranking",
                operation_id="aircraft_frequency",
                measure_ids=["distinct_tailnums"],
                grouping=["aircraft_manufacturer"],
            )
        )
    actual = {g.identity[0].code: g.measures["distinct_tailnums"].value for g in result.values}
    assert actual == {key: len(value) for key, value in expected.items()}


def test_month_of_year_pools_years_instead_of_ranking_calendar_months(tmp_path):
    import csv

    from tests.integration.test_exploration_browsing import copy_flights

    source = copy_flights(tmp_path, 6)
    path = source / "nyc_flights_fixed.csv"
    rows = read_rows(path)
    observations = [
        (2013, 1, 60),
        (2014, 1, 60),
        (2013, 2, 100),
        (2014, 2, 0),
        (2014, 1, -200),
        (2014, 1, "NA"),
    ]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(
            row | {"year": str(year), "month": str(month), "day": "1", "dep_delay": str(delay)}
            for row, (year, month, delay) in zip(rows, observations, strict=True)
        )
    with DuckDBExecutor(str(source)) as executor:

        def report(grouping, **changes):
            return generate(
                executor,
                family="ranking",
                operation_id="departure_delay_total",
                measure_ids=["positive_delay_minutes"],
                grouping=[grouping],
                order={"field_id": "positive_delay_minutes", "direction": "desc"},
                bound=1,
                **changes,
            )

        calendar = evidence(report("flight_month"))
        pooled_report = report("month_of_year")
        pooled = evidence(pooled_report)
        counts = evidence(
            generate(
                executor,
                family="grouped_summary",
                measure_ids=["flight_count"],
                grouping=["month_of_year"],
                order={"field_id": "month_of_year", "direction": "asc"},
            )
        )
        means = evidence(
            generate(
                executor,
                family="grouped_summary",
                measure_ids=["mean_departure_delay"],
                grouping=["month_of_year"],
            )
        )
        scoped = evidence(
            report(
                "month_of_year",
                scope_edits=[
                    {
                        "action": "replace",
                        "field_id": "flight_year",
                        "operator": "eq",
                        "value": 2013,
                    }
                ],
            )
        )
    assert calendar.values[0].identity[0].code == "2013-02"
    assert calendar.values[0].measures["positive_delay_minutes"].value == 100
    assert pooled.values[0].identity[0].code == "01"
    assert pooled.values[0].identity[0].label == "January [01]"
    assert pooled.values[0].measures["positive_delay_minutes"].value == 120
    assert pooled.values[0].missing_count == 1
    assert pooled.grain == "month_of_year"
    assert pooled.selection.available == 2
    assert pooled_report.report.sections[0].interpretation.grouping == ["month_of_year"]
    assert "pool the same named month" in pooled_report.report.sections[0].narrative
    assert scoped.values[0].identity[0].label == "February [02]"
    assert scoped.values[0].measures["positive_delay_minutes"].value == 100
    assert [
        (item.identity[0].code, item.measures["flight_count"].value) for item in counts.values
    ] == [("01", 4), ("02", 2)]
    assert {
        item.identity[0].code: item.measures["mean_departure_delay"].value for item in means.values
    } == {"01": pytest.approx(-80 / 3), "02": 50}
    import io

    from pypdf import PdfReader

    from airport_analytics.auth import AnalystIdentity
    from airport_analytics.history.repository import ReportRepository
    from airport_analytics.reports.export import export_report_csv, export_report_pdf
    from airport_analytics.storage import Storage

    identity = AnalystIdentity("owner", "synthetic", "owner")
    repository = ReportRepository(Storage(tmp_path / "month.sqlite"))
    repository.save_report(pooled_report.report, identity)
    saved = repository.get_report(identity, pooled_report.report.report_id)
    assert saved == pooled_report.report
    exported = list(csv.DictReader(io.StringIO(export_report_csv(saved).decode("utf-8-sig"))))
    assert exported[0]["month_of_year_code"] == "01"
    assert exported[0]["positive_delay_minutes"] == "120"
    text = " ".join(
        "\n".join(
            page.extract_text() for page in PdfReader(io.BytesIO(export_report_pdf(saved))).pages
        ).split()
    )
    assert "January [01]" in text
    assert "pool the same named month" in text


@pytest.mark.parametrize("measure", ["distinct_tailnums", "explicit_flight_frequency"])
def test_aircraft_models_remain_manufacturer_qualified_and_frequency_is_explicit(measure):
    import json
    from collections import Counter

    planes = {row["tailnum"]: row for row in read_rows(FIXTURES / "nyc_planes.csv")}
    identities = defaultdict(set)
    frequencies = Counter()
    for row in read_rows(FIXTURES / "nyc_flights_fixed.csv"):
        plane = planes.get(row["tailnum"])
        if plane is None:
            continue
        key = None if plane["model"] == "NA" else (plane["manufacturer"], plane["model"])
        identities[key].add(row["tailnum"])
        frequencies[key] += 1
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = evidence(
            generate(
                executor,
                family="ranking",
                operation_id="aircraft_frequency",
                measure_ids=[measure],
                grouping=["aircraft_model"],
            )
        )
    actual = {}
    for group in result.values:
        code = group.identity[0].code
        identity = json.loads(code) if code is not None else None
        key = (identity["manufacturer"], identity["model"]) if identity else None
        actual[key] = group.measures[measure].value
    assert actual == (
        dict(frequencies)
        if measure == "explicit_flight_frequency"
        else {key: len(value) for key, value in identities.items()}
    )
    assert ("Maker A", "Shared") in actual and ("Maker B", "Shared") in actual


def test_weather_panel_allows_provisional_pearson_without_claiming_verified_units():
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = evidence(
            generate(
                executor,
                family="numeric_relationship",
                operation_id="weather_relationship",
                measure_ids=["mean_departure_delay"],
            )
        )
    assert result.weather_units_status == "unverified"
    assert result.precipitation_comparison == []
    assert len(result.variables) == 4


@pytest.mark.parametrize(
    "filename,column,value",
    [
        ("nyc_flights_fixed.csv", "dep_delay", "NaN"),
        ("nyc_flights_fixed.csv", "distance", "inf"),
        ("nyc_planes.csv", "seats", "-1"),
        ("nyc_weather.csv", "temp", "-inf"),
    ],
)
def test_invalid_finite_measurements_and_negative_seats_fail_explicitly(
    tmp_path, filename, column, value
):
    import csv

    from airport_analytics.errors import DatasetUnavailableError
    from tests.integration.test_exploration_browsing import copy_flights

    source = copy_flights(tmp_path, 9)
    path = source / filename
    rows = read_rows(path)
    rows[0][column] = value
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(DatasetUnavailableError):
        DuckDBExecutor(str(source))
