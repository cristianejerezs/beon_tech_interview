"""Bounded read-only execution over validated local CSV snapshot views."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event, RLock, Timer
from typing import Any

import duckdb

from airport_analytics.analytics.query_compiler import compile_analysis_plan
from airport_analytics.config import Settings
from airport_analytics.data.loader import DatasetLoader, SnapshotManifest
from airport_analytics.errors import DatasetUnavailableError, QueryExecutionError, QueryTimeoutError
from airport_analytics.models import AnalysisPlan


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    snapshot_id: str
    manifest: SnapshotManifest
    scope_evidence: dict[str, Any] = field(default_factory=dict)
    routes: dict[str, Any] = field(default_factory=dict)
    ranking: dict[str, Any] = field(default_factory=dict)


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
        try:
            self.manifest = DatasetLoader(source_data_dir).register_views(self._connection)
        except DatasetUnavailableError:
            self.close()
            raise

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
                # One look-ahead row detects a tie truncated by the requested limit.
                parameters = (*compiled.parameters[:-1], plan.row_limit + 1)
                cursor = self._connection.execute(compiled.sql, parameters)
                columns = tuple(description[0] for description in cursor.description or ())
                all_rows = tuple(dict(zip(columns, row, strict=True)) for row in cursor.fetchall())
                rows = all_rows[: plan.row_limit]
                ranking: dict[str, Any] = {}
                if plan.sort and plan.sort.field_id == plan.metric_id:
                    values = [row["metric_value"] for row in rows]
                    ranking = {
                        "has_visible_ties": len(values) != len(set(values)),
                        "cutoff_tie": len(all_rows) > len(rows)
                        and all_rows[len(rows)]["metric_value"] == rows[-1]["metric_value"],
                    }
                scope = compile_analysis_plan(plan, evidence="scope")
                cursor = self._connection.execute(scope.sql, scope.parameters)
                scope_columns = [description[0] for description in cursor.description]
                scope_evidence = dict(zip(scope_columns, cursor.fetchone(), strict=True))
                routes: dict[str, Any] = {}
                if plan.metric_id == "distinct_destination_count":
                    query = compile_analysis_plan(plan, evidence="routes")
                    cursor = self._connection.execute(query.sql, query.parameters)
                    route_columns = [description[0] for description in cursor.description]
                    route_rows = [
                        dict(zip(route_columns, row, strict=True)) for row in cursor.fetchall()
                    ]
                    routes = {
                        "columns": route_columns,
                        "rows": route_rows[:500],
                        "complete": len(route_rows) <= 500,
                        "population": "All routes in the effective filtered scope, before top-N.",
                    }
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
            scope_evidence=scope_evidence,
            routes=routes,
            ranking=ranking,
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
