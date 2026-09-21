"""One-time confirmation tokens for AGX ACTION messages."""

from __future__ import annotations

import secrets
import time
from threading import Lock


class ConfirmationStore:
    """Store pending ACTION containers behind short-lived one-time tokens."""

    def __init__(self, *, ttl_seconds: int = 120) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")

        self.ttl_seconds = ttl_seconds
        self._pending: dict[str, tuple[str, float]] = {}
        self._pending_by_container: dict[str, str] = {}
        self._lock = Lock()

    def create(self, container: str) -> str:
        with self._lock:
            now = time.time()
            self._cleanup_locked()

            existing_token = self._pending_by_container.get(container)
            if existing_token is not None:
                item = self._pending.get(existing_token)
                if item is not None:
                    _, expires_at = item
                    if expires_at > now:
                        return existing_token
                self._pending_by_container.pop(container, None)

            token = secrets.token_urlsafe(32)
            expires_at = now + self.ttl_seconds

            self._pending[token] = (container, expires_at)
            self._pending_by_container[container] = token

            return token

    def consume(self, token: str) -> str:
        now = time.time()

        with self._lock:
            self._cleanup_locked()

            item = self._pending.pop(token, None)

            if item is None:
                raise ValueError("Confirmation token is invalid or expired")

            container, expires_at = item

            if self._pending_by_container.get(container) == token:
                self._pending_by_container.pop(container, None)

            if expires_at <= now:
                raise ValueError("Confirmation token is expired")

            return container

    def cancel(self, token: str) -> str:
        now = time.time()

        with self._lock:
            self._cleanup_locked()

            item = self._pending.pop(token, None)

            if item is None:
                raise ValueError("Confirmation token is invalid or expired")

            container, expires_at = item

            if self._pending_by_container.get(container) == token:
                self._pending_by_container.pop(container, None)

            if expires_at <= now:
                raise ValueError("Confirmation token is expired")

            return container

    def _cleanup_locked(self) -> None:
        now = time.time()

        expired = [
            token
            for token, (_, expires_at) in self._pending.items()
            if expires_at <= now
        ]

        for token in expired:
            item = self._pending.pop(token, None)
            if item is not None:
                container, _ = item
                if self._pending_by_container.get(container) == token:
                    self._pending_by_container.pop(container, None)


__all__ = ["ConfirmationStore"]