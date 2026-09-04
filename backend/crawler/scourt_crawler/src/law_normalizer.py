from typing import Dict, Any, List, Optional

def clean_text(s: Any) -> str:
    if not s:
        return ""
    if isinstance(s, list):
        return "\n".join(clean_text(x) for x in s if x).strip()
    return str(s).strip()

def format_date(d: Any) -> Optional[str]:
    if not d:
        return None
    s = str(d).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s

def parse_law_service_response(law_dict: Dict[str, Any], hierarchy_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Open API 법령(target=law) 응답 객체 정규화
    """
    law_body = law_dict.get("법령", {})
    base = law_body.get("기본정보", {})
    
    # 조문 정규화
    articles_raw = law_body.get("조문", {}).get("조문단위", [])
    if isinstance(articles_raw, dict):
        articles_raw = [articles_raw]
        
    articles = []
    for art in articles_raw:
        art_no = clean_text(art.get("조문번호"))
        art_branch = clean_text(art.get("조문가지번호"))
        art_display_no = f"제{art_no}조" + (f"의{art_branch}" if art_branch and art_branch != "0" else "")
        
        # Paragraphs (항/호)
        paragraphs = []
        p_raw = art.get("항")
        if p_raw:
            if isinstance(p_raw, dict):
                p_raw = [p_raw]
            for p in p_raw:
                p_no = clean_text(p.get("항번호"))
                p_content = clean_text(p.get("항내용"))
                paragraphs.append({
                    "paragraph_no": p_no,
                    "content": p_content
                })
                
        articles.append({
            "article_no": art_display_no,
            "article_title": clean_text(art.get("조문제목")),
            "article_type": clean_text(art.get("조문여부")), # 조문 / 전문 / 편 등
            "content": clean_text(art.get("조문내용")),
            "paragraphs": paragraphs
        })

    # 부칙 정규화
    supplementary_raw = law_body.get("부칙", {}).get("부칙단위", [])
    if isinstance(supplementary_raw, dict):
        supplementary_raw = [supplementary_raw]
    supplementary = []
    for sup in supplementary_raw:
        supplementary.append({
            "promulgation_date": format_date(sup.get("부칙공포일자")),
            "promulgation_no": clean_text(sup.get("부칙공포번호")),
            "content": clean_text(sup.get("부칙내용"))
        })

    return {
        "statute_id": clean_text(base.get("법령일련번호") or base.get("법령ID")),
        "statute_name": clean_text(base.get("법령명_한글")),
        "statute_type": clean_text(base.get("법종구분")),
        "promulgation_no": clean_text(base.get("공포번호")),
        "promulgation_date": format_date(base.get("공포일자")),
        "enforcement_date": format_date(base.get("시행일자")),
        "action_type": clean_text(base.get("제개정구분")),
        "department": clean_text(base.get("소관부처")),
        "hierarchy_level": hierarchy_info.get("level") if hierarchy_info else None,
        "parent_statute": hierarchy_info.get("parent") if hierarchy_info else None,
        "revision_reason": clean_text(law_body.get("제개정이유", {}).get("제개정이유내용")),
        "revision_text": clean_text(law_body.get("개정문", {}).get("개정문내용")),
        "articles": articles,
        "supplementary": supplementary
    }

def parse_admrul_service_response(adm_dict: Dict[str, Any], meta_info: Dict[str, Any], hierarchy_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Open API 행정규칙(target=admrul) 응답 객체 정규화
    """
    adm_service = adm_dict.get("AdmRulService", {})
    rev_content = adm_service.get("개정문", {}).get("개정문내용", [])
    if isinstance(rev_content, list):
        # Flatten list of lists if needed
        flat_lines = []
        for item in rev_content:
            if isinstance(item, list):
                flat_lines.extend([clean_text(x) for x in item if x])
            elif item:
                flat_lines.append(clean_text(item))
        full_text = "\n".join(flat_lines)
    else:
        full_text = clean_text(rev_content)

    return {
        "statute_id": clean_text(meta_info.get("행정규칙일련번호") or meta_info.get("행정규칙ID")),
        "statute_name": clean_text(meta_info.get("행정규칙명")),
        "statute_type": clean_text(meta_info.get("법종구분", {}).get("content", "가족관계등록예규")),
        "promulgation_no": clean_text(meta_info.get("발령번호")),
        "promulgation_date": format_date(meta_info.get("발령일자")),
        "enforcement_date": format_date(meta_info.get("시행일자")),
        "action_type": clean_text(meta_info.get("제개정구분", {}).get("content")),
        "department": "법원행정처",
        "hierarchy_level": hierarchy_info.get("level") if hierarchy_info else 3,
        "parent_statute": hierarchy_info.get("parent") if hierarchy_info else "가족관계의 등록 등에 관한 규칙",
        "content_text": full_text
    }
