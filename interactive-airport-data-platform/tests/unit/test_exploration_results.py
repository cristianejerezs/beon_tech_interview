from copy import deepcopy
from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from airport_analytics.models import (
    CompositeReportV2,
    DistributionResult,
    ExplorationResult,
    GroupedResult,
    NumericEvidence,
    PairEvidence,
    ScalarResult,
)


def scalar_report_payload():
    definition = {
        "unit": "flights",
        "numerator": "source records",
        "denominator": None,
        "weighting": "source_record",
        "additivity": "additive",
        "match_rules": [],
        "exclusions": [],
    }
    interpretation = {
        "request_id": "request",
        "revision": 1,
        "section_id": "section",
        "original_clause": "Count flights",
        "family": "overall_summary",
        "operation_id": "aggregate",
        "measure_ids": ["flight_count"],
        "population": "flights",
        "snapshot_id": "a" * 64,
        "context_id": "b" * 64,
        "definition": definition,
    }
    result = {
        "result_version": 2,
        "evidence_version": 2,
        "kind": "scalar",
        "report_id": "report",
        "section_id": "section",
        "snapshot_id": "a" * 64,
        "context_id": "b" * 64,
        "definition": definition,
        "grain": "scalar",
        "scope": {
            "filters": [],
            "requested_period": None,
            "observed_period": None,
            "origins": ["JFK"],
            "coverage_status": "unknown",
            "denominator_basis": "not_applicable",
            "requested_days": None,
            "verified_days": 0,
            "unknown_days": None,
            "observed_days": 1,
            "eligible_days": None,
        },
        "fields": [
            {
                "field_id": "flight_count",
                "label": "Flights",
                "role": "numeric",
                "unit": "flights",
                "unit_provenance": "catalog",
            }
        ],
        "order": [],
        "missingness": {"filtered_flights": 9},
        "selection": {"available": 1, "selected": 1, "omitted": 0, "cutoff_tie": False},
        "format": {"locale": "en", "computed_places": 2, "rounding": None},
        "limitations": ["Historical synthetic data."],
        "daily_support": [],
        "route_support": [],
        "value": {"value": 9, "absence": None},
    }
    return {
        "report_version": 2,
        "report_id": "report",
        "analyst_id": "owner",
        "session_id": "session",
        "question": "Count flights",
        "revision": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "snapshot_id": "a" * 64,
        "context_id": "b" * 64,
        "versions": {"catalog": "2.0"},
        "shared_scope": {},
        "removed_sections": [],
        "sections": [
            {
                "section_id": "section",
                "position": 1,
                "label": "Count flights",
                "interpretation": interpretation,
                "narrative": "9 flights",
                "outcome": {"status": "completed", "result": result},
            }
        ],
        "completeness": "complete",
        "parent_report_id": None,
        "incomplete_acknowledgement": None,
        "presentation_preferences": {},
        "preference_version": 1,
    }


def test_v2_report_round_trip_has_no_legacy_first_section_proxy():
    report = CompositeReportV2.model_validate(scalar_report_payload())
    assert CompositeReportV2.model_validate_json(report.model_dump_json()) == report
    assert not hasattr(report, "analysis_plan")
    assert not hasattr(report, "result_payload")
    assert report.sections[0].outcome.result.value.value == 9


@pytest.mark.parametrize(
    "changes",
    [
        {"value": None, "absence": None},
        {"value": 0, "absence": "no_known_values"},
        {"value": float("inf"), "absence": None},
        {"value": True, "absence": None},
        {"value": "9", "absence": None},
    ],
)
def test_numeric_evidence_preserves_absence_and_finite_types(changes):
    with pytest.raises(ValidationError):
        NumericEvidence.model_validate(changes)
    assert NumericEvidence(value=0, absence=None).value == 0
    assert NumericEvidence(value=None, absence="no_known_values").value is None


def test_evidence_identity_scope_and_pooled_support_bounds():
    original = scalar_report_payload()
    for key, value in [
        ("report_id", "different"),
        ("section_id", "different"),
        ("snapshot_id", "c" * 64),
        ("context_id", "c" * 64),
    ]:
        payload = deepcopy(original)
        payload["sections"][0]["outcome"]["result"][key] = value
        with pytest.raises(ValidationError):
            CompositeReportV2.model_validate(payload)
    result = original["sections"][0]["outcome"]["result"]
    ScalarResult.model_validate(result | {"daily_support": [{"day": "2013-01-01"}] * 500})
    for changes in [
        {"daily_support": [{"day": "2013-01-01"}] * 501},
        {"route_support": [{"destination": "BOS"}] * 501},
        {"selection": {"available": 2, "selected": 1, "omitted": 0, "cutoff_tie": False}},
        {"missingness": {"filtered_flights": -1}},
    ]:
        with pytest.raises(ValidationError):
            ScalarResult.model_validate(result | changes)


def test_pair_population_threshold_and_full_density_reconciliation():
    common = {
        "x_field": "distance",
        "y_field": "departure_delay",
        "x_unit": "miles",
        "y_unit": "minutes",
        "pair_count": 5000,
        "x_missing_only": 1,
        "y_missing_only": 2,
        "both_missing": 3,
        "scoped_count": 5006,
        "x_extent": [0, 0],
        "y_extent": [0, 0],
    }
    pair = {"source_id": "1", "x": 0, "y": 0}
    pairs = [{**pair, "source_id": str(index)} for index in range(5000)]
    assert (
        PairEvidence.model_validate(common | {"pairs": pairs, "density": None}).pair_count == 5000
    )
    with pytest.raises(ValidationError):
        PairEvidence.model_validate(common | {"pair_count": 5001, "pairs": pairs, "density": None})
    density = {"x_edges": [0, 1], "y_edges": [0, 1], "cells": [{"x": 0, "y": 0, "count": 5001}]}
    valid = common | {
        "pair_count": 5001,
        "scoped_count": 5007,
        "pairs": None,
        "density": density,
        "x_extent": [0, 1],
        "y_extent": [0, 1],
    }
    PairEvidence.model_validate(valid)
    for changes in [
        {"scoped_count": 9},
        {"density": density | {"x_edges": [0, 0]}},
        {"density": density | {"cells": [{"x": 0, "y": 0, "count": 5000}]}},
        {"density": density | {"x_edges": list(range(22))}},
    ]:
        with pytest.raises(ValidationError):
            PairEvidence.model_validate(valid | changes)


def test_all_failed_reports_are_not_successful_and_acknowledgement_is_exact():
    original = scalar_report_payload()
    failed = deepcopy(original["sections"][0])
    failed.update(section_id="failed", position=2, label="Failed section")
    failed["interpretation"]["section_id"] = "failed"
    failed["outcome"] = {
        "status": "failed",
        "failure": {"category": "execution_failed", "code": "timeout", "message": "Timed out."},
    }
    all_failed = deepcopy(original)
    failed_first = deepcopy(failed)
    failed_first["position"] = 1
    all_failed["sections"] = [failed_first]
    all_failed["completeness"] = "incomplete"
    with pytest.raises(ValidationError):
        CompositeReportV2.model_validate(all_failed)
    original["sections"].append(failed)
    original["completeness"] = "incomplete"
    report = CompositeReportV2.model_validate(original)
    with pytest.raises(ValueError, match="acknowledgement"):
        report.require_persistable()
    acknowledgement = {
        "analyst_id": "owner",
        "session_id": "session",
        "report_id": "report",
        "revision": 1,
        "failed_section_ids": ["failed"],
        "acknowledged_at": datetime.now(UTC).isoformat(),
    }
    original["incomplete_acknowledgement"] = acknowledgement
    CompositeReportV2.model_validate(original).require_persistable()
    for changes in [
        {"analyst_id": "other"},
        {"revision": 2},
        {"failed_section_ids": ["section"]},
        {"acknowledged_at": "2013-01-01T00:00:00"},
    ]:
        payload = deepcopy(original)
        payload["incomplete_acknowledgement"] = acknowledgement | changes
        with pytest.raises(ValidationError):
            CompositeReportV2.model_validate(payload)


def test_every_result_variant_is_closed_and_round_trips():
    common = scalar_report_payload()["sections"][0]["outcome"]["result"]
    common = {key: value for key, value in common.items() if key not in {"kind", "value"}}
    number = {"value": 9, "absence": None}
    group = {
        "identity": [{"field_id": "origin", "code": "JFK", "label": "JFK", "status": "known"}],
        "measures": {"flight_count": number},
        "sample_size": 9,
        "tied": False,
    }
    pair = {
        "x_field": "distance",
        "y_field": "departure_delay",
        "x_unit": "miles",
        "y_unit": "minutes",
        "pair_count": 1,
        "scoped_count": 1,
        "x_missing_only": 0,
        "y_missing_only": 0,
        "both_missing": 0,
        "pairs": [{"source_id": "one", "x": 1, "y": 0}],
        "density": None,
        "x_extent": [1, 1],
        "y_extent": [0, 0],
    }
    period = {
        "period": {"start": "2013-01-01", "end": "2013-01-01"},
        "value": number,
        "observation_count": 9,
        "day_exposure": 1,
    }
    variants = [
        {"kind": "scalar", "value": number},
        {"kind": "grouped", "values": [group]},
        {
            "kind": "listing",
            "population": "flights",
            "total_rows": 1,
            "rows": [{"flight_count": 9}],
            "identity_columns": ["flight_count"],
        },
        {
            "kind": "period_change",
            "baseline": period,
            "comparison": period,
            "absolute_change": {"value": 0, "absence": None},
            "relative_change": {"value": 0, "absence": None},
            "warnings": [],
        },
        {
            "kind": "distribution",
            "variable": "departure_delay",
            "width": 15.0,
            "bins": [{"lower": 0, "upper": 15, "count": 9, "upper_inclusive": True}],
            "known_count": 9,
            "missing_count": 0,
        },
        {"kind": "relationship", "pairing": pair},
        {
            "kind": "daily_mean",
            "values": [
                group
                | {
                    "value": number,
                    "numerator": 9,
                    "eligible_days": 1,
                    "known_contribution_count": 9,
                    "unknown_contribution_count": 0,
                    "complete_days": 1,
                    "incomplete_days": 0,
                    "provisional": False,
                }
            ],
        },
        {
            "kind": "weather_panel",
            "variables": [
                {
                    "variable": variable,
                    "origin": None,
                    "pairing": pair | {"x_field": variable, "x_unit": unit},
                    "coefficient": {"value": None, "absence": "insufficient_pairs"},
                }
                for variable, unit in [
                    ("temp", "F"),
                    ("wind_speed", "mph"),
                    ("precip", "inches"),
                    ("visib", "miles"),
                ]
            ],
            "precipitation_comparison": [group],
        },
    ]
    adapter = TypeAdapter(ExplorationResult)
    for variant in variants:
        result = adapter.validate_python(common | variant)
        assert adapter.validate_json(result.model_dump_json()) == result
        with pytest.raises(ValidationError):
            adapter.validate_python(common | variant | {"raw_provider_body": "not evidence"})


def test_group_bin_and_density_bounds_are_inclusive():
    common = scalar_report_payload()["sections"][0]["outcome"]["result"]
    common = {key: value for key, value in common.items() if key not in {"kind", "value"}}
    groups = [
        {
            "identity": [
                {"field_id": "origin", "code": str(i), "label": str(i), "status": "known"}
            ],
            "measures": {"flight_count": {"value": 1, "absence": None}},
            "sample_size": 1,
            "tied": True,
        }
        for i in range(500)
    ]
    grouped = common | {
        "kind": "grouped",
        "values": groups,
        "selection": {"available": 500, "selected": 500, "omitted": 0, "cutoff_tie": False},
    }
    GroupedResult.model_validate(grouped)
    with pytest.raises(ValidationError):
        GroupedResult.model_validate(grouped | {"values": groups + [groups[0]]})
    bins = [
        {"lower": i, "upper": i + 1, "count": 1, "upper_inclusive": i == 99} for i in range(100)
    ]
    distribution = common | {
        "kind": "distribution",
        "variable": "departure_delay",
        "width": 1.0,
        "bins": bins,
        "known_count": 100,
        "missing_count": 0,
    }
    DistributionResult.model_validate(distribution)
    with pytest.raises(ValidationError):
        DistributionResult.model_validate(distribution | {"bins": bins + [bins[-1]]})
    density = {
        "x_edges": list(range(21)),
        "y_edges": list(range(21)),
        "cells": [{"x": x, "y": y, "count": 13} for x in range(20) for y in range(20)],
    }
    pair = {
        "x_field": "distance",
        "y_field": "departure_delay",
        "x_unit": "miles",
        "y_unit": "minutes",
        "pair_count": 5200,
        "scoped_count": 5200,
        "x_missing_only": 0,
        "y_missing_only": 0,
        "both_missing": 0,
        "pairs": None,
        "density": density,
        "x_extent": [0, 20],
        "y_extent": [0, 20],
    }
    PairEvidence.model_validate(pair)
    with pytest.raises(ValidationError):
        PairEvidence.model_validate(
            pair
            | {
                "density": density | {"cells": density["cells"] + [density["cells"][0]]},
            }
        )
