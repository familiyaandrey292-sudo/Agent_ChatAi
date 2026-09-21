import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from gateway.signing import ResultSigner


class TestResultSigner(unittest.TestCase):

    def test_signature_verifies_with_public_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_path = Path(tmp) / "result_signing_key.pem"

            signer = ResultSigner.load_or_create(key_path)

            data = "AGX1:R:test-container"

            signature_b64 = signer.sign(data)

            public_key_der = __import__("base64").b64decode(
                signer.public_key_spki_b64()
            )

            public_key = serialization.load_der_public_key(
                public_key_der
            )

            self.assertIsInstance(
                public_key,
                Ed25519PublicKey,
            )

            signature = __import__("base64").b64decode(
                signature_b64
            )

            public_key.verify(
                signature,
                data.encode("utf-8"),
            )

    def test_key_survives_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_path = Path(tmp) / "result_signing_key.pem"

            signer1 = ResultSigner.load_or_create(key_path)
            signer2 = ResultSigner.load_or_create(key_path)

            data = "AGX1:R:persistent"

            self.assertEqual(
                signer1.public_key_spki_b64(),
                signer2.public_key_spki_b64(),
            )

            self.assertEqual(
                signer1.sign(data),
                signer2.sign(data),
            )

    def test_tampered_data_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_path = Path(tmp) / "result_signing_key.pem"

            signer = ResultSigner.load_or_create(key_path)

            signature = __import__("base64").b64decode(
                signer.sign("original")
            )

            public_key_der = __import__("base64").b64decode(
                signer.public_key_spki_b64()
            )

            public_key = serialization.load_der_public_key(
                public_key_der
            )

            with self.assertRaises(Exception):
                public_key.verify(
                    signature,
                    b"tampered",
                )


if __name__ == "__main__":
    unittest.main()
