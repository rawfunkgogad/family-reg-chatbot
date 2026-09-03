import os
import re
import json
import time
import ssl
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

# Ensure output directories
DATA_DIR = Path(__file__).parent.parent / "data"
CORPUS_DIR = DATA_DIR / "corpus"
CORPUS_DIR.mkdir(parents=True, exist_ok=True)

# SSL context for government sites
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

def fetch_url(url: str, timeout: int = 15) -> Optional[str]:
    """HTTP GET 요청 헬퍼"""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as res:
            if res.status == 200:
                charset = res.headers.get_content_charset() or "utf-8"
                return res.read().decode(charset, errors="ignore")
    except Exception as e:
        print(f"[Crawler] Fetch error for {url}: {e}", flush=True)
    return None

def clean_text(text: str) -> str:
    """공백 및 특수문자 정리"""
    if not text:
        return ""
    text = re.sub(r"[\r\n\t]+", "\n", text)
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n +", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def detect_articles(text: str) -> List[str]:
    """본문에서 가족관계등록법, 민법, 규칙, 예규 등 관련 조문 정밀 검출"""
    patterns = [
        r"[「『]?가족관계의\s*등록\s*등에\s*관한\s*법률[」』]?(?:\s*제\d+조(?:의\d+)?(?:\s*제\d+항)?(?:\s*제\d+호)?)?",
        r"[「『]?가족관계의\s*등록\s*등에\s*관한\s*규칙[」』]?(?:\s*제\d+조(?:의\d+)?(?:\s*제\d+항)?(?:\s*제\d+호)?)?",
        r"[「『]?가족관계등록예규[」』]?(?:\s*제\d+호)?",
        r"[「『]?가족관계등록선례[」』]?(?:\s*제\d+[-–]\d+호)?",
        r"[「『]?민법[」』]?(?:\s*제\d+조(?:의\d+)?(?:\s*제\d+항)?(?:\s*제\d+호)?)?",
        r"[「『]?주민등록법[」』]?(?:\s*제\d+조(?:의\d+)?(?:\s*제\d+항)?)?",
        r"제\d+조(?:의\d+)?(?:\s*제\d+항)?(?:\s*제\d+호)?"
    ]
    found = set()
    for p in patterns:
        matches = re.findall(p, text)
        for m in matches:
            m_str = m.strip()
            m_clean = re.sub(r"^[「『]|[\」』]$", "", m_str).strip()
            if len(m_clean) >= 4 and any(kw in m_clean for kw in ["법", "규칙", "예규", "선례", "제"]):
                found.add(m_clean)
    return sorted(list(found))

def extract_hierarchy(articles: List[str]) -> Dict[str, Optional[str]]:
    """검출된 조문 목록으로부터 법률-규칙-예규-선례 4단계 체계 매핑"""
    h_data = {
        "primary_law": None,
        "sub_rule": None,
        "directive": None,
        "precedent": None
    }
    for a in articles:
        if "법률" in a and not h_data["primary_law"]:
            h_data["primary_law"] = a
        elif "규칙" in a and not h_data["sub_rule"]:
            h_data["sub_rule"] = a
        elif "예규" in a and not h_data["directive"]:
            h_data["directive"] = a
        elif "선례" in a and not h_data["precedent"]:
            h_data["precedent"] = a
    return h_data


# ==============================================================================
# 1. 대법원 전자가족관계등록시스템 크롤러 (efamily.scourt.go.kr)
# ==============================================================================
class EFamilyCrawler:
    BASE_URL = "https://efamily.scourt.go.kr"
    
    GUIDE_PAGES = [
        # 가족관계등록제도 개요 (0000010)
        {"bltnbordId": "0000010", "guideCd": "0000010001", "category": "가족관계등록제도 개요", "title": "가족관계등록제도 개요"},
        {"bltnbordId": "0000010", "guideCd": "0000010002", "category": "가족관계등록제도 개요", "title": "외국방식에 의한 신분행위 창설 및 보고"},
        {"bltnbordId": "0000010", "guideCd": "0000010003", "category": "가족관계등록제도 개요", "title": "가족관계등록부 직권정정 절차"},
        {"bltnbordId": "0000010", "guideCd": "0000010004", "category": "가족관계등록제도 개요", "title": "법원허가에 의한 등록부정정 신청"},
        {"bltnbordId": "0000010", "guideCd": "0000010005", "category": "가족관계등록제도 개요", "title": "성·본의 창설 및 변경 허가신청"},
        {"bltnbordId": "0000010", "guideCd": "0000010006", "category": "가족관계등록제도 개요", "title": "가족관계등록창설 허가신청"},
        {"bltnbordId": "0000010", "guideCd": "0000010007", "category": "가족관계등록제도 개요", "title": "과태료 부과 및 처분 규칙"},

        # 증명서 발급 안내 (0000007)
        {"bltnbordId": "0000007", "guideCd": "0000007001", "category": "증명서 발급안내", "title": "가족관계증명서 발급 안내"},
        {"bltnbordId": "0000007", "guideCd": "0000007002", "category": "증명서 발급안내", "title": "기본증명서 발급 안내"},
        {"bltnbordId": "0000007", "guideCd": "0000007003", "category": "증명서 발급안내", "title": "혼인관계증명서 발급 안내"},
        {"bltnbordId": "0000007", "guideCd": "0000007004", "category": "증명서 발급안내", "title": "입양관계증명서 발급 안내"},
        {"bltnbordId": "0000007", "guideCd": "0000007005", "category": "증명서 발급안내", "title": "친양자입양관계증명서 발급 안내"},
        {"bltnbordId": "0000007", "guideCd": "0000007006", "category": "증명서 발급안내", "title": "제적등본 및 초본 발급 안내"},
        {"bltnbordId": "0000007", "guideCd": "0000007007", "category": "증명서 발급안내", "title": "폐쇄등록부 증명서 발급 안내"},
        {"bltnbordId": "0000007", "guideCd": "0000007008", "category": "증명서 발급안내", "title": "영문증명서 발급 및 아포스티유 안내"},

        # 신고 안내 (0000008)
        {"bltnbordId": "0000008", "guideCd": "0000008001", "category": "출생신고", "title": "출생신고 절차 및 첨부서류"},
        {"bltnbordId": "0000008", "guideCd": "0000008002", "category": "사망신고", "title": "사망신고 절차 및 기한"},
        {"bltnbordId": "0000008", "guideCd": "0000008003", "category": "국적관련신고", "title": "국적상실 및 국적취득 통보·신고"},
        {"bltnbordId": "0000008", "guideCd": "0000008004", "category": "성본창설신고", "title": "성·본 창설신고 및 성본변경신고"},
        {"bltnbordId": "0000008", "guideCd": "0000008005", "category": "등록창설신고", "title": "가족관계등록창설 신고 절차"},
        {"bltnbordId": "0000008", "guideCd": "0000008006", "category": "개명신고", "title": "개명신고 절차 및 첨부서류"},
        {"bltnbordId": "0000008", "guideCd": "0000008007", "category": "혼인신고", "title": "혼인신고 절차 및 당사자 적격"},
        {"bltnbordId": "0000008", "guideCd": "0000008008", "category": "이혼신고", "title": "협의이혼 및 재판상이혼 신고 절차"},
        {"bltnbordId": "0000008", "guideCd": "0000008009", "category": "인지신고", "title": "인지신고 및 친생자출생신고 절차"},
        {"bltnbordId": "0000008", "guideCd": "0000008010", "category": "파양신고", "title": "협의파양 및 재판상파양 신고 절차"},
        {"bltnbordId": "0000008", "guideCd": "0000008011", "category": "입양신고", "title": "일반입양 신고 절차 및 동의요건"},
        {"bltnbordId": "0000008", "guideCd": "0000008012", "category": "친양자입양신고", "title": "친양자입양 및 친양자파양 신고 절차"},
        {"bltnbordId": "0000008", "guideCd": "0000008013", "category": "실종신고", "title": "실종선고 및 부재선고 신고 절차"},

        # 이용안내 및 전자신고 (0000009)
        {"bltnbordId": "0000009", "guideCd": "0000009001", "category": "전자등록창구안내", "title": "인터넷 신고 발급 이용안내"},
        {"bltnbordId": "0000009", "guideCd": "0000009002", "category": "인터넷신고안내", "title": "인터넷 신고 가능 사건 및 이용시간 안내"},
        {"bltnbordId": "0000009", "guideCd": "0000009003", "category": "아포스티유안내", "title": "아포스티유 및 본부영사확인 안내"},
        {"bltnbordId": "0000009", "guideCd": "0000009004", "category": "보안프로그램안내", "title": "전자증명서 발급 보안 및 확인 프로그램 안내"},
        {"bltnbordId": "0000009", "guideCd": "0000009008", "category": "전자접수안내", "title": "재외국민 가족관계등록 전자접수 서비스 안내"},
    ]

    def crawl_all(self) -> List[Dict[str, Any]]:
        print(f"\n[E-Family Crawler] Starting mining of {len(self.GUIDE_PAGES)} guide pages...", flush=True)
        all_chunks = []

        for idx, item in enumerate(self.GUIDE_PAGES, 1):
            url = f"{self.BASE_URL}/cs/CsBltnWrtGuide.do?bltnbordId={item['bltnbordId']}&guideCd={item['guideCd']}&guideYn=Y"
            print(f"[{idx}/{len(self.GUIDE_PAGES)}] Fetching: {item['title']} ({item['guideCd']})...", flush=True)
            html = fetch_url(url)
            if not html:
                continue

            chunks = self._parse_guide_page(html, item, url)
            print(f"  -> Generated {len(chunks)} semantic chunks", flush=True)
            all_chunks.extend(chunks)
            time.sleep(0.2)

        print(f"[E-Family Crawler] Successfully mined total {len(all_chunks)} chunks.", flush=True)
        return all_chunks

    def _parse_guide_page(self, html: str, meta: Dict[str, str], url: str) -> List[Dict[str, Any]]:
        chunks = []
        html_content = ""

        # 1. Look for $("#contentSpan").html(...) anywhere in script blocks
        m = re.search(r'\$\([\'"]#contentSpan[\'"]\)\.html\((.*?)\);', html, re.DOTALL)
        if m:
            raw_val = m.group(1).strip()
            if (raw_val.startswith('"') and raw_val.endswith('"')) or (raw_val.startswith("'") and raw_val.endswith("'")):
                try:
                    html_content = json.loads(raw_val)
                except Exception:
                    html_content = raw_val[1:-1].replace('\\"', '"').replace("\\'", "'").replace('\\/', '/')
            else:
                html_content = raw_val

        # 2. Fallback to direct DOM span
        if not html_content:
            soup = BeautifulSoup(html, "html.parser")
            span = soup.find(id="contentSpan") or soup.find(class_="guideWrap") or soup.find(class_="conWrap")
            if span:
                html_content = str(span)

        if not html_content:
            return chunks

        doc_soup = BeautifulSoup(html_content, "html.parser")
        page_title = meta["title"]
        h2 = doc_soup.find(["h2", "h1"])
        if h2:
            page_title = h2.get_text(strip=True) or meta["title"]

        headers = doc_soup.find_all(["h3", "h4", "div.sTitle", "strong.sTitle"])
        if headers:
            for h_idx, h in enumerate(headers, 1):
                sec_title = h.get_text(strip=True)
                sec_content = []
                curr = h.next_sibling
                while curr and (curr.name not in ["h3", "h4", "h2"]):
                    if hasattr(curr, "get_text"):
                        txt = clean_text(curr.get_text())
                        if txt:
                            sec_content.append(txt)
                    curr = curr.next_sibling

                body_text = "\n".join(sec_content)
                if len(body_text) < 15:
                    continue

                full_content = f"[{meta['category']} - {page_title}]\n주제: {sec_title}\n\n{body_text}"
                arts = detect_articles(full_content)

                chunks.append({
                    "id": f"efamily_{meta['guideCd']}_{h_idx:02d}",
                    "title": f"{page_title} - {sec_title}",
                    "category": meta["category"],
                    "source": f"대법원 전자가족관계등록시스템 민원안내 ({page_title})",
                    "section_heading": sec_title,
                    "content": full_content,
                    "detected_articles": arts,
                    "hierarchy_data": extract_hierarchy(arts),
                    "file_name": f"efamily_{meta['guideCd']}_{meta['category']}.json",
                    "metadata": {
                        "source_site": "대법원 전자가족관계등록시스템",
                        "source_url": url,
                        "guide_code": meta["guideCd"],
                        "bltnbord_id": meta["bltnbordId"]
                    }
                })

        if not chunks:
            all_text = clean_text(doc_soup.get_text())
            if len(all_text) > 30:
                arts = detect_articles(all_text)
                chunks.append({
                    "id": f"efamily_{meta['guideCd']}_01",
                    "title": page_title,
                    "category": meta["category"],
                    "source": f"대법원 전자가족관계등록시스템 민원안내 ({page_title})",
                    "section_heading": "전체 안내사항",
                    "content": f"[{meta['category']} - {page_title}]\n\n{all_text}",
                    "detected_articles": arts,
                    "hierarchy_data": extract_hierarchy(arts),
                    "file_name": f"efamily_{meta['guideCd']}_{meta['category']}.json",
                    "metadata": {
                        "source_site": "대법원 전자가족관계등록시스템",
                        "source_url": url,
                        "guide_code": meta["guideCd"],
                        "bltnbord_id": meta["bltnbordId"]
                    }
                })

        return chunks


# ==============================================================================
# 2. 법제처 찾기쉬운 생활법령정보 크롤러 (easylaw.go.kr)
# ==============================================================================
class EasyLawCrawler:
    BASE_URL = "https://www.easylaw.go.kr"
    CSM_SEQ = 707
    
    CHAPTERS = [
        {"ccfNo": 1, "cciNo": 1, "cnpClsNo": 1, "chapter": "가족관계등록제도 알아보기", "section": "가족관계등록제도 이해하기"},
        {"ccfNo": 1, "cciNo": 1, "cnpClsNo": 2, "chapter": "가족관계등록제도 알아보기", "section": "증명서 발급 및 열람"},

        {"ccfNo": 2, "cciNo": 1, "cnpClsNo": 1, "chapter": "출생 및 인지 신고", "section": "출생신고의 의의 및 절차"},
        {"ccfNo": 2, "cciNo": 2, "cnpClsNo": 1, "chapter": "출생 및 인지 신고", "section": "인지신고 절차 및 효력"},

        {"ccfNo": 3, "cciNo": 1, "cnpClsNo": 1, "chapter": "입양 및 파양 등 신고", "section": "입양신고의 요건 및 절차"},
        {"ccfNo": 3, "cciNo": 1, "cnpClsNo": 2, "chapter": "입양 및 파양 등 신고", "section": "친양자 입양신고 절차"},
        {"ccfNo": 3, "cciNo": 2, "cnpClsNo": 1, "chapter": "입양 및 파양 등 신고", "section": "파양신고 절차"},
        {"ccfNo": 3, "cciNo": 2, "cnpClsNo": 2, "chapter": "입양 및 파양 등 신고", "section": "친양자 파양신고 절차"},
        {"ccfNo": 3, "cciNo": 3, "cnpClsNo": 1, "chapter": "입양 및 파양 등 신고", "section": "입양취소 및 파양무효 신고"},

        {"ccfNo": 4, "cciNo": 1, "cnpClsNo": 1, "chapter": "혼인 및 이혼 신고", "section": "혼인신고 및 혼인취소 신고"},
        {"ccfNo": 4, "cciNo": 2, "cnpClsNo": 1, "chapter": "혼인 및 이혼 신고", "section": "협의이혼 및 재판상이혼 신고"},

        {"ccfNo": 5, "cciNo": 1, "cnpClsNo": 1, "chapter": "친권 및 미성년후견 신고", "section": "친권지정 및 친권상실 신고"},
        {"ccfNo": 5, "cciNo": 2, "cnpClsNo": 1, "chapter": "친권 및 미성년후견 신고", "section": "친권자 변경 및 대리권 사임"},
        {"ccfNo": 5, "cciNo": 3, "cnpClsNo": 1, "chapter": "친권 및 미성년후견 신고", "section": "미성년후견개시 및 종료 신고"},

        {"ccfNo": 6, "cciNo": 1, "cnpClsNo": 1, "chapter": "사망 및 실종선고 신고", "section": "사망신고 의무자 및 기한"},
        {"ccfNo": 6, "cciNo": 2, "cnpClsNo": 1, "chapter": "사망 및 실종선고 신고", "section": "실종선고 및 부재선고 신고"},

        {"ccfNo": 7, "cciNo": 1, "cnpClsNo": 1, "chapter": "개명신고 및 성·본 창설", "section": "개명신고 및 개명허가 효력"},
        {"ccfNo": 7, "cciNo": 2, "cnpClsNo": 1, "chapter": "개명신고 및 성·본 창설", "section": "성·본의 창설 및 변경신고"},

        {"ccfNo": 8, "cciNo": 1, "cnpClsNo": 1, "chapter": "등록부 창설 및 정정 등", "section": "가족관계등록부 창설신고"},
        {"ccfNo": 8, "cciNo": 2, "cnpClsNo": 1, "chapter": "등록부 창설 및 정정 등", "section": "등록부 정정신고 (법원허가/직권)"},

        {"ccfNo": 9, "cciNo": 1, "cnpClsNo": 1, "chapter": "등록부 처분에 대한 불복청구", "section": "처분에 대한 이의신청 절차"},
        {"ccfNo": 9, "cciNo": 2, "cnpClsNo": 1, "chapter": "등록부 처분에 대한 불복청구", "section": "항고 및 재항고 불복구제"},

        {"ccfNo": 10, "cciNo": 1, "cnpClsNo": 1, "chapter": "과태료 등 벌칙", "section": "신고태만 과태료 부과 및 감경"},
    ]

    def crawl_all(self) -> List[Dict[str, Any]]:
        print(f"\n[EasyLaw Crawler] Starting mining of {len(self.CHAPTERS)} chapters...", flush=True)
        all_chunks = []

        for idx, item in enumerate(self.CHAPTERS, 1):
            url = f"{self.BASE_URL}/CSP/CnpClsMain.laf?popMenu=ov&csmSeq={self.CSM_SEQ}&ccfNo={item['ccfNo']}&cciNo={item['cciNo']}&cnpClsNo={item['cnpClsNo']}"
            print(f"[{idx}/{len(self.CHAPTERS)}] Fetching: {item['chapter']} > {item['section']}...", flush=True)
            html = fetch_url(url)
            if not html:
                continue

            chunks = self._parse_easylaw_page(html, item, url)
            print(f"  -> Generated {len(chunks)} semantic chunks", flush=True)
            all_chunks.extend(chunks)
            time.sleep(0.2)

        print(f"[EasyLaw Crawler] Successfully mined total {len(all_chunks)} chunks.", flush=True)
        return all_chunks

    def _parse_easylaw_page(self, html: str, meta: Dict[str, Any], url: str) -> List[Dict[str, Any]]:
        chunks = []
        soup = BeautifulSoup(html, "html.parser")
        contents = soup.find(id="contents")
        if not contents:
            return chunks

        for remove_tag in contents.find_all(["script", "style", "div.print_box", "div.pageTitle", "div.link_box"]):
            remove_tag.decompose()

        divs = contents.find_all("div", id=re.compile(r"^div707\."))
        if divs:
            current_topic = None
            current_body = []

            def flush_topic(topic_title, body_list, seq):
                if not body_list:
                    return None
                body_text = clean_text("\n".join(body_list))
                if len(body_text) < 25:
                    return None

                heading = topic_title or f"{meta['section']} 세부 #{seq}"
                full_content = f"[{meta['chapter']} > {meta['section']}]\n주제: {heading}\n\n{body_text}"
                arts = detect_articles(full_content)

                qa_dict = None
                q_match = re.search(r"\(질문\)\s*(.*?)(?:\n|\r|\?)([\s\S]*?)(?:\(답변\)|답변:|\n\n)([\s\S]*)", body_text)
                if q_match:
                    qa_dict = {
                        "question": clean_text(q_match.group(1)),
                        "answer": clean_text(q_match.group(3))
                    }

                return {
                    "id": f"easylaw_{meta['ccfNo']}_{meta['cciNo']}_{meta['cnpClsNo']}_{seq:02d}",
                    "title": f"{meta['chapter']} - {heading}",
                    "category": meta["chapter"],
                    "source": f"법제처 찾기쉬운 생활법령정보 (가족관계 등록 > {meta['section']})",
                    "section_heading": heading,
                    "content": full_content,
                    "detected_articles": arts,
                    "hierarchy_data": extract_hierarchy(arts),
                    "qa_pair": qa_dict,
                    "file_name": f"easylaw_ch{meta['ccfNo']}_{meta['section']}.json",
                    "metadata": {
                        "source_site": "법제처 찾기쉬운 생활법령정보",
                        "source_url": url,
                        "chapter": meta["chapter"],
                        "section": meta["section"]
                    }
                }

            seq = 1
            for d in divs:
                cls_list = d.get("class", [])
                text_content = clean_text(d.get_text())
                if not text_content:
                    continue

                if "plv2a" in cls_list or "plv1a" in cls_list:
                    if current_topic and current_body:
                        chunk = flush_topic(current_topic, current_body, seq)
                        if chunk:
                            chunks.append(chunk)
                            seq += 1
                        current_body = []
                    current_topic = text_content
                else:
                    current_body.append(text_content)

            if current_topic and current_body:
                chunk = flush_topic(current_topic, current_body, seq)
                if chunk:
                    chunks.append(chunk)
        else:
            all_text = clean_text(contents.get_text())
            if len(all_text) > 40:
                arts = detect_articles(all_text)
                chunks.append({
                    "id": f"easylaw_{meta['ccfNo']}_{meta['cciNo']}_{meta['cnpClsNo']}_01",
                    "title": f"{meta['chapter']} - {meta['section']}",
                    "category": meta["chapter"],
                    "source": f"법제처 찾기쉬운 생활법령정보 (가족관계 등록 > {meta['section']})",
                    "section_heading": meta["section"],
                    "content": f"[{meta['chapter']} > {meta['section']}]\n\n{all_text}",
                    "detected_articles": arts,
                    "hierarchy_data": extract_hierarchy(arts),
                    "file_name": f"easylaw_ch{meta['ccfNo']}_{meta['section']}.json",
                    "metadata": {
                        "source_site": "법제처 찾기쉬운 생활법령정보",
                        "source_url": url,
                        "chapter": meta["chapter"],
                        "section": meta["section"]
                    }
                })

        return chunks


# ==============================================================================
# 3. 통합 TDM 파이프라인 엔진
# ==============================================================================
def run_tdm_pipeline():
    start_time = time.time()
    print("========================================================================", flush=True)
    print("  대한민국 가족관계등록 실무 TDM(텍스트·데이터 마이닝) 파이프라인 구동", flush=True)
    print("========================================================================", flush=True)

    efamily_crawler = EFamilyCrawler()
    efamily_chunks = efamily_crawler.crawl_all()

    easylaw_crawler = EasyLawCrawler()
    easylaw_chunks = easylaw_crawler.crawl_all()

    integrated_chunks = []
    integrated_chunks.extend(efamily_chunks)
    integrated_chunks.extend(easylaw_chunks)

    efamily_path = CORPUS_DIR / "efamily_scourt_guide_corpus.json"
    easylaw_path = CORPUS_DIR / "easylaw_family_reg_corpus.json"
    integrated_path = CORPUS_DIR / "integrated_family_reg_tdm_corpus.json"

    with open(efamily_path, "w", encoding="utf-8") as f:
        json.dump(efamily_chunks, f, ensure_ascii=False, indent=2)

    with open(easylaw_path, "w", encoding="utf-8") as f:
        json.dump(easylaw_chunks, f, ensure_ascii=False, indent=2)

    with open(integrated_path, "w", encoding="utf-8") as f:
        json.dump(integrated_chunks, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time

    categories = {}
    qna_count = 0
    article_count = 0
    for c in integrated_chunks:
        cat = c.get("category", "기타")
        categories[cat] = categories.get(cat, 0) + 1
        if c.get("qa_pair"):
            qna_count += 1
        if c.get("detected_articles"):
            article_count += 1

    print("\n========================================================================", flush=True)
    print("  TDM 파이프라인 수집 및 JSON 생성 완료 결과 요약", flush=True)
    print("========================================================================", flush=True)
    print(f"총 소요 시간: {elapsed:.2f}초", flush=True)
    print(f"1. 전자가족관계등록시스템 지식 청크: {len(efamily_chunks)}건 -> {efamily_path.name}", flush=True)
    print(f"2. 법제처 생활법령정보 지식 청크: {len(easylaw_chunks)}건 -> {easylaw_path.name}", flush=True)
    print(f"3. 통합 마이닝 코퍼스 총합: {len(integrated_chunks)}건 -> {integrated_path.name}", flush=True)
    print(f"- 법령 조문 태깅 완료 청크: {article_count}건", flush=True)
    print(f"- 질의응답(Q&A) 구조화 청크: {qna_count}건", flush=True)
    print("\n[카테고리별 지식 분포]:", flush=True)
    for cat, cnt in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {cat}: {cnt}건", flush=True)
    print("========================================================================\n", flush=True)

    return {
        "efamily_count": len(efamily_chunks),
        "easylaw_count": len(easylaw_chunks),
        "total_count": len(integrated_chunks),
        "integrated_path": str(integrated_path)
    }

if __name__ == "__main__":
    run_tdm_pipeline()
