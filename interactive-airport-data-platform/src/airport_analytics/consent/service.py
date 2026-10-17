"""Explicit reversible session consent and minimal shared-artifact creation."""

from __future__ import annotations

from collections.abc import MutableMapping

from airport_analytics.auth import AnalystIdentity, require_owner
from airport_analytics.consent.repository import (
    ConsentAction,
    ConsentPurpose,
    ConsentRepository,
)
from airport_analytics.errors import ConsentError
from airport_analytics.history.repository import ReportRepository
from airport_analytics.models import ReportContent, SharedArtifact

CONSENT_STATE_KEY = "airport_reuse_consent"
PURPOSES: tuple[ConsentPurpose, ...] = ("faq", "system_improvement")


class ConsentService:
    def __init__(
        self,
        reports: ReportRepository,
        events: ConsentRepository,
        *,
        shared_reuse_enabled: bool = False,
        production: bool = False,
        retention_policy_approved: bool = False,
    ) -> None:
        self.reports = reports
        self.events = events
        self.shared_reuse_enabled = shared_reuse_enabled
        self.production = production
        self.retention_policy_approved = retention_policy_approved

    @staticmethod
    def _session_state(session_id: str, state: MutableMapping[str, object]) -> dict[str, object]:
        sessions = state.setdefault(CONSENT_STATE_KEY, {})
        if not isinstance(sessions, dict):
            raise ConsentError("The session consent state has an invalid shape.")
        current = sessions.setdefault(session_id, {})
        if not isinstance(current, dict):
            raise ConsentError("The session consent state has an invalid shape.")
        return current

    def is_active(
        self,
        identity: AnalystIdentity,
        session_id: str,
        purpose: ConsentPurpose,
        state: MutableMapping[str, object],
    ) -> bool:
        current = self._session_state(session_id, state).get(purpose)
        if not isinstance(current, dict) or current.get("enabled") is not True:
            return False
        grant_id = current.get("consent_event_id")
        latest = self.events.latest_event(identity, session_id, purpose)
        return (
            latest is not None and latest.action == "grant" and latest.consent_event_id == grant_id
        )

    def set_consent(
        self,
        identity: AnalystIdentity,
        session_id: str,
        purpose: ConsentPurpose,
        enabled: bool,
        state: MutableMapping[str, object],
        *,
        notice_version: str,
    ):
        if enabled and not self.shared_reuse_enabled:
            raise ConsentError("Shared reuse is disabled by deployment configuration.")
        if enabled and self.production and not self.retention_policy_approved:
            raise ConsentError(
                "Production reuse remains disabled until the retention/deletion policy is approved."
            )
        action: ConsentAction = "grant" if enabled else "withdraw"
        event = self.events.record_event(
            identity,
            session_id,
            purpose,
            action,
            notice_version,
        )
        current = self._session_state(session_id, state)
        current[purpose] = {
            "enabled": enabled,
            "consent_event_id": event.consent_event_id if enabled else None,
        }
        return event

    def create_shared_artifact(
        self,
        identity: AnalystIdentity,
        report: ReportContent,
        purpose: ConsentPurpose,
        state: MutableMapping[str, object],
    ) -> SharedArtifact:
        require_owner(identity, report.analyst_id)
        if not self.is_active(identity, report.session_id, purpose, state):
            raise ConsentError("Shared reuse is not active for this report and purpose.")
        current = self._session_state(report.session_id, state)[purpose]
        consent_event_id = current.get("consent_event_id")
        if not isinstance(consent_event_id, str):
            raise ConsentError("No active consent grant authorizes this artifact.")
        return self.reports.create_shared_artifact(
            identity,
            report.report_id,
            purpose=purpose,
            consent_event_id=consent_event_id,
        )
