"""Local HTTP transport for the AGX Gateway."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from gateway.audit import AuditLogger
from gateway.browser_auth import BrowserAuth
from gateway.confirmation import ConfirmationStore
from gateway.executor import GatewayExecutor
from gateway.gateway import Gateway
from gateway.pairing import PairingManager
from gateway.replay_store import SQLiteReplayStore
from gateway.signing import ResultSigner
from pc_agent.agent import PCAgent
from protocol.MSGv1 import (
    decode_action,
    decode_result,
    encode_action,
    create_action,
    new_hmac_secret,
)
from protocol.command import decode_command


class GatewayHTTPHandler(BaseHTTPRequestHandler):
    executor: GatewayExecutor | None = None
    signer: ResultSigner | None = None
    confirmations: ConfirmationStore | None = None

    browser_auth: BrowserAuth | None = None
    pairing: PairingManager | None = None
    audit: AuditLogger | None = None

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        content_length = self.headers.get("Content-Length")

        if not content_length:
            raise ValueError("missing_content_length")

        try:
            length = int(content_length)
        except ValueError as exc:
            raise ValueError("invalid_content_length") from exc

        if length <= 0 or length > 1024 * 1024:
            raise ValueError("invalid_body_size")

        return self.rfile.read(length)

    def _read_json_body(self, body: bytes) -> dict:
        try:
            payload = json.loads(
                body.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError("invalid_json") from exc

        if not isinstance(payload, dict):
            raise ValueError(
                "request_must_be_object"
            )

        return payload

    def _require_browser_auth(
        self,
        body: bytes,
    ) -> None:
        if self.browser_auth is None:
            if self.pairing is not None:
                raise PermissionError(
                    "browser_not_paired"
                )
            return

        challenge = self.headers.get(
            "X-AGX-Challenge"
        )
        signature = self.headers.get(
            "X-AGX-Signature"
        )

        if not challenge or not signature:
            raise PermissionError(
                "browser_auth_required"
            )

        try:
            self.browser_auth.verify(
                method=self.command,
                path=self.path,
                body=body,
                challenge=challenge,
                signature=signature,
            )
        except ValueError as exc:
            raise PermissionError(
                str(exc)
            ) from exc

    def _result_response(
        self,
        result_container: str,
        *,
        confirmation_token: str | None = None,
    ) -> None:
        if self.executor is None:
            self._send_json(
                503,
                {
                    "error":
                        "gateway_not_initialized"
                },
            )
            return

        result = decode_result(
            result_container,
            self.executor.hmac_secret,
        )

        signature = (
            self.signer.sign(result_container)
            if self.signer is not None
            else None
        )

        payload = {
            "container": result_container,
            "status": result.status,
            "message": result.message,
        }

        if signature is not None:
            payload["signature"] = signature

        if confirmation_token is not None:
            payload["confirmation_token"] = (
                confirmation_token
            )

            if self.confirmations is not None:
                payload["confirmation_expires_in"] = (
                    self.confirmations.ttl_seconds
                )

        self._send_json(
            200,
            payload,
        )

    def do_GET(self) -> None:
        if self.path == "/v1/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "service":
                        "Agent ChatAI Gateway",
                    "paired":
                        self.browser_auth is not None,
                    "browser_auth":
                        self.browser_auth is not None,
                },
            )
            return

        if self.path == "/v1/auth/challenge":
            if self.browser_auth is None:
                self._send_json(
                    409,
                    {
                        "error":
                            "browser_not_paired"
                    },
                )
                return

            self._send_json(
                200,
                {
                    "challenge":
                        self.browser_auth.create_challenge(),
                    "expires_in":
                        self.browser_auth
                            .challenge_ttl_seconds,
                },
            )
            return

        self._send_json(
            404,
            {"error": "not_found"},
        )

    def do_POST(self) -> None:
        try:
            body = self._read_body()
        except ValueError as exc:
            self._send_json(
                400,
                {"error": str(exc)},
            )
            return

        try:
            if self.path == "/v1/pair":
                self._handle_pair(body)
                return

            if self.path in {
                "/v1/action",
                "/v1/command",
                "/v1/confirm",
                "/v1/cancel",
            }:
                self._require_browser_auth(body)

            if self.path == "/v1/action":
                self._handle_action(body)

            elif self.path == "/v1/command":
                self._handle_command(body)
            elif self.path == "/v1/confirm":
                self._handle_confirm(body)

            elif self.path == "/v1/cancel":
                self._handle_cancel(body)

            else:
                self._send_json(
                    404,
                    {"error": "not_found"},
                )

        except PermissionError as exc:
            self._send_json(
                401,
                {
                    "error":
                        "browser_auth_failed",
                    "message": str(exc),
                },
            )

    def _handle_pair(self, body: bytes) -> None:
        if self.pairing is None:
            self._send_json(
                503,
                {
                    "error":
                        "pairing_not_initialized"
                },
            )
            return

        try:
            payload = self._read_json_body(body)

            code = payload.get("code")
            public_key = payload.get(
                "public_key_spki_b64"
            )

            if (
                not isinstance(code, str)
                or not code
            ):
                raise ValueError(
                    "missing_pairing_code"
                )

            if (
                not isinstance(public_key, str)
                or not public_key
            ):
                raise ValueError(
                    "missing_public_key"
                )

            self.pairing.pair(
                code=code,
                public_key_spki_b64=public_key,
            )

            public_path = (
                self.pairing.public_key_path
            )

            self.browser_auth = (
                BrowserAuth.load_many(
                    self.pairing.public_key_paths
                )
            )

            GatewayHTTPHandler.browser_auth = (
                self.browser_auth
            )

        except ValueError as exc:
            self._send_json(
                409,
                {
                    "error": "pairing_rejected",
                    "message": str(exc),
                },
            )
            return

        self._send_json(
            200,
            {
                "status": "paired",
            },
        )

    def _handle_action(self, body: bytes) -> None:
        try:
            payload = self._read_json_body(body)

            container = payload.get(
                "container"
            )

            if (
                not isinstance(container, str)
                or not container
            ):
                raise ValueError(
                    "missing_container"
                )

            if self.executor is None:
                self._send_json(
                    503,
                    {
                        "error":
                            "gateway_not_initialized"
                    },
                )
                return

            result_container = (
                self.executor.process(container)
            )

            result = decode_result(
                result_container,
                self.executor.hmac_secret,
            )

            confirmation_token = None

            if (
                result.status
                == "confirmation_required"
            ):
                if self.confirmations is None:
                    self._send_json(
                        503,
                        {
                            "error":
                                "confirmation_store_not_initialized"
                        },
                    )
                    return

                confirmation_token = (
                    self.confirmations.create(
                        container
                    )
                )

            self._result_response(
                result_container,
                confirmation_token=
                    confirmation_token,
            )

        except ValueError as exc:
            self._send_json(
                409,
                {
                    "error":
                        "replay_or_invalid_state",
                    "message": str(exc),
                },
            )

        except Exception as exc:
            self._send_json(
                400,
                {
                    "error":
                        "action_rejected",
                    "message": str(exc),
                },
            )

    def _handle_command(
        self,
        body: bytes,
    ) -> None:
        try:
            payload = self._read_json_body(body)

            container = payload.get(
                "container"
            )

            if (
                not isinstance(container, str)
                or not container
            ):
                raise ValueError(
                    "missing_container"
                )

            command = decode_command(container)

            if self.executor is None:
                self._send_json(
                    503,
                    {
                        "error":
                            "gateway_not_initialized"
                    },
                )
                return

            action = create_action(
                command.action,
                command.args,
                session_id=command.session_id,
                message_id=command.message_id,
            )

            action_container = encode_action(
                action
            )

            result_container = (
                self.executor.process(
                    action_container
                )
            )

            result = decode_result(
                result_container,
                self.executor.hmac_secret,
            )

            confirmation_token = None

            if (
                result.status
                == "confirmation_required"
            ):
                if self.confirmations is None:
                    self._send_json(
                        503,
                        {
                            "error":
                                "confirmation_store_not_initialized"
                        },
                    )
                    return

                confirmation_token = (
                    self.confirmations.create(
                        action_container
                    )
                )

            self._result_response(
                result_container,
                confirmation_token=
                    confirmation_token,
            )

        except ValueError as exc:
            self._send_json(
                409,
                {
                    "error":
                        "command_rejected",
                    "message": str(exc),
                },
            )

        except Exception as exc:
            self._send_json(
                400,
                {
                    "error":
                        "command_failed",
                    "message": str(exc),
                },
            )
    def _handle_confirm(
        self,
        body: bytes,
    ) -> None:
        try:
            payload = self._read_json_body(body)

            token = payload.get(
                "confirmation_token"
            )

            if (
                not isinstance(token, str)
                or not token
            ):
                raise ValueError(
                    "missing_confirmation_token"
                )

            if (
                self.executor is None
                or self.confirmations is None
            ):
                self._send_json(
                    503,
                    {
                        "error":
                            "confirmation_not_initialized"
                    },
                )
                return

            container = (
                self.confirmations.consume(token)
            )

            result_container = (
                self.executor.process_confirmed(
                    container
                )
            )

            self._result_response(
                result_container,
            )

        except ValueError as exc:
            self._send_json(
                409,
                {
                    "error":
                        "confirmation_rejected",
                    "message": str(exc),
                },
            )

        except Exception as exc:
            self._send_json(
                400,
                {
                    "error":
                        "confirmation_failed",
                    "message": str(exc),
                },
            )

    def _handle_cancel(
        self,
        body: bytes,
    ) -> None:
        try:
            payload = self._read_json_body(body)

            token = payload.get(
                "confirmation_token"
            )

            if (
                not isinstance(token, str)
                or not token
            ):
                raise ValueError(
                    "missing_confirmation_token"
                )

            if self.confirmations is None:
                self._send_json(
                    503,
                    {
                        "error":
                            "confirmation_not_initialized"
                    },
                )
                return

            container = self.confirmations.cancel(token)

            if self.audit is not None:
                action = decode_action(container)

                self.audit.record(
                    "confirmation_cancelled",
                    action=action.action,
                    command_id=action.command_id,
                    session_id=action.session_id,
                    message_id=action.message_id,
                )

        except ValueError as exc:
            self._send_json(
                409,
                {
                    "error":
                        "cancel_rejected",
                    "message": str(exc),
                },
            )
            return

        self._send_json(
            200,
            {"status": "cancelled"},
        )

    def log_message(
        self,
        format,
        *args,
    ) -> None:
        print(
            f"[GatewayHTTP] {format % args}"
        )


def create_server(
    executor: GatewayExecutor,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    signer: ResultSigner | None = None,
    confirmations: ConfirmationStore | None = None,
    browser_auth: BrowserAuth | None = None,
    pairing: PairingManager | None = None,
    audit: AuditLogger | None = None,
) -> ThreadingHTTPServer:
    GatewayHTTPHandler.executor = executor
    GatewayHTTPHandler.signer = signer
    GatewayHTTPHandler.confirmations = (
        confirmations
        or ConfirmationStore()
    )
    GatewayHTTPHandler.browser_auth = (
        browser_auth
    )
    GatewayHTTPHandler.pairing = pairing

    GatewayHTTPHandler.audit = audit
    return ThreadingHTTPServer(
        (host, port),
        GatewayHTTPHandler,
    )


if __name__ == "__main__":
    secret = new_hmac_secret()

    replay_db = Path(
        os.environ.get(
            "AGX_REPLAY_DB",
            str(
                Path(__file__).with_name(
                    "replay.sqlite3"
                )
            ),
        )
    )

    signing_key_path = Path(
        os.environ.get(
            "AGX_RESULT_SIGNING_KEY",
            str(
                Path(__file__).with_name(
                    "result_signing_key.pem"
                )
            ),
        )
    )

    browser_public_key_path = Path(
        os.environ.get(
            "AGX_BROWSER_PUBLIC_KEY",
            str(
                Path(__file__).with_name(
                    "browser_auth_public.pem"
                )
            ),
        )
    )

    replay_store = SQLiteReplayStore(
        replay_db,
        retention_seconds=900,
    )

    signer = ResultSigner.load_or_create(
        signing_key_path
    )

    confirmations = ConfirmationStore(
        ttl_seconds=120,
    )

    pairing = PairingManager(
        browser_public_key_path
    )

    if pairing.paired:
        pairing.ensure_pairing_code()

    browser_auth = None

    if pairing.paired:
        browser_auth = BrowserAuth.load_many(
            pairing.public_key_paths
        )

    gateway = Gateway(
        allow_actions={"system.info"},
        confirm_actions={"files.list"},
        replay_store=replay_store,
    )

    audit_path = Path(
        os.environ.get(
            "AGX_AUDIT_LOG",
            str(
                Path(__file__).with_name(
                    "audit.jsonl"
                )
            ),
        )
    )

    try:
        audit_max_bytes = int(
            os.environ.get(
                "AGX_AUDIT_MAX_BYTES",
                str(AuditLogger.DEFAULT_MAX_BYTES),
            )
        )
        audit_backup_count = int(
            os.environ.get(
                "AGX_AUDIT_BACKUP_COUNT",
                str(AuditLogger.DEFAULT_BACKUP_COUNT),
            )
        )
    except ValueError as exc:
        raise ValueError(
            "AGX_AUDIT_MAX_BYTES and "
            "AGX_AUDIT_BACKUP_COUNT must be integers"
        ) from exc

    audit = AuditLogger(
        audit_path,
        max_bytes=audit_max_bytes,
        backup_count=audit_backup_count,
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
        port=8765,
        signer=signer,
        confirmations=confirmations,
        browser_auth=browser_auth,
        pairing=pairing,
        audit=audit,
    )

    print(
        "Gateway HTTP server listening on "
        "http://127.0.0.1:8765",
        flush=True,
    )

    if pairing.pairing_code:
        print(
            "BROWSER PAIRING CODE:",
            pairing.pairing_code,
            flush=True,
        )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


