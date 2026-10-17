from pathlib import Path

import pytest

from airport_analytics.auth import resolve_analyst_identity
from airport_analytics.errors import AuthorizationError
from airport_analytics.history.repository import ReportRepository
from airport_analytics.storage import Storage
from tests.factories import make_report


def test_reports_and_export_source_access_are_owner_scoped(tmp_path: Path) -> None:
    repository = ReportRepository(Storage(tmp_path / "reports.sqlite3"))
    alice = resolve_analyst_identity("issuer", "alice")
    bob = resolve_analyst_identity("issuer", "bob")
    report = make_report("alice-report", alice.analyst_id, "alice-session")
    repository.save_report(report, alice)

    assert repository.get_report(alice, report.report_id) == report
    assert [item.report_id for item in repository.list_reports(alice)] == [report.report_id]
    with pytest.raises(AuthorizationError):
        repository.get_report(bob, report.report_id)
    with pytest.raises(AuthorizationError):
        repository.delete_report(bob, report.report_id)
    with pytest.raises(AuthorizationError):
        repository.save_report(report, bob)
    assert repository.get_report(alice, report.report_id) == report


def test_private_report_deletion_requires_owner(tmp_path: Path) -> None:
    repository = ReportRepository(Storage(tmp_path / "delete.sqlite3"))
    owner = resolve_analyst_identity("issuer", "owner")
    other = resolve_analyst_identity("issuer", "other")
    report = make_report("delete-me", owner.analyst_id, "session")
    repository.save_report(report, owner)
    with pytest.raises(AuthorizationError):
        repository.delete_report(other, report.report_id)
    repository.delete_report(owner, report.report_id)
    with pytest.raises(AuthorizationError):
        repository.get_report(owner, report.report_id)
