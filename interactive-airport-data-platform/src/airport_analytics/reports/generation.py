"""Plan-to-evidence report orchestration with deterministic, result-grounded narrative."""

from __future__ import annotations

import uuid
from collections.abc import MutableMapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from airport_analytics.analytics.execution import DuckDBExecutor, QueryResult
from airport_analytics.analytics.follow_up import merge_follow_up_plan
from airport_analytics.analytics.metrics import build_report_metadata
from airport_analytics.analytics.model_client import (
    FollowUpContext,
    LangChainPlanClient,
)
from airport_analytics.analytics.question_validation import validate_question
from airport_analytics.data.catalog import DIMENSIONS, METRICS
from airport_analytics.errors import InvalidPlanError
from airport_analytics.models import AnalysisPlan, ReportContent

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
