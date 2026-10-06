"""Multi-browser one-time pairing for Browser Bridge keys."""

from __future__ import annotations

import base64
import hashlib
import secrets
from pathlib import Path
from threading import Lock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


class PairingManager:
    def __init__(self, public_key_path: str | Path) -> None:
        self.public_key_path = Path(public_key_path)
        self.public_key_path.parent.mkdir(parents=True, exist_ok=True)

        self._keys_dir = self.public_key_path.parent / (
            self.public_key_path.stem + "_keys"
        )
        self._keys_dir.mkdir(parents=True, exist_ok=True)

        self._lock = Lock()
        self._pairing_code: str | None = None

        if self.public_key_path.exists():
            self._migrate_primary_key()

        if not self.paired:
            self._pairing_code = secrets.token_urlsafe(18)

    def _migrate_primary_key(self) -> None:
        data = self.public_key_path.read_bytes()
        name = hashlib.sha256(data).hexdigest() + ".pem"
        target = self._keys_dir / name
        if not target.exists():
            target.write_bytes(data)

    @property
    def public_key_paths(self) -> tuple[Path, ...]:
        paths: list[Path] = []
        if self.public_key_path.exists():
            paths.append(self.public_key_path)
        for path in sorted(self._keys_dir.glob("*.pem")):
            if path not in paths:
                paths.append(path)
        return tuple(paths)

    @property
    def paired(self) -> bool:
        return bool(self.public_key_paths)

    @property
    def pairing_code(self) -> str | None:
        return self._pairing_code

    def ensure_pairing_code(self) -> str:
        with self._lock:
            if not self._pairing_code:
                self._pairing_code = secrets.token_urlsafe(18)
            return self._pairing_code

    def reset_pairing_code(self) -> str:
        """Force a fresh pairing code (used to recover after state loss)."""
        with self._lock:
            self._pairing_code = secrets.token_urlsafe(18)
            return self._pairing_code

    def pair(self, *, code: str, public_key_spki_b64: str) -> None:
        with self._lock:
            if (
                not self._pairing_code
                or not secrets.compare_digest(code, self._pairing_code)
            ):
                raise ValueError("Pairing code is invalid")

            try:
                der = _b64decode(public_key_spki_b64)
                public_key = serialization.load_der_public_key(der)
            except Exception as exc:
                raise ValueError("Browser public key is invalid") from exc

            if not isinstance(public_key, Ed25519PublicKey):
                raise ValueError("Browser public key must be Ed25519")

            pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )

            fingerprint = hashlib.sha256(der).hexdigest()
            target = self._keys_dir / f"{fingerprint}.pem"

            if target.exists():
                raise ValueError("Browser key is already paired")

            target.write_bytes(pem)

            if not self.public_key_path.exists():
                self.public_key_path.write_bytes(pem)

            self._pairing_code = None


__all__ = ["PairingManager"]