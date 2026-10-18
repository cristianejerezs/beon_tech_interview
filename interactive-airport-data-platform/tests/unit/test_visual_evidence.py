import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from airport_analytics.errors import VisualEvidenceError
from airport_analytics.models import CompositeReportV2
from airport_analytics.reports.visual_evidence import (
    FrozenDocument,
    PresentationResolution,
    VisualCategory,
    VisualDimension,
    VisualSelection,
    canonical_identity,
    prepare_visual_evidence,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visual_reporting"


def report_payload():
    return json.loads((FIXTURES / "historical-v2.json").read_text(encoding="utf-8"))


def report():
    return CompositeReportV2.model_validate(report_payload())


def test_scalar_projection_preserves_values_definitions_unknown_coverage_and_provenance():
    source = report()
    visual = prepare_visual_evidence(source, "section")
    assert visual.shape == "scalar"
    assert visual.visual_evidence_version == 1
    assert visual.selection_rule_version == "003.1"
    assert visual.report_id == source.report_id
    assert visual.section_id == "section"
    assert visual.analytical_revision == 1
    assert visual.snapshot_id == source.snapshot_id
    assert visual.context_id == source.context_id
    assert visual.payload.to_dict()["value"] == {"value": 9, "absence": None}
    assert visual.definition.to_dict()["denominator"] is None
    assert visual.coverage.to_dict()["status"] == "unknown"
    assert visual.coverage.to_dict()["reason"]
    assert visual.selection.available_groups == 1


def test_projection_and_nested_snapshot_are_immutable_and_detached():
    source = report()
    visual = prepare_visual_evidence(source, "section")
    before = visual.payload.canonical_json
    source.sections[0].outcome.result.value.value = 999
    detached = visual.payload.to_dict()
    detached["value"]["value"] = 123
    assert visual.payload.canonical_json == before
    with pytest.raises(ValidationError):
        visual.shape = "category"
    with pytest.raises(ValidationError):
        visual.selection.shown_groups = 0


def test_fingerprint_ignores_narrative_preferences_and_creation_timestamp():
    source = report()
    before = prepare_visual_evidence(source, "section")
    source.question = "Different narrative framing"
    source.sections[0].narrative = "Different explanation"
    source.sections[0].label = "A different display label"
    source.preference_version = 9
    source.presentation_preferences = {"section": {"chart_family": "table"}}
    source.created_at = source.created_at.replace(year=2025)
    after = prepare_visual_evidence(source, "section")
    assert before.evidence_fingerprint == after.evidence_fingerprint
    assert len(before.evidence_fingerprint) == 64


def test_changed_analytical_evidence_changes_fingerprint():
    source = report()
    before = prepare_visual_evidence(source, "section")
    source.sections[0].outcome.result.value.value = 10
    after = prepare_visual_evidence(source, "section")
    assert before.evidence_fingerprint != after.evidence_fingerprint


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -float("inf"), "9"])
def test_mutated_invalid_numbers_are_rejected_without_coercion(value):
    source = report()
    source.sections[0].outcome.result.value.value = value
    with pytest.raises(VisualEvidenceError):
        prepare_visual_evidence(source, "section")


def test_exact_integer_above_javascript_safe_range_is_not_float_coerced():
    source = report()
    source.sections[0].outcome.result.value.value = 9007199254740993
    projected = prepare_visual_evidence(source, "section")
    assert projected.payload.to_dict()["value"]["value"] == 9007199254740993
    assert "9007199254740993" in projected.payload.canonical_json


def test_canonical_identity_preserves_reference_status_null_and_delimiters():
    triples = [
        ("origin", None, "missing"),
        ("origin", "Missing category", "known"),
        ("origin", "AAA", "known"),
        ("origin", "AAA", "unmatched_reference"),
        ("origin", 'AAA|known,"x"', "known"),
    ]
    tokens = [canonical_identity(*triple) for triple in triples]
    assert len(set(tokens)) == len(triples)
    assert [json.loads(token) for token in tokens] == [list(triple) for triple in triples]
    with pytest.raises(VisualEvidenceError):
        canonical_identity("origin", None, "known")


@pytest.mark.parametrize(
    "changes",
    [
        {"visual_evidence_version": 2},
        {"visual_evidence_version": True},
        {"selection_rule_version": "future"},
        {"shape": "guess_from_labels"},
        {"dimensions": (VisualDimension(field_id="origin", label="Origin", role="category"),) * 3},
    ],
)
def test_visual_contract_is_closed(changes):
    visual = prepare_visual_evidence(report(), "section")
    with pytest.raises(ValidationError):
        type(visual).model_validate(visual.model_dump() | changes)


@pytest.mark.parametrize("role", ["date", "guess", "numeric"])
def test_visual_dimensions_accept_only_declared_visual_roles(role):
    with pytest.raises(ValidationError):
        VisualDimension(field_id="origin", label="Origin", role=role)


def test_frozen_document_canonicalizes_key_order_and_rejects_nonfinite_values():
    assert FrozenDocument.from_dict({"b": 2, "a": 1}).canonical_json == '{"a":1,"b":2}'
    with pytest.raises(VisualEvidenceError):
        FrozenDocument.from_dict({"value": float("nan")})


def test_selection_counts_must_reconcile_and_unknown_total_stays_unknown():
    selection = VisualSelection(shown_groups=1, returned_groups=1, available_groups=None)
    assert selection.available_groups is None
    with pytest.raises(ValidationError):
        VisualSelection(shown_groups=2, returned_groups=1, available_groups=None)
    with pytest.raises(ValidationError):
        VisualSelection(shown_groups=1, returned_groups=2, available_groups=1)


def test_resolution_states_are_closed_and_failures_require_reasons():
    with pytest.raises(ValidationError):
        PresentationResolution(state="success", reason="Not a supported state")
    with pytest.raises(ValidationError):
        PresentationResolution(state="invalid_evidence")
    with pytest.raises(ValidationError):
        PresentationResolution(state="ready")
    result = PresentationResolution(state="missing_evidence", reason="Saved evidence unavailable.")
    assert result.evidence is None


@pytest.mark.parametrize("field", ["report_id", "section_id", "snapshot_id", "context_id"])
def test_mutated_source_identity_mismatch_is_rejected(field):
    source = report()
    setattr(source.sections[0].outcome.result, field, "different")
    with pytest.raises(VisualEvidenceError):
        prepare_visual_evidence(source, "section")


def test_conflicting_operation_and_noninteger_source_version_are_rejected():
    source = report()
    source.sections[0].interpretation.operation_id = "distribution"
    with pytest.raises(VisualEvidenceError):
        prepare_visual_evidence(source, "section")
    source = report()
    source.sections[0].outcome.result.__dict__["evidence_version"] = 2.0
    with pytest.raises(VisualEvidenceError):
        prepare_visual_evidence(source, "section")


def test_saved_coverage_rejects_overlaps_and_other_snapshot():
    source = report()
    payload = source.sections[0].outcome.result.model_dump(mode="json")
    payload["bucket_coverage"] = {
        "coverage_version": 1,
        "snapshot_id": "c" * 64,
        "context_id": source.context_id,
        "declaration_sha256": "d" * 64,
        "intervals": [{"origin": "JFK", "start": "2013-01-01", "end": "2013-01-07"}],
    }
    result_type = type(source.sections[0].outcome.result)
    with pytest.raises(ValidationError):
        result_type.model_validate(payload)
    payload["bucket_coverage"]["snapshot_id"] = source.snapshot_id
    payload["bucket_coverage"]["intervals"].append(
        {"origin": "JFK", "start": "2013-01-03", "end": "2013-01-08"},
    )
    with pytest.raises(ValidationError):
        result_type.model_validate(payload)


def test_missing_or_failed_section_never_becomes_scalar_chart():
    source = report()
    with pytest.raises(VisualEvidenceError):
        prepare_visual_evidence(source, "absent")
    payload = report_payload()
    second = deepcopy(payload["sections"][0])
    second.update(section_id="failed", position=2, label="Failed analysis")
    second["interpretation"]["section_id"] = "failed"
    second["outcome"] = {
        "status": "failed",
        "failure": {"category": "execution_failed", "code": "timeout", "message": "Timed out."},
    }
    payload["sections"].append(second)
    payload["completeness"] = "incomplete"
    with pytest.raises(VisualEvidenceError):
        prepare_visual_evidence(CompositeReportV2.model_validate(payload), "failed")


@pytest.mark.parametrize(
    "shape,view,groups,primary,series,valid",
    [
        ("category", "bar", 20, 20, 0, True),
        ("category", "bar", 21, 21, 0, False),
        ("category", "table", 21, 21, 0, True),
        ("time_series", "line", 8, 1, 8, True),
        ("time_series", "line", 9, 1, 9, False),
        ("time_series", "small_multiples", 20, 1, 20, True),
        ("time_series", "small_multiples", 21, 1, 21, False),
        ("two_category", "grouped_bar", 160, 20, 8, True),
        ("two_category", "grouped_bar", 180, 20, 9, False),
        ("two_category", "grouped_bar", 168, 21, 8, False),
        ("two_category", "heatmap", 500, 25, 20, True),
        ("two_category", "heatmap", 501, 25, 21, False),
    ],
)
def test_applied_resolution_enforces_inclusive_shape_bounds(
    shape,
    view,
    groups,
    primary,
    series,
    valid,
):
    def dimension(field, count):
        return VisualDimension(
            field_id=field,
            label=field,
            role="category",
            identities=tuple(
                VisualCategory(
                    token=canonical_identity(field, str(index), "known"),
                    code=str(index),
                    label=str(index),
                    reference_status="known",
                )
                for index in range(count)
            ),
        )

    selection = VisualSelection(
        shown_groups=groups,
        returned_groups=groups,
        available_groups=groups,
        shown_series=series or None,
        returned_series=series or None,
        available_series=series or None,
    )
    visual = prepare_visual_evidence(report(), "section").model_copy(
        update={
            "shape": shape,
            "selection": selection,
            "dimensions": (dimension("primary", primary), dimension("series", series)),
        }
    )
    kwargs = dict(
        state="table_selected" if view == "table" else "ready",
        evidence=visual,
        view=view,
        selection=selection,
        compatible_views=(view,),
    )
    if valid:
        assert PresentationResolution(**kwargs).view == view
    else:
        with pytest.raises(ValidationError):
            PresentationResolution(**kwargs)


def test_applied_resolution_rejects_unknown_identity_and_changed_analytical_counts():
    visual = prepare_visual_evidence(report(), "section")
    for selection in [
        VisualSelection(
            shown_groups=1,
            returned_groups=1,
            available_groups=1,
            category_ids=("absent",),
        ),
        VisualSelection(shown_groups=1, returned_groups=2, available_groups=2),
    ]:
        with pytest.raises(ValidationError):
            PresentationResolution(
                state="ready",
                evidence=visual,
                selection=selection,
                view="summary",
                compatible_views=("summary",),
            )
