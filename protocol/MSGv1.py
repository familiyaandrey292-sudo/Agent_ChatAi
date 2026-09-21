"""AGX v1 transport container for browser-based AI integration.

The module uses only Python's standard library.

Design goals
------------
* Web-chat safe wire format: ASCII-only base64url payloads.
* ACTION messages are untrusted input from an AI/browser and are protected
  against accidental corruption with SHA-256.
* RESULT messages are produced by the local gateway and authenticated with
  HMAC-SHA256 using a secret shared by the browser bridge and local gateway.
* ACTION and RESULT have different wire-level type markers, preventing a
  valid container from one type being reused as the other type.
* session_id, message_id, command_id, nonce, timestamp and sequence are
  included for correlation and replay protection at the gateway/bridge layer.

Wire format
-----------
ACTION:
    AGX1:A:<base64url(canonical-json)>:<sha256>

RESULT:
    AGX1:R:<base64url(canonical-json)>:<hmac-sha256>

The protocol deliberately does not contain a "PC" or "Windows" marker.
The browser chat only needs to know that a structured action/result envelope
exists; local policy decides what the action actually does.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Literal

PROTOCOL_VERSION = 1
PREFIX = "AGX1"
ACTION_KIND = "A"
RESULT_KIND = "R"
SHA256_HEX_LENGTH = 64
HMAC_HEX_LENGTH = 64
MAX_TIMESTAMP_LENGTH = 64
MAX_ID_LENGTH = 128
MAX_ACTION_LENGTH = 128

# ACTION freshness policy.
MAX_ACTION_AGE_SECONDS = 300
MAX_ACTION_FUTURE_SKEW_SECONDS = 30

_CONTAINER_RE = re.compile(
    rf"(?<![A-Za-z0-9_-]){re.escape(PREFIX)}:(?P<kind>[AR]):"
    rf"(?P<payload>[A-Za-z0-9_-]+):"
    rf"(?P<auth>[0-9a-fA-F]{{{HMAC_HEX_LENGTH}}})(?![A-Za-z0-9_-])"
)


class AGXError(ValueError):
    """Base exception for protocol errors."""


class AGXFormatError(AGXError):
    """Container syntax or encoding is invalid."""


class AGXIntegrityError(AGXError):
    """Checksum or HMAC validation failed."""


class AGXAuthenticationError(AGXIntegrityError):
    """Authenticated RESULT does not have a valid MAC."""


class AGXValidationError(AGXError):
    """Decoded envelope does not satisfy the protocol schema."""


@dataclass(frozen=True, slots=True)
class Action:
    """An AI-originated action request.

    ACTION is intentionally considered untrusted. Its integrity checksum only
    detects accidental or text-transport corruption; it does not authenticate
    the AI as a trusted execution authority.
    """

    version: int
    message_id: str
    command_id: str
    session_id: str
    action: str
    args: dict[str, Any]
    timestamp: str
    nonce: str
    sequence: int

    kind: Literal["action"] = "action"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "kind": self.kind,
            "message_id": self.message_id,
            "command_id": self.command_id,
            "session_id": self.session_id,
            "action": self.action,
            "args": self.args,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "sequence": self.sequence,
        }


@dataclass(frozen=True, slots=True)
class Result:
    """A locally produced execution result authenticated with HMAC-SHA256."""

    version: int
    message_id: str
    command_id: str
    session_id: str
    status: Literal["ok", "error", "denied", "timeout", "confirmation_required"]
    result: Any
    timestamp: str
    nonce: str
    sequence: int
    message: str | None = None

    kind: Literal["result"] = "result"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "version": self.version,
            "kind": self.kind,
            "message_id": self.message_id,
            "command_id": self.command_id,
            "session_id": self.session_id,
            "status": self.status,
            "result": self.result,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "sequence": self.sequence,
        }
        if self.message is not None:
            data["message"] = self.message
        return data


def _canonical_json(data: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise AGXValidationError(f"Payload is not JSON-compatible: {exc}") from exc


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    if not value or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise AGXFormatError("Invalid base64url payload")
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise AGXFormatError("Invalid base64url payload") from exc


def _sha256_hex(kind: str, payload: str) -> str:
    data = f"{PREFIX}:{kind}:{payload}".encode("ascii")
    return hashlib.sha256(data).hexdigest()


def _hmac_hex(kind: str, payload: str, secret: bytes) -> str:
    if not isinstance(secret, bytes) or not secret:
        raise ValueError("HMAC secret must be non-empty bytes")
    data = f"{PREFIX}:{kind}:{payload}".encode("ascii")
    return hmac.new(secret, data, hashlib.sha256).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_action_timestamp(timestamp: str) -> None:
    try:
        parsed = datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise AGXValidationError("timestamp must be valid ISO-8601 UTC") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AGXValidationError("timestamp must include timezone information")

    parsed = parsed.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)

    oldest = now - timedelta(seconds=MAX_ACTION_AGE_SECONDS)
    newest = now + timedelta(seconds=MAX_ACTION_FUTURE_SKEW_SECONDS)

    if parsed < oldest:
        raise AGXValidationError(
            f"ACTION timestamp is too old; maximum age is "
            f"{MAX_ACTION_AGE_SECONDS} seconds"
        )

    if parsed > newest:
        raise AGXValidationError(
            f"ACTION timestamp is too far in the future; maximum skew is "
            f"{MAX_ACTION_FUTURE_SKEW_SECONDS} seconds"
        )


def new_session_id() -> str:
    return secrets.token_urlsafe(18)


def new_message_id() -> str:
    return uuid.uuid4().hex


def new_command_id() -> str:
    return uuid.uuid4().hex


def new_nonce() -> str:
    return secrets.token_urlsafe(18)


def _validate_common(
    data: Mapping[str, Any],
    *,
    expected_kind: Literal["action", "result"],
) -> None:
    required_common = {
        "version",
        "kind",
        "message_id",
        "command_id",
        "session_id",
        "timestamp",
        "nonce",
        "sequence",
    }
    missing = required_common - data.keys()
    if missing:
        raise AGXValidationError(f"Missing required fields: {sorted(missing)}")

    version = data["version"]
    if not isinstance(version, int) or isinstance(version, bool) or version != PROTOCOL_VERSION:
        raise AGXValidationError(f"Unsupported protocol version: {version!r}")

    kind = data["kind"]
    if kind != expected_kind:
        raise AGXValidationError(f"Unexpected message kind: {kind!r}")

    for field in ("message_id", "command_id", "session_id", "nonce"):
        value = data[field]
        if not isinstance(value, str) or not value or len(value) > MAX_ID_LENGTH:
            raise AGXValidationError(
                f"{field} must be a non-empty string <= {MAX_ID_LENGTH} characters"
            )

    timestamp = data["timestamp"]
    if not isinstance(timestamp, str) or not timestamp or len(timestamp) > MAX_TIMESTAMP_LENGTH:
        raise AGXValidationError(
            f"timestamp must be a non-empty string <= {MAX_TIMESTAMP_LENGTH} characters"
        )

    sequence = data["sequence"]
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        raise AGXValidationError("sequence must be a non-negative integer")


def validate_action_dict(data: Mapping[str, Any]) -> Action:
    required = {
        "version",
        "kind",
        "message_id",
        "command_id",
        "session_id",
        "action",
        "args",
        "timestamp",
        "nonce",
        "sequence",
    }
    if set(data.keys()) != required:
        missing = required - data.keys()
        extra = set(data.keys()) - required
        details: list[str] = []
        if missing:
            details.append(f"missing={sorted(missing)}")
        if extra:
            details.append(f"unknown={sorted(extra)}")
        raise AGXValidationError("Invalid ACTION fields: " + ", ".join(details))

    _validate_common(data, expected_kind="action")
    _validate_action_timestamp(data["timestamp"])

    action = data["action"]
    if (
        not isinstance(action, str)
        or not action
        or len(action) > MAX_ACTION_LENGTH
        or re.fullmatch(r"[a-zA-Z0-9_.:-]+", action) is None
    ):
        raise AGXValidationError("action contains invalid characters")

    args = data["args"]
    if not isinstance(args, dict):
        raise AGXValidationError("args must be a JSON object")

    return Action(
        version=data["version"],
        message_id=data["message_id"],
        command_id=data["command_id"],
        session_id=data["session_id"],
        action=action,
        args=dict(args),
        timestamp=data["timestamp"],
        nonce=data["nonce"],
        sequence=data["sequence"],
    )


def validate_result_dict(data: Mapping[str, Any]) -> Result:
    required = {
        "version",
        "kind",
        "message_id",
        "command_id",
        "session_id",
        "status",
        "result",
        "timestamp",
        "nonce",
        "sequence",
    }
    allowed = required | {"message"}
    missing = required - data.keys()
    extra = set(data.keys()) - allowed
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing={sorted(missing)}")
        if extra:
            details.append(f"unknown={sorted(extra)}")
        raise AGXValidationError("Invalid RESULT fields: " + ", ".join(details))

    _validate_common(data, expected_kind="result")

    status = data["status"]
    if status not in {"ok", "error", "denied", "timeout", "confirmation_required"}:
        raise AGXValidationError(f"Unsupported RESULT status: {status!r}")

    if "message" in data:
        message = data["message"]
        if message is not None and (not isinstance(message, str) or len(message) > 16_384):
            raise AGXValidationError("message must be a string <= 16384 characters or null")
    else:
        message = None

    return Result(
        version=data["version"],
        message_id=data["message_id"],
        command_id=data["command_id"],
        session_id=data["session_id"],
        status=status,
        result=data["result"],
        timestamp=data["timestamp"],
        nonce=data["nonce"],
        sequence=data["sequence"],
        message=message,
    )


def create_action(
    action: str,
    args: Mapping[str, Any] | None = None,
    *,
    session_id: str,
    command_id: str | None = None,
    sequence: int = 0,
) -> Action:
    raw = {
        "version": PROTOCOL_VERSION,
        "kind": "action",
        "message_id": new_message_id(),
        "command_id": command_id or new_command_id(),
        "session_id": session_id,
        "action": action,
        "args": dict(args or {}),
        "timestamp": _utc_now(),
        "nonce": new_nonce(),
        "sequence": sequence,
    }
    return validate_action_dict(raw)


def create_result(
    *,
    command_id: str,
    session_id: str,
    status: Literal["ok", "error", "denied", "timeout", "confirmation_required"],
    result: Any,
    message: str | None = None,
    sequence: int = 0,
) -> Result:
    raw = {
        "version": PROTOCOL_VERSION,
        "kind": "result",
        "message_id": new_message_id(),
        "command_id": command_id,
        "session_id": session_id,
        "status": status,
        "result": result,
        "timestamp": _utc_now(),
        "nonce": new_nonce(),
        "sequence": sequence,
    }
    if message is not None:
        raw["message"] = message
    return validate_result_dict(raw)


def encode_action(action: Action) -> str:
    """Encode an ACTION with a SHA-256 transport integrity checksum."""
    canonical = _canonical_json(action.to_dict())
    payload = _b64url_encode(canonical.encode("utf-8"))
    digest = _sha256_hex(ACTION_KIND, payload)
    return f"{PREFIX}:{ACTION_KIND}:{payload}:{digest}"


def encode_result(result: Result, secret: bytes) -> str:
    """Encode a RESULT with an HMAC-SHA256 authentication tag."""
    canonical = _canonical_json(result.to_dict())
    payload = _b64url_encode(canonical.encode("utf-8"))
    mac = _hmac_hex(RESULT_KIND, payload, secret)
    return f"{PREFIX}:{RESULT_KIND}:{payload}:{mac}"


def _decode_payload(payload: str) -> dict[str, Any]:
    raw_json = _b64url_decode(payload)
    try:
        data = json.loads(raw_json.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AGXFormatError("Decoded payload is not valid UTF-8 JSON") from exc
    if not isinstance(data, dict):
        raise AGXValidationError("Decoded payload must be a JSON object")
    return data


def decode_action(container: str) -> Action:
    """Verify and decode one ACTION container."""
    if not isinstance(container, str):
        raise AGXFormatError("Container must be a string")

    pattern = rf"{re.escape(PREFIX)}:{ACTION_KIND}:(?P<payload>[A-Za-z0-9_-]+):(?P<auth>[0-9a-fA-F]{{{SHA256_HEX_LENGTH}}})"
    match = re.fullmatch(pattern, container.strip())
    if match is None:
        raise AGXFormatError("Invalid ACTION container format")

    payload = match.group("payload")
    supplied = match.group("auth").lower()
    expected = _sha256_hex(ACTION_KIND, payload)
    if not secrets.compare_digest(supplied, expected):
        raise AGXIntegrityError("ACTION payload hash mismatch")

    return validate_action_dict(_decode_payload(payload))


def decode_result(container: str, secret: bytes) -> Result:
    """Verify the HMAC and decode one RESULT container."""
    if not isinstance(container, str):
        raise AGXFormatError("Container must be a string")

    pattern = rf"{re.escape(PREFIX)}:{RESULT_KIND}:(?P<payload>[A-Za-z0-9_-]+):(?P<auth>[0-9a-fA-F]{{{HMAC_HEX_LENGTH}}})"
    match = re.fullmatch(pattern, container.strip())
    if match is None:
        raise AGXFormatError("Invalid RESULT container format")

    payload = match.group("payload")
    supplied = match.group("auth").lower()
    expected = _hmac_hex(RESULT_KIND, payload, secret)
    if not secrets.compare_digest(supplied, expected):
        raise AGXAuthenticationError("RESULT HMAC verification failed")

    return validate_result_dict(_decode_payload(payload))


def extract_containers(text: str, *, kind: str | None = None) -> list[str]:
    """Extract ACTION/RESULT containers from arbitrary chat text.

    Args:
        text: Raw text obtained from the browser DOM.
        kind: Optional 'A' or 'R' filter.
    """
    if not isinstance(text, str) or not text:
        return []
    if kind not in {None, ACTION_KIND, RESULT_KIND}:
        raise ValueError("kind must be None, 'A' or 'R'")

    found: list[str] = []
    for match in _CONTAINER_RE.finditer(text):
        if kind is None or match.group("kind") == kind:
            found.append(match.group(0))
    return found


def new_hmac_secret(byte_length: int = 32) -> bytes:
    """Generate a random secret for browser-bridge/gateway RESULT signing."""
    if byte_length < 32:
        raise ValueError("HMAC secret should be at least 32 bytes")
    return secrets.token_bytes(byte_length)


__all__ = [
    "PROTOCOL_VERSION",
    "PREFIX",
    "ACTION_KIND",
    "RESULT_KIND",
    "AGXError",
    "AGXFormatError",
    "AGXIntegrityError",
    "AGXAuthenticationError",
    "AGXValidationError",
    "Action",
    "Result",
    "create_action",
    "create_result",
    "decode_action",
    "decode_result",
    "encode_action",
    "encode_result",
    "extract_containers",
    "new_session_id",
    "new_message_id",
    "new_command_id",
    "new_nonce",
    "new_hmac_secret",
    "validate_action_dict",
    "validate_result_dict",
]
