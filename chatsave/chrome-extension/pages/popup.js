import { normalizeSettings, calculateNextTrigger } from '../utils/schedule.js';
import { storage, tabs } from '../utils/chrome-helpers.js';

const nextRunEl = document.getElementById('next-run');
const reminderNoteEl = document.getElementById('reminder-note');
const openDialogBtn = document.getElementById('open-dialog-btn');
const openOptionsBtn = document.getElementById('open-options-btn');

document.addEventListener('DOMContentLoaded', init);

async function init() {
    try {
        const { settings } = await storage.get('settings');
        const normalized = normalizeSettings(settings);
        renderSchedule(normalized);

        openDialogBtn.addEventListener('click', () => openDialog());
        openOptionsBtn.addEventListener('click', () => chrome.runtime.openOptionsPage());
    } catch (error) {
        console.error('Failed to initialize popup:', error);
        nextRunEl.textContent = '加载失败';
        reminderNoteEl.textContent = '无法读取当前设置，请稍后重试';
    }
}

function renderSchedule(settings) {
    const nextTrigger = calculateNextTrigger(settings);
    if (!nextTrigger) {
        nextRunEl.textContent = '未启用定时提醒';
    } else {
        const date = new Date(nextTrigger);
        nextRunEl.textContent = `下次提醒：${date.toLocaleString()}`;
    }
    reminderNoteEl.textContent = '提醒只负责通知，不会自动导出';
}

async function openDialog() {
    const tab = await getActiveChatGPTTab();
    if (!tab) {
        chrome.tabs.create({ url: 'https://chatgpt.com/' });
        return;
    }
    const isNoReceiverError = (err) => {
        const message = err?.message || String(err || '');
        return message.includes('Receiving end does not exist') || message.includes('Could not establish connection');
    };

    const requestOpenDialog = async () => {
        const response = await tabs.sendMessage(tab.id, { type: 'OPEN_EXPORT_DIALOG' });
        if (response?.ok) {
            return;
        }
        throw new Error(response?.error || '页面导出脚本尚未就绪。');
    };

    try {
        await requestOpenDialog();
        return;
    } catch (error) {
        console.warn('Failed to open exporter dialog directly, retrying after injection...', error);
    }

    try {
        await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content/inject-exporter.js', 'content/auto-export.js']
        });
        await requestOpenDialog();
    } catch (retryError) {
        if (!isNoReceiverError(retryError)) {
            console.error('Retry failed:', retryError);
        }
        alert('无法连接到页面脚本。请尝试刷新 ChatGPT 页面后再试。');
    }
}

async function getActiveChatGPTTab() {
    const [tab] = await tabs.query({ active: true, currentWindow: true });
    const url = tab?.url || '';
    const isChatGPT = /^https:\/\/(.*\.)?chatgpt\.com/.test(url);
    const isOpenAI = /^https:\/\/(.*\.)?chat\.openai\.com/.test(url);
    
    if (tab && (isChatGPT || isOpenAI)) {
        return tab;
    }
    return null;
}
