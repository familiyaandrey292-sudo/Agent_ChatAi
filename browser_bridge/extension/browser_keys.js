"use strict";

const AGX_KEY_DB = "agx_browser_bridge";
const AGX_KEY_STORE = "identity";
const AGX_KEY_ID = "browser";

function openKeyDb() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(
            AGX_KEY_DB,
            1
        );

        request.onupgradeneeded = () => {
            const db = request.result;

            if (!db.objectStoreNames.contains(
                AGX_KEY_STORE
            )) {
                db.createObjectStore(
                    AGX_KEY_STORE
                );
            }
        };

        request.onsuccess = () => {
            resolve(request.result);
        };

        request.onerror = () => {
            reject(request.error);
        };
    });
}

function getIdentity() {
    return openKeyDb().then(
        (db) =>
            new Promise((resolve, reject) => {
                const tx = db.transaction(
                    AGX_KEY_STORE,
                    "readonly"
                );

                const request = tx.objectStore(
                    AGX_KEY_STORE
                ).get(AGX_KEY_ID);

                request.onsuccess = () => {
                    resolve(request.result || null);
                };

                request.onerror = () => {
                    reject(request.error);
                };
            })
    );
}

function saveIdentity(identity) {
    return openKeyDb().then(
        (db) =>
            new Promise((resolve, reject) => {
                const tx = db.transaction(
                    AGX_KEY_STORE,
                    "readwrite"
                );

                tx.objectStore(
                    AGX_KEY_STORE
                ).put(
                    identity,
                    AGX_KEY_ID
                );

                tx.oncomplete = () => {
                    resolve();
                };

                tx.onerror = () => {
                    reject(tx.error);
                };
            })
    );
}

function newSessionId() {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    return b64urlEncode(bytes);
}

function b64urlEncode(bytes) {
    let binary = "";

    for (const byte of new Uint8Array(bytes)) {
        binary += String.fromCharCode(byte);
    }

    return btoa(binary)
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/g, "");
}

async function sha256Hex(bytes) {
    const digest = await crypto.subtle.digest(
        "SHA-256",
        bytes
    );

    return [...new Uint8Array(digest)]
        .map((value) =>
            value.toString(16).padStart(2, "0")
        )
        .join("");
}

async function ensureIdentity() {
    const existing = await getIdentity();

    if (existing?.privateKey &&
        existing?.publicKeySpkiB64) {
        if (
            typeof existing.sessionId === "string" &&
            existing.sessionId
        ) {
            return existing;
        }

        const upgraded = {
            ...existing,
            sessionId: newSessionId()
        };

        await saveIdentity(upgraded);
        return upgraded;
    }

    const keyPair = await crypto.subtle.generateKey(
        {
            name: "Ed25519"
        },
        false,
        ["sign", "verify"]
    );

    const publicSpki = await crypto.subtle.exportKey(
        "spki",
        keyPair.publicKey
    );

    const identity = {
        privateKey: keyPair.privateKey,
        publicKeySpkiB64: b64urlEncode(
            publicSpki
        ),
        sessionId: newSessionId()
    };

    await saveIdentity(identity);

    return identity;
}

async function signRequest({
    method,
    path,
    challenge,
    bodyBytes,
    privateKey
}) {
    const bodyHash = await sha256Hex(
        bodyBytes
    );

    const message =
        method.toUpperCase()
        + "\n"
        + path
        + "\n"
        + challenge
        + "\n"
        + bodyHash;

    const signature =
        await crypto.subtle.sign(
            {
                name: "Ed25519"
            },
            privateKey,
            new TextEncoder().encode(
                message
            )
        );

    return b64urlEncode(signature);
}

async function getSessionIdForTab(tabId) {
    if (!Number.isInteger(tabId) || tabId < 0) {
        throw new Error("invalid_tab_id");
    }

    const key = "session:" + tabId;
    const stored = await chrome.storage.session.get(key);
    if (typeof stored[key] === "string" && stored[key]) {
        return stored[key];
    }

    const sessionId = newSessionId();
    await chrome.storage.session.set({
        [key]: sessionId
    });
    return sessionId;
}

async function deleteSessionIdForTab(tabId) {
    if (Number.isInteger(tabId) && tabId >= 0) {
        await chrome.storage.session.remove("session:" + tabId);
    }
}

async function authenticatedFetch(
    path,
    payload
) {
    const identity =
        await ensureIdentity();

    const body = JSON.stringify(
        payload
    );

    const bodyBytes =
        new TextEncoder().encode(body);

    const challengeResponse =
        await fetch(
            "http://127.0.0.1:8765/v1/auth/challenge"
        );

    const challengePayload =
        await challengeResponse.json();

    if (!challengeResponse.ok) {
        throw new Error(
            challengePayload.message ||
            challengePayload.error ||
            `Challenge HTTP ${challengeResponse.status}`
        );
    }

    const signature =
        await signRequest({
            method: "POST",
            path,
            challenge:
                challengePayload.challenge,
            bodyBytes,
            privateKey:
                identity.privateKey
        });

    const response = await fetch(
        "http://127.0.0.1:8765" + path,
        {
            method: "POST",
            headers: {
                "Content-Type":
                    "application/json",
                "X-AGX-Challenge":
                    challengePayload.challenge,
                "X-AGX-Signature":
                    signature
            },
            body
        }
    );

    const result =
        await response.json();

    if (!response.ok) {
        const error = new Error(
            result.message ||
            result.error ||
            `Gateway HTTP ${response.status}`
        );
        if (result && typeof result === "object") {
            Object.assign(error, result);
        }
        throw error;
    }

    return result;
}

globalThis.AGXBrowserKeys = {
    ensureIdentity,
    getIdentity,
    saveIdentity,
    getSessionId: async () => (await ensureIdentity()).sessionId,
    getSessionIdForTab,
    deleteSessionIdForTab,
    authenticatedFetch
};
