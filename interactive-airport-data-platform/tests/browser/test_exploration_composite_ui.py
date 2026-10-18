from airport_analytics.errors import QueryExecutionError
from tests.browser.test_exploration_summary_ui import open_app
from tests.unit.test_exploration_contracts import proposed_section


def test_two_pending_sections_resolve_before_any_main_query(monkeypatch, tmp_path):
    from airport_analytics.analytics.request_state import PENDING_REQUEST_KEY
    from tests.integration.test_exploration_clarification import ClarificationClient

    app, model, executor = open_app(monkeypatch, tmp_path)
    model.payload = ClarificationClient().proposal.model_dump(mode="json")
    model.payload["sections"][0]["clarification"]["choices"] = [
        {
            "choice_id": code,
            "label": code,
            "edits": [{"field_id": "origin", "action": "replace", "operator": "eq", "value": code}],
        }
        for code in ["JFK", "LGA"]
    ]
    model.payload["sections"].append(
        model.payload["sections"][0]
        | {
            "position": 2,
            "original_clause": "Second count needing an origin",
        }
    )
    actual = executor.execute_summary
    calls = []

    def execute(interpretation):
        calls.append(interpretation.section_id)
        return actual(interpretation)

    monkeypatch.setattr(executor, "execute_summary", execute)
    try:
        app.text_area[0].input("Two counts with ambiguous origins")
        next(button for button in app.button if button.label == "Generate report").click().run()
        original_ids = [
            section.section_id for section in app.session_state[PENDING_REQUEST_KEY].draft.sections
        ]
        next(button for button in app.button if button.label == "Use selected choice").click().run()
        assert not calls
        assert app.session_state[PENDING_REQUEST_KEY].active_section.position == 2
        next(button for button in app.button if button.label == "Use selected choice").click().run()
        assert not app.error
        assert not app.exception
        assert calls == original_ids
        assert model.calls == 1
    finally:
        executor.close()


def test_four_section_ui_and_saved_bundle(monkeypatch, tmp_path):
    app, model, executor = open_app(monkeypatch, tmp_path)
    model.payload["sections"] = [
        proposed_section(position=index, original_clause=f"Analysis {index}")
        for index in range(1, 5)
    ]
    try:
        app.text_area[0].input("Four analyses")
        next(button for button in app.button if button.label == "Generate report").click().run()
        assert not app.error
        assert not app.exception
        assert len([item for item in app.subheader if "Analysis" in item.value]) == 4
        assert any("bundle" in button.label for button in app.get("download_button"))
        assert model.calls == 1
        next(select for select in app.selectbox if select.label == "Presentation").select("table")
        next(
            button
            for button in app.button
            if button.label == "Save section presentation preference"
        ).click().run()
        assert not app.error
        assert not app.exception
        assert model.calls == 1
        next(button for button in app.button if button.label == "Create shared copy").click().run()
        app.run()
        assert not app.exception
        assert any("Section 4: Analysis 4" in item.value for item in app.markdown)
        next(
            select for select in app.selectbox if select.label == "Scope refinement origin"
        ).select("JFK")
        next(
            button
            for button in app.button
            if button.label == "Apply explicit section scope refinement"
        ).click().run()
        assert not app.error
        assert not app.exception
        assert model.calls == 1
    finally:
        executor.close()


def test_incomplete_report_requires_explicit_save_acknowledgement(monkeypatch, tmp_path):
    app, model, executor = open_app(monkeypatch, tmp_path)
    model.payload["sections"] = [
        proposed_section(position=index, original_clause=f"Analysis {index}")
        for index in range(1, 3)
    ]
    actual = executor.execute_summary
    calls = 0

    def execute(item):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise QueryExecutionError()
        return actual(item)

    monkeypatch.setattr(executor, "execute_summary", execute)
    try:
        app.text_area[0].input("Two analyses")
        next(button for button in app.button if button.label == "Generate report").click().run()
        assert not app.exception
        assert app.session_state["unsaved_exploration_report"].completeness == "incomplete"
        save = next(button for button in app.button if button.label == "Save unsaved report")
        assert save.disabled
        next(
            box for box in app.checkbox if "acknowledge the listed failed" in box.label
        ).check().run()
        next(button for button in app.button if button.label == "Save unsaved report").click().run()
        assert not app.exception
        assert "unsaved_exploration_report" not in app.session_state
        assert any("bundle" in button.label for button in app.get("download_button"))
        assert model.calls == 1
    finally:
        executor.close()


def test_more_than_four_requires_confirmed_subset_and_never_queues_other_work(
    monkeypatch, tmp_path
):
    app, model, executor = open_app(monkeypatch, tmp_path)
    model.payload.update(
        status="requires_selection",
        sections=[],
        selection_reason="Select at most four of these five requested analyses.",
    )
    try:
        app.text_area[0].input("Five related analyses")
        next(button for button in app.button if button.label == "Generate report").click().run()
        assert model.calls == 1
        assert not app.exception
        next(area for area in app.text_area if area.label.startswith("Selected subset")).input(
            "Count flights"
        )
        next(
            button
            for button in app.button
            if button.label == "Analyze the explicitly selected subset"
        ).click().run()
        assert model.calls == 1
        assert app.error
        next(
            box for box in app.checkbox if box.label.startswith("I select only this subset")
        ).check()
        model.payload.update(
            status="proposed",
            sections=[proposed_section()],
            selection_reason=None,
        )
        next(
            button
            for button in app.button
            if button.label == "Analyze the explicitly selected subset"
        ).click().run()
        assert not app.exception
        assert not app.error
        assert model.calls == 2
        app.run()
        assert model.calls == 2
    finally:
        executor.close()
