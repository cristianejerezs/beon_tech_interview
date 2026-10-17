from airport_analytics.data.catalog import DATASETS, DIMENSIONS, FIELDS, METRICS


def test_catalog_is_closed_and_uses_only_supplied_datasets() -> None:
    assert {dataset.filename for dataset in DATASETS.values()} == {
        "nyc_airlines.csv",
        "nyc_airports.csv",
        "nyc_flights_fixed.csv",
        "nyc_planes.csv",
        "nyc_weather.csv",
    }
    assert "mean_departure_delay" in METRICS
    assert "distinct_destination_count" in METRICS
    assert "unrestricted_sql" not in METRICS
    assert "flight_date" in FIELDS
    assert "weather_precipitation_band" in DIMENSIONS
