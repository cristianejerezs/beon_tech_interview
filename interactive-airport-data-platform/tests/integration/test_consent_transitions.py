from pathlib import Path

import pytest

from airport_analytics.auth import resolve_analyst_identity
from airport_analytics.consent.repository import ConsentRepository
from airport_analytics.consent.service import ConsentService
from airport_analytics.errors import ConsentError
from airport_analytics.history.repository import ReportRepository
from airport_analytics.storage import Storage
from tests.factories import make_report


def service_for(tmp_path: Path) -> tuple[ConsentService, ReportRepository, ConsentRepository]:
    storage = Storage(tmp_path / "consent.sqlite3")
    reports = ReportRepository(storage)
    events = ConsentRepository(storage)
    return ConsentService(reports, events, shared_reuse_enabled=True), reports, events


def test_session_consent_decline_opt_in_withdrawal_reenable_and_new_session(
    tmp_path: Path,
) -> None:
    service, reports, events = service_for(tmp_path)
    analyst = resolve_analyst_identity("issuer", "analyst")
    session_state: dict[str, object] = {}
    session_id = "session-one"

    assert not service.is_active(analyst, session_id, "faq", session_state)
    service.set_consent(analyst, session_id, "faq", False, session_state, notice_version="v1")
    assert not service.is_active(analyst, session_id, "faq", session_state)

    service.set_consent(analyst, session_id, "faq", True, session_state, notice_version="v1")
    assert service.is_active(analyst, session_id, "faq", session_state)
    first = make_report("first", analyst.analyst_id, session_id)
    reports.save_report(first, analyst)
    first_artifact = service.create_shared_artifact(analyst, first, "faq", session_state)
    assert first_artifact is not None

    service.set_consent(analyst, session_id, "faq", False, session_state, notice_version="v1")
    assert not service.is_active(analyst, session_id, "faq", session_state)
    second = make_report("second", analyst.analyst_id, session_id)
    reports.save_report(second, analyst)
    with pytest.raises(ConsentError):
        service.create_shared_artifact(analyst, second, "faq", session_state)

    service.set_consent(analyst, session_id, "faq", True, session_state, notice_version="v1")
    third = make_report("third", analyst.analyst_id, session_id)
    reports.save_report(third, analyst)
    third_artifact = service.create_shared_artifact(analyst, third, "faq", session_state)
    assert third_artifact is not None

    new_session: dict[str, object] = {}
    assert not service.is_active(analyst, "session-two", "faq", new_session)
    assert [item.artifact_id for item in reports.list_shared_artifacts("faq")] == [
        first_artifact.artifact_id,
        third_artifact.artifact_id,
    ]
    recorded = events.list_events(analyst, session_id, "faq")
    assert [item.action for item in recorded] == ["withdraw", "grant", "withdraw", "grant"]


def test_reuse_is_blocked_in_production_until_retention_policy_is_approved(
    tmp_path: Path,
) -> None:
    storage = Storage(tmp_path / "production.sqlite3")
    reports = ReportRepository(storage)
    events = ConsentRepository(storage)
    service = ConsentService(
        reports,
        events,
        shared_reuse_enabled=True,
        production=True,
        retention_policy_approved=False,
    )
    analyst = resolve_analyst_identity("issuer", "analyst")
    with pytest.raises(ConsentError):
        service.set_consent(analyst, "session", "faq", True, {}, notice_version="v1")
