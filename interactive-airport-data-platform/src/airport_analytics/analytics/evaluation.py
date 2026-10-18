"""Explicitly invoked provider acceptance evaluation; never runs during normal app use."""

from __future__ import annotations

import argparse
import json
import math
import platform
from datetime import UTC, date, datetime
from importlib.metadata import version
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
from airport_analytics.observability.timing import capture_stage_timings
from airport_analytics.observability.tracing import TracingConfig
from airport_analytics.reports.generation import ReportGenerator
from airport_analytics.storage import Storage


def compare_values(actual: Any, expected: Any) -> tuple[bool, list[float]]:
    """Exact discrete/null/shape comparison and documented finite float tolerance."""
    if isinstance(expected, int) and not isinstance(expected, bool):
        error = abs(actual - expected) if type(actual) is int else None
        return type(actual) is int and actual == expected, [
            float(error)
        ] if error is not None else []
    if expected is None or isinstance(expected, (str, bool)):
        return type(actual) is type(expected) and actual == expected, []
    if isinstance(expected, float):
        if isinstance(actual, bool) or not isinstance(actual, (int, float)):
            return False, []
        if not math.isfinite(actual) or not math.isfinite(expected):
            return False, []
        error = abs(actual - expected)
        return error <= max(1e-9, 1e-12 * abs(expected)), [float(error)]
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False, []
        shape_matches = len(actual) == len(expected)
        checks = [compare_values(a, b) for a, b in zip(actual, expected, strict=False)]
    elif isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False, []
        shape_matches = set(actual) == set(expected)
        checks = [compare_values(actual[key], expected[key]) for key in expected if key in actual]
    else:
        raise ValueError("Gold results must contain JSON-like finite values.")
    return shape_matches and all(item[0] for item in checks), [
        error for item in checks for error in item[1]
    ]


def canonical_interpretation(interpretation) -> dict[str, Any]:
    payload = interpretation.model_dump(mode="json")
    if interpretation.comparison is not None:
        from airport_analytics.analytics.multi_stage import comparison_periods

        baseline, comparison, _ = comparison_periods(interpretation.comparison)
        payload["comparison"] = {
            "baseline": baseline.model_dump(mode="json"),
            "comparison": comparison.model_dump(mode="json"),
        }
    filters = []
    for predicate in payload["filters"]:
        item = dict(predicate)
        if item["operator"] == "in":
            item["value"] = sorted(set(item["value"]), key=lambda value: json.dumps(value))
            if len(item["value"]) == 1:
                item["operator"], item["value"] = "eq", item["value"][0]
        filters.append(item)
    return {
        key: payload[key]
        for key in [
            "family",
            "operation_id",
            "measure_ids",
            "population",
            "grouping",
            "date_scope",
            "denominator_basis",
            "comparison",
            "binning",
            "pairing",
            "order",
            "selection",
        ]
    } | {"filters": sorted(filters, key=lambda item: json.dumps(item, sort_keys=True))}


def evaluate_exploration(generator, cases, gold, *, session_state):
    """Score every generated section even when its semantic scope is wrong."""
    from airport_analytics.analytics.evaluation_records import EvaluationCaseResult
    from airport_analytics.reports.export import export_report_bundle
    from airport_analytics.reports.rendering import section_evidence, summary_result_table

    results = []
    for case in cases:
        started = perf_counter()
        outcome = None
        timings = {}
        try:
            with capture_stage_timings() as timings:
                outcome = generator.generate(
                    case.text,
                    analyst_id="evaluation-only",
                    session_id="evaluation",
                    session_state=session_state,
                )
                if outcome.report is not None:
                    for section in outcome.report.sections:
                        evidence = section_evidence(section)
                        if evidence is not None:
                            summary_result_table(evidence)
                    export_report_bundle(
                        outcome.report,
                        analyst_id="evaluation-only",
                        session_id="evaluation",
                    )
        except (PlatformError, ValueError):
            results.append(
                EvaluationCaseResult(
                    case_id=case.case_id,
                    status="failed",
                    comparison_category="execution_failure",
                    generated_result=outcome is not None and outcome.report is not None,
                    seconds=perf_counter() - started,
                    stage_seconds=timings,
                )
            )
            continue
        semantics = (
            [canonical_interpretation(item) for item in outcome.interpretations]
            if outcome.report
            else []
        )
        generated = (
            [
                section_evidence(section).model_dump(
                    mode="json",
                    exclude={
                        "report_id",
                        "section_id",
                        "snapshot_id",
                        "context_id",
                    },
                )
                if section_evidence(section)
                else {"outcome": "failed"}
                for section in outcome.report.sections
            ]
            if outcome.report
            else []
        )
        interpretations_match = semantics == gold[case.interpretation_reference]
        numerical_match, errors = (
            compare_values(
                generated,
                gold[case.result_reference],
            )
            if case.result_reference
            else (not generated, [])
        )
        outcome_match = outcome.status == case.expected_outcome
        category = (
            "outcome_mismatch"
            if not outcome_match
            else "interpretation_mismatch"
            if not interpretations_match
            else "numeric_mismatch"
            if not numerical_match
            else "match"
        )
        results.append(
            EvaluationCaseResult(
                case_id=case.case_id,
                status="passed" if category == "match" else "failed",
                comparison_category=category,
                absolute_errors=errors,
                generated_result=outcome.report is not None,
                seconds=perf_counter() - started,
                stage_seconds=timings,
            )
        )
    return results


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
    parser.add_argument("--suite", choices=["legacy12", "v2"], default="legacy12")
    parser.add_argument("--corpus-version")
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--gold", type=Path)
    parser.add_argument("--thermal-state", choices=["cold", "warm"], default="cold")
    args = parser.parse_args()
    if not args.run_live:
        parser.error("--run-live is required; this command dispatches real requests.")
    cases = None
    gold = None
    if args.suite == "v2":
        from airport_analytics.analytics.evaluation_records import CorpusCase

        if not args.corpus or not args.gold or not args.corpus_version:
            parser.error("V2 requires --corpus, --gold and --corpus-version.")
        cases = [
            CorpusCase.model_validate(item)
            for item in json.loads(args.corpus.read_text(encoding="utf-8"))
        ]
        if not cases or any(item.corpus_version != args.corpus_version for item in cases):
            parser.error("Every case must match the explicitly selected corpus version.")
        if len({item.case_id for item in cases}) != len(cases):
            parser.error("Corpus case identities must be unique.")
        gold = json.loads(args.gold.read_text(encoding="utf-8"))
        if any(
            item.interpretation_reference not in gold
            or (item.result_reference and item.result_reference not in gold)
            for item in cases
        ):
            parser.error("Every case requires its exact gold references before dispatch.")
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
    client = LangChainPlanClient(
        settings,
        budget=budget,
        tracing=tracing,
        contract_version=2 if cases else 1,
    )
    state: dict[str, object] = {}
    mark_disclosed(state, client.provider)
    if cases:
        from airport_analytics.reports.generation import ExplorationReportGenerator

        started = perf_counter()
        with capture_stage_timings() as source_stages:
            executor = DuckDBExecutor.from_settings(settings)
        with executor:
            load_seconds = perf_counter() - started
            scored = evaluate_exploration(
                ExplorationReportGenerator(client, executor),
                cases,
                gold,
                session_state=state,
            )
            unambiguous = [item for item in cases if item.category == "unambiguous"]
            family_counts = {
                family: sum(item.family == family for item in unambiguous)
                for family in {item.family for item in unambiguous}
            }
            by_id = {item.case_id: item for item in scored}
            family_pass = {
                family: sum(
                    by_id[item.case_id].status == "passed"
                    for item in unambiguous
                    if item.family == family
                )
                for family in family_counts
            }
            negative = [item for item in cases if item.category == "negative"]
            airport = [item for item in cases if item.category == "airport_question"]
            airport_counts = {
                f"AQ-{index:02d}": sum(
                    item.airport_question_id == f"AQ-{index:02d}" for item in airport
                )
                for index in range(1, 11)
            }
            all_generated_match = all(
                item.status == "passed" for item in scored if item.generated_result
            )
            passed = (
                len(unambiguous) == 100
                and len(family_counts) == 10
                and all(value == 10 for value in family_counts.values())
                and sum(by_id[item.case_id].status == "passed" for item in unambiguous) >= 90
                and all(value >= 8 for value in family_pass.values())
                and len(negative) == 20
                and all(value >= 3 for value in airport_counts.values())
                and all(by_id[item.case_id].status == "passed" for item in [*negative, *airport])
                and all_generated_match
            )
            output = {
                "suite": "v2",
                "corpus_version": args.corpus_version,
                "snapshot": executor.manifest.snapshot_id,
                "context": executor.context.context_id,
                "provider": settings.model_provider,
                "model": settings.model_name,
                "python": platform.python_version(),
                "versions": {
                    package: version(package) for package in ["duckdb", "pydantic", "streamlit"]
                }
                | {"catalog": executor.context.catalog_version, "intent": "2", "evidence": "2"},
                "settings": {
                    "max_input_tokens": settings.max_input_tokens,
                    "max_output_tokens": settings.max_output_tokens,
                    "model_timeout_seconds": settings.model_timeout_seconds,
                    "query_timeout_seconds": settings.query_timeout_seconds,
                    "automatic_retries": 0,
                },
                "environment": {"platform": platform.system(), "machine": platform.machine()},
                "dataset_load_seconds": load_seconds,
                "cases": [item.model_dump() for item in scored],
                "thermal_state": args.thermal_state,
                "thermal_state_basis": "Operator-declared; no hidden warm-up or provider retry.",
                "stage_seconds": source_stages
                | {
                    stage: sum(item.stage_seconds.get(stage, 0.0) for item in scored)
                    for stage in sorted({key for item in scored for key in item.stage_seconds})
                },
                "browser_ready": "Not measured; table_preparation is server-side only.",
                "chart_ready": "Not run; depends on specification 003.",
                "family_counts": family_counts,
                "family_pass": family_pass,
                "airport_question_variant_counts": airport_counts,
                "numeric_and_semantic_thresholds_passed": passed,
                "independent_review_freeze_verified": False,
                "passed": False,
                "release_status": (
                    "Blocked: independent review/freeze and external acceptance are not verified."
                ),
            }
        print(json.dumps(output, indent=2))
        raise SystemExit(1)
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
