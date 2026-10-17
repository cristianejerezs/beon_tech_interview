"""Validated domain models shared across application boundaries."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AnalysisStatus = Literal["ready", "needs_clarification", "unsupported"]
AnalysisIntent = Literal["aggregate", "compare", "trend", "distribution", "records"]
FilterOperator = Literal["eq", "neq", "in", "gt", "gte", "lt", "lte", "between"]
ChartIntent = Literal["bar", "line", "histogram", "table", "map"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisFilter(StrictModel):
    field_id: str = Field(min_length=1)
    operator: FilterOperator
    value: Any


class TimeRange(StrictModel):
    start: date | None
    end: date | None

    @model_validator(mode="after")
    def validate_order(self) -> TimeRange:
        if self.start and self.end and self.start > self.end:
            raise ValueError("Time-range start must not be after end.")
        return self


class SortSpec(StrictModel):
    field_id: str = Field(min_length=1)
    direction: Literal["asc", "desc"]


class AnalysisPlan(StrictModel):
    status: AnalysisStatus
    intent: AnalysisIntent | None
    metric_id: str | None
    group_by: list[str] = Field(max_length=4)
    filters: list[AnalysisFilter] = Field(max_length=12)
    time_range: TimeRange | None
    sort: SortSpec | None
    row_limit: int = Field(ge=1, le=500)
    chart_intent: ChartIntent | None
    clarification_question: str | None = Field(max_length=500)
    unsupported_reason: str | None = Field(max_length=500)

    @model_validator(mode="after")
    def validate_outcome(self) -> AnalysisPlan:
        if self.status == "ready":
            if (
                self.intent is None
                or self.metric_id is None
                or self.clarification_question is not None
                or self.unsupported_reason is not None
            ):
                raise ValueError("A ready plan requires intent and metric only.")
        elif self.status == "needs_clarification":
            if not self.clarification_question or self.unsupported_reason is not None:
                raise ValueError("A clarification plan requires one focused question.")
        elif self.clarification_question is not None or not self.unsupported_reason:
            raise ValueError("An unsupported plan requires a reason, not a clarification.")
        return self


class DatasetSnapshot(StrictModel):
    snapshot_id: str
    dataset_name: str
    relative_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_count: int = Field(ge=0)
    headers: list[str]
    schema_version: str
    missingness: dict[str, float]
    join_key_coverage: dict[str, float]
    validated_at: str


class ReportContent(StrictModel):
    report_id: str
    analyst_id: str
    session_id: str
    question: str = Field(min_length=1, max_length=2000)
    analysis_plan: AnalysisPlan
    result_payload: dict[str, Any]
    narrative: str
    definitions: dict[str, str]
    limitations: list[str]
    snapshot_id: str
    created_at: str


class SharedArtifact(StrictModel):
    artifact_id: str
    source_report_id: str
    consent_event_id: str
    purpose: Literal["faq", "system_improvement"]
    content: dict[str, Any]
    created_at: str


class ProviderUsage(StrictModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    provider_request_id: str | None = None
    acceptance_confirmed: bool | None = None
