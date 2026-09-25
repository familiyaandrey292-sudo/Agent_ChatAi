# HANDOFF.md — Agent ChatAI Gateway + Edge Browser Bridge

## Project
Root: `C:\Proj\Agents\Agent_ChatAI`

Цель: универсальный мост AI через браузерный DOM к локальному ПК. Команды извлекаются из отображённого DOM, а не только через прямой API AI.

## Архитектура

`AI chat DOM → AGX1:C → Browser Bridge → /v1/command → Gateway → AGX1:A → Executor → PC Agent → AGX1:R → Browser Bridge → chat`

### AGX1:C — COMMAND
Команда от AI/DOM:
- `version`
- `kind=command`
- `command_id`
- `session_id`
- `issued_at`
- `sequence`
- `action`
- `args`

Целостность: SHA-256 checksum.

### AGX1:A — ACTION
Внутренний слой между Gateway и Executor. Оставлен для возможного будущего разделения процессов/серверов.

### AGX1:R — RESULT
Результат выполнения. Подписывается HMAC.

## Безопасность

- Повторное выполнение: `command_id` + persistent replay protection.
- Свежесть: `issued_at`, но это не общий execution timeout.
- Авторизация: `ALLOW / CONFIRM / DENY`.
- RESULT защищён HMAC.
- ChatGPT-specific DOM roles не используются как граница безопасности.
- `nonce` пока не имеет отдельной обязательной роли.

## Gateway

Адрес: `http://127.0.0.1:8765`

Health: `/v1/health`

Состояние:
- Browser Auth: paired/enabled
- Ed25519 browser authentication: работает
- Replay protection: SQLite, retention 900 секунд
- Audit logging: работает
- RESULT signing: работает

Audit события не содержат `args` и `result`.

## Browser Bridge

Текущий браузер: Brave.

- `AGX1:C` извлекается из `document.body.innerText`
- MutationObserver отслеживает изменения DOM
- Дубли команд подавляются
- RESULT автоматически вставляется в чат и отправляется
- Панель поддерживает resize, drag, сохранение позиции/размера
- Есть day/night theme
- Есть history последних команд

## Управление Bridge

Требуемое поведение:

1. Панель не появляется автоматически после загрузки вкладки.
2. Состояние Bridge отдельно для каждой вкладки.
3. Парсер работает только когда Bridge включён.
4. На панели есть `×`.
5. `Alt+Shift+A` переключает Bridge.
6. В popup есть ON/OFF переключатель.
7. Надпись `Alt+Shift+A` в popup заменена tooltip.

Последняя проверка `content.js`:

- `NODE_CHECK=OK`
- `BRIDGE_FUNCTIONS=True`
- `PARSER_GUARD=True`
- `CLOSE_BUTTON=True`

## Важная история исправлений

В одном из патчей в JavaScript случайно попала литеральная строка `` `r`n `` из PowerShell. Это ломало выполнение `content.js`. Ошибка исправлена.

Также отсутствовали:
- `openCommandPanel()`
- `closeCommandPanel()`
- `toggleCommandPanel()`

Они добавлены.

## Следующая точка проверки

После перезагрузки расширения и вкладки проверить:

- после reload панель скрыта;
- `Alt+Shift+A` открывает панель;
- `×` закрывает панель;
- popup ON открывает Bridge;
- popup OFF закрывает Bridge;
- при OFF `AGX1:C` не обрабатывается.

## Основные файлы

- `protocol\MSGv1.py`
- `protocol\command.py`
- `gateway\gateway.py`
- `gateway\executor.py`
- `gateway\server.py`
- `gateway\pairing.py`
- `gateway\browser_auth.py`
- `pc_agent\agent.py`
- `browser_bridge\extension\content.js`
- `browser_bridge\extension\background.js`
- `browser_bridge\extension\browser_keys.js`
- `browser_bridge\extension\popup.html`
- `browser_bridge\extension\popup.js`

## Инварианты корреляции

`C.command_id == A.command_id == R.command_id`

`C.session_id == A.session_id == R.session_id`

`C.issued_at == A.issued_at == R.issued_at`

`C.sequence == A.sequence == R.sequence`

## Текущая стратегия

Не переделывать протокол целиком. Сначала довести существующую цепочку `C → A → R` до рабочей версии.
