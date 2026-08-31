import asyncio
import io
import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from llm_client import stream_chat_completion
from rag.rag_service import rag_service
from rag.corpus_data import CORPUS_DOCS
from rag.document_parser import parse_pdf, parse_json, parse_excel
from rag.excel_hierarchy_parser import create_sample_hierarchy_excel
from optimization.cache_manager import cache_manager
from optimization.metrics_collector import metrics_collector
from security.input_filter import input_filter

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize RAG vector cache on startup
    print("[Server] Initializing RAG vector cache on startup...")
    try:
        await rag_service.initialize()
    except Exception as e:
        print(f"[Server] Failed to initialize RAG on startup: {e}")
    yield
    # Shutdown

app = FastAPI(
    title="대한민국 법원 전자가족관계등록시스템 AI 민원 상담 & 실무 포털",
    description="llama-3.3-70b 및 gpt-oss-120b 듀얼 모델 기반 실시간 RAG 민원 상담 시스템",
    version="4.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR = BASE_DIR.parent / "frontend"

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.5
    max_tokens: Optional[int] = 2500
    use_rag: Optional[bool] = True
    use_web_search: Optional[bool] = False
    mode: Optional[str] = "unified"  # 단일 통합 어시스턴트
    model: Optional[str] = "llama-3.3-70b"  # "llama-3.3-70b" (표준·고속) or "gpt-oss-120b" (심층 추론)
    bypass_cache: Optional[bool] = False  # 캐시 우회 및 실시간 강제 재생성 여부

class CheckInputRequest(BaseModel):
    text: str

class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 3

class ManualDocRequest(BaseModel):
    category: str
    title: str
    source: str
    content: str

@app.post("/api/security/check-input")
async def check_input_security(req: CheckInputRequest):
    """프론트엔드 실시간 개인정보 및 부적절 입력 사전 검증 API"""
    return input_filter.validate_and_sanitize(req.text)

@app.get("/api/security/stats")
async def get_security_statistics():
    """개인정보 마스킹 및 유해 입력 차단 실시간 통계 API"""
    return input_filter.get_stats()

def load_kb_data():
    kb_path = DATA_DIR / "family_reg_officials_kb.json"
    if kb_path.exists():
        with open(kb_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@app.get("/api/kb")
async def get_kb():
    return load_kb_data()

@app.get("/api/quick-cases")
async def get_quick_cases():
    """통합 AI 상담 및 실무 대표 추천 질문 프리셋"""
    return [
        {
            "category": "증명서 무료 발급",
            "title": "일반 vs 상세 증명서 차이 & 무료 발급",
            "prompt": "가족관계증명서 발급받을 때 '일반', '상세', '특정'의 차이가 무엇인가요? 인터넷 무료 발급 수수료(0원)와 신청 요령을 알려주세요."
        },
        {
            "category": "직권정정 법령위계",
            "title": "전산오기 직권정정의 상하위 법령 체계",
            "prompt": "전산오기 직권정정의 상위법률(법 제18조), 대법원규칙(규칙 제60조), 대법원예규, 등록선례의 위임관계와 우선순위를 설명해주세요."
        },
        {
            "category": "인터넷 신고",
            "title": "온라인 출생신고 & 법원 개명신고",
            "prompt": "전자가족관계등록시스템에서 인터넷으로 출생신고 및 법원 개명허가 후 개명신고를 진행하는 순서와 필요 준비물을 알려주세요."
        },
        {
            "category": "친생추정·친생부인",
            "title": "민법 제844조 친생추정과 등록사무",
            "prompt": "혼인종료 후 300일 내 출생한 자녀의 민법 제844조 친생추정 적용과 친생부인 허가청구에 따른 출생신고 절차를 알려주세요."
        },
        {
            "category": "발급권한 제한",
            "title": "형제자매 가족관계증명서 발급 제한",
            "prompt": "가족관계등록법 제14조에 따라 형제자매가 본인의 가족관계증명서를 발급받을 수 있는지, 가능한 예외 사유와 위임장 요건을 설명해주세요."
        },
        {
            "category": "섭외사법 실무",
            "title": "외국인 부모 사이 자녀 출생신고",
            "prompt": "부모가 모두 외국인인 경우 한국 가족관계등록관서에 출생신고를 수리할 수 있는지, 국제사법 및 국적법상 기준을 설명해주세요."
        },
        {
            "category": "장애해결·PDF",
            "title": "프린터 출력 불가 시 PDF 파일 저장",
            "prompt": "집에 프린터가 없거나 '지원하지 않는 프린터' 오류가 발생할 때 증명서를 PDF 파일로 컴퓨터에 저장하는 방법을 알려주세요."
        },
        {
            "category": "간편인증 안내",
            "title": "공인인증서 없이 카카오/네이버 인증",
            "prompt": "공동인증서(구 공인인증서)가 없는데 카카오톡, 네이버, 토스 간편인증으로도 인터넷 증명서 발급이 가능한가요?"
        }
    ]

@app.get("/api/efamily/services")
async def get_efamily_services():
    """전자가족관계등록시스템(efamily.scourt.go.kr) 주요 공식 서비스 링크 목록"""
    return [
        {
            "id": "cert-issue",
            "name": "증명서 발급 (무료)",
            "icon": "fa-print",
            "desc": "가족관계·기본·혼인·입양 등 증명서 인터넷 무료 발급",
            "url": "https://efamily.scourt.go.kr/index.jsp",
            "fee": "인터넷 무료 (0원) / 주민센터 1,000원",
            "prompt": "가족관계증명서와 기본증명서를 인터넷으로 무료 발급받는 방법과 일반/상세증명서 차이점을 알려주세요."
        },
        {
            "id": "birth-apply",
            "name": "인터넷 출생신고",
            "icon": "fa-baby",
            "desc": "참여병원 출생아 대상 온라인 출생신고",
            "url": "https://efamily.scourt.go.kr/index.jsp",
            "fee": "수수료 없음 (무료)",
            "prompt": "인터넷으로 출생신고 하려면 어떤 조건(참여병원 등)이 필요하고 어떤 절차로 진행하나요?"
        },
        {
            "id": "name-apply",
            "name": "인터넷 개명신고",
            "icon": "fa-pen-to-square",
            "desc": "가정법원 개명허가 결정 후 1개월 내 온라인 신고",
            "url": "https://efamily.scourt.go.kr/index.jsp",
            "fee": "수수료 없음 (무료)",
            "prompt": "가정법원에서 개명허가 결정문을 받았습니다. 인터넷으로 개명신고하는 순서를 알려주세요."
        },
        {
            "id": "domicile-change",
            "name": "등록기준지 변경신고",
            "icon": "fa-house-user",
            "desc": "원하는 주소지로 온라인 등록기준지(구 본적) 변경",
            "url": "https://efamily.scourt.go.kr/index.jsp",
            "fee": "수수료 없음 (무료)",
            "prompt": "가족관계등록부의 등록기준지(본적)를 원하는 주소로 인터넷에서 변경하는 방법을 알려주세요."
        },
        {
            "id": "doc-verify",
            "name": "발급문서 진위확인",
            "icon": "fa-shield-halved",
            "desc": "발급문서 상단 16자리 문서확인번호 검증",
            "url": "https://efamily.scourt.go.kr/index.jsp",
            "fee": "무료 조회",
            "prompt": "전자가족관계등록시스템에서 발급받은 증명서의 16자리 문서확인번호로 진위확인하는 방법을 알려주세요."
        },
        {
            "id": "tech-help",
            "name": "인증서/프린터 오류 해결",
            "icon": "fa-screwdriver-wrench",
            "desc": "간편인증 지원 및 PDF 저장·프린터 문제 해결",
            "url": "https://efamily.scourt.go.kr/index.jsp",
            "fee": "고객지원",
            "prompt": "증명서 출력 시 '지원하지 않는 프린터' 오류가 나거나 출력이 안 될 때 PDF로 저장하는 방법을 알려주세요."
        }
    ]

@app.get("/api/efamily/quick-faq")
async def get_efamily_quick_faq():
    """자주 묻는 질문 (호환 유지)"""
    return await get_quick_cases()

@app.get("/api/rag/stats")
async def get_rag_stats():
    docs = rag_service.get_all_documents()
    return {
        "total_corpus_docs": len(docs),
        "embedding_model": "bge-m3",
        "reranker_model": "bge-reranker-v2-m3",
        "default_model": "llama-3.3-70b",
        "reasoning_model": "gpt-oss-120b",
        "has_cached_embeddings": (DATA_DIR / "corpus_embeddings.npy").exists()
    }

@app.get("/api/metrics/stats")
async def get_metrics_stats():
    """지연시간, 토큰 소비량 및 질의 캐시 적중률 통계"""
    cache_stats = cache_manager.get_stats()
    metric_summary = metrics_collector.get_summary()
    return {
        "cache": cache_stats,
        "metrics": metric_summary
    }

@app.post("/api/cache/clear")
async def clear_query_cache():
    """질의 캐시 초기화"""
    cache_manager.clear()
    return {"success": True, "message": "질의응답 캐시가 초기화되었습니다."}

@app.post("/api/rag/search")
async def search_rag(req: SearchRequest):
    results = await rag_service.retrieve(req.query, top_k=req.top_k or 3)
    return {"query": req.query, "results": results}

# --- 관리자 문서/파일 관리 API 엔드포인트 ---

@app.get("/api/admin/files")
async def get_admin_files():
    """등록된 문서를 파일/출처 단위로 그룹화하여 목록 반환"""
    files = rag_service.get_grouped_files()
    total_chunks = len(rag_service.get_all_documents())
    return {
        "total_files": len(files),
        "total_chunks": total_chunks,
        "files": files
    }

@app.delete("/api/admin/file/{file_id}")
async def delete_admin_file(file_id: str):
    """특정 파일/문서 그룹 및 속한 모든 청크 일괄 삭제"""
    result = await rag_service.delete_file_group(file_id)
    return {
        "success": True,
        "file_id": file_id,
        "deleted_chunks": result["deleted_count"],
        "remaining_chunks": result["remaining_docs"]
    }

@app.get("/api/admin/documents")
async def get_admin_documents():
    docs = rag_service.get_all_documents()
    return {
        "total": len(docs),
        "documents": docs
    }

@app.get("/api/admin/sample-excel")
async def get_sample_hierarchy_excel():
    """상하위 법률 관계 표준 엑셀 템플릿 파일 생성 및 다운로드"""
    excel_bytes = create_sample_hierarchy_excel()
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=legal_hierarchy_template.xlsx"}
    )

@app.post("/api/admin/upload")
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename or "unknown_file"
    file_bytes = await file.read()
    
    saved_path = UPLOAD_DIR / f"{int(time.time())}_{filename}"
    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    docs = []
    lower_fn = filename.lower()
    if lower_fn.endswith((".xlsx", ".xls")):
        docs = parse_excel(file_bytes, filename)
    elif lower_fn.endswith(".pdf"):
        docs = parse_pdf(file_bytes, filename)
    elif lower_fn.endswith(".json"):
        docs = parse_json(file_bytes, filename)
    else:
        raise HTTPException(status_code=400, detail="지원되지 않는 파일 형식입니다. (PDF, JSON 또는 엑셀 .xlsx만 지원)")

    if not docs:
        raise HTTPException(status_code=400, detail="문서에서 추출 가능한 유효한 지식/법령 데이터가 없습니다.")

    added_count = await rag_service.add_documents(docs)
    return {
        "success": True,
        "filename": filename,
        "chunks_created": added_count,
        "total_corpus_docs": len(rag_service.get_all_documents())
    }

@app.post("/api/admin/document")
async def create_single_document(doc: ManualDocRequest):
    if not doc.title.strip() or not doc.content.strip():
        raise HTTPException(status_code=400, detail="제목과 내용을 모두 입력해주세요.")

    timestamp = int(time.time())
    new_item = {
        "id": f"MANUAL-{timestamp}",
        "category": doc.category.strip() or "일반실무",
        "source": doc.source.strip() or "관리자 직접등록",
        "title": doc.title.strip(),
        "content": doc.content.strip(),
        "created_at": timestamp
    }

    added_count = await rag_service.add_documents([new_item])
    return {
        "success": True,
        "document": new_item,
        "total_corpus_docs": len(rag_service.get_all_documents())
    }

@app.delete("/api/admin/documents")
async def clear_all_documents():
    await rag_service.clear_all_documents()
    return {
        "success": True,
        "message": "모든 RAG 지식 문서가 삭제되었습니다.",
        "remaining_docs": 0
    }

@app.post("/api/admin/reset-default")
async def reset_default_corpus():
    total = await rag_service.reset_to_default()
    return {
        "success": True,
        "message": f"기본 지식 코퍼스({total}건)로 초기화 및 재임베딩되었습니다.",
        "total_docs": total
    }

@app.delete("/api/admin/document/{doc_id}")
async def delete_document(doc_id: str):
    success = await rag_service.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="해당 문서를 찾을 수 없습니다.")
    return {
        "success": True,
        "deleted_id": doc_id,
        "remaining_docs": len(rag_service.get_all_documents())
    }

@app.post("/api/admin/reindex")
async def reindex_corpus():
    total = await rag_service.reindex_all()
    return {
        "success": True,
        "reindexed_count": total
    }

@app.get("/api/quick-cases")
async def get_quick_cases():
    return [
        {
            "category": "직권정정",
            "title": "전산오기 간이직권정정 여부",
            "prompt": "출생신고서 원본에는 모의 주민등록번호가 정확하게 기재되어 있으나, 가족관계등록부 전산 입력 시 오기된 경우 감독법원의 사전허가를 받아야 하나요? 관련 법령 및 처리 절차를 알려주세요."
        },
        {
            "category": "직권정정",
            "title": "이중등록부 폐쇄 절차",
            "prompt": "동일인에 대해 착오로 2개의 가족관계등록부가 작성된 이중등록부 사실이 발견되었습니다. 어떤 절차를 거쳐 폐쇄 및 정리해야 하며 감독법원의 허가가 필요한가요?"
        },
        {
            "category": "출생신고",
            "title": "미혼부의 자녀 단독 출생신고",
            "prompt": "생모의 인적사항을 알 수 없는 미혼부가 자녀의 출생신고를 하러 왔습니다. 접수 시 확인해야 할 법원 결정서와 유전자검사서 등 필수 요건 및 심사 기준을 설명해주세요."
        },
        {
            "category": "출생신고",
            "title": "이혼 후 300일 내 출생 자녀",
            "prompt": "전남편과 협의이혼 후 200일 만에 다른 남자의 아이를 출생하였습니다. 전남편의 자녀로 등록되지 않고 생부의 자녀로 출생신고하려면 어떤 법적 절차(친생부인 허가 등)가 필요한가요?"
        },
        {
            "category": "혼인/이혼",
            "title": "혼인신고 일방 출석 시 심사",
            "prompt": "혼인신고 시 당사자 일방만 출석하였습니다. 불출석 당사자의 신분증 제시 요건 및 의사 확인 기준(예규 제543호), 서명/날인 흠결 시 처리 요령을 알려주세요."
        },
        {
            "category": "혼인/이혼",
            "title": "협의이혼확인서 3개월 도과 건",
            "prompt": "가정법원의 협의이혼의사확인서등본 교부일로부터 3개월 3일이 지난 협의이혼신고서가 제출되었습니다. 수리 가능한지, 불수리 처분 시 근거 법조항과 불수리통지서 교부 절차를 안내해주세요."
        },
        {
            "category": "사망신고",
            "title": "사망진단서 흠결 시 인우보증 불가",
            "prompt": "사망진단서나 시체검안서 없이 인우인 2명의 보증서만 첨부하여 사망신고서가 접수되었습니다. 수리 가능한지 여부와 대체 가능한 공적 증명 서면의 종류를 설명해주세요."
        },
        {
            "category": "증명서교부",
            "title": "형제자매의 가족관계증명서 발급 청구",
            "prompt": "성인인 형제가 동생의 가족관계증명서 상세본을 발급해달라고 방문했습니다. 원칙적 발급 가능 여부와 예외적으로 발급이 허용되는 요건(위임장, 소송 제출명령 등)을 설명해주세요."
        }
    ]

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages list cannot be empty")
        
    messages_payload = [{"role": m.role, "content": m.content} for m in request.messages]
    
    # 0. Security Guardrail: Validate & Sanitize last user message
    last_user_query = ""
    last_user_idx = -1
    for i in range(len(messages_payload) - 1, -1, -1):
        if messages_payload[i]["role"] == "user":
            last_user_query = messages_payload[i]["content"]
            last_user_idx = i
            break

    sec_result = input_filter.validate_and_sanitize(last_user_query) if last_user_query else {"allowed": True, "sanitized_text": "", "pii": {"has_pii": False}}

    # Case A: Inappropriate input (profanity / injection), block immediately without burning LLM tokens
    if not sec_result["allowed"]:
        async def blocked_event_generator():
            warning_msg = sec_result["inappropriate"]["message"]
            yield f"data: {json.dumps({'type': 'security_block', 'data': {'category': sec_result['inappropriate']['category'], 'reason': sec_result['inappropriate']['reason']}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'delta', 'data': warning_msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'metrics', 'data': {'latency_ms': 5, 'prompt_tokens': 0, 'completion_tokens': 25, 'total_tokens': 25, 'model': '보안 가드레일 (SafeGuard)', 'cached': False}}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            blocked_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream; charset=utf-8",
            }
        )

    # Case B: PII detected, replace message content with sanitized/masked version
    pii_notice_data = None
    if sec_result["pii"]["has_pii"] and last_user_idx >= 0:
        messages_payload[last_user_idx]["content"] = sec_result["sanitized_text"]
        pii_notice_data = {
            "masked": True,
            "detected_types": sec_result["pii"]["detected_types"],
            "sanitized_text": sec_result["sanitized_text"]
        }

    # 1. Web Agent Search Mode (/v1/agent/chat)
    if request.use_web_search:
        async def agent_event_generator():
            if pii_notice_data:
                yield f"data: {json.dumps({'type': 'pii_notice', 'data': pii_notice_data}, ensure_ascii=False)}\n\n"

            last_query = messages_payload[-1]["content"] if messages_payload else ""
            agent_result = await rag_service.execute_web_agent(last_query, messages_payload)
            
            sources = agent_result.get("sources", [])
            if sources:
                yield f"data: {json.dumps({'type': 'sources', 'data': [{'title': '웹 검색 출처', 'source': s, 'content': s} for s in sources]}, ensure_ascii=False)}\n\n"
            
            answer = agent_result.get("answer", "웹 검색 에이전트 응답을 가져올 수 없습니다.")
            yield f"data: {json.dumps({'type': 'delta', 'data': answer}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'metrics', 'data': {'latency_ms': 850, 'prompt_tokens': 120, 'completion_tokens': 200, 'total_tokens': 320, 'model': 'qwen3-coder (웹에이전트)', 'cached': False}}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            agent_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream; charset=utf-8",
            }
        )

    # 2. Standard Chat / RAG Mode with llama-3.3-70b (or gpt-oss-120b) and Query Caching
    async def event_generator():
        if pii_notice_data:
            yield f"data: {json.dumps({'type': 'pii_notice', 'data': pii_notice_data}, ensure_ascii=False)}\n\n"

        selected_model = request.model or "llama-3.3-70b"
        async for chunk in stream_chat_completion(
            messages=messages_payload,
            temperature=request.temperature or 0.5,
            max_tokens=request.max_tokens or 2500,
            use_rag=request.use_rag if request.use_rag is not None else True,
            mode=request.mode or "unified",
            model=selected_model,
            bypass_cache=request.bypass_cache or False
        ):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
        }
    )

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
async def read_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(
            str(index_file),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"message": "Frontend not found"}
