"""Deterministic compiler from validated plans to bounded parameterized DuckDB SELECTs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.data.catalog import (
    DIMENSIONS,
    FIELDS,
    JOIN_SQL,
    METRICS,
    required_joins,
)
from airport_analytics.errors import InvalidPlanError
from airport_analytics.models import AnalysisPlan

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
    plan: AnalysisPlan


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


def compile_analysis_plan(plan: AnalysisPlan) -> CompiledQuery:
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

    if plan.metric_id == "mean_delay_by_weather_context":
        predicates.append("w.origin IS NOT NULL")

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
    elif selected_dimensions:
        sql += f' ORDER BY "{selected_dimensions[0].dimension_id}" ASC NULLS LAST'

    sql += " LIMIT ?"
    parameters.append(plan.row_limit)
    return CompiledQuery(sql=sql, parameters=tuple(parameters), plan=plan)
