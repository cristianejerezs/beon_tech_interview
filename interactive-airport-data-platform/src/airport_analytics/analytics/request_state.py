"""Pure session-only transitions; no provider dispatch, persistence or analytical queries."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal
from uuid import uuid4

from pydantic import Field

from airport_analytics.analytics.question_validation import validate_question
from airport_analytics.models import (
    ExplorationModel,
    FieldProvenance,
    IntentProposalV2,
    RequestDraft,
    RequestedSection,
    ResolvedInterpretation,
    SafeFailure,
    SnapshotBinding,
)

PENDING_REQUEST_KEY = "exploration_request"


class AnswerEvent(ExplorationModel):
    session_binding: str
    request_id: str
    revision: int = Field(strict=True, ge=1)
    section_id: str
    question_id: str
    choice_id: str | None = None
    text: str | None = None


@dataclass(frozen=True)
class ExplorationRequest:
    draft: RequestDraft
    proposal: IntentProposalV2 | None = None
    previous: ResolvedInterpretation | None = None
    question_id: str = ""
    resume_state: Literal[
        "unresolved", "clarification_pending", "guided_correction", "resolved"
    ] = "unresolved"

    @property
    def active_section(self) -> RequestedSection:
        return next(
            (section for section in self.draft.sections if section.status == "unresolved"),
            self.draft.sections[0],
        )


def _draft(request: ExplorationRequest, **changes: object) -> RequestDraft:
    return RequestDraft.model_validate(request.draft.model_dump(mode="json") | changes)


def begin_request(
    question: object,
    session_id: str,
    snapshot_id: str,
    context_id: str,
    previous: ResolvedInterpretation | None = None,
) -> ExplorationRequest:
    return ExplorationRequest(
        draft=RequestDraft(
            original_question=validate_question(question),
            session_binding=session_id,
            revision=previous.revision + 1 if previous else 1,
            snapshot_binding=SnapshotBinding(snapshot_id=snapshot_id, context_id=context_id),
        ),
        previous=previous,
        question_id=str(uuid4()),
    )


def bind_proposal(
    state: ExplorationRequest,
    proposal: IntentProposalV2,
    *,
    answered: bool = False,
) -> ExplorationRequest:
    if state.draft.state not in {"unresolved", "clarification_pending", "guided_correction"}:
        raise ValueError("This request cannot receive a new interpretation.")
    proposal = IntentProposalV2.model_validate(proposal.model_dump(mode="json"))
    if proposal.status == "requires_selection":
        return replace(state, proposal=proposal, draft=_draft(state, state="guided_correction"))
    sections = []
    active_id = state.active_section.section_id
    for index, candidate in enumerate(proposal.sections):
        old = state.draft.sections[index] if index < len(state.draft.sections) else None
        sections.append(
            RequestedSection(
                section_id=old.section_id if old else str(uuid4()),
                position=candidate.position,
                original_clause=(
                    old.original_clause
                    if answered and old is not None
                    else candidate.original_clause
                ),
                status="resolved" if candidate.status == "proposed" else "unresolved",
                answered_turns=(old.answered_turns if old else 0)
                + (1 if answered and old is not None and old.section_id == active_id else 0),
                clarification=candidate.clarification,
                choices=[
                    *(old.choices if old else []),
                    *(
                        [
                            FieldProvenance(
                                source="clarification",
                                revision=state.draft.revision + 1,
                                choice=old.clarification.field_id,
                            )
                        ]
                        if answered
                        and old is not None
                        and old.section_id == active_id
                        and old.clarification is not None
                        else []
                    ),
                ],
            )
        )
    unresolved = next((s for s in sections if s.status == "unresolved"), None)
    phase = (
        "resolved"
        if unresolved is None
        else "guided_correction"
        if unresolved.answered_turns == 3 or unresolved.clarification is None
        else "clarification_pending"
    )
    return replace(
        state,
        proposal=proposal,
        question_id=str(uuid4()),
        draft=_draft(
            state,
            sections=sections,
            state=phase,
            revision=state.draft.revision + int(answered),
            last_failure=None,
            shared_scope=proposal.shared_scope,
        ),
    )


def validate_answer(
    state: ExplorationRequest,
    event: AnswerEvent,
    session_id: str,
) -> AnswerEvent:
    event = AnswerEvent.model_validate(event.model_dump())
    if state.draft.state != "clarification_pending":
        raise ValueError("No clarification answer is currently accepted.")
    if (
        session_id != state.draft.session_binding
        or event.session_binding != session_id
        or event.request_id != state.draft.request_id
        or event.revision != state.draft.revision
        or event.section_id != state.active_section.section_id
        or event.question_id != state.question_id
    ):
        raise ValueError("This clarification is stale or belongs to another session.")
    spec = state.active_section.clarification
    if spec is None:
        raise ValueError("There is no focused clarification question.")
    if (event.choice_id is None) == (event.text is None):
        raise ValueError("Submit one choice or one free-text answer.")
    if event.choice_id is not None:
        if event.choice_id not in {choice.choice_id for choice in spec.choices}:
            raise ValueError("Select a currently offered choice.")
    else:
        event = event.model_copy(update={"text": validate_question(event.text)})
    return event


def remove_pending_section(
    state: ExplorationRequest,
    section_id: str,
    *,
    session_id: str,
    request_id: str,
    revision: int,
) -> ExplorationRequest:
    from airport_analytics.models import RemovedSection

    if (
        session_id != state.draft.session_binding
        or request_id != state.draft.request_id
        or revision != state.draft.revision
        or state.proposal is None
        or state.draft.state not in {"clarification_pending", "guided_correction", "resolved"}
    ):
        raise ValueError("Section removal is stale or belongs to another session.")
    matches = [item for item in state.draft.sections if item.section_id == section_id]
    if len(matches) != 1 or len(state.draft.sections) <= 1:
        raise ValueError("Retain at least one requested section, or cancel the request.")
    position = matches[0].position
    sections = [
        item.model_copy(update={"position": index})
        for index, item in enumerate(
            [item for item in state.draft.sections if item.section_id != section_id],
            1,
        )
    ]
    candidates = [
        item.model_copy(update={"position": index})
        for index, item in enumerate(
            [item for item in state.proposal.sections if item.position != position],
            1,
        )
    ]
    status = (
        "unsupported"
        if any(item.status == "unsupported" for item in candidates)
        else "needs_clarification"
        if any(item.status == "needs_clarification" for item in candidates)
        else "proposed"
    )
    proposal = IntentProposalV2.model_validate(
        state.proposal.model_dump()
        | {
            "sections": candidates,
            "status": status,
        }
    )
    updated = replace(
        state,
        draft=_draft(
            state,
            sections=sections,
            revision=revision + 1,
            state="unresolved",
            removed_sections=[
                *state.draft.removed_sections,
                RemovedSection(
                    section_id=section_id,
                    label=matches[0].original_clause,
                    reason="analyst_removed",
                ),
            ],
        ),
    )
    return bind_proposal(updated, proposal)


def fail_request(state: ExplorationRequest, failure: SafeFailure) -> ExplorationRequest:
    phase = state.draft.state
    resume = (
        phase
        if phase
        in {
            "unresolved",
            "clarification_pending",
            "guided_correction",
            "resolved",
        }
        else "resolved"
    )
    return replace(
        state,
        resume_state=resume,
        draft=_draft(state, state="failed", last_failure=failure),
    )


def retry_request(state: ExplorationRequest, session_id: str) -> ExplorationRequest:
    if state.draft.state != "failed" or state.draft.session_binding != session_id:
        raise ValueError("Only this session's failed request can be explicitly retried.")
    return replace(
        state,
        question_id=str(uuid4()),
        draft=_draft(
            state,
            state=state.resume_state,
            revision=state.draft.revision + 1,
            last_failure=None,
        ),
    )


def stop_request(
    state: ExplorationRequest,
    phase: Literal["cancelled", "superseded"],
) -> ExplorationRequest:
    return replace(state, question_id=str(uuid4()), draft=_draft(state, state=phase))


def start_execution(state: ExplorationRequest) -> ExplorationRequest:
    if state.draft.state != "resolved":
        raise ValueError("Every section must resolve before analytical execution.")
    return replace(state, draft=_draft(state, state="executing"))


def finish_execution(
    state: ExplorationRequest,
    phase: Literal["completed", "incomplete", "failed"],
) -> ExplorationRequest:
    if state.draft.state != "executing":
        raise ValueError("Only an executing request can finish.")
    sections = [
        section.model_copy(update={"status": "completed"}) if phase == "completed" else section
        for section in state.draft.sections
    ]
    return replace(state, draft=_draft(state, state=phase, sections=sections))
