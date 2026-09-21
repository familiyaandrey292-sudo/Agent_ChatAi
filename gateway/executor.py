"""Gateway execution service.

Connects AGX ACTION validation, local policy, PC Agent execution,
and authenticated AGX RESULT creation.
"""

from __future__ import annotations

from typing import Any

from pc_agent.agent import PCAgent, AgentError
from protocol.MSGv1 import (
    Action,
    create_result,
    encode_result,
)

from .audit import AuditLogger
from .gateway import Gateway, PolicyDecision


class GatewayExecutor:
    """Execute policy-approved ACTION messages locally."""

    def __init__(
        self,
        gateway: Gateway,
        agent: PCAgent | None = None,
        *,
        hmac_secret: bytes,
        audit: AuditLogger | None = None,
    ) -> None:
        self.gateway = gateway
        self.agent = agent or PCAgent()
        self.hmac_secret = hmac_secret
        self.audit = audit

    def process(self, container: str) -> str:
        """Process one ACTION and return an authenticated RESULT container."""
        action, policy = self.gateway.decode_and_check(container)

        self._audit(
            "action_received",
            action,
            decision=policy.decision.value,
            reason=policy.reason,
        )

        if policy.decision is PolicyDecision.DENY:
            result_container = self._result(
                action,
                status="denied",
                result={},
                message=policy.reason,
            )

            self._audit(
                "action_denied",
                action,
                status="denied",
                reason=policy.reason,
            )

            return result_container

        if policy.decision is PolicyDecision.CONFIRM:
            result_container = self._result(
                action,
                status="confirmation_required",
                result={},
                message=policy.reason,
            )

            self._audit(
                "confirmation_required",
                action,
                status="confirmation_required",
                reason=policy.reason,
            )

            return result_container

        return self._execute(action)

    def process_confirmed(self, container: str) -> str:
        """Execute one ACTION after explicit user confirmation."""
        action = self.gateway.confirm_and_reserve(container)

        self._audit(
            "confirmation_accepted",
            action,
        )

        return self._execute(action)

    def _execute(self, action: Action) -> str:
        try:
            execution = self.agent.execute(
                action.action,
                action.args,
            )

            status = "ok" if execution.success else "error"

            result_container = self._result(
                action,
                status=status,
                result=execution.result,
                message=execution.message,
            )

            self._audit(
                "action_result",
                action,
                status=status,
            )

            return result_container

        except AgentError as exc:
            result_container = self._result(
                action,
                status="error",
                result={},
                message=str(exc),
            )

            self._audit(
                "action_result",
                action,
                status="error",
            )

            return result_container

        except Exception as exc:
            result_container = self._result(
                action,
                status="error",
                result={},
                message=f"Unexpected executor error: {exc}",
            )

            self._audit(
                "action_result",
                action,
                status="error",
            )

            return result_container

    def _audit(
        self,
        event: str,
        action: Action,
        *,
        status: str | None = None,
        decision: str | None = None,
        reason: str | None = None,
    ) -> None:
        if self.audit is None:
            return

        self.audit.record(
            event,
            action=action.action,
            command_id=action.command_id,
            session_id=action.session_id,
            message_id=action.message_id,
            status=status,
            decision=decision,
            reason=reason,
        )

    def _result(
        self,
        action: Action,
        *,
        status: str,
        result: dict[str, Any],
        message: str,
    ) -> str:
        result_message = create_result(
            command_id=action.command_id,
            session_id=action.session_id,
            status=status,
            result=result,
            message=message,
            sequence=action.sequence,
        )

        return encode_result(
            result_message,
            self.hmac_secret,
        )
