"""Owner-scoped private reports and separately retained shared artifacts."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from airport_analytics.auth import AnalystIdentity, require_owner
from airport_analytics.errors import AuthorizationError, ConsentError
from airport_analytics.models import ReportContent, SharedArtifact
from airport_analytics.storage import Storage

PRIVATE_REPORT_LIMIT = 10


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, Decimal)):
        return value.isoformat() if isinstance(value, datetime) else str(value)
    raise TypeError(f"Unsupported report value type: {type(value).__name__}")


class ReportRepository:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def save_report(self, report: ReportContent, identity: AnalystIdentity) -> ReportContent:
        require_owner(identity, report.analyst_id)
        payload = json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,
        )
        with self.storage.transaction() as connection:
            connection.execute(
                """
                INSERT INTO reports (
                    report_id, analyst_id, session_id, question, payload_json,
                    snapshot_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.report_id,
                    report.analyst_id,
                    report.session_id,
                    report.question,
                    payload,
                    report.snapshot_id,
                    report.created_at,
                ),
            )
            connection.execute(
                """
                DELETE FROM reports
                WHERE analyst_id = ? AND report_id NOT IN (
                    SELECT report_id FROM reports
                    WHERE analyst_id = ?
                    ORDER BY created_at DESC, rowid DESC
                    LIMIT ?
                )
                """,
                (identity.analyst_id, identity.analyst_id, PRIVATE_REPORT_LIMIT),
            )
        return report

    def list_reports(self, identity: AnalystIdentity) -> list[ReportContent]:
        with self.storage.read() as connection:
            rows = connection.execute(
                """
                SELECT payload_json FROM reports
                WHERE analyst_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (identity.analyst_id, PRIVATE_REPORT_LIMIT),
            ).fetchall()
        return [ReportContent.model_validate_json(row["payload_json"]) for row in rows]

    def get_report(self, identity: AnalystIdentity, report_id: str) -> ReportContent:
        with self.storage.read() as connection:
            row = connection.execute(
                "SELECT payload_json FROM reports WHERE report_id = ? AND analyst_id = ?",
                (report_id, identity.analyst_id),
            ).fetchone()
        if row is None:
            raise AuthorizationError()
        report = ReportContent.model_validate_json(row["payload_json"])
        require_owner(identity, report.analyst_id)
        return report

    def delete_report(self, identity: AnalystIdentity, report_id: str) -> None:
        with self.storage.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM reports WHERE report_id = ? AND analyst_id = ?",
                (report_id, identity.analyst_id),
            )
            if cursor.rowcount != 1:
                raise AuthorizationError()

    def create_shared_artifact(
        self,
        identity: AnalystIdentity,
        report_id: str,
        *,
        purpose: str,
        consent_event_id: str,
    ) -> SharedArtifact:
        with self.storage.transaction() as connection:
            owned_report = connection.execute(
                """
                SELECT analyst_id, session_id, created_at, payload_json
                FROM reports WHERE report_id = ? AND analyst_id = ?
                """,
                (report_id, identity.analyst_id),
            ).fetchone()
            if owned_report is None:
                raise AuthorizationError()
            report = ReportContent.model_validate_json(owned_report["payload_json"])
            require_owner(identity, report.analyst_id)
            grant = connection.execute(
                """
                SELECT analyst_id, session_id, purpose, action, occurred_at
                FROM consent_events WHERE consent_event_id = ?
                """,
                (consent_event_id,),
            ).fetchone()
            latest = connection.execute(
                """
                SELECT consent_event_id, action FROM consent_events
                WHERE analyst_id = ? AND session_id = ? AND purpose = ?
                ORDER BY occurred_at DESC, rowid DESC LIMIT 1
                """,
                (identity.analyst_id, report.session_id, purpose),
            ).fetchone()
            if (
                grant is None
                or grant["analyst_id"] != identity.analyst_id
                or grant["session_id"] != report.session_id
                or grant["purpose"] != purpose
                or grant["action"] != "grant"
                or grant["occurred_at"] > owned_report["created_at"]
                or latest is None
                or latest["consent_event_id"] != consent_event_id
                or latest["action"] != "grant"
            ):
                raise ConsentError("The report was not created under an active consent grant.")
            artifact = SharedArtifact(
                artifact_id=str(uuid.uuid4()),
                source_report_id=report.report_id,
                consent_event_id=consent_event_id,
                purpose=purpose,
                content={
                    "question": report.question,
                    "answer": report.narrative,
                    "metric_id": report.analysis_plan.metric_id,
                    "definitions": report.definitions,
                    "scope": report.result_payload["scope"],
                    "summary_rows": report.result_payload["rows"][:10],
                },
                created_at=datetime.now(UTC).isoformat(),
            )
            content_json = json.dumps(
                artifact.content,
                ensure_ascii=False,
                separators=(",", ":"),
                default=_json_default,
            )
            connection.execute(
                """
                INSERT INTO shared_artifacts (
                    artifact_id, source_report_id, consent_event_id, purpose,
                    content_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    artifact.source_report_id,
                    artifact.consent_event_id,
                    artifact.purpose,
                    content_json,
                    artifact.created_at,
                ),
            )
        return artifact

    def list_shared_artifacts(self, purpose: str) -> list[SharedArtifact]:
        with self.storage.read() as connection:
            rows = connection.execute(
                """
                SELECT artifact_id, source_report_id, consent_event_id, purpose,
                    content_json, created_at
                FROM shared_artifacts WHERE purpose = ?
                ORDER BY created_at, artifact_id
                """,
                (purpose,),
            ).fetchall()
        return [
            SharedArtifact(
                artifact_id=row["artifact_id"],
                source_report_id=row["source_report_id"],
                consent_event_id=row["consent_event_id"],
                purpose=row["purpose"],
                content=json.loads(row["content_json"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def get_shared_artifact(self, artifact_id: str) -> SharedArtifact:
        with self.storage.read() as connection:
            row = connection.execute(
                """
                SELECT artifact_id, source_report_id, consent_event_id, purpose,
                    content_json, created_at
                FROM shared_artifacts WHERE artifact_id = ?
                """,
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise KeyError("Shared artifact not found.")
        return SharedArtifact(
            artifact_id=row["artifact_id"],
            source_report_id=row["source_report_id"],
            consent_event_id=row["consent_event_id"],
            purpose=row["purpose"],
            content=json.loads(row["content_json"]),
            created_at=row["created_at"],
        )
