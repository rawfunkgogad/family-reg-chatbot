const cases = [
  "「국내입양에 관한 특별법」 제21조, 「국제입양에 관한 법률」 제12조, 제22조제4항, 제23조에 따라 신고할 수 있습니다.",
  "「가족관계의 등록 등에 관한 법률」 제14조의2(인터넷에 의한 증명서 발급)에 규정되어 있습니다.",
  "「가족관계의 등록 등에 관한 규칙」 제19조 내지 제22조를 참조하십시오.",
  "법 제14조, 제15조 및 제18조에 따라 처리합니다.",
  "규칙 제60조제1항에 따른 직권정정 절차입니다.",
  "민법 제844조(남편의 친생자의 추정)에 따릅니다.",
  "가사소송법 제2조제1항제1호나목에 따른 재판입니다.",
  "입양특례법 제10조에 따라 허가를 받습니다.",
  "「가사소송규칙」 제118조를 적용합니다.",
  "비송사건절차법 제66조에 따릅니다."
];

function getLawCanonicalName(raw) {
  let clean = raw.replace(/[「」]/g, "").trim();
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
  return `<a href="${url}" class="law-link-badge">${fullText}</a>`;
}

const lawCompoundPattern = /(「([^」\n]+)」|(가족관계의\s*등록\s*등에\s*관한\s*법률|가족관계등록법|가족관계의\s*등록\s*등에\s*관한\s*규칙|가족관계등록규칙|국내입양에\s*관한\s*특별법|국내입양특별법|국제입양에\s*관한\s*법률|국제입양법|입양특례법|가사소송법|가사소송규칙|민법|주민등록법|국제사법|국적법|비송사건절차법|(?<=(?:^|[^\w가-힣]))법|(?<=(?:^|[^\w가-힣]))규칙))\s*(제\d+조(?:의\d+)?(?:\s*\([^)\n]+\))?(?:\s*제\d+항)?(?:\s*제\d+호)?(?:\s*(?:,|및|와|과|내지|~|-)\s*제\d+조(?:의\d+)?(?:\s*\([^)\n]+\))?(?:\s*제\d+항)?(?:\s*제\d+호)?)*)/g;

function linkify(html) {
  return html.replace(lawCompoundPattern, (match, quotedLaw, innerQuoted, unquotedLaw, articlesSequence) => {
    const rawLawName = innerQuoted || unquotedLaw;
    const canonLaw = getLawCanonicalName(rawLawName);

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
}

cases.forEach((c, idx) => {
  console.log(`[Case ${idx + 1}]`);
  console.log("In: ", c);
  console.log("Out:", linkify(c));
  console.log("");
});
