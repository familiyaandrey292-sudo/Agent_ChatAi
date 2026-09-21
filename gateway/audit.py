"""Structured local audit log for AGX Gateway events."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    """Append privacy-conscious Gateway events to a rotating JSONL file."""

    DEFAULT_MAX_BYTES = 5 * 1024 * 1024
    DEFAULT_BACKUP_COUNT = 3

    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")

        if backup_count < 0:
            raise ValueError("backup_count must be non-negative")

        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._lock = threading.Lock()

    def record(
        self,
        event: str,
        *,
        action: str | None = None,
        command_id: str | None = None,
        session_id: str | None = None,
        message_id: str | None = None,
        status: str | None = None,
        decision: str | None = None,
        reason: str | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "event": event,
        }

        fields = {
            "action": action,
            "command_id": command_id,
            "session_id": session_id,
            "message_id": message_id,
            "status": status,
            "decision": decision,
            "reason": reason,
        }

        for key, value in fields.items():
            if value is not None:
                entry[key] = value

        line = json.dumps(
            entry,
            ensure_ascii=False,
            separators=(",", ":"),
        ) + "\n"

        encoded = line.encode("utf-8")

        with self._lock:
            current_size = (
                self.path.stat().st_size
                if self.path.exists()
                else 0
            )

            if (
                current_size > 0
                and current_size + len(encoded) > self.max_bytes
            ):
                self._rotate_locked()

            with self.path.open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write(line)

    def _rotate_locked(self) -> None:
        if not self.path.exists():
            return

        if self.backup_count == 0:
            self.path.unlink()
            return

        oldest = self.path.with_name(
            self.path.name + f".{self.backup_count}"
        )

        if oldest.exists():
            oldest.unlink()

        for index in range(
            self.backup_count - 1,
            0,
            -1,
        ):
            source = self.path.with_name(
                self.path.name + f".{index}"
            )
            target = self.path.with_name(
                self.path.name + f".{index + 1}"
            )

            if source.exists():
                os.replace(source, target)

        first_backup = self.path.with_name(
            self.path.name + ".1"
        )

        os.replace(
            self.path,
            first_backup,
        )


__all__ = ["AuditLogger"]
