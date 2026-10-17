"""Local CSV snapshot verification and DuckDB view registration."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from airport_analytics.data.catalog import DATASETS
from airport_analytics.data.validation import build_snapshots, measure_join_coverage
from airport_analytics.errors import DatasetUnavailableError
from airport_analytics.models import DatasetSnapshot


@dataclass(frozen=True)
class SnapshotManifest:
    snapshot_id: str
    datasets: tuple[DatasetSnapshot, ...]
    join_coverage: dict[str, dict[str, int | float]]
    flight_period_start: str
    flight_period_end: str
    origin_airports: tuple[str, ...]


class DatasetLoader:
    def __init__(self, source_data_dir: str | Path) -> None:
        self.source_data_dir = Path(source_data_dir).resolve()

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _quote_path(path: Path) -> str:
        return str(path).replace("'", "''")

    def _verify_file_headers(self, dataset_id: str, path: Path) -> None:
        dataset = DATASETS[dataset_id]
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as source:
                actual = next(csv.reader(source))
        except (OSError, UnicodeError, StopIteration, csv.Error) as exc:
            raise DatasetUnavailableError(
                f"Could not read the expected header from {dataset.filename}."
            ) from exc

        normalized = [
            "column00" if index == 0 and not column else column
            for index, column in enumerate(actual)
        ]
        if normalized != list(dataset.columns):
            raise DatasetUnavailableError(
                f"Unexpected source headers in {dataset.filename}; analytics cannot "
                "use this snapshot."
            )

    def register_views(self, connection: duckdb.DuckDBPyConnection) -> SnapshotManifest:
        missing = [
            dataset.filename
            for dataset in DATASETS.values()
            if not (self.source_data_dir / dataset.filename).is_file()
        ]
        if missing:
            raise DatasetUnavailableError(
                f"Required source files are missing: {', '.join(missing)}."
            )

        checksums: dict[str, str] = {}
        for dataset_id, dataset in DATASETS.items():
            path = self.source_data_dir / dataset.filename
            self._verify_file_headers(dataset_id, path)
            checksums[dataset_id] = self._sha256(path)
            sql_path = self._quote_path(path)
            connection.execute(
                f"CREATE OR REPLACE TEMP TABLE {dataset.table_name} AS "
                f"SELECT * FROM read_csv_auto('{sql_path}', header=true, nullstr='NA', "
                "sample_size=-1)"
            )

        digest_material = "".join(
            f"{dataset_id}:{checksums[dataset_id]}\n" for dataset_id in sorted(checksums)
        )
        snapshot_id = hashlib.sha256(digest_material.encode("utf-8")).hexdigest()
        snapshots = build_snapshots(
            connection=connection,
            source_data_dir=self.source_data_dir,
            checksums=checksums,
            snapshot_id=snapshot_id,
            validated_at=datetime.now(UTC).isoformat(),
        )
        join_coverage = {
            name: {
                "total": total,
                "matched": matched,
                "unmatched": total - matched,
                "fraction": (matched / total if total else 0.0),
            }
            for name, (total, matched) in measure_join_coverage(connection).items()
        }
        period = connection.execute(
            "SELECT MIN(make_date(year, month, day)), MAX(make_date(year, month, day)) FROM flights"
        ).fetchone()
        origin_airports = tuple(
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT origin FROM flights WHERE origin IS NOT NULL ORDER BY origin"
            ).fetchall()
        )
        if period[0] is None or period[1] is None:
            raise DatasetUnavailableError("The flight dataset has no usable date range.")
        return SnapshotManifest(
            snapshot_id=snapshot_id,
            datasets=tuple(snapshots),
            join_coverage=join_coverage,
            flight_period_start=period[0].isoformat(),
            flight_period_end=period[1].isoformat(),
            origin_airports=origin_airports,
        )
