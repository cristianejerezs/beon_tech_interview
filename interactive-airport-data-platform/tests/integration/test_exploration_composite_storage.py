import io
import json
import zipfile

import pytest

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.auth import AnalystIdentity
from airport_analytics.history.repository import ReportRepository
from airport_analytics.reports.export import export_report_bundle
from airport_analytics.reports.generation import ExplorationReportGenerator
from airport_analytics.storage import Storage
from tests.integration.test_exploration_composites import composite_client
from tests.integration.test_exploration_summaries import FIXTURES


def stored_composite(tmp_path):
    owner = AnalystIdentity(analyst_id="owner", issuer="synthetic", subject="owner")
    with DuckDBExecutor(str(FIXTURES)) as executor:
        report = (
            ExplorationReportGenerator(composite_client(), executor)
            .generate(
                "Four analyses",
                analyst_id="owner",
                session_id="session",
                session_state={},
            )
            .report
        )
    repository = ReportRepository(Storage(tmp_path / "reports.sqlite3"))
    repository.save_report(report, owner)
    return repository, owner, report


def test_preference_updates_are_versioned_owner_scoped_and_preserve_evidence(tmp_path):
    from airport_analytics.errors import AuthorizationError, PreferenceConflictError
    from airport_analytics.models import SectionPresentationPreference

    repository, owner, report = stored_composite(tmp_path)
    preferences = {
        report.sections[1].section_id: SectionPresentationPreference(chart_family="table")
    }
    changed = repository.update_preferences(
        owner,
        report.report_id,
        expected_version=1,
        preferences=preferences,
    )
    assert changed.preference_version == 2
    omitted = {"presentation_preferences", "preference_version"}
    assert changed.model_dump(exclude=omitted) == report.model_dump(exclude=omitted)
    with pytest.raises(PreferenceConflictError, match="Refresh"):
        repository.update_preferences(owner, report.report_id, expected_version=1, preferences={})
    with pytest.raises(AuthorizationError):
        repository.update_preferences(
            AnalystIdentity("other", "synthetic", "other"),
            report.report_id,
            expected_version=2,
            preferences={},
        )
    assert repository.get_report(owner, report.report_id) == changed


def test_interrupted_preference_update_rolls_back_and_incompatible_chart_is_rejected(tmp_path):
    import sqlite3

    from airport_analytics.errors import PresentationPreferenceError
    from airport_analytics.models import SectionPresentationPreference

    repository, owner, report = stored_composite(tmp_path)
    section_id = report.sections[0].section_id
    with pytest.raises(PresentationPreferenceError):
        repository.update_preferences(
            owner,
            report.report_id,
            expected_version=1,
            preferences={section_id: SectionPresentationPreference(chart_family="scatter")},
        )
    with repository.storage.transaction() as connection:
        connection.execute(
            "CREATE TRIGGER fail_preference BEFORE UPDATE ON reports "
            "BEGIN SELECT RAISE(ABORT, 'synthetic interruption'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="interruption"):
        repository.update_preferences(
            owner,
            report.report_id,
            expected_version=1,
            preferences={section_id: SectionPresentationPreference(chart_family="table")},
        )
    assert repository.get_report(owner, report.report_id) == report


def test_retention_pruning_failure_rolls_back_parent_insertion(tmp_path):
    import sqlite3
    import uuid

    from airport_analytics.models import CompositeReportV2

    repository, owner, report = stored_composite(tmp_path)
    for _ in range(9):
        other = CompositeReportV2.model_validate_json(
            report.model_dump_json().replace(report.report_id, str(uuid.uuid4())),
        )
        repository.save_report(other, owner)
    original = repository.list_reports(owner)
    with repository.storage.transaction() as connection:
        connection.execute(
            "CREATE TRIGGER fail_prune BEFORE DELETE ON reports "
            "BEGIN SELECT RAISE(ABORT, 'synthetic prune failure'); END"
        )
    last = CompositeReportV2.model_validate_json(
        report.model_dump_json().replace(report.report_id, str(uuid.uuid4())),
    )
    with pytest.raises(sqlite3.IntegrityError, match="prune failure"):
        repository.save_report(last, owner)
    assert repository.list_reports(owner) == original


def test_composite_one_retention_slot_and_atomic_bundle_metadata(tmp_path):
    owner = AnalystIdentity(analyst_id="owner", issuer="synthetic", subject="owner")
    with DuckDBExecutor(str(FIXTURES)) as executor:
        report = (
            ExplorationReportGenerator(composite_client(), executor)
            .generate(
                "Four analyses",
                analyst_id="owner",
                session_id="session",
                session_state={},
            )
            .report
        )
    repository = ReportRepository(Storage(tmp_path / "reports.sqlite3"))
    repository.save_report(report, owner)
    assert len(repository.list_reports(owner)) == 1
    reopened = repository.get_report(owner, report.report_id)
    assert reopened == report
    data = export_report_bundle(reopened, analyst_id="owner", session_id="session")
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        assert len(bundle.namelist()) == 5
        manifest = json.loads(bundle.read("manifest.json"))
        assert [item["status"] for item in manifest["sections"]] == ["completed"] * 4
        assert manifest["completeness"] == "complete"


def test_bundle_failure_offers_no_partial_artifact(monkeypatch):
    import airport_analytics.reports.export as exports

    with DuckDBExecutor(str(FIXTURES)) as executor:
        report = (
            ExplorationReportGenerator(composite_client(), executor)
            .generate(
                "Four analyses",
                analyst_id="owner",
                session_id="session",
                session_state={},
            )
            .report
        )
    actual = exports._export_summary_csv
    calls = 0

    def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Synthetic serialization failure")
        return actual(*args, **kwargs)

    monkeypatch.setattr(exports, "_export_summary_csv", fail)
    with pytest.raises(RuntimeError, match="serialization"):
        export_report_bundle(report, analyst_id="owner", session_id="session")


def test_acknowledged_incomplete_sharing_keeps_failures_and_original_consent_time(
    tmp_path, monkeypatch
):
    from datetime import UTC, datetime

    from airport_analytics.consent.repository import ConsentRepository
    from airport_analytics.consent.service import ConsentService
    from airport_analytics.errors import ConsentError, QueryExecutionError
    from airport_analytics.models import CompositeReportV2, IncompleteAcknowledgement

    owner = AnalystIdentity("owner", "local", "owner")
    storage = Storage(tmp_path / "reports.sqlite3")
    repository = ReportRepository(storage)
    service = ConsentService(repository, ConsentRepository(storage), shared_reuse_enabled=True)
    state = {}
    service.set_consent(owner, "session", "faq", True, state, notice_version="synthetic")
    with DuckDBExecutor(str(FIXTURES)) as executor:
        actual = executor.execute_summary
        calls = 0

        def execute(item):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise QueryExecutionError()
            return actual(item)

        monkeypatch.setattr(executor, "execute_summary", execute)
        report = (
            ExplorationReportGenerator(composite_client(), executor)
            .generate(
                "Four analyses",
                analyst_id="owner",
                session_id="session",
                session_state={},
            )
            .report
        )
    created = report.created_at
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
    repository.save_report(report, owner)
    shared = service.create_shared_artifact(owner, report, "faq", state)
    assert shared.content["sections"][1]["status"] == "failed"
    assert shared.content["sections"][1]["summary_rows"] == []
    assert report.created_at == created
    service.set_consent(owner, "session", "faq", False, state, notice_version="synthetic")
    service.set_consent(owner, "session", "faq", True, state, notice_version="synthetic")
    with pytest.raises(ConsentError):
        service.create_shared_artifact(owner, report, "faq", state)


def test_allocated_bundle_enforces_one_combined_listing_limit_and_confirmation(tmp_path):
    import csv

    from pydantic import ValidationError

    from airport_analytics.models import IntentProposalV2
    from airport_analytics.reports.export import bundle_export_selection
    from tests.integration.test_exploration_browsing import copy_flights

    source = copy_flights(tmp_path, 10001)
    client = composite_client()
    payload = client.proposal.model_dump()
    for section in payload["sections"][:2]:
        section.update(
            family="individual_records",
            operation_id="flight_records",
            measure_ids=[],
            population="flights",
        )
    client.proposal = IntentProposalV2.model_validate(payload)
    with DuckDBExecutor(str(source)) as executor:
        report = (
            ExplorationReportGenerator(client, executor)
            .generate(
                "Two listings and two counts",
                analyst_id="owner",
                session_id="session",
                session_state={},
            )
            .report
        )
        allocations = {section.section_id: 5000 for section in report.sections[:2]}
        selection = bundle_export_selection(
            report, analyst_id="owner", session_id="session", allocations=allocations
        )
        with pytest.raises(ValueError, match="confirmation"):
            export_report_bundle(
                report,
                analyst_id="owner",
                session_id="session",
                executor=executor,
                selection=selection,
            )
        first = report.sections[0].section_id
        with pytest.raises(ValidationError, match="10,000"):
            bundle_export_selection(
                report,
                analyst_id="owner",
                session_id="session",
                allocations=allocations | {first: 5001},
            )
        data = export_report_bundle(
            report,
            analyst_id="owner",
            session_id="session",
            executor=executor,
            selection=selection.confirm(),
        )
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            total = 0
            for index in [1, 2]:
                rows = list(
                    csv.DictReader(
                        io.StringIO(archive.read(f"section-{index}.csv").decode("utf-8-sig"))
                    )
                )
                assert [int(row["source_row_id"]) for row in rows] == list(range(1, 5001))
                total += len(rows)
            assert total == 10000
