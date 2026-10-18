"""002 table/evidence components of shared cases; no 003 visual acceptance claim."""

import csv
import io
from collections import Counter
from statistics import mean

import pytest
from pypdf import PdfReader

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.auth import AnalystIdentity
from airport_analytics.history.repository import ReportRepository
from airport_analytics.reports.export import export_report_csv, export_report_pdf
from airport_analytics.reports.generation import ExplorationReportGenerator
from airport_analytics.reports.rendering import summary_result_table
from airport_analytics.storage import Storage
from tests.exploration_oracles import number, read_rows
from tests.integration.test_exploration_summaries import FIXTURES, SummaryClient, evidence, generate


@pytest.mark.parametrize(
    "case", ["E2E-01", "E2E-02", "E2E-04", "E2E-05", "E2E-06", "E2E-07", "E2E-08"]
)
def test_shared_numerical_saved_table_csv_and_pdf_components(tmp_path, case):
    rows = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    options = {
        "E2E-01": dict(
            family="grouped_summary",
            measure_ids=["distinct_destination_count"],
            grouping=["origin"],
        ),
        "E2E-02": dict(
            family="historical_trend",
            measure_ids=["flight_count"],
            grouping=["origin", "flight_month"],
        ),
        "E2E-04": dict(
            family="period_change",
            operation_id="period_change",
            measure_ids=["mean_departure_delay"],
            comparison={
                "baseline": {"start": "2013-01-01", "end": "2013-01-02"},
                "comparison": {"start": "2013-01-04", "end": "2013-01-07"},
            },
        ),
        "E2E-05": dict(
            family="distribution", operation_id="distribution", measure_ids=["departure_delay"]
        ),
        "E2E-06": dict(
            family="numeric_relationship",
            operation_id="flight_relationship",
            measure_ids=["departure_delay", "arrival_delay"],
        ),
        "E2E-07": dict(family="ranking", measure_ids=["flight_count"], grouping=["destination"]),
        "E2E-08": dict(measure_ids=["flight_count"]),
    }[case]
    with DuckDBExecutor(str(FIXTURES)) as executor:
        outcome = generate(executor, **options)
    result = evidence(outcome)
    if case == "E2E-01":
        assert {
            item.identity[0].code: item.measures["distinct_destination_count"].value
            for item in result.values
        } == {
            origin: len({row["dest"] for row in rows if row["origin"] == origin})
            for origin in {row["origin"] for row in rows}
        }
    elif case == "E2E-02":
        assert {
            tuple(identity.code for identity in item.identity): item.measures["flight_count"].value
            for item in result.values
        } == dict(
            Counter((row["origin"], f"{row['year']}-{int(row['month']):02d}") for row in rows)
        )
    elif case == "E2E-04":
        a, b = [
            mean(
                number(row["dep_delay"])
                for row in rows
                if start <= int(row["day"]) <= end and number(row["dep_delay"]) is not None
            )
            for start, end in [(1, 2), (4, 7)]
        ]
        assert result.baseline.value.value == a
        assert result.comparison.value.value == b
        assert result.absolute_change.value == b - a
        assert result.relative_change.value == pytest.approx(
            float(100 * (b - a) / a), abs=1e-9, rel=1e-12
        )
    elif case == "E2E-05":
        values = [number(row["dep_delay"]) for row in rows if number(row["dep_delay"]) is not None]
        for bucket in result.bins:
            assert bucket.count == sum(bucket.lower <= value < bucket.upper for value in values)
        assert result.missing_count == len(rows) - len(values)
    elif case == "E2E-06":
        assert [(item.source_id, item.x, item.y) for item in result.pairing.pairs] == [
            (row["column00"], number(row["dep_delay"]), number(row["arr_delay"]))
            for row in rows
            if number(row["dep_delay"]) is not None and number(row["arr_delay"]) is not None
        ]
    elif case == "E2E-07":
        counts = Counter(row["dest"] for row in rows)
        assert [
            (item.identity[0].code, item.measures["flight_count"].value) for item in result.values
        ] == sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    else:
        assert result.value.value == len(rows)
    owner = AnalystIdentity("owner", "synthetic", "owner")
    repository = ReportRepository(Storage(tmp_path / "reports.sqlite3"))
    repository.save_report(outcome.report, owner)
    reopened = repository.get_report(owner, outcome.report.report_id)
    assert reopened == outcome.report
    exported = list(csv.DictReader(io.StringIO(export_report_csv(reopened).decode("utf-8-sig"))))
    columns, displayed = summary_result_table(result)
    assert len(exported) == len(displayed)
    for saved, expected in zip(exported, displayed, strict=True):
        for column in columns:
            assert saved[column] == ("" if expected.get(column) is None else str(expected[column]))
    reader = PdfReader(io.BytesIO(export_report_pdf(reopened)))
    pdf_text = "\n".join(page.extract_text() for page in reader.pages)
    assert reopened.question in pdf_text
    assert reopened.snapshot_id in pdf_text


def test_shared_e2e_03_clarification_then_snapshot_bound_individual_records():
    from types import SimpleNamespace

    from airport_analytics.analytics.request_state import PENDING_REQUEST_KEY, AnswerEvent
    from airport_analytics.models import IntentProposalV2
    from tests.unit.test_exploration_contracts import proposed_section

    ready = IntentProposalV2.model_validate(
        {
            "intent_version": 2,
            "status": "proposed",
            "shared_scope": {},
            "selection_reason": None,
            "sections": [
                proposed_section(
                    family="individual_records",
                    operation_id="flight_records",
                    measure_ids=[],
                    population="flights",
                )
            ],
        }
    )

    class ClarificationClient(SummaryClient):
        def generate_clarification(self, *args, **kwargs):
            self.calls += 1
            return SimpleNamespace(proposal=ready)

    client = ClarificationClient()
    client.proposal = IntentProposalV2.model_validate(
        {
            "intent_version": 2,
            "status": "needs_clarification",
            "shared_scope": {},
            "selection_reason": None,
            "sections": [
                proposed_section(
                    status="needs_clarification",
                    family=None,
                    operation_id=None,
                    measure_ids=[],
                    population=None,
                    clarification={
                        "field_id": "operation",
                        "question": "Individual records or a summary?",
                        "choices": [],
                    },
                )
            ],
        }
    )
    state = {}
    with DuckDBExecutor(str(FIXTURES)) as executor:
        generator = ExplorationReportGenerator(client, executor)
        pending = generator.generate(
            "Show all flights",
            analyst_id="owner",
            session_id="session",
            session_state=state,
        )
        assert pending.report is None
        request = state[PENDING_REQUEST_KEY]
        outcome = generator.answer(
            request,
            AnswerEvent(
                session_binding="session",
                request_id=request.draft.request_id,
                revision=request.draft.revision,
                section_id=request.active_section.section_id,
                question_id=request.question_id,
                text="Individual records",
            ),
            analyst_id="owner",
            session_id="session",
            session_state=state,
        )
        listing = evidence(outcome)
        assert listing.total_rows == len(read_rows(FIXTURES / "nyc_flights_fixed.csv"))
        assert [row["source_row_id"] for row in listing.rows] == list(range(1, 10))
        assert client.calls == 2


@pytest.mark.parametrize("fault", [False, True])
def test_shared_e2e_09_mixed_sections_and_independent_runtime_fault(tmp_path, monkeypatch, fault):
    import json
    import zipfile
    from datetime import UTC, datetime

    from airport_analytics.errors import QueryExecutionError
    from airport_analytics.models import (
        CompositeReportV2,
        IncompleteAcknowledgement,
        IntentProposalV2,
    )
    from airport_analytics.reports.export import export_report_bundle
    from airport_analytics.reports.rendering import section_evidence
    from tests.unit.test_exploration_contracts import proposed_section

    client = SummaryClient()
    client.proposal = IntentProposalV2.model_validate(
        {
            "intent_version": 2,
            "status": "proposed",
            "selection_reason": None,
            "shared_scope": {
                "edits": [
                    {"field_id": "origin", "action": "replace", "operator": "eq", "value": "JFK"}
                ],
                "dates": {"start": "2013-01-01", "end": "2013-01-31"},
            },
            "sections": [
                proposed_section(position=1, original_clause="Count flights"),
                proposed_section(
                    position=2,
                    original_clause="Monthly flight counts",
                    family="historical_trend",
                    grouping=["flight_month"],
                ),
                proposed_section(
                    position=3,
                    original_clause="List destinations",
                    family="unique_entity_list",
                    operation_id="entity_list",
                    measure_ids=[],
                    population="observed_destinations",
                ),
                proposed_section(
                    position=4,
                    original_clause="Departure delay distribution",
                    family="distribution",
                    operation_id="distribution",
                    measure_ids=["departure_delay"],
                ),
            ],
        }
    )
    with DuckDBExecutor(str(FIXTURES)) as executor:
        actual = executor.execute_summary

        def execute(interpretation):
            if fault and interpretation.family == "historical_trend":
                raise QueryExecutionError()
            return actual(interpretation)

        monkeypatch.setattr(executor, "execute_summary", execute)
        report = (
            ExplorationReportGenerator(client, executor)
            .generate(
                "Four related analyses",
                analyst_id="owner",
                session_id="session",
                session_state={},
            )
            .report
        )
    rows = [row for row in read_rows(FIXTURES / "nyc_flights_fixed.csv") if row["origin"] == "JFK"]
    assert section_evidence(report.sections[0]).value.value == len(rows)
    assert {row["code"] for row in section_evidence(report.sections[2]).rows} == {
        row["dest"] for row in rows
    }
    assert section_evidence(report.sections[3]).known_count == sum(
        number(row["dep_delay"]) is not None for row in rows
    )
    if fault:
        with pytest.raises(ValueError, match="acknowledgement"):
            report.require_persistable()
        report = CompositeReportV2.model_validate(
            report.model_dump()
            | {
                "incomplete_acknowledgement": IncompleteAcknowledgement(
                    analyst_id="owner",
                    session_id="session",
                    report_id=report.report_id,
                    revision=report.revision,
                    failed_section_ids=[report.sections[1].section_id],
                    acknowledged_at=datetime.now(UTC),
                ),
            }
        )
    else:
        assert section_evidence(report.sections[1]).values[0].measures["flight_count"].value == len(
            rows
        )
    owner = AnalystIdentity("owner", "synthetic", "owner")
    repository = ReportRepository(Storage(tmp_path / "reports.sqlite3"))
    repository.save_report(report, owner)
    reopened = repository.get_report(owner, report.report_id)
    with zipfile.ZipFile(
        io.BytesIO(
            export_report_bundle(
                reopened,
                analyst_id="owner",
                session_id="session",
            )
        )
    ) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        assert len(manifest["sections"]) == 4
        assert manifest["sections"][1]["status"] == ("failed" if fault else "completed")
    pdf_text = " ".join(
        "\n".join(
            page.extract_text() or ""
            for page in PdfReader(io.BytesIO(export_report_pdf(reopened))).pages
        ).split()
    )
    for section in reopened.sections:
        assert section.label in pdf_text
    if fault:
        assert reopened.sections[1].outcome.failure.message in pdf_text
