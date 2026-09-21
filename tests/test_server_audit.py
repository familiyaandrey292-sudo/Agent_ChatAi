import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from gateway.audit import AuditLogger
from gateway.executor import GatewayExecutor
from gateway.gateway import Gateway
from gateway.server import create_server
from pc_agent.agent import PCAgent
from protocol.MSGv1 import (
    create_action,
    decode_result,
    encode_action,
    new_hmac_secret,
    new_session_id,
)


def post_json(host: str, port: int, path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")

    request = Request(
        f"http://{host}:{port}{path}",
        data=body,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urlopen(request, timeout=5) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


class TestGatewayHTTPAudit(unittest.TestCase):

    def test_http_confirm_lifecycle_is_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            audit = AuditLogger(audit_path)

            secret = new_hmac_secret()

            gateway = Gateway(
                confirm_actions={"files.list"},
            )

            executor = GatewayExecutor(
                gateway,
                PCAgent(),
                hmac_secret=secret,
                audit=audit,
            )

            server = create_server(
                executor,
                host="127.0.0.1",
                port=0,
                audit=audit,
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

                pending = post_json(
                    host,
                    port,
                    "/v1/action",
                    {
                        "container": encode_action(action),
                    },
                )

                self.assertEqual(
                    pending["status"],
                    "confirmation_required",
                )

                token = pending["confirmation_token"]
                self.assertTrue(token)

                confirmed = post_json(
                    host,
                    port,
                    "/v1/confirm",
                    {
                        "confirmation_token": token,
                    },
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

                entries = [
                    json.loads(line)
                    for line in audit_path.read_text(
                        encoding="utf-8"
                    ).splitlines()
                ]

                events = [
                    entry["event"]
                    for entry in entries
                ]

                self.assertEqual(
                    events,
                    [
                        "action_received",
                        "confirmation_required",
                        "confirmation_accepted",
                        "action_result",
                    ],
                )

                for entry in entries:
                    self.assertNotIn("args", entry)
                    self.assertNotIn("result", entry)

            finally:
                server.shutdown()
                server.server_close()

    def test_http_cancel_lifecycle_is_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            audit = AuditLogger(audit_path)

            secret = new_hmac_secret()

            gateway = Gateway(
                confirm_actions={"files.list"},
            )

            executor = GatewayExecutor(
                gateway,
                PCAgent(),
                hmac_secret=secret,
                audit=audit,
            )

            server = create_server(
                executor,
                host="127.0.0.1",
                port=0,
                audit=audit,
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

                pending = post_json(
                    host,
                    port,
                    "/v1/action",
                    {
                        "container": encode_action(action),
                    },
                )

                self.assertEqual(
                    pending["status"],
                    "confirmation_required",
                )

                token = pending["confirmation_token"]
                self.assertTrue(token)

                cancelled = post_json(
                    host,
                    port,
                    "/v1/cancel",
                    {
                        "confirmation_token": token,
                    },
                )

                self.assertEqual(
                    cancelled["status"],
                    "cancelled",
                )

                with self.assertRaises(HTTPError) as context:
                    post_json(
                        host,
                        port,
                        "/v1/confirm",
                        {
                            "confirmation_token": token,
                        },
                    )

                self.assertEqual(
                    context.exception.code,
                    409,
                )

                entries = [
                    json.loads(line)
                    for line in audit_path.read_text(
                        encoding="utf-8"
                    ).splitlines()
                ]

                events = [
                    entry["event"]
                    for entry in entries
                ]

                self.assertEqual(
                    events,
                    [
                        "action_received",
                        "confirmation_required",
                        "confirmation_cancelled",
                    ],
                )

                for entry in entries:
                    self.assertNotIn("args", entry)
                    self.assertNotIn("result", entry)

            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
