"""Validated domain models shared across application boundaries."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta
from types import MappingProxyType
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from airport_analytics.data.catalog import (
    FIELDS,
    ExplorationDimension,
    ExplorationMeasure,
    ExplorationOperation,
    exploration_definition,
    validate_exploration_combination,
    validate_exploration_population,
)

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
    grain: list[str] = Field(default_factory=list)
    repeated_observations: int = Field(default=0, ge=0)


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
    cached_input_tokens: int | None = Field(default=None, ge=0)
    provider_request_id: str | None = None
    acceptance_confirmed: bool | None = None


class ExplorationModel(StrictModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_default=True)


NonEmptyText = Annotated[str, Field(min_length=1)]
ContentHash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
PositiveInteger = Annotated[int, Field(strict=True, ge=1)]
NonnegativeInteger = Annotated[int, Field(strict=True, ge=0)]
NumericValue = StrictInt | StrictFloat
CellValue = StrictStr | StrictInt | StrictFloat | None
FilterValue = CellValue | Annotated[list[CellValue], Field(min_length=1, max_length=100)]
FilterField = Literal[
    "origin",
    "destination",
    "carrier",
    "tailnum",
    "airline_name",
    "aircraft_model",
    "flight_year",
    "flight_month_number",
    "departure_delay",
    "arrival_delay",
    "distance",
    "flight_date",
]
RequestFamily = Literal[
    "overall_summary",
    "grouped_summary",
    "unique_entity_list",
    "individual_records",
    "ranking",
    "category_comparison",
    "historical_trend",
    "period_change",
    "distribution",
    "numeric_relationship",
]
RequestState = Literal[
    "unresolved",
    "clarification_pending",
    "guided_correction",
    "resolved",
    "executing",
    "completed",
    "incomplete",
    "failed",
    "cancelled",
    "superseded",
]
FailureCategory = Literal[
    "provider_unavailable",
    "invalid_provider_output",
    "source_unavailable",
    "execution_failed",
    "disclosure_refused",
    "budget_refused",
]


def _question_text(value: str) -> str:
    trimmed = value.strip()
    if not 1 <= len(trimmed) <= 2000:
        raise ValueError("Enter a non-empty question of up to 2,000 Unicode code points.")
    return trimmed


class TypedFilter(ExplorationModel):
    field_id: FilterField
    operator: FilterOperator
    value: FilterValue

    @model_validator(mode="after")
    def validate_value(self) -> TypedFilter:
        values = self.value if isinstance(self.value, list) else [self.value]
        if isinstance(self.value, list) != (self.operator in {"in", "between"}):
            raise ValueError("List filter values require in or between.")
        if not 1 <= len(values) <= 100:
            raise ValueError("A filter list requires 1..100 values.")
        if self.operator == "between" and len(values) != 2:
            raise ValueError("A between filter requires two endpoints.")
        kind = FIELDS[self.field_id].data_type
        if kind == "string" and self.operator not in {"eq", "neq", "in"}:
            raise ValueError("Text filters require equality or membership.")
        for value in values:
            if value is None:
                if self.operator not in {"eq", "neq"}:
                    raise ValueError("Null requires equality.")
                continue
            if kind in {"string", "date"} and not isinstance(value, str):
                raise ValueError("Expected text filter value.")
            if kind == "number" and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                raise ValueError("Expected numeric filter value.")
            if kind == "date":
                parsed = date.fromisoformat(str(value))
                if parsed.isoformat() != value:
                    raise ValueError("Expected ISO YYYY-MM-DD calendar date.")
        if self.operator == "between" and values[0] is not None and values[1] is not None:
            if type(values[0]) is not type(values[1]) and kind != "number":
                raise ValueError("Incompatible interval endpoints.")
            if _compare_values(values[0], values[1]) > 0:
                raise ValueError("Inverted filter interval.")
        return self


def _compare_values(left: CellValue, right: CellValue) -> int:
    if isinstance(left, str) and isinstance(right, str):
        return (left > right) - (left < right)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return (left > right) - (left < right)
    raise ValueError("Interval values require compatible non-null types.")


def _predicate_accepts(predicate: TypedFilter, value: CellValue) -> bool:
    target = predicate.value
    if predicate.operator == "in":
        return isinstance(target, list) and value in target
    if predicate.operator == "eq":
        return value == target
    if predicate.operator == "neq":
        return value != target if target is None else value is not None and value != target
    if value is None:
        return False
    if predicate.operator == "between":
        return (
            isinstance(target, list)
            and _compare_values(value, target[0]) >= 0
            and _compare_values(value, target[1]) <= 0
        )
    if isinstance(target, list):
        raise ValueError("An ordered predicate requires a scalar.")
    comparison = _compare_values(value, target)
    return {
        "gt": comparison > 0,
        "gte": comparison >= 0,
        "lt": comparison < 0,
        "lte": comparison <= 0,
    }[predicate.operator]


def _validate_filter_conjunction(filters: list[TypedFilter]) -> None:
    for field_id in {item.field_id for item in filters}:
        predicates = [item for item in filters if item.field_id == field_id]
        candidates: list[CellValue] | None = None
        lower: tuple[CellValue, bool] | None = None
        upper: tuple[CellValue, bool] | None = None
        for item in predicates:
            if item.operator in {"eq", "in"}:
                values = item.value if isinstance(item.value, list) else [item.value]
                candidates = (
                    values if candidates is None else [v for v in candidates if v in values]
                )
            bounds: list[tuple[str, CellValue, bool]] = []
            if item.operator == "between" and isinstance(item.value, list):
                bounds = [("lower", item.value[0], True), ("upper", item.value[1], True)]
            elif item.operator in {"gt", "gte", "lt", "lte"} and not isinstance(item.value, list):
                bounds = [
                    (
                        "lower" if item.operator in {"gt", "gte"} else "upper",
                        item.value,
                        item.operator in {"gte", "lte"},
                    )
                ]
            for side, value, inclusive in bounds:
                current = lower if side == "lower" else upper
                direction = 1 if side == "lower" else -1
                if current is None or direction * _compare_values(value, current[0]) > 0:
                    current = (value, inclusive)
                elif _compare_values(value, current[0]) == 0:
                    current = (value, inclusive and current[1])
                if side == "lower":
                    lower = current
                else:
                    upper = current
        if candidates is not None:
            if not any(
                all(_predicate_accepts(p, value) for p in predicates) for value in candidates
            ):
                raise ValueError(f"Contradictory filters for {field_id}.")
        elif lower is not None and upper is not None:
            comparison = _compare_values(lower[0], upper[0])
            if comparison > 0 or (comparison == 0 and not (lower[1] and upper[1])):
                raise ValueError(f"Contradictory interval for {field_id}.")
            if comparison == 0 and not all(_predicate_accepts(p, lower[0]) for p in predicates):
                raise ValueError(f"Excluded sole interval value for {field_id}.")


class ScopeEdit(ExplorationModel):
    field_id: FilterField
    action: Literal["add", "replace", "remove"]
    operator: FilterOperator | None
    value: FilterValue

    @model_validator(mode="after")
    def validate_edit(self) -> ScopeEdit:
        if self.action == "remove":
            if self.operator is not None or self.value is not None:
                raise ValueError("Removal carries no replacement predicate.")
        elif self.operator is None:
            raise ValueError("A scope predicate requires an operator.")
        else:
            TypedFilter(field_id=self.field_id, operator=self.operator, value=self.value)
        return self


class ProposedSharedScope(ExplorationModel):
    edits: list[ScopeEdit] = Field(default_factory=list, max_length=12)
    dates: TimeRange | None = None


class RoundingSpec(ExplorationModel):
    places: int = Field(strict=True, ge=0, le=12)
    mode: Literal["half_up"]


class ComparisonSpec(ExplorationModel):
    baseline: TimeRange | None = None
    comparison: TimeRange
    baseline_rule: Literal[
        "explicit",
        "previous_equal_days",
        "previous_month",
        "previous_year",
    ] = "explicit"

    @model_validator(mode="after")
    def baseline_matches_rule(self) -> ComparisonSpec:
        if (self.baseline_rule == "explicit") != (self.baseline is not None):
            raise ValueError(
                "Explicit comparisons require a baseline; relative rules calculate it locally."
            )
        return self


class BinningSpec(ExplorationModel):
    width: StrictFloat = Field(gt=0)
    accepted: bool


class PairingSpec(ExplorationModel):
    x: Literal["departure_delay", "arrival_delay", "distance"]
    y: Literal["departure_delay", "arrival_delay", "distance"]

    @model_validator(mode="after")
    def distinct_variables(self) -> PairingSpec:
        if self.x == self.y:
            raise ValueError("Pair variables must differ.")
        return self


class EntityMention(ExplorationModel):
    kind: Literal["origin", "destination", "airline", "origin_region"]
    text: NonEmptyText
    code_candidate: str | None


class ClarificationChoice(ExplorationModel):
    choice_id: NonEmptyText
    label: NonEmptyText
    edits: list[ScopeEdit] = Field(max_length=12)


class ClarificationSpec(ExplorationModel):
    field_id: NonEmptyText
    question: str = Field(min_length=1, max_length=500)
    choices: list[ClarificationChoice] = Field(max_length=8)

    @model_validator(mode="after")
    def distinct_choices(self) -> ClarificationSpec:
        if len(self.choices) == 1:
            raise ValueError("Offer 2..8 choices or an open question.")
        if len({item.choice_id for item in self.choices}) != len(self.choices):
            raise ValueError("Repeated clarification choice.")
        return self


class ExplorationOrder(ExplorationModel):
    field_id: (
        ExplorationDimension | ExplorationMeasure | Literal["source_row_id", "connection_count"]
    )
    direction: Literal["asc", "desc"]


class SectionProposal(ExplorationModel):
    position: int = Field(strict=True, ge=1, le=4)
    original_clause: str = Field(min_length=1, max_length=2000)
    status: Literal["proposed", "needs_clarification", "unsupported"]
    family: RequestFamily | None
    operation_id: ExplorationOperation | None
    measure_ids: list[ExplorationMeasure] = Field(max_length=2)
    population: (
        Literal[
            "flights",
            "observed_origins",
            "observed_destinations",
            "observed_airlines",
            "airport_reference",
            "airport_connections",
        ]
        | None
    )
    entity_mentions: list[EntityMention]
    scope_edits: list[ScopeEdit] = Field(max_length=12)
    grouping: list[ExplorationDimension] = Field(max_length=2)
    comparison: ComparisonSpec | None
    binning: BinningSpec | None
    pairing: PairingSpec | None
    order: ExplorationOrder | None
    bound: int | None = Field(ge=1, le=500, strict=True)
    rounding: RoundingSpec | None
    denominator_basis: Literal["verified_calendar_days", "observed_operating_days"] | None = None
    clarification: ClarificationSpec | None
    unsupported_reason: str | None = Field(max_length=500)

    @model_validator(mode="after")
    def validate_proposal(self) -> SectionProposal:
        if self.status == "proposed":
            if self.family is None or self.operation_id is None or self.population is None:
                raise ValueError("A proposed section requires family, operation and population.")
            if self.clarification is not None or self.unsupported_reason is not None:
                raise ValueError("A proposed section carries no unresolved explanation.")
            validate_exploration_combination(self.operation_id, self.measure_ids, self.grouping)
            validate_exploration_population(self.operation_id, self.family, self.population)
            if self.denominator_basis is not None and self.operation_id not in {
                "daily_distinct_mean",
                "daily_capacity_mean",
            }:
                raise ValueError("Only daily means accept a denominator basis.")
        elif self.status == "needs_clarification":
            if self.clarification is None or self.unsupported_reason is not None:
                raise ValueError("Clarification requires one focused question.")
        elif not self.unsupported_reason or self.clarification is not None:
            raise ValueError("Unsupported sections require an explanation.")
        return self


class IntentProposalV2(ExplorationModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"status": {"const": "requires_selection"}}},
                    "then": {
                        "properties": {
                            "sections": {"maxItems": 0},
                            "selection_reason": {"type": "string", "minLength": 1},
                        },
                    },
                    "else": {
                        "properties": {
                            "sections": {"minItems": 1},
                            "selection_reason": {"type": "null"},
                        },
                    },
                }
            ],
        }
    )
    intent_version: Literal[2]
    status: Literal["proposed", "needs_clarification", "unsupported", "requires_selection"]
    shared_scope: ProposedSharedScope
    sections: list[SectionProposal] = Field(max_length=4)
    selection_reason: str | None = Field(max_length=500)

    @model_validator(mode="after")
    def validate_envelope(self) -> IntentProposalV2:
        if self.status == "requires_selection":
            if not self.selection_reason or self.sections:
                raise ValueError("Selection requires explanation without a truncated plan.")
        else:
            if not self.sections or self.selection_reason is not None:
                raise ValueError("A request requires 1..4 sections.")
            expected = (
                "unsupported"
                if any(s.status == "unsupported" for s in self.sections)
                else "needs_clarification"
                if any(s.status == "needs_clarification" for s in self.sections)
                else "proposed"
            )
            if self.status != expected:
                raise ValueError("Envelope and section outcomes disagree.")
        if [s.position for s in self.sections] != list(range(1, len(self.sections) + 1)):
            raise ValueError("Section positions must be consecutive and unique.")
        return self


class FieldProvenance(ExplorationModel):
    source: Literal["explicit", "correction", "clarification", "inherited", "default"]
    revision: PositiveInteger
    choice: str | None = None


class ResolvedEntity(ExplorationModel):
    kind: Literal["origin", "destination", "airline"]
    code: NonEmptyText
    name: str | None
    status: Literal["observed", "reference_only", "unmatched_reference"]
    method: Literal["code", "name", "alias", "confirmed_spelling"]
    alias_version: NonEmptyText


class AnalyticalDefinition(ExplorationModel):
    unit: NonEmptyText
    numerator: str | None
    denominator: str | None
    weighting: NonEmptyText
    additivity: Literal["additive", "non_additive"]
    match_rules: list[str]
    exclusions: list[str]


class ResolvedInterpretation(ExplorationModel):
    interpretation_version: Literal[2] = 2
    request_id: NonEmptyText
    revision: PositiveInteger
    section_id: NonEmptyText
    original_clause: str = Field(min_length=1, max_length=2000)
    family: RequestFamily
    operation_id: ExplorationOperation
    measure_ids: list[ExplorationMeasure] = Field(max_length=2)
    entities: list[ResolvedEntity] = Field(default_factory=list)
    population: Literal[
        "flights",
        "observed_origins",
        "observed_destinations",
        "observed_airlines",
        "airport_reference",
        "airport_connections",
    ]
    filters: list[TypedFilter] = Field(default_factory=list, max_length=12)
    grouping: list[ExplorationDimension] = Field(default_factory=list, max_length=2)
    date_scope: TimeRange | None = None
    grain: Literal[
        "scalar",
        "flight",
        "entity",
        "category",
        "date",
        "week",
        "month",
        "month_of_year",
        "weekday",
        "bin",
        "flight_pair",
        "origin_hour",
    ] = "scalar"
    calendar: Literal["recorded_departure_date_monday_weeks"] = (
        "recorded_departure_date_monday_weeks"
    )
    denominator_basis: Literal[
        "not_applicable", "verified_calendar_days", "observed_operating_days"
    ] = "not_applicable"
    definition: AnalyticalDefinition
    comparison: ComparisonSpec | None = None
    binning: BinningSpec | None = None
    pairing: PairingSpec | None = None
    order: list[ExplorationOrder] = Field(default_factory=list)
    selection: int = Field(default=500, strict=True, ge=1, le=500)
    display_rounding: RoundingSpec | None = None
    field_provenance: dict[str, FieldProvenance] = Field(default_factory=dict)
    snapshot_id: ContentHash
    context_id: ContentHash

    @model_validator(mode="after")
    def validate_resolved(self) -> ResolvedInterpretation:
        validate_exploration_combination(self.operation_id, self.measure_ids, self.grouping)
        validate_exploration_population(self.operation_id, self.family, self.population)
        _validate_filter_conjunction(self.filters)
        expected = exploration_definition(self.operation_id, self.measure_ids, self.population)
        if expected is not None and (
            self.definition.unit != expected.unit
            or self.definition.weighting != expected.weighting
            or self.definition.additivity != expected.additivity
        ):
            raise ValueError("Definition must match the application catalog.")
        if (
            self.date_scope is not None
            and self.date_scope.start is None
            and self.date_scope.end is None
        ):
            raise ValueError("Explicit date scope requires a boundary.")
        if self.date_scope is not None:
            date_bounds = [
                TypedFilter(field_id="flight_date", operator=operator, value=boundary.isoformat())
                for boundary, operator in [
                    (self.date_scope.start, "gte"),
                    (self.date_scope.end, "lte"),
                ]
                if boundary is not None
            ]
            _validate_filter_conjunction([*self.filters, *date_bounds])
        if any(value.revision > self.revision for value in self.field_provenance.values()):
            raise ValueError("Provenance cannot refer to a future revision.")
        if self.denominator_basis == "observed_operating_days":
            choice = self.field_provenance.get("denominator_basis")
            if choice is None or choice.source not in {"clarification", "correction", "explicit"}:
                raise ValueError("Observed-day alternatives require explicit selection.")
        if self.operation_id in {"daily_distinct_mean", "daily_capacity_mean"}:
            if self.denominator_basis == "not_applicable":
                raise ValueError("Daily means require a denominator basis.")
        elif self.denominator_basis != "not_applicable":
            raise ValueError("This operation does not use a daily denominator.")
        if self.order and any(
            item.field_id
            not in (
                {*self.grouping, *self.measure_ids, "source_row_id"}
                if self.operation_id not in {"flight_records", "entity_list"}
                else {
                    "source_row_id",
                    "origin",
                    "destination",
                    "carrier",
                    "flight_date",
                    "departure_delay",
                    "arrival_delay",
                    "distance",
                    "tailnum",
                    "airline_name",
                    "connection_count",
                }
            )
            for item in self.order
        ):
            raise ValueError("Ordering requires a selected output field.")
        if self.operation_id == "entity_list" and any(
            item.field_id
            not in (
                {"origin", "destination", "airline_name", "connection_count"}
                if self.population == "airport_connections"
                else {"origin", "destination", "carrier", "airline_name"}
            )
            for item in self.order
        ):
            raise ValueError("Entity lists can order only by code identity or reference name.")
        if self.population != "airport_connections" and any(
            item.field_id == "connection_count" for item in self.order
        ):
            raise ValueError(
                "Connection-count ordering requires the airport connection population."
            )
        if self.population == "airport_reference" and (
            self.date_scope is not None
            or any(item.field_id not in {"origin", "destination"} for item in self.filters)
        ):
            raise ValueError("Airport-reference lists have no flight-attribute scope.")
        for option, operation in [
            (self.comparison, "period_change"),
            (self.binning, "distribution"),
            (self.pairing, "flight_relationship"),
        ]:
            if (option is not None) != (self.operation_id == operation):
                raise ValueError(f"Options must match operation {operation}.")
        return self


class SnapshotBinding(ExplorationModel):
    snapshot_id: ContentHash
    context_id: ContentHash


class SafeFailure(ExplorationModel):
    category: FailureCategory
    code: NonEmptyText
    message: NonEmptyText


class RequestedSection(ExplorationModel):
    section_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    position: int = Field(default=1, strict=True, ge=1, le=4)
    original_clause: str = Field(min_length=1, max_length=2000)
    status: Literal["unresolved", "resolved", "removed", "completed", "valid_empty", "failed"] = (
        "unresolved"
    )
    answered_turns: int = Field(default=0, strict=True, ge=0, le=3)
    interpretation: ResolvedInterpretation | None = None
    clarification: ClarificationSpec | None = None
    choices: list[FieldProvenance] = Field(default_factory=list)


class RemovedSection(ExplorationModel):
    section_id: NonEmptyText
    label: NonEmptyText
    reason: Literal["analyst_removed"]


class RequestDraft(ExplorationModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    session_binding: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    revision: PositiveInteger = 1
    original_question: str
    state: RequestState = "unresolved"
    sections: list[RequestedSection] = Field(default_factory=list, max_length=4)
    shared_scope: ProposedSharedScope = Field(default_factory=ProposedSharedScope)
    removed_sections: list[RemovedSection] = Field(default_factory=list)
    snapshot_binding: SnapshotBinding | None = None
    last_failure: SafeFailure | None = None

    _trim_question = field_validator("original_question")(_question_text)

    @model_validator(mode="before")
    @classmethod
    def initial_section(cls, value: object) -> object:
        if isinstance(value, dict) and "sections" not in value and "original_question" in value:
            value = dict(value)
            if isinstance(value["original_question"], str):
                value["sections"] = [
                    {"original_clause": _question_text(value["original_question"])}
                ]
        return value

    @model_validator(mode="after")
    def validate_sections(self) -> RequestDraft:
        if not self.sections:
            raise ValueError("A decomposed draft requires 1..4 sections.")
        if len({s.section_id for s in self.sections}) != len(self.sections):
            raise ValueError("Repeated requested section identity.")
        if [s.position for s in self.sections] != list(range(1, len(self.sections) + 1)):
            raise ValueError("Requested section order must be consecutive.")
        return self


AbsenceReason = Literal[
    "no_matching_records",
    "no_known_values",
    "no_verified_days",
    "insufficient_pairs",
    "constant_axis",
    "unknown_capacity",
]
EvidenceRow = dict[str, CellValue]


class NumericEvidence(ExplorationModel):
    value: NumericValue | None
    absence: AbsenceReason | None

    @model_validator(mode="after")
    def explain_absence(self) -> NumericEvidence:
        if (self.value is None) != (self.absence is not None):
            raise ValueError("Unavailable numbers require a reason; observed values have none.")
        return self


class EvidenceScope(ExplorationModel):
    filters: list[TypedFilter] = Field(max_length=12)
    requested_period: TimeRange | None
    observed_period: TimeRange | None
    origins: list[NonEmptyText]
    coverage_status: Literal["unknown", "verified", "partial"]
    denominator_basis: Literal[
        "not_applicable",
        "verified_calendar_days",
        "observed_operating_days",
    ]
    requested_days: NonnegativeInteger | None
    verified_days: NonnegativeInteger
    unknown_days: NonnegativeInteger | None
    observed_days: NonnegativeInteger
    eligible_days: NonnegativeInteger | None

    @model_validator(mode="after")
    def validate_scope(self) -> EvidenceScope:
        _validate_filter_conjunction(self.filters)
        if self.requested_days is not None and self.unknown_days is not None:
            if self.verified_days + self.unknown_days != self.requested_days:
                raise ValueError("Requested-day coverage must reconcile.")
        if self.coverage_status == "unknown" and self.verified_days:
            raise ValueError("Unknown coverage cannot supply verified days.")
        if self.denominator_basis == "verified_calendar_days":
            if self.eligible_days != self.verified_days:
                raise ValueError("Calendar denominator must equal verified days.")
        if self.denominator_basis == "observed_operating_days":
            if self.eligible_days != self.observed_days:
                raise ValueError("Observed denominator must equal observed days.")
        return self


class EvidenceField(ExplorationModel):
    field_id: NonEmptyText
    label: NonEmptyText
    role: Literal["numeric", "date", "category", "ordinal", "identity"]
    unit: str | None
    unit_provenance: str | None


class EvidenceSelection(ExplorationModel):
    available: NonnegativeInteger
    selected: int = Field(strict=True, ge=0, le=500)
    omitted: NonnegativeInteger
    cutoff_tie: bool

    @model_validator(mode="after")
    def reconcile_selection(self) -> EvidenceSelection:
        if self.selected + self.omitted != self.available:
            raise ValueError("Selected and omitted counts must equal available count.")
        return self


class EvidenceFormat(ExplorationModel):
    locale: Literal["en"]
    computed_places: Literal[2]
    rounding: RoundingSpec | None


class VerifiedCoverageInterval(ExplorationModel):
    origin: NonEmptyText
    start: date
    end: date

    @model_validator(mode="after")
    def ordered_interval(self) -> VerifiedCoverageInterval:
        if self.start > self.end:
            raise ValueError("Coverage intervals must be ordered.")
        return self


class SavedBucketCoverage(ExplorationModel):
    coverage_version: Literal[1] = 1
    snapshot_id: ContentHash
    context_id: ContentHash
    declaration_sha256: ContentHash
    intervals: list[VerifiedCoverageInterval] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def distinct_verified_intervals(self) -> SavedBucketCoverage:
        previous: dict[str, date] = {}
        for interval in sorted(self.intervals, key=lambda item: (item.origin, item.start)):
            if interval.origin in previous and interval.start <= previous[interval.origin]:
                raise ValueError("Coverage intervals must not overlap for an origin.")
            previous[interval.origin] = interval.end
        return self


class ResultEvidence(ExplorationModel):
    result_version: Literal[2]
    evidence_version: Literal[2]
    report_id: NonEmptyText
    section_id: NonEmptyText
    snapshot_id: ContentHash
    context_id: ContentHash
    definition: AnalyticalDefinition
    grain: Literal[
        "scalar",
        "flight",
        "entity",
        "category",
        "date",
        "week",
        "month",
        "month_of_year",
        "weekday",
        "bin",
        "flight_pair",
        "origin_hour",
    ]
    calendar: Literal["recorded_departure_date_monday_weeks"] = (
        "recorded_departure_date_monday_weeks"
    )
    scope: EvidenceScope
    fields: list[EvidenceField]
    order: list[ExplorationOrder]
    missingness: dict[str, NonnegativeInteger]
    selection: EvidenceSelection
    format: EvidenceFormat
    limitations: list[str]
    daily_support: list[EvidenceRow] = Field(max_length=500)
    route_support: list[EvidenceRow] = Field(max_length=500)
    bucket_coverage: SavedBucketCoverage | None = None

    @model_validator(mode="after")
    def unique_fields(self) -> ResultEvidence:
        if len({field.field_id for field in self.fields}) != len(self.fields):
            raise ValueError("Evidence field IDs must be unique.")
        coverage = self.bucket_coverage
        if coverage is not None and (
            coverage.snapshot_id != self.snapshot_id
            or coverage.context_id != self.context_id
            or any(interval.origin not in self.scope.origins for interval in coverage.intervals)
        ):
            raise ValueError("Bucket coverage must bind to this evidence snapshot and origins.")
        return self


class ScalarResult(ResultEvidence):
    kind: Literal["scalar"]
    value: NumericEvidence
    numerator: NumericValue | None = None
    denominator: NumericValue | None = None

    @model_validator(mode="after")
    def scalar_selection(self) -> ScalarResult:
        if self.selection.available != 1 or self.selection.selected != 1:
            raise ValueError("Scalar evidence contains exactly one selected observation.")
        return self


class CategoryIdentity(ExplorationModel):
    field_id: ExplorationDimension
    code: str | None
    label: NonEmptyText
    status: Literal["known", "missing", "unmatched_reference"]

    @model_validator(mode="after")
    def preserve_identity(self) -> CategoryIdentity:
        if (self.status == "missing") != (self.code is None):
            raise ValueError("Missing categories have no code; known identities retain codes.")
        return self


class GroupEvidence(ExplorationModel):
    identity: list[CategoryIdentity] = Field(max_length=2)
    measures: dict[ExplorationMeasure, NumericEvidence]
    sample_size: NonnegativeInteger
    tied: bool
    scoped_count: NonnegativeInteger | None = None
    missing_count: NonnegativeInteger | None = None

    @model_validator(mode="after")
    def reconcile_group_population(self) -> GroupEvidence:
        if (self.scoped_count is None) != (self.missing_count is None):
            raise ValueError("Group population and missingness must be supplied together.")
        if self.scoped_count is not None and self.missing_count is not None:
            if self.sample_size + self.missing_count != self.scoped_count:
                raise ValueError("Known and missing group observations must reconcile.")
        return self


class GroupedResult(ResultEvidence):
    kind: Literal["grouped"]
    values: list[GroupEvidence] = Field(max_length=500)

    @model_validator(mode="after")
    def reconcile_groups(self) -> GroupedResult:
        if len(self.values) != self.selection.selected:
            raise ValueError("Selected groups must match the stored evidence.")
        keys = [tuple((c.field_id, c.code) for c in row.identity) for row in self.values]
        if any(not key for key in keys):
            raise ValueError("Grouped evidence requires category identities.")
        if len(set(keys)) != len(keys):
            raise ValueError("Group identities must be unique.")
        return self


class BrowsePage(ExplorationModel):
    analyst_id: NonEmptyText
    session_id: NonEmptyText
    request_id: NonEmptyText
    revision: PositiveInteger
    section_id: NonEmptyText
    snapshot_id: ContentHash
    context_id: ContentHash
    scope_hash: ContentHash
    order_hash: ContentHash
    sort_field: NonEmptyText
    direction: Literal["asc", "desc"]
    page_size: Literal[25, 50, 100, 500]
    page_index: PositiveInteger
    total_rows: NonnegativeInteger
    total_pages: NonnegativeInteger
    identity_column: NonEmptyText
    first_identity: str | int | None
    last_identity: str | int | None
    rows: list[EvidenceRow] = Field(max_length=500)
    notice: str | None = None

    @model_validator(mode="after")
    def reconcile_page(self) -> BrowsePage:
        expected_pages = (self.total_rows + self.page_size - 1) // self.page_size
        if self.total_pages != expected_pages:
            raise ValueError("Page count must reconcile to the complete population.")
        if self.page_index > max(1, self.total_pages):
            raise ValueError("Page position exceeds the available population.")
        expected_rows = min(
            self.page_size,
            max(
                0,
                self.total_rows - (self.page_index - 1) * self.page_size,
            ),
        )
        if len(self.rows) != expected_rows:
            raise ValueError("Page rows must reconcile to position and population.")
        identities = [row.get(self.identity_column) for row in self.rows]
        if any(value is None for value in identities) or len(set(identities)) != len(identities):
            raise ValueError("Page identities must be complete and unique.")
        if self.first_identity != (identities[0] if identities else None) or self.last_identity != (
            identities[-1] if identities else None
        ):
            raise ValueError("Page boundary identities must match its rows.")
        return self


class ExportSelection(ExplorationModel):
    analyst_id: NonEmptyText
    session_id: NonEmptyText
    report_id: NonEmptyText
    request_id: NonEmptyText
    revision: PositiveInteger
    snapshot_id: ContentHash
    context_id: ContentHash
    scope_hash: ContentHash
    order_hash: ContentHash
    kind: Literal["listing_csv", "bundle_csv"]
    allocations: dict[str, NonnegativeInteger] = Field(min_length=1, max_length=4)
    total_rows: dict[str, NonnegativeInteger] = Field(min_length=1, max_length=4)
    confirmation: ContentHash | None = None
    incomplete_acknowledgement: IncompleteAcknowledgement | None = None

    @model_validator(mode="after")
    def allocation_limit(self) -> ExportSelection:
        if sum(self.allocations.values()) > 10000:
            raise ValueError("Combined listing exports cannot exceed 10,000 rows.")
        if set(self.allocations) != set(self.total_rows):
            raise ValueError("Every selected section requires an exact total.")
        if any(count > self.total_rows[key] for key, count in self.allocations.items()):
            raise ValueError("Allocation exceeds the selected population.")
        return self

    def confirmation_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(
                self.model_dump(mode="json", exclude={"confirmation"}),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    def confirm(self) -> ExportSelection:
        return self.model_copy(update={"confirmation": self.confirmation_hash()})

    def require_confirmation(self) -> None:
        partial = any(self.allocations[key] < total for key, total in self.total_rows.items())
        if partial and self.confirmation != self.confirmation_hash():
            raise ValueError(
                "Explicit partial-listing confirmation is required for this selection."
            )


class ListingResult(ResultEvidence):
    kind: Literal["listing"]
    population: Literal[
        "flights",
        "observed_origins",
        "observed_destinations",
        "observed_airlines",
        "airport_reference",
        "airport_connections",
    ]
    total_rows: NonnegativeInteger
    rows: list[EvidenceRow] = Field(max_length=500)
    identity_columns: list[NonEmptyText] = Field(min_length=1)
    browse_page: BrowsePage | None = None

    @model_validator(mode="after")
    def validate_rows(self) -> ListingResult:
        columns = {field.field_id for field in self.fields}
        if not set(self.identity_columns).issubset(columns):
            raise ValueError("Listing identity must use declared columns.")
        if self.total_rows != self.selection.available or len(self.rows) != self.selection.selected:
            raise ValueError("Listing counts must reconcile.")
        if any(set(row) != columns for row in self.rows):
            raise ValueError("Listing rows must match their declared columns.")
        identities = [tuple(row[key] for key in self.identity_columns) for row in self.rows]
        if any(None in identity for identity in identities) or len(set(identities)) != len(
            identities
        ):
            raise ValueError("Listing identities must be complete and unique.")
        if self.browse_page is not None and (
            self.browse_page.rows != self.rows
            or self.browse_page.total_rows != self.total_rows
            or self.browse_page.snapshot_id != self.snapshot_id
            or self.browse_page.context_id != self.context_id
            or self.browse_page.section_id != self.section_id
        ):
            raise ValueError("Saved page and listing evidence must agree.")
        return self


class PeriodEvidence(ExplorationModel):
    period: TimeRange
    value: NumericEvidence
    observation_count: NonnegativeInteger
    day_exposure: NonnegativeInteger


class PeriodChangeResult(ResultEvidence):
    kind: Literal["period_change"]
    baseline: PeriodEvidence
    comparison: PeriodEvidence
    absolute_change: NumericEvidence
    relative_change: NumericEvidence
    warnings: list[str]


class DistributionBin(ExplorationModel):
    lower: NumericValue
    upper: NumericValue
    count: NonnegativeInteger
    upper_inclusive: bool

    @model_validator(mode="after")
    def positive_width(self) -> DistributionBin:
        if self.lower >= self.upper:
            raise ValueError("Bins require positive width.")
        return self


class DistributionResult(ResultEvidence):
    kind: Literal["distribution"]
    variable: Literal["departure_delay", "arrival_delay", "distance"]
    width: StrictFloat = Field(gt=0)
    bins: list[DistributionBin] = Field(max_length=100)
    known_count: NonnegativeInteger
    missing_count: NonnegativeInteger

    @model_validator(mode="after")
    def reconcile_bins(self) -> DistributionResult:
        if sum(item.count for item in self.bins) != self.known_count:
            raise ValueError("Bin counts must equal the known population.")
        for index, item in enumerate(self.bins):
            if item.upper_inclusive != (index == len(self.bins) - 1):
                raise ValueError("Only the final bin includes its upper boundary.")
            if index and self.bins[index - 1].upper != item.lower:
                raise ValueError("Bins must be ordered contiguous intervals.")
            if abs((item.upper - item.lower) - self.width) > max(1e-9, 1e-12 * self.width):
                raise ValueError("All bins must use the accepted width.")
        return self


class EvidencePair(ExplorationModel):
    source_id: NonEmptyText
    x: NumericValue
    y: NumericValue


class DensityCell(ExplorationModel):
    x: int = Field(strict=True, ge=0, le=19)
    y: int = Field(strict=True, ge=0, le=19)
    count: NonnegativeInteger


class DensityEvidence(ExplorationModel):
    x_edges: list[NumericValue] = Field(min_length=2, max_length=21)
    y_edges: list[NumericValue] = Field(min_length=2, max_length=21)
    cells: list[DensityCell] = Field(max_length=400)

    @model_validator(mode="after")
    def valid_grid(self) -> DensityEvidence:
        for edges in [self.x_edges, self.y_edges]:
            if any(left >= right for left, right in zip(edges, edges[1:], strict=False)):
                raise ValueError("Density boundaries must be strictly increasing.")
            width = (edges[-1] - edges[0]) / (len(edges) - 1)
            if any(
                abs((right - left) - width) > max(1e-9, 1e-12 * abs(width))
                for left, right in zip(edges, edges[1:], strict=False)
            ):
                raise ValueError("Density intervals must be equal-width.")
        identities = {(cell.x, cell.y) for cell in self.cells}
        if len(identities) != len(self.cells):
            raise ValueError("Density cells must be unique.")
        if any(
            cell.x >= len(self.x_edges) - 1 or cell.y >= len(self.y_edges) - 1
            for cell in self.cells
        ):
            raise ValueError("Density cell lies outside declared edges.")
        return self


class PairEvidence(ExplorationModel):
    x_field: Literal[
        "departure_delay", "arrival_delay", "distance", "temp", "wind_speed", "precip", "visib"
    ]
    y_field: Literal["departure_delay", "arrival_delay", "distance"]
    x_unit: NonEmptyText
    y_unit: NonEmptyText
    pair_count: NonnegativeInteger
    scoped_count: NonnegativeInteger
    x_missing_only: NonnegativeInteger
    y_missing_only: NonnegativeInteger
    both_missing: NonnegativeInteger
    x_extent: tuple[NumericValue, NumericValue] | None
    y_extent: tuple[NumericValue, NumericValue] | None
    pairs: list[EvidencePair] | None = Field(default=None, max_length=5000)
    density: DensityEvidence | None = None

    @model_validator(mode="after")
    def reconcile_pairs(self) -> PairEvidence:
        if self.x_field == self.y_field:
            raise ValueError("Pair variables must be distinct.")
        if self.scoped_count != (
            self.pair_count + self.x_missing_only + self.y_missing_only + self.both_missing
        ):
            raise ValueError("Pair missingness partition must reconcile.")
        for extent in [self.x_extent, self.y_extent]:
            if (extent is None) != (self.pair_count == 0):
                raise ValueError("Axis extents require known pairs, not fabricated bounds.")
            if extent is not None and extent[0] > extent[1]:
                raise ValueError("Axis extent bounds must be ordered.")
        if self.pair_count <= 5000:
            if self.pairs is None or self.density is not None or len(self.pairs) != self.pair_count:
                raise ValueError("Up to 5,000 pairs must be stored completely, not sampled.")
            if len({pair.source_id for pair in self.pairs}) != len(self.pairs):
                raise ValueError("Paired observations require unique source identities.")
            if self.pairs and (
                self.x_extent
                != (min(pair.x for pair in self.pairs), max(pair.x for pair in self.pairs))
                or self.y_extent
                != (min(pair.y for pair in self.pairs), max(pair.y for pair in self.pairs))
            ):
                raise ValueError("Stored pair extents must match every known observation.")
        elif (
            self.pairs is not None
            or self.density is None
            or sum(cell.count for cell in self.density.cells) != self.pair_count
        ):
            raise ValueError("Above 5,000 pairs requires reconciled full-population density.")
        if self.density is not None:
            for extent, edges in [
                (self.x_extent, self.density.x_edges),
                (self.y_extent, self.density.y_edges),
            ]:
                if extent is not None and (
                    edges[0] != extent[0]
                    or (extent[0] != extent[1] and edges[-1] != extent[1])
                    or (extent[0] == extent[1] and len(edges) != 2)
                ):
                    raise ValueError("Density must preserve actual axis extents and constant axes.")
        return self


class RelationshipResult(ResultEvidence):
    kind: Literal["relationship"]
    pairing: PairEvidence


class DailyMeanEvidence(GroupEvidence):
    value: NumericEvidence
    numerator: NumericValue | None
    eligible_days: NonnegativeInteger
    known_contribution_count: NonnegativeInteger
    unknown_contribution_count: NonnegativeInteger
    complete_days: NonnegativeInteger
    incomplete_days: NonnegativeInteger
    provisional: bool

    @model_validator(mode="after")
    def validate_denominator(self) -> DailyMeanEvidence:
        if self.complete_days + self.incomplete_days != self.eligible_days:
            raise ValueError("Daily completeness must reconcile with the denominator.")
        if not self.eligible_days and self.value.value is not None:
            raise ValueError("No eligible days cannot produce a daily mean.")
        return self


class DailyMeanResult(ResultEvidence):
    kind: Literal["daily_mean"]
    values: list[DailyMeanEvidence] = Field(max_length=500)

    @model_validator(mode="after")
    def reconcile_daily_groups(self) -> DailyMeanResult:
        if len(self.values) != self.selection.selected:
            raise ValueError("Selected daily groups must match stored evidence.")
        return self


class WeatherVariableEvidence(ExplorationModel):
    variable: Literal["temp", "wind_speed", "precip", "visib"]
    origin: str | None
    pairing: PairEvidence
    coefficient: NumericEvidence

    @model_validator(mode="after")
    def validate_coefficient(self) -> WeatherVariableEvidence:
        if self.pairing.x_field != self.variable or self.pairing.y_field != "departure_delay":
            raise ValueError("Weather pairs must use the declared weather variable and delay.")
        value = self.coefficient.value
        if value is not None and (self.pairing.pair_count < 3 or not -1 <= value <= 1):
            raise ValueError("Pearson requires at least three valid pairs and lies in [-1,1].")
        if value is not None and any(
            extent is not None and extent[0] == extent[1]
            for extent in [self.pairing.x_extent, self.pairing.y_extent]
        ):
            raise ValueError("A constant axis cannot produce a Pearson coefficient.")
        return self


class WeatherPanelResult(ResultEvidence):
    kind: Literal["weather_panel"]
    weather_units_status: Literal["verified", "unverified"] = "verified"
    variables: list[WeatherVariableEvidence] = Field(min_length=4, max_length=2000)
    precipitation_comparison: list[GroupEvidence] = Field(max_length=500)

    @model_validator(mode="after")
    def complete_weather_panels(self) -> WeatherPanelResult:
        if self.weather_units_status == "unverified" and (
            self.precipitation_comparison
            or any(item.pairing.x_unit != "recorded units (unverified)" for item in self.variables)
        ):
            raise ValueError(
                "Unverified weather units forbid physical labels and precipitation bands."
            )
        identities = {(item.origin, item.variable) for item in self.variables}
        if len(identities) != len(self.variables):
            raise ValueError("Weather panels cannot repeat variable/origin populations.")
        for origin in {item.origin for item in self.variables}:
            if {item.variable for item in self.variables if item.origin == origin} != {
                "temp",
                "wind_speed",
                "precip",
                "visib",
            }:
                raise ValueError("Every weather population requires all four variables.")
        return self


ExplorationResult = Annotated[
    ScalarResult
    | GroupedResult
    | ListingResult
    | PeriodChangeResult
    | DistributionResult
    | RelationshipResult
    | DailyMeanResult
    | WeatherPanelResult,
    Field(discriminator="kind"),
]

RESULT_KINDS_BY_OPERATION = MappingProxyType(
    {
        "aggregate": frozenset({"scalar", "grouped"}),
        "entity_list": frozenset({"listing"}),
        "flight_records": frozenset({"listing"}),
        "period_change": frozenset({"period_change"}),
        "distribution": frozenset({"distribution"}),
        "flight_relationship": frozenset({"relationship"}),
        "daily_distinct_mean": frozenset({"daily_mean"}),
        "departure_delay_total": frozenset({"scalar", "grouped"}),
        "daily_capacity_mean": frozenset({"daily_mean"}),
        "aircraft_frequency": frozenset({"grouped"}),
        "weather_relationship": frozenset({"weather_panel"}),
    }
)


class CompletedSection(ExplorationModel):
    status: Literal["completed"]
    result: ExplorationResult


class EmptySection(ExplorationModel):
    status: Literal["valid_empty"]
    evidence: ExplorationResult

    @model_validator(mode="after")
    def zero_matching_scope(self) -> EmptySection:
        matching = (
            self.evidence.total_rows
            if isinstance(self.evidence, ListingResult)
            else self.evidence.missingness.get("filtered_flights")
        )
        if matching != 0:
            raise ValueError("Valid empty evidence requires exactly zero matching records.")
        return self


class FailedSection(ExplorationModel):
    status: Literal["failed"]
    failure: SafeFailure


SectionOutcome = Annotated[
    CompletedSection | EmptySection | FailedSection, Field(discriminator="status")
]


class ReportSection(ExplorationModel):
    section_id: NonEmptyText
    position: int = Field(strict=True, ge=1, le=4)
    label: NonEmptyText
    interpretation: ResolvedInterpretation
    narrative: str
    outcome: SectionOutcome


class IncompleteAcknowledgement(ExplorationModel):
    analyst_id: NonEmptyText
    session_id: NonEmptyText
    report_id: NonEmptyText
    revision: PositiveInteger
    failed_section_ids: list[NonEmptyText] = Field(min_length=1, max_length=4)
    acknowledged_at: AwareDatetime

    @field_validator("acknowledged_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("Acknowledgement timestamps must be UTC.")
        return value


class SectionPresentationPreference(ExplorationModel):
    chart_family: Literal[
        "default",
        "summary",
        "bar",
        "dot",
        "line",
        "small_multiples",
        "grouped_bar",
        "heatmap",
        "histogram",
        "scatter",
        "density",
        "table",
    ] = "default"
    category_ids: list[str] = Field(default_factory=list, max_length=500)
    series_ids: list[str] = Field(default_factory=list, max_length=500)


class CompositeReportV2(ExplorationModel):
    report_version: Literal[2]
    report_id: NonEmptyText
    analyst_id: NonEmptyText
    session_id: NonEmptyText
    parent_report_id: str | None
    question: str
    revision: PositiveInteger
    created_at: AwareDatetime
    snapshot_id: ContentHash
    context_id: ContentHash
    versions: dict[str, NonEmptyText]
    shared_scope: ProposedSharedScope
    removed_sections: list[RemovedSection]
    sections: list[ReportSection] = Field(min_length=1, max_length=4)
    completeness: Literal["complete", "incomplete"]
    incomplete_acknowledgement: IncompleteAcknowledgement | None
    presentation_preferences: dict[str, SectionPresentationPreference]
    preference_version: PositiveInteger

    _trim_question = field_validator("question")(_question_text)

    @model_validator(mode="after")
    def validate_report(self) -> CompositeReportV2:
        if self.created_at.utcoffset() != timedelta(0):
            raise ValueError("Report creation timestamp must be UTC.")
        ids = [section.section_id for section in self.sections]
        if len(set(ids)) != len(ids):
            raise ValueError("Report section identities must be unique.")
        if [s.position for s in self.sections] != list(range(1, len(self.sections) + 1)):
            raise ValueError("Report sections must retain their requested order.")
        failed = [s.section_id for s in self.sections if s.outcome.status == "failed"]
        if len(failed) == len(self.sections):
            raise ValueError("All-failed requests cannot become successful reports.")
        if self.completeness != ("incomplete" if failed else "complete"):
            raise ValueError("Report completeness must reflect every requested section.")
        request_ids = {s.interpretation.request_id for s in self.sections}
        if len(request_ids) != 1:
            raise ValueError("Report sections must belong to the same request.")
        for section in self.sections:
            interpretation = section.interpretation
            if (
                interpretation.section_id != section.section_id
                or interpretation.revision != self.revision
                or interpretation.snapshot_id != self.snapshot_id
                or interpretation.context_id != self.context_id
            ):
                raise ValueError("Section interpretation identity is stale or mismatched.")
            if section.outcome.status == "failed":
                continue
            result = (
                section.outcome.result
                if section.outcome.status == "completed"
                else section.outcome.evidence
            )
            if result.kind not in RESULT_KINDS_BY_OPERATION[interpretation.operation_id]:
                raise ValueError("Result shape must match the saved analytical operation.")
            if (
                result.report_id != self.report_id
                or result.section_id != section.section_id
                or result.snapshot_id != self.snapshot_id
                or result.context_id != self.context_id
                or result.definition != interpretation.definition
                or result.scope.filters != interpretation.filters
                or result.scope.denominator_basis != interpretation.denominator_basis
                or result.grain != interpretation.grain
            ):
                raise ValueError("Evidence must match its saved interpretation and report.")
            if isinstance(result, ListingResult) and result.browse_page is not None:
                page = result.browse_page
                if (
                    page.analyst_id != self.analyst_id
                    or page.session_id != self.session_id
                    or page.request_id != interpretation.request_id
                    or page.revision != interpretation.revision
                ):
                    raise ValueError(
                        "Saved browsing state must belong to this report owner/request."
                    )
        if not set(self.presentation_preferences).issubset(ids):
            raise ValueError("Presentation preferences must target existing sections.")
        acknowledgement = self.incomplete_acknowledgement
        if acknowledgement is not None and (
            not failed
            or acknowledgement.analyst_id != self.analyst_id
            or acknowledgement.session_id != self.session_id
            or acknowledgement.report_id != self.report_id
            or acknowledgement.revision != self.revision
            or sorted(acknowledgement.failed_section_ids) != sorted(failed)
            or acknowledgement.acknowledged_at < self.created_at
        ):
            raise ValueError("Incomplete acknowledgement must bind to this exact report.")
        return self

    def require_persistable(self) -> None:
        if self.completeness == "incomplete" and self.incomplete_acknowledgement is None:
            raise ValueError("Incomplete save/export requires an exact acknowledgement.")


SavedReport = ReportContent | CompositeReportV2

from airport_analytics.analytics.evaluation_records import (  # noqa: E402,F401
    CorpusCase,
    EvaluationRun,
    ReviewRecord,
)
