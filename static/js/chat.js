/* AI text is rendered as plain text. Only a signed proposal can be confirmed. */
const chatCopy = {
    zh: {
        title: 'AI 样品助手', close: '收起助手', history: '聊天记录',
        resize: '调整助手宽度（方向键调节，双击恢复默认）',
        notice: '支持检索和已存图片解读；每个样品分别确认保存。',
        inputLabel: '告诉助手要查找或修改什么', placeholder: '例如：把当前样品的烧制耗时改为 72 小时',
        reset: '新建会话', sessions: '历史会话（已登录设备共享）', refresh: '刷新会话',
        loading: '正在加载会话…', expired: '方案已过期，请重新提出要求。',
        undoExpired: '已保存，撤销期限已过。', processing: '操作处理中；若结果未确认，请重新加载并核对样品。',
        send: '发送', keyHint: 'Enter 发送 · Shift + Enter 换行',
        context: '当前样品：', none: '未选择', draft: '新建草稿（尚未保存）',
        welcome: '可以检索、比较样品，解读已保存的照片、EDX 或 XRD 图片，并批量新建或修改制度、时间和比例。每次最多 10 个编号，每个样品分别核对、确认及撤销。',
        examples: ['列出最近的样品', '解读当前样品的 EDX 图片', '将 CG-001、CG-002 的烧制耗时改为 72 小时'],
        user: '你', assistant: '助手', thinking: '正在读取样品并生成回复…', saving: '正在保存已确认的变更…',
        create: '待确认：新建样品 ', update: '待确认：修改样品 ', before: '修改前', after: '修改后',
        confirm: '确认保存', cancel: '取消', pending: '尚未保存 · 方案 30 分钟内有效',
        cancelled: '已取消，未保存。', replaced: '已由后续消息替代，未保存。',
        saved: '已保存，30 分钟内可撤销。样品列表已刷新，当前表单草稿保留。重新点击样品可查看已保存数据。',
        undo: '撤销本次保存', confirmUndo: '确认撤销', keep: '保留变更', undoing: '正在撤销本次保存…',
        undoCreate: '撤销将删除刚新建的样品，请确认：', undoUpdate: '撤销将恢复本次保存前的样品内容，请确认：',
        undone: '已撤销本次保存，样品列表已刷新。当前表单内容保留，请重新选择样品查看；已删除样品的表单转为未保存草稿。',
        undoUncertain: '撤销状态未确认，请重新读取样品核对。',
        uncertain: '保存状态未确认，请重新读取样品核对后再操作。', failed: '请求失败，请重试。',
        full: '对话较长，请开启新对话后继续。', yes: '是', no: '否', reference: '参考',
        statuses: ['失败', '成功', '待定', '生长中', '生长完成'],
    },
    en: {
        title: 'AI Sample Assistant', close: 'Close assistant', history: 'Chat history',
        resize: 'Resize assistant (arrow keys to adjust, double-click to reset)',
        notice: 'Search and read saved images. Confirm each sample separately.',
        inputLabel: 'What would you like to find or change?', placeholder: 'For example: change this sample’s sintering duration to 72 hours',
        reset: 'New conversation', sessions: 'History (shared by signed-in devices)', refresh: 'Refresh conversations',
        loading: 'Loading conversation…', expired: 'Proposal expired. Describe your request again.',
        undoExpired: 'Saved. The undo period has expired.', processing: 'Operation processing. Reload and check the sample if the result is unknown.',
        send: 'Send', keyHint: 'Enter to send · Shift + Enter for a new line',
        context: 'Current sample: ', none: 'None selected', draft: 'New draft (not saved)',
        welcome: 'Find and compare samples, interpret saved photos, EDX or XRD images, and create or update records in batches of up to 10 IDs. Review, confirm and undo each sample separately.',
        examples: ['List recent samples', 'Interpret this sample’s saved EDX images', 'Change sintering duration to 72 hours for CG-001 and CG-002'],
        user: 'You', assistant: 'Assistant', thinking: 'Reading samples and preparing a reply…', saving: 'Saving your confirmed changes…',
        create: 'Confirm new sample: ', update: 'Confirm sample update: ', before: 'Before', after: 'After',
        confirm: 'Confirm save', cancel: 'Cancel', pending: 'Not saved · Proposal expires in 30 minutes',
        cancelled: 'Cancelled. Nothing saved.', replaced: 'Superseded by your next message. Nothing saved.',
        saved: 'Saved. Undo is available for 30 minutes. The sample list was refreshed; your form draft was preserved. Select the sample again to view saved data.',
        undo: 'Undo this save', confirmUndo: 'Confirm undo', keep: 'Keep changes', undoing: 'Undoing this save…',
        undoCreate: 'Undo will delete the sample just created. Please confirm: ', undoUpdate: 'Undo will restore the sample to its state before this save. Please confirm: ',
        undone: 'Save undone. The list was refreshed and your form content was preserved. Select the sample again to view saved data; a deleted sample’s form becomes an unsaved draft.',
        undoUncertain: 'Undo status is unknown. Read the sample again to check.',
        uncertain: 'Save status is unknown. Read the sample again before making further changes.', failed: 'Request failed. Please retry.',
        full: 'This conversation is long. Start a new chat to continue.', yes: 'Yes', no: 'No', reference: 'Ref',
        statuses: ['Fail', 'Success', 'Pending', 'Growing', 'Done'],
    },
};
const chatFields = {
    target_product: ['目标产物', 'Target product'], status: ['状态', 'Status'],
    growth_process: ['生长流程（中文）', 'Growth procedure (Chinese)'], growth_process_en: ['生长流程（英文）', 'Growth procedure (English)'],
    results: ['结果（中文）', 'Results (Chinese)'], results_en: ['结果（英文）', 'Results (English)'],
    notes: ['备注', 'Notes'], sintering_start: ['烧制开始时间', 'Sintering start'],
    sintering_duration: ['烧制耗时（小时）', 'Duration (hours)'], sintering_end: ['烧制结束时间', 'Sintering end'],
    element_ratios: ['元素摩尔比', 'Element ratios'], actual_masses: ['称量质量', 'Weighing masses'],
    has_electric: ['电学测量', 'Electric'], has_magnetic: ['磁性测量', 'Magnetic'],
    has_xrd: ['XRD', 'XRD'], has_edx: ['EDX', 'EDX'], has_pdf: ['PDF', 'PDF'],
};
const chatPanel = document.getElementById('aiChatPanel');
const chatResizer = document.getElementById('aiChatResizer');
const chatLauncher = document.getElementById('aiChatToggle');
const chatBackdrop = document.getElementById('aiChatBackdrop');
const chatMessages = document.getElementById('aiChatMessages');
const chatInput = document.getElementById('aiChatInput');
const chatSend = document.getElementById('aiChatSend');
const chatReset = document.getElementById('aiChatReset');
const chatConversations = document.getElementById('aiChatConversations');
const chatRefresh = document.getElementById('aiChatRefresh');
const chatStatus = document.getElementById('aiChatStatus');
const chatSmallScreen = window.matchMedia('(max-width: 1350px)');
let chatConversation = null;
let chatConversationList = [];
let chatBusy = false;
const rememberedChatWidth = localStorage.getItem('crystal-chat-width');
let chatWidth = rememberedChatWidth === null ? 360 : Number(rememberedChatWidth);
if (!Number.isFinite(chatWidth)) chatWidth = 360;
let chatResizeStart = null;

function chatText(key) { return chatCopy[currentLang][key]; }
function chatElement(tag, className, text) {
    const element = document.createElement(tag);
    element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}
function updateChatContext() {
    document.getElementById('aiChatContext').textContent = chatText('context') +
        (isNewSample ? chatText('draft') : (currentSampleId || chatText('none')));
}
function updateChatLanguage() {
    document.querySelectorAll('[data-chat-i18n]').forEach(el => { el.textContent = chatText(el.dataset.chatI18n); });
    document.querySelectorAll('[data-chat-i18n-label]').forEach(el => { el.setAttribute('aria-label', chatText(el.dataset.chatI18nLabel)); });
    document.querySelectorAll('[data-chat-i18n-placeholder]').forEach(el => { el.placeholder = chatText(el.dataset.chatI18nPlaceholder); });
    updateChatContext();
    renderChatConversations();
    if (chatConversation) renderChatConversation();
    else if (!chatBusy) showChatWelcome();
}
function setChatOpen(open) {
    chatPanel.hidden = !open;
    document.body.classList.toggle('ai-chat-open', open);
    chatLauncher.setAttribute('aria-expanded', String(open));
    chatBackdrop.hidden = !(open && chatSmallScreen.matches);
    chatPanel.setAttribute('role', chatSmallScreen.matches ? 'dialog' : 'complementary');
    [document.querySelector('.top-bar'), document.getElementById('sidebar'), document.getElementById('mainPanel')]
        .forEach(element => { element.inert = open && chatSmallScreen.matches; });
    if (chatSmallScreen.matches && open) chatPanel.setAttribute('aria-modal', 'true');
    else chatPanel.removeAttribute('aria-modal');
    updateChatContext();
    if (open) chatInput.focus({preventScroll: true});
    else chatLauncher.focus({preventScroll: true});
}
function setChatWidth(width, remember = false) {
    const maximum = chatSmallScreen.matches ? 720 : Math.min(720, Math.floor(window.innerWidth * .4));
    chatWidth = Math.round(Math.max(320, Math.min(maximum, width)));
    chatPanel.style.setProperty('--ai-chat-width', chatWidth + 'px');
    chatResizer.setAttribute('aria-valuemin', '320');
    chatResizer.setAttribute('aria-valuemax', String(maximum));
    chatResizer.setAttribute('aria-valuenow', String(chatWidth));
    if (remember) localStorage.setItem('crystal-chat-width', String(chatWidth));
}
function finishChatResize(event) {
    if (!chatResizeStart || event.pointerId !== chatResizeStart.pointerId) return;
    chatResizeStart = null;
    document.body.classList.remove('ai-chat-resizing');
    setChatWidth(chatWidth, true);
}
function scrollChat() { chatMessages.scrollTop = chatMessages.scrollHeight; }
function setChatBusy(busy, status = '') {
    chatBusy = busy;
    chatSend.disabled = busy || !chatConversation;
    chatReset.disabled = busy;
    chatConversations.disabled = busy;
    chatRefresh.disabled = busy;
    chatInput.disabled = busy || !chatConversation;
    chatStatus.textContent = status;
    document.getElementById('aiChatForm').setAttribute('aria-busy', String(busy));
    if (busy && chatSmallScreen.matches) document.getElementById('aiChatClose').focus({preventScroll: true});
}
function showChatWelcome() {
    chatMessages.replaceChildren();
    const welcome = chatElement('div', 'ai-chat-welcome', chatText('welcome'));
    const examples = chatElement('div', 'ai-chat-examples');
    chatText('examples').forEach(text => {
        const button = chatElement('button', 'ai-chat-button', text);
        button.type = 'button';
        button.addEventListener('click', () => { chatInput.value = text; chatInput.focus(); });
        examples.append(button);
    });
    welcome.append(examples);
    chatMessages.append(welcome);
}
function appendChatMessage(role, text, error = false) {
    const message = chatElement('div', `ai-chat-message ai-chat-${role}${error ? ' ai-chat-error' : ''}`);
    message.append(chatElement('small', '', chatText(role === 'user' ? 'user' : 'assistant')),
        chatElement('div', '', text));
    chatMessages.append(message);
    scrollChat();
}
function chatValue(field, value) {
    if (value === null || value === '') return '—';
    if (field === 'status') return chatText('statuses')[value];
    if (field.startsWith('has_')) return chatText(value ? 'yes' : 'no');
    if (field === 'element_ratios') return value.map(item => `${item.element}: ${item.ratio}${item.is_reference ? ` (${chatText('reference')})` : ''}`).join('\n');
    if (field === 'actual_masses') return value.length ? value.map(item => `${item.element}: ${item.mass.toFixed(4)} g`).join('\n') : '—';
    return String(value);
}
async function chatRequest(url, options) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    return data;
}
function renderChatConversations() {
    chatConversations.replaceChildren();
    chatConversationList.forEach(conversation => {
        const option = chatElement('option', '', (conversation.title || chatText('reset')) +
            ' · ' + conversation.updated_at.slice(5, 16).replace('T', ' '));
        option.value = conversation.id;
        chatConversations.append(option);
    });
    if (chatConversation) chatConversations.value = chatConversation.id;
}
async function loadChatConversations() {
    chatConversationList = await chatRequest('/api/chat/conversations');
    renderChatConversations();
}
function setChatConversation(conversation) {
    chatConversation = conversation;
    const {messages, ...summary} = conversation;
    chatConversationList = [summary, ...chatConversationList.filter(item => item.id !== conversation.id)]
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    localStorage.setItem('crystal-chat-conversation', conversation.id);
    renderChatConversations();
    renderChatConversation();
}
async function loadChatConversation(id) {
    setChatConversation(await chatRequest('/api/chat/conversations/' + encodeURIComponent(id)));
}
function renderChatConversation() {
    chatMessages.replaceChildren();
    if (!chatConversation.messages.length) { showChatWelcome(); return; }
    chatConversation.messages.forEach(message => {
        if (message.content) appendChatMessage(message.role, message.content);
        if (message.proposal) showChatProposal(message);
    });
    scrollChat();
}
function showChatProposal(message) {
    const proposal = message.proposal;
    const card = chatElement('section', 'ai-chat-proposal');
    card.dataset.messageId = message.id;
    card.append(chatElement('h3', '', chatText(proposal.operation) + proposal.sample_id));
    proposal.diff.forEach(change => {
        const diff = chatElement('div', 'ai-chat-diff');
        diff.append(chatElement('h4', '', chatFields[change.field][currentLang === 'zh' ? 0 : 1]),
            chatElement('div', 'ai-chat-diff-label', chatText('before')),
            chatElement('div', 'ai-chat-diff-value', chatValue(change.field, change.before)),
            chatElement('div', 'ai-chat-diff-label', chatText('after')),
            chatElement('div', 'ai-chat-diff-value ai-chat-diff-after', chatValue(change.field, change.after)));
        card.append(diff);
    });
    const actions = chatElement('div', 'ai-chat-proposal-actions');
    const confirm = chatElement('button', 'ai-chat-button ai-chat-primary', chatText('confirm'));
    const cancel = chatElement('button', 'ai-chat-button', chatText('cancel'));
    const undo = chatElement('button', 'ai-chat-button', chatText('undo'));
    const keep = chatElement('button', 'ai-chat-button', chatText('keep'));
    confirm.type = cancel.type = undo.type = keep.type = 'button';
    confirm.hidden = cancel.hidden = message.state !== 'pending';
    confirm.disabled = cancel.disabled = !message.can_confirm;
    undo.hidden = message.state !== 'saved';
    undo.disabled = !message.can_undo;
    keep.hidden = true;
    let undoReady = false;
    const labels = {
        pending: message.can_confirm ? 'pending' : 'expired',
        saved: message.can_undo ? 'saved' : 'undoExpired',
        cancelled: 'cancelled', superseded: 'replaced', undone: 'undone',
        confirming: 'processing', undoing: 'processing', failed: 'failed',
    };
    const outcome = chatElement('p', 'ai-chat-outcome', chatText(labels[message.state]) +
        (message.outcome ? '\n' + message.outcome : ''));
    actions.append(confirm, cancel, undo, keep);
    card.append(actions, outcome);
    chatMessages.append(card);
    cancel.addEventListener('click', async () => {
        if (chatBusy) return;
        setChatBusy(true);
        try {
            const conversation = await chatRequest('/api/chat/cancel', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token: proposal.token}),
            });
            setChatConversation(conversation);
        } catch (error) {
            outcome.textContent = error.message;
        } finally { setChatBusy(false); }
    });
    confirm.addEventListener('click', async () => {
        if (chatBusy) return;
        confirm.disabled = cancel.disabled = true;
        setChatBusy(true, chatText('saving'));
        try {
            await chatRequest('/api/chat/confirm', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token: proposal.token}),
            });
            await loadChatConversation(chatConversation.id);
            await loadSampleList(searchInput.value);
        } catch (error) {
            outcome.textContent = chatText('uncertain') + '\n' + error.message;
        } finally { setChatBusy(false); scrollChat(); }
    });
    keep.addEventListener('click', () => {
        if (chatBusy) return;
        undoReady = false;
        keep.hidden = true;
        undo.textContent = chatText('undo');
        outcome.textContent = chatText('saved') + (message.outcome ? '\n' + message.outcome : '');
    });
    undo.addEventListener('click', async () => {
        if (chatBusy) return;
        if (!undoReady) {
            undoReady = true;
            keep.hidden = false;
            undo.textContent = chatText('confirmUndo');
            outcome.textContent = chatText(proposal.operation === 'create' ? 'undoCreate' : 'undoUpdate') + proposal.sample_id;
            scrollChat();
            return;
        }
        undo.disabled = keep.disabled = true;
        setChatBusy(true, chatText('undoing'));
        try {
            const data = await chatRequest('/api/chat/undo', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token: message.undo_token}),
            });
            if (data.deleted && currentSampleId === proposal.sample_id) {
                currentSampleId = null;
                originalData = null;
                isNewSample = true;
                sampleIdInput.disabled = false;
                showForm(t('form.newSampleTitle'), false, false);
                updateChatContext();
            }
            await loadChatConversation(chatConversation.id);
            await loadSampleList(searchInput.value);
        } catch (error) {
            outcome.textContent = chatText('undoUncertain') + '\n' + error.message;
        } finally { setChatBusy(false); scrollChat(); }
    });
}
async function sendChatMessage(event) {
    event.preventDefault();
    const content = chatInput.value.trim();
    if (!content || chatBusy) return;
    appendChatMessage('user', content);
    chatInput.value = '';
    setChatBusy(true, chatText('thinking'));
    try {
        const data = await chatRequest('/api/chat', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({conversation_id: chatConversation.id, revision: chatConversation.revision,
                message: content, sample_id: currentSampleId, lang: currentLang}),
        });
        setChatConversation(data.conversation);
    } catch (error) {
        renderChatConversation();
        chatInput.value = content;
        appendChatMessage('assistant', error.message, true);
    } finally {
        setChatBusy(false);
        chatInput.focus({preventScroll: true});
    }
}
async function initializeChat() {
    setChatBusy(true, chatText('loading'));
    try {
        await loadChatConversations();
        const remembered = localStorage.getItem('crystal-chat-conversation');
        const selected = chatConversationList.find(conversation => conversation.id === remembered) || chatConversationList[0];
        if (selected) await loadChatConversation(selected.id);
        else {
            setChatConversation(await chatRequest('/api/chat/conversations', {method: 'POST'}));
        }
    } catch (error) {
        appendChatMessage('assistant', error.message, true);
    } finally { setChatBusy(false); }
}
chatResizer.addEventListener('pointerdown', event => {
    if (chatSmallScreen.matches || event.button !== 0 || chatResizeStart) return;
    event.preventDefault();
    chatResizer.focus({preventScroll: true});
    chatResizeStart = {pointerId: event.pointerId, x: event.clientX, width: chatWidth};
    chatResizer.setPointerCapture(event.pointerId);
    document.body.classList.add('ai-chat-resizing');
});
chatResizer.addEventListener('pointermove', event => {
    if (chatResizeStart && event.pointerId === chatResizeStart.pointerId && !chatSmallScreen.matches) {
        setChatWidth(chatResizeStart.width + chatResizeStart.x - event.clientX);
    }
});
['pointerup', 'pointercancel', 'lostpointercapture'].forEach(type => chatResizer.addEventListener(type, finishChatResize));
chatResizer.addEventListener('keydown', event => {
    if (chatSmallScreen.matches) return;
    const widths = {ArrowLeft: chatWidth + 20, ArrowRight: chatWidth - 20, Home: 320, End: 720};
    if (!(event.key in widths)) return;
    event.preventDefault();
    setChatWidth(widths[event.key], true);
});
chatResizer.addEventListener('dblclick', () => { if (!chatSmallScreen.matches) setChatWidth(360, true); });
window.addEventListener('resize', () => setChatWidth(chatWidth));
chatLauncher.addEventListener('click', () => setChatOpen(true));
document.getElementById('aiChatClose').addEventListener('click', () => setChatOpen(false));
chatBackdrop.addEventListener('click', () => setChatOpen(false));
document.getElementById('aiChatForm').addEventListener('submit', sendChatMessage);
chatInput.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) sendChatMessage(event);
});
chatReset.addEventListener('click', async () => {
    if (chatBusy) return;
    setChatBusy(true, chatText('loading'));
    try {
        setChatConversation(await chatRequest('/api/chat/conversations', {method: 'POST'}));
        chatInput.value = '';
    } catch (error) {
        appendChatMessage('assistant', error.message, true);
    } finally { setChatBusy(false); chatInput.focus(); }
});
chatConversations.addEventListener('change', async () => {
    setChatBusy(true, chatText('loading'));
    try {
        await loadChatConversation(chatConversations.value);
        chatInput.value = '';
    } catch (error) {
        chatConversations.value = chatConversation ? chatConversation.id : '';
        appendChatMessage('assistant', error.message, true);
    } finally { setChatBusy(false); }
});
chatRefresh.addEventListener('click', async () => {
    setChatBusy(true, chatText('loading'));
    try {
        await loadChatConversations();
        if (chatConversation) await loadChatConversation(chatConversation.id);
        else await initializeChat();
    } catch (error) {
        appendChatMessage('assistant', error.message, true);
    } finally { setChatBusy(false); }
});
chatPanel.addEventListener('keydown', event => {
    if (event.key === 'Escape') setChatOpen(false);
    if (event.key === 'Tab' && chatSmallScreen.matches) {
        const controls = [...chatPanel.querySelectorAll('button:not(:disabled):not([hidden]), select:not(:disabled), textarea:not(:disabled)')];
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
});
chatSmallScreen.addEventListener('change', () => {
    if (chatResizeStart) finishChatResize(chatResizeStart);
    setChatOpen(!chatPanel.hidden);
});
setChatWidth(chatWidth);
updateChatLanguage();
if (!chatSmallScreen.matches) {
    chatPanel.hidden = false;
    document.body.classList.add('ai-chat-open');
    chatLauncher.setAttribute('aria-expanded', 'true');
}
initializeChat();
