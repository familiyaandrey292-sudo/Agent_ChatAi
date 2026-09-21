import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from protocol.MSGv1 import (
    AGXValidationError,
    create_action,
    decode_action,
    encode_action,
    new_session_id,
)


class TestMSGv1Timestamp(unittest.TestCase):

    def test_fresh_action_timestamp_is_accepted(self):
        action = create_action(
            "system.info",
            {},
            session_id=new_session_id(),
        )

        decoded = decode_action(encode_action(action))

        self.assertEqual(decoded.command_id, action.command_id)

    def test_old_action_timestamp_is_rejected(self):
        action = create_action(
            "system.info",
            {},
            session_id=new_session_id(),
        )

        old_timestamp = (
            datetime.now(timezone.utc)
            - timedelta(seconds=301)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        old_action = replace(
            action,
            timestamp=old_timestamp,
        )

        with self.assertRaises(AGXValidationError):
            decode_action(encode_action(old_action))

    def test_future_action_timestamp_is_rejected(self):
        action = create_action(
            "system.info",
            {},
            session_id=new_session_id(),
        )

        future_timestamp = (
            datetime.now(timezone.utc)
            + timedelta(seconds=31)
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        future_action = replace(
            action,
            timestamp=future_timestamp,
        )

        with self.assertRaises(AGXValidationError):
            decode_action(encode_action(future_action))


if __name__ == "__main__":
    unittest.main()
