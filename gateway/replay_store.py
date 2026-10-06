"""Replay protection stores for the AGX Gateway."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock
from typing import Protocol


class ReplayStore(Protocol):
    """Reserve an ACTION identity exactly once."""

    def reserve(self, session_id: str, message_id: str) -> bool:
        """Return True when the identity is new, False when already seen."""


class InMemoryReplayStore:
    """Process-local replay store used by tests and embedded callers."""

    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()
        self._lock = Lock()

    def reserve(self, session_id: str, message_id: str) -> bool:
        key = (session_id, message_id)

        with self._lock:
            if key in self._seen:
                return False

            self._seen.add(key)
            return True


class SQLiteReplayStore:
    """Persistent replay store backed by SQLite."""

    def __init__(
        self,
        path: str | Path,
        *,
        retention_seconds: int = 900,
    ) -> None:
        if retention_seconds <= 0:
            raise ValueError("retention_seconds must be positive")

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.retention_seconds = retention_seconds
        self._lock = Lock()

        self._initialize()

    # Schema is created lazily on every connection, not only in __init__.
    # Legacy databases created before per-tab sessions may exist without the
    # replay_keys table; a one-time init at process start left such DBs broken
    # ("no such table: replay_keys") until the gateway was restarted.
    _SCHEMA_SQL = """
                CREATE TABLE IF NOT EXISTS replay_keys (
                    session_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY (session_id, message_id)
                )
    """

    _INDEX_SQL = """
                CREATE INDEX IF NOT EXISTS idx_replay_created_at
                ON replay_keys(created_at)
    """

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=5.0,
        )

        self._ensure_schema(connection)

        return connection

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        """Create or migrate the replay_keys table on every connection.

        Legacy databases may lack the table entirely ("no such table") or
        carry the pre-5A single-column schema keyed only by message_id.
        Such tables are rebuilt with the composite (session_id, message_id)
        primary key; old rows are dropped since per-tab sessions changed
        replay semantics anyway.
        """
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='replay_keys'"
        ).fetchone()

        if row is not None and "session_id" in (row[0] or ""):
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_replay_created_at "
                "ON replay_keys(created_at)"
            )
            return

        # Missing table or legacy schema without session_id -> rebuild.
        connection.execute("DROP TABLE IF EXISTS replay_keys")
        connection.execute(SQLiteReplayStore._SCHEMA_SQL)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_replay_created_at "
            "ON replay_keys(created_at)"
        )

    def _initialize(self) -> None:
        connection = self._connect()

        try:
            connection.commit()
        finally:
            connection.close()

    def reserve(self, session_id: str, message_id: str) -> bool:
        import time

        created_at = int(time.time())
        cutoff = created_at - self.retention_seconds

        with self._lock:
            connection = self._connect()

            try:
                connection.execute("BEGIN IMMEDIATE")

                connection.execute(
                    "DELETE FROM replay_keys WHERE created_at < ?",
                    (cutoff,),
                )

                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO replay_keys(
                        session_id,
                        message_id,
                        created_at
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        session_id,
                        message_id,
                        created_at,
                    ),
                )

                connection.commit()
                return cursor.rowcount == 1
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()


__all__ = [
    "ReplayStore",
    "InMemoryReplayStore",
    "SQLiteReplayStore",
]
