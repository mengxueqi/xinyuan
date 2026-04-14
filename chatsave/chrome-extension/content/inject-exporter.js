(function injectExporter() {
    const EXPORT_READY_EVENT = 'CHATGPT_EXPORTER_READY';
    const EXPORT_FAILED_EVENT = 'CHATGPT_EXPORTER_FAILED';
    const READY_ATTR = 'data-chatgpt-exporter-ready';
    const FAILED_ATTR = 'data-chatgpt-exporter-failed';
    const FAILURE_REASON_ATTR = 'data-chatgpt-exporter-failure';
    const BOOT_TIMEOUT_MS = 5000;

    if (window.__CHATGPT_EXPORTER_INJECTED__) return;
    window.__CHATGPT_EXPORTER_INJECTED__ = true;
    const resetInjectedFlag = () => {
        delete window.__CHATGPT_EXPORTER_INJECTED__;
    };

    // Prevent double injection if the page script is already running
    if (document.documentElement.getAttribute(READY_ATTR) === '1') {
        return;
    }

    let bootSettled = false;
    const cleanup = () => {
        clearTimeout(timeoutId);
        window.removeEventListener(EXPORT_READY_EVENT, handleReady);
    };
    const handleReady = () => {
        if (bootSettled) return;
        bootSettled = true;
        document.documentElement.setAttribute(READY_ATTR, '1');
        document.documentElement.removeAttribute(FAILED_ATTR);
        document.documentElement.removeAttribute(FAILURE_REASON_ATTR);
        cleanup();
    };
    const failBoot = (message) => {
        if (bootSettled) return;
        bootSettled = true;
        document.documentElement.removeAttribute(READY_ATTR);
        document.documentElement.setAttribute(FAILED_ATTR, '1');
        document.documentElement.setAttribute(FAILURE_REASON_ATTR, message);
        cleanup();
        resetInjectedFlag();
        window.dispatchEvent(new CustomEvent(EXPORT_FAILED_EVENT, {
            detail: { message }
        }));
        console.error('[ChatGPT Exporter]', message);
    };
    const timeoutId = setTimeout(() => {
        failBoot('Timed out waiting for exporter initialization.');
    }, BOOT_TIMEOUT_MS);

    document.documentElement.removeAttribute(FAILED_ATTR);
    document.documentElement.removeAttribute(FAILURE_REASON_ATTR);
    window.addEventListener(EXPORT_READY_EVENT, handleReady, { once: true });

    const script = document.createElement('script');
    script.src = chrome.runtime.getURL('exporter.user.js');
    script.type = 'text/javascript';
    script.onload = () => {
        script.remove();
        if (document.documentElement.getAttribute(READY_ATTR) === '1') {
            handleReady();
        }
    };
    script.onerror = () => {
        script.remove();
        failBoot('Failed to inject exporter.user.js');
    };
    document.documentElement.appendChild(script);
})();
