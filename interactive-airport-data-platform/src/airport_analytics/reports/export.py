"""Complete-report PDF and current-result-table CSV serialization."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import zipfile
from datetime import date, datetime
from html import escape as html_escape
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

from airport_analytics.analytics.execution import DuckDBExecutor, listing_bindings
from airport_analytics.analytics.query_compiler import listing_sort
from airport_analytics.errors import (
    AuthorizationError,
    IncompleteReportError,
    PlatformError,
    UnsupportedAnalysisError,
    VisualExportError,
)
from airport_analytics.models import (
    CompositeReportV2,
    ExplorationResult,
    ExportSelection,
    ListingResult,
    SavedReport,
)
from airport_analytics.observability.timing import timed_stage
from airport_analytics.reports.charts import build_browser_chart, describe_visual
from airport_analytics.reports.pdf_runtime import font_face_css, render_tagged_pdf
from airport_analytics.reports.rendering import (
    section_evidence,
    summary_result_table,
    weather_findings,
)
from airport_analytics.reports.visual_evidence import (
    PresentationResolution,
    prepare_visual_evidence,
    resolve_presentation,
)


def _cell_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _transport_cell(value: Any) -> str:
    if isinstance(value, str) and (
        value.startswith("'") or value.lstrip().startswith(("=", "+", "-", "@"))
    ):
        return "'" + value
    return _cell_value(value)


def _auxiliary_csv(report, section, *, kind, columns, rows, total_rows, context=None):
    evidence = section_evidence(section)
    metadata = {
        "_meta_report_id": report.report_id,
        "_meta_section_id": section.section_id,
        "_meta_snapshot_id": report.snapshot_id,
        "_meta_context_id": report.context_id,
        "_meta_scope": json.dumps(evidence.scope.model_dump(mode="json"), separators=(",", ":")),
        "_meta_definition": json.dumps(
            evidence.definition.model_dump(mode="json"), separators=(",", ":")
        ),
        "_meta_evidence_kind": kind,
        "_meta_auxiliary_context": json.dumps(context, separators=(",", ":")),
        "_meta_fields": json.dumps(
            [field.model_dump() for field in evidence.fields],
            separators=(",", ":"),
        ),
        "_meta_limitations": json.dumps(evidence.limitations, separators=(",", ":")),
        **(
            {"_meta_weather_units_status": evidence.weather_units_status}
            if evidence.kind == "weather_panel"
            else {}
        ),
        "_meta_exported_rows": len(rows),
        "_meta_total_rows": total_rows,
        "_meta_completeness": report.completeness,
        "_meta_text_rule": "Risky text gains one apostrophe; remove that prefix to recover text.",
        "_meta_row_kind": "data" if rows else "metadata_only",
        "_meta_null_fields": "",
    }
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=[*columns, *metadata], lineterminator="\r\n")
    writer.writeheader()
    for row in rows or [{}]:
        writer.writerow(
            {key: _transport_cell(row.get(key)) for key in columns}
            | metadata
            | {
                "_meta_null_fields": json.dumps([key for key in columns if row.get(key) is None]),
            }
        )
    return output.getvalue().encode("utf-8-sig")


def listing_export_selection(
    report: CompositeReportV2,
    *,
    analyst_id: str,
    session_id: str,
    allocation: int,
    section_id: str | None = None,
) -> ExportSelection:
    if report.analyst_id != analyst_id:
        raise AuthorizationError()
    section, evidence = _summary_export_section(report, section_id)
    if not isinstance(evidence, ListingResult):
        raise UnsupportedAnalysisError("Choose a listing report for record export.")
    interpretation = section.interpretation
    sort = listing_sort(interpretation)
    direction = interpretation.order[0].direction if interpretation.order else "asc"
    scope, order = listing_bindings(interpretation, sort, direction)
    return ExportSelection(
        analyst_id=analyst_id,
        session_id=session_id,
        report_id=report.report_id,
        request_id=interpretation.request_id,
        revision=report.revision,
        snapshot_id=report.snapshot_id,
        context_id=report.context_id,
        scope_hash=scope,
        order_hash=order,
        kind="listing_csv",
        allocations={section.section_id: allocation},
        total_rows={section.section_id: evidence.total_rows},
        incomplete_acknowledgement=report.incomplete_acknowledgement,
    )


def export_listing_csv(
    report: CompositeReportV2,
    executor: DuckDBExecutor,
    selection: ExportSelection,
    *,
    analyst_id: str,
    session_id: str,
) -> bytes:
    selection = ExportSelection.model_validate(selection.model_dump())
    if (
        report.analyst_id != analyst_id
        or selection.analyst_id != analyst_id
        or selection.session_id != session_id
    ):
        raise AuthorizationError()
    if len(selection.allocations) != 1:
        raise UnsupportedAnalysisError("Select one listing section for a standalone CSV.")
    section_id = next(iter(selection.allocations))
    section, _ = _summary_export_section(report, section_id)
    expected = listing_export_selection(
        report,
        analyst_id=analyst_id,
        session_id=session_id,
        allocation=selection.allocations.get(section.section_id, -1),
        section_id=section.section_id,
    )
    if selection.model_dump(exclude={"confirmation"}) != expected.model_dump(
        exclude={"confirmation"}
    ):
        raise ValueError("Export selection is stale; choose the current report and allocation.")
    selection.require_confirmation()
    evidence = section_evidence(section)
    if not isinstance(evidence, ListingResult):
        raise UnsupportedAnalysisError("Listing evidence is required.")
    rows = executor.listing_export_rows(
        section.interpretation,
        allocation=selection.allocations[section.section_id],
        expected_total=evidence.total_rows,
    )
    return _listing_csv(report, evidence, list(rows), kind="bounded_listing_export")


def _listing_csv(
    report: CompositeReportV2,
    evidence: ListingResult,
    rows: list[dict[str, Any]],
    *,
    kind: str,
) -> bytes:
    def serialized(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    columns = [field.field_id for field in evidence.fields]
    if any(column.startswith("_meta_") for column in columns):
        raise ValueError("Listing data columns cannot use reserved metadata names.")
    metadata = {
        "_meta_report_id": report.report_id,
        "_meta_section_id": evidence.section_id,
        "_meta_revision": report.revision,
        "_meta_snapshot_id": report.snapshot_id,
        "_meta_context_id": report.context_id,
        "_meta_scope": serialized(evidence.scope.model_dump(mode="json")),
        "_meta_definition": serialized(evidence.definition.model_dump(mode="json")),
        "_meta_denominator_basis": evidence.scope.denominator_basis,
        "_meta_completeness": report.completeness,
        "_meta_exported_rows": len(rows),
        "_meta_total_rows": evidence.total_rows,
        "_meta_partial": str(len(rows) < evidence.total_rows).lower(),
        "_meta_evidence_kind": kind,
        "_meta_fields": serialized([field.model_dump(mode="json") for field in evidence.fields]),
        "_meta_order": serialized(
            evidence.browse_page.model_dump(include={"sort_field", "direction"})
            if evidence.browse_page
            else [item.model_dump() for item in evidence.order]
        ),
        "_meta_text_rule": (
            "Data text beginning with apostrophe or, after whitespace, = + - @ is prefixed "
            "with one apostrophe; remove that prefix to recover original text. Metadata is literal."
        ),
        "_meta_row_kind": "data" if rows else "metadata_only",
    }
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=[*columns, *metadata, "_meta_null_fields"],
        lineterminator="\r\n",
    )
    writer.writeheader()
    for row in rows or [{}]:
        values = {}
        for key in columns:
            values[key] = _transport_cell(row.get(key))
        writer.writerow(
            values
            | metadata
            | {
                "_meta_null_fields": serialized([key for key in columns if row.get(key) is None]),
            }
        )
    return output.getvalue().encode("utf-8-sig")


@timed_stage("export_generation")
def export_report_csv(report: SavedReport, *, supporting_routes: bool = False) -> bytes:
    if isinstance(report, CompositeReportV2):
        if len(report.sections) == 1:
            evidence = section_evidence(report.sections[0])
            if isinstance(evidence, ListingResult):
                _summary_export_section(report)
                if supporting_routes:
                    raise UnsupportedAnalysisError("Listing reports have no route-summary export.")
                return _listing_csv(report, evidence, evidence.rows, kind="saved_listing_preview")
        return _export_summary_csv(report, supporting_routes=supporting_routes)
    output = io.StringIO(newline="")
    table = report.result_payload["routes"] if supporting_routes else report.result_payload
    columns = table["columns"]
    writer = csv.DictWriter(
        output,
        fieldnames=columns,
        extrasaction="raise",
        lineterminator="\r\n",
    )
    writer.writeheader()
    for row in table["rows"]:
        writer.writerow({key: _cell_value(row.get(key)) for key in columns})
    return output.getvalue().encode("utf-8-sig")


def _flat_row(values: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in values.items():
        name = f"{prefix}__{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flat_row(value, name))
        elif not isinstance(value, list):
            flat[name] = value
    return flat


@timed_stage("export_generation")
def export_chart_evidence_csv(
    report: CompositeReportV2, resolution: PresentationResolution
) -> bytes:
    """Exact rows plotted by the applied presentation, bound to its evidence and preference."""
    evidence = resolution.evidence
    if evidence is None or resolution.state not in {"ready", "table_selected"}:
        raise VisualExportError()
    if (
        evidence.report_id != report.report_id
        or evidence.analytical_revision != report.revision
        or evidence.snapshot_id != report.snapshot_id
    ):
        raise VisualExportError("The chart evidence belongs to a different report revision.")
    payload = evidence.payload.to_dict()
    pairing = payload.get("pairing")
    if isinstance(pairing, dict) and isinstance(pairing.get("pairs"), list):
        x_name, y_name = str(pairing["x_field"]), str(pairing["y_field"])
        columns = ["source_id", x_name, y_name]
        rows = [
            {"source_id": pair.get("source_id"), x_name: pair.get("x"), y_name: pair.get("y")}
            for pair in pairing["pairs"]
        ]
    elif isinstance(pairing, dict) and isinstance(pairing.get("density"), dict):
        columns = ["x", "y", "count"]
        rows = list(pairing["density"].get("cells") or [])
    else:
        chart = (
            build_browser_chart(resolution) if resolution.view not in {"summary", "table"} else None
        )
        if chart is not None:
            rows = [_flat_row(row) for row in chart["data"]["values"]]
        else:
            rows = [_flat_row({key: value for key, value in payload.items() if key != "kind"})]
        columns = list(dict.fromkeys(key for row in rows for key in row))
    metadata = {
        "_meta_report_id": report.report_id,
        "_meta_section_id": evidence.section_id,
        "_meta_revision": evidence.analytical_revision,
        "_meta_snapshot_id": evidence.snapshot_id,
        "_meta_evidence_fingerprint": evidence.evidence_fingerprint,
        "_meta_preference_version": report.preference_version,
        "_meta_selection_rule_version": evidence.selection_rule_version,
        "_meta_visual_evidence_version": evidence.visual_evidence_version,
        "_meta_view": resolution.view,
        "_meta_state": resolution.state,
        "_meta_evidence_kind": "chart_evidence",
        "_meta_row_kind": "data" if rows else "metadata_only",
        "_meta_null_fields": "",
        "_meta_text_rule": "Risky data text gains one apostrophe; remove it to recover text.",
    }
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=[*columns, *metadata], lineterminator="\r\n")
    writer.writeheader()
    for row in rows or [{}]:
        writer.writerow(
            {key: _transport_cell(row.get(key)) for key in columns}
            | metadata
            | {"_meta_null_fields": json.dumps([key for key in columns if row.get(key) is None])}
        )
    return output.getvalue().encode("utf-8-sig")


def _register_pdf_font() -> str:
    font_name = "AirportVera"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        font_path = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
        if not font_path.is_file():
            raise FileNotFoundError("The bundled PDF font is not available.")
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    return font_name


@timed_stage("export_generation")
def export_report_pdf(report: SavedReport) -> bytes:
    if isinstance(report, CompositeReportV2):
        return _export_summary_pdf(report)
    font_name = _register_pdf_font()
    output = io.BytesIO()
    columns = report.result_payload["columns"]
    page_size = landscape(A4) if len(columns) > 4 else A4
    document = SimpleDocTemplate(
        output,
        pagesize=page_size,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="Airport Analytics Report",
        author="Interactive Airport Data Platform",
    )
    base = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AirportTitle",
        parent=base["Title"],
        fontName=font_name,
        alignment=TA_LEFT,
    )
    body_style = ParagraphStyle(
        "AirportBody",
        parent=base["BodyText"],
        fontName=font_name,
        leading=13,
    )
    question_style = ParagraphStyle("AirportQuestion", parent=base["Heading2"], fontName=font_name)
    story: list[Any] = [
        Paragraph("Airport Analytics Report", title_style),
        Spacer(1, 5 * mm),
        Paragraph(escape(report.question), question_style),
        Spacer(1, 2 * mm),
        Paragraph(escape(report.narrative), body_style),
        Spacer(1, 4 * mm),
        Paragraph("Metric definitions and scope", base["Heading2"]),
    ]
    for label, value in report.definitions.items():
        story.append(Paragraph(f"<b>{escape(label)}:</b> {escape(str(value))}", body_style))
    for label, value in report.result_payload["scope"].items():
        story.append(Paragraph(f"<b>{escape(label)}:</b> {escape(str(value))}", body_style))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Supporting result table", base["Heading2"]))
    table_data = [
        [Paragraph(escape(str(column)), body_style) for column in columns],
        *[
            [Paragraph(escape(_cell_value(row.get(column))), body_style) for column in columns]
            for row in report.result_payload["rows"]
        ],
    ]
    table = LongTable(table_data, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#102A43")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#8795A1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([table, Spacer(1, 4 * mm)])
    routes = report.result_payload.get("routes", {})
    if routes:
        story.append(Paragraph("Supporting routes", base["Heading2"]))
        status = "Complete." if routes["complete"] else "Incomplete: limited to 500 routes."
        story.append(Paragraph(escape(routes["population"] + " " + status), body_style))
        route_table = LongTable(
            [
                [Paragraph(escape(column), body_style) for column in routes["columns"]],
                *[
                    [
                        Paragraph(escape(_cell_value(row[column])), body_style)
                        for column in routes["columns"]
                    ]
                    for row in routes["rows"]
                ],
            ],
            repeatRows=1,
            hAlign="LEFT",
        )
        route_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.extend([route_table, Spacer(1, 4 * mm)])

    if report.result_payload["join_coverage"]:
        story.append(Paragraph("Reference/context join coverage", base["Heading2"]))
        for name, counts in report.result_payload["join_coverage"].items():
            story.append(
                Paragraph(
                    escape(
                        f"{name}: {counts['matched']:,} matched; "
                        f"{counts['unmatched']:,} unmatched of {counts['total']:,} "
                        f"({counts['fraction']:.2%})"
                    ),
                    body_style,
                )
            )

    if report.result_payload["glossary"]:
        story.append(PageBreak())
        story.append(Paragraph("Terms", base["Heading2"]))
        for term, definition in report.result_payload["glossary"].items():
            story.append(
                Paragraph(
                    f"<b>{escape(term.replace('_', ' ').title())}:</b> {escape(definition)}",
                    body_style,
                )
            )
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Limitations", base["Heading2"]))
    for limitation in report.limitations:
        story.append(Paragraph(f"- {escape(limitation)}", body_style))
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            f"Source snapshot: {escape(report.snapshot_id)}; report ID: "
            f"{escape(report.report_id)}; created at: {escape(report.created_at)}",
            body_style,
        )
    )
    document.build(story)
    return output.getvalue()


def _summary_export_section(report: CompositeReportV2, section_id: str | None = None):
    try:
        report.require_persistable()
    except ValueError as exc:
        raise IncompleteReportError() from exc
    if len(report.sections) != 1 and section_id is None:
        raise UnsupportedAnalysisError("Composite export is not integrated yet.")
    section = next(
        (item for item in report.sections if item.section_id == section_id),
        report.sections[0] if section_id is None else None,
    )
    if section is None:
        raise ValueError("Select an existing report section.")
    evidence = section_evidence(section)
    if evidence is None:
        raise UnsupportedAnalysisError("Failed sections cannot be exported as summary results.")
    summary_result_table(evidence)
    return section, evidence


def _export_summary_csv(
    report: CompositeReportV2,
    *,
    supporting_routes: bool,
    section_id: str | None = None,
) -> bytes:
    section, evidence = _summary_export_section(report, section_id)
    if isinstance(evidence, ListingResult):
        return _listing_csv(report, evidence, evidence.rows, kind="saved_listing_preview")
    columns, rows = summary_result_table(evidence)
    if supporting_routes:
        if "available_routes" not in evidence.missingness:
            raise UnsupportedAnalysisError("This summary has no route evidence.")
        columns = ["origin", "destination", "destination_name", "flights"]
        rows = list(evidence.route_support)
    if section.outcome.status == "valid_empty":
        rows = []

    def serialized(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    metadata = {
        "_meta_report_id": report.report_id,
        "_meta_section_id": section.section_id,
        "_meta_revision": report.revision,
        "_meta_snapshot_id": report.snapshot_id,
        "_meta_context_id": report.context_id,
        "_meta_outcome": section.outcome.status,
        "_meta_definition": serialized(evidence.definition.model_dump(mode="json")),
        "_meta_scope": serialized(evidence.scope.model_dump(mode="json")),
        "_meta_denominator_basis": evidence.scope.denominator_basis,
        "_meta_completeness": report.completeness,
        "_meta_exported_count": len(rows),
        "_meta_total_count": (
            evidence.missingness["available_routes"]
            if supporting_routes
            else _table_total_rows(evidence)
        ),
        "_meta_selection": serialized(evidence.selection.model_dump(mode="json")),
        "_meta_missingness": serialized(evidence.missingness),
        "_meta_limitations": serialized(evidence.limitations),
        "_meta_evidence_kind": "routes" if supporting_routes else "selected_summary",
        "_meta_row_kind": "data" if rows else "metadata_only",
        "_meta_fields": serialized([field.model_dump(mode="json") for field in evidence.fields]),
        "_meta_evidence_details": serialized(
            {
                key: value
                for key, value in evidence.model_dump(mode="json").items()
                if key
                in {"warnings", "known_count", "missing_count", "width", "weather_units_status"}
            }
        ),
        "_meta_null_fields": "",
        "_meta_text_rule": "Risky data text gains one apostrophe; remove it to recover text.",
    }
    if evidence.kind == "relationship":
        pair = evidence.pairing
        metadata["_meta_pair_population"] = serialized(
            pair.model_dump(
                exclude={"pairs", "density"},
            )
        )
        metadata["_meta_density_edges"] = serialized(
            pair.density.model_dump(exclude={"cells"}) if pair.density else None
        )
    if evidence.kind == "weather_panel":
        metadata["_meta_weather_populations"] = serialized(
            [
                item.model_dump(exclude={"pairing"})
                | {
                    "pairing": item.pairing.model_dump(exclude={"pairs", "density"}),
                }
                for item in evidence.variables
            ]
        )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=[*columns, *metadata], lineterminator="\r\n")
    writer.writeheader()
    for row in rows or [{}]:
        escaped = {key: _transport_cell(value) for key, value in row.items()}
        writer.writerow(
            escaped
            | metadata
            | {
                "_meta_null_fields": serialized([key for key in columns if row.get(key) is None]),
            }
        )
    return output.getvalue().encode("utf-8-sig")


def _table_total_rows(evidence: ExplorationResult) -> int:
    if evidence.kind == "relationship":
        pairing = evidence.pairing
        if pairing.pairs is not None:
            return len(pairing.pairs)
        if pairing.density is not None:
            return len(pairing.density.cells)
        raise ValueError("Relationship evidence must contain complete pairs or density cells.")
    if evidence.kind == "weather_panel":
        return len(evidence.variables)
    return evidence.selection.available


def bundle_export_selection(
    report: CompositeReportV2,
    *,
    analyst_id: str,
    session_id: str,
    allocations: dict[str, int],
) -> ExportSelection:
    if report.analyst_id != analyst_id:
        raise AuthorizationError()
    report.require_persistable()
    scopes, orders, totals = {}, {}, {}
    for section in report.sections:
        evidence = section_evidence(section)
        if not isinstance(evidence, ListingResult):
            continue
        interpretation = section.interpretation
        scope, order = listing_bindings(
            interpretation,
            listing_sort(interpretation),
            interpretation.order[0].direction if interpretation.order else "asc",
        )
        scopes[section.section_id], orders[section.section_id] = scope, order
        totals[section.section_id] = evidence.total_rows
    if set(totals) != set(allocations):
        raise ValueError("Allocate rows explicitly for every listing section.")

    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    return ExportSelection(
        analyst_id=analyst_id,
        session_id=session_id,
        report_id=report.report_id,
        request_id=report.sections[0].interpretation.request_id,
        revision=report.revision,
        snapshot_id=report.snapshot_id,
        context_id=report.context_id,
        scope_hash=digest(scopes),
        order_hash=digest(orders),
        kind="bundle_csv",
        allocations=allocations,
        total_rows=totals,
        incomplete_acknowledgement=report.incomplete_acknowledgement,
    )


@timed_stage("export_generation")
def export_report_bundle(
    report: CompositeReportV2,
    *,
    analyst_id: str,
    session_id: str,
    executor: DuckDBExecutor | None = None,
    selection: ExportSelection | None = None,
) -> bytes:
    """Atomic saved-evidence bundle; listing previews are never expanded implicitly."""
    if report.analyst_id != analyst_id:
        raise AuthorizationError()
    report.require_persistable()
    if selection is not None:
        if executor is None:
            raise ValueError("Prepared listing bundles require the bound source executor.")
        selection = ExportSelection.model_validate(selection.model_dump())
        expected = bundle_export_selection(
            report,
            analyst_id=analyst_id,
            session_id=session_id,
            allocations=selection.allocations,
        )
        if expected.model_dump(exclude={"confirmation"}) != selection.model_dump(
            exclude={"confirmation"}
        ):
            raise ValueError("The bundle selection is stale or belongs to another session.")
        selection.require_confirmation()
    files = []
    manifest = {
        "report_id": report.report_id,
        "revision": report.revision,
        "snapshot_id": report.snapshot_id,
        "context_id": report.context_id,
        "completeness": report.completeness,
        "allocations": selection.allocations if selection else None,
        "kind": "saved_evidence_csv_bundle",
        "listing_rule": "Explicit deterministic listing allocations from row one."
        if selection
        else "Saved bounded previews only; not a full-listing export.",
        "null_rule": "_meta_null_fields records null fields independently of empty text.",
        "text_rule": "Risky data text is prefixed with one reversible apostrophe.",
        "sections": [],
    }
    listing_rows = 0
    for section in report.sections:
        filename = f"section-{section.position}.csv"
        evidence = section_evidence(section)
        if evidence is None:
            output = io.StringIO(newline="")
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "_meta_report_id",
                    "_meta_section_id",
                    "_meta_snapshot_id",
                    "_meta_context_id",
                    "_meta_outcome",
                    "_meta_row_kind",
                    "_meta_failure",
                    "_meta_completeness",
                ],
                lineterminator="\r\n",
            )
            writer.writeheader()
            writer.writerow(
                {
                    "_meta_report_id": report.report_id,
                    "_meta_section_id": section.section_id,
                    "_meta_snapshot_id": report.snapshot_id,
                    "_meta_context_id": report.context_id,
                    "_meta_outcome": "failed",
                    "_meta_row_kind": "metadata_only",
                    "_meta_failure": section.outcome.failure.message,
                    "_meta_completeness": report.completeness,
                }
            )
            data = output.getvalue().encode("utf-8-sig")
            exported = 0
        else:
            if isinstance(evidence, ListingResult) and selection is not None:
                rows = list(
                    executor.listing_export_rows(
                        section.interpretation,
                        allocation=selection.allocations[section.section_id],
                        expected_total=evidence.total_rows,
                    )
                )
                data = _listing_csv(report, evidence, rows, kind="bounded_listing_export")
            else:
                data = _export_summary_csv(
                    report,
                    supporting_routes=False,
                    section_id=section.section_id,
                )
                _, rows = summary_result_table(evidence)
                if section.outcome.status == "valid_empty":
                    rows = []
            exported = len(rows)
            if isinstance(evidence, ListingResult):
                listing_rows += exported
        auxiliary_files = []
        manifest["sections"].append(
            {
                "section_id": section.section_id,
                "label": section.label,
                "file": filename,
                "auxiliary_files": auxiliary_files,
                "status": section.outcome.status,
                "exported_rows": exported,
                "total_rows": _table_total_rows(evidence) if evidence else 0,
                "selection": evidence.selection.model_dump() if evidence else None,
                "scope": evidence.scope.model_dump(mode="json") if evidence else None,
                "definition": evidence.definition.model_dump(mode="json") if evidence else None,
                "fields": [field.model_dump(mode="json") for field in evidence.fields]
                if evidence
                else [],
                "failure": section.outcome.failure.model_dump() if evidence is None else None,
                **(
                    {"weather_units_status": evidence.weather_units_status}
                    if evidence is not None and evidence.kind == "weather_panel"
                    else {}
                ),
                "listing_omitted_rows": evidence.total_rows - exported
                if isinstance(evidence, ListingResult)
                else None,
            }
        )
        files.append((filename, data))
        if evidence is not None and evidence.daily_support:
            name = f"section-{section.position}-daily-support.csv"
            auxiliary_files.append(
                {
                    "file": name,
                    "kind": "daily_support",
                    "exported_rows": len(evidence.daily_support),
                    "total_rows": evidence.missingness["available_daily_support"],
                }
            )
            files.append(
                (
                    name,
                    _auxiliary_csv(
                        report,
                        section,
                        kind="bounded_daily_support",
                        columns=list(evidence.daily_support[0]),
                        rows=list(evidence.daily_support),
                        total_rows=evidence.missingness["available_daily_support"],
                    ),
                )
            )
        if evidence is not None and evidence.kind == "weather_panel":
            for variable_index, variable in enumerate(evidence.variables, 1):
                pair = variable.pairing
                rows = (
                    [item.model_dump() for item in pair.pairs]
                    if pair.pairs is not None
                    else [item.model_dump() for item in pair.density.cells]
                )
                columns = ["source_id", "x", "y"] if pair.pairs is not None else ["x", "y", "count"]
                name = f"section-{section.position}-weather-{variable_index}.csv"
                auxiliary_files.append(
                    {
                        "file": name,
                        "kind": "weather_pairs" if pair.pairs is not None else "weather_density",
                        "exported_rows": len(rows),
                        "total_rows": len(rows),
                        "pair_count": pair.pair_count,
                    }
                )
                files.append(
                    (
                        name,
                        _auxiliary_csv(
                            report,
                            section,
                            kind="weather_pairs" if pair.pairs is not None else "weather_density",
                            columns=columns,
                            rows=rows,
                            total_rows=len(rows),
                            context=variable.model_dump(mode="json", exclude={"pairing"})
                            | {
                                "pair_population": pair.model_dump(
                                    mode="json",
                                    exclude={"pairs", "density"},
                                ),
                                "density_edges": pair.density.model_dump(exclude={"cells"})
                                if pair.density
                                else None,
                            },
                        ),
                    )
                )
    if listing_rows > 10000:
        raise ValueError("Combined listing data cannot exceed 10,000 rows.")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, data in files:
            archive.writestr(filename, data)
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return output.getvalue()


def _html_text(value: object) -> str:
    return html_escape(str(value), quote=True)


def _section_figure(report: CompositeReportV2, section) -> str:
    """Saved-evidence chart as an SVG figure with alternative text, or an explanatory note."""
    try:
        evidence = prepare_visual_evidence(report, section.section_id)
        preference = report.presentation_preferences.get(section.section_id)
        resolution = resolve_presentation(evidence, preference)
        if resolution.state not in {"ready", "table_selected"}:
            return f"<p><b>Chart:</b> {_html_text(resolution.reason or 'not available')}</p>"
        description = describe_visual(resolution)
        chart = None
        if resolution.view not in {"summary", "table"}:
            chart = build_browser_chart(resolution)
    except PlatformError as exc:
        return f"<p><b>Chart:</b> {_html_text(exc.user_message)}</p>"
    if chart is None:
        return f"<p><b>Visual summary:</b> {_html_text(description.explanation)}</p>"
    import vl_convert

    target = chart.get("spec", chart) if "facet" in chart else chart
    target.setdefault("width", 560)
    target.setdefault("height", 300)
    chart["config"] = {
        **chart.get("config", {}),
        "font": "Noto Sans",
        "axis": {"labelLimit": 360},
    }
    svg = vl_convert.vegalite_to_svg(chart)
    source = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode()
    alt = description.explanation or description.name
    return (
        f'<figure><img src="{source}" alt="{_html_text(alt)}">'
        f"<figcaption>{_html_text(description.name)}: {_html_text(alt)}</figcaption></figure>"
    )


def _export_summary_pdf(report: CompositeReportV2) -> bytes:
    """Tagged PDF for every saved V2 section, including acknowledged failed sections."""
    try:
        report.require_persistable()
    except ValueError as exc:
        raise IncompleteReportError() from exc
    blocks: list[str] = []
    widest = 0

    def paragraph(label: str, value: object) -> None:
        blocks.append(f"<p><b>{_html_text(label)}:</b> {_html_text(value)}</p>")

    def table(title: str, names: list[str], values: list[dict[str, object]]) -> None:
        nonlocal widest
        blocks.append(f"<h3>{_html_text(title)}</h3>")
        if not values:
            paragraph("Result", "No matching rows.")
            return
        widest = max(widest, len(names))
        header = "".join(f'<th scope="col">{_html_text(name)}</th>' for name in names)
        body = "".join(
            "<tr>"
            + "".join(f"<td>{_html_text(_cell_value(row.get(name)))}</td>" for name in names)
            + "</tr>"
            for row in values
        )
        blocks.append(f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>")

    blocks.append("<h1>Airport analytics report V2</h1>")
    blocks.append(f'<h2 class="question">{_html_text(report.question)}</h2>')
    paragraph("Completeness", report.completeness)
    if report.incomplete_acknowledgement is not None:
        paragraph(
            "Incomplete report acknowledged",
            ", ".join(report.incomplete_acknowledgement.failed_section_ids),
        )
    for index, section in enumerate(report.sections, 1):
        heading_class = "section" if index == 1 else "section break"
        blocks.append(
            f'<h2 class="{heading_class}">Section {index}: {_html_text(section.label)}</h2>'
        )
        paragraph("Section", section.label)
        evidence = section_evidence(section)
        if evidence is None:
            paragraph("Outcome", section.outcome.status)
            failure = section.outcome.failure
            if failure is not None:
                paragraph("Failure", failure.message)
                paragraph("Failure category", failure.category)
            continue
        columns, rows = summary_result_table(evidence)
        if isinstance(evidence, ListingResult):
            paragraph("Answer", section.narrative)
            paragraph("Outcome", section.outcome.status)
            paragraph("Operation", section.interpretation.operation_id)
            table("Saved listing preview", columns, rows)
            paragraph("Listing rows", f"{len(rows)} shown of {evidence.total_rows}")
            for limitation in evidence.limitations:
                paragraph("Limitation", limitation)
            continue
        if evidence.kind == "weather_panel":
            for finding in weather_findings(evidence).split("\n\n"):
                paragraph("Finding", finding)
        else:
            paragraph("Answer", section.narrative)
        blocks.append(_section_figure(report, section))
        if evidence.kind == "weather_panel":
            table("Weather correlations", columns, rows)
        paragraph("Outcome", section.outcome.status)
        paragraph("Operation", section.interpretation.operation_id)
        paragraph("Measures", ", ".join(section.interpretation.measure_ids))
        for label, value in evidence.definition.model_dump(mode="json").items():
            paragraph(label, value)
        for label, value in evidence.scope.model_dump(mode="json").items():
            paragraph(label, value)
        paragraph("Selection", evidence.selection.model_dump(mode="json"))
        paragraph("Known, missing and unmatched populations", evidence.missingness)
        if evidence.kind != "weather_panel":
            table("Exact selected result table", columns, rows)
        if evidence.daily_support:
            paragraph(
                "Daily support completeness",
                {
                    key: value
                    for key, value in evidence.missingness.items()
                    if "daily_support" in key
                },
            )
            table(
                "Bounded daily supporting evidence",
                list(evidence.daily_support[0]),
                list(evidence.daily_support),
            )
        if evidence.kind == "period_change":
            for warning in evidence.warnings:
                paragraph("Warning", warning)
        if evidence.kind == "relationship":
            paragraph("Pair population", evidence.pairing.model_dump(exclude={"pairs", "density"}))
            if evidence.pairing.density:
                paragraph(
                    "Density boundaries", evidence.pairing.density.model_dump(exclude={"cells"})
                )
        if evidence.kind == "weather_panel":
            for variable in evidence.variables:
                paragraph(
                    f"Weather {variable.variable} ({variable.origin or 'combined origins'})",
                    variable.pairing.model_dump(exclude={"pairs", "density"}),
                )
            if evidence.precipitation_comparison:
                paragraph(
                    "Precipitation descriptive comparison",
                    [item.model_dump(mode="json") for item in evidence.precipitation_comparison],
                )
        if evidence.route_support:
            available_routes = evidence.missingness["available_routes"]
            paragraph(
                "Route selection",
                f"{len(evidence.route_support)} shown of {available_routes}",
            )
            table(
                "Supporting routes",
                ["origin", "destination", "destination_name", "flights"],
                list(evidence.route_support),
            )
        for limitation in evidence.limitations:
            paragraph("Limitation", limitation)
        paragraph("Section ID", section.section_id)
    paragraph("Report ID", report.report_id)
    paragraph("Revision", report.revision)
    paragraph("Snapshot", report.snapshot_id)
    paragraph("Semantic context", report.context_id)
    paragraph("Created at", report.created_at.isoformat())
    paragraph(
        "Presentation",
        "Tagged PDF with saved-evidence charts where supported; exact tables are authoritative.",
    )
    page = "A4 landscape" if widest > 4 else "A4"
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        "<title>Airport analytics report V2</title>"
        '<meta name="author" content="Interactive Airport Data Platform">'
        "<style>" + font_face_css() + f"@page{{size:{page};margin:15mm}}"
        "body{font-family:AirportNoto,sans-serif;font-size:9.5pt;line-height:1.3}"
        "h1{font-size:16pt}h2{font-size:13pt}h3{font-size:11pt}"
        "h2.break{break-before:page}p{margin:0 0 2mm 0;overflow-wrap:anywhere}"
        "figure{margin:3mm 0;break-inside:avoid}figure img{max-width:100%;height:auto}"
        "figcaption{font-size:9pt}"
        "table{border-collapse:collapse;width:100%;table-layout:fixed;margin-bottom:4mm}"
        "th{background:#E8EEF4;text-align:left}"
        "th,td{border:.25pt solid #8795A1;padding:1mm;overflow-wrap:anywhere;font-size:8pt}"
        "thead{display:table-header-group}tr{break-inside:avoid}"
        "</style></head><body>" + "".join(blocks) + "</body></html>"
    )
    return render_tagged_pdf(document)
