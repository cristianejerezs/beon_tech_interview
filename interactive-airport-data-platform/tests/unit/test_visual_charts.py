import json
from importlib import import_module

import pytest

from airport_analytics.models import SectionPresentationPreference
from airport_analytics.reports.charts import (
    build_browser_chart,
    build_chart,
    describe_visual,
    format_visual_number,
)
from airport_analytics.reports.visual_evidence import canonical_identity, resolve_presentation
from tests.unit.test_visual_defaults import category_values, dimension, visual

vlc = import_module("vl_convert")


@pytest.mark.parametrize("object_identities", [False, True])
def test_browser_chart_projects_scalar_columns_without_changing_saved_values(object_identities):
    import pyarrow as pa

    rows = category_values(["JFK", "LGA"], [12, 4])
    if object_identities:
        for row, code in zip(rows, ["JFK", "LGA"], strict=True):
            row["identity"] = [
                {"field_id": "origin", "code": code, "label": code, "status": "known"}
            ]
    item = visual("category", (dimension("origin", ["JFK", "LGA"]),), values=rows)
    before = item.model_dump_json()
    spec = build_browser_chart(resolve_presentation(item))
    assert item.model_dump_json() == before
    assert "transform" not in spec
    assert [row["visual_category_0"] for row in spec["data"]["values"]] == ["JFK", "LGA"]
    assert [row["measures__flight_count__value"] for row in spec["data"]["values"]] == [12, 4]
    assert all(
        not isinstance(value, (list, dict))
        for row in spec["data"]["values"]
        for value in row.values()
    )
    assert pa.Table.from_pylist(spec["data"]["values"]).to_pylist() == spec["data"]["values"]
    assert "<svg" in vlc.vegalite_to_svg(spec)


def test_temporal_chart_accepts_saved_object_identities():
    item = temporal_evidence("flight_month", ["2013-01", "2013-02"], [12, 4])
    payload = item.payload.to_dict()
    for row, month in zip(payload["values"], ["2013-01", "2013-02"], strict=True):
        row["identity"] = [
            {"field_id": "flight_month", "code": month, "label": month, "status": "known"}
        ]
    item = item.model_copy(update={"payload": type(item.payload).from_dict(payload)})
    spec = build_browser_chart(resolve_presentation(item))
    assert [row["measures__flight_count__value"] for row in spec["data"]["values"]] == [12, 4]
    assert "<svg" in vlc.vegalite_to_svg(spec)


def temporal_values(field_id, codes, values, series_id=None):
    rows = []
    for code, value in zip(codes, values, strict=True):
        identity = [canonical_identity(field_id, code, "known")]
        if series_id is not None:
            identity.append(series_id)
        rows.append(
            {
                "identity": identity,
                "measures": {
                    "flight_count": {
                        "value": value,
                        "absence": "no_known_values" if value is None else None,
                    }
                },
                "sample_size": int(value is not None),
                "scoped_count": 1,
                "missing_count": int(value is None),
                "tied": False,
            }
        )
    return rows


def temporal_evidence(
    field_id,
    codes,
    values,
    *,
    series_codes=None,
    coverage=None,
    requested_period=None,
    rounding=None,
):
    dimensions = [dimension(field_id, codes, role="time")]
    series_id = None
    if series_codes is not None:
        dimensions.append(dimension("origin", series_codes))
        series_id = canonical_identity("origin", series_codes[0], "known")
    item = visual(
        "time" if series_codes is None else "time_series",
        tuple(dimensions),
        values=temporal_values(field_id, codes, values, series_id),
    )
    return item.model_copy(
        update={
            "scope": type(item.scope).from_dict(
                {
                    "filters": [],
                    "origins": ["JFK"],
                    "requested_period": requested_period,
                    "observed_period": None,
                }
            ),
            "coverage": type(item.coverage).from_dict(
                coverage
                or {
                    "status": "unknown",
                    "intervals": [],
                    "reason": "Exact verified bucket coverage was not saved.",
                }
            ),
            "format": type(item.format).from_dict(
                {
                    "locale": "en",
                    "computed_places": 2,
                    "rounding": rounding,
                }
            ),
        }
    )


def test_chart_uses_exact_embedded_rows_and_no_remote_data_or_reaggregation():
    rows = category_values(["JFK", "LGA"], [12, 0])
    resolution = resolve_presentation(
        visual("category", (dimension("origin", ["JFK", "LGA"]),), values=rows)
    )
    spec = build_chart(resolution)
    serialized = json.dumps(spec, ensure_ascii=False)
    assert spec["data"]["values"] == rows
    assert "url" not in spec["data"]
    assert "aggregate" not in serialized
    assert "bin" not in serialized
    assert spec["encoding"]["y"]["scale"]["zero"] is True
    assert spec["encoding"]["y"]["scale"]["domain"][0] <= 0
    assert "Origin" in describe_visual(resolution).name
    assert "<svg" in vlc.vegalite_to_svg(spec)


def test_chart_description_is_limited_to_shown_scope_and_has_non_color_cues():
    rows = category_values(["JFK", "LGA"], [12, -3])
    resolution = resolve_presentation(
        visual("category", (dimension("origin", ["JFK", "LGA"]),), values=rows)
    )
    spec = build_chart(resolution)
    description = describe_visual(resolution)
    assert "shown" in description.explanation.lower()
    assert "available" in description.explanation.lower()
    assert spec["mark"]["type"] == "bar"
    assert spec["encoding"]["y"]["scale"]["zero"] is True
    assert "color" not in spec["encoding"]


def test_all_zero_categories_are_labelled_as_observed_zeroes():
    rows = category_values(["JFK", "LGA"], [0, 0])
    resolution = resolve_presentation(
        visual("category", (dimension("origin", ["JFK", "LGA"]),), values=rows)
    )
    description = describe_visual(resolution)
    assert "All displayed values are zero" in description.explanation
    spec = build_chart(resolution)
    assert spec["encoding"]["y"]["scale"]["domain"] == [0, 1]
    assert "<svg" in vlc.vegalite_to_svg(spec)


def test_rendering_one_group_does_not_create_a_summary_card():
    rows = category_values(["JFK"], [1])
    resolution = resolve_presentation(
        visual("category", (dimension("origin", ["JFK"]),), values=rows)
    )
    assert resolution.view == "bar"
    assert build_chart(resolution)["mark"]["type"] == "bar"


def test_explicit_chart_subset_contains_only_selected_saved_rows():
    rows = category_values(["JFK", "LGA"], [12, 4])
    evidence = visual(
        "category",
        (dimension("origin", ["JFK", "LGA"]),),
        values=rows,
    )
    selected_id = canonical_identity("origin", "LGA", "known")
    resolution = resolve_presentation(
        evidence,
        SectionPresentationPreference(category_ids=[selected_id]),
    )
    spec = build_chart(resolution)
    assert spec["data"]["values"] == [rows[1]]


def test_small_multiples_use_shared_scales_and_chronological_saved_order():
    months = ["2013-01", "2013-02"]
    origins = ["JFK", "LGA", "EWR", "BOS", "ORD", "ATL", "MIA", "SFO", "SEA"]
    rows = [
        {
            "identity": [
                canonical_identity("flight_month", month, "known"),
                canonical_identity("origin", origin, "known"),
            ],
            "measures": {"flight_count": {"value": month_index + index, "absence": None}},
            "sample_size": 1,
            "tied": False,
        }
        for month_index, month in enumerate(months)
        for index, origin in enumerate(origins)
    ]
    resolution = resolve_presentation(
        visual(
            "time_series",
            (
                dimension("flight_month", months, role="time"),
                dimension("origin", origins),
            ),
            values=rows,
        )
    )
    spec = build_chart(resolution)

    assert resolution.view == "small_multiples"
    assert [row["identity"] for row in spec["data"]["values"]] == [row["identity"] for row in rows]
    assert spec["resolve"]["scale"] == {"x": "shared", "y": "shared"}
    assert spec["spec"]["layer"][0]["encoding"]["x"]["type"] == "temporal"
    assert spec["facet"]["column"]["sort"] == origins
    assert "<svg" in vlc.vegalite_to_svg(spec)


def test_heatmap_preserves_sparse_cells_and_adds_a_non_color_value_cue():
    primary = [f"P{index}" for index in range(21)]
    series = [f"S{index}" for index in range(9)]
    rows = [
        {
            "identity": [
                canonical_identity("origin", primary[0], "known"),
                canonical_identity("carrier", series[0], "known"),
            ],
            "measures": {"flight_count": {"value": 0, "absence": None}},
            "sample_size": 0,
            "tied": False,
        }
    ]
    resolution = resolve_presentation(
        visual(
            "two_category",
            (dimension("origin", primary), dimension("carrier", series)),
            values=rows,
        )
    )
    spec = build_chart(resolution)

    assert resolution.view == "heatmap"
    assert spec["data"]["values"] == rows
    assert len(spec["layer"]) == 2
    assert spec["layer"][1]["encoding"]["text"]["field"].endswith(".value")
    assert "<svg" in vlc.vegalite_to_svg(spec)


def test_time_chart_uses_temporal_axis_and_verified_coverage_gaps_without_zero_fill():
    item = temporal_evidence(
        "flight_date",
        ["2013-01-01", "2013-01-03"],
        [4, 0],
        coverage={
            "status": "verified_intervals",
            "intervals": [{"origin": "JFK", "start": "2013-01-01", "end": "2013-01-03"}],
            "reason": None,
        },
    )
    resolution = resolve_presentation(item)
    spec = build_chart(resolution)
    values = spec["data"]["values"]
    gap = next(row for row in values if row["visual_time"] == "2013-01-02")

    assert resolution.view == "line"
    assert spec["layer"][0]["encoding"]["x"]["type"] == "temporal"
    assert gap["measures"]["flight_count"] == {
        "value": None,
        "absence": "verified_coverage_gap",
    }
    assert "<svg" in vlc.vegalite_to_svg(spec)


def test_verified_time_series_coverage_is_applied_per_selected_origin():
    months = ["2013-01-01", "2013-01-03"]
    origins = ["JFK", "LGA"]
    rows = []
    for month, origin, value in [
        ("2013-01-01", "JFK", 1),
        ("2013-01-03", "JFK", 3),
        ("2013-01-01", "LGA", 4),
    ]:
        rows.extend(
            temporal_values(
                "flight_date",
                [month],
                [value],
                canonical_identity("origin", origin, "known"),
            )
        )
    item = visual(
        "time_series",
        (
            dimension("flight_date", months, role="time"),
            dimension("origin", origins),
        ),
        values=rows,
    )
    item = item.model_copy(
        update={
            "coverage": type(item.coverage).from_dict(
                {
                    "status": "verified_intervals",
                    "intervals": [
                        {"origin": "JFK", "start": "2013-01-01", "end": "2013-01-03"},
                        {"origin": "LGA", "start": "2013-01-01", "end": "2013-01-01"},
                    ],
                    "reason": None,
                }
            )
        }
    )
    resolution = resolve_presentation(item)
    spec = build_chart(resolution)

    gaps = [
        row for row in spec["data"]["values"] if row["visual_gap_reason"] == "verified_coverage_gap"
    ]
    assert len(gaps) == 1
    assert gaps[0]["visual_time"] == "2013-01-02"
    assert gaps[0]["visual_category_1"] == "JFK"
    assert "<svg" in vlc.vegalite_to_svg(spec)


def test_aggregate_coverage_is_partial_when_one_scoped_origin_is_incomplete():
    item = temporal_evidence(
        "flight_month",
        ["2013-01"],
        [5],
        coverage={
            "status": "verified_intervals",
            "intervals": [
                {"origin": "JFK", "start": "2013-01-01", "end": "2013-01-31"},
                {"origin": "LGA", "start": "2013-01-01", "end": "2013-01-15"},
            ],
            "reason": None,
        },
    )
    item = item.model_copy(
        update={
            "scope": type(item.scope).from_dict(
                {
                    "filters": [],
                    "origins": ["JFK", "LGA"],
                    "requested_period": None,
                    "observed_period": None,
                }
            )
        }
    )
    spec = build_chart(resolve_presentation(item))

    assert spec["data"]["values"][0]["visual_period_status"] == "partial"
    assert "partial calendar period" in spec["description"]


def test_temporal_series_subset_does_not_emit_other_series_or_its_gaps():
    rows = [
        *temporal_values(
            "flight_date",
            ["2013-01-01", "2013-01-03"],
            [1, 3],
            canonical_identity("origin", "JFK", "known"),
        ),
        *temporal_values(
            "flight_date",
            ["2013-01-01"],
            [4],
            canonical_identity("origin", "LGA", "known"),
        ),
    ]
    item = visual(
        "time_series",
        (
            dimension("flight_date", ["2013-01-01", "2013-01-03"], role="time"),
            dimension("origin", ["JFK", "LGA"]),
        ),
        values=rows,
    )
    item = item.model_copy(
        update={
            "coverage": type(item.coverage).from_dict(
                {
                    "status": "verified_intervals",
                    "intervals": [
                        {"origin": "JFK", "start": "2013-01-01", "end": "2013-01-03"},
                        {"origin": "LGA", "start": "2013-01-01", "end": "2013-01-01"},
                    ],
                    "reason": None,
                }
            )
        }
    )
    preference = SectionPresentationPreference(
        series_ids=[canonical_identity("origin", "LGA", "known")]
    )
    spec = build_chart(resolve_presentation(item, preference))

    assert {row["visual_category_1"] for row in spec["data"]["values"]} == {"LGA"}
    assert not any(
        row["visual_gap_reason"] == "verified_coverage_gap" for row in spec["data"]["values"]
    )


def test_unknown_coverage_breaks_nonconsecutive_line_and_is_disclosed():
    item = temporal_evidence(
        "flight_week",
        ["2013-01-07", "2013-01-21"],
        [1, 2],
    )
    resolution = resolve_presentation(item)
    spec = build_chart(resolution)
    description = describe_visual(resolution)

    assert "coverage completeness is unknown" in description.explanation.lower()
    assert spec["layer"][0]["encoding"]["detail"]
    assert len({row["visual_segment"] for row in spec["data"]["values"]}) == 2
    assert "<svg" in vlc.vegalite_to_svg(spec)


def test_monthly_partial_periods_are_marked_and_names_retain_unicode_and_unit():
    item = temporal_evidence(
        "flight_month",
        ["2013-01", "2013-02"],
        [1.25, 2.5],
        requested_period={"start": "2013-01-15", "end": "2013-02-10"},
    )
    item = item.model_copy(
        update={
            "dimensions": (
                dimension("flight_month", ["2013-01", "2013-02"], role="time").model_copy(
                    update={"label": "Mois de départ — été"}
                ),
            )
        }
    )
    resolution = resolve_presentation(item)
    spec = build_chart(resolution)
    description = describe_visual(resolution)

    assert "Mois de départ — été" in description.name
    assert "flights" in description.name
    assert all(row["visual_period_status"] == "partial" for row in spec["data"]["values"])
    assert spec["layer"][1]["encoding"]["shape"]["field"] == "visual_period_status"
    assert "<svg" in vlc.vegalite_to_svg(spec)


def test_one_temporal_value_is_rendered_as_an_isolated_point():
    item = temporal_evidence("flight_date", ["2013-01-01"], [0])
    spec = build_chart(resolve_presentation(item))

    assert spec["mark"]["type"] == "point"
    assert "<svg" in vlc.vegalite_to_svg(spec)


@pytest.mark.parametrize(
    "rounding,expected",
    [
        (None, ",.2f"),
        ({"places": 0, "mode": "half_up"}, ",.0f"),
        ({"places": 3, "mode": "half_up"}, ",.3f"),
    ],
)
def test_numeric_display_uses_saved_precision_without_rounding_evidence(rounding, expected):
    item = visual(
        "category",
        (dimension("origin", ["JFK"]),),
        values=category_values(["JFK"], [1.235]),
    )
    item = item.model_copy(
        update={
            "format": type(item.format).from_dict(
                {"locale": "en", "computed_places": 2, "rounding": rounding}
            )
        }
    )
    spec = build_chart(resolve_presentation(item))

    assert spec["encoding"]["y"]["axis"]["format"] == expected
    measure_tooltip = next(
        item
        for item in spec["encoding"]["tooltip"]
        if item["field"] == "measures.flight_count.value"
    )
    assert measure_tooltip["format"] == expected
    assert spec["data"]["values"][0]["measures"]["flight_count"]["value"] == 1.235


def test_description_reports_only_shown_extrema_and_exact_snapshot_provenance():
    rows = category_values(["JFK", "LGA"], [1.234, 99.999])
    evidence = visual("category", (dimension("origin", ["JFK", "LGA"]),), values=rows)
    selected_id = canonical_identity("origin", "JFK", "known")
    resolution = resolve_presentation(
        evidence,
        SectionPresentationPreference(category_ids=[selected_id]),
    )
    description = describe_visual(resolution)

    assert "1.23" in description.explanation
    assert "100.00" not in description.explanation
    assert "snapshot" in description.explanation.lower()
    assert evidence.snapshot_id in description.explanation


def test_unavailable_reason_and_unrounded_non_ties_are_described_from_shown_rows():
    rows = category_values(["JFK", "LGA"], [1.234, 1.233])
    rows[1]["measures"]["flight_count"] = {
        "value": None,
        "absence": "no_known_values",
    }
    rows[1]["sample_size"] = 0
    evidence = visual(
        "category",
        (dimension("origin", ["JFK", "LGA"]),),
        values=rows,
    )
    description = describe_visual(resolve_presentation(evidence))

    assert "no_known_values" in description.explanation
    assert "tied values" not in description.explanation.lower()


def test_shared_number_formatter_uses_half_up_and_keeps_unavailable_reasons():
    evidence = visual("scalar", values=[{"value": {"value": 1.235, "absence": None}}])
    evidence = evidence.model_copy(
        update={
            "format": type(evidence.format).from_dict(
                {
                    "locale": "en",
                    "computed_places": 2,
                    "rounding": {"places": 2, "mode": "half_up"},
                }
            )
        }
    )

    assert format_visual_number({"value": 1.235, "absence": None}, evidence) == "1.24"
    assert (
        format_visual_number({"value": None, "absence": "no_known_values"}, evidence, "flights")
        == "unavailable (no_known_values)"
    )
