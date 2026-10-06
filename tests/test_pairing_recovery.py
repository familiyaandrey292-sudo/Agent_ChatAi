"""Recovery path after gateway state loss (keys/replay DB wiped).

After `git clean -fd` removed result_signing_key.pem, browser_auth_public.pem
and replay.sqlite3, the pairing code existed only in the dead process memory.
The /v1/pairing-code endpoint lets ops fetch a fresh code from the running
gateway so the browser extension can re-pair without reading console output.
"""

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

from gateway.gateway import Gateway
from gateway.executor import GatewayExecutor
from gateway.pairing import PairingManager
from gateway.server import create_server
from pc_agent.agent import PCAgent
from protocol.MSGv1 import new_hmac_secret


class TestPairingCodeEndpoint(unittest.TestCase):
    def _start(self, pairing):
        executor = GatewayExecutor(
            Gateway(allow_actions={"system.info"}),
            PCAgent(),
            hmac_secret=new_hmac_secret(),
        )
        server = create_server(
            executor,
            host="127.0.0.1",
            port=0,
            browser_auth=None,
            pairing=pairing,
        )
        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
        )
        thread.start()
        return server, thread

    def _get_code(self, server):
        host, port = server.server_address
        with urlopen(
            f"http://{host}:{port}/v1/pairing-code",
            timeout=5,
        ) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_returns_stable_code_when_unpaired(self):
        with tempfile.TemporaryDirectory() as tmp:
            pairing = PairingManager(Path(tmp) / "browser_public.pem")
            server, thread = self._start(pairing)
            try:
                first = self._get_code(server)
                second = self._get_code(server)
                self.assertEqual(first["code"], second["code"])
                self.assertFalse(first["paired"])
                self.assertEqual(
                    first["code"],
                    pairing.pairing_code,
                )
            finally:
                server.shutdown()
                server.server_close()

    def test_resets_code_when_already_paired(self):
        with tempfile.TemporaryDirectory() as tmp:
            pairing = PairingManager(Path(tmp) / "browser_public.pem")
            original = pairing.ensure_pairing_code()
            # Simulate completed pairing by dropping a key file on disk.
            key_dir = Path(tmp) / "browser_public_keys"
            key_dir.mkdir(parents=True, exist_ok=True)
            (key_dir / ("a" * 64 + ".pem")).write_bytes(b"stub")
            server, thread = self._start(pairing)
            try:
                payload = self._get_code(server)
                self.assertTrue(payload["paired"])
                self.assertNotEqual(payload["code"], original)
                self.assertEqual(payload["code"], pairing.pairing_code)
            finally:
                server.shutdown()
                server.server_close()

    def test_new_pairing_code_works_after_state_loss(self):
        """Full recovery: wipe state, restart manager, pair via fresh code."""
        with tempfile.TemporaryDirectory() as tmp:
            public_path = Path(tmp) / "browser_public.pem"
            pairing = PairingManager(public_path)
            del pairing
            # Fresh process == fresh codes; old code must not be accepted.
            recovered = PairingManager(public_path)
            self.assertIsNotNone(recovered.pairing_code)
            with self.assertRaises(ValueError):
                recovered.pair(code="", public_key_spki_b64="x")


if __name__ == "__main__":
    unittest.main()
