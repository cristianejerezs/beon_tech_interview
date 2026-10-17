from pathlib import Path

import duckdb
import pytest

from airport_analytics.data.loader import DatasetLoader
from airport_analytics.errors import DatasetUnavailableError

WORKSPACE = Path(__file__).resolve().parents[2]


def test_supplied_csv_snapshot_headers_counts_and_joins_are_validated() -> None:
    connection = duckdb.connect()
    try:
        manifest = DatasetLoader(WORKSPACE / "source_data").register_views(connection)
    finally:
        connection.close()

    counts = {item.dataset_name: item.row_count for item in manifest.datasets}
    assert counts == {
        "flights": 277977,
        "airports": 1458,
        "airlines": 16,
        "planes": 3322,
        "weather": 26112,
    }
    flights = next(item for item in manifest.datasets if item.dataset_name == "flights")
    planes = next(item for item in manifest.datasets if item.dataset_name == "planes")
    assert planes.missingness["speed"] > 0.99
    assert flights.join_key_coverage["weather_origin_time_exact"] == pytest.approx(276688 / 277977)
    assert flights.join_key_coverage["origin_airport"] == 1.0


def test_missing_source_file_blocks_analytics(tmp_path: Path) -> None:
    connection = duckdb.connect()
    try:
        with pytest.raises(DatasetUnavailableError):
            DatasetLoader(tmp_path).register_views(connection)
    finally:
        connection.close()
