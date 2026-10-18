import json
import sqlite3
from contextlib import contextmanager
from copy import deepcopy

import pytest

from airport_analytics.auth import AnalystIdentity
from airport_analytics.consent.repository import ConsentRepository
from airport_analytics.errors import (
    AuthorizationError,
    ConsentError,
    IncompleteReportError,
    ReportFormatError,
)
from airport_analytics.history.repository import ReportRepository, decode_report
from airport_analytics.models import CompositeReportV2, ReportContent
from airport_analytics.reports.rendering import saved_report_sections
from airport_analytics.storage import Storage
from tests.factories import make_report
from tests.unit.test_exploration_results import scalar_report_payload


def test_legacy_owner_and_retention_rollback(tmp_path, monkeypatch):
    storage = Storage(tmp_path / "reports.sqlite")
    owner = AnalystIdentity(analyst_id="owner", issuer="local", subject="owner")
    other = AnalystIdentity(analyst_id="other", issuer="local", subject="other")
    repo = ReportRepository(storage)
    for index in range(10):
        repo.save_report(make_report(f"old-{index}", "owner", "session"), owner)
    before = [report.report_id for report in repo.list_reports(owner)]
    original_transaction = storage.transaction

    @contextmanager
    def fail_before_commit():
        with original_transaction() as connection:
            yield connection
            raise sqlite3.OperationalError("synthetic interruption before commit")

    monkeypatch.setattr(storage, "transaction", fail_before_commit)
    with pytest.raises(sqlite3.OperationalError, match="synthetic interruption"):
        repo.save_report(make_report("new", "owner", "session"), owner)
    assert [report.report_id for report in repo.list_reports(owner)] == before
    with pytest.raises(AuthorizationError):
        repo.get_report(other, before[0])
    assert repo.get_report(owner, before[0]).analysis_plan.metric_id == "flight_count"


def test_versioned_round_trip_uses_one_parent_and_owner_scope(tmp_path):
    storage = Storage(tmp_path / "reports.sqlite")
    owner = AnalystIdentity("owner", "local", "owner")
    other = AnalystIdentity("other", "local", "other")
    repo = ReportRepository(storage)
    legacy = make_report("legacy", "owner", "session")
    report = CompositeReportV2.model_validate(scalar_report_payload())
    repo.save_report(legacy, owner)
    repo.save_report(report, owner)
    restored = repo.get_report(owner, report.report_id)
    assert restored == report
    assert isinstance(repo.get_report(owner, legacy.report_id), ReportContent)
    assert len(repo.list_reports(owner)) == 2
    assert not hasattr(restored, "analysis_plan")
    assert saved_report_sections(restored)[0].section_id == "section"
    assert len(saved_report_sections(legacy)) == 1
    with pytest.raises(AuthorizationError):
        repo.get_report(other, report.report_id)
    with pytest.raises(AuthorizationError):
        repo.delete_report(other, report.report_id)
    with storage.read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 2


@pytest.mark.parametrize("version", [0, 1, 3, "2", 2.0, True, None])
def test_unknown_or_invalid_version_is_not_guessed_from_rows(version):
    payload = make_report("legacy", "owner", "session").model_dump(mode="json")
    with pytest.raises(ReportFormatError):
        decode_report(json.dumps(payload | {"report_version": version}))


def test_malformed_json_and_invalid_v2_are_safe_explicit_errors():
    for raw in ["{}", "[]", "{", '{"report_version":2}', '{"report_version":3}']:
        with pytest.raises(ReportFormatError):
            decode_report(raw)


def test_invalid_save_never_prunes_or_persists_and_multisection_adapter_is_not_proxy(tmp_path):
    storage = Storage(tmp_path / "reports.sqlite")
    owner = AnalystIdentity("owner", "local", "owner")
    repo = ReportRepository(storage)
    original = scalar_report_payload()
    second = deepcopy(original["sections"][0])
    second.update(section_id="second", position=2, label="Second analysis")
    second["interpretation"]["section_id"] = "second"
    second["outcome"]["result"]["section_id"] = "second"
    original["sections"].append(second)
    report = CompositeReportV2.model_validate(original)
    repo.save_report(report, owner)
    assert [s.section_id for s in saved_report_sections(repo.get_report(owner, "report"))] == [
        "section",
        "second",
    ]
    failed = deepcopy(original)
    failed["report_id"] = "incomplete"
    failed["sections"][0]["outcome"]["result"]["report_id"] = "incomplete"
    failed["sections"][1]["outcome"] = {
        "status": "failed",
        "failure": {"category": "execution_failed", "code": "timeout", "message": "Timed out."},
    }
    failed["completeness"] = "incomplete"
    incomplete = CompositeReportV2.model_validate(failed)
    with pytest.raises(IncompleteReportError):
        repo.save_report(incomplete, owner)
    assert [saved.report_id for saved in repo.list_reports(owner)] == ["report"]


def test_v2_pregrant_and_wrong_session_consent_never_create_shared_content(tmp_path):
    storage = Storage(tmp_path / "reports.sqlite")
    owner = AnalystIdentity("owner", "local", "owner")
    repo = ReportRepository(storage)
    report = CompositeReportV2.model_validate(scalar_report_payload())
    repo.save_report(report, owner)
    consents = ConsentRepository(storage)
    for session in ["session", "different-session"]:
        grant = consents.record_event(owner, session, "faq", "grant", "test-v2")
        with pytest.raises(ConsentError):
            repo.create_shared_artifact(
                owner, report.report_id, purpose="faq", consent_event_id=grant.consent_event_id
            )
    assert repo.list_shared_artifacts("faq") == []
