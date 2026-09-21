import unittest

from gateway.executor import GatewayExecutor
from gateway.gateway import Gateway
from pc_agent.agent import PCAgent
from protocol.MSGv1 import (
    create_action,
    decode_result,
    encode_action,
    new_hmac_secret,
    new_session_id,
)


class TestGatewayExecutorPolicy(unittest.TestCase):

    def test_denied_action_returns_denied_result(self):
        secret = new_hmac_secret()

        action = create_action(
            "delete_file",
            {"path": "C:\\Temp\\test.txt"},
            session_id=new_session_id(),
        )

        gateway = Gateway()

        executor = GatewayExecutor(
            gateway,
            PCAgent(),
            hmac_secret=secret,
        )

        result = decode_result(
            executor.process(encode_action(action)),
            secret,
        )

        self.assertEqual(result.status, "denied")

    def test_confirmation_action_does_not_execute(self):
        secret = new_hmac_secret()

        action = create_action(
            "write_file",
            {"path": "C:\\Temp\\test.txt"},
            session_id=new_session_id(),
        )

        gateway = Gateway(
            confirm_actions={"write_file"},
        )

        executor = GatewayExecutor(
            gateway,
            PCAgent(),
            hmac_secret=secret,
        )

        result = decode_result(
            executor.process(encode_action(action)),
            secret,
        )

        self.assertEqual(result.status, "confirmation_required")


if __name__ == "__main__":
    unittest.main()
