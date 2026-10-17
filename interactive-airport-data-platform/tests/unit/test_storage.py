from pathlib import Path

import pytest

from airport_analytics.storage import SCHEMA_VERSION, Storage


def test_storage_initializes_local_tables_and_schema_version(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "nested" / "application.sqlite3")
    with storage.read() as connection:
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        version = connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
        ).fetchone()["value"]
    assert {"reports", "consent_events", "shared_artifacts", "usage_reservations"} <= tables
    assert version == str(SCHEMA_VERSION)


def test_storage_transaction_rolls_back_on_error(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "rollback.sqlite3")
    with pytest.raises(RuntimeError):
        with storage.transaction() as connection:
            connection.execute(
                """
                INSERT INTO consent_events (
                    consent_event_id, analyst_id, session_id, purpose, action,
                    notice_version, occurred_at
                ) VALUES ('event', 'analyst', 'session', 'faq', 'grant', '1', 'now')
                """
            )
            raise RuntimeError("force rollback")
    with storage.read() as connection:
        assert connection.execute("SELECT COUNT(*) FROM consent_events").fetchone()[0] == 0
