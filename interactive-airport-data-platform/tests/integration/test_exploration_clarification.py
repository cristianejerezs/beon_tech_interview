from dataclasses import replace
from types import SimpleNamespace

import pytest

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.request_state import PENDING_REQUEST_KEY
from airport_analytics.errors import DatasetUnavailableError, InvalidPlanError, ProviderTimeoutError
from airport_analytics.models import IntentProposalV2, ScopeEdit
from airport_analytics.reports.generation import ExplorationReportGenerator
from tests.integration.test_exploration_summaries import FIXTURES
from tests.unit.test_exploration_interpretation import proposal
from tests.unit.test_exploration_state import ambiguous, event


class ClarificationClient:
    def __init__(self):
        self.proposal = ambiguous()
        self.calls = 0
        self.answer_proposal = proposal(
            scope_edits=[
                {
                    "field_id": "origin",
                    "action": "replace",
                    "operator": "eq",
                    "value": "JFK",
                }
            ],
        )
        self.failure = None

    def generate_intent(self, *args, **kwargs):
        self.calls += 1
        return SimpleNamespace(proposal=self.proposal)

    def generate_clarification(self, *args, **kwargs):
        self.calls += 1
        if self.failure:
            raise self.failure
        return SimpleNamespace(proposal=self.answer_proposal)


def begin(executor, client):
    session = {}
    generator = ExplorationReportGenerator(client, executor)
    result = generator.generate(
        "Count flights at the airport",
        analyst_id="owner",
        session_id="session",
        session_state=session,
    )
    assert result.status == "needs_clarification"
    return generator, session


def answer(generator, session, **changes):
    state = session[PENDING_REQUEST_KEY]
    return generator.answer(
        state,
        event(state, **changes),
        analyst_id="owner",
        session_id="session",
        session_state=session,
    )


def test_answer_computes_once_after_resolution_and_preserves_resolved_scope(monkeypatch):
    client = ClarificationClient()
    client.proposal.shared_scope.edits = [
        ScopeEdit(field_id="carrier", action="add", operator="eq", value="BB"),
    ]
    # A provider cannot silently remove a retained carrier filter or change the measure.
    client.answer_proposal = proposal(
        measure_ids=["mean_distance"],
        family="grouped_summary",
        grouping=["origin"],
        scope_edits=[
            {"field_id": "origin", "action": "replace", "operator": "eq", "value": "JFK"},
            {"field_id": "carrier", "action": "remove", "operator": None, "value": None},
        ],
    )
    with DuckDBExecutor(str(FIXTURES)) as executor:
        batches = []
        real = executor.execute_summary

        def execute(interpretation):
            batches.append(interpretation)
            return real(interpretation)

        monkeypatch.setattr(executor, "execute_summary", execute)
        generator, session = begin(executor, client)
        assert not batches
        outcome = answer(generator, session)
        assert len(batches) == 1
        assert outcome.report.question == "Count flights at the airport"
        interpretation = outcome.report.sections[0].interpretation
        assert interpretation.measure_ids == ["flight_count"]
        assert interpretation.grouping == []
        assert {(item.field_id, item.value) for item in interpretation.filters} == {
            ("origin", "JFK"),
            ("carrier", "BB"),
        }
        assert outcome.report.sections[0].outcome.result.value.value == 3
        assert interpretation.field_provenance["filters"].source == "clarification"
        assert client.calls == 2


@pytest.mark.parametrize("failure", [ProviderTimeoutError(), InvalidPlanError()])
def test_failed_clarification_is_not_an_answer_and_retry_requires_resubmission(failure):
    client = ClarificationClient()
    with DuckDBExecutor(str(FIXTURES)) as executor:
        generator, session = begin(executor, client)
        state = session[PENDING_REQUEST_KEY]
        client.failure = failure
        with pytest.raises(type(failure)):
            answer(generator, session)
        failed = session[PENDING_REQUEST_KEY]
        assert failed.active_section.answered_turns == 0
        assert failed.proposal == state.proposal
        assert failed.draft.state == "failed"
        client.failure = None
        generator.retry(
            failed,
            analyst_id="owner",
            session_id="session",
            session_state=session,
        )
        assert client.calls == 2
        assert session[PENDING_REQUEST_KEY].draft.revision > state.draft.revision
        outcome = answer(generator, session)
        assert outcome.status == "report"
        assert client.calls == 3


def test_stale_session_revision_question_and_changed_sources_never_dispatch(monkeypatch):
    client = ClarificationClient()
    with DuckDBExecutor(str(FIXTURES)) as executor:
        generator, session = begin(executor, client)
        original = session[PENDING_REQUEST_KEY]
        for changes in [
            {"revision": 99},
            {"session_binding": "other"},
            {"question_id": "other"},
        ]:
            with pytest.raises(ValueError):
                answer(generator, session, **changes)
        assert client.calls == 1
        session[PENDING_REQUEST_KEY] = replace(original, question_id="new")
        with pytest.raises(ValueError):
            generator.answer(
                original,
                event(original),
                analyst_id="owner",
                session_id="session",
                session_state=session,
            )
        session[PENDING_REQUEST_KEY] = original

        def changed(*args):
            raise DatasetUnavailableError()

        monkeypatch.setattr(executor, "require_current_binding", changed)
        with pytest.raises(DatasetUnavailableError):
            answer(generator, session)
        assert client.calls == 1
        assert session[PENDING_REQUEST_KEY].active_section.answered_turns == 0


def test_multiple_sections_execute_only_after_all_clarifications_resolve(monkeypatch):
    client = ClarificationClient()
    first = client.proposal.model_dump(mode="json")
    second = proposal().sections[0].model_dump(mode="json") | {"position": 2}
    first["sections"].append(second)
    client.proposal = IntentProposalV2.model_validate(first)
    resolved = first | {"status": "proposed"}
    resolved["sections"] = [
        client.answer_proposal.sections[0].model_dump(mode="json"),
        second,
    ]
    client.answer_proposal = IntentProposalV2.model_validate(resolved)
    with DuckDBExecutor(str(FIXTURES)) as executor:
        actual = executor.execute_summary
        calls = []

        def execute(item):
            calls.append(item)
            return actual(item)

        monkeypatch.setattr(executor, "execute_summary", execute)
        generator, session = begin(executor, client)
        assert calls == []
        result = answer(generator, session)
        assert result.status == "report"
        assert len(result.report.sections) == 2
        assert len(calls) == 2
        assert session[PENDING_REQUEST_KEY].draft.state == "completed"
