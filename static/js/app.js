/* ============================================================
   晶体材料样品管理系统 - 前端主逻辑
   ============================================================ */

// ---- State ----
let currentSampleId = null;   // 当前选中的样品 ID
let isEditing = false;        // 是否在编辑模式
let isNewSample = false;      // 是否是新建样品
let originalData = null;      // 编辑前的原始数据 (用于退出编辑恢复)
let allElements = {};         // 元素摩尔质量表

// ---- DOM Elements ----
const sampleList = document.getElementById('sampleList');
const sampleForm = document.getElementById('sampleForm');
const emptyState = document.getElementById('emptyState');
const searchInput = document.getElementById('searchInput');
const clearSearchBtn = document.getElementById('clearSearchBtn');
const newSampleBtn = document.getElementById('newSampleBtn');
const saveBtn = document.getElementById('saveBtn');
const cancelBtn = document.getElementById('cancelBtn');
const deleteBtn = document.getElementById('deleteBtn');
const copyBtn = document.getElementById('copyBtn');
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

// Modal
const imageModal = document.getElementById('imageModal');
const modalImage = document.getElementById('modalImage');
const modalCloseBtn = document.getElementById('modalCloseBtn');

// ---- Init ----
document.addEventListener('DOMContentLoaded', async () => {
    // 获取元素表
    try {
        const resp = await fetch('/api/elements');
        allElements = await resp.json();
    } catch (e) {
        console.error('获取元素表失败', e);
    }

    loadSampleList();
    bindEvents();
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

    // Sample list click - event delegation (handles special chars in IDs)
    sampleList.addEventListener('click', (e) => {
        const item = e.target.closest('.sample-item');
        if (item && item.dataset.id) {
            selectSample(item.dataset.id);
        }
    });

    // Save / Cancel / Delete / Copy
    saveBtn.addEventListener('click', () => saveSample());
    cancelBtn.addEventListener('click', () => cancelEdit());
    deleteBtn.addEventListener('click', () => deleteSample());
    copyBtn.addEventListener('click', () => copySample());

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

    // Toggle success/fail
    toggleSuccess.addEventListener('click', () => {
        toggleSuccess.classList.add('active');
        toggleFail.classList.remove('active');
    });
    toggleFail.addEventListener('click', () => {
        toggleFail.classList.add('active');
        toggleSuccess.classList.remove('active');
    });

    // Element calculator
    addElementBtn.addEventListener('click', () => addElementRow());
    calculateBtn.addEventListener('click', () => calculateMass());

    // Photo upload
    setupUploadZone(photoUploadZone, photoInput, (files) => uploadFiles(files, 'photos'));
    
    // EDX upload
    setupUploadZone(edxUploadZone, edxInput, (files) => uploadFiles(files, 'edx'));

    // Data file upload
    setupUploadZone(dataUploadZone, dataInput, (files) => uploadFiles(files, 'datafiles'));

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


// ============================================================
// Sample List
// ============================================================
async function loadSampleList(query = '') {
    try {
        const url = query ? `/api/samples?q=${encodeURIComponent(query)}` : '/api/samples';
        const resp = await fetch(url);
        const samples = await resp.json();

        sampleCountEl.textContent = `${samples.length} 个样品`;

        if (samples.length === 0) {
            sampleList.innerHTML = `
                <li class="list-empty">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                    </svg>
                    <p>${query ? '没有找到匹配的样品' : '还没有样品，点击上方按钮新建'}</p>
                </li>`;
            return;
        }

        sampleList.innerHTML = samples.map(s => `
            <li class="sample-item ${s.id === currentSampleId ? 'active' : ''}" 
                data-id="${escapeHtml(s.id)}">
                <div class="sample-item-id">
                    <span class="status-dot ${s.is_successful ? 'success' : 'fail'}"></span>
                    ${escapeHtml(s.id)}
                </div>
                <div class="sample-item-product">${escapeHtml(s.target_product || '—')}</div>
                <div class="sample-item-date">${formatDate(s.updated_at)}</div>
            </li>
        `).join('');
    } catch (e) {
        console.error('加载样品列表失败', e);
        showToast('加载样品列表失败', 'error');
    }
}

async function selectSample(id, scrollToTop = true) {
    currentSampleId = id;
    isNewSample = false;
    closeSidebar(); // auto-close on mobile

    try {
        const resp = await fetch(`/api/samples/${encodeURIComponent(id)}`);
        if (!resp.ok) throw new Error('获取样品失败');
        const sample = await resp.json();

        originalData = JSON.parse(JSON.stringify(sample));
        fillForm(sample);
        showForm('编辑样品', true, scrollToTop);
        highlightActive(id);
    } catch (e) {
        console.error(e);
        showToast('获取样品详情失败', 'error');
    }
}

function highlightActive(id) {
    document.querySelectorAll('.sample-item').forEach(el => {
        el.classList.toggle('active', el.dataset.id === id);
    });
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
    toggleSuccess.classList.add('active');
    toggleFail.classList.remove('active');
    elementTableBody.innerHTML = '';
    photoGrid.innerHTML = '';
    edxList.innerHTML = '';
    dataFileList.innerHTML = '';

    // 默认添加两行元素
    addElementRow();
    addElementRow();

    showForm('新建样品', false);
    highlightActive(null);
}

function fillForm(sample) {
    sampleIdInput.value = sample.id;
    sampleIdInput.disabled = false; // 允许修改 ID
    targetProductInput.value = sample.target_product || '';
    growthProcessInput.value = sample.growth_process || '';
    resultsFieldInput.value = sample.results || '';
    notesFieldInput.value = sample.notes || '';

    if (sample.is_successful) {
        toggleSuccess.classList.add('active');
        toggleFail.classList.remove('active');
    } else {
        toggleFail.classList.add('active');
        toggleSuccess.classList.remove('active');
    }

    // 元素表
    elementTableBody.innerHTML = '';
    const ratios = sample.element_ratios || [];
    const masses = sample.actual_masses || [];
    if (ratios.length > 0) {
        ratios.forEach((item, idx) => {
            const mass = masses[idx] ? masses[idx].mass : '';
            const molarMass = allElements[item.element] || '';
            addElementRow(item.element, item.ratio, molarMass, mass, idx === 0);
        });
    }

    // 照片
    renderPhotos(sample.photos || []);

    // EDX
    renderEdxList(sample.edx_images || []);

    // 数据文件
    renderDataFiles(sample.data_files || []);
}

function showForm(title, showDelete, scrollToTop = true) {
    emptyState.style.display = 'none';
    sampleForm.style.display = 'block';
    formTitle.textContent = title;
    deleteBtn.style.display = showDelete ? 'inline-flex' : 'none';
    copyBtn.style.display = showDelete ? 'inline-flex' : 'none';
    isEditing = true;

    if (scrollToTop) {
        document.getElementById('mainPanel').scrollTop = 0;
    }
}

async function saveSample() {
    const id = sampleIdInput.value.trim();
    if (!id) {
        showToast('请输入样品编号', 'warning');
        sampleIdInput.focus();
        return;
    }

    const isSuccessful = toggleSuccess.classList.contains('active');

    // 收集元素数据
    const elementRows = elementTableBody.querySelectorAll('tr');
    const elementRatios = [];
    const actualMasses = [];
    elementRows.forEach(row => {
        const elInput = row.querySelector('.el-symbol');
        const ratioInput = row.querySelector('.el-ratio');
        const massInput = row.querySelector('.el-mass');
        if (elInput && elInput.value.trim()) {
            elementRatios.push({
                element: elInput.value.trim(),
                ratio: parseFloat(ratioInput.value) || 0
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
        is_successful: isSuccessful,
        growth_process: growthProcessInput.value.trim(),
        results: resultsFieldInput.value.trim(),
        notes: notesFieldInput.value.trim(),
        element_ratios: elementRatios,
        actual_masses: actualMasses
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
            throw new Error(err.error || '保存失败');
        }

        const saved = await resp.json();
        currentSampleId = saved.id;
        isNewSample = false;
        originalData = JSON.parse(JSON.stringify(saved));
        fillForm(saved);
        showForm('编辑样品', true);
        await loadSampleList(searchInput.value);
        highlightActive(saved.id);
        showToast('保存成功', 'success');
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
        showToast('已恢复原始数据', 'info');
    }
}

async function deleteSample() {
    if (!currentSampleId) return;
    if (!confirm(`确定要删除样品 "${currentSampleId}" 吗？此操作不可撤销。`)) return;

    try {
        const resp = await fetch(`/api/samples/${encodeURIComponent(currentSampleId)}`, {
            method: 'DELETE'
        });
        if (!resp.ok) throw new Error('删除失败');

        showToast('已删除样品', 'success');
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
    toggleSuccess.classList.add('active');
    toggleFail.classList.remove('active');

    // 元素表 - 复制比例和质量
    elementTableBody.innerHTML = '';
    const ratios = originalData.element_ratios || [];
    const masses = originalData.actual_masses || [];
    if (ratios.length > 0) {
        ratios.forEach((item, idx) => {
            const mass = masses[idx] ? masses[idx].mass : '';
            const molarMass = allElements[item.element] || '';
            addElementRow(item.element, item.ratio, molarMass, mass, idx === 0);
        });
    } else {
        addElementRow();
        addElementRow();
    }

    // 清空附件区（新样品不复制附件）
    photoGrid.innerHTML = '';
    edxList.innerHTML = '';
    dataFileList.innerHTML = '';

    showForm('复制样品 — 请输入新编号', false);
    highlightActive(null);
    showToast('已复制流程、产物、元素配比，请输入新的样品编号', 'info');
}

// ============================================================
// Element Calculator
// ============================================================
function addElementRow(element = '', ratio = '', molarMass = '', mass = '', isRef = false) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><input type="text" class="el-symbol" value="${escapeHtml(String(element))}" placeholder="Fe" 
             oninput="onElementInput(this)"></td>
        <td><input type="number" class="el-ratio" value="${ratio}" placeholder="1" step="0.01" min="0.01" max="150"></td>
        <td><input type="text" class="el-molar readonly-mass" value="${molarMass}" readonly tabindex="-1"></td>
        <td><input type="number" class="el-mass" value="${mass}" placeholder="—" step="0.0001" min="0" max="50"></td>
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
window.onElementInput = function(input) {
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
        showToast('请先添加元素', 'warning');
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
        showToast('请选择一个参考元素', 'warning');
        return;
    }

    if (refMass <= 0) {
        showToast('请输入参考元素的质量', 'warning');
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
            throw new Error(err.error || '计算失败');
        }

        const data = await resp.json();
        
        // 填充结果
        const resultMap = {};
        data.results.forEach(r => { resultMap[r.element] = r; });

        rows.forEach(row => {
            const el = row.querySelector('.el-symbol').value.trim();
            if (resultMap[el]) {
                row.querySelector('.el-mass').value = resultMap[el].mass;
                row.querySelector('.el-molar').value = resultMap[el].molar_mass;
            }
        });

        showToast('计算完成', 'success');
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
        showToast('请先保存样品后再上传文件', 'warning');
        return;
    }

    const formData = new FormData();
    for (const file of files) {
        formData.append('file', file);
    }

    const urlMap = {
        photos: `/api/samples/${encodeURIComponent(currentSampleId)}/photos`,
        edx: `/api/samples/${encodeURIComponent(currentSampleId)}/edx`,
        datafiles: `/api/samples/${encodeURIComponent(currentSampleId)}/datafiles`
    };

    try {
        const resp = await fetch(urlMap[type], {
            method: 'POST',
            body: formData
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || '上传失败');
        }

        showToast('上传成功', 'success');
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
        return `
            <div class="photo-item" onclick="openModal('${escapeJs(src)}')">
                <img src="${src}" alt="${escapeHtml(p.filename)}" loading="lazy">
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
        const hasData = edx.recognized_data && edx.recognized_data.length > 0;

        let tableHtml = '';
        if (hasData) {
            tableHtml = `
                <table class="edx-table">
                    <thead>
                        <tr>
                            <th>元素</th>
                            <th>质量百分比 (%)</th>
                            <th>原子百分比 (%)</th>
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
            tableHtml = '<div class="edx-no-data">暂无识别数据，请点击「AI 识别」按钮</div>';
        }

        return `
            <div class="edx-card">
                <div class="edx-card-header">
                    <span class="edx-card-title">📊 ${escapeHtml(edx.filename)}</span>
                    <div class="edx-card-actions">
                        <button class="btn-accent btn-sm" onclick="recognizeEdx(${edx.id}, this)">
                            🤖 AI 识别
                        </button>
                        <button class="btn-danger btn-sm" onclick="deleteAttachment('edx', ${edx.id})">
                            × 删除
                        </button>
                    </div>
                </div>
                <div class="edx-content">
                    <div class="edx-image" onclick="openModal('${escapeJs(src)}')">
                        <img src="${src}" alt="${escapeHtml(edx.filename)}" loading="lazy">
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

// ============================================================
// EDX Recognition
// ============================================================
async function recognizeEdx(edxId, btn) {
    const tableContainer = document.getElementById(`edxTable_${edxId}`);
    const originalBtnText = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = '⏳ 识别中...';
    tableContainer.innerHTML = `
        <div class="recognizing">
            <span class="loading-dot"></span>
            <span class="loading-dot"></span>
            <span class="loading-dot"></span>
            正在调用 AI 识别...
        </div>
    `;

    try {
        const resp = await fetch(`/api/edx/${edxId}/recognize`, { method: 'POST' });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || '识别失败');
        }

        const data = await resp.json();
        const results = data.recognized_data || [];

        if (results.length > 0) {
            tableContainer.innerHTML = `
                <table class="edx-table">
                    <thead>
                        <tr><th>元素</th><th>质量百分比 (%)</th><th>原子百分比 (%)</th></tr>
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
            showToast('EDX 识别完成', 'success');
        } else {
            tableContainer.innerHTML = '<div class="edx-no-data">未识别到元素数据</div>';
            showToast('未识别到元素数据', 'warning');
        }
    } catch (e) {
        tableContainer.innerHTML = `<div class="edx-no-data" style="color:var(--danger)">识别失败: ${escapeHtml(e.message)}</div>`;
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
    if (!confirm('确定要删除此文件吗？')) return;

    const urlMap = {
        photos: `/api/photos/${id}`,
        edx: `/api/edx/${id}`,
        datafiles: `/api/datafiles/${id}`
    };

    try {
        const resp = await fetch(urlMap[type], { method: 'DELETE' });
        if (!resp.ok) throw new Error('删除失败');

        showToast('已删除', 'success');
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
    if (!confirm('确定要退出登录吗？')) return;
    try {
        await fetch('/api/logout', { method: 'POST' });
    } catch (e) { /* ignore */ }
    window.location.href = '/login';
}

window.logout = logout;

