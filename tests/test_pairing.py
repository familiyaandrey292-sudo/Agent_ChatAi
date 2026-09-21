import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from gateway.pairing import PairingManager


class TestPairingManager(unittest.TestCase):

    def test_pairing_with_valid_code_and_key(self):
        private_key = Ed25519PrivateKey.generate()

        public_der = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        public_b64 = base64.urlsafe_b64encode(
            public_der
        ).decode("ascii").rstrip("=")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "browser_public.pem"

            manager = PairingManager(path)

            self.assertFalse(manager.paired)
            self.assertTrue(manager.pairing_code)

            manager.pair(
                code=manager.pairing_code,
                public_key_spki_b64=public_b64,
            )

            self.assertTrue(manager.paired)
            self.assertIsNone(manager.pairing_code)
            self.assertTrue(path.exists())

    def test_wrong_code_is_rejected(self):
        private_key = Ed25519PrivateKey.generate()

        public_der = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        public_b64 = base64.urlsafe_b64encode(
            public_der
        ).decode("ascii").rstrip("=")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "browser_public.pem"

            manager = PairingManager(path)

            with self.assertRaises(ValueError):
                manager.pair(
                    code="wrong-code",
                    public_key_spki_b64=public_b64,
                )

            self.assertFalse(manager.paired)

    def test_pairing_is_one_time(self):
        private_key = Ed25519PrivateKey.generate()

        public_der = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        public_b64 = base64.urlsafe_b64encode(
            public_der
        ).decode("ascii").rstrip("=")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "browser_public.pem"

            manager = PairingManager(path)
            code = manager.pairing_code

            manager.pair(
                code=code,
                public_key_spki_b64=public_b64,
            )

            with self.assertRaises(ValueError):
                manager.pair(
                    code=code or "",
                    public_key_spki_b64=public_b64,
                )


if __name__ == "__main__":
    unittest.main()
