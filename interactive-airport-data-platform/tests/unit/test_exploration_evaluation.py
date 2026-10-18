import pytest
from pydantic import ValidationError

from airport_analytics.models import CorpusCase, ReviewRecord


def test_frozen_corpus_requires_review_and_numerical_gold():
    payload = dict(
        case_id="synthetic",
        corpus_version="candidate-1",
        text="How many flights?",
        family="overall_summary",
        partition="development",
        category="unambiguous",
        expected_outcome="report",
        interpretation_reference="scope-1",
        result_reference="rows-1",
    )
    CorpusCase(**payload)
    with pytest.raises(ValidationError):
        CorpusCase(**(payload | {"result_reference": None}))
    with pytest.raises(ValidationError):
        CorpusCase(**(payload | {"partition": "frozen_held_out"}))
    with pytest.raises(ValidationError):
        CorpusCase(**(payload | {"family": "invented_family"}))
    with pytest.raises(ValidationError):
        CorpusCase(**(payload | {"category": "airport_question"}))


def test_evaluation_cli_never_dispatches_without_explicit_live_flag(monkeypatch, capsys):
    import sys

    from airport_analytics.analytics import evaluation

    monkeypatch.setattr(sys, "argv", ["evaluation", "--suite", "v2"])
    monkeypatch.setattr(
        evaluation, "LangChainPlanClient", lambda *args, **kwargs: pytest.fail("Dispatch")
    )
    with pytest.raises(SystemExit) as error:
        evaluation.main()
    assert error.value.code == 2
    assert "--run-live is required" in capsys.readouterr().err


def test_agent_review_cannot_freeze_independent_gold():
    from datetime import UTC, datetime

    payload = dict(
        review_id="candidate",
        corpus_version="candidate-1",
        case_ids=["one"],
        reviewer_labels={"author": {"one": "plan1"}, "agent": {"one": "plan1"}},
        agreement_count=1,
        disputes=[],
        adjudicator=None,
        adjudication={},
        frozen_at=None,
        corpus_sha256="a" * 64,
        independent_human_review=False,
    )
    ReviewRecord(**payload)
    with pytest.raises(ValidationError):
        ReviewRecord(**(payload | {"frozen_at": datetime.now(UTC)}))


def test_numeric_scoring_checks_finite_tolerance_and_all_shape_values():
    from airport_analytics.analytics.evaluation import compare_values

    assert compare_values({"n": 3, "v": None}, {"n": 3, "v": None})[0]
    assert not compare_values({"n": 4}, {"n": 3})[0]
    assert not compare_values(0.0, None)[0]
    assert compare_values(1.0 + 5e-10, 1.0)[0]
    matches, errors = compare_values(1.0 + 2e-9, 1.0)
    assert not matches
    assert errors[0] > 1e-9
    assert not compare_values(float("nan"), 1.0)[0]


def test_shape_mismatch_still_scores_all_available_numeric_sections():
    from airport_analytics.analytics.evaluation import compare_values

    matches, errors = compare_values([{"value": 7.0}], [{"value": 2.0}, {"value": 9.0}])
    assert not matches
    assert errors == [5.0]
    assert compare_values(8, 5) == (False, [3.0])
    assert not compare_values(True, 1)[0]


def test_review_disputes_must_match_actual_independent_labels():
    payload = dict(
        review_id="candidate",
        corpus_version="candidate-1",
        case_ids=["one"],
        reviewer_labels={"reviewer-a": {"one": "plan1"}, "reviewer-b": {"one": "plan2"}},
        agreement_count=1,
        disputes=[],
        adjudicator=None,
        adjudication={},
        frozen_at=None,
        corpus_sha256="a" * 64,
        independent_human_review=False,
    )
    with pytest.raises(ValidationError, match="disagreements"):
        ReviewRecord(**payload)
    valid = ReviewRecord(**(payload | {"agreement_count": 0, "disputes": ["one"]}))
    assert valid.frozen_at is None


def test_evaluation_run_records_every_attempt_and_finite_nonnegative_timing():
    from datetime import UTC, datetime

    from airport_analytics.models import EvaluationRun

    payload = dict(
        run_id="synthetic-only",
        corpus_version="development-1",
        source_snapshot="a" * 64,
        context_id="b" * 64,
        versions={"python": "3.12"},
        provider="synthetic",
        model="stub",
        settings={},
        environment={"platform": "synthetic"},
        started_at=datetime.now(UTC),
        attempted_case_ids=["failed-case"],
        cases=[
            {
                "case_id": "failed-case",
                "status": "failed",
                "comparison_category": "execution_failure",
                "absolute_errors": [],
                "generated_result": False,
                "seconds": 0.1,
            }
        ],
        stage_seconds={"interpretation": 0.1},
        thermal_state="cold",
    )
    EvaluationRun(**payload)
    for change in [
        {"attempted_case_ids": []},
        {"attempted_case_ids": ["failed-case", "failed-case"]},
        {"stage_seconds": {"interpretation": -1.0}},
        {"stage_seconds": {"interpretation": float("inf")}},
    ]:
        with pytest.raises(ValidationError):
            EvaluationRun(**(payload | change))


def test_wrong_scope_still_records_the_actual_numeric_error():
    from types import SimpleNamespace

    from airport_analytics.analytics.evaluation import (
        canonical_interpretation,
        evaluate_exploration,
    )
    from airport_analytics.analytics.execution import DuckDBExecutor
    from airport_analytics.reports.generation import ExplorationReportGenerator
    from airport_analytics.reports.rendering import section_evidence
    from tests.integration.test_exploration_summaries import FIXTURES, SummaryClient

    with DuckDBExecutor(str(FIXTURES)) as executor:
        outcome = ExplorationReportGenerator(SummaryClient(), executor).generate(
            "Count flights",
            analyst_id="evaluation-only",
            session_id="evaluation",
            session_state={},
        )
    interpreted = canonical_interpretation(outcome.interpretations[0])
    expected = section_evidence(outcome.report.sections[0]).model_dump(
        mode="json",
        exclude={"report_id", "section_id", "snapshot_id", "context_id"},
    )
    actual_value = expected["value"]["value"]
    expected["value"]["value"] = actual_value + 2.0
    case = CorpusCase(
        case_id="synthetic-score",
        corpus_version="development-1",
        text="Count flights",
        family="overall_summary",
        partition="development",
        category="unambiguous",
        expected_outcome="report",
        interpretation_reference="scope",
        result_reference="numbers",
    )
    scored = evaluate_exploration(
        SimpleNamespace(generate=lambda *args, **kwargs: outcome),
        [case],
        {"scope": [interpreted | {"grouping": ["origin"]}], "numbers": [expected]},
        session_state={},
    )
    assert scored[0].comparison_category == "interpretation_mismatch"
    assert 2.0 in scored[0].absolute_errors
    assert scored[0].status == "failed"
