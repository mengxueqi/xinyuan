(function () {
    if (window.__CHATGPT_AUTO_EXPORT_LOADED__) return;
    window.__CHATGPT_AUTO_EXPORT_LOADED__ = true;

    const EXPORT_READY_EVENT = 'CHATGPT_EXPORTER_READY';
    const EXPORT_FAILED_EVENT = 'CHATGPT_EXPORTER_FAILED';
    const COMMAND_TYPE = 'CHATGPT_EXPORTER_COMMAND';
    let exporterReady = false;
    let exporterFailed = false;
    let exporterFailureReason = '';
    const pendingCommands = [];
    const statusWaiters = [];

    function queueCommand(action, payload) {
        if (exporterFailed) {
            return { ok: false, error: exporterFailureReason || 'Exporter failed to initialize.' };
        }
        if (exporterReady) {
            dispatchCommand(action, payload);
            return { ok: true, state: 'dispatched' };
        } else {
            pendingCommands.push({ action, payload });
            return { ok: true, state: 'queued' };
        }
    }

    function dispatchCommand(action, payload) {
        window.postMessage({
            type: COMMAND_TYPE,
            action,
            payload
        }, '*');
    }

    window.addEventListener(EXPORT_READY_EVENT, () => markReady());
    window.addEventListener(EXPORT_FAILED_EVENT, (event) => markFailed(event?.detail?.message));

    function markReady() {
        exporterReady = true;
        exporterFailed = false;
        exporterFailureReason = '';
        while (pendingCommands.length) {
            const cmd = pendingCommands.shift();
            dispatchCommand(cmd.action, cmd.payload);
        }
        flushStatusWaiters({ ok: true, state: 'ready' });
    }

    function markFailed(message) {
        exporterReady = false;
        exporterFailed = true;
        exporterFailureReason = message || 'Exporter failed to initialize.';
        pendingCommands.length = 0;
        flushStatusWaiters({ ok: false, error: exporterFailureReason });
    }

    function flushStatusWaiters(result) {
        while (statusWaiters.length) {
            const resolve = statusWaiters.shift();
            resolve(result);
        }
    }

    function waitForExporterState(timeoutMs = 5500) {
        if (exporterReady) {
            return Promise.resolve({ ok: true, state: 'ready' });
        }
        if (exporterFailed) {
            return Promise.resolve({ ok: false, error: exporterFailureReason || 'Exporter failed to initialize.' });
        }
        return new Promise((resolve) => {
            const timer = setTimeout(() => {
                const index = statusWaiters.indexOf(onResult);
                if (index >= 0) {
                    statusWaiters.splice(index, 1);
                }
                resolve({ ok: false, error: 'Timed out waiting for exporter initialization.' });
            }, timeoutMs);

            const onResult = (result) => {
                clearTimeout(timer);
                resolve(result);
            };

            statusWaiters.push(onResult);
        });
    }

    if (document.documentElement.getAttribute('data-chatgpt-exporter-ready') === '1') {
        markReady();
    } else if (document.documentElement.getAttribute('data-chatgpt-exporter-failed') === '1') {
        markFailed(document.documentElement.getAttribute('data-chatgpt-exporter-failure') || undefined);
    }

    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message?.type === 'OPEN_EXPORT_DIALOG') {
            const result = queueCommand('OPEN_DIALOG');
            if (!result.ok || result.state === 'dispatched') {
                sendResponse(result);
                return false;
            }

            waitForExporterState().then((status) => {
                if (!status.ok) {
                    sendResponse(status);
                    return;
                }
                sendResponse({ ok: true, state: 'queued' });
            });
            return true;
        }
        return false;
    });
})();
