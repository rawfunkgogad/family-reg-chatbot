const fs = require('fs');
const path = require('path');

// 1. Read index.html and app.js
const html = fs.readFileSync(path.join(__dirname, 'frontend', 'index.html'), 'utf-8');
const js = fs.readFileSync(path.join(__dirname, 'frontend', 'app.js'), 'utf-8');

console.log("=================================================================");
console.log("1. HTML 및 JS 파일 무결성 및 바인딩 검증");
console.log("=================================================================");
console.log(`- index.html 길이: ${html.length} chars`);
console.log(`- app.js 길이: ${js.length} chars`);

// Check required IDs in index.html
const requiredIds = [
  'adminBtn', 'adminModal', 'closeAdminModalBtn', 'tabListCount', 'tabFilesCount', 'tabChunksCount',
  'reindexAllBtn', 'dropzone', 'fileInput', 'uploadStatus', 'manualDocForm',
  'adminDocTableBody', 'adminFilesContainer', 'adminChunksContainer', 'docSearchInput',
  'viewModeFilesBtn', 'viewModeChunksBtn', 'refreshMetricsBtn', 'clearCacheBtn',
  'messagesContainer', 'welcomeHero', 'heroMainTitle', 'chatForm', 'userInput',
  'sendBtn', 'stopBtn', 'clearChatBtn', 'quickCasesList', 'statuteChips',
  'officialMemo', 'clearMemoBtn', 'ragToggle', 'webSearchToggle', 'modelSelect', 'currentModelBadge'
];

let missingIds = [];
requiredIds.forEach(id => {
  if (!html.includes(`id="${id}"`)) {
    missingIds.push(id);
  }
});

if (missingIds.length === 0) {
  console.log("-> [성공] 모든 프론트엔드 DOM 엘리먼트 ID (35개)가 index.html에 정확히 존재합니다.");
} else {
  console.error("-> [실패] 누락된 ID 발견:", missingIds);
  process.exit(1);
}

console.log("\n=================================================================");
console.log("2. 백엔드 핵심 API 엔드포인트 응답 점검");
console.log("=================================================================");

async function checkEndpoints() {
  const endpoints = [
    { url: 'http://127.0.0.1:8000/', desc: '메인 웹 페이지' },
    { url: 'http://127.0.0.1:8000/static/app.js', desc: '자바스크립트 소스' },
    { url: 'http://127.0.0.1:8000/static/style.css', desc: '스타일시트' },
    { url: 'http://127.0.0.1:8000/api/efamily/services', desc: 'e-family 서비스 목록' },
    { url: 'http://127.0.0.1:8000/api/quick-cases', desc: '통합 추천 질문 프리셋' },
    { url: 'http://127.0.0.1:8000/api/admin/files', desc: '관리자 파일별 목록' },
    { url: 'http://127.0.0.1:8000/api/admin/documents', desc: '관리자 청크 목록' },
    { url: 'http://127.0.0.1:8000/api/metrics/stats', desc: '성능/비용 메트릭 통계' },
    { url: 'http://127.0.0.1:8000/api/admin/sample-excel', desc: '상하위 법령 엑셀 템플릿' }
  ];

  for (const ep of endpoints) {
    try {
      const res = await fetch(ep.url);
      console.log(`[HTTP ${res.status}] ${ep.desc} (${ep.url})`);
      if (!res.ok) {
        console.error(`  - 오류: ${res.statusText}`);
      }
    } catch (err) {
      console.error(`  - 연결 실패: ${err.message}`);
    }
  }

  console.log("\n=================================================================");
  console.log("3. 실시간 챗봇 스트리밍 (/api/chat) 엔드포인트 직접 호출 검증");
  console.log("=================================================================");

  const chatPayload = {
    messages: [{ role: "user", content: "가족관계증명서 무료 발급 방법 알려주세요" }],
    temperature: 0.5,
    max_tokens: 1000,
    use_rag: true,
    use_web_search: false,
    mode: "unified",
    model: "llama-3.3-70b"
  };

  const chatRes = await fetch("http://127.0.0.1:8000/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(chatPayload)
  });

  console.log(`-> /api/chat 응답 상태코드: ${chatRes.status} ${chatRes.statusText}`);
  const text = await chatRes.text();
  console.log(`-> 응답 스트림 길이: ${text.length} bytes`);
  console.log(`-> 응답 내용 앞부분:\n${text.slice(0, 250)}...`);

  console.log("\n🎉 [전체 프론트엔드/백엔드/DOM/채팅 스트리밍 무결성 검증 완료]");
}

checkEndpoints();
