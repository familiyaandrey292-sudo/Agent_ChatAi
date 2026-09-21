import json
import tempfile
import threading
import unittest
from pathlib import Path

from gateway.audit import AuditLogger


class TestAuditLogger(unittest.TestCase):

    def test_record_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            logger = AuditLogger(path)

            logger.record(
                "action_received",
                action="system.info",
                command_id="cmd-1",
                session_id="session-1",
                message_id="msg-1",
                decision="allow",
            )

            lines = path.read_text(
                encoding="utf-8"
            ).splitlines()

            self.assertEqual(len(lines), 1)

            entry = json.loads(lines[0])

            self.assertEqual(
                entry["event"],
                "action_received",
            )
            self.assertEqual(
                entry["action"],
                "system.info",
            )
            self.assertEqual(
                entry["decision"],
                "allow",
            )
            self.assertIn(
                "timestamp",
                entry,
            )

    def test_sensitive_action_arguments_are_not_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            logger = AuditLogger(path)

            logger.record(
                "action_received",
                action="files.list",
                reason="path=C:\\secret",
            )

            text = path.read_text(
                encoding="utf-8"
            )

            self.assertNotIn(
                "args",
                text,
            )



    def test_rotates_when_size_limit_is_exceeded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            logger = AuditLogger(
                path,
                max_bytes=180,
                backup_count=3,
            )

            for index in range(6):
                logger.record(
                    "rotation_test",
                    command_id=f"cmd-{index}",
                    reason="x" * 40,
                )

            backup = Path(
                str(path) + ".1"
            )

            self.assertTrue(
                backup.exists()
            )

            current_lines = [
                json.loads(line)
                for line in path.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]

            backup_lines = [
                json.loads(line)
                for line in backup.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]

            self.assertGreater(
                len(current_lines),
                0,
            )

            self.assertGreater(
                len(backup_lines),
                0,
            )

            self.assertEqual(
                current_lines[-1]["event"],
                "rotation_test",
            )

            self.assertEqual(
                backup_lines[-1]["event"],
                "rotation_test",
            )

    def test_rotation_keeps_jsonl_chain_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            logger = AuditLogger(
                path,
                max_bytes=160,
                backup_count=3,
            )

            for index in range(20):
                logger.record(
                    "rotation_test",
                    command_id=f"cmd-{index}",
                )

            files = [
                path,
                Path(str(path) + ".1"),
                Path(str(path) + ".2"),
                Path(str(path) + ".3"),
            ]

            existing = [
                item
                for item in files
                if item.exists()
            ]

            self.assertGreaterEqual(
                len(existing),
                2,
            )

            for item in existing:
                for line in item.read_text(
                    encoding="utf-8"
                ).splitlines():
                    json.loads(line)

    def test_invalid_rotation_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"

            with self.assertRaises(
                ValueError
            ):
                AuditLogger(
                    path,
                    max_bytes=0,
                )

            with self.assertRaises(
                ValueError
            ):
                AuditLogger(
                    path,
                    backup_count=-1,
                )

    def test_concurrent_writes_remain_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            logger = AuditLogger(path)

            def writer(index):
                for item in range(10):
                    logger.record(
                        "test",
                        command_id=f"{index}-{item}",
                    )

            threads = [
                threading.Thread(
                    target=writer,
                    args=(index,),
                )
                for index in range(4)
            ]

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            lines = path.read_text(
                encoding="utf-8"
            ).splitlines()

            self.assertEqual(
                len(lines),
                40,
            )

            for line in lines:
                json.loads(line)


if __name__ == "__main__":
    unittest.main()
