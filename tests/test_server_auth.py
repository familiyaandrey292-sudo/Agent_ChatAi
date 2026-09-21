import base64
from contextlib import contextmanager
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from gateway.browser_auth import (
    BrowserAuth,
    build_auth_message,
)
from gateway.gateway import Gateway
from gateway.executor import GatewayExecutor
from gateway.pairing import PairingManager
from gateway.server import create_server
from pc_agent.agent import PCAgent
from protocol.MSGv1 import (
    create_action,
    encode_action,
    new_hmac_secret,
    new_session_id,
)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(
        data
    ).decode("ascii").rstrip("=")


class TestGatewayHTTPAuth(unittest.TestCase):

    @contextmanager
    def _start_server(self):
        private_key = Ed25519PrivateKey.generate()

        public_der = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        public_b64 = b64url(public_der)

        gateway = Gateway(
            allow_actions={"system.info"},
        )

        executor = GatewayExecutor(
            gateway,
            PCAgent(),
            hmac_secret=new_hmac_secret(),
        )

        with tempfile.TemporaryDirectory() as tmp:
            public_path = (
                Path(tmp) / "browser_public.pem"
            )

            pairing = PairingManager(public_path)

            pairing.pair(
                code=pairing.pairing_code,
                public_key_spki_b64=public_b64,
            )

            browser_auth = BrowserAuth.load(
                public_path
            )

            server = create_server(
                executor,
                host="127.0.0.1",
                port=0,
                browser_auth=browser_auth,
                pairing=pairing,
            )

            thread = threading.Thread(
                target=server.serve_forever,
                daemon=True,
            )
            thread.start()

            yield (
                server,
                private_key,
            )

            server.shutdown()
            server.server_close()

    def test_signed_action_is_accepted(self):
        with self._start_server() as (
            server,
            private_key,
        ):
            host, port = server.server_address

            action = create_action(
                "system.info",
                {},
                session_id=new_session_id(),
            )

            body = json.dumps(
                {
                    "container": encode_action(action),
                }
            ).encode("utf-8")

            challenge_request = Request(
                f"http://{host}:{port}/v1/auth/challenge",
                method="GET",
            )

            with urlopen(
                challenge_request,
                timeout=5,
            ) as response:
                challenge_payload = json.loads(
                    response.read().decode("utf-8")
                )

            challenge = challenge_payload["challenge"]

            message = build_auth_message(
                method="POST",
                path="/v1/action",
                challenge=challenge,
                body=body,
            )

            signature = b64url(
                private_key.sign(message)
            )

            request = Request(
                f"http://{host}:{port}/v1/action",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-AGX-Challenge": challenge,
                    "X-AGX-Signature": signature,
                },
                method="POST",
            )

            with urlopen(
                request,
                timeout=5,
            ) as response:
                payload = json.loads(
                    response.read().decode("utf-8")
                )

            self.assertEqual(
                payload["status"],
                "ok",
            )

    def test_unpaired_like_request_is_rejected(self):
        private_key = Ed25519PrivateKey.generate()

        gateway = Gateway(
            allow_actions={"system.info"},
        )

        executor = GatewayExecutor(
            gateway,
            PCAgent(),
            hmac_secret=new_hmac_secret(),
        )

        with tempfile.TemporaryDirectory() as tmp:
            pairing = PairingManager(
                Path(tmp) / "browser_public.pem"
            )

            server = create_server(
                executor,
                host="127.0.0.1",
                port=0,
                pairing=pairing,
            )

            thread = threading.Thread(
                target=server.serve_forever,
                daemon=True,
            )
            thread.start()

            try:
                host, port = server.server_address

                action = create_action(
                    "system.info",
                    {},
                    session_id=new_session_id(),
                )

                body = json.dumps(
                    {
                        "container":
                            encode_action(action),
                    }
                ).encode("utf-8")

                with self.assertRaises(HTTPError) as error:
                    urlopen(
                        Request(
                            f"http://{host}:{port}/v1/action",
                            data=body,
                            headers={
                                "Content-Type":
                                    "application/json",
                            },
                            method="POST",
                        ),
                        timeout=5,
                    )

                self.assertEqual(
                    error.exception.code,
                    401,
                )
            finally:
                server.shutdown()
                server.server_close()

    def test_tampered_body_is_rejected(self):
        with self._start_server() as (
            server,
            private_key,
        ):
            host, port = server.server_address

            original = b'{"container":"original"}'
            tampered = b'{"container":"tampered"}'

            with urlopen(
                f"http://{host}:{port}/v1/auth/challenge",
                timeout=5,
            ) as response:
                challenge = json.loads(
                    response.read().decode("utf-8")
                )["challenge"]

            message = build_auth_message(
                method="POST",
                path="/v1/action",
                challenge=challenge,
                body=original,
            )

            signature = b64url(
                private_key.sign(message)
            )

            request = Request(
                f"http://{host}:{port}/v1/action",
                data=tampered,
                headers={
                    "Content-Type": "application/json",
                    "X-AGX-Challenge": challenge,
                    "X-AGX-Signature": signature,
                },
                method="POST",
            )

            with self.assertRaises(HTTPError) as error:
                urlopen(
                    request,
                    timeout=5,
                )

            self.assertEqual(
                error.exception.code,
                401,
            )


if __name__ == "__main__":
    unittest.main()
