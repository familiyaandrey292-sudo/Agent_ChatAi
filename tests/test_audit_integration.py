import json
import tempfile
import unittest
from pathlib import Path

from gateway.audit import AuditLogger
from gateway.executor import GatewayExecutor
from gateway.gateway import Gateway
from pc_agent.agent import PCAgent
from protocol.MSGv1 import (
    create_action,
    decode_result,
    encode_action,
    new_hmac_secret,
)


class TestAuditIntegration(unittest.TestCase):

    def test_allowed_action_and_result_are_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            audit = AuditLogger(path)

            gateway = Gateway(
                allow_actions={"system.info"},
            )

            secret = new_hmac_secret()

            executor = GatewayExecutor(
                gateway,
                PCAgent(),
                hmac_secret=secret,
                audit=audit,
            )

            action = create_action(
                "system.info",
                {},
                session_id="audit-test-session",
            )

            result_container = executor.process(
                encode_action(action)
            )

            result = decode_result(
                result_container,
                secret,
            )

            self.assertEqual(
                result.status,
                "ok",
            )

            entries = [
                json.loads(line)
                for line in path.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]

            events = [
                entry["event"]
                for entry in entries
            ]

            self.assertIn(
                "action_received",
                events,
            )

            self.assertIn(
                "action_result",
                events,
            )

            for entry in entries:
                self.assertNotIn(
                    "args",
                    entry,
                )

    def test_confirmation_lifecycle_is_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            audit = AuditLogger(path)

            gateway = Gateway(
                confirm_actions={"files.list"},
            )

            secret = new_hmac_secret()

            executor = GatewayExecutor(
                gateway,
                PCAgent(),
                hmac_secret=secret,
                audit=audit,
            )

            action = create_action(
                "files.list",
                {"path": "."},
                session_id="audit-test-session",
            )

            container = encode_action(action)

            pending = executor.process(
                container
            )

            self.assertEqual(
                decode_result(
                    pending,
                    secret,
                ).status,
                "confirmation_required",
            )

            confirmed = executor.process_confirmed(
                container
            )

            self.assertEqual(
                decode_result(
                    confirmed,
                    secret,
                ).status,
                "ok",
            )

            entries = [
                json.loads(line)
                for line in path.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]

            events = [
                entry["event"]
                for entry in entries
            ]

            self.assertIn(
                "action_received",
                events,
            )

            self.assertIn(
                "confirmation_required",
                events,
            )

            self.assertIn(
                "confirmation_accepted",
                events,
            )

            self.assertIn(
                "action_result",
                events,
            )


if __name__ == "__main__":
    unittest.main()
