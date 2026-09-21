import tempfile
import unittest
from pathlib import Path

from gateway.gateway import Gateway
from gateway.replay_store import SQLiteReplayStore
from protocol.MSGv1 import (
    create_action,
    encode_action,
    new_session_id,
)


class TestReplayPersistence(unittest.TestCase):

    def test_replay_survives_gateway_restart(self):
        action = create_action(
            "open_app",
            {"name": "notepad.exe"},
            session_id=new_session_id(),
        )

        container = encode_action(action)

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "replay.sqlite3"

            first_gateway = Gateway(
                allow_actions={"open_app"},
                replay_store=SQLiteReplayStore(db),
            )

            first_gateway.decode_and_check(container)

            second_gateway = Gateway(
                allow_actions={"open_app"},
                replay_store=SQLiteReplayStore(db),
            )

            with self.assertRaises(ValueError):
                second_gateway.decode_and_check(container)


if __name__ == "__main__":
    unittest.main()
