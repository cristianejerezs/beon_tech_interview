import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from airport_analytics.data.loader import DatasetLoader
from tests.exploration_oracles import (
    aircraft_counts,
    bins,
    calendar_dates,
    capacity_days,
    daily_destinations,
    delay_totals,
    equal_day_mean,
    half_up,
    number,
    pearson,
    read_rows,
    weather_pairs,
    weekday_means,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "exploration"


def test_synthetic_calendar_and_distinct_mean():
    flights = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    assert len({row["column00"] for row in flights}) == len(flights) == 9
    rows = [row for row in flights if row["origin"] == "JFK"]
    calendar = json.loads((FIXTURES / "calendar.json").read_text())
    dates = tuple(date.fromisoformat(day) for day in calendar["verified_dates"])
    counts = daily_destinations(rows, dates)
    assert list(counts.values()) == [2, 2, 0, 2]
    assert equal_day_mean(counts) == Decimal("1.5")
    assert half_up(equal_day_mean(counts)) == 2
    assert weekday_means(counts)[4] == (Decimal(0), 1)
    assert weekday_means(counts)[5] == (None, 0)
    assert len(calendar_dates(date(2013, 1, 1), date(2013, 1, 7))) == 7
    assert equal_day_mean({}) is None


def test_two_stage_weighting_and_missing_seats():
    rows = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    rows = [row for row in rows if row["origin"] == "JFK"]
    dates = calendar_dates(date(2013, 1, 1), date(2013, 1, 3))
    totals = capacity_days(rows, read_rows(FIXTURES / "nyc_planes.csv"), dates, ("AA", "BB"))
    assert totals["AA", dates[0]] == (Decimal(200), 2, 0)
    assert totals["BB", dates[1]] == (Decimal(0), 0, 1)
    assert totals["AA", dates[2]] == (Decimal(0), 0, 0)
    positive, net, known, missing = delay_totals(rows)
    assert (positive, net, known, missing) == (Decimal(135), Decimal(130), 7, 1)
    assert delay_totals([]) == (None, None, 0, 0)


def test_aircraft_identity_not_flight_frequency():
    rows = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    planes = read_rows(FIXTURES / "nyc_planes.csv")
    counts = aircraft_counts(rows, planes, by_model=True)
    assert counts[("Maker A", "Shared")] == counts[("Maker B", "Shared")] == 1
    assert (
        aircraft_counts(rows, planes, by_model=True, flight_activity=True)[("Maker A", "Shared")]
        == 4
    )


def test_bins_negative_constant_endpoint_and_missing():
    result, missing = bins([Decimal(-15), Decimal(0), Decimal(15), None], Decimal(15))
    assert result == [
        (Decimal(-15), Decimal(0), 1),
        (Decimal(0), Decimal(15), 1),
        (Decimal(15), Decimal(30), 1),
    ]
    assert missing == 1
    assert bins([Decimal(0)], Decimal(15))[0] == [(Decimal(0), Decimal(15), 1)]


def test_weather_collapses_flights_before_pairing():
    rows = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    rows = [row for row in rows if row["origin"] == "JFK"]
    pairs = weather_pairs(rows, read_rows(FIXTURES / "nyc_weather.csv"), "temp")
    assert len(pairs) == 4
    assert pairs[0][1] == Decimal("7.5")
    assert (
        pearson([(Decimal(1), Decimal(2)), (Decimal(2), Decimal(4)), (Decimal(3), Decimal(6))]) == 1
    )
    assert pearson([(Decimal(1), Decimal(2))] * 3) is None
    assert pearson([]) is None


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_oracles_do_not_silently_drop_invalid_measurements(value):
    with pytest.raises(ValueError, match="Nonfinite"):
        number(value)


def test_mutations_use_temporary_copies(tmp_path):
    path = tmp_path / "flights.csv"
    path.write_bytes((FIXTURES / "nyc_flights_fixed.csv").read_bytes())
    original = (FIXTURES / "nyc_flights_fixed.csv").read_bytes()
    path.write_text(path.read_text().replace("JFK", "LGA"))
    assert path.read_bytes() != original
    assert (FIXTURES / "nyc_flights_fixed.csv").read_bytes() == original


def test_synthetic_sources_satisfy_existing_loader_contract():
    with duckdb.connect() as connection:
        manifest = DatasetLoader(FIXTURES).register_views(connection)
        assert len(manifest.snapshot_id) == 64
        assert connection.execute("SELECT COUNT(*) FROM flights").fetchone() == (9,)
