"""Strict schema and catalog validation for untrusted model-produced analysis plans."""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from airport_analytics.data.catalog import DIMENSIONS, FIELDS, METRICS
from airport_analytics.errors import InvalidPlanError
from airport_analytics.models import AnalysisPlan

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "001-airport-analytics-platform"
    / "contracts"
    / "analysis-plan.schema.json"
)


@lru_cache(maxsize=1)
def _load_schema(path: str) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    Draft202012Validator.check_schema(schema)
    return schema


def _json_object(response: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    if not isinstance(response, str):
        raise InvalidPlanError()
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError as exc:
        raise InvalidPlanError("The model response was not a JSON analysis plan.") from exc
    if not isinstance(parsed, dict):
        raise InvalidPlanError("The model response must be one JSON object.")
    return parsed


def _validate_filter_value(field_id: str, operator: str, value: Any) -> None:
    field = FIELDS[field_id]
    if isinstance(value, list) and operator not in {"in", "between"}:
        raise InvalidPlanError("List values are allowed only with in or between filters.")
    values = value if isinstance(value, list) else [value]
    if operator == "between" and len(values) != 2:
        raise InvalidPlanError("A between filter requires exactly two values.")
    if operator == "in" and (not isinstance(value, list) or not value):
        raise InvalidPlanError("An in filter requires a non-empty list.")
    if isinstance(value, list) and len(value) > 100:
        raise InvalidPlanError("A filter list cannot contain more than 100 values.")

    for item in values:
        if item is None and operator in {"eq", "neq"}:
            continue
        if field.data_type == "string" and not isinstance(item, str):
            raise InvalidPlanError(f"Filter {field_id} requires text values.")
        if field.data_type == "number" and (
            isinstance(item, bool) or not isinstance(item, (int, float))
        ):
            raise InvalidPlanError(f"Filter {field_id} requires numeric values.")
        if field.data_type == "date":
            if not isinstance(item, str):
                raise InvalidPlanError(f"Filter {field_id} requires ISO date values.")
            try:
                date.fromisoformat(item)
            except ValueError as exc:
                raise InvalidPlanError(f"Filter {field_id} requires ISO date values.") from exc
        if isinstance(item, float) and (item != item or abs(item) == float("inf")):
            raise InvalidPlanError("Filter values must be finite.")

    if operator in {"gt", "gte", "lt", "lte", "between"} and field.data_type == "string":
        raise InvalidPlanError(f"Operator {operator} is not supported for text fields.")


def validate_analysis_plan(
    response: str | dict[str, Any], *, schema_path: str | Path = SCHEMA_PATH
) -> AnalysisPlan:
    payload = _json_object(response)
    validator = Draft202012Validator(
        _load_schema(str(Path(schema_path).resolve())), format_checker=FormatChecker()
    )
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        raise InvalidPlanError("The model response does not match the approved plan schema.") from (
            errors[0]
        )
    try:
        plan = AnalysisPlan.model_validate(payload)
    except ValidationError as exc:
        raise InvalidPlanError("The model response is not a valid analysis plan.") from exc

    if plan.status != "ready":
        return plan
    if plan.metric_id not in METRICS:
        raise InvalidPlanError("The plan selected a metric outside the approved catalog.")
    unknown_dimensions = set(plan.group_by) - DIMENSIONS.keys()
    if unknown_dimensions:
        raise InvalidPlanError("The plan selected a dimension outside the approved catalog.")
    metric = METRICS[plan.metric_id]
    if metric.allowed_dimensions is not None and not set(plan.group_by).issubset(
        metric.allowed_dimensions
    ):
        raise InvalidPlanError("The selected metric cannot be grouped by that dimension.")

    for item in plan.filters:
        if item.field_id not in FIELDS or not FIELDS[item.field_id].filterable:
            raise InvalidPlanError("The plan selected a filter outside the approved catalog.")
        _validate_filter_value(item.field_id, item.operator, item.value)

    if plan.sort is not None and plan.sort.field_id not in (DIMENSIONS.keys() | METRICS.keys()):
        raise InvalidPlanError("The plan selected a sort field outside the approved catalog.")
    if (
        plan.sort is not None
        and plan.sort.field_id in METRICS
        and plan.sort.field_id != plan.metric_id
    ):
        raise InvalidPlanError("A report may be sorted only by its selected metric.")
    if (
        plan.sort is not None
        and plan.sort.field_id in DIMENSIONS
        and plan.sort.field_id not in plan.group_by
    ):
        raise InvalidPlanError("A report may be sorted only by a selected dimension.")
    if plan.time_range is not None:
        if plan.time_range.start is None and plan.time_range.end is None:
            raise InvalidPlanError("A time range must include a start or end date.")
    return plan
