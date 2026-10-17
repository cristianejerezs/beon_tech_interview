"""Explicitly invoked provider acceptance evaluation; never runs during normal app use."""

from __future__ import annotations

import argparse
import json
import math
import platform
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from airport_analytics.analytics.budget import BudgetLedger
from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.model_client import LangChainPlanClient
from airport_analytics.analytics.provider_policy import mark_disclosed
from airport_analytics.config import Settings
from airport_analytics.errors import PlatformError
from airport_analytics.models import AnalysisPlan
from airport_analytics.observability.tracing import TracingConfig
from airport_analytics.reports.generation import ReportGenerator
from airport_analytics.storage import Storage


def _scope(plan: AnalysisPlan) -> dict[str, Any]:
    payload = plan.model_dump(mode="json")
    filters = sorted(payload["filters"], key=lambda item: json.dumps(item, sort_keys=True))
    for item in filters:
        if item["operator"] == "in" and len(item["value"]) == 1:
            item["operator"], item["value"] = "eq", item["value"][0]
    return {
        "metric": plan.metric_id,
        "groups": sorted(plan.group_by),
        "filters": filters,
        "period": payload["time_range"],
        "sort": payload["sort"],
        # Overall aggregates have exactly one output row irrespective of the limit.
        "limit": plan.row_limit if plan.group_by else 1,
    }


def _normal(value: Any) -> Any:
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def _rows_match(actual: list[dict], expected: list[dict]) -> bool:
    if len(actual) != len(expected):
        return False
    for left, right in zip(actual, expected, strict=True):
        if left.keys() != right.keys():
            return False
        for key, wanted in right.items():
            value = _normal(left[key])
            if isinstance(wanted, float):
                if not isinstance(value, (int, float)) or not math.isclose(
                    value, wanted, rel_tol=0, abs_tol=1e-12
                ):
                    return False
            elif value != wanted:
                return False
    return True


def evaluate(
    generator: ReportGenerator,
    questions: list[dict],
    expected: dict[str, list[dict]],
    *,
    session_state: dict[str, object],
) -> dict[str, Any]:
    if len(questions) != 12 or {item["id"] for item in questions} != set(expected):
        raise ValueError("Evaluation requires exactly the fixed 12 questions and matching results.")
    cases = []
    for question in questions:
        started = perf_counter()
        try:
            outcome = generator.generate(
                question["question"],
                analyst_id="evaluation-only",
                session_id="evaluation",
                session_state=session_state,
            )
        except PlatformError as exc:
            cases.append(
                {
                    "id": question["id"],
                    "seconds": perf_counter() - started,
                    "interpretation_matches": False,
                    "numeric_matches": False,
                    "error": exc.code,
                }
            )
            continue
        interpretation = (
            outcome.report is not None
            and outcome.plan.status == "ready"
            and _scope(outcome.plan) == _scope(AnalysisPlan.model_validate(question["plan"]))
        )
        numeric = outcome.report is not None and _rows_match(
            outcome.report.result_payload["rows"], expected[question["id"]]
        )
        cases.append(
            {
                "id": question["id"],
                "seconds": perf_counter() - started,
                "interpretation_matches": interpretation,
                "numeric_matches": numeric,
                "generated_report": outcome.report is not None,
                "status": outcome.status,
            }
        )
    interpreted = sum(item["interpretation_matches"] for item in cases)
    all_generated_correct = all(
        item["numeric_matches"] for item in cases if item.get("generated_report")
    )
    return {
        "cases": cases,
        "correct_interpretations": interpreted,
        "every_generated_numeric_result_matches": all_generated_correct,
        "passed": interpreted >= 11 and all_generated_correct,
        "scope_comparison": (
            "Strict catalog scope equality; equivalent alternate encodings need review."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live", action="store_true", help="Authorize live model requests.")
    parser.add_argument("--acknowledge-hosted-processing", action="store_true")
    parser.add_argument("--fixtures", type=Path, default=Path("tests") / "fixtures")
    args = parser.parse_args()
    if not args.run_live:
        parser.error("--run-live is required; this command dispatches real requests.")
    settings = Settings.from_env()
    if settings.model_provider != "ollama" and not args.acknowledge_hosted_processing:
        parser.error("Review provider/data-use terms, then pass --acknowledge-hosted-processing.")
    tracing = TracingConfig.from_env()
    if tracing.enabled:
        parser.error("Disable tracing for this evaluation; it is not needed for acceptance.")
    budget = BudgetLedger(
        Storage(settings.database_path),
        monthly_cap_usd=settings.deployment_monthly_budget_usd,
        free_monthly_request_limit=settings.free_monthly_request_limit,
        free_monthly_token_limit=settings.free_monthly_token_limit,
    )
    client = LangChainPlanClient(settings, budget=budget, tracing=tracing)
    state: dict[str, object] = {}
    mark_disclosed(state, client.provider)
    questions = json.loads((args.fixtures / "golden_questions.json").read_text(encoding="utf-8"))
    expected = {
        item["id"]: item["rows"]
        for item in json.loads(
            (args.fixtures / "golden_expected_results.json").read_text(encoding="utf-8")
        )
    }
    started = perf_counter()
    with DuckDBExecutor.from_settings(settings) as executor:
        load_seconds = perf_counter() - started
        result = evaluate(
            ReportGenerator(client, executor), questions, expected, session_state=state
        )
        result.update(
            provider=settings.model_provider,
            model=settings.model_name,
            snapshot=executor.manifest.snapshot_id,
            python=platform.python_version(),
            platform=platform.system(),
            timestamp=datetime.now(UTC).isoformat(),
            dataset_load_seconds=load_seconds,
            latency_method=(
                "First call cold/model-dependent; later calls warm, ordered golden corpus."
            ),
        )
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
