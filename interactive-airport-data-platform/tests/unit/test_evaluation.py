import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from airport_analytics.analytics.evaluation import evaluate
from airport_analytics.models import AnalysisPlan


def test_evaluation_scores_generated_plans_and_numeric_results():
    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    questions = json.loads((fixtures / "golden_questions.json").read_text(encoding="utf-8"))
    expected = {
        item["id"]: item["rows"]
        for item in json.loads(
            (fixtures / "golden_expected_results.json").read_text(encoding="utf-8")
        )
    }

    class Generator:
        wrong_numbers = False
        wrong_metric = False

        def generate(self, text, **kwargs):
            question = next(item for item in questions if item["question"] == text)
            payload = deepcopy(question["plan"])
            if self.wrong_metric:
                payload["metric_id"] = "flight_count"
            rows = deepcopy(expected[question["id"]])
            if self.wrong_numbers:
                rows[0]["metric_value"] = -999
            return SimpleNamespace(
                plan=AnalysisPlan.model_validate(payload),
                status="report",
                report=SimpleNamespace(result_payload={"rows": rows}),
            )

    generator = Generator()
    result = evaluate(generator, questions, expected, session_state={})
    assert result["passed"]
    assert result["correct_interpretations"] == 12
    generator.wrong_numbers = True
    assert not evaluate(generator, questions, expected, session_state={})["passed"]
    generator.wrong_numbers = False
    generator.wrong_metric = True
    assert not evaluate(generator, questions, expected, session_state={})["passed"]
