from dataclasses import replace

import pytest

from airport_analytics.analytics.request_state import (
    AnswerEvent,
    begin_request,
    bind_proposal,
    fail_request,
    finish_execution,
    retry_request,
    start_execution,
    stop_request,
    validate_answer,
)
from airport_analytics.errors import InvalidQuestionError
from airport_analytics.models import IntentProposalV2, SafeFailure
from tests.unit.test_exploration_contracts import proposed_section
from tests.unit.test_exploration_interpretation import proposal


def ambiguous():
    return IntentProposalV2.model_validate(
        {
            "intent_version": 2,
            "status": "needs_clarification",
            "shared_scope": {},
            "sections": [
                proposed_section(
                    status="needs_clarification",
                    clarification={
                        "field_id": "origin",
                        "question": "Which origin?",
                        "choices": [],
                    },
                )
            ],
            "selection_reason": None,
        }
    )


def pending():
    state = begin_request("Count flights at the airport", "session", "a" * 64, "b" * 64)
    return bind_proposal(state, ambiguous())


def event(state, **changes):
    return AnswerEvent(
        session_binding=state.draft.session_binding,
        request_id=state.draft.request_id,
        revision=state.draft.revision,
        section_id=state.active_section.section_id,
        question_id=state.question_id,
        text="JFK",
    ).model_copy(update=changes)


def test_three_answered_ambiguous_turns_then_guided_correction():
    state = pending()
    original = state.draft.original_question
    for turn in range(1, 4):
        validate_answer(state, event(state), "session")
        old = state
        state = bind_proposal(state, ambiguous(), answered=True)
        assert state.draft.sections[0].answered_turns == turn
        assert old.draft.sections[0].answered_turns == turn - 1
        assert state.draft.revision == turn + 1
        assert state.question_id != old.question_id
    assert state.draft.state == "guided_correction"
    assert state.draft.original_question == original
    with pytest.raises(ValueError):
        validate_answer(state, event(state), "session")


@pytest.mark.parametrize(
    "changes",
    [
        {"session_binding": "other"},
        {"request_id": "other"},
        {"revision": 99},
        {"section_id": "other"},
        {"question_id": "old"},
        {"text": " "},
        {"text": "x" * 2001},
        {"choice_id": "unoffered", "text": None},
    ],
)
def test_stale_or_invalid_answers_are_rejected_without_mutation(changes):
    state = pending()
    with pytest.raises((ValueError, InvalidQuestionError)):
        validate_answer(state, event(state, **changes), "session")
    assert state.draft.sections[0].answered_turns == 0


def test_provider_failure_preserves_question_choices_and_turns_then_explicit_retry():
    state = pending()
    failure = SafeFailure(
        category="provider_unavailable",
        code="provider_timeout",
        message="Provider timed out.",
    )
    failed = fail_request(state, failure)
    assert failed.draft.state == "failed"
    assert failed.question_id == state.question_id
    assert failed.proposal == state.proposal
    assert failed.active_section.answered_turns == 0
    with pytest.raises(ValueError):
        validate_answer(failed, event(failed), "session")
    retried = retry_request(failed, "session")
    assert retried.draft.state == "clarification_pending"
    assert retried.draft.revision > failed.draft.revision
    assert retried.question_id != failed.question_id
    assert retried.active_section.answered_turns == 0


@pytest.mark.parametrize("terminal", ["cancelled", "superseded"])
def test_stop_invalidates_pending_answers(terminal):
    state = stop_request(pending(), terminal)
    assert state.draft.state == terminal
    with pytest.raises(ValueError):
        validate_answer(state, event(state), "session")


def test_resolved_execution_outcomes_are_explicit():
    state = bind_proposal(pending(), proposal(), answered=True)
    assert state.draft.state == "resolved"
    assert state.draft.sections[0].answered_turns == 1
    running = start_execution(state)
    assert running.draft.state == "executing"
    for outcome in ["completed", "incomplete", "failed"]:
        assert finish_execution(running, outcome).draft.state == outcome
    with pytest.raises(ValueError):
        start_execution(pending())
    with pytest.raises(ValueError):
        finish_execution(state, "completed")


def test_first_unresolved_section_in_request_order_preserves_other_turn_counts():
    state = begin_request("Two questions", "session", "a" * 64, "b" * 64)
    envelope = proposal()
    envelope = envelope.model_copy(
        update={
            "status": "needs_clarification",
            "sections": [
                envelope.sections[0],
                type(envelope.sections[0]).model_validate(
                    proposed_section(
                        position=2,
                        status="needs_clarification",
                        clarification={
                            "field_id": "origin",
                            "question": "Which origin?",
                            "choices": [],
                        },
                    )
                ),
            ],
        }
    )
    state = bind_proposal(state, envelope)
    assert state.active_section.position == 2
    assert state.draft.sections[0].status == "resolved"
    state = bind_proposal(state, envelope, answered=True)
    assert state.draft.sections[0].answered_turns == 0
    assert state.active_section.answered_turns == 1
    with pytest.raises(ValueError):
        retry_request(replace(state, draft=state.draft), "other")
