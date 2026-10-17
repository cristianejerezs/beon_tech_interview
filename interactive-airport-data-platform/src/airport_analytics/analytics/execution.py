"""Bounded read-only execution over validated local CSV snapshot views."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, RLock, Timer
from typing import Any

import duckdb

from airport_analytics.analytics.query_compiler import compile_analysis_plan
from airport_analytics.config import Settings
from airport_analytics.data.loader import DatasetLoader, SnapshotManifest
from airport_analytics.errors import QueryExecutionError, QueryTimeoutError
from airport_analytics.models import AnalysisPlan


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    snapshot_id: str
    manifest: SnapshotManifest


class DuckDBExecutor:
    def __init__(
        self,
        source_data_dir: str,
        *,
        timeout_seconds: int = 30,
    ) -> None:
        if timeout_seconds < 1:
            raise ValueError("Query timeout must be positive.")
        self.timeout_seconds = timeout_seconds
        self._connection = duckdb.connect(database=":memory:")
        self._lock = RLock()
        self._closed = False
        self.manifest = DatasetLoader(source_data_dir).register_views(self._connection)

    @classmethod
    def from_settings(cls, settings: Settings) -> DuckDBExecutor:
        return cls(
            str(settings.source_data_dir),
            timeout_seconds=settings.query_timeout_seconds,
        )

    def execute(self, plan: AnalysisPlan) -> QueryResult:
        compiled = compile_analysis_plan(plan)
        if not compiled.sql.lstrip().upper().startswith("SELECT "):
            raise QueryExecutionError("Only application-compiled SELECT queries are permitted.")
        timeout_event = Event()

        def interrupt_query() -> None:
            timeout_event.set()
            self._connection.interrupt()

        with self._lock:
            if self._closed:
                raise QueryExecutionError("The analytical connection is closed.")
            timer = Timer(self.timeout_seconds, interrupt_query)
            timer.daemon = True
            timer.start()
            try:
                cursor = self._connection.execute(compiled.sql, compiled.parameters)
                columns = tuple(description[0] for description in cursor.description or ())
                rows = tuple(dict(zip(columns, row, strict=True)) for row in cursor.fetchall())
            except duckdb.Error as exc:
                if timeout_event.is_set():
                    raise QueryTimeoutError() from exc
                raise QueryExecutionError("The compiled analysis query failed.") from exc
            finally:
                timer.cancel()
        return QueryResult(
            columns=columns,
            rows=rows,
            snapshot_id=self.manifest.snapshot_id,
            manifest=self.manifest,
        )

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def __enter__(self) -> DuckDBExecutor:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
