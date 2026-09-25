"use strict";

const codeInput =
    document.getElementById("code");

const pairButton =
    document.getElementById("pair");

const status =
    document.getElementById("status");

const bridgeToggle =
    document.getElementById("bridgeToggle");

const discoveryToggle =
    document.getElementById("discoveryToggle");

const discoveryPhrase =
    document.getElementById("discoveryPhrase");

const copyDiscovery =
    document.getElementById("copyDiscovery");

const discoveryState =
    document.getElementById("discoveryState");

const discoveryHelp =
    document.getElementById("discoveryHelp");

let currentDiscoveryPhrase = "";

if (bridgeToggle) {
    bridgeToggle.title =
        "Alt+Shift+A — включить или выключить Bridge";
}

function randomSevenDigitNumber() {
    return (
        Math.floor(
            1000000 +
            Math.random() * 9000000
        )
    );
}

function makeDiscoveryPhrase() {
    let x = randomSevenDigitNumber();
    let y = randomSevenDigitNumber();

    while (x === y) {
        y = randomSevenDigitNumber();
    }

    return (
        "ИИ сколько будет " +
        x +
        " умножить на " +
        y
    );
}

function setDiscoveryPhrase(phrase) {
    currentDiscoveryPhrase = phrase || "";

    if (discoveryPhrase) {
        discoveryPhrase.value =
            currentDiscoveryPhrase;
    }
}

function setDiscoveryVisual(
    listening,
    phase = "idle"
) {
    if (discoveryToggle) {
        discoveryToggle.disabled = false;
        discoveryToggle.dataset.listening =
            listening ? "true" : "false";
        discoveryToggle.setAttribute(
            "aria-pressed",
            listening ? "true" : "false"
        );
        discoveryToggle.setAttribute(
            "aria-label",
            listening
                ? "Остановить поиск элементов чата"
                : "Начать поиск элементов чата"
        );
    }

    if (discoveryState) {
        if (phase === "complete") {
            discoveryState.textContent =
                "Готово";
        } else if (listening) {
            discoveryState.textContent =
                phase === "wait_send"
                    ? "Поле найдено"
                    : phase === "wait_message"
                        ? "Кнопка найдена"
                        : "Слушает";
        } else {
            discoveryState.textContent =
                "Покой";
        }
    }

    if (discoveryHelp) {
        if (phase === "wait_send") {
            discoveryHelp.textContent =
                "Поле чата найдено. Теперь нажми кнопку отправки.";
        } else if (phase === "wait_message") {
            discoveryHelp.textContent =
                "Кнопка найдена. Жду появление отправленного сообщения.";
        } else if (listening) {
            discoveryHelp.textContent =
                "Вставь фразу в поле чата.";
        } else if (phase === "complete") {
            discoveryHelp.textContent =
                "Поле, кнопка отправки и сообщение найдены.";
        } else {
            discoveryHelp.textContent =
                "Bridge запоминает найденные элементы для этого сайта.";
        }
    }
}

async function copyDiscoveryPhrase() {
    if (!currentDiscoveryPhrase) {
        return;
    }

    try {
        if (
            navigator.clipboard &&
            typeof navigator.clipboard.writeText ===
                "function"
        ) {
            await navigator.clipboard.writeText(
                currentDiscoveryPhrase
            );
        } else {
            const helper =
                document.createElement("textarea");

            helper.value =
                currentDiscoveryPhrase;

            document.body.appendChild(helper);
            helper.select();
            document.execCommand("copy");
            helper.remove();
        }

        if (discoveryHelp) {
            discoveryHelp.textContent =
                "Фраза скопирована. Вставь её в поле чата.";
        }
    } catch (error) {
        if (discoveryHelp) {
            discoveryHelp.textContent =
                "Не удалось скопировать: " +
                error.message;
        }
    }
}

async function getDiscoveryState() {
    try {
        const tab = await getActiveTab();

        if (!tab?.id) {
            setDiscoveryVisual(false);
            return;
        }

        const response =
            await chrome.tabs.sendMessage(
                tab.id,
                {
                    type:
                        "AGX_CHAT_DISCOVERY_STATE"
                }
            );

        if (response?.phrase) {
            setDiscoveryPhrase(
                response.phrase
            );
        } else if (!currentDiscoveryPhrase) {
            setDiscoveryPhrase(
                makeDiscoveryPhrase()
            );
        }

        setDiscoveryVisual(
            response?.active === true,
            response?.phase || "idle"
        );
    } catch (_) {
        setDiscoveryVisual(false);
    }
}

async function setDiscoveryListening(
    listening
) {
    const tab = await getActiveTab();

    if (!tab?.id) {
        setDiscoveryVisual(false);
        return;
    }

    try {
        if (listening) {
            if (!currentDiscoveryPhrase) {
                setDiscoveryPhrase(
                    makeDiscoveryPhrase()
                );
            }

            const response =
                await chrome.tabs.sendMessage(
                    tab.id,
                    {
                        type:
                            "AGX_CHAT_DISCOVERY_START",
                        phrase:
                            currentDiscoveryPhrase
                    }
                );

            setDiscoveryVisual(
                response?.active === true,
                response?.phase || "idle"
            );
        } else {
            const response =
                await chrome.tabs.sendMessage(
                    tab.id,
                    {
                        type:
                            "AGX_CHAT_DISCOVERY_STOP"
                    }
                );

            setDiscoveryVisual(
                false,
                response?.phase || "idle"
            );
        }
    } catch (error) {
        setDiscoveryVisual(false);
        if (discoveryHelp) {
            discoveryHelp.textContent =
                "Bridge unavailable on this tab.";
        }
    }
}

async function getActiveTab() {
    const tabs =
        await chrome.tabs.query({
            active: true,
            currentWindow: true
        });

    return tabs[0] || null;
}

function updateBridgeToggle(enabled, available = true) {
    if (!bridgeToggle) {
        return;
    }

    bridgeToggle.disabled = !available;

    bridgeToggle.setAttribute(
        "aria-checked",
        enabled ? "true" : "false"
    );

    bridgeToggle.setAttribute(
        "aria-label",
        enabled
            ? "Выключить Agent ChatAI Bridge"
            : "Включить Agent ChatAI Bridge"
    );
}

async function refreshBridgeState() {
    try {
        const tab = await getActiveTab();

        if (!tab?.id) {
            updateBridgeToggle(false, false);
            return;
        }

        const response =
            await chrome.tabs.sendMessage(
                tab.id,
                {
                    type: "AGX_GET_BRIDGE_STATE"
                }
            );

        updateBridgeToggle(
            response?.enabled === true,
            true
        );
    } catch (_) {
        updateBridgeToggle(false, false);
    }
}

async function setBridgeState(enabled) {
    const tab = await getActiveTab();

    if (!tab?.id) {
        updateBridgeToggle(false, false);
        return;
    }

    try {
        const response =
            await chrome.tabs.sendMessage(
                tab.id,
                {
                    type: "AGX_SET_BRIDGE_STATE",
                    enabled: enabled === true
                }
            );

        updateBridgeToggle(
            response?.enabled === true,
            true
        );
    } catch (error) {
        updateBridgeToggle(false, false);

        status.textContent =
            "Bridge unavailable on this tab.";
    }
}

bridgeToggle?.addEventListener(
    "click",
    async () => {
        const enabled =
            bridgeToggle.getAttribute(
                "aria-checked"
            ) === "true";

        bridgeToggle.disabled = true;

        try {
            await setBridgeState(!enabled);
        } finally {
            bridgeToggle.disabled = false;
        }
    }
);


async function refreshStatus() {
    try {
        const identity =
            await AGXBrowserKeys
                .ensureIdentity();

        const response =
            await fetch(
                "http://127.0.0.1:8765/v1/health"
            );

        const health =
            await response.json();

        if (!response.ok) {
            throw new Error(
                health.message ||
                health.error ||
                "Gateway unavailable"
            );
        }

        if (health.paired) {
            status.textContent =
                "Gateway: paired\n" +
                "Browser key: ready";
        } else {
            status.textContent =
                "Gateway: waiting for pairing\n" +
                "Browser key: ready\n" +
                "Enter the pairing code.";
        }

        return identity;
    } catch (error) {
        status.textContent =
            "Error: " + error.message;
        throw error;
    }
}

setDiscoveryPhrase(
    makeDiscoveryPhrase()
);

copyDiscovery?.addEventListener(
    "click",
    () => {
        copyDiscoveryPhrase();
    }
);

discoveryToggle?.addEventListener(
    "click",
    async () => {
        const listening =
            discoveryToggle.dataset.listening ===
            "true";

        discoveryToggle.disabled = true;

        try {
            await setDiscoveryListening(
                !listening
            );
        } finally {
            discoveryToggle.disabled = false;
        }
    }
);

pairButton.addEventListener(
    "click",
    async () => {
        pairButton.disabled = true;

        try {
            const identity =
                await AGXBrowserKeys
                    .ensureIdentity();

            const response =
                await fetch(
                    "http://127.0.0.1:8765/v1/pair",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type":
                                "application/json"
                        },
                        body: JSON.stringify({
                            code:
                                codeInput.value.trim(),
                            public_key_spki_b64:
                                identity.publicKeySpkiB64
                        })
                    }
                );

            const payload =
                await response.json();

            if (!response.ok) {
                throw new Error(
                    payload.message ||
                    payload.error ||
                    `Gateway HTTP ${response.status}`
                );
            }

            status.textContent =
                "Pairing successful.";
            codeInput.value = "";

        } catch (error) {
            status.textContent =
                "Pairing failed: " +
                error.message;
        } finally {
            pairButton.disabled = false;
        }
    }
);

refreshStatus().catch(() => {});
getDiscoveryState();


