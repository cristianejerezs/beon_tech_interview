"""Owner-scoped private reports and separately retained shared artifacts."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from airport_analytics.auth import AnalystIdentity, require_owner
from airport_analytics.errors import (
    AuthorizationError,
    ConsentError,
    IncompleteReportError,
    PreferenceConflictError,
    PresentationPreferenceError,
    ReportFormatError,
    UnsupportedAnalysisError,
)
from airport_analytics.models import (
    CompositeReportV2,
    ReportContent,
    SavedReport,
    SectionPresentationPreference,
    SharedArtifact,
)
from airport_analytics.reports.rendering import section_evidence, summary_result_table
from airport_analytics.storage import Storage

PRIVATE_REPORT_LIMIT = 10


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, Decimal)):
        return value.isoformat() if isinstance(value, datetime) else str(value)
    raise TypeError(f"Unsupported report value type: {type(value).__name__}")


def decode_report(payload_json: str) -> SavedReport:
    try:
        payload = json.loads(payload_json)
        if not isinstance(payload, dict):
            raise ReportFormatError()
        if "report_version" not in payload:
            return ReportContent.model_validate(payload)
        if type(payload["report_version"]) is not int or payload["report_version"] != 2:
            raise ReportFormatError()
        return CompositeReportV2.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ReportFormatError() from exc


class ReportRepository:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def save_report(self, report: SavedReport, identity: AnalystIdentity) -> SavedReport:
        require_owner(identity, report.analyst_id)
        report = decode_report(report.model_dump_json())
        if isinstance(report, CompositeReportV2):
            try:
                report.require_persistable()
            except ValueError as exc:
                raise IncompleteReportError() from exc
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
                    (
                        report.created_at.isoformat()
                        if isinstance(report, CompositeReportV2)
                        else report.created_at
                    ),
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

    def list_reports(self, identity: AnalystIdentity) -> list[SavedReport]:
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
        reports = [decode_report(row["payload_json"]) for row in rows]
        for report in reports:
            require_owner(identity, report.analyst_id)
        return reports

    def get_report(self, identity: AnalystIdentity, report_id: str) -> SavedReport:
        with self.storage.read() as connection:
            row = connection.execute(
                "SELECT payload_json FROM reports WHERE report_id = ? AND analyst_id = ?",
                (report_id, identity.analyst_id),
            ).fetchone()
        if row is None:
            raise AuthorizationError()
        report = decode_report(row["payload_json"])
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

    def update_preferences(
        self,
        identity: AnalystIdentity,
        report_id: str,
        *,
        expected_version: int,
        preferences: dict[str, SectionPresentationPreference],
    ) -> CompositeReportV2:
        if type(expected_version) is not int or expected_version < 1:
            raise PreferenceConflictError()
        validated = {
            section_id: SectionPresentationPreference.model_validate(value.model_dump())
            for section_id, value in preferences.items()
        }
        if any(
            value.chart_family not in {"default", "table"} or value.category_ids or value.series_ids
            for value in validated.values()
        ):
            raise PresentationPreferenceError()
        with self.storage.transaction() as connection:
            row = connection.execute(
                "SELECT payload_json FROM reports WHERE report_id = ? AND analyst_id = ?",
                (report_id, identity.analyst_id),
            ).fetchone()
            if row is None:
                raise AuthorizationError()
            original = decode_report(row["payload_json"])
            if not isinstance(original, CompositeReportV2):
                raise PresentationPreferenceError()
            if original.preference_version != expected_version:
                raise PreferenceConflictError()
            changed = CompositeReportV2.model_validate(
                original.model_dump()
                | {
                    "presentation_preferences": validated,
                    "preference_version": expected_version + 1,
                }
            )
            cursor = connection.execute(
                "UPDATE reports SET payload_json = ? WHERE report_id = ? AND analyst_id = ? "
                "AND payload_json = ?",
                (changed.model_dump_json(), report_id, identity.analyst_id, row["payload_json"]),
            )
            if cursor.rowcount != 1:
                raise PreferenceConflictError()
        return changed

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
            report = decode_report(owned_report["payload_json"])
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
            if isinstance(report, CompositeReportV2):
                report.require_persistable()
                if len(report.sections) > 1 or report.completeness == "incomplete":
                    summaries = []
                    for section in report.sections:
                        evidence = section_evidence(section)
                        if evidence is None:
                            summaries.append(
                                {
                                    "label": section.label,
                                    "status": "failed",
                                    "failure": section.outcome.failure.message,
                                    "summary_rows": [],
                                }
                            )
                            continue
                        safe_summary = evidence.kind not in {"listing", "relationship"}
                        _, rows = summary_result_table(evidence) if safe_summary else ([], [])
                        summaries.append(
                            {
                                "label": section.label,
                                "status": section.outcome.status,
                                "answer": section.narrative
                                if safe_summary
                                else "Record-level evidence is excluded from shared summaries.",
                                "definition": evidence.definition.model_dump(mode="json"),
                                "scope": evidence.scope.model_dump(mode="json"),
                                "summary_rows": rows[:10],
                                "selection": evidence.selection.model_dump(),
                                "missingness": evidence.missingness,
                                "limitations": evidence.limitations,
                            }
                        )
                    content = {
                        "shared_summary_version": 2,
                        "snapshot_id": report.snapshot_id,
                        "context_id": report.context_id,
                        "question": report.question,
                        "answer": "Incomplete analytical summary; failed sections are not answers."
                        if report.completeness == "incomplete"
                        else "Multi-section analytical summary.",
                        "metric_id": "composite",
                        "definitions": {},
                        "scope": {},
                        "summary_rows": [],
                        "sections": summaries,
                        "completeness": report.completeness,
                    }
                else:
                    content = self._single_section_shared_content(report)
            else:
                content = {
                    "question": report.question,
                    "answer": report.narrative,
                    "metric_id": report.analysis_plan.metric_id,
                    "definitions": report.definitions,
                    "scope": report.result_payload["scope"],
                    "summary_rows": report.result_payload["rows"][:10],
                }
            artifact = SharedArtifact(
                artifact_id=str(uuid.uuid4()),
                source_report_id=report.report_id,
                consent_event_id=consent_event_id,
                purpose=purpose,
                content=content,
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

    @staticmethod
    def _single_section_shared_content(report: CompositeReportV2) -> dict:
        section = report.sections[0]
        evidence = section_evidence(section)
        if evidence is None or evidence.kind in {"listing", "relationship"}:
            raise UnsupportedAnalysisError("Record-level evidence cannot be shared as a summary.")
        _, summary_rows = summary_result_table(evidence)
        return {
            "shared_summary_version": 2,
            "question": report.question,
            "answer": section.narrative,
            "metric_id": section.interpretation.measure_ids[0],
            "definitions": section.interpretation.definition.model_dump(mode="json"),
            "scope": evidence.scope.model_dump(mode="json"),
            "summary_rows": summary_rows[:10],
            "section_id": section.section_id,
            "snapshot_id": report.snapshot_id,
            "context_id": report.context_id,
            "selection": evidence.selection.model_dump(mode="json"),
            "missingness": evidence.missingness,
            "limitations": evidence.limitations,
        }

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
