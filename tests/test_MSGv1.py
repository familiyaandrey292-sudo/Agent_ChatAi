import unittest

from protocol.MSGv1 import (
    AGXAuthenticationError,
    AGXFormatError,
    AGXIntegrityError,
    create_action,
    create_result,
    decode_action,
    decode_result,
    encode_action,
    encode_result,
    extract_containers,
    new_hmac_secret,
    new_session_id,
)


class TestMSGv1(unittest.TestCase):

    def test_action_roundtrip(self):
        action = create_action(
            "open_app",
            {"name": "notepad.exe", "text": "Привет, мир! 😃"},
            session_id=new_session_id(),
            sequence=1,
        )

        encoded = encode_action(action)
        decoded = decode_action(encoded)

        self.assertEqual(decoded.action, action.action)
        self.assertEqual(decoded.args, action.args)
        self.assertEqual(decoded.command_id, action.command_id)
        self.assertEqual(decoded.session_id, action.session_id)

    def test_action_survives_chat_text(self):
        action = create_action(
            "open_app",
            {"name": "notepad.exe"},
            session_id=new_session_id(),
        )
        encoded = encode_action(action)

        text = f"""Обычный текст ИИ.

**Markdown**, кавычки " ' и Unicode: ё, 中文, 😃

{encoded}

Ещё обычный текст после команды.
"""

        found = extract_containers(text, kind="A")

        self.assertEqual(found, [encoded])
        self.assertEqual(decode_action(found[0]).action, "open_app")

    def test_action_tamper_is_detected(self):
        action = create_action(
            "open_app",
            {"name": "notepad.exe"},
            session_id=new_session_id(),
        )
        encoded = encode_action(action)

        parts = encoded.split(":")
        parts[2] = parts[2][:-1] + ("A" if parts[2][-1] != "A" else "B")
        tampered = ":".join(parts)

        with self.assertRaises((AGXIntegrityError, AGXFormatError)):
            decode_action(tampered)

    def test_result_roundtrip_with_hmac(self):
        secret = new_hmac_secret()

        result = create_result(
            command_id="command-123",
            session_id="session-456",
            status="ok",
            result={"message": "Готово", "pid": 12345},
            message="Команда успешно выполнена",
            sequence=2,
        )

        encoded = encode_result(result, secret)
        decoded = decode_result(encoded, secret)

        self.assertEqual(decoded.command_id, result.command_id)
        self.assertEqual(decoded.status, "ok")
        self.assertEqual(decoded.result, result.result)

    def test_result_wrong_secret_is_rejected(self):
        secret = new_hmac_secret()
        wrong_secret = new_hmac_secret()

        result = create_result(
            command_id="command-123",
            session_id="session-456",
            status="ok",
            result={"ok": True},
        )

        encoded = encode_result(result, secret)

        with self.assertRaises(AGXAuthenticationError):
            decode_result(encoded, wrong_secret)

    def test_action_cannot_be_decoded_as_result(self):
        secret = new_hmac_secret()

        action = create_action(
            "open_app",
            {"name": "notepad.exe"},
            session_id=new_session_id(),
        )
        encoded = encode_action(action)

        with self.assertRaises(AGXFormatError):
            decode_result(encoded, secret)


if __name__ == "__main__":
    unittest.main()
