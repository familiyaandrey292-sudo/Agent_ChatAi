"use strict";

const codeInput =
    document.getElementById("code");

const pairButton =
    document.getElementById("pair");

const status =
    document.getElementById("status");

const bridgeToggle =
    document.getElementById("bridgeToggle");

if (bridgeToggle) {
    bridgeToggle.title =
        "Alt+Shift+A — включить или выключить Bridge";
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


