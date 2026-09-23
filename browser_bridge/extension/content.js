"use strict";

document.documentElement.dataset.agentChataiBridge = "loaded";

const AGX_ACTION_PATTERN =
    /AGX1:A:[A-Za-z0-9_-]+:[A-Fa-f0-9]{64}/g;

let lastContainer = null;
let confirmationToken = null;
let confirmationBar = null;

function bridgeEnabled() {
    return (
        document.documentElement.dataset
            .agentChataiBridgeEnabled !== "0"
    );
}

function extractActionContainers(text) {
    if (!bridgeEnabled()) {
        return [];
    }

    if (typeof text !== "string" || !text.length) {
        return [];
    }

    return [...new Set(
        text.match(AGX_ACTION_PATTERN) || []
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

function inspectDocument() {
    const text =
        document.body?.innerText ||
        document.documentElement?.innerText ||
        "";

    reportContainers(
        extractActionContainers(text)
    );
}

inspectDocument();

new MutationObserver(() => {
    if (!bridgeEnabled() && confirmationBar) {
        removeConfirmationBar();
    }
}).observe(
    document.documentElement,
    {
        attributes: true,
        attributeFilter: ["data-agent-chatai-bridge-enabled"]
    }
);

const observer = new MutationObserver(
    (mutations) => {
        for (const mutation of mutations) {
            if (
                mutation.type !== "childList" ||
                mutation.addedNodes.length === 0
            ) {
                continue;
            }

            for (const node of mutation.addedNodes) {
                if (
                    node.nodeType !== Node.ELEMENT_NODE
                ) {
                    continue;
                }

                reportContainers(
                    extractActionContainers(
                        node.textContent || ""
                    )
                );
            }
        }
    }
);

observer.observe(
    document.documentElement,
    {
        childList: true,
        subtree: true
    }
);
