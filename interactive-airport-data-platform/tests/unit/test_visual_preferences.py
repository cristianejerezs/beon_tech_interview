import pytest
from pydantic import ValidationError

from airport_analytics.errors import PresentationPreferenceError
from airport_analytics.models import SectionPresentationPreference
from airport_analytics.reports.visual_evidence import (
    canonical_identity,
    resolve_presentation,
)
from tests.unit.test_visual_defaults import category_values, dimension, visual

FAMILIES = (
    "default",
    "summary",
    "bar",
    "dot",
    "line",
    "small_multiples",
    "grouped_bar",
    "heatmap",
    "histogram",
    "scatter",
    "density",
    "table",
)


@pytest.mark.parametrize("family", FAMILIES)
def test_preference_accepts_every_declared_chart_family(family):
    assert SectionPresentationPreference(chart_family=family).chart_family == family


def test_preference_schema_version_defaults_for_legacy_values():
    preference = SectionPresentationPreference.model_validate({})

    assert getattr(preference, "preference_schema_version", None) == 1
    with pytest.raises(ValidationError):
        SectionPresentationPreference.model_validate({"preference_schema_version": 2})


@pytest.mark.parametrize("orientation", ["horizontal", "vertical"])
def test_bar_orientation_is_typed_and_relevant_only_to_bars(orientation):
    preference = SectionPresentationPreference.model_validate(
        {"chart_family": "bar", "orientation": orientation}
    )

    assert preference.orientation == orientation
    with pytest.raises(ValidationError):
        SectionPresentationPreference.model_validate(
            {"chart_family": "table", "orientation": orientation}
        )


def test_weather_selection_is_typed_and_rejected_for_non_weather_evidence():
    preference = SectionPresentationPreference.model_validate(
        {
            "chart_family": "scatter",
            "weather_variable": "temp",
            "weather_origin_id": "JFK",
        }
    )
    category_evidence = visual(
        "category",
        (dimension("origin", ["JFK", "LGA"]),),
        values=category_values(["JFK", "LGA"]),
    )

    assert preference.weather_variable == "temp"
    assert preference.weather_origin_id == "JFK"
    with pytest.raises(PresentationPreferenceError):
        resolve_presentation(category_evidence, preference)


def test_preference_ids_reject_duplicate_unknown_and_over_limit_drafts():
    codes = ["JFK", "LGA"]
    evidence = visual(
        "category",
        (dimension("origin", codes),),
        values=category_values(codes),
    )
    jfk = canonical_identity("origin", "JFK", "known")

    for category_ids in ([jfk, jfk], ["unknown"]):
        with pytest.raises(PresentationPreferenceError):
            resolve_presentation(
                evidence,
                SectionPresentationPreference(category_ids=category_ids),
            )

    many_codes = [f"A{index:02}" for index in range(21)]
    many_evidence = visual(
        "category",
        (dimension("origin", many_codes),),
        values=category_values(many_codes),
    )
    with pytest.raises(PresentationPreferenceError):
        resolve_presentation(
            many_evidence,
            SectionPresentationPreference(
                category_ids=[canonical_identity("origin", code, "known") for code in many_codes]
            ),
        )


def test_preference_binding_rejects_stale_evidence_or_selection_rule():
    evidence = visual("scalar")
    preference = SectionPresentationPreference.model_validate(
        {
            "chart_family": "summary",
            "visual_evidence_version": evidence.visual_evidence_version,
            "selection_rule_version": evidence.selection_rule_version,
            "evidence_fingerprint": evidence.evidence_fingerprint,
        }
    )

    assert resolve_presentation(evidence, preference).evidence == evidence
    for changes in [
        {"evidence_fingerprint": "d" * 64},
        {"selection_rule_version": "999.0"},
    ]:
        stale = preference.model_copy(update=changes)
        with pytest.raises(PresentationPreferenceError):
            resolve_presentation(evidence, stale)


def evidence_for_matrix(shape):
    if shape == "time_series":
        return visual(
            shape,
            (
                dimension("flight_month", ["2013-01", "2013-02"], role="time"),
                dimension("origin", ["JFK"]),
            ),
        )
    if shape == "two_category":
        return visual(
            shape,
            (
                dimension("origin", [f"P{index}" for index in range(20)]),
                dimension("carrier", [f"S{index}" for index in range(8)]),
            ),
        )
    return visual(shape)


@pytest.mark.parametrize(
    ("shape", "default", "compatible"),
    [
        ("scalar", "summary", ("summary", "table")),
        ("listing", "table", ("table",)),
        ("category", "bar", ("bar", "dot", "table")),
        ("ranking", "bar", ("bar", "dot", "table")),
        ("time", "line", ("line", "bar", "table")),
        ("time_series", "line", ("line", "small_multiples", "table")),
        ("two_category", "grouped_bar", ("grouped_bar", "heatmap", "table")),
        ("period_change", "bar", ("bar", "dot", "table")),
        ("distribution", "histogram", ("histogram", "table")),
        ("relationship", "scatter", ("scatter", "table")),
        ("weather", "scatter", ("scatter", "table")),
    ],
)
def test_preference_compatibility_matrix(shape, default, compatible):
    resolution = resolve_presentation(evidence_for_matrix(shape))

    assert resolution.view == default
    assert resolution.compatible_views == compatible
