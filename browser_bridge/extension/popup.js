"use strict";

const codeInput =
    document.getElementById("code");

const pairButton =
    document.getElementById("pair");

const status =
    document.getElementById("status");

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
