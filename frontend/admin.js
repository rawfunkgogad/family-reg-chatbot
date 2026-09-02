// State
let adminToken = sessionStorage.getItem("court_admin_token") || "";
let adminFilesList = [];
let adminDocsList = [];
let currentDocViewMode = "files"; // "files" or "chunks"

// DOM Elements
const authSection = document.getElementById("authSection");
const dashboardSection = document.getElementById("dashboardSection");
const adminLoginForm = document.getElementById("adminLoginForm");
const authCodeInput = document.getElementById("authCodeInput");
const btnTogglePassword = document.getElementById("btnTogglePassword");
const btnSubmitLogin = document.getElementById("btnSubmitLogin");
const loginAlertBox = document.getElementById("loginAlertBox");
const sessionBadge = document.getElementById("sessionBadge");
const btnLogout = document.getElementById("btnLogout");
const themeToggleBtn = document.getElementById("themeToggleBtn");

// Dashboard Elements
const statTotalChunks = document.getElementById("statTotalChunks");
const docsTotalBadge = document.getElementById("docsTotalBadge");
const tabListCount = document.getElementById("tabListCount");
const tabFilesCount = document.getElementById("tabFilesCount");
const tabChunksCount = document.getElementById("tabChunksCount");
const btnRefreshAdmin = document.getElementById("btnRefreshAdmin");
const btnResetDefault = document.getElementById("btnResetDefault");
const btnClearAll = document.getElementById("btnClearAll");
const modalTabs = document.querySelectorAll(".modal-tab");
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const uploadStatus = document.getElementById("uploadStatus");
const manualDocForm = document.getElementById("manualDocForm");
const adminDocTableBody = document.getElementById("adminDocTableBody");
const docSearchInput = document.getElementById("docSearchInput");
const viewModeFilesBtn = document.getElementById("viewModeFilesBtn");
const viewModeChunksBtn = document.getElementById("viewModeChunksBtn");
const adminFilesContainer = document.getElementById("adminFilesContainer");
const adminChunksContainer = document.getElementById("adminChunksContainer");

// Metrics Elements (Tab 4)
const metricTotalCalls = document.getElementById("metricTotalCalls");
const metricTodayCalls = document.getElementById("metricTodayCalls");
const metricRagRatio = document.getElementById("metricRagRatio");
const metricRagSub = document.getElementById("metricRagSub");
const metricTotalTokens = document.getElementById("metricTotalTokens");
const metricDailyCost = document.getElementById("metricDailyCost");
const metricAvgLatency = document.getElementById("metricAvgLatency");
const metricAvgLatencySub = document.getElementById("metricAvgLatencySub");
const metricHitRate = document.getElementById("metricHitRate");
const metricHitSub = document.getElementById("metricHitSub");
const metricSavedTokens = document.getElementById("metricSavedTokens");
const metricCachedCount = document.getElementById("metricCachedCount");
const refreshMetricsBtn = document.getElementById("refreshMetricsBtn");
const resetMetricsBtn = document.getElementById("resetMetricsBtn");
const clearCacheBtn = document.getElementById("clearCacheBtn");

// Security Elements (Tab 5)
const refreshSecurityBtn = document.getElementById("refreshSecurityBtn");
const metricTotalChecked = document.getElementById("metricTotalChecked");
const metricPiiMasked = document.getElementById("metricPiiMasked");
const metricAbuseBlocked = document.getElementById("metricAbuseBlocked");
const metricRrnMasked = document.getElementById("metricRrnMasked");

// Helper: Authenticated fetch wrapper
async function authFetch(url, options = {}) {
  const headers = options.headers ? { ...options.headers } : {};
  if (adminToken) {
    headers["Authorization"] = `Bearer ${adminToken}`;
  }
  options.headers = headers;

  const res = await fetch(url, options);
  if (res.status === 401) {
    // Session expired or invalid
    sessionStorage.removeItem("court_admin_token");
    adminToken = "";
    showAuthView();
    showLoginAlert("인증 세션이 만료되었습니다. 인증코드를 다시 입력해주세요.");
    throw new Error("401 Unauthorized");
  }
  return res;
}

// Initialization
document.addEventListener("DOMContentLoaded", () => {
  initThemeToggle();
  initAuthFlow();
  setupDashboardEvents();
  
  if (adminToken) {
    verifySession();
  } else {
    showAuthView();
  }
});

// Theme Toggle
function initThemeToggle() {
  const savedTheme = localStorage.getItem("court_ai_theme") || "dark";
  applyTheme(savedTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", () => {
      const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
      const nextTheme = currentTheme === "dark" ? "light" : "dark";
      applyTheme(nextTheme);
    });
  }
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("court_ai_theme", theme);
  
  if (themeToggleBtn) {
    const icon = themeToggleBtn.querySelector("i");
    const text = themeToggleBtn.querySelector(".theme-text");
    if (theme === "light") {
      if (icon) icon.className = "fa-solid fa-sun";
      if (text) text.textContent = "라이트";
      themeToggleBtn.title = "다크 모드로 전환";
    } else {
      if (icon) icon.className = "fa-solid fa-moon";
      if (text) text.textContent = "다크";
      themeToggleBtn.title = "라이트 모드로 전환";
    }
  }
}

// Auth Flow
function initAuthFlow() {
  // Toggle password visibility
  if (btnTogglePassword) {
    btnTogglePassword.addEventListener("click", () => {
      const isPassword = authCodeInput.type === "password";
      authCodeInput.type = isPassword ? "text" : "password";
      btnTogglePassword.innerHTML = isPassword ? '<i class="fa-regular fa-eye-slash"></i>' : '<i class="fa-regular fa-eye"></i>';
    });
  }

  // Login form submit
  if (adminLoginForm) {
    adminLoginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const code = authCodeInput.value.trim();
      if (!code) return;

      btnSubmitLogin.disabled = true;
      btnSubmitLogin.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 인증 확인 중...';
      hideLoginAlert();

      try {
        const res = await fetch("/api/admin/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ auth_code: code })
        });

        const data = await res.json();
        if (res.ok && data.success && data.token) {
          adminToken = data.token;
          sessionStorage.setItem("court_admin_token", adminToken);
          authCodeInput.value = "";
          showDashboardView();
          loadAdminFiles();
          loadAdminDocuments();
          loadMetricsStats();
          loadSecurityStats();
          loadQueryLogs(1, "");
        } else {
          showLoginAlert(data.detail || "인증코드가 올바르지 않습니다.");
          authCodeInput.focus();
        }
      } catch (err) {
        showLoginAlert(`서버 통신 오류: ${err.message}`);
      } finally {
        btnSubmitLogin.disabled = false;
        btnSubmitLogin.innerHTML = '<i class="fa-solid fa-shield-check"></i> 보안 인증 및 관리자 접속';
      }
    });
  }

  // Logout handler
  if (btnLogout) {
    btnLogout.addEventListener("click", async () => {
      if (!confirm("관리자 콘솔에서 로그아웃하시겠습니까?")) return;
      try {
        await authFetch("/api/admin/auth/logout", { method: "POST" });
      } catch (e) {
        // ignore
      }
      sessionStorage.removeItem("court_admin_token");
      adminToken = "";
      showAuthView();
    });
  }
}

async function verifySession() {
  try {
    const res = await authFetch("/api/admin/auth/verify");
    if (res.ok) {
      showDashboardView();
      loadAdminFiles();
      loadAdminDocuments();
      loadMetricsStats();
      loadSecurityStats();
      loadQueryLogs(1, "");
    }
  } catch (err) {
    showAuthView();
  }
}

function showAuthView() {
  authSection.style.display = "flex";
  dashboardSection.style.display = "none";
  sessionBadge.style.display = "none";
  btnLogout.style.display = "none";
  hideLoginAlert();
}

function showDashboardView() {
  authSection.style.display = "none";
  dashboardSection.style.display = "flex";
  sessionBadge.style.display = "flex";
  btnLogout.style.display = "inline-flex";
}

function showLoginAlert(msg) {
  loginAlertBox.style.display = "block";
  loginAlertBox.className = "auth-alert-box error";
  loginAlertBox.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> ${msg}`;
}

function hideLoginAlert() {
  loginAlertBox.style.display = "none";
}

// Dashboard Events
function setupDashboardEvents() {
  // Tab Switching
  modalTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      modalTabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      
      const tabId = tab.dataset.tab;
      document.querySelectorAll(".tab-pane").forEach(p => p.style.display = "none");
      const targetPane = document.getElementById(tabId);
      if (targetPane) targetPane.style.display = "block";

      if (tabId === "tab-list") {
        loadAdminFiles();
        loadAdminDocuments();
      } else if (tabId === "tab-metrics") {
        loadMetricsStats();
      } else if (tabId === "tab-security") {
        loadSecurityStats();
      } else if (tabId === "tab-logs") {
        loadQueryLogs(1, currentLogSearch);
      }
    });
  });

  // View Mode Switcher in Tab 3 (Files vs Chunks)
  if (viewModeFilesBtn && viewModeChunksBtn) {
    viewModeFilesBtn.addEventListener("click", () => {
      currentDocViewMode = "files";
      viewModeFilesBtn.classList.add("active");
      viewModeChunksBtn.classList.remove("active");
      adminFilesContainer.style.display = "flex";
      adminChunksContainer.style.display = "none";
    });

    viewModeChunksBtn.addEventListener("click", () => {
      currentDocViewMode = "chunks";
      viewModeChunksBtn.classList.add("active");
      viewModeFilesBtn.classList.remove("active");
      adminChunksContainer.style.display = "block";
      adminFilesContainer.style.display = "none";
    });
  }

  // Dropzone
  ['dragenter', 'dragover'].forEach(eventName => {
    if (dropzone) {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });
    }
  });

  ['dragleave', 'drop'].forEach(eventName => {
    if (dropzone) {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
      });
    }
  });

  if (dropzone) {
    dropzone.addEventListener('drop', (e) => {
      const files = e.dataTransfer.files;
      if (files.length > 0) uploadFile(files[0]);
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) uploadFile(e.target.files[0]);
    });
  }

  // Manual doc form
  if (manualDocForm) {
    manualDocForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const category = document.getElementById('manualCategory').value;
      const source = document.getElementById('manualSource').value.trim();
      const title = document.getElementById('manualTitle').value.trim();
      const content = document.getElementById('manualContent').value.trim();

      const saveBtn = document.getElementById('saveManualBtn');
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> bge-m3 임베딩 중...';

      try {
        const res = await authFetch('/api/admin/document', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ category, source, title, content })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          alert('신규 법률/선례 지식이 등록되고 bge-m3 임베딩이 완료되었습니다.');
          manualDocForm.reset();
          loadAdminFiles();
          loadAdminDocuments();
        } else {
          alert(`등록 실패: ${data.detail || '오류 발생'}`);
        }
      } catch (err) {
        alert(`오류: ${err.message}`);
      } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> 등록 및 bge-m3 임베딩 실행';
      }
    });
  }

  // Reindex all button
  if (reindexAllBtn) {
    reindexAllBtn.addEventListener('click', async () => {
      if (!confirm('현재 등록된 모든 문서에 대해 bge-m3 임베딩을 다시 생성하시겠습니까?')) return;
      reindexAllBtn.disabled = true;
      reindexAllBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 재색인 중...';
      try {
        const res = await authFetch('/api/admin/reindex', { method: 'POST' });
        const data = await res.json();
        if (res.ok && data.success) {
          alert(`전체 ${data.reindexed_count}건의 문서가 성공적으로 재임베딩되었습니다.`);
          loadAdminFiles();
          loadAdminDocuments();
        }
      } catch (err) {
        alert(`재색인 실패: ${err.message}`);
      } finally {
        reindexAllBtn.disabled = false;
        reindexAllBtn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> 재색인';
      }
    });
  }

  // Clear all documents button
  if (clearAllDocsBtn) {
    clearAllDocsBtn.addEventListener('click', async () => {
      const confirmText = prompt('등록된 모든 RAG 지식 문서와 임베딩 인덱스를 완전히 삭제하시겠습니까?\n삭제를 진행하려면 "전체삭제"를 입력하세요:');
      if (confirmText !== '전체삭제') {
        if (confirmText !== null) alert('입력 내용이 일치하지 않아 삭제가 취소되었습니다.');
        return;
      }

      clearAllDocsBtn.disabled = true;
      clearAllDocsBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 삭제 중...';
      try {
        const res = await authFetch('/api/admin/documents', { method: 'DELETE' });
        const data = await res.json();
        if (res.ok && data.success) {
          alert('모든 RAG 지식 문서 및 임베딩 인덱스가 완전히 삭제되었습니다.');
          loadAdminFiles();
          loadAdminDocuments();
        } else {
          alert(`삭제 실패: ${data.detail || '오류 발생'}`);
        }
      } catch (err) {
        alert(`오류: ${err.message}`);
      } finally {
        clearAllDocsBtn.disabled = false;
        clearAllDocsBtn.innerHTML = '<i class="fa-solid fa-trash-can"></i> 전체 삭제';
      }
    });
  }

  // Reset to default corpus button
  if (resetDefaultBtn) {
    resetDefaultBtn.addEventListener('click', async () => {
      if (!confirm('초기 기본 가족관계등록 법령/선례 지식 데이터로 복원하고 bge-m3 재임베딩을 진행하시겠습니까?')) return;
      resetDefaultBtn.disabled = true;
      resetDefaultBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 복원 중...';
      try {
        const res = await authFetch('/api/admin/reset-default', { method: 'POST' });
        const data = await res.json();
        if (res.ok && data.success) {
          alert(`기본 지식 코퍼스(${data.total_docs}건)로 성공적으로 복원 및 재임베딩되었습니다.`);
          loadAdminFiles();
          loadAdminDocuments();
        }
      } catch (err) {
        alert(`복원 실패: ${err.message}`);
      } finally {
        resetDefaultBtn.disabled = false;
        resetDefaultBtn.innerHTML = '<i class="fa-solid fa-rotate-left"></i> 기본 복원';
      }
    });
  }

  // Search filter for both Files and Chunks
  if (docSearchInput) {
    docSearchInput.addEventListener('input', (e) => {
      const keyword = e.target.value.toLowerCase();
      
      // Filter files
      const filteredFiles = adminFilesList.filter(f =>
        (f.file_name && f.file_name.toLowerCase().includes(keyword)) ||
        (f.category && f.category.toLowerCase().includes(keyword)) ||
        (f.chunks && f.chunks.some(c => c.content && c.content.toLowerCase().includes(keyword)))
      );
      renderAdminFiles(filteredFiles);

      // Filter chunks
      const filteredChunks = adminDocsList.filter(d => 
        (d.title && d.title.toLowerCase().includes(keyword)) ||
        (d.source && d.source.toLowerCase().includes(keyword)) ||
        (d.category && d.category.toLowerCase().includes(keyword)) ||
        (d.content && d.content.toLowerCase().includes(keyword))
      );
      renderAdminDocTable(filteredChunks);
    });
  }

  // Top Action Buttons
  if (btnRefreshAdmin) {
    btnRefreshAdmin.addEventListener('click', () => {
      loadAdminFiles();
      loadAdminDocuments();
      loadMetricsStats();
      loadSecurityStats();
      loadQueryLogs(1, currentLogSearch);
    });
  }

  if (btnClearAll) {
    btnClearAll.addEventListener('click', async () => {
      const confirmText = prompt('등록된 모든 RAG 지식 문서와 임베딩 인덱스를 완전히 삭제하시겠습니까?\n삭제를 진행하려면 "전체삭제"를 입력하세요:');
      if (confirmText !== '전체삭제') {
        if (confirmText !== null) alert('입력 내용이 일치하지 않아 삭제가 취소되었습니다.');
        return;
      }

      btnClearAll.disabled = true;
      btnClearAll.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 삭제 중...';
      try {
        const res = await authFetch('/api/admin/documents', { method: 'DELETE' });
        const data = await res.json();
        if (res.ok && data.success) {
          alert('모든 RAG 지식 문서 및 임베딩 인덱스가 완전히 삭제되었습니다.');
          loadAdminFiles();
          loadAdminDocuments();
        } else {
          alert(`삭제 실패: ${data.detail || '오류 발생'}`);
        }
      } catch (err) {
        alert(`오류: ${err.message}`);
      } finally {
        btnClearAll.disabled = false;
        btnClearAll.innerHTML = '<i class="fa-solid fa-trash-can"></i> 전체 비우기';
      }
    });
  }

  if (btnResetDefault) {
    btnResetDefault.addEventListener('click', async () => {
      if (!confirm('초기 기본 가족관계등록 법령/선례 지식 데이터로 복원하고 bge-m3 재임베딩을 진행하시겠습니까?')) return;
      btnResetDefault.disabled = true;
      btnResetDefault.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 복원 중...';
      try {
        const res = await authFetch('/api/admin/reset-default', { method: 'POST' });
        const data = await res.json();
        if (res.ok && data.success) {
          alert(`기본 지식 코퍼스(${data.total_docs}건)로 성공적으로 복원 및 재임베딩되었습니다.`);
          loadAdminFiles();
          loadAdminDocuments();
        } else {
          alert(`복원 실패: ${data.detail || '오류 발생'}`);
        }
      } catch (err) {
        alert(`복원 실패: ${err.message}`);
      } finally {
        btnResetDefault.disabled = false;
        btnResetDefault.innerHTML = '<i class="fa-solid fa-rotate-left"></i> 기본 코퍼스 복원';
      }
    });
  }

  // Metrics handlers
  if (refreshMetricsBtn) {
    refreshMetricsBtn.addEventListener('click', loadMetricsStats);
  }

  if (resetMetricsBtn) {
    resetMetricsBtn.addEventListener('click', async () => {
      if (!confirm('실시간 성능 지표를 초기화하시겠습니까?')) return;
      try {
        const res = await authFetch('/api/metrics/reset', { method: 'POST' });
        if (res.ok) {
          alert('통계 지표가 초기화되었습니다.');
          loadMetricsStats();
        }
      } catch (err) {
        alert(`오류: ${err.message}`);
      }
    });
  }

  if (clearCacheBtn) {
    clearCacheBtn.addEventListener('click', async () => {
      if (!confirm('저장된 모든 질의응답 캐시를 초기화하시겠습니까?')) return;
      try {
        const res = await fetch('/api/cache/clear', { method: 'POST' });
        if (res.ok) {
          alert('질의응답 캐시가 성공적으로 초기화되었습니다.');
          loadMetricsStats();
        }
      } catch (err) {
        alert(`오류: ${err.message}`);
      }
    });
  }

  if (refreshSecurityBtn) {
    refreshSecurityBtn.addEventListener('click', loadSecurityStats);
  }
}

// Upload file
async function uploadFile(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (ext !== 'pdf' && ext !== 'json' && ext !== 'xlsx' && ext !== 'xls') {
    showUploadStatus('PDF, JSON 또는 엑셀(.xlsx, .xls) 파일만 업로드할 수 있습니다.', 'error');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  const fileTypeLabel = (ext === 'xlsx' || ext === 'xls') ? '상하위 법령 엑셀' : (ext === 'pdf' ? 'PDF 실무편람' : 'JSON 지식');
  showUploadStatus(`'${file.name}' (${fileTypeLabel}) 업로드 및 bge-m3 임베딩 생성 중...`, 'loading');

  try {
    const res = await authFetch('/api/admin/upload', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (res.ok && data.success) {
      showUploadStatus(`'${file.name}' 등록 완료! (${data.chunks_created}개 지식/법령 체인 생성 및 bge-m3 임베딩 완료)`, 'success');
      loadAdminFiles();
      loadAdminDocuments();
    } else {
      showUploadStatus(`업로드 실패: ${data.detail || '오류 발생'}`, 'error');
    }
  } catch (err) {
    showUploadStatus(`업로드 오류: ${err.message}`, 'error');
  } finally {
    if (fileInput) fileInput.value = '';
  }
}

function showUploadStatus(msg, type) {
  if (!uploadStatus) return;
  uploadStatus.style.display = 'block';
  uploadStatus.className = `upload-status ${type}`;
  uploadStatus.innerHTML = msg;
}

// Load Grouped Files List
async function loadAdminFiles() {
  try {
    const res = await authFetch('/api/admin/files');
    if (!res.ok) return;
    const data = await res.json();
    adminFilesList = data.files || [];
    
    if (tabFilesCount) tabFilesCount.textContent = `${adminFilesList.length}`;
    if (tabChunksCount) tabChunksCount.textContent = `${data.total_chunks}`;
    if (adminDocCount) adminDocCount.textContent = `${data.total_chunks}건 (${adminFilesList.length}개 파일)`;
    if (tabListCount) tabListCount.textContent = `${adminFilesList.length}개 파일`;
    
    renderAdminFiles(adminFilesList);
  } catch (err) {
    console.error('Failed to load admin files:', err);
  }
}

function renderAdminFiles(files) {
  if (!adminFilesContainer) return;
  adminFilesContainer.innerHTML = '';

  if (files.length === 0) {
    adminFilesContainer.innerHTML = `
      <div style="text-align: center; color: #64748b; padding: 40px; background: rgba(30, 41, 59, 0.3); border-radius: 8px;">
        <i class="fa-solid fa-folder-open" style="font-size: 32px; margin-bottom: 8px; color: #475569;"></i>
        <p>등록된 지식 파일/문서가 없습니다. PDF, JSON 또는 엑셀(.xlsx) 파일을 업로드해 보세요.</p>
      </div>
    `;
    return;
  }

  files.forEach((file) => {
    const card = document.createElement('div');
    card.className = 'file-group-card';

    let iconClass = 'pdf';
    let iconTag = 'fa-file-pdf';
    if (file.file_type === 'EXCEL') {
      iconClass = 'excel';
      iconTag = 'fa-file-excel';
    } else if (file.file_type === 'JSON') {
      iconClass = 'json';
      iconTag = 'fa-file-code';
    } else if (file.file_type === 'BUILTIN') {
      iconClass = 'builtin';
      iconTag = 'fa-book-bookmark';
    } else if (file.file_type === 'MANUAL') {
      iconClass = 'manual';
      iconTag = 'fa-pen-nib';
    }

    const kbSize = (file.total_chars / 1024).toFixed(1);
    const dateStr = file.created_at ? new Date(file.created_at * 1000).toLocaleDateString('ko-KR') : '기본 탑재';

    card.innerHTML = `
      <div class="file-group-header" onclick="toggleFileDrawer('${file.file_id}')">
        <div class="file-group-left">
          <div class="file-type-icon ${iconClass}">
            <i class="fa-solid ${iconTag}"></i>
          </div>
          <div class="file-group-info">
            <div class="file-group-name" title="${file.file_name}">${file.file_name}</div>
            <div class="file-meta-row">
              <span class="doc-cat-tag">${file.category || '기타'}</span>
              <span class="file-chunk-badge"><i class="fa-solid fa-layer-group"></i> ${file.chunks_count}개 ${file.file_type === 'EXCEL' ? '법령체인' : '청크'}</span>
              <span class="file-size-tag">약 ${kbSize} KB</span>
              <span class="file-size-tag"><i class="fa-regular fa-clock"></i> ${dateStr}</span>
            </div>
          </div>
        </div>
        <div class="file-group-right" onclick="event.stopPropagation()">
          <button class="btn-toggle-chunks" onclick="toggleFileDrawer('${file.file_id}')">
            <i class="fa-solid fa-chevron-down toggle-icon-${file.file_id}"></i>
            <span>${file.file_type === 'EXCEL' ? '법령 체계 목록' : '청크 목록'}</span>
          </button>
          <button class="btn-del-file" title="이 파일의 모든 데이터 일괄 삭제" onclick="deleteAdminFile('${file.file_id}', '${file.file_name.replace(/'/g, "\\'")}')">
            <i class="fa-solid fa-trash-can"></i> 파일 삭제
          </button>
        </div>
      </div>
      <div class="file-chunks-drawer" id="drawer-${file.file_id}" style="display: none;">
        ${renderDrawerChunks(file.chunks)}
      </div>
    `;
    adminFilesContainer.appendChild(card);
  });
}

function renderDrawerChunks(chunks) {
  if (!chunks || chunks.length === 0) {
    return '<div style="color: #64748b; font-size: 11px;">상세 청크 데이터가 없습니다.</div>';
  }

  return chunks.map((c, idx) => {
    let hierarchyHtml = '';
    if (c.hierarchy_data) {
      const hd = c.hierarchy_data;
      hierarchyHtml = `
        <div class="hierarchy-breadcrumb-chain">
          ${hd.primary_law ? `<span class="hierarchy-chip tier-1"><i class="fa-solid fa-scale-balanced"></i> 법률: ${hd.primary_law}</span>` : ''}
          ${hd.sub_rule ? `<span class="hierarchy-arrow">➔</span><span class="hierarchy-chip tier-2"><i class="fa-solid fa-scroll"></i> 규칙: ${hd.sub_rule}</span>` : ''}
          ${hd.directive ? `<span class="hierarchy-arrow">➔</span><span class="hierarchy-chip tier-3"><i class="fa-solid fa-book"></i> 예규: ${hd.directive}</span>` : ''}
          ${hd.precedent ? `<span class="hierarchy-arrow">➔</span><span class="hierarchy-chip tier-4"><i class="fa-solid fa-gavel"></i> 선례: ${hd.precedent}</span>` : ''}
        </div>
      `;
    }

    return `
      <div class="drawer-chunk-item">
        <div class="drawer-chunk-header">
          <span class="drawer-chunk-title">[항목 ${idx + 1}] ${c.title || ''}</span>
          <span class="drawer-chunk-page">${c.page_number ? `제${c.page_number}페이지` : ''} (${c.char_length}자)</span>
        </div>
        ${hierarchyHtml}
        <div class="drawer-chunk-text">${c.preview || ''}</div>
      </div>
    `;
  }).join('');
}

// Toggle drawer
window.toggleFileDrawer = function(fileId) {
  const drawer = document.getElementById(`drawer-${fileId}`);
  const icon = document.querySelector(`.toggle-icon-${fileId}`);
  if (!drawer) return;

  const isOpen = drawer.style.display !== 'none';
  drawer.style.display = isOpen ? 'none' : 'flex';
  if (icon) {
    icon.className = isOpen ? `fa-solid fa-chevron-down toggle-icon-${fileId}` : `fa-solid fa-chevron-up toggle-icon-${fileId}`;
  }
};

// Delete Entire File Group
window.deleteAdminFile = async function(fileId, fileName) {
  if (!confirm(`'${fileName}' 문서와 여기에 포함된 모든 지식 청크를 일괄 삭제하시겠습니까?`)) return;
  try {
    const res = await authFetch(`/api/admin/file/${encodeURIComponent(fileId)}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (res.ok && data.success) {
      alert(`'${fileName}' 및 포함된 ${data.deleted_chunks}개의 지식 청크가 모두 삭제되었습니다.`);
      loadAdminFiles();
      loadAdminDocuments();
    } else {
      alert(`삭제 실패: ${data.detail || '오류 발생'}`);
    }
  } catch (err) {
    alert(`오류: ${err.message}`);
  }
};

// Load admin documents list (Flat chunk view)
async function loadAdminDocuments() {
  try {
    const res = await authFetch('/api/admin/documents');
    if (!res.ok) return;
    const data = await res.json();
    adminDocsList = data.documents || [];
    renderAdminDocTable(adminDocsList);
  } catch (err) {
    console.error('Failed to load admin docs:', err);
  }
}

function renderAdminDocTable(docs) {
  if (!adminDocTableBody) return;
  adminDocTableBody.innerHTML = '';
  if (docs.length === 0) {
    adminDocTableBody.innerHTML = '<tr><td colspan="5" class="empty-state-box">등록된 지식 청크가 없습니다.</td></tr>';
    return;
  }

  docs.forEach((d) => {
    const tr = document.createElement('tr');
    const preview = d.content ? (d.content.length > 70 ? d.content.substring(0, 70) + '...' : d.content) : '';
    
    tr.innerHTML = `
      <td><span class="doc-cat-tag">${escapeHtml(d.category || '기타')}</span></td>
      <td><strong class="doc-title-text">${escapeHtml(d.title || '')}</strong></td>
      <td class="doc-source-text">${escapeHtml(d.source || '')}</td>
      <td class="doc-preview-text">${escapeHtml(preview)}</td>
      <td>
        <button class="btn-del-doc" title="청크 삭제" onclick="deleteAdminDoc('${d.id}')">
          <i class="fa-solid fa-trash-can"></i>
        </button>
      </td>
    `;
    adminDocTableBody.appendChild(tr);
  });
}

// Delete single chunk
window.deleteAdminDoc = async function(docId) {
  if (!confirm(`해당 개별 지식 청크(ID: ${docId})를 삭제하시겠습니까?`)) return;
  try {
    const res = await authFetch(`/api/admin/document/${encodeURIComponent(docId)}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (res.ok && data.success) {
      loadAdminFiles();
      loadAdminDocuments();
    } else {
      alert(`삭제 실패: ${data.detail || '오류 발생'}`);
    }
  } catch (err) {
    alert(`오류: ${err.message}`);
  }
};

// Load Metrics Stats
async function loadMetricsStats() {
  try {
    const res = await fetch('/api/metrics/stats');
    if (!res.ok) return;
    const data = await res.json();
    
    // 1. Overall Call Stats
    if (metricTotalCalls) metricTotalCalls.textContent = `${(data.total_calls || 0).toLocaleString()}건`;
    if (metricTodayCalls) metricTodayCalls.textContent = `오늘: ${(data.today_calls || 0).toLocaleString()}건 인입`;
    if (metricRagRatio) metricRagRatio.textContent = `${data.rag_ratio_pct || 0}%`;
    if (metricRagSub) metricRagSub.textContent = `지식 참조 응답: ${(data.logger?.rag_count || 0).toLocaleString()}건`;
    if (metricTotalTokens) metricTotalTokens.textContent = `${(data.total_tokens || 0).toLocaleString()} tk`;
    if (metricDailyCost) metricDailyCost.textContent = `예상 비용: ${data.estimated_daily_cost || '$0.00'}`;
    if (metricAvgLatency) metricAvgLatency.textContent = `${data.avg_latency_sec || 0}초 (${data.avg_latency_ms || 0}ms)`;
    if (metricAvgLatencySub) metricAvgLatencySub.textContent = `실시간 스트리밍 처리 (최신 ${data.metrics?.recent_latency_ms || 0}ms)`;

    // 2. Cache Metrics
    if (data.cache) {
      if (metricHitRate) metricHitRate.textContent = `${data.cache.hit_rate_pct || 0}%`;
      if (metricHitSub) metricHitSub.textContent = `${data.cache.cache_hits || 0}건 적중 / ${data.cache.total_queries || 0}건 전체`;
      if (metricSavedTokens) metricSavedTokens.textContent = `${(data.cache.total_saved_tokens || 0).toLocaleString()} 토큰`;
      if (metricCachedCount) metricCachedCount.textContent = `보관된 캐시: ${data.cache.cached_entries || 0}건 (절감: ${data.cache.total_saved_time_sec || 0}초)`;
    }
  } catch (err) {
    console.error('Failed to load metrics:', err);
  }
}

// Load Security & Privacy Stats
async function loadSecurityStats() {
  try {
    const res = await fetch('/api/security/stats');
    if (!res.ok) return;
    const data = await res.json();
    
    if (metricTotalChecked) metricTotalChecked.textContent = `${(data.total_checked || 0).toLocaleString()}건`;
    if (metricPiiMasked) metricPiiMasked.textContent = `${(data.pii_masked_count || 0).toLocaleString()}건`;
    if (metricAbuseBlocked) metricAbuseBlocked.textContent = `${(data.inappropriate_blocked_count || 0).toLocaleString()}건`;
    if (metricRrnMasked) metricRrnMasked.textContent = `${(data.pii_type_counts?.rrn || 0).toLocaleString()}건`;
  } catch (err) {
    console.error('Failed to load security stats:', err);
  }
}

// Helper: Format log date and time accurately
function formatLogDateTime(log) {
  if (!log) return '-';
  if (log.timestamp) {
    const d = new Date(log.timestamp * 1000);
    if (!isNaN(d.getTime())) {
      const pad = (n) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    }
  }
  return log.datetime_str || '-';
}

// ==========================================
// 📋 실무 질의 이력 감사 (Query History & Audit Logs)
// ==========================================

let currentLogPage = 1;
let currentLogSearch = "";
let totalLogPages = 1;
let currentDetailLog = null;

// Query Log Elements
const tabLogsCount = document.getElementById("tabLogsCount");
const logStatTotal = document.getElementById("logStatTotal");
const logStatToday = document.getElementById("logStatToday");
const logStatRagRatio = document.getElementById("logStatRagRatio");
const logStatPiiCount = document.getElementById("logStatPiiCount");
const logSearchInput = document.getElementById("logSearchInput");
const btnRefreshLogs = document.getElementById("btnRefreshLogs");
const btnImportLogs = document.getElementById("btnImportLogs");
const logImportFileInput = document.getElementById("logImportFileInput");
const btnExportLogs = document.getElementById("btnExportLogs");
const btnClearLogs = document.getElementById("btnClearLogs");
const adminLogsTableBody = document.getElementById("adminLogsTableBody");
const btnLogPrevPage = document.getElementById("btnLogPrevPage");
const btnLogNextPage = document.getElementById("btnLogNextPage");
const logPageIndicator = document.getElementById("logPageIndicator");

// Detail Modal Elements
const logDetailModal = document.getElementById("logDetailModal");
const btnCloseLogDetailModal = document.getElementById("btnCloseLogDetailModal");
const detailLogId = document.getElementById("detailLogId");
const detailLogTime = document.getElementById("detailLogTime");
const detailLogModel = document.getElementById("detailLogModel");
const detailLogLatency = document.getElementById("detailLogLatency");
const detailLogTokens = document.getElementById("detailLogTokens");
const detailLogPii = document.getElementById("detailLogPii");
const detailLogQuery = document.getElementById("detailLogQuery");
const detailLogSourcesWrapper = document.getElementById("detailLogSourcesWrapper");
const detailLogSourcesCount = document.getElementById("detailLogSourcesCount");
const detailLogSourcesList = document.getElementById("detailLogSourcesList");
const detailLogResponse = document.getElementById("detailLogResponse");
const btnCopyDetailLog = document.getElementById("btnCopyDetailLog");

// Load Query Logs API
async function loadQueryLogs(page = 1, search = "") {
  currentLogPage = page;
  currentLogSearch = search;

  try {
    const params = new URLSearchParams({
      page: page,
      page_size: 15,
      search: search
    });

    const res = await authFetch(`/api/admin/logs?${params.toString()}`);
    if (!res.ok) return;
    const data = await res.json();

    // Update Summary Stats
    if (data.stats) {
      if (tabLogsCount) tabLogsCount.textContent = `${(data.stats.total_logs || 0).toLocaleString()}`;
      if (logStatTotal) logStatTotal.textContent = `${(data.stats.total_logs || 0).toLocaleString()}건`;
      if (logStatToday) logStatToday.textContent = `${(data.stats.today_logs || 0).toLocaleString()}건`;
      if (logStatRagRatio) logStatRagRatio.textContent = `${data.stats.rag_ratio_pct || 0}%`;
      if (logStatPiiCount) logStatPiiCount.textContent = `${(data.stats.pii_detected_count || 0).toLocaleString()}건`;
    }

    totalLogPages = data.total_pages || 1;
    if (logPageIndicator) logPageIndicator.textContent = `${data.page} / ${totalLogPages}`;
    if (btnLogPrevPage) btnLogPrevPage.disabled = (data.page <= 1);
    if (btnLogNextPage) btnLogNextPage.disabled = (data.page >= totalLogPages);

    renderQueryLogsTable(data.logs || []);
  } catch (err) {
    console.error('Failed to load query logs:', err);
  }
}

function renderQueryLogsTable(logs) {
  if (!adminLogsTableBody) return;
  adminLogsTableBody.innerHTML = '';

  if (logs.length === 0) {
    adminLogsTableBody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; color: #64748b; padding: 36px 20px;">
          <i class="fa-solid fa-inbox" style="font-size: 28px; margin-bottom: 8px; color: #475569; display: block;"></i>
          저장된 실무 질의 이력이 없습니다. 메인 화면에서 AI 상담을 진행하면 실시간으로 자동 기록됩니다.
        </td>
      </tr>
    `;
    return;
  }

  logs.forEach(log => {
    const tr = document.createElement('tr');

    // Query text preview (mask notice tag if masked)
    const piiTag = log.has_pii ? '<span class="doc-cat-tag" style="background: rgba(239, 68, 68, 0.2); color: #f87171; font-size: 10px; margin-left: 4px;">PII</span>' : '';
    const ragBadge = log.use_rag ? '<span class="doc-cat-tag" style="background: rgba(45, 212, 191, 0.15); color: #2dd4bf; font-size: 11px;">RAG</span>' : '<span class="doc-cat-tag" style="background: rgba(148, 163, 184, 0.15); color: #94a3b8; font-size: 11px;">일반</span>';
    const cachedBadge = log.cached ? '<span class="doc-cat-tag" style="background: rgba(16, 185, 129, 0.15); color: #34d399; font-size: 10px; margin-left: 3px;">캐시</span>' : '';

    const queryShort = log.user_query ? (log.user_query.length > 55 ? log.user_query.substring(0, 55) + '...' : log.user_query) : '(질의 없음)';
    const respShort = log.assistant_response ? (log.assistant_response.length > 75 ? log.assistant_response.substring(0, 75) + '...' : log.assistant_response) : '(답변 없음)';

    tr.innerHTML = `
      <td class="log-col-time"><i class="fa-regular fa-clock"></i> ${escapeHtml(formatLogDateTime(log))}</td>
      <td class="log-col-query">
        ${escapeHtml(queryShort)} ${piiTag}
      </td>
      <td class="log-col-resp">
        ${escapeHtml(respShort)}
      </td>
      <td>
        <div style="display: flex; flex-direction: column; gap: 2px;">
          <span class="log-col-model">${escapeHtml(log.model || 'llama-3.3-70b')}</span>
          <div>${ragBadge}${cachedBadge}</div>
        </div>
      </td>
      <td class="log-col-metrics">
        ${log.latency_ms || 0}ms<br><span>${(log.tokens || 0).toLocaleString()} tk</span>
      </td>
      <td>
        <button class="btn-stat-action" style="padding: 4px 10px; font-size: 11.5px; display: inline-flex; align-items: center; gap: 4px;" onclick="openLogDetailModal('${log.id}')" title="질의응답 상세 감사 보기">
          <i class="fa-solid fa-magnifying-glass"></i> 상세
        </button>
      </td>
    `;
    adminLogsTableBody.appendChild(tr);
  });
}

function escapeHtml(text) {
  if (!text) return "";
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// Open Detail Modal
window.openLogDetailModal = async function(logId) {
  try {
    const res = await authFetch(`/api/admin/logs/${encodeURIComponent(logId)}`);
    if (!res.ok) return;
    const log = await res.json();
    currentDetailLog = log;

    if (detailLogId) detailLogId.innerHTML = `<i class="fa-solid fa-hashtag"></i> ${log.id}`;
    if (detailLogTime) detailLogTime.innerHTML = `<i class="fa-regular fa-clock"></i> ${escapeHtml(formatLogDateTime(log))}`;
    if (detailLogModel) detailLogModel.innerHTML = `<i class="fa-solid fa-microchip"></i> ${log.model} ${log.cached ? '(캐시적중)' : ''}`;
    if (detailLogLatency) detailLogLatency.innerHTML = `<i class="fa-solid fa-stopwatch"></i> ${log.latency_ms} ms`;
    if (detailLogTokens) detailLogTokens.innerHTML = `<i class="fa-solid fa-coins"></i> ${log.tokens} 토큰`;
    
    if (detailLogPii) {
      if (log.has_pii) {
        detailLogPii.style.display = 'inline-flex';
        detailLogPii.innerHTML = `<i class="fa-solid fa-user-shield"></i> PII 감지: ${(log.pii_types || []).join(', ')}`;
      } else {
        detailLogPii.style.display = 'none';
      }
    }

    if (detailLogQuery) detailLogQuery.textContent = log.user_query || '';
    
    // Markdown formatted AI Response
    if (detailLogResponse) {
      if (typeof marked !== 'undefined' && marked.parse) {
        detailLogResponse.innerHTML = marked.parse(log.assistant_response || '');
      } else {
        detailLogResponse.textContent = log.assistant_response || '';
      }
    }

    // Sources
    if (detailLogSourcesWrapper && detailLogSourcesList) {
      if (log.sources && log.sources.length > 0) {
        detailLogSourcesWrapper.style.display = 'block';
        if (detailLogSourcesCount) detailLogSourcesCount.textContent = `${log.sources.length}`;
        detailLogSourcesList.innerHTML = log.sources.map((s, idx) => `
          <div class="modal-source-card">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <strong class="modal-source-title">[참조 ${idx + 1}] ${escapeHtml(s.title || '법령 문서')}</strong>
              <span class="doc-cat-tag">${escapeHtml(s.category || '실무')}</span>
            </div>
            <div class="modal-source-meta">근거: ${escapeHtml(s.source || '')}</div>
            <div class="modal-source-preview">${escapeHtml(s.preview || '')}</div>
          </div>
        `).join('');
      } else {
        detailLogSourcesWrapper.style.display = 'none';
      }
    }

    if (logDetailModal) logDetailModal.style.display = 'flex';
  } catch (err) {
    alert(`로그 조회 실패: ${err.message}`);
  }
};

function closeLogDetailModal() {
  if (logDetailModal) logDetailModal.style.display = 'none';
  currentDetailLog = null;
}

if (btnCloseLogDetailModal) {
  btnCloseLogDetailModal.addEventListener('click', closeLogDetailModal);
}

if (logDetailModal) {
  logDetailModal.addEventListener('click', (e) => {
    if (e.target === logDetailModal) closeLogDetailModal();
  });
}

// Copy detail log
if (btnCopyDetailLog) {
  btnCopyDetailLog.addEventListener('click', () => {
    if (!currentDetailLog) return;
    const textToCopy = `[질의 일시: ${currentDetailLog.datetime_str}]\n\n[질의 내용]\n${currentDetailLog.user_query}\n\n[AI 심사 답변]\n${currentDetailLog.assistant_response}`;
    navigator.clipboard.writeText(textToCopy).then(() => {
      btnCopyDetailLog.innerHTML = '<i class="fa-solid fa-check"></i> 복사 완료!';
      setTimeout(() => {
        btnCopyDetailLog.innerHTML = '<i class="fa-regular fa-copy"></i> 질의응답 복사';
      }, 2000);
    });
  });
}

// Filter & Search handler with debounce
let logSearchDebounceTimer;
if (logSearchInput) {
  logSearchInput.addEventListener('input', (e) => {
    clearTimeout(logSearchDebounceTimer);
    logSearchDebounceTimer = setTimeout(() => {
      loadQueryLogs(1, e.target.value.trim());
    }, 300);
  });
}

if (btnRefreshLogs) {
  btnRefreshLogs.addEventListener('click', () => {
    loadQueryLogs(currentLogPage, currentLogSearch);
  });
}

// Pagination Handlers
if (btnLogPrevPage) {
  btnLogPrevPage.addEventListener('click', () => {
    if (currentLogPage > 1) {
      loadQueryLogs(currentLogPage - 1, currentLogSearch);
    }
  });
}

if (btnLogNextPage) {
  btnLogNextPage.addEventListener('click', () => {
    if (currentLogPage < totalLogPages) {
      loadQueryLogs(currentLogPage + 1, currentLogSearch);
    }
  });
}

// Clear Logs handler
if (btnClearLogs) {
  btnClearLogs.addEventListener('click', async () => {
    const confirmInput = prompt('저장된 모든 실무 질의 및 감사 이력을 영구 삭제하시겠습니까?\n삭제를 진행하려면 "이력삭제"를 입력하세요:');
    if (confirmInput !== '이력삭제') {
      if (confirmInput !== null) alert('입력 내용이 일치하지 않아 삭제가 취소되었습니다.');
      return;
    }

    btnClearLogs.disabled = true;
    btnClearLogs.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 삭제 중...';
    try {
      const res = await authFetch('/api/admin/logs', { method: 'DELETE' });
      const data = await res.json();
      if (res.ok && data.success) {
        alert('모든 실무 질의 이력이 완전히 삭제되었습니다.');
        loadQueryLogs(1, '');
      } else {
        alert(`삭제 실패: ${data.detail || '오류 발생'}`);
      }
    } catch (err) {
      alert(`오류: ${err.message}`);
    } finally {
      btnClearLogs.disabled = false;
      btnClearLogs.innerHTML = '<i class="fa-solid fa-trash-can"></i> 이력 비우기';
    }
  });
}

// Export Logs handler
if (btnExportLogs) {
  btnExportLogs.addEventListener('click', async (e) => {
    e.preventDefault();
    try {
      const res = await authFetch('/api/admin/logs/export');
      if (!res.ok) throw new Error("다운로드 실패");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `family_reg_query_logs_${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(`이력 다운로드 오류: ${err.message}`);
    }
  });
}

// Import Logs handler
if (btnImportLogs && logImportFileInput) {
  btnImportLogs.addEventListener('click', () => {
    logImportFileInput.value = '';
    logImportFileInput.click();
  });

  logImportFileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    btnImportLogs.disabled = true;
    btnImportLogs.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 복원 중...';

    try {
      const res = await authFetch('/api/admin/logs/import?merge=true', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok && data.success) {
        alert(`✅ ${data.message}`);
        loadQueryLogs(1, '');
      } else {
        alert(`❌ 가져오기 실패: ${data.detail || '오류가 발생했습니다.'}`);
      }
    } catch (err) {
      alert(`오류: ${err.message}`);
    } finally {
      btnImportLogs.disabled = false;
      btnImportLogs.innerHTML = '<i class="fa-solid fa-file-import"></i> JSON 불러오기';
    }
  });
}

