from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{22}$")
MESSAGE_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")


PREFIX = "AGX1"
COMMAND_KIND = "C"
SHA256_HEX_LENGTH = 64
MAX_COMMAND_LENGTH = 128
ACTION_PATTERN = re.compile(r"^[a-zA-Z0-9_.:-]+$")


class CommandFormatError(ValueError):
    pass


class CommandValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Command:
    action: str
    args: dict[str, Any]
    session_id: str
    message_id: str


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise CommandFormatError("Invalid base64url payload")

    padding = "=" * (-len(value) % 4)

    try:
        return base64.urlsafe_b64decode(
            value + padding
        )
    except Exception as exc:
        raise CommandFormatError(
            "Invalid base64url payload"
        ) from exc


def _sha256_hex(payload: str) -> str:
    return hashlib.sha256(
        f"{COMMAND_KIND}:{payload}".encode("ascii")
    ).hexdigest()


def create_command(
    action: str,
    args: Mapping[str, Any] | None = None,
    *,
    session_id: str | None = None,
    message_id: str | None = None,
) -> Command:
    if not isinstance(action, str) or not action:
        raise CommandValidationError(
            "Command action must be a non-empty string"
        )

    if len(action) > MAX_COMMAND_LENGTH:
        raise CommandValidationError(
            "Command action is too long"
        )

    if ACTION_PATTERN.fullmatch(action) is None:
        raise CommandValidationError(
            "Invalid command action"
        )

    command_args = dict(args or {})

    if not isinstance(session_id, str) or SESSION_ID_PATTERN.fullmatch(session_id) is None:
        raise CommandValidationError("Invalid command session_id")

    if not isinstance(message_id, str) or MESSAGE_ID_PATTERN.fullmatch(message_id) is None:
        raise CommandValidationError("Invalid command message_id")

    return Command(
        action=action,
        args=command_args,
        session_id=session_id,
        message_id=message_id,
    )


def encode_command(command: Command) -> str:
    command = create_command(
        command.action,
        command.args,
    )

    canonical = _canonical_json(
        {
            "action": command.action,
            "args": command.args,
            "session_id": command.session_id,
            "message_id": command.message_id,
        }
    )

    payload = _b64url_encode(
        canonical.encode("utf-8")
    )

    digest = _sha256_hex(payload)

    return (
        f"{PREFIX}:{COMMAND_KIND}:"
        f"{payload}:{digest}"
    )


def decode_command(container: str) -> Command:
    if not isinstance(container, str):
        raise CommandFormatError(
            "Container must be a string"
        )

    container = container.strip()

    pattern = (
        rf"{re.escape(PREFIX)}:{COMMAND_KIND}:"
        rf"(?P<payload>[A-Za-z0-9_-]+):"
        rf"(?P<auth>[0-9a-fA-F]"
        rf"{{{SHA256_HEX_LENGTH}}})"
    )

    match = re.fullmatch(pattern, container)

    if match is None:
        raise CommandFormatError(
            "Invalid AGX1:C container"
        )

    payload = match.group("payload")
    supplied_auth = match.group("auth").lower()

    expected_auth = _sha256_hex(payload)

    if not hmac.compare_digest(
        supplied_auth,
        expected_auth,
    ):
        raise CommandFormatError(
            "Command integrity check failed"
        )

    raw = _b64url_decode(payload)

    try:
        data = json.loads(
            raw.decode("utf-8")
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise CommandFormatError(
            "Decoded command is not valid JSON"
        ) from exc

    if not isinstance(data, dict):
        raise CommandValidationError(
            "Decoded command must be an object"
        )

    action = data.get("action")
    args = data.get("args")
    session_id = data.get("session_id")
    message_id = data.get("message_id")

    if not isinstance(action, str) or not action:
        raise CommandValidationError(
            "Command action is missing"
        )

    if not isinstance(args, dict):
        raise CommandValidationError(
            "Command args must be an object"
        )

    return create_command(
        action,
        args,
        session_id=session_id,
        message_id=message_id,
    )

