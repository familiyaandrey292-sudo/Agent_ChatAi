"""Ed25519 authentication for Browser Bridge HTTP requests."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from pathlib import Path
from collections.abc import Iterable
from threading import Lock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(
        (value + padding).encode("ascii")
    )


def build_auth_message(
    *,
    method: str,
    path: str,
    challenge: str,
    body: bytes,
) -> bytes:
    body_hash = hashlib.sha256(body).hexdigest()

    return (
        method.upper()
        + "\n"
        + path
        + "\n"
        + challenge
        + "\n"
        + body_hash
    ).encode("utf-8")


class BrowserAuth:
    """Verify browser requests signed by a pre-paired Ed25519 key."""

    def __init__(
        self,
        public_key: Ed25519PublicKey | Iterable[Ed25519PublicKey],
        *,
        challenge_ttl_seconds: int = 30,
    ) -> None:
        if challenge_ttl_seconds <= 0:
            raise ValueError(
                "challenge_ttl_seconds must be positive"
            )

        if isinstance(public_key, Ed25519PublicKey):
            keys = (public_key,)
        else:
            keys = tuple(public_key)

        if not keys or any(
            not isinstance(key, Ed25519PublicKey)
            for key in keys
        ):
            raise ValueError(
                "Browser authentication keys must be Ed25519"
            )

        self.public_keys = keys
        self.public_key = keys[0]
        self.challenge_ttl_seconds = challenge_ttl_seconds

        self._challenges: dict[str, float] = {}
        self._lock = Lock()

    @classmethod
    def load(cls, path: str | Path) -> "BrowserAuth":
        path = Path(path)

        public_key = serialization.load_pem_public_key(
            path.read_bytes()
        )

        if not isinstance(public_key, Ed25519PublicKey):
            raise ValueError(
                "Browser authentication key must be Ed25519"
            )

        return cls(public_key)

    @classmethod
    def load_many(
        cls,
        paths: Iterable[str | Path],
    ) -> "BrowserAuth":
        keys: list[Ed25519PublicKey] = []

        for item in paths:
            path = Path(item)
            public_key = serialization.load_pem_public_key(
                path.read_bytes()
            )

            if not isinstance(public_key, Ed25519PublicKey):
                raise ValueError(
                    "Browser authentication key must be Ed25519"
                )

            keys.append(public_key)

        if not keys:
            raise ValueError(
                "No browser authentication keys found"
            )

        return cls(keys)
    def create_challenge(self) -> str:
        challenge = _b64url_encode(
            secrets.token_bytes(32)
        )

        with self._lock:
            self._cleanup_locked()
            self._challenges[challenge] = (
                time.time() + self.challenge_ttl_seconds
            )

        return challenge

    def verify(
        self,
        *,
        method: str,
        path: str,
        body: bytes,
        challenge: str,
        signature: str,
    ) -> None:
        now = time.time()

        with self._lock:
            self._cleanup_locked()
            expires_at = self._challenges.get(
                challenge
            )

        if expires_at is None:
            raise ValueError(
                "Authentication challenge is invalid or expired"
            )

        if expires_at <= now:
            raise ValueError(
                "Authentication challenge is expired"
            )

        try:
            signature_bytes = _b64url_decode(signature)
        except Exception as exc:
            raise ValueError(
                "Authentication signature is invalid"
            ) from exc

        message = build_auth_message(
            method=method,
            path=path,
            challenge=challenge,
            body=body,
        )

        verified = False

        for public_key in self.public_keys:
            try:
                public_key.verify(
                    signature_bytes,
                    message,
                )
                verified = True
                break
            except Exception:
                continue

        if not verified:
            raise ValueError(
                "Authentication signature verification failed"
            )

        with self._lock:
            self._cleanup_locked()

        with self._lock:
            self._cleanup_locked()

            current_expiry = self._challenges.get(
                challenge
            )

            if current_expiry is None:
                raise ValueError(
                    "Authentication challenge is invalid or expired"
                )

            self._challenges.pop(
                challenge,
                None,
            )

    def _cleanup_locked(self) -> None:
        now = time.time()

        expired = [
            challenge
            for challenge, expires_at
            in self._challenges.items()
            if expires_at <= now
        ]

        for challenge in expired:
            self._challenges.pop(
                challenge,
                None,
            )


__all__ = [
    "BrowserAuth",
    "build_auth_message",
]
