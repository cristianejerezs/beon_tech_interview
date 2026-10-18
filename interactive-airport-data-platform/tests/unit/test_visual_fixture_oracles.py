import json
from collections import Counter
from fractions import Fraction
from math import sqrt
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visual_reporting"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
EXAMPLES = MANIFEST["examples"]


def test_fixture_catalog_is_independent_traceable_and_covers_all_ten_rows():
    counts = Counter(example["row"] for example in EXAMPLES)
    assert len(counts) == 11  # Ten defaults plus the explicit weather bundle.
    assert all(count >= 3 for count in counts.values())
    assert len({example["id"] for example in EXAMPLES}) == len(EXAMPLES)
    assert all(example["refs"] for example in EXAMPLES)
    assert MANIFEST["fixture_version"] == 1


@pytest.mark.parametrize(
    "example",
    [example for example in EXAMPLES if "operation" in example],
    ids=lambda example: example["id"],
)
def test_handwritten_aggregate_expectations(example):
    source = example["source"]
    operation = example["operation"]
    if operation == "count":
        actual = len(source)
    elif operation == "mean":
        known = [Fraction(str(value)) for value in source if value is not None]
        actual = sum(known) / len(known) if known else None
    elif operation == "rank":
        actual = sorted(source, key=lambda row: (-Fraction(str(row[1])), row[0]))
    elif operation == "time":
        actual = sorted(source)
    else:
        assert operation == "identity"
        actual = source
    assert actual == example["expected"]


@pytest.mark.parametrize(
    "example",
    [example for example in EXAMPLES if example["row"] == "distribution"],
    ids=lambda example: example["id"],
)
def test_handwritten_interval_counts(example):
    values = [value for value in example["source"] if value is not None]
    edges = example["edges"]
    actual = [
        sum(
            lower <= value and (value < upper or (index == len(edges) - 2 and value == upper))
            for value in values
        )
        for index, (lower, upper) in enumerate(zip(edges, edges[1:], strict=False))
    ]
    assert actual == example["counts"]
    assert sum(actual) == len(values)
    assert example["missing"] == len(example["source"]) - len(values)


@pytest.mark.parametrize(
    "example",
    [example for example in EXAMPLES if example["row"] == "period_change"],
    ids=lambda example: example["id"],
)
def test_handwritten_period_changes(example):
    difference = example["comparison"] - example["baseline"]
    assert difference == example["absolute"]
    percentage = Fraction(100 * difference, example["baseline"]) if example["baseline"] else None
    assert percentage == example["relative_percent"]


@pytest.mark.parametrize(
    "example",
    [example for example in EXAMPLES if example["row"] == "weather"],
    ids=lambda example: example["id"],
)
def test_handwritten_weather_coefficients_separate_from_plot_eligibility(example):
    pairs = example["source"]
    if len(pairs) < 3:
        coefficient = None
    else:
        mean_x = sum(x for x, _ in pairs) / len(pairs)
        mean_y = sum(y for _, y in pairs) / len(pairs)
        products = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
        variance_x = sum((x - mean_x) ** 2 for x, _ in pairs)
        variance_y = sum((y - mean_y) ** 2 for _, y in pairs)
        coefficient = products / sqrt(variance_x * variance_y) if variance_x * variance_y else None
    assert coefficient == example["coefficient"]
    assert example["default_variable"] == "temp"
    assert example["view"] == ("scatter" if pairs else "no_plottable_data")


def test_frozen_historical_payloads_are_valid_original_formats():
    from airport_analytics.models import CompositeReportV2, ReportContent

    legacy = ReportContent.model_validate_json((FIXTURES / "legacy-v1.json").read_text())
    current = CompositeReportV2.model_validate_json((FIXTURES / "historical-v2.json").read_text())
    assert legacy.report_id == "visual-legacy"
    assert current.report_id == "report"
    assert current.sections[0].outcome.status == "completed"
    assert "presentation_preferences" not in json.loads((FIXTURES / "legacy-v1.json").read_text())
