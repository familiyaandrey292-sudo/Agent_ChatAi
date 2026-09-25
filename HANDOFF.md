# HANDOFF.md — Agent ChatAI Gateway + Edge Browser Bridge

## 0. Purpose of this file

This file is the continuity checkpoint for the project.

A new AI must read this file first and continue from the **Current project point** below. Do not restart the project from scratch and do not redesign proven parts without a concrete reason.

---

## 1. Project identity

Project name: **Agent ChatAI Gateway + Edge Browser Bridge**

Local root:
`C:\Proj\Agents\Agent_ChatAi`

GitHub repository:
`familiyaandrey292-sudo/Agent_ChatAi`

Main branch:
`main`

Latest confirmed repository commit at this handoff:
`91f92f070d7816b6f57466f93a95bd909249c5e5`

Date of this handoff:
**2026-09-25**

Primary goal:

> Universal bridge from an AI chat page, using the **rendered browser DOM as the authoritative command source**, to the local Windows PC.

Direct AI APIs are **not** the primary command transport.

The protocol deliberately uses neutral AGX1 containers so the AI is not modeled as having direct PC control.

---

## 2. Core architecture

Verified architecture:

**AI chat rendered DOM → AGX1:C → Browser Bridge → /v1/command → Gateway → AGX1:A → Executor → PC Agent → AGX1:R → Browser Bridge → chat**

Important:

- The browser DOM is authoritative.
- Browser Bridge parses rendered chat content.
- AGX1:C is the neutral upper-level command container.
- `/v1/command` decodes C and creates a **fresh internal AGX1:A**.
- Current implementation uses:
  `create_action(..., session_id=new_session_id()))
- Do not invent additional C/A correlation semantics that are not present in the current C schema.
- Do not redesign this flow just to solve a local browser issue.

---

## 3. AGX1:C — command from rendered AI chat

File:

`protocol/command.py`

Format:

`AGX1:C:<base64url(canonical-json)>:<sha256>`

Current logical fields:

- `action`
- `args`

Validation:

- action must match `[a-zA-Z0-9_.:-]+`
- action maximum length: 128
- args must be a JSON object
- canonical JSON
- SHA-256 integrity/checksum
- invalid container rejected
- wrong kind rejected
- missing action rejected
- invalid action rejected

Dedicated COMMAND test coverage:

**8 tests pass**

---

## 4. AGX1:A — internal action layer

File:

`protocol/MSGv1.py`

Format:

`AGX1:A:<base64url(canonical-json)>:<sha256>`

ACTION is the internal Gateway → Executor layer.

Metadata includes:

- version
- kind
- message_id
- command_id
- session_id
- timestamp
- nonce
- sequence
- action
- args

Protection:

- canonical JSON
- base64url
- SHA-256 integrity
- maximum age: 300 seconds
- maximum future skew: 30 seconds

Do not weaken these freshness/integrity checks.

---

## 5. AGX1:R — result

Format:

`AGX1:R:<base64url(canonical-json)>:<hmac-sha256>`

RESULT protection:

- HMAC-SHA256 authentication/integrity at the protocol layer
- persistent Ed25519 signing at the gateway/browser-facing layer

File:

`gateway/signing.py`

Browser Bridge verifies the returned Ed25519 signature.

The browser private signing key must never be exported.

---

## 6. Gateway / Executor / PC Agent

Main files:

- `gateway/gateway.py`
- `gateway/executor.py`
- `gateway/server.py`
- `pc_agent/agent.py`

Gateway policy modes:

- ALLOW
- CONFIRM
- DENY

Replay protection:

- persistent SQLite
- reservation key: `session_id + message_id`
- survives Gateway restart

PC Agent currently supports:

- `system.info`
- `files.list`
- `app.open`

External executable handling:

- uses `shutil.which()`
- missing required external components must produce an explicit install/PATH message
- never silently fail just because a dependency/component is absent

This dependency-check rule applies to every new external component added to the project.

---

## 7. Browser Authentication

Files:

- `gateway/browser_auth.py`
- `browser_bridge/extension/browser_keys.js`
- `browser_bridge/extension/background.js`

Mechanism:

- Ed25519 challenge-response
- browser private key stored in IndexedDB
- private key is non-extractable
- challenges are one-time
- invalid signatures do not consume the challenge
- tampered request body is rejected
- multiple browser keys are supported

Gateway:

`http://127.0.0.1:8765`

Challenge:

`/v1/auth/challenge`

---

## 8. HTTP API

GET:

- `/v1/health`
- `/v1/auth/challenge`

POST:

- `/v1/pair`
- `/v1/action`
- `/v1/command`
- `/v1/confirm`
- `/v1/cancel`

Current `/v1/command` flow:

1. receive JSON containing C
2. decode AGX1:C
3. create fresh internal AGX1:A
4. apply gateway policy/replay protections
5. execute through Executor/PC Agent
6. create AGX1:R
7. return RESULT
8. return Ed25519 signature separately
9. return confirmation token when policy requires confirmation

Verified HTTP integration:

- valid C → HTTP 200
- tampered C → HTTP 409
- valid C produced an authenticated/signed RESULT
- `system.info` executed successfully

---

## 9. Audit logging

Files:

- `gateway/audit.py`
- `gateway/audit.jsonl`

Audit logging is integrated end-to-end.

Typical events:

- `action_received`
- `action_result`

Important privacy/security rule:

**Audit records do not store action args or result payloads.**

Already tested:

- JSONL validity
- rotation
- concurrent writes
- sensitive argument exclusion
- HTTP/executor lifecycle logging

Do not add raw command arguments/results to the audit log without an explicit security decision.

---

## 10. Browser Bridge

Extension directory:

`browser_bridge/extension`

Main files:

- `content.js`
- `background.js`
- `browser_keys.js`
- `popup.html`
- `popup.js`
- `manifest.json`

Other relevant files include:

- `agx_extractor.js`
- `result_public_key.js`
- backup copies of earlier `content.js`

Manifest:

- MV3
- permissions: storage, tabs, scripting
- host permissions: `<all_urls>` and `http://127.0.0.1:8765/*`
- background service worker: `background.js`
- popup: `popup.html`
- content script: `content.js` at `document_idle`

Bridge behavior already implemented:

- reads rendered DOM / `document.body.innerText`
- MutationObserver tracks DOM changes
- recognizes AGX1:A and AGX1:C
- duplicate commands are suppressed
- result can be inserted into the chat composer
- command panel supports resize
- command panel supports drag
- command history exists
- day/night theme exists
- confirmation UI exists
- panel is hidden after tab load
- Bridge state is separate per tab
- parser runs only while Bridge is enabled
- panel has X close button
- Alt+Shift+A toggles Bridge
- popup provides ON/OFF
- popup uses a tooltip for the shortcut information

Static checks previously verified:

- `NODE_CHECK=OK`
- `BRIDGE_FUNCTIONS=True`
- `PARSER_GUARD=True`
- `CLOSE_BUTTON=True`

The extension is already installed and loaded in the user's **Brave** browser. Do **not** ask the user to reinstall it as a first response.

The project name says Edge Browser Bridge, but the current real-world E2E test is being performed in **Brave/Chromium**.

---

## 11. Critical current E2E finding

The first real rendered-chat E2E has already succeeded through the complete execution path.

A valid AGX1:C was manually pasted into a new ChatGPT chat in Brave:

`AGX1:C:eyJhY3Rpb24iOiJzeXN0ZW0uaW5mbyIsImFyZ3MiOnt9fQ:09c5efa7890894ff4b634cf06c6bc3c52eee0227b33e5eb9ab818f9bf930ad20`

Observed behavior:

1. Bridge detected the C in the rendered DOM.
2. Bridge authenticated the request to Gateway.
3. Gateway accepted C.
4. Gateway created internal A.
5. Executor executed `system.info`.
6. Gateway returned AGX1:R plus Ed25519 signature.
7. Bridge accepted the returned result.
8. Bridge inserted the AGX1:R into the ChatGPT composer.

The returned RESULT decoded successfully to status `ok` with Windows system information.

### What is NOT finished

The Bridge **did not press Enter automatically** after inserting the RESULT.

Therefore the current real-world chain is:

**AI/DOM C → execute → R → composer**

but not yet:

**AI/DOM C → execute → R → composer → automatic send**

This is the current primary browser-side bug/unfinished behavior.

Do not treat this as a backend problem. The backend C/A/R chain is already proven.

---

## 12. Required final E2E behavior

The intended behavior is now explicit:

> When the rendered AI chat contains a valid AGX1:C, Browser Bridge parses it, executes it, inserts the resulting AGX1:R into the chat composer, and automatically presses Enter to send it.

The Bridge must distinguish its own generated/sent result from ordinary user input so that automatic sending does not cause:

- self-reprocessing
- duplicate execution
- command/result loops
- accidental repeated parsing of its own generated RESULT

A suitable internal flag/guard may be introduced in the browser layer, but it must be kept local to the Bridge and must not weaken protocol/security boundaries.

The exact DOM send mechanism should be adapted to the current ChatGPT/Chromium composer instead of assuming a generic selector will always work.

---

## 13. Very important next E2E test instruction

Do **not** ask the user to manually paste AGX1:C for the final test once the automatic-Enter fix is ready.

The intended real test is:

1. Start a new test chat in Brave.
2. Ask the test AI itself to write a valid AGX1:C into the rendered chat.
3. Browser Bridge should detect that AI-generated C.
4. Bridge should execute it.
5. Bridge should insert the signed R.
6. Bridge should automatically press Enter.
7. The chat should receive/send the result.
8. Verify there is no execution loop or duplicate execution.

When this test is ready to run, explicitly tell the user to **ask a test AI chat to write AGX1:C**.

Do not prematurely ask for this before the automatic-submit code path is ready.

---

## 14. Current test status

Full Python test suite:

**83 tests — OK**

Last known full run:

`Ran 89 tests in 7.732s`

`OK`

Recent COMMAND tests:

`tests/test_command.py`

8 tests covering:

- roundtrip
- Unicode/nested args
- tamper detection
- invalid container
- wrong kind
- invalid action
- missing action
- args must be object

Recent server tests:

`tests/test_server.py`

- `test_command_endpoint`
- `test_command_endpoint_rejects_tampered_container`

Integration:

- valid C → HTTP 200
- tampered C → HTTP 409

---

## 15. Doctor status snapshot

Last verified:

**DOCTOR: PASS**

Checks that passed:

- Python 3.12.10
- cryptography 50.0.1
- Gateway process was running
- 127.0.0.1:8765 listening
- health OK
- Browser Auth paired/enabled
- auth challenge available
- result signing key present
- browser auth key present
- replay database present
- audit log valid JSONL
- autostart task Ready
- browser extension files present
- JavaScript syntax checks
- Python compilation
- 89 tests OK

Doctor command:

`ops\doctor.ps1`

Important:

- PID and transient runtime values are snapshots and may change after restart.
- Do not treat old PID values as required configuration.

Browser test page:

`http://127.0.0.1:8766/index.html`

At the beginning of the current E2E phase, port 8766 was **not listening**. Do not assume the test page is currently available without checking.

---

## 16. Security invariants — DO NOT BREAK

Do not weaken or bypass these without an explicit design decision:

- rendered DOM is the authoritative command source
- direct AI API is not the primary command transport
- AGX1:C remains neutral
- ACTION integrity uses SHA-256
- RESULT protocol authentication/integrity uses HMAC-SHA256
- browser-facing RESULT uses persistent Ed25519 signing
- replay protection is persistent
- CONFIRM never executes before confirmation
- DENY never executes
- audit excludes args/result payloads
- browser private signing key is never exported
- Browser Auth challenges are one-time
- tampered request body/container is rejected
- external components are checked before use

---

## 17. Known history / pitfalls

Previously fixed issues:

1. A PowerShell patch inserted a literal line-ending escape sequence into JavaScript and broke `content.js`. This was fixed.
2. `openCommandPanel()`, `closeCommandPanel()`, and `toggleCommandPanel()` were previously missing and were added.
3. Browser Bridge control/panel behavior was refined and verified by static checks.

Avoid large blind PowerShell text replacements in JavaScript. Prefer targeted edits with immediate syntax/test validation.

---

## 18. Development/testing workflow

User preferences:

- Work in Python unless a browser extension file must be changed.
- Prefer **one self-contained PowerShell command at a time**.
- Whenever possible, copy command output to Windows Clipboard.
- Keep responses/diagnostics compact; do not dump huge outputs unnecessarily.
- Check every external dependency/component before using it.
- If a required component is missing, explicitly offer installation instead of silently failing.
- Add/update tests after meaningful code changes.
- Run the full suite after runtime-affecting changes.
- Run Doctor after runtime-affecting changes.
- Update this HANDOFF after every meaningful project stage.

---

## 19. Browser Bridge auto-submit + universal chat discovery

The previous real Brave E2E proved:

**rendered AGX1:C → Bridge → Gateway → execution → signed AGX1:R → Bridge → composer**

The observed problem was that the RESULT was inserted into the composer but was not reliably submitted.

Commit `732c7e81feda2307b6e5b78c6ef56bd75fcdf3fc` added Browser Bridge result auto-submit hardening:

- direct send-button selectors before broad heuristics
- bounded retry while the send control becomes ready
- Bridge-generated composer marker
- guard against reprocessing Bridge-generated text
- verification that the composer still contains the exact RESULT before sending

The earlier auto-submit hardening was syntax-checked and the full Python suite passed before the universal discovery changes. The universal discovery changes below still require local browser verification.

### Universal chat discovery mode

The requested design is now implemented in three pieces:

- `browser_bridge/extension/content.js`
- `browser_bridge/extension/popup.html`
- `browser_bridge/extension/popup.js`
- `tests/test_browser_discovery.py`

The popup now contains a discovery card with:

- generated phrase: `ИИ сколько будет <7-digit X> умножить на <7-digit Y>`
- `Копировать` button
- round listening control shown as a simple circle
- states `Покой` and `Слушает`

Discovery protocol messages:

- `AGX_CHAT_DISCOVERY_START`
- `AGX_CHAT_DISCOVERY_STOP`
- `AGX_CHAT_DISCOVERY_STATE`

Discovery sequence:

1. Popup generates a fresh phrase with two seven-digit numbers.
2. User presses the circle button; state becomes `Слушает`.
3. User copies/inserts the phrase into the real chat composer.
4. Content script observes the actual input event and records the real composer element.
5. User presses the real send button.
6. Content script records the actual clicked button associated with that composer.
7. MutationObserver waits for the same phrase to appear as rendered chat text outside the composer.
8. The message element is recorded.
9. Selectors/fingerprints for composer, send button, and message are saved in page-origin `localStorage` under `agentChataiChatDiscovery`.
10. Discovery state becomes `complete` and `agentChataiChatDiscoveryReady=1`.

Normal `findChatComposer()` and `findChatSubmitButton()` now prefer learned selectors before generic heuristics.

This is intentionally site-agnostic: it learns from the real DOM interaction rather than hard-coding ChatGPT/Qwen/etc. selectors.

**Important:** the universal discovery implementation is currently **code-complete but not yet browser-verified** in Brave after the latest changes.



### Latest browser-discovery fix

Commit `87b3b395de297c0520b76fd154e9463a3c85ea68` improves discovery of the user's sent test phrase. The previous implementation required the entire parent DOM block to equal the phrase, which can fail in real chat UIs because the message container may include metadata or child nodes. The new implementation searches visible DOM elements for an exact normalized text match and chooses the most specific candidate.

After this fix the local suite was run again:

- **89 tests, OK**
- Browser discovery static tests included
- No backend changes

The browser-side behavior still needs real Brave verification.

### Latest verified backend/runtime checkpoint

After the universal discovery implementation:

- full Python suite: **89 tests, OK**
- Doctor: **DOCTOR: PASS**
- JavaScript syntax: PASS
- Python compilation: PASS
- Gateway health: PASS
- Browser Auth: paired/enabled
- RESULT signing key: present
- Replay database: present
- Audit JSONL: valid

Latest related commits:

- `732c7e81feda2307b6e5b78c6ef56bd75fcdf3fc` — auto-submit hardening
- `d61ff3149c086eefb669c1b06c332d3625ec9d60` — universal chat discovery in content.js
- `6bdc4bbeb4f0275e0e49efe1f7a30d839dad090` — discovery UI in popup.html
- `5181c3d0006c42a8185ad8dc1fb936d3c1414366` — discovery logic in popup.js
- `c43a7ffa5629ab102727bc391127faf9d626edaf` — six static discovery tests
- `bd71c9a66f72ae4df250f4f64075c9d79c5353f0` — fixed discovery UI static test
- `ec5946a52ebf8232de41ddab2fcd876f486f7a0f` — HANDOFF checkpoint
- `bbdc72cc75fd6af82ce7463be4456e24bfda1352` — HANDOFF verification-status correction

Current GitHub HEAD is later than the above intermediate commits; local `git pull --ff-only` was already confirmed up to date before the latest test run.

## 20. Current project point — START HERE

Backend/protocol/security are already in a verified state:

**89/89 tests + DOCTOR: PASS**

The most important already-proven path is:

**AGX1:C → /v1/command → AGX1:A → Executor → AGX1:R → Ed25519 signature**

The first real Brave/Chromium DOM E2E has also proven:

**rendered C → Bridge → Gateway → execution → signed R → Bridge → composer**

### The one immediate unfinished item

**Fix Browser Bridge so that after inserting AGX1:R into the chat composer, it automatically sends the message by pressing Enter/correctly invoking the site's send action, while preventing the Bridge from reprocessing its own generated message.**

Do not redesign the backend.

After that fix:

- add/adjust browser-side tests or static checks as appropriate
- run full tests
- run Doctor
- update HANDOFF again
- then perform the true AI-generated-C E2E test in Brave

---

## 21. Next verification stage

Before changing backend code, perform the browser-side verification:

1. `git pull` locally so the new commits are present.
2. Run the full test suite.
3. Run Doctor.
4. Reload the unpacked extension in Brave and reload the ChatGPT tab.
5. Click the extension icon and verify the new discovery card is visible.
6. Click the circle so it shows `Слушает`.
7. Click `Копировать` and paste the generated phrase into the ChatGPT composer.
8. Press the chat site's real Send button.
9. Verify the state reaches `Готово` and that composer/send/message selectors were learned.
10. Then send a real AI-generated `AGX1:C` and verify the full chain including automatic RESULT submission.

For the final AI-generated-command test, the user should ask a test AI chat to write the `AGX1:C`; do not manually paste the command yourself.

## 22. Instructions for the next AI

1. Read this file first.
2. Continue from section 19.
3. Do not repeat already-proven backend work without a specific reason.
4. Inspect the existing `content.js` send/composer logic before modifying it.
5. Make the smallest safe browser-side change that enables automatic submission.
6. Add a loop/reprocessing guard for Bridge-generated messages/results.
7. Preserve all security invariants.
8. Test the change.
9. Run full suite + Doctor.
10. Update HANDOFF.md again after the stage is complete.
11. When the real AI-generated-command test is ready, ask the user to have a test AI chat write AGX1:C into the rendered chat.
12. Prefer one self-contained PowerShell command per step and copy output to clipboard when possible.

**Continuity rule: this HANDOFF is the first document to read after context loss.**
