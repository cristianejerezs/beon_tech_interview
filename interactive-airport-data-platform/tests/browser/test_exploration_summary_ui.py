import sqlite3
from pathlib import Path

from streamlit.testing.v1 import AppTest

import app as product_app
from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.model_client import LangChainPlanClient
from airport_analytics.auth import resolve_development_identity
from airport_analytics.history.repository import ReportRepository
from airport_analytics.models import CompositeReportV2
from airport_analytics.storage import Storage
from tests.browser.test_app_authentication import _configure_development, _development_app
from tests.integration.test_exploration_provider import IntentModel

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "exploration"


def open_app(monkeypatch, tmp_path):
    _configure_development(monkeypatch, tmp_path, "127.0.0.1")
    monkeypatch.setenv("AIRPORT_SOURCE_DATA_DIR", str(FIXTURES))
    executor = DuckDBExecutor(str(FIXTURES))
    monkeypatch.setattr(product_app, "_executor", lambda *args: executor)
    model = IntentModel()
    monkeypatch.setattr(
        product_app,
        "LangChainPlanClient",
        lambda settings, **kwargs: LangChainPlanClient(settings, model=model, **kwargs),
    )
    app = AppTest.from_function(_development_app).run()
    app.button[0].click().run()
    assert (
        next(toggle for toggle in app.toggle if toggle.label == "Use V2 summary exploration").value
        is True
    )
    return app, model, executor


def test_v2_question_history_exports_faq_and_explicit_follow_up(monkeypatch, tmp_path):
    app, model, executor = open_app(monkeypatch, tmp_path)
    try:
        app.text_area[0].input("How many flights?")
        next(button for button in app.button if button.label == "Generate report").click().run()
        assert not app.exception
        assert not app.error
        assert model.calls == 1
        assert not app.get("json")
        assert any(item.label == "How this was calculated" for item in app.expander)
        assert any(item.label == "Scope and data quality" for item in app.expander)
        assert any(
            "Distinct" in table.value.to_string() or "Numerator" in table.value.to_string()
            for table in app.table
        )
        identity = resolve_development_identity(production=False, server_address="127.0.0.1")
        repo = ReportRepository(Storage(tmp_path / "development.sqlite3"))
        saved = repo.list_reports(identity)
        assert len(saved) == 1
        assert isinstance(saved[0], CompositeReportV2)
        assert len(app.get("download_button")) >= 2
        assert any("Logical interpretation" in title.value for title in app.subheader)
        next(button for button in app.button if button.label == "Create shared copy").click().run()
        assert not app.error
        app.run()
        next(
            button for button in app.button if button.label == "Use this FAQ question"
        ).click().run()
        assert app.text_area[0].value == "How many flights?"
        next(checkbox for checkbox in app.checkbox if "Refine" in checkbox.label).check()
        app.text_area[0].input("All origins combined")
        next(button for button in app.button if button.label == "Generate report").click().run()
        assert not app.error
        assert model.calls == 2
        assert repo.list_reports(identity)[0].revision == 2
    finally:
        executor.close()


def test_edit_cancel_keeps_saved_report_and_apply_is_local_new_revision(monkeypatch, tmp_path):
    app, model, executor = open_app(monkeypatch, tmp_path)
    try:
        app.text_area[0].input("Count flights")
        next(button for button in app.button if button.label == "Generate report").click().run()
        identity = resolve_development_identity(production=False, server_address="127.0.0.1")
        repo = ReportRepository(Storage(tmp_path / "development.sqlite3"))
        original = repo.list_reports(identity)[0]
        next(button for button in app.button if button.label == "Edit interpretation").click().run()
        next(
            multiselect for multiselect in app.multiselect if multiselect.label == "Group by"
        ).select("origin")
        next(button for button in app.button if button.label == "Cancel edits").click().run()
        assert repo.list_reports(identity) == [original]
        assert model.calls == 1
        next(button for button in app.button if button.label == "Edit interpretation").click().run()
        next(
            multiselect for multiselect in app.multiselect if multiselect.label == "Group by"
        ).select("origin")
        next(
            button for button in app.button if button.label == "Apply interpretation"
        ).click().run()
        assert not app.error
        assert not app.exception
        revised = repo.list_reports(identity)[0]
        assert revised.report_id != original.report_id
        assert revised.parent_report_id == original.report_id
        assert revised.revision == 2
        assert revised.sections[0].interpretation.grouping == ["origin"]
        assert model.calls == 1
        assert repo.get_report(identity, original.report_id) == original
    finally:
        executor.close()


def test_edit_can_group_connected_airports_by_airport_and_render_chart(monkeypatch, tmp_path):
    from tests.exploration_oracles import read_rows
    from tests.unit.test_exploration_contracts import proposed_section

    monkeypatch.setenv("AIRPORT_VISUAL_REPORTING_ENABLED", "true")
    app, model, executor = open_app(monkeypatch, tmp_path)
    model.payload["sections"] = [proposed_section(measure_ids=["distinct_destination_count"])]
    try:
        app.text_area[0].input(
            "Determine the number of distinct destinations connected to all airports"
        )
        next(button for button in app.button if button.label == "Generate report").click().run()
        assert not app.exception
        next(button for button in app.button if button.label == "Edit interpretation").click().run()
        group_by = next(item for item in app.multiselect if item.label == "Group by")
        assert "airport" in group_by.options
        next(item for item in app.selectbox if item.label == "Measure").select(
            "distinct_connected_airport_count"
        )
        group_by.select("airport")
        next(
            button for button in app.button if button.label == "Apply interpretation"
        ).click().run()
        assert not app.error
        assert not app.exception
        identity = resolve_development_identity(production=False, server_address="127.0.0.1")
        revised = ReportRepository(Storage(tmp_path / "development.sqlite3")).list_reports(
            identity
        )[0]
        interpretation = revised.sections[0].interpretation
        assert interpretation.measure_ids == ["distinct_connected_airport_count"]
        assert interpretation.grouping == ["airport"]
        neighbours: dict[str, set[str]] = {}
        for row in read_rows(FIXTURES / "nyc_flights_fixed.csv"):
            if row["origin"] and row["dest"] and row["origin"] != row["dest"]:
                neighbours.setdefault(row["origin"], set()).add(row["dest"])
                neighbours.setdefault(row["dest"], set()).add(row["origin"])
        table = next(
            item.value
            for item in app.dataframe
            if "distinct_connected_airport_count" in item.value.columns
        )
        assert dict(
            zip(table["airport_code"], table["distinct_connected_airport_count"], strict=True)
        ) == {airport: len(codes) for airport, codes in neighbours.items()}
        assert app.get("vega_lite_chart") or app.get("arrow_vega_lite_chart")
    finally:
        executor.close()


def test_origin_destination_counts_show_all_recorded_origins_and_scope_note(monkeypatch, tmp_path):
    from tests.unit.test_exploration_contracts import proposed_section

    app, model, executor = open_app(monkeypatch, tmp_path)
    model.payload["sections"] = [
        proposed_section(
            family="grouped_summary",
            measure_ids=["distinct_destination_count"],
            grouping=["origin"],
        )
    ]
    try:
        app.text_area[0].input("Count distinct destinations by origin")
        next(button for button in app.button if button.label == "Generate report").click().run()
        assert not app.exception
        assert not app.error
        assert not app.get("json")
        table = next(
            item.value
            for item in app.dataframe
            if "distinct_destination_count" in item.value.columns
        )
        from tests.exploration_oracles import read_rows

        rows = read_rows(FIXTURES / "nyc_flights_fixed.csv")
        expected = {
            origin: len({row["dest"] for row in rows if row["origin"] == origin})
            for origin in {row["origin"] for row in rows}
        }
        assert (
            dict(
                zip(
                    table["origin_code"],
                    table["distinct_destination_count"],
                    strict=True,
                )
            )
            == expected
        )
        assert any(
            "Airports without departure observations are not included" in item.value
            for item in app.caption
        )
    finally:
        executor.close()


def test_weather_pearson_is_visible_with_provisional_warning(monkeypatch, tmp_path):
    from tests.unit.test_exploration_contracts import proposed_section

    app, model, executor = open_app(monkeypatch, tmp_path)
    model.payload["sections"] = [
        proposed_section(
            family="numeric_relationship",
            operation_id="weather_relationship",
            measure_ids=["mean_departure_delay"],
        )
    ]
    try:
        app.text_area[0].input("Analyze the correlation between departure delay and weather")
        next(button for button in app.button if button.label == "Generate report").click().run()
        assert not app.exception
        assert not app.error
        assert not app.get("json")
        assert any("Provisional Pearson" in item.value for item in app.warning)
        assert any(
            "Temperature: r =" in item.value and "valid origin-hours" in item.value
            for item in app.markdown
        )
        assert any(
            "precipitation comparisons are unavailable" in item.value for item in app.warning
        )
        coefficients = next(
            item.value for item in app.dataframe if "coefficient" in item.value.columns
        )
        assert len(coefficients) == 4
        assert set(coefficients["variable"]) == {"temp", "wind_speed", "precip", "visib"}
        assert any("recorded units (unverified)" in table.value.to_string() for table in app.table)
        assert model.calls == 1
    finally:
        executor.close()


def test_month_of_year_ranking_keeps_seasonal_identity_in_ui(monkeypatch, tmp_path):
    from tests.unit.test_exploration_contracts import proposed_section

    app, model, executor = open_app(monkeypatch, tmp_path)
    model.payload["sections"] = [
        proposed_section(
            family="ranking",
            operation_id="departure_delay_total",
            measure_ids=["positive_delay_minutes"],
            grouping=["month_of_year"],
            order={"field_id": "positive_delay_minutes", "direction": "desc"},
            bound=1,
        )
    ]
    try:
        app.text_area[0].input(
            "Identify the month of the year with the highest accumulated departure delay "
            "for all years"
        )
        next(button for button in app.button if button.label == "Generate report").click().run()
        assert not app.exception
        assert not app.error
        table = next(
            item.value for item in app.dataframe if "month_of_year_code" in item.value.columns
        )
        assert len(table) == 1
        assert table["month_of_year_code"].iloc[0] in {"01", "02"}
        assert any("pool the same named month" in item.value for item in app.markdown)
        assert model.calls == 1
    finally:
        executor.close()


def test_relationship_evidence_uses_readable_details_not_raw_json(monkeypatch, tmp_path):
    from tests.unit.test_exploration_contracts import proposed_section

    app, model, executor = open_app(monkeypatch, tmp_path)
    model.payload["sections"] = [
        proposed_section(
            family="numeric_relationship",
            operation_id="flight_relationship",
            measure_ids=["departure_delay", "arrival_delay"],
        )
    ]
    try:
        app.text_area[0].input("Compare departure and arrival delays")
        next(button for button in app.button if button.label == "Generate report").click().run()
        assert not app.exception
        assert not app.error
        assert not app.get("json")
        assert any(item.label == "Pair populations and missingness" for item in app.expander)
    finally:
        executor.close()


def test_readable_details_preserve_text_and_render_missing_values():
    from airport_analytics.reports.rendering import detail_rows

    assert detail_rows(
        {
            "denominator": None,
            "weighting": "distinct_destination",
            "match_rules": ["Keep source_row_id intact."],
            "scope": {"origins": ["A_B", "JFK"], "verified": False},
        }
    ) == [
        {"Detail": "Denominator", "Description": "Not applicable"},
        {"Detail": "Weighting", "Description": "distinct destination"},
        {"Detail": "Match rules", "Description": "Keep source_row_id intact."},
        {"Detail": "Scope / Origins", "Description": "A_B; JFK"},
        {"Detail": "Scope / Verified", "Description": "No"},
    ]


def test_airport_connection_listing_is_readable_saved_and_browsable(monkeypatch, tmp_path):
    from tests.unit.test_exploration_contracts import proposed_section

    app, model, executor = open_app(monkeypatch, tmp_path)
    model.payload["sections"] = [
        proposed_section(
            family="unique_entity_list",
            operation_id="entity_list",
            measure_ids=[],
            population="airport_connections",
            order={"field_id": "connection_count", "direction": "desc"},
        )
    ]
    try:
        app.text_area[0].input(
            "Count distinct neighbours in either direction for all catalogue airports"
        )
        next(button for button in app.button if button.label == "Generate report").click().run()
        assert not app.exception
        assert not app.error
        assert not app.get("json")
        table = next(
            item.value for item in app.dataframe if "connection_count" in item.value.columns
        )
        assert "ZZZ" in set(table["code"])
        assert table.loc[table["code"] == "ZZZ", "connection_count"].iloc[0] == 0
        assert any(item.label == "Listing sort column" for item in app.selectbox)
        identity = resolve_development_identity(production=False, server_address="127.0.0.1")
        report = ReportRepository(Storage(tmp_path / "development.sqlite3")).list_reports(identity)[
            0
        ]
        assert report.sections[0].interpretation.population == "airport_connections"
        assert report.sections[0].outcome.result.definition.unit == "connected airports"
    finally:
        executor.close()


def test_failed_save_keeps_visible_session_evidence_and_explicit_retry_does_not_call_model(
    monkeypatch,
    tmp_path,
):
    app, model, executor = open_app(monkeypatch, tmp_path)
    real_save = ReportRepository.save_report
    calls = 0

    def interrupted_save(self, report, identity):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise sqlite3.OperationalError("Synthetic interruption")
        return real_save(self, report, identity)

    monkeypatch.setattr(ReportRepository, "save_report", interrupted_save)
    try:
        app.text_area[0].input("Count flights")
        next(button for button in app.button if button.label == "Generate report").click().run()
        assert not app.exception
        assert app.error
        assert any("not saved" in warning.value for warning in app.warning)
        assert (
            app.session_state["unsaved_exploration_report"].sections[0].outcome.result.value.value
            == 9
        )
        assert model.calls == 1
        next(button for button in app.button if button.label == "Save unsaved report").click().run()
        assert not app.error
        assert model.calls == 1
        assert "unsaved_exploration_report" not in app.session_state
        identity = resolve_development_identity(production=False, server_address="127.0.0.1")
        repo = ReportRepository(Storage(tmp_path / "development.sqlite3"))
        assert len(repo.list_reports(identity)) == 1
    finally:
        executor.close()


def test_unchanged_editor_scope_preserves_negative_and_unshown_predicates(monkeypatch, tmp_path):
    app, model, executor = open_app(monkeypatch, tmp_path)
    model.payload["sections"][0]["scope_edits"] = [
        {"field_id": "origin", "action": "add", "operator": "neq", "value": "JFK"},
        {"field_id": "flight_year", "action": "add", "operator": "eq", "value": 2013},
    ]
    try:
        app.text_area[0].input("Flights outside JFK in 2013")
        next(button for button in app.button if button.label == "Generate report").click().run()
        assert not app.error, [item.value for item in app.error]
        identity = resolve_development_identity(production=False, server_address="127.0.0.1")
        repo = ReportRepository(Storage(tmp_path / "development.sqlite3"))
        original = repo.list_reports(identity)[0]
        next(button for button in app.button if button.label == "Edit interpretation").click().run()
        next(
            button for button in app.button if button.label == "Apply interpretation"
        ).click().run()
        assert not app.exception
        assert not app.error
        revised = repo.list_reports(identity)[0]
        assert (
            revised.sections[0].interpretation.filters
            == original.sections[0].interpretation.filters
        )
        assert revised.sections[0].outcome.result.value.value == 1
        assert model.calls == 1
    finally:
        executor.close()
