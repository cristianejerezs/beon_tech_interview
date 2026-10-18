"""Deterministic compiler from validated plans to bounded parameterized DuckDB SELECTs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.data.catalog import (
    DIMENSIONS,
    FIELDS,
    JOIN_SQL,
    METRICS,
    required_joins,
    summary_metric,
    summary_observation_expression,
)
from airport_analytics.errors import InvalidPlanError
from airport_analytics.models import AnalysisPlan, ResolvedInterpretation

OPERATOR_SQL = {
    "eq": "=",
    "neq": "<>",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}

JOIN_ORDER = ("airlines", "planes", "weather")


@dataclass(frozen=True)
class CompiledQuery:
    sql: str
    parameters: tuple[Any, ...]
    plan: AnalysisPlan | ResolvedInterpretation
    purpose: Literal[
        "aggregate",
        "scope",
        "routes",
        "count",
        "page",
        "distribution",
        "pairs",
        "density",
        "daily_support",
        "weather",
        "eligibility",
    ]
    kind: Literal["select", "owned_cte"]
    output_columns: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.output_columns or len(set(self.output_columns)) != len(self.output_columns):
            raise ValueError("Compiled queries require unique declared output columns.")
        if self.kind not in {"select", "owned_cte"}:
            raise ValueError("Unsupported application-owned query kind.")


def _compile_filter(field_id: str, operator: str, value: Any) -> tuple[str, list[Any]]:
    expression = FIELDS[field_id].expression
    if value is None:
        if operator not in {"eq", "neq"}:
            raise InvalidPlanError()
        return f"{expression} IS {'NOT ' if operator == 'neq' else ''}NULL", []
    if operator == "in":
        placeholders = ", ".join("?" for _ in value)
        return f"{expression} IN ({placeholders})", list(value)
    if operator == "between":
        left, right = value
        if FIELDS[field_id].data_type == "date":
            left, right = date.fromisoformat(left), date.fromisoformat(right)
        return f"{expression} BETWEEN ? AND ?", [left, right]
    if operator not in OPERATOR_SQL:
        raise InvalidPlanError()
    if FIELDS[field_id].data_type == "date":
        value = date.fromisoformat(value)
    return f"{expression} {OPERATOR_SQL[operator]} ?", [value]


def compile_analysis_plan(
    plan: AnalysisPlan, *, evidence: str | None = None, lookahead: bool = False
) -> CompiledQuery:
    plan = validate_analysis_plan(plan.model_dump(mode="json"))
    if plan.status != "ready" or plan.metric_id not in METRICS:
        raise InvalidPlanError("Only ready plans using a catalog metric can be compiled.")

    metric = METRICS[plan.metric_id]
    selected_dimensions = [DIMENSIONS[item] for item in plan.group_by]
    sort_id = plan.sort.field_id if plan.sort else None
    try:
        joins = required_joins(
            metric_id=plan.metric_id,
            dimensions=plan.group_by,
            filter_ids=[item.field_id for item in plan.filters],
            sort_id=sort_id,
        )
    except (KeyError, ValueError) as exc:
        raise InvalidPlanError("The plan requested an unsupported join.") from exc

    select_parts = [
        f'{dimension.expression} AS "{dimension.dimension_id}"' for dimension in selected_dimensions
    ]
    select_parts.extend(
        [
            f"{metric.expression} AS metric_value",
            "COUNT(*) AS flight_count",
            f"{metric.observation_expression} AS observation_count",
        ]
    )

    joins_sql = " ".join(JOIN_SQL[join] for join in JOIN_ORDER if join in joins)
    predicates: list[str] = []
    parameters: list[Any] = []
    for filter_item in plan.filters:
        sql, values = _compile_filter(filter_item.field_id, filter_item.operator, filter_item.value)
        predicates.append(sql)
        parameters.extend(values)

    if plan.time_range is not None:
        if plan.time_range.start is not None:
            predicates.append("make_date(f.year, f.month, f.day) >= ?")
            parameters.append(plan.time_range.start)
        if plan.time_range.end is not None:
            predicates.append("make_date(f.year, f.month, f.day) <= ?")
            parameters.append(plan.time_range.end)

    scope_predicates = list(predicates)
    if plan.metric_id == "mean_delay_by_weather_context" and evidence is None:
        predicates.append("w.origin IS NOT NULL")

    if evidence is not None:
        source = " FROM flights f " + joins_sql
        where = " WHERE " + " AND ".join(scope_predicates) if scope_predicates else ""
        if evidence == "scope":
            output_columns = ["period_start", "period_end", "total"]
            parts = [
                "MIN(make_date(f.year, f.month, f.day)) AS period_start",
                "MAX(make_date(f.year, f.month, f.day)) AS period_end",
                "COUNT(*) AS total",
            ]
            for join, key in (
                ("airlines", "a.carrier"),
                ("planes", "p.tailnum"),
                ("weather", "w.origin"),
            ):
                if join in joins:
                    parts.append(f"COUNT({key}) AS {join}_matched")
                    output_columns.append(f"{join}_matched")
            sql = "SELECT " + ", ".join(parts) + source + where
        elif evidence == "routes" and plan.metric_id == "distinct_destination_count":
            output_columns = [item.dimension_id for item in selected_dimensions]
            output_columns.extend(["route_origin", "destination", "flights"])
            parts = [f'{item.expression} AS "{item.dimension_id}"' for item in selected_dimensions]
            parts.extend(
                ["f.origin AS route_origin", "f.dest AS destination", "COUNT(*) AS flights"]
            )
            grain = [item.expression for item in selected_dimensions] + ["f.origin", "f.dest"]
            sql = (
                "SELECT "
                + ", ".join(parts)
                + source
                + where
                + " GROUP BY "
                + ", ".join(grain)
                + " ORDER BY "
                + ", ".join(grain)
                + " LIMIT 501"
            )
        else:
            raise ValueError("Unknown evidence query.")
        return CompiledQuery(
            sql=sql,
            parameters=tuple(parameters),
            plan=plan,
            purpose="scope" if evidence == "scope" else "routes",
            kind="select",
            output_columns=tuple(output_columns),
        )

    sql = (
        "SELECT "
        + ", ".join(select_parts)
        + " FROM flights f "
        + joins_sql
        + (" WHERE " + " AND ".join(predicates) if predicates else "")
        + (
            " GROUP BY " + ", ".join(dimension.expression for dimension in selected_dimensions)
            if selected_dimensions
            else ""
        )
    )

    if plan.sort is not None:
        sort_field = "metric_value" if plan.sort.field_id in METRICS else plan.sort.field_id
        sql += f' ORDER BY "{sort_field}" {plan.sort.direction.upper()} NULLS LAST'
        for dimension in selected_dimensions:
            if dimension.dimension_id != sort_field:
                sql += f', "{dimension.dimension_id}" ASC NULLS LAST'
    elif selected_dimensions:
        sql += f' ORDER BY "{selected_dimensions[0].dimension_id}" ASC NULLS LAST'

    sql += " LIMIT ?"
    parameters.append(plan.row_limit + int(lookahead))
    return CompiledQuery(
        sql=sql,
        parameters=tuple(parameters),
        plan=plan,
        purpose="aggregate",
        kind="select",
        output_columns=tuple(
            [item.dimension_id for item in selected_dimensions]
            + ["metric_value", "flight_count", "observation_count"]
        ),
    )


_SUMMARY_SOURCE = (
    " FROM flights f "
    + " ".join(JOIN_SQL[join] for join in JOIN_ORDER)
    + " LEFT JOIN airports destination_ref ON f.dest = destination_ref.faa "
    + " LEFT JOIN airports origin_ref ON f.origin = origin_ref.faa "
)

_CONNECTED_ENDPOINTS = "fl.origin IS NOT NULL AND fl.dest IS NOT NULL AND fl.origin <> fl.dest"
# One row per (flight, endpoint airport): each flight connects its origin and destination.
_CONNECTED_SUMMARY_SOURCE = (
    " FROM (SELECT fl.*, fl.origin AS connected_airport, fl.dest AS neighbour_airport "
    f"FROM flights fl WHERE {_CONNECTED_ENDPOINTS} UNION ALL "
    "SELECT fl.*, fl.dest AS connected_airport, fl.origin AS neighbour_airport "
    f"FROM flights fl WHERE {_CONNECTED_ENDPOINTS}) f "
    + " ".join(JOIN_SQL[join] for join in JOIN_ORDER)
    + " LEFT JOIN airports destination_ref ON f.dest = destination_ref.faa "
    + " LEFT JOIN airports origin_ref ON f.origin = origin_ref.faa "
    + " LEFT JOIN airports airport_ref ON f.connected_airport = airport_ref.faa "
)

FLIGHT_LIST_COLUMNS = {
    "source_row_id": "f.column00",
    "flight_date": "CAST(make_date(f.year, f.month, f.day) AS VARCHAR)",
    "origin": "f.origin",
    "destination": "f.dest",
    "carrier": "f.carrier",
    "airline_name": "a.name",
    "flight_number": "f.flight",
    "tailnum": "f.tailnum",
    "departure_delay": "f.dep_delay",
    "arrival_delay": "f.arr_delay",
    "distance": "f.distance",
}
ENTITY_LIST_COLUMNS = ("code", "name", "reference_status")


def listing_columns(interpretation: ResolvedInterpretation) -> tuple[str, ...]:
    if interpretation.population == "airport_connections":
        return (*ENTITY_LIST_COLUMNS, "connection_count")
    return (
        tuple(FLIGHT_LIST_COLUMNS)
        if interpretation.operation_id == "flight_records"
        else ENTITY_LIST_COLUMNS
    )


def listing_sort(
    interpretation: ResolvedInterpretation,
    sort_field: str | None = None,
) -> str:
    default = "source_row_id" if interpretation.operation_id == "flight_records" else "code"
    field = sort_field or (interpretation.order[0].field_id if interpretation.order else default)
    if interpretation.operation_id == "entity_list":
        field = {
            "origin": "code",
            "destination": "code",
            "carrier": "code",
            "airline_name": "name",
        }.get(field, field)
    if field not in listing_columns(interpretation):
        raise InvalidPlanError("Listing ordering requires an approved output column.")
    return field


def compile_listing(
    interpretation: ResolvedInterpretation,
    *,
    purpose: Literal["count", "page"] = "page",
    limit: int = 100,
    offset: int = 0,
    sort_field: str | None = None,
    direction: Literal["asc", "desc"] = "asc",
) -> CompiledQuery:
    interpretation = ResolvedInterpretation.model_validate(interpretation.model_dump(mode="json"))
    if interpretation.operation_id not in {"flight_records", "entity_list"}:
        raise InvalidPlanError("Only listing operations use the listing compiler.")
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 0 <= limit <= 10000
        or isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
        or direction not in {"asc", "desc"}
    ):
        raise InvalidPlanError("Invalid listing slice or ordering.")
    clauses = []
    parameters: list[Any] = []
    connections = interpretation.population == "airport_connections"
    reference = interpretation.population in {"airport_reference", "airport_connections"}
    flight_clauses = []
    flight_parameters: list[Any] = []
    for predicate in interpretation.filters:
        if connections and predicate.field_id not in {"origin", "destination"}:
            clause, values = _compile_filter(
                predicate.field_id,
                predicate.operator,
                predicate.value,
            )
            flight_clauses.append(clause)
            flight_parameters.extend(values)
            continue
        if reference:
            if predicate.field_id not in {"origin", "destination"}:
                raise InvalidPlanError(
                    "Airport-reference lists accept only airport-code filters, not flight filters."
                )
            expression = "r.faa"
            if predicate.operator not in {"eq", "neq", "in"}:
                raise InvalidPlanError("Invalid airport-reference filter.")
            if predicate.value is None:
                clause = expression + (" IS NULL" if predicate.operator == "eq" else " IS NOT NULL")
                values = []
            elif predicate.operator == "in":
                values = predicate.value
                clause = expression + " IN (" + ", ".join("?" for _ in values) + ")"
            else:
                values = [predicate.value]
                clause = expression + " " + OPERATOR_SQL[predicate.operator] + " ?"
        else:
            clause, values = _compile_filter(
                predicate.field_id,
                predicate.operator,
                predicate.value,
            )
        clauses.append(clause)
        parameters.extend(values)
    if interpretation.date_scope is not None:
        if reference and not connections:
            raise InvalidPlanError("Airport-reference population has no departure-date scope.")
        for bound, operator in [
            (interpretation.date_scope.start, ">="),
            (interpretation.date_scope.end, "<="),
        ]:
            if bound is not None:
                target_clauses = flight_clauses if connections else clauses
                target_parameters = flight_parameters if connections else parameters
                target_clauses.append(f"make_date(f.year, f.month, f.day) {operator} ?")
                target_parameters.append(bound)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    if interpretation.operation_id == "flight_records":
        select = ", ".join(
            f"{expression} AS {key}" for key, expression in FLIGHT_LIST_COLUMNS.items()
        )
        base = "SELECT " + select + _SUMMARY_SOURCE + where
    elif connections:
        flight_where = " WHERE " + " AND ".join(flight_clauses) if flight_clauses else ""
        base = (
            "WITH scoped_flights AS (SELECT f.origin, f.dest"
            + _SUMMARY_SOURCE
            + flight_where
            + "), edges AS (SELECT origin AS airport, dest AS neighbour FROM scoped_flights "
            "UNION SELECT dest AS airport, origin AS neighbour FROM scoped_flights), "
            "connections AS (SELECT airport, count(DISTINCT neighbour) AS connection_count "
            "FROM edges WHERE airport IS NOT NULL AND neighbour IS NOT NULL "
            "AND airport <> neighbour GROUP BY airport) "
            "SELECT r.faa AS code, r.name AS name, 'known' AS reference_status, "
            "COALESCE(c.connection_count, 0) AS connection_count FROM airports r "
            "LEFT JOIN connections c ON c.airport = r.faa" + where
        )
        parameters = [*flight_parameters, *parameters]
    elif reference:
        base = (
            "SELECT r.faa AS code, r.name AS name, 'known' AS reference_status FROM airports r"
            + where
        )
    else:
        code, reference_key, reference_name = {
            "observed_origins": ("f.origin", "origin_ref.faa", "origin_ref.name"),
            "observed_destinations": ("f.dest", "destination_ref.faa", "destination_ref.name"),
            "observed_airlines": ("f.carrier", "a.carrier", "a.name"),
        }[interpretation.population]
        source = _SUMMARY_SOURCE
        where += (" AND " if where else " WHERE ") + f"{code} IS NOT NULL"
        base = (
            f"SELECT DISTINCT {code} AS code, {reference_name} AS name, "
            f"CASE WHEN {reference_key} IS NULL THEN 'unmatched_reference' "
            "ELSE 'known' END AS reference_status" + source + where
        )
    if purpose == "count":
        sql = "WITH listing AS (" + base + ") SELECT COUNT(*) AS total_rows FROM listing"
        columns = ("total_rows",)
    else:
        field = listing_sort(interpretation, sort_field)
        identity = "source_row_id" if interpretation.operation_id == "flight_records" else "code"
        order = f"{field} {direction.upper()} NULLS LAST"
        if field != identity:
            order += f", {identity} ASC"
        sql = "WITH listing AS (" + base + ") SELECT * FROM listing ORDER BY " + order
        sql += " LIMIT ? OFFSET ?"
        parameters.extend([limit, offset])
        columns = listing_columns(interpretation)
    return CompiledQuery(
        sql=sql,
        parameters=tuple(parameters),
        plan=interpretation,
        purpose=purpose,
        kind="owned_cte",
        output_columns=columns,
    )


_SUMMARY_DIMENSIONS: dict[str, tuple[str, str]] = {
    "airport": ("f.connected_airport", "COALESCE(airport_ref.name, f.connected_airport)"),
    "origin": ("f.origin", "COALESCE(origin_ref.name, f.origin)"),
    "destination": ("f.dest", "COALESCE(destination_ref.name, f.dest)"),
    "carrier": ("f.carrier", "COALESCE(a.name, f.carrier)"),
    "airline_name": ("f.carrier", "COALESCE(a.name, f.carrier)"),
    "tailnum": ("f.tailnum", "f.tailnum"),
    "aircraft_manufacturer": ("p.manufacturer", "p.manufacturer"),
    "aircraft_model": (
        "CASE WHEN p.model IS NULL THEN NULL ELSE "
        "to_json(struct_pack(manufacturer := p.manufacturer, model := p.model)) END",
        "COALESCE(p.manufacturer, 'Unknown manufacturer') || ' / ' || p.model",
    ),
    "flight_date": (
        "CAST(make_date(f.year, f.month, f.day) AS VARCHAR)",
        "CAST(make_date(f.year, f.month, f.day) AS VARCHAR)",
    ),
    "flight_week": (
        "CAST(CAST(DATE_TRUNC('week', make_date(f.year, f.month, f.day)) AS DATE) AS VARCHAR)",
        "CAST(CAST(DATE_TRUNC('week', make_date(f.year, f.month, f.day)) AS DATE) AS VARCHAR)",
    ),
    "flight_month": (
        "strftime(make_date(f.year, f.month, f.day), '%Y-%m')",
        "strftime(make_date(f.year, f.month, f.day), '%Y-%m')",
    ),
    "month_of_year": (
        "printf('%02d', f.month)",
        "monthname(make_date(f.year, f.month, f.day))",
    ),
    "weather_precipitation_band": (
        "CASE WHEN w.origin IS NULL THEN 'unmatched_weather' "
        "WHEN w.precip IS NULL THEN 'missing_precipitation' "
        "WHEN w.precip = 0 THEN 'none' WHEN w.precip < 0.1 THEN 'light' "
        "ELSE 'at_least_0_1_in' END",
        "CASE WHEN w.origin IS NULL THEN 'unmatched_weather' "
        "WHEN w.precip IS NULL THEN 'missing_precipitation' "
        "WHEN w.precip = 0 THEN 'none' WHEN w.precip < 0.1 THEN 'light' "
        "ELSE 'at_least_0_1_in' END",
    ),
}


def compile_summary(
    interpretation: ResolvedInterpretation,
    *,
    purpose: Literal["aggregate", "scope", "routes"] = "aggregate",
) -> CompiledQuery:
    interpretation = ResolvedInterpretation.model_validate(interpretation.model_dump(mode="json"))
    if interpretation.operation_id not in {
        "aggregate",
        "departure_delay_total",
        "aircraft_frequency",
    }:
        raise InvalidPlanError("Only resolved aggregate operations use the summary compiler.")
    measure_id = interpretation.measure_ids[0]
    metric = summary_metric(measure_id)
    predicates: list[str] = []
    parameters: list[Any] = []
    for predicate in interpretation.filters:
        clause, values = _compile_filter(predicate.field_id, predicate.operator, predicate.value)
        predicates.append(clause)
        parameters.extend(values)
    if interpretation.date_scope is not None:
        for boundary, operator in [
            (interpretation.date_scope.start, ">="),
            (interpretation.date_scope.end, "<="),
        ]:
            if boundary is not None:
                predicates.append(f"make_date(f.year, f.month, f.day) {operator} ?")
                parameters.append(boundary)
    where = " WHERE " + " AND ".join(predicates) if predicates else ""
    # All templates use identical validated predicates and immutable reference joins.
    if purpose == "scope":
        columns = (
            "filtered_flights",
            "known_measure",
            "period_start",
            "period_end",
            "observed_days",
            "origin_codes",
            "airline_reference_unmatched",
            "plane_reference_unmatched",
            "weather_reference_unmatched",
            "destination_reference_unmatched",
            "available_routes",
        )
        known = summary_observation_expression(measure_id)
        sql = (
            "SELECT COUNT(*) AS filtered_flights, " + known + " AS known_measure, "
            "MIN(make_date(f.year,f.month,f.day)) AS period_start, "
            "MAX(make_date(f.year,f.month,f.day)) AS period_end, "
            "COUNT(DISTINCT make_date(f.year,f.month,f.day)) AS observed_days, "
            "LIST(DISTINCT f.origin ORDER BY f.origin) FILTER (WHERE f.origin IS NOT NULL) "
            "AS origin_codes, "
            "COUNT(*) FILTER (WHERE a.carrier IS NULL) AS airline_reference_unmatched, "
            "COUNT(*) FILTER (WHERE p.tailnum IS NULL) AS plane_reference_unmatched, "
            "COUNT(*) FILTER (WHERE w.origin IS NULL) AS weather_reference_unmatched, "
            "COUNT(*) FILTER (WHERE destination_ref.faa IS NULL) "
            "AS destination_reference_unmatched, "
            "COUNT(DISTINCT (f.origin, f.dest)) AS available_routes" + _SUMMARY_SOURCE + where
        )
        return CompiledQuery(
            sql=sql,
            parameters=tuple(parameters),
            plan=interpretation,
            purpose=purpose,
            kind="select",
            output_columns=columns,
        )
    if purpose == "routes":
        if measure_id != "distinct_destination_count":
            raise InvalidPlanError("Route evidence applies only to destination connectivity.")
        return CompiledQuery(
            sql="SELECT f.origin AS origin, f.dest AS destination, "
            "destination_ref.name AS destination_name, COUNT(*) AS flights"
            + _SUMMARY_SOURCE
            + where
            + " GROUP BY f.origin, f.dest, destination_ref.name "
            "ORDER BY f.origin ASC NULLS LAST, f.dest ASC NULLS LAST LIMIT 500",
            parameters=tuple(parameters),
            plan=interpretation,
            purpose=purpose,
            kind="select",
            output_columns=("origin", "destination", "destination_name", "flights"),
        )
    parts: list[str] = []
    groups: list[str] = []
    columns: list[str] = []
    for dimension in interpretation.grouping:
        code, label = _SUMMARY_DIMENSIONS[dimension]
        status = f"CASE WHEN {code} IS NULL THEN 'missing' ELSE 'known' END"
        if dimension in {"airport", "origin", "carrier", "airline_name", "destination", "tailnum"}:
            reference = {
                "airport": "airport_ref.faa",
                "origin": "origin_ref.faa",
                "carrier": "a.carrier",
                "airline_name": "a.carrier",
                "destination": "destination_ref.faa",
                "tailnum": "p.tailnum",
            }[dimension]
            status = (
                f"CASE WHEN {code} IS NULL THEN 'missing' "
                f"WHEN {reference} IS NULL THEN 'unmatched_reference' ELSE 'known' END"
            )
        for suffix, expression in [("code", code), ("label", label), ("status", status)]:
            alias = f"{dimension}_{suffix}"
            parts.append(f'{expression} AS "{alias}"')
            groups.append(expression)
            columns.append(alias)
    connected = (
        measure_id == "distinct_connected_airport_count" or "airport" in interpretation.grouping
    )
    parts.extend(
        [
            f"{metric.expression} AS metric_value",
            ("COUNT(DISTINCT f.column00)" if connected else "COUNT(*)") + " AS flight_count",
            (
                "COUNT(DISTINCT f.column00)"
                if connected
                else summary_observation_expression(measure_id)
            )
            + " AS observation_count",
        ]
    )
    columns.extend(["metric_value", "flight_count", "observation_count"])
    main_where = where
    if measure_id == "weather_context_departure_delay":
        main_where += (" AND " if main_where else " WHERE ") + "w.origin IS NOT NULL"
    if interpretation.operation_id == "aircraft_frequency":
        main_where += (" AND " if main_where else " WHERE ") + "p.tailnum IS NOT NULL"
    aggregate = (
        "SELECT "
        + ", ".join(parts)
        + (_CONNECTED_SUMMARY_SOURCE if connected else _SUMMARY_SOURCE)
        + main_where
        + (" GROUP BY " + ", ".join(dict.fromkeys(groups)) if groups else "")
    )
    sql = (
        "WITH grouped AS (" + aggregate + ") SELECT *, "
        "COUNT(*) OVER () AS available_groups, "
        "COUNT(*) OVER (PARTITION BY metric_value) AS equal_value_groups FROM grouped"
    )
    ordering: list[str] = []
    for item in interpretation.order:
        column = "metric_value" if item.field_id == measure_id else f"{item.field_id}_code"
        ordering.append(f'"{column}" {item.direction.upper()} NULLS LAST')
    for dimension in interpretation.grouping:
        column = f"{dimension}_code"
        if not any(f'"{column}"' in clause for clause in ordering):
            ordering.append(f'"{column}" ASC NULLS LAST')
    if ordering:
        sql += " ORDER BY " + ", ".join(ordering)
    sql += " LIMIT ?"
    parameters.append(interpretation.selection)
    return CompiledQuery(
        sql=sql,
        parameters=tuple(parameters),
        plan=interpretation,
        purpose=purpose,
        kind="owned_cte",
        output_columns=tuple(columns + ["available_groups", "equal_value_groups"]),
    )
