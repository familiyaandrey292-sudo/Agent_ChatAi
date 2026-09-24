"use strict";

const codeInput =
    document.getElementById("code");

const pairButton =
    document.getElementById("pair");

const status =
    document.getElementById("status");

const bridgeToggle =
    document.getElementById("bridge-toggle");

const bridgeLabel =
    document.getElementById("bridge-label");

function setBridgeUi(enabled, unavailable) {
    bridgeToggle.checked = enabled;
    bridgeToggle.disabled = Boolean(unavailable);

    if (unavailable) {
        bridgeLabel.textContent =
            "Bridge unavailable on this tab.";
    } else if (enabled) {
        bridgeLabel.textContent =
            "Bridge enabled on this tab";
    } else {
        bridgeLabel.textContent =
            "Bridge disabled on this tab";
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

function isBridgeSupportedUrl(url) {
    return (
        typeof url === "string" &&
        /^(https?|file):/.test(url)
    );
}

async function refreshBridgeState(tab) {
    if (!tab || !isBridgeSupportedUrl(tab.url)) {
        setBridgeUi(false, true);
        return;
    }

    try {
        const results =
            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: () =>
                    document.documentElement.dataset
                        .agentChataiBridgeEnabled !== "0"
            });

        const enabled =
            results?.[0]?.result !== false;

        setBridgeUi(enabled, false);
    } catch (error) {
        setBridgeUi(false, true);
    }
}

bridgeToggle.addEventListener(
    "change",
    async () => {
        const desired = bridgeToggle.checked;
        const tab = await getActiveTab();

        if (!tab || !isBridgeSupportedUrl(tab.url)) {
            setBridgeUi(false, true);
            return;
        }

        try {
            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: (enabled) => {
                    document.documentElement.dataset
                        .agentChataiBridgeEnabled =
                        enabled ? "1" : "0";
                },
                args: [desired]
            });

            setBridgeUi(desired, false);
        } catch (error) {
            setBridgeUi(false, true);
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

getActiveTab()
    .then(refreshBridgeState)
    .catch(() => setBridgeUi(false, true));

refreshStatus().catch(() => {});
