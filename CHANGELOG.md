# Changelog

## 0.3.0

### Added
- Browser Auth pairing and signed browser requests.
- Ed25519 RESULT signing and browser verification.
- Privacy-conscious audit JSONL logging.
- Audit rotation.
- Browser Confirm / Cancel confirmation flow.
- Static regression tests for Browser Cancel.
- Confirmation lifecycle audit events.

### Security hardening
- Browser private key is generated as non-extractable.
- Browser private key is never exported.
- Persistent replay protection.
- One-time confirmation tokens.
- Idempotent pending confirmation requests for identical ACTION containers.

### Verification
- Full test suite: 67 tests, OK.
- Doctor: PASS.
- Real Edge ACTION / Cancel flow verified.

### Fixed
- Browser Cancel now sends AGX_CANCEL_ACTION instead of only removing the UI.
- Repeated identical CONFIRM ACTION requests reuse the existing pending confirmation token.
