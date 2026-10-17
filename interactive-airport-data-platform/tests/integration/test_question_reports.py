import json
from datetime import date, datetime
from pathlib import Path

import pytest

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.plan_schema import validate_analysis_plan

WORKSPACE = Path(__file__).resolve().parents[2]


def _normalize(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def test_twelve_golden_questions_match_independent_exact_results() -> None:
    questions = json.loads(
        (WORKSPACE / "tests" / "fixtures" / "golden_questions.json").read_text(encoding="utf-8")
    )
    expected_rows = {
        item["id"]: item["rows"]
        for item in json.loads(
            (WORKSPACE / "tests" / "fixtures" / "golden_expected_results.json").read_text(
                encoding="utf-8"
            )
        )
    }
    areas = {area: 0 for area in ("connectivity", "delays", "airlines", "aircraft")}
    for question in questions:
        areas[question["area"]] += 1
    assert len(questions) == 12
    assert areas == {area: 3 for area in areas}
    assert set(expected_rows) == {item["id"] for item in questions}

    with DuckDBExecutor(str(WORKSPACE / "source_data")) as executor:
        for question in questions:
            plan = validate_analysis_plan(question["plan"])
            assert plan.metric_id
            result = executor.execute(plan)
            actual_rows = [
                {key: _normalize(value) for key, value in row.items()} for row in result.rows
            ]
            expected = expected_rows[question["id"]]
            assert len(actual_rows) == len(expected)
            for actual_row, expected_row in zip(actual_rows, expected, strict=True):
                assert actual_row.keys() == expected_row.keys()
                for key, expected_value in expected_row.items():
                    actual_value = actual_row[key]
                    if isinstance(expected_value, float):
                        assert actual_value == pytest.approx(expected_value, abs=1e-12)
                    else:
                        assert actual_value == expected_value
