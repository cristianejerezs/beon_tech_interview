from types import SimpleNamespace

import pytest

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.plan_schema import validate_analysis_plan
from airport_analytics.errors import DatasetUnavailableError
from airport_analytics.reports.generation import ReportGenerator


class StubModelClient:
    def __init__(self, plan) -> None:
        self.plan = plan

    def generate_plan(self, *args, **kwargs):
        return SimpleNamespace(plan=self.plan)


class UnexpectedExecutor:
    def execute(self, plan):
        raise AssertionError("Non-ready plans must not execute.")


def _outcome_plan(status: str):
    return validate_analysis_plan(
        {
            "status": status,
            "intent": "aggregate" if status == "ready" else None,
            "metric_id": "flight_count" if status == "ready" else None,
            "group_by": [],
            "filters": [],
            "time_range": None,
            "sort": None,
            "row_limit": 10,
            "chart_intent": "table" if status == "ready" else None,
            "clarification_question": (
                "Which delay measure do you mean?" if status == "needs_clarification" else None
            ),
            "unsupported_reason": (
                "Live gate capacity is not in the supplied data."
                if status == "unsupported"
                else None
            ),
        }
    )


@pytest.mark.parametrize(
    ("status", "expected_outcome"),
    [
        ("needs_clarification", "needs_clarification"),
        ("unsupported", "unsupported"),
    ],
)
def test_unclear_and_unavailable_questions_do_not_execute(
    status: str, expected_outcome: str
) -> None:
    generator = ReportGenerator(StubModelClient(_outcome_plan(status)), UnexpectedExecutor())

    outcome = generator.generate(
        "Tell me about airport operations",
        analyst_id="analyst",
        session_id="session",
        session_state={},
    )

    assert outcome.status == expected_outcome
    assert outcome.report is None


def test_empty_supported_result_is_not_reported_as_zero() -> None:
    class EmptyExecutor:
        def execute(self, plan):
            return SimpleNamespace(rows=(), columns=())

    generator = ReportGenerator(
        StubModelClient(_outcome_plan("ready")),
        EmptyExecutor(),
    )
    outcome = generator.generate(
        "How many flights match this scope?",
        analyst_id="analyst",
        session_id="session",
        session_state={},
    )

    assert outcome.status == "empty"
    assert outcome.report is None
    assert "No records match" in outcome.message


def test_missing_source_data_fails_with_an_explicit_dataset_error(tmp_path) -> None:
    with pytest.raises(DatasetUnavailableError):
        DuckDBExecutor(str(tmp_path / "missing-source-data"))
