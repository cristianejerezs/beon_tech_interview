"""Deterministic, accessible report presentation from validated result rows."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

import plotly.express as px

from airport_analytics.data.catalog import METRICS
from airport_analytics.errors import (
    MissingVisualEvidenceError,
    PresentationPreferenceError,
    UnsupportedAnalysisError,
    VisualEvidenceError,
)
from airport_analytics.models import (
    CompositeReportV2,
    DailyMeanResult,
    DistributionResult,
    ExplorationResult,
    GroupedResult,
    ListingResult,
    PeriodChangeResult,
    RelationshipResult,
    ReportContent,
    ReportSection,
    SavedReport,
    ScalarResult,
    WeatherPanelResult,
)
from airport_analytics.observability.timing import capture_visual_preparation, timed_stage
from airport_analytics.reports.charts import (
    build_browser_chart,
    describe_visual,
    format_visual_number,
)
from airport_analytics.reports.visual_evidence import (
    prepare_visual_evidence,
    resolve_presentation,
)


def section_evidence(section: ReportSection) -> ExplorationResult | None:
    if section.outcome.status == "failed":
        return None
    if section.outcome.status == "completed":
        return section.outcome.result
    return section.outcome.evidence


def weather_findings(evidence: WeatherPanelResult) -> str:
    """Explain the saved coefficients without model calls or strength thresholds."""
    labels = {
        "temp": "Temperature",
        "wind_speed": "Wind speed",
        "precip": "Precipitation",
        "visib": "Visibility",
    }
    findings = [
        "Weather and departure delay: Pearson correlations compare each recorded weather "
        "value with mean departure delay per origin-hour, giving each valid hour equal weight."
    ]
    for origin in dict.fromkeys(item.origin for item in evidence.variables):
        variables = [item for item in evidence.variables if item.origin == origin]
        findings.append(f"{origin or 'All scoped origins combined'}:")
        available = []
        for item in variables:
            label = labels[item.variable]
            value = item.coefficient.value
            count = item.pairing.pair_count
            if value is None:
                reason = (
                    "a constant axis"
                    if item.coefficient.absence == "constant_axis"
                    else "fewer than three valid pairs"
                )
                findings.append(f"{label}: correlation unavailable ({reason}; {count:,} pairs).")
                continue
            available.append(item)
            relationship = (
                "higher recorded values are associated with higher mean departure delays"
                if value > 0
                else "higher recorded values are associated with lower mean departure delays"
                if value < 0
                else "no observed linear association"
            )
            findings.append(
                f"{label}: r = {value:.3f} ({count:,} valid origin-hours); {relationship}."
            )
        if available:
            largest = max(abs(item.coefficient.value) for item in available)
            if largest > 0:
                names = ", ".join(
                    labels[item.variable].lower()
                    for item in available
                    if abs(item.coefficient.value) == largest
                )
                findings.append(
                    f"Largest absolute correlation among the available variables: {names} "
                    f"(|r| = {largest:.3f})."
                )
    findings.append(
        "Values closer to zero indicate less linear association; values closer to -1 or +1 "
        "indicate more. These descriptive correlations do not establish causation, statistical "
        "significance or predictive accuracy. Pooled origins can mask airport-specific patterns; "
        "each variable may use a different set of valid hours."
    )
    if evidence.weather_units_status == "unverified":
        findings.append(
            "Provisional Pearson correlations use recorded weather values with unverified "
            "units. Unit-dependent precipitation comparisons are unavailable."
        )
    return "\n\n".join(findings)


def detail_rows(details: dict[str, object], prefix: str = "") -> list[dict[str, str]]:
    rows = []
    for key, value in details.items():
        label = (
            f"{prefix} / {key.replace('_', ' ').capitalize()}"
            if prefix
            else (key.replace("_", " ").capitalize())
        )
        if isinstance(value, dict):
            rows.extend(detail_rows(value, label))
        elif isinstance(value, list) and any(isinstance(item, dict) for item in value):
            for index, item in enumerate(value, 1):
                rows.extend(detail_rows({str(index): item}, label))
        else:
            text = (
                "Not applicable"
                if value is None
                else "Yes"
                if value is True
                else "No"
                if value is False
                else "; ".join(str(item) for item in value)
                if isinstance(value, list)
                else str(value).replace("_", " ")
                if key in {"weighting", "additivity", "denominator_basis", "coverage_status"}
                else str(value)
            )
            rows.append({"Detail": label, "Description": text or "None"})
    return rows


@timed_stage("table_preparation")
def summary_result_table(
    evidence: ExplorationResult,
) -> tuple[list[str], list[dict[str, object]]]:
    if isinstance(evidence, ListingResult):
        return [field.field_id for field in evidence.fields], list(evidence.rows)
    if isinstance(evidence, DailyMeanResult):

        def rounded(group):
            if (
                evidence.format.rounding is None
                or group.numerator is None
                or not group.eligible_days
                or group.value.value is None
            ):
                return None
            places = evidence.format.rounding.places
            with localcontext() as context:
                context.prec = 40
                value = Decimal(str(group.numerator)) / Decimal(group.eligible_days)
                return str(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))

        rows = [
            {
                **{identity.field_id: identity.label for identity in group.identity},
                "value": group.value.value,
                "unavailable_reason": group.value.absence,
                "numerator": group.numerator,
                "eligible_days": group.eligible_days,
                "known_contributions": group.known_contribution_count,
                "unknown_contributions": group.unknown_contribution_count,
                "provisional": group.provisional,
                "rounded_display": rounded(group),
            }
            for group in evidence.values
        ]
        return list(rows[0]) if rows else ["value", "unavailable_reason"], rows
    if isinstance(evidence, DistributionResult):
        return ["lower", "upper", "count", "upper_inclusive"], [
            item.model_dump() for item in evidence.bins
        ]
    if isinstance(evidence, PeriodChangeResult):
        return ["component", "value", "unavailable_reason", "day_exposure"], [
            {
                "component": name,
                "value": value.value,
                "unavailable_reason": value.absence,
                "day_exposure": exposure,
            }
            for name, value, exposure in [
                ("baseline", evidence.baseline.value, evidence.baseline.day_exposure),
                ("comparison", evidence.comparison.value, evidence.comparison.day_exposure),
                ("absolute_change", evidence.absolute_change, None),
                ("relative_change_percent", evidence.relative_change, None),
            ]
        ]
    if isinstance(evidence, RelationshipResult):
        pair = evidence.pairing
        if pair.pairs is not None:
            return ["source_id", pair.x_field, pair.y_field], [
                {"source_id": item.source_id, pair.x_field: item.x, pair.y_field: item.y}
                for item in pair.pairs
            ]
        return ["x_cell", "y_cell", "count"], [
            {"x_cell": cell.x, "y_cell": cell.y, "count": cell.count} for cell in pair.density.cells
        ]
    if isinstance(evidence, WeatherPanelResult):
        return ["origin", "variable", "coefficient", "unavailable_reason", "pair_count"], [
            {
                "origin": item.origin,
                "variable": item.variable,
                "coefficient": item.coefficient.value,
                "unavailable_reason": item.coefficient.absence,
                "pair_count": item.pairing.pair_count,
            }
            for item in evidence.variables
        ]
    if isinstance(evidence, ScalarResult):
        measure = next(field.field_id for field in evidence.fields if field.role == "numeric")
        return [measure, "unavailable_reason"], [
            {
                measure: evidence.value.value,
                "unavailable_reason": evidence.value.absence,
            }
        ]
    if not isinstance(evidence, GroupedResult):
        raise UnsupportedAnalysisError("This result requires its section-specific table adapter.")
    dimensions = [field.field_id for field in evidence.fields if field.role != "numeric"]
    measures = [field.field_id for field in evidence.fields if field.role == "numeric"]
    columns = [
        key
        for field in dimensions
        for key in [f"{field}_code", f"{field}_label", f"{field}_status"]
    ]
    columns += [key for field in measures for key in [field, f"{field}_unavailable_reason"]]
    columns += ["scoped_count", "observation_count", "missing_count", "tied"]
    rows: list[dict[str, object]] = []
    for group in evidence.values:
        row: dict[str, object] = {}
        for identity in group.identity:
            row.update(
                {
                    f"{identity.field_id}_code": identity.code,
                    f"{identity.field_id}_label": identity.label,
                    f"{identity.field_id}_status": identity.status,
                }
            )
        for measure, number in group.measures.items():
            row[measure] = number.value
            row[f"{measure}_unavailable_reason"] = number.absence
        row.update(
            scoped_count=group.scoped_count,
            observation_count=group.sample_size,
            missing_count=group.missing_count,
            tied=group.tied,
        )
        rows.append(row)
    return columns, rows


def _paged_pair_rows(
    report: CompositeReportV2,
    section: ReportSection,
    st: Any,
    rows: list[dict[str, object]],
    *,
    pair_label: str,
    pair_index: int,
) -> list[dict[str, object]]:
    if not rows:
        st.info("No complete paired observations are available in the saved evidence.")
        return rows

    page_size = 100
    page_count = (len(rows) + page_size - 1) // page_size
    page = 1
    if page_count > 1:
        page = st.number_input(
            f"Page of exact paired observations for {pair_label}",
            min_value=1,
            max_value=page_count,
            value=1,
            step=1,
            format="%d",
            required=True,
            key=(
                f"visual-pairs-page-{report.analyst_id}-{report.report_id}-"
                f"{section.section_id}-{pair_index}"
            ),
            help="Review all saved paired observations in 100-row table pages.",
        )
        if type(page) is not int:
            st.error("Enter a valid page number to view exact paired observations.")
            return []

    start = (page - 1) * page_size
    end = min(start + page_size, len(rows))
    st.caption(
        f"Exact paired observations: rows {start + 1:,}–{end:,} of {len(rows):,} "
        f"(page {page:,} of {page_count:,}). All paired values remain in the saved evidence."
    )
    return rows[start:end]


@dataclass(frozen=True)
class SavedSectionView:
    section_id: str
    label: str
    narrative: str
    definitions: dict[str, object]
    evidence: dict[str, object]
    failure: str | None = None


def saved_report_sections(report: SavedReport) -> tuple[SavedSectionView, ...]:
    if isinstance(report, ReportContent):
        return (
            SavedSectionView(
                section_id=f"{report.report_id}:legacy",
                label=report.question,
                narrative=report.narrative,
                definitions=dict(report.definitions),
                evidence=report.result_payload,
            ),
        )
    sections: list[SavedSectionView] = []
    for section in report.sections:
        result = None
        failure = None
        if section.outcome.status == "completed":
            result = section.outcome.result
        elif section.outcome.status == "valid_empty":
            result = section.outcome.evidence
        else:
            failure = section.outcome.failure.message
        sections.append(
            SavedSectionView(
                section_id=section.section_id,
                label=section.label,
                narrative=section.narrative,
                definitions=section.interpretation.definition.model_dump(mode="json"),
                evidence=result.model_dump(mode="json") if result is not None else {},
                failure=failure,
            )
        )
    return tuple(sections)


def chart_kind(report: SavedReport) -> str:
    if isinstance(report, CompositeReportV2):
        return "table"
    rows = report.result_payload["rows"]
    plan = report.analysis_plan
    if not rows or len(plan.group_by) != 1 or len(rows) > 50:
        return "table"
    dimension = plan.group_by[0]
    if plan.chart_intent == "line" and dimension == "flight_month":
        return "line"
    if plan.chart_intent == "bar":
        return "bar"
    return "table"


def build_figure(report: SavedReport) -> Any | None:
    if isinstance(report, CompositeReportV2):
        return None
    kind = chart_kind(report)
    if kind == "table":
        return None
    data = report.result_payload["rows"]
    dimension = report.analysis_plan.group_by[0]
    metric = METRICS[report.analysis_plan.metric_id]
    labels = {dimension: dimension.replace("_", " "), "metric_value": metric.unit}
    if kind == "line":
        return px.line(
            data,
            x=dimension,
            y="metric_value",
            markers=True,
            labels=labels,
            title=f"{metric.description} ({metric.unit}); {report.definitions['period']}",
        )
    return px.bar(
        data,
        x=dimension,
        y="metric_value",
        labels=labels,
        title=f"{metric.description} ({metric.unit}); {report.definitions['period']}",
        hover_data=["flight_count", "observation_count"],
    )


def render_report(
    report: SavedReport,
    st: Any,
    *,
    visual_reporting_enabled: bool = False,
) -> None:
    st.header(report.question)
    if not visual_reporting_enabled:
        st.caption(
            "Visual reporting is disabled; this report uses the existing saved-evidence view."
        )
    if isinstance(report, CompositeReportV2):
        st.caption(
            f"Report V2; {report.completeness}; snapshot {report.snapshot_id[:12]}; "
            f"semantic context {report.context_id[:12]}."
        )
        for index, section in enumerate(saved_report_sections(report), start=1):
            st.subheader(f"{index}. {section.label}")
            if section.failure is not None:
                st.error(section.failure)
                continue
            evidence = section_evidence(report.sections[index - 1])
            st.write(
                weather_findings(evidence)
                if isinstance(evidence, WeatherPanelResult)
                else section.narrative
            )
            with st.expander("How this was calculated"):
                st.table(
                    detail_rows(section.definitions),
                    alt=f"Analytical definition: {section.label}",
                )
            evidence = section_evidence(report.sections[index - 1])
            if evidence is not None:
                if visual_reporting_enabled:
                    render_visual_section(
                        report,
                        report.sections[index - 1],
                        st,
                    )
                if (
                    isinstance(evidence, WeatherPanelResult)
                    and evidence.weather_units_status == "unverified"
                ):
                    st.warning(
                        "Provisional Pearson correlations use recorded weather values with "
                        "unverified units. Unit-dependent precipitation comparisons are "
                        "unavailable."
                    )
                _, rows = summary_result_table(evidence)
                results_alt = f"Exact results: {section.label}"
                if isinstance(evidence, RelationshipResult):
                    if evidence.pairing.pairs is not None:
                        rows = _paged_pair_rows(
                            report,
                            report.sections[index - 1],
                            st,
                            rows,
                            pair_label=section.label,
                            pair_index=0,
                        )
                        results_alt = f"Exact paired observations: {section.label}"
                    else:
                        st.caption(
                            f"Exact relationship density cells: {len(rows):,} displayed cells "
                            f"for {evidence.pairing.pair_count:,} paired observations."
                        )
                        results_alt = f"Exact relationship density cells: {section.label}"
                st.dataframe(
                    rows,
                    hide_index=True,
                    alt=results_alt,
                    column_config={
                        column: column.replace("_", " ").capitalize()
                        for column in (rows[0] if rows else {})
                    },
                )
                if visual_reporting_enabled and not isinstance(evidence, ListingResult):
                    st.caption(
                        f"Exact saved evidence table: {len(rows):,} displayed rows. "
                        "The full saved analytical result is retained; the default visual "
                        "does not change it."
                    )
                if (
                    isinstance(evidence, GroupedResult)
                    and "origin" in report.sections[index - 1].interpretation.grouping
                    and "distinct_destination_count"
                    in report.sections[index - 1].interpretation.measure_ids
                ):
                    st.caption(
                        "Each row counts distinct destination codes for a recorded departure "
                        "origin in the selected flight data. The airport reference supplies "
                        "metadata, not additional flights. Airports without departure "
                        "observations are not included; their worldwide connections are unknown."
                    )
                if isinstance(evidence, ListingResult):
                    st.caption(
                        f"Saved preview: {len(evidence.rows):,} of {evidence.total_rows:,} "
                        f"{evidence.population.replace('_', ' ')}. Not a full-population export."
                    )
                else:
                    st.caption(
                        f"Analytical selection: {evidence.selection.selected} of "
                        f"{evidence.selection.available} groups; omitted "
                        f"{evidence.selection.omitted}. "
                        f"Cutoff tie: {'yes' if evidence.selection.cutoff_tie else 'no'}."
                    )
                with st.expander("Scope and data quality"):
                    st.table(
                        detail_rows(evidence.scope.model_dump(mode="json")),
                        alt=f"Requested and observed scope: {section.label}",
                    )
                    st.table(
                        detail_rows(evidence.missingness),
                        alt=f"Known, missing and unmatched populations: {section.label}",
                    )
                if evidence.route_support:
                    st.write("Supporting routes")
                    st.dataframe(
                        evidence.route_support,
                        hide_index=True,
                        alt=f"Supporting observed routes: {section.label}",
                    )
                for limitation in evidence.limitations:
                    st.caption(limitation)
                if evidence.daily_support:
                    st.write("Bounded daily supporting evidence")
                    st.dataframe(
                        evidence.daily_support,
                        hide_index=True,
                        alt=f"Bounded daily supporting evidence: {section.label}",
                    )
                if isinstance(evidence, PeriodChangeResult):
                    for warning in evidence.warnings:
                        st.warning(warning)
                if isinstance(evidence, (RelationshipResult, WeatherPanelResult)):
                    pairings = (
                        [(section.label, evidence.pairing)]
                        if isinstance(evidence, RelationshipResult)
                        else [
                            (f"{item.origin or 'All origins'} / {item.variable}", item.pairing)
                            for item in evidence.variables
                        ]
                    )
                    with st.expander("Pair populations and missingness"):
                        if isinstance(evidence, WeatherPanelResult):
                            for variable in evidence.variables:
                                st.table(
                                    detail_rows(
                                        variable.model_dump(
                                            mode="json",
                                            exclude={"pairing"},
                                        )
                                    ),
                                    alt=f"Weather coefficient and comparison: {variable.variable}",
                                )
                        for pair_index, (label, pairing) in enumerate(pairings):
                            st.write(label)
                            st.table(
                                detail_rows(
                                    pairing.model_dump(
                                        mode="json",
                                        exclude={"pairs", "density"},
                                    )
                                ),
                                alt=f"Pair population details: {label}",
                            )
                            if pairing.density is not None:
                                st.table(
                                    detail_rows(pairing.density.model_dump(exclude={"cells"})),
                                    alt=f"Density boundaries: {label}",
                                )
                            if isinstance(evidence, WeatherPanelResult):
                                if pairing.pairs is not None:
                                    values = [
                                        {
                                            "source_id": item.source_id,
                                            pairing.x_field: item.x,
                                            pairing.y_field: item.y,
                                        }
                                        for item in pairing.pairs
                                    ]
                                    values = _paged_pair_rows(
                                        report,
                                        report.sections[index - 1],
                                        st,
                                        values,
                                        pair_label=label,
                                        pair_index=pair_index,
                                    )
                                    table_alt = f"Exact weather paired observations: {label}"
                                else:
                                    values = [
                                        {
                                            "x_cell": item.x,
                                            "y_cell": item.y,
                                            "count": item.count,
                                        }
                                        for item in pairing.density.cells
                                    ]
                                    table_alt = f"Exact weather density cells: {label}"
                                st.dataframe(
                                    values,
                                    hide_index=True,
                                    alt=table_alt,
                                )
            else:
                st.write("Saved numerical evidence")
                st.table(detail_rows(section.evidence), alt="Saved numerical evidence")
        return
    st.subheader("Answer")
    st.write(report.narrative)
    st.subheader("Metric definition and scope")
    st.table(
        [
            {"Item": label.replace("_", " ").title(), "Description": value}
            for label, value in report.definitions.items()
        ],
        alt="Metric definitions and scope",
    )
    scope = report.result_payload["scope"]
    st.caption(
        "Active filters: "
        + (", ".join(scope["filters"]) if scope["filters"] else "none")
        + "; grouped by: "
        + (", ".join(scope["group_by"]) if scope["group_by"] else "overall")
    )
    st.caption(
        "Source coverage: "
        + (", ".join(scope["geographic_coverage"]) or "no origin codes")
        + "; source snapshot "
        + report.snapshot_id[:12]
    )

    coverage = report.result_payload["join_coverage"]
    if coverage:
        st.subheader("Reference and context coverage")
        coverage_rows = [
            {
                "Join": name.replace("_", " ").title(),
                "Matched records": counts["matched"],
                "Unmatched records": counts["unmatched"],
                "Coverage": f"{counts['fraction']:.2%}",
                "Population": (
                    f"{counts['total']:,} records in the filtered scope before match exclusions"
                ),
            }
            for name, counts in coverage.items()
        ]
        st.dataframe(
            coverage_rows,
            hide_index=True,
            alt="Reference and context coverage",
        )

    figure = build_figure(report)
    st.subheader("Supporting results")
    if figure is not None:
        st.plotly_chart(figure, alt="Supporting results in the saved report")
    st.dataframe(
        report.result_payload["rows"],
        hide_index=True,
        alt="Saved analytical result rows",
    )
    routes = report.result_payload.get("routes", {})
    if routes:
        st.subheader("Supporting routes")
        st.caption(routes["population"])
        st.caption("Complete route table." if routes["complete"] else "Truncated to 500 routes.")
        st.dataframe(
            routes["rows"],
            hide_index=True,
            alt="Supporting route results",
        )

    glossary = report.result_payload["glossary"]
    if glossary:
        st.subheader("Terms")
        for term, definition in glossary.items():
            st.write(f"**{term.replace('_', ' ').title()}:** {definition}")
    if report.limitations:
        st.subheader("Limitations")
        for limitation in report.limitations:
            st.write(f"- {limitation}")


def render_visual_section(report: CompositeReportV2, section: ReportSection, st: Any) -> None:
    """Render only a deterministic view over this saved section's typed evidence."""
    try:
        with capture_visual_preparation() as timing:
            evidence = prepare_visual_evidence(report, section.section_id)
            timing.set_evidence(
                evidence.shape,
                len(evidence.payload.canonical_json.encode("utf-8")),
            )
            preference = report.presentation_preferences.get(section.section_id)
            resolution = resolve_presentation(evidence, preference)
            description = None
            chart = None
            if resolution.state in {"ready", "table_selected"}:
                description = describe_visual(resolution)
                if resolution.view not in {"summary", "table"}:
                    try:
                        chart = build_browser_chart(resolution)
                    except VisualEvidenceError:
                        timing.set_failure("chart_render")
                        raise
    except MissingVisualEvidenceError as exc:
        st.info(exc.user_message)
        return
    except (PresentationPreferenceError, VisualEvidenceError) as exc:
        st.error(exc.user_message)
        return

    if resolution.state == "selection_required":
        st.info(resolution.reason)
        return
    if resolution.state == "no_plottable_data":
        st.info(resolution.reason)
        return
    if resolution.state not in {"ready", "table_selected"}:
        st.error("This saved evidence is not available for visual presentation.")
        return
    if description is None:
        st.error("This saved evidence is not available for visual presentation.")
        return
    if resolution.view == "summary":
        payload = evidence.payload.to_dict()
        value = payload.get("value")
        if payload.get("kind") == "daily_mean":
            daily = evidence.typed_result()
            if isinstance(daily, DailyMeanResult) and len(daily.values) == 1:
                value = daily.values[0].value.model_dump(mode="json")
        raw = value.get("value") if isinstance(value, dict) else None
        if type(raw) not in {int, float}:
            st.info("The saved scalar value is unavailable; see its exact evidence below.")
            return
        shown_value = format_visual_number(value, evidence)
        st.metric(description.name, shown_value)
        st.caption(description.explanation)
        return
    if resolution.view == "table":
        st.caption("This saved result is available as an exact evidence table.")
        return
    if chart is None:
        st.caption("No graphical view is required; the exact evidence table follows.")
        return
    st.vega_lite_chart(chart, alt=description.name)
    st.caption(description.explanation)
    if evidence.shape == "period_change":
        payload = evidence.payload.to_dict()
        saved_unit = evidence.definition.to_dict().get("unit")
        unit = saved_unit if isinstance(saved_unit, str) and saved_unit else "recorded units"
        absolute = format_visual_number(payload.get("absolute_change"), evidence, unit)
        relative = format_visual_number(payload.get("relative_change"), evidence, "%")
        st.write(
            f"Period-change summary: Absolute change: {absolute}; Relative change: {relative}."
        )
