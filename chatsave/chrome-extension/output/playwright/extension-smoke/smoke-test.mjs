import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { chromium } from 'playwright';

const chromePath = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const extensionPath = 'D:/codex/chatsave/chrome-extension';
const outputDir = 'D:/codex/chatsave/chrome-extension/output/playwright/extension-smoke';
const userDataDir = path.join(outputDir, 'chrome-profile');
const remoteDebuggingPort = 9223;

async function ensureCleanDir(dir) {
  await fs.rm(dir, { recursive: true, force: true });
  await fs.mkdir(dir, { recursive: true });
}

async function waitForChromeEndpoint(port, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (response.ok) {
        return await response.json();
      }
    } catch {}
    await delay(250);
  }
  throw new Error(`Timed out waiting for Chrome DevTools endpoint on port ${port}.`);
}

async function waitForServiceWorker(context, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const workers = context.serviceWorkers();
    const extensionWorker = workers.find((worker) => worker.url().startsWith('chrome-extension://') && worker.url().endsWith('/background.js'));
    if (extensionWorker) {
      return extensionWorker;
    }
    await delay(250);
  }
  throw new Error('Timed out waiting for extension service worker.');
}

async function collectExtensionsDebug(context) {
  const page = await context.newPage();
  await page.goto('chrome://extensions/', { waitUntil: 'load' });
  await page.waitForTimeout(2000);

  const details = await page.evaluate(() => {
    const results = [];

    function collectFromShadow(root) {
      if (!root) return;
      const items = root.querySelectorAll('extensions-item');
      items.forEach((item) => {
        const itemRoot = item.shadowRoot;
        const name = itemRoot?.querySelector('#name')?.textContent?.trim() || '';
        const version = itemRoot?.querySelector('#version')?.textContent?.trim() || '';
        const errors = Array.from(itemRoot?.querySelectorAll('[id*="error"], .error, [class*="error"]') || [])
          .map((node) => node.textContent?.trim())
          .filter(Boolean);
        if (name || version || errors.length > 0) {
          results.push({ name, version, errors });
        }
      });

      root.querySelectorAll('*').forEach((node) => {
        if (node.shadowRoot) {
          collectFromShadow(node.shadowRoot);
        }
      });
    }

    collectFromShadow(document);
    const bodyText = document.body?.innerText || '';

    return {
      items: results,
      bodyText
    };
  });

  await page.screenshot({ path: path.join(outputDir, 'extensions-page.png') });
  await page.close();
  return details;
}

async function collectPageState(page) {
  return await page.evaluate(() => ({
    ready: document.documentElement.getAttribute('data-chatgpt-exporter-ready'),
    failed: document.documentElement.getAttribute('data-chatgpt-exporter-failed'),
    failure: document.documentElement.getAttribute('data-chatgpt-exporter-failure'),
    hasApi: Boolean(window.ChatGPTExporter),
    hasAuto: Boolean(window.__CHATGPT_AUTO_EXPORT_LOADED__)
  }));
}

async function main() {
  await fs.mkdir(outputDir, { recursive: true });
  await ensureCleanDir(userDataDir);

  const summary = {
    extensionId: null,
    extensionsDebug: null,
    chromeLogs: {
      stdout: '',
      stderr: ''
    },
    error: null,
    options: null,
    popup: null,
    chatgpt: null
  };

  const chrome = spawn(chromePath, [
    `--remote-debugging-port=${remoteDebuggingPort}`,
    `--user-data-dir=${userDataDir}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--enable-logging=stderr',
    '--v=1',
    `--disable-extensions-except=${extensionPath}`,
    `--load-extension=${extensionPath}`,
    'about:blank'
  ], {
    stdio: ['ignore', 'pipe', 'pipe']
  });

  chrome.stdout?.on('data', (chunk) => {
    summary.chromeLogs.stdout += chunk.toString();
  });
  chrome.stderr?.on('data', (chunk) => {
    summary.chromeLogs.stderr += chunk.toString();
  });

  let browser;
  try {
    await waitForChromeEndpoint(remoteDebuggingPort);
    browser = await chromium.connectOverCDP(`http://127.0.0.1:${remoteDebuggingPort}`);
    const context = browser.contexts()[0];
    if (!context) {
      throw new Error('No browser context found after connecting to Chrome.');
    }

    let serviceWorker;
    try {
      serviceWorker = await waitForServiceWorker(context);
    } catch (error) {
      summary.extensionsDebug = await collectExtensionsDebug(context);
      summary.error = error.message;
      console.log(JSON.stringify(summary, null, 2));
      throw error;
    }
    summary.extensionId = new URL(serviceWorker.url()).host;

    const optionsPage = await context.newPage();
    await optionsPage.goto(`chrome-extension://${summary.extensionId}/pages/options.html`, { waitUntil: 'load' });
    await optionsPage.locator('#frequency').selectOption('daily');
    await optionsPage.locator('#timeOfDay').fill('09:30');
    await optionsPage.locator('#settings-form button[type="submit"]').click();
    await optionsPage.locator('#save-state').waitFor({ state: 'visible', timeout: 5000 });
    summary.options = {
      title: await optionsPage.title(),
      heading: await optionsPage.locator('h1').textContent(),
      saveState: await optionsPage.locator('#save-state').textContent()
    };
    await optionsPage.screenshot({ path: path.join(outputDir, 'options-page.png') });

    const popupPage = await context.newPage();
    await popupPage.goto(`chrome-extension://${summary.extensionId}/pages/popup.html`, { waitUntil: 'load' });
    await popupPage.locator('#next-run').waitFor({ state: 'visible', timeout: 5000 });
    summary.popup = {
      title: await popupPage.title(),
      nextRun: await popupPage.locator('#next-run').textContent(),
      reminderNote: await popupPage.locator('#reminder-note').textContent()
    };
    await popupPage.screenshot({ path: path.join(outputDir, 'popup-page.png') });

    const chatPage = await context.newPage();
    const consoleErrors = [];
    chatPage.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await chatPage.goto('https://chatgpt.com/', { waitUntil: 'domcontentloaded' });
    await chatPage.waitForTimeout(5000);

    const initialState = await collectPageState(chatPage);
    let dialogVisible = false;
    if (initialState.hasApi) {
      dialogVisible = await chatPage.evaluate(() => {
        window.ChatGPTExporter.showDialog();
        return Boolean(document.getElementById('export-dialog-overlay'));
      });
    }

    summary.chatgpt = {
      state: initialState,
      dialogVisible,
      consoleErrors
    };
    await chatPage.screenshot({ path: path.join(outputDir, 'chatgpt-page.png') });

    console.log(JSON.stringify(summary, null, 2));
  } finally {
    await browser?.close().catch(() => {});
    chrome.kill('SIGKILL');
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
