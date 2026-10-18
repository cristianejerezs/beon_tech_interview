"""Deterministic report definitions, scope, coverage, and glossary metadata."""

from __future__ import annotations

from datetime import date
from typing import Any

from airport_analytics.analytics.execution import QueryResult, SummaryQueryResult
from airport_analytics.analytics.query_compiler import listing_columns
from airport_analytics.data.catalog import (
    DIMENSIONS,
    EXPLORATION_MEASURES,
    METRICS,
    required_joins,
)
from airport_analytics.models import (
    AnalysisPlan,
    BrowsePage,
    CategoryIdentity,
    EvidenceField,
    EvidenceFormat,
    EvidenceScope,
    EvidenceSelection,
    GroupedResult,
    GroupEvidence,
    ListingResult,
    NumericEvidence,
    ResolvedInterpretation,
    ScalarResult,
    TimeRange,
)

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
        "divided by the flight records in the report's effective filtered scope, "
        "before exclusions that require a successful reference/context match."
    ),
    "weather_association": (
        "Weather comparisons are contextual associations for matched origin/time observations; "
        "they do not establish that weather caused a delay."
    ),
}


def build_listing_evidence(
    interpretation: ResolvedInterpretation,
    page: BrowsePage,
    *,
    report_id: str,
) -> ListingResult:
    fields = [
        EvidenceField(
            field_id=column,
            label=column.replace("_", " "),
            role="identity"
            if column == page.identity_column
            else (
                "numeric"
                if column in {"departure_delay", "arrival_delay", "distance", "connection_count"}
                else "date"
                if column == "flight_date"
                else "category"
            ),
            unit="connected airports"
            if column == "connection_count"
            else EXPLORATION_MEASURES[column].unit
            if column in EXPLORATION_MEASURES
            else None,
            unit_provenance="application_catalog"
            if column in EXPLORATION_MEASURES or column == "connection_count"
            else None,
        )
        for column in listing_columns(interpretation)
    ]
    return ListingResult(
        result_version=2,
        evidence_version=2,
        report_id=report_id,
        section_id=interpretation.section_id,
        snapshot_id=interpretation.snapshot_id,
        context_id=interpretation.context_id,
        definition=interpretation.definition,
        grain=interpretation.grain,
        scope=EvidenceScope(
            filters=interpretation.filters,
            requested_period=interpretation.date_scope,
            observed_period=None,
            origins=[],
            coverage_status="unknown",
            denominator_basis="not_applicable",
            requested_days=None,
            verified_days=0,
            unknown_days=None,
            observed_days=0,
            eligible_days=None,
        ),
        fields=fields,
        order=interpretation.order,
        missingness={},
        selection=EvidenceSelection(
            available=page.total_rows,
            selected=len(page.rows),
            omitted=page.total_rows - len(page.rows),
            cutoff_tie=False,
        ),
        format=EvidenceFormat(locale="en", computed_places=2, rounding=None),
        limitations=[
            "Saved rows are a bounded preview, not the full population.",
            "Continuation requires the identical source snapshot and analytical context.",
            "Unmatched references preserve observed codes; null is not observed zero.",
            *(
                [
                    "Connections count distinct other airport codes in either flight direction.",
                    "All catalogue airports are included; zero means no recorded connection "
                    "in this dataset, not no real-world service.",
                    "Self-connections and missing endpoints are excluded; unmatched neighbour "
                    "codes count without adding extra catalogue rows.",
                ]
                if interpretation.population == "airport_connections"
                else []
            ),
        ],
        daily_support=[],
        route_support=[],
        kind="listing",
        population=interpretation.population,
        total_rows=page.total_rows,
        rows=page.rows,
        identity_columns=[page.identity_column],
        browse_page=page,
    )


def build_summary_evidence(
    interpretation: ResolvedInterpretation,
    result: SummaryQueryResult,
    *,
    report_id: str,
) -> ScalarResult | GroupedResult:
    scope = result.scope
    total = int(scope["filtered_flights"])
    known = int(scope["known_measure"])
    available_routes = int(scope["available_routes"])
    missingness = {
        "filtered_flights": total,
        "known_measure": known,
        "missing_measure": total - known,
        **{
            key: int(scope[key])
            for key in [
                "airline_reference_unmatched",
                "plane_reference_unmatched",
                "weather_reference_unmatched",
                "destination_reference_unmatched",
            ]
        },
    }
    if interpretation.measure_ids == ["distinct_destination_count"]:
        missingness.update(
            available_routes=available_routes,
            selected_routes=len(result.routes),
            omitted_routes=available_routes - len(result.routes),
        )
    fields = [
        EvidenceField(
            field_id=dimension,
            label=dimension.replace("_", " "),
            role="category",
            unit=None,
            unit_provenance=None,
        )
        for dimension in interpretation.grouping
    ]
    measure = interpretation.measure_ids[0]
    fields.append(
        EvidenceField(
            field_id=measure,
            label=measure.replace("_", " "),
            role="numeric",
            unit=interpretation.definition.unit,
            unit_provenance="application_catalog",
        )
    )
    observed_period = (
        TimeRange(start=scope["period_start"], end=scope["period_end"])
        if scope["period_start"] is not None
        else None
    )
    limits = [
        "Historical observed records only; recorded bounds do not establish calendar completeness.",
        "Missing reference names preserve code identity; missing values are not observed zero.",
    ]
    if interpretation.family in {"ranking", "category_comparison"}:
        limits.append("Differences are descriptive, not a statistical significance test.")
    if measure == "weather_context_departure_delay":
        limits.append("Weather context is flight-weighted association, not causation.")
    available = int(result.rows[0]["available_groups"]) if result.rows else 0
    values = [row["metric_value"] for row in result.rows]
    if interpretation.family == "ranking" and result.rows:
        missingness.update(
            top_equal_value_groups=int(result.rows[0]["equal_value_groups"]),
            selected_top_equal_value_groups=values.count(values[0]),
            omitted_top_equal_value_groups=(
                int(result.rows[0]["equal_value_groups"]) - values.count(values[0])
            ),
        )
    cutoff = bool(
        result.rows
        and available > len(result.rows)
        and int(result.rows[-1]["equal_value_groups"]) > values.count(values[-1])
        and interpretation.order
        and interpretation.order[0].field_id == measure
    )
    common = dict(
        result_version=2,
        evidence_version=2,
        report_id=report_id,
        section_id=interpretation.section_id,
        snapshot_id=interpretation.snapshot_id,
        context_id=interpretation.context_id,
        definition=interpretation.definition,
        grain=interpretation.grain,
        scope=EvidenceScope(
            filters=interpretation.filters,
            requested_period=interpretation.date_scope,
            observed_period=observed_period,
            origins=scope["origin_codes"] or [],
            coverage_status="unknown",
            denominator_basis="not_applicable",
            requested_days=None,
            verified_days=0,
            unknown_days=None,
            observed_days=int(scope["observed_days"]),
            eligible_days=None,
        ),
        fields=fields,
        order=interpretation.order,
        missingness=missingness,
        selection=EvidenceSelection(
            available=available,
            selected=len(result.rows),
            omitted=available - len(result.rows),
            cutoff_tie=cutoff,
        ),
        format=EvidenceFormat(
            locale="en", computed_places=2, rounding=interpretation.display_rounding
        ),
        limitations=limits,
        daily_support=[],
        route_support=list(result.routes),
    )

    def value(raw: object) -> NumericEvidence:
        if raw is None:
            return NumericEvidence(value=None, absence="no_known_values")
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ValueError("Analytical evidence requires finite numeric source values.")
        return NumericEvidence(value=raw, absence=None)

    if not interpretation.grouping:
        if len(result.rows) != 1:
            raise ValueError("An aggregate scalar requires exactly one numerical result.")
        return ScalarResult(**common, kind="scalar", value=value(result.rows[0]["metric_value"]))
    groups: list[GroupEvidence] = []
    for row in result.rows:
        identities = [
            CategoryIdentity(
                field_id=dimension,
                code=str(row[f"{dimension}_code"])
                if row[f"{dimension}_code"] is not None
                else None,
                label=(
                    str(row[f"{dimension}_label"]) + " [" + str(row[f"{dimension}_code"]) + "]"
                    if row[f"{dimension}_label"] is not None
                    else "Missing " + dimension.replace("_", " ")
                ),
                status=row[f"{dimension}_status"],
            )
            for dimension in interpretation.grouping
        ]
        groups.append(
            GroupEvidence(
                identity=identities,
                measures={measure: value(row["metric_value"])},
                sample_size=int(row["observation_count"]),
                tied=int(row["equal_value_groups"]) > 1,
                scoped_count=int(row["flight_count"]),
                missing_count=int(row["flight_count"]) - int(row["observation_count"]),
            )
        )
    return GroupedResult(**common, kind="grouped", values=groups)


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
    coverage = {}
    for join in sorted(joins):
        if join in coverage_key_by_join:
            total = result.scope_evidence["total"]
            matched = result.scope_evidence[f"{join}_matched"]
            coverage[coverage_key_by_join[join]] = {
                "total": total,
                "matched": matched,
                "unmatched": total - matched,
                "fraction": matched / total if total else 0.0,
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
    if result.scope_evidence:
        active_period["start"] = str(result.scope_evidence["period_start"])
        active_period["end"] = str(result.scope_evidence["period_end"])

    definitions = {
        "metric": metric.description,
        "unit": metric.unit,
        "population": metric.population,
        "numerator": metric.numerator or "Not applicable",
        "denominator": metric.denominator or "Not applicable",
        "period": f"{active_period['start']} through {active_period['end']}",
        "period_basis": "Observed date bounds in the effective filtered flight population.",
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
    if result.ranking.get("has_visible_ties"):
        limitations.append("Equal ranking values are tied; secondary ordering is by group labels.")
    if result.ranking.get("cutoff_tie"):
        limitations.append(
            "A tie crosses the requested result limit; additional tied groups are omitted. "
            "The last displayed rank is not exclusive."
        )
    if result.routes and not result.routes["complete"]:
        limitations.append(
            "Supporting route evidence is limited to 500 rows and is incomplete; "
            "do not reconcile the distinct count from this truncated table."
        )
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
