import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from gateway.executor import GatewayExecutor
from gateway.gateway import Gateway
from gateway.pairing import PairingManager
from gateway.signing import ResultSigner
from gateway.server import create_server
from pc_agent.agent import PCAgent
from protocol.MSGv1 import (
    create_action,
    decode_result,
    encode_action,
    new_hmac_secret,
    new_session_id,
)


class TestGatewayHTTP(unittest.TestCase):


    def test_confirmation_endpoint(self):
        secret = new_hmac_secret()

        gateway = Gateway(
            confirm_actions={"files.list"},
        )

        executor = GatewayExecutor(
            gateway,
            PCAgent(),
            hmac_secret=secret,
        )

        signer = ResultSigner.load_or_create(
            Path("tests") / "test_result_signing_key.pem"
        )

        server = create_server(
            executor,
            host="127.0.0.1",
            port=0,
            signer=signer,
        )
        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
        )
        thread.start()

        try:
            host, port = server.server_address

            action = create_action(
                "files.list",
                {"path": "."},
                session_id=new_session_id(),
            )

            body = json.dumps(
                {
                    "container": encode_action(action),
                }
            ).encode("utf-8")

            request = Request(
                f"http://{host}:{port}/v1/action",
                data=body,
                headers={
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urlopen(request, timeout=5) as response:
                pending = json.loads(
                    response.read().decode("utf-8")
                )

            self.assertEqual(
                pending["status"],
                "confirmation_required",
            )

            token = pending["confirmation_token"]
            self.assertTrue(token)

            confirm_body = json.dumps(
                {
                    "confirmation_token": token,
                }
            ).encode("utf-8")

            confirm_request = Request(
                f"http://{host}:{port}/v1/confirm",
                data=confirm_body,
                headers={
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urlopen(
                confirm_request,
                timeout=5,
            ) as response:
                confirmed = json.loads(
                    response.read().decode("utf-8")
                )

            self.assertEqual(
                confirmed["status"],
                "ok",
            )

            result = decode_result(
                confirmed["container"],
                secret,
            )

            self.assertEqual(
                result.status,
                "ok",
            )

            self.assertTrue(
                confirmed.get("signature")
            )

            with self.assertRaises(Exception):
                urlopen(
                    confirm_request,
                    timeout=5,
                )

        finally:
            server.shutdown()
            server.server_close()

    def test_cancel_endpoint(self):
        secret = new_hmac_secret()

        gateway = Gateway(
            confirm_actions={"files.list"},
        )

        executor = GatewayExecutor(
            gateway,
            PCAgent(),
            hmac_secret=secret,
        )

        signer = ResultSigner.load_or_create(
            Path("tests") / "test_result_signing_key.pem"
        )

        server = create_server(
            executor,
            host="127.0.0.1",
            port=0,
            signer=signer,
        )

        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
        )
        thread.start()

        try:
            host, port = server.server_address

            action = create_action(
                "files.list",
                {"path": "."},
                session_id=new_session_id(),
            )

            body = json.dumps(
                {
                    "container": encode_action(action),
                }
            ).encode("utf-8")

            request = Request(
                f"http://{host}:{port}/v1/action",
                data=body,
                headers={
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urlopen(request, timeout=5) as response:
                pending = json.loads(
                    response.read().decode("utf-8")
                )

            token = pending["confirmation_token"]

            cancel_body = json.dumps(
                {
                    "confirmation_token": token,
                }
            ).encode("utf-8")

            cancel_request = Request(
                f"http://{host}:{port}/v1/cancel",
                data=cancel_body,
                headers={
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urlopen(
                cancel_request,
                timeout=5,
            ) as response:
                cancelled = json.loads(
                    response.read().decode("utf-8")
                )

            self.assertEqual(
                cancelled["status"],
                "cancelled",
            )

            confirm_request = Request(
                f"http://{host}:{port}/v1/confirm",
                data=cancel_body,
                headers={
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with self.assertRaises(Exception):
                urlopen(
                    confirm_request,
                    timeout=5,
                )

        finally:
            server.shutdown()
            server.server_close()
    def test_unpaired_gateway_rejects_action(self):
        secret = new_hmac_secret()

        gateway = Gateway(
            allow_actions={"system.info"},
        )

        executor = GatewayExecutor(
            gateway,
            PCAgent(),
            hmac_secret=secret,
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
                        "container": encode_action(action),
                    }
                ).encode("utf-8")

                request = Request(
                    f"http://{host}:{port}/v1/action",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )

                with self.assertRaises(Exception):
                    urlopen(request, timeout=5)

            finally:
                server.shutdown()
                server.server_close()
    def test_duplicate_confirmation_request_reuses_token(self):
        secret = new_hmac_secret()

        gateway = Gateway(
            confirm_actions={"files.list"},
        )

        executor = GatewayExecutor(
            gateway,
            PCAgent(),
            hmac_secret=secret,
        )

        server = create_server(
            executor,
            host="127.0.0.1",
            port=0,
        )

        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
        )
        thread.start()

        try:
            host, port = server.server_address

            action = create_action(
                "files.list",
                {"path": "."},
                session_id=new_session_id(),
            )

            body = json.dumps(
                {
                    "container": encode_action(action),
                }
            ).encode("utf-8")

            def send_action():
                request = Request(
                    f"http://{host}:{port}/v1/action",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    return json.loads(
                        response.read().decode("utf-8")
                    )

            first = send_action()
            second = send_action()

            self.assertEqual(
                first["status"],
                "confirmation_required",
            )
            self.assertEqual(
                second["status"],
                "confirmation_required",
            )
            self.assertTrue(first["confirmation_token"])
            self.assertEqual(
                first["confirmation_token"],
                second["confirmation_token"],
            )

        finally:
            server.shutdown()
            server.server_close()
    def test_action_endpoint(self):
        secret = new_hmac_secret()

        gateway = Gateway(
            allow_actions={"system.info"},
        )

        executor = GatewayExecutor(
            gateway,
            PCAgent(),
            hmac_secret=secret,
        )

        server = create_server(
            executor,
            host="127.0.0.1",
            port=0,
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
                    "container": encode_action(action),
                }
            ).encode("utf-8")

            request = Request(
                f"http://{host}:{port}/v1/action",
                data=body,
                headers={
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            with urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, 200)
                payload = json.loads(
                    response.read().decode("utf-8")
                )

            result = decode_result(
                payload["container"],
                secret,
            )

            self.assertEqual(result.command_id, action.command_id)
            self.assertEqual(result.status, "ok")
            self.assertEqual(result.result["system"], "Windows")

        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
