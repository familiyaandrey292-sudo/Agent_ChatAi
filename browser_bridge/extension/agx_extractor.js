"use strict";

/*
 * Browser-independent AGX container extractor.
 *
 * The browser only finds the ASCII envelope.
 * Cryptographic validation and decoding remain in the Python Gateway.
 */

const AGX_ACTION_PATTERN =
    /AGX1:A:[A-Za-z0-9_-]+:[A-Fa-f0-9]{64}/g;

function extractActionContainers(text) {
    if (typeof text !== "string" || text.length === 0) {
        return [];
    }

    return [...new Set(text.match(AGX_ACTION_PATTERN) || [])];
}

globalThis.AgentChatAI = globalThis.AgentChatAI || {};
globalThis.AgentChatAI.extractActionContainers =
    extractActionContainers;

console.log(
    "[Agent ChatAI Browser Bridge] AGX extractor loaded."
);
