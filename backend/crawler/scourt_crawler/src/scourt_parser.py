import re
import html
from typing import Dict, Any, List

def clean_html_text(raw_html: str) -> str:
    """
    HTML 태그를 줄바꿈 및 순수 텍스트로 정제
    """
    if not raw_html:
        return ""
    # Block 태그를 줄바꿈으로 치환
    text = re.sub(r'<(?:br|/p|/div|/tr|/li|h\d|/h\d)[^>]*>', '\n', raw_html, flags=re.IGNORECASE)
    # 잔여 HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)
    # HTML 엔티티 변환
    text = html.unescape(text)
    # 다중 공백 및 줄바꿈 정리
    lines = [line.strip() for line in text.splitlines()]
    clean_lines = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                clean_lines.append("")
                prev_empty = True
        else:
            clean_lines.append(line)
            prev_empty = False
    return '\n'.join(clean_lines).strip()

def format_date(date_str: Any) -> str:
    """
    '20130607' -> '2013-06-07' 포맷팅
    """
    if not date_str:
        return None
    s = str(date_str).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s

def parse_context_document(xslt_html: str) -> Dict[str, Any]:
    """
    대법원 포털 xsltDocument HTML 파싱
    - history: 제·개정 연혁 목록
    - articles: 조문별 구조화 목록 (예: 제1조, 제2조...)
    - supplementary: 부칙 내용
    - content_text: 정제된 전체 텍스트
    - content_html: 원본 HTML
    """
    if not xslt_html:
        return {
            "history": [],
            "articles": [],
            "supplementary": "",
            "content_text": "",
            "content_html": ""
        }
    
    # 1. 제·개정 연혁 추출
    history = []
    hsto_match = re.search(r'<div\s+id=[\'"]rvsnHstoArea[\'"][^>]*>(.*?)</div>', xslt_html, re.DOTALL)
    if hsto_match:
        hsto_html = hsto_match.group(1)
        p_matches = re.findall(r'<p[^>]*>(.*?)</p>', hsto_html, re.DOTALL)
        for p in p_matches:
            c = clean_html_text(p)
            if c:
                history.append(c)
    
    # 2. 부칙 추출
    supplementary = ""
    bylaws_match = re.search(r'(<p[^>]*><strong>\s*부\s*칙.*?)(?:</div>|\Z)', xslt_html, re.DOTALL)
    if bylaws_match:
        supplementary = clean_html_text(bylaws_match.group(1))
    
    # 3. 조문 구조화 추출
    articles = []
    article_blocks = re.findall(
        r'<p\s+id=[\'"](제\d+조[^\'"]*)[\'"][^>]*>\s*<strong>(.*?)</strong>\s*</p>(.*?)(?=<p\s+id=[\'"]제\d+조|<p[^>]*><strong>\s*부\s*칙|\Z)',
        xslt_html,
        re.DOTALL
    )
    for art_id, art_title_html, body_html in article_blocks:
        title_clean = clean_html_text(art_title_html)
        body_clean = clean_html_text(body_html)
        
        m = re.match(r'^(제\d+조(?:\s*의\s*\d+)?)\s*(?:\(([^)]+)\))?', title_clean)
        if m:
            art_no = m.group(1)
            art_title = m.group(2) if m.group(2) else ""
        else:
            art_no = art_id
            art_title = title_clean
            
        articles.append({
            "article_no": art_no,
            "article_title": art_title,
            "content": body_clean
        })
    
    # 4. 전체 정제 텍스트
    full_text = clean_html_text(xslt_html)
    
    return {
        "history": history,
        "articles": articles,
        "supplementary": supplementary,
        "content_text": full_text,
        "content_html": xslt_html
    }
