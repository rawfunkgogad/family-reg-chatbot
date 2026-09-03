// Global State
let conversationHistory = [];
let abortController = null;
let isStreaming = false;
let adminDocsList = [];
let currentSelectedModel = "llama-3.3-70b"; // "llama-3.3-70b" (표준·고속) or "gpt-oss-120b" (심층 추론)
let lastUserQuery = "";

// DOM Elements
const messagesContainer = document.getElementById("messagesContainer");
const welcomeHero = document.getElementById("welcomeHero");
const heroMainTitle = document.getElementById("heroMainTitle");
const heroSubtitle = document.getElementById("heroSubtitle");
const appHeaderTitle = document.getElementById("appHeaderTitle");
const categorySectionTitle = document.getElementById("categorySectionTitle");
const efamilyServicesGrid = document.getElementById("efamilyServicesGrid");

const modelSelect = document.getElementById("modelSelect");
const currentModelBadge = document.getElementById("currentModelBadge");

const chatForm = document.getElementById("chatForm");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const stopBtn = document.getElementById("stopBtn");
const clearChatBtn = document.getElementById("clearChatBtn");
const quickCasesList = document.getElementById("quickCasesList");
const statuteChips = document.getElementById("statuteChips");
const officialMemo = document.getElementById("officialMemo");
const clearMemoBtn = document.getElementById("clearMemoBtn");
const ragToggle = document.getElementById("ragToggle");
const webSearchToggle = document.getElementById("webSearchToggle");

// Security & PII Elements
const piiConfirmModal = document.getElementById("piiConfirmModal");
const btnClosePiiModal = document.getElementById("btnClosePiiModal");
const btnPiiEdit = document.getElementById("btnPiiEdit");
const btnPiiSendMasked = document.getElementById("btnPiiSendMasked");
const piiDetectedTypesText = document.getElementById("piiDetectedTypesText");
const piiSanitizedPreview = document.getElementById("piiSanitizedPreview");
const piiLiveAlertBar = document.getElementById("piiLiveAlertBar");
const piiLiveAlertText = document.getElementById("piiLiveAlertText");
const btnStripPii = document.getElementById("btnStripPii");
const inputWrapper = document.getElementById("inputWrapper");

// Initialize Markdown configuration
marked.setOptions({
  breaks: true,
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value;
    }
    return hljs.highlightAuto(code).value;
  }
});

// Theme Toggle Elements & Handlers
const themeToggleBtn = document.getElementById("themeToggleBtn");

// Initialization
document.addEventListener("DOMContentLoaded", () => {
  initThemeToggle();
  initMemo();
  loadEfamilyServices();
  loadQuickCases();
  setupEventListeners();
});

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

function initMemo() {
  const savedMemo = localStorage.getItem("family_reg_official_memo");
  if (savedMemo) {
    officialMemo.value = savedMemo;
  }
  officialMemo.addEventListener("input", () => {
    localStorage.setItem("family_reg_official_memo", officialMemo.value);
  });
  clearMemoBtn.addEventListener("click", () => {
    if (confirm("심사 실무 메모를 모두 삭제하시겠습니까?")) {
      officialMemo.value = "";
      localStorage.removeItem("family_reg_official_memo");
    }
  });
}

// Client-Side PII Pre-checker
function checkClientPii(text) {
  if (!text) return { hasPii: false, types: [], sanitizedText: "" };
  const types = [];
  let sanitized = text;

  // 1. 주민등록번호 / 외국인등록번호 (900101-1234567)
  const rrnRegex = /(?<!\d)(\d{6})[-.\s]?([1-8])(?:\d{6}|\*{6})(?!\d)/g;
  if (rrnRegex.test(text)) {
    types.push("주민등록번호/외국인등록번호");
    sanitized = sanitized.replace(rrnRegex, "$1-$2******");
  }

  // 2. 휴대전화번호 (010-1234-5678)
  const mobileRegex = /(?<!\d)(01[016789])[-.\s]?(\d{3,4})[-.\s]?(\d{4})(?!\d)/g;
  if (mobileRegex.test(text)) {
    types.push("휴대전화번호");
    sanitized = sanitized.replace(mobileRegex, "$1-****-$3");
  }

  // 3. 일반 유선전화번호 (02-1234-5678, 031-123-4567, 070-1234-5678)
  const telRegex = /(?<!\d)(02|0[3-6]\d|070|050\d?)[-.\s]?(\d{3,4})[-.\s]?(\d{4})(?!\d)/g;
  if (telRegex.test(text)) {
    if (!types.includes("전화번호") && !types.includes("휴대전화번호")) types.push("일반전화번호");
    sanitized = sanitized.replace(telRegex, "$1-****-$3");
  }

  // 4. 신용카드번호
  const cardRegex = /(?<!\d)(?:4\d{3}|5[1-5]\d{2}|6011|3[47]\d{2})[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{3,4}(?!\d)/g;
  if (cardRegex.test(text)) {
    types.push("신용카드번호");
    sanitized = sanitized.replace(cardRegex, "[신용카드번호 마스킹됨]");
  }

  return {
    hasPii: types.length > 0,
    types: [...new Set(types)],
    sanitizedText: sanitized
  };
}

// Real-time Typing Guard for PII
function updatePiiTypingGuard() {
  const val = userInput.value;
  const check = checkClientPii(val);
  
  if (check.hasPii) {
    if (piiLiveAlertBar) {
      piiLiveAlertText.innerHTML = `⚠️ <strong>개인정보(${check.types.join(", ")}) 입력 차단:</strong> 개인정보보호를 위해 전송이 차단되었습니다. 개인정보를 지우고 문의해 주세요.`;
      piiLiveAlertBar.style.display = "flex";
    }
    if (inputWrapper) {
      inputWrapper.classList.add("has-pii-alert");
    }
    if (sendBtn) {
      sendBtn.disabled = true;
      sendBtn.classList.add("btn-disabled-pii");
      sendBtn.title = "개인정보(주민번호/연락처 등)를 삭제해야 전송할 수 있습니다";
    }
  } else {
    if (piiLiveAlertBar) {
      piiLiveAlertBar.style.display = "none";
    }
    if (inputWrapper) {
      inputWrapper.classList.remove("has-pii-alert");
    }
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.classList.remove("btn-disabled-pii");
      sendBtn.title = "상담 전송";
    }
  }
}

function setupEventListeners() {
  // Model Select Change
  if (modelSelect) {
    modelSelect.addEventListener("change", (e) => {
      currentSelectedModel = e.target.value;
      if (currentModelBadge) {
        currentModelBadge.innerHTML = currentSelectedModel === "llama-3.3-70b" 
          ? '<i class="fa-solid fa-bolt"></i> llama-3.3-70b'
          : '<i class="fa-solid fa-brain"></i> gpt-oss-120b';
      }
    });
  }

  // Input auto-resize & real-time PII typing guard
  userInput.addEventListener("input", () => {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 140) + "px";
    updatePiiTypingGuard();
  });

  // Strip PII button handler
  if (btnStripPii) {
    btnStripPii.addEventListener("click", () => {
      const check = checkClientPii(userInput.value);
      userInput.value = check.sanitizedText;
      updatePiiTypingGuard();
      userInput.focus();
    });
  }

  // Enter to send (Shift+Enter for newline)
  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });

  // Chat Form Submit with Strict PII Input Blocking
  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const rawText = userInput.value.trim();
    if (!rawText || isStreaming) return;

    // Strict PII Check: block submission completely if PII exists
    const piiCheck = checkClientPii(rawText);
    if (piiCheck.hasPii) {
      updatePiiTypingGuard();
      if (inputWrapper) {
        inputWrapper.classList.remove("has-pii-alert");
        void inputWrapper.offsetWidth; // Trigger reflow for shake animation
        inputWrapper.classList.add("has-pii-alert");
      }
      alert(`❌ [개인정보 입력 원천 차단 안내]\n\n입력하신 내용에 ${piiCheck.types.join(", ")}이(가) 포함되어 있어 전송이 차단되었습니다.\n\n개인정보보호법에 따라 고유식별정보의 전송은 원천 차단됩니다. [개인정보 즉시 지우기] 버튼을 누르시거나 직접 삭제하신 후 전송해 주세요.`);
      userInput.focus();
      return;
    }

    sendMessage(rawText);
  });

  // PII Modal Close & Edit Handlers
  if (btnClosePiiModal) {
    btnClosePiiModal.addEventListener("click", () => {
      piiConfirmModal.style.display = "none";
    });
  }
  if (btnPiiEdit) {
    btnPiiEdit.addEventListener("click", () => {
      piiConfirmModal.style.display = "none";
      userInput.focus();
    });
  }

  stopBtn.addEventListener("click", () => {
    if (abortController) {
      abortController.abort();
      setStreamingState(false);
    }
  });

  clearChatBtn.addEventListener("click", () => {
    if (conversationHistory.length === 0) return;
    if (confirm("현재 대화 내용을 모두 초기화하고 새로운 상담을 시작하시겠습니까?")) {
      resetChat();
    }
  });

  // Statute chips click event
  statuteChips.addEventListener("click", (e) => {
    const btn = e.target.closest(".statute-btn");
    if (btn) {
      const statuteName = btn.dataset.statute;
      sendMessage(`'${statuteName}'에 관하여 전자가족관계등록시스템(efamily) 이용 절차와 관련 법률·규칙·예규·선례의 핵심 기준을 알기 쉽게 설명해주세요.`);
    }
  });
}

// Load e-Family Official Services
async function loadEfamilyServices() {
  try {
    const res = await fetch("/api/efamily/services");
    if (!res.ok) return;
    const services = await res.json();
    
    efamilyServicesGrid.innerHTML = "";
    services.forEach(srv => {
      const card = document.createElement("div");
      card.className = "efamily-service-card";
      card.innerHTML = `
        <div class="efamily-card-left">
          <div class="efamily-card-icon"><i class="fa-solid ${srv.icon}"></i></div>
          <div class="efamily-card-info">
            <h4>${srv.name}</h4>
            <p>${srv.desc}</p>
          </div>
        </div>
        <span class="efamily-fee-badge">${srv.fee.split('/')[0].trim()}</span>
      `;
      card.addEventListener("click", () => {
        selectQuickQuestion(srv.prompt);
      });
      efamilyServicesGrid.appendChild(card);
    });
  } catch (err) {
    console.error("Failed to load e-family services:", err);
  }
}

// Load Quick Cases (Unified)
async function loadQuickCases() {
  try {
    const res = await fetch("/api/quick-cases");
    if (!res.ok) return;
    const cases = await res.json();
    renderQuickCases(cases);
  } catch (err) {
    console.error("Failed to load cases:", err);
  }
}

function renderQuickCases(cases) {
  quickCasesList.innerHTML = "";
  cases.forEach(item => {
    const div = document.createElement("div");
    div.className = "quick-case-item";
    div.innerHTML = `
      <span class="quick-case-badge">[${item.category}]</span>
      <span class="quick-case-title">${item.title}</span>
    `;
    div.addEventListener("click", () => {
      selectQuickQuestion(item.prompt);
    });
    quickCasesList.appendChild(div);
  });
}

function selectQuickQuestion(text) {
  userInput.value = text;
  userInput.style.height = "auto";
  userInput.style.height = Math.min(userInput.scrollHeight, 140) + "px";
  sendMessage(text);
}

function resetChat() {
  if (abortController) abortController.abort();
  conversationHistory = [];
  messagesContainer.innerHTML = "";
  if (welcomeHero) {
    messagesContainer.appendChild(welcomeHero);
    welcomeHero.style.display = "block";
  }
  setStreamingState(false);
  userInput.value = "";
  userInput.style.height = "auto";
}

// Send Message Flow
async function sendMessage(text, options = {}) {
  if (!text || !text.trim()) return;
  const queryText = text.trim();
  lastUserQuery = queryText;

  if (welcomeHero && welcomeHero.parentNode) {
    welcomeHero.style.display = "none";
  }

  const bypassCache = options.bypassCache || false;

  // Append user message if not a silent regeneration
  if (!options.isSilent) {
    appendMessage("user", queryText);
    conversationHistory.push({ role: "user", content: queryText });
  }
  userInput.value = "";
  userInput.style.height = "auto";

  // Create assistant message container for streaming
  const assistantBubble = appendMessage("assistant", "");
  const bodyDiv = assistantBubble.querySelector(".message-body");
  const contentDiv = assistantBubble.querySelector(".message-content");
  
  // Add streaming cursor or live regen notice
  if (bypassCache) {
    contentDiv.innerHTML = '<div style="font-size:12.5px; color:#fbbf24; margin-bottom:8px; display:flex; align-items:center; gap:6px;"><i class="fa-solid fa-arrows-rotate fa-spin"></i> <strong>실시간 AI 재추론 중...</strong> (캐시 우회 및 새 답변 생성)</div><span class="streaming-cursor"></span>';
  } else {
    const cursorSpan = document.createElement("span");
    cursorSpan.className = "streaming-cursor";
    contentDiv.appendChild(cursorSpan);
  }

  setStreamingState(true);
  abortController = new AbortController();

  let accumulatedContent = "";
  let sourcesContainer = null;
  let responseMetrics = null;
  let isCachedResponse = false;
  let piiNoticeData = null;
  let securityBlockData = null;

  const useRag = ragToggle ? ragToggle.checked : true;
  const useWebSearch = webSearchToggle ? webSearchToggle.checked : false;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        messages: conversationHistory,
        temperature: 0.5,
        max_tokens: 2500,
        use_rag: useRag,
        use_web_search: useWebSearch,
        mode: "unified",
        model: currentSelectedModel,
        bypass_cache: bypassCache
      }),
      signal: abortController.signal
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // Keep last partial line

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("data:")) {
          const dataStr = trimmed.slice(5).trim();
          if (dataStr === "[DONE]") {
            break;
          }
          try {
            const parsed = JSON.parse(dataStr);
            
            // 1. If security block event received
            if (parsed.type === "security_block" && parsed.data) {
              securityBlockData = parsed.data;
            }
            // 2. If PII notice event received
            else if (parsed.type === "pii_notice" && parsed.data) {
              piiNoticeData = parsed.data;
            }
            // 2.5 If queue status event received (concurrency limiter waiting)
            else if (parsed.type === "queue_status" && parsed.data) {
              if (parsed.data.waiting) {
                const pos = parsed.data.position || 1;
                const estSec = parsed.data.estimated_sec || (pos * 3);
                contentDiv.innerHTML = `
                  <div class="queue-waiting-indicator">
                    <div class="queue-spinner-ring"><i class="fa-solid fa-hourglass-half fa-spin"></i></div>
                    <div class="queue-info">
                      <div class="queue-title"><i class="fa-solid fa-users-line"></i> 앞선 민원 상담 처리 중 (대기 순번: ${pos}번)</div>
                      <div class="queue-desc">동시 요청을 안전하게 순차 처리하고 있습니다. 약 <strong>${estSec}초</strong> 후 답변이 시작됩니다...</div>
                    </div>
                  </div>
                  <span class="streaming-cursor"></span>
                `;
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
              }
            }
            // 3. If cache status event received
            else if (parsed.type === "cache_status" && parsed.data) {
              if (parsed.data.is_cached) {
                isCachedResponse = true;
              }
            }
            // 4. If RAG sources metadata received
            else if (parsed.type === "sources" && parsed.data && parsed.data.length > 0) {
              sourcesContainer = renderSourcesAccordion(parsed.data);
              bodyDiv.insertBefore(sourcesContainer, contentDiv);
            }
            // 5. If content delta received
            else if (parsed.type === "delta" && parsed.data) {
              accumulatedContent += parsed.data;
              contentDiv.innerHTML = marked.parse(accumulatedContent) + '<span class="streaming-cursor"></span>';
              messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
            // 6. If performance metrics received
            else if (parsed.type === "metrics" && parsed.data) {
              responseMetrics = parsed.data;
              if (responseMetrics.cached) {
                isCachedResponse = true;
              }
            }
          } catch (e) {
            // Ignore partial json parse errors
          }
        }
      }
    }

    // Final render with law linkify
    contentDiv.innerHTML = linkifyLawReferences(marked.parse(accumulatedContent));

    // If response was from cache, attach interactive banner
    if (isCachedResponse) {
      const bannerDiv = document.createElement("div");
      bannerDiv.className = "cache-hit-banner";
      bannerDiv.innerHTML = `
        <div class="cache-hit-left">
          <i class="fa-solid fa-bolt-lightning cache-bolt-icon"></i>
          <div class="cache-hit-text">
            <span class="cache-hit-title">⚡ 검증된 고속 캐시 즉시 응답 (0.00초)</span>
            <span class="cache-hit-desc">이전에 검증된 질의응답 캐시에서 0초 만에 인출되었습니다. (비용 0원 절감)</span>
          </div>
        </div>
        <button class="btn-regen-inline" type="button">
          <i class="fa-solid fa-rotate"></i> 실시간 재추론 (새 답변)
        </button>
      `;
      const bannerBtn = bannerDiv.querySelector(".btn-regen-inline");
      if (bannerBtn) {
        bannerBtn.addEventListener("click", (e) => {
          e.preventDefault();
          regenerateAnswer(queryText);
        });
      }
      contentDiv.insertBefore(bannerDiv, contentDiv.firstChild);
    }

    // If PII was detected and masked
    if (piiNoticeData) {
      const piiBanner = document.createElement("div");
      piiBanner.className = "pii-notice-banner";
      piiBanner.innerHTML = `<i class="fa-solid fa-user-shield"></i> <span><strong>개인정보 안심 보호:</strong> ${piiNoticeData.detected_types.join(', ')} 항목이 안전하게 자동 마스킹 처리되었습니다.</span>`;
      contentDiv.insertBefore(piiBanner, contentDiv.firstChild);
    }

    // If Security Blocked
    if (securityBlockData) {
      const blockBanner = document.createElement("div");
      blockBanner.className = "security-block-banner";
      blockBanner.innerHTML = `<i class="fa-solid fa-shield-halved"></i> <span><strong>보안 필터링 적용:</strong> ${securityBlockData.reason || '부적절한 입력 차단'}</span>`;
      contentDiv.insertBefore(blockBanner, contentDiv.firstChild);
    }
    
    conversationHistory.push({ role: "assistant", content: accumulatedContent });
    addAssistantActions(assistantBubble, accumulatedContent, responseMetrics, queryText, isCachedResponse);

  } catch (err) {
    if (err.name === "AbortError") {
      contentDiv.innerHTML = linkifyLawReferences(marked.parse(accumulatedContent + "\n\n*(상담 생성이 사용자에 의해 중단되었습니다.)*"));
    } else {
      contentDiv.innerHTML = linkifyLawReferences(marked.parse(accumulatedContent + `\n\n**[오류]**: 통신 중 문제가 발생했습니다: ${err.message}`));
    }
  } finally {
    setStreamingState(false);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
}

function regenerateAnswer(targetQuery) {
  if (isStreaming) return;
  let q = targetQuery;
  if (typeof q === 'string' && q.startsWith('%')) {
    try { q = decodeURIComponent(q); } catch(e){}
  }
  if (!q) q = lastUserQuery;
  if (!q) return;

  // Clean conversation history last assistant response before regenerating
  if (conversationHistory.length > 0 && conversationHistory[conversationHistory.length - 1].role === "assistant") {
    conversationHistory.pop();
  }
  sendMessage(q, { bypassCache: true, isSilent: false });
}
window.regenerateAnswer = regenerateAnswer;

// Linkify Korean Laws & Directives with National Law Information Center (국가법령정보센터 law.go.kr)
function linkifyLawReferences(html) {
  if (!html) return "";

  function getLawCanonicalName(raw) {
    if (!raw) return "가족관계의등록등에관한법률";
    const clean = raw.replace(/[「」]/g, "").trim();
    const noSpace = clean.replace(/\s+/g, "");

    if (clean === "법" || noSpace === "가족관계등록법" || noSpace === "가족관계의등록등에관한법률") {
      return "가족관계의등록등에관한법률";
    }
    if (clean === "규칙" || noSpace === "가족관계등록규칙" || noSpace === "가족관계의등록등에관한규칙") {
      return "가족관계의등록등에관한규칙";
    }
    if (noSpace === "국내입양에관한특별법" || noSpace === "국내입양특별법") {
      return "국내입양에관한특별법";
    }
    if (noSpace === "국제입양에관한법률" || noSpace === "국제입양법") {
      return "국제입양에관한법률";
    }
    if (noSpace === "민법") return "민법";
    if (noSpace === "주민등록법") return "주민등록법";
    if (noSpace === "국제사법") return "국제사법";
    if (noSpace === "국적법") return "국적법";
    if (noSpace === "비송사건절차법") return "비송사건절차법";
    if (noSpace === "가사소송법") return "가사소송법";
    if (noSpace === "가사소송규칙") return "가사소송규칙";
    if (noSpace === "입양특례법") return "입양특례법";
    
    return noSpace;
  }

  function buildArticleLink(lawName, fullText, articleNum) {
    const artAnchor = articleNum ? articleNum.replace(/\s+/g, "") : "";
    const url = artAnchor
      ? `https://www.law.go.kr/법령/${encodeURIComponent(lawName)}/${encodeURIComponent(artAnchor)}`
      : `https://www.law.go.kr/법령/${encodeURIComponent(lawName)}`;
    return `<a href="${url}" target="_blank" class="law-link-badge" title="국가법령정보센터 (${lawName} ${artAnchor}) 조문 바로가기"><i class="fa-solid fa-scale-balanced"></i> ${fullText} <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>`;
  }

  // 1. Compound Law & Consecutive Articles
  // Matches:
  // - 「국내입양에 관한 특별법」 제21조
  // - 「국제입양에 관한 법률」 제12조, 제22조제4항, 제23조
  // - 「가족관계의 등록 등에 관한 법률」 제14조의2(인터넷에 의한 증명서 발급)
  // - 법 제14조의2 제1항 및 제18조
  // - 「가족관계의 등록 등에 관한 규칙」 제19조 내지 제22조
  // - 민법 제844조(남편의 친생자의 추정)
  const lawCompoundPattern = /(「([^」\n]+)」|(가족관계의\s*등록\s*등에\s*관한\s*법률|가족관계등록법|가족관계의\s*등록\s*등에\s*관한\s*규칙|가족관계등록규칙|국내입양에\s*관한\s*특별법|국내입양특별법|국제입양에\s*관한\s*법률|국제입양법|입양특례법|가사소송법|가사소송규칙|민법|주민등록법|국제사법|국적법|비송사건절차법|(?<=(?:^|[^\w가-힣]))법|(?<=(?:^|[^\w가-힣]))규칙))\s*(제\d+조(?:의\d+)?(?:\s*\([^)\n]+\))?(?:\s*제\d+항)?(?:\s*제\d+호)?(?:\s*(?:,|및|와|과|내지|~|-)\s*제\d+조(?:의\d+)?(?:\s*\([^)\n]+\))?(?:\s*제\d+항)?(?:\s*제\d+호)?)*)/g;

  let out = html.replace(lawCompoundPattern, (match, quotedLaw, innerQuoted, unquotedLaw, articlesSequence) => {
    const rawLawName = innerQuoted || unquotedLaw;
    const canonLaw = getLawCanonicalName(rawLawName);
    
    // Replace each individual article inside the sequence
    const articleItemPattern = /(제\d+조(?:의\d+)?(?:\s*\([^)\n]+\))?(?:\s*제\d+항)?(?:\s*제\d+호)?)/g;
    const linkedSequence = articlesSequence.replace(articleItemPattern, (artMatch) => {
      const artNumMatch = artMatch.match(/제\d+조(?:의\d+)?/);
      const artNum = artNumMatch ? artNumMatch[0] : "";
      return buildArticleLink(canonLaw, artMatch, artNum);
    });

    const isShortForm = rawLawName === "법" || rawLawName === "규칙";
    const prefixDisplay = isShortForm ? `<span class="law-prefix-tag">${rawLawName}</span>` : `<span class="law-name-tag">${quotedLaw || rawLawName}</span>`;
    return `${prefixDisplay} ${linkedSequence}`;
  });

  // 2. Directives (예규)
  out = out.replace(
    /(대법원\s*)?(가족관계등록예규\s*제\d+호|예규\s*제\d+호)/g,
    (match) => {
      const query = match.replace(/대법원\s*/, '').trim();
      return `<a href="javascript:void(0)" onclick="openLegalDocModal('${query}')" class="law-link-badge directive in-app-viewer" title="대법원 예규 원문 전문 및 스마트 링크 열람"><i class="fa-solid fa-book"></i> ${match} <i class="fa-solid fa-file-lines" style="font-size: 9.5px; margin-left: 2px;"></i></a>`;
    }
  );

  // 3. Precedents (선례)
  out = out.replace(
    /(대법원\s*)?(등록선례\s*제?[\w\-]+호?|선례\s*제?[\w\-]+)/g,
    (match) => {
      const query = match.replace(/대법원\s*/, '').trim();
      return `<a href="javascript:void(0)" onclick="openLegalDocModal('${query}')" class="law-link-badge civil in-app-viewer" title="대법원 선례 원문 전문 및 스마트 링크 열람"><i class="fa-solid fa-gavel"></i> ${match} <i class="fa-solid fa-file-lines" style="font-size: 9.5px; margin-left: 2px;"></i></a>`;
    }
  );

  return out;
}

function renderSourcesAccordion(sources) {
  const container = document.createElement("div");
  container.className = "rag-sources-container";

  const header = document.createElement("div");
  header.className = "rag-sources-header";
  header.innerHTML = `
    <div class="rag-sources-title">
      <i class="fa-solid fa-layer-group rag-sources-icon"></i>
      <span>참조된 법령 및 실무 근거 (bge-reranker 선정)</span>
      <span class="rag-sources-count">${sources.length}건</span>
    </div>
    <i class="fa-solid fa-chevron-down toggle-icon" style="font-size: 11px;"></i>
  `;

  const body = document.createElement("div");
  body.className = "rag-sources-body";
  body.style.display = "none"; // Initially collapsed

  sources.forEach((s, idx) => {
    const item = document.createElement("div");
    item.className = "rag-source-item";
    const scoreText = s.rerank_score !== undefined ? `관련도: ${s.rerank_score}` : (s.dense_similarity ? `유사도: ${s.dense_similarity}` : '');
    
    item.innerHTML = `
      <div class="rag-source-meta">
        <span class="rag-source-tag">[근거 ${idx + 1}] ${s.title || '법령 근거'}</span>
        ${scoreText ? `<span class="rag-score-badge">${scoreText}</span>` : ''}
      </div>
      <div class="rag-source-source">${linkifyLawReferences(s.source || '')}</div>
      <div class="rag-source-text">${linkifyLawReferences(s.content || '')}</div>
    `;
    body.appendChild(item);
  });

  header.addEventListener("click", () => {
    const isOpen = body.style.display !== "none";
    body.style.display = isOpen ? "none" : "flex";
    const icon = header.querySelector(".toggle-icon");
    icon.className = isOpen ? "fa-solid fa-chevron-down toggle-icon" : "fa-solid fa-chevron-up toggle-icon";
  });

  container.appendChild(header);
  container.appendChild(body);
  return container;
}

function appendMessage(role, content) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.innerHTML = role === "user" 
    ? '<i class="fa-solid fa-user"></i>' 
    : '<i class="fa-solid fa-landmark-dome"></i>';

  const body = document.createElement("div");
  body.className = "message-body";

  const contentDiv = document.createElement("div");
  contentDiv.className = "message-content";
  if (role === "user") {
    contentDiv.textContent = content;
  } else if (content) {
    contentDiv.innerHTML = linkifyLawReferences(marked.parse(content));
  }

  body.appendChild(contentDiv);
  row.appendChild(avatar);
  row.appendChild(body);

  messagesContainer.appendChild(row);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
  return row;
}

function addAssistantActions(messageRow, textContent, metrics, userQuery, isCached) {
  const body = messageRow.querySelector(".message-body");
  
  // 1. Performance Metrics Badge
  if (metrics) {
    const metricsDiv = document.createElement("div");
    metricsDiv.className = "msg-metrics-badge";
    metricsDiv.innerHTML = `
      <span class="metric-pill latency"><i class="fa-solid fa-stopwatch"></i> ${metrics.latency_ms}ms</span>
      <span class="metric-pill tokens"><i class="fa-solid fa-coins"></i> ${metrics.total_tokens} tokens</span>
      <span class="metric-pill model"><i class="fa-solid fa-microchip"></i> ${metrics.model}</span>
      ${metrics.cached ? '<span class="metric-pill cached"><i class="fa-solid fa-bolt"></i> 캐시 적중 (0원)</span>' : ''}
    `;
    body.appendChild(metricsDiv);
  }

  // 2. Action Buttons
  const actionsDiv = document.createElement("div");
  actionsDiv.className = "message-actions";

  // Copy button
  const copyBtn = document.createElement("button");
  copyBtn.className = "msg-action-btn";
  copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> 상담 내용 복사';
  copyBtn.addEventListener("click", () => {
    navigator.clipboard.writeText(textContent).then(() => {
      copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> 복사 완료';
      setTimeout(() => {
        copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> 상담 내용 복사';
      }, 2000);
    });
  });

  // efamily Direct link button
  const portalBtn = document.createElement("a");
  portalBtn.className = "msg-action-btn";
  portalBtn.href = "https://efamily.scourt.go.kr/index.jsp";
  portalBtn.target = "_blank";
  portalBtn.style.textDecoration = "none";
  portalBtn.innerHTML = '<i class="fa-solid fa-arrow-up-right-from-square"></i> 전자가족관계등록시스템 바로가기';

  // Send to memo button
  const memoBtn = document.createElement("button");
  memoBtn.className = "msg-action-btn";
  memoBtn.innerHTML = '<i class="fa-solid fa-note-sticky"></i> 메모장에 추가';
  memoBtn.addEventListener("click", () => {
    const timestamp = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
    officialMemo.value += `\n[${timestamp} 상담 요약]\n` + textContent.substring(0, 150) + "...\n";
    localStorage.setItem("family_reg_official_memo", officialMemo.value);
    memoBtn.innerHTML = '<i class="fa-solid fa-check"></i> 추가됨';
    setTimeout(() => {
      memoBtn.innerHTML = '<i class="fa-solid fa-note-sticky"></i> 메모장에 추가';
    }, 2000);
  });

  // Regenerate button (Bypass cache & live generation)
  const regenBtn = document.createElement("button");
  regenBtn.className = "msg-action-btn btn-regen-live";
  regenBtn.innerHTML = '<i class="fa-solid fa-rotate"></i> 실시간 재추론 (새 답변)';
  regenBtn.title = "캐시를 우회하여 최신 실시간 AI로 새로운 답변을 생성합니다";
  regenBtn.addEventListener("click", () => {
    const targetQ = userQuery || lastUserQuery;
    regenerateAnswer(targetQ);
  });

  actionsDiv.appendChild(copyBtn);
  actionsDiv.appendChild(regenBtn);
  actionsDiv.appendChild(portalBtn);
  actionsDiv.appendChild(memoBtn);
  body.appendChild(actionsDiv);
}

function setStreamingState(streaming) {
  isStreaming = streaming;
  if (streaming) {
    sendBtn.style.display = "none";
    stopBtn.style.display = "flex";
  } else {
    sendBtn.style.display = "flex";
    stopBtn.style.display = "none";
  }
}

// =============================================================================
// Supreme Court Directives & Precedents In-App Viewer Modal Logic
// =============================================================================
async function openLegalDocModal(targetQuery) {
  const modal = document.getElementById("legalDocModal");
  if (!modal) return;

  const titleEl = document.getElementById("legalDocTitle");
  const categoryEl = document.getElementById("legalDocCategory");
  const sourceEl = document.getElementById("legalDocSource");
  const idEl = document.getElementById("legalDocId");
  const contentEl = document.getElementById("legalDocContent");
  const scourtLinkEl = document.getElementById("linkScourtPortal");
  const lawLinkEl = document.getElementById("linkLawGoKr");
  const iconEl = document.getElementById("legalDocIcon");

  // Initial loading state
  modal.style.display = "flex";
  titleEl.textContent = `${targetQuery} 원문 로딩 중...`;
  contentEl.textContent = "대법원 사법정보 코퍼스에서 원문을 조회하고 있습니다...";
  
  const isPrecedent = targetQuery.includes("선례");
  categoryEl.textContent = isPrecedent ? "대법원 가족관계등록선례" : "대법원 가족관계등록예규";
  categoryEl.className = isPrecedent ? "legal-doc-badge precedent" : "legal-doc-badge";
  iconEl.className = isPrecedent ? "fa-solid fa-gavel" : "fa-solid fa-scale-balanced";

  try {
    const res = await fetch(`/api/legal/document?query=${encodeURIComponent(targetQuery)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (data.found) {
      titleEl.textContent = data.title || targetQuery;
      categoryEl.textContent = data.category || (isPrecedent ? "대법원 가족관계등록선례" : "대법원 가족관계등록예규");
      categoryEl.className = data.category.includes("선례") ? "legal-doc-badge precedent" : "legal-doc-badge";
      iconEl.className = data.category.includes("선례") ? "fa-solid fa-gavel" : "fa-solid fa-scale-balanced";
      sourceEl.textContent = `출처: ${data.source || '대한민국 법원'}`;
      idEl.textContent = data.id || '';
      contentEl.textContent = data.content || '등록된 본문 내용이 없습니다.';

      // Smart Links
      if (data.law_go_kr_url) {
        lawLinkEl.href = data.law_go_kr_url;
        lawLinkEl.style.display = "inline-flex";
        lawLinkEl.title = `국가법령정보센터 (${data.search_keyword || '본문'}) 검색 바로가기`;
      } else {
        lawLinkEl.style.display = "none";
      }

      if (data.scourt_url) {
        scourtLinkEl.href = data.scourt_url;
        scourtLinkEl.style.display = "inline-flex";
      } else {
        scourtLinkEl.style.display = "none";
      }
    } else {
      titleEl.textContent = targetQuery;
      contentEl.textContent = data.message || "해당 예규 또는 선례 원문을 찾을 수 없습니다.";
      lawLinkEl.href = `https://www.law.go.kr/LSW/admRulSc.do?menuId=5&subMenuId=41&tabNo=2&query=${encodeURIComponent(targetQuery)}`;
      lawLinkEl.style.display = "inline-flex";
      scourtLinkEl.href = "https://portal.scourt.go.kr/pgp/index.on?m=PGP1051M01&l=N&c=900";
      scourtLinkEl.style.display = "inline-flex";
    }
  } catch (err) {
    titleEl.textContent = targetQuery;
    contentEl.textContent = `원문 조회 중 오류가 발생했습니다: ${err.message}`;
  }
}
window.openLegalDocModal = openLegalDocModal;

// Modal Close & Copy Listeners
document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("legalDocModal");
  const btnClose = document.getElementById("btnCloseLegalDocModal");
  const btnCloseBottom = document.getElementById("btnCloseLegalDocBottom");
  const btnCopy = document.getElementById("btnCopyLegalDocText");
  const contentEl = document.getElementById("legalDocContent");

  if (btnClose) btnClose.addEventListener("click", () => { if (modal) modal.style.display = "none"; });
  if (btnCloseBottom) btnCloseBottom.addEventListener("click", () => { if (modal) modal.style.display = "none"; });
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.style.display = "none";
    });
  }

  if (btnCopy) {
    btnCopy.addEventListener("click", async () => {
      if (!contentEl) return;
      try {
        await navigator.clipboard.writeText(contentEl.textContent);
        const originalHtml = btnCopy.innerHTML;
        btnCopy.innerHTML = '<i class="fa-solid fa-check"></i> <span>복사 완료!</span>';
        btnCopy.style.borderColor = "#22c55e";
        btnCopy.style.color = "#22c55e";
        setTimeout(() => {
          btnCopy.innerHTML = originalHtml;
          btnCopy.style.borderColor = "";
          btnCopy.style.color = "";
        }, 2000);
      } catch (err) {
        alert("클립보드 복사에 실패했습니다.");
      }
    });
  }
});

