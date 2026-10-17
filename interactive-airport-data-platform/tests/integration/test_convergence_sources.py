import csv
import io
import shutil
from pathlib import Path

import duckdb
import pytest

import app
from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.data.catalog import DATASETS
from airport_analytics.data.loader import DatasetLoader
from airport_analytics.data.validation import build_snapshots, validate_dataset_structure
from airport_analytics.errors import DatasetUnavailableError


def test_duplicate_missing_and_malformed_source_keys_fail():
    with duckdb.connect() as connection:
        connection.execute("CREATE TABLE airlines(carrier VARCHAR, name VARCHAR)")
        connection.execute("INSERT INTO airlines VALUES ('AA', 'Example'), ('AA', 'Example')")
        with pytest.raises(DatasetUnavailableError, match="Duplicate"):
            validate_dataset_structure(
                connection, "airlines", connection.execute("DESCRIBE airlines").fetchall()
            )
        connection.execute("DELETE FROM airlines")
        connection.execute("INSERT INTO airlines VALUES (NULL, 'Example')")
        with pytest.raises(DatasetUnavailableError, match="Missing"):
            validate_dataset_structure(
                connection, "airlines", connection.execute("DESCRIBE airlines").fetchall()
            )
        connection.execute("CREATE TABLE bad(carrier BIGINT, name VARCHAR)")
        with pytest.raises(DatasetUnavailableError, match="type"):
            validate_dataset_structure(
                connection, "airlines", connection.execute("DESCRIBE bad").fetchall()
            )


def test_snapshot_cache_refreshes_and_invalid_replacement_fails_closed(tmp_path):
    source = Path(__file__).resolve().parents[2] / "source_data"
    for file in source.glob("*.csv"):
        shutil.copyfile(file, tmp_path / file.name)
    first = app._executor(str(tmp_path), 30)
    before = first.manifest.snapshot_id
    reference = tmp_path / "nyc_airlines.csv"
    original = reference.read_text(encoding="utf-8")
    reference.write_text(
        original.replace("United Air Lines", "United Test Lines"), encoding="utf-8"
    )
    second = app._executor(str(tmp_path), 30)
    assert second.manifest.snapshot_id != before
    assert first.manifest.snapshot_id == before
    reference.write_text("wrong,headers\n", encoding="utf-8")
    with pytest.raises(DatasetUnavailableError):
        app._executor(str(tmp_path), 30)
    assert DatasetLoader(tmp_path).fingerprint()
    first.close()
    second.close()


def test_repeated_observations_retain_unique_source_rows():
    source = Path(__file__).resolve().parents[2] / "source_data"
    with duckdb.connect() as connection:
        DatasetLoader(source).register_views(connection)
        connection.execute(
            "INSERT INTO flights SELECT * REPLACE (999999 AS column00) FROM flights LIMIT 1"
        )
        snapshots = build_snapshots(
            connection, source, dict.fromkeys(DATASETS, "a" * 64), "test", "2026-10-17"
        )
        flight = next(item for item in snapshots if item.dataset_name == "flights")
        assert flight.row_count == 277978
        assert flight.repeated_observations == 1
        assert flight.grain == ["column00"]
        connection.execute("INSERT INTO flights SELECT * FROM flights WHERE column00=999999")
        with pytest.raises(DatasetUnavailableError, match="Duplicate"):
            build_snapshots(
                connection, source, dict.fromkeys(DATASETS, "a" * 64), "test", "2026-10-17"
            )


def test_invalid_date_is_a_safe_source_error_and_closes_connection(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[2] / "source_data"
    for file in source.glob("*.csv"):
        shutil.copyfile(file, tmp_path / file.name)
    flight_file = tmp_path / DATASETS["flights"].filename
    with flight_file.open(encoding="utf-8", newline="") as stream:
        header = stream.readline()
        row = next(csv.reader([stream.readline()]))
        remainder = stream.read()
    row[DATASETS["flights"].columns.index("day")] = "32"
    replacement = io.StringIO(newline="")
    csv.writer(replacement).writerow(row)
    flight_file.write_text(header + replacement.getvalue() + remainder, encoding="utf-8")
    connection = duckdb.connect()
    monkeypatch.setattr(duckdb, "connect", lambda **kwargs: connection)
    with pytest.raises(DatasetUnavailableError, match="could not be loaded or validated"):
        DuckDBExecutor(str(tmp_path))
    with pytest.raises(duckdb.ConnectionException, match="closed"):
        connection.execute("SELECT 1")
