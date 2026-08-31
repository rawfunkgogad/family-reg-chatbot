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

def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> List[str]:
    """텍스트를 적정 크기로 분할 (문단/문장 단위 고려)"""
    cleaned_text = re.sub(r'\s+', ' ', text).strip()
    if not cleaned_text:
        return []

    if len(cleaned_text) <= chunk_size:
        return [cleaned_text]

    chunks = []
    start = 0
    while start < len(cleaned_text):
        end = start + chunk_size
        if end >= len(cleaned_text):
            chunks.append(cleaned_text[start:].strip())
            break

        # Try to find sentence end (.!?) near the end boundary
        lookback = cleaned_text[max(start, end - 120):end]
        match = re.search(r'[.!?\n]\s+', lookback)
        if match:
            split_point = max(start, end - 120) + match.end()
            chunks.append(cleaned_text[start:split_point].strip())
            start = split_point
        else:
            chunks.append(cleaned_text[start:end].strip())
            start = end - overlap

    return [c for c in chunks if len(c) > 20]

def parse_pdf(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """PDF 파일 파싱 및 페이지별 텍스트 청킹"""
    reader = PdfReader(io.BytesIO(file_bytes))
    docs = []
    base_name = filename.rsplit('.', 1)[0]
    timestamp = int(time.time())
    group_id = f"PDF-{timestamp}"

    for page_idx, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        if not page_text.strip():
            continue

        page_chunks = chunk_text(page_text, chunk_size=700, overlap=100)
        for chunk_idx, chunk in enumerate(page_chunks):
            doc_id = f"{group_id}-{page_idx+1}-{chunk_idx+1}"
            docs.append({
                "id": doc_id,
                "group_id": group_id,
                "file_name": filename,
                "category": "PDF 실무자료",
                "source": f"{filename} (제{page_idx+1}페이지)",
                "title": f"[{base_name}] 제{page_idx+1}면 발췌 #{chunk_idx+1}",
                "content": chunk,
                "page_number": page_idx + 1,
                "chunk_index": chunk_idx + 1,
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
