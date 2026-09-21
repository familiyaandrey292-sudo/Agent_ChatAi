import base64
import hashlib
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from gateway.browser_auth import (
    BrowserAuth,
    build_auth_message,
)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(
        data
    ).decode("ascii").rstrip("=")


class TestBrowserAuth(unittest.TestCase):

    def _make_auth(self):
        private_key = Ed25519PrivateKey.generate()

        public_key = private_key.public_key()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "browser_public.pem"

            path.write_bytes(
                public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )

            auth = BrowserAuth.load(path)

        return auth, private_key

    def test_valid_signed_request(self):
        auth, private_key = self._make_auth()

        body = b'{"container":"AGX1:A:test"}'
        challenge = auth.create_challenge()

        message = build_auth_message(
            method="POST",
            path="/v1/action",
            challenge=challenge,
            body=body,
        )

        signature = b64url(
            private_key.sign(message)
        )

        auth.verify(
            method="POST",
            path="/v1/action",
            body=body,
            challenge=challenge,
            signature=signature,
        )

    def test_challenge_is_one_time(self):
        auth, private_key = self._make_auth()

        body = b"{}"
        challenge = auth.create_challenge()

        message = build_auth_message(
            method="POST",
            path="/v1/action",
            challenge=challenge,
            body=body,
        )

        signature = b64url(
            private_key.sign(message)
        )

        auth.verify(
            method="POST",
            path="/v1/action",
            body=body,
            challenge=challenge,
            signature=signature,
        )

        with self.assertRaises(ValueError):
            auth.verify(
                method="POST",
                path="/v1/action",
                body=body,
                challenge=challenge,
                signature=signature,
            )

    def test_invalid_signature_does_not_consume_challenge(self):
        auth, private_key = self._make_auth()

        body = b"{}"
        challenge = auth.create_challenge()

        valid_message = build_auth_message(
            method="POST",
            path="/v1/action",
            challenge=challenge,
            body=body,
        )

        valid_signature = b64url(
            private_key.sign(valid_message)
        )

        with self.assertRaises(ValueError):
            auth.verify(
                method="POST",
                path="/v1/action",
                body=body,
                challenge=challenge,
                signature=b64url(b"invalid"),
            )

        auth.verify(
            method="POST",
            path="/v1/action",
            body=body,
            challenge=challenge,
            signature=valid_signature,
        )

    def test_tampered_body_is_rejected(self):
        auth, private_key = self._make_auth()

        body = b'{"container":"original"}'
        tampered = b'{"container":"tampered"}'
        challenge = auth.create_challenge()

        message = build_auth_message(
            method="POST",
            path="/v1/action",
            challenge=challenge,
            body=body,
        )

        signature = b64url(
            private_key.sign(message)
        )

        with self.assertRaises(ValueError):
            auth.verify(
                method="POST",
                path="/v1/action",
                body=tampered,
                challenge=challenge,
                signature=signature,
            )

    def test_wrong_path_is_rejected(self):
        auth, private_key = self._make_auth()

        body = b"{}"
        challenge = auth.create_challenge()

        message = build_auth_message(
            method="POST",
            path="/v1/action",
            challenge=challenge,
            body=body,
        )

        signature = b64url(
            private_key.sign(message)
        )

        with self.assertRaises(ValueError):
            auth.verify(
                method="POST",
                path="/v1/confirm",
                body=body,
                challenge=challenge,
                signature=signature,
            )


if __name__ == "__main__":
    unittest.main()
