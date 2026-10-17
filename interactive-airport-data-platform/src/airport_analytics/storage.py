"""SQLite connection, schema, and transaction management."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 3


class Storage:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=30,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        if self.database_path != ":memory:":
            connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        connection = self._connect()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reports (
                    report_id TEXT PRIMARY KEY,
                    analyst_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    question TEXT NOT NULL CHECK(length(question) <= 2000),
                    payload_json TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_reports_owner_created
                    ON reports(analyst_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS consent_events (
                    consent_event_id TEXT PRIMARY KEY,
                    analyst_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    purpose TEXT NOT NULL CHECK(purpose IN ('faq', 'system_improvement')),
                    action TEXT NOT NULL CHECK(action IN ('grant', 'withdraw')),
                    notice_version TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_consent_session_purpose
                    ON consent_events(analyst_id, session_id, purpose, occurred_at);
                CREATE TABLE IF NOT EXISTS shared_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    source_report_id TEXT NOT NULL,
                    consent_event_id TEXT NOT NULL,
                    purpose TEXT NOT NULL CHECK(purpose IN ('faq', 'system_improvement')),
                    content_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(consent_event_id)
                        REFERENCES consent_events(consent_event_id)
                );
                CREATE TABLE IF NOT EXISTS usage_reservations (
                    reservation_id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    period_start_utc TEXT NOT NULL,
                    reserved_usd TEXT NOT NULL,
                    actual_usd TEXT,
                    input_usd_per_million TEXT,
                    output_usd_per_million TEXT,
                    fee_fx_multiplier TEXT NOT NULL DEFAULT '1',
                    maximum_extra_fee_usd TEXT NOT NULL DEFAULT '0',
                    free_plan INTEGER NOT NULL DEFAULT 0,
                    max_input_tokens INTEGER NOT NULL DEFAULT 0,
                    max_output_tokens INTEGER NOT NULL DEFAULT 0,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    reserved_tokens INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL CHECK(
                        status IN ('reserved', 'settled', 'failed', 'released')
                    ),
                    failure_reason TEXT,
                    acceptance_uncertain INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    settled_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_usage_period_status
                    ON usage_reservations(period_start_utc, status);
                INSERT OR REPLACE INTO schema_metadata(key, value)
                    VALUES ('schema_version', '3');
                """
            )
            usage_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(usage_reservations)")
            }
            migrations = {
                "input_usd_per_million": "TEXT",
                "output_usd_per_million": "TEXT",
                "fee_fx_multiplier": "TEXT NOT NULL DEFAULT '1'",
                "maximum_extra_fee_usd": "TEXT NOT NULL DEFAULT '0'",
                "free_plan": "INTEGER NOT NULL DEFAULT 0",
                "max_input_tokens": "INTEGER NOT NULL DEFAULT 0",
                "max_output_tokens": "INTEGER NOT NULL DEFAULT 0",
                "acceptance_uncertain": "INTEGER NOT NULL DEFAULT 0",
            }
            for name, definition in migrations.items():
                if name not in usage_columns:
                    connection.execute(
                        f"ALTER TABLE usage_reservations ADD COLUMN {name} {definition}"
                    )
                    if name == "acceptance_uncertain":
                        connection.execute(
                            "UPDATE usage_reservations SET acceptance_uncertain = 1 "
                            "WHERE status = 'reserved' AND failure_reason IS NOT NULL"
                        )
        finally:
            connection.close()

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()
