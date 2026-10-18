"""Bounded read-only execution over validated local CSV snapshot views."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, RLock, Timer
from typing import Any, Literal

import duckdb

from airport_analytics.analytics.entity_resolution import EntityDirectory
from airport_analytics.analytics.query_compiler import (
    CompiledQuery,
    compile_analysis_plan,
    compile_listing,
    compile_summary,
    listing_sort,
)
from airport_analytics.config import Settings
from airport_analytics.data.loader import DatasetLoader, SnapshotManifest
from airport_analytics.errors import (
    AuthorizationError,
    DatasetUnavailableError,
    InvalidPlanError,
    QueryExecutionError,
    QueryTimeoutError,
)
from airport_analytics.models import AnalysisPlan, BrowsePage, ResolvedInterpretation
from airport_analytics.observability.timing import timed_stage


def listing_bindings(
    interpretation: ResolvedInterpretation,
    sort_field: str,
    direction: str,
) -> tuple[str, str]:
    scope = interpretation.model_dump(
        mode="json",
        include={
            "operation_id",
            "population",
            "filters",
            "date_scope",
        },
    )

    def digest(value: object) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    return digest(scope), digest({"field": sort_field, "direction": direction})


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    snapshot_id: str
    manifest: SnapshotManifest
    scope_evidence: dict[str, Any] = field(default_factory=dict)
    routes: dict[str, Any] = field(default_factory=dict)
    ranking: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SummaryQueryResult:
    rows: tuple[dict[str, Any], ...]
    scope: dict[str, Any]
    routes: tuple[dict[str, Any], ...]


class DuckDBExecutor:
    def __init__(
        self,
        source_data_dir: str,
        *,
        timeout_seconds: int = 30,
        coverage_path: str | Path | None = None,
        weather_units_path: str | Path | None = None,
    ) -> None:
        if timeout_seconds < 1:
            raise ValueError("Query timeout must be positive.")
        self.timeout_seconds = timeout_seconds
        self._connection = duckdb.connect(database=":memory:")
        self._lock = RLock()
        self._closed = False
        self._loader = DatasetLoader(source_data_dir)
        self._coverage_path = Path(coverage_path).resolve() if coverage_path is not None else None
        self._weather_units_path = (
            Path(weather_units_path).resolve() if weather_units_path else None
        )
        try:
            self.manifest = self._loader.register_views(self._connection)
            self.context = self._loader.semantic_context(
                self.manifest,
                coverage_path=self._coverage_path,
                unit_provenance=self._current_unit_provenance(),
            )
            from airport_analytics.data.coverage import load_coverage

            origins = {
                row[0]
                for row in self._connection.execute(
                    "SELECT DISTINCT origin FROM flights WHERE origin IS NOT NULL"
                ).fetchall()
            }
            self.coverage = load_coverage(
                self._coverage_path,
                self.manifest.snapshot_id,
                origins,
            )
        except DatasetUnavailableError:
            self.close()
            raise

    @classmethod
    def from_settings(cls, settings: Settings) -> DuckDBExecutor:
        return cls(
            str(settings.source_data_dir),
            timeout_seconds=settings.query_timeout_seconds,
            coverage_path=settings.coverage_path,
            weather_units_path=settings.weather_units_path,
        )

    def execute(self, plan: AnalysisPlan) -> QueryResult:
        compiled = compile_analysis_plan(plan, lookahead=True)
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
                all_rows = self._run_compiled_query(compiled)
                columns = compiled.output_columns
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
                scope_rows = self._run_compiled_query(scope)
                if len(scope_rows) != 1:
                    raise QueryExecutionError("Scope evidence requires one result row.")
                scope_evidence = scope_rows[0]
                routes: dict[str, Any] = {}
                if plan.metric_id == "distinct_destination_count":
                    query = compile_analysis_plan(plan, evidence="routes")
                    route_rows = self._run_compiled_query(query)
                    routes = {
                        "columns": list(query.output_columns),
                        "rows": list(route_rows[:500]),
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

    def require_current_binding(self, snapshot_id: str, context_id: str) -> None:
        with self._lock:
            if self._closed:
                raise QueryExecutionError("The analytical connection is closed.")
            if snapshot_id != self.manifest.snapshot_id or context_id != self.context.context_id:
                raise DatasetUnavailableError(
                    "The source/context binding is stale. Explicitly restart the analysis."
                )
            expected = {dataset.dataset_name: dataset.sha256 for dataset in self.manifest.datasets}
            if dict(self._loader.fingerprint()) != expected:
                raise DatasetUnavailableError(
                    "The source changed. Explicitly restart against a newly validated snapshot."
                )
            current = self._loader.semantic_context(
                self.manifest,
                coverage_path=self._coverage_path,
                unit_provenance=self._current_unit_provenance(),
            )
            if current.context_id != self.context.context_id:
                raise DatasetUnavailableError(
                    "The semantic context changed. Explicitly restart the analysis."
                )
            from airport_analytics.data.coverage import load_coverage

            origins = {
                row[0]
                for row in self._connection.execute(
                    "SELECT DISTINCT origin FROM flights WHERE origin IS NOT NULL"
                ).fetchall()
            }
            if (
                load_coverage(self._coverage_path, self.manifest.snapshot_id, origins)
                != self.coverage
            ):
                raise DatasetUnavailableError(
                    "The coverage evidence changed. Explicitly restart the analysis."
                )

    def _current_unit_provenance(self) -> dict[str, str]:
        from airport_analytics.data.units import weather_unit_provenance

        weather_sha = next(
            dataset.sha256
            for dataset in self.manifest.datasets
            if dataset.dataset_name == "weather"
        )
        return weather_unit_provenance(self._weather_units_path, weather_sha)

    def entity_directory(self) -> EntityDirectory:
        with self._lock:
            if self._closed:
                raise QueryExecutionError("The analytical connection is closed.")
            self.require_current_binding(self.manifest.snapshot_id, self.context.context_id)
            try:
                airports = self._connection.execute(
                    "SELECT faa, name FROM airports ORDER BY faa"
                ).fetchall()
                airlines = self._connection.execute(
                    "SELECT carrier, name FROM airlines ORDER BY carrier"
                ).fetchall()
                observed = self._connection.execute(
                    "SELECT LIST(DISTINCT origin) FILTER (WHERE origin IS NOT NULL), "
                    "LIST(DISTINCT dest) FILTER (WHERE dest IS NOT NULL), "
                    "LIST(DISTINCT carrier) FILTER (WHERE carrier IS NOT NULL) FROM flights"
                ).fetchone()
            except duckdb.Error as exc:
                raise QueryExecutionError("Entity references could not be verified.") from exc
            if observed is None:
                raise QueryExecutionError("Entity populations could not be verified.")
            return EntityDirectory(
                airports=airports,
                airlines=airlines,
                observed_origins=set(observed[0] or []),
                observed_destinations=set(observed[1] or []),
                observed_airlines=set(observed[2] or []),
            )

    @timed_stage("execution")
    def execute_summary(self, interpretation: ResolvedInterpretation) -> SummaryQueryResult:
        queries = [
            compile_summary(interpretation),
            compile_summary(interpretation, purpose="scope"),
        ]
        if interpretation.measure_ids == ["distinct_destination_count"]:
            queries.append(compile_summary(interpretation, purpose="routes"))
        timeout_event = Event()

        def interrupt_query() -> None:
            timeout_event.set()
            self._connection.interrupt()

        with self._lock:
            self.require_current_binding(interpretation.snapshot_id, interpretation.context_id)
            timer = Timer(self.timeout_seconds, interrupt_query)
            timer.daemon = True
            timer.start()
            try:
                rows = self._run_compiled_query(queries[0])
                scope_rows = self._run_compiled_query(queries[1])
                if len(scope_rows) != 1:
                    raise QueryExecutionError("Summary scope evidence requires one row.")
                routes = self._run_compiled_query(queries[2]) if len(queries) == 3 else ()
                self.require_current_binding(interpretation.snapshot_id, interpretation.context_id)
                return SummaryQueryResult(rows=rows, scope=scope_rows[0], routes=routes)
            except duckdb.Error as exc:
                if timeout_event.is_set():
                    raise QueryTimeoutError() from exc
                raise QueryExecutionError("The compiled summary query failed.") from exc
            finally:
                timer.cancel()

    @timed_stage("execution")
    def execute_multi_stage(
        self,
        interpretation: ResolvedInterpretation,
        *,
        report_id: str,
        preflight: bool = False,
    ):
        from airport_analytics.analytics.multi_stage import (
            distribution_constraints,
            execute_multi_stage,
        )

        timeout_event = Event()

        def interrupt() -> None:
            timeout_event.set()
            self._connection.interrupt()

        with self._lock:
            self.require_current_binding(interpretation.snapshot_id, interpretation.context_id)
            timer = Timer(self.timeout_seconds, interrupt)
            timer.daemon = True
            timer.start()
            try:
                if preflight:
                    if interpretation.operation_id != "distribution":
                        raise InvalidPlanError("Only distribution eligibility uses this preflight.")
                    distribution_constraints(self, interpretation, timed_out=timeout_event.is_set)
                    result = None
                else:
                    result = execute_multi_stage(
                        self, interpretation, report_id, timed_out=timeout_event.is_set
                    )
                self.require_current_binding(interpretation.snapshot_id, interpretation.context_id)
                return result
            except duckdb.Error as exc:
                if timeout_event.is_set():
                    raise QueryTimeoutError() from exc
                raise QueryExecutionError("The multi-stage analytical query failed.") from exc
            finally:
                timer.cancel()

    @timed_stage("execution")
    def browse(
        self,
        interpretation: ResolvedInterpretation,
        *,
        analyst_id: str,
        session_id: str,
        page_size: Literal[25, 50, 100, 500] = 100,
        page_index: int = 1,
        sort_field: str | None = None,
        direction: Literal["asc", "desc"] | None = None,
        previous: BrowsePage | None = None,
    ) -> BrowsePage:
        if page_size not in {25, 50, 100, 500} or isinstance(page_size, bool):
            raise ValueError("Page size must be 25, 50, 100 or 500.")
        if not isinstance(page_index, int) or isinstance(page_index, bool) or page_index < 1:
            raise ValueError("Page index must be positive.")
        field = listing_sort(interpretation, sort_field)
        direction = direction or (
            interpretation.order[0].direction if interpretation.order else "asc"
        )
        scope_hash, order_hash = listing_bindings(interpretation, field, direction)
        notice = None
        if previous is not None:
            previous = BrowsePage.model_validate(previous.model_dump())
            if previous.analyst_id != analyst_id or previous.session_id != session_id:
                raise AuthorizationError()
            if (
                previous.request_id != interpretation.request_id
                or previous.section_id != interpretation.section_id
                or previous.revision != interpretation.revision
            ):
                raise AuthorizationError("The listing continuation belongs to a different request.")
            if (
                previous.scope_hash != scope_hash
                or previous.order_hash != order_hash
                or previous.page_size != page_size
            ):
                page_index = 1
                notice = "Scope, ordering or page size changed; showing page one."
            if (
                previous.snapshot_id != interpretation.snapshot_id
                or previous.context_id != interpretation.context_id
            ):
                raise DatasetUnavailableError(
                    "Historical browsing is unavailable; explicitly restart."
                )
        timeout_event = Event()

        def interrupt() -> None:
            timeout_event.set()
            self._connection.interrupt()

        with self._lock:
            self.require_current_binding(interpretation.snapshot_id, interpretation.context_id)
            timer = Timer(self.timeout_seconds, interrupt)
            timer.daemon = True
            timer.start()
            try:
                total = int(
                    self._run_compiled_query(
                        compile_listing(interpretation, purpose="count"),
                    )[0]["total_rows"]
                )
                pages = (total + page_size - 1) // page_size
                if page_index > max(1, pages):
                    page_index = 1
                    notice = "Requested page is out of range; showing page one."
                rows = self._run_compiled_query(
                    compile_listing(
                        interpretation,
                        limit=page_size,
                        offset=(page_index - 1) * page_size,
                        sort_field=field,
                        direction=direction,
                    )
                )
                self.require_current_binding(interpretation.snapshot_id, interpretation.context_id)
            except duckdb.Error as exc:
                if timeout_event.is_set():
                    raise QueryTimeoutError() from exc
                raise QueryExecutionError("The compiled listing query failed.") from exc
            finally:
                timer.cancel()
        identity = "source_row_id" if interpretation.operation_id == "flight_records" else "code"
        return BrowsePage(
            analyst_id=analyst_id,
            session_id=session_id,
            request_id=interpretation.request_id,
            revision=interpretation.revision,
            section_id=interpretation.section_id,
            snapshot_id=interpretation.snapshot_id,
            context_id=interpretation.context_id,
            scope_hash=scope_hash,
            order_hash=order_hash,
            sort_field=field,
            direction=direction,
            page_size=page_size,
            page_index=page_index,
            total_rows=total,
            total_pages=pages,
            identity_column=identity,
            first_identity=rows[0][identity] if rows else None,
            last_identity=rows[-1][identity] if rows else None,
            rows=list(rows),
            notice=notice,
        )

    @timed_stage("execution")
    def listing_export_rows(
        self,
        interpretation: ResolvedInterpretation,
        *,
        allocation: int,
        expected_total: int,
    ) -> tuple[dict[str, Any], ...]:
        timeout_event = Event()

        def interrupt() -> None:
            timeout_event.set()
            self._connection.interrupt()

        with self._lock:
            self.require_current_binding(interpretation.snapshot_id, interpretation.context_id)
            timer = Timer(self.timeout_seconds, interrupt)
            timer.daemon = True
            timer.start()
            try:
                total = self._run_compiled_query(
                    compile_listing(interpretation, purpose="count"),
                )[0]["total_rows"]
                if total != expected_total:
                    raise DatasetUnavailableError("The listing population changed; restart export.")
                rows = self._run_compiled_query(
                    compile_listing(
                        interpretation,
                        limit=allocation,
                        direction=interpretation.order[0].direction
                        if interpretation.order
                        else "asc",
                    )
                )
                self.require_current_binding(interpretation.snapshot_id, interpretation.context_id)
                return rows
            except duckdb.Error as exc:
                if timeout_event.is_set():
                    raise QueryTimeoutError() from exc
                raise QueryExecutionError("The listing export query failed.") from exc
            finally:
                timer.cancel()

    def _run_compiled_query(self, query: CompiledQuery) -> tuple[dict[str, Any], ...]:
        cursor = self._connection.execute(query.sql, query.parameters)
        columns = tuple(description[0] for description in cursor.description or ())
        if columns != query.output_columns:
            raise QueryExecutionError(
                "The compiled query output does not match its declared schema."
            )
        return tuple(dict(zip(columns, row, strict=True)) for row in cursor.fetchall())

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def __enter__(self) -> DuckDBExecutor:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
