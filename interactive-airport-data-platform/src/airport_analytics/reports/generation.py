"""Plan-to-evidence report orchestration with deterministic, result-grounded narrative."""

from __future__ import annotations

import uuid
from collections.abc import MutableMapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Literal

from airport_analytics.analytics.entity_resolution import EntityResolutionError
from airport_analytics.analytics.execution import DuckDBExecutor, QueryResult
from airport_analytics.analytics.follow_up import apply_scope_edits, merge_follow_up_plan
from airport_analytics.analytics.interpretation import (
    apply_clarification_choice,
    merge_clarification,
    resolve_proposal,
)
from airport_analytics.analytics.metrics import (
    build_listing_evidence,
    build_report_metadata,
    build_summary_evidence,
)
from airport_analytics.analytics.model_client import (
    FollowUpContext,
    LangChainPlanClient,
)
from airport_analytics.analytics.question_validation import validate_question
from airport_analytics.analytics.request_state import (
    PENDING_REQUEST_KEY,
    AnswerEvent,
    ExplorationRequest,
    begin_request,
    bind_proposal,
    fail_request,
    finish_execution,
    remove_pending_section,
    retry_request,
    start_execution,
    validate_answer,
)
from airport_analytics.data.catalog import DIMENSIONS, METRICS
from airport_analytics.errors import (
    AuthorizationError,
    DatasetUnavailableError,
    InvalidPlanError,
    PlatformError,
    QueryExecutionError,
    user_safe_message,
)
from airport_analytics.models import (
    AnalysisPlan,
    ClarificationSpec,
    CompletedSection,
    CompositeReportV2,
    EmptySection,
    ExplorationResult,
    FailedSection,
    FailureCategory,
    FieldProvenance,
    GroupedResult,
    IntentProposalV2,
    ListingResult,
    ReportContent,
    ReportSection,
    RequestDraft,
    ResolvedInterpretation,
    SafeFailure,
    SavedBucketCoverage,
    ScalarResult,
    ScopeEdit,
    TimeRange,
    VerifiedCoverageInterval,
)

OutcomeStatus = Literal["report", "needs_clarification", "unsupported", "empty"]


@dataclass(frozen=True)
class AnalysisOutcome:
    status: OutcomeStatus
    plan: AnalysisPlan
    report: ReportContent | None
    message: str
    query_result: QueryResult | None = None


def _format_number(value: object, unit: str) -> str:
    if value is None:
        return "not available"
    if isinstance(value, bool):
        rendered = str(value)
    elif isinstance(value, int):
        rendered = f"{value:,}"
    elif isinstance(value, float):
        rendered = f"{value:,.2f}"
    else:
        rendered = str(value)
    return f"{rendered} {unit}".strip()


def _save_bucket_coverage(
    evidence: ExplorationResult,
    executor: DuckDBExecutor,
) -> ExplorationResult:
    if not any(
        field.field_id in {"flight_date", "flight_week", "flight_month"}
        for field in evidence.fields
    ):
        return evidence
    declaration_hash = executor.context.coverage_sha256
    if not declaration_hash or not executor.coverage.days:
        return evidence
    period = evidence.scope.requested_period
    intervals: list[VerifiedCoverageInterval] = []
    for origin in sorted(evidence.scope.origins):
        days = sorted(
            day
            for day in executor.coverage.days.get(origin, ())
            if (period is None or period.start is None or day >= period.start)
            and (period is None or period.end is None or day <= period.end)
        )
        start = end = None
        for day in days:
            if end is not None and day == end + timedelta(days=1):
                end = day
                continue
            if start is not None and end is not None:
                intervals.append(VerifiedCoverageInterval(origin=origin, start=start, end=end))
            start = end = day
        if start is not None and end is not None:
            intervals.append(VerifiedCoverageInterval(origin=origin, start=start, end=end))
        if len(intervals) > 500:
            return evidence.model_copy(
                update={
                    "limitations": [
                        *evidence.limitations,
                        "Verified bucket coverage exceeds the saved 500-interval bound; "
                        "bucket completeness is unknown.",
                    ],
                }
            )
    if not intervals:
        return evidence
    coverage = SavedBucketCoverage(
        snapshot_id=evidence.snapshot_id,
        context_id=evidence.context_id,
        declaration_sha256=declaration_hash,
        intervals=intervals,
    )
    return evidence.model_copy(update={"bucket_coverage": coverage})


def _row_label(plan: AnalysisPlan, row: dict[str, object]) -> str:
    if not plan.group_by:
        return "the selected scope"
    dimension = plan.group_by[0]
    label = DIMENSIONS[dimension].dimension_id.replace("_", " ")
    value = row.get(dimension)
    return f"{label} {value if value is not None else 'unmatched'}"


def _narrative(plan: AnalysisPlan, result: QueryResult, metadata: dict) -> str:
    metric = METRICS[plan.metric_id]
    first = result.rows[0]
    label = _row_label(plan, first)
    value = _format_number(first["metric_value"], metric.unit)
    observations = int(first["observation_count"])
    flights = int(first["flight_count"])

    if metric.metric_id == "flight_count":
        answer = f"{value} were observed in {label}."
    elif plan.group_by:
        rank_word = ""
        if plan.sort is not None and plan.sort.field_id == plan.metric_id:
            rank_word = "Highest " if plan.sort.direction == "desc" else "Lowest "
        answer = f"{rank_word}{metric.description} for {label}: {value}."
    else:
        answer = f"{metric.description} for {label}: {value}."

    answer += (
        f" The displayed result represents {observations:,} metric observations "
        f"across {flights:,} matching flight records."
    )
    if plan.intent == "compare":
        answer += " Ranking differences are descriptive, not a statistical significance test."

    period = metadata["definitions"]["period"]
    origins = ", ".join(metadata["scope"]["geographic_coverage"])
    answer += f" Active period: {period}. Geographic coverage in the supplied snapshot: {origins}."
    return answer


class ReportGenerator:
    def __init__(self, model_client: LangChainPlanClient, executor: DuckDBExecutor) -> None:
        self.model_client = model_client
        self.executor = executor

    def generate(
        self,
        question: object,
        *,
        analyst_id: str,
        session_id: str,
        session_state: MutableMapping[str, object],
        follow_up_context: FollowUpContext | None = None,
    ) -> AnalysisOutcome:
        current_question = validate_question(question)
        generated = self.model_client.generate_plan(
            current_question,
            session_state=session_state,
            follow_up_context=follow_up_context,
        )
        plan = generated.plan
        if follow_up_context is not None and plan.status == "ready":
            plan = merge_follow_up_plan(
                follow_up_context.previous_plan,
                plan,
                current_question,
            )
        if plan.status == "needs_clarification":
            return AnalysisOutcome(
                status="needs_clarification",
                plan=plan,
                report=None,
                message=plan.clarification_question or "Please clarify the intended analysis.",
            )
        if plan.status == "unsupported":
            return AnalysisOutcome(
                status="unsupported",
                plan=plan,
                report=None,
                message=plan.unsupported_reason or "The requested analysis is unsupported.",
            )
        if plan.status != "ready" or plan.metric_id is None:
            raise InvalidPlanError("The validated plan has no executable outcome.")

        result = self.executor.execute(plan)
        if not result.rows or (len(result.rows) == 1 and result.rows[0].get("flight_count") == 0):
            return AnalysisOutcome(
                status="empty",
                plan=plan,
                report=None,
                message="No records match the requested scope. Try broadening the filters.",
                query_result=result,
            )

        metadata = build_report_metadata(plan, result)
        limitations = list(metadata["limitations"])
        if plan.intent == "compare":
            limitations.append(
                "Rankings are descriptive comparisons and do not test statistical significance."
            )
        payload = {
            "columns": list(result.columns),
            "rows": list(result.rows),
            "scope": metadata["scope"],
            "join_coverage": metadata["join_coverage"],
            "sample_counts": metadata["sample_counts"],
            "glossary": metadata["glossary"],
            "routes": result.routes,
            "ranking": result.ranking,
        }
        report = ReportContent(
            report_id=str(uuid.uuid4()),
            analyst_id=analyst_id,
            session_id=session_id,
            question=current_question,
            analysis_plan=plan,
            result_payload=payload,
            narrative=_narrative(plan, result, metadata),
            definitions=metadata["definitions"],
            limitations=list(dict.fromkeys(limitations)),
            snapshot_id=result.snapshot_id,
            created_at=datetime.now(UTC).isoformat(),
        )
        return AnalysisOutcome(
            status="report",
            plan=plan,
            report=report,
            message=report.narrative,
            query_result=result,
        )


@dataclass(frozen=True)
class ExplorationOutcome:
    status: Literal["report", "needs_clarification", "unsupported", "requires_selection"]
    draft: RequestDraft
    report: CompositeReportV2 | None
    message: str
    interpretations: tuple[ResolvedInterpretation, ...] = ()


class ExplorationReportGenerator:
    def refine_scope(
        self,
        report: CompositeReportV2,
        *,
        section_ids: set[str],
        edits: list[ScopeEdit],
        replace_dates: bool,
        date_scope: TimeRange | None,
        analyst_id: str,
        session_id: str,
    ) -> ExplorationOutcome:
        from airport_analytics.analytics.interpretation import _resolved_scope

        if report.analyst_id != analyst_id:
            raise AuthorizationError()
        report = CompositeReportV2.model_validate(report.model_dump())
        if not section_ids or not section_ids.issubset(
            {item.section_id for item in report.sections}
        ):
            raise InvalidPlanError("Explicitly choose the owned sections to refine.")
        if not edits and not replace_dates:
            raise InvalidPlanError("Choose at least one explicit scope change.")
        self.executor.require_current_binding(report.snapshot_id, report.context_id)
        revision = report.revision + 1
        interpretations = []
        for section in report.sections:
            original = section.interpretation
            changes = {"revision": revision}
            if section.section_id in section_ids:
                applied = list(edits)
                if replace_dates:
                    applied.append(
                        ScopeEdit(
                            field_id="flight_date",
                            action="remove",
                            operator=None,
                            value=None,
                        )
                    )
                filters, entities = _resolved_scope(
                    None,
                    apply_scope_edits(original.filters, applied),
                    self.executor.entity_directory(),
                )
                provenance = dict(original.field_provenance)
                for field in ["filters", *(["date_scope"] if replace_dates else [])]:
                    provenance[field] = FieldProvenance(source="correction", revision=revision)
                changes.update(filters=filters, entities=entities, field_provenance=provenance)
                if replace_dates:
                    changes["date_scope"] = date_scope
            interpretations.append(
                ResolvedInterpretation.model_validate(original.model_dump() | changes)
            )
        draft = RequestDraft(
            request_id=interpretations[0].request_id,
            revision=revision,
            original_question=report.question,
            session_binding=session_id,
            shared_scope=report.shared_scope,
            removed_sections=report.removed_sections,
        )
        return self.execute_interpretations(
            draft,
            interpretations,
            analyst_id=analyst_id,
            session_id=session_id,
            parent_report_id=report.report_id,
        )

    def accept_bin_width(
        self,
        *,
        width: float,
        section_id: str,
        analyst_id: str,
        session_id: str,
        session_state: MutableMapping[str, object],
    ) -> ExplorationOutcome:
        from airport_analytics.models import BinningSpec

        state = session_state.get(PENDING_REQUEST_KEY)
        if not isinstance(state, ExplorationRequest) or state.proposal is None:
            raise ValueError("There is no pending interpretation.")
        self._require_current(state, session_id)
        index = next(
            (
                index
                for index, section in enumerate(state.draft.sections)
                if section.section_id == section_id
            ),
            None,
        )
        if index is None or state.proposal.sections[index].operation_id != "distribution":
            raise ValueError("Choose the current distribution section.")
        if state.draft.state not in {"failed", "guided_correction", "clarification_pending"}:
            raise ValueError("This request does not accept a pending analytical correction.")
        payload = state.proposal.model_dump()
        payload["sections"][index]["binning"] = BinningSpec(width=width, accepted=True).model_dump()
        payload["sections"][index]["status"] = "proposed"
        payload["sections"][index]["clarification"] = None
        payload["sections"][index]["unsupported_reason"] = None
        payload["status"] = (
            "needs_clarification"
            if any(item["status"] == "needs_clarification" for item in payload["sections"])
            else "proposed"
        )
        state = bind_proposal(
            replace(
                state,
                draft=state.draft.model_copy(
                    update={
                        "state": "unresolved",
                        "revision": state.draft.revision + 1,
                    }
                ),
            ),
            IntentProposalV2.model_validate(payload),
        )
        session_state[PENDING_REQUEST_KEY] = state
        return self._process_request(
            state, analyst_id, session_id, session_state, provenance="correction"
        )

    def remove_section(
        self,
        *,
        section_id: str,
        analyst_id: str,
        session_id: str,
        session_state: MutableMapping[str, object],
        request_id: str,
        revision: int,
    ) -> ExplorationOutcome:
        state = session_state.get(PENDING_REQUEST_KEY)
        if not isinstance(state, ExplorationRequest):
            raise ValueError("There is no pending request to modify.")
        self._require_current(state, session_id)
        state = remove_pending_section(
            state,
            section_id,
            session_id=session_id,
            request_id=request_id,
            revision=revision,
        )
        session_state[PENDING_REQUEST_KEY] = state
        return self._process_request(state, analyst_id, session_id, session_state)

    def __init__(self, model_client: LangChainPlanClient, executor: DuckDBExecutor) -> None:
        self.model_client = model_client
        self.executor = executor

    def generate(
        self,
        question: object,
        *,
        analyst_id: str,
        session_id: str,
        session_state: MutableMapping[str, object],
        follow_up_context: ResolvedInterpretation | None = None,
    ) -> ExplorationOutcome:
        state = begin_request(
            question,
            session_id,
            self.executor.manifest.snapshot_id,
            self.executor.context.context_id,
            follow_up_context,
        )
        session_state[PENDING_REQUEST_KEY] = state
        return self.resume_initial(
            state, analyst_id=analyst_id, session_id=session_id, session_state=session_state
        )

    def _record_failure(
        self,
        state: ExplorationRequest,
        session_state: MutableMapping[str, object],
        error: Exception,
    ) -> None:
        code = error.code if isinstance(error, PlatformError) else "execution_failed"
        category: FailureCategory = (
            "invalid_provider_output"
            if isinstance(error, InvalidPlanError)
            else "disclosure_refused"
            if "disclosure" in code
            else "budget_refused"
            if any(word in code for word in ["budget", "cost", "quota"])
            else "source_unavailable"
            if any(word in code for word in ["snapshot", "dataset", "context"])
            else "provider_unavailable"
            if "provider" in code
            else "execution_failed"
        )
        session_state[PENDING_REQUEST_KEY] = fail_request(
            state,
            SafeFailure(category=category, code=code, message=user_safe_message(error)),
        )

    def _require_current(self, state: ExplorationRequest, session_id: str) -> None:
        if state.draft.session_binding != session_id:
            raise ValueError("This request belongs to another session.")
        binding = state.draft.snapshot_binding
        if binding is None:
            raise ValueError("This request has no source binding.")
        self.executor.require_current_binding(binding.snapshot_id, binding.context_id)

    def resume_initial(
        self,
        state: ExplorationRequest,
        *,
        analyst_id: str,
        session_id: str,
        session_state: MutableMapping[str, object],
    ) -> ExplorationOutcome:
        if state.draft.state != "unresolved":
            raise ValueError("Only an unresolved request may be submitted.")
        if session_state.get(PENDING_REQUEST_KEY) != state:
            raise ValueError("This request has been replaced.")
        try:
            self._require_current(state, session_id)
            if state.previous is not None:
                self.executor.require_current_binding(
                    state.previous.snapshot_id,
                    state.previous.context_id,
                )
            generated = self.model_client.generate_intent(
                state.draft.original_question,
                session_state=session_state,
                follow_up_context=state.previous,
            )
            state = bind_proposal(state, generated.proposal)
            session_state[PENDING_REQUEST_KEY] = state
            return self._process_request(state, analyst_id, session_id, session_state)
        except Exception as exc:
            self._record_failure(state, session_state, exc)
            raise

    def answer(
        self,
        state: ExplorationRequest,
        event: AnswerEvent,
        *,
        analyst_id: str,
        session_id: str,
        session_state: MutableMapping[str, object],
    ) -> ExplorationOutcome:
        current = session_state.get(PENDING_REQUEST_KEY)
        if current != state:
            raise ValueError("This pending request has been replaced.")
        event = validate_answer(state, event, session_id)
        try:
            self._require_current(state, session_id)
            if state.proposal is None:
                raise ValueError("No candidate interpretation is available.")
            position = state.active_section.position
            if event.choice_id is not None:
                spec = state.active_section.clarification
                if spec is None:
                    raise ValueError("The clarification is no longer available.")
                choice = next(item for item in spec.choices if item.choice_id == event.choice_id)
                proposal = apply_clarification_choice(
                    state.proposal,
                    position,
                    choice,
                    self.executor.entity_directory(),
                )
            else:
                response = self.model_client.generate_clarification(
                    state.draft.original_question,
                    event.text,
                    state.proposal,
                    position,
                    session_state=session_state,
                    follow_up_context=state.previous,
                )
                try:
                    proposal = merge_clarification(state.proposal, response.proposal, position)
                except ValueError as exc:
                    raise InvalidPlanError(
                        "The clarification response changed incompatible request structure."
                    ) from exc
            state = bind_proposal(state, proposal, answered=True)
            session_state[PENDING_REQUEST_KEY] = state
            return self._process_request(state, analyst_id, session_id, session_state)
        except Exception as exc:
            self._record_failure(state, session_state, exc)
            raise

    def retry(
        self,
        state: ExplorationRequest,
        *,
        analyst_id: str,
        session_id: str,
        session_state: MutableMapping[str, object],
    ) -> ExplorationOutcome:
        if session_state.get(PENDING_REQUEST_KEY) != state:
            raise ValueError("This request has been replaced.")
        state = retry_request(state, session_id)
        session_state[PENDING_REQUEST_KEY] = state
        if state.draft.state == "unresolved":
            return self.resume_initial(
                state, analyst_id=analyst_id, session_id=session_id, session_state=session_state
            )
        if state.draft.state == "resolved":
            try:
                self._require_current(state, session_id)
                return self._process_request(state, analyst_id, session_id, session_state)
            except Exception as exc:
                self._record_failure(state, session_state, exc)
                raise
        return ExplorationOutcome(
            status="needs_clarification",
            draft=state.draft,
            report=None,
            message="Review the retained clarification and explicitly submit your answer.",
        )

    def correct_pending(
        self,
        state: ExplorationRequest,
        proposal: IntentProposalV2,
        *,
        analyst_id: str,
        session_id: str,
        session_state: MutableMapping[str, object],
    ) -> ExplorationOutcome:
        if session_state.get(PENDING_REQUEST_KEY) != state:
            raise ValueError("This request has been replaced.")
        if state.draft.state not in {"guided_correction", "clarification_pending", "failed"}:
            raise ValueError("This request does not accept a correction.")
        self._require_current(state, session_id)
        corrected_section_id = state.active_section.section_id
        if state.proposal is not None and len(state.proposal.sections) > 1:
            if len(proposal.sections) != 1:
                raise ValueError("Guided correction must explicitly target the focused section.")
            if proposal.shared_scope.edits != state.proposal.shared_scope.edits:
                raise ValueError(
                    "A focused correction cannot change other sections' shared filters."
                )
            position = state.active_section.position
            candidate = proposal.sections[0].model_copy(deep=True)
            candidate.position = position
            candidate.original_clause = state.proposal.sections[position - 1].original_clause
            if proposal.shared_scope.dates != state.proposal.shared_scope.dates:
                from airport_analytics.models import ScopeEdit

                candidate.scope_edits = [
                    edit for edit in candidate.scope_edits if edit.field_id != "flight_date"
                ] + [ScopeEdit(field_id="flight_date", action="remove", operator=None, value=None)]
                if proposal.shared_scope.dates is not None:
                    for boundary, operator in [
                        (proposal.shared_scope.dates.start, "gte"),
                        (proposal.shared_scope.dates.end, "lte"),
                    ]:
                        if boundary is not None:
                            candidate.scope_edits.append(
                                ScopeEdit(
                                    field_id="flight_date",
                                    action="add",
                                    operator=operator,
                                    value=boundary.isoformat(),
                                )
                            )
            payload = state.proposal.model_dump(mode="json")
            payload["sections"][position - 1] = candidate.model_dump(mode="json")
            statuses = {section["status"] for section in payload["sections"]}
            payload["status"] = (
                "unsupported"
                if "unsupported" in statuses
                else ("needs_clarification" if "needs_clarification" in statuses else "proposed")
            )
            proposal = IntentProposalV2.model_validate(payload)
        state = replace(
            state,
            draft=state.draft.model_copy(
                update={
                    "state": "unresolved",
                    "revision": state.draft.revision + 1,
                }
            ),
        )
        state = bind_proposal(state, proposal)
        session_state[PENDING_REQUEST_KEY] = state
        try:
            return self._process_request(
                state,
                analyst_id,
                session_id,
                session_state,
                provenance="correction",
                corrected_section_id=corrected_section_id,
            )
        except Exception as exc:
            self._record_failure(state, session_state, exc)
            raise

    def _process_request(
        self,
        state: ExplorationRequest,
        analyst_id: str,
        session_id: str,
        session_state: MutableMapping[str, object],
        provenance: Literal["correction"] | None = None,
        corrected_section_id: str | None = None,
    ) -> ExplorationOutcome:
        draft = state.draft
        proposal = state.proposal
        if proposal is None:
            raise ValueError("A validated candidate is required.")
        if proposal.status != "proposed":
            message = proposal.selection_reason or next(
                (
                    section.clarification.question
                    if section.clarification is not None
                    else section.unsupported_reason
                    for section in proposal.sections
                    if section.clarification is not None or section.unsupported_reason
                ),
                "Please clarify the intended analysis.",
            )
            return ExplorationOutcome(
                status=proposal.status,
                draft=draft,
                report=None,
                message=message,
            )
        if proposal.sections[0].operation_id is None:
            session_state[PENDING_REQUEST_KEY] = replace(
                state,
                draft=state.draft.model_copy(update={"state": "guided_correction"}),
            )
            return ExplorationOutcome(
                status="unsupported",
                draft=draft,
                report=None,
                message=(
                    "This operation is not integrated yet. "
                    "Scalar/grouped summaries, entity lists and flight records are available."
                ),
            )
        try:
            interpretations = resolve_proposal(
                draft,
                proposal,
                self.executor.entity_directory(),
                snapshot_id=self.executor.manifest.snapshot_id,
                context_id=self.executor.context.context_id,
                previous=state.previous,
            )
        except (EntityResolutionError, ValueError) as exc:
            from airport_analytics.analytics.interpretation import SectionResolutionError

            position = exc.position if isinstance(exc, SectionResolutionError) else 1
            error = exc.error if isinstance(exc, SectionResolutionError) else exc
            focused = proposal.sections[position - 1]
            candidate = focused.model_dump(mode="json")
            candidate.update(
                status="needs_clarification",
                unsupported_reason=None,
                clarification=ClarificationSpec(
                    field_id=(
                        focused.entity_mentions[0].kind
                        if focused.entity_mentions
                        else "comparison"
                        if focused.operation_id == "period_change"
                        else "scope"
                    ),
                    question=(
                        str(error)
                        if isinstance(error, EntityResolutionError)
                        else "Which scope or grouping should be used? Review the interpretation."
                    ),
                    choices=[],
                ).model_dump(mode="json"),
            )
            payload = proposal.model_dump(mode="json")
            payload["sections"][position - 1] = candidate
            payload["status"] = "needs_clarification"
            state = bind_proposal(
                replace(state, draft=state.draft.model_copy(update={"state": "unresolved"})),
                IntentProposalV2.model_validate(payload),
            )
            session_state[PENDING_REQUEST_KEY] = state
            return ExplorationOutcome(
                status="needs_clarification",
                draft=state.draft,
                report=None,
                message=(
                    str(error)
                    if isinstance(error, EntityResolutionError)
                    else (
                        "The requested scope or grouping needs correction. "
                        "No analytical query was executed."
                    )
                ),
            )
        revised_interpretations = []
        for item, section_draft in zip(interpretations, state.draft.sections, strict=True):
            correction = provenance if corrected_section_id in {None, item.section_id} else None
            if correction is None and not section_draft.answered_turns:
                revised_interpretations.append(item)
                continue
            source = correction or "clarification"
            clarified = {choice.choice for choice in section_draft.choices}
            clarified_fields = {
                "date_scope"
                if field in {"dates", "date_scope", "flight_date"}
                else "measure_ids"
                if field in {"measure", "measure_ids"}
                else "operation_id"
                if field in {"operation", "operation_id"}
                else "grouping"
                if field in {"grouping", "dimension"}
                else field
                if field in {"family", "population", "order", "selection"}
                else "filters"
                for field in clarified
            }
            revised_interpretations.append(
                item.model_copy(
                    update={
                        "field_provenance": {
                            key: value.model_copy(update={"source": source})
                            if value.source == "explicit"
                            and (correction == "correction" or key in clarified_fields)
                            else value
                            for key, value in item.field_provenance.items()
                        }
                    }
                )
            )
        interpretations = revised_interpretations
        sections = [
            section.model_copy(update={"interpretation": interpretation, "status": "resolved"})
            for section, interpretation in zip(state.draft.sections, interpretations, strict=True)
        ]
        state = replace(
            state,
            draft=RequestDraft.model_validate(
                state.draft.model_dump(mode="json") | {"sections": sections}
            ),
        )
        draft = state.draft
        executing = start_execution(state)
        session_state[PENDING_REQUEST_KEY] = executing
        outcome = self.execute_interpretations(
            draft,
            interpretations,
            analyst_id=analyst_id,
            session_id=session_id,
        )
        session_state[PENDING_REQUEST_KEY] = finish_execution(
            executing,
            "incomplete"
            if outcome.report and outcome.report.completeness == "incomplete"
            else "completed",
        )
        return outcome

    def execute_interpretations(
        self,
        draft: RequestDraft,
        interpretations: list[ResolvedInterpretation],
        *,
        analyst_id: str,
        session_id: str,
        parent_report_id: str | None = None,
    ) -> ExplorationOutcome:
        if not 1 <= len(interpretations) <= 4:
            raise InvalidPlanError("Choose one to four resolved sections.")
        if any(
            item.request_id != draft.request_id
            or item.revision != draft.revision
            or item.snapshot_id != interpretations[0].snapshot_id
            or item.context_id != interpretations[0].context_id
            for item in interpretations
        ):
            raise InvalidPlanError("All sections must share the current request and snapshot.")
        report_id = str(uuid.uuid4())
        for interpretation in interpretations:
            if interpretation.operation_id == "distribution":
                self.executor.execute_multi_stage(
                    interpretation,
                    report_id=report_id,
                    preflight=True,
                )
        sections = []
        base = None
        for position, interpretation in enumerate(interpretations, 1):
            try:
                outcome = self._execute_one(
                    draft,
                    [interpretation],
                    analyst_id=analyst_id,
                    session_id=session_id,
                    parent_report_id=parent_report_id,
                )
            except (QueryExecutionError, DatasetUnavailableError) as exc:
                sections.append(
                    ReportSection(
                        section_id=interpretation.section_id,
                        position=position,
                        label=interpretation.original_clause,
                        interpretation=interpretation,
                        narrative="This section did not produce an analytical answer.",
                        outcome=FailedSection(
                            status="failed",
                            failure=SafeFailure(
                                category="source_unavailable"
                                if isinstance(exc, DatasetUnavailableError)
                                else "execution_failed",
                                code=exc.code,
                                message=user_safe_message(exc),
                            ),
                        ),
                    )
                )
                continue
            current = outcome.report
            base = base or current
            section = current.sections[0]
            result = (
                section.outcome.result
                if section.outcome.status == "completed"
                else section.outcome.evidence
            )
            payload = section.outcome.model_dump()
            payload["result" if section.outcome.status == "completed" else "evidence"] = (
                result.model_copy(update={"report_id": report_id})
            )
            sections.append(
                ReportSection.model_validate(
                    section.model_dump()
                    | {
                        "position": position,
                        "outcome": payload,
                    }
                )
            )
        if base is None:
            raise QueryExecutionError("Every requested section failed; no report was saved.")
        complete = all(section.outcome.status != "failed" for section in sections)
        report = CompositeReportV2.model_validate(
            base.model_dump()
            | {
                "report_id": report_id,
                "sections": sections,
                "completeness": "complete" if complete else "incomplete",
            }
        )
        return ExplorationOutcome(
            status="report",
            draft=draft,
            report=report,
            message="All sections completed."
            if complete
            else (
                "Incomplete report: review failed sections and explicitly acknowledge "
                "before saving."
            ),
            interpretations=tuple(interpretations),
        )

    def _execute_one(
        self,
        draft: RequestDraft,
        interpretations: list[ResolvedInterpretation],
        *,
        analyst_id: str,
        session_id: str,
        parent_report_id: str | None = None,
    ) -> ExplorationOutcome:
        if len(interpretations) != 1:
            raise InvalidPlanError("One resolved section is required in the current story.")
        interpretation = ResolvedInterpretation.model_validate(
            interpretations[0].model_dump(mode="json")
        )
        if (
            interpretation.request_id != draft.request_id
            or interpretation.revision != draft.revision
        ):
            raise InvalidPlanError(
                "The interpretation does not match the current request revision."
            )
        report_id = str(uuid.uuid4())
        if interpretation.operation_id in {"entity_list", "flight_records"}:
            page = self.executor.browse(
                interpretation,
                analyst_id=analyst_id,
                session_id=session_id,
            )
            evidence = build_listing_evidence(interpretation, page, report_id=report_id)
        elif interpretation.operation_id in {
            "aggregate",
            "departure_delay_total",
            "aircraft_frequency",
        }:
            result = self.executor.execute_summary(interpretation)
            evidence = build_summary_evidence(interpretation, result, report_id=report_id)
        else:
            evidence = self.executor.execute_multi_stage(interpretation, report_id=report_id)
        evidence = _save_bucket_coverage(evidence, self.executor)
        empty = (
            evidence.total_rows == 0
            if isinstance(evidence, ListingResult)
            else evidence.missingness["filtered_flights"] == 0
        )
        if empty:
            outcome = EmptySection(status="valid_empty", evidence=evidence)
            narrative = "No records match the requested scope."
        else:
            outcome = CompletedSection(status="completed", result=evidence)
            if isinstance(evidence, ScalarResult):
                narrative = (
                    f"{_format_number(evidence.value.value, evidence.definition.unit)} "
                    f"in the selected scope; {evidence.missingness['filtered_flights']:,} "
                    "matching flight records."
                )
            elif isinstance(evidence, GroupedResult):
                narrative = (
                    f"Showing {evidence.selection.selected:,} of {evidence.selection.available:,} "
                    f"groups; {evidence.missingness['filtered_flights']:,} "
                    "matching flight records. "
                    "Values are computed independently at the displayed group grain."
                )
            elif isinstance(evidence, ListingResult):
                narrative = (
                    f"Showing {len(evidence.rows):,} of {evidence.total_rows:,} "
                    f"{evidence.population.replace('_', ' ')} records. "
                    "The saved preview is bounded; browsing and export are explicit local actions."
                )
            else:
                narrative = (
                    f"{interpretation.operation_id.replace('_', ' ').title()}: "
                    f"{evidence.missingness['filtered_flights']:,} scoped historical records. "
                    "Exact values, unavailable reasons and limitations are retained below."
                )
        if evidence.kind == "weather_panel":
            from airport_analytics.reports.rendering import weather_findings

            narrative = weather_findings(evidence)
        elif "month_of_year" in interpretation.grouping:
            narrative += (
                " Month-of-year groups pool the same named month across all years in the "
                "selected scope; they are not separate calendar year-months."
            )
        report = CompositeReportV2(
            report_version=2,
            report_id=report_id,
            analyst_id=analyst_id,
            session_id=session_id,
            parent_report_id=parent_report_id,
            question=draft.original_question,
            revision=draft.revision,
            created_at=datetime.now(UTC),
            snapshot_id=interpretation.snapshot_id,
            context_id=interpretation.context_id,
            versions={
                "catalog": self.executor.context.catalog_version,
                "aliases": self.executor.context.alias_version,
                "rules": self.executor.context.rules_version,
                "units": str(self.executor.context.unit_provenance),
                "coverage": self.executor.context.coverage_status,
            },
            shared_scope=draft.shared_scope,
            removed_sections=draft.removed_sections,
            sections=[
                ReportSection(
                    section_id=interpretation.section_id,
                    position=1,
                    label=interpretation.original_clause,
                    interpretation=interpretation,
                    narrative=narrative,
                    outcome=outcome,
                )
            ],
            completeness="complete",
            incomplete_acknowledgement=None,
            presentation_preferences={},
            preference_version=1,
        )
        return ExplorationOutcome(
            status="report",
            draft=draft,
            report=report,
            message=narrative,
            interpretations=tuple(interpretations),
        )
