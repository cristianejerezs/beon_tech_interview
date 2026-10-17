"""Complete-report PDF and current-result-table CSV serialization."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
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

from airport_analytics.models import ReportContent


def _cell_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def export_report_csv(report: ReportContent, *, supporting_routes: bool = False) -> bytes:
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


def _register_pdf_font() -> str:
    font_name = "AirportVera"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        font_path = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
        if not font_path.is_file():
            raise FileNotFoundError("The bundled PDF font is not available.")
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    return font_name


def export_report_pdf(report: ReportContent) -> bytes:
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
    story: list[Any] = [
        Paragraph("Airport Analytics Report", title_style),
        Spacer(1, 5 * mm),
        Paragraph(f"<b>Question:</b> {escape(report.question)}", body_style),
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
