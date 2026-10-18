from airport_analytics.analytics.request_state import PENDING_REQUEST_KEY
from tests.browser.test_exploration_summary_ui import open_app
from tests.unit.test_exploration_contracts import proposed_section
from tests.unit.test_exploration_state import ambiguous


def button(app, label):
    return next(item for item in app.button if item.label == label)


def submit_ambiguous(app, model):
    model.payload = ambiguous().model_dump(mode="json")
    app.text_area[0].input("Count flights at the airport")
    button(app, "Generate report").click().run()
    assert not app.exception
    assert any(item.value == "Which origin?" for item in app.info)


def test_free_text_clarification_is_bounded_and_guided_correction_is_local(monkeypatch, tmp_path):
    app, model, executor = open_app(monkeypatch, tmp_path)
    try:
        submit_ambiguous(app, model)
        for turn in range(1, 4):
            next(area for area in app.text_area if area.label == "Clarification answer").input(
                "JFK"
            )
            button(app, "Submit clarification").click().run()
            assert not app.exception
            state = app.session_state[PENDING_REQUEST_KEY]
            assert state.active_section.answered_turns == turn
            assert model.calls == turn + 1
        assert state.draft.state == "guided_correction"
        assert not any(area.label == "Clarification answer" for area in app.text_area)
        next(item for item in app.selectbox if item.label == "Corrected origin").select("JFK")
        button(app, "Apply guided correction").click().run()
        assert not app.exception
        assert not app.error
        assert model.calls == 4
        assert app.session_state[PENDING_REQUEST_KEY].draft.state == "completed"
    finally:
        executor.close()


def test_clarification_failure_retains_turn_count_and_requires_explicit_retry(
    monkeypatch, tmp_path
):
    app, model, executor = open_app(monkeypatch, tmp_path)
    try:
        submit_ambiguous(app, model)
        model.failure = TimeoutError("private provider detail")
        next(area for area in app.text_area if area.label == "Clarification answer").input("JFK")
        button(app, "Submit clarification").click().run()
        assert not app.exception
        state = app.session_state[PENDING_REQUEST_KEY]
        assert state.draft.state == "failed"
        assert state.active_section.answered_turns == 0
        assert "private provider detail" not in str(app.error)
        assert model.calls == 2
        model.failure = None
        button(app, "Retry interpretation").click().run()
        assert app.session_state[PENDING_REQUEST_KEY].draft.state == "clarification_pending"
        assert model.calls == 2
        button(app, "Cancel analysis").click().run()
        assert app.session_state[PENDING_REQUEST_KEY].draft.state == "cancelled"
        assert not any(area.label == "Clarification answer" for area in app.text_area)
    finally:
        executor.close()


def test_clarification_choices_are_local_and_preserve_original_question(monkeypatch, tmp_path):
    app, model, executor = open_app(monkeypatch, tmp_path)
    payload = ambiguous().model_dump(mode="json")
    payload["sections"][0]["clarification"]["choices"] = [
        {
            "choice_id": code,
            "label": code,
            "edits": [
                {"field_id": "origin", "action": "replace", "operator": "eq", "value": code},
            ],
        }
        for code in ["JFK", "LGA"]
    ]
    model.payload = payload
    try:
        app.text_area[0].input("Count flights at the airport")
        button(app, "Generate report").click().run()
        next(item for item in app.selectbox if item.label == "Clarification choice").select("LGA")
        button(app, "Use selected choice").click().run()
        assert not app.exception
        assert not app.error
        assert model.calls == 1
        state = app.session_state[PENDING_REQUEST_KEY]
        assert state.draft.original_question == "Count flights at the airport"
        assert state.draft.state == "completed"
        assert any("1 flights" in item.value for item in app.markdown)
    finally:
        executor.close()


def test_invalid_provider_output_has_recovery_controls_not_fake_clarification(
    monkeypatch, tmp_path
):
    app, model, executor = open_app(monkeypatch, tmp_path)
    try:
        model.payload = {"intent_version": 2, "invalid": True}
        app.text_area[0].input("Four analytical questions")
        button(app, "Generate report").click().run()
        assert not app.exception
        assert app.error
        assert app.session_state[PENDING_REQUEST_KEY].draft.last_failure.category == (
            "invalid_provider_output"
        )
        assert not any(area.label == "Clarification answer" for area in app.text_area)
        assert button(app, "Retry interpretation")
        assert button(app, "Apply guided correction")
        button(app, "Sign out").click().run()
        assert PENDING_REQUEST_KEY not in app.session_state
    finally:
        executor.close()


def test_new_question_supersedes_pending_and_invalid_choices_are_not_selectable(
    monkeypatch,
    tmp_path,
):
    app, model, executor = open_app(monkeypatch, tmp_path)
    payload = ambiguous().model_dump(mode="json")
    payload["sections"][0]["clarification"]["choices"] = [
        {
            "choice_id": code,
            "label": code,
            "edits": [
                {"field_id": "origin", "action": "replace", "operator": "eq", "value": code},
            ],
        }
        for code in ["NOT_REAL", "LGA"]
    ]
    model.payload = payload
    try:
        app.text_area[0].input("Count flights at the airport")
        button(app, "Generate report").click().run()
        original = app.session_state[PENDING_REQUEST_KEY]
        selector = next(item for item in app.selectbox if item.label == "Clarification choice")
        assert selector.options == ["LGA"]
        assert any("not selectable" in warning.value for warning in app.warning)
        model.payload = {
            "intent_version": 2,
            "status": "proposed",
            "shared_scope": {},
            "sections": [proposed_section()],
            "selection_reason": None,
        }
        app.text_area[0].input("Count all flights")
        button(app, "Generate report").click().run()
        assert not app.exception
        assert not app.error
        current = app.session_state[PENDING_REQUEST_KEY]
        assert current.draft.request_id != original.draft.request_id
        assert current.draft.original_question == "Count all flights"
        assert current.draft.state == "completed"
        assert model.calls == 2
        assert not any(area.label == "Clarification answer" for area in app.text_area)
    finally:
        executor.close()
