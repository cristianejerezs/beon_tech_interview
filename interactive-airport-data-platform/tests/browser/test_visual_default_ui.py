import logging
from copy import deepcopy
from importlib import import_module
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

import airport_analytics.reports.rendering as rendering
from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.model_client import LangChainPlanClient
from airport_analytics.errors import MissingVisualEvidenceError
from airport_analytics.models import CompositeReportV2
from airport_analytics.reports.charts import build_chart
from airport_analytics.reports.visual_evidence import prepare_visual_evidence, resolve_presentation
from airport_analytics.storage import Storage
from tests.unit.test_exploration_results import scalar_report_payload

_REPORT_JSON = ""
_VISUAL_ENABLED = True
vlc = import_module("vl_convert")


def _visual_app():
    import streamlit as st

    from airport_analytics.models import CompositeReportV2
    from airport_analytics.reports.rendering import render_report
    from tests.browser.test_visual_default_ui import _REPORT_JSON, _VISUAL_ENABLED

    report = CompositeReportV2.model_validate_json(_REPORT_JSON)
    render_report(report, st, visual_reporting_enabled=_VISUAL_ENABLED)


def _run_report(report, visual_enabled=True):
    global _REPORT_JSON, _VISUAL_ENABLED
    _REPORT_JSON = report.model_dump_json()
    _VISUAL_ENABLED = visual_enabled
    return AppTest.from_function(_visual_app).run()


def _report_payload():
    payload = deepcopy(scalar_report_payload())
    return payload


def _listing_report_payload():
    payload = _report_payload()
    section = payload["sections"][0]
    definition = {
        "unit": "entities",
        "numerator": "distinct_code",
        "denominator": None,
        "weighting": "distinct_code",
        "additivity": "non_additive",
        "match_rules": [],
        "exclusions": [],
    }
    section["interpretation"].update(
        {
            "family": "unique_entity_list",
            "operation_id": "entity_list",
            "measure_ids": [],
            "population": "observed_origins",
            "grain": "entity",
            "definition": definition,
        }
    )
    result = section["outcome"]["result"]
    for key in ("value", "kind"):
        result.pop(key, None)
    result.update(
        {
            "kind": "listing",
            "definition": definition,
            "grain": "entity",
            "fields": [
                {
                    "field_id": "origin",
                    "label": "Origin",
                    "role": "identity",
                    "unit": "airport code",
                    "unit_provenance": "catalog",
                }
            ],
            "selection": {"available": 1, "selected": 1, "omitted": 0, "cutoff_tie": False},
            "population": "observed_origins",
            "total_rows": 1,
            "rows": [{"origin": "JFK"}],
            "identity_columns": ["origin"],
            "browse_page": None,
        }
    )
    return payload


def _grouped_report_payload():
    payload = _report_payload()
    section = payload["sections"][0]
    section["interpretation"].update(
        {"family": "grouped_summary", "grouping": ["origin"], "grain": "category"}
    )
    result = section["outcome"]["result"]
    result.pop("value")
    result.update(
        {
            "kind": "grouped",
            "grain": "category",
            "fields": [
                *result["fields"],
                {
                    "field_id": "origin",
                    "label": "Origin",
                    "role": "category",
                    "unit": "airport code",
                    "unit_provenance": "catalog",
                },
            ],
            "values": [
                {
                    "identity": [
                        {"field_id": "origin", "code": "JFK", "label": "JFK", "status": "known"}
                    ],
                    "measures": {"flight_count": {"value": 9, "absence": None}},
                    "sample_size": 9,
                    "tied": False,
                    "scoped_count": None,
                    "missing_count": None,
                }
            ],
        }
    )
    return payload


def test_default_visual_section_is_source_free_and_renders_saved_scalar(monkeypatch, caplog):
    queries = [
        Mock(side_effect=AssertionError("Visual rendering must not execute queries."))
        for _ in range(3)
    ]
    for method, query in zip(
        ("execute", "execute_summary", "execute_multi_stage"),
        queries,
        strict=True,
    ):
        monkeypatch.setattr(DuckDBExecutor, method, query)
    providers = [
        Mock(side_effect=AssertionError("Visual rendering must not call a provider."))
        for _ in range(3)
    ]
    for method, provider in zip(
        ("generate_intent", "generate_plan", "generate_clarification"),
        providers,
        strict=True,
    ):
        monkeypatch.setattr(LangChainPlanClient, method, provider)
    report = CompositeReportV2.model_validate(_report_payload())
    caplog.set_level(logging.INFO, logger="airport_analytics.observability.timing")
    app = _run_report(report)

    assert not app.exception
    assert not app.error
    assert app.header[0].value == report.question
    assert any(item.label == "Flights summary" for item in app.metric)
    assert "9" in app.metric[0].value
    timing = next(event for event in caplog.records if event.getMessage() == "visual_preparation")
    assert timing.family == "scalar"
    assert timing.evidence_size_bytes > 0
    assert timing.failure_category is None
    for query in queries:
        query.assert_not_called()
    for provider in providers:
        provider.assert_not_called()


def test_daily_mean_scalar_renders_saved_value_with_requested_rounding():
    payload = _report_payload()
    section = payload["sections"][0]
    definition = {
        "unit": "destinations_per_day",
        "numerator": None,
        "denominator": None,
        "weighting": "equal_day",
        "additivity": "non_additive",
        "match_rules": ["Reference joins preserve source-flight grain."],
        "exclusions": [],
    }
    section["interpretation"].update(
        {
            "operation_id": "daily_distinct_mean",
            "measure_ids": ["distinct_destination_count"],
            "denominator_basis": "observed_operating_days",
            "field_provenance": {"denominator_basis": {"source": "explicit", "revision": 1}},
            "definition": definition,
        }
    )
    result = section["outcome"]["result"]
    result["definition"] = definition
    result["fields"][0].update(
        {
            "field_id": "distinct_destination_count",
            "label": "Daily distinct destinations",
            "unit": "destinations_per_day",
        }
    )
    result["scope"].update(
        {
            "denominator_basis": "observed_operating_days",
            "observed_days": 365,
            "eligible_days": 365,
        }
    )
    result["missingness"]["filtered_flights"] = 277977
    result.pop("value")
    result["kind"] = "daily_mean"
    result["format"]["rounding"] = {"places": 0, "mode": "half_up"}
    result["values"] = [
        {
            "identity": [],
            "tied": False,
            "measures": {"distinct_destination_count": {"value": 29593 / 365, "absence": None}},
            "sample_size": 277977,
            "value": {"value": 29593 / 365, "absence": None},
            "numerator": 29593,
            "eligible_days": 365,
            "known_contribution_count": 277977,
            "unknown_contribution_count": 0,
            "complete_days": 365,
            "incomplete_days": 0,
            "provisional": True,
        }
    ]
    app = _run_report(CompositeReportV2.model_validate(payload))

    assert not app.exception
    assert not app.error
    assert app.metric[0].value == "81"
    assert not any("scalar value is unavailable" in item.value for item in app.info)


def test_grouped_result_renders_a_named_embedded_chart_and_exact_table():
    report = CompositeReportV2.model_validate(_grouped_report_payload())
    resolution = resolve_presentation(prepare_visual_evidence(report, "section"))
    spec = build_chart(resolution)
    assert spec is not None
    assert "<svg" in vlc.vegalite_to_svg(spec)
    app = _run_report(report)

    assert not app.exception
    charts = app.get("vega_lite_chart")
    assert len(charts) == 1
    assert charts[0].alt == "Bar of Flights (flights) by Origin"
    assert any("JFK" in item.value.to_string() for item in app.dataframe)


def test_entity_listing_remains_an_exact_table_without_a_chart():
    report = CompositeReportV2.model_validate(_listing_report_payload())
    app = _run_report(report)

    assert not app.exception
    assert not app.error
    assert not app.get("vega_lite_chart")
    assert any("exact evidence table" in item.value for item in app.caption)
    assert any("JFK" in item.value.to_string() for item in app.dataframe)


def test_disabled_capability_keeps_the_existing_report_view():
    report = CompositeReportV2.model_validate(_report_payload())
    app = _run_report(report, visual_enabled=False)

    assert not app.exception
    assert not app.get("metric")
    assert any("Visual reporting is disabled" in item.value for item in app.caption)


def test_valid_empty_and_failed_sections_keep_explicit_states():
    empty_payload = _report_payload()
    section = empty_payload["sections"][0]
    result = section["outcome"]["result"]
    result["value"] = {"value": None, "absence": "no_matching_records"}
    result["missingness"]["filtered_flights"] = 0
    section["outcome"] = {"status": "valid_empty", "evidence": result}
    empty_report = CompositeReportV2.model_validate(empty_payload)
    empty_app = _run_report(empty_report)
    assert not empty_app.exception
    assert any("No finite observed values" in item.value for item in empty_app.info)

    failed_payload = _report_payload()
    successful_section = deepcopy(failed_payload["sections"][0])
    successful_section["section_id"] = "section2"
    successful_section["position"] = 2
    successful_section["interpretation"]["section_id"] = "section2"
    successful_section["outcome"]["result"]["section_id"] = "section2"
    failed_payload["sections"].append(successful_section)
    failed_payload["sections"][0]["outcome"] = {
        "status": "failed",
        "failure": {
            "category": "source_unavailable",
            "code": "saved_failure",
            "message": "The saved section did not complete.",
        },
    }
    failed_payload["completeness"] = "incomplete"
    failed_payload["incomplete_acknowledgement"] = {
        "analyst_id": "owner",
        "session_id": "session",
        "report_id": "report",
        "revision": 1,
        "failed_section_ids": ["section"],
        "acknowledged_at": "2099-04-20T00:00:00Z",
    }
    failed_report = CompositeReportV2.model_validate(failed_payload)
    failed_app = _run_report(failed_report)
    assert not failed_app.exception
    assert any("did not complete" in item.value for item in failed_app.error)


def test_missing_saved_visual_evidence_is_explained_without_replacing_the_report(monkeypatch):
    monkeypatch.setattr(
        rendering,
        "prepare_visual_evidence",
        Mock(
            side_effect=MissingVisualEvidenceError(
                "This synthetic report has no visual projection."
            )
        ),
    )
    report = CompositeReportV2.model_validate(_report_payload())
    app = _run_report(report)
    assert not app.exception
    assert any("Required saved visual evidence is unavailable" in item.value for item in app.info)
    assert any("Exact results" in item.alt for item in app.dataframe)


def test_visual_history_renders_saved_scalar_when_source_data_is_unavailable(
    monkeypatch,
    tmp_path,
):
    import app as product_app
    from airport_analytics.auth import resolve_development_identity
    from airport_analytics.errors import DatasetUnavailableError
    from airport_analytics.history.repository import ReportRepository
    from tests.browser.test_app_authentication import _configure_development, _development_app

    _configure_development(monkeypatch, tmp_path, "127.0.0.1")
    monkeypatch.setenv("AIRPORT_VISUAL_REPORTING_ENABLED", "true")
    monkeypatch.setenv("AIRPORT_SOURCE_DATA_DIR", str(tmp_path / "missing-source"))
    source = Mock(side_effect=DatasetUnavailableError())
    provider = Mock(
        side_effect=AssertionError("Rendering saved evidence must not call a provider.")
    )
    monkeypatch.setattr(product_app, "_executor", source)
    monkeypatch.setattr(product_app, "LangChainPlanClient", provider)
    app = AppTest.from_function(_development_app).run()
    app.button[0].click().run()
    identity = resolve_development_identity(production=False, server_address="127.0.0.1")
    payload = _report_payload()
    payload["analyst_id"] = identity.analyst_id
    payload["session_id"] = app.session_state["airport_session_id"]
    report = CompositeReportV2.model_validate(payload)
    repository = ReportRepository(Storage(tmp_path / "development.sqlite3"))
    repository.save_report(report, identity)
    app.session_state["active_report_id"] = report.report_id
    source.reset_mock()
    app.run()

    assert not app.exception
    assert any("Current source data is unavailable" in item.value for item in app.info)
    assert any(item.label == "Flights summary" for item in app.metric)
    assert source.call_count == 1
    provider.assert_not_called()
