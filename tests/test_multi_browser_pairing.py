import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from gateway.browser_auth import BrowserAuth, build_auth_message
from gateway.pairing import PairingManager


def public_b64(private_key):
    der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return base64.urlsafe_b64encode(der).decode("ascii").rstrip("=")


class TestMultiBrowserPairing(unittest.TestCase):
    def test_multiple_browser_keys_are_accepted(self):
        key1 = Ed25519PrivateKey.generate()
        key2 = Ed25519PrivateKey.generate()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p1 = root / "key1.pem"
            p2 = root / "key2.pem"

            p1.write_bytes(
                key1.public_key().public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )
            p2.write_bytes(
                key2.public_key().public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )

            auth = BrowserAuth.load_many([p1, p2])
            body = b"{}"
            challenge = auth.create_challenge()
            message = build_auth_message(
                method="POST",
                path="/v1/action",
                challenge=challenge,
                body=body,
            )

            signature = base64.urlsafe_b64encode(
                key2.sign(message)
            ).decode("ascii").rstrip("=")

            auth.verify(
                method="POST",
                path="/v1/action",
                body=body,
                challenge=challenge,
                signature=signature,
            )

    def test_pairing_can_add_second_browser(self):
        key1 = Ed25519PrivateKey.generate()
        key2 = Ed25519PrivateKey.generate()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "browser_public.pem"
            manager = PairingManager(path)

            code1 = manager.pairing_code
            manager.pair(
                code=code1,
                public_key_spki_b64=public_b64(key1),
            )

            manager.ensure_pairing_code()
            code2 = manager.pairing_code
            self.assertNotEqual(code1, code2)

            manager.pair(
                code=code2,
                public_key_spki_b64=public_b64(key2),
            )

            self.assertGreaterEqual(
                len(manager.public_key_paths),
                2,
            )


if __name__ == "__main__":
    unittest.main()
