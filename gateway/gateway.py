"""Core AGX Gateway.

Validates ACTION messages, applies the local PolicyEngine,
and prevents replay of actions approved for execution.
"""

from __future__ import annotations

from dataclasses import dataclass

from protocol.MSGv1 import Action, decode_action

from .policy import PolicyDecision, PolicyEngine, PolicyResult
from .replay_store import InMemoryReplayStore, ReplayStore


@dataclass(frozen=True, slots=True)
class GatewayCheck:
    action: Action
    policy: PolicyResult


class Gateway:
    """Core message gateway for browser-originated AGX ACTION messages."""

    def __init__(
        self,
        policy: PolicyEngine | None = None,
        *,
        allow_actions: set[str] | None = None,
        confirm_actions: set[str] | None = None,
        deny_actions: set[str] | None = None,
        replay_store: ReplayStore | None = None,
    ) -> None:
        if policy is not None and any(
            value is not None
            for value in (
                allow_actions,
                confirm_actions,
                deny_actions,
            )
        ):
            raise ValueError(
                "Pass either policy=PolicyEngine(...) or action sets, not both."
            )

        self.policy = policy or PolicyEngine(
            allow_actions=allow_actions,
            confirm_actions=confirm_actions,
            deny_actions=deny_actions,
        )

        self._replay_store = replay_store or InMemoryReplayStore()

    def decode_and_check(
        self,
        container: str,
    ) -> tuple[Action, PolicyResult]:
        """Decode one ACTION and apply replay protection + local policy."""
        action = decode_action(container)
        policy = self.policy.check(action.action)

        if policy.decision is PolicyDecision.ALLOW:
            self._reserve_for_execution(action)

        return action, policy

    def confirm_and_reserve(self, container: str) -> Action:
        """Validate and reserve one ACTION that requires confirmation."""
        action = decode_action(container)
        policy = self.policy.check(action.action)

        if policy.decision is not PolicyDecision.CONFIRM:
            raise ValueError(
                "ACTION is not awaiting user confirmation"
            )

        self._reserve_for_execution(action)
        return action

    def _reserve_for_execution(self, action: Action) -> None:
        if not self._replay_store.reserve(
            action.session_id,
            action.message_id,
        ):
            raise ValueError(
                "ACTION message has already been processed"
            )


__all__ = [
    "Gateway",
    "GatewayCheck",
    "PolicyDecision",
    "PolicyEngine",
    "PolicyResult",
]
