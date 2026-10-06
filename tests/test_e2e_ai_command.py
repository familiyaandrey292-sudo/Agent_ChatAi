"""End-to-end tests for AI-generated AGX1:C commands.

These tests simulate the real chat pipeline:

1. An AI model writes free-form text into the chat and embeds an
   AGX1:C container (the exact string the user would see rendered).
2. The browser-side extractor regex (mirrored from content.js) finds
   the container in the surrounding prose, markdown fences and code
   blocks without modification.
3. The extracted container is POSTed verbatim to the Gateway
   /v1/command endpoint together with the per-tab session_id.
4. The Gateway validates integrity, timestamp/TTL, session match,
   policy and executes the action, returning a signed AGX1:R result.

Negative cases cover the failure modes a real AI chat produces:
hallucinated integrity tags, stale timestamps, oversized TTL, wrong
session_id and truncated containers.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import threading
import unittest
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from gateway.executor import GatewayExecutor
from gateway.gateway import Gateway
from gateway.server import create_server
from pc_agent.agent import PCAgent
from protocol.command import create_command, encode_command
from protocol.MSGv1 import decode_result, new_hmac_secret


# Mirror of the command extractor in browser_bridge/extension/content.js
# (line ~72): /AGX1:C:[A-Za-z0-9_-]+:[A-Fa-f0-9]{64}/g
COMMAND_EXTRACTOR_RE = re.compile(r"AGX1:C:[A-Za-z0-9_-]+:[A-Fa-f0-9]{64}")

ALLOWED_ACTIONS = {"system.info"}


def _raw_container(fields: dict) -> str:
    """Build an AGX1:C container bypassing client-side validation.

    Simulates an AI model that writes a syntactically valid but
    semantically invalid container into the chat (stale timestamp,
    oversized TTL, unknown fields).  The integrity tag is computed the
    same way as in encode_command so the Gateway reaches its semantic
    validation stage instead of failing on integrity alone.
    """
    canonical = json.dumps(
        fields,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    payload = base64.urlsafe_b64encode(
        canonical.encode("utf-8")
    ).decode("ascii").rstrip("=")
    digest = hashlib.sha256(f"C:{payload}".encode("ascii")).hexdigest()
    return f"AGX1:C:{payload}:{digest}"


def _tampered_payload(container: str, mutate) -> str:
    """Replace the JSON payload inside a container, keep OLD integrity."""
    parts = container.split(":")
    raw = json.loads(
        base64.urlsafe_b64decode(parts[2] + "==").decode("utf-8")
    )
    mutated = mutate(dict(raw))
    canonical = json.dumps(
        mutated,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    new_payload = base64.urlsafe_b64encode(
        canonical.encode("utf-8")
    ).decode("ascii").rstrip("=")
    parts[2] = new_payload
    # Integrity tag intentionally NOT recomputed.
    return ":".join(parts)


class E2EAICommandTest(unittest.TestCase):
    def setUp(self):
        self.secret = new_hmac_secret()
        self.gateway = Gateway(allow_actions=set(ALLOWED_ACTIONS))
        self.executor = GatewayExecutor(
            self.gateway,
            PCAgent(),
            hmac_secret=self.secret,
        )
        self.server = create_server(
            self.executor,
            host="127.0.0.1",
            port=0,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        self.host, self.port = self.server.server_address

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _post_command(self, container: str, session_id: str):
        body = json.dumps(
            {
                "container": container,
                "session_id": session_id,
            }
        ).encode("utf-8")
        request = Request(
            f"http://{self.host}:{self.port}/v1/command",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(
                    response.read().decode("utf-8")
                )
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    # ------------------------------------------------------------------
    # Positive: full AI-style pipeline
    # ------------------------------------------------------------------
    def test_ai_generated_container_executes_end_to_end(self):
        command = create_command("system.info", {}, ttl=120)
        container = encode_command(command)

        # What a real AI chat renders around the container: prose,
        # markdown fences, inline code, trailing punctuation.
        ai_reply = (
            "Конечно, выполняю действие на ПК.\n\n"
            "```text\n"
            f"{container}\n"
            "```\n"
            f"Отправил команду `{container}` в Agent ChatAI Bridge.\n"
            "Дождитесь результата в консоли моста."
        )

        found = COMMAND_EXTRACTOR_RE.findall(ai_reply)
        self.assertEqual(found.count(container), 2)
        # Extractor must return byte-identical containers.
        self.assertTrue(all(chunk == container for chunk in found))

        status, payload = self._post_command(
            container, command.session_id
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(
            payload["container"].startswith("AGX1:R:")
        )

        result = decode_result(payload["container"], self.secret)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.session_id, command.session_id)

    def test_multiple_containers_in_one_reply_dedupe(self):
        first = encode_command(create_command("system.info", {}))
        second = encode_command(create_command("system.info", {}))
        reply = f"Вариант A: {first}\nВариант B: {second}\n{first} снова"

        found = list(dict.fromkeys(COMMAND_EXTRACTOR_RE.findall(reply)))
        self.assertEqual(found, [first, second])

    # ------------------------------------------------------------------
    # Negative: realistic AI failure modes
    # ------------------------------------------------------------------
    def test_hallucinated_integrity_is_rejected(self):
        command = create_command("system.info", {})
        container = encode_command(command)
        bad = container[:-1] + ("0" if container[-1] != "0" else "1")

        status, payload = self._post_command(
            bad, command.session_id
        )
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"], "command_rejected")
        self.assertEqual(payload.get("code"), "COMMAND_INVALID")

    def test_tampered_action_keeps_old_integrity_and_fails(self):
        command = create_command("system.info", {})
        container = encode_command(command)
        tampered = _tampered_payload(
            container, lambda d: d.update(action="file.delete") or d
        )

        status, payload = self._post_command(
            tampered, command.session_id
        )
        self.assertEqual(status, 409)
        self.assertIn("integrity", json.dumps(payload).lower())

    def test_stale_timestamp_is_rejected(self):
        import time as _time

        fields = {
            "action": "system.info",
            "args": {},
            "message_id": "1d" * 16,
            "session_id": None,  # replaced below
            "timestamp": _time.time() - 3600,
            "ttl": 60.0,
        }
        command = create_command("system.info", {})
        fields["session_id"] = command.session_id
        container = _raw_container(fields)

        status, payload = self._post_command(
            container, command.session_id
        )
        self.assertEqual(status, 409)
        self.assertIn("COMMAND_EXPIRED", json.dumps(payload))

    def test_ttl_over_maximum_is_rejected_with_code(self):
        command = create_command("system.info", {})
        container = _raw_container(
            {
                "action": "system.info",
                "args": {},
                "message_id": command.message_id,
                "session_id": command.session_id,
                "timestamp": command.timestamp,
                "ttl": 99999.0,
            }
        )

        status, payload = self._post_command(
            container, command.session_id
        )
        self.assertEqual(status, 409)
        self.assertEqual(payload.get("code"), "COMMAND_TTL_EXCEEDED")
        self.assertTrue(payload.get("retryable"))

    def test_wrong_tab_session_is_rejected(self):
        command = create_command("system.info", {})
        container = encode_command(command)

        status, payload = self._post_command(
            container, "AAAAAAAAAAAAAAAAAAAAAA"
        )
        self.assertEqual(status, 409)
        self.assertEqual(
            payload.get("code"), "COMMAND_SESSION_MISMATCH"
        )
        self.assertTrue(payload.get("retryable"))

    def test_truncated_container_not_extracted(self):
        command = create_command("system.info", {})
        container = encode_command(command)
        truncated = container[:-8]
        reply = f"Команда: {truncated}"
        self.assertEqual(COMMAND_EXTRACTOR_RE.findall(reply), [])

    def test_denied_action_not_in_allowlist(self):
        command = create_command("app.open", {"name": "notepad"})
        container = encode_command(command)

        status, payload = self._post_command(
            container, command.session_id
        )
        # Policy denial still returns a structured result, not ok.
        self.assertIn(status, (200, 403, 409))
        if status == 200:
            self.assertNotEqual(payload["status"], "ok")


if __name__ == "__main__":
    unittest.main()
