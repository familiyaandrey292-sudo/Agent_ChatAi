"use strict";

chrome.runtime.onMessage.addListener(
    (message, sender, sendResponse) => {
        if (message?.type === "AGX_GET_BRIDGE_STATE") {
            sendResponse({
                ok: true,
                enabled: commandBridgeEnabled === true
            });
            return false;
        }

        if (message?.type === "AGX_SET_BRIDGE_STATE") {
            const enabled =
                message.enabled === true;

            if (enabled) {
                openCommandPanel();
            } else {
                closeCommandPanel();
            }

            sendResponse({
                ok: true,
                enabled: commandBridgeEnabled === true
            });

            return false;
        }
    }
);


document.documentElement.dataset.agentChataiBridge = "loaded";

const AGX_ACTION_PATTERN =
    /AGX1:A:[A-Za-z0-9_-]+:[A-Fa-f0-9]{64}/g;

const AGX_COMMAND_PATTERN =
    /AGX1:C:[A-Za-z0-9_-]+:[A-Fa-f0-9]{64}/g;
let lastCommandContainer = null;
let lastContainer = null;
let confirmationToken = null;
let confirmationBar = null;
let lastPublishedResult = null;
let bridgeGeneratedComposer = null;
const BRIDGE_SEND_RETRY_MS = 100;
const BRIDGE_SEND_MAX_ATTEMPTS = 25;

function extractActionContainers(text) {
    if (typeof text !== "string" || !text.length) {
        return [];
    }

    return [...new Set(
        text.match(AGX_ACTION_PATTERN) || []
    )];
}

function extractCommandContainers(text) {
    if (typeof text !== "string" || !text.length) {
        return [];
    }

    return [...new Set(
        text.match(AGX_COMMAND_PATTERN) || []
    )];
}
function removeConfirmationBar() {
    if (confirmationBar) {
        confirmationBar.remove();
        confirmationBar = null;
    }

    confirmationToken = null;

    document.documentElement.dataset
        .agentChataiConfirmationPending = "0";
}

function showConfirmationBar(response) {
    removeConfirmationBar();

    confirmationToken = response.confirmationToken;

    if (!confirmationToken) {
        return;
    }

    document.documentElement.dataset
        .agentChataiConfirmationPending = "1";

    const bar = document.createElement("div");

    bar.style.position = "fixed";
    bar.style.right = "20px";
    bar.style.bottom = "20px";
    bar.style.zIndex = "2147483647";
    bar.style.padding = "14px";
    bar.style.background = "#ffffff";
    bar.style.border = "1px solid #888";
    bar.style.borderRadius = "8px";
    bar.style.boxShadow = "0 4px 18px rgba(0,0,0,.2)";
    bar.style.fontFamily = "system-ui, sans-serif";
    bar.style.maxWidth = "360px";

    const title = document.createElement("div");
    title.textContent = "Action requires your confirmation";
    title.style.fontWeight = "600";
    title.style.marginBottom = "8px";

    const details = document.createElement("div");
    details.textContent =
        response.resultMessage ||
        "A local action is waiting for confirmation.";
    details.style.marginBottom = "12px";

    const confirm = document.createElement("button");
    confirm.textContent = "Confirm";
    confirm.style.marginRight = "8px";

    const cancel = document.createElement("button");
    cancel.textContent = "Cancel";

    cancel.addEventListener("click", () => {
        cancel.disabled = true;

        chrome.runtime.sendMessage(
            {
                type: "AGX_CANCEL_ACTION",
                confirmationToken
            },
            (result) => {
                if (chrome.runtime.lastError) {
                    document.documentElement.dataset
                        .agentChataiGatewayError =
                        chrome.runtime.lastError.message;
                    cancel.disabled = false;
                    return;
                }

                if (!result || !result.ok) {
                    document.documentElement.dataset
                        .agentChataiGatewayError =
                        result?.message ||
                        result?.error ||
                        "cancel_rejected";
                    cancel.disabled = false;
                    return;
                }

                document.documentElement.dataset
                    .agentChataiConfirmationPending =
                    "0";

                document.documentElement.dataset
                    .agentChataiConfirmationCancelled =
                    "1";

                removeConfirmationBar();
            }
        );
    });

    confirm.addEventListener("click", () => {
        confirm.disabled = true;
        cancel.disabled = true;
        confirm.textContent = "Confirming...";

        chrome.runtime.sendMessage(
            {
                type: "AGX_CONFIRM_ACTION",
                confirmationToken
            },
            (result) => {
                if (chrome.runtime.lastError) {
                    document.documentElement.dataset
                        .agentChataiGatewayError =
                        chrome.runtime.lastError.message;
                    confirm.disabled = false;
                    cancel.disabled = false;
                    confirm.textContent = "Confirm";
                    return;
                }

                if (!result || !result.ok) {
                    document.documentElement.dataset
                        .agentChataiGatewayError =
                        result?.message ||
                        result?.error ||
                        "confirmation_rejected";

                    confirm.disabled = false;
                    cancel.disabled = false;
                    confirm.textContent = "Confirm";
                    return;
                }

                document.documentElement.dataset
                    .agentChataiBackgroundAck = "1";

                document.documentElement.dataset
                    .agentChataiGatewayAck = "1";

                document.documentElement.dataset
                    .agentChataiSignatureVerified =
                        result.signatureVerified === true
                            ? "1"
                            : "0";

                document.documentElement.dataset
                    .agentChataiGatewayResult =
                        result.signatureVerified === true
                            ? "received"
                            : "rejected";

                document.documentElement.dataset
                    .agentChataiResultStatus =
                        result.resultStatus || "";

                document.documentElement.dataset
                    .agentChataiResultStatus =
                    result.resultStatus || "";

                if (result.signatureVerified === true && result.resultContainer) {
                    publishResultToChat(result.resultContainer);
                }

                document.documentElement.dataset
                    .agentChataiConfirmationPending = "0";

                removeConfirmationBar();
            }
        );
    });

    bar.appendChild(title);
    bar.appendChild(details);
    bar.appendChild(confirm);
    bar.appendChild(cancel);

    document.body.appendChild(bar);

    confirmationBar = bar;
}

function reportContainers(containers) {
    for (const container of containers) {
        if (container === lastContainer) {
            continue;
        }

        lastContainer = container;

        document.documentElement.dataset
            .agentChataiAgxFound = "1";

        chrome.runtime.sendMessage(
            {
                type: "AGX_ACTION_DETECTED",
                containers: [container]
            },
            (response) => {
                if (chrome.runtime.lastError) {
                    document.documentElement.dataset
                        .agentChataiGatewayError =
                        chrome.runtime.lastError.message;
                    return;
                }

                if (!response || !response.ok) {
                    document.documentElement.dataset
                        .agentChataiGatewayError =
                        response?.message ||
                        response?.error ||
                        "unknown_error";
                    return;
                }

                document.documentElement.dataset
                    .agentChataiBackgroundAck = "1";

                document.documentElement.dataset
                    .agentChataiGatewayAck = "1";

                document.documentElement.dataset
                    .agentChataiSignatureVerified =
                        response.signatureVerified === true
                            ? "1"
                            : "0";

                document.documentElement.dataset
                    .agentChataiGatewayResult =
                        response.signatureVerified === true
                            ? "received"
                            : "rejected";

                document.documentElement.dataset
                    .agentChataiResultStatus =
                    response.resultStatus || "";

                if (response.signatureVerified === true && response.resultContainer && !response.confirmationRequired) {
                    publishResultToChat(response.resultContainer);
                }

                if (
                    response.confirmationRequired &&
                    response.confirmationToken
                ) {
                    showConfirmationBar(response);
                }
            }
        );
    }
}

function isVisibleEditable(element) {
    if (!element || !document.documentElement.contains(element)) {
        return false;
    }

    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();

    return (
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        rect.width > 0 &&
        rect.height > 0 &&
        !element.disabled &&
        element.getAttribute("aria-hidden") !== "true"
    );
}

function editableScore(element) {
    let score = 0;
    const text = [
        element.getAttribute("aria-label") || "",
        element.getAttribute("placeholder") || "",
        element.getAttribute("name") || "",
        element.getAttribute("data-testid") || "",
        element.getAttribute("role") || ""
    ].join(" ").toLowerCase();

    if (element === document.activeElement) score += 100;
    if (element.matches('[contenteditable="true"]')) score += 40;
    if (element.matches("textarea")) score += 35;
    if (element.matches('input[type="text"]')) score += 20;
    if (element.matches('[role="textbox"]')) score += 20;

    if (/message|chat|prompt|reply|compose|ask|Р Р†Р Р†Р ВµР Т‘|РЎРѓР С•Р С•Р В±РЎвЂ°|Р В·Р В°Р С—РЎР‚Р С•РЎРѓ/.test(text)) {
        score += 35;
    }

    const rect = element.getBoundingClientRect();
    if (rect.bottom > window.innerHeight * 0.45) {
        score += 15;
    }

    return score;
}

function findChatComposer() {
    const candidates = [
        ...document.querySelectorAll(
            '[contenteditable="true"], textarea, input[type="text"], [role="textbox"]'
        )
    ].filter(isVisibleEditable);

    candidates.sort(
        (a, b) => editableScore(b) - editableScore(a)
    );

    return candidates[0] || null;
}

function setComposerText(element, text) {
    element.focus();

    if (
        element instanceof HTMLTextAreaElement ||
        element instanceof HTMLInputElement
    ) {
        const setter = Object.getOwnPropertyDescriptor(
            Object.getPrototypeOf(element),
            "value"
        )?.set;

        if (setter) {
            setter.call(element, text);
        } else {
            element.value = text;
        }

        element.dispatchEvent(
            new Event("input", { bubbles: true })
        );
        element.dispatchEvent(
            new Event("change", { bubbles: true })
        );
        return;
    }

    const selection = window.getSelection();
    const range = document.createRange();

    range.selectNodeContents(element);
    selection.removeAllRanges();
    selection.addRange(range);

    let inserted = false;

    try {
        inserted = document.execCommand(
            "insertText",
            false,
            text
        );
    } catch (_) {
        inserted = false;
    }

    if (!inserted) {
        element.replaceChildren(
            document.createTextNode(text)
        );
    }

    try {
        element.dispatchEvent(
            new InputEvent("input", {
                bubbles: true,
                inputType: "insertText",
                data: text
            })
        );
    } catch (_) {
        element.dispatchEvent(
            new Event("input", { bubbles: true })
        );
    }
}

function findChatSubmitButton(composer) {
    const directSelectors = [
        'button[data-testid="send-button"]',
        'button[aria-label*="Send"]',
        'button[aria-label*="send"]',
        'button[aria-label*="Отправ"]',
        'button[title*="Send"]',
        'button[title*="send"]'
    ];

    for (const selector of directSelectors) {
        const direct = document.querySelector(selector);

        if (direct && isVisibleEditable(direct)) {
            return direct;
        }
    }

    const form = composer.closest("form");

    if (form) {
        const submit = form.querySelector(
            'button[type="submit"], input[type="submit"]'
        );

        if (submit && isVisibleEditable(submit)) {
            return submit;
        }
    }

    const container =
        composer.closest("form") ||
        composer.parentElement?.parentElement ||
        document.body;

    const buttons = [
        ...container.querySelectorAll(
            'button, [role="button"], input[type="submit"]'
        )
    ].filter(
        (button) =>
            button !== composer &&
            !button.disabled &&
            isVisibleEditable(button)
    );

    const scored = buttons.map((button) => {
        const label = [
            button.getAttribute("aria-label") || "",
            button.getAttribute("title") || "",
            button.getAttribute("data-testid") || "",
            button.getAttribute("name") || "",
            button.textContent || ""
        ].join(" ").toLowerCase();

        let score = 0;
        if (/send|submit|ask|message|Р С•РЎвЂљР С—РЎР‚Р В°Р Р†|Р С—Р С•РЎРѓР В»Р В°РЎвЂљРЎРЉ|Р С•РЎвЂљР Р†Р ВµРЎвЂљР С‘РЎвЂљРЎРЉ/.test(label)) {
            score += 100;
        }

        const r = button.getBoundingClientRect();
        const c = composer.getBoundingClientRect();

        if (r.bottom >= c.top - 100 && r.top <= c.bottom + 100) {
            score += 25;
        }

        return { button, score };
    });

    scored.sort((a, b) => b.score - a.score);

    return scored[0]?.score >= 100
        ? scored[0].button
        : null;
}

function submitChatComposer(composer) {
    const button = findChatSubmitButton(composer);

    if (button) {
        button.click();
        return true;
    }

    const form = composer.closest("form");

    if (form && typeof form.requestSubmit === "function") {
        form.requestSubmit();
        return true;
    }

    for (const type of ["keydown", "keyup"]) {
        composer.dispatchEvent(
            new KeyboardEvent(type, {
                key: "Enter",
                code: "Enter",
                keyCode: 13,
                which: 13,
                bubbles: true,
                cancelable: true
            })
        );
    }

    return true;
}

function getComposerText(element) {
    if (
        element instanceof HTMLTextAreaElement ||
        element instanceof HTMLInputElement
    ) {
        return element.value || "";
    }

    return element.innerText || element.textContent || "";
}

function markBridgeGeneratedComposer(composer, text) {
    bridgeGeneratedComposer = {
        composer,
        text,
        expiresAt: Date.now() + 10000
    };

    composer.dataset.agentChataiBridgeGenerated = "1";
    document.documentElement.dataset.agentChataiBridgeGenerated = "1";
}

function clearBridgeGeneratedComposer(composer = null) {
    if (
        composer &&
        composer.dataset
    ) {
        delete composer.dataset.agentChataiBridgeGenerated;
    }

    if (
        !composer ||
        bridgeGeneratedComposer?.composer === composer
    ) {
        bridgeGeneratedComposer = null;
        delete document.documentElement.dataset.agentChataiBridgeGenerated;
    }
}

function bridgeOwnsComposerText(composer, expectedText) {
    const marker = bridgeGeneratedComposer;

    if (
        !marker ||
        marker.composer !== composer ||
        Date.now() > marker.expiresAt
    ) {
        return false;
    }

    return getComposerText(composer) === expectedText;
}

function submitPublishedResultWhenReady(
    composer,
    expectedText,
    attempt = 0
) {
    if (
        !bridgeOwnsComposerText(composer, expectedText)
    ) {
        document.documentElement.dataset.agentChataiChatOutput =
            "send_guard_failed";
        return false;
    }

    const currentComposer = findChatComposer();

    if (!currentComposer) {
        if (attempt < BRIDGE_SEND_MAX_ATTEMPTS) {
            window.setTimeout(
                () => submitPublishedResultWhenReady(
                    composer,
                    expectedText,
                    attempt + 1
                ),
                BRIDGE_SEND_RETRY_MS
            );
            return false;
        }

        document.documentElement.dataset.agentChataiChatOutput =
            "submit_failed";
        clearBridgeGeneratedComposer(composer);
        return false;
    }

    if (currentComposer !== composer) {
        if (
            getComposerText(currentComposer) === expectedText
        ) {
            composer = currentComposer;
            markBridgeGeneratedComposer(
                composer,
                expectedText
            );
        } else {
            document.documentElement.dataset.agentChataiChatOutput =
                "composer_changed";
            clearBridgeGeneratedComposer();
            return false;
        }
    }

    if (submitChatComposer(composer)) {
        document.documentElement.dataset.agentChataiChatOutput =
            "submitted";

        window.setTimeout(
            () => clearBridgeGeneratedComposer(composer),
            500
        );

        return true;
    }

    if (attempt < BRIDGE_SEND_MAX_ATTEMPTS) {
        window.setTimeout(
            () => submitPublishedResultWhenReady(
                composer,
                expectedText,
                attempt + 1
            ),
            BRIDGE_SEND_RETRY_MS
        );
        return false;
    }

    document.documentElement.dataset.agentChataiChatOutput =
        "submit_failed";
    clearBridgeGeneratedComposer(composer);
    return false;
}

function publishResultToChat(resultContainer) {
    if (
        typeof resultContainer !== "string" ||
        !resultContainer.startsWith("AGX1:R:") ||
        resultContainer === lastPublishedResult
    ) {
        return false;
    }

    const composer = findChatComposer();

    if (!composer) {
        document.documentElement.dataset.agentChataiChatOutput =
            "composer_not_found";
        return false;
    }

    lastPublishedResult = resultContainer;

    try {
        setComposerText(
            composer,
            resultContainer
        );

        markBridgeGeneratedComposer(
            composer,
            resultContainer
        );

        document.documentElement.dataset.agentChataiChatOutput =
            "inserted";

        window.setTimeout(
            () => submitPublishedResultWhenReady(
                composer,
                resultContainer
            ),
            BRIDGE_SEND_RETRY_MS
        );

        return true;
    } catch (error) {
        clearBridgeGeneratedComposer(composer);
        document.documentElement.dataset.agentChataiChatOutput =
            "error";

        console.error(
            "[Agent ChatAI Browser Bridge]",
            "chat result injection failed",
            error
        );

        return false;
    }
}

const COMMAND_STATUS_META = {
    running: {
        label: "Выполняется",
        color: "#2563eb"
    },
    done: {
        label: "Выполнено",
        color: "#15803d"
    },
    confirm: {
        label: "Ожидает подтверждения",
        color: "#b45309"
    },
    error: {
        label: "Ошибка",
        color: "#dc2626"
    }
};

const COMMAND_PANEL_HISTORY_KEY =
    "agentChataiCommandPanelHistory";

const COMMAND_PANEL_SIZE_KEY =
    "agentChataiCommandPanelSize";

let commandBridgeEnabled = false;
let commandPanel = null;
let commandPanelCurrentDot = null;
let commandPanelCurrentText = null;
let commandPanelHistoryBox = null;

function getCommandAction(container) {
    try {
        const encoded = container.split(":")[2];
        const normalized =
            encoded.replace(/-/g, "+").replace(/_/g, "/");
        const padded =
            normalized +
            "=".repeat(
                (4 - (normalized.length % 4)) % 4
            );

        const binary = atob(padded);
        const bytes = Uint8Array.from(
            binary,
            (char) => char.charCodeAt(0)
        );

        const payload =
            JSON.parse(
                new TextDecoder().decode(bytes)
            );

        return typeof payload.action === "string" &&
            payload.action.length > 0
            ? payload.action
            : "command";
    } catch (_) {
        return "command";
    }
}
function commandStatusMeta(state) {
    return (
        COMMAND_STATUS_META[state] ||
        COMMAND_STATUS_META.error
    );
}

function loadCommandHistory() {
    try {
        const raw = localStorage.getItem(
            COMMAND_PANEL_HISTORY_KEY
        );

        if (!raw) {
            return [];
        }

        const value = JSON.parse(raw);

        return Array.isArray(value)
            ? value.slice(0, 20)
            : [];
    } catch (_) {
        return [];
    }
}

function saveCommandHistory(history) {
    try {
        localStorage.setItem(
            COMMAND_PANEL_HISTORY_KEY,
            JSON.stringify(history.slice(0, 20))
        );
    } catch (_) {}
}

function loadCommandPanelSize() {
    const fallback = {
        width: 380,
        height: 240
    };

    try {
        const raw = localStorage.getItem(
            COMMAND_PANEL_SIZE_KEY
        );

        if (!raw) {
            return fallback;
        }

        const value = JSON.parse(raw);

        const width = Number(value.width);
        const height = Number(value.height);

        return {
            width:
                Number.isFinite(width) &&
                width >= 44
                    ? width
                    : fallback.width,

            height:
                Number.isFinite(height) &&
                height >= 44
                    ? height
                    : fallback.height
        };
    } catch (_) {
        return fallback;
    }
}

function saveCommandPanelSize() {
    if (!commandPanel) {
        return;
    }

    try {
        localStorage.setItem(
            COMMAND_PANEL_SIZE_KEY,
            JSON.stringify({
                width: commandPanel.offsetWidth,
                height: commandPanel.offsetHeight
            })
        );
    } catch (_) {}
}

const COMMAND_PANEL_POSITION_KEY =
    "agentChataiCommandPanelPosition";

const COMMAND_PANEL_THEME_KEY =
    "agentChataiCommandPanelTheme";

function loadCommandPanelPosition() {
    const fallback = {
        left: 16,
        top: null
    };

    try {
        const raw = localStorage.getItem(
            COMMAND_PANEL_POSITION_KEY
        );

        if (!raw) {
            return fallback;
        }

        const value = JSON.parse(raw);

        return {
            left: Number.isFinite(Number(value.left))
                ? Number(value.left)
                : fallback.left,

            top:
                value.top === null ||
                value.top === undefined
                    ? null
                    : Number.isFinite(Number(value.top))
                        ? Number(value.top)
                        : fallback.top
        };
    } catch (_) {
        return fallback;
    }
}

function saveCommandPanelPosition(panel) {
    if (!panel) {
        return;
    }

    try {
        localStorage.setItem(
            COMMAND_PANEL_POSITION_KEY,
            JSON.stringify({
                left: panel.offsetLeft,
                top: panel.offsetTop
            })
        );
    } catch (_) {}
}

function loadCommandPanelTheme() {
    try {
        const stored =
            localStorage.getItem(
                COMMAND_PANEL_THEME_KEY
            );

        if (stored === "dark" || stored === "light") {
            return stored;
        }
    } catch (_) {}

    return window.matchMedia &&
        window.matchMedia(
            "(prefers-color-scheme: dark)"
        ).matches
        ? "dark"
        : "light";
}

function saveCommandPanelTheme(theme) {
    try {
        localStorage.setItem(
            COMMAND_PANEL_THEME_KEY,
            theme
        );
    } catch (_) {}
}
function closeCommandPanel() {
    commandBridgeEnabled = false;
    clearBridgeGeneratedComposer();
    if (typeof removeConfirmationBar === "function") {
        removeConfirmationBar();
    }
    if (commandPanel) {
        commandPanel.remove();
    }
    commandPanel = null;
    commandPanelCurrentDot = null;
    commandPanelCurrentText = null;
    commandPanelHistoryBox = null;
    document.documentElement.dataset.agentChataiBridgeEnabled = "0";
}

function openCommandPanel() {
    commandBridgeEnabled = true;
    document.documentElement.dataset.agentChataiBridgeEnabled = "1";
    ensureCommandPanel();
    inspectDocument();
}

function toggleCommandPanel() {
    if (commandBridgeEnabled) {
        closeCommandPanel();
    } else {
        openCommandPanel();
    }
}

function ensureCommandPanel() {
    if (
        commandPanel &&
        document.documentElement.contains(
            commandPanel
        )
    ) {
        return commandPanel;
    }

    if (!document.body) {
        return null;
    }

    commandPanel =
        document.getElementById(
            "agentChataiCommandPanel"
        );

    if (commandPanel) {
        return commandPanel;
    }

    const size =
        loadCommandPanelSize();

    const position =
        loadCommandPanelPosition();

    const panel =
        document.createElement("div");

    panel.id =
        "agentChataiCommandPanel";

    Object.assign(
        panel.style,
        {
            position: "fixed",
            left: `${Math.max(
                8,
                position.left
            )}px`,
            top:
                position.top === null
                    ? "auto"
                    : `${Math.max(
                        8,
                        position.top
                    )}px`,
            bottom:
                position.top === null
                    ? "16px"
                    : "auto",
            zIndex: "2147483647",
            width: `${size.width}px`,
            height: `${size.height}px`,
            minWidth: "44px",
            minHeight: "44px",
            maxWidth:
                "calc(100vw - 16px)",
            maxHeight:
                "calc(100vh - 16px)",
            overflow: "hidden",
            boxSizing: "border-box",
            padding: "10px",
            borderRadius: "12px",
            fontFamily:
                "system-ui, sans-serif",
            fontSize: "13px",
            lineHeight: "1.35",
            userSelect: "none",
            resize: "none",
            cursor: "default"
        }
    );

    const applyTheme =
        (theme) => {
            const dark =
                theme === "dark";

            panel.style.setProperty(
                "--agx-panel-bg",
                dark
                    ? "#1f2937"
                    : "#ffffff"
            );

            panel.style.setProperty(
                "--agx-panel-fg",
                dark
                    ? "#f9fafb"
                    : "#222222"
            );

            panel.style.setProperty(
                "--agx-panel-border",
                dark
                    ? "#4b5563"
                    : "#9ca3af"
            );

            panel.style.setProperty(
                "--agx-panel-divider",
                dark
                    ? "#374151"
                    : "#e5e7eb"
            );

            panel.style.background =
                "var(--agx-panel-bg)";

            panel.style.color =
                "var(--agx-panel-fg)";

            panel.style.border =
                "1px solid var(--agx-panel-border)";

            panel.style.boxShadow =
                dark
                    ? "0 6px 24px rgba(0,0,0,.45)"
                    : "0 6px 24px rgba(0,0,0,.20)";

            if (
                typeof themeButton !==
                "undefined" &&
                themeButton
            ) {
                themeButton.setAttribute(
                    "aria-checked",
                    dark
                        ? "true"
                        : "false"
                );

                themeButton.style.background =
                    dark
                        ? "#374151"
                        : "#e5e7eb";

                themeKnob.style.transform =
                    dark
                        ? "translateX(20px)"
                        : "translateX(0)";

                themeKnob.textContent =
                    dark ? "☾" : "☀";
            }
        };

    const header =
        document.createElement("div");

    header.className =
        "agentChataiCommandPanelHeader";

    Object.assign(
        header.style,
        {
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "8px",
            fontWeight: "600",
            marginBottom: "8px",
            userSelect: "none",
            cursor: "move"
        }
    );

    const title =
        document.createElement("div");

    title.textContent =
        "Agent ChatAI";

    title.className =
        "agentChataiCommandPanelTitle";

    const themeButton =
        document.createElement("button");

    themeButton.type = "button";
    themeButton.setAttribute(
        "role",
        "switch"
    );
    themeButton.setAttribute(
        "aria-label",
        "Переключить тему Agent ChatAI"
    );

    Object.assign(
        themeButton.style,
        {
            position: "relative",
            width: "44px",
            height: "24px",
            padding: "0",
            margin: "0",
            border: "0",
            borderRadius: "999px",
            cursor: "pointer",
            flex: "0 0 auto"
        }
    );

    const themeKnob =
        document.createElement("span");

    Object.assign(
        themeKnob.style,
        {
            position: "absolute",
            left: "3px",
            top: "3px",
            width: "18px",
            height: "18px",
            borderRadius: "50%",
            background: "#ffffff",
            color: "#111827",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "12px",
            lineHeight: "1",
            boxShadow:
                "0 1px 3px rgba(0,0,0,.25)",
            transition:
                "transform .15s ease"
        }
    );

    themeButton.appendChild(
        themeKnob
    );

    const current =
        document.createElement("div");

    current.className =
        "agentChataiCommandPanelCurrent";

    Object.assign(
        current.style,
        {
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "6px 4px 8px",
            fontWeight: "600",
            borderBottom:
                "1px solid var(--agx-panel-divider)",
            marginBottom: "6px",
            overflow: "hidden",
            cursor: "move"
        }
    );

    const dot =
        document.createElement("span");

    dot.textContent = "●";
    dot.style.flex =
        "0 0 auto";

    const currentText =
        document.createElement("span");

    currentText.style.overflow =
        "hidden";

    currentText.style.textOverflow =
        "ellipsis";

    currentText.style.whiteSpace =
        "nowrap";

    current.appendChild(dot);
    current.appendChild(
        currentText
    );

    const historyTitle =
        document.createElement("div");

    historyTitle.textContent =
        "История";

    historyTitle.className =
        "agentChataiCommandPanelHistoryTitle";

    Object.assign(
        historyTitle.style,
        {
            fontSize: "11px",
            fontWeight: "600",
            opacity: "0.7",
            marginBottom: "4px"
        }
    );

    const history =
        document.createElement("div");

    history.className =
        "agentChataiCommandPanelHistory";

    Object.assign(
        history.style,
        {
            overflowY: "auto",
            height:
                "calc(100% - 76px)",
            paddingRight: "3px"
        }
    );

    header.appendChild(title);
    const closeButton = document.createElement("button");

closeButton.type = "button";
closeButton.textContent = "×";
closeButton.setAttribute("aria-label", "Закрыть Agent ChatAI");
Object.assign(closeButton.style, { width: "24px", height: "24px", padding: "0", margin: "0 0 0 4px", border: "0", borderRadius: "6px", background: "transparent", color: "inherit", cursor: "pointer", fontSize: "20px", lineHeight: "20px", flex: "0 0 auto" });
closeButton.className = "agentChataiCommandPanelClose";
closeButton.addEventListener("click", (event) => { event.preventDefault(); event.stopPropagation(); closeCommandPanel(); });

header.appendChild(themeButton);
    header.appendChild(closeButton);

    panel.appendChild(header);
    panel.appendChild(current);
    panel.appendChild(historyTitle);
    panel.appendChild(history);

    document.body.appendChild(panel);

    commandPanel = panel;
    commandPanelCurrentDot = dot;
    commandPanelCurrentText = currentText;
    commandPanelHistoryBox = history;

    let currentTheme =
        loadCommandPanelTheme();

    const setTheme =
        (theme) => {
            currentTheme =
                theme === "dark"
                    ? "dark"
                    : "light";

            applyTheme(
                currentTheme
            );

            saveCommandPanelTheme(
                currentTheme
            );
        };

    themeButton.addEventListener(
        "click",
        (event) => {
            event.preventDefault();
            event.stopPropagation();

            setTheme(
                currentTheme === "dark"
                    ? "light"
                    : "dark"
            );
        }
    );

    applyTheme(
        currentTheme
    );

    const clampPanel =
        (
            left,
            top,
            width,
            height
        ) => {
            const minWidth = 44;
            const minHeight = 44;

            width =
                Math.max(
                    minWidth,
                    Math.min(
                        width,
                        window.innerWidth - 8
                    )
                );

            height =
                Math.max(
                    minHeight,
                    Math.min(
                        height,
                        window.innerHeight - 8
                    )
                );

            left =
                Math.max(
                    4,
                    Math.min(
                        left,
                        window.innerWidth -
                        width -
                        4
                    )
                );

            top =
                Math.max(
                    4,
                    Math.min(
                        top,
                        window.innerHeight -
                        height -
                        4
                    )
                );

            return {
                left,
                top,
                width,
                height
            };
        };

    const saveGeometry =
        () => {
            try {
                localStorage.setItem(
                    COMMAND_PANEL_POSITION_KEY,
                    JSON.stringify({
                        left:
                            panel.offsetLeft,
                        top:
                            panel.offsetTop
                    })
                );

                localStorage.setItem(
                    COMMAND_PANEL_SIZE_KEY,
                    JSON.stringify({
                        width:
                            panel.offsetWidth,
                        height:
                            panel.offsetHeight
                    })
                );
            } catch (_) {}
        };

    const dragStart =
        (event) => {
            if (
                event.button !== 0 ||
                event.target?.closest?.("button")
            ) {
                return;
            }

            event.preventDefault();

            const startX =
                event.clientX;

            const startY =
                event.clientY;

            const startLeft =
                panel.offsetLeft;

            const startTop =
                panel.offsetTop;

            const move =
                (moveEvent) => {
                    const geometry =
                        clampPanel(
                            startLeft +
                                moveEvent.clientX -
                                startX,
                            startTop +
                                moveEvent.clientY -
                                startY,
                            panel.offsetWidth,
                            panel.offsetHeight
                        );

                    panel.style.left =
                        `${geometry.left}px`;

                    panel.style.top =
                        `${geometry.top}px`;

                    panel.style.bottom =
                        "auto";
                };

            const stop =
                () => {
                    window.removeEventListener(
                        "pointermove",
                        move
                    );

                    window.removeEventListener(
                        "pointerup",
                        stop
                    );

                    saveGeometry();
                };

            window.addEventListener(
                "pointermove",
                move
            );

            window.addEventListener(
                "pointerup",
                stop,
                { once: true }
            );
        };

    header.addEventListener(
        "pointerdown",
        dragStart
    );

    current.addEventListener(
        "pointerdown",
        dragStart
    );

    const handles = [
        ["n", "ns-resize"],
        ["s", "ns-resize"],
        ["e", "ew-resize"],
        ["w", "ew-resize"],
        ["ne", "nesw-resize"],
        ["sw", "nesw-resize"],
        ["nw", "nwse-resize"],
        ["se", "nwse-resize"]
    ];

    const handleStyle = {
        position: "absolute",
        zIndex: "3"
    };

    for (
        const [direction, cursor]
        of handles
    ) {
        const handle =
            document.createElement("div");

        handle.dataset.direction =
            direction;

        Object.assign(
            handle.style,
            handleStyle,
            {
                cursor,
                userSelect: "none",
                touchAction: "none"
            }
        );

        if (direction === "n") {
            Object.assign(
                handle.style,
                {
                    top: "-4px",
                    left: "8px",
                    right: "8px",
                    height: "9px"
                }
            );
        }

        if (direction === "s") {
            Object.assign(
                handle.style,
                {
                    bottom: "-4px",
                    left: "8px",
                    right: "8px",
                    height: "9px"
                }
            );
        }

        if (direction === "e") {
            Object.assign(
                handle.style,
                {
                    right: "-4px",
                    top: "8px",
                    bottom: "8px",
                    width: "9px"
                }
            );
        }

        if (direction === "w") {
            Object.assign(
                handle.style,
                {
                    left: "-4px",
                    top: "8px",
                    bottom: "8px",
                    width: "9px"
                }
            );
        }

        if (direction === "ne") {
            Object.assign(
                handle.style,
                {
                    top: "-5px",
                    right: "-5px",
                    width: "12px",
                    height: "12px"
                }
            );
        }

        if (direction === "nw") {
            Object.assign(
                handle.style,
                {
                    top: "-5px",
                    left: "-5px",
                    width: "12px",
                    height: "12px"
                }
            );
        }

        if (direction === "se") {
            Object.assign(
                handle.style,
                {
                    bottom: "-5px",
                    right: "-5px",
                    width: "12px",
                    height: "12px"
                }
            );
        }

        if (direction === "sw") {
            Object.assign(
                handle.style,
                {
                    bottom: "-5px",
                    left: "-5px",
                    width: "12px",
                    height: "12px"
                }
            );
        }

        panel.appendChild(handle);

        handle.addEventListener(
            "pointerdown",
            (event) => {
                if (
                    event.button !== 0
                ) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                const startX =
                    event.clientX;

                const startY =
                    event.clientY;

                const startLeft =
                    panel.offsetLeft;

                const startTop =
                    panel.offsetTop;

                const startWidth =
                    panel.offsetWidth;

                const startHeight =
                    panel.offsetHeight;

                const move =
                    (moveEvent) => {
                        let left =
                            startLeft;

                        let top =
                            startTop;

                        let width =
                            startWidth;

                        let height =
                            startHeight;

                        const dx =
                            moveEvent.clientX -
                            startX;

                        const dy =
                            moveEvent.clientY -
                            startY;

                        if (
                            direction.includes("e")
                        ) {
                            width =
                                startWidth +
                                dx;
                        }

                        if (
                            direction.includes("s")
                        ) {
                            height =
                                startHeight +
                                dy;
                        }

                        if (
                            direction.includes("w")
                        ) {
                            width =
                                startWidth -
                                dx;

                            left =
                                startLeft +
                                dx;
                        }

                        if (
                            direction.includes("n")
                        ) {
                            height =
                                startHeight -
                                dy;

                            top =
                                startTop +
                                dy;
                        }

                        const geometry =
                            clampPanel(
                                left,
                                top,
                                width,
                                height
                            );

                        panel.style.left =
                            `${geometry.left}px`;

                        panel.style.top =
                            `${geometry.top}px`;

                        panel.style.bottom =
                            "auto";

                        panel.style.width =
                            `${geometry.width}px`;

                        panel.style.height =
                            `${geometry.height}px`;
                    };

                const stop =
                    () => {
                        window.removeEventListener(
                            "pointermove",
                            move
                        );

                        window.removeEventListener(
                            "pointerup",
                            stop
                        );

                        saveGeometry();
                    };

                window.addEventListener(
                    "pointermove",
                    move
                );

                window.addEventListener(
                    "pointerup",
                    stop,
                    { once: true }
                );
            }
        );
    }

    const updateCompactMode =
        () => {
            if (!commandPanel) {
                return;
            }

            const compact =
                commandPanel.offsetWidth < 230;

            const micro =
                commandPanel.offsetWidth < 90;

            title.style.display =
                compact || micro
                    ? "none"
                    : "block";

            historyTitle.style.display =
                compact || micro
                    ? "none"
                    : "block";

            commandPanelHistoryBox.style.display =
                compact || micro
                    ? "none"
                    : "block";

            header.style.justifyContent =
                compact
                    ? "flex-end"
                    : "space-between";

            current.style.justifyContent =
                micro
                    ? "center"
                    : "flex-start";

            currentText.style.display =
                micro
                    ? "none"
                    : "block";

            header.style.display =
                micro
                    ? "none"
                    : "flex";

            saveGeometry();
        };

    if (
        typeof ResizeObserver === "function"
    ) {
        const observer =
            new ResizeObserver(
                updateCompactMode
            );

        observer.observe(panel);
    }

    window.addEventListener(
        "resize",
        () => {
            const geometry =
                clampPanel(
                    panel.offsetLeft,
                    panel.offsetTop,
                    panel.offsetWidth,
                    panel.offsetHeight
                );

            panel.style.left =
                `${geometry.left}px`;

            panel.style.top =
                `${geometry.top}px`;

            panel.style.bottom =
                "auto";

            panel.style.width =
                `${geometry.width}px`;

            panel.style.height =
                `${geometry.height}px`;

            saveGeometry();
        }
    );

    updateCompactMode();

    renderCommandHistory();

    return panel;
}

function renderCommandHistory() {
    ensureCommandPanel();

    if (!commandPanelHistoryBox) {
        return;
    }

    commandPanelHistoryBox.replaceChildren();

    const history =
        loadCommandHistory();

    for (const item of history) {
        const meta =
            commandStatusMeta(
                item.state
            );

        const row =
            document.createElement("div");

        Object.assign(
            row.style,
            {
                color: meta.color,
                padding: "4px 2px",
                borderBottom: "1px solid var(--agx-panel-divider)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap"
            }
        );

        const time =
            document.createElement("span");

        time.textContent =
            item.time || "";

        time.style.opacity =
            "0.65";

        const action =
            document.createElement("span");

        action.textContent =
            item.action || "command";

        const status =
            document.createElement("span");

        status.textContent =
            ` — ${meta.label}`;

        row.appendChild(time);
        row.appendChild(
            document.createTextNode(" ")
        );
        row.appendChild(action);
        row.appendChild(status);

        if (item.detail) {
            const detail =
                document.createElement("span");

            detail.textContent =
                ` — ${item.detail}`;

            detail.style.opacity =
                "0.75";

            row.appendChild(detail);
        }

        commandPanelHistoryBox.appendChild(row);
    }
}

function setCommandStatus(
    action,
    state,
    detail = "",
    historyId = null
) {
    ensureCommandPanel();

    const meta =
        commandStatusMeta(state);

    if (commandPanelCurrentDot) {
        commandPanelCurrentDot.style.color =
            meta.color;
    }

    if (commandPanelCurrentText) {
        commandPanelCurrentText.textContent =
            `${meta.label}: ${action}` +
            (detail
                ? ` — ${detail}`
                : "");

        commandPanelCurrentText.style.color =
            meta.color;
    }

    document.documentElement.dataset
        .agentChataiCommandStatus =
        state;

    const history =
        loadCommandHistory();

    const index =
        historyId
            ? history.findIndex(
                (item) =>
                    item.id === historyId
            )
            : -1;

    const now =
        new Date();

    if (index >= 0) {
        history[index] = {
            ...history[index],
            action,
            state,
            detail,
            time:
                history[index].time ||
                now.toLocaleTimeString()
        };
    } else {
        history.unshift({
            id:
                historyId ||
                (
                    globalThis.crypto?.randomUUID
                        ? crypto.randomUUID()
                        : `${Date.now()}-${Math.random()}`
                ),
            action,
            state,
            detail,
            time:
                now.toLocaleTimeString()
        });
    }

    saveCommandHistory(history);

    renderCommandHistory();
}
function reportCommandContainers(containers) {
    for (const container of containers) {
        if (container === lastCommandContainer) {
            continue;
        }

        lastCommandContainer = container;

        const actionName =
            getCommandAction(container);

        const historyId =
            globalThis.crypto?.randomUUID
                ? crypto.randomUUID()
                : `${Date.now()}-${Math.random()}`;

        setCommandStatus(
            actionName,
            "running",
            "",
            historyId
        );

        document.documentElement.dataset
            .agentChataiAgxFound = "1";

        chrome.runtime.sendMessage(
            {
                type: "AGX_COMMAND_DETECTED",
                containers: [container]
            },
            (response) => {
                if (chrome.runtime.lastError) {
                    const message =
                        chrome.runtime.lastError.message ||
                        "unknown_error";

                    setCommandStatus(
                        actionName,
                        "error",
                        message,
                        historyId
                    );

                    document.documentElement.dataset
                        .agentChataiGatewayError =
                        message;

                    return;
                }

                if (!response || !response.ok) {
                    const message =
                        response?.message ||
                        response?.error ||
                        "unknown_error";

                    setCommandStatus(
                        actionName,
                        "error",
                        message,
                        historyId
                    );

                    document.documentElement.dataset
                        .agentChataiGatewayError =
                        message;

                    return;
                }

                document.documentElement.dataset
                    .agentChataiBackgroundAck = "1";

                document.documentElement.dataset
                    .agentChataiGatewayAck = "1";

                document.documentElement.dataset
                    .agentChataiSignatureVerified =
                    response.signatureVerified === true
                        ? "1"
                        : "0";

                document.documentElement.dataset
                    .agentChataiGatewayResult =
                    response.signatureVerified === true
                        ? "received"
                        : "rejected";

                document.documentElement.dataset
                    .agentChataiResultStatus =
                    response.resultStatus || "";

                if (
                    response.signatureVerified !== true
                ) {
                    setCommandStatus(
                        actionName,
                        "error",
                        "RESULT signature rejected",
                        historyId
                    );

                    return;
                }

                if (
                    response.confirmationRequired &&
                    response.confirmationToken
                ) {
                    setCommandStatus(
                        actionName,
                        "confirm",
                        "Требуется подтверждение",
                        historyId
                    );

                    showConfirmationBar(
                        response
                    );

                    return;
                }

                if (
                    response.resultContainer
                ) {
                    setCommandStatus(
                        actionName,
                        response.resultStatus === "ok"
                            ? "done"
                            : "error",
                        response.resultStatus || "",
                        historyId
                    );

                    publishResultToChat(
                        response.resultContainer
                    );

                    return;
                }

                setCommandStatus(
                    actionName,
                    "error",
                    "Gateway returned no RESULT",
                    historyId
                );
            }
        );
    }
}

function inspectDocument() {
    if (!commandBridgeEnabled) {
        return;
    }

    const commandContainers =
        extractCommandContainers(
            document.body?.innerText || ""
        );

    if (commandContainers.length > 0) {
        reportCommandContainers(commandContainers);
    }
    const text =
        document.body?.innerText ||
        document.documentElement?.innerText ||
        "";

    reportContainers(
        extractActionContainers(text)
    );
}

inspectDocument();

let inspectTimer = null;

function scheduleInspectDocument() {
    if (inspectTimer !== null) {
        return;
    }

    inspectTimer = window.setTimeout(() => {
        inspectTimer = null;
        inspectDocument();
    }, 50);
}

const observer = new MutationObserver(
    (mutations) => {
        for (const mutation of mutations) {
            if (
                (mutation.type === "childList" &&
                    mutation.addedNodes.length > 0) ||
                mutation.type === "characterData"
            ) {
                scheduleInspectDocument();
                break;
            }
        }
    }
);

observer.observe(
    document.documentElement,
    {
        childList: true,
        subtree: true,
        characterData: true
    }
);

scheduleInspectDocument();
observer.observe(
    document.documentElement,
    {
        childList: true,
        subtree: true
    }
);














document.documentElement.dataset.agentChataiBridgeEnabled = "0";

function agentChataiBridgeShortcutHandler(event) {
    if (
        event.altKey &&
        event.shiftKey &&
        event.code === "KeyA" &&
        !event.ctrlKey &&
        !event.metaKey
    ) {
        event.preventDefault();
        event.stopPropagation();
        toggleCommandPanel();
    }
}

window.addEventListener(
    "keydown",
    agentChataiBridgeShortcutHandler,
    true
);


