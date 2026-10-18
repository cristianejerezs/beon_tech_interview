from copy import deepcopy

from streamlit.testing.v1 import AppTest

from airport_analytics.models import CompositeReportV2
from tests.unit.test_exploration_results import scalar_report_payload

_REPORT_JSON = ""


def _visual_app():
    import streamlit as st

    from airport_analytics.models import CompositeReportV2
    from airport_analytics.reports.rendering import render_report
    from tests.browser.test_visual_accessibility import _REPORT_JSON

    report = CompositeReportV2.model_validate_json(_REPORT_JSON)
    render_report(report, st, visual_reporting_enabled=True)


def _relationship_report(pair_count: int) -> CompositeReportV2:
    payload = deepcopy(scalar_report_payload())
    payload["question"] = "Compare departure delay with distance"
    section = payload["sections"][0]
    section["label"] = "Departure delay by distance"
    section["narrative"] = "Synthetic paired observations across flights."
    definition = {
        "unit": "paired_units",
        "numerator": "paired observations",
        "denominator": None,
        "weighting": "source_record",
        "additivity": "non_additive",
        "match_rules": [],
        "exclusions": [],
    }
    section["interpretation"].update(
        {
            "family": "numeric_relationship",
            "operation_id": "flight_relationship",
            "measure_ids": ["distance", "departure_delay"],
            "grain": "flight_pair",
            "definition": definition,
            "pairing": {"x": "distance", "y": "departure_delay"},
        }
    )
    result = section["outcome"]["result"]
    result.pop("value")
    result["missingness"] = {"filtered_flights": pair_count}
    result.update(
        {
            "kind": "relationship",
            "grain": "flight_pair",
            "definition": definition,
            "fields": [
                {
                    "field_id": "distance",
                    "label": "Distance",
                    "role": "numeric",
                    "unit": "miles",
                    "unit_provenance": "catalog",
                },
                {
                    "field_id": "departure_delay",
                    "label": "Departure delay",
                    "role": "numeric",
                    "unit": "minutes",
                    "unit_provenance": "catalog",
                },
            ],
            "pairing": {
                "x_field": "distance",
                "y_field": "departure_delay",
                "x_unit": "miles",
                "y_unit": "minutes",
                "pair_count": pair_count,
                "scoped_count": pair_count,
                "x_missing_only": 0,
                "y_missing_only": 0,
                "both_missing": 0,
                "pairs": [
                    {"source_id": f"flight-{index:03}", "x": index, "y": index * 2}
                    for index in range(pair_count)
                ],
                "density": None,
                "x_extent": [0, pair_count - 1],
                "y_extent": [0, (pair_count - 1) * 2],
            },
        }
    )
    return CompositeReportV2.model_validate(payload)


def _run_report(report: CompositeReportV2):
    global _REPORT_JSON
    _REPORT_JSON = report.model_dump_json()
    return AppTest.from_function(_visual_app).run()


def test_large_relationship_table_is_paged_with_named_exact_evidence():
    app = _run_report(_relationship_report(125))

    assert not app.exception
    assert not app.error
    assert len(app.get("vega_lite_chart")) == 1
    assert (
        app.get("vega_lite_chart")[0].alt
        == "Scatter of distance (miles) and departure_delay (minutes)"
    )
    assert len(app.number_input) == 1
    assert app.number_input[0].label == (
        "Page of exact paired observations for Departure delay by distance"
    )
    table = app.dataframe[0]
    assert "Exact paired observations" in table.alt
    assert len(table.value) == 100
    assert table.value.iloc[0]["source_id"] == "flight-000"
    assert table.value.iloc[-1]["source_id"] == "flight-099"
    assert any("rows 1–100 of 125" in item.value for item in app.caption)
    explanation = next(
        item.value for item in app.caption if "complete paired observations" in item.value
    )
    assert "125 complete paired observations" in explanation
    assert "saved group" not in explanation
    assert "verified bucket coverage" not in explanation

    app.number_input[0].set_value(2).run()

    assert not app.exception
    table = app.dataframe[0]
    assert len(table.value) == 25
    assert table.value.iloc[0]["source_id"] == "flight-100"
    assert table.value.iloc[-1]["source_id"] == "flight-124"
    assert any("rows 101–125 of 125" in item.value for item in app.caption)


def test_small_relationship_table_remains_a_single_complete_named_table():
    app = _run_report(_relationship_report(5))

    assert not app.exception
    assert not app.number_input
    assert len(app.dataframe[0].value) == 5
    assert app.dataframe[0].alt == "Exact paired observations: Departure delay by distance"


if __name__ == "__main__":
    import streamlit as st

    from airport_analytics.reports.rendering import render_report

    render_report(_relationship_report(125), st, visual_reporting_enabled=True)
