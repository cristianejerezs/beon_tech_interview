import json
import platform

import pytest

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.observability.timing import capture_stage_timings, timed_stage
from airport_analytics.reports.export import export_report_bundle
from airport_analytics.reports.generation import ExplorationReportGenerator
from airport_analytics.reports.rendering import summary_result_table
from tests.integration.test_exploration_provider import IntentModel, client_for
from tests.integration.test_exploration_summaries import FIXTURES


def test_stage_duration_has_no_arguments_names_content_or_exception_bodies(monkeypatch):
    import airport_analytics.observability.timing as timing

    clock = iter([1.0, 3.0])
    monkeypatch.setattr(timing, "perf_counter", lambda: next(clock))

    @timed_stage("execution")
    def sensitive_name(secret):
        raise ValueError(secret)

    with capture_stage_timings() as measured:
        with pytest.raises(ValueError):
            sensitive_name("private synthetic wording")
    assert measured == {"execution": 2.0}
    assert "private" not in json.dumps(measured)
    assert "sensitive_name" not in json.dumps(measured)
    sensitive_name_without_capture = timed_stage("execution")(lambda: 1)
    assert sensitive_name_without_capture() == 1


def test_nested_same_stage_is_not_double_counted(monkeypatch):
    import airport_analytics.observability.timing as timing

    clock = iter([1.0, 4.0])
    monkeypatch.setattr(timing, "perf_counter", lambda: next(clock))
    inner = timed_stage("execution")(lambda: "done")
    outer = timed_stage("execution")(inner)
    with capture_stage_timings() as measured:
        assert outer() == "done"
    assert measured == {"execution": 3.0}


def test_offline_cold_warm_stages_are_measured_separately(tmp_path, monkeypatch):
    client, _ = client_for(tmp_path, monkeypatch, IntentModel(), provider="ollama")
    measurements = []
    with capture_stage_timings() as cold:
        executor = DuckDBExecutor(str(FIXTURES))
        generator = ExplorationReportGenerator(client, executor)
        report = generator.generate(
            "Count flights",
            analyst_id="synthetic",
            session_id="synthetic",
            session_state={},
        ).report
        summary_result_table(report.sections[0].outcome.result)
        export_report_bundle(report, analyst_id="synthetic", session_id="synthetic")
    try:
        with capture_stage_timings() as warm:
            report = generator.generate(
                "Count flights",
                analyst_id="synthetic",
                session_id="synthetic",
                session_state={},
            ).report
            summary_result_table(report.sections[0].outcome.result)
            export_report_bundle(report, analyst_id="synthetic", session_id="synthetic")
        for thermal, captured in [("cold", cold), ("warm", warm)]:
            assert {
                "interpretation",
                "execution",
                "table_preparation",
                "export_generation",
            } <= captured.keys()
            assert all(duration > 0 for duration in captured.values())
            measurements.append(
                {
                    "thermal_state": thermal,
                    "stage_seconds": captured,
                    "snapshot_id": executor.manifest.snapshot_id,
                    "context_id": executor.context.context_id,
                    "python": platform.python_version(),
                    "platform": platform.system(),
                    "provider": "synthetic-stub",
                    "browser_ready": "not measured",
                    "chart_ready": "not run",
                }
            )
        assert cold["source_validation"] > 0
        assert "source_validation" not in warm
        print(json.dumps({"offline_stage_baselines": measurements}, sort_keys=True))
    finally:
        executor.close()
