"""Minimal local PC Agent.

Executes a small allow-listed set of local operations.
No external Python packages are required.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AgentError(Exception):
    """Base error for PC Agent operations."""


class UnsupportedActionError(AgentError):
    """Raised when an action is not implemented by the agent."""


class InvalidArgumentsError(AgentError):
    """Raised when action arguments are invalid."""


class ComponentNotFoundError(AgentError):
    """Raised when a required external executable/component is missing."""


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    success: bool
    action: str
    result: dict[str, Any]
    message: str


class PCAgent:
    """Minimal local executor for approved actions."""

    SUPPORTED_ACTIONS = frozenset(
        {
            "system.info",
            "files.list",
            "app.open",
        }
    )

    def execute(self, action: str, args: dict[str, Any] | None = None) -> ExecutionResult:
        args = args or {}

        if action not in self.SUPPORTED_ACTIONS:
            raise UnsupportedActionError(f"Unsupported action: {action}")

        if action == "system.info":
            return self._system_info()

        if action == "files.list":
            return self._list_files(args)

        if action == "app.open":
            return self._open_app(args)

        raise UnsupportedActionError(f"Unsupported action: {action}")

    def _system_info(self) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            action="system.info",
            result={
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "python": platform.python_version(),
            },
            message="System information collected.",
        )

    def _list_files(self, args: dict[str, Any]) -> ExecutionResult:
        raw_path = args.get("path")

        if not isinstance(raw_path, str) or not raw_path.strip():
            raise InvalidArgumentsError("'path' must be a non-empty string")

        path = Path(raw_path).expanduser()

        if not path.exists():
            raise AgentError(f"Path does not exist: {path}")

        if not path.is_dir():
            raise InvalidArgumentsError(f"Path is not a directory: {path}")

        entries = []
        for item in sorted(path.iterdir(), key=lambda p: p.name.lower()):
            entries.append(
                {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                }
            )

        return ExecutionResult(
            success=True,
            action="files.list",
            result={
                "path": str(path.resolve()),
                "entries": entries,
            },
            message=f"Listed {len(entries)} entries.",
        )

    def _open_app(self, args: dict[str, Any]) -> ExecutionResult:
        name = args.get("name")

        if not isinstance(name, str) or not name.strip():
            raise InvalidArgumentsError("'name' must be a non-empty string")

        executable = shutil.which(name)

        if executable is None:
            raise ComponentNotFoundError(
                f"Executable '{name}' was not found. "
                f"Please install it or provide a valid executable available on PATH."
            )

        process = subprocess.Popen(
            [executable],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

        return ExecutionResult(
            success=True,
            action="app.open",
            result={
                "executable": executable,
                "pid": process.pid,
            },
            message=f"Started {name}.",
        )


if __name__ == "__main__":
    agent = PCAgent()
    result = agent.execute("system.info")
    print(result)
