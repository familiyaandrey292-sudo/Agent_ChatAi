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
