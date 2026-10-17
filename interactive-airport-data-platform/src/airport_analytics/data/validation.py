"""Source schema, missingness, and join-integrity validation."""

from __future__ import annotations

from pathlib import Path

import duckdb

from airport_analytics.data.catalog import (
    DATASETS,
    SCHEMA_VERSION,
    SOURCE_FRACTIONAL_FIELDS,
    SOURCE_GRAINS,
    SOURCE_TEXT_FIELDS,
)
from airport_analytics.errors import DatasetUnavailableError
from airport_analytics.models import DatasetSnapshot

REFERENCE_KEYS: tuple[tuple[str, str], ...] = (
    ("airlines", "carrier"),
    ("airports", "faa"),
    ("planes", "tailnum"),
)

JOIN_COVERAGE_SQL: dict[str, str] = {
    "origin_airport": (
        "SELECT COUNT(*), COUNT(o.faa) FROM flights f LEFT JOIN airports o ON f.origin = o.faa"
    ),
    "destination_airport": (
        "SELECT COUNT(*), COUNT(d.faa) FROM flights f LEFT JOIN airports d ON f.dest = d.faa"
    ),
    "airline": (
        "SELECT COUNT(*), COUNT(a.carrier) "
        "FROM flights f LEFT JOIN airlines a ON f.carrier = a.carrier"
    ),
    "aircraft": (
        "SELECT COUNT(*), COUNT(p.tailnum) "
        "FROM flights f LEFT JOIN planes p ON f.tailnum = p.tailnum"
    ),
    "weather_origin_time_exact": (
        "SELECT COUNT(*), COUNT(w.origin) "
        "FROM flights f LEFT JOIN weather w "
        "ON f.origin = w.origin AND f.time_hour = w.time_hour"
    ),
}


def measure_join_coverage(
    connection: duckdb.DuckDBPyConnection,
) -> dict[str, tuple[int, int]]:
    return {
        name: (int(total), int(matched))
        for name, sql in JOIN_COVERAGE_SQL.items()
        for total, matched in [connection.execute(sql).fetchone()]
    }


def validate_reference_cardinality(connection: duckdb.DuckDBPyConnection) -> None:
    for table, key in REFERENCE_KEYS:
        duplicate = connection.execute(
            f'SELECT "{key}" FROM {table} WHERE "{key}" IS NOT NULL '
            f'GROUP BY "{key}" HAVING COUNT(*) > 1 LIMIT 1'
        ).fetchone()
        if duplicate is not None:
            raise DatasetUnavailableError(
                f"Reference key {table}.{key} is not unique; joining would duplicate flight rows."
            )

    duplicate_weather = connection.execute(
        """
        SELECT origin, time_hour
        FROM weather
        WHERE origin IS NOT NULL AND time_hour IS NOT NULL
        GROUP BY origin, time_hour
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    ).fetchone()
    if duplicate_weather is not None:
        raise DatasetUnavailableError(
            "Weather origin/time keys are not unique; the contextual join is unsafe."
        )


def build_snapshots(
    connection: duckdb.DuckDBPyConnection,
    source_data_dir: Path,
    checksums: dict[str, str],
    snapshot_id: str,
    validated_at: str,
) -> list[DatasetSnapshot]:
    validate_reference_cardinality(connection)
    coverage_counts = measure_join_coverage(connection)
    snapshots: list[DatasetSnapshot] = []

    for dataset in DATASETS.values():
        describe = connection.execute(f"DESCRIBE SELECT * FROM {dataset.table_name}").fetchall()
        headers = [str(row[0]) for row in describe]
        if headers != list(dataset.columns):
            raise DatasetUnavailableError(
                f"Unexpected columns in {dataset.filename}; analytics cannot use this snapshot."
            )
        validate_dataset_structure(connection, dataset.dataset_id, describe)

        row_count = int(
            connection.execute(f"SELECT COUNT(*) FROM {dataset.table_name}").fetchone()[0]
        )
        if dataset.dataset_id == "flights" and row_count == 0:
            raise DatasetUnavailableError("The flight dataset contains no records.")

        missing_counts = connection.execute(
            "SELECT "
            + ", ".join(f'COUNT(*) FILTER (WHERE "{column}" IS NULL)' for column in dataset.columns)
            + f" FROM {dataset.table_name}"
        ).fetchone()
        missingness = {
            column: (int(missing_counts[index]) / row_count if row_count else 0.0)
            for index, column in enumerate(dataset.columns)
        }

        join_key_coverage: dict[str, float] = {}
        if dataset.dataset_id == "flights":
            join_key_coverage = {
                name: (matched / total if total else 0.0)
                for name, (total, matched) in coverage_counts.items()
            }

        snapshots.append(
            DatasetSnapshot(
                snapshot_id=snapshot_id,
                dataset_name=dataset.dataset_id,
                relative_path=(Path("source_data") / dataset.filename).as_posix(),
                sha256=checksums[dataset.dataset_id],
                row_count=row_count,
                headers=headers,
                schema_version=SCHEMA_VERSION,
                missingness=missingness,
                join_key_coverage=join_key_coverage,
                validated_at=validated_at,
                grain=list(SOURCE_GRAINS[dataset.dataset_id]),
                repeated_observations=(
                    int(
                        connection.execute(
                            "SELECT COALESCE(SUM(n - 1), 0) FROM "
                            "(SELECT * EXCLUDE (column00), COUNT(*) AS n FROM flights "
                            "GROUP BY ALL)"
                        ).fetchone()[0]
                    )
                    if dataset.dataset_id == "flights"
                    else 0
                ),
            )
        )
    return snapshots


def validate_dataset_structure(
    connection: duckdb.DuckDBPyConnection, dataset_id: str, describe: list
) -> None:
    dataset = DATASETS[dataset_id]
    for column, actual_type, *_ in describe:
        if column in SOURCE_TEXT_FIELDS[dataset_id]:
            allowed = {"VARCHAR"}
        elif column == "time_hour":
            allowed = {"TIMESTAMP WITH TIME ZONE"}
        elif column in SOURCE_FRACTIONAL_FIELDS[dataset_id]:
            allowed = {"BIGINT", "DOUBLE"}
        else:
            allowed = {"BIGINT"}
        if actual_type not in allowed:
            raise DatasetUnavailableError(
                f"Unexpected source type for {dataset_id}.{column}; expected {sorted(allowed)}."
            )
    keys = SOURCE_GRAINS[dataset_id]
    nulls = " OR ".join(f'"{key}" IS NULL' for key in keys)
    group = ", ".join(f'"{key}"' for key in keys)
    if connection.execute(f"SELECT 1 FROM {dataset.table_name} WHERE {nulls} LIMIT 1").fetchone():
        raise DatasetUnavailableError(f"Missing source grain key in {dataset_id}.")
    if connection.execute(
        f"SELECT 1 FROM {dataset.table_name} GROUP BY {group} HAVING COUNT(*) > 1 LIMIT 1"
    ).fetchone():
        raise DatasetUnavailableError(f"Duplicate source grain key in {dataset_id}.")
