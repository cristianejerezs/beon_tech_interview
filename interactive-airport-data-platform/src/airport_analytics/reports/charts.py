"""Deterministic, embedded Vega-Lite charts for immutable saved evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

from airport_analytics.errors import VisualEvidenceError
from airport_analytics.reports.visual_evidence import (
    PresentationResolution,
    VisualEvidence,
    canonical_identity,
)

_VL_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.20.1.json"


@dataclass(frozen=True)
class VisualDescription:
    name: str
    explanation: str


def describe_visual(resolution: PresentationResolution) -> VisualDescription:
    evidence = _require_evidence(resolution)
    if resolution.selection is None:
        raise VisualEvidenceError()
    dimension_names = [dimension.label for dimension in evidence.dimensions]
    measure = _measure_label(evidence)
    unit = _measure_unit(evidence)
    measure_text = f"{measure} ({unit})" if unit else measure
    if resolution.view == "summary":
        name = f"{measure} summary"
    elif resolution.view == "table":
        name = "Exact evidence table"
    elif resolution.view == "histogram":
        name = f"Distribution of {evidence.payload.to_dict().get('variable', measure_text)}"
    elif resolution.view == "scatter":
        name = _relationship_name(resolution, "Scatter")
    elif resolution.view == "density":
        name = _relationship_name(resolution, "Density")
    elif evidence.shape in {"time", "time_series"}:
        grain = evidence.grain.replace("_", " ")
        axes = " by ".join(dimension_names)
        name = f"Line chart of {measure_text} by {axes} ({grain})"
    elif evidence.shape == "period_change":
        name = f"Period comparison of {measure_text}"
    else:
        view_name = resolution.view.replace("_", " ").title()
        target = f"{measure_text} by {', '.join(dimension_names)}"
        name = f"{view_name} of {target}"
    if evidence.shape in {"relationship", "weather"}:
        pairing = _relationship_pairing(resolution)
        if pairing is None:
            raise VisualEvidenceError()
        pair_count = pairing.get("pair_count")
        scoped_count = pairing.get("scoped_count")
        x_missing = pairing.get("x_missing_only")
        y_missing = pairing.get("y_missing_only")
        both_missing = pairing.get("both_missing")
        x_field = pairing.get("x_field")
        y_field = pairing.get("y_field")
        if (
            type(pair_count) is not int
            or type(scoped_count) is not int
            or type(x_missing) is not int
            or type(y_missing) is not int
            or type(both_missing) is not int
            or not isinstance(x_field, str)
            or not isinstance(y_field, str)
        ):
            raise VisualEvidenceError()
        if evidence.shape == "weather":
            variable = resolution.selection.weather_variable
            if variable is None:
                raise VisualEvidenceError()
            airport = resolution.selection.weather_airport or "combined airport scope"
            scope = (
                f"Weather {variable} for {airport}: {pair_count:,} complete paired observations."
            )
        else:
            scope = f"Represents {pair_count:,} complete paired observations."
        if resolution.view == "density" or pairing.get("pairs") is None:
            scope += " All complete pairs are summarized in the saved density cells."
        else:
            scope += " All complete paired observations are shown."
        scope += (
            f" Of {scoped_count:,} scoped observations, {x_missing:,} lacked {x_field} only, "
            f"{y_missing:,} lacked {y_field} only, and {both_missing:,} lacked both."
        )
    else:
        shown = resolution.selection.shown_groups
        available = resolution.selection.available_groups
        scope = f"Shown: {shown} saved group{'s' if shown != 1 else ''}"
        if resolution.selection.visual_omitted_groups:
            scope += f"; omitted from the visual: {resolution.selection.visual_omitted_groups}"
        if available is not None:
            scope += f"; returned: {resolution.selection.returned_groups}; available: {available}."
        else:
            scope += (
                f"; returned: {resolution.selection.returned_groups}. "
                "The available total is unknown."
            )
    limitations = list(evidence.limitations)
    coverage = evidence.coverage.to_dict()
    if evidence.shape in {"time", "time_series"} and coverage.get("status") == "unknown":
        limitations.append("Coverage completeness is unknown.")
    elif (
        evidence.shape in {"time", "time_series"} and coverage.get("status") == "verified_intervals"
    ):
        limitations.append(
            "Verified intervals define expected buckets; dates outside them remain unknown."
        )
    requested_period = _period_range(evidence.scope.to_dict().get("requested_period"))
    observed_period = _period_range(evidence.scope.to_dict().get("observed_period"))
    if requested_period is not None:
        limitations.append(f"Requested period: {requested_period}.")
    if observed_period is not None:
        limitations.append(f"Observed period: {observed_period}.")
    limitations.append(
        f"Snapshot {evidence.snapshot_id}; report revision {evidence.analytical_revision}; "
        f"section {evidence.section_id}."
    )
    if evidence.shape in {"time", "time_series"}:
        limitations.append(
            f"Time zone: {coverage.get('time_zone') or 'not applicable - recorded departure date'}."
        )
        if resolution.view in {"line", "small_multiples"}:
            statuses = [
                row.get("visual_period_status")
                for row in _temporal_rows(evidence, _shown_rows(resolution))
            ]
            partial = statuses.count("partial")
            if partial:
                limitations.append(
                    f"{partial} displayed bucket{'s' if partial != 1 else ''} "
                    "intersect a partial calendar period."
                )
    if evidence.shape in {"time", "time_series"} and isinstance(coverage.get("reason"), str):
        limitations.append(coverage["reason"])
    values = [
        value
        for row in _shown_rows(resolution)
        if (value := _row_measure(row, evidence.measure_ids[0] if evidence.measure_ids else None))
        is not None
    ]
    if values:
        low = _format_display_number(min(values), evidence)
        high = _format_display_number(max(values), evidence)
        limits = f" {unit}" if unit else ""
        limitations.append(f"Displayed range within the shown subset: {low} to {high}{limits}.")
    if values and all(value == 0 for value in values):
        limitations.append("All displayed values are zero; category labels are retained.")
    shown_rows = _shown_rows(resolution)
    if any(isinstance(row, dict) and row.get("tied") is True for row in shown_rows):
        limitations.append("Tied values are present within the shown subset.")
    if resolution.selection.visual_cutoff_tie:
        limitations.append("The visual cutoff omits a category tied at the displayed boundary.")
    if evidence.shape in {"time", "time_series"} and resolution.view in {
        "line",
        "small_multiples",
    }:
        temporal_rows = _temporal_rows(evidence, _shown_rows(resolution))
        gap_count = sum(
            isinstance(row.get("visual_gap_reason"), str)
            and row.get("visual_gap_reason")
            in {"verified_coverage_gap", "coverage_unknown_missing_bucket"}
            for row in temporal_rows
        )
        if gap_count:
            limitations.append(
                f"{gap_count} unavailable calendar bucket{'s' if gap_count != 1 else ''} "
                "break the line; no zero values were inferred."
            )
    population_counts = _population_counts(shown_rows)
    if population_counts:
        limitations.append(population_counts)
    unavailable_reasons = _unavailable_reasons(shown_rows, evidence)
    if unavailable_reasons:
        limitations.append(f"Unavailable values: {', '.join(unavailable_reasons)}.")
    saved_missingness = evidence.missingness.to_dict()
    if saved_missingness:
        limitations.append(
            "Saved missingness counts: "
            + ", ".join(f"{key} {value}" for key, value in sorted(saved_missingness.items()))
            + "."
        )
    if evidence.population:
        limitations.append(f"Population: {evidence.population}.")
    explanation = " ".join([scope, *limitations]).strip()
    return VisualDescription(name=name, explanation=explanation)


def build_chart(resolution: PresentationResolution) -> dict[str, Any] | None:
    """Build a local Vega-Lite spec using only facts contained in saved evidence."""
    evidence = _require_evidence(resolution)
    if resolution.view in {"summary", "table"}:
        return None
    if resolution.state not in {"ready", "table_selected"}:
        raise VisualEvidenceError()
    payload = evidence.payload.to_dict()
    spec: dict[str, Any] = {
        "$schema": _VL_SCHEMA,
        "description": describe_visual(resolution).explanation,
        "data": {"values": []},
        "mark": {},
        "encoding": {},
    }
    if evidence.shape in {"time", "time_series"} and resolution.view in {"line", "small_multiples"}:
        rows = _temporal_rows(evidence, _shown_rows(resolution))
        spec["data"]["values"] = rows
        dimensions = evidence.dimensions
        if not dimensions:
            raise VisualEvidenceError()
        layers = _time_chart_layers(evidence, rows, dimensions)
        if resolution.view == "small_multiples":
            if len(dimensions) != 2:
                raise VisualEvidenceError()
            spec["facet"] = {
                "column": {
                    "field": "visual_category_1",
                    "type": "nominal",
                    "title": dimensions[1].label,
                    "sort": [identity.label for identity in dimensions[1].identities],
                }
            }
            spec["spec"] = {"layer": layers}
            spec["resolve"] = {"scale": {"x": "shared", "y": "shared"}}
        elif sum(_row_measure(row, evidence.measure_ids[0]) is not None for row in rows) == 1:
            spec["mark"] = layers[1]["mark"]
            spec["encoding"] = layers[1]["encoding"]
        else:
            spec["layer"] = layers
        if "layer" in spec or "facet" in spec:
            spec.pop("mark")
            spec.pop("encoding")
    elif evidence.shape != "period_change" and resolution.view in {
        "bar",
        "dot",
        "line",
        "small_multiples",
        "grouped_bar",
        "heatmap",
    }:
        saved_rows = payload.get("values")
        if not isinstance(saved_rows, list):
            raise VisualEvidenceError()
        rows = _shown_rows(resolution)
        spec["data"]["values"] = rows
        dimensions = evidence.dimensions
        if not dimensions:
            raise VisualEvidenceError()
        transforms = _dimension_transforms(dimensions, rows)
        if transforms:
            spec["transform"] = transforms
        if resolution.view == "heatmap":
            if len(dimensions) != 2:
                raise VisualEvidenceError()
            base_encoding = {
                "x": {
                    "field": "visual_category_0",
                    "type": "ordinal",
                    "title": dimensions[0].label,
                    "sort": [identity.label for identity in dimensions[0].identities],
                },
                "y": {
                    "field": "visual_category_1",
                    "type": "ordinal",
                    "title": dimensions[1].label,
                    "sort": [identity.label for identity in dimensions[1].identities],
                },
            }
            measure_field = _measure_field(evidence)
            spec["layer"] = [
                {
                    "mark": {"type": "rect", "stroke": "#FFFFFF"},
                    "encoding": base_encoding
                    | {
                        "color": {
                            "field": measure_field,
                            "type": "quantitative",
                            "title": _measure_label(evidence),
                        },
                        "tooltip": _tooltips(evidence, dimensions, rows),
                    },
                },
                {
                    "mark": {"type": "text", "fontSize": 10, "color": "#000000"},
                    "encoding": base_encoding
                    | {
                        "text": {"field": measure_field, "type": "quantitative"},
                        "tooltip": _tooltips(evidence, dimensions, rows),
                    },
                },
            ]
            spec.pop("mark")
            spec.pop("encoding")
        elif resolution.view == "grouped_bar":
            if len(dimensions) != 2:
                raise VisualEvidenceError()
            spec["mark"] = {"type": "bar"}
            spec["encoding"] = {
                "x": {
                    "field": "visual_category_0",
                    "type": "nominal",
                    "title": dimensions[0].label,
                    "sort": [identity.label for identity in dimensions[0].identities],
                },
                "xOffset": {"field": "visual_category_1", "type": "nominal"},
                "y": _quantitative_encoding(evidence, rows, "zero"),
                "color": {
                    "field": "visual_category_1",
                    "type": "nominal",
                    "title": dimensions[1].label,
                },
                "tooltip": _tooltips(evidence, dimensions, rows),
            }
        elif resolution.view == "small_multiples":
            if len(dimensions) != 2:
                raise VisualEvidenceError()
            spec["facet"] = {
                "column": {
                    "field": "visual_category_1",
                    "type": "nominal",
                    "title": dimensions[1].label,
                }
            }
            spec["spec"] = {
                "mark": {"type": "line", "point": True},
                "encoding": {
                    "x": {
                        "field": "visual_category_0",
                        "type": "ordinal",
                        "title": dimensions[0].label,
                        "sort": [identity.label for identity in dimensions[0].identities],
                    },
                    "y": _quantitative_encoding(evidence, rows),
                    "tooltip": _tooltips(evidence, dimensions, rows),
                },
            }
            spec["resolve"] = {"scale": {"x": "shared", "y": "shared"}}
            spec.pop("mark")
            spec.pop("encoding")
        elif resolution.view == "line":
            spec["mark"] = {"type": "line", "point": True}
            spec["encoding"] = {
                "x": {
                    "field": "visual_category_0",
                    "type": "ordinal",
                    "title": dimensions[0].label,
                    "sort": [identity.label for identity in dimensions[0].identities],
                },
                "y": _quantitative_encoding(evidence, rows),
                "tooltip": _tooltips(evidence, dimensions, rows),
            }
            if len(dimensions) == 2:
                spec["encoding"]["color"] = {
                    "field": "visual_category_1",
                    "type": "nominal",
                    "title": dimensions[1].label,
                }
        elif resolution.view == "bar" and evidence.shape == "ranking":
            labels = [identity.label for identity in dimensions[0].identities]
            spec["mark"] = {"type": "bar"}
            spec["encoding"] = {
                "x": _quantitative_encoding(evidence, rows, "zero"),
                "y": {
                    "field": "visual_category_0",
                    "type": "nominal",
                    "title": dimensions[0].label,
                    "sort": labels,
                },
                "tooltip": _tooltips(evidence, dimensions, rows),
            }
        elif resolution.view == "dot":
            spec["mark"] = {"type": "point", "filled": True}
            spec["encoding"] = {
                "x": {
                    "field": "visual_category_0",
                    "type": "nominal",
                    "title": dimensions[0].label,
                    "sort": [identity.label for identity in dimensions[0].identities],
                },
                "y": _quantitative_encoding(evidence, rows),
                "tooltip": _tooltips(evidence, dimensions, rows),
            }
        else:
            spec["mark"] = {"type": "bar"}
            spec["encoding"] = {
                "x": {
                    "field": "visual_category_0",
                    "type": "nominal",
                    "title": dimensions[0].label,
                    "sort": [identity.label for identity in dimensions[0].identities],
                },
                "y": _quantitative_encoding(evidence, rows, "zero"),
                "tooltip": _tooltips(evidence, dimensions, rows),
            }
    elif resolution.view == "histogram":
        bins = payload.get("bins")
        if not isinstance(bins, list):
            raise VisualEvidenceError()
        spec["data"]["values"] = bins
        spec["mark"] = {"type": "bar"}
        spec["encoding"] = {
            "x": {"field": "lower", "type": "quantitative", "title": payload.get("variable")},
            "x2": {"field": "upper"},
            "y": {"field": "count", "type": "quantitative", "title": "Flights"},
            "tooltip": [
                {"field": "lower", "type": "quantitative"},
                {"field": "upper", "type": "quantitative"},
                {"field": "count", "type": "quantitative"},
            ],
        }
    elif evidence.shape == "period_change" and resolution.view in {"bar", "dot"}:
        values = [
            {
                "period": label,
                "value": (
                    payload.get(period, {}).get("value", {}).get("value")
                    if isinstance(payload.get(period), dict)
                    and isinstance(payload[period].get("value"), dict)
                    else None
                ),
            }
            for label, period in (("Baseline", "baseline"), ("Comparison", "comparison"))
        ]
        spec["data"]["values"] = values
        spec["mark"] = (
            {"type": "bar"} if resolution.view == "bar" else {"type": "point", "filled": True}
        )
        spec["encoding"] = {
            "x": {"field": "period", "type": "nominal", "title": "Period"},
            "y": {
                "field": "value",
                "type": "quantitative",
                "title": _measure_label(evidence),
                "scale": {"zero": True},
            },
            "tooltip": [
                {"field": "period", "type": "nominal"},
                {"field": "value", "type": "quantitative"},
            ],
        }
    elif resolution.view in {"scatter", "density"}:
        spec = _relationship_chart(spec, resolution, payload, resolution.view)
    else:
        raise VisualEvidenceError()
    spec["usermeta"] = {
        "visual_evidence_version": evidence.visual_evidence_version,
        "evidence_fingerprint": evidence.evidence_fingerprint,
        "selection_rule_version": evidence.selection_rule_version,
    }
    return spec


def build_browser_chart(resolution: PresentationResolution) -> dict[str, Any] | None:
    """Project nested evidence into scalar columns for Streamlit's Arrow transport."""
    spec = build_chart(resolution)
    if spec is None:
        return None
    evidence = _require_evidence(resolution)
    rows = spec["data"]["values"]
    projected = []
    for row in rows:
        if not isinstance(row, dict):
            raise VisualEvidenceError()
        flat = _flat_chart_row(row)
        identities = row.get("identity")
        if isinstance(identities, list):
            for index, dimension in enumerate(evidence.dimensions):
                if index >= len(identities):
                    raise VisualEvidenceError()
                token = _identity_token(identities[index], dimension.field_id)
                identity = next(
                    (item for item in dimension.identities if item.token == token), None
                )
                if identity is None:
                    raise VisualEvidenceError()
                flat.setdefault(f"visual_category_{index}", identity.label)
        projected.append(flat)
    spec["data"]["values"] = projected
    spec.pop("transform", None)

    def rewrite_fields(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "field" and isinstance(value, str):
                    node[key] = value.replace(".", "__")
                else:
                    rewrite_fields(value)
        elif isinstance(node, list):
            for value in node:
                rewrite_fields(value)

    rewrite_fields(spec)
    return spec


def _flat_chart_row(values: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in values.items():
        name = f"{prefix}__{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flat_chart_row(value, name))
        elif not isinstance(value, list):
            flat[name] = value
    return flat


def _require_evidence(resolution: PresentationResolution) -> VisualEvidence:
    if resolution.evidence is None:
        raise VisualEvidenceError()
    return resolution.evidence


def _shown_rows(resolution: PresentationResolution) -> list[Any]:
    evidence = _require_evidence(resolution)
    payload = evidence.payload.to_dict()
    rows = payload.get("values")
    if not isinstance(rows, list) or not evidence.dimensions or resolution.selection is None:
        return rows if isinstance(rows, list) else []
    selected = [set(resolution.selection.category_ids)]
    if len(evidence.dimensions) > 1:
        selected.append(set(resolution.selection.series_ids))
    return [
        row
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("identity"), list)
        and all(
            index < len(row["identity"])
            and _identity_token(row["identity"][index], dimension.field_id) in selected[index]
            for index, dimension in enumerate(evidence.dimensions)
        )
    ]


def _identity_token(identity: Any, field_id: str) -> str | None:
    if isinstance(identity, str):
        return identity
    if not isinstance(identity, dict):
        return None
    code = identity.get("code")
    status = identity.get("status")
    if (code is not None and not isinstance(code, str)) or status not in {
        "known",
        "missing",
        "unmatched_reference",
        "unknown",
    }:
        return None
    try:
        return canonical_identity(field_id, code, status)
    except VisualEvidenceError:
        return None


def _row_measure(row: Any, measure_id: str | None) -> int | float | None:
    if not isinstance(row, dict) or not measure_id:
        return None
    measures = row.get("measures")
    measure = measures.get(measure_id) if isinstance(measures, dict) else None
    value = measure.get("value") if isinstance(measure, dict) else None
    if type(value) in {int, float}:
        return value
    raw = row.get("value")
    value = raw.get("value") if isinstance(raw, dict) else None
    return value if type(value) in {int, float} else None


def _dimension_transforms(dimensions, rows: list[Any]) -> list[dict[str, Any]]:
    first_row = next((row for row in rows if isinstance(row, dict)), None)
    identities = first_row.get("identity") if first_row else None
    transforms: list[dict[str, Any]] = []
    for index, dimension in enumerate(dimensions):
        if (
            isinstance(identities, list)
            and len(identities) > index
            and isinstance(identities[index], dict)
        ):
            transforms.append(
                {
                    "calculate": f"datum.identity[{index}].label",
                    "as": f"visual_category_{index}",
                }
            )
        else:
            transforms.append(
                {
                    "calculate": f"datum.identity[{index}]",
                    "as": f"visual_identity_{index}",
                }
            )
            transforms.append(
                {
                    "lookup": f"visual_identity_{index}",
                    "from": {
                        "data": {
                            "values": [
                                {"token": identity.token, "label": identity.label}
                                for identity in dimension.identities
                            ]
                        },
                        "key": "token",
                        "fields": ["label"],
                    },
                    "as": [f"visual_category_{index}"],
                }
            )
    return transforms


def _measure_field(evidence: VisualEvidence) -> str:
    if not evidence.measure_ids:
        raise VisualEvidenceError()
    return f"measures.{evidence.measure_ids[0]}.value"


def _measure_label(evidence: VisualEvidence) -> str:
    payload = evidence.payload.to_dict()
    fields = payload.get("fields")
    if isinstance(fields, list):
        field = next(
            (
                item
                for item in fields
                if isinstance(item, dict)
                and evidence.measure_ids
                and item.get("field_id") == evidence.measure_ids[0]
            ),
            None,
        )
        if isinstance(field, dict) and isinstance(field.get("label"), str):
            return field["label"]
    return str(
        evidence.measure_ids[0]
        if evidence.measure_ids
        else evidence.definition.to_dict().get("unit") or "saved measure"
    )


def _measure_unit(evidence: VisualEvidence) -> str | None:
    unit = evidence.definition.to_dict().get("unit")
    return unit if isinstance(unit, str) and unit else None


def _measure_axis_label(evidence: VisualEvidence) -> str:
    unit = _measure_unit(evidence)
    label = _measure_label(evidence)
    return f"{label} ({unit})" if unit else label


def _relationship_pairing(resolution: PresentationResolution) -> dict[str, Any] | None:
    evidence = _require_evidence(resolution)
    payload = evidence.payload.to_dict()
    pairing = payload.get("pairing")
    if isinstance(pairing, dict):
        return pairing
    if evidence.shape != "weather":
        return None
    variables = payload.get("variables")
    if not isinstance(variables, list):
        return None
    return next(
        (
            row["pairing"]
            for row in variables
            if isinstance(row, dict)
            and resolution.selection is not None
            and row.get("origin") == resolution.selection.weather_airport
            and row.get("variable") == resolution.selection.weather_variable
            and isinstance(row.get("pairing"), dict)
        ),
        None,
    )


def _relationship_name(resolution: PresentationResolution, family: str) -> str:
    pairing = _relationship_pairing(resolution)
    if not isinstance(pairing, dict):
        return f"{family} of saved relationship"
    x_field = pairing.get("x_field") or "x"
    y_field = pairing.get("y_field") or "y"
    x_unit = pairing.get("x_unit")
    y_unit = pairing.get("y_unit")
    x_text = f"{x_field} ({x_unit})" if isinstance(x_unit, str) else str(x_field)
    y_text = f"{y_field} ({y_unit})" if isinstance(y_unit, str) else str(y_field)
    return f"{family} of {x_text} and {y_text}"


def _number_format(evidence: VisualEvidence, rows: list[Any]) -> str:
    rounding = evidence.format.to_dict().get("rounding")
    if isinstance(rounding, dict) and type(rounding.get("places")) is int:
        return f",.{rounding['places']}f"
    values = _numeric_values(evidence, rows)
    return ",.2f" if any(type(value) is float for value in values) else ",d"


def _format_display_number(value: int | float, evidence: VisualEvidence) -> str:
    if type(value) is int:
        exact = str(value)
    else:
        exact = str(value)
    rounding = evidence.format.to_dict().get("rounding")
    places = (
        rounding["places"]
        if isinstance(rounding, dict) and type(rounding.get("places")) is int
        else 2
        if type(value) is float
        else None
    )
    if places is None:
        return f"{value:,}"
    decimal_value = Decimal(exact)
    with localcontext() as context:
        context.prec = max(
            40,
            len(decimal_value.as_tuple().digits) + max(decimal_value.adjusted(), 0) + places + 8,
        )
        rounded = decimal_value.quantize(
            Decimal(1).scaleb(-places),
            rounding=ROUND_HALF_UP,
        )
    return f"{rounded:,.{places}f}"


def format_visual_number(
    value: Any,
    evidence: VisualEvidence,
    unit: str | None = None,
) -> str:
    if not isinstance(value, dict):
        return "unavailable"
    number = value.get("value")
    if type(number) in {int, float}:
        formatted = _format_display_number(number, evidence)
        if unit:
            separator = "" if unit == "%" else " "
            return f"{formatted}{separator}{unit}"
        return formatted
    reason = value.get("absence")
    return f"unavailable ({reason})" if isinstance(reason, str) else "unavailable"


def _numeric_values(evidence: VisualEvidence, rows: list[Any]) -> list[int | float]:
    field = evidence.measure_ids[0]
    values: list[int | float] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        measures = row.get("measures")
        measure = measures.get(field) if isinstance(measures, dict) else None
        value = measure.get("value") if isinstance(measure, dict) else None
        if type(value) in {int, float}:
            values.append(value)
    return values


def _quantitative_encoding(
    evidence: VisualEvidence,
    rows: list[Any],
    zero: str | None = None,
) -> dict[str, Any]:
    number_format = _number_format(evidence, rows)
    encoding: dict[str, Any] = {
        "field": _measure_field(evidence),
        "type": "quantitative",
        "title": _measure_axis_label(evidence),
        "axis": {"format": number_format},
    }
    values = _numeric_values(evidence, rows)
    if zero == "zero" and values:
        lower = min(0, min(values))
        upper = max(0, max(values))
        if lower == upper == 0:
            upper = 1
        encoding["scale"] = {
            "zero": True,
            "domain": [lower, upper],
        }
    return encoding


def _tooltips(
    evidence: VisualEvidence,
    dimensions: tuple[Any, ...],
    rows: list[Any],
) -> list[dict[str, Any]]:
    tooltips = [
        {"field": f"visual_category_{index}", "type": "nominal", "title": dimension.label}
        for index, dimension in enumerate(dimensions)
    ]
    tooltips.append(
        {
            "field": _measure_field(evidence),
            "type": "quantitative",
            "title": _measure_axis_label(evidence),
            "format": _number_format(evidence, rows),
        }
    )
    tooltips.append(
        {
            "field": f"measures.{evidence.measure_ids[0]}.absence",
            "type": "nominal",
            "title": "Unavailable reason",
        }
    )
    return tooltips


def _period_range(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    start = value.get("start")
    end = value.get("end")
    if start is None and end is None:
        return None
    return f"{start or 'unbounded'} through {end or 'unbounded'}"


def _population_counts(rows: list[Any]) -> str | None:
    sample = [row.get("sample_size") for row in rows if isinstance(row, dict)]
    scoped = [row.get("scoped_count") for row in rows if isinstance(row, dict)]
    missing = [row.get("missing_count") for row in rows if isinstance(row, dict)]
    if not sample or any(type(value) is not int for value in sample):
        return None
    details = [f"Observed records represented: {sum(sample):,}"]
    if scoped and all(type(value) is int for value in scoped):
        details.append(f"scoped records: {sum(scoped):,}")
    if missing and all(type(value) is int for value in missing):
        details.append(f"missing measure records: {sum(missing):,}")
    return "; ".join(details) + "."


def _unavailable_reasons(rows: list[Any], evidence: VisualEvidence) -> list[str]:
    reasons: set[str] = set()
    measure_id = evidence.measure_ids[0] if evidence.measure_ids else None
    for row in rows:
        if not isinstance(row, dict):
            continue
        measures = row.get("measures")
        measure = measures.get(measure_id) if isinstance(measures, dict) and measure_id else None
        reason = measure.get("absence") if isinstance(measure, dict) else None
        if isinstance(reason, str):
            reasons.add(reason)
    return sorted(reasons)


def _temporal_rows(evidence: VisualEvidence, rows: list[Any]) -> list[dict[str, Any]]:
    dimensions = evidence.dimensions
    if not dimensions or len(dimensions) > 2 or not evidence.measure_ids:
        raise VisualEvidenceError()
    normalized = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("identity"), list):
            raise VisualEvidenceError()
        if len(row["identity"]) != len(dimensions):
            raise VisualEvidenceError()
        normalized.append(
            row
            | {
                "identity": [
                    _identity_token(identity, dimension.field_id)
                    for identity, dimension in zip(row["identity"], dimensions, strict=True)
                ]
            }
        )
    rows = normalized
    first_dimension = dimensions[0]
    first_by_token = {identity.token: identity for identity in first_dimension.identities}
    second_dimension = dimensions[1] if len(dimensions) == 2 else None
    second_by_token = (
        {identity.token: identity for identity in second_dimension.identities}
        if second_dimension
        else {}
    )
    records: dict[tuple[str, date], dict[str, Any]] = {}
    encountered_series = {
        row["identity"][1]
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("identity"), list)
        and len(row["identity"]) > 1
        and isinstance(row["identity"][1], str)
    }
    series_categories = (
        [
            (identity.token, identity)
            for identity in second_dimension.identities
            if identity.token in encountered_series
        ]
        if second_dimension
        else [("__single_series__", None)]
    )
    for source in rows:
        if not isinstance(source, dict):
            raise VisualEvidenceError()
        identities = source.get("identity")
        if not isinstance(identities, list) or not identities or not isinstance(identities[0], str):
            raise VisualEvidenceError()
        temporal = first_by_token.get(identities[0])
        if temporal is None:
            raise VisualEvidenceError()
        bucket = _temporal_date(first_dimension.field_id, temporal.code)
        series_token = "__single_series__"
        series_identity = None
        if second_dimension:
            if len(identities) < 2 or not isinstance(identities[1], str):
                raise VisualEvidenceError()
            series_token = identities[1]
            series_identity = second_by_token.get(series_token)
            if series_identity is None:
                raise VisualEvidenceError()
        record = dict(source)
        record["visual_time"] = bucket.isoformat()
        record["visual_category_0"] = _bucket_label(first_dimension.field_id, bucket)
        if series_identity is not None:
            record["visual_category_1"] = series_identity.label
        record["visual_period_status"] = _period_status(
            evidence,
            bucket,
            series_identity,
        )
        measure = source.get("measures", {}).get(evidence.measure_ids[0], {})
        reason = measure.get("absence") if isinstance(measure, dict) else None
        record["visual_gap_reason"] = reason
        records[(series_token, bucket)] = record

    coverage = evidence.coverage.to_dict()
    verified = coverage.get("status") == "verified_intervals"
    all_intervals = coverage.get("intervals")
    if verified and isinstance(all_intervals, list):
        for series_token, series_identity in series_categories:
            intervals = _coverage_intervals(evidence, series_identity)
            for bucket in _expected_buckets(first_dimension.field_id, intervals):
                key = (series_token, bucket)
                if key not in records:
                    records[key] = _gap_record(
                        evidence,
                        first_dimension,
                        second_dimension,
                        bucket,
                        series_identity,
                        "verified_coverage_gap",
                    )
    else:
        known: dict[str, list[date]] = {}
        for series_token, bucket in records:
            known.setdefault(series_token, []).append(bucket)
        for series_token, buckets in known.items():
            ordered = sorted(set(buckets))
            for previous, current in zip(ordered, ordered[1:], strict=False):
                missing = _next_bucket(first_dimension.field_id, previous)
                if missing < current and (series_token, missing) not in records:
                    identity = next(
                        (item for token, item in series_categories if token == series_token),
                        None,
                    )
                    records[(series_token, missing)] = _gap_record(
                        evidence,
                        first_dimension,
                        second_dimension,
                        missing,
                        identity,
                        "coverage_unknown_missing_bucket",
                    )

    selected_series = {token: index for index, (token, _) in enumerate(series_categories)}
    ordered_records = sorted(
        records.items(),
        key=lambda entry: (entry[0][1], selected_series.get(entry[0][0], 0)),
    )
    segment_by_series: dict[str, int] = {}
    output: list[dict[str, Any]] = []
    previous_by_series: dict[str, date] = {}
    for (series_token, bucket), record in ordered_records:
        segment = segment_by_series.get(series_token, 0)
        previous = previous_by_series.get(series_token)
        if previous is not None and _next_bucket(first_dimension.field_id, previous) != bucket:
            segment += 1
        value = _row_measure(record, evidence.measure_ids[0])
        record["visual_segment"] = segment
        if value is None:
            segment += 1
        segment_by_series[series_token] = segment
        previous_by_series[series_token] = bucket
        output.append(record)
    return output


def _temporal_date(field_id: str, code: str | None) -> date:
    if not isinstance(code, str):
        raise VisualEvidenceError()
    try:
        if field_id == "flight_month":
            return date.fromisoformat(f"{code}-01")
        bucket = date.fromisoformat(code)
    except ValueError as exc:
        raise VisualEvidenceError() from exc
    if bucket.isoformat() != code:
        raise VisualEvidenceError()
    if field_id not in {"flight_date", "flight_week"}:
        raise VisualEvidenceError()
    if field_id == "flight_week" and bucket.weekday() != 0:
        raise VisualEvidenceError()
    return bucket


def _bucket_label(field_id: str, bucket: date) -> str:
    return bucket.strftime("%Y-%m") if field_id == "flight_month" else bucket.isoformat()


def _bucket_span(field_id: str, bucket: date) -> tuple[date, date]:
    if field_id == "flight_date":
        return bucket, bucket
    if field_id == "flight_week":
        return bucket, bucket + timedelta(days=6)
    if field_id == "flight_month":
        next_month = date(bucket.year + (bucket.month == 12), bucket.month % 12 + 1, 1)
        return bucket, next_month - timedelta(days=1)
    raise VisualEvidenceError()


def _next_bucket(field_id: str, bucket: date) -> date:
    if field_id == "flight_date":
        return bucket + timedelta(days=1)
    if field_id == "flight_week":
        return bucket + timedelta(days=7)
    if field_id == "flight_month":
        return date(bucket.year + (bucket.month == 12), bucket.month % 12 + 1, 1)
    raise VisualEvidenceError()


def _coverage_intervals(
    evidence: VisualEvidence,
    series_identity: Any,
) -> list[tuple[date, date]]:
    series_dimension = evidence.dimensions[1] if len(evidence.dimensions) > 1 else None
    series_is_origin = (
        series_dimension is not None
        and series_dimension.field_id == "origin"
        and series_identity is not None
    )
    if series_is_origin:
        if not isinstance(series_identity.code, str):
            return []
        return _coverage_intervals_for_origin(evidence, series_identity.code)
    return _coverage_intervals_for_origin(evidence, None)


def _coverage_intervals_for_origin(
    evidence: VisualEvidence,
    origin: str | None,
) -> list[tuple[date, date]]:
    raw = evidence.coverage.to_dict().get("intervals")
    if not isinstance(raw, list):
        return []
    intervals: list[tuple[date, date]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if origin is not None and item.get("origin") != origin:
            continue
        start = item.get("start")
        end = item.get("end")
        if not isinstance(start, str) or not isinstance(end, str):
            raise VisualEvidenceError()
        try:
            intervals.append((date.fromisoformat(start), date.fromisoformat(end)))
        except ValueError as exc:
            raise VisualEvidenceError() from exc
    return intervals


def _expected_buckets(
    field_id: str,
    intervals: list[tuple[date, date]],
) -> list[date]:
    expected: set[date] = set()
    for start, end in intervals:
        if field_id == "flight_date":
            cursor = start
        elif field_id == "flight_week":
            cursor = start - timedelta(days=start.weekday())
        elif field_id == "flight_month":
            cursor = date(start.year, start.month, 1)
        else:
            raise VisualEvidenceError()
        while cursor <= end:
            expected.add(cursor)
            cursor = _next_bucket(field_id, cursor)
    return sorted(expected)


def _period_status(
    evidence: VisualEvidence,
    bucket: date,
    series_identity: Any,
) -> str:
    field_id = evidence.dimensions[0].field_id
    bucket_start, bucket_end = _bucket_span(field_id, bucket)
    partial = False
    requested = evidence.scope.to_dict().get("requested_period")
    if isinstance(requested, dict):
        requested_start = requested.get("start")
        requested_end = requested.get("end")
        if isinstance(requested_start, str):
            partial |= date.fromisoformat(requested_start) > bucket_start
        if isinstance(requested_end, str):
            partial |= date.fromisoformat(requested_end) < bucket_end
    coverage = evidence.coverage.to_dict()
    if coverage.get("status") != "verified_intervals":
        return "partial" if partial else "unknown"
    raw_intervals = coverage.get("intervals")
    if not isinstance(raw_intervals, list):
        return "unknown"
    series_dimension = evidence.dimensions[1] if len(evidence.dimensions) > 1 else None
    if (
        series_dimension is not None
        and series_dimension.field_id == "origin"
        and series_identity is not None
    ):
        if not isinstance(series_identity.code, str):
            return "partial" if partial else "unknown"
        origins = [series_identity.code]
    else:
        scoped_origins = evidence.scope.to_dict().get("origins")
        if isinstance(scoped_origins, list):
            origins = [origin for origin in scoped_origins if isinstance(origin, str)]
        else:
            origins = sorted(
                {
                    item["origin"]
                    for item in raw_intervals
                    if isinstance(item, dict) and isinstance(item.get("origin"), str)
                }
            )
    if not origins:
        return "partial" if partial else "unknown"
    any_overlap = False
    all_full = True
    for origin in origins:
        origin_intervals = _coverage_intervals_for_origin(evidence, origin)
        any_overlap |= any(
            start <= bucket_end and end >= bucket_start for start, end in origin_intervals
        )
        all_full &= _covers_bucket(origin_intervals, bucket_start, bucket_end)
    if not any_overlap:
        return "partial" if partial else "unknown"
    if not all_full:
        partial = True
    return "partial" if partial else "full"


def _covers_bucket(
    intervals: list[tuple[date, date]],
    bucket_start: date,
    bucket_end: date,
) -> bool:
    covered_until: date | None = None
    for start, end in sorted(intervals):
        if covered_until is None:
            if start <= bucket_start:
                covered_until = end
        elif start <= covered_until + timedelta(days=1):
            covered_until = max(covered_until, end)
        if covered_until is not None and covered_until >= bucket_end:
            return True
    return False


def _gap_record(
    evidence: VisualEvidence,
    first_dimension: Any,
    second_dimension: Any,
    bucket: date,
    series_identity: Any,
    reason: str,
) -> dict[str, Any]:
    time_code = _bucket_label(first_dimension.field_id, bucket)
    identity = [canonical_identity(first_dimension.field_id, time_code, "known")]
    if second_dimension is not None and series_identity is not None:
        identity.append(series_identity.token)
    row: dict[str, Any] = {
        "identity": identity,
        "measures": {evidence.measure_ids[0]: {"value": None, "absence": reason}},
        "sample_size": 0,
        "scoped_count": 0,
        "missing_count": 0,
        "tied": False,
        "visual_time": bucket.isoformat(),
        "visual_category_0": _bucket_label(first_dimension.field_id, bucket),
        "visual_period_status": _period_status(
            evidence,
            bucket,
            series_identity,
        ),
        "visual_gap_reason": reason,
    }
    if series_identity is not None:
        row["visual_category_1"] = series_identity.label
    return row


def _time_chart_layers(
    evidence: VisualEvidence,
    rows: list[Any],
    dimensions: tuple[Any, ...],
) -> list[dict[str, Any]]:
    x_format = {
        "flight_date": "%b %d, %Y",
        "flight_week": "Week of %b %d, %Y",
        "flight_month": "%b %Y",
    }[dimensions[0].field_id]
    x = {
        "field": "visual_time",
        "type": "temporal",
        "title": f"{dimensions[0].label} ({evidence.grain})",
        "axis": {"format": x_format},
    }
    quantitative = _quantitative_encoding(evidence, rows)
    color = (
        {
            "field": "visual_category_1",
            "type": "nominal",
            "title": dimensions[1].label,
            "scale": {
                "domain": [identity.label for identity in dimensions[1].identities],
            },
        }
        if len(dimensions) == 2
        else None
    )
    detail = [{"field": "visual_segment", "type": "nominal"}]
    if color:
        detail.insert(
            0,
            {"field": "visual_category_1", "type": "nominal"},
        )
    line_encoding: dict[str, Any] = {
        "x": x,
        "y": quantitative,
        "detail": detail,
        "tooltip": _time_tooltips(evidence, dimensions, rows),
    }
    if color:
        line_encoding["color"] = color
    point_encoding: dict[str, Any] = {
        "x": x,
        "y": quantitative,
        "shape": {
            "field": "visual_period_status",
            "type": "nominal",
            "title": "Bucket coverage",
            "scale": {
                "domain": ["full", "partial", "unknown"],
                "range": ["circle", "triangle-up", "square"],
            },
        },
        "tooltip": _time_tooltips(evidence, dimensions, rows),
    }
    if color:
        point_encoding["color"] = color
    return [
        {"mark": {"type": "line"}, "encoding": line_encoding},
        {"mark": {"type": "point", "filled": True, "size": 70}, "encoding": point_encoding},
    ]


def _time_tooltips(
    evidence: VisualEvidence,
    dimensions: tuple[Any, ...],
    rows: list[Any],
) -> list[dict[str, Any]]:
    tooltips = [
        {
            "field": "visual_time",
            "type": "temporal",
            "title": dimensions[0].label,
        }
    ]
    if len(dimensions) == 2:
        tooltips.append(
            {
                "field": "visual_category_1",
                "type": "nominal",
                "title": dimensions[1].label,
            }
        )
    tooltips.extend(
        [
            {
                "field": _measure_field(evidence),
                "type": "quantitative",
                "title": _measure_axis_label(evidence),
                "format": _number_format(evidence, rows),
            },
            {"field": "visual_gap_reason", "type": "nominal", "title": "Unavailable reason"},
            {"field": "visual_period_status", "type": "nominal", "title": "Bucket coverage"},
        ]
    )
    return tooltips


def _relationship_chart(
    spec: dict[str, Any],
    resolution: PresentationResolution,
    payload: dict[str, Any],
    view: str,
) -> dict[str, Any]:
    evidence = _require_evidence(resolution)
    pairing = payload.get("pairing")
    if evidence.shape == "weather":
        variables = payload.get("variables")
        if resolution.selection is None:
            raise VisualEvidenceError()
        airport = resolution.selection.weather_airport
        variable = resolution.selection.weather_variable
        if not isinstance(variables, list):
            raise VisualEvidenceError()
        match = next(
            (
                row
                for row in variables
                if isinstance(row, dict)
                and row.get("origin") == airport
                and row.get("variable") == variable
            ),
            None,
        )
        pairing = match.get("pairing") if isinstance(match, dict) else None
    if not isinstance(pairing, dict):
        raise VisualEvidenceError()
    pairs = pairing.get("pairs")
    if view == "scatter":
        if not isinstance(pairs, list):
            raise VisualEvidenceError()
        spec["data"]["values"] = pairs
        spec["mark"] = {"type": "point", "filled": True, "opacity": 0.65}
        spec["encoding"] = {
            "x": {"field": "x", "type": "quantitative", "title": pairing.get("x_unit")},
            "y": {"field": "y", "type": "quantitative", "title": pairing.get("y_unit")},
            "tooltip": [
                {"field": "x", "type": "quantitative", "title": pairing.get("x_field")},
                {"field": "y", "type": "quantitative", "title": pairing.get("y_field")},
            ],
        }
        return spec
    density = pairing.get("density")
    if not isinstance(density, dict):
        raise VisualEvidenceError()
    x_edges = density.get("x_edges")
    y_edges = density.get("y_edges")
    cells = density.get("cells")
    if (
        not isinstance(x_edges, list)
        or not isinstance(y_edges, list)
        or not isinstance(cells, list)
    ):
        raise VisualEvidenceError()
    spec["data"]["values"] = [
        {
            "x0": x_edges[cell["x"]],
            "x1": x_edges[cell["x"] + 1],
            "y0": y_edges[cell["y"]],
            "y1": y_edges[cell["y"] + 1],
            "count": cell["count"],
        }
        for cell in cells
    ]
    spec["mark"] = {"type": "rect", "stroke": "#FFFFFF"}
    spec["encoding"] = {
        "x": {"field": "x0", "type": "quantitative", "title": pairing.get("x_unit")},
        "x2": {"field": "x1"},
        "y": {"field": "y0", "type": "quantitative", "title": pairing.get("y_unit")},
        "y2": {"field": "y1"},
        "color": {
            "field": "count",
            "type": "quantitative",
            "title": "Origin-hours" if evidence.shape == "weather" else "Flights",
        },
        "tooltip": [{"field": "count", "type": "quantitative"}],
    }
    return spec
