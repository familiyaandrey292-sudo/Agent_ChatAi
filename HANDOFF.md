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

**103/103 tests — OK**

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

### Normal-size result

When a PowerShell command produces a result that fits safely in the chat/Clipboard transfer:

1. Show the result in the console.
2. Copy the **same complete result** to Windows Clipboard.
3. The user can paste that result directly into the chat.

### Large result

When the result is too large to return directly:

1. Do **not** put the huge result into the chat.
2. Save the **complete original result** to:

`C:\Proj\Agents\Agent_ChatAi\Buffer-drops\latest.txt`

3. The local `Buffer-drops` directory must be a Git repository connected to:

`https://github.com/familiyaandrey292-sudo/Buffer-drops.git`

4. Push `latest.txt` through normal local Git:

`git add → git commit → git push`

5. Only after **successful `git push`** copy this exact single line to Windows Clipboard:

`GitHub Buffer-drops\latest.txt`

**IMPORTANT: the required Clipboard marker is exactly `GitHub Buffer-drops\latest.txt`. Never use `GitHub Nickname Buffer-drops\latest.txt`, never substitute a nickname, and never use any other marker.**

6. Do not put any error, diagnostic text, commit message, Git output, or other text in Clipboard after successful push.

### Failure handling

If `git add`, `git commit`, or `git push` fails:

- **never** copy `GitHub Buffer-drops\latest.txt` to Clipboard;
- keep the complete result in local `latest.txt`;
- report the Git failure separately;
- do not claim that the result is available on GitHub.

### Important distinction

The large-result mechanism is **not** a manual GitHub API upload. It is a local PowerShell → local Git repository → normal git add/commit/push workflow.

A pasted Clipboard value of exactly:

`GitHub Buffer-drops\latest.txt`

means that the complete result was too large for direct transfer and was successfully pushed to the GitHub `Buffer-drops` repository at `latest.txt`.

### Test reference

A successful test produced:

- commit: `d59d415`
- push: `620e588..d59d415 main -> main`
- `latest.txt`: 100,000 generated lines
- Clipboard: exactly `GitHub Buffer-drops\latest.txt`

This confirms the intended large-result workflow.

### Command construction requirement

When giving a PowerShell command whose result may exceed the safe transfer size, the command itself must implement the decision:

**generate/collect result → measure size → either Clipboard full result OR Buffer-drops + Git push + exact pointer**

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
