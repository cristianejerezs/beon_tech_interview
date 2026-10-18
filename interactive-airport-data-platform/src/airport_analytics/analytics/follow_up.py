"""Bounded follow-up context and deterministic scope preservation/replacement rules."""

from __future__ import annotations

import re

from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.analytics.question_validation import validate_question
from airport_analytics.models import AnalysisPlan, ScopeEdit, TypedFilter

AIRLINE_FIELDS = frozenset({"carrier", "airline_name"})
DATE_FIELDS = frozenset({"flight_year", "flight_month_number", "flight_date"})
FILTER_REMOVAL_CUES: dict[str, tuple[str, ...]] = {
    "origin": (
        "remove airport",
        "remove the airport",
        "remove airport and airline",
        "remove the airport and airline",
        "clear airport",
        "clear the airport",
        "clear airport and airline",
        "clear the airport and airline",
        "without airport",
        "without the airport",
        "all airports",
        "any airport",
        "remove origin",
        "clear origin",
        "all origins",
    ),
    "destination": (
        "remove destination",
        "clear destination",
        "without destination",
        "all destinations",
        "any destination",
    ),
    "carrier": (
        "remove airline",
        "remove the airline",
        "remove airport and airline",
        "remove the airport and airline",
        "clear airline",
        "clear the airline",
        "clear airport and airline",
        "clear the airport and airline",
        "without airline",
        "without the airline",
        "all airlines",
        "any airline",
        "all carriers",
        "remove carrier",
        "clear carrier",
    ),
    "tailnum": (
        "remove aircraft",
        "clear aircraft",
        "without aircraft",
        "all aircraft",
        "remove tail number",
        "all tail numbers",
    ),
    "aircraft_model": (
        "remove aircraft",
        "clear aircraft",
        "without aircraft",
        "all aircraft",
        "remove model",
        "clear model",
    ),
    "flight_date": (
        "remove date",
        "clear date",
        "without date",
        "all dates",
        "all time",
        "whole period",
        "full period",
        "entire period",
        "entire available period",
    ),
    "flight_year": (
        "remove date",
        "clear date",
        "without date",
        "all dates",
        "all time",
        "whole period",
        "full period",
        "entire period",
        "entire available period",
    ),
    "flight_month_number": (
        "remove date",
        "clear date",
        "without date",
        "all dates",
        "all time",
        "whole period",
        "full period",
        "entire period",
        "entire available period",
    ),
}

TIME_REMOVAL_CUES = (
    "remove date",
    "clear date",
    "without date",
    "all dates",
    "all time",
    "whole period",
    "full period",
    "entire period",
    "entire available period",
)


def apply_scope_edits(
    previous: list[TypedFilter],
    edits: list[ScopeEdit],
) -> list[TypedFilter]:
    filters = list(previous)
    for edit in edits:
        fields = (
            AIRLINE_FIELDS
            if edit.field_id in AIRLINE_FIELDS
            else DATE_FIELDS
            if edit.field_id == "flight_date" and edit.action == "remove"
            else {edit.field_id}
        )
        if edit.action in {"remove", "replace"}:
            filters = [item for item in filters if item.field_id not in fields]
        if edit.action != "remove":
            if edit.operator is None:
                raise ValueError("Scope edits require an explicit operator.")
            filters.append(
                TypedFilter(field_id=edit.field_id, operator=edit.operator, value=edit.value)
            )
        if len(filters) > 12:
            raise ValueError("The final scope cannot exceed twelve predicates.")
    return filters


def _contains_cue(question: str, cues: tuple[str, ...]) -> bool:
    normalized = re.sub(r"\s+", " ", question.casefold())
    return any(cue in normalized for cue in cues)


def _is_explicitly_removed(field_id: str, question: str) -> bool:
    if field_id in AIRLINE_FIELDS:
        cues = FILTER_REMOVAL_CUES["carrier"]
    elif field_id in DATE_FIELDS:
        cues = FILTER_REMOVAL_CUES[field_id]
    else:
        cues = FILTER_REMOVAL_CUES.get(field_id, ())
    return _contains_cue(question, cues)


def merge_follow_up_plan(
    previous_plan: AnalysisPlan,
    follow_up_plan: AnalysisPlan,
    follow_up_question: object,
) -> AnalysisPlan:
    question = validate_question(follow_up_question)
    if follow_up_plan.status != "ready":
        return follow_up_plan
    if previous_plan.status != "ready":
        raise ValueError("Follow-up scope requires a previous ready analysis plan.")

    replacement_fields = {item.field_id for item in follow_up_plan.filters}
    if replacement_fields.intersection(AIRLINE_FIELDS):
        replacement_fields.update(AIRLINE_FIELDS)
    if replacement_fields.intersection(DATE_FIELDS) or follow_up_plan.time_range is not None:
        replacement_fields.update(DATE_FIELDS)

    retained_filters = [
        item
        for item in previous_plan.filters
        if item.field_id not in replacement_fields
        and not _is_explicitly_removed(item.field_id, question)
    ]
    merged_filters = retained_filters + follow_up_plan.filters

    time_range = follow_up_plan.time_range
    if time_range is None and replacement_fields.intersection(DATE_FIELDS):
        time_range = None
    elif time_range is None and not _contains_cue(question, TIME_REMOVAL_CUES):
        time_range = previous_plan.time_range

    merged = follow_up_plan.model_dump(mode="json")
    merged["filters"] = [item.model_dump(mode="json") for item in merged_filters]
    merged["time_range"] = time_range.model_dump(mode="json") if time_range is not None else None
    return validate_analysis_plan(merged)
