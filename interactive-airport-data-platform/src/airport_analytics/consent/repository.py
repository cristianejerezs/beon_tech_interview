"""Append-only persistence for session- and purpose-scoped consent events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from airport_analytics.auth import AnalystIdentity
from airport_analytics.storage import Storage

ConsentPurpose = Literal["faq", "system_improvement"]
ConsentAction = Literal["grant", "withdraw"]


@dataclass(frozen=True)
class ConsentEvent:
    consent_event_id: str
    analyst_id: str
    session_id: str
    purpose: ConsentPurpose
    action: ConsentAction
    notice_version: str
    occurred_at: str


class ConsentRepository:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def record_event(
        self,
        identity: AnalystIdentity,
        session_id: str,
        purpose: ConsentPurpose,
        action: ConsentAction,
        notice_version: str,
        *,
        occurred_at: datetime | None = None,
    ) -> ConsentEvent:
        if not session_id.strip() or not notice_version.strip():
            raise ValueError("Consent session and notice version are required.")
        event = ConsentEvent(
            consent_event_id=str(uuid.uuid4()),
            analyst_id=identity.analyst_id,
            session_id=session_id,
            purpose=purpose,
            action=action,
            notice_version=notice_version,
            occurred_at=(occurred_at or datetime.now(UTC)).astimezone(UTC).isoformat(),
        )
        with self.storage.transaction() as connection:
            connection.execute(
                """
                INSERT INTO consent_events (
                    consent_event_id, analyst_id, session_id, purpose, action,
                    notice_version, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.consent_event_id,
                    event.analyst_id,
                    event.session_id,
                    event.purpose,
                    event.action,
                    event.notice_version,
                    event.occurred_at,
                ),
            )
        return event

    def latest_event(
        self,
        identity: AnalystIdentity,
        session_id: str,
        purpose: ConsentPurpose,
    ) -> ConsentEvent | None:
        with self.storage.read() as connection:
            row = connection.execute(
                """
                SELECT consent_event_id, analyst_id, session_id, purpose, action,
                    notice_version, occurred_at
                FROM consent_events
                WHERE analyst_id = ? AND session_id = ? AND purpose = ?
                ORDER BY occurred_at DESC, rowid DESC LIMIT 1
                """,
                (identity.analyst_id, session_id, purpose),
            ).fetchone()
        return ConsentEvent(**dict(row)) if row is not None else None

    def list_events(
        self,
        identity: AnalystIdentity,
        session_id: str,
        purpose: ConsentPurpose,
    ) -> list[ConsentEvent]:
        with self.storage.read() as connection:
            rows = connection.execute(
                """
                SELECT consent_event_id, analyst_id, session_id, purpose, action,
                    notice_version, occurred_at
                FROM consent_events
                WHERE analyst_id = ? AND session_id = ? AND purpose = ?
                ORDER BY occurred_at, rowid
                """,
                (identity.analyst_id, session_id, purpose),
            ).fetchall()
        return [ConsentEvent(**dict(row)) for row in rows]
