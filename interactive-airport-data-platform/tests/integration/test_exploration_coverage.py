import json
from datetime import date

import pytest

from airport_analytics.data.coverage import CoverageDeclaration, calendar_eligibility, load_coverage


def test_calendar_intersects_origins_and_excludes_unknown_dates():
    a, b, c = (date(2013, 1, day) for day in [1, 2, 3])
    declaration = CoverageDeclaration({"JFK": frozenset([a, b]), "EWR": frozenset([b, c])})
    result = calendar_eligibility(
        declaration, ["JFK", "EWR"], a, c, {a, c}, "verified_calendar_days"
    )
    assert result["dates"] == [b]
    assert result["unknown_days"] == 2
    observed = calendar_eligibility(
        declaration, ["JFK", "EWR"], a, c, {a, c}, "observed_operating_days"
    )
    assert observed["dates"] == [a, c]


def test_malformed_missing_declaration_is_visible_unknown(tmp_path):
    path = tmp_path / "coverage.json"
    assert load_coverage(path, "a" * 64, {"JFK"}).warning
    path.write_text("{}", encoding="utf-8")
    assert load_coverage(path, "a" * 64, {"JFK"}).days == {}


@pytest.mark.parametrize(
    "fault",
    [
        "snapshot",
        "overlap",
        "unknown_origin",
        "outside_gap",
        "evidence_hash",
        "failed_check",
        "missing_reviewer",
    ],
)
def test_invalid_or_conflicting_declarations_never_claim_verified_dates(tmp_path, fault):
    from airport_analytics.analytics.execution import DuckDBExecutor
    from tests.integration.test_exploration_daily_metrics import verified_coverage
    from tests.integration.test_exploration_summaries import FIXTURES

    with DuckDBExecutor(str(FIXTURES)) as executor:
        path = verified_coverage(tmp_path, executor)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if fault == "snapshot":
            payload["snapshot_id"] = "0" * 64
        elif fault == "overlap":
            payload["origins"][0]["covered_intervals"].append(
                {"start": "2013-01-05", "end": "2013-01-08"},
            )
        elif fault == "unknown_origin":
            payload["origins"][0]["code"] = "ZZZ"
        elif fault == "outside_gap":
            payload["origins"][0]["gaps"] = [
                {
                    "start": "2013-01-08",
                    "end": "2013-01-09",
                }
            ]
        elif fault == "evidence_hash":
            payload["documentation"][0]["sha256"] = "0" * 64
        elif fault == "failed_check":
            payload["validation"]["checks"][0]["passed"] = False
        else:
            payload["validation"]["reviewed_by"] = ""
        path.write_text(json.dumps(payload), encoding="utf-8")
        result = load_coverage(path, executor.manifest.snapshot_id, {"JFK", "LGA"})
    assert result.warning
    assert result.days == {}


def test_gaps_exclude_only_declared_origin_and_linked_evidence_mutation_invalidates(tmp_path):
    from airport_analytics.analytics.execution import DuckDBExecutor
    from airport_analytics.errors import DatasetUnavailableError
    from tests.integration.test_exploration_daily_metrics import verified_coverage
    from tests.integration.test_exploration_summaries import FIXTURES

    with DuckDBExecutor(str(FIXTURES)) as initial:
        path = verified_coverage(tmp_path, initial)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["origins"][0]["gaps"] = [
        {
            "start": "2013-01-03",
            "end": "2013-01-03",
        }
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with DuckDBExecutor(str(FIXTURES), coverage_path=path) as executor:
        assert len(executor.coverage.days["JFK"]) == 6
        assert len(executor.coverage.days["LGA"]) == 7
        assert date(2013, 1, 3) not in executor.coverage.days["JFK"]
        (tmp_path / "synthetic-provenance.txt").write_text("Changed evidence", encoding="utf-8")
        with pytest.raises(DatasetUnavailableError):
            executor.require_current_binding(
                executor.manifest.snapshot_id, executor.context.context_id
            )
