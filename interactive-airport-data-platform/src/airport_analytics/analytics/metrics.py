"""Deterministic report definitions, scope, coverage, and glossary metadata."""

from __future__ import annotations

from datetime import date
from typing import Any

from airport_analytics.analytics.execution import QueryResult
from airport_analytics.data.catalog import (
    DIMENSIONS,
    METRICS,
    required_joins,
)
from airport_analytics.models import AnalysisPlan

GLOSSARY: dict[str, str] = {
    "average": (
        "Mean (average) is the sum of observed values divided by the number of "
        "non-missing observations."
    ),
    "distinct": (
        "Distinct counts include each unique identifier once within the selected scope, "
        "regardless of how many matching records it appears in."
    ),
    "join_coverage": (
        "Join coverage is the number of source records matched to a reference/context row "
        "divided by all source records in the current flight snapshot."
    ),
    "weather_association": (
        "Weather comparisons are contextual associations for matched origin/time observations; "
        "they do not establish that weather caused a delay."
    ),
}


def _date_label(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _filter_label(field_id: str, operator: str, value: Any) -> str:
    field_name = field_id.replace("_", " ")
    rendered = ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)
    operator_label = {
        "eq": "=",
        "neq": "is not",
        "in": "is one of",
        "gt": ">",
        "gte": "≥",
        "lt": "<",
        "lte": "≤",
        "between": "between",
    }[operator]
    return f"{field_name} {operator_label} {rendered}"


def build_report_metadata(plan: AnalysisPlan, result: QueryResult) -> dict[str, object]:
    metric = METRICS[plan.metric_id]
    sort_id = plan.sort.field_id if plan.sort else None
    joins = required_joins(
        metric_id=plan.metric_id,
        dimensions=plan.group_by,
        filter_ids=[item.field_id for item in plan.filters],
        sort_id=sort_id,
    )
    coverage_key_by_join = {
        "airlines": "airline",
        "planes": "aircraft",
        "weather": "weather_origin_time_exact",
    }
    coverage = {
        coverage_key_by_join[join]: result.manifest.join_coverage[coverage_key_by_join[join]]
        for join in sorted(joins)
        if join in coverage_key_by_join
    }

    active_period = {
        "start": _date_label(plan.time_range.start) if plan.time_range else None,
        "end": _date_label(plan.time_range.end) if plan.time_range else None,
        "source_start": result.manifest.flight_period_start,
        "source_end": result.manifest.flight_period_end,
    }
    if active_period["start"] is None:
        active_period["start"] = result.manifest.flight_period_start
    if active_period["end"] is None:
        active_period["end"] = result.manifest.flight_period_end

    definitions = {
        "metric": metric.description,
        "unit": metric.unit,
        "population": metric.population,
        "numerator": metric.numerator or "Not applicable",
        "denominator": metric.denominator or "Not applicable",
        "period": f"{active_period['start']} through {active_period['end']}",
    }
    scope = {
        "filters": [
            _filter_label(item.field_id, item.operator, item.value) for item in plan.filters
        ],
        "group_by": [DIMENSIONS[item].dimension_id for item in plan.group_by],
        "period": definitions["period"],
        "geographic_coverage": list(result.manifest.origin_airports),
        "source_snapshot": result.snapshot_id,
    }
    limitations = list(metric.caveats)
    if coverage:
        limitations.append(
            "Reference/context records may be unmatched; matched and unmatched counts are shown."
        )
    limitations.append(
        "This report describes the supplied historical NYC-area flight snapshot, "
        "not live or global operations."
    )
    glossary: dict[str, str] = {}
    if "AVG(" in metric.expression.upper():
        glossary["average"] = GLOSSARY["average"]
    if "DISTINCT" in metric.expression.upper():
        glossary["distinct"] = GLOSSARY["distinct"]
    if coverage:
        glossary["join_coverage"] = GLOSSARY["join_coverage"]
    if "weather" in joins:
        glossary["weather_association"] = GLOSSARY["weather_association"]

    return {
        "definitions": definitions,
        "scope": scope,
        "limitations": list(dict.fromkeys(limitations)),
        "join_coverage": coverage,
        "glossary": glossary,
        "metric_id": metric.metric_id,
        "metric_value_description": metric.description,
        "sample_counts": [
            {
                "flight_count": row["flight_count"],
                "observation_count": row["observation_count"],
            }
            for row in result.rows
        ],
    }
