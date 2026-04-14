function wrapChromeCall(invoke) {
    return new Promise((resolve, reject) => {
        invoke((result) => {
            if (chrome.runtime.lastError) {
                reject(chrome.runtime.lastError);
            } else {
                resolve(result);
            }
        });
    });
}

export const storage = {
    get: (keys) => wrapChromeCall((callback) => chrome.storage.sync.get(keys, callback)),
    set: (items) => wrapChromeCall((callback) => chrome.storage.sync.set(items, callback))
};

export const runtime = {
    sendMessage: (message) => wrapChromeCall((callback) => chrome.runtime.sendMessage(message, callback))
};

export const tabs = {
    query: (queryOptions) => wrapChromeCall((callback) => chrome.tabs.query(queryOptions, callback)),
    sendMessage: (tabId, payload) => wrapChromeCall((callback) => chrome.tabs.sendMessage(tabId, payload, callback))
};
