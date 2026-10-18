import pytest

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.models import DailyMeanResult
from tests.integration.test_exploration_summaries import FIXTURES, evidence, generate


def verified_coverage(tmp_path, executor):
    import hashlib
    import json

    document = tmp_path / "synthetic-provenance.txt"
    document.write_text(
        "Synthetic fixture completeness: declared origins Jan 1-7 2013.", encoding="utf-8"
    )
    declaration = {
        "schema_version": 1,
        "declaration_id": "synthetic-only",
        "declaration_version": 1,
        "snapshot_id": executor.manifest.snapshot_id,
        "declared_at": "2026-10-17T00:00:00Z",
        "declared_by": "synthetic-fixture-author",
        "calendar_basis": "recorded_departure_date",
        "origins": [
            {
                "code": code,
                "covered_intervals": [{"start": "2013-01-01", "end": "2013-01-07"}],
                "gaps": [],
            }
            for code in sorted(executor.entity_directory().observed["origin"])
        ],
        "documentation": [
            {
                "reference": document.name,
                "sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
                "supports": "Synthetic known-empty fixture days, not production completeness.",
            }
        ],
        "validation": {
            "validator_version": "synthetic-1",
            "validated_at": "2026-10-17T00:00:00Z",
            "reviewed_by": "synthetic-fixture-reviewer",
            "checks": [
                {
                    "check_id": "fixture-enumeration",
                    "passed": True,
                    "evidence_reference": document.name,
                }
            ],
        },
    }
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(declaration), encoding="utf-8")
    return path


def test_daily_destination_mean_without_coverage_is_unavailable_not_observed_zero():
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = evidence(
            generate(
                executor,
                operation_id="daily_distinct_mean",
                measure_ids=["distinct_destination_count"],
            )
        )
    assert isinstance(result, DailyMeanResult)
    assert result.scope.denominator_basis == "verified_calendar_days"
    assert result.values[0].value.value is None
    assert result.values[0].eligible_days == 0
    assert result.values[0].value.absence == "no_verified_days"


@pytest.mark.parametrize("grouping", [[], ["weekday"]])
def test_explicit_observed_day_proposal_reaches_daily_mean_without_calendar_coverage(grouping):
    from collections import defaultdict
    from datetime import date

    from airport_analytics.analytics.plan_schema import validate_intent_proposal
    from tests.exploration_oracles import read_rows
    from tests.integration.test_exploration_summaries import SummaryClient

    client = SummaryClient(
        family="grouped_summary" if grouping else "overall_summary",
        operation_id="daily_distinct_mean",
        measure_ids=["distinct_destination_count"],
        grouping=grouping,
        denominator_basis="observed_operating_days",
        rounding={"places": 0, "mode": "half_up"},
    )
    validate_intent_proposal(client.proposal.model_dump(mode="json"))
    daily = defaultdict(set)
    for row in read_rows(FIXTURES / "nyc_flights_fixed.csv"):
        day = date(int(row["year"]), int(row["month"]), int(row["day"]))
        daily[day].add(row["dest"])
    with DuckDBExecutor(str(FIXTURES)) as executor:
        from airport_analytics.reports.generation import ExplorationReportGenerator

        outcome = ExplorationReportGenerator(client, executor).generate(
            "Average daily destinations over observed operating days only",
            analyst_id="owner",
            session_id="session",
            session_state={},
        )
    result = evidence(outcome)
    interpretation = outcome.report.sections[0].interpretation
    assert interpretation.denominator_basis == "observed_operating_days"
    assert interpretation.field_provenance["denominator_basis"].source == "explicit"
    assert interpretation.display_rounding.places == 0
    for row in result.values:
        eligible = [
            values
            for day, values in daily.items()
            if not grouping or day.isoweekday() == int(row.identity[0].code)
        ]
        assert row.eligible_days == len(eligible)
        if eligible:
            assert row.value.value == pytest.approx(sum(map(len, eligible)) / len(eligible))
        else:
            assert row.value.value is None
            assert row.value.absence is not None
    assert result.scope.coverage_status == "unknown"


def test_verified_daily_mean_includes_known_zero_days_and_weekday_denominators(tmp_path):
    from airport_analytics.data.coverage import load_coverage
    from airport_analytics.models import IntentProposalV2
    from airport_analytics.reports.generation import ExplorationReportGenerator
    from tests.exploration_oracles import read_rows
    from tests.integration.test_exploration_summaries import SummaryClient

    rows = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    with DuckDBExecutor(str(FIXTURES)) as executor:
        path = verified_coverage(tmp_path, executor)
        executor.coverage = load_coverage(
            path, executor.manifest.snapshot_id, {"JFK", "EWR", "LGA"}
        )
        executor._coverage_path = path
        executor.context = executor._loader.semantic_context(
            executor.manifest,
            coverage_path=path,
        )
        assert executor.coverage.warning is None
        client = SummaryClient(
            operation_id="daily_distinct_mean",
            measure_ids=["distinct_destination_count"],
        )
        payload = client.proposal.model_dump()
        payload["shared_scope"]["dates"] = {"start": "2013-01-01", "end": "2013-01-07"}
        client.proposal = IntentProposalV2.model_validate(payload)
        result = evidence(
            ExplorationReportGenerator(client, executor).generate(
                "Daily distinct destinations",
                analyst_id="owner",
                session_id="session",
                session_state={},
            )
        )
    expected = sum(
        len({row["dest"] for row in rows if row["month"] == "1" and row["day"] == str(day)})
        for day in range(1, 8)
    )
    assert result.values[0].eligible_days == 7
    assert result.values[0].numerator == expected
    assert result.values[0].value.value == expected / 7
    assert result.scope.verified_days == 7
    assert len(result.daily_support) == 7
    assert any(row["contribution"] == 0 for row in result.daily_support)


def test_explicit_origin_and_verified_no_flight_date_remain_known_zero(tmp_path):
    from airport_analytics.models import IntentProposalV2
    from airport_analytics.reports.generation import ExplorationReportGenerator
    from tests.integration.test_exploration_summaries import SummaryClient

    with DuckDBExecutor(str(FIXTURES)) as initial:
        path = verified_coverage(tmp_path, initial)
    with DuckDBExecutor(str(FIXTURES), coverage_path=path) as executor:
        client = SummaryClient(
            operation_id="daily_distinct_mean", measure_ids=["distinct_destination_count"]
        )
        payload = client.proposal.model_dump()
        payload["shared_scope"] = {
            "edits": [
                {"field_id": "origin", "action": "replace", "operator": "eq", "value": "LGA"}
            ],
            "dates": {"start": "2013-01-03", "end": "2013-01-03"},
        }
        client.proposal = IntentProposalV2.model_validate(payload)
        result = evidence(
            ExplorationReportGenerator(client, executor).generate(
                "Daily destinations from LGA on January 3",
                analyst_id="owner",
                session_id="session",
                session_state={},
            )
        )
    assert result.scope.origins == ["LGA"]
    assert result.values[0].eligible_days == 1
    assert result.values[0].numerator == 0
    assert result.values[0].value.value == 0


@pytest.mark.parametrize("days,places,expected", [(2, 0, "3"), (4, 1, "1.3")])
def test_daily_rounding_uses_exact_count_ratio_and_decimal_half_up(
    tmp_path, days, places, expected
):
    import csv

    from airport_analytics.models import IntentProposalV2
    from airport_analytics.reports.generation import ExplorationReportGenerator
    from airport_analytics.reports.rendering import summary_result_table
    from tests.exploration_oracles import read_rows
    from tests.integration.test_exploration_browsing import copy_flights
    from tests.integration.test_exploration_summaries import SummaryClient

    source = copy_flights(tmp_path, 5)
    path = source / "nyc_flights_fixed.csv"
    rows = read_rows(path)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(
            row
            | {
                "year": 2013,
                "month": 1,
                "day": 1 if index < 3 else 2,
                "dest": ["AAA", "BBB", "CCC", "AAA", "BBB"][index],
            }
            for index, row in enumerate(rows)
        )
    with DuckDBExecutor(str(source)) as initial:
        coverage_path = verified_coverage(tmp_path, initial)
    with DuckDBExecutor(str(source), coverage_path=coverage_path) as executor:
        client = SummaryClient(
            operation_id="daily_distinct_mean",
            measure_ids=["distinct_destination_count"],
            rounding={"places": places, "mode": "half_up"},
        )
        payload = client.proposal.model_dump()
        payload["shared_scope"]["dates"] = {"start": "2013-01-01", "end": f"2013-01-0{days}"}
        client.proposal = IntentProposalV2.model_validate(payload)
        result = evidence(
            ExplorationReportGenerator(client, executor).generate(
                "Rounded daily destinations",
                analyst_id="owner",
                session_id="session",
                session_state={},
            )
        )
    assert result.values[0].numerator == 5
    assert result.values[0].eligible_days == days
    assert summary_result_table(result)[1][0]["rounded_display"] == expected


def test_weekday_means_have_independent_calendar_denominators_and_known_zero_days(tmp_path):
    from datetime import date

    from airport_analytics.models import IntentProposalV2
    from airport_analytics.reports.generation import ExplorationReportGenerator
    from tests.exploration_oracles import read_rows
    from tests.integration.test_exploration_summaries import SummaryClient

    with DuckDBExecutor(str(FIXTURES)) as initial:
        path = verified_coverage(tmp_path, initial)
    with DuckDBExecutor(str(FIXTURES), coverage_path=path) as executor:
        client = SummaryClient(
            family="grouped_summary",
            operation_id="daily_distinct_mean",
            measure_ids=["distinct_destination_count"],
            grouping=["weekday"],
        )
        payload = client.proposal.model_dump()
        payload["shared_scope"]["dates"] = {"start": "2013-01-01", "end": "2013-01-07"}
        client.proposal = IntentProposalV2.model_validate(payload)
        result = evidence(
            ExplorationReportGenerator(client, executor).generate(
                "Average destinations by weekday",
                analyst_id="owner",
                session_id="session",
                session_state={},
            )
        )
    source = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    for group in result.values:
        weekday = int(group.identity[0].code)
        expected = sum(
            len({row["dest"] for row in source if int(row["day"]) == day})
            for day in range(1, 8)
            if date(2013, 1, day).isoweekday() == weekday
        )
        assert group.eligible_days == 1
        assert group.numerator == expected
        assert group.value.value == expected
    assert [group.identity[0].label for group in result.values] == [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]


@pytest.mark.parametrize("grouping", [["carrier"], ["origin", "carrier"]])
def test_observed_capacity_uses_common_dates_and_one_pooled_support_bound(tmp_path, grouping):
    import csv
    from datetime import date, timedelta

    from airport_analytics.models import FieldProvenance, RequestDraft
    from airport_analytics.reports.generation import ExplorationReportGenerator
    from tests.exploration_oracles import read_rows
    from tests.integration.test_exploration_browsing import copy_flights
    from tests.integration.test_exploration_summaries import SummaryClient

    source = copy_flights(tmp_path, 600)
    path = source / "nyc_flights_fixed.csv"
    rows = read_rows(path)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        for index, row in enumerate(rows):
            day = date(2012, 1, 1) + timedelta(days=index)
            writer.writerow(row | {"year": day.year, "month": day.month, "day": day.day})
    with DuckDBExecutor(str(source)) as executor:
        generator = ExplorationReportGenerator(
            SummaryClient(
                family="ranking",
                operation_id="daily_capacity_mean",
                measure_ids=["known_reference_seats"],
                grouping=grouping,
            ),
            executor,
        )
        initial = generator.generate(
            "Rank daily recorded seat capacity",
            analyst_id="owner",
            session_id="session",
            session_state={},
        )
        interpreted = initial.interpretations[0]
        revised = type(interpreted).model_validate(
            interpreted.model_dump()
            | {
                "revision": 2,
                "denominator_basis": "observed_operating_days",
                "field_provenance": interpreted.field_provenance
                | {
                    "denominator_basis": FieldProvenance(source="correction", revision=2),
                },
            }
        )
        result = evidence(
            generator.execute_interpretations(
                RequestDraft(
                    request_id=revised.request_id,
                    revision=2,
                    original_question="Rank daily recorded seat capacity",
                    session_binding="session",
                ),
                [revised],
                analyst_id="owner",
                session_id="session",
            )
        )
    origins = {row["origin"] for row in rows}
    days_by_origin = {origin: sum(row["origin"] == origin for row in rows) for origin in origins}
    expected_support = (
        1200
        if len(grouping) == 1
        else sum(
            days_by_origin[origin]
            * len({row["carrier"] for row in rows if row["origin"] == origin})
            for origin in origins
        )
    )
    assert {group.eligible_days for group in result.values} == (
        {600} if len(grouping) == 1 else set(days_by_origin.values())
    )
    assert len(result.daily_support) == 500
    assert result.missingness["available_daily_support"] == expected_support
    assert result.missingness["omitted_daily_support"] == expected_support - 500
    assert all(group.provisional for group in result.values)
    planes = {
        row["tailnum"]: int(row["seats"]) if row["seats"] not in {"NA", ""} else None
        for row in read_rows(source / "nyc_planes.csv")
    }
    flights = read_rows(source / "nyc_flights_fixed.csv")
    for group in result.values:
        identities = {item.field_id: item.code for item in group.identity}
        population = [
            row
            for row in flights
            if row["carrier"] == identities["carrier"]
            and ("origin" not in identities or row["origin"] == identities["origin"])
        ]
        known = [
            planes[row["tailnum"]] for row in population if planes.get(row["tailnum"]) is not None
        ]
        assert group.numerator == sum(known)
        denominator = days_by_origin[identities["origin"]] if "origin" in identities else 600
        assert group.value.value == sum(known) / denominator
        assert group.unknown_contribution_count == len(population) - len(known)
