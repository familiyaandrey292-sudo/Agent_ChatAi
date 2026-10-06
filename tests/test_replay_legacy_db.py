"""Regression: legacy replay DB without replay_keys table must self-heal.

Stage 5A moved the replay PK to (session_id, message_id). Databases created
by older gateway builds either lack the table entirely or carry the old
single-column schema. Previously SQLiteReplayStore only ran CREATE TABLE in
__init__, so a running process hitting such a DB raised
"no such table: replay_keys". Schema is now ensured on every connection.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from gateway.replay_store import SQLiteReplayStore


class TestReplayLegacyDatabase(unittest.TestCase):
    def test_existing_empty_db_file_gets_table_on_reserve(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "replay.sqlite3"
            # Simulate a file created by an old build that never initialized
            # the schema (empty valid sqlite file).
            sqlite3.connect(db).close()

            store = SQLiteReplayStore.__new__(SQLiteReplayStore)
            # Skip __init__-time init to emulate a long-running process whose
            # DB lost/never had the table; reserve() must still work.
            from threading import Lock

            store.path = db
            store.retention_seconds = 900
            store._lock = Lock()

            self.assertTrue(store.reserve("sess-a", "m" * 32))
            self.assertFalse(store.reserve("sess-a", "m" * 32))
            self.assertTrue(store.reserve("sess-b", "m" * 32))

    def test_legacy_single_column_schema_is_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "replay.sqlite3"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE replay_keys (message_id TEXT PRIMARY KEY, "
                "created_at INTEGER NOT NULL)"
            )
            conn.execute(
                "INSERT INTO replay_keys VALUES (?, ?)", ("old" * 1, 1)
            )
            conn.commit()
            conn.close()

            store = SQLiteReplayStore(db)
            # New composite-PK semantics must hold against the legacy file.
            self.assertTrue(store.reserve("sess-1", "msg-1"))
            self.assertFalse(store.reserve("sess-1", "msg-1"))
            self.assertTrue(store.reserve("sess-2", "msg-1"))


if __name__ == "__main__":
    unittest.main()
