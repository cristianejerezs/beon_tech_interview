import pytest

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.errors import QueryExecutionError
from airport_analytics.models import IntentProposalV2
from airport_analytics.reports.generation import ExplorationReportGenerator
from tests.integration.test_exploration_summaries import FIXTURES, SummaryClient
from tests.unit.test_exploration_contracts import proposed_section


def composite_client():
    client = SummaryClient()
    client.proposal = IntentProposalV2.model_validate(
        {
            "intent_version": 2,
            "status": "proposed",
            "shared_scope": {},
            "selection_reason": None,
            "sections": [
                proposed_section(position=index, original_clause=f"Analysis {index}")
                for index in range(1, 5)
            ],
        }
    )
    return client


def test_four_sections_preserve_order_and_one_snapshot():
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = ExplorationReportGenerator(composite_client(), executor).generate(
            "Four related analyses",
            analyst_id="owner",
            session_id="session",
            session_state={},
        )
    assert result.report is not None, result.message
    assert len(result.report.sections) == 4
    assert [section.position for section in result.report.sections] == [1, 2, 3, 4]
    assert len({section.section_id for section in result.report.sections}) == 4
    assert result.report.completeness == "complete"


def test_later_section_resolution_error_retains_every_requested_section(monkeypatch):
    from airport_analytics.analytics.request_state import PENDING_REQUEST_KEY
    from airport_analytics.models import IntentProposalV2

    client = composite_client()
    payload = client.proposal.model_dump()
    payload["sections"][2]["entity_mentions"] = [
        {"kind": "origin", "text": "unknown airport", "code_candidate": None}
    ]
    client.proposal = IntentProposalV2.model_validate(payload)
    state = {}
    with DuckDBExecutor(str(FIXTURES)) as executor:
        monkeypatch.setattr(executor, "execute_summary", lambda _: pytest.fail("Unresolved query"))
        result = ExplorationReportGenerator(client, executor).generate(
            "Four related analyses",
            analyst_id="owner",
            session_id="session",
            session_state=state,
        )
    assert result.status == "needs_clarification"
    assert len(state[PENDING_REQUEST_KEY].proposal.sections) == 4
    assert state[PENDING_REQUEST_KEY].active_section.position == 3
    assert [item.status for item in state[PENDING_REQUEST_KEY].proposal.sections] == [
        "proposed",
        "proposed",
        "needs_clarification",
        "proposed",
    ]


@pytest.mark.parametrize("all_sections", [False, True])
def test_explicit_scope_refinement_preserves_untargeted_meaning_without_model_calls(all_sections):
    from airport_analytics.models import ScopeEdit
    from tests.exploration_oracles import read_rows

    client = composite_client()
    with DuckDBExecutor(str(FIXTURES)) as executor:
        generator = ExplorationReportGenerator(client, executor)
        original = generator.generate(
            "Four counts",
            analyst_id="owner",
            session_id="session",
            session_state={},
        ).report
        ids = {section.section_id for section in original.sections}
        target = ids if all_sections else {original.sections[2].section_id}
        changed = generator.refine_scope(
            original,
            section_ids=target,
            edits=[ScopeEdit(field_id="origin", action="replace", operator="eq", value="JFK")],
            replace_dates=False,
            date_scope=None,
            analyst_id="owner",
            session_id="session",
        ).report
    assert client.calls == 1
    expected = sum(row["origin"] == "JFK" for row in read_rows(FIXTURES / "nyc_flights_fixed.csv"))
    assert {section.section_id for section in changed.sections} == ids
    for old, new in zip(original.sections, changed.sections, strict=True):
        assert new.interpretation.revision == original.revision + 1
        if new.section_id in target:
            assert new.outcome.result.value.value == expected
            assert new.interpretation.field_provenance["filters"].source == "correction"
        else:
            assert new.interpretation.filters == old.interpretation.filters
            assert new.outcome.result.value == old.outcome.result.value
    assert changed.parent_report_id == original.report_id


def test_guided_correction_only_replaces_focused_composite_section():
    from airport_analytics.analytics.request_state import PENDING_REQUEST_KEY
    from airport_analytics.models import IntentProposalV2

    client = composite_client()
    payload = client.proposal.model_dump()
    payload["sections"][2]["entity_mentions"] = [
        {"kind": "origin", "text": "unknown airport", "code_candidate": None},
    ]
    client.proposal = IntentProposalV2.model_validate(payload)
    state = {}
    with DuckDBExecutor(str(FIXTURES)) as executor:
        generator = ExplorationReportGenerator(client, executor)
        generator.generate(
            "Four counts", analyst_id="owner", session_id="session", session_state=state
        )
        pending = state[PENDING_REQUEST_KEY]
        ids = [section.section_id for section in pending.draft.sections]
        correction = IntentProposalV2.model_validate(
            {
                "intent_version": 2,
                "status": "proposed",
                "shared_scope": {},
                "selection_reason": None,
                "sections": [proposed_section()],
            }
        )
        changed = generator.correct_pending(
            pending,
            correction,
            analyst_id="owner",
            session_id="session",
            session_state=state,
        ).report
    assert client.calls == 1
    assert [section.section_id for section in changed.sections] == ids
    assert [section.label for section in changed.sections] == [f"Analysis {i}" for i in range(1, 5)]
    assert [
        section.interpretation.field_provenance["measure_ids"].source
        for section in changed.sections
    ] == ["explicit", "explicit", "correction", "explicit"]


def test_all_failed_sections_never_become_a_success_report(monkeypatch):
    with DuckDBExecutor(str(FIXTURES)) as executor:

        def fail(_):
            raise QueryExecutionError()

        monkeypatch.setattr(executor, "execute_summary", fail)
        with pytest.raises(QueryExecutionError):
            ExplorationReportGenerator(composite_client(), executor).generate(
                "Four counts",
                analyst_id="owner",
                session_id="session",
                session_state={},
            )


def test_runtime_fault_retains_failed_section_and_requires_acknowledgement(monkeypatch):
    with DuckDBExecutor(str(FIXTURES)) as executor:
        original = executor.execute_summary
        calls = 0

        def execute(interpretation):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise QueryExecutionError()
            return original(interpretation)

        monkeypatch.setattr(executor, "execute_summary", execute)
        result = ExplorationReportGenerator(composite_client(), executor).generate(
            "Four related analyses",
            analyst_id="owner",
            session_id="session",
            session_state={},
        )
        assert result.report.completeness == "incomplete"
        assert result.report.sections[1].outcome.status == "failed"
        with pytest.raises(ValueError, match="acknowledgement"):
            result.report.require_persistable()


def test_later_bin_eligibility_blocks_all_main_sections_before_execution(tmp_path, monkeypatch):
    import csv

    from airport_analytics.errors import BinWidthRequiredError
    from tests.exploration_oracles import read_rows
    from tests.integration.test_exploration_browsing import copy_flights

    source = copy_flights(tmp_path, 2)
    path = source / "nyc_flights_fixed.csv"
    rows = read_rows(path)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(row | {"dep_delay": index * 1500} for index, row in enumerate(rows))
    client = composite_client()
    payload = client.proposal.model_dump()
    payload["sections"][3].update(
        family="distribution",
        operation_id="distribution",
        measure_ids=["departure_delay"],
    )
    client.proposal = IntentProposalV2.model_validate(payload)
    with DuckDBExecutor(str(source)) as executor:
        monkeypatch.setattr(
            executor, "execute_summary", lambda _: pytest.fail("Premature main query")
        )
        with pytest.raises(BinWidthRequiredError) as failure:
            ExplorationReportGenerator(client, executor).generate(
                "Three summaries and a distribution",
                analyst_id="owner",
                session_id="session",
                session_state={},
            )
    assert failure.value.suggested_width == 30.0


def test_explicit_section_removal_invalidates_stale_answer_and_retains_identity():
    from airport_analytics.analytics.request_state import (
        begin_request,
        bind_proposal,
        remove_pending_section,
    )
    from airport_analytics.models import IntentProposalV2
    from tests.integration.test_exploration_clarification import ClarificationClient

    with DuckDBExecutor(str(FIXTURES)) as executor:
        client = ClarificationClient()
        payload = client.proposal.model_dump()
        payload["sections"].append(
            proposed_section(position=2, original_clause="Keep this analysis")
        )
        proposal = IntentProposalV2.model_validate(payload)
        state = bind_proposal(
            begin_request(
                "Two analyses",
                "session",
                executor.manifest.snapshot_id,
                executor.context.context_id,
            ),
            proposal,
        )
        removed_id, kept_id = [section.section_id for section in state.draft.sections]
        changed = remove_pending_section(
            state,
            removed_id,
            session_id="session",
            request_id=state.draft.request_id,
            revision=state.draft.revision,
        )
        assert changed.draft.sections[0].section_id == kept_id
        assert changed.draft.removed_sections[0].section_id == removed_id
        assert changed.draft.state == "resolved"
        assert changed.question_id != state.question_id
        with pytest.raises(ValueError, match="stale"):
            remove_pending_section(
                changed,
                kept_id,
                session_id="session",
                request_id=state.draft.request_id,
                revision=state.draft.revision,
            )
