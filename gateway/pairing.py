"""One-time pairing for the Browser Bridge authentication key."""

from __future__ import annotations

import base64
import secrets
from pathlib import Path
from threading import Lock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
)


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(
        (value + padding).encode("ascii")
    )


class PairingManager:
    """Pair exactly one Browser Bridge public key."""

    def __init__(self, public_key_path: str | Path) -> None:
        self.public_key_path = Path(public_key_path)
        self.public_key_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = Lock()

        if self.public_key_path.exists():
            self._pairing_code: str | None = None
        else:
            self._pairing_code = secrets.token_urlsafe(18)

    @property
    def paired(self) -> bool:
        return self.public_key_path.exists()

    @property
    def pairing_code(self) -> str | None:
        return self._pairing_code

    def pair(
        self,
        *,
        code: str,
        public_key_spki_b64: str,
    ) -> None:
        with self._lock:
            if self.paired:
                raise ValueError(
                    "Browser Bridge is already paired"
                )

            if (
                not self._pairing_code
                or not secrets.compare_digest(
                    code,
                    self._pairing_code,
                )
            ):
                raise ValueError(
                    "Pairing code is invalid"
                )

            try:
                der = _b64decode(public_key_spki_b64)
                public_key = (
                    serialization.load_der_public_key(der)
                )
            except Exception as exc:
                raise ValueError(
                    "Browser public key is invalid"
                ) from exc

            if not isinstance(
                public_key,
                Ed25519PublicKey,
            ):
                raise ValueError(
                    "Browser public key must be Ed25519"
                )

            pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )

            temp_path = self.public_key_path.with_suffix(
                self.public_key_path.suffix + ".tmp"
            )

            temp_path.write_bytes(pem)
            temp_path.replace(self.public_key_path)

            self._pairing_code = None


__all__ = ["PairingManager"]
