import csv
import io
import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from pypdf import PdfReader

import airport_analytics.reports.export as report_exports
from airport_analytics.auth import AnalystIdentity
from airport_analytics.errors import AuthorizationError, IncompleteReportError
from airport_analytics.history.repository import ReportRepository
from airport_analytics.models import CompositeReportV2, SectionPresentationPreference
from airport_analytics.reports.charts import build_chart
from airport_analytics.reports.export import export_report_csv, export_report_pdf
from airport_analytics.reports.visual_evidence import (
    prepare_visual_evidence,
    resolve_presentation,
)
from airport_analytics.storage import Storage
from tests.unit.test_exploration_results import scalar_report_payload


def _relationship_report() -> CompositeReportV2:
    payload = deepcopy(scalar_report_payload())
    section = payload["sections"][0]
    definition = {
        "unit": "paired_units",
        "numerator": "paired observations",
        "denominator": None,
        "weighting": "source_record",
        "additivity": "non_additive",
        "match_rules": [],
        "exclusions": [],
    }
    section["interpretation"].update(
        {
            "family": "numeric_relationship",
            "operation_id": "flight_relationship",
            "measure_ids": ["distance", "departure_delay"],
            "grain": "flight_pair",
            "definition": definition,
            "pairing": {"x": "distance", "y": "departure_delay"},
        }
    )
    result = section["outcome"]["result"]
    result.pop("value")
    result.update(
        {
            "kind": "relationship",
            "grain": "flight_pair",
            "definition": definition,
            "fields": [
                {
                    "field_id": "distance",
                    "label": "Distance",
                    "role": "numeric",
                    "unit": "miles",
                    "unit_provenance": "catalog",
                },
                {
                    "field_id": "departure_delay",
                    "label": "Departure delay",
                    "role": "numeric",
                    "unit": "minutes",
                    "unit_provenance": "catalog",
                },
            ],
            "missingness": {"filtered_flights": 4},
            "pairing": {
                "x_field": "distance",
                "y_field": "departure_delay",
                "x_unit": "miles",
                "y_unit": "minutes",
                "pair_count": 2,
                "scoped_count": 4,
                "x_missing_only": 1,
                "y_missing_only": 0,
                "both_missing": 1,
                "pairs": [
                    {"source_id": "=SUM(1,2)", "x": 0.0, "y": 0.0},
                    {
                        "source_id": "flight-002",
                        "x": 1.23456789012345,
                        "y": 9.87654321098765,
                    },
                ],
                "density": None,
                "x_extent": [0.0, 1.23456789012345],
                "y_extent": [0.0, 9.87654321098765],
            },
        }
    )
    return CompositeReportV2.model_validate(payload)


def _incomplete_report(*, acknowledged: bool) -> CompositeReportV2:
    payload = scalar_report_payload()
    failed = deepcopy(payload["sections"][0])
    failed.update(section_id="failed", position=2, label="Failed analysis")
    failed["interpretation"]["section_id"] = "failed"
    failed["outcome"] = {
        "status": "failed",
        "failure": {
            "category": "execution_failed",
            "code": "timeout",
            "message": "Synthetic timeout.",
        },
    }
    payload["sections"].append(failed)
    payload["completeness"] = "incomplete"
    if acknowledged:
        payload["incomplete_acknowledgement"] = {
            "analyst_id": payload["analyst_id"],
            "session_id": payload["session_id"],
            "report_id": payload["report_id"],
            "revision": payload["revision"],
            "failed_section_ids": ["failed"],
            "acknowledged_at": datetime.now(UTC).isoformat(),
        }
    return CompositeReportV2.model_validate(payload)


def _period_report_with_missing_baseline() -> CompositeReportV2:
    payload = deepcopy(scalar_report_payload())
    section = payload["sections"][0]
    baseline = {"start": "2013-01-01", "end": "2013-01-01"}
    comparison = {"start": "2013-01-02", "end": "2013-01-02"}
    section["interpretation"].update(
        {
            "family": "period_change",
            "operation_id": "period_change",
            "comparison": {"baseline": baseline, "comparison": comparison},
        }
    )
    result = section["outcome"]["result"]
    result.pop("value")
    result.update(
        {
            "kind": "period_change",
            "baseline": {
                "period": baseline,
                "value": {"value": None, "absence": "no_known_values"},
                "observation_count": 0,
                "day_exposure": 1,
            },
            "comparison": {
                "period": comparison,
                "value": {"value": 0, "absence": None},
                "observation_count": 0,
                "day_exposure": 1,
            },
            "absolute_change": {"value": None, "absence": "no_known_values"},
            "relative_change": {"value": None, "absence": "no_known_values"},
            "warnings": [],
        }
    )
    return CompositeReportV2.model_validate(payload)


def _csv_rows(content: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))


def test_export_defaults_chart_and_analytical_csv_preserve_bound_pair_evidence(tmp_path):
    report = _relationship_report()
    owner = AnalystIdentity("owner", "local", "owner")
    other = AnalystIdentity("other", "local", "other")
    repository = ReportRepository(Storage(tmp_path / "reports.sqlite"))
    repository.save_report(report, owner)

    saved = repository.get_report(owner, report.report_id)
    evidence = prepare_visual_evidence(saved, "section")
    chart_resolution = resolve_presentation(evidence)
    chart = build_chart(chart_resolution)
    analytical_csv = export_report_csv(saved)
    rows = _csv_rows(analytical_csv)

    assert chart is not None
    assert chart["data"]["values"] == [
        pair.model_dump() for pair in saved.sections[0].outcome.result.pairing.pairs
    ]
    assert chart["usermeta"]["evidence_fingerprint"] == evidence.evidence_fingerprint
    assert len(rows) == 2
    assert [row["source_id"] for row in rows] == ["'=SUM(1,2)", "flight-002"]
    assert [row["distance"] for row in rows] == ["0.0", "1.23456789012345"]
    assert [row["departure_delay"] for row in rows] == ["0.0", "9.87654321098765"]
    assert all(json.loads(row["_meta_null_fields"]) == [] for row in rows)
    population = json.loads(rows[0]["_meta_pair_population"])
    assert population["pair_count"] == 2
    assert population["scoped_count"] == 4
    assert population["x_missing_only"] == 1
    assert population["both_missing"] == 1
    assert rows[0]["_meta_report_id"] == evidence.report_id
    assert rows[0]["_meta_section_id"] == evidence.section_id
    assert rows[0]["_meta_revision"] == str(evidence.analytical_revision)
    assert rows[0]["_meta_snapshot_id"] == evidence.snapshot_id

    table_resolution = resolve_presentation(
        evidence,
        SectionPresentationPreference(chart_family="table"),
    )
    assert table_resolution.state == "table_selected"
    assert table_resolution.evidence.evidence_fingerprint == evidence.evidence_fingerprint
    assert build_chart(table_resolution) is None
    assert export_report_csv(saved) == analytical_csv
    with pytest.raises(AuthorizationError):
        repository.get_report(other, report.report_id)


def test_export_defaults_csv_distinguishes_null_from_zero():
    rows = _csv_rows(export_report_csv(_period_report_with_missing_baseline()))
    rows_by_component = {row["component"]: row for row in rows}
    baseline = rows_by_component["baseline"]
    comparison = rows_by_component["comparison"]

    assert baseline["component"] == "baseline"
    assert baseline["value"] == ""
    assert json.loads(baseline["_meta_null_fields"]) == ["value"]
    assert comparison["component"] == "comparison"
    assert comparison["value"] == "0"
    assert json.loads(comparison["_meta_null_fields"]) == ["unavailable_reason"]


def test_export_defaults_chart_csv_is_distinct_and_bound_to_applied_resolution():
    report = _relationship_report()
    evidence = prepare_visual_evidence(report, "section")
    resolution = resolve_presentation(evidence)
    exporter = getattr(report_exports, "export_chart_evidence_csv", None)

    assert callable(exporter), "A distinct chart-evidence CSV exporter is required."
    chart_rows = _csv_rows(exporter(report, resolution))
    analytical_rows = _csv_rows(export_report_csv(report))

    assert chart_rows != analytical_rows
    assert len(chart_rows) == len(resolution.evidence.payload.to_dict()["pairing"]["pairs"])
    assert {evidence.evidence_fingerprint} <= {
        value for row in chart_rows for value in row.values()
    }
    assert any(
        report.report_id == value for key, value in chart_rows[0].items() if "report" in key.lower()
    )
    assert any(
        str(report.preference_version) == value
        for key, value in chart_rows[0].items()
        if "preference" in key.lower()
    )
    assert any(
        evidence.selection_rule_version == value
        for key, value in chart_rows[0].items()
        if "rule" in key.lower()
    )
    assert [row["distance"] for row in chart_rows] == ["0.0", "1.23456789012345"]
    assert [row["departure_delay"] for row in chart_rows] == ["0.0", "9.87654321098765"]
    assert chart_rows[0]["source_id"] == "'=SUM(1,2)"


def test_export_defaults_unacknowledged_composite_never_returns_pdf_bytes():
    report = _incomplete_report(acknowledged=False)

    with pytest.raises(IncompleteReportError):
        export_report_pdf(report)


def test_export_defaults_acknowledged_composite_pdf_contains_every_section():
    report = _incomplete_report(acknowledged=True)

    content = export_report_pdf(report)
    assert content.startswith(b"%PDF-")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
    assert "Count flights" in text
    assert "Failed analysis" in text
    assert "Synthetic timeout." in text


def test_export_defaults_renderer_failure_never_returns_partial_pdf(monkeypatch):
    report = _relationship_report()

    def fail_build(*args, **kwargs):
        raise RuntimeError("synthetic renderer failure")

    monkeypatch.setattr(report_exports, "render_tagged_pdf", fail_build)
    with pytest.raises(RuntimeError, match="synthetic renderer failure"):
        export_report_pdf(report)
