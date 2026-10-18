"""Immutable, source-free projections of already saved analytical evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from airport_analytics.errors import (
    MissingVisualEvidenceError,
    PresentationPreferenceError,
    VisualEvidenceError,
)
from airport_analytics.models import (
    RESULT_KINDS_BY_OPERATION,
    DailyMeanResult,
    DistributionResult,
    ExplorationResult,
    GroupedResult,
    ListingResult,
    PeriodChangeResult,
    RelationshipResult,
    ReportContent,
    SavedReport,
    ScalarResult,
    SectionPresentationPreference,
    WeatherPanelResult,
)

Shape = Literal[
    "listing",
    "scalar",
    "category",
    "ranking",
    "time",
    "time_series",
    "two_category",
    "period_change",
    "distribution",
    "relationship",
    "weather",
]
View = Literal[
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
]
PresentationState = Literal[
    "ready",
    "table_selected",
    "selection_required",
    "no_plottable_data",
    "missing_evidence",
    "invalid_evidence",
    "render_failed",
]
ReferenceStatus = Literal["known", "missing", "unmatched_reference", "unknown"]
Count = Annotated[int, Field(strict=True, ge=0)]
_DOCUMENT = TypeAdapter(dict[str, JsonValue])
_RESULT = TypeAdapter(ExplorationResult)
_TIME_ROLES = {"flight_date", "flight_week", "flight_month"}
_ORDERED_ROLES = {"weekday", "month_of_year"}
_LEGACY_GRAINS = {
    "flight_date": "date",
    "flight_week": "week",
    "flight_month": "month",
    "weekday": "weekday",
    "month_of_year": "month_of_year",
}


def _canonical(value: object) -> str:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except (ValueError, TypeError, OverflowError) as exc:
        raise VisualEvidenceError() from exc


@dataclass(frozen=True)
class FrozenDocument:
    """Canonical bytes are immutable; readers receive detached typed JSON copies."""

    canonical_json: str

    def __post_init__(self) -> None:
        try:
            value = _DOCUMENT.validate_json(self.canonical_json)
        except ValueError as exc:
            raise VisualEvidenceError() from exc
        if _canonical(value) != self.canonical_json:
            raise VisualEvidenceError()

    @classmethod
    def from_dict(cls, value: dict[str, JsonValue]) -> FrozenDocument:
        return cls(_canonical(value))

    def to_dict(self) -> dict[str, JsonValue]:
        return _DOCUMENT.validate_json(self.canonical_json)


def canonical_identity(field_id: str, code: str | None, reference_status: ReferenceStatus) -> str:
    if (
        not isinstance(field_id, str)
        or not field_id
        or (code is not None and not isinstance(code, str))
        or reference_status not in {"known", "missing", "unmatched_reference", "unknown"}
        or ((code is None) != (reference_status == "missing"))
    ):
        raise VisualEvidenceError()
    return _canonical([field_id, code, reference_status])


class ImmutableVisualModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class VisualCategory(ImmutableVisualModel):
    token: str
    code: str | None
    label: str
    reference_status: ReferenceStatus


class VisualDimension(ImmutableVisualModel):
    field_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    role: Literal["category", "ordered_category", "time"]
    identities: tuple[VisualCategory, ...] = ()

    @model_validator(mode="after")
    def canonical_identities(self) -> VisualDimension:
        tokens = [identity.token for identity in self.identities]
        if len(set(tokens)) != len(tokens):
            raise ValueError("Dimension identities must be unique.")
        for identity in self.identities:
            if identity.token != canonical_identity(
                self.field_id,
                identity.code,
                identity.reference_status,
            ):
                raise ValueError("Identity tokens must bind to their field and reference status.")
        return self


class VisualSelection(ImmutableVisualModel):
    category_ids: tuple[str, ...] = Field(default=(), max_length=500)
    series_ids: tuple[str, ...] = Field(default=(), max_length=500)
    shown_groups: Count
    returned_groups: Count
    available_groups: Count | None
    shown_series: Count | None = None
    returned_series: Count | None = None
    available_series: Count | None = None
    analytical_cutoff_tie: bool = False
    visual_cutoff_tie: bool = False
    selection_required: bool = False
    reason: str | None = None
    subset_origin: Literal["all_returned", "default_ranking", "explicit"] = "all_returned"
    weather_variable: Literal["temp", "wind_speed", "precip", "visib"] | None = None
    weather_airport: str | None = None

    @property
    def visual_omitted_groups(self) -> int:
        return self.returned_groups - self.shown_groups

    @property
    def analytical_omitted_groups(self) -> int | None:
        return (
            self.available_groups - self.returned_groups
            if self.available_groups is not None
            else None
        )

    @model_validator(mode="after")
    def valid_counts(self) -> VisualSelection:
        if self.shown_groups > self.returned_groups:
            raise ValueError("Shown groups cannot exceed returned groups.")
        if self.available_groups is not None and self.returned_groups > self.available_groups:
            raise ValueError("Returned groups cannot exceed available groups.")
        if len(set(self.category_ids)) != len(self.category_ids):
            raise ValueError("Duplicate category selections are invalid.")
        if len(set(self.series_ids)) != len(self.series_ids):
            raise ValueError("Duplicate series selections are invalid.")
        for shown, returned, available in [
            (self.shown_series, self.returned_series, self.available_series)
        ]:
            if shown is not None and returned is not None and shown > returned:
                raise ValueError("Shown series cannot exceed returned series.")
            if returned is not None and available is not None and returned > available:
                raise ValueError("Returned series cannot exceed available series.")
        if self.selection_required and not self.reason:
            raise ValueError("Selection-required states need an explanation.")
        return self


class VisualEvidence(ImmutableVisualModel):
    visual_evidence_version: Literal[1] = 1
    selection_rule_version: Literal["003.1"] = "003.1"
    report_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    analytical_revision: int = Field(ge=1)
    snapshot_id: str = Field(min_length=1)
    context_id: str | None
    source_evidence_version: Literal[1, 2]
    evidence_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    shape: Shape
    definition: FrozenDocument
    measure_ids: tuple[str, ...] = Field(max_length=2)
    population: str | None
    grain: str
    dimensions: tuple[VisualDimension, ...] = Field(max_length=2)
    scope: FrozenDocument
    coverage: FrozenDocument
    selection: VisualSelection
    missingness: FrozenDocument
    limitations: tuple[str, ...]
    format: FrozenDocument
    payload: FrozenDocument

    @field_validator("visual_evidence_version", "source_evidence_version", mode="before")
    @classmethod
    def exact_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("Evidence versions require exact integers.")
        return value

    def typed_result(self) -> ExplorationResult:
        """Decode a detached instance of the existing closed shape-specific union."""
        if self.source_evidence_version != 2:
            raise MissingVisualEvidenceError(
                "Legacy visual evidence uses its preserved version-one payload, not a V2 result."
            )
        return _RESULT.validate_json(self.payload.canonical_json)


class PresentationResolution(ImmutableVisualModel):
    state: PresentationState
    evidence: VisualEvidence | None = None
    view: View | None = None
    selection: VisualSelection | None = None
    compatible_views: tuple[View, ...] = ()
    reason: str | None = None

    @model_validator(mode="after")
    def valid_state(self) -> PresentationResolution:
        if self.state in {"ready", "table_selected"}:
            if self.evidence is None or self.view is None or self.selection is None:
                raise ValueError("An applied view requires evidence, view and selection.")
            if self.state == "table_selected" and self.view != "table":
                raise ValueError("A deliberate table selection must be a table.")
            if self.view not in self.compatible_views:
                raise ValueError("The applied view must be an offered compatible view.")
            selection = self.selection
            evidence = self.evidence
            if (
                selection.returned_groups != evidence.selection.returned_groups
                or selection.available_groups != evidence.selection.available_groups
            ):
                raise ValueError("A visual selection cannot change analytical counts.")
            tokens = {
                identity.token
                for dimension in evidence.dimensions
                for identity in dimension.identities
            }
            if not set(selection.category_ids + selection.series_ids) <= tokens:
                raise ValueError("Selected identities must exist in the saved evidence.")
            if self.view != "table":
                if evidence.shape in {"category", "ranking"} and selection.shown_groups > 20:
                    raise ValueError("Single-category charts are limited to twenty identities.")
                if evidence.shape == "time_series" and (
                    selection.shown_series is None or selection.shown_series > 20
                ):
                    raise ValueError("Time-series charts require at most twenty selected series.")
                if (
                    self.view == "line"
                    and evidence.shape == "time_series"
                    and (selection.shown_series is None or selection.shown_series > 8)
                ):
                    raise ValueError("Line charts are limited to eight selected series.")
                if self.view == "grouped_bar":
                    if evidence.shape != "two_category" or len(evidence.dimensions) != 2:
                        raise ValueError("Grouped bars require two categorical dimensions.")
                    primary = (
                        len(selection.category_ids)
                        if selection.category_ids
                        else len(evidence.dimensions[0].identities)
                    )
                    series = (
                        len(selection.series_ids)
                        if selection.series_ids
                        else len(evidence.dimensions[1].identities)
                    )
                    if primary > 20 or not 1 <= series <= 8:
                        raise ValueError("Grouped bars require twenty primary/eight series bounds.")
                if self.view == "heatmap" and selection.returned_groups > 500:
                    raise ValueError("Heatmaps cannot exceed five hundred saved cells.")
        elif not self.reason:
            raise ValueError("Unavailable presentations need an explicit reason.")
        return self


def prepare_visual_evidence(report: SavedReport, section_id: str) -> VisualEvidence:
    if isinstance(report, ReportContent):
        return _prepare_legacy(report, section_id)
    if type(report.report_version) is not int or report.report_version != 2:
        raise VisualEvidenceError()
    sections = [section for section in report.sections if section.section_id == section_id]
    if len(sections) != 1:
        raise MissingVisualEvidenceError()
    section = sections[0]
    if section.outcome.status == "failed":
        raise MissingVisualEvidenceError(
            "This saved analysis failed; its notice remains available but no chart is defined."
        )
    source = (
        section.outcome.result
        if section.outcome.status == "completed"
        else section.outcome.evidence
    )
    if type(source.result_version) is not int or type(source.evidence_version) is not int:
        raise VisualEvidenceError()
    try:
        # Revalidate the detached result: persisted Pydantic instances are not deeply frozen.
        result = _RESULT.validate_python(source.model_dump(mode="python", warnings=False))
    except ValidationError as exc:
        raise VisualEvidenceError() from exc
    interpretation = section.interpretation
    if (
        result.report_id != report.report_id
        or result.section_id != section_id
        or result.snapshot_id != report.snapshot_id
        or result.context_id != report.context_id
        or interpretation.snapshot_id != report.snapshot_id
        or interpretation.context_id != report.context_id
        or interpretation.section_id != section_id
        or interpretation.revision != report.revision
        or result.definition != interpretation.definition
        or result.scope.filters != interpretation.filters
        or result.grain != interpretation.grain
        or result.kind not in RESULT_KINDS_BY_OPERATION.get(interpretation.operation_id, ())
    ):
        raise VisualEvidenceError()
    grouping = tuple(interpretation.grouping)
    ranked = interpretation.family == "ranking"
    shape = _classify(result, grouping, ranked)
    dimensions = _dimensions(result, grouping, ranked)
    payload = FrozenDocument.from_dict(result.model_dump(mode="json"))
    analytical = {
        "interpretation": interpretation.model_dump(mode="json"),
        "result": payload.to_dict(),
    }
    digest = hashlib.sha256(_canonical(analytical).encode("utf-8")).hexdigest()
    return VisualEvidence(
        report_id=report.report_id,
        section_id=section_id,
        analytical_revision=report.revision,
        snapshot_id=report.snapshot_id,
        context_id=report.context_id,
        source_evidence_version=2,
        evidence_fingerprint=digest,
        shape=shape,
        definition=FrozenDocument.from_dict(result.definition.model_dump(mode="json")),
        measure_ids=tuple(interpretation.measure_ids),
        population=interpretation.population,
        grain=result.grain,
        dimensions=dimensions,
        scope=FrozenDocument.from_dict(result.scope.model_dump(mode="json")),
        coverage=(
            FrozenDocument.from_dict(
                result.bucket_coverage.model_dump(mode="json")
                | {
                    "status": "verified_intervals",
                    "time_zone": "not applicable - recorded departure date",
                    "outside_intervals": "unknown",
                }
            )
            if result.bucket_coverage is not None
            else _unknown_coverage()
        ),
        selection=VisualSelection(
            shown_groups=result.selection.selected,
            returned_groups=result.selection.selected,
            available_groups=result.selection.available,
            analytical_cutoff_tie=result.selection.cutoff_tie,
        ),
        missingness=FrozenDocument.from_dict(dict(result.missingness)),
        limitations=tuple(result.limitations),
        format=FrozenDocument.from_dict(result.format.model_dump(mode="json")),
        payload=payload,
    )


def _unknown_coverage() -> FrozenDocument:
    return FrozenDocument.from_dict(
        {
            "status": "unknown",
            "intervals": [],
            "reason": "Exact verified bucket coverage was not saved; completeness is unknown.",
            "time_zone": "not applicable - recorded departure date",
        }
    )


def _classify(result: ExplorationResult, grouping: tuple[str, ...], ranked: bool) -> Shape:
    if isinstance(result, ListingResult):
        return "listing"
    if isinstance(result, DistributionResult):
        return "distribution"
    if isinstance(result, WeatherPanelResult):
        return "weather"
    if isinstance(result, RelationshipResult):
        return "relationship"
    if isinstance(result, PeriodChangeResult):
        return "period_change"
    if isinstance(result, ScalarResult):
        if grouping:
            raise VisualEvidenceError()
        return "scalar"
    if isinstance(result, DailyMeanResult) and not grouping:
        if len(result.values) > 1 or any(row.identity for row in result.values):
            raise VisualEvidenceError()
        return "scalar"
    if not grouping or len(grouping) > 2 or len(set(grouping)) != len(grouping):
        raise VisualEvidenceError()
    if ranked:
        if len(grouping) != 1:
            raise VisualEvidenceError(
                "A two-dimensional ranking has no supported chart. Retain its saved table "
                "or refine to one ranked dimension."
            )
        return "ranking"
    temporal = sum(field_id in _TIME_ROLES for field_id in grouping)
    if temporal > 1:
        raise VisualEvidenceError()
    if temporal:
        return "time" if len(grouping) == 1 else "time_series"
    return "category" if len(grouping) == 1 else "two_category"


def _dimensions(
    result: ExplorationResult,
    grouping: tuple[str, ...],
    ranked: bool,
) -> tuple[VisualDimension, ...]:
    if not isinstance(result, (GroupedResult, DailyMeanResult)) or not grouping:
        return ()
    for row in result.values:
        if tuple(identity.field_id for identity in row.identity) != grouping:
            raise VisualEvidenceError()
    fields = {field.field_id: field for field in result.fields}
    dimensions: list[VisualDimension] = []
    for index, field_id in enumerate(grouping):
        identities: dict[str, VisualCategory] = {}
        for row in result.values:
            identity = row.identity[index]
            token = canonical_identity(field_id, identity.code, identity.status)
            category = VisualCategory(
                token=token,
                code=identity.code,
                label=identity.label,
                reference_status=identity.status,
            )
            if token in identities and identities[token] != category:
                raise VisualEvidenceError()
            identities[token] = category
        dimensions.append(
            VisualDimension(
                field_id=field_id,
                label=fields[field_id].label if field_id in fields else field_id.replace("_", " "),
                role=(
                    "time"
                    if field_id in _TIME_ROLES and not ranked
                    else "ordered_category"
                    if field_id in _ORDERED_ROLES
                    else "category"
                ),
                identities=tuple(identities.values()),
            )
        )
    return tuple(dimensions)


def _prepare_legacy(report: ReportContent, section_id: str) -> VisualEvidence:
    if section_id != "legacy":
        raise MissingVisualEvidenceError()
    required_definitions = {"metric", "unit", "population", "numerator", "denominator", "period"}
    if not required_definitions.issubset(report.definitions) or any(
        not report.definitions[key].strip() for key in required_definitions
    ):
        raise MissingVisualEvidenceError()
    plan = report.analysis_plan
    rows = report.result_payload.get("rows")
    columns = report.result_payload.get("columns")
    if (
        not isinstance(rows, list)
        or len(rows) > 500
        or not isinstance(columns, list)
        or "metric_value" not in columns
        or not plan.metric_id
        or not report.snapshot_id
    ):
        raise MissingVisualEvidenceError()
    grouping = tuple(plan.group_by)
    if len(grouping) > 2 or len(set(grouping)) != len(grouping):
        raise VisualEvidenceError()
    identities: list[dict[str, VisualCategory]] = [{} for _ in grouping]
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        if not isinstance(row, dict) or "metric_value" not in row:
            raise MissingVisualEvidenceError()
        value = row["metric_value"]
        if value is not None and type(value) not in {int, float}:
            raise VisualEvidenceError()
        _canonical(value)
        tokens: list[str] = []
        for index, field_id in enumerate(grouping):
            if field_id not in row:
                raise MissingVisualEvidenceError()
            code = row[field_id]
            if code is not None and type(code) not in {str, int}:
                raise VisualEvidenceError()
            code = str(code) if code is not None else None
            status = "unknown" if code is not None else "missing"
            token = canonical_identity(field_id, code, status)
            tokens.append(token)
            identities[index][token] = VisualCategory(
                token=token,
                code=code,
                label=code if code is not None else "Missing category",
                reference_status=status,
            )
        if grouping and tuple(tokens) in seen:
            raise VisualEvidenceError()
        seen.add(tuple(tokens))
    if not grouping and len(rows) > 1:
        raise VisualEvidenceError()
    if plan.intent not in {"aggregate", "compare", "trend"}:
        raise MissingVisualEvidenceError(
            "This legacy result has no complete typed bins, pairs or listing metadata. "
            "Retain its saved evidence table; a graphical shape cannot be inferred."
        )
    ranked = plan.sort is not None and plan.sort.field_id in {plan.metric_id, "metric_value"}
    if ranked and len(grouping) != 1:
        raise VisualEvidenceError()
    if not grouping:
        shape: Shape = "scalar"
    elif ranked:
        shape = "ranking"
    elif any(field_id in _TIME_ROLES for field_id in grouping):
        if sum(field_id in _TIME_ROLES for field_id in grouping) > 1:
            raise VisualEvidenceError()
        shape = "time" if len(grouping) == 1 else "time_series"
    else:
        shape = "category" if len(grouping) == 1 else "two_category"
    dimensions = tuple(
        VisualDimension(
            field_id=field_id,
            label=field_id.replace("_", " "),
            role=(
                "time"
                if field_id in _TIME_ROLES and not ranked
                else "ordered_category"
                if field_id in _ORDERED_ROLES
                else "category"
            ),
            identities=tuple(identities[index].values()),
        )
        for index, field_id in enumerate(grouping)
    )
    semantic_plan = plan.model_dump(mode="json", exclude={"chart_intent"})
    analytical = {
        "legacy_mapping_version": 1,
        "plan": semantic_plan,
        "definitions": dict(report.definitions),
        "result": report.result_payload,
        "snapshot_id": report.snapshot_id,
    }
    scope = report.result_payload.get("scope")
    if not isinstance(scope, dict):
        raise MissingVisualEvidenceError()
    return VisualEvidence(
        report_id=report.report_id,
        section_id="legacy",
        analytical_revision=1,
        snapshot_id=report.snapshot_id,
        context_id=None,
        source_evidence_version=1,
        evidence_fingerprint=hashlib.sha256(_canonical(analytical).encode("utf-8")).hexdigest(),
        shape=shape,
        definition=FrozenDocument.from_dict(dict(report.definitions)),
        measure_ids=(plan.metric_id,),
        population=report.definitions["population"],
        grain=(
            next(
                (_LEGACY_GRAINS[field] for field in grouping if field in _LEGACY_GRAINS), "category"
            )
            if grouping
            else "scalar"
        ),
        dimensions=dimensions,
        scope=FrozenDocument.from_dict(scope),
        coverage=_unknown_coverage(),
        selection=VisualSelection(
            shown_groups=len(rows),
            returned_groups=len(rows),
            available_groups=None,
        ),
        missingness=FrozenDocument.from_dict({}),
        limitations=tuple(report.limitations)
        + ("Legacy evidence: exact total, reference status and bucket coverage may be unknown.",),
        format=FrozenDocument.from_dict({"locale": "en", "computed_places": 2, "rounding": None}),
        payload=FrozenDocument.from_dict(report.result_payload),
    )


def resolve_presentation(
    evidence: VisualEvidence,
    preference: SectionPresentationPreference | None = None,
) -> PresentationResolution:
    """Resolve a bounded compatible view without changing saved result facts."""
    preference = preference or SectionPresentationPreference()
    dimensions = evidence.dimensions
    first_ids = tuple(item.token for item in dimensions[0].identities) if dimensions else ()
    second_ids = (
        tuple(item.token for item in dimensions[1].identities) if len(dimensions) > 1 else ()
    )
    payload = evidence.payload.to_dict()
    values = payload.get("values", [])
    if not isinstance(values, list):
        raise VisualEvidenceError()
    ranking = evidence.shape == "ranking"
    selected_first = first_ids
    selected_second = second_ids
    subset_origin: Literal["all_returned", "default_ranking", "explicit"] = "all_returned"
    explicit_ids = tuple(preference.category_ids)
    explicit_series = tuple(preference.series_ids)
    table_requested = preference.chart_family == "table"
    if explicit_ids:
        if (
            (len(explicit_ids) > 20 and not table_requested)
            or len(set(explicit_ids)) != len(explicit_ids)
            or not set(explicit_ids) <= set(first_ids)
        ):
            raise PresentationPreferenceError()
        selected_first = tuple(token for token in first_ids if token in set(explicit_ids))
        subset_origin = "explicit"
    if explicit_series:
        if (
            (len(explicit_series) > 20 and not table_requested)
            or len(set(explicit_series)) != len(explicit_series)
            or not set(explicit_series) <= set(second_ids)
        ):
            raise PresentationPreferenceError()
        selected_second = tuple(token for token in second_ids if token in set(explicit_series))
        subset_origin = "explicit"
    omitted_tie = False
    if ranking and not explicit_ids and len(first_ids) > 20:
        selected_first = first_ids[:20]
        subset_origin = "default_ranking"
        ordered_values = _values_for_ids(values, 0, first_ids, dimensions[0])
        omitted_tie = _cutoff_tie(ordered_values, 20, evidence.measure_ids[0])
    if (
        evidence.shape == "category"
        and len(first_ids) > 20
        and not explicit_ids
        and not table_requested
    ):
        return _unresolved(
            evidence,
            "selection_required",
            "This unranked result has more than twenty categories. Select at most twenty or "
            "choose the exact evidence table; no categories were chosen automatically.",
            ("table",),
        )
    if evidence.shape == "time_series":
        if len(second_ids) > 20 and not explicit_series and not table_requested:
            return _unresolved(
                evidence,
                "selection_required",
                "This result has more than twenty series. Select at most twenty explicitly.",
                ("table",),
            )
        if len(selected_second) > 20 and not table_requested:
            raise PresentationPreferenceError()
    if len(selected_first) == 0 and first_ids or len(selected_second) == 0 and second_ids:
        raise PresentationPreferenceError()
    categories = selected_first
    series = selected_second
    selected_values = _select_values(values, dimensions, categories, series)
    has_data = _has_numeric_data(evidence, selected_values, payload)
    if evidence.shape == "weather":
        has_data = _weather_selection_has_pairs(
            payload,
            _default_weather_airport(payload),
            "temp",
        )
    shown = (
        len(selected_values)
        if len(dimensions) > 1 and subset_origin == "explicit"
        else evidence.selection.returned_groups
        if len(dimensions) > 1
        else len(categories)
        if dimensions
        else evidence.selection.returned_groups
    )
    selection = VisualSelection(
        category_ids=categories,
        series_ids=series,
        shown_groups=shown,
        returned_groups=evidence.selection.returned_groups,
        available_groups=evidence.selection.available_groups,
        shown_series=len(series) if len(dimensions) > 1 else None,
        returned_series=len(second_ids) if len(dimensions) > 1 else None,
        available_series=len(second_ids) if len(dimensions) > 1 else None,
        analytical_cutoff_tie=evidence.selection.analytical_cutoff_tie,
        visual_cutoff_tie=omitted_tie,
        subset_origin=subset_origin,
        weather_variable="temp" if evidence.shape == "weather" else None,
        weather_airport=(
            _default_weather_airport(payload) if evidence.shape == "weather" else None
        ),
    )
    default_view, compatible = _default_view(evidence, len(categories), len(series))
    if evidence.shape in {"relationship", "weather"}:
        pairing = _default_pairing(payload, selection.weather_airport)
        if pairing is not None and isinstance(pairing.get("density"), dict):
            default_view = "density"
            compatible = ("density", "table")
    requested_view = preference.chart_family
    view: View = default_view
    if requested_view != "default":
        if requested_view not in compatible:
            raise PresentationPreferenceError()
        view = requested_view
    if not has_data and view != "table":
        return PresentationResolution(
            state="no_plottable_data",
            evidence=evidence,
            selection=selection,
            compatible_views=compatible,
            reason="No finite observed values are available for this view. The saved evidence "
            "and unavailable reasons remain available in the exact table.",
        )
    if view != "table":
        if evidence.shape in {"category", "ranking"} and len(categories) > 20:
            raise PresentationPreferenceError()
        if evidence.shape == "time_series":
            if len(series) > 20 or (view == "line" and len(series) > 8):
                raise PresentationPreferenceError()
        if view == "grouped_bar" and (len(categories) > 20 or not 1 <= len(series) <= 8):
            view = "heatmap"
    state: Literal["ready", "table_selected"] = (
        "table_selected" if view == "table" and requested_view == "table" else "ready"
    )
    return PresentationResolution(
        state=state,
        evidence=evidence,
        view=view,
        selection=selection,
        compatible_views=compatible,
    )


def _unresolved(
    evidence: VisualEvidence,
    state: Literal[
        "selection_required", "no_plottable_data", "missing_evidence", "invalid_evidence"
    ],
    reason: str,
    views: tuple[View, ...],
) -> PresentationResolution:
    return PresentationResolution(
        state=state,
        evidence=evidence,
        selection=evidence.selection,
        compatible_views=views,
        reason=reason,
    )


def _values_for_ids(
    values: list[JsonValue],
    dimension: int,
    ids: tuple[str, ...],
    definition: VisualDimension,
) -> list[JsonValue]:
    token_set = set(ids)
    return [
        row
        for row in values
        if isinstance(row, dict)
        and isinstance(row.get("identity"), list)
        and len(row["identity"]) > dimension
        and _row_identity_token(row["identity"][dimension], definition) in token_set
    ]


def _select_values(
    values: list[JsonValue],
    dimensions: tuple[VisualDimension, ...],
    categories: tuple[str, ...],
    series: tuple[str, ...],
) -> list[JsonValue]:
    if not dimensions or not values:
        return values
    selected = _values_for_ids(values, 0, categories, dimensions[0])
    if len(dimensions) > 1:
        selected = [
            row
            for row in selected
            if isinstance(row, dict)
            and isinstance(row.get("identity"), list)
            and len(row["identity"]) > 1
            and _row_identity_token(row["identity"][1], dimensions[1]) in set(series)
        ]
    return selected


def _row_identity_token(identity: JsonValue, dimension: VisualDimension) -> str | None:
    if isinstance(identity, str):
        return identity
    if not isinstance(identity, dict):
        return None
    code = identity.get("code")
    status = identity.get("status")
    if status not in {"known", "missing", "unmatched_reference", "unknown"}:
        return None
    try:
        return canonical_identity(dimension.field_id, code, status)
    except VisualEvidenceError:
        return None


def _numeric_value(row: JsonValue, measure_id: str | None) -> int | float | None:
    if not isinstance(row, dict):
        return None
    measures = row.get("measures")
    if isinstance(measures, dict) and measure_id:
        item = measures.get(measure_id)
        if isinstance(item, dict):
            value = item.get("value")
            return value if type(value) in {int, float} else None
    value = row.get("value")
    if isinstance(value, dict):
        result = value.get("value")
        return result if type(result) in {int, float} else None
    return value if type(value) in {int, float} else None


def _has_numeric_data(
    evidence: VisualEvidence,
    rows: list[JsonValue],
    payload: dict[str, JsonValue],
) -> bool:
    if evidence.shape == "listing":
        return True
    if evidence.shape == "distribution":
        bins = payload.get("bins")
        if not isinstance(bins, list):
            return True
        return sum(item.get("count", 0) for item in bins if isinstance(item, dict)) > 0
    if evidence.shape in {"relationship", "weather"}:
        pairing = payload.get("pairing")
        if not isinstance(pairing, dict) and not isinstance(payload.get("pairs"), list):
            return True
        return _pair_count(payload) > 0
    if evidence.shape == "period_change":
        if "baseline" not in payload and "comparison" not in payload:
            return True
        return any(
            _numeric_value(payload.get(period, {}), evidence.measure_ids[0]) is not None
            for period in ("baseline", "comparison")
        )
    if evidence.shape == "scalar":
        raw = payload.get("value")
        if isinstance(raw, dict):
            return type(raw.get("value")) in {int, float}
        if rows:
            return any(_numeric_value(row, evidence.measure_ids[0]) is not None for row in rows)
        return True
    if not rows:
        return True
    return any(_numeric_value(row, evidence.measure_ids[0]) is not None for row in rows)


def _pair_count(payload: dict[str, JsonValue]) -> int:
    count = payload.get("pair_count")
    if type(count) is int:
        return count
    pairing = payload.get("pairing")
    if isinstance(pairing, dict):
        return _pair_count(pairing)
    variables = payload.get("variables")
    if isinstance(variables, list):
        return max(
            (
                _pair_count(item["pairing"])
                for item in variables
                if isinstance(item, dict) and isinstance(item.get("pairing"), dict)
            ),
            default=0,
        )
    pairs = payload.get("pairs")
    return len(pairs) if isinstance(pairs, list) else 0


def _weather_selection_has_pairs(
    payload: dict[str, JsonValue],
    airport: str | None,
    variable: str,
) -> bool:
    variables = payload.get("variables")
    if not isinstance(variables, list):
        return True
    selected = next(
        (
            item
            for item in variables
            if isinstance(item, dict)
            and item.get("origin") == airport
            and item.get("variable") == variable
        ),
        None,
    )
    if selected is None:
        return False
    pairing = selected.get("pairing")
    return isinstance(pairing, dict) and _pair_count(pairing) > 0


def _default_pairing(
    payload: dict[str, JsonValue],
    airport: str | None,
) -> dict[str, JsonValue] | None:
    if isinstance(payload.get("pairing"), dict):
        return payload["pairing"]
    variables = payload.get("variables")
    if not isinstance(variables, list):
        return None
    selected = next(
        (
            item
            for item in variables
            if isinstance(item, dict)
            and item.get("origin") == airport
            and item.get("variable") == "temp"
        ),
        None,
    )
    pairing = selected.get("pairing") if isinstance(selected, dict) else None
    return pairing if isinstance(pairing, dict) else None


def _default_weather_airport(payload: dict[str, JsonValue]) -> str | None:
    variables = payload.get("variables")
    if not isinstance(variables, list):
        return None
    airports = sorted(
        {
            row["origin"]
            for row in variables
            if isinstance(row, dict) and isinstance(row.get("origin"), str)
        }
    )
    return airports[0] if airports else None


def _default_view(
    evidence: VisualEvidence,
    primary: int,
    series: int,
) -> tuple[View, tuple[View, ...]]:
    choices = {
        "listing": ("table", ("table",)),
        "scalar": ("summary", ("summary", "table")),
        "category": ("bar", ("bar", "dot", "table")),
        "ranking": ("bar", ("bar", "dot", "table")),
        "time": ("line", ("line", "bar", "table")),
        "time_series": ("line", ("line", "small_multiples", "table")),
        "two_category": (
            ("grouped_bar" if primary <= 20 and series <= 8 else "heatmap"),
            ("grouped_bar", "heatmap", "table"),
        ),
        "period_change": ("bar", ("bar", "dot", "table")),
        "distribution": ("histogram", ("histogram", "table")),
        "relationship": ("scatter", ("scatter", "table")),
        "weather": ("scatter", ("scatter", "table")),
    }
    default, views = choices[evidence.shape]
    compatible = tuple(views)
    if evidence.shape == "time_series":
        if series > 20:
            return "small_multiples", ("table",)
        if series > 8:
            return "small_multiples", ("small_multiples", "table")
        return "line", ("line", "small_multiples", "table")
    if default == "heatmap":
        compatible = ("heatmap", "table")
    return default, compatible


def _views_for_shape(
    evidence: VisualEvidence,
    primary: int,
    series: int,
) -> tuple[View, ...]:
    _, views = _default_view(evidence, primary, series)
    return views


def _cutoff_tie(rows: list[JsonValue], shown: int, measure_id: str) -> bool:
    if len(rows) <= shown or shown <= 0:
        return False
    before = _numeric_value(rows[shown - 1], measure_id)
    after = _numeric_value(rows[shown], measure_id)
    return before is not None and after is not None and before == after
