/* ============================================================
   晶体材料样品管理系统 - 前端主逻辑
   ============================================================ */

// ---- State ----
let currentSampleId = null;   // 当前选中的样品 ID
let isEditing = false;        // 是否在编辑模式
let isNewSample = false;      // 是否是新建样品
let originalData = null;      // 编辑前的原始数据 (用于退出编辑恢复)
let allElements = {};         // 元素摩尔质量表

// ---- i18n Dictionary ----
const translations = {
    zh: {
        title: "晶体材料样品管理系统",
        nav: { sampleList: "样品列表", logoutTitle: "退出登录", logout: "🔒 退出" },
        sidebar: { searchPlaceholder: "搜索样品编号、产物、备注...", clearSearch: "清除搜索", newSample: "新建样品" },
        main: { emptyStateTitle: "选择或新建一个样品", emptyStateDesc: "从左侧列表选择一个样品查看详情，或点击「新建样品」开始记录" },
        form: {
            newSampleTitle: "新建样品", editSampleTitle: "编辑样品", copySampleTitle: "复制样品 — 请输入新编号",
            copyTitle: "复制此样品的流程、产物、元素配比", copyBtn: "复制样品", cancelBtn: "退出编辑", deleteBtn: "删除", saveBtn: "保存",
            sections: { basicInfo: "基本信息", growthProcess: "生长流程", results: "结果", notes: "额外备注", calculator: "元素比例 & 质量计算", photos: "实物照片", edx: "EDX 能谱分析", dataFiles: "数据文件 (.dat)", otherFiles: "其他文件" },
            fields: { sampleId: "样品编号", targetProduct: "目标产物", status: "状态", measurements: "测量",
                       sinteringStart: "开始烧制时间", sinteringDuration: "烧制耗时 (小时)", sinteringEnd: "结束时间",
                       sinteringNowBtn: "当前时间", sinteringNowTitle: "设为当前时间" },
            placeholders: { sampleId: "例如: CG-2026-001", targetProduct: "例如: FeSi₂", growthProcess: "描述晶体的生长方法、温度曲线、时间等参数...", results: "实验结果描述...", notes: "其他需要记录的信息..." },
            status: { success: "成功", fail: "失败", pending: "待定", growing: "生长中" },
            measurements: { electric: "电学测量", magnetic: "磁性测量" },
            badges: { electric: "电", magnetic: "磁" },
            calc: { symbol: "元素符号", ratio: "摩尔比", molarMass: "摩尔质量 (g/mol)", mass: "实际质量 (g)", reference: "参考", addElement: "添加元素", calcMass: "计算质量" },
            upload: { dragPhoto: "拖拽照片到此处，或", dragEdx: "拖拽 EDX 谱图到此处，或", dragData: "拖拽 .dat/.csv/.txt 文件到此处，或", dragOther: "拖拽任何其他文件到此处，或", clickUpload: "点击上传", takePhoto: "拍照上传" }
        },
        messages: {
            samplesCount: "{0} 个样品", noMatch: "没有找到匹配的样品", noSamples: "还没有样品，点击上方按钮新建",
            fetchElementsFailed: "获取元素表失败", loadListFailed: "加载样品列表失败", fetchSampleFailed: "获取样品详情失败",
            enterId: "请输入样品编号", saveFailed: "保存失败", saveSuccess: "保存成功", restoredOriginal: "已恢复原始数据",
            confirmDelete: "确定要删除样品 \"{0}\" 吗？此操作不可撤销。", deleteFailed: "删除失败", deleteSuccess: "已删除样品",
            copySuccess: "已复制流程、产物、元素配比，请输入新的样品编号", addElementFirst: "请先添加元素", selectReference: "请选择一个参考元素",
            enterReferenceMass: "请输入参考元素的质量", calcFailed: "计算失败", calcSuccess: "计算完成",
            saveBeforeUpload: "请先保存样品后再上传文件", uploadFailed: "上传失败", uploadSuccess: "上传成功",
            recognizing: "正在调用 AI 识别...", recognizeFailed: "识别失败", edxSuccess: "EDX 识别完成",
            noData: "未识别到元素数据", recognizeErrorPrefix: "识别失败: ", confirmDeleteFile: "确定要删除此文件吗？", confirmLogout: "确定要退出登录吗？",
            edxHeader: { element: "元素", wt: "质量百分比 (%)", at: "原子百分比 (%)", nodata: "暂无识别数据，请点击「AI 识别」按钮" },
            aiBtn: "🤖 AI 识别", delBtn: "× 删除",
            todoSynced: "已同步到 Microsoft To Do", todoSyncFailed: "To Do 同步失败: {0}"
        },
        msTodo: { connect: "连接 To Do", connected: "已连接 To Do", disconnect: "断开 To Do", notConfigured: "请先在 config.py 配置 MS_CLIENT_ID", confirmDisconnect: "确定要断开 Microsoft To Do 连接吗？" }
    },
    en: {
        title: "Crystal Sample Management",
        nav: { sampleList: "Sample List", logoutTitle: "Logout", logout: "🔒 Logout" },
        sidebar: { searchPlaceholder: "Search ID, product, notes...", clearSearch: "Clear", newSample: "New Sample" },
        main: { emptyStateTitle: "Select or Create a Sample", emptyStateDesc: "Select a sample from the list to view details, or click 'New Sample'." },
        form: {
            newSampleTitle: "New Sample", editSampleTitle: "Edit Sample", copySampleTitle: "Copy Sample — Enter New ID",
            copyTitle: "Copy process, product, and elemental ratios", copyBtn: "Copy", cancelBtn: "Cancel", deleteBtn: "Delete", saveBtn: "Save",
            sections: { basicInfo: "Basic Info", growthProcess: "Growth Process", results: "Results", notes: "Notes", calculator: "Element Ratios & Mass", photos: "Photos", edx: "EDX Analysis", dataFiles: "Data Files (.dat)", otherFiles: "Other Files" },
            fields: { sampleId: "Sample ID", targetProduct: "Target Product", status: "Status", measurements: "Measurements",
                       sinteringStart: "Sintering Start", sinteringDuration: "Duration (hours)", sinteringEnd: "End Time",
                       sinteringNowBtn: "Now", sinteringNowTitle: "Set to current time" },
            placeholders: { sampleId: "e.g., CG-2026-001", targetProduct: "e.g., FeSi₂", growthProcess: "Describe growth method, temp profile, time, etc...", results: "Experiment results...", notes: "Any other notes..." },
            status: { success: "Success", fail: "Fail", pending: "Pending", growing: "Growing" },
            measurements: { electric: "Electric", magnetic: "Magnetic" },
            badges: { electric: "Elec", magnetic: "Mag" },
            calc: { symbol: "Symbol", ratio: "Mol Ratio", molarMass: "Molar Mass (g/mol)", mass: "Actual Mass (g)", reference: "Ref", addElement: "Add Element", calcMass: "Calculate Mass" },
            upload: { dragPhoto: "Drag photos here, or ", dragEdx: "Drag EDX spectra here, or ", dragData: "Drag .dat/.csv/.txt files here, or ", dragOther: "Drag any other files here, or ", clickUpload: "Click to Select", takePhoto: "Take Photo" }
        },
        messages: {
            samplesCount: "{0} Samples", noMatch: "No matching samples found", noSamples: "No samples yet, create one.",
            fetchElementsFailed: "Failed to fetch elements", loadListFailed: "Failed to load sample list", fetchSampleFailed: "Failed to fetch sample details",
            enterId: "Please enter Sample ID", saveFailed: "Failed to save", saveSuccess: "Saved successfully", restoredOriginal: "Restored original data",
            confirmDelete: "Are you sure you want to delete sample \"{0}\"? This action cannot be undone.", deleteFailed: "Failed to delete", deleteSuccess: "Sample deleted",
            copySuccess: "Copied process, product, and ratios. Please enter a new ID.", addElementFirst: "Add an element first", selectReference: "Select a reference element",
            enterReferenceMass: "Enter the reference mass", calcFailed: "Calculation failed", calcSuccess: "Calculation complete",
            saveBeforeUpload: "Please save the sample before uploading files", uploadFailed: "Upload failed", uploadSuccess: "Upload successful",
            recognizing: "Calling AI for recognition...", recognizeFailed: "Recognition failed", edxSuccess: "EDX Recognition complete",
            noData: "No element data identified", recognizeErrorPrefix: "Recognition failed: ", confirmDeleteFile: "Are you sure you want to delete this file?", confirmLogout: "Are you sure you want to logout?",
            edxHeader: { element: "Element", wt: "Weight %", at: "Atomic %", nodata: "No data, click 'AI Recognition' button" },
            aiBtn: "🤖 AI Recognize", delBtn: "× Delete",
            todoSynced: "Synced to Microsoft To Do", todoSyncFailed: "To Do sync failed: {0}"
        },
        msTodo: { connect: "Connect To Do", connected: "Connected", disconnect: "Disconnect To Do", notConfigured: "Please configure MS_CLIENT_ID in config.py", confirmDisconnect: "Disconnect Microsoft To Do?" }
    }
};

let currentLang = localStorage.getItem('crystal_lang') || 'zh'; // 默认中文

function t(path, ...args) {
    let result = path.split('.').reduce((obj, key) => (obj && obj[key] !== 'undefined') ? obj[key] : null, translations[currentLang]);
    if (result === null) {
        result = path.split('.').reduce((obj, key) => (obj && obj[key] !== 'undefined') ? obj[key] : null, translations['zh']); // Fallback
        if (result === null) return path;
    }
    if (args.length > 0) {
        args.forEach((arg, i) => { result = result.replace(`{${i}}`, arg); });
    }
    return result;
}

function updateI18n() {
    // 翻译常规元素的 textContent
    document.querySelectorAll('[data-i18n]').forEach(el => {
        el.innerHTML = t(el.getAttribute('data-i18n'));
    });
    // 翻译 placeholder
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        el.placeholder = t(el.getAttribute('data-i18n-placeholder'));
    });
    // 翻译 title
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        el.title = t(el.getAttribute('data-i18n-title'));
    });
    // 翻译混合属性 (e.g. data-i18n-attr="content|description")
    document.querySelectorAll('[data-i18n-attr]').forEach(el => {
        const rules = el.getAttribute('data-i18n-attr').split(',');
        rules.forEach(rule => {
            const [attrName, transKey] = rule.split('|');
            if (attrName && transKey) el.setAttribute(attrName, t(transKey));
        });
    });
    
    // 更新动态文本（如样品数量、表单标题、空列表提示）
    if(sampleList.querySelector('.list-empty')) loadSampleList(searchInput.value);
    if(sampleCountEl && sampleCountEl.dataset.count !== undefined) {
        sampleCountEl.textContent = t('messages.samplesCount', sampleCountEl.dataset.count);
    }
    if(isEditing && currentSampleId) {
        formTitle.textContent = t('form.editSampleTitle');
    } else if (isNewSample) {
        if(document.getElementById('copyBtn').style.display === 'none') {
             formTitle.textContent = t('form.newSampleTitle');
        } else {
             // Form is in "Copy" mode but not saved yet, we let it be handled when needed or keep "newSampleTitle" 
        }
    }
    
    // 重新渲染可能的动态块
    if(originalData) {
         renderEdxList(originalData.edx_images || []);
    }
}

function toggleLanguage() {
    currentLang = currentLang === 'zh' ? 'en' : 'zh';
    localStorage.setItem('crystal_lang', currentLang);
    updateI18n();
}


// ---- DOM Elements ----
const sampleList = document.getElementById('sampleList');
const sampleForm = document.getElementById('sampleForm');
const emptyState = document.getElementById('emptyState');
const searchInput = document.getElementById('searchInput');
const clearSearchBtn = document.getElementById('clearSearchBtn');
const newSampleBtn = document.getElementById('newSampleBtn');
const fullscreenListBtn = document.getElementById('fullscreenListBtn');
const saveBtn = document.getElementById('saveBtn');
const cancelBtn = document.getElementById('cancelBtn');
const deleteBtn = document.getElementById('deleteBtn');
const copyBtn = document.getElementById('copyBtn');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const formTitle = document.getElementById('formTitle');
const sampleCountEl = document.getElementById('sampleCount');

// Form fields
const sampleIdInput = document.getElementById('sampleId');
const targetProductInput = document.getElementById('targetProduct');
const growthProcessInput = document.getElementById('growthProcess');
const resultsFieldInput = document.getElementById('resultsField');
const notesFieldInput = document.getElementById('notesField');
const toggleSuccess = document.getElementById('toggleSuccess');
const toggleFail = document.getElementById('toggleFail');
const togglePending = document.getElementById('togglePending');
const toggleElectric = document.getElementById('toggleElectric');
const toggleMagnetic = document.getElementById('toggleMagnetic');
const toggleGrowing = document.getElementById('toggleGrowing');

// Sintering time
const sinteringStartInput = document.getElementById('sinteringStart');
const sinteringDurationInput = document.getElementById('sinteringDuration');
const sinteringEndInput = document.getElementById('sinteringEnd');
const btnNow = document.getElementById('btnNow');

// Element calculator
const elementTableBody = document.getElementById('elementTableBody');
const addElementBtn = document.getElementById('addElementBtn');
const calculateBtn = document.getElementById('calculateBtn');

// Upload zones
const photoUploadZone = document.getElementById('photoUploadZone');
const photoInput = document.getElementById('photoInput');
const photoGrid = document.getElementById('photoGrid');

const edxUploadZone = document.getElementById('edxUploadZone');
const edxInput = document.getElementById('edxInput');
const edxList = document.getElementById('edxList');

const dataUploadZone = document.getElementById('dataUploadZone');
const dataInput = document.getElementById('dataInput');
const dataFileList = document.getElementById('dataFileList');

const otherUploadZone = document.getElementById('otherUploadZone');
const otherInput = document.getElementById('otherInput');
const otherFileList = document.getElementById('otherFileList');

// Modal
const imageModal = document.getElementById('imageModal');
const modalImage = document.getElementById('modalImage');
const modalCloseBtn = document.getElementById('modalCloseBtn');

// ---- Init ----
document.addEventListener('DOMContentLoaded', async () => {
    updateI18n(); // 初始化语言界面
    // 获取元素表
    try {
        const resp = await fetch('/api/elements');
        allElements = await resp.json();
    } catch (e) {
        console.error(t('messages.fetchElementsFailed'), e);
    }

    loadSampleList();
    bindEvents();
    bindTextareaResize();
    checkMsStatus(); // 检查 Microsoft To Do 连接状态
});

// ============================================================
// Event Binding
// ============================================================
function bindEvents() {
    // Search
    searchInput.addEventListener('input', debounce(() => {
        clearSearchBtn.classList.toggle('visible', searchInput.value.length > 0);
        loadSampleList(searchInput.value);
    }, 300));

    clearSearchBtn.addEventListener('click', () => {
        searchInput.value = '';
        clearSearchBtn.classList.remove('visible');
        loadSampleList();
    });

    // New sample
    newSampleBtn.addEventListener('click', () => createNewSample());

    // Fullscreen list toggle
    if (fullscreenListBtn) {
        fullscreenListBtn.addEventListener('click', () => {
            const sidebar = document.getElementById('sidebar');
            const icon = document.getElementById('fullscreenIcon');
            sidebar.classList.toggle('is-fullscreen');
            
            if (sidebar.classList.contains('is-fullscreen')) {
                fullscreenListBtn.title = '退出全屏';
                icon.innerHTML = '<path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/>';
            } else {
                fullscreenListBtn.title = '全屏显示';
                icon.innerHTML = '<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>';
            }
        });
    }

    // Sample list click - event delegation (handles special chars in IDs)
    sampleList.addEventListener('click', (e) => {
        const item = e.target.closest('.sample-item');
        if (item && item.dataset.id) {
            selectSample(item.dataset.id);
            // Exit fullscreen if active
            const sidebar = document.getElementById('sidebar');
            if (sidebar.classList.contains('is-fullscreen') && fullscreenListBtn) {
                sidebar.classList.remove('is-fullscreen');
                fullscreenListBtn.title = '全屏显示';
                document.getElementById('fullscreenIcon').innerHTML = '<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>';
            }
        }
    });

    // Save / Cancel / Delete / Copy / Prev / Next
    saveBtn.addEventListener('click', () => saveSample());
    cancelBtn.addEventListener('click', () => cancelEdit());
    deleteBtn.addEventListener('click', () => deleteSample());
    copyBtn.addEventListener('click', () => copySample());
    prevBtn.addEventListener('click', () => navigateSample(1));   // 上一页：往列表后面走（旧数据）
    nextBtn.addEventListener('click', () => navigateSample(-1));  // 下一页：往列表前面走（新数据）

    // Camera input (mobile) - photos
    const cameraInput = document.getElementById('cameraInput');
    if (cameraInput) {
        cameraInput.addEventListener('change', () => {
            if (cameraInput.files.length > 0) {
                uploadFiles(cameraInput.files, 'photos');
                cameraInput.value = '';
            }
        });
    }

    // Camera input (mobile) - EDX
    const edxCameraInput = document.getElementById('edxCameraInput');
    if (edxCameraInput) {
        edxCameraInput.addEventListener('change', () => {
            if (edxCameraInput.files.length > 0) {
                uploadFiles(edxCameraInput.files, 'edx');
                edxCameraInput.value = '';
            }
        });
    }

    // Toggle success/fail/pending
    toggleSuccess.addEventListener('click', () => {
        toggleSuccess.classList.add('active');
        toggleFail.classList.remove('active');
        togglePending.classList.remove('active');
        toggleGrowing.classList.remove('active');
    });
    toggleFail.addEventListener('click', () => {
        toggleFail.classList.add('active');
        toggleSuccess.classList.remove('active');
        togglePending.classList.remove('active');
        toggleGrowing.classList.remove('active');
    });
    togglePending.addEventListener('click', () => {
        togglePending.classList.add('active');
        toggleSuccess.classList.remove('active');
        toggleFail.classList.remove('active');
        toggleGrowing.classList.remove('active');
    });
    toggleGrowing.addEventListener('click', () => {
        toggleGrowing.classList.add('active');
        toggleSuccess.classList.remove('active');
        toggleFail.classList.remove('active');
        togglePending.classList.remove('active');
    });

    // Measurement toggles
    toggleElectric.addEventListener('click', (e) => {
        e.preventDefault();
        toggleElectric.classList.toggle('active');
    });
    toggleMagnetic.addEventListener('click', (e) => {
        e.preventDefault();
        toggleMagnetic.classList.toggle('active');
    });

    // Sintering time
    btnNow.addEventListener('click', () => {
        const now = new Date();
        // Format to datetime-local value: YYYY-MM-DDTHH:MM
        const pad = n => String(n).padStart(2, '0');
        const local = `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
        sinteringStartInput.value = local;
        updateSinteringEnd();
    });
    sinteringStartInput.addEventListener('change', updateSinteringEnd);
    sinteringDurationInput.addEventListener('input', updateSinteringEnd);

    // Element calculator
    addElementBtn.addEventListener('click', () => addElementRow());
    calculateBtn.addEventListener('click', () => calculateMass());

    // Photo upload
    setupUploadZone(photoUploadZone, photoInput, (files) => uploadFiles(files, 'photos'));

    // EDX upload
    setupUploadZone(edxUploadZone, edxInput, (files) => uploadFiles(files, 'edx'));

    // Data file upload
    setupUploadZone(dataUploadZone, dataInput, (files) => uploadFiles(files, 'datafiles'));

    // Other file upload
    setupUploadZone(otherUploadZone, otherInput, (files) => uploadFiles(files, 'otherfiles'));

    // Modal
    modalCloseBtn.addEventListener('click', closeModal);
    imageModal.addEventListener('click', (e) => {
        if (e.target === imageModal) closeModal();
    });

    // Keyboard - Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (imageModal.style.display !== 'none') closeModal();
            closeSidebar();
        }
    });

    // Mobile sidebar toggle
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            sidebarOverlay.classList.toggle('visible');
        });
    }
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeSidebar);
    }
}

function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('visible');
}

// Auto-resize textareas
function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto'; // Reset height to recalculate
    const newHeight = textarea.scrollHeight;
    if (newHeight > 0) {
        textarea.style.height = (newHeight + 2) + 'px'; // Set to scrollHeight + small buffer for border
    } else {
        textarea.style.height = '74px'; // Fallback default height if hidden
    }
}

function bindTextareaResize() {
    const textareas = document.querySelectorAll('textarea');
    textareas.forEach(textarea => {
        // Initial resize
        autoResizeTextarea(textarea);

        // Resize on input
        textarea.addEventListener('input', function () {
            autoResizeTextarea(this);
        });

        // Resize when window changes (optional, handles edge cases)
        window.addEventListener('resize', () => autoResizeTextarea(textarea));
    });
}


// ============================================================
// Sample List
// ============================================================
async function loadSampleList(query = '') {
    try {
        const url = query ? `/api/samples?q=${encodeURIComponent(query)}` : '/api/samples';
        const resp = await fetch(url);
        const samples = await resp.json();

        sampleCountEl.dataset.count = samples.length;
        sampleCountEl.textContent = t('messages.samplesCount', samples.length);

        if (samples.length === 0) {
            sampleList.innerHTML = `
                <li class="list-empty">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                    </svg>
                    <p>${query ? t('messages.noMatch') : t('messages.noSamples')}</p>
                </li>`;
            return;
        }

        sampleList.innerHTML = samples.map(s => `
            <li class="sample-item ${s.id === currentSampleId ? 'active' : ''}" 
                data-id="${escapeHtml(s.id)}">
                <div class="sample-item-id">
                    <span class="status-dot ${s.is_successful === 1 ? 'success' : (s.is_successful === 0 ? 'fail' : (s.is_successful === 3 ? 'growing' : 'pending'))}"></span>
                    ${escapeHtml(s.id)}
                    ${s.has_electric ? '<span class="badge badge-elect" data-i18n="form.badges.electric">' + t('form.badges.electric') + '</span>' : ''}
                    ${s.has_magnetic ? '<span class="badge badge-magn" data-i18n="form.badges.magnetic">' + t('form.badges.magnetic') + '</span>' : ''}
                </div>
                <div class="sample-item-product">${escapeHtml(s.target_product || '—')}</div>
                <div class="sample-item-date">${formatDate(s.sintering_start || s.created_at)}</div>
            </li>
        `).join('');
    } catch (e) {
        console.error(t('messages.loadListFailed'), e);
        showToast(t('messages.loadListFailed'), 'error');
    }
}

async function selectSample(id, scrollToTop = true) {
    currentSampleId = id;
    isNewSample = false;
    closeSidebar(); // auto-close on mobile

    try {
        const resp = await fetch(`/api/samples/${encodeURIComponent(id)}`);
        if (!resp.ok) throw new Error(t('messages.fetchSampleFailed'));
        const sample = await resp.json();

        originalData = JSON.parse(JSON.stringify(sample));
        fillForm(sample);
        showForm(t('form.editSampleTitle'), true, scrollToTop);
        highlightActive(id);
    } catch (e) {
        console.error(e);
        showToast(t('messages.fetchSampleFailed'), 'error');
    }
}

function highlightActive(id) {
    document.querySelectorAll('.sample-item').forEach(el => {
        el.classList.toggle('active', el.dataset.id === id);
    });
}

async function navigateSample(direction) {
    if (!currentSampleId) return;
    
    const items = Array.from(document.querySelectorAll('.sample-item'));
    if (items.length === 0) return;
    
    const currentIndex = items.findIndex(el => el.dataset.id === currentSampleId);
    if (currentIndex === -1) return;
    
    let targetIndex = currentIndex + direction;
    if (targetIndex < 0) {
        showToast(t('messages.alreadyLast') || '已经是最后一个了 (最新)', 'info');
        return;
    }
    if (targetIndex >= items.length) {
        showToast(t('messages.alreadyFirst') || '已经是第一个了 (最早)', 'info');
        return;
    }
    
    const targetId = items[targetIndex].dataset.id;
    await selectSample(targetId);
    showToast((t('messages.switchedTo') || '已切换到样品 ') + targetId, 'success');
}

// ============================================================
// Form Operations
// ============================================================
function createNewSample() {
    currentSampleId = null;
    isNewSample = true;
    originalData = null;

    // 清空表单
    sampleIdInput.value = '';
    sampleIdInput.disabled = false;
    targetProductInput.value = '';
    growthProcessInput.value = '';
    resultsFieldInput.value = '';
    notesFieldInput.value = '';

    // Auto-resize empty textareas back to minimal height
    autoResizeTextarea(growthProcessInput);
    autoResizeTextarea(resultsFieldInput);
    autoResizeTextarea(notesFieldInput);
    toggleSuccess.classList.remove('active');
    toggleFail.classList.remove('active');
    togglePending.classList.add('active');
    toggleGrowing.classList.remove('active');
    
    toggleElectric.classList.remove('active');
    toggleMagnetic.classList.remove('active');

    // Clear sintering time
    sinteringStartInput.value = '';
    sinteringDurationInput.value = '';
    sinteringEndInput.value = '';

    elementTableBody.innerHTML = '';
    photoGrid.innerHTML = '';
    edxList.innerHTML = '';
    dataFileList.innerHTML = '';
    otherFileList.innerHTML = '';

    // 默认添加两行元素
    addElementRow();
    addElementRow();

    showForm(t('form.newSampleTitle'), false);
    highlightActive(null);
}

function fillForm(sample) {
    sampleIdInput.value = sample.id;
    sampleIdInput.disabled = false; // 允许修改 ID
    targetProductInput.value = sample.target_product || '';
    growthProcessInput.value = sample.growth_process || '';
    resultsFieldInput.value = sample.results || '';
    notesFieldInput.value = sample.notes || '';

    // Auto-resize populated textareas
    autoResizeTextarea(growthProcessInput);
    autoResizeTextarea(resultsFieldInput);
    autoResizeTextarea(notesFieldInput);

    toggleSuccess.classList.remove('active');
    toggleFail.classList.remove('active');
    togglePending.classList.remove('active');
    toggleGrowing.classList.remove('active');

    let sVal = sample.status !== undefined ? sample.status : sample.is_successful;
    if (sVal === 2) {
        togglePending.classList.add('active');
    } else if (sVal === 3) {
        toggleGrowing.classList.add('active');
    } else if (sVal === 1 || sVal === true) {
        toggleSuccess.classList.add('active');
    } else {
        toggleFail.classList.add('active');
    }

    if (sample.has_electric) toggleElectric.classList.add('active');
    else toggleElectric.classList.remove('active');

    if (sample.has_magnetic) toggleMagnetic.classList.add('active');
    else toggleMagnetic.classList.remove('active');

    // Sintering time
    sinteringStartInput.value = isoToDatetimeLocal(sample.sintering_start || '');
    sinteringDurationInput.value = (sample.sintering_duration != null && sample.sintering_duration !== '') ? sample.sintering_duration : '';
    updateSinteringEnd();

    // 元素表
    elementTableBody.innerHTML = '';
    const ratios = sample.element_ratios || [];
    const masses = sample.actual_masses || [];

    // Check if any element has is_reference set (for older saved samples)
    const hasExplicitRef = ratios.some(r => r.is_reference);

    if (ratios.length > 0) {
        ratios.forEach((item, idx) => {
            const mass = masses[idx] ? masses[idx].mass : '';
            const molarMass = allElements[item.element] || '';
            const isRef = hasExplicitRef ? item.is_reference : (idx === 0);
            addElementRow(item.element, item.ratio, molarMass, mass, isRef);
        });
    }

    // 照片
    renderPhotos(sample.photos || []);

    // EDX
    renderEdxList(sample.edx_images || []);

    // 数据文件
    renderDataFiles(sample.data_files || []);

    // 其他文件
    renderOtherFiles(sample.other_files || []);
}

function showForm(title, showDelete, scrollToTop = true) {
    emptyState.style.display = 'none';
    sampleForm.style.display = 'block';

    // Auto-resize textareas now that they are visible and have dimensions
    const formTextareas = sampleForm.querySelectorAll('textarea');
    formTextareas.forEach(ta => autoResizeTextarea(ta));

    formTitle.textContent = title;
    deleteBtn.style.display = showDelete ? 'inline-flex' : 'none';
    copyBtn.style.display = showDelete ? 'inline-flex' : 'none';
    if (prevBtn) prevBtn.style.display = showDelete ? 'inline-flex' : 'none';
    if (nextBtn) nextBtn.style.display = showDelete ? 'inline-flex' : 'none';
    isEditing = true;

    if (scrollToTop) {
        document.getElementById('mainPanel').scrollTop = 0;
    }
}

async function saveSample() {
    const id = sampleIdInput.value.trim();
    if (!id) {
        showToast(t('messages.enterId'), 'warning');
        sampleIdInput.focus();
        return;
    }

    let statusVal = 1;
    if (toggleFail.classList.contains('active')) statusVal = 0;
    else if (togglePending.classList.contains('active')) statusVal = 2;
    else if (toggleGrowing.classList.contains('active')) statusVal = 3;
    
    const hasElectric = toggleElectric.classList.contains('active') ? 1 : 0;
    const hasMagnetic = toggleMagnetic.classList.contains('active') ? 1 : 0;

    // 收集元素数据
    const elementRows = elementTableBody.querySelectorAll('tr');
    const elementRatios = [];
    const actualMasses = [];
    elementRows.forEach(row => {
        const elInput = row.querySelector('.el-symbol');
        const ratioInput = row.querySelector('.el-ratio');
        const massInput = row.querySelector('.el-mass');
        const refRadio = row.querySelector('.ref-radio');

        if (elInput && elInput.value.trim()) {
            elementRatios.push({
                element: elInput.value.trim(),
                ratio: parseFloat(ratioInput.value) || 0,
                is_reference: refRadio ? refRadio.checked : false
            });
            actualMasses.push({
                element: elInput.value.trim(),
                mass: parseFloat(massInput.value) || 0
            });
        }
    });

    const data = {
        id: id,
        target_product: targetProductInput.value.trim(),
        status: statusVal,
        has_electric: hasElectric,
        has_magnetic: hasMagnetic,
        growth_process: growthProcessInput.value.trim(),
        results: resultsFieldInput.value.trim(),
        notes: notesFieldInput.value.trim(),
        element_ratios: elementRatios,
        actual_masses: actualMasses,
        sintering_start: datetimeLocalToIso(sinteringStartInput.value),
        sintering_duration: sinteringDurationInput.value !== '' ? parseFloat(sinteringDurationInput.value) : null,
        sintering_end: sinteringEndInput.value
    };

    try {
        let resp;
        if (isNewSample) {
            resp = await fetch('/api/samples', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        } else {
            resp = await fetch(`/api/samples/${encodeURIComponent(currentSampleId || id)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || t('messages.saveFailed'));
        }

        const saved = await resp.json();
        currentSampleId = saved.id;
        isNewSample = false;
        originalData = JSON.parse(JSON.stringify(saved));
        fillForm(saved);
        showForm(t('form.editSampleTitle'), true);
        await loadSampleList(searchInput.value);
        highlightActive(saved.id);
        showToast(t('messages.saveSuccess'), 'success');

        // 显示 To Do 同步结果
        if (saved.todo_synced) {
            showToast(t('messages.todoSynced'), 'info');
        } else if (saved.todo_msg && saved.todo_msg !== '') {
            // 仅在有同步尝试时才显示失败
            if (saved.todo_msg !== '未连接 Microsoft To Do') {
                showToast(t('messages.todoSyncFailed', saved.todo_msg), 'warning');
            }
        }
    } catch (e) {
        console.error(e);
        showToast(e.message, 'error');
    }
}

function cancelEdit() {
    if (isNewSample) {
        // 退出新建
        sampleForm.style.display = 'none';
        emptyState.style.display = 'flex';
        isEditing = false;
        isNewSample = false;
        currentSampleId = null;
        highlightActive(null);
    } else if (originalData) {
        // 恢复原始数据
        fillForm(originalData);
        showToast(t('messages.restoredOriginal'), 'info');
    }
}

async function deleteSample() {
    if (!currentSampleId) return;
    if (!confirm(t('messages.confirmDelete', currentSampleId))) return;

    try {
        const resp = await fetch(`/api/samples/${encodeURIComponent(currentSampleId)}`, {
            method: 'DELETE'
        });
        if (!resp.ok) throw new Error(t('messages.deleteFailed'));

        showToast(t('messages.deleteSuccess'), 'success');
        sampleForm.style.display = 'none';
        emptyState.style.display = 'flex';
        currentSampleId = null;
        isEditing = false;
        await loadSampleList(searchInput.value);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function copySample() {
    if (!originalData) return;

    // 切换为新建模式，但保留关键字段
    currentSampleId = null;
    isNewSample = true;

    // 清空 ID，让用户输入新编号
    sampleIdInput.value = '';
    sampleIdInput.disabled = false;
    sampleIdInput.focus();

    // 保留的字段：目标产物、生长流程、元素比例、质量
    targetProductInput.value = originalData.target_product || '';
    growthProcessInput.value = originalData.growth_process || '';

    // 清空这些字段
    resultsFieldInput.value = '';
    notesFieldInput.value = '';

    // Auto-resize empty/populated textareas
    autoResizeTextarea(growthProcessInput);
    autoResizeTextarea(resultsFieldInput);
    autoResizeTextarea(notesFieldInput);
    toggleSuccess.classList.remove('active');
    toggleFail.classList.remove('active');
    togglePending.classList.add('active');
    toggleGrowing.classList.remove('active');

    toggleElectric.classList.remove('active');
    toggleMagnetic.classList.remove('active');

    // Clear sintering time for copy
    sinteringStartInput.value = '';
    sinteringDurationInput.value = '';
    sinteringEndInput.value = ''

    // Find currently selected reference element before clearing
    let selectedRefElement = null;
    const currentRefRadio = elementTableBody.querySelector('.ref-radio:checked');
    if (currentRefRadio) {
        const row = currentRefRadio.closest('tr');
        if (row) {
            const symInput = row.querySelector('.el-symbol');
            if (symInput) selectedRefElement = symInput.value.trim();
        }
    }

    // 元素表 - 复制比例和质量
    elementTableBody.innerHTML = '';
    const ratios = originalData.element_ratios || [];
    const masses = originalData.actual_masses || [];
    if (ratios.length > 0) {
        ratios.forEach((item, idx) => {
            const mass = masses[idx] ? masses[idx].mass : '';
            const molarMass = allElements[item.element] || '';
            const isRef = selectedRefElement ? (item.element === selectedRefElement) : (idx === 0);
            addElementRow(item.element, item.ratio, molarMass, mass, isRef);
        });
    } else {
        addElementRow();
        addElementRow();
    }

    // 清空附件区（新样品不复制附件）
    photoGrid.innerHTML = '';
    edxList.innerHTML = '';
    dataFileList.innerHTML = '';

    showForm(t('form.copySampleTitle'), false);
    highlightActive(null);
    showToast(t('messages.copySuccess'), 'info');
}

// ============================================================
// Element Calculator
// ============================================================
function addElementRow(element = '', ratio = '', molarMass = '', mass = '', isRef = false) {
    const formattedMass = (mass !== '' && mass !== 0 && !isNaN(mass)) ? parseFloat(mass).toFixed(4) : mass;
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><input type="text" class="el-symbol" value="${escapeHtml(String(element))}" placeholder="Fe" 
             oninput="onElementInput(this)"></td>
        <td><input type="number" class="el-ratio" value="${ratio}" placeholder="1" step="0.01" min="0.01" max="150"></td>
        <td><input type="text" class="el-molar readonly-mass" value="${molarMass}" readonly tabindex="-1"></td>
        <td><input type="number" class="el-mass" value="${formattedMass}" placeholder="—" step="0.0001" min="0" max="50"></td>
        <td style="text-align:center"><input type="radio" name="refElement" class="ref-radio" ${isRef ? 'checked' : ''}></td>
        <td><button class="element-row-del" onclick="this.closest('tr').remove()">×</button></td>
    `;
    elementTableBody.appendChild(tr);

    // 如果是第一行且没有选中参考元素，则选中
    if (elementTableBody.querySelectorAll('tr').length === 1) {
        tr.querySelector('.ref-radio').checked = true;
    }
}

// 当输入元素符号时，自动填充摩尔质量
window.onElementInput = function (input) {
    const val = input.value.trim();
    const row = input.closest('tr');
    const molarInput = row.querySelector('.el-molar');

    // 首字母大写，第二个字母小写
    if (val.length > 0) {
        const formatted = val.charAt(0).toUpperCase() + val.slice(1).toLowerCase();
        if (allElements[formatted] !== undefined) {
            molarInput.value = allElements[formatted];
            input.value = formatted;
        } else {
            molarInput.value = '';
        }
    } else {
        molarInput.value = '';
    }
};

async function calculateMass() {
    const rows = elementTableBody.querySelectorAll('tr');
    if (rows.length === 0) {
        showToast(t('messages.addElementFirst'), 'warning');
        return;
    }

    // 找参考元素
    let refElement = null;
    let refMass = 0;
    const elements = [];

    rows.forEach(row => {
        const el = row.querySelector('.el-symbol').value.trim();
        const ratio = parseFloat(row.querySelector('.el-ratio').value) || 0;
        const mass = parseFloat(row.querySelector('.el-mass').value) || 0;
        const isRef = row.querySelector('.ref-radio').checked;

        if (el) {
            elements.push({ element: el, ratio: ratio });
            if (isRef) {
                refElement = el;
                refMass = mass;
            }
        }
    });

    if (!refElement) {
        showToast(t('messages.selectReference'), 'warning');
        return;
    }

    if (refMass <= 0) {
        showToast(t('messages.enterReferenceMass'), 'warning');
        return;
    }

    try {
        const resp = await fetch('/api/calculate_mass', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                elements: elements,
                reference_element: refElement,
                reference_mass: refMass
            })
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || t('messages.calcFailed'));
        }

        const data = await resp.json();

        // 填充结果
        const resultMap = {};
        data.results.forEach(r => { resultMap[r.element] = r; });

        rows.forEach(row => {
            const el = row.querySelector('.el-symbol').value.trim();
            if (resultMap[el]) {
                row.querySelector('.el-mass').value = parseFloat(resultMap[el].mass).toFixed(4);
                row.querySelector('.el-molar').value = resultMap[el].molar_mass;
            }
        });

        showToast(t('messages.calcSuccess'), 'success');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ============================================================
// File Upload
// ============================================================
function setupUploadZone(zone, input, onFiles) {
    zone.addEventListener('click', (e) => {
        if (e.target.closest('button')) return; // 避免点击删除按钮时触发
        input.click();
    });

    input.addEventListener('change', () => {
        if (input.files.length > 0) {
            onFiles(input.files);
            input.value = '';
        }
    });

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            onFiles(e.dataTransfer.files);
        }
    });
}

async function uploadFiles(files, type) {
    // 必须先保存样品
    if (isNewSample || !currentSampleId) {
        showToast(t('messages.saveBeforeUpload'), 'warning');
        return;
    }

    const formData = new FormData();
    for (const file of files) {
        formData.append('file', file);
    }

    const urlMap = {
        photos: `/api/samples/${encodeURIComponent(currentSampleId)}/photos`,
        edx: `/api/samples/${encodeURIComponent(currentSampleId)}/edx`,
        datafiles: `/api/samples/${encodeURIComponent(currentSampleId)}/datafiles`,
        otherfiles: `/api/samples/${encodeURIComponent(currentSampleId)}/otherfiles`
    };

    try {
        const resp = await fetch(urlMap[type], {
            method: 'POST',
            body: formData
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || t('messages.uploadFailed'));
        }

        showToast(t('messages.uploadSuccess'), 'success');
        // 重新加载样品详情，但保持滚动位置
        await selectSample(currentSampleId, false);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ============================================================
// Render attachments
// ============================================================
function renderPhotos(photos) {
    if (photos.length === 0) {
        photoGrid.innerHTML = '';
        return;
    }

    photoGrid.innerHTML = photos.map(p => {
        const src = getUploadUrl(p.filepath);
        const thumbSrc = src + '?thumb=1';
        return `
            <div class="photo-item" onclick="openModal('${escapeJs(src)}')">
                <img src="${thumbSrc}" alt="${escapeHtml(p.filename)}" loading="lazy">
                <button class="photo-delete" onclick="event.stopPropagation(); deleteAttachment('photos', ${p.id})" title="删除">×</button>
            </div>
        `;
    }).join('');
}

function renderEdxList(edxImages) {
    if (edxImages.length === 0) {
        edxList.innerHTML = '';
        return;
    }

    edxList.innerHTML = edxImages.map(edx => {
        const src = getUploadUrl(edx.filepath);
        const thumbSrc = src + '?thumb=1';
        const hasData = edx.recognized_data && edx.recognized_data.length > 0;

        let tableHtml = '';
        if (hasData) {
            tableHtml = `
                <table class="edx-table">
                    <thead>
                        <tr>
                            <th>${t('messages.edxHeader.element')}</th>
                            <th>${t('messages.edxHeader.wt')}</th>
                            <th>${t('messages.edxHeader.at')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${edx.recognized_data.map(d => `
                            <tr>
                                <td>${escapeHtml(d.element)}</td>
                                <td>${d.weight_percent ?? '—'}</td>
                                <td>${d.atomic_percent ?? '—'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        } else {
            tableHtml = `<div class="edx-no-data">${t('messages.edxHeader.nodata')}</div>`;
        }

        return `
            <div class="edx-card">
                <div class="edx-card-header">
                    <span class="edx-card-title">📊 ${escapeHtml(edx.filename)}</span>
                    <div class="edx-card-actions">
                        <button class="btn-accent btn-sm" onclick="recognizeEdx(${edx.id}, this)">
                            ${t('messages.aiBtn')}
                        </button>
                        <button class="btn-danger btn-sm" onclick="deleteAttachment('edx', ${edx.id})">
                            ${t('messages.delBtn')}
                        </button>
                    </div>
                </div>
                <div class="edx-content">
                    <div class="edx-image" onclick="openModal('${escapeJs(src)}')">
                        <img src="${thumbSrc}" alt="${escapeHtml(edx.filename)}" loading="lazy">
                    </div>
                    <div class="edx-table-container" id="edxTable_${edx.id}">
                        ${tableHtml}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function renderDataFiles(files) {
    if (files.length === 0) {
        dataFileList.innerHTML = '';
        return;
    }

    dataFileList.innerHTML = files.map(f => `
        <div class="file-item">
            <div class="file-info">
                <div class="file-icon">📄</div>
                <div>
                    <div class="file-name">${escapeHtml(f.filename)}</div>
                    <div class="file-date">${formatDate(f.uploaded_at)}</div>
                </div>
            </div>
            <div class="file-actions">
                <a href="${getUploadUrl(f.filepath)}" download="${escapeHtml(f.filename)}" class="file-action-btn" title="下载">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="7,10 12,15 17,10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                </a>
                <button class="file-action-btn delete" onclick="deleteAttachment('datafiles', ${f.id})" title="删除">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <polyline points="3,6 5,6 21,6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

function renderOtherFiles(files) {
    if (files.length === 0) {
        otherFileList.innerHTML = '';
        return;
    }

    otherFileList.innerHTML = files.map(f => `
        <div class="file-item">
            <div class="file-info">
                <div class="file-icon">📂</div>
                <div>
                    <div class="file-name">${escapeHtml(f.filename)}</div>
                    <div class="file-date">${formatDate(f.uploaded_at)}</div>
                </div>
            </div>
            <div class="file-actions">
                <a href="${getUploadUrl(f.filepath)}" download="${escapeHtml(f.filename)}" class="file-action-btn" title="下载">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="7,10 12,15 17,10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                </a>
                <button class="file-action-btn delete" onclick="deleteAttachment('otherfiles', ${f.id})" title="删除">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <polyline points="3,6 5,6 21,6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

// ============================================================
// EDX Recognition
// ============================================================
async function recognizeEdx(edxId, btn) {
    const tableContainer = document.getElementById(`edxTable_${edxId}`);
    const originalBtnText = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = '⏳ ...';
    tableContainer.innerHTML = `
        <div class="recognizing">
            <span class="loading-dot"></span>
            <span class="loading-dot"></span>
            <span class="loading-dot"></span>
            ${t('messages.recognizing')}
        </div>
    `;

    try {
        const resp = await fetch(`/api/edx/${edxId}/recognize`, { method: 'POST' });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || t('messages.recognizeFailed'));
        }

        const data = await resp.json();
        const results = data.recognized_data || [];

        if (results.length > 0) {
            tableContainer.innerHTML = `
                <table class="edx-table">
                    <thead>
                        <tr><th>${t('messages.edxHeader.element')}</th><th>${t('messages.edxHeader.wt')}</th><th>${t('messages.edxHeader.at')}</th></tr>
                    </thead>
                    <tbody>
                        ${results.map(d => `
                            <tr>
                                <td>${escapeHtml(d.element)}</td>
                                <td>${d.weight_percent ?? '—'}</td>
                                <td>${d.atomic_percent ?? '—'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            showToast(t('messages.edxSuccess'), 'success');
        } else {
            tableContainer.innerHTML = `<div class="edx-no-data">${t('messages.noData')}</div>`;
            showToast(t('messages.noData'), 'warning');
        }
    } catch (e) {
        tableContainer.innerHTML = `<div class="edx-no-data" style="color:var(--danger)">${t('messages.recognizeErrorPrefix')}${escapeHtml(e.message)}</div>`;
        showToast(e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalBtnText;
    }
}

// Make it globally accessible
window.recognizeEdx = recognizeEdx;

// ============================================================
// Delete Attachment
// ============================================================
async function deleteAttachment(type, id) {
    if (!confirm(t('messages.confirmDeleteFile'))) return;

    const urlMap = {
        photos: `/api/photos/${id}`,
        edx: `/api/edx/${id}`,
        datafiles: `/api/datafiles/${id}`,
        otherfiles: `/api/otherfiles/${id}`
    };

    try {
        const resp = await fetch(urlMap[type], { method: 'DELETE' });
        if (!resp.ok) throw new Error(t('messages.deleteFailed'));

        showToast(t('messages.deleteSuccess'), 'success');
        // 重新加载（保持滚动位置）
        if (currentSampleId) await selectSample(currentSampleId, false);
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// Make it globally accessible
window.deleteAttachment = deleteAttachment;

// ============================================================
// Image Modal
// ============================================================
function openModal(src) {
    modalImage.src = src;
    imageModal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    imageModal.style.display = 'none';
    document.body.style.overflow = '';
}

// Make globally accessible
window.openModal = openModal;
window.selectSample = selectSample;

// ============================================================
// Utilities
// ============================================================
function getUploadUrl(filepath) {
    // filepath is absolute, convert to relative URL
    // Example: C:\...\uploads\photos\xxx.jpg -> /uploads/photos/xxx.jpg
    if (!filepath) return '';
    const parts = filepath.replace(/\\/g, '/').split('/uploads/');
    if (parts.length > 1) {
        return '/uploads/' + parts[parts.length - 1];
    }
    return filepath;
}

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function escapeJs(str) {
    return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('zh-CN', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
    });
}

function debounce(fn, ms) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// ============================================================
// Logout
// ============================================================
async function logout() {
    if (!confirm(t('messages.confirmLogout'))) return;
    try {
        await fetch('/api/logout', { method: 'POST' });
    } catch (e) { /* ignore */ }
    window.location.href = '/login';
}

window.logout = logout;

// ============================================================
// Microsoft To Do Integration
// ============================================================

async function checkMsStatus() {
    try {
        const resp = await fetch('/api/ms-status');
        const data = await resp.json();
        const btn = document.getElementById('msTodoBtn');
        const icon = document.getElementById('msTodoIcon');
        const label = document.getElementById('msTodoLabel');
        if (!btn) return;

        if (!data.configured) {
            btn.classList.add('ms-not-configured');
            btn.classList.remove('ms-connected');
            icon.textContent = '📋';
            label.textContent = t('msTodo.connect');
        } else if (data.connected) {
            btn.classList.add('ms-connected');
            btn.classList.remove('ms-not-configured');
            icon.textContent = '✅';
            label.textContent = t('msTodo.connected');
        } else {
            btn.classList.remove('ms-connected', 'ms-not-configured');
            icon.textContent = '📋';
            label.textContent = t('msTodo.connect');
        }
    } catch (e) {
        console.error('检查 MS To Do 状态失败', e);
    }
}

async function handleMsTodo() {
    try {
        const resp = await fetch('/api/ms-status');
        const data = await resp.json();

        if (!data.configured) {
            showToast(t('msTodo.notConfigured'), 'warning');
            return;
        }

        if (data.connected) {
            // 已连接，提供断开选项
            if (confirm(t('msTodo.confirmDisconnect'))) {
                await fetch('/api/ms-disconnect', { method: 'POST' });
                showToast(t('msTodo.disconnect'), 'info');
                checkMsStatus();
            }
        } else {
            // 未连接，开始授权
            window.location.href = '/auth/microsoft';
        }
    } catch (e) {
        showToast('Microsoft To Do 操作失败', 'error');
    }
}

window.handleMsTodo = handleMsTodo;

// ============================================================
// Sintering Time Helpers
// ============================================================

/**
 * Convert ISO datetime string to datetime-local input value (YYYY-MM-DDTHH:MM)
 */
function isoToDatetimeLocal(isoStr) {
    if (!isoStr) return '';
    // Support both ISO ("2026-04-16T14:30:00") and already-local formats
    let d;
    try {
        // datetime-local format is already local; if stored as ISO with offset, parse correctly
        d = new Date(isoStr);
        if (isNaN(d.getTime())) return isoStr;
        const pad = n => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    } catch (e) {
        return isoStr;
    }
}

/**
 * Convert datetime-local string back to a display-friendly string for storage.
 * We store exactly the string from the input (local time, no timezone offset).
 */
function datetimeLocalToIso(localStr) {
    return localStr || '';
}

/**
 * Compute sintering end time from start + duration, display in sinteringEndInput.
 */
function updateSinteringEnd() {
    const startVal = sinteringStartInput.value;
    const durVal = sinteringDurationInput.value;

    if (!startVal || durVal === '' || durVal === null) {
        sinteringEndInput.value = '';
        return;
    }

    const startDate = new Date(startVal);
    const durationHours = parseFloat(durVal);

    if (isNaN(startDate.getTime()) || isNaN(durationHours) || durationHours < 0) {
        sinteringEndInput.value = '';
        return;
    }

    const endDate = new Date(startDate.getTime() + durationHours * 3600 * 1000);
    const pad = n => String(n).padStart(2, '0');
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    const weekday = weekdays[endDate.getDay()];
    const endStr = `${endDate.getFullYear()}-${pad(endDate.getMonth()+1)}-${pad(endDate.getDate())} ${pad(endDate.getHours())}:${pad(endDate.getMinutes())}  ${weekday}`;
    sinteringEndInput.value = endStr;
}

