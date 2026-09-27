import time
import unittest

from protocol.command import (
    CommandFormatError,
    CommandValidationError,
    create_command,
    decode_command,
    encode_command,
)


class TestCommand(unittest.TestCase):
    def test_roundtrip(self):
        command = create_command(
            "system.info",
            {"message": "hello"},
        )

        container = encode_command(command)
        decoded = decode_command(container)

        self.assertEqual(decoded, command)
        self.assertTrue(command.session_id)
        self.assertTrue(command.message_id)
        self.assertTrue(container.startswith("AGX1:C:"))

    def test_roundtrip_preserves_unicode_and_nested_args(self):
        command = create_command(
            "files.list",
            {
                "path": "C:\\Тест\\папка",
                "options": {
                    "recursive": False,
                    "labels": ["файл", "тест"],
                },
            },
        )

        decoded = decode_command(
            encode_command(command)
        )

        self.assertEqual(decoded, command)

    def test_tamper_is_detected(self):
        container = encode_command(
            create_command(
                "system.info",
                {},
            )
        )

        payload, digest = container.rsplit(":", 1)
        tampered = (
            payload[:-1]
            + ("A" if payload[-1] != "A" else "B")
            + ":"
            + digest
        )

        with self.assertRaises(CommandFormatError):
            decode_command(tampered)

    def test_invalid_container_is_rejected(self):
        with self.assertRaises(CommandFormatError):
            decode_command("AGX1:C:invalid")

    def test_wrong_kind_is_rejected(self):
        with self.assertRaises(CommandFormatError):
            decode_command(
                "AGX1:A:invalid:" + ("0" * 64)
            )

    def test_invalid_action_is_rejected(self):
        with self.assertRaises(CommandValidationError):
            create_command(
                "system info",
                {},
            )

    def test_missing_action_is_rejected(self):
        container = (
            "AGX1:C:"
            "eyJhcmdzIjp7fX0"
            ":"
            "0000000000000000000000000000000000000000000000000000000000000000"
        )

        with self.assertRaises(CommandFormatError):
            decode_command(container)

    def test_missing_session_id_is_rejected(self):
        command = create_command(
            "system.info",
            {},
        )
        payload, digest = encode_command(command).rsplit(":", 1)
        import base64
        raw = base64.urlsafe_b64decode(
            payload.split(":", 2)[-1] + "=="
        ).decode("utf-8")
        data = __import__("json").loads(raw)
        data.pop("session_id")
        rebuilt = base64.urlsafe_b64encode(
            __import__("json").dumps(
                data,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).decode("ascii").rstrip("=")
        import hashlib
        auth = hashlib.sha256(
            ("C:" + rebuilt).encode("ascii")
        ).hexdigest()
        with self.assertRaises(CommandValidationError):
            decode_command("AGX1:C:" + rebuilt + ":" + auth)

    def test_message_id_is_preserved(self):
        command = create_command(
            "system.info",
            {},
            session_id="AAAAAAAAAAAAAAAAAAAAAA",
            message_id="0123456789abcdef0123456789abcdef",
        )
        decoded = decode_command(encode_command(command))
        self.assertEqual(decoded.message_id, command.message_id)
        self.assertEqual(decoded.session_id, command.session_id)

    def test_timestamp_and_ttl_are_preserved(self):
        command = create_command(
            "system.info",
            {},
            session_id="AAAAAAAAAAAAAAAAAAAAAA",
            message_id="0123456789abcdef0123456789abcdef",
            timestamp=time.time(),
            ttl=42,
        )
        decoded = decode_command(encode_command(command))
        self.assertEqual(decoded.timestamp, command.timestamp)
        self.assertEqual(decoded.ttl, 42.0)

    def test_ttl_over_maximum_is_rejected(self):
        from protocol.command import CommandTTLExceeded

        with self.assertRaises(CommandTTLExceeded) as ctx:
            create_command("system.info", {}, ttl=301)

        self.assertEqual(ctx.exception.requested_ttl, 301)
        self.assertEqual(ctx.exception.max_ttl, 300)

    def test_expired_command_is_rejected(self):
        with self.assertRaises(CommandValidationError) as ctx:
            create_command(
                "system.info",
                {},
                timestamp=time.time() - 10,
                ttl=1,
            )
        self.assertEqual(str(ctx.exception), "COMMAND_EXPIRED")

    def test_future_command_is_rejected(self):
        with self.assertRaises(CommandValidationError) as ctx:
            create_command(
                "system.info",
                {},
                timestamp=time.time() + 31,
                ttl=60,
            )
        self.assertEqual(
            str(ctx.exception),
            "COMMAND_TIMESTAMP_IN_FUTURE",
        )

    def test_args_must_be_object(self):
        command = create_command(
            "system.info",
            {},
        )
        container = encode_command(command)

        self.assertEqual(
            decode_command(container).args,
            {},
        )


if __name__ == "__main__":
    unittest.main()
