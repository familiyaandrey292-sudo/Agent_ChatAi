# Agent ChatAI Gateway + Edge Browser Bridge

## Status

Current verified state:
- AGX ACTION/RESULT protocol with integrity checks.
- ACTION timestamp freshness and replay protection.
- Local policy: ALLOW / CONFIRM / DENY.
- Persistent SQLite replay protection.
- One-time confirmation tokens with TTL.
- Idempotent pending confirmations: repeated identical ACTION reuses the existing confirmation token.
- Confirm and Cancel browser UI flow.
- Browser Auth with Ed25519 challenge-response.
- Non-extractable browser private key.
- Ed25519 RESULT signing and browser verification.
- Privacy-conscious JSONL audit logging with rotation.
- Browser Bridge for Edge.
- Windows Task Scheduler autostart.
- Doctor diagnostics.

## Verification

- Full test suite: **67 tests, OK**.
- Doctor: **PASS**.
- Gateway: 127.0.0.1:8765.
- Browser test page: http://127.0.0.1:8766/index.html.

## Security

Browser private keys are generated as non-extractable Web Crypto keys and are never exported.
Browser requests are authenticated with challenge-response signatures.
Replay protection is persistent across Gateway restarts.
Audit records intentionally exclude action arguments and full result payloads.
