import json

import pytest

from airport_analytics.errors import PresentationPreferenceError
from airport_analytics.models import SectionPresentationPreference
from airport_analytics.reports.visual_evidence import (
    FrozenDocument,
    VisualCategory,
    VisualDimension,
    VisualEvidence,
    VisualSelection,
    canonical_identity,
    resolve_presentation,
)


def dimension(field_id, codes, role="category"):
    return VisualDimension(
        field_id=field_id,
        label=field_id.replace("_", " ").title(),
        role=role,
        identities=tuple(
            VisualCategory(
                token=canonical_identity(field_id, code, "known"),
                code=code,
                label=code,
                reference_status="known",
            )
            for code in codes
        ),
    )


def visual(shape, dimensions=(), *, values=None, available=None):
    groups = (
        len(values)
        if values is not None
        else (
            len(dimensions[0].identities) * len(dimensions[1].identities)
            if len(dimensions) > 1
            else len(dimensions[0].identities)
            if dimensions
            else 1
        )
    )
    return VisualEvidence(
        report_id="synthetic",
        section_id="section",
        analytical_revision=1,
        snapshot_id="a" * 64,
        context_id="b" * 64,
        source_evidence_version=2,
        evidence_fingerprint="c" * 64,
        shape=shape,
        definition=FrozenDocument.from_dict(
            {"unit": "flights", "weighting": "source_record", "additivity": "additive"}
        ),
        measure_ids=("flight_count",),
        population="flights",
        grain="category" if dimensions else "scalar",
        dimensions=tuple(dimensions),
        scope=FrozenDocument.from_dict(
            {"filters": [], "requested_period": None, "observed_period": None}
        ),
        coverage=FrozenDocument.from_dict(
            {"status": "unknown", "intervals": [], "reason": "Coverage unknown."}
        ),
        selection=VisualSelection(
            shown_groups=groups,
            returned_groups=groups,
            available_groups=available if available is not None else groups,
        ),
        missingness=FrozenDocument.from_dict({}),
        limitations=(),
        format=FrozenDocument.from_dict({"locale": "en", "computed_places": 2, "rounding": None}),
        payload=FrozenDocument.from_dict(
            {"kind": shape, "values": values if values is not None else []}
        ),
    )


@pytest.mark.parametrize("shape", ["relationship", "weather"])
def test_density_default_remains_in_the_offered_compatible_views(shape):
    from airport_analytics.reports.charts import build_browser_chart

    item = visual(shape)
    pairing = {
        "pair_count": 1000,
        "scoped_count": 1000,
        "x_missing_only": 0,
        "y_missing_only": 0,
        "both_missing": 0,
        "x_field": "temp",
        "y_field": "departure_delay",
        "x_unit": "recorded values",
        "y_unit": "minutes",
        "density": {
            "x_edges": [0, 1],
            "y_edges": [0, 1],
            "cells": [{"x": 0, "y": 0, "count": 1000}],
        },
    }
    payload = (
        {"pairing": pairing}
        if shape == "relationship"
        else {"variables": [{"variable": "temp", "origin": None, "pairing": pairing}]}
    )
    item = item.model_copy(update={"payload": FrozenDocument.from_dict(payload)})
    resolution = resolve_presentation(item)
    assert resolution.view == "density"
    assert resolution.compatible_views == ("density", "table")
    chart = build_browser_chart(resolution)
    assert chart["encoding"]["color"]["title"] == (
        "Origin-hours" if shape == "weather" else "Flights"
    )
    assert chart["data"]["values"] == [{"x0": 0, "x1": 1, "y0": 0, "y1": 1, "count": 1000}]


def category_values(codes, values=None):
    numeric = values or [index + 1 for index in range(len(codes))]
    return [
        {
            "identity": [canonical_identity("origin", code, "known")],
            "measures": {"flight_count": {"value": value, "absence": None}},
            "sample_size": value,
            "tied": False,
        }
        for code, value in zip(codes, numeric, strict=True)
    ]


@pytest.mark.parametrize(
    "shape,view",
    [
        ("scalar", "summary"),
        ("listing", "table"),
        ("time", "line"),
        ("period_change", "bar"),
        ("distribution", "histogram"),
        ("relationship", "scatter"),
        ("weather", "scatter"),
    ],
)
def test_shapes_have_deterministic_default_views(shape, view):
    result = resolve_presentation(visual(shape))
    assert result.state == "ready"
    assert result.view == view
    assert result.evidence.shape == shape
    assert view in result.compatible_views


def test_a_one_row_grouped_category_stays_a_category_not_a_scalar():
    item = visual(
        "category",
        (dimension("origin", ["JFK"]),),
        values=category_values(["JFK"]),
    )
    result = resolve_presentation(item)
    assert result.evidence.shape == "category"
    assert result.view == "bar"
    assert result.selection.shown_groups == 1


def test_unranked_categories_require_explicit_selection_above_twenty():
    codes = [f"A{index:02}" for index in range(21)]
    item = visual(
        "category",
        (dimension("origin", codes),),
        values=category_values(codes),
    )
    result = resolve_presentation(item)
    assert result.state == "selection_required"
    assert result.view is None
    assert "twenty" in result.reason.lower()
    assert "table" in result.compatible_views


def test_unranked_categories_can_select_a_full_table_without_auto_pruning():
    codes = [f"A{index:02}" for index in range(21)]
    item = visual(
        "category",
        (dimension("origin", codes),),
        values=category_values(codes),
    )
    result = resolve_presentation(item, SectionPresentationPreference(chart_family="table"))
    assert result.state == "table_selected"
    assert result.view == "table"
    assert result.selection.shown_groups == 21


def test_explicit_category_selection_is_membership_checked_and_canonical():
    codes = [f"A{index:02}" for index in range(21)]
    item = visual(
        "category",
        (dimension("origin", codes),),
        values=category_values(codes),
    )
    requested = [
        canonical_identity("origin", "A20", "known"),
        canonical_identity("origin", "A02", "known"),
    ]
    result = resolve_presentation(
        item,
        SectionPresentationPreference(category_ids=requested),
    )
    assert result.selection.category_ids == tuple(reversed(requested))
    with pytest.raises(PresentationPreferenceError):
        resolve_presentation(
            item,
            SectionPresentationPreference(category_ids=[requested[0], requested[0]]),
        )


def test_rankings_take_first_twenty_only_in_saved_order_and_disclose_tied_cutoff():
    codes = [f"A{index:02}" for index in range(21)]
    rows = category_values(codes, [100 - index for index in range(21)])
    rows[20]["measures"]["flight_count"]["value"] = rows[19]["measures"]["flight_count"]["value"]
    rows[20]["sample_size"] = rows[19]["sample_size"]
    result = resolve_presentation(
        visual("ranking", (dimension("origin", codes),), values=rows, available=35)
    )
    assert result.state == "ready"
    assert result.view == "bar"
    assert result.selection.category_ids == tuple(
        canonical_identity("origin", code, "known") for code in codes[:20]
    )
    assert result.selection.shown_groups == 20
    assert result.selection.returned_groups == 21
    assert result.selection.available_groups == 35
    assert result.selection.visual_omitted_groups == 1
    assert result.selection.analytical_omitted_groups == 14
    assert result.selection.visual_cutoff_tie


def test_ranking_first_twenty_has_no_false_tie_from_rounded_values():
    codes = [f"A{index:02}" for index in range(21)]
    rows = category_values(codes, [2.0 - index / 10 for index in range(21)])
    result = resolve_presentation(visual("ranking", (dimension("origin", codes),), values=rows))
    assert result.selection.visual_cutoff_tie is False
    assert result.selection.shown_groups == 20


def test_ranked_year_month_labels_remain_ranked_categories():
    codes = ["2013-02", "2013-01"]
    rows = category_values(codes, [9, 4])
    item = visual(
        "ranking",
        (dimension("flight_month", codes, role="time"),),
        values=rows,
    )
    result = resolve_presentation(item)
    assert result.view == "bar"
    assert result.selection.category_ids == tuple(
        canonical_identity("flight_month", code, "known") for code in codes
    )


@pytest.mark.parametrize(
    "series,expected",
    [
        (8, ("ready", "line")),
        (9, ("ready", "small_multiples")),
        (20, ("ready", "small_multiples")),
        (21, ("selection_required", None)),
    ],
)
def test_time_series_default_thresholds(series, expected):
    primary_codes = ["2013-01", "2013-02"]
    series_codes = [f"A{index:02}" for index in range(series)]
    item = visual(
        "time_series",
        (
            dimension("flight_month", primary_codes, role="time"),
            dimension("origin", series_codes),
        ),
    )
    result = resolve_presentation(item)
    assert (result.state, result.view) == expected
    if series <= 20:
        assert result.selection.shown_series == series
        assert result.selection.available_series == series


@pytest.mark.parametrize(
    "primary,series,view",
    [(20, 8, "grouped_bar"), (20, 9, "heatmap"), (21, 8, "heatmap")],
)
def test_two_category_view_switch_uses_both_inclusive_grouped_bar_limits(primary, series, view):
    item = visual(
        "two_category",
        (
            dimension("origin", [f"P{i}" for i in range(primary)]),
            dimension("carrier", [f"S{i}" for i in range(series)]),
        ),
    )
    result = resolve_presentation(item)
    assert result.state == "ready"
    assert result.view == view
    assert result.selection.returned_groups == primary * series


@pytest.mark.parametrize(
    "value,expected_state",
    [(None, "no_plottable_data"), (0, "ready"), (-2, "ready"), (1, "ready")],
)
def test_numeric_eligibility_distinguishes_null_zero_negative_and_positive(value, expected_state):
    item = visual(
        "scalar",
        values=[
            {"value": {"value": value, "absence": "no_known_values" if value is None else None}}
        ],
    )
    result = resolve_presentation(item)
    assert result.state == expected_state
    if value is not None:
        assert result.view == "summary"
    else:
        assert "unavailable" in result.reason.lower()


def test_scalar_selection_does_not_convert_a_single_group_to_a_metric():
    item = visual(
        "category",
        (dimension("origin", ["JFK"]),),
        values=category_values(["JFK"]),
    )
    result = resolve_presentation(item)
    assert result.evidence.shape == "category"
    assert json.loads(result.evidence.payload.canonical_json)["values"][0]["identity"]


def test_month_of_year_is_an_ordered_category_and_not_a_calendar_time_axis():
    item = visual(
        "category",
        (dimension("month_of_year", ["01", "02", "12"], role="ordered_category"),),
        values=category_values(["01", "02", "12"]),
    )
    result = resolve_presentation(item)
    assert result.evidence.dimensions[0].role == "ordered_category"
    assert [item.code for item in result.evidence.dimensions[0].identities] == ["01", "02", "12"]


def test_weekday_is_an_ordered_category_and_preserves_saved_week_order():
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    item = visual(
        "category",
        (dimension("weekday", weekdays, role="ordered_category"),),
        values=category_values(weekdays),
    )
    result = resolve_presentation(item)
    assert result.evidence.dimensions[0].role == "ordered_category"
    assert [identity.label for identity in result.evidence.dimensions[0].identities] == weekdays
