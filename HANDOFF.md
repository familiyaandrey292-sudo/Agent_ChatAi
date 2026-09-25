# HANDOFF.md — Agent ChatAI Gateway + Edge Browser Bridge

## Current verified state

Project: Agent ChatAI Gateway + Edge Browser Bridge
Local root: C:\Proj\Agents\Agent_ChatAi
GitHub: familiyaandrey292-sudo/Agent_ChatAi
Last previously confirmed commit: 325c782

Goal: universal bridge from AI chat rendered browser DOM to the local PC. The rendered DOM is authoritative; direct AI APIs are not the primary command transport. The protocol uses neutral AGX1 containers so the AI is not modeled as having direct PC control.

## Architecture

AI chat DOM → AGX1:C → Browser Bridge → /v1/command → Gateway → AGX1:A → Executor → PC Agent → AGX1:R → Browser Bridge → chat

AGX1:C is a neutral upper-level command. Current /v1/command decodes C and creates a fresh internal ACTION with create_action(..., session_id=new_session_id()). Do not redesign this correlation model without a specific requirement.

## AGX1:C

File: protocol/command.py

Format:
AGX1:C:<base64url(canonical-json)>:<sha256>

Current Command fields:
- action
- args

Validation includes:
- action regex [a-zA-Z0-9_.:-]+
- action max 128 chars
- args must be a JSON object
- SHA-256 tamper detection
- invalid container/kind/action/missing action rejection

Eight dedicated COMMAND unit tests pass.

## AGX1:A

File: protocol/MSGv1.py

Format:
AGX1:A:<base64url(canonical-json)>:<sha256>

ACTION is the internal Gateway → Executor layer.

Metadata includes:
version, kind, message_id, command_id, session_id, timestamp, nonce, sequence, action, args.

Protection:
- canonical JSON
- base64url
- SHA-256 integrity
- max age 300 seconds
- max future skew 30 seconds

## AGX1:R

Format:
AGX1:R:<base64url(canonical-json)>:<hmac-sha256>

RESULT has HMAC-SHA256 authentication/integrity.

Additionally gateway/signing.py provides persistent Ed25519 RESULT signing. The Browser Bridge verifies the returned Ed25519 signature.

## Gateway / Executor / Agent

Main files:
- gateway/gateway.py
- gateway/executor.py
- gateway/server.py
- pc_agent/agent.py

Policy:
- ALLOW
- CONFIRM
- DENY

Replay protection:
- persistent SQLite
- reservation key is session_id + message_id
- survives Gateway restart

PC Agent currently supports:
- system.info
- files.list
- app.open

External executable checks use shutil.which(). Missing components must produce an explicit install/PATH message rather than an unexplained failure.

## Browser Auth

Files:
- gateway/browser_auth.py
- browser_bridge/extension/browser_keys.js
- browser_bridge/extension/background.js

Browser authentication:
- Ed25519 challenge-response
- private key stored in browser IndexedDB
- private key non-extractable
- one-time challenges
- invalid signatures do not consume the challenge
- tampered request body rejected
- multiple browser keys supported

Gateway: http://127.0.0.1:8765
Challenge endpoint: /v1/auth/challenge

## HTTP API

GET:
- /v1/health
- /v1/auth/challenge

POST:
- /v1/pair
- /v1/action
- /v1/command
- /v1/confirm
- /v1/cancel

/v1/command flow:
1. receive JSON container
2. decode AGX1:C
3. create internal AGX1:A
4. pass ACTION to Executor
5. return AGX1:R
6. create confirmation token when required
7. return Ed25519 signature separately

Confirmed:
- valid C → HTTP 200 → authenticated/signed R → system.info executed
- tampered C → HTTP 409 → command rejected

## Audit

Files:
- gateway/audit.py
- gateway/audit.jsonl

Audit is integrated end-to-end and excludes action args and result payloads. JSONL validity, rotation, concurrent writes, sensitive-argument exclusion, and HTTP/executor lifecycle are tested.

Typical events:
- action_received
- action_result

## Browser Bridge

Main files:
- browser_bridge/extension/content.js
- browser_bridge/extension/background.js
- browser_bridge/extension/browser_keys.js
- browser_bridge/extension/popup.html
- browser_bridge/extension/popup.js

Current behavior:
- reads rendered DOM / document.body.innerText
- MutationObserver tracks DOM changes
- recognizes AGX1:A and AGX1:C
- suppresses duplicates
- publishes RESULT back into chat composer
- command panel supports resize/drag/history
- day/night theme
- confirmation UI

Bridge control requirements:
1. panel hidden after tab load
2. state separate per tab
3. parser only active while Bridge is enabled
4. close button X exists
5. Alt+Shift+A toggles Bridge
6. popup has ON/OFF
7. Alt+Shift+A in popup is represented by tooltip

Static checks previously verified:
- NODE_CHECK=OK
- BRIDGE_FUNCTIONS=True
- PARSER_GUARD=True
- CLOSE_BUTTON=True

A previous PowerShell patch accidentally inserted a literal line-ending escape sequence into JavaScript and broke content.js; this was fixed. Missing openCommandPanel(), closeCommandPanel(), and toggleCommandPanel() were also added.

## Current test status

Full suite:
**83 tests — OK**

Last full run:
Ran 83 tests in 7.732s
OK

Recent additions:
tests/test_command.py — 8 tests covering roundtrip, Unicode/nested args, tamper detection, invalid container, wrong kind, invalid action, missing action, and args type.

tests/test_server.py:
- test_command_endpoint
- test_command_endpoint_rejects_tampered_container

Integration results:
- valid /v1/command → HTTP 200
- tampered /v1/command → HTTP 409

## Current Doctor status

**DOCTOR: PASS**

Verified:
- Python 3.12.10
- cryptography 50.0.1
- Gateway PID 1732
- 127.0.0.1:8765 listening
- Health OK
- Browser Auth paired and enabled
- Auth challenge available, length 43
- Result signing key present
- Browser auth key present
- Replay database present
- Audit log valid JSONL, 35 recent lines checked
- Autostart Ready, last result 0
- Browser extension files present
- JavaScript syntax checks passed
- Python compilation passed
- 83 tests OK

Browser test page:
http://127.0.0.1:8766/index.html

## Security invariants

Do not break without a deliberate design decision:
- rendered DOM is the command source
- direct AI API is not the primary command transport
- AGX1:C remains a neutral command container
- ACTION integrity uses SHA-256
- RESULT protocol authentication uses HMAC
- Browser-facing RESULT signing uses Ed25519
- replay protection is persistent
- CONFIRM never executes before confirmation
- DENY never executes
- audit excludes args/result payloads
- browser private signing key is never exported
- Browser Auth challenges are one-time
- tampered body/container is rejected
- external dependencies are checked before use

## Current project point

Backend, security, protocol, and HTTP C/A/R chain are in a verified working state:

**83/83 tests + DOCTOR: PASS**

Verified chain:
**AGX1:C → /v1/command → AGX1:A → Executor → AGX1:R → signature**

Next task is the real Edge/Chromium end-to-end test, not a backend redesign:
1. AI emits AGX1:C into rendered chat DOM
2. Browser Bridge detects it
3. Browser Auth signs the HTTP request
4. Gateway accepts C
5. Gateway creates A
6. Executor performs the action
7. Gateway returns R + Ed25519 signature
8. Browser Bridge verifies the signature
9. R is inserted back into the AI chat DOM
10. Test ALLOW, CONFIRM, DENY, and replay

## Work completed in the latest session

1. Reviewed the existing C/A/R architecture.
2. Added 8 COMMAND unit tests.
3. Added /v1/command integration test.
4. Verified valid C → /v1/command → R with HTTP 200.
5. Added tampered-C integration test.
6. Verified tampered C → HTTP 409.
7. Full suite reached 83/83 OK.
8. Doctor returned DOCTOR: PASS.
9. HANDOFF is being updated as the continuity checkpoint.

## Git working-tree note

The previously confirmed clean state was before the latest test additions. The latest tests and this HANDOFF update must be checked with git status before the next commit. Do not assume the working tree is clean from the old status.

## Instructions for the next AI

- Read this HANDOFF first.
- Do not repeat already-proven tests without a reason.
- Understand existing architecture before changing code.
- Do not redesign the whole protocol for a local issue.
- Add/update tests after meaningful code changes.
- Run the full suite and Doctor after runtime-affecting changes.
- **Always update HANDOFF.md after a meaningful project stage.**
- Prefer one self-contained PowerShell command at a time.
- When possible, copy PowerShell output to Windows Clipboard.
- If an external component is missing, explicitly offer installation.
- If context is lost, use this HANDOFF as the continuity source and continue from Current project point.
