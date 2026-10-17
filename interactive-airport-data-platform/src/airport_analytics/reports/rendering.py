"""Deterministic, accessible report presentation from validated result rows."""

from __future__ import annotations

from typing import Any

import plotly.express as px

from airport_analytics.data.catalog import METRICS
from airport_analytics.models import ReportContent


def chart_kind(report: ReportContent) -> str:
    rows = report.result_payload["rows"]
    plan = report.analysis_plan
    if not rows or len(plan.group_by) != 1 or len(rows) > 50:
        return "table"
    dimension = plan.group_by[0]
    if plan.chart_intent == "line" and dimension == "flight_month":
        return "line"
    if plan.chart_intent == "bar":
        return "bar"
    return "table"


def build_figure(report: ReportContent) -> Any | None:
    kind = chart_kind(report)
    if kind == "table":
        return None
    data = report.result_payload["rows"]
    dimension = report.analysis_plan.group_by[0]
    metric = METRICS[report.analysis_plan.metric_id]
    labels = {dimension: dimension.replace("_", " "), "metric_value": metric.unit}
    if kind == "line":
        return px.line(
            data,
            x=dimension,
            y="metric_value",
            markers=True,
            labels=labels,
            title=f"{metric.description} ({metric.unit}); {report.definitions['period']}",
        )
    return px.bar(
        data,
        x=dimension,
        y="metric_value",
        labels=labels,
        title=f"{metric.description} ({metric.unit}); {report.definitions['period']}",
        hover_data=["flight_count", "observation_count"],
    )


def render_report(report: ReportContent, st: Any) -> None:
    st.subheader("Answer")
    st.write(report.narrative)
    st.subheader("Metric definition and scope")
    st.table(
        [
            {"Item": label.replace("_", " ").title(), "Description": value}
            for label, value in report.definitions.items()
        ]
    )
    scope = report.result_payload["scope"]
    st.caption(
        "Active filters: "
        + (", ".join(scope["filters"]) if scope["filters"] else "none")
        + "; grouped by: "
        + (", ".join(scope["group_by"]) if scope["group_by"] else "overall")
    )
    st.caption(
        "Source coverage: "
        + (", ".join(scope["geographic_coverage"]) or "no origin codes")
        + "; source snapshot "
        + report.snapshot_id[:12]
    )

    coverage = report.result_payload["join_coverage"]
    if coverage:
        st.subheader("Reference and context coverage")
        coverage_rows = [
            {
                "Join": name.replace("_", " ").title(),
                "Matched records": counts["matched"],
                "Unmatched records": counts["unmatched"],
                "Coverage": f"{counts['fraction']:.2%}",
                "Population": (
                    f"{counts['total']:,} records in the filtered scope before match exclusions"
                ),
            }
            for name, counts in coverage.items()
        ]
        st.dataframe(coverage_rows, hide_index=True)

    figure = build_figure(report)
    st.subheader("Supporting results")
    if figure is not None:
        st.plotly_chart(figure)
    st.dataframe(report.result_payload["rows"], hide_index=True)
    routes = report.result_payload.get("routes", {})
    if routes:
        st.subheader("Supporting routes")
        st.caption(routes["population"])
        st.caption("Complete route table." if routes["complete"] else "Truncated to 500 routes.")
        st.dataframe(routes["rows"], hide_index=True)

    glossary = report.result_payload["glossary"]
    if glossary:
        st.subheader("Terms")
        for term, definition in glossary.items():
            st.write(f"**{term.replace('_', ' ').title()}:** {definition}")
    if report.limitations:
        st.subheader("Limitations")
        for limitation in report.limitations:
            st.write(f"- {limitation}")
