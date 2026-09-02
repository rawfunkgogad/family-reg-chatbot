function linkifyLawReferences(html) {
  if (!html) return "";

  function getLawCanonicalName(raw) {
    const clean = raw.replace(/[「」\s]/g, "");
    if (clean.includes("규칙")) return "가족관계의등록등에관한규칙";
    if (clean.includes("민법")) return "민법";
    if (clean.includes("주민등록")) return "주민등록법";
    if (clean.includes("국제사법")) return "국제사법";
    if (clean.includes("국적법")) return "국적법";
    if (clean.includes("비송")) return "비송사건절차법";
    return "가족관계의등록등에관한법률";
  }

  function buildArticleLink(lawName, fullText, articleNum) {
    const artAnchor = articleNum ? articleNum.replace(/\s+/g, "") : "";
    const url = artAnchor
      ? `https://www.law.go.kr/법령/${encodeURIComponent(lawName)}/${encodeURIComponent(artAnchor)}`
      : `https://www.law.go.kr/법령/${encodeURIComponent(lawName)}`;
    return `<a href="${url}" target="_blank" class="law-link-badge" title="국가법령정보센터 (${lawName} ${artAnchor}) 조문 바로가기"><i class="fa-solid fa-scale-balanced"></i> ${fullText} <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>`;
  }

  // 1. Match Law Prefix + Consecutive Article Sequence
  // Examples:
  // 「가족관계의 등록 등에 관한 법률」 제14조의2(인터넷에 의한 증명서 발급)
  // 「가족관계의 등록 등에 관한 법률」 제14조, 제14조의2 및 제15조
  // 법 제14조, 제18조 제2항
  // 규칙 제19조 내지 제22조
  const lawCompoundPattern = /(「?(가족관계의\s*등록\s*등에\s*관한\s*법률|가족관계등록법|가족관계의\s*등록\s*등에\s*관한\s*규칙|가족관계등록규칙|민법|주민등록법|국제사법|국적법|비송사건절차법)」?|(?<=(?:^|[^\w가-힣]))법|(?<=(?:^|[^\w가-힣]))규칙)\s*(제\d+조(?:의\d+)?(?:\s*\([^)\n]+\))?(?:\s*제\d+항)?(?:\s*제\d+호)?(?:\s*(?:,|및|와|과|내지|~|-)\s*제\d+조(?:의\d+)?(?:\s*\([^)\n]+\))?(?:\s*제\d+항)?(?:\s*제\d+호)?)*)/g;

  let out = html.replace(lawCompoundPattern, (match, lawPrefix, _, articlesSequence) => {
    const canonLaw = getLawCanonicalName(lawPrefix);
    
    // Replace each individual article inside articlesSequence
    const articleItemPattern = /(제\d+조(?:의\d+)?(?:\s*\([^)\n]+\))?(?:\s*제\d+항)?(?:\s*제\d+호)?)/g;
    const linkedSequence = articlesSequence.replace(articleItemPattern, (artMatch) => {
      const artNumMatch = artMatch.match(/제\d+조(?:의\d+)?/);
      const artNum = artNumMatch ? artNumMatch[0] : "";
      return buildArticleLink(canonLaw, artMatch, artNum);
    });

    const isShortForm = lawPrefix === "법" || lawPrefix === "규칙";
    const prefixDisplay = isShortForm ? `<span class="law-prefix-tag">${lawPrefix}</span>` : `<span class="law-name-tag">${lawPrefix}</span>`;
    return `${prefixDisplay} ${linkedSequence}`;
  });

  // 2. Directives (예규)
  out = out.replace(
    /(대법원\s*)?(가족관계등록예규\s*제\d+호|예규\s*제\d+호)/g,
    (match) => {
      const query = match.replace(/대법원\s*/, '').trim();
      const url = `https://www.law.go.kr/LSW/admRulSc.do?menuId=5&subMenuId=41&tabNo=0&query=${encodeURIComponent(query)}`;
      return `<a href="${url}" target="_blank" class="law-link-badge directive" title="국가법령정보센터 행정예규 검색 바로가기"><i class="fa-solid fa-book"></i> ${match} <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>`;
    }
  );

  // 3. Precedents (선례)
  out = out.replace(
    /(대법원\s*)?(등록선례\s*제?[\w\-]+호?|선례\s*제?[\w\-]+)/g,
    (match) => {
      const query = match.replace(/대법원\s*/, '').trim();
      const url = `https://www.law.go.kr/LSW/precSc.do?menuId=1&subMenuId=15&tabNo=0&query=${encodeURIComponent(query)}`;
      return `<a href="${url}" target="_blank" class="law-link-badge civil" title="국가법령정보센터 판례/선례 검색 바로가기"><i class="fa-solid fa-gavel"></i> ${match} <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 9.5px;"></i></a>`;
    }
  );

  return out;
}

// Test Suite
const testCases = [
  {
    input: "「가족관계의 등록 등에 관한 법률」 제14조의2(인터넷에 의한 증명서 발급)에 따라 온라인 발급이 가능합니다.",
    desc: "가지번호 조문 및 괄호 제목: 제14조의2(인터넷에 의한 증명서 발급)"
  },
  {
    input: "가족관계등록법 제14조, 제14조의2, 제15조 및 제18조 제2항을 검토하여야 합니다.",
    desc: "연속 다중 조항 (쉼표 및 '및'): 제14조, 제14조의2, 제15조, 제18조"
  },
  {
    input: "「가족관계의 등록 등에 관한 규칙」 제19조 내지 제22조에 규정되어 있습니다.",
    desc: "범위 조항 ('내지'): 제19조 내지 제22조"
  },
  {
    input: "법 제14조의2 제1항 및 제18조에 근거합니다.",
    desc: "약칭 '법' + 가지번호 조항"
  },
  {
    input: "민법 제844조(남편의 친생자의 추정)에 의하여 친생자로 추정됩니다.",
    desc: "민법 조문 + 괄호 제목"
  },
  {
    input: "가족관계등록예규 제543호 및 등록선례 제201503-2호에 따릅니다.",
    desc: "예규 및 선례"
  }
];

console.log("=================================================");
console.log("법령 조문 지능형 파서 검증 테스트");
console.log("=================================================");

testCases.forEach((tc, idx) => {
  console.log(`\n[테스트 ${idx + 1}] ${tc.desc}`);
  console.log(`원문: ${tc.input}`);
  const result = linkifyLawReferences(tc.input);
  console.log(`변환: ${result}`);
});
