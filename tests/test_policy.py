import unittest

from gateway.policy import PolicyDecision, PolicyEngine


class TestPolicyEngine(unittest.TestCase):

    def test_allow(self):
        policy = PolicyEngine(
            allow_actions={"system.info"},
        )

        result = policy.check("system.info")

        self.assertEqual(result.decision, PolicyDecision.ALLOW)

    def test_confirm(self):
        policy = PolicyEngine(
            confirm_actions={"write_file"},
        )

        result = policy.check("write_file")

        self.assertEqual(result.decision, PolicyDecision.CONFIRM)

    def test_explicit_deny_has_priority(self):
        policy = PolicyEngine(
            allow_actions={"delete_file"},
            deny_actions={"delete_file"},
        )

        result = policy.check("delete_file")

        self.assertEqual(result.decision, PolicyDecision.DENY)

    def test_unknown_action_is_denied(self):
        policy = PolicyEngine()

        result = policy.check("unknown.action")

        self.assertEqual(result.decision, PolicyDecision.DENY)


if __name__ == "__main__":
    unittest.main()
