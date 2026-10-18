/* AI text is rendered as plain text. Only a signed proposal can be confirmed. */
const chatCopy = {
    zh: {
        title: 'AI 样品助手', close: '收起助手', history: '聊天记录',
        notice: '只读取已保存数据；每次新建和修改都需确认。',
        inputLabel: '告诉助手要查找或修改什么', placeholder: '例如：把当前样品的烧制耗时改为 72 小时',
        reset: '新对话', send: '发送', keyHint: 'Enter 发送 · Shift + Enter 换行',
        context: '当前样品：', none: '未选择', draft: '新建草稿（尚未保存）',
        welcome: '可以查找样品、新建记录、修改生长制度或元素比例。先说明要求，再核对并确认具体变更。',
        examples: ['列出最近的样品', '查看当前样品的生长制度', '把当前样品的烧制耗时改为 72 小时'],
        user: '你', assistant: '助手', thinking: '正在读取样品并生成回复…', saving: '正在保存已确认的变更…',
        create: '待确认：新建样品 ', update: '待确认：修改样品 ', before: '修改前', after: '修改后',
        confirm: '确认保存', cancel: '取消', pending: '尚未保存 · 方案 30 分钟内有效',
        cancelled: '已取消，未保存。', replaced: '已由后续消息替代，未保存。',
        saved: '已保存。样品列表已刷新，当前表单草稿保留。重新点击样品可查看已保存数据。',
        uncertain: '保存状态未确认，请重新读取样品核对后再操作。', failed: '请求失败，请重试。',
        full: '对话较长，请开启新对话后继续。', yes: '是', no: '否', reference: '参考',
        statuses: ['失败', '成功', '待定', '生长中', '生长完成'],
    },
    en: {
        title: 'AI Sample Assistant', close: 'Close assistant', history: 'Chat history',
        notice: 'Reads saved data only. Every create or update needs your confirmation.',
        inputLabel: 'What would you like to find or change?', placeholder: 'For example: change this sample’s sintering duration to 72 hours',
        reset: 'New chat', send: 'Send', keyHint: 'Enter to send · Shift + Enter for a new line',
        context: 'Current sample: ', none: 'None selected', draft: 'New draft (not saved)',
        welcome: 'Find samples, create records, or change growth procedures and element ratios. Describe your request, then review and confirm the exact changes.',
        examples: ['List recent samples', 'Read this sample’s growth procedure', 'Change this sample’s sintering duration to 72 hours'],
        user: 'You', assistant: 'Assistant', thinking: 'Reading samples and preparing a reply…', saving: 'Saving your confirmed changes…',
        create: 'Confirm new sample: ', update: 'Confirm sample update: ', before: 'Before', after: 'After',
        confirm: 'Confirm save', cancel: 'Cancel', pending: 'Not saved · Proposal expires in 30 minutes',
        cancelled: 'Cancelled. Nothing saved.', replaced: 'Superseded by your next message. Nothing saved.',
        saved: 'Saved. The sample list was refreshed; your form draft was preserved. Select the sample again to view saved data.',
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
const chatLauncher = document.getElementById('aiChatToggle');
const chatBackdrop = document.getElementById('aiChatBackdrop');
const chatMessages = document.getElementById('aiChatMessages');
const chatInput = document.getElementById('aiChatInput');
const chatSend = document.getElementById('aiChatSend');
const chatReset = document.getElementById('aiChatReset');
const chatStatus = document.getElementById('aiChatStatus');
const chatSmallScreen = window.matchMedia('(max-width: 1350px)');
let chatHistory = [];
let chatPending = null;
let chatBusy = false;

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
    if (!chatHistory.length && !chatBusy) showChatWelcome();
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
function scrollChat() { chatMessages.scrollTop = chatMessages.scrollHeight; }
function setChatBusy(busy, status = '') {
    chatBusy = busy;
    chatSend.disabled = busy;
    chatReset.disabled = busy;
    chatInput.disabled = busy;
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
function resolveChatProposal(message) {
    if (!chatPending) return;
    chatPending.confirm.disabled = true;
    chatPending.cancel.disabled = true;
    chatPending.outcome.textContent = message;
    chatPending = null;
}
function showChatProposal(proposal) {
    const card = chatElement('section', 'ai-chat-proposal');
    card.append(chatElement('h3', '', chatText(proposal.operation) + proposal.sample_id),
        chatElement('p', 'ai-chat-proposal-note', chatText('pending')));
    const summary = [];
    proposal.diff.forEach(change => {
        const diff = chatElement('div', 'ai-chat-diff');
        const field = chatFields[change.field][currentLang === 'zh' ? 0 : 1];
        const before = chatValue(change.field, change.before);
        const after = chatValue(change.field, change.after);
        diff.append(chatElement('h4', '', field),
            chatElement('div', 'ai-chat-diff-label', chatText('before')),
            chatElement('div', 'ai-chat-diff-value', before),
            chatElement('div', 'ai-chat-diff-label', chatText('after')),
            chatElement('div', 'ai-chat-diff-value ai-chat-diff-after', after));
        card.append(diff);
        summary.push(`${field}: ${before} → ${after}`);
    });
    const actions = chatElement('div', 'ai-chat-proposal-actions');
    const confirm = chatElement('button', 'ai-chat-button ai-chat-primary', chatText('confirm'));
    const cancel = chatElement('button', 'ai-chat-button', chatText('cancel'));
    confirm.type = cancel.type = 'button';
    const outcome = chatElement('p', 'ai-chat-outcome');
    actions.append(confirm, cancel);
    card.append(actions, outcome);
    chatMessages.append(card);
    chatPending = {confirm, cancel, outcome};
    chatHistory.push({role: 'assistant', content: `${chatText(proposal.operation)}${proposal.sample_id}\n${summary.join('\n')}\n${chatText('pending')}`});
    cancel.addEventListener('click', () => {
        resolveChatProposal(chatText('cancelled'));
        chatHistory.push({role: 'assistant', content: chatText('cancelled')});
    });
    confirm.addEventListener('click', async () => {
        if (chatBusy) return;
        confirm.disabled = cancel.disabled = true;
        setChatBusy(true, chatText('saving'));
        try {
            const response = await fetch('/api/chat/confirm', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token: proposal.token}),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error);
            resolveChatProposal(chatText('saved'));
            chatHistory.push({role: 'assistant', content: `${proposal.sample_id}: ${chatText('saved')}`});
            await loadSampleList(searchInput.value);
            if (data.todo_msg) appendChatMessage('assistant', data.todo_msg);
        } catch (error) {
            const message = `${chatText('uncertain')}\n${error.message}`;
            resolveChatProposal(message);
            chatHistory.push({role: 'assistant', content: message});
        } finally {
            setChatBusy(false);
            scrollChat();
        }
    });
    scrollChat();
}
async function sendChatMessage(event) {
    event.preventDefault();
    const content = chatInput.value.trim();
    if (!content || chatBusy) return;
    if (chatHistory.length >= 28) { chatStatus.textContent = chatText('full'); return; }
    resolveChatProposal(chatText('replaced'));
    if (!chatHistory.length) chatMessages.replaceChildren();
    appendChatMessage('user', content);
    chatHistory.push({role: 'user', content});
    chatInput.value = '';
    setChatBusy(true, chatText('thinking'));
    try {
        const response = await fetch('/api/chat', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({messages: chatHistory, sample_id: currentSampleId, lang: currentLang}),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error);
        appendChatMessage('assistant', data.reply);
        if (data.proposal) showChatProposal(data.proposal);
        else chatHistory.push({role: 'assistant', content: data.reply});
    } catch (error) {
        chatHistory.pop();
        chatInput.value = content;
        appendChatMessage('assistant', error.message || chatText('failed'), true);
    } finally {
        setChatBusy(false);
        chatInput.focus({preventScroll: true});
    }
}
chatLauncher.addEventListener('click', () => setChatOpen(true));
document.getElementById('aiChatClose').addEventListener('click', () => setChatOpen(false));
chatBackdrop.addEventListener('click', () => setChatOpen(false));
document.getElementById('aiChatForm').addEventListener('submit', sendChatMessage);
chatInput.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) sendChatMessage(event);
});
chatReset.addEventListener('click', () => {
    resolveChatProposal(chatText('cancelled'));
    chatHistory = [];
    chatStatus.textContent = '';
    showChatWelcome();
    chatInput.focus();
});
chatPanel.addEventListener('keydown', event => {
    if (event.key === 'Escape') setChatOpen(false);
    if (event.key === 'Tab' && chatSmallScreen.matches) {
        const controls = [...chatPanel.querySelectorAll('button:not(:disabled), textarea:not(:disabled)')];
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
});
chatSmallScreen.addEventListener('change', () => setChatOpen(!chatPanel.hidden));
updateChatLanguage();
// Desktop uses an independent right column; touch layouts start collapsed.
if (!chatSmallScreen.matches) {
    chatPanel.hidden = false;
    document.body.classList.add('ai-chat-open');
    chatLauncher.setAttribute('aria-expanded', 'true');
}
