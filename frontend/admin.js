// State
let adminToken = sessionStorage.getItem("court_admin_token") || "";
let adminFilesList = [];
let adminDocsList = [];
let currentDocViewMode = "split"; // "split" | "files" | "chunks"
let currentTab = "tab-upload"; // active tab id

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

// Floating Toast Helper
function showAdminToast(msg, type = 'success', duration = 4000) {
  let container = document.getElementById('adminToastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'adminToastContainer';
    container.className = 'admin-toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `admin-toast ${type}`;
  const icon = type === 'success' ? 'fa-circle-check' : (type === 'error' ? 'fa-circle-exclamation' : 'fa-circle-info');
  toast.innerHTML = `<i class="fa-solid ${icon}" style="font-size: 16px;"></i> <span>${escapeHtml(msg)}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 300);
  }, duration);
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
      currentTab = tabId;

      document.querySelectorAll(".tab-pane").forEach(p => {
        p.classList.remove("active");
        p.style.display = "none";
      });
      const targetPane = document.getElementById(tabId);
      if (targetPane) {
        targetPane.classList.add("active");
        // #tab-list needs flex display for split explorer to fill remaining height
        targetPane.style.display = (tabId === "tab-list") ? "flex" : "block";
      }

      if (tabId === "tab-list") {
        setDocViewMode(currentDocViewMode || 'split');
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

  // View Mode Switcher in Tab 3 (Split vs Files vs Chunks Table)
  const viewModeSplitBtn = document.getElementById("viewModeSplitBtn");
  const viewModeFilesBtn = document.getElementById("viewModeFilesBtn");
  const viewModeChunksBtn = document.getElementById("viewModeChunksBtn");

  if (viewModeSplitBtn) viewModeSplitBtn.addEventListener("click", () => setDocViewMode("split"));
  if (viewModeFilesBtn) viewModeFilesBtn.addEventListener("click", () => setDocViewMode("files"));
  if (viewModeChunksBtn) viewModeChunksBtn.addEventListener("click", () => setDocViewMode("chunks"));

  // Real-time Search Filter in Tab 3
  const docSearchInput = document.getElementById("docSearchInput");
  if (docSearchInput) {
    docSearchInput.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      if (!q) {
        renderAdminFiles(adminFilesList);
        renderAdminDocTable(adminDocsList);
        return;
      }
      // Filter files & internal chunks
      const filteredFiles = adminFilesList.filter(f => 
        (f.file_name && f.file_name.toLowerCase().includes(q)) ||
        (f.category && f.category.toLowerCase().includes(q)) ||
        (f.chunks && f.chunks.some(c => (c.title && c.title.toLowerCase().includes(q)) || (c.preview && c.preview.toLowerCase().includes(q))))
      );
      renderAdminFiles(filteredFiles);

      // Filter flat chunks table
      const filteredChunks = adminDocsList.filter(d => 
        (d.title && d.title.toLowerCase().includes(q)) ||
        (d.content && d.content.toLowerCase().includes(q)) ||
        (d.source && d.source.toLowerCase().includes(q)) ||
        (d.category && d.category.toLowerCase().includes(q))
      );
      renderAdminDocTable(filteredChunks);
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
      const catEl = document.getElementById('docCategory') || document.getElementById('manualCategory');
      const srcEl = document.getElementById('docSource') || document.getElementById('manualSource');
      const titleEl = document.getElementById('docTitle') || document.getElementById('manualTitle');
      const contentEl = document.getElementById('docContent') || document.getElementById('manualContent');
      const saveBtn = document.getElementById('btnSaveDoc') || document.getElementById('saveManualBtn');

      const category = catEl ? catEl.value : '일반실무';
      const source = srcEl ? srcEl.value.trim() : '관리자 직접등록';
      const title = titleEl ? titleEl.value.trim() : '';
      const content = contentEl ? contentEl.value.trim() : '';

      if (!title || !content) {
        alert('제목과 내용을 모두 입력해주세요.');
        return;
      }

      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> bge-m3 임베딩 중...';
      }

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
        if (saveBtn) {
          saveBtn.disabled = false;
          saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> 지식 베이스에 즉시 등록';
        }
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

  // Doc View Mode Switching (Split Master-Detail, Files Grouped, Chunks Table)
  // Global Keyboard Navigation for 2-Column Split View
  document.addEventListener('keydown', (e) => {
    if (currentTab === 'tab-list' && currentDocViewMode === 'split') {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT')) return;
      if (e.key === 'ArrowLeft' || (e.altKey && e.key === 'ArrowLeft')) {
        e.preventDefault();
        navigateSplitChunk(-1);
      } else if (e.key === 'ArrowRight' || (e.altKey && e.key === 'ArrowRight')) {
        e.preventDefault();
        navigateSplitChunk(1);
      }
    }
  });

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

  // Export Knowledge Base Package
  const btnExportCorpus = document.getElementById("btnExportCorpus");
  if (btnExportCorpus) {
    btnExportCorpus.addEventListener("click", async () => {
      btnExportCorpus.disabled = true;
      btnExportCorpus.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 백업 생성 중...';
      try {
        const res = await authFetch('/api/admin/corpus/export');
        if (!res.ok) throw new Error('백업 파일 생성에 실패했습니다.');
        
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const nowStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        const filename = `scourt_family_knowledge_backup_${nowStr}.json`;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        
        showAdminToast(`지식 코퍼스 및 임베딩 백업 파일(${filename})이 정상 다운로드되었습니다!`, 'success');
      } catch (err) {
        showAdminToast(`백업 오류: ${err.message}`, 'error');
      } finally {
        btnExportCorpus.disabled = false;
        btnExportCorpus.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> 지식 백업 (Export)';
      }
    });
  }

  // Import Knowledge Base Package
  const btnImportCorpus = document.getElementById("btnImportCorpus");
  const corpusImportFileInput = document.getElementById("corpusImportFileInput");
  if (btnImportCorpus && corpusImportFileInput) {
    btnImportCorpus.addEventListener("click", () => {
      corpusImportFileInput.click();
    });

    corpusImportFileInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      if (!file.name.toLowerCase().endsWith('.json')) {
        showAdminToast('백업 파일은 .json 형식이어야 합니다.', 'error');
        corpusImportFileInput.value = '';
        return;
      }

      if (!confirm(`'${file.name}' 백업 파일로부터 전체 지식 베이스를 복원하시겠습니까?\n(기존 데이터가 백업본으로 안전하게 교체됩니다)`)) {
        corpusImportFileInput.value = '';
        return;
      }

      btnImportCorpus.disabled = true;
      btnImportCorpus.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 지식 복원 중...';

      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await authFetch('/api/admin/corpus/import', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (res.ok && data.success) {
          showAdminToast(`총 ${data.total_docs}건의 지식 코퍼스 및 임베딩이 100% 완벽하게 복원되었습니다!`, 'success');
          await loadAdminFiles();
          await loadAdminDocuments();
        } else {
          showAdminToast(`복원 실패: ${data.detail || '오류 발생'}`, 'error');
        }
      } catch (err) {
        showAdminToast(`복원 오류: ${err.message}`, 'error');
      } finally {
        btnImportCorpus.disabled = false;
        btnImportCorpus.innerHTML = '<i class="fa-solid fa-cloud-arrow-up"></i> 지식 복원 (Import)';
        corpusImportFileInput.value = '';
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

// Drawer state tracking (per fileId)
const drawerStates = {}; // fileId -> { page: 1, pageSize: 'all', search: '', expanded: true }

function getDrawerState(fileId) {
  if (!drawerStates[fileId]) {
    drawerStates[fileId] = { page: 1, pageSize: 'all', search: '', expanded: true };
  }
  return drawerStates[fileId];
}

// =========================================================================
// 2-Column Document-to-Chunks Explorer Split View Logic (Tab 3)
// Left: Target Document Files | Right: Chunks List for Selected Document
// =========================================================================
currentDocViewMode = 'split'; // 'split' | 'files' | 'chunks'
const splitDocState = {
  selectedFileId: null,
  docSearch: '',
  chunkSearch: '',
  expandedChunks: {}, // chunkId -> boolean
  allExpanded: true
};
window.splitDocState = splitDocState;

// Mode Switching (Split, Files, Table)
function setDocViewMode(mode) {
  currentDocViewMode = mode;
  const splitBtn = document.getElementById('viewModeSplitBtn');
  const filesBtn = document.getElementById('viewModeFilesBtn');
  const chunksBtn = document.getElementById('viewModeChunksBtn');

  const splitCont = document.getElementById('splitViewContainer');
  const filesCont = document.getElementById('filesViewContainer');
  const chunksCont = document.getElementById('chunksViewContainer');

  if (splitBtn) splitBtn.classList.toggle('active', mode === 'split');
  if (filesBtn) filesBtn.classList.toggle('active', mode === 'files');
  if (chunksBtn) chunksBtn.classList.toggle('active', mode === 'chunks');

  if (splitCont) splitCont.style.display = (mode === 'split') ? 'flex' : 'none';
  if (filesCont) filesCont.style.display = (mode === 'files') ? 'block' : 'none';
  if (chunksCont) chunksCont.style.display = (mode === 'chunks') ? 'block' : 'none';

  if (mode === 'split') {
    renderSplitView();
  }
}
window.setDocViewMode = setDocViewMode;

// Render Document -> Chunks Split Explorer View
function renderSplitView() {
  const docListContainer = document.getElementById('splitDocListContainer');
  const docCountBadge = document.getElementById('splitDocCountBadge');
  const contentContainer = document.getElementById('splitDocContentContainer');

  if (!docListContainer || !contentContainer) return;

  if (adminFilesList.length === 0) {
    if (docCountBadge) docCountBadge.textContent = '총 0개 파일';
    docListContainer.innerHTML = `
      <div style="text-align: center; color: #64748b; padding: 40px 16px;">
        <i class="fa-solid fa-folder-open" style="font-size: 32px; margin-bottom: 8px; color: #475569;"></i>
        <p style="font-size: 13px;">등록된 지식 문서가 없습니다.</p>
      </div>
    `;
    renderSplitDocContent(null);
    return;
  }

  // Filter Documents by docSearch
  const docQ = (splitDocState.docSearch || '').toLowerCase().trim();
  const filteredDocs = adminFilesList.filter(f => 
    !docQ || 
    (f.file_name && f.file_name.toLowerCase().includes(docQ)) ||
    (f.category && f.category.toLowerCase().includes(docQ))
  );

  if (docCountBadge) {
    docCountBadge.textContent = `총 ${adminFilesList.length}개 파일 (표시 ${filteredDocs.length}개)`;
  }

  // Ensure an active document is selected
  const hasSelected = filteredDocs.some(f => f.file_id === splitDocState.selectedFileId);
  if (!hasSelected && filteredDocs.length > 0) {
    splitDocState.selectedFileId = filteredDocs[0].file_id;
  } else if (filteredDocs.length === 0) {
    splitDocState.selectedFileId = null;
  }

  // 1. Render Left Sidebar Documents List
  if (filteredDocs.length === 0) {
    docListContainer.innerHTML = `
      <div style="text-align: center; color: #64748b; padding: 40px 16px;">
        <i class="fa-solid fa-magnifying-glass" style="font-size: 24px; margin-bottom: 8px; color: #475569;"></i>
        <p style="font-size: 13px;">'${escapeHtml(docQ)}' 검색 결과와 일치하는 문서가 없습니다.</p>
      </div>
    `;
  } else {
    docListContainer.innerHTML = filteredDocs.map((file, idx) => {
      const isActive = file.file_id === splitDocState.selectedFileId;
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

      const count = file.chunks ? file.chunks.length : (file.chunks_count || 0);
      const kbSize = (file.total_chars / 1024).toFixed(1);

      return `
        <div class="doc-sidebar-item ${isActive ? 'active' : ''}" id="doc-card-${file.file_id}" onclick="selectSplitDocument('${file.file_id}')">
          <div class="doc-item-header">
            <div class="doc-item-icon ${iconClass}">
              <i class="fa-solid ${iconTag}"></i>
            </div>
            <div class="doc-item-name" title="${escapeHtml(file.file_name)}">
              ${escapeHtml(file.file_name)}
            </div>
          </div>
          <div class="doc-item-meta">
            <span class="doc-item-badge">${escapeHtml(file.category || '기타')}</span>
            <span class="doc-item-chunks-count"><i class="fa-solid fa-layer-group"></i> ${count}개 ${file.file_type === 'EXCEL' ? '체인' : '청크'}</span>
            <span class="doc-item-badge">약 ${kbSize} KB</span>
            ${isActive ? '<span class="doc-item-status-tag"><i class="fa-solid fa-check"></i> 열람 중 ➔</span>' : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  // 2. Render Right Content Panel for Selected Document
  renderSplitDocContent(splitDocState.selectedFileId);
}
window.renderSplitView = renderSplitView;

// Select a specific document
window.selectSplitDocument = function(fileId) {
  splitDocState.selectedFileId = fileId;
  splitDocState.chunkSearch = ''; // reset in-doc search query
  renderSplitView();
};

// Search documents in left sidebar
window.onSplitDocSearch = function(query) {
  splitDocState.docSearch = query;
  renderSplitView();
};

// Search chunks inside active document
window.onSplitChunkSearch = function(query) {
  splitDocState.chunkSearch = query;
  renderSplitDocContent(splitDocState.selectedFileId);
};

// Toggle all chunks expand/collapse inside active document
window.toggleAllSplitChunks = function(fileId) {
  splitDocState.allExpanded = !splitDocState.allExpanded;
  const file = adminFilesList.find(f => f.file_id === fileId);
  if (file && file.chunks) {
    file.chunks.forEach(c => {
      splitDocState.expandedChunks[c.id] = splitDocState.allExpanded;
    });
  }
  renderSplitDocContent(fileId);
};

// Toggle single chunk expand/collapse
window.toggleSplitChunkExpand = function(chunkId) {
  splitDocState.expandedChunks[chunkId] = !splitDocState.expandedChunks[chunkId];
  const box = document.getElementById(`split-chunk-text-${chunkId}`);
  const btn = document.getElementById(`split-chunk-btn-${chunkId}`);
  if (box && btn) {
    const isExp = splitDocState.expandedChunks[chunkId];
    box.classList.toggle('collapsed', !isExp);
    btn.innerHTML = isExp ? '<i class="fa-solid fa-chevron-up"></i> 본문 접기' : '<i class="fa-solid fa-chevron-down"></i> 본문 전체 펼치기';
  }
};

// Render Right Panel with all chunks of selected document
function renderSplitDocContent(fileId) {
  const contentContainer = document.getElementById('splitDocContentContainer');
  if (!contentContainer) return;

  if (!fileId) {
    contentContainer.innerHTML = `
      <div class="split-empty-state" style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; min-height: 500px; text-align: center; padding: 40px; color: #94a3b8;">
        <i class="fa-solid fa-folder-open" style="font-size: 52px; color: #38bdf8; opacity: 0.8; margin-bottom: 12px;"></i>
        <h4 style="color: #f1f5f9; font-size: 17px; margin-bottom: 6px;">열람할 문서를 좌측 목록에서 선택해 주세요</h4>
        <p style="font-size: 13.5px; color: #94a3b8; max-width: 360px;">좌측의 대상 문서를 클릭하시면 해당 문서에 포함된 모든 법령 조문 및 지식 청크가 이곳에 한눈에 펼쳐집니다.</p>
      </div>
    `;
    return;
  }

  const file = adminFilesList.find(f => f.file_id === fileId);
  if (!file) return;

  const chunks = file.chunks || [];
  const chunkQ = (splitDocState.chunkSearch || '').toLowerCase().trim();
  const filteredChunks = chunks.filter(c => 
    !chunkQ ||
    (c.title && c.title.toLowerCase().includes(chunkQ)) ||
    (c.content && c.content.toLowerCase().includes(chunkQ)) ||
    (c.source && c.source.toLowerCase().includes(chunkQ)) ||
    (c.category && c.category.toLowerCase().includes(chunkQ))
  );

  const kbSize = (file.total_chars / 1024).toFixed(1);
  const dateStr = file.created_at ? new Date(file.created_at * 1000).toLocaleDateString('ko-KR') : '기본 탑재';

  let chunksCardsHtml = '';
  if (filteredChunks.length === 0) {
    chunksCardsHtml = `
      <div style="text-align: center; color: #64748b; padding: 60px 20px;">
        <i class="fa-solid fa-magnifying-glass" style="font-size: 28px; margin-bottom: 10px; color: #475569;"></i>
        <p style="font-size: 14px;">'${escapeHtml(chunkQ)}' 검색 조건에 일치하는 조문 청크가 없습니다.</p>
      </div>
    `;
  } else {
    chunksCardsHtml = filteredChunks.map((chunk, idx) => {
      const fullText = chunk.content || chunk.preview || '';
      const isLong = fullText.length > 280;
      const isExp = splitDocState.expandedChunks[chunk.id] !== false; // default true/expanded
      
      let hierarchyHtml = '';
      if (chunk.hierarchy_data) {
        const hd = chunk.hierarchy_data;
        hierarchyHtml = `
          <div class="hierarchy-breadcrumb-chain" style="margin: 4px 0 8px 0;">
            ${hd.primary_law ? `<span class="hierarchy-chip tier-1"><i class="fa-solid fa-scale-balanced"></i> 법률: ${escapeHtml(hd.primary_law)}</span>` : ''}
            ${hd.sub_rule ? `<span class="hierarchy-arrow">➔</span><span class="hierarchy-chip tier-2"><i class="fa-solid fa-scroll"></i> 규칙: ${escapeHtml(hd.sub_rule)}</span>` : ''}
            ${hd.directive ? `<span class="hierarchy-arrow">➔</span><span class="hierarchy-chip tier-3"><i class="fa-solid fa-book"></i> 예규: ${escapeHtml(hd.directive)}</span>` : ''}
            ${hd.precedent ? `<span class="hierarchy-arrow">➔</span><span class="hierarchy-chip tier-4"><i class="fa-solid fa-gavel"></i> 선례: ${escapeHtml(hd.precedent)}</span>` : ''}
          </div>
        `;
      }

      return `
        <div class="split-chunk-full-card" id="split-chunk-card-${chunk.id}">
          <div class="chunk-card-top-bar">
            <div class="chunk-card-title-group">
              <span class="chunk-num-badge">#${idx + 1}</span>
              <span class="chunk-main-title">${escapeHtml(chunk.title || '(제목 없음)')}</span>
              ${chunk.page_number ? `<span class="chunk-page-tag"><i class="fa-regular fa-file-lines"></i> 제${chunk.page_number}p</span>` : ''}
              <span class="chunk-page-tag"><i class="fa-solid fa-font"></i> ${fullText.length}자</span>
            </div>
            <div class="doc-chunks-actions">
              <button class="btn-chunk-action" onclick="copyChunkText('${chunk.id}')" title="조문 본문 복사">
                <i class="fa-regular fa-copy"></i> 복사
              </button>
              <button class="btn-chunk-action" onclick="openChunkDetailModal('${chunk.id}')" title="대형 전체화면으로 크게 보기">
                <i class="fa-solid fa-expand"></i> 크게보기
              </button>
              <button class="btn-chunk-action danger" onclick="deleteAdminDoc('${chunk.id}')" title="이 조문 청크 삭제">
                <i class="fa-solid fa-trash-can"></i> 삭제
              </button>
            </div>
          </div>

          ${chunk.source ? `<div style="font-size: 13px; color: #94a3b8;"><i class="fa-solid fa-bookmark" style="color: #38bdf8;"></i> <strong>출처:</strong> ${escapeHtml(chunk.source)}</div>` : ''}
          ${hierarchyHtml}

          <div class="chunk-text-box ${isLong && !isExp ? 'collapsed' : ''}" id="split-chunk-text-${chunk.id}">
            ${escapeHtml(fullText)}
          </div>

          ${isLong ? `
            <button class="btn-toggle-expand-chunk" id="split-chunk-btn-${chunk.id}" onclick="toggleSplitChunkExpand('${chunk.id}')">
              <i class="fa-solid ${isExp ? 'fa-chevron-up' : 'fa-chevron-down'}"></i> ${isExp ? '본문 접기' : '본문 전체 펼치기'}
            </button>
          ` : ''}
        </div>
      `;
    }).join('');
  }

  contentContainer.innerHTML = `
    <!-- Top Header Bar -->
    <div class="doc-chunks-header">
      <div class="doc-chunks-header-top">
        <div class="doc-chunks-title-group">
          <div class="doc-chunks-title">
            <i class="fa-regular fa-file-lines" style="color: #38bdf8;"></i> ${escapeHtml(file.file_name)}
          </div>
          <div class="doc-chunks-pills">
            <span class="doc-item-badge" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; font-weight: 700;"><i class="fa-solid fa-tag"></i> ${escapeHtml(file.category || '기타')}</span>
            <span class="doc-item-badge"><i class="fa-solid fa-layer-group"></i> 총 ${chunks.length}개 조문 청크</span>
            <span class="doc-item-badge"><i class="fa-regular fa-hard-drive"></i> 약 ${kbSize} KB</span>
            <span class="doc-item-badge"><i class="fa-regular fa-clock"></i> ${dateStr}</span>
            <span class="doc-item-badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399;"><i class="fa-solid fa-check"></i> bge-m3 임베딩 완료</span>
          </div>
        </div>
        <div class="doc-chunks-actions">
          <button class="btn-stat-action" onclick="toggleAllSplitChunks('${file.file_id}')" title="모든 조문 본문 일괄 접기 / 펼치기">
            <i class="fa-solid fa-arrows-up-down"></i> 본문 일괄 접기/펼치기
          </button>
          <button class="btn-stat-action" style="background: rgba(239, 68, 68, 0.15); color: #f87171; border-color: rgba(239, 68, 68, 0.3);" onclick="deleteAdminFile('${file.file_id}', '${escapeHtml(file.file_name).replace(/'/g, "\\'")}')" title="이 문서의 모든 데이터 일괄 삭제">
            <i class="fa-solid fa-trash-can"></i> 파일 삭제
          </button>
        </div>
      </div>

      <!-- Filter / Search Row -->
      <div class="doc-chunks-filter-bar">
        <div class="doc-chunks-search-box">
          <i class="fa-solid fa-magnifying-glass"></i>
          <input type="text" id="splitChunkSearchInput" placeholder="이 문서 내 조문 번호 / 제목 / 본문 키워드 실시간 검색..." value="${escapeHtml(splitDocState.chunkSearch || '')}" oninput="onSplitChunkSearch(this.value)">
        </div>
        <div class="doc-chunks-stats-badge">
          표시: <strong>${filteredChunks.length}</strong> / ${chunks.length}개 조문
        </div>
      </div>
    </div>

    <!-- Scrollable Chunks Body -->
    <div class="doc-chunks-scroll-area">
      ${chunksCardsHtml}
    </div>
  `;
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
    if (statTotalChunks) statTotalChunks.textContent = `${data.total_chunks}건 (${adminFilesList.length}개 파일)`;
    if (docsTotalBadge) docsTotalBadge.textContent = `총 ${data.total_chunks}개 지식 청크 (${adminFilesList.length}개 파일)`;
    if (tabListCount) tabListCount.textContent = `${adminFilesList.length}`;
    
    renderAdminFiles(adminFilesList);
    renderSplitView();
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
            <div class="file-group-name" title="${escapeHtml(file.file_name)}">${escapeHtml(file.file_name)}</div>
            <div class="file-meta-row">
              <span class="doc-cat-tag">${escapeHtml(file.category || '기타')}</span>
              <span class="file-chunk-badge"><i class="fa-solid fa-layer-group"></i> ${file.chunks_count}개 ${file.file_type === 'EXCEL' ? '법령체인' : '청크'}</span>
              <span class="file-size-tag">약 ${kbSize} KB</span>
              <span class="file-size-tag"><i class="fa-regular fa-clock"></i> ${dateStr}</span>
            </div>
          </div>
        </div>
        <div class="file-group-right" onclick="event.stopPropagation()">
          <button class="btn-toggle-chunks" onclick="toggleFileDrawer('${file.file_id}')">
            <i class="fa-solid fa-chevron-down toggle-icon-${file.file_id}"></i>
            <span>${file.file_type === 'EXCEL' ? '법령 체계 목록' : '청크 목록 보기'}</span>
          </button>
          <button class="btn-del-file" title="이 파일의 모든 데이터 일괄 삭제" onclick="deleteAdminFile('${file.file_id}', '${escapeHtml(file.file_name).replace(/'/g, "\\'")}')">
            <i class="fa-solid fa-trash-can"></i> 파일 삭제
          </button>
        </div>
      </div>
      <div class="file-chunks-drawer" id="drawer-${file.file_id}" style="display: none;">
        <!-- Dynamically rendered by renderFileDrawerContent -->
      </div>
    `;
    adminFilesContainer.appendChild(card);
  });
}

// Track individual chunk expanded state
const chunkExpandedStates = {}; // chunkId -> boolean

// Render dynamic drawer content with foldable previews, full search, and TOC jump
function renderFileDrawerContent(fileId) {
  const drawer = document.getElementById(`drawer-${fileId}`);
  if (!drawer) return;

  const file = adminFilesList.find(f => f.file_id === fileId);
  if (!file || !file.chunks || file.chunks.length === 0) {
    drawer.innerHTML = '<div style="color: #94a3b8; font-size: 13px; padding: 20px; text-align: center;">상세 지식 청크 데이터가 없습니다.</div>';
    return;
  }

  const state = getDrawerState(fileId);
  if (state.allExpanded === undefined) {
    state.allExpanded = false; // Default to clean compact summary cards so all items can be scanned easily
  }
  const searchQ = (state.search || '').toLowerCase().trim();

  // Filter chunks within this file
  let filtered = file.chunks;
  if (searchQ) {
    filtered = file.chunks.filter(c => 
      (c.title && c.title.toLowerCase().includes(searchQ)) ||
      (c.content && c.content.toLowerCase().includes(searchQ)) ||
      (c.source && c.source.toLowerCase().includes(searchQ))
    );
  }

  const totalChunks = filtered.length;
  let currentChunks = filtered;
  let isAll = state.pageSize === 'all';
  let pageSize = isAll ? totalChunks : parseInt(state.pageSize, 10);
  let totalPages = Math.max(1, Math.ceil(totalChunks / pageSize));

  if (!isAll) {
    if (state.page > totalPages) state.page = totalPages;
    if (state.page < 1) state.page = 1;
    const startIdx = (state.page - 1) * pageSize;
    const endIdx = Math.min(startIdx + pageSize, totalChunks);
    currentChunks = filtered.slice(startIdx, endIdx);
  }

  // Generate TOC options for quick jump
  const tocOptions = filtered.map((c, i) => {
    const rawTitle = c.title || `항목 ${i + 1}`;
    const truncatedTitle = rawTitle.length > 28 ? rawTitle.substring(0, 28) + '...' : rawTitle;
    return `<option value="${c.id}">[${i + 1}] ${escapeHtml(truncatedTitle)}</option>`;
  }).join('');

  // 1. Toolbar HTML
  const paginationControls = isAll ? `
    <span class="drawer-page-info" style="color: #38bdf8; font-weight: 700;">
      총 ${totalChunks}개 항목
    </span>
  ` : `
    <div class="drawer-pagination">
      <button class="drawer-page-btn" onclick="onDrawerPageChange('${fileId}', -1)" ${state.page <= 1 ? 'disabled' : ''}>
        <i class="fa-solid fa-chevron-left"></i> 이전
      </button>
      <span class="drawer-page-info">${state.page} / ${totalPages} (총 ${totalChunks}개)</span>
      <button class="drawer-page-btn" onclick="onDrawerPageChange('${fileId}', 1)" ${state.page >= totalPages ? 'disabled' : ''}>
        다음 <i class="fa-solid fa-chevron-right"></i>
      </button>
    </div>
  `;

  const toolbarHtml = `
    <div class="drawer-toolbar">
      <div class="drawer-toolbar-left">
        <i class="fa-solid fa-magnifying-glass" style="color: #38bdf8; font-size: 13.5px;"></i>
        <input type="text" class="drawer-filter-input" placeholder="이 문서 내 조문/본문 실시간 검색..." value="${escapeHtml(state.search)}" oninput="onDrawerSearch('${fileId}', this.value)">
      </div>
      <div class="drawer-toolbar-right">
        <!-- Quick TOC Jump -->
        <select class="drawer-page-btn" onchange="jumpToChunk(this.value, '${fileId}')" style="max-width: 240px; cursor: pointer;">
          <option value="">📑 조문 목차 바로가기 (${filtered.length}개)...</option>
          ${tocOptions}
        </select>

        <!-- View Mode Selector -->
        <select class="drawer-page-btn" onchange="onDrawerPageSize('${fileId}', this.value)" style="padding: 6px 12px; cursor: pointer;">
          <option value="all" ${state.pageSize === 'all' ? 'selected' : ''}>전체 스크롤 보기 (${file.chunks.length}개)</option>
          <option value="25" ${state.pageSize === 25 ? 'selected' : ''}>25개씩 보기</option>
          <option value="10" ${state.pageSize === 10 ? 'selected' : ''}>10개씩 보기</option>
        </select>

        <!-- Toggle All Chunks Expanded / Folded -->
        <button class="drawer-page-btn" onclick="toggleAllChunksFold('${fileId}')" title="이 문서의 모든 조문 본문을 한번에 펼치거나 접습니다">
          <i class="fa-solid ${state.allExpanded ? 'fa-compress' : 'fa-expand'}"></i> ${state.allExpanded ? '모두 요약으로 접기' : '모든 본문 펼치기'}
        </button>

        ${paginationControls}
      </div>
    </div>
  `;

  // 2. Chunks List HTML
  let chunksListHtml = '';
  if (currentChunks.length === 0) {
    chunksListHtml = `<div style="color: #94a3b8; font-size: 13.5px; padding: 32px; text-align: center; background: rgba(15, 23, 42, 0.5); border-radius: 8px;">'${escapeHtml(state.search)}' 검색 결과와 일치하는 조문/청크가 없습니다.</div>`;
  } else {
    const baseOffset = isAll ? 0 : (state.page - 1) * pageSize;
    chunksListHtml = currentChunks.map((c, i) => {
      const actualIndex = baseOffset + i + 1;
      
      let hierarchyHtml = '';
      if (c.hierarchy_data) {
        const hd = c.hierarchy_data;
        hierarchyHtml = `
          <div class="hierarchy-breadcrumb-chain">
            ${hd.primary_law ? `<span class="hierarchy-chip tier-1"><i class="fa-solid fa-scale-balanced"></i> 법률: ${escapeHtml(hd.primary_law)}</span>` : ''}
            ${hd.sub_rule ? `<span class="hierarchy-arrow">➔</span><span class="hierarchy-chip tier-2"><i class="fa-solid fa-scroll"></i> 규칙: ${escapeHtml(hd.sub_rule)}</span>` : ''}
            ${hd.directive ? `<span class="hierarchy-arrow">➔</span><span class="hierarchy-chip tier-3"><i class="fa-solid fa-book"></i> 예규: ${escapeHtml(hd.directive)}</span>` : ''}
            ${hd.precedent ? `<span class="hierarchy-arrow">➔</span><span class="hierarchy-chip tier-4"><i class="fa-solid fa-gavel"></i> 선례: ${escapeHtml(hd.precedent)}</span>` : ''}
          </div>
        `;
      }

      const textToShow = c.content || c.preview || '';
      const isLongText = textToShow.length > 180;
      
      // Determine if this card is currently expanded
      let isCardExpanded = state.allExpanded;
      if (chunkExpandedStates[c.id] !== undefined) {
        isCardExpanded = chunkExpandedStates[c.id];
      }

      const textClass = (isLongText && !isCardExpanded) ? 'drawer-chunk-text collapsed' : 'drawer-chunk-text expanded';
      const foldBtnHtml = isLongText ? `
        <button class="btn-toggle-chunk-fold" onclick="toggleChunkCardText('${c.id}', '${fileId}')">
          <i class="fa-solid ${isCardExpanded ? 'fa-chevron-up' : 'fa-chevron-down'}"></i>
          <span>${isCardExpanded ? '본문 요약으로 접기' : `본문 더보기 (${textToShow.length}자 전체 펼치기)`}</span>
        </button>
      ` : '';

      return `
        <div class="drawer-chunk-item" id="chunk-card-${c.id}">
          <div class="drawer-chunk-header">
            <div class="drawer-chunk-title-group">
              <span class="drawer-chunk-num-badge">항목 ${actualIndex} / ${file.chunks.length}</span>
              <span class="drawer-chunk-title">${escapeHtml(c.title || '(제목 없음)')}</span>
            </div>
            <div class="drawer-chunk-meta-right">
              ${c.page_number ? `<span class="drawer-chunk-page"><i class="fa-regular fa-file"></i> 제${c.page_number}페이지</span>` : ''}
              <span class="drawer-chunk-page">${c.char_length || textToShow.length}자</span>
              <button class="btn-chunk-action" onclick="copyChunkText('${c.id}')" title="이 청크 본문 클립보드 복사">
                <i class="fa-regular fa-copy"></i> 복사
              </button>
              <button class="btn-chunk-action" onclick="openChunkDetailModal('${c.id}')" title="전체 화면으로 크게 보기">
                <i class="fa-solid fa-expand"></i> 크게보기
              </button>
              <button class="btn-chunk-action danger" onclick="deleteAdminDoc('${c.id}')" title="이 개별 청크 삭제">
                <i class="fa-solid fa-trash-can"></i> 삭제
              </button>
            </div>
          </div>
          ${hierarchyHtml}
          <div class="drawer-chunk-text-wrapper">
            <div class="${textClass}" id="chunk-text-${c.id}">${escapeHtml(textToShow)}</div>
            ${foldBtnHtml}
          </div>
        </div>
      `;
    }).join('');
  }

  drawer.innerHTML = `
    ${toolbarHtml}
    <div class="drawer-chunks-list">
      ${chunksListHtml}
    </div>
  `;
}

// Toggle individual chunk card text expansion
window.toggleChunkCardText = function(chunkId, fileId) {
  const current = chunkExpandedStates[chunkId];
  const state = getDrawerState(fileId);
  const isCurrentlyExpanded = (current !== undefined) ? current : state.allExpanded;
  chunkExpandedStates[chunkId] = !isCurrentlyExpanded;

  const textEl = document.getElementById(`chunk-text-${chunkId}`);
  const cardEl = document.getElementById(`chunk-card-${chunkId}`);
  if (textEl && cardEl) {
    const btn = cardEl.querySelector('.btn-toggle-chunk-fold');
    if (chunkExpandedStates[chunkId]) {
      textEl.className = 'drawer-chunk-text expanded';
      if (btn) btn.innerHTML = '<i class="fa-solid fa-chevron-up"></i> <span>본문 요약으로 접기</span>';
    } else {
      textEl.className = 'drawer-chunk-text collapsed';
      const len = textEl.textContent.length;
      if (btn) btn.innerHTML = `<i class="fa-solid fa-chevron-down"></i> <span>본문 더보기 (${len}자 전체 펼치기)</span>`;
    }
  } else {
    renderFileDrawerContent(fileId);
  }
};

// Toggle all chunks in drawer between expanded and folded
window.toggleAllChunksFold = function(fileId) {
  const state = getDrawerState(fileId);
  state.allExpanded = !state.allExpanded;
  
  // Reset individual overrides to match global state
  const file = adminFilesList.find(f => f.file_id === fileId);
  if (file && file.chunks) {
    file.chunks.forEach(c => {
      chunkExpandedStates[c.id] = state.allExpanded;
    });
  }
  
  renderFileDrawerContent(fileId);
};

// Jump directly to a chunk item from TOC
window.jumpToChunk = function(chunkId, fileId) {
  if (!chunkId) return;
  const target = document.getElementById(`chunk-card-${chunkId}`);
  if (target) {
    if (typeof target.scrollIntoView === 'function') {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    target.classList.remove('chunk-card-highlight');
    void target.offsetWidth; // Trigger reflow for restart animation
    target.classList.add('chunk-card-highlight');
  }
};

// Drawer Action Handlers
window.onDrawerSearch = function(fileId, value) {
  const state = getDrawerState(fileId);
  state.search = value;
  state.page = 1;
  renderFileDrawerContent(fileId);
};

window.onDrawerPageSize = function(fileId, size) {
  const state = getDrawerState(fileId);
  state.pageSize = size === 'all' ? 'all' : parseInt(size, 10);
  state.page = 1;
  renderFileDrawerContent(fileId);
};

window.onDrawerPageChange = function(fileId, delta) {
  const state = getDrawerState(fileId);
  state.page += delta;
  renderFileDrawerContent(fileId);
};

// Toggle drawer open/close
window.toggleFileDrawer = function(fileId) {
  const drawer = document.getElementById(`drawer-${fileId}`);
  const icon = document.querySelector(`.toggle-icon-${fileId}`);
  if (!drawer) return;

  const isCurrentlyOpen = drawer.style.display !== 'none';
  if (isCurrentlyOpen) {
    drawer.style.display = 'none';
    if (icon) icon.className = `fa-solid fa-chevron-down toggle-icon-${fileId}`;
  } else {
    drawer.style.display = 'flex';
    if (icon) icon.className = `fa-solid fa-chevron-up toggle-icon-${fileId}`;
    renderFileDrawerContent(fileId);
  }
};

// Copy Chunk Text Helper
window.copyChunkText = function(chunkId) {
  let foundChunk = null;
  for (const f of adminFilesList) {
    if (f.chunks) {
      foundChunk = f.chunks.find(c => c.id === chunkId);
      if (foundChunk) break;
    }
  }
  if (!foundChunk) {
    foundChunk = adminDocsList.find(d => d.id === chunkId);
  }

  const textToCopy = foundChunk ? (foundChunk.content || foundChunk.preview || '') : '';
  if (textToCopy) {
    navigator.clipboard.writeText(textToCopy).then(() => {
      alert('청크 본문이 클립보드에 복사되었습니다.');
    }).catch(() => {
      prompt('클립보드 복사:', textToCopy);
    });
  }
};

// Open Chunk Detail Modal
window.openChunkDetailModal = function(chunkId) {
  let foundChunk = null;
  for (const f of adminFilesList) {
    if (f.chunks) {
      foundChunk = f.chunks.find(c => c.id === chunkId);
      if (foundChunk) break;
    }
  }
  if (!foundChunk) {
    foundChunk = adminDocsList.find(d => d.id === chunkId);
  }

  if (!foundChunk) return;

  const modal = document.getElementById("chunkDetailModal");
  const modalCat = document.getElementById("modalChunkCategory");
  const modalSrc = document.getElementById("modalChunkSource");
  const modalPage = document.getElementById("modalChunkPage");
  const modalLen = document.getElementById("modalChunkLength");
  const modalTitle = document.getElementById("modalChunkTitle");
  const modalHier = document.getElementById("modalChunkHierarchy");
  const modalContent = document.getElementById("modalChunkContent");

  if (modalCat) modalCat.textContent = foundChunk.category || '일반';
  if (modalSrc) modalSrc.innerHTML = `<i class="fa-solid fa-bookmark"></i> ${escapeHtml(foundChunk.source || '')}`;
  if (modalPage) {
    modalPage.style.display = foundChunk.page_number ? 'inline-flex' : 'none';
    modalPage.innerHTML = `<i class="fa-regular fa-file-lines"></i> 제${foundChunk.page_number}페이지`;
  }
  const fullText = foundChunk.content || foundChunk.preview || '';
  if (modalLen) modalLen.innerHTML = `<i class="fa-solid fa-font"></i> ${fullText.length}자`;
  if (modalTitle) modalTitle.textContent = foundChunk.title || '(제목 없음)';
  if (modalContent) modalContent.textContent = fullText;

  if (modalHier) {
    if (foundChunk.hierarchy_data) {
      const hd = foundChunk.hierarchy_data;
      modalHier.style.display = 'block';
      modalHier.innerHTML = `
        <div class="hierarchy-breadcrumb-chain">
          ${hd.primary_law ? `<span class="hierarchy-chip tier-1"><i class="fa-solid fa-scale-balanced"></i> 법률: ${escapeHtml(hd.primary_law)}</span>` : ''}
          ${hd.sub_rule ? `<span class="hierarchy-arrow">➔</span><span class="hierarchy-chip tier-2"><i class="fa-solid fa-scroll"></i> 규칙: ${escapeHtml(hd.sub_rule)}</span>` : ''}
          ${hd.directive ? `<span class="hierarchy-arrow">➔</span><span class="hierarchy-chip tier-3"><i class="fa-solid fa-book"></i> 예규: ${escapeHtml(hd.directive)}</span>` : ''}
          ${hd.precedent ? `<span class="hierarchy-arrow">➔</span><span class="hierarchy-chip tier-4"><i class="fa-solid fa-gavel"></i> 선례: ${escapeHtml(hd.precedent)}</span>` : ''}
        </div>
      `;
    } else {
      modalHier.style.display = 'none';
    }
  }

  // Copy button in modal
  const btnCopy = document.getElementById("btnCopyChunkModal");
  if (btnCopy) {
    btnCopy.onclick = () => {
      navigator.clipboard.writeText(fullText).then(() => {
        alert('청크 본문이 클립보드에 복사되었습니다.');
      });
    };
  }

  // Close handlers
  const btnClose = document.getElementById("btnCloseChunkModal");
  const btnCloseBottom = document.getElementById("btnCloseChunkModalBtn");
  const closeModal = () => { if (modal) modal.style.display = 'none'; };
  if (btnClose) btnClose.onclick = closeModal;
  if (btnCloseBottom) btnCloseBottom.onclick = closeModal;

  if (modal) modal.style.display = 'flex';
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
      await loadAdminFiles();
      await loadAdminDocuments();
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
    renderSplitView();
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
    const preview = d.content ? (d.content.length > 85 ? d.content.substring(0, 85) + '...' : d.content) : '';
    
    tr.innerHTML = `
      <td><span class="doc-cat-tag">${escapeHtml(d.category || '기타')}</span></td>
      <td><strong class="doc-title-text" style="cursor: pointer; color: #38bdf8;" onclick="openChunkDetailModal('${d.id}')" title="클릭하여 원문 보기">${escapeHtml(d.title || '')}</strong></td>
      <td class="doc-source-text">${escapeHtml(d.source || '')}</td>
      <td class="doc-preview-text">${escapeHtml(preview)}</td>
      <td>
        <div style="display: flex; gap: 4px;">
          <button class="btn-chunk-action" title="원문 크게보기" onclick="openChunkDetailModal('${d.id}')">
            <i class="fa-solid fa-expand"></i>
          </button>
          <button class="btn-del-doc" title="청크 삭제" onclick="deleteAdminDoc('${d.id}')">
            <i class="fa-solid fa-trash-can"></i>
          </button>
        </div>
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
      await loadAdminFiles();
      await loadAdminDocuments();
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

