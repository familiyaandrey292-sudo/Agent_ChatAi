"""Persistent Ed25519 signing for browser-verifiable AGX results."""

from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)


class ResultSigner:
    """Sign exact RESULT container bytes with a persistent Ed25519 key."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._private_key = private_key

    @classmethod
    def load_or_create(cls, path: str | Path) -> "ResultSigner":
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            private_key = serialization.load_pem_private_key(
                path.read_bytes(),
                password=None,
            )

            if not isinstance(private_key, Ed25519PrivateKey):
                raise ValueError("Signing key is not an Ed25519 private key")

            return cls(private_key)

        private_key = Ed25519PrivateKey.generate()

        path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

        return cls(private_key)

    def sign(self, data: str) -> str:
        signature = self._private_key.sign(
            data.encode("utf-8")
        )

        return base64.b64encode(signature).decode("ascii")

    def public_key_spki_b64(self) -> str:
        public_key = self._private_key.public_key()

        der = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return base64.b64encode(der).decode("ascii")


__all__ = ["ResultSigner"]
