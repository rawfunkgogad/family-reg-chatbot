import io
import json
import time
import uuid
import re
from typing import List, Dict, Any
from pypdf import PdfReader
from rag.excel_hierarchy_parser import parse_excel_hierarchy

def parse_excel(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """엑셀 파일(.xlsx, .xls) 상하위 법령 위계 관계 파싱"""
    return parse_excel_hierarchy(file_bytes, filename)

def clean_pdf_text(raw_text: str) -> str:
    """PDF 추출 텍스트의 줄바꿈·하이픈 절단 및 노이즈를 의미 단위로 복원 및 정제"""
    if not raw_text:
        return ""
    
    text = raw_text

    # 1. 머리글/바닥글 및 쪽번호 패턴 제거 (예: "- 12 -", "Page 3 of 10", "법원행정처")
    text = re.sub(r'^[-\u2013\u2014\s]*\d+[-\u2013\u2014\s]*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*(?:Page\s*\d+|\d+\s*/\s*\d+|법원행정처|대법원\s*법원행정처|가족관계등록실무)\s*$', '', text, flags=re.MULTILINE)

    # 2. 영문/한글 단어 중간 하이픈 줄바꿈 복원 ("신-\n고" -> "신고", "regis-\ntration" -> "registration")
    text = re.sub(r'([가-힣a-zA-Z])-\s*\n\s*([가-힣a-zA-Z])', r'\1\2', text)

    # 3. 한글 문장 내 부자연스러운 강제 줄바꿈 접합
    #    (줄 끝이 마침표, 콜론, 따옴표가 아니고 다음 줄이 조문/번호/불릿으로 시작하지 않는 경우 공백 하나로 치환)
    bullet_pattern = r'(?:제\s*\d+조|제\s*\d+장|제\s*\d+절|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]|\d+[.)]|[가-하][.)]|[-*•■▶※\u25b6\u25cf]|【|\b[A-Z]\.)'
    
    lines = text.split('\n')
    merged_lines = []
    
    for i, line in enumerate(lines):
        line_str = line.strip()
        if not line_str:
            if merged_lines and merged_lines[-1] != "":
                merged_lines.append("")
            continue
            
        if not merged_lines or merged_lines[-1] == "":
            merged_lines.append(line_str)
        else:
            prev = merged_lines[-1]
            # 이전 줄이 마침표(.!?), 콜론(:), 닫는 괄호/따옴표로 끝나지 않고, 현재 줄이 새 조문이나 불릿으로 시작하지 않는 경우 연결
            is_prev_ended = bool(re.search(r'[.!?:"\'”」』]\s*$', prev))
            is_curr_bullet = bool(re.match(f'^{bullet_pattern}', line_str))
            
            if not is_prev_ended and not is_curr_bullet and len(prev) > 0:
                merged_lines[-1] = prev + " " + line_str
            else:
                merged_lines.append(line_str)
                
    cleaned = "\n".join(merged_lines)
    # 다중 공백 정리
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()

def extract_legal_metadata(text: str, filename: str, chunk_idx: int) -> Dict[str, Any]:
    """청크 텍스트에서 법령 조문 번호, 섹션 제목, 의미 있는 자동 타이틀 추출"""
    base_name = filename.rsplit('.', 1)[0]
    
    # 조문 패턴 탐지 (예: 제18조, 제14조제1항, 규칙 제60조, 예규 제543호, 선례 201503-2)
    article_matches = re.findall(r'(?:(?:가족관계등록법|법|규칙|예규|선례|민법)?\s*제\s*\d+조(?:의\d+)?(?:제\d+항)?|예규\s*제\d+호|선례\s*\d+-\d+)', text)
    unique_articles = list(dict.fromkeys(article_matches))[:5]
    
    # 장/절 또는 주제 헤딩 탐지 (예: 제3장 직권정정, 【의의 및 요건】)
    heading_match = re.search(r'(?:제\s*\d+\s*[장절관편]\s*([^\n]{2,30})|【([^\n】]{2,30})】|\[([^\n\]]{2,30})\])', text)
    section_heading = ""
    if heading_match:
        section_heading = (heading_match.group(1) or heading_match.group(2) or heading_match.group(3) or "").strip()
        
    # 자동 제목 구성
    if unique_articles:
        main_art = unique_articles[0].strip()
        if section_heading:
            auto_title = f"[{base_name}] {main_art} - {section_heading}"
        else:
            auto_title = f"[{base_name}] {main_art} 관련 실무"
    elif section_heading:
        auto_title = f"[{base_name}] {section_heading}"
    else:
        # 첫 문장의 핵심 어구 발췌
        first_line = text.split('\n')[0].strip()
        summary_title = first_line[:35] + ("..." if len(first_line) > 35 else "")
        auto_title = f"[{base_name}] #{chunk_idx} {summary_title}"
        
    return {
        "auto_title": auto_title,
        "section_heading": section_heading,
        "detected_articles": unique_articles
    }

def semantic_chunk_text(
    full_text: str,
    page_boundaries: List[Dict[str, int]],
    min_size: int = 450,
    target_size: int = 700,
    max_size: int = 950,
    overlap: int = 150
) -> List[Dict[str, Any]]:
    """
    문단(\n\n), 법률 조문 시작(\n제N조), 항목(\n①, \n1.), 문장 종결(.)을 우선순위로 고려한 지능형 의미 청킹
    크로스 페이지 지원 및 페이지 범위 추적
    """
    if not full_text.strip():
        return []

    chunks_raw = []
    text_len = len(full_text)
    start = 0

    while start < text_len:
        if text_len - start <= max_size:
            chunk_content = full_text[start:].strip()
            if len(chunk_content) > 15:
                chunks_raw.append({"start": start, "end": text_len, "content": chunk_content})
            break

        # target_size 주변에서 최적의 분할점 탐색
        ideal_end = start + target_size
        search_start = max(start + min_size, ideal_end - 150)
        search_end = min(text_len, start + max_size)
        search_window = full_text[search_start:search_end]

        split_offset = -1

        # 1순위: 빈 줄 (문단 경계)
        para_match = [m.start() for m in re.finditer(r'\n\s*\n', search_window)]
        if para_match:
            split_offset = para_match[-1] + search_start

        # 2순위: 법률 조문 또는 장/절 시작점 (\n제N조, \n제N장, \n【)
        if split_offset == -1:
            art_matches = [m.start() for m in re.finditer(r'\n(?=제\s*\d+[조장절관]|【|\[|\d+\.\s+[가-힣])', search_window)]
            if art_matches:
                split_offset = art_matches[-1] + search_start

        # 3순위: 항/호 번호 시작 (\n①, \n1), \n가.)
        if split_offset == -1:
            item_matches = [m.start() for m in re.finditer(r'\n(?=[①②③④⑤⑥⑦⑧⑨⑩]|\d+[.)]|[가-하][.)])', search_window)]
            if item_matches:
                split_offset = item_matches[-1] + search_start

        # 4순위: 문장 종결 기호 (.!? 또는 '다.' 뒤 공백/줄바꿈)
        if split_offset == -1:
            sent_matches = [m.end() for m in re.finditer(r'(?:[.!?]|다\.)\s+', search_window)]
            if sent_matches:
                split_offset = sent_matches[-1] + search_start

        # 분할점을 찾지 못한 경우 max_size 경계의 공백에서 분할
        if split_offset == -1:
            space_match = search_window.rfind(' ')
            if space_match != -1:
                split_offset = space_match + search_start
            else:
                split_offset = ideal_end

        chunk_content = full_text[start:split_offset].strip()
        if len(chunk_content) > 15:
            chunks_raw.append({"start": start, "end": split_offset, "content": chunk_content})

        # 다음 청크 시작 위치 (오버랩 적용하되 무한루프 방지)
        next_start = max(start + min_size, split_offset - overlap)
        if next_start >= text_len or next_start <= start:
            next_start = split_offset
        start = next_start

    # 페이지 번호 매핑 (시작 위치와 끝 위치 기반)
    results = []
    for c in chunks_raw:
        c_start = c["start"]
        c_end = c["end"]
        
        start_page = 1
        end_page = 1
        for b in page_boundaries:
            if c_start >= b["start"] and c_start <= b["end"]:
                start_page = b["page"]
            if c_end >= b["start"] and c_end <= b["end"]:
                end_page = b["page"]

        page_str = f"제{start_page}페이지" if start_page == end_page else f"제{start_page}~{end_page}페이지"
        results.append({
            "content": c["content"],
            "start_page": start_page,
            "end_page": end_page,
            "page_str": page_str
        })

    return results

def parse_pdf(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """PDF 파일 파싱: 텍스트 정제, 전페이지 연결 크로스 청킹, 조문 및 맥락 메타데이터 보강"""
    reader = PdfReader(io.BytesIO(file_bytes))
    base_name = filename.rsplit('.', 1)[0]
    timestamp = int(time.time())
    group_id = f"PDF-{timestamp}"

    # 1. 전체 페이지 텍스트 추출 및 페이지별 경계 기록
    full_text_parts = []
    page_boundaries = []
    curr_char_idx = 0

    for page_idx, page in enumerate(reader.pages):
        raw_page = page.extract_text() or ""
        cleaned_page = clean_pdf_text(raw_page)
        
        if cleaned_page:
            start_pos = curr_char_idx
            full_text_parts.append(cleaned_page)
            curr_char_idx += len(cleaned_page) + 2  # "\n\n" 구분자
            end_pos = curr_char_idx
            page_boundaries.append({
                "page": page_idx + 1,
                "start": start_pos,
                "end": end_pos
            })

    full_text = "\n\n".join(full_text_parts)
    if not full_text.strip():
        return []

    # 2. 지능형 의미 단위 청킹 (크로스 페이지 맥락 보존)
    raw_chunks = semantic_chunk_text(full_text, page_boundaries, min_size=450, target_size=700, max_size=950, overlap=150)
    total_chunks = len(raw_chunks)
    docs = []

    # 3. 메타데이터 추출 및 이웃 청크 프리뷰 보강
    for idx, c in enumerate(raw_chunks):
        chunk_idx = idx + 1
        doc_id = f"{group_id}-{chunk_idx}"
        content = c["content"]
        
        legal_meta = extract_legal_metadata(content, filename, chunk_idx)
        
        # 이전 / 다음 청크 힌트 프리뷰
        prev_preview = raw_chunks[idx - 1]["content"][-100:].strip() if idx > 0 else ""
        next_preview = raw_chunks[idx + 1]["content"][:100].strip() if idx < total_chunks - 1 else ""

        docs.append({
            "id": doc_id,
            "group_id": group_id,
            "file_name": filename,
            "category": "PDF 실무자료",
            "source": f"{filename} ({c['page_str']})",
            "title": legal_meta["auto_title"],
            "section_heading": legal_meta["section_heading"],
            "detected_articles": legal_meta["detected_articles"],
            "content": content,
            "page_number": c["start_page"],
            "end_page_number": c["end_page"],
            "chunk_index": chunk_idx,
            "total_chunks": total_chunks,
            "prev_chunk_preview": prev_preview,
            "next_chunk_preview": next_preview,
            "created_at": timestamp
        })

    return docs

def parse_json(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """JSON 파일 파싱 및 지식 객체 정규화"""
    try:
        raw_str = file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        raw_str = file_bytes.decode('cp949', errors='ignore')

    data = json.loads(raw_str)
    items = []

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        if "documents" in data and isinstance(data["documents"], list):
            items = data["documents"]
        elif "items" in data and isinstance(data["items"], list):
            items = data["items"]
        elif "corpus" in data and isinstance(data["corpus"], list):
            items = data["corpus"]
        else:
            # Single object or key-value dictionary
            items = [data]

    docs = []
    timestamp = int(time.time())
    group_id = f"JSON-{timestamp}"

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        # Extract fields with multiple fallbacks
        doc_id = str(item.get("id") or f"{group_id}-{idx+1}")
        category = str(item.get("category") or item.get("type") or "행정지식")
        source = str(item.get("source") or item.get("rules") or item.get("ref") or filename)
        title = str(item.get("title") or item.get("name") or item.get("question") or f"{filename} #{idx+1}")
        content = str(item.get("content") or item.get("text") or item.get("answer") or item.get("summary") or "")

        if not content.strip():
            # If item is structured, serialize values as content
            content = " ".join([f"{k}: {v}" for k, v in item.items() if k not in ["id", "category", "source", "title"]])

        if content.strip():
            docs.append({
                "id": doc_id,
                "group_id": group_id,
                "file_name": filename,
                "category": category,
                "source": source,
                "title": title,
                "content": content.strip(),
            })

    return docs
