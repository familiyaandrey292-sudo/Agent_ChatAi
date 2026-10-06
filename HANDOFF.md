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

Primary goal:

> Universal bridge from an AI chat page, using the **rendered browser DOM as the authoritative command source**, to the local Windows PC.

Direct AI APIs are **not** the primary command transport.

---

## 2. Core architecture

Verified architecture:

**AI chat rendered DOM → AGX1:C → Browser Bridge → /v1/command → Gateway → AGX1:A → Executor → PC Agent → AGX1:R → Browser Bridge → chat**

Important:

- The browser DOM is authoritative.
- Browser Bridge parses rendered chat content.
- AGX1:C is the neutral upper-level command container.
- Do not redesign proven backend/security flow for local browser issues.

---

## 3. Security and runtime invariants

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

External executable handling uses `shutil.which()`; missing required components must produce an explicit install/PATH message.

---

## 4. Current verified project point

Backend/protocol/security are in a verified state.

Current local validation checkpoint:

**Последний подтверждённый checkpoint: 116/116 tests on Windows — OK, DOCTOR: PASS**

The per-tab AGX1:C sessions and TTL/timestamp validation change set (stage 5A) is now VERIFIED:

- Windows full suite: 116 tests, OK.
- ops/doctor.ps1 on Windows: all 16 checks PASS (Python, cryptography, Gateway process/port, health, browser auth pairing, challenge, signing keys, replay DB, audit JSONL, autostart task, extension files, JS syntax, Python compilation, test suite).
- Linux CI run: 121 passed / 4 failed; the 4 failures are platform-only assertions (`'Linux' != 'Windows'` in test_agent/test_executor/test_server system.info checks), not regressions.

**DOCTOR: PASS**

The proven backend path is:

**AGX1:C → /v1/command → AGX1:A → Executor → AGX1:R → Ed25519 signature**

The first real Brave/Chromium DOM E2E has also proven:

**rendered C → Bridge → Gateway → execution → signed R → Bridge → composer**

Universal Browser Discovery has been manually verified in Brave on:
- DeepSeek: discovery reached `Кнопка найдена`
- Claude: discovery reached `Готово`
- Qwen: discovery reached `Готово`

Next project stage is the true AI-generated AGX1:C E2E.

---

## 5A. AGX1:C session and freshness rules — VERIFIED

- session_id is per browser tab, not global to the extension.
- Browser Bridge stores a tab session by tabId; popup displays the session of the currently active tab.
- /v1/command receives both container and authenticated session_id.
- Gateway requires the request session_id to equal the decoded AGX1:C session_id.
- AGX1:C now contains timestamp and ttl.
- AI calculates ttl as the expected delivery/processing allowance.
- Gateway enforces MAX_COMMAND_LIFETIME = 300 seconds and does not silently clamp TTL.
- If TTL exceeds the maximum, Gateway returns COMMAND_TTL_EXCEEDED with requested_ttl and max_ttl.
- Expired or future AGX1:C commands are rejected.
- Retryable command validation errors are sent back into the rendered chat so the AI can regenerate the command.
- Different session_id values remain independent; Gateway/replay protection must not serialize them into one global session.

Verification status: confirmed on Windows (116 tests OK + DOCTOR PASS). Command-level error contract observed in E2E tests: all command rejections return HTTP 409 with `error=command_rejected` and a machine-readable `code` (COMMAND_INVALID / COMMAND_TTL_EXCEEDED / COMMAND_SESSION_MISMATCH) plus `retryable` flag.

## 5B. True AI-generated AGX1:C E2E — automated part DONE, live chat part PENDING

New suite: `tests/test_e2e_ai_command.py` (9 tests, all passing locally) simulates the full AI pipeline:

1. AI-style free-form reply (prose + markdown fences + inline code, Russian text) containing an AGX1:C container.
2. Extraction via the exact content.js regex mirror (`AGX1:C:[A-Za-z0-9_-]+:[A-Fa-f0-9]{64}`), byte-identical containers, dedupe, truncated containers not extracted.
3. POST to live Gateway `/v1/command` with per-tab session_id → execution → signed AGX1:R result verified with HMAC.
4. Realistic AI failure modes rejected by Gateway: hallucinated integrity tag, tampered payload with stale tag, stale timestamp (COMMAND_EXPIRED), ttl > MAX (COMMAND_TTL_EXCEEDED, retryable), wrong tab session (COMMAND_SESSION_MISMATCH, retryable), action outside allowlist (structured non-ok result).

Remaining for stage closure — live manual E2E in Brave/Chromium with a real test AI chat:
- the test AI must generate AGX1:C into the rendered chat (no manual paste);
- verify execution succeeds, signed RESULT is inserted and auto-submitted;
- verify no self-reprocessing, no duplicate execution, no command/result loop.

Live E2E attempt #1 (user report): the parallel-chat AI emitted an AGX1:C that was silently ignored by the Bridge. Root cause analysis (verified by decoding the container):
- payload had only session_id/message_id/action/args — missing required timestamp and ttl (old pre-5A schema);
- message_id was "msg_002" instead of 32 hex chars;
- integrity tag was 16 hex chars instead of 64 and did not match SHA-256("C:"+payload) at all (hallucinated);
- JSON was non-canonical (chat field order, not sorted keys).
Because the tag length failed content.js AGX_COMMAND_PATTERN ({64}), extraction never happened: no Gateway request, no AGX1:R, no visible error. This matches E2E failure-mode coverage in tests/test_e2e_ai_command.py.

Process issue found and fixed: two AI handoff docs existed — root AI_CHAT_HANDOFF.md (Russian, OLD 4-field schema, "<integrity>" wording) and chat_handoff/HANDOFF.md (English, current 6-field schema). The parallel chat followed AI_CHAT_HANDOFF.md literally and produced a valid-per-that-doc but rejected command. AI_CHAT_HANDOFF.md has been updated to the current contract (timestamp/ttl, 32-hex message_id, full 64-hex sha256 over "C:"+b64url, canonical sorted-key JSON). Action item: keep a single source of truth for AI chat rules or explicitly deprecate one of the files.

Usability follow-up (open): containers that fail the envelope regex are invisible to the user. Consider a heuristic warning in content.js (e.g., text matching AGX1:C:[A-Za-z0-9_-]+:[A-Fa-f0-9]{8,63}) shown as a status notice so malformed AI commands surface instead of being silently dropped.
## 5. Browser Bridge current next step

The intended final behavior is:

**AI-generated rendered AGX1:C → Bridge parses → Gateway executes → signed AGX1:R → Bridge inserts result → Bridge automatically submits result**

The test AI must generate AGX1:C into the rendered chat. Do not manually paste the AGX1:C for the final E2E.

Verify:
- execution succeeds
- signed RESULT is inserted
- RESULT is automatically submitted
- no self-reprocessing
- no duplicate execution
- no command/result loop

---

## 6. Development/testing workflow

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

## 7. PowerShell output / Clipboard / Buffer-drops rule — 2026-09-26

This rule is mandatory for future PowerShell diagnostic and test commands.

### Special Buffer-drops marker

**IMPORTANT: `GitHub Nikname Buffer-drops\\latest.txt` is a special marker.**

If this exact string is received, it means:

> Get and read `latest.txt` at `GitHub\\имя пользователя (на GitHub)\\Buffer-drops\\latest.txt`.

`Nikname` in the marker is **literal text**. Do not replace, remove, or reinterpret it.

### Normal-size result

When a PowerShell command produces a result that fits safely in the chat/Clipboard transfer:

1. Show the result in the console.
2. Copy the **same complete result** to Windows Clipboard.
3. The user can paste that result directly into the chat.

### Large result

When the result is too large to return directly:

1. Do **not** put the huge result into the chat.
2. Save the **complete original result** to:

`C:\Proj\Agents\Buffer-drops\latest.txt`

3. This directory is the local Git repository for the user's GitHub project **Buffer-drops**.
4. Push `latest.txt` through normal local Git:

`git add → git commit → git push`

5. Only after **successful `git push`** copy this exact single line to Windows Clipboard:

`GitHub Nikname Buffer-drops\\latest.txt`

6. Do not put any error, diagnostic text, commit message, Git output, or other text in Clipboard after successful push.

### Failure handling

If `git add`, `git commit`, or `git push` fails:

- **never** copy the marker to Clipboard;
- keep the complete result in local `latest.txt`;
- report the Git failure separately;
- do not claim that the result is available on GitHub.

### Important distinction

The large-result mechanism is **not** a manual GitHub API upload. It is:

**local PowerShell → local Buffer-drops Git repository → git add/commit/push → exact Clipboard marker**

The marker means that the complete result was successfully pushed to the user's GitHub `Buffer-drops` repository at `latest.txt`.

### Command construction requirement

When giving a PowerShell command whose result may exceed the safe transfer size, the command itself must implement the decision:

**generate/collect result → measure size → either Clipboard full result OR Buffer-drops + Git push + exact marker**

Do not give a separate manual simulation of the GitHub upload when the purpose is to test the actual PowerShell result-handling mechanism.

---

## 8. Next AI instructions

1. Read this HANDOFF first.
2. Continue from the current project point.
3. Do not repeat proven backend work without a specific reason.
4. Inspect existing Browser Bridge logic before modifying it.
5. Make the smallest safe browser-side change needed.
6. Preserve all security invariants.
7. Add/update tests after meaningful changes.
8. Run full suite + Doctor after runtime-affecting changes.
9. For PowerShell commands, follow section 7 exactly.
10. Prefer one self-contained PowerShell command per step.
11. When the true AI-generated-command test is ready, ask the user to have a test AI chat write AGX1:C into the rendered chat.
12. Update HANDOFF after each meaningful project stage.

**Continuity rule: this HANDOFF is the first document to read after context loss.**
