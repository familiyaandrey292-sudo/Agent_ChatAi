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


class TestGatewayExecutor(unittest.TestCase):

    def test_allowed_action_returns_authenticated_result(self):
        secret = new_hmac_secret()

        action = create_action(
            "system.info",
            {},
            session_id=new_session_id(),
        )

        gateway = Gateway(
            allow_actions={"system.info"},
        )

        executor = GatewayExecutor(
            gateway,
            PCAgent(),
            hmac_secret=secret,
        )

        result_container = executor.process(
            encode_action(action)
        )

        result = decode_result(
            result_container,
            secret,
        )

        self.assertEqual(result.command_id, action.command_id)
        self.assertEqual(result.session_id, action.session_id)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.result["system"], "Windows")


if __name__ == "__main__":
    unittest.main()
