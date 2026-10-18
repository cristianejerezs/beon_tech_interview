from datetime import date

import pytest

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.models import DistributionResult, PeriodChangeResult, RelationshipResult
from tests.exploration_oracles import number, read_rows
from tests.integration.test_exploration_summaries import FIXTURES, evidence, generate


def test_distribution_includes_negative_zero_and_all_known_values():
    values = [
        number(row["dep_delay"])
        for row in read_rows(FIXTURES / "nyc_flights_fixed.csv")
        if number(row["dep_delay"]) is not None
    ]
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = evidence(
            generate(
                executor,
                family="distribution",
                operation_id="distribution",
                measure_ids=["departure_delay"],
            )
        )
    assert isinstance(result, DistributionResult)
    assert result.width == 15
    assert result.known_count == len(values)
    assert result.missing_count + result.known_count == 9
    for index, bin in enumerate(result.bins):
        assert bin.count == sum(bin.lower <= value < bin.upper for value in values)
        assert bin.upper_inclusive == (index == len(result.bins) - 1)
    assert result.bins[-1].upper > max(values)


def test_flight_pairs_preserve_source_identities_and_disjoint_missingness():
    rows = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    expected = [
        (row["column00"], number(row["dep_delay"]), number(row["arr_delay"]))
        for row in rows
        if number(row["dep_delay"]) is not None and number(row["arr_delay"]) is not None
    ]
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = evidence(
            generate(
                executor,
                family="numeric_relationship",
                operation_id="flight_relationship",
                measure_ids=["departure_delay", "arrival_delay"],
                pairing={"x": "departure_delay", "y": "arrival_delay"},
            )
        )
    assert isinstance(result, RelationshipResult)
    assert [(p.source_id, p.x, p.y) for p in result.pairing.pairs] == expected
    assert result.pairing.scoped_count == len(rows)


def test_period_change_uses_exact_inclusive_windows_and_zero_baseline():
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = evidence(
            generate(
                executor,
                family="period_change",
                operation_id="period_change",
                measure_ids=["flight_count"],
                comparison={
                    "baseline": {"start": "2012-12-30", "end": "2012-12-31"},
                    "comparison": {"start": "2013-01-01", "end": "2013-01-02"},
                },
            )
        )
    assert isinstance(result, PeriodChangeResult)
    assert result.baseline.day_exposure == 2
    assert result.baseline.value.value == 0
    assert result.relative_change.value is None
    assert "baseline is zero" in " ".join(result.warnings)
    assert result.comparison.period.start == date(2013, 1, 1)


@pytest.mark.parametrize(
    "rule,start,end,expected_start,expected_end,clamped",
    [
        ("previous_equal_days", "2013-03-01", "2013-03-03", "2013-02-26", "2013-02-28", False),
        ("previous_month", "2012-03-01", "2012-03-31", "2012-02-01", "2012-02-29", False),
        ("previous_month", "2013-03-30", "2013-03-31", "2013-02-28", "2013-02-28", True),
        ("previous_month", "2013-02-01", "2013-02-28", "2013-01-01", "2013-01-31", False),
        ("previous_year", "2012-02-29", "2012-03-03", "2011-02-28", "2011-03-03", True),
        ("previous_year", "2013-01-01", "2013-12-31", "2012-01-01", "2012-12-31", False),
    ],
)
def test_application_owned_previous_period_calendar_rules(
    rule,
    start,
    end,
    expected_start,
    expected_end,
    clamped,
):
    from airport_analytics.analytics.multi_stage import comparison_periods
    from airport_analytics.models import ComparisonSpec

    baseline, current, warnings = comparison_periods(
        ComparisonSpec(
            baseline=None,
            comparison={"start": start, "end": end},
            baseline_rule=rule,
        )
    )
    assert baseline.start.isoformat() == expected_start
    assert baseline.end.isoformat() == expected_end
    assert current.start.isoformat() == start
    assert bool(warnings) == clamped


@pytest.mark.parametrize("groups", [499, 500, 501])
def test_primary_group_selection_counts_complete_population(tmp_path, groups):
    import csv
    from itertools import islice, product
    from string import ascii_uppercase

    from tests.integration.test_exploration_browsing import copy_flights

    source = copy_flights(tmp_path, groups)
    path = source / "nyc_flights_fixed.csv"
    rows = read_rows(path)
    codes = ["".join(item) for item in islice(product(ascii_uppercase, repeat=3), groups)]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(row | {"dest": code} for row, code in zip(rows, codes, strict=True))
    with DuckDBExecutor(str(source)) as executor:
        result = evidence(
            generate(
                executor,
                family="grouped_summary",
                grouping=["destination"],
                measure_ids=["flight_count"],
            )
        )
        ranking = evidence(
            generate(
                executor,
                family="ranking",
                grouping=["destination"],
                measure_ids=["flight_count"],
                bound=1,
            )
        )
    assert result.selection.available == groups
    assert result.selection.selected == min(groups, 500)
    assert result.selection.omitted == max(0, groups - 500)
    assert [group.identity[0].code for group in result.values] == codes[:500]
    assert ranking.missingness["top_equal_value_groups"] == groups
    assert ranking.missingness["selected_top_equal_value_groups"] == 1
    assert ranking.missingness["omitted_top_equal_value_groups"] == groups - 1
    assert ranking.selection.cutoff_tie


def test_requested_top_501_is_rejected_before_execution():
    from pydantic import ValidationError

    from airport_analytics.models import SectionProposal
    from tests.unit.test_exploration_contracts import proposed_section

    with pytest.raises(ValidationError):
        SectionProposal.model_validate(
            proposed_section(family="ranking", grouping=["destination"], bound=501)
        )


@pytest.mark.parametrize("baseline", [-5, 0, "NA"])
def test_period_change_negative_zero_and_unknown_baseline_are_distinct(tmp_path, baseline):
    import csv

    from tests.integration.test_exploration_browsing import copy_flights

    source = copy_flights(tmp_path, 2)
    path = source / "nyc_flights_fixed.csv"
    rows = read_rows(path)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(
            row | {"day": index + 1, "dep_delay": baseline if index == 0 else 10}
            for index, row in enumerate(rows)
        )
    with DuckDBExecutor(str(source)) as executor:
        result = evidence(
            generate(
                executor,
                family="period_change",
                operation_id="period_change",
                measure_ids=["mean_departure_delay"],
                comparison={
                    "baseline": {"start": "2013-01-01", "end": "2013-01-01"},
                    "comparison": {"start": "2013-01-02", "end": "2013-01-02"},
                },
            )
        )
    if baseline == -5:
        assert result.absolute_change.value == 15
        assert result.relative_change.value == -300
        assert any("Negative baseline" in warning for warning in result.warnings)
    else:
        assert result.relative_change.value is None
        assert result.absolute_change.value == (10 if baseline == 0 else None)


@pytest.mark.parametrize("size", [5000, 5001])
def test_pair_threshold_uses_complete_population_not_sample(tmp_path, size):
    import csv
    import io
    import json
    import zipfile

    from airport_analytics.reports.export import export_report_bundle, export_report_csv
    from tests.integration.test_exploration_browsing import copy_flights

    source = copy_flights(tmp_path, size)
    path = source / "nyc_flights_fixed.csv"
    source_rows = read_rows(path)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(source_rows[0]))
        writer.writeheader()
        writer.writerows(
            row | {"dep_delay": str(index % 37), "distance": str(index % 301 + 1)}
            for index, row in enumerate(source_rows)
        )
    with DuckDBExecutor(str(source)) as executor:
        outcome = generate(
            executor,
            family="numeric_relationship",
            operation_id="flight_relationship",
            measure_ids=["distance", "departure_delay"],
            pairing={"x": "distance", "y": "departure_delay"},
        )
        result = evidence(outcome)
    rows = read_rows(source / "nyc_flights_fixed.csv")
    count = sum(row["distance"] != "NA" and row["dep_delay"] != "NA" for row in rows)
    assert result.pairing.pair_count == count
    if count <= 5000:
        assert len(result.pairing.pairs) == count
    else:
        assert sum(cell.count for cell in result.pairing.density.cells) == count
    exported = list(
        csv.DictReader(io.StringIO(export_report_csv(outcome.report).decode("utf-8-sig")))
    )
    assert int(exported[0]["_meta_total_count"]) == len(exported)
    assert json.loads(exported[0]["_meta_pair_population"])["pair_count"] == count
    with zipfile.ZipFile(
        io.BytesIO(
            export_report_bundle(
                outcome.report,
                analyst_id="owner",
                session_id="session",
            )
        )
    ) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["sections"][0]["total_rows"] == len(exported)
        assert manifest["sections"][0]["exported_rows"] == len(exported)
    if count <= 5000:
        assert len(exported) == count
    else:
        assert len(exported) <= 400
        assert sum(int(row["count"]) for row in exported) == count


@pytest.mark.parametrize("bin_count", [99, 100, 101])
def test_distribution_bin_ceiling_requires_explicit_coarsening(tmp_path, bin_count):
    import csv

    from airport_analytics.errors import InvalidPlanError
    from tests.integration.test_exploration_browsing import copy_flights

    source = copy_flights(tmp_path, 2)
    path = source / "nyc_flights_fixed.csv"
    source_rows = read_rows(path)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(source_rows[0]))
        writer.writeheader()
        writer.writerows(
            row | {"dep_delay": str(index * 15 * (bin_count - 1))}
            for index, row in enumerate(source_rows)
        )
    with DuckDBExecutor(str(source)) as executor:
        if bin_count > 100:
            with pytest.raises(InvalidPlanError, match="accept a bin width"):
                generate(
                    executor,
                    family="distribution",
                    operation_id="distribution",
                    measure_ids=["departure_delay"],
                )
        else:
            result = evidence(
                generate(
                    executor,
                    family="distribution",
                    operation_id="distribution",
                    measure_ids=["departure_delay"],
                )
            )
            assert len(result.bins) == bin_count
            assert sum(item.count for item in result.bins) == 2


def test_large_distribution_range_proposes_without_linear_integer_scan(monkeypatch):
    from types import SimpleNamespace

    from airport_analytics.analytics import multi_stage
    from airport_analytics.errors import BinWidthRequiredError

    executor = SimpleNamespace(
        _run_compiled_query=lambda query: [
            {
                "known": 2,
                "missing": 0,
                "minimum": 0.0,
                "maximum": 1e12,
            }
        ]
    )
    interpretation = SimpleNamespace(
        measure_ids=["departure_delay"],
        filters=[],
        date_scope=None,
        binning=None,
    )
    floor = multi_stage.math.floor
    calls = []

    def bounded_floor(value):
        calls.append(value)
        assert len(calls) <= 10, "Coarsening scanned from one instead of the necessary range bound."
        return floor(value)

    monkeypatch.setattr(multi_stage.math, "floor", bounded_floor)
    with pytest.raises(BinWidthRequiredError) as error:
        multi_stage.distribution_constraints(executor, interpretation, timed_out=lambda: False)
    assert error.value.suggested_width == 15 * 666666667


@pytest.mark.parametrize(
    "minimum,maximum",
    [
        (-20000, -10000),
        (-10000, 10000),
        (10000, 20000),
        (650000, 800000),
    ],
)
def test_distribution_proposal_is_the_smallest_anchored_integer_multiple(minimum, maximum):
    import math
    from types import SimpleNamespace

    from airport_analytics.analytics.multi_stage import distribution_constraints
    from airport_analytics.errors import BinWidthRequiredError

    executor = SimpleNamespace(
        _run_compiled_query=lambda query: [
            {
                "known": 2,
                "missing": 0,
                "minimum": minimum,
                "maximum": maximum,
            }
        ]
    )
    interpretation = SimpleNamespace(
        measure_ids=["departure_delay"],
        filters=[],
        date_scope=None,
        binning=None,
    )
    expected = next(
        15 * multiple
        for multiple in range(1, 1000)
        if math.floor(
            (maximum - math.floor(minimum / (15 * multiple)) * (15 * multiple)) / (15 * multiple)
        )
        + 1
        <= 100
    )
    with pytest.raises(BinWidthRequiredError) as error:
        distribution_constraints(executor, interpretation, timed_out=lambda: False)
    assert error.value.suggested_width == expected


@pytest.mark.parametrize(
    "minimum,maximum,width,cancelled,error_name",
    [
        (0, 15000, 15, True, "QueryTimeoutError"),
        (0, 1e308, 15, False, "InvalidPlanError"),
        (-1e308, 1e308, 1e308, False, "InvalidPlanError"),
        (1e308, 1.7e308, 1e308, False, "InvalidPlanError"),
    ],
)
def test_distribution_timeout_and_unrepresentable_edges_fail_explicitly(
    minimum,
    maximum,
    width,
    cancelled,
    error_name,
):
    from types import SimpleNamespace

    from airport_analytics import errors
    from airport_analytics.analytics.multi_stage import distribution_constraints

    executor = SimpleNamespace(
        _run_compiled_query=lambda query: [
            {
                "known": 2,
                "missing": 0,
                "minimum": minimum,
                "maximum": maximum,
            }
        ]
    )
    interpretation = SimpleNamespace(
        measure_ids=["departure_delay"],
        filters=[],
        date_scope=None,
        binning=SimpleNamespace(width=width, accepted=True),
    )
    with pytest.raises(getattr(errors, error_name)):
        distribution_constraints(executor, interpretation, timed_out=lambda: cancelled)
