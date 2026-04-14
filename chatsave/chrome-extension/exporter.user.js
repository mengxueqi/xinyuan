(function () {
    'use strict';

    // --- 配置与全局变量 ---
    const BASE_DELAY = 600;
    const JITTER = 400;
    const PAGE_LIMIT = 100;
    const PROJECT_SIDEBAR_PREVIEW = 5;
    const DEFAULT_EXPORT_FORMAT = 'md';
    let accessToken = null;
    let capturedWorkspaceIds = new Set(); // 使用Set存储网络拦截到的ID，确保唯一性
    let lastCapturedWorkspaceId = null;

    // --- 核心：网络拦截与信息捕获 ---
    (function interceptNetwork() {
        const rawFetch = window.fetch;
        window.fetch = async function (resource, options) {
            const headerSource = options?.headers || resource?.headers;
            tryCaptureToken(headerSource);
            tryCaptureWorkspaceId(headerSource, 'Fetch');
            return rawFetch.apply(this, arguments);
        };

        const rawOpen = XMLHttpRequest.prototype.open;
        const rawSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;
        XMLHttpRequest.prototype.open = function () {
            this.__chatgptExporterHeaders = {};
            return rawOpen.apply(this, arguments);
        };
        XMLHttpRequest.prototype.setRequestHeader = function (name, value) {
            try {
                if (!this.__chatgptExporterHeaders) {
                    this.__chatgptExporterHeaders = {};
                }
                this.__chatgptExporterHeaders[name] = value;
                tryCaptureToken(this.__chatgptExporterHeaders);
                tryCaptureWorkspaceId(this.__chatgptExporterHeaders, 'XHR');
            } catch (_) {}
            return rawSetRequestHeader.apply(this, arguments);
        };
    })();

    function readHeaderValue(headers, headerName) {
        if (!headers) return null;
        const normalizedHeaderName = headerName.toLowerCase();
        if (typeof headers === 'string') {
            return normalizedHeaderName === 'authorization' ? headers : null;
        }
        if (typeof Headers !== 'undefined' && headers instanceof Headers) {
            return headers.get(headerName) || headers.get(normalizedHeaderName);
        }
        if (Array.isArray(headers)) {
            const match = headers.find(([key]) => typeof key === 'string' && key.toLowerCase() === normalizedHeaderName);
            return match ? match[1] : null;
        }
        if (typeof headers.get === 'function') {
            try {
                return headers.get(headerName) || headers.get(normalizedHeaderName);
            } catch (_) {}
        }
        if (typeof headers === 'object') {
            const direct = headers[headerName] ?? headers[normalizedHeaderName];
            if (direct != null) return direct;
            const matchedKey = Object.keys(headers).find(key => key.toLowerCase() === normalizedHeaderName);
            return matchedKey ? headers[matchedKey] : null;
        }
        return null;
    }

    function tryCaptureToken(headerSource) {
        const h = readHeaderValue(headerSource, 'Authorization');
        if (h?.startsWith('Bearer ')) {
            const token = h.slice(7);
            if (token && token.toLowerCase() !== 'dummy') {
                accessToken = token;
            }
        }
    }

    function normalizeWorkspaceId(value) {
        if (typeof value !== 'string') return null;
        const normalized = value.trim().replace(/^"+|"+$/g, '');
        return normalized || null;
    }

    function tryCaptureWorkspaceId(headerSource, sourceLabel = 'Request') {
        const workspaceId = normalizeWorkspaceId(readHeaderValue(headerSource, 'ChatGPT-Account-Id'));
        if (workspaceId) {
            lastCapturedWorkspaceId = workspaceId;
        }
        if (typeof workspaceId !== 'string' || !workspaceId || capturedWorkspaceIds.has(workspaceId)) {
            return;
        }
        console.log(`🎯 [${sourceLabel}] 捕获到 Workspace ID:`, workspaceId);
        capturedWorkspaceIds.add(workspaceId);
    }

    async function ensureAccessToken() {
        if (accessToken) return accessToken;
        try {
            const session = await (await fetch('/api/auth/session?unstable_client=true')).json();
            if (session.accessToken) {
                accessToken = session.accessToken;
                return accessToken;
            }
        } catch (_) {}
        alert('无法获取 Access Token。请刷新页面或打开任意一个对话后再试。');
        return null;
    }

    // --- 辅助函数 ---
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const jitter = () => BASE_DELAY + Math.random() * JITTER;
    const sanitizeFilename = (name) => name.replace(/[\/\\?%*:|"<>]/g, '-').trim();
    const normalizeEpochSeconds = (value) => {
        if (!value) return 0;
        if (typeof value === 'number' && Number.isFinite(value)) {
            return value > 1e12 ? Math.floor(value / 1000) : value;
        }
        if (typeof value === 'string') {
            const parsed = Date.parse(value);
            if (!Number.isNaN(parsed)) {
                return Math.floor(parsed / 1000);
            }
        }
        return 0;
    };
    const formatTimestamp = (value) => {
        const seconds = normalizeEpochSeconds(value);
        if (!seconds) return '';
        const date = new Date(seconds * 1000);
        return Number.isNaN(date.getTime()) ? '' : date.toLocaleString();
    };
    const parseDateInputToEpoch = (value, isEnd = false) => {
        if (!value) return null;
        const parts = value.split('-').map(Number);
        if (parts.length !== 3 || parts.some(Number.isNaN)) return null;
        const [year, month, day] = parts;
        const date = isEnd
            ? new Date(year, month - 1, day, 23, 59, 59, 999)
            : new Date(year, month - 1, day, 0, 0, 0, 0);
        const epochMs = date.getTime();
        return Number.isNaN(epochMs) ? null : Math.floor(epochMs / 1000);
    };

    /**
     * [新增] 从Cookie中获取 oai-device-id
     * @returns {string|null} - 返回设备ID或null
     */
    function getOaiDeviceId() {
        const cookieString = document.cookie;
        const match = cookieString.match(/oai-did=([^;]+)/);
        return match ? match[1] : null;
    }

    function normalizeExportFormat(format) {
        return format === 'json' ? 'json' : DEFAULT_EXPORT_FORMAT;
    }

    function getExportFormatLabel(format) {
        return normalizeExportFormat(format) === 'json' ? 'JSON' : 'Markdown';
    }

    function generateConversationFileStem(convData) {
        const convId = convData.conversation_id || '';
        const shortId = convId.includes('-') ? convId.split('-').pop() : (convId || Date.now().toString(36));
        let baseName = convData.title;
        if (!baseName || baseName.trim().toLowerCase() === 'new chat') {
            baseName = 'Untitled Conversation';
        }
        return `${sanitizeFilename(baseName)}_${shortId}`;
    }

    function generateDownloadFilename(convData, exportFormat = DEFAULT_EXPORT_FORMAT, projectTitle = null) {
        const normalizedFormat = normalizeExportFormat(exportFormat);
        const parts = [];
        if (projectTitle) {
            parts.push(sanitizeFilename(projectTitle));
        }
        parts.push(generateConversationFileStem(convData));
        return `${parts.filter(Boolean).join('__')}.${normalizedFormat}`;
    }

    function buildExportFile(convData, exportFormat = DEFAULT_EXPORT_FORMAT, projectTitle = null) {
        const normalizedFormat = normalizeExportFormat(exportFormat);
        if (normalizedFormat === 'json') {
            return {
                filename: generateDownloadFilename(convData, normalizedFormat, projectTitle),
                mimeType: 'application/json;charset=utf-8',
                content: JSON.stringify(convData, null, 2)
            };
        }

        return {
            filename: generateDownloadFilename(convData, normalizedFormat, projectTitle),
            mimeType: 'text/markdown;charset=utf-8',
            content: convertConversationToMarkdown(convData)
        };
    }

    function cleanMessageContent(text) {
        if (!text) return '';
        return text
            .replace(/\uE200cite(?:\uE202turn\d+(?:search|view)\d+)+\uE201/gi, '')
            .replace(/cite(?:turn\d+(?:search|view)\d+)+/gi, '')
            .trim();
    }

    function processContentReferences(text, contentReferences) {
        if (!text || !Array.isArray(contentReferences) || contentReferences.length === 0) {
            return { text, footnotes: [] };
        }

        const references = contentReferences.filter(ref => ref && typeof ref.matched_text === 'string' && ref.matched_text.length > 0);
        if (references.length === 0) {
            return { text, footnotes: [] };
        }

        const getReferenceInfo = (ref) => {
            const item = Array.isArray(ref.items) ? ref.items[0] : null;
            const url = item?.url || (Array.isArray(ref.safe_urls) ? ref.safe_urls[0] : '') || '';
            const title = item?.title || '';
            let label = item?.attribution || '';
            if (!label && typeof ref.alt === 'string') {
                const match = ref.alt.match(/\[([^\]]+)\]\([^)]+\)/);
                if (match) label = match[1];
            }
            if (!label) label = title || url;
            return { url, title, label };
        };

        const footnotes = [];
        const footnoteIndexByKey = new Map();
        const citationRefs = references
            .filter(ref => ref.type === 'grouped_webpages')
            .sort((a, b) => {
                const aIdx = Number.isFinite(a.start_idx) ? a.start_idx : Number.MAX_SAFE_INTEGER;
                const bIdx = Number.isFinite(b.start_idx) ? b.start_idx : Number.MAX_SAFE_INTEGER;
                return aIdx - bIdx;
            });

        citationRefs.forEach(ref => {
            const info = getReferenceInfo(ref);
            if (!info.url) return;
            const key = `${info.url}|${info.title}`;
            if (footnoteIndexByKey.has(key)) return;
            const index = footnotes.length + 1;
            footnoteIndexByKey.set(key, index);
            footnotes.push({ index, url: info.url, title: info.title, label: info.label });
        });

        const sortedByReplacement = references
            .slice()
            .sort((a, b) => {
                const aIdx = Number.isFinite(a.start_idx) ? a.start_idx : -1;
                const bIdx = Number.isFinite(b.start_idx) ? b.start_idx : -1;
                if (aIdx !== -1 || bIdx !== -1) {
                    return bIdx - aIdx;
                }
                return (b.matched_text?.length || 0) - (a.matched_text?.length || 0);
            });

        const findUniqueMatchIndex = (sourceText, needle) => {
            if (!needle) return -1;
            const firstIndex = sourceText.indexOf(needle);
            if (firstIndex === -1) return -1;
            const secondIndex = sourceText.indexOf(needle, firstIndex + needle.length);
            return secondIndex === -1 ? firstIndex : -1;
        };

        let output = text;
        sortedByReplacement.forEach(ref => {
            if (!ref?.matched_text || ref.type === 'sources_footnote') return;
            let replacement = '';
            if (ref.type === 'grouped_webpages') {
                const info = getReferenceInfo(ref);
                if (info.url) {
                    const key = `${info.url}|${info.title}`;
                    const index = footnoteIndexByKey.get(key);
                    replacement = index ? `([${info.label}][${index}])` : (ref.alt || '');
                } else {
                    replacement = ref.alt || '';
                }
            } else {
                replacement = ref.alt || '';
            }

            if (Number.isFinite(ref.start_idx) && Number.isFinite(ref.end_idx)) {
                if (output.slice(ref.start_idx, ref.end_idx) === ref.matched_text) {
                    output = output.slice(0, ref.start_idx) + replacement + output.slice(ref.end_idx);
                    return;
                }
            }

            // Safer fallback: only replace when the matched text appears exactly once.
            const uniqueMatchIndex = findUniqueMatchIndex(output, ref.matched_text);
            if (uniqueMatchIndex !== -1) {
                output = output.slice(0, uniqueMatchIndex) + replacement + output.slice(uniqueMatchIndex + ref.matched_text.length);
            }
        });

        return { text: output, footnotes };
    }

    function getActiveConversationNodeIds(convData) {
        const mapping = convData?.mapping;
        if (!mapping) return [];

        const mappingKeys = Object.keys(mapping);
        if (mappingKeys.length === 0) return [];
        const rootId = mapping['client-created-root']
            ? 'client-created-root'
            : mappingKeys.find(id => !mapping[id]?.parent) || mappingKeys[0];
        const currentNodeId = convData?.current_node;

        if (currentNodeId && mapping[currentNodeId]) {
            const path = [];
            const visited = new Set();
            let nodeId = currentNodeId;
            while (nodeId && !visited.has(nodeId) && mapping[nodeId]) {
                visited.add(nodeId);
                path.push(nodeId);
                nodeId = mapping[nodeId]?.parent || null;
            }
            return path.reverse();
        }

        const visited = new Set();
        const path = [];
        let nodeId = rootId;
        while (nodeId && !visited.has(nodeId) && mapping[nodeId]) {
            visited.add(nodeId);
            path.push(nodeId);
            const children = Array.isArray(mapping[nodeId]?.children)
                ? mapping[nodeId].children.filter(childId => mapping[childId])
                : [];
            if (children.length === 0) break;
            if (children.length === 1) {
                nodeId = children[0];
                continue;
            }
            nodeId = children
                .slice()
                .sort((a, b) => {
                    const aNode = mapping[a];
                    const bNode = mapping[b];
                    const aTs = normalizeEpochSeconds(aNode?.message?.create_time || aNode?.message?.update_time || 0);
                    const bTs = normalizeEpochSeconds(bNode?.message?.create_time || bNode?.message?.update_time || 0);
                    return bTs - aTs;
                })[0];
        }

        return path;
    }

    function extractConversationMessages(convData) {
        const mapping = convData?.mapping;
        if (!mapping) return [];

        const messages = [];
        const activeNodeIds = getActiveConversationNodeIds(convData);

        activeNodeIds.forEach((nodeId) => {
            const node = mapping[nodeId];
            if (!node) return;

            const msg = node.message;
            if (!msg) return;

            const author = msg.author?.role;
            const isHidden = msg.metadata?.is_visually_hidden_from_conversation ||
                msg.metadata?.is_contextual_answers_system_message;
            if (!author || author === 'system' || isHidden) return;

            const content = msg.content;
            if (content?.content_type !== 'text' || !Array.isArray(content.parts)) return;

            const rawText = content.parts
                .map(part => typeof part === 'string' ? part : (part?.text ?? ''))
                .filter(Boolean)
                .join('\n');
            const contentReferences = msg.metadata?.content_references || [];
            let processedText = rawText;
            let footnotes = [];
            if (Array.isArray(contentReferences) && contentReferences.length > 0) {
                const processed = processContentReferences(rawText, contentReferences);
                processedText = processed.text;
                footnotes = processed.footnotes;
            }
            const cleaned = cleanMessageContent(processedText);
            if (!cleaned) return;

            messages.push({
                role: author,
                content: cleaned,
                create_time: msg.create_time || null,
                footnotes
            });
        });

        return messages;
    }

    function convertConversationToMarkdown(convData) {
        const messages = extractConversationMessages(convData);
        if (messages.length === 0) {
            return '# Conversation\nNo visible user or assistant messages were exported.\n';
        }

        const mdLines = [];
        messages.forEach(msg => {
            const roleLabel = msg.role === 'user' ? '# User' : '# Assistant';
            mdLines.push(roleLabel);
            mdLines.push(msg.content);
            if (Array.isArray(msg.footnotes) && msg.footnotes.length > 0) {
                mdLines.push('');
                msg.footnotes
                    .slice()
                    .sort((a, b) => a.index - b.index)
                    .forEach(note => {
                        if (!note.url) return;
                        const title = note.title ? ` "${note.title}"` : '';
                        mdLines.push(`[${note.index}]: ${note.url}${title}`);
                    });
            }
            mdLines.push('');
        });

        return mdLines.join('\n').trim() + '\n';
    }

    function downloadFile(blob, filename) {
        const a = document.createElement('a');
        const objectUrl = URL.createObjectURL(blob);
        a.href = objectUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    }

    function downloadTextFile(content, filename, mimeType) {
        downloadFile(new Blob([content], { type: mimeType }), filename);
    }

    function recordExportFailure(failures, details, error) {
        const message = error?.message || String(error || 'Unknown error');
        const failure = {
            id: details?.id || '',
            title: details?.title || '',
            projectTitle: details?.projectTitle || '',
            error: message
        };
        failures.push(failure);
        console.error('[ChatGPT Exporter] Failed to export conversation:', failure, error);
    }

    function downloadFailureReport(failures) {
        const timestamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
        const filename = `chatgpt_export_errors_${timestamp}.json`;
        downloadTextFile(JSON.stringify({
            generatedAt: new Date().toISOString(),
            failureCount: failures.length,
            failures
        }, null, 2), filename, 'application/json;charset=utf-8');
        return filename;
    }

    async function downloadConversationExport(entry, workspaceId, exportFormat, failures) {
        try {
            const convData = await getConversation(entry.id, workspaceId);
            const exportFile = buildExportFile(convData, exportFormat, entry?.projectTitle);
            downloadTextFile(exportFile.content, exportFile.filename, exportFile.mimeType);
            return true;
        } catch (error) {
            recordExportFailure(failures, entry, error);
            return false;
        } finally {
            await sleep(jitter());
        }
    }

    // --- 导出流程核心逻辑 ---
    function getExportButton() {
        let btn = document.getElementById('gpt-rescue-btn');
        if (!btn) {
            btn = document.createElement('button');
            btn.id = 'gpt-rescue-btn';
            Object.assign(btn.style, {
                position: 'fixed', bottom: '24px', right: '24px', zIndex: '99997',
                padding: '10px 14px', borderRadius: '8px', border: 'none', cursor: 'pointer',
                fontWeight: 'bold', background: '#10a37f', color: '#fff', fontSize: '14px',
                boxShadow: '0 3px 12px rgba(0,0,0,.15)', userSelect: 'none'
            });
            btn.textContent = '下载对话';
            btn.onclick = showExportDialog;
            document.body.appendChild(btn);
        }
        return btn;
    }

    async function exportConversations(options = {}) {
        const {
            mode = 'personal',
            workspaceId = null,
            conversationEntries = null,
            exportFormat = DEFAULT_EXPORT_FORMAT
        } = options;
        const normalizedExportFormat = normalizeExportFormat(exportFormat);
        const btn = getExportButton();
        btn.disabled = true;

        if (!await ensureAccessToken()) {
            btn.disabled = false;
            btn.textContent = '下载对话';
            return;
        }

        if (!Array.isArray(conversationEntries) || conversationEntries.length === 0) {
            btn.disabled = false;
            btn.textContent = '下载对话';
            throw new Error('请先选择至少一条对话后再下载。');
        }

        try {
            const exportFailures = [];
            let exportedCount = 0;
            for (let i = 0; i < conversationEntries.length; i++) {
                const entry = conversationEntries[i];
                const label = entry?.title ? entry.title.slice(0, 12) : '对话';
                btn.textContent = `📥 ${label} (${i + 1}/${conversationEntries.length})`;
                if (await downloadConversationExport(entry, workspaceId, normalizedExportFormat, exportFailures)) {
                    exportedCount += 1;
                }
            }

            btn.textContent = '⬇️ 准备下载文件…';
            if (exportFailures.length > 0) {
                const failureReportName = downloadFailureReport(exportFailures);
                const summary = exportedCount > 0
                    ? `✅ 下载已完成。\n成功下载 ${exportedCount} 个 ${getExportFormatLabel(normalizedExportFormat)} 文件，失败 ${exportFailures.length} 条。`
                    : `⚠️ 本次未成功下载任何对话。\n失败 ${exportFailures.length} 条。`;
                alert(`${summary}\n失败详情已另存为 ${failureReportName}。`);
            } else {
                const downloadHint = exportedCount > 1
                    ? '\n如果浏览器提示“允许多个下载”，请允许当前站点继续下载。'
                    : '';
                alert(`✅ 下载完成！共下载 ${exportedCount} 个 ${getExportFormatLabel(normalizedExportFormat)} 文件。${downloadHint}`);
            }
            btn.textContent = '✅ 完成';

        } catch (e) {
            console.error("导出过程中发生严重错误:", e);
            alert(`导出失败: ${e.message}。详情请查看控制台（F12 -> Console）。`);
            btn.textContent = '⚠️ Error';
        } finally {
            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = '下载对话';
            }, 3000);
        }
    }

    async function startExportProcess(mode, workspaceId, exportFormat = DEFAULT_EXPORT_FORMAT) {
        showConversationPicker({ mode, workspaceId, exportFormat });
    }

    async function startProjectSpaceExportProcess(workspaceId = null, exportFormat = DEFAULT_EXPORT_FORMAT) {
        showConversationPicker({ mode: 'project', workspaceId, exportFormat });
    }

    async function startSelectiveExportProcess(mode, workspaceId, conversationEntries, exportFormat = DEFAULT_EXPORT_FORMAT) {
        await exportConversations({ mode, workspaceId, conversationEntries, exportFormat });
    }

    function startScheduledExport(options = {}) {
        const {
            mode = 'personal',
            workspaceId = null,
            autoConfirm = false,
            source = 'schedule',
            exportFormat = DEFAULT_EXPORT_FORMAT
        } = options;
        const proceed = () => {
            try {
                if (mode === 'project') {
                    startProjectSpaceExportProcess(workspaceId, exportFormat);
                    return;
                }
                startExportProcess(mode, workspaceId, exportFormat);
            } catch (err) {
                console.error('[ChatGPT Exporter] 打开选择器失败:', err);
            }
        };

        if (autoConfirm) {
            proceed();
            return;
        }

        const modeLabel = mode === 'team' ? '团队空间' : mode === 'project' ? '项目空间' : '个人空间';
        const formatLabel = getExportFormatLabel(exportFormat);
        if (confirm(`Chrome 扩展准备打开 ${modeLabel} 的对话选择器，并以 ${formatLabel} 格式下载选中内容（来源: ${source}）。是否继续？`)) {
            proceed();
        }
    }

    // --- API 调用函数 ---
    async function getProjects(workspaceId) {
        if (!workspaceId) return [];
        const deviceId = getOaiDeviceId();
        if (!deviceId) {
            throw new Error('无法获取 oai-device-id，请确保已登录并刷新页面。');
        }
        const headers = {
            'Authorization': `Bearer ${accessToken}`,
            'ChatGPT-Account-Id': workspaceId,
            'oai-device-id': deviceId
        };
        const r = await fetch(`/backend-api/gizmos/snorlax/sidebar`, { headers });
        if (!r.ok) {
            console.warn(`获取项目(Gizmo)列表失败 (${r.status})`);
            return [];
        }
        const data = await r.json();
        const projects = [];
        data.items?.forEach(item => {
            if (item?.gizmo?.id && item?.gizmo?.display?.name) {
                projects.push({ id: item.gizmo.id, title: item.gizmo.display.name });
            }
        });
        return projects;
    }

    function getCookieWorkspaceId() {
        const match = document.cookie.match(/(?:^|; )_account=([^;]+)/);
        if (!match?.[1]) return null;
        try {
            return normalizeWorkspaceId(decodeURIComponent(match[1]));
        } catch (_) {
            return normalizeWorkspaceId(match[1]);
        }
    }

    function resolveWorkspaceId(workspaceId, options = {}) {
        const { allowSingleDetectedFallback = false } = options;
        const explicitWorkspaceId = normalizeWorkspaceId(workspaceId);
        if (explicitWorkspaceId) return explicitWorkspaceId;

        const detectedIds = detectAllWorkspaceIds();
        if (lastCapturedWorkspaceId && (!detectedIds.length || detectedIds.includes(lastCapturedWorkspaceId))) {
            return lastCapturedWorkspaceId;
        }

        const cookieWorkspaceId = getCookieWorkspaceId();
        if (cookieWorkspaceId && (
            detectedIds.length === 0 ||
            (detectedIds.length === 1 && detectedIds[0] === cookieWorkspaceId)
        )) {
            return cookieWorkspaceId;
        }

        if (allowSingleDetectedFallback && detectedIds.length === 1) {
            return detectedIds[0];
        }

        return null;
    }

    async function getProjectSpaces(workspaceId, options = {}) {
        const deviceId = getOaiDeviceId();
        if (!deviceId) {
            throw new Error('无法获取 oai-device-id，请确保已登录并刷新页面。');
        }
        const headers = {
            'Authorization': `Bearer ${accessToken}`,
            'oai-device-id': deviceId
        };
        const resolvedWorkspaceId = resolveWorkspaceId(workspaceId, { allowSingleDetectedFallback: true });
        if (resolvedWorkspaceId) { headers['ChatGPT-Account-Id'] = resolvedWorkspaceId; }

        const query = new URLSearchParams();
        if (options.conversationsPerGizmo !== undefined) {
            query.set('conversations_per_gizmo', String(options.conversationsPerGizmo));
        }
        if (options.ownedOnly !== undefined) {
            query.set('owned_only', options.ownedOnly ? 'true' : 'false');
        }
        const url = query.toString()
            ? `/backend-api/gizmos/snorlax/sidebar?${query.toString()}`
            : '/backend-api/gizmos/snorlax/sidebar';

        const r = await fetch(url, { headers });
        if (!r.ok) {
            throw new Error(`获取项目空间列表失败 (${r.status})`);
        }
        const data = await r.json();
        const projects = [];
        data.items?.forEach(item => {
            const rawGizmo = item?.gizmo?.gizmo || item?.gizmo || item;
            const display = rawGizmo?.display || item?.gizmo?.display || item?.display;
            const id = rawGizmo?.id || item?.gizmo?.id || item?.id;
            const title = display?.name || rawGizmo?.name || 'Untitled Project';
            if (!id) return;
            projects.push({
                id,
                title,
                conversations: item?.conversations?.items || []
            });
        });
        return projects;
    }

    async function collectIds(btn, workspaceId, gizmoId) {
        const all = new Set();
        const deviceId = getOaiDeviceId();
        if (!deviceId) {
            throw new Error('无法获取 oai-device-id，请确保已登录并刷新页面。');
        }
        const headers = {
            'Authorization': `Bearer ${accessToken}`,
            'oai-device-id': deviceId
        };
        if (workspaceId) { headers['ChatGPT-Account-Id'] = workspaceId; }

        if (gizmoId) {
            let cursor = '0';
            do {
                const r = await fetch(`/backend-api/gizmos/${gizmoId}/conversations?cursor=${cursor}`, { headers });
                if (!r.ok) throw new Error(`列举项目对话列表失败 (${r.status})`);
                const j = await r.json();
                j.items?.forEach(it => all.add(it.id));
                cursor = j.cursor;
                await sleep(jitter());
            } while (cursor);
        } else {
            for (const is_archived of [false, true]) {
                let offset = 0, has_more = true, page = 0;
                do {
                    btn.textContent = `📂 项目外对话 (${is_archived ? 'Archived' : 'Active'} p${++page})`;
                    const r = await fetch(`/backend-api/conversations?offset=${offset}&limit=${PAGE_LIMIT}&order=updated${is_archived ? '&is_archived=true' : ''}`, { headers });
                    if (!r.ok) throw new Error(`列举项目外对话列表失败 (${r.status})`);
                    const j = await r.json();
                    if (j.items && j.items.length > 0) {
                        j.items.forEach(it => all.add(it.id));
                        has_more = j.items.length === PAGE_LIMIT;
                        offset += j.items.length;
                    } else {
                        has_more = false;
                    }
                    await sleep(jitter());
                } while (has_more);
            }
        }
        return Array.from(all);
    }

    function upsertConversationEntry(map, item, extra = {}) {
        if (!item?.id) return;
        const create_time = normalizeEpochSeconds(item.create_time || 0);
        const update_time = normalizeEpochSeconds(item.update_time || item.create_time || 0);
        const entry = {
            id: item.id,
            title: item.title || 'Untitled Conversation',
            create_time,
            update_time,
            is_archived: item.is_archived ?? extra.is_archived ?? false,
            projectId: extra.projectId || null,
            projectTitle: extra.projectTitle || null
        };
        const existing = map.get(entry.id);
        if (!existing) {
            map.set(entry.id, entry);
            return;
        }
        if (!existing.projectTitle && entry.projectTitle) {
            existing.projectTitle = entry.projectTitle;
            existing.projectId = entry.projectId;
        }
        if (!existing.create_time && entry.create_time) {
            existing.create_time = entry.create_time;
        }
        existing.is_archived = existing.is_archived || entry.is_archived;
        if ((entry.update_time || 0) > (existing.update_time || 0)) {
            existing.update_time = entry.update_time;
        }
        if (existing.title === 'Untitled Conversation' && entry.title) {
            existing.title = entry.title;
        }
    }

    async function listConversations(workspaceId) {
        if (!await ensureAccessToken()) {
            throw new Error('无法获取 Access Token，请刷新页面或打开任意一个对话后再试。');
        }

        const deviceId = getOaiDeviceId();
        if (!deviceId) {
            throw new Error('无法获取 oai-device-id，请确保已登录并刷新页面。');
        }

        const headers = {
            'Authorization': `Bearer ${accessToken}`,
            'oai-device-id': deviceId
        };
        if (workspaceId) { headers['ChatGPT-Account-Id'] = workspaceId; }

        const map = new Map();
        const addEntry = (item, extra = {}) => upsertConversationEntry(map, item, extra);

        for (const is_archived of [false, true]) {
            let offset = 0;
            let has_more = true;
            do {
                const r = await fetch(`/backend-api/conversations?offset=${offset}&limit=${PAGE_LIMIT}&order=updated${is_archived ? '&is_archived=true' : ''}`, { headers });
                if (!r.ok) throw new Error(`列举对话列表失败 (${r.status})`);
                const j = await r.json();
                if (j.items && j.items.length > 0) {
                    j.items.forEach(it => addEntry(it, { is_archived }));
                    has_more = j.items.length === PAGE_LIMIT;
                    offset += j.items.length;
                } else {
                    has_more = false;
                }
                await sleep(jitter());
            } while (has_more);
        }

        if (workspaceId) {
            const projects = await getProjects(workspaceId);
            for (const project of projects) {
                let cursor = '0';
                do {
                    const r = await fetch(`/backend-api/gizmos/${project.id}/conversations?cursor=${cursor}`, { headers });
                    if (!r.ok) throw new Error(`列举项目对话列表失败 (${r.status})`);
                    const j = await r.json();
                    j.items?.forEach(it => addEntry(it, { projectId: project.id, projectTitle: project.title }));
                    cursor = j.cursor;
                    await sleep(jitter());
                } while (cursor);
            }
        }

        return Array.from(map.values())
            .sort((a, b) => (b.update_time || 0) - (a.update_time || 0));
    }

    async function listProjectSpaceConversations(workspaceId) {
        if (!await ensureAccessToken()) {
            throw new Error('无法获取 Access Token，请刷新页面或打开任意一个对话后再试。');
        }

        const deviceId = getOaiDeviceId();
        if (!deviceId) {
            throw new Error('无法获取 oai-device-id，请确保已登录并刷新页面。');
        }

        const headers = {
            'Authorization': `Bearer ${accessToken}`,
            'oai-device-id': deviceId
        };
        const resolvedWorkspaceId = resolveWorkspaceId(workspaceId, { allowSingleDetectedFallback: true });
        if (!resolvedWorkspaceId) {
            throw new Error('无法确定当前项目空间所属的 Workspace。请先打开该项目中的任意对话后再试。');
        }
        headers['ChatGPT-Account-Id'] = resolvedWorkspaceId;

        const map = new Map();
        const projects = await getProjectSpaces(resolvedWorkspaceId, { conversationsPerGizmo: PROJECT_SIDEBAR_PREVIEW, ownedOnly: true });

        for (const project of projects) {
            let cursor = '0';
            let fetched = false;
            do {
                const r = await fetch(`/backend-api/gizmos/${project.id}/conversations?cursor=${cursor}`, { headers });
                if (!r.ok) {
                    if (!fetched && Array.isArray(project.conversations) && project.conversations.length > 0) {
                        console.warn(`项目空间对话列表请求失败 (${r.status})，使用侧边栏返回的预览对话。`);
                        project.conversations.forEach(item => upsertConversationEntry(map, item, {
                            projectId: project.id,
                            projectTitle: project.title
                        }));
                        cursor = null;
                        break;
                    }
                    throw new Error(`列举项目空间对话列表失败 (${r.status})`);
                }
                const j = await r.json();
                j.items?.forEach(item => upsertConversationEntry(map, item, {
                    projectId: project.id,
                    projectTitle: project.title
                }));
                cursor = j.cursor;
                fetched = true;
                await sleep(jitter());
            } while (cursor);
        }

        return Array.from(map.values())
            .sort((a, b) => (b.update_time || 0) - (a.update_time || 0));
    }

    async function getConversation(id, workspaceId) {
        const deviceId = getOaiDeviceId();
        if (!deviceId) {
            throw new Error('无法获取 oai-device-id，请确保已登录并刷新页面。');
        }
        const headers = {
            'Authorization': `Bearer ${accessToken}`,
            'oai-device-id': deviceId
        };
        if (workspaceId) { headers['ChatGPT-Account-Id'] = workspaceId; }
        const r = await fetch(`/backend-api/conversation/${id}`, { headers });
        if (!r.ok) throw new Error(`获取对话详情失败 conv ${id} (${r.status})`);
        const j = await r.json();
        j.__fetched_at = new Date().toISOString();
        return j;
    }

    // --- UI 相关函数 ---
    /**
     * [新增] 全面检测函数，返回所有找到的ID
     * @returns {string[]} - 返回包含所有唯一Workspace ID的数组
     */
    function detectAllWorkspaceIds() {
        const foundIds = [];
        const seenIds = new Set();
        const pushWorkspaceId = (value) => {
            const normalizedValue = normalizeWorkspaceId(value);
            if (!normalizedValue || seenIds.has(normalizedValue)) return;
            seenIds.add(normalizedValue);
            foundIds.push(normalizedValue);
        };

        pushWorkspaceId(lastCapturedWorkspaceId);
        capturedWorkspaceIds.forEach(pushWorkspaceId);

        const cookieWorkspaceId = getCookieWorkspaceId();
        pushWorkspaceId(cookieWorkspaceId);

        // 扫描 __NEXT_DATA__
        try {
            const nextDataEl = document.getElementById('__NEXT_DATA__');
            const data = nextDataEl ? JSON.parse(nextDataEl.textContent) : null;
            // 遍历所有账户信息
            const accounts = data?.props?.pageProps?.user?.accounts;
            if (accounts) {
                Object.values(accounts).forEach(acc => {
                    if (acc?.account?.id) {
                        pushWorkspaceId(acc.account.id);
                    }
                });
            }
        } catch (e) {}

        // 扫描 localStorage
        try {
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && (key.includes('account') || key.includes('workspace'))) {
                    const value = localStorage.getItem(key);
                    if (value && /^[a-z0-9]{2,}-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(value.replace(/"/g, ''))) {
                         const extractedId = value.match(/ws-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/i);
                         if (extractedId) pushWorkspaceId(extractedId[0]);
                    } else if (value && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(value.replace(/"/g, ''))) {
                         pushWorkspaceId(value.replace(/"/g, ''));
                    }
                }
            }
        } catch(e) {}

        console.log('🔍 检测到以下 Workspace IDs:', foundIds);
        return foundIds;
    }

    function renderExportFormatControl(selectedFormat, hintText = '将按对话直接下载单个文件，不会生成压缩包。') {
        const normalized = normalizeExportFormat(selectedFormat);
        return `
            <div style="display: flex; gap: 8px; margin-bottom: 12px; align-items: center; flex-wrap: wrap;">
                <label for="export-format" style="font-size: 12px; color: #666;">下载格式</label>
                <select id="export-format" style="padding: 8px 28px 8px 8px; border-radius: 6px; border: 1px solid #ccc;">
                    <option value="md" ${normalized === 'md' ? 'selected' : ''}>Markdown (.md)</option>
                    <option value="json" ${normalized === 'json' ? 'selected' : ''}>JSON (.json)</option>
                </select>
                <span style="font-size: 12px; color: #666;">${hintText}</span>
            </div>
        `;
    }

    function showConversationPicker(options = {}) {
        const { mode = 'personal', workspaceId = null, exportFormat = DEFAULT_EXPORT_FORMAT } = options;
        const existing = document.getElementById('export-dialog-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = 'export-dialog-overlay';
        Object.assign(overlay.style, {
            position: 'fixed', top: '0', left: '0', width: '100%', height: '100%',
            backgroundColor: 'rgba(0, 0, 0, 0.5)', zIndex: '99998',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
        });

        const dialog = document.createElement('div');
        dialog.id = 'export-dialog';
        Object.assign(dialog.style, {
            background: '#fff', padding: '24px', borderRadius: '12px',
            boxShadow: '0 5px 15px rgba(0,0,0,.3)', width: '720px',
            fontFamily: 'sans-serif', color: '#333', boxSizing: 'border-box'
        });

        const closeDialog = () => document.body.removeChild(overlay);
        const state = {
            list: [],
            filtered: [],
            selected: new Set(),
            query: '',
            scope: mode === 'project' ? 'project' : 'all',
            scopeLocked: mode === 'project',
            archived: 'all',
            timeField: 'update',
            loading: true,
            pageSize: 100,
            visibleCount: 100,
            startDate: '',
            endDate: '',
            exportFormat: normalizeExportFormat(exportFormat)
        };

        const renderBase = () => {
            const modeLabel = mode === 'team' ? '团队空间' : mode === 'project' ? '项目空间' : '个人空间';
            const workspaceLabel = workspaceId ? `（${workspaceId}）` : '';
            dialog.innerHTML = `
                <h2 style="margin-top:0; margin-bottom: 12px; font-size: 18px;">选择要下载的对话</h2>
                <div style="margin-bottom: 12px; color: #666; font-size: 12px;">空间：${modeLabel}${workspaceLabel}</div>
                ${renderExportFormatControl(state.exportFormat)}
                <div style="display: flex; gap: 8px; margin-bottom: 8px;">
                    <input id="conv-search" type="text" placeholder="搜索标题/项目名/ID"
                        style="flex: 1; padding: 8px; border-radius: 6px; border: 1px solid #ccc; box-sizing: border-box;">
                    <select id="filter-scope" style="padding: 8px 28px 8px 8px; border-radius: 6px; border: 1px solid #ccc;">
                        <option value="all">全部范围</option>
                        <option value="project">仅项目</option>
                        <option value="root">仅项目外</option>
                    </select>
                    <select id="filter-archived" style="padding: 8px 28px 8px 8px; border-radius: 6px; border: 1px solid #ccc;">
                        <option value="all">全部状态</option>
                        <option value="active">仅未归档</option>
                        <option value="archived">仅已归档</option>
                    </select>
                </div>
                <div style="display: flex; gap: 8px; margin-bottom: 8px; align-items: center;">
                    <select id="filter-time-field" style="padding: 8px 28px 8px 8px; border-radius: 6px; border: 1px solid #ccc;">
                        <option value="update">按更新时间</option>
                        <option value="create">按创建时间</option>
                    </select>
                    <input id="filter-start-date" type="date" style="padding: 8px; border-radius: 6px; border: 1px solid #ccc;">
                    <span style="color: #666; font-size: 12px;">至</span>
                    <input id="filter-end-date" type="date" style="padding: 8px; border-radius: 6px; border: 1px solid #ccc;">
                    <button id="clear-date-btn" style="padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; background: #fff; cursor: pointer;">清空日期</button>
                </div>
                <div id="conv-status" style="margin-bottom: 8px; font-size: 12px; color: #666;">正在加载列表...</div>
                <div id="conv-list" style="max-height: 360px; overflow: auto; border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px; background: #fff;"></div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 16px;">
                    <div style="display: flex; gap: 8px;">
                        <button id="select-all-btn" style="padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; background: #fff; cursor: pointer;">全选</button>
                        <button id="clear-all-btn" style="padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; background: #fff; cursor: pointer;">清空</button>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <button id="back-btn" style="padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; background: #fff; cursor: pointer;">返回</button>
                        <button id="export-selected-btn" style="padding: 8px 12px; border: none; border-radius: 6px; background: #10a37f; color: #fff; cursor: pointer; font-weight: bold;" disabled>下载选中 (0)</button>
                    </div>
                </div>
            `;

            const searchInput = dialog.querySelector('#conv-search');
            const scopeSelect = dialog.querySelector('#filter-scope');
            const archivedSelect = dialog.querySelector('#filter-archived');
            const timeFieldSelect = dialog.querySelector('#filter-time-field');
            const startDateInput = dialog.querySelector('#filter-start-date');
            const endDateInput = dialog.querySelector('#filter-end-date');
            const clearDateBtn = dialog.querySelector('#clear-date-btn');
            const selectAllBtn = dialog.querySelector('#select-all-btn');
            const clearAllBtn = dialog.querySelector('#clear-all-btn');
            const backBtn = dialog.querySelector('#back-btn');
            const exportBtn = dialog.querySelector('#export-selected-btn');
            const exportFormatSelect = dialog.querySelector('#export-format');

            if (state.scopeLocked && scopeSelect) {
                scopeSelect.value = 'project';
                scopeSelect.disabled = true;
                scopeSelect.style.opacity = '0.7';
                scopeSelect.style.cursor = 'not-allowed';
                scopeSelect.title = '项目空间仅包含项目对话';
            }

            searchInput.oninput = (e) => {
                state.query = e.target.value || '';
                applyFilters();
                renderList();
            };
            scopeSelect.onchange = (e) => {
                state.scope = e.target.value;
                applyFilters();
                renderList();
            };
            archivedSelect.onchange = (e) => {
                state.archived = e.target.value;
                applyFilters();
                renderList();
            };
            timeFieldSelect.onchange = (e) => {
                state.timeField = e.target.value;
                applyFilters();
                renderList();
            };
            startDateInput.onchange = (e) => {
                state.startDate = e.target.value || '';
                applyFilters();
                renderList();
            };
            endDateInput.onchange = (e) => {
                state.endDate = e.target.value || '';
                applyFilters();
                renderList();
            };
            clearDateBtn.onclick = () => {
                state.startDate = '';
                state.endDate = '';
                startDateInput.value = '';
                endDateInput.value = '';
                applyFilters();
                renderList();
            };
            selectAllBtn.onclick = () => {
                state.filtered.forEach(item => state.selected.add(item.id));
                renderList();
            };
            clearAllBtn.onclick = () => {
                state.selected.clear();
                renderList();
            };
            exportFormatSelect.onchange = (e) => {
                state.exportFormat = normalizeExportFormat(e.target.value);
            };
            backBtn.onclick = () => {
                closeDialog();
                showExportDialog({ exportFormat: state.exportFormat });
            };
            exportBtn.onclick = async () => {
                if (state.selected.size === 0) return;
                const selectedList = state.list.filter(item => state.selected.has(item.id));
                closeDialog();
                await startSelectiveExportProcess(mode, workspaceId, selectedList, state.exportFormat);
            };
        };

        const applyFilters = () => {
            const query = state.query.trim().toLowerCase();
            const startBound = parseDateInputToEpoch(state.startDate, false);
            const endBound = parseDateInputToEpoch(state.endDate, true);
            state.filtered = state.list.filter(item => {
                const text = `${item.title || ''} ${item.projectTitle || ''} ${item.id || ''}`.toLowerCase();
                if (query && !text.includes(query)) return false;
                if (state.scope === 'project' && !item.projectTitle) return false;
                if (state.scope === 'root' && item.projectTitle) return false;
                if (state.archived === 'active' && item.is_archived) return false;
                if (state.archived === 'archived' && !item.is_archived) return false;
                if (startBound || endBound) {
                    const sourceTime = state.timeField === 'create'
                        ? item.create_time
                        : item.update_time;
                    const ts = normalizeEpochSeconds(sourceTime || 0);
                    if (!ts) return false;
                    if (startBound && ts < startBound) return false;
                    if (endBound && ts > endBound) return false;
                }
                return true;
            });
            state.visibleCount = state.pageSize;
        };

        const renderList = () => {
            const statusEl = dialog.querySelector('#conv-status');
            const listEl = dialog.querySelector('#conv-list');
            const exportBtn = dialog.querySelector('#export-selected-btn');
            const selectAllBtn = dialog.querySelector('#select-all-btn');
            const clearAllBtn = dialog.querySelector('#clear-all-btn');
            const controlsDisabled = state.loading;

            if (selectAllBtn) selectAllBtn.disabled = controlsDisabled;
            if (clearAllBtn) clearAllBtn.disabled = controlsDisabled;
            if (exportBtn) exportBtn.disabled = controlsDisabled || state.selected.size === 0;

            listEl.innerHTML = '';
            if (state.loading) {
                statusEl.textContent = '正在加载列表...';
                return;
            }

            const visibleCount = Math.min(state.visibleCount, state.filtered.length);
            statusEl.textContent = `共 ${state.list.length} 条，当前筛选 ${state.filtered.length} 条，显示 ${visibleCount} 条，已选 ${state.selected.size} 条`;
            exportBtn.textContent = `下载选中 (${state.selected.size})`;

            if (state.filtered.length === 0) {
                const empty = document.createElement('div');
                empty.textContent = '没有匹配的对话。';
                empty.style.color = '#999';
                empty.style.padding = '8px 4px';
                listEl.appendChild(empty);
                return;
            }

            const visibleItems = state.filtered.slice(0, state.visibleCount);
            visibleItems.forEach(item => {
                const label = document.createElement('label');
                Object.assign(label.style, {
                    display: 'flex', gap: '8px', padding: '8px',
                    border: '1px solid #e5e7eb', borderRadius: '6px',
                    marginBottom: '8px', cursor: 'pointer', alignItems: 'flex-start'
                });

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = state.selected.has(item.id);
                checkbox.onchange = (e) => {
                    if (e.target.checked) {
                        state.selected.add(item.id);
                    } else {
                        state.selected.delete(item.id);
                    }
                    renderList();
                };

                const content = document.createElement('div');
                content.style.flex = '1';

                const title = document.createElement('div');
                title.textContent = item.title || 'Untitled Conversation';
                title.style.fontWeight = 'bold';
                title.style.fontSize = '14px';

                const meta = document.createElement('div');
                meta.style.fontSize = '12px';
                meta.style.color = '#666';
                const timeLabelPrefix = state.timeField === 'create' ? '创建' : '更新';
                const timeValue = state.timeField === 'create' ? item.create_time : item.update_time;
                const timeLabel = formatTimestamp(timeValue) || '未知';
                meta.textContent = `${timeLabelPrefix}: ${timeLabel}`;

                const tags = document.createElement('div');
                tags.style.marginTop = '6px';
                tags.style.display = 'flex';
                tags.style.gap = '6px';
                tags.style.flexWrap = 'wrap';

                if (item.projectTitle) {
                    const projectTag = document.createElement('span');
                    projectTag.textContent = `项目: ${item.projectTitle}`;
                    Object.assign(projectTag.style, {
                        background: '#eef2ff', color: '#4338ca',
                        padding: '2px 6px', borderRadius: '999px', fontSize: '11px'
                    });
                    tags.appendChild(projectTag);
                }

                if (item.is_archived) {
                    const archivedTag = document.createElement('span');
                    archivedTag.textContent = '已归档';
                    Object.assign(archivedTag.style, {
                        background: '#fef3c7', color: '#92400e',
                        padding: '2px 6px', borderRadius: '999px', fontSize: '11px'
                    });
                    tags.appendChild(archivedTag);
                }

                content.appendChild(title);
                content.appendChild(meta);
                if (tags.childNodes.length > 0) content.appendChild(tags);

                label.appendChild(checkbox);
                label.appendChild(content);
                listEl.appendChild(label);
            });

            if (state.filtered.length > state.visibleCount) {
                const loadMore = document.createElement('button');
                loadMore.textContent = `加载更多（剩余 ${state.filtered.length - state.visibleCount} 条）`;
                Object.assign(loadMore.style, {
                    width: '100%', padding: '8px 12px', border: '1px solid #ccc',
                    borderRadius: '6px', background: '#fff', cursor: 'pointer'
                });
                loadMore.onclick = () => {
                    state.visibleCount = Math.min(state.visibleCount + state.pageSize, state.filtered.length);
                    renderList();
                };
                listEl.appendChild(loadMore);
            }
        };

        renderBase();
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);
        overlay.onclick = (e) => { if (e.target === overlay) closeDialog(); };

        const listPromise = mode === 'project'
            ? listProjectSpaceConversations(workspaceId)
            : listConversations(workspaceId);
        listPromise
            .then(list => {
                state.list = list;
                state.loading = false;
                applyFilters();
                renderList();
            })
            .catch(err => {
                const statusEl = dialog.querySelector('#conv-status');
                state.loading = false;
                state.list = [];
                state.filtered = [];
                statusEl.textContent = `加载失败: ${err.message}`;
                renderList();
            });
    }

    /**
     * [重构] 多步骤、用户主导的导出对话框
     */
    function showExportDialog(options = {}) {
        const { exportFormat = DEFAULT_EXPORT_FORMAT } = options;
        if (document.getElementById('export-dialog-overlay')) return;

        const overlay = document.createElement('div');
        overlay.id = 'export-dialog-overlay';
        Object.assign(overlay.style, {
            position: 'fixed', top: '0', left: '0', width: '100%', height: '100%',
            backgroundColor: 'rgba(0, 0, 0, 0.5)', zIndex: '99998',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
        });

        const dialog = document.createElement('div');
        dialog.id = 'export-dialog';
        Object.assign(dialog.style, {
            background: '#fff', padding: '24px', borderRadius: '12px',
            boxShadow: '0 5px 15px rgba(0,0,0,.3)', width: '450px',
            fontFamily: 'sans-serif', color: '#333', boxSizing: 'border-box'
        });

        const closeDialog = () => document.body.removeChild(overlay);

        let selectedExportFormat = normalizeExportFormat(exportFormat);
        const renderStep = (step) => {
            let html = '';
            switch (step) {
                case 'team': {
                    const detectedIds = detectAllWorkspaceIds();
                    html = `<h2 style="margin-top:0; margin-bottom: 20px; font-size: 18px;">下载团队空间对话</h2>
                            ${renderExportFormatControl(selectedExportFormat)}`;

                    if (detectedIds.length > 1) {
                        html += `<div style="background: #eef2ff; border: 1px solid #818cf8; border-radius: 8px; padding: 12px; margin-bottom: 20px;">
                                     <p style="margin: 0 0 12px 0; font-weight: bold; color: #4338ca;">🔎 检测到多个 Workspace，请选择一个:</p>
                                     <div id="workspace-id-list">`;
                        detectedIds.forEach((id, index) => {
                            html += `<label style="display: block; margin-bottom: 8px; padding: 8px; border-radius: 6px; cursor: pointer; border: 1px solid #ddd; background: #fff;">
                                         <input type="radio" name="workspace_id" value="${id}" ${index === 0 ? 'checked' : ''}>
                                         <code style="margin-left: 8px; font-family: monospace; color: #555;">${id}</code>
                                      </label>`;
                        });
                        html += `</div></div>`;
                    } else if (detectedIds.length === 1) {
                        html += `<div style="background: #f0fdf4; border: 1px solid #4ade80; border-radius: 8px; padding: 12px; margin-bottom: 20px;">
                                     <p style="margin: 0 0 8px 0; font-weight: bold; color: #166534;">✅ 已自动检测到 Workspace ID:</p>
                                     <code id="workspace-id-code" style="background: #e0e7ff; padding: 4px 8px; border-radius: 4px; font-family: monospace; color: #4338ca; word-break: break-all;">${detectedIds[0]}</code>
                                   </div>`;
                    } else {
                        html += `<div style="background: #fffbeb; border: 1px solid #facc15; border-radius: 8px; padding: 12px; margin-bottom: 20px;">
                                     <p style="margin: 0; color: #92400e;">⚠️ 未能自动检测到 Workspace ID。</p>
                                     <p style="margin: 8px 0 0 0; font-size: 12px; color: #92400e;">请尝试刷新页面或打开一个团队对话，或在下方手动输入。</p>
                                   </div>
                                   <label for="team-id-input" style="display: block; margin-bottom: 8px; font-weight: bold;">手动输入 Team Workspace ID:</label>
                                   <input type="text" id="team-id-input" placeholder="粘贴您的 Workspace ID (ws-...)" style="width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #ccc; box-sizing: border-box;">`;
                    }

                    html += `<div style="display: flex; justify-content: space-between; align-items: center; margin-top: 24px;">
                                 <button id="back-btn" style="padding: 10px 16px; border: 1px solid #ccc; border-radius: 8px; background: #fff; cursor: pointer;">返回</button>
                                 <button id="start-team-picker-btn" style="padding: 10px 16px; border: 1px solid #ccc; border-radius: 8px; background: #fff; cursor: pointer;">选择对话下载</button>
                               </div>`;
                    break;
                }

                case 'initial':
                default:
                    html = `<h2 style="margin-top:0; margin-bottom: 20px; font-size: 18px;">选择要下载的空间</h2>
                                ${renderExportFormatControl(selectedExportFormat)}
                                <div style="display: flex; flex-direction: column; gap: 16px;">
                                    <div style="padding: 16px; border: 1px solid #ccc; border-radius: 8px; background: #f9fafb;">
                                        <strong style="font-size: 16px;">个人空间</strong>
                                        <p style="margin: 4px 0 12px 0; color: #666;">直接下载您个人账户下的对话。</p>
                                        <button id="select-personal-picker-btn" style="padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; background: #fff; cursor: pointer;">选择对话下载</button>
                                    </div>
                                    <div style="padding: 16px; border: 1px solid #ccc; border-radius: 8px; background: #f9fafb;">
                                        <strong style="font-size: 16px;">项目空间</strong>
                                        <p style="margin: 4px 0 12px 0; color: #666;">直接下载项目空间下的对话，并按项目自动命名。</p>
                                        <button id="select-project-picker-btn" style="padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; background: #fff; cursor: pointer;">选择对话下载</button>
                                    </div>
                                    <div style="padding: 16px; border: 1px solid #ccc; border-radius: 8px; background: #f9fafb;">
                                        <strong style="font-size: 16px;">团队空间</strong>
                                        <p style="margin: 4px 0 12px 0; color: #666;">直接下载团队空间下的对话，并自动检测 ID。</p>
                                        <button id="select-team-picker-btn" style="padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; background: #fff; cursor: pointer;">选择对话下载</button>
                                    </div>
                                </div>
                                <div style="display: flex; justify-content: flex-end; margin-top: 24px;">
                                    <button id="cancel-btn" style="padding: 10px 16px; border: 1px solid #ccc; border-radius: 8px; background: #fff; cursor: pointer;">取消</button>
                                </div>`;
                    break;
            }
            dialog.innerHTML = html;
            attachListeners(step);
        };

        const attachListeners = (step) => {
            const exportFormatSelect = document.getElementById('export-format');
            if (exportFormatSelect) {
                exportFormatSelect.onchange = (event) => {
                    selectedExportFormat = normalizeExportFormat(event.target.value);
                };
            }

            if (step === 'initial') {
                document.getElementById('select-personal-picker-btn').onclick = () => {
                    closeDialog();
                    showConversationPicker({ mode: 'personal', workspaceId: null, exportFormat: selectedExportFormat });
                };
                document.getElementById('select-project-picker-btn').onclick = () => {
                    const resolvedWorkspaceId = resolveWorkspaceId(null, { allowSingleDetectedFallback: true });
                    if (!resolvedWorkspaceId) {
                        alert('无法确定当前项目空间所属的 Workspace。请先打开该项目中的任意对话后再试。');
                        return;
                    }
                    closeDialog();
                    showConversationPicker({ mode: 'project', workspaceId: resolvedWorkspaceId, exportFormat: selectedExportFormat });
                };
                const startTeamFlow = () => {
                    const workspaceId = resolveWorkspaceId(null, { allowSingleDetectedFallback: true });
                    if (workspaceId) {
                        closeDialog();
                        showConversationPicker({ mode: 'team', workspaceId, exportFormat: selectedExportFormat });
                        return;
                    }
                    renderStep('team');
                };
                document.getElementById('select-team-picker-btn').onclick = () => startTeamFlow();
                document.getElementById('cancel-btn').onclick = closeDialog;
            } else if (step === 'team') {
                document.getElementById('back-btn').onclick = () => renderStep('initial');
                const resolveWorkspaceId = () => {
                    let workspaceId = '';
                    const radioChecked = document.querySelector('input[name="workspace_id"]:checked');
                    const codeEl = document.getElementById('workspace-id-code');
                    const inputEl = document.getElementById('team-id-input');

                    if (radioChecked) {
                        workspaceId = radioChecked.value;
                    } else if (codeEl) {
                        workspaceId = codeEl.textContent;
                    } else if (inputEl) {
                        workspaceId = inputEl.value.trim();
                    }

                    if (!workspaceId) {
                        alert('请选择或输入一个有效的 Team Workspace ID！');
                        return;
                    }
                    return workspaceId;
                };
                const pickerBtn = document.getElementById('start-team-picker-btn');
                if (pickerBtn) pickerBtn.onclick = () => {
                    const workspaceId = resolveWorkspaceId();
                    if (!workspaceId) return;
                    closeDialog();
                    showConversationPicker({ mode: 'team', workspaceId, exportFormat: selectedExportFormat });
                };
            }
        };

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);
        overlay.onclick = (e) => { if (e.target === overlay) closeDialog(); };
        renderStep('initial');
    }


    window.ChatGPTExporter = window.ChatGPTExporter || {};
    Object.assign(window.ChatGPTExporter, {
        showDialog: showExportDialog,
        startManualExport: (mode = 'personal', workspaceId = null, exportFormat = DEFAULT_EXPORT_FORMAT) => {
            if (mode === 'personal') {
                return showConversationPicker({ mode, workspaceId: null, exportFormat });
            }
            const resolvedWorkspaceId = resolveWorkspaceId(workspaceId, { allowSingleDetectedFallback: true });
            if (!resolvedWorkspaceId) {
                return showExportDialog({ exportFormat });
            }
            return showConversationPicker({ mode, workspaceId: resolvedWorkspaceId, exportFormat });
        },
        startScheduledExport
    });

    document.documentElement.setAttribute('data-chatgpt-exporter-ready', '1');
    window.dispatchEvent(new CustomEvent('CHATGPT_EXPORTER_READY'));

    window.addEventListener('message', (event) => {
        if (event.source !== window) return;
        const data = event.data || {};
        if (data?.type !== 'CHATGPT_EXPORTER_COMMAND') return;
        const api = window.ChatGPTExporter;
        if (!api) return;
        try {
            switch (data.action) {
                case 'START_SCHEDULED_EXPORT':
                    api.startScheduledExport(data.payload || {});
                    break;
                case 'OPEN_DIALOG':
                    api.showDialog();
                    break;
                case 'START_MANUAL_EXPORT':
                    api.startManualExport(data.payload?.mode, data.payload?.workspaceId, data.payload?.exportFormat);
                    break;
                default:
                    console.warn('[ChatGPT Exporter] 未知命令:', data.action);
            }
        } catch (err) {
            console.error('[ChatGPT Exporter] 处理命令失败:', err);
        }
    });

})();
