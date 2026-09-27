from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import re
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{22}$")
MESSAGE_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")

PREFIX = "AGX1"
COMMAND_KIND = "C"
SHA256_HEX_LENGTH = 64
MAX_COMMAND_LENGTH = 128
MAX_COMMAND_LIFETIME = 300
MAX_COMMAND_FUTURE_SKEW_SECONDS = 30
ACTION_PATTERN = re.compile(r"^[a-zA-Z0-9_.:-]+$")


class CommandFormatError(ValueError):
    pass


class CommandValidationError(ValueError):
    pass


class CommandTTLExceeded(CommandValidationError):
    def __init__(self, requested_ttl: float, max_ttl: int) -> None:
        self.requested_ttl = requested_ttl
        self.max_ttl = max_ttl
        super().__init__(
            f"COMMAND_TTL_EXCEEDED: requested_ttl={requested_ttl:g}; "
            f"max_ttl={max_ttl}"
        )


@dataclass(frozen=True)
class Command:
    action: str
    args: dict[str, Any]
    session_id: str
    message_id: str
    timestamp: float
    ttl: float


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
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise CommandFormatError("Invalid base64url payload") from exc


def _sha256_hex(payload: str) -> str:
    return hashlib.sha256(
        f"{COMMAND_KIND}:{payload}".encode("ascii")
    ).hexdigest()


def _validate_time(timestamp: float, ttl: float, now: float | None = None) -> None:
    if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
        raise CommandValidationError("Command timestamp must be a number")
    if not math.isfinite(float(timestamp)):
        raise CommandValidationError("Command timestamp must be finite")
    if not isinstance(ttl, (int, float)) or isinstance(ttl, bool):
        raise CommandValidationError("Command ttl must be a number")
    if not math.isfinite(float(ttl)) or float(ttl) <= 0:
        raise CommandValidationError("Command ttl must be positive")
    if float(ttl) > MAX_COMMAND_LIFETIME:
        raise CommandTTLExceeded(float(ttl), MAX_COMMAND_LIFETIME)

    current = time.time() if now is None else now
    if float(timestamp) > current + MAX_COMMAND_FUTURE_SKEW_SECONDS:
        raise CommandValidationError("COMMAND_TIMESTAMP_IN_FUTURE")
    if current > float(timestamp) + float(ttl):
        raise CommandValidationError("COMMAND_EXPIRED")


def create_command(
    action: str,
    args: Mapping[str, Any] | None = None,
    *,
    session_id: str | None = None,
    message_id: str | None = None,
    timestamp: float | None = None,
    ttl: float = 60,
) -> Command:
    if not isinstance(action, str) or not action:
        raise CommandValidationError("Command action must be a non-empty string")
    if len(action) > MAX_COMMAND_LENGTH:
        raise CommandValidationError("Command action is too long")
    if ACTION_PATTERN.fullmatch(action) is None:
        raise CommandValidationError("Invalid command action")

    command_args = dict(args or {})
    session_id = session_id or secrets.token_urlsafe(16)
    message_id = message_id or uuid.uuid4().hex
    timestamp = time.time() if timestamp is None else timestamp

    if SESSION_ID_PATTERN.fullmatch(session_id) is None:
        raise CommandValidationError("Invalid command session_id")
    if MESSAGE_ID_PATTERN.fullmatch(message_id) is None:
        raise CommandValidationError("Invalid command message_id")

    _validate_time(timestamp, ttl)

    return Command(
        action=action,
        args=command_args,
        session_id=session_id,
        message_id=message_id,
        timestamp=float(timestamp),
        ttl=float(ttl),
    )


def encode_command(command: Command) -> str:
    command = create_command(
        command.action,
        command.args,
        session_id=command.session_id,
        message_id=command.message_id,
        timestamp=command.timestamp,
        ttl=command.ttl,
    )
    canonical = _canonical_json(
        {
            "action": command.action,
            "args": command.args,
            "message_id": command.message_id,
            "session_id": command.session_id,
            "timestamp": command.timestamp,
            "ttl": command.ttl,
        }
    )
    payload = _b64url_encode(canonical.encode("utf-8"))
    digest = _sha256_hex(payload)
    return f"{PREFIX}:{COMMAND_KIND}:{payload}:{digest}"


def decode_command(container: str) -> Command:
    if not isinstance(container, str):
        raise CommandFormatError("Container must be a string")
    container = container.strip()
    pattern = (
        rf"{re.escape(PREFIX)}:{COMMAND_KIND}:"
        rf"(?P<payload>[A-Za-z0-9_-]+):"
        rf"(?P<auth>[0-9a-fA-F]{{{SHA256_HEX_LENGTH}}})"
    )
    match = re.fullmatch(pattern, container)
    if match is None:
        raise CommandFormatError("Invalid AGX1:C container")

    payload = match.group("payload")
    supplied_auth = match.group("auth").lower()
    expected_auth = _sha256_hex(payload)
    if not hmac.compare_digest(supplied_auth, expected_auth):
        raise CommandFormatError("Command integrity check failed")

    raw = _b64url_decode(payload)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommandFormatError("Decoded command is not valid JSON") from exc
    if not isinstance(data, dict):
        raise CommandValidationError("Decoded command must be an object")

    action = data.get("action")
    args = data.get("args")
    session_id = data.get("session_id")
    message_id = data.get("message_id")
    timestamp = data.get("timestamp")
    ttl = data.get("ttl")

    if not isinstance(action, str) or not action:
        raise CommandValidationError("Command action is missing")
    if not isinstance(args, dict):
        raise CommandValidationError("Command args must be an object")
    if not isinstance(session_id, str) or not session_id:
        raise CommandValidationError("Command session_id is missing")
    if not isinstance(message_id, str) or not message_id:
        raise CommandValidationError("Command message_id is missing")
    if timestamp is None:
        raise CommandValidationError("Command timestamp is missing")
    if ttl is None:
        raise CommandValidationError("Command ttl is missing")

    return create_command(
        action,
        args,
        session_id=session_id,
        message_id=message_id,
        timestamp=timestamp,
        ttl=ttl,
    )
