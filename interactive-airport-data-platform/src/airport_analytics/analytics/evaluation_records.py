"""Strict synthetic evaluation records, separate from operational telemetry."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from airport_analytics.data.catalog import EXPLORATION_FAMILIES


class EvaluationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class CorpusCase(EvaluationRecord):
    case_id: str = Field(min_length=1)
    corpus_version: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=2000)
    family: str = Field(min_length=1)
    partition: Literal["development", "candidate_held_out", "frozen_held_out"]
    category: Literal["unambiguous", "negative", "airport_question", "composite"]
    expected_outcome: Literal["report", "needs_clarification", "unsupported", "requires_selection"]
    interpretation_reference: str = Field(min_length=1)
    result_reference: str | None
    review_reference: str | None = None
    airport_question_id: (
        Literal[
            "AQ-01",
            "AQ-02",
            "AQ-03",
            "AQ-04",
            "AQ-05",
            "AQ-06",
            "AQ-07",
            "AQ-08",
            "AQ-09",
            "AQ-10",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def require_gold(self):
        if self.category == "unambiguous" and self.family not in set().union(
            *EXPLORATION_FAMILIES.values()
        ):
            raise ValueError("Unambiguous evaluation cases must use an approved analytical family.")
        if self.expected_outcome == "report" and not self.result_reference:
            raise ValueError("Every report case needs independent numerical gold.")
        if self.partition == "frozen_held_out" and not self.review_reference:
            raise ValueError("Held-out claims require independent frozen review provenance.")
        if (self.category == "airport_question") != (self.airport_question_id is not None):
            raise ValueError("Each airport-question variant must identify its AQ-01..10 family.")
        return self


class ReviewRecord(EvaluationRecord):
    review_id: str = Field(min_length=1)
    corpus_version: str = Field(min_length=1)
    case_ids: list[str] = Field(min_length=1)
    reviewer_labels: dict[str, dict[str, str]] = Field(min_length=2)
    agreement_count: int = Field(ge=0)
    disputes: list[str]
    adjudicator: str | None
    adjudication: dict[str, str]
    frozen_at: AwareDatetime | None
    corpus_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    independent_human_review: bool

    @model_validator(mode="after")
    def freeze_gate(self):
        if len(set(self.case_ids)) != len(self.case_ids):
            raise ValueError("Review cases must be unique.")
        if any(set(labels) != set(self.case_ids) for labels in self.reviewer_labels.values()):
            raise ValueError("Each reviewer must independently label every case.")
        if any(
            not reviewer.strip() or any(not value.strip() for value in labels.values())
            for reviewer, labels in self.reviewer_labels.items()
        ):
            raise ValueError("Reviewers and independent labels must be nonempty.")
        if self.agreement_count + len(self.disputes) != len(self.case_ids):
            raise ValueError("Agreement and disputes must reconcile.")
        if not set(self.disputes).issubset(self.case_ids):
            raise ValueError("Disputes must identify reviewed cases.")
        actual_disputes = {
            case_id
            for case_id in self.case_ids
            if len({labels[case_id] for labels in self.reviewer_labels.values()}) != 1
        }
        if len(set(self.disputes)) != len(self.disputes) or set(self.disputes) != actual_disputes:
            raise ValueError("Disputes must match actual independent label disagreements.")
        if not set(self.adjudication).issubset(actual_disputes) or any(
            not value.strip() for value in self.adjudication.values()
        ):
            raise ValueError("Adjudication must label disputed cases only.")
        if self.frozen_at is not None and (
            not self.independent_human_review
            or (
                self.disputes
                and (not self.adjudicator or set(self.adjudication) != set(self.disputes))
            )
        ):
            raise ValueError("Freeze requires independent human review and resolved disputes.")
        return self


class EvaluationCaseResult(EvaluationRecord):
    case_id: str
    status: Literal["passed", "failed"]
    comparison_category: Literal[
        "match",
        "interpretation_mismatch",
        "numeric_mismatch",
        "outcome_mismatch",
        "execution_failure",
    ]
    absolute_errors: list[float] = Field(default_factory=list)
    generated_result: bool
    seconds: float = Field(ge=0)
    stage_seconds: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def nonnegative_errors(self):
        if any(value < 0 for value in self.absolute_errors):
            raise ValueError("Absolute errors cannot be negative.")
        if any(value < 0 for value in self.stage_seconds.values()):
            raise ValueError("Stage timings cannot be negative.")
        return self


class EvaluationRun(EvaluationRecord):
    run_id: str
    corpus_version: str
    source_snapshot: str = Field(pattern="^[a-f0-9]{64}$")
    context_id: str = Field(pattern="^[a-f0-9]{64}$")
    versions: dict[str, str]
    provider: str
    model: str
    settings: dict[str, str | int | float | bool]
    environment: dict[str, str]
    started_at: AwareDatetime
    attempted_case_ids: list[str]
    cases: list[EvaluationCaseResult]
    stage_seconds: dict[str, float]
    thermal_state: Literal["cold", "warm"]

    @model_validator(mode="after")
    def reconcile_attempts(self):
        if (
            len(set(self.attempted_case_ids)) != len(self.attempted_case_ids)
            or [item.case_id for item in self.cases] != self.attempted_case_ids
        ):
            raise ValueError("Every attempted case, including failures, needs one ordered result.")
        if any(value < 0 for value in self.stage_seconds.values()):
            raise ValueError("Stage timings cannot be negative.")
        return self
