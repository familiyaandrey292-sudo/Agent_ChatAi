import unittest

from gateway.gateway import Gateway, PolicyDecision
from protocol.MSGv1 import create_action, encode_action, new_session_id


class TestGateway(unittest.TestCase):

    def test_allowed_action(self):
        session_id = new_session_id()

        action = create_action(
            "open_app",
            {"name": "notepad.exe"},
            session_id=session_id,
        )

        gateway = Gateway(allow_actions={"open_app"})

        decoded, policy = gateway.decode_and_check(encode_action(action))

        self.assertEqual(decoded.action, "open_app")
        self.assertEqual(policy.decision, PolicyDecision.ALLOW)

    def test_confirmation_required(self):
        action = create_action(
            "write_file",
            {"path": "C:\\Temp\\test.txt"},
            session_id=new_session_id(),
        )

        gateway = Gateway(confirm_actions={"write_file"})

        _, policy = gateway.decode_and_check(encode_action(action))

        self.assertEqual(policy.decision, PolicyDecision.CONFIRM)

    def test_unknown_action_is_denied(self):
        action = create_action(
            "delete_file",
            {"path": "C:\\Temp\\test.txt"},
            session_id=new_session_id(),
        )

        gateway = Gateway()

        _, policy = gateway.decode_and_check(encode_action(action))

        self.assertEqual(policy.decision, PolicyDecision.DENY)

    def test_replay_is_rejected(self):
        action = create_action(
            "open_app",
            {"name": "notepad.exe"},
            session_id=new_session_id(),
        )

        container = encode_action(action)
        gateway = Gateway(allow_actions={"open_app"})

        gateway.decode_and_check(container)

        with self.assertRaises(ValueError):
            gateway.decode_and_check(container)


if __name__ == "__main__":
    unittest.main()
