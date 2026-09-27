"use strict";

importScripts(
    "browser_keys.js",
    "result_public_key.js"
);

let verificationKeyPromise = null;

function base64ToBytes(value) {
    const normalized = value
        .replace(/-/g, "+")
        .replace(/_/g, "/")
        + "=".repeat(
            (-value.length) % 4
        );

    const binary = atob(normalized);
    const bytes = new Uint8Array(
        binary.length
    );

    for (
        let i = 0;
        i < binary.length;
        i++
    ) {
        bytes[i] = binary.charCodeAt(i);
    }

    return bytes;
}

async function getVerificationKey() {
    if (!verificationKeyPromise) {
        verificationKeyPromise =
            crypto.subtle.importKey(
                "spki",
                base64ToBytes(
                    globalThis
                        .AGX_RESULT_PUBLIC_KEY_SPKI_B64
                ),
                {
                    name: "Ed25519"
                },
                false,
                ["verify"]
            );
    }

    return verificationKeyPromise;
}

async function verifyResultSignature(
    resultContainer,
    signature
) {
    if (
        typeof resultContainer !== "string" ||
        !resultContainer.startsWith("AGX1:R:")
    ) {
        throw new Error(
            "invalid_result_container"
        );
    }

    if (
        typeof signature !== "string" ||
        !signature
    ) {
        throw new Error(
            "missing_result_signature"
        );
    }

    const key =
        await getVerificationKey();

    return crypto.subtle.verify(
        {
            name: "Ed25519"
        },
        key,
        base64ToBytes(signature),
        new TextEncoder().encode(
            resultContainer
        )
    );
}

async function postJson(
    path,
    body
) {
    const payload =
        await globalThis.AGXBrowserKeys
            .authenticatedFetch(
                path,
                body
            );

    const verified =
        await verifyResultSignature(
            payload.container,
            payload.signature
        );

    if (!verified) {
        throw new Error(
            "result_signature_invalid"
        );
    }

    return payload;
}

async function confirmAction(token) {
    return postJson(
        "/v1/confirm",
        {
            confirmation_token:
                token
        }
    );
}

async function cancelAction(token) {
    return globalThis.AGXBrowserKeys
        .authenticatedFetch(
            "/v1/cancel",
            {
                confirmation_token:
                    token
            }
        );
}

chrome.tabs.onRemoved.addListener((tabId) => {
    globalThis.AGXBrowserKeys
        .deleteSessionIdForTab(tabId)
        .catch((error) => console.error(
            "[Agent ChatAI Browser Bridge]",
            "tab session cleanup failed",
            error
        ));
});

chrome.runtime.onInstalled.addListener(() => {
    console.log(
        "Agent ChatAI Browser Bridge installed."
    );
});

chrome.runtime.onMessage.addListener(
    (
        message,
        sender,
        sendResponse
    ) => {
        if (
            message?.type ===
            "AGX_ACTION_DETECTED"
        ) {
            const containers =
                Array.isArray(
                    message.containers
                )
                    ? message.containers
                    : [];

            if (containers.length === 0) {
                sendResponse({
                    ok: false,
                    error:
                        "empty_action"
                });
                return;
            }

            globalThis.AGXBrowserKeys
                .authenticatedFetch(
                    "/v1/action",
                    {
                        container:
                            containers[0]
                    }
                )
                .then(
                    async (payload) => {
                        const verified =
                            await verifyResultSignature(
                                payload.container,
                                payload.signature
                            );

                        if (!verified) {
                            throw new Error(
                                "result_signature_invalid"
                            );
                        }

                        const confirmationRequired =
                            payload.status ===
                            "confirmation_required";

                        sendResponse({
                            ok: true,
                            resultContainer:
                                payload.container,
                            resultStatus:
                                payload.status ||
                                null,
                            resultMessage:
                                payload.message ||
                                null,
                            signatureVerified:
                                true,
                            confirmationRequired,
                            confirmationToken:
                                confirmationRequired
                                    ? payload.confirmation_token ||
                                      null
                                    : null,
                            tabId:
                                sender.tab?.id ??
                                null
                        });
                    }
                )
                .catch(
                    (error) => {
                        console.error(
                            "[Agent ChatAI Browser Bridge]",
                            error
                        );

                        sendResponse({
                            ok: false,
                            error:
                                "gateway_action_rejected",
                            message:
                                error.message
                        });
                    }
                );

            return true;
        }

        if (
            message?.type ===
            "AGX_COMMAND_DETECTED"
        ) {
            const containers =
                Array.isArray(
                    message.containers
                )
                    ? message.containers
                    : [];

            if (containers.length === 0) {
                sendResponse({
                    ok: false,
                    error:
                        "empty_command"
                });
                return;
            }

            const tabId = sender.tab?.id;
            if (!Number.isInteger(tabId) || tabId < 0) {
                sendResponse({
                    ok: false,
                    error: "command_tab_unknown"
                });
                return;
            }

            globalThis.AGXBrowserKeys
                .getSessionIdForTab(tabId)
                .then((sessionId) =>
                    globalThis.AGXBrowserKeys
                        .authenticatedFetch(
                            "/v1/command",
                            {
                                container:
                                    containers[0],
                                session_id:
                                    sessionId
                            }
                        )
                )
                .then(
                    async (payload) => {
                        const verified =
                            await verifyResultSignature(
                                payload.container,
                                payload.signature
                            );

                        if (!verified) {
                            throw new Error(
                                "result_signature_invalid"
                            );
                        }

                        const confirmationRequired =
                            payload.status ===
                            "confirmation_required";

                        sendResponse({
                            ok: true,
                            resultContainer:
                                payload.container,
                            resultStatus:
                                payload.status ||
                                null,
                            resultMessage:
                                payload.message ||
                                null,
                            signatureVerified:
                                true,
                            confirmationRequired,
                            confirmationToken:
                                confirmationRequired
                                    ? payload.confirmation_token ||
                                      null
                                    : null,
                            tabId:
                                sender.tab?.id ??
                                null
                        });
                    }
                )
                .catch(
                    (error) => {
                        console.error(
                            "[Agent ChatAI Browser Bridge]",
                            error
                        );

                        sendResponse({
                            ok: false,
                            error:
                                "gateway_command_rejected",
                            code:
                                error.code || null,
                            message:
                                error.message,
                            requestedTtl:
                                error.requested_ttl ?? null,
                            maxTtl:
                                error.max_ttl ?? null,
                            retryable:
                                error.retryable === true
                        });
                    }
                );

            return true;
        }
        if (
            message?.type ===
            "AGX_CONFIRM_ACTION"
        ) {
            confirmAction(
                message.confirmationToken
            )
                .then((payload) =>
                    sendResponse({
                        ok: true,
                        resultContainer:
                            payload.container,
                        resultStatus:
                            payload.status ||
                            null,
                        resultMessage:
                            payload.message ||
                            null,
                        signatureVerified:
                            true
                    })
                )
                .catch((error) =>
                    sendResponse({
                        ok: false,
                        error:
                            "confirmation_rejected",
                        message:
                            error.message
                    })
                );

            return true;
        }

        if (
            message?.type ===
            "AGX_CANCEL_ACTION"
        ) {
            cancelAction(
                message.confirmationToken
            )
                .then(() =>
                    sendResponse({
                        ok: true,
                        status:
                            "cancelled"
                    })
                )
                .catch((error) =>
                    sendResponse({
                        ok: false,
                        error:
                            "cancel_rejected",
                        message:
                            error.message
                    })
                );

            return true;
        }

        sendResponse({
            ok: false,
            error: "unknown_message_type"
        });
    }
);

