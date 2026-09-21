"""Local policy engine for AGX ACTION messages."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class PolicyResult:
    decision: PolicyDecision
    reason: str


class PolicyEngine:
    """Evaluate actions against explicit local allow/confirm/deny rules."""

    def __init__(
        self,
        *,
        allow_actions: set[str] | None = None,
        confirm_actions: set[str] | None = None,
        deny_actions: set[str] | None = None,
    ) -> None:
        self._allow_actions = set(allow_actions or ())
        self._confirm_actions = set(confirm_actions or ())
        self._deny_actions = set(deny_actions or ())

    def check(self, action: str) -> PolicyResult:
        if action in self._deny_actions:
            return PolicyResult(
                PolicyDecision.DENY,
                "Action is explicitly denied by local policy.",
            )

        if action in self._allow_actions:
            return PolicyResult(
                PolicyDecision.ALLOW,
                "Action is explicitly allowed by local policy.",
            )

        if action in self._confirm_actions:
            return PolicyResult(
                PolicyDecision.CONFIRM,
                "Action requires explicit user confirmation.",
            )

        return PolicyResult(
            PolicyDecision.DENY,
            "Action is not allowed by the current local policy.",
        )
