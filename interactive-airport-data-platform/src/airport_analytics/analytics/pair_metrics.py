"""Bounded pair and weather-panel evidence compiled into DuckDB."""

from __future__ import annotations

import re
from math import isfinite, nextafter
from typing import Any

from airport_analytics.analytics.query_compiler import (
    _SUMMARY_SOURCE,
    CompiledQuery,
    _compile_filter,
)
from airport_analytics.data.catalog import EXPLORATION_MEASURES
from airport_analytics.errors import InvalidPlanError
from airport_analytics.models import (
    CategoryIdentity,
    DensityCell,
    DensityEvidence,
    EvidencePair,
    GroupEvidence,
    NumericEvidence,
    PairEvidence,
    ResolvedInterpretation,
    WeatherPanelResult,
    WeatherVariableEvidence,
)

PAIR_LIMIT = 5000
DENSITY_BINS = 20
WEATHER_VARIABLES = ("temp", "wind_speed", "precip", "visib")
WEATHER_UNITS = {
    "temp": "F",
    "wind_speed": "mph",
    "precip": "inches",
    "visib": "miles",
}
WEATHER_PROVENANCE_PATTERN = re.compile(
    r"weather_units:v1;sha256=([0-9a-f]{64});"
    r"temp=F;wind_speed=mph;precip=inches;visib=miles"
)
WEATHER_EXPRESSIONS = {variable: f"w.{variable}" for variable in WEATHER_VARIABLES}
PAIR_EXPRESSIONS = {
    "departure_delay": "f.dep_delay",
    "arrival_delay": "f.arr_delay",
    "distance": "f.distance",
}
PRECIPITATION_LABELS = {
    "unmatched": ("unmatched_weather", "Unmatched weather"),
    "missing_precipitation": ("missing_precipitation", "Missing precipitation"),
    "none": ("none", "No precipitation"),
    "light": ("light", "Light precipitation"),
    "at_least_0_1_in": ("at_least_0_1_in", "At least 0.1 inches"),
}


def _scope(interpretation: ResolvedInterpretation) -> tuple[str, tuple[Any, ...]]:
    clauses: list[str] = []
    parameters: list[Any] = []
    for predicate in interpretation.filters:
        clause, values = _compile_filter(predicate.field_id, predicate.operator, predicate.value)
        clauses.append(clause)
        parameters.extend(values)
    if interpretation.date_scope is not None:
        for boundary, operator in (
            (interpretation.date_scope.start, ">="),
            (interpretation.date_scope.end, "<="),
        ):
            if boundary is not None:
                clauses.append(f"make_date(f.year, f.month, f.day) {operator} ?")
                parameters.append(boundary)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), tuple(parameters)


def _weather_units_verified(executor: Any) -> bool:
    provenance = dict(executor.context.unit_provenance).get("weather")
    match = WEATHER_PROVENANCE_PATTERN.fullmatch(provenance or "")
    weather_snapshot = next(
        (
            dataset.sha256
            for dataset in executor.manifest.datasets
            if dataset.dataset_name == "weather"
        ),
        None,
    )
    return match is not None and weather_snapshot is not None and match.group(1) == weather_snapshot


def _compiled(
    interpretation: ResolvedInterpretation,
    sql: str,
    parameters: tuple[Any, ...],
    purpose: str,
    columns: tuple[str, ...],
) -> CompiledQuery:
    return CompiledQuery(
        sql=sql,
        parameters=parameters,
        plan=interpretation,
        purpose=purpose,  # type: ignore[arg-type]
        kind="owned_cte",
        output_columns=columns,
    )


def _pair_source(
    interpretation: ResolvedInterpretation,
    *,
    weather_variable: str | None,
    origin: str | None,
) -> tuple[str, tuple[Any, ...], str, str, str]:
    where, parameters = _scope(interpretation)
    if weather_variable is not None:
        if weather_variable not in WEATHER_EXPRESSIONS:
            raise InvalidPlanError("Weather pairings use only the four catalog variables.")
        if interpretation.operation_id != "weather_relationship":
            raise InvalidPlanError("Weather variables require a weather relationship.")
        y_expression = "AVG(f.dep_delay)"
        scoped_flights = (
            "scoped_flights AS (SELECT f.origin, f.time_hour, f.dep_delay"
            + _SUMMARY_SOURCE
            + where
            + (" AND " if where else " WHERE ")
            + "f.origin = ?)"
            if origin is not None
            else "scoped_flights AS (SELECT f.origin, f.time_hour, f.dep_delay"
            + _SUMMARY_SOURCE
            + where
            + ")"
        )
        scoped_parameters = parameters + ((origin,) if origin is not None else ())
        ctes = (
            "WITH " + scoped_flights + ", hourly AS (SELECT origin, time_hour, "
            "AVG(dep_delay) AS y, COUNT(*) AS flight_count, "
            "COUNT(dep_delay) AS known_delay_flights "
            "FROM scoped_flights GROUP BY origin, time_hour), "
            "scoped AS (SELECT CAST(h.origin AS VARCHAR) || '|' || "
            "strftime(timezone('UTC', h.time_hour), '%Y-%m-%dT%H:%M:%SZ') AS source_id, "
            + WEATHER_EXPRESSIONS[weather_variable]
            + " AS x, h.y AS y, h.flight_count, h.known_delay_flights, "
            "w.origin AS matched_weather_origin "
            "FROM hourly h LEFT JOIN weather w "
            "ON h.origin = w.origin AND h.time_hour = w.time_hour)"
        )
        return (
            ctes,
            scoped_parameters,
            weather_variable,
            "departure_delay",
            y_expression,
        )

    if interpretation.operation_id != "flight_relationship" or interpretation.pairing is None:
        raise InvalidPlanError("Flight pair evidence requires a resolved flight pairing.")
    x_field, y_field = interpretation.pairing.x, interpretation.pairing.y
    try:
        x_expression = PAIR_EXPRESSIONS[x_field]
        y_expression = PAIR_EXPRESSIONS[y_field]
    except KeyError as exc:
        raise InvalidPlanError("Unsupported flight relationship field.") from exc
    ctes = (
        "WITH scoped AS (SELECT CAST(f.column00 AS VARCHAR) AS source_id, "
        f"{x_expression} AS x, {y_expression} AS y"
        + ", NULL::VARCHAR AS matched_weather_origin"
        + _SUMMARY_SOURCE
        + where
        + ")"
    )
    return ctes, parameters, x_field, y_field, y_expression


def _pair_summary(
    executor: Any,
    interpretation: ResolvedInterpretation,
    ctes: str,
    parameters: tuple[Any, ...],
) -> dict[str, Any]:
    sql = (
        ctes + ", flagged AS (SELECT *, x IS NOT NULL AS x_known, "
        "y IS NOT NULL AS y_known FROM scoped), "
        "valid AS (SELECT x, y FROM flagged WHERE x_known AND y_known), "
        "moments AS (SELECT COUNT(*) AS pair_count, AVG(x) AS mean_x, AVG(y) AS mean_y, "
        "MIN(x) AS min_x, MAX(x) AS max_x, MIN(y) AS min_y, MAX(y) AS max_y FROM valid), "
        "centered AS (SELECT SUM((v.x - m.mean_x) * (v.x - m.mean_x)) AS xx, "
        "SUM((v.y - m.mean_y) * (v.y - m.mean_y)) AS yy, "
        "SUM((v.x - m.mean_x) * (v.y - m.mean_y)) AS xy "
        "FROM valid v CROSS JOIN moments m) "
        ", counts AS (SELECT COUNT(*) AS scoped_count, "
        "COUNT(*) FILTER (WHERE x_known AND y_known) AS pair_count, "
        "COUNT(*) FILTER (WHERE NOT x_known AND y_known) AS x_missing_only, "
        "COUNT(*) FILTER (WHERE x_known AND NOT y_known) AS y_missing_only, "
        "COUNT(*) FILTER (WHERE NOT x_known AND NOT y_known) AS both_missing, "
        "COUNT(*) FILTER (WHERE x IS NOT NULL AND NOT isfinite(x)) AS invalid_x, "
        "COUNT(*) FILTER (WHERE y IS NOT NULL AND NOT isfinite(y)) AS invalid_y, "
        "MIN(x) FILTER (WHERE x_known AND y_known) AS x_extent_min, "
        "MAX(x) FILTER (WHERE x_known AND y_known) AS x_extent_max, "
        "MIN(y) FILTER (WHERE x_known AND y_known) AS y_extent_min, "
        "MAX(y) FILTER (WHERE x_known AND y_known) AS y_extent_max, "
        "COUNT(*) FILTER (WHERE matched_weather_origin IS NULL) AS unmatched_weather, "
        "COUNT(*) FILTER (WHERE matched_weather_origin IS NOT NULL AND NOT y_known) "
        "AS matched_without_delay, "
        "COUNT(*) FILTER (WHERE matched_weather_origin IS NOT NULL AND y_known) "
        "AS matched_with_delay, "
        "COUNT(*) FILTER (WHERE matched_weather_origin IS NOT NULL AND y_known AND NOT x_known) "
        "AS matched_delay_missing_weather FROM flagged) "
        "SELECT counts.*, m.mean_x, m.mean_y, c.xx, c.yy, c.xy "
        "FROM counts CROSS JOIN moments m CROSS JOIN centered c"
    )
    columns = (
        "scoped_count",
        "pair_count",
        "x_missing_only",
        "y_missing_only",
        "both_missing",
        "invalid_x",
        "invalid_y",
        "x_extent_min",
        "x_extent_max",
        "y_extent_min",
        "y_extent_max",
        "unmatched_weather",
        "matched_without_delay",
        "matched_with_delay",
        "matched_delay_missing_weather",
        "mean_x",
        "mean_y",
        "xx",
        "yy",
        "xy",
    )
    rows = executor._run_compiled_query(
        _compiled(interpretation, sql, parameters, "pairs", columns)
    )
    if len(rows) != 1:
        raise ValueError("Pair summary query did not return exactly one row.")
    row = rows[0]
    if row["invalid_x"] or row["invalid_y"]:
        raise ValueError("Nonfinite relationship measurements cannot be paired.")
    return row


def _density_edges(low: float, high: float) -> tuple[list[float], int]:
    if low == high:
        edge = nextafter(low, float("inf"))
        if not isfinite(edge) or edge <= low:
            raise ValueError("A positive density interval cannot represent this constant axis.")
        return [low, edge], 1
    for count in range(DENSITY_BINS, 0, -1):
        width = (high - low) / count
        edges = [low + index * width for index in range(count)] + [high]
        if all(isfinite(edge) for edge in edges) and all(
            left < right for left, right in zip(edges, edges[1:], strict=False)
        ):
            return edges, count
    raise ValueError("Relationship extents cannot be represented as positive density bins.")


def _pair_evidence(
    executor: Any,
    interpretation: ResolvedInterpretation,
    *,
    weather_variable: str | None = None,
    origin: str | None = None,
) -> tuple[PairEvidence, float | None, dict[str, Any]]:
    ctes, parameters, x_field, y_field, _ = _pair_source(
        interpretation, weather_variable=weather_variable, origin=origin
    )
    summary = _pair_summary(executor, interpretation, ctes, parameters)
    pair_count = int(summary["pair_count"])
    scoped_count = int(summary["scoped_count"])
    x_extent = (summary["x_extent_min"], summary["x_extent_max"]) if pair_count else None
    y_extent = (summary["y_extent_min"], summary["y_extent_max"]) if pair_count else None

    pairs: list[EvidencePair] | None = None
    density: DensityEvidence | None = None
    if pair_count <= PAIR_LIMIT:
        pair_columns = ("source_id", "x", "y")
        rows = executor._run_compiled_query(
            _compiled(
                interpretation,
                ctes + " SELECT source_id, x, y FROM scoped "
                "WHERE x IS NOT NULL AND y IS NOT NULL ORDER BY source_id",
                parameters,
                "pairs",
                pair_columns,
            )
        )
        if len(rows) != pair_count:
            raise ValueError("Stored pairs do not match the full known-pair population.")
        pairs = [
            EvidencePair(source_id=str(row["source_id"]), x=row["x"], y=row["y"]) for row in rows
        ]
    elif pair_count:
        assert x_extent is not None and y_extent is not None
        x_edges, x_bins = _density_edges(float(x_extent[0]), float(x_extent[1]))
        y_edges, y_bins = _density_edges(float(y_extent[0]), float(y_extent[1]))
        x_index = (
            "0"
            if x_bins == 1
            else f"LEAST({x_bins - 1}, CAST(FLOOR((x - s.min_x) / "
            f"(s.max_x - s.min_x) * {x_bins}) AS INTEGER))"
        )
        y_index = (
            "0"
            if y_bins == 1
            else f"LEAST({y_bins - 1}, CAST(FLOOR((y - s.min_y) / "
            f"(s.max_y - s.min_y) * {y_bins}) AS INTEGER))"
        )
        density_sql = (
            ctes + ", valid AS (SELECT x, y FROM scoped WHERE x IS NOT NULL AND y IS NOT NULL), "
            "stats AS (SELECT MIN(x) AS min_x, MAX(x) AS max_x, "
            "MIN(y) AS min_y, MAX(y) AS max_y FROM valid), "
            f"binned AS (SELECT {x_index} AS ix, {y_index} AS iy "
            "FROM valid CROSS JOIN stats s) "
            "SELECT ix, iy, COUNT(*) AS count FROM binned "
            "GROUP BY ix, iy ORDER BY ix, iy"
        )
        density_rows = executor._run_compiled_query(
            _compiled(
                interpretation,
                density_sql,
                parameters,
                "density",
                ("ix", "iy", "count"),
            )
        )
        cells = [
            DensityCell(x=int(row["ix"]), y=int(row["iy"]), count=int(row["count"]))
            for row in density_rows
        ]
        if sum(cell.count for cell in cells) != pair_count:
            raise ValueError("Density cells do not reconcile to the full pair population.")
        density = DensityEvidence(x_edges=x_edges, y_edges=y_edges, cells=cells)

    if weather_variable is not None:
        x_unit = (
            WEATHER_UNITS[weather_variable]
            if _weather_units_verified(executor)
            else "recorded units (unverified)"
        )
        y_unit = "minutes"
    else:
        x_unit = EXPLORATION_MEASURES[x_field].unit
        y_unit = EXPLORATION_MEASURES[y_field].unit
    evidence = PairEvidence(
        x_field=x_field,
        y_field=y_field,
        x_unit=x_unit,
        y_unit=y_unit,
        pair_count=pair_count,
        scoped_count=scoped_count,
        x_missing_only=int(summary["x_missing_only"]),
        y_missing_only=int(summary["y_missing_only"]),
        both_missing=int(summary["both_missing"]),
        x_extent=x_extent,
        y_extent=y_extent,
        pairs=pairs,
        density=density,
    )

    coefficient = None
    if weather_variable is not None and pair_count >= 3:
        xx, yy, xy = summary["xx"], summary["yy"], summary["xy"]
        if xx is not None and yy is not None and xx > 0 and yy > 0:
            coefficient = float(xy / (xx * yy) ** 0.5)
            if not isfinite(coefficient):
                coefficient = None
            else:
                coefficient = min(1.0, max(-1.0, coefficient))
    return evidence, coefficient, summary


def build_pairing(
    executor: Any,
    interpretation: ResolvedInterpretation,
    *,
    weather_variable: str | None = None,
    origin: str | None = None,
) -> PairEvidence:
    """Build complete flight-pair or equal-origin-hour evidence without fetching populations."""
    pairing, _, _ = _pair_evidence(
        executor,
        interpretation,
        weather_variable=weather_variable,
        origin=origin,
    )
    return pairing


def _weather_origins(executor: Any, interpretation: ResolvedInterpretation) -> list[str | None]:
    if "origin" not in interpretation.grouping:
        return [None]
    where, parameters = _scope(interpretation)
    rows = executor._run_compiled_query(
        _compiled(
            interpretation,
            "SELECT DISTINCT f.origin AS origin"
            + _SUMMARY_SOURCE
            + where
            + (" AND " if where else " WHERE ")
            + "f.origin IS NOT NULL ORDER BY f.origin LIMIT 501",
            parameters,
            "weather",
            ("origin",),
        )
    )
    if len(rows) > 500:
        raise ValueError("Origin-specific weather panels exceed the 500-origin evidence bound.")
    return [str(row["origin"]) for row in rows]


def _weather_coverage(executor: Any, interpretation: ResolvedInterpretation) -> dict[str, int]:
    where, parameters = _scope(interpretation)
    sql = (
        "WITH scoped_flights AS (SELECT f.origin, f.time_hour, f.dep_delay"
        + _SUMMARY_SOURCE
        + where
        + "), hourly AS (SELECT origin, time_hour, COUNT(*) AS flight_count, "
        "COUNT(dep_delay) AS known_delay_flights FROM scoped_flights "
        "GROUP BY origin, time_hour), matched AS (SELECT h.*, w.origin AS weather_origin "
        "FROM hourly h LEFT JOIN weather w "
        "ON h.origin = w.origin AND h.time_hour = w.time_hour) "
        "SELECT (SELECT COUNT(*) FROM scoped_flights) AS flights, "
        "(SELECT COUNT(dep_delay) FROM scoped_flights) AS known_delay_flights, "
        "(SELECT COUNT(*) - COUNT(dep_delay) FROM scoped_flights) AS missing_delay_flights, "
        "COUNT(*) AS origin_hours, "
        "COUNT(*) FILTER (WHERE weather_origin IS NULL) AS unmatched_hours, "
        "COUNT(*) FILTER (WHERE weather_origin IS NOT NULL AND known_delay_flights = 0) "
        "AS matched_without_delay_hours, "
        "COUNT(*) FILTER (WHERE weather_origin IS NOT NULL AND known_delay_flights > 0) "
        "AS matched_with_delay_hours FROM matched"
    )
    columns = (
        "flights",
        "known_delay_flights",
        "missing_delay_flights",
        "origin_hours",
        "unmatched_hours",
        "matched_without_delay_hours",
        "matched_with_delay_hours",
    )
    row = executor._run_compiled_query(
        _compiled(interpretation, sql, parameters, "weather", columns)
    )[0]
    return {
        "weather_scope_flights": int(row["flights"]),
        "weather_scope_known_delay_flights": int(row["known_delay_flights"]),
        "weather_scope_missing_delay_flights": int(row["missing_delay_flights"]),
        "weather_scope_origin_hours": int(row["origin_hours"]),
        "weather_unmatched_origin_hours": int(row["unmatched_hours"]),
        "weather_matched_without_known_delay_origin_hours": int(row["matched_without_delay_hours"]),
        "weather_matched_with_known_delay_origin_hours": int(row["matched_with_delay_hours"]),
    }


def _precipitation_comparison(
    executor: Any, interpretation: ResolvedInterpretation
) -> list[GroupEvidence]:
    where, parameters = _scope(interpretation)
    band_expression = (
        "CASE WHEN w.origin IS NULL THEN 'unmatched' "
        "WHEN w.precip IS NULL THEN 'missing_precipitation' "
        "WHEN w.precip = 0 THEN 'none' WHEN w.precip < 0.1 THEN 'light' "
        "ELSE 'at_least_0_1_in' END"
    )
    group_expressions = ["f.origin"] if "origin" in interpretation.grouping else []
    selected = [
        expression + f" AS group_{index}" for index, expression in enumerate(group_expressions)
    ]
    selected.append(f"{band_expression} AS band")
    group_by = group_expressions + [band_expression]
    sql = (
        "SELECT " + ", ".join(selected) + ", COUNT(*) AS scoped_count, "
        "COUNT(f.dep_delay) FILTER (WHERE w.origin IS NOT NULL) AS known_count, "
        "AVG(f.dep_delay) FILTER (WHERE w.origin IS NOT NULL) AS mean_delay"
        + _SUMMARY_SOURCE
        + where
        + " GROUP BY "
        + ", ".join(group_by)
        + " ORDER BY "
        + (", ".join(group_expressions) + ", " if group_expressions else "")
        + "band LIMIT 501"
    )
    columns = tuple([f"group_{index}" for index in range(len(group_expressions))]) + (
        "band",
        "scoped_count",
        "known_count",
        "mean_delay",
    )
    rows = executor._run_compiled_query(
        _compiled(interpretation, sql, parameters, "weather", columns)
    )
    if len(rows) > 500:
        raise ValueError("Precipitation comparison exceeds the 500-group evidence bound.")
    groups: list[GroupEvidence] = []
    for row in rows:
        band = str(row["band"])
        code, label = PRECIPITATION_LABELS.get(band, (band, band.replace("_", " ").title()))
        identity = []
        if group_expressions:
            origin = row["group_0"]
            identity.append(
                CategoryIdentity(
                    field_id="origin",
                    code=str(origin) if origin is not None else None,
                    label=str(origin) if origin is not None else "Missing origin",
                    status="known" if origin is not None else "missing",
                )
            )
        identity.append(
            CategoryIdentity(
                field_id="weather_precipitation_band",
                code=code,
                label=label,
                status="known",
            )
        )
        known = int(row["known_count"])
        scoped = int(row["scoped_count"])
        groups.append(
            GroupEvidence(
                identity=identity,
                measures={
                    "weather_context_departure_delay": NumericEvidence(
                        value=row["mean_delay"] if known else None,
                        absence=None if known else "no_known_values",
                    )
                },
                sample_size=known,
                tied=False,
                scoped_count=scoped,
                missing_count=scoped - known,
            )
        )
    return groups


def build_weather(
    executor: Any,
    interpretation: ResolvedInterpretation,
    common: dict,
) -> WeatherPanelResult:
    """Build Pearson panels; unit-dependent comparisons require verified units."""
    if interpretation.operation_id != "weather_relationship":
        raise InvalidPlanError("Weather evidence requires a weather_relationship interpretation.")
    units_verified = _weather_units_verified(executor)
    origins = _weather_origins(executor, interpretation)
    if len(origins) * len(WEATHER_VARIABLES) > 2000:
        raise ValueError("Weather panel exceeds the 2,000-variable evidence bound.")

    variables: list[WeatherVariableEvidence] = []
    by_origin: dict[str | None, list[dict[str, Any]]] = {}
    for origin in origins:
        for variable in WEATHER_VARIABLES:
            pairing, coefficient, summary = _pair_evidence(
                executor,
                interpretation,
                weather_variable=variable,
                origin=origin,
            )
            absence = (
                None
                if coefficient is not None
                else "constant_axis"
                if pairing.pair_count >= 3
                and (
                    (pairing.x_extent is not None and pairing.x_extent[0] == pairing.x_extent[1])
                    or (pairing.y_extent is not None and pairing.y_extent[0] == pairing.y_extent[1])
                )
                else "insufficient_pairs"
            )
            variables.append(
                WeatherVariableEvidence(
                    variable=variable,
                    origin=origin,
                    pairing=pairing,
                    coefficient=NumericEvidence(value=coefficient, absence=absence),
                )
            )
            by_origin.setdefault(origin, []).append(summary)

    missingness = dict(common.get("missingness", {}))
    if origins == [None]:
        missingness.update(_weather_coverage(executor, interpretation))
    for origin, summaries in by_origin.items():
        prefix = f"weather_origin_{origin or 'missing'}_"
        if origin is not None:
            missingness[prefix + "hours"] = int(summaries[0]["scoped_count"])
            missingness[prefix + "unmatched_hours"] = int(summaries[0]["unmatched_weather"])
            missingness[prefix + "matched_without_delay_hours"] = int(
                summaries[0]["matched_without_delay"]
            )
            missingness[prefix + "matched_with_delay_hours"] = int(
                summaries[0]["matched_with_delay"]
            )
        for variable, summary in zip(WEATHER_VARIABLES, summaries, strict=True):
            missingness[prefix + variable + "_matched_delay_missing_weather_hours"] = int(
                summary["matched_delay_missing_weather"]
            )
    limitations = list(common.get("limitations", []))
    if not units_verified:
        limitations.extend(
            [
                "Provisional Pearson correlations use recorded weather values with unverified "
                "units; "
                "no Fahrenheit, mph, inch or mile units have been confirmed or applied.",
                "Pearson is dimensionless and invariant under positive linear unit conversions. "
                "Consistent numeric scales are assumed; mixed units, nonlinear transformations "
                "or undocumented missing-value codes can invalidate interpretation.",
                "Unit-dependent precipitation comparisons are unavailable until local units "
                "are verified. Correlation does not establish causation.",
            ]
        )
    common = {**common, "missingness": missingness, "limitations": limitations}
    return WeatherPanelResult(
        **common,
        kind="weather_panel",
        variables=variables,
        weather_units_status="verified" if units_verified else "unverified",
        precipitation_comparison=(
            _precipitation_comparison(executor, interpretation) if units_verified else []
        ),
    )
