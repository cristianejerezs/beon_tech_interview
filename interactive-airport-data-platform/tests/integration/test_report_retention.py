from datetime import UTC, datetime, timedelta
from pathlib import Path

from airport_analytics.auth import resolve_analyst_identity
from airport_analytics.consent.repository import ConsentRepository
from airport_analytics.consent.service import ConsentService
from airport_analytics.history.repository import ReportRepository
from airport_analytics.storage import Storage
from tests.factories import make_report


def test_ten_private_reports_retained_and_shared_artifacts_remain(
    tmp_path: Path,
) -> None:
    storage = Storage(tmp_path / "retention.sqlite3")
    reports = ReportRepository(storage)
    events = ConsentRepository(storage)
    service = ConsentService(reports, events, shared_reuse_enabled=True)
    owner = resolve_analyst_identity("issuer", "owner")
    other = resolve_analyst_identity("issuer", "other")
    session_id = "owner-session"
    session_state: dict[str, object] = {}
    service.set_consent(owner, session_id, "faq", True, session_state, notice_version="v1")
    first_created_at = (datetime.now(UTC) + timedelta(seconds=1)).isoformat()
    first = make_report(
        "report-00",
        owner.analyst_id,
        session_id,
        created_at=first_created_at,
    )
    reports.save_report(first, owner)
    artifact = service.create_shared_artifact(owner, first, "faq", session_state)
    assert artifact is not None

    for index in range(1, 12):
        reports.save_report(
            make_report(
                f"report-{index:02}",
                owner.analyst_id,
                session_id,
                created_at=(
                    datetime.fromisoformat(first_created_at) + timedelta(days=index)
                ).isoformat(),
            ),
            owner,
        )
    reports.save_report(make_report("other-report", other.analyst_id, "other-session"), other)

    owner_history = reports.list_reports(owner)
    assert len(owner_history) == 10
    assert "report-00" not in {item.report_id for item in owner_history}
    assert len(reports.list_reports(other)) == 1
    assert reports.get_shared_artifact(artifact.artifact_id) == artifact
    with storage.read() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM reports WHERE report_id = 'report-00'"
            ).fetchone()[0]
            == 0
        )
