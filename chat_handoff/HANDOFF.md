# HANDOFF.md — AI chat command rules

This document is for the AI model used in a new browser chat with Agent ChatAI Bridge.

It is NOT the development handoff for the Agent_ChatAi project.

## 1. Session

At the beginning of the chat, the user may provide the current Bridge `session_id`.

- Treat the supplied `session_id` as the session identifier for this chat.
- Keep using exactly that `session_id` in every new `AGX1:C`.
- If the user later supplies a new `session_id`, use the new one from that point onward.
- If the session_id is forgotten, ask the user to copy it from the Agent ChatAI Bridge popup.
- Never invent a different session_id when the user has already supplied one.

## 2. AGX1:C command format

When a PC action is needed, output a valid `AGX1:C` container in the rendered chat.

The decoded JSON payload MUST contain these fields:

```json
{
  "session_id": "<current Bridge tab session_id>",
  "message_id": "<new unique message_id>",
  "action": "<action name>",
  "args": {},
  "timestamp": 1770000000.0,
  "ttl": 30
}
```

- `timestamp` is the Unix time when the AI creates the command.
- `ttl` is the number of seconds the AI estimates are needed for delivery and processing.
- Calculate a reasonable `ttl` for the expected chat/browser delay; do not use an unnecessarily large value.
- Gateway enforces an absolute maximum `MAX_COMMAND_LIFETIME`.
- If Gateway reports `COMMAND_TTL_EXCEEDED`, create a new command with a fresh `timestamp` and a `ttl` not exceeding the reported maximum.
- A command with an expired `timestamp + ttl` is not executed.
- A command from another browser tab/session is not executed.

The container format is:

```
AGX1:C:<base64url(canonical-json)>:<sha256>
```

The SHA-256 value is calculated over:

```
C:<base64url-payload>
```

Use canonical JSON: UTF-8, sorted object keys, no insignificant whitespace.

## 3. message_id

The AI generates `message_id` itself.

- Generate a new unique 32-character hexadecimal `message_id` for every new `AGX1:C`.
- Never reuse a previous `message_id` for a different command.
- Do not ask the Bridge to generate `message_id`.

## 4. session_id vs message_id

- `session_id` identifies the current Bridge/chat session.
- `message_id` identifies one particular command message.
- The user can provide the same `session_id` again if the AI loses context.
- Each new command still requires a new `message_id`.

## 5. Secret keys

NEVER put a private or secret signing key into `AGX1:C`.

`session_id` and `message_id` are identifiers, not secrets.

Browser authentication is handled separately by the Agent ChatAI Bridge Browser Key. The private Browser Key must never be requested from or exposed by the AI.

## 6. Normal response + command

When a PC action is requested, the response should contain:

1. A short natural-language message explaining what is being done.
2. The `AGX1:C` command container.

The command container must be present in the rendered chat exactly as generated. Do not alter, quote, escape, or wrap the container in Markdown code fences when the Bridge is expected to detect it.

If there are multiple independent PC actions, multiple `AGX1:C` containers may be emitted, each with its own new `message_id`.

## 7. Result handling

After execution, the Bridge may return an `AGX1:R` result in the chat.

Treat the returned result as the result of the corresponding command. Use its `session_id` and `message_id` for correlation when available.

Do not generate a new command merely because an `AGX1:R` appeared. Generate another command only when the conversation actually requires another PC action.

## 8. Startup procedure for a new chat

At the beginning of a new chat:

1. Read this HANDOFF document.
2. Receive the current `session_id` from the user/Bridge.
3. Remember that `session_id` for this chat.
4. For every new PC command, generate a fresh `message_id`.
5. Generate `AGX1:C` according to these rules.

The project-development `HANDOFF.md` from the Agent_ChatAi repository is a separate document and must not be treated as the command-format instructions for the AI chat.
