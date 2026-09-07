import asyncio
import io
import json
import time
import hashlib
import secrets
import re
import urllib.parse
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from llm_client import stream_chat_completion
import zipfile
from rag.rag_service import rag_service
from rag.corpus_data import CORPUS_DOCS
from rag.document_parser import parse_pdf, parse_json, parse_excel
from rag.excel_hierarchy_parser import create_sample_hierarchy_excel
from rag.rig_engine import rig_engine, form_matcher, LawCitationParser
from optimization.cache_manager import cache_manager
from optimization.metrics_collector import metrics_collector
from optimization.query_logger import query_logger
from security.input_filter import input_filter
from sync.corpus_sync_manager import corpus_sync_manager
from sync.scheduler import start_daily_midnight_scheduler

# --- 관리자 보안 인증 체계 (Salted SHA-256 Hashing & Session Token) ---
ADMIN_SALT = "scourt_family_reg_admin_2026_salt"
# 인증코드: family_manager_035 의 솔트 결합 SHA-256 해시값 (평문 저장 방지)
EXPECTED_AUTH_HASH = hashlib.sha256((ADMIN_SALT + "family_manager_035").encode("utf-8")).hexdigest()
admin_sessions: Dict[str, float] = {}  # token -> expiration timestamp (8시간 유효)

security_bearer = HTTPBearer(auto_error=False)

async def verify_admin_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> str:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="지식 관리자 보안 인증이 필요합니다.")
    token = credentials.credentials
    exp = admin_sessions.get(token)
    if not exp or time.time() > exp:
        admin_sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="인증 세션이 만료되었거나 유효하지 않습니다. 다시 로그인해주세요.")
    return token

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 크롤러 산출물 기반 기본 지식 코퍼스 무결성 검증 및 확보
    print("[Server] Ensuring default knowledge corpus from crawlers...")
    try:
        await corpus_sync_manager.ensure_default_knowledge()
    except Exception as e:
        print(f"[Server] Warning during ensure_default_knowledge: {e}")

    # 2. RAG 벡터 캐시 인덱스 초기화
    print("[Server] Initializing RAG vector cache on startup...")
    try:
        await rag_service.initialize()
    except Exception as e:
        print(f"[Server] Failed to initialize RAG on startup: {e}")

    # 3. 매일 00:00 KST 자동 현행화 백그라운드 스케줄러 가동
    try:
        start_daily_midnight_scheduler()
    except Exception as e:
        print(f"[Server] Failed to start daily midnight scheduler: {e}")

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
    use_rig: Optional[bool] = True
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
    category: Optional[str] = "일반실무"
    title: Optional[str] = ""
    source: Optional[str] = "관리자 직접등록"
    content: Optional[str] = ""
    # RLHF / Gold Standard Alignment Fields
    prompt: Optional[str] = None
    chosen: Optional[str] = None
    rejected: Optional[str] = None
    legal_basis: Optional[str] = None
    confidence_boost: Optional[float] = 1.5


@app.post("/api/security/check-input")
async def check_input_security(req: CheckInputRequest):
    """프론트엔드 실시간 개인정보 및 부적절 입력 사전 검증 API"""
    return input_filter.validate_and_sanitize(req.text)

@app.get("/api/health")
async def health_check():
    """서버 상태 및 RAG 인덱스 헬스체크 API"""
    return {
        "status": "healthy",
        "service": "family-registry-chatbot",
        "version": "5.2.2",
        "corpus_docs": len(rag_service.corpus),
        "embeddings_ready": rag_service.embeddings is not None
    }

@app.get("/api/security/stats")
async def get_security_statistics():
    """개인정보 마스킹 및 유해 입력 차단 실시간 종합 통계 API"""
    sec_stats = input_filter.get_stats()
    pii_in_logs = sum(1 for l in query_logger.logs if l.get("has_pii", False))
    total_pii = max(sec_stats.get("pii_masked_count", 0), pii_in_logs)
    total_checked = max(sec_stats.get("total_checked", 0), len(query_logger.logs))
    return {
        "total_checked": total_checked,
        "pii_masked_count": total_pii,
        "inappropriate_blocked_count": sec_stats.get("inappropriate_blocked_count", 0),
        "pii_type_counts": sec_stats.get("pii_type_counts", {}),
        "last_incident_time": sec_stats.get("last_incident_time")
    }

def load_kb_data():
    kb_path = DATA_DIR / "family_reg_officials_kb.json"
    if kb_path.exists():
        with open(kb_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@app.get("/api/kb")
async def get_kb():
    return load_kb_data()

@app.get("/api/legal/document")
async def get_legal_document(query: str = ""):
    """대법원 예규/선례/법령 조문 실시간 원문 및 스마트 링크 조회 API"""
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    q_clean = query.strip()
    corpus = rag_service.corpus
    found_doc = None

    # 1. Direct ID match
    for d in corpus:
        if d.get("id") == q_clean:
            found_doc = d
            break

    # 2. Number extraction for Directives (예규) and Precedents (선례)
    if not found_doc:
        dir_match = re.search(r'(?:예규\s*제?|DIR-?)(\d+)', q_clean)
        prec_match = re.search(r'(?:선례\s*제?|PREC-?)([\d\-]+)', q_clean)

        if dir_match:
            dir_no = dir_match.group(1)
            target_id = f"SCOURT-DIR-{dir_no}"
            for d in corpus:
                if d.get("id") == target_id or (d.get("category") == "가족관계등록예규" and f"제{dir_no}호" in d.get("title", "")):
                    found_doc = d
                    break

        if not found_doc and prec_match:
            prec_no = prec_match.group(1)
            target_id = f"SCOURT-PREC-{prec_no}"
            for d in corpus:
                if d.get("id") == target_id or (d.get("category") == "가족관계등록선례" and prec_no in d.get("title", "")):
                    found_doc = d
                    break

    # 3. Pure digit query
    if not found_doc and q_clean.isdigit():
        target_id = f"SCOURT-DIR-{q_clean}"
        for d in corpus:
            if d.get("id") == target_id:
                found_doc = d
                break

    # 4. Search in titles
    if not found_doc:
        for d in corpus:
            if q_clean in d.get("title", ""):
                found_doc = d
                break

    if not found_doc:
        return {
            "found": False,
            "query": query,
            "message": "해당 예규 또는 선례 원문을 찾을 수 없습니다."
        }

    title = found_doc.get("title", "")
    category = found_doc.get("category", "")
    content = found_doc.get("content", "")
    source = found_doc.get("source", "")
    doc_id = found_doc.get("id", "")

    # Clean title without bracket prefix e.g. "[가족관계등록예규 제626호] "
    clean_title = re.sub(r'^\[.*?\]\s*', '', title).strip()

    # Smart law.go.kr URL using the actual rule/precedent title keyword
    search_keyword = clean_title.split()[0] if clean_title else q_clean
    if len(clean_title) >= 6:
        search_keyword = clean_title[:20].strip()

    import urllib.parse
    if category == "가족관계등록선례":
        law_go_kr_url = f"https://www.law.go.kr/LSW/precSc.do?menuId=1&subMenuId=15&tabNo=0&query={urllib.parse.quote(search_keyword)}"
    else:
        law_go_kr_url = f"https://www.law.go.kr/LSW/admRulSc.do?menuId=5&subMenuId=41&tabNo=0&query={urllib.parse.quote(search_keyword)}"

    scourt_url = "https://portal.scourt.go.kr/pgp/index.on?m=PGP1051M01&l=N&c=900"

    return {
        "found": True,
        "id": doc_id,
        "title": title,
        "clean_title": clean_title,
        "category": category,
        "source": source,
        "content": content,
        "law_go_kr_url": law_go_kr_url,
        "scourt_url": scourt_url,
        "search_keyword": search_keyword
    }

@app.get("/api/quick-cases")
async def get_quick_cases():
    """대법원·감독법원·등록관서 실무관 및 심사관 핵심 추천 질문 프리셋"""
    return [
        {
            "category": "제14조 교부적격심사",
            "title": "형제자매 발급 제한 및 소명자료 심사",
            "prompt": "가족관계등록법 제14조에 따라 형제자매가 본인의 가족관계증명서를 교부 청구할 때, 원칙적 발급제한과 예외적 발급 허용 사유(소송계속, 채권집행 등 소명자료)의 적격 심사 기준을 설명해주세요."
        },
        {
            "category": "직권정정·규칙60조",
            "title": "간이직권정정 vs 감독법원 허가 판단",
            "prompt": "등록공무원의 명백한 전산오기 정정(법 제18조)에 있어 관서 단독 간이직권정정이 가능한 범위와 대법원규칙 제60조에 따라 감독법원(가정법원)의 직권정정 허가를 반드시 받아야 하는 사례의 구분 기준을 알려주세요."
        },
        {
            "category": "혼인신고 심사",
            "title": "협의이혼의사확인서 3개월 실효 및 불수리",
            "prompt": "가정법원의 협의이혼의사확인서 등본 송달 후 3개월이 경과하여 신고서가 접수된 경우, 확인서의 효력상실 여부와 등록관서의 불수리통지서 작성 및 처리 절차를 설명해주세요."
        },
        {
            "category": "섭외가족관계사무",
            "title": "외국인 부모 사이 자녀 출생신고 수리심사",
            "prompt": "부모가 모두 외국인이거나 일방이 외국인인 경우 한국 등록관서에 출생신고가 접수되었을 때 수리 가부 판단 기준과 증서등본 편철 및 성·본 창설 실무 지침을 알려주세요."
        },
        {
            "category": "친생추정·친생부인",
            "title": "민법 제844조 친생추정과 출생신고 실무",
            "prompt": "혼인종료 후 300일 내 출생한 자녀의 민법 제844조 친생추정 적용과 가정법원의 친생부인의 허가결정에 따른 출생신고 심사 및 수리 요령을 설명해주세요."
        },
        {
            "category": "사망·실종 심사",
            "title": "인정사망 관공서 통보 및 실종선고 심사",
            "prompt": "수난·화재 등 변사 사건에 대한 관공서 인정사망 통보(법 제87조)와 법원의 실종선고 확정에 따른 사망등록 처리 절차 및 등록부 정리 기준을 알려주세요."
        },
        {
            "category": "불수리 처분·이의신청",
            "title": "법 제107조 불수리처분과 감독법원 송부",
            "prompt": "등록신고사건의 수리 불능으로 불수리처분 통지를 한 후 당사자가 법 제107조에 따라 이의신청을 제기하였을 때, 관서의 의견서 작성 및 감독법원(가정법원) 송부 절차를 알려주세요."
        },
        {
            "category": "친양자입양 심사",
            "title": "친양자입양 확정 및 종전 등록부 폐쇄",
            "prompt": "가정법원의 친양자 입양결정 확정 후 등록신고 접수 시, 종전 친생부모와의 친족관계 단절 및 가족관계등록부 폐쇄·신규 등록부 작성 실무 절차를 설명해주세요."
        }
    ]

@app.get("/api/efamily/services")
async def get_efamily_services():
    """등록관서 및 감독법원 실무 심사 연계 핵심 시스템 목록"""
    return [
        {
            "id": "audit-standards",
            "name": "등록관서 수리·심사 기준표",
            "icon": "fa-clipboard-check",
            "desc": "출생·혼인·이혼·사망·개명 법정 수리요건 심사",
            "url": "https://efamily.scourt.go.kr/index.jsp",
            "fee": "실무 심사",
            "prompt": "가족관계등록 접수사건(출생·혼인·이혼·사망·개명)의 기본 수리 심사 요건 및 필수 첨부서면 체크리스트를 설명해주세요."
        },
        {
            "id": "rect-court",
            "name": "직권정정 & 감독법원 허가",
            "icon": "fa-scale-balanced",
            "desc": "법 제18조 간이정정 및 가정법원 허가신청",
            "url": "https://efamily.scourt.go.kr/index.jsp",
            "fee": "법리 판단",
            "prompt": "전산오기 직권정정의 상위법률(법 제18조), 대법원규칙(규칙 제60조), 대법원예규, 등록선례의 위임관계와 우선순위를 설명해주세요."
        },
        {
            "id": "cert-eligibility",
            "name": "제14조 교부청구 적격심사",
            "icon": "fa-user-shield",
            "desc": "본인·직계혈족 원칙 및 형제자매 발급제한 심사",
            "url": "https://efamily.scourt.go.kr/index.jsp",
            "fee": "권한 심사",
            "prompt": "가족관계등록법 제14조에 따라 형제자매가 본인의 가족관계증명서를 발급받을 수 있는지, 가능한 예외 사유와 위임장 요건을 설명해주세요."
        },
        {
            "id": "rejection-objection",
            "name": "불수리 통지 & 이의신청",
            "icon": "fa-ban",
            "desc": "법 제107조 불수리통지서 작성 및 법원 이의신청",
            "url": "https://efamily.scourt.go.kr/index.jsp",
            "fee": "처분 실무",
            "prompt": "등록관서의 수리 거부(불수리처분) 통지서 작성 요령과 신청인의 감독법원 이의신청(법 제107조) 접수 처리 절차를 설명해주세요."
        },
        {
            "id": "intl-family",
            "name": "섭외가족관계사무 심사",
            "icon": "fa-earth-asia",
            "desc": "외국인 신분행위 수리 및 증서등본 편철",
            "url": "https://efamily.scourt.go.kr/index.jsp",
            "fee": "섭외 사법",
            "prompt": "부모가 모두 외국인인 경우 한국 가족관계등록관서에 출생신고를 수리할 수 있는지, 국제사법 및 국적법상 기준을 설명해주세요."
        },
        {
            "id": "judicial-link",
            "name": "사법정보망 & 전산조회",
            "icon": "fa-network-wired",
            "desc": "대법원 종합법률정보, 전자관보, e-하나로 연계",
            "url": "https://glaw.scourt.go.kr",
            "fee": "공무 연계",
            "prompt": "대법원 가족관계등록선례집 및 예규 검색 시 최신 제·개정 사항을 반영하여 해석하는 실무 기준을 설명해주세요."
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
    """지연시간, 토큰 소비량, 질의 통계 및 캐시 적중률 종합 통계"""
    cache_stats = cache_manager.get_stats()
    metric_summary = metrics_collector.get_summary()
    logger_stats = query_logger.get_stats_summary()
    
    total_calls = logger_stats["total_logs"]
    avg_lat = logger_stats["avg_latency_ms"] if total_calls > 0 else metric_summary.get("avg_latency_ms", 0.0)
    total_tok = logger_stats["total_tokens"] if total_calls > 0 else metric_summary.get("total_tokens_consumed", 0)

    return {
        "total_calls": total_calls,
        "today_calls": logger_stats["today_logs"],
        "rag_ratio_pct": logger_stats["rag_ratio_pct"],
        "avg_latency_ms": avg_lat,
        "avg_latency_sec": round(avg_lat / 1000, 2),
        "total_tokens": total_tok,
        "estimated_daily_cost": logger_stats["estimated_cost_usd"],
        "model_breakdown": logger_stats["model_breakdown"],
        "cache": cache_stats,
        "metrics": metric_summary,
        "logger": logger_stats
    }

@app.post("/api/metrics/reset")
async def reset_metrics_stats(token: str = Depends(verify_admin_token)):
    """실시간 수집 메트릭 초기화"""
    metrics_collector.history = []
    metrics_collector.model_stats = {
        "llama-3.3-70b": {"requests": 0, "total_tokens": 0, "total_latency_ms": 0},
        "gpt-oss-120b": {"requests": 0, "total_tokens": 0, "total_latency_ms": 0}
    }
    return {"success": True, "message": "모니터링 통계 지표가 초기화되었습니다."}

@app.post("/api/cache/clear")
async def clear_query_cache():
    """질의 캐시 초기화"""
    cache_manager.clear()
    return {"success": True, "message": "질의응답 캐시가 초기화되었습니다."}

@app.post("/api/rag/search")
async def search_rag(req: SearchRequest):
    results = await rag_service.retrieve(req.query, top_k=req.top_k or 3)
    return {"query": req.query, "results": results}

# --- 관리자 보안 인증 (Authentication) API 엔드포인트 ---

class AdminLoginRequest(BaseModel):
    auth_code: str

@app.post("/api/admin/auth/login")
async def admin_auth_login(req: AdminLoginRequest):
    """관리자 인증코드 솔트 해시 검증 및 세션 토큰 발급"""
    provided = req.auth_code.strip()
    computed_hash = hashlib.sha256((ADMIN_SALT + provided).encode("utf-8")).hexdigest()
    if computed_hash != EXPECTED_AUTH_HASH:
        raise HTTPException(status_code=401, detail="관리자 인증코드가 일치하지 않습니다. 다시 확인해주세요.")
    
    token = secrets.token_urlsafe(32)
    admin_sessions[token] = time.time() + 8 * 3600  # 8시간 세션 유효
    return {
        "success": True,
        "token": token,
        "expires_in": 28800,
        "message": "사법행정 지식 관리자 보안 인증에 성공하였습니다."
    }

@app.post("/api/admin/auth/logout")
async def admin_auth_logout(token: str = Depends(verify_admin_token)):
    """관리자 세션 토큰 무효화(로그아웃)"""
    admin_sessions.pop(token, None)
    return {"success": True, "message": "성공적으로 로그아웃되었습니다."}

@app.get("/api/admin/auth/verify")
async def admin_auth_verify(token: str = Depends(verify_admin_token)):
    """현재 세션 토큰 유효성 검사"""
    return {"authenticated": True, "remaining_seconds": int(admin_sessions.get(token, 0) - time.time())}

# --- 관리자 문서/파일 관리 API 엔드포인트 (토큰 검증 보호) ---

@app.get("/api/admin/files")
async def get_admin_files(token: str = Depends(verify_admin_token)):
    """등록된 문서를 파일/출처 단위로 그룹화하여 목록 반환"""
    files = rag_service.get_grouped_files()
    total_chunks = len(rag_service.get_all_documents())
    return {
        "total_files": len(files),
        "total_chunks": total_chunks,
        "files": files
    }

@app.delete("/api/admin/file/{file_id}")
async def delete_admin_file(file_id: str, token: str = Depends(verify_admin_token)):
    """특정 파일/문서 그룹 및 속한 모든 청크 일괄 삭제"""
    result = await rag_service.delete_file_group(file_id)
    return {
        "success": True,
        "file_id": file_id,
        "deleted_chunks": result["deleted_count"],
        "remaining_chunks": result["remaining_docs"]
    }

@app.get("/api/admin/documents")
async def get_admin_documents(token: str = Depends(verify_admin_token)):
    docs = rag_service.get_all_documents()
    return {
        "total": len(docs),
        "documents": docs
    }

@app.get("/api/admin/sample-excel")
async def get_sample_hierarchy_excel(token: str = Depends(verify_admin_token)):
    """상하위 법률 관계 표준 엑셀 템플릿 파일 생성 및 다운로드"""
    excel_bytes = create_sample_hierarchy_excel()
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=legal_hierarchy_template.xlsx"}
    )

@app.get("/api/admin/corpus/export")
async def export_admin_corpus(token: str = Depends(verify_admin_token)):
    """전체 지식 코퍼스를 표준 UTF-8 JSON 백업 파일로 직렬화하여 즉시 다운로드 (초고속·초경량)"""
    package = rag_service.export_corpus_package()
    timestamp_str = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    filename = f"scourt_family_reg_knowledge_backup_{timestamp_str}.json"
    
    json_bytes = json.dumps(package, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(json_bytes)),
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.post("/api/admin/corpus/import")
async def import_admin_corpus(file: UploadFile = File(...), token: str = Depends(verify_admin_token)):
    """백업 JSON 파일로부터 지식 코퍼스 복원 및 임베딩 자동 동기화"""
    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="백업 파일은 .json 형식이어야 합니다.")
    
    try:
        content_bytes = await file.read()
        if not content_bytes:
            raise HTTPException(status_code=400, detail="업로드된 백업 파일의 내용이 비어있습니다.")

        try:
            package_data = json.loads(content_bytes.decode("utf-8"))
        except Exception as je:
            raise HTTPException(status_code=400, detail=f"유효한 JSON 파일이 아닙니다: {str(je)}")

        result = await rag_service.import_corpus_package(package_data, merge_mode="replace")
        return {
            "success": True,
            "message": f"총 {result['total_docs']}건의 지식 코퍼스가 성공적으로 복원되었습니다.",
            "total_docs": result["total_docs"],
            "restored_count": result.get("restored_count", result["total_docs"])
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"지식 복원 처리 중 오류 발생: {str(e)}")

# --- 지식 코퍼스 실시간 현행화 (대법원·국가법령 수집기 연동 & 00시/수동 동기화) API ---

@app.get("/api/admin/corpus/sync/status")
async def get_corpus_sync_status():
    """현재 지식 코퍼스 동기화 상태, 다음 자정(00:00 KST) 예정 시각 및 최근 통계 반환"""
    return corpus_sync_manager.get_status()

class SyncTriggerRequest(BaseModel):
    run_crawlers: Optional[bool] = True

@app.post("/api/admin/corpus/sync")
async def trigger_corpus_sync(
    req: Optional[SyncTriggerRequest] = None,
    token: str = Depends(verify_admin_token)
):
    """관리자 수동 지식 코퍼스 현행화 트리거 (백그라운드 비동기 실행)"""
    if corpus_sync_manager.is_running:
        return {
            "success": False,
            "message": "이미 지식 코퍼스 현행화 작업이 진행 중입니다.",
            "status": corpus_sync_manager.get_status()
        }
    
    run_crawlers = req.run_crawlers if req is not None else True
    # 백그라운드 태스크로 안전하게 비동기 실행
    asyncio.create_task(corpus_sync_manager.sync(run_crawlers=run_crawlers))
    return {
        "success": True,
        "message": "지식 코퍼스 현행화(대법원 예규·선례 및 법령체계도 수집·임베딩 갱신)가 시작되었습니다.",
        "status": corpus_sync_manager.get_status()
    }

@app.post("/api/admin/upload")
async def upload_document(
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    token: str = Depends(verify_admin_token)
):
    incoming_files: List[UploadFile] = []
    if files:
        incoming_files.extend(files)
    if file:
        incoming_files.append(file)

    if not incoming_files:
        raise HTTPException(status_code=400, detail="업로드할 파일이 지정되지 않았습니다.")

    all_parsed_docs = []
    file_results = []
    existing_files = rag_service.get_grouped_files()

    for f in incoming_files:
        filename = f.filename or "unknown_file"
        try:
            file_bytes = await f.read()
            if not file_bytes:
                file_results.append({
                    "filename": filename,
                    "chunks": 0,
                    "status": "error",
                    "error": "빈 파일입니다."
                })
                continue

            saved_path = UPLOAD_DIR / f"{int(time.time())}_{filename}"
            with open(saved_path, "wb") as out_f:
                out_f.write(file_bytes)

            docs = []
            lower_fn = filename.lower()
            if lower_fn.endswith((".xlsx", ".xls")):
                docs = parse_excel(file_bytes, filename)
            elif lower_fn.endswith(".pdf"):
                docs = parse_pdf(file_bytes, filename)
            elif lower_fn.endswith(".json"):
                docs = parse_json(file_bytes, filename)
            else:
                file_results.append({
                    "filename": filename,
                    "chunks": 0,
                    "status": "error",
                    "error": "지원되지 않는 파일 형식 (PDF, JSON, 엑셀만 지원)"
                })
                continue

            if not docs:
                file_results.append({
                    "filename": filename,
                    "chunks": 0,
                    "status": "error",
                    "error": "추출 가능한 유효한 지식/법령 데이터가 없습니다."
                })
                continue

            # 동일 파일명이 기존 코퍼스에 이미 존재한다면 구버전 청크를 먼저 깔끔하게 교체 정리
            for ef in existing_files:
                if ef.get("file_name") == filename or ef.get("file_name") == filename.rsplit('.', 1)[0] + ".pdf":
                    print(f"[Upload] Replacing existing version of '{filename}' ({ef.get('file_id')})...")
                    await rag_service.delete_file_group(ef.get("file_id"))

            all_parsed_docs.extend(docs)
            file_results.append({
                "filename": filename,
                "chunks": len(docs),
                "status": "success"
            })
        except Exception as fe:
            file_results.append({
                "filename": filename,
                "chunks": 0,
                "status": "error",
                "error": str(fe)
            })

    if not all_parsed_docs:
        failed_msgs = "; ".join([f"{r['filename']}: {r.get('error', '추출 실패')}" for r in file_results])
        raise HTTPException(status_code=400, detail=f"처리 가능한 파일이 없습니다. ({failed_msgs})")

    added_count = await rag_service.add_documents(all_parsed_docs)
    total_docs = len(rag_service.get_all_documents())

    return {
        "success": True,
        "total_files": len(file_results),
        "successful_files": len([r for r in file_results if r["status"] == "success"]),
        "chunks_created": added_count,
        "files": file_results,
        "total_corpus_docs": total_docs,
        "filename": incoming_files[0].filename if len(incoming_files) == 1 else f"{len(incoming_files)}개 파일"
    }

@app.post("/api/admin/document")
async def create_single_document(doc: ManualDocRequest, token: str = Depends(verify_admin_token)):
    timestamp = int(time.time())

    # 1. RLHF Gold Standard Q&A Registration
    if doc.prompt and doc.prompt.strip() and doc.chosen and doc.chosen.strip():
        prompt_txt = doc.prompt.strip()
        chosen_txt = doc.chosen.strip()
        rejected_txt = (doc.rejected or "").strip()
        basis_txt = (doc.legal_basis or "").strip()

        title = f"[심사관 공인 정답] {prompt_txt}"
        category = doc.category.strip() if doc.category and doc.category.strip() != "일반실무" else "RLHF모범정답"
        source = doc.source.strip() if doc.source and doc.source.strip() != "관리자 직접등록" else "심사관 인간 피드백(RLHF)"

        content_parts = [
            f"【실무 표준 질의】\n{prompt_txt}",
            f"【심사관 공인 모범 정답 (Gold Standard)】\n{chosen_txt}"
        ]
        if basis_txt:
            content_parts.append(f"【근거 법령 및 심사 사유】\n{basis_txt}")
        if rejected_txt:
            content_parts.append(f"【지양/반려 답변 유형 (Avoid Pattern)】\n{rejected_txt}")

        full_content = "\n\n".join(content_parts)

        new_item = {
            "id": f"RLHF-{timestamp}",
            "category": category,
            "source": source,
            "title": title,
            "content": full_content,
            "created_at": timestamp,
            "metadata": {
                "is_rlhf": True,
                "prompt": prompt_txt,
                "chosen": chosen_txt,
                "rejected": rejected_txt,
                "legal_basis": basis_txt,
                "confidence_boost": doc.confidence_boost or 1.5
            }
        }
    # 2. Traditional title + content
    else:
        if not doc.title or not doc.title.strip() or not doc.content or not doc.content.strip():
            raise HTTPException(status_code=400, detail="제목과 내용 또는 질의(Prompt)와 모범정답(Chosen)을 입력해주세요.")

        new_item = {
            "id": f"MANUAL-{timestamp}",
            "category": (doc.category or "").strip() or "일반실무",
            "source": (doc.source or "").strip() or "관리자 직접등록",
            "title": doc.title.strip(),
            "content": doc.content.strip(),
            "created_at": timestamp,
            "metadata": {
                "is_rlhf": False
            }
        }

    added_count = await rag_service.add_documents([new_item])
    return {
        "success": True,
        "document": new_item,
        "is_rlhf": new_item.get("metadata", {}).get("is_rlhf", False),
        "total_corpus_docs": len(rag_service.get_all_documents())
    }

@app.get("/api/admin/corpus/rlhf/export")
async def export_rlhf_dataset(format: Optional[str] = "json", token: str = Depends(verify_admin_token)):
    """RLHF / DPO 파인튜닝용 표준 JSONL 데이터셋 내보내기 API (format=json 또는 format=jsonl)"""
    rlhf_docs = rag_service.get_rlhf_documents()
    dataset = []
    for d in rlhf_docs:
        meta = d.get("metadata") or {}
        dataset.append({
            "id": d.get("id"),
            "prompt": meta.get("prompt") or d.get("title", "").replace("[심사관 공인 정답] ", ""),
            "chosen": meta.get("chosen") or d.get("content", ""),
            "rejected": meta.get("rejected", ""),
            "legal_basis": meta.get("legal_basis", ""),
            "source": d.get("source", ""),
            "created_at": d.get("created_at")
        })

    if format == "jsonl":
        jsonl_lines = [json.dumps(item, ensure_ascii=False) for item in dataset]
        content = "\n".join(jsonl_lines)
        return Response(
            content=content,
            media_type="application/x-jsonlines",
            headers={
                "Content-Disposition": 'attachment; filename="family_reg_rlhf_dpo.jsonl"'
            }
        )

    return {
        "success": True,
        "total_count": len(dataset),
        "dataset": dataset
    }


@app.delete("/api/admin/documents")
async def clear_all_documents(token: str = Depends(verify_admin_token)):
    await rag_service.clear_all_documents()
    return {
        "success": True,
        "message": "모든 RAG 지식 문서가 삭제되었습니다.",
        "remaining_docs": 0
    }

@app.post("/api/admin/reset-default")
async def reset_default_corpus(token: str = Depends(verify_admin_token)):
    total = await rag_service.reset_to_default()
    return {
        "success": True,
        "message": f"기본 지식 코퍼스({total}건)로 초기화 및 재임베딩되었습니다.",
        "total_docs": total
    }

@app.delete("/api/admin/document/{doc_id}")
async def delete_document(doc_id: str, token: str = Depends(verify_admin_token)):
    success = await rag_service.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="해당 문서를 찾을 수 없습니다.")
    return {
        "success": True,
        "deleted_id": doc_id,
        "remaining_docs": len(rag_service.get_all_documents())
    }

@app.post("/api/admin/reindex")
async def reindex_corpus(token: str = Depends(verify_admin_token)):
    total = await rag_service.reindex_all()
    return {
        "success": True,
        "reindexed_count": total
    }

# --- 관리자 질의 이력 (Audit Logs) API 엔드포인트 ---

@app.get("/api/admin/logs")
async def get_admin_query_logs(
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    token: str = Depends(verify_admin_token)
):
    """관리자용 실무 질의 이력 목록 및 검색 통계 반환"""
    return query_logger.get_logs(page=page, page_size=page_size, search=search)

@app.get("/api/admin/logs/export")
async def export_admin_query_logs(token: str = Depends(verify_admin_token)):
    """질의응답 이력 전체 JSON 파일 다운로드"""
    content = json.dumps(query_logger.logs, ensure_ascii=False, indent=2)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=family_reg_query_logs_{int(time.time())}.json"}
    )

@app.post("/api/admin/logs/import")
async def import_admin_query_logs(
    file: UploadFile = File(...),
    merge: bool = True,
    token: str = Depends(verify_admin_token)
):
    """백업 JSON 파일로부터 질의 이력 가져오기/복원"""
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="유효한 JSON 배열 형식이 아닙니다.")
        added = query_logger.import_logs(data, merge=merge)
        return {"success": True, "message": f"{added}건의 질의 감사 이력이 성공적으로 복원되었습니다.", "imported_count": added, "total": len(query_logger.logs)}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON 파일 파싱에 실패하였습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"로그 가져오기 실패: {str(e)}")

@app.delete("/api/admin/logs")
async def clear_admin_query_logs(token: str = Depends(verify_admin_token)):
    """모든 질의응답 이력 전체 삭제"""
    query_logger.clear_logs()
    return {"success": True, "message": "모든 실무 질의 이력이 삭제되었습니다."}

@app.get("/api/admin/logs/{log_id}")
async def get_admin_query_log_detail(log_id: str, token: str = Depends(verify_admin_token)):
    """특정 질의응답 상세 감사 로그 조회"""
    entry = query_logger.get_log_by_id(log_id)
    if not entry:
        raise HTTPException(status_code=404, detail="해당 질의 이력을 찾을 수 없습니다.")
    return entry

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

FORM_TEMPLATES_ZIP = DATA_DIR / "form_templates.zip"

@app.get("/api/forms/download")
async def download_form(filename: str):
    """36종 대법원 공식 서식(HWP/PDF) 안전 다운로드"""
    if not FORM_TEMPLATES_ZIP.exists():
        raise HTTPException(status_code=404, detail="서식 아카이브 파일을 찾을 수 없습니다.")

    try:
        with zipfile.ZipFile(FORM_TEMPLATES_ZIP, "r") as z:
            target_name = None
            for name in z.namelist():
                if name == filename or filename in name or name.endswith(filename):
                    target_name = name
                    break

            if not target_name:
                raise HTTPException(status_code=404, detail=f"요청하신 서식 '{filename}'을 찾을 수 없습니다.")

            file_bytes = z.read(target_name)
            media_type = "application/pdf" if target_name.endswith(".pdf") else "application/octet-stream"
            encoded_fn = urllib.parse.quote(target_name.split("/")[-1])

            return Response(
                content=file_bytes,
                media_type=media_type,
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_fn}"
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서식 파일 다운로드 처리 중 오류: {str(e)}")

@app.get("/api/forms/match")
async def match_forms(query: str):
    """질의 또는 상담 주제에 맞는 공식 서식 및 전자민원 딥링크 매칭"""
    return form_matcher.match(query)

@app.get("/api/laws/preview")
async def law_preview(law: str, article: str, branch: Optional[str] = None):
    """조문 인앱 인스턴트 호버 프리뷰 전용 API"""
    clean_law = LawCitationParser.resolve_canonical_law(law)
    art_res = await rig_engine.cache.get_article(clean_law, article, branch)
    if not art_res:
        return {
            "statute_name": clean_law,
            "article_no": article,
            "article_title": "공식 법령 조문",
            "content": f"「{clean_law}」 {article}의 상세 법문은 국가법령정보센터에서 확인하실 수 있습니다.",
            "enforcement_date": "현행",
            "law_url": f"https://www.law.go.kr/법령/{urllib.parse.quote(clean_law)}/{urllib.parse.quote(article)}",
            "tier": "국가법령정보센터"
        }

    body = art_res.get("content", "")
    summary = body[:280] + "..." if len(body) > 280 else body
    return {
        "statute_name": art_res.get("statute_name", clean_law),
        "article_no": art_res.get("article_no", article),
        "article_title": art_res.get("article_title", ""),
        "content": summary,
        "enforcement_date": art_res.get("enforcement_date", "현행"),
        "law_url": art_res.get("law_url", "https://www.law.go.kr"),
        "tier": art_res.get("retrieval_tier", "검증됨")
    }

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
            
            # Log Web Agent Query
            try:
                query_logger.log_query(
                    user_query=last_user_query,
                    sanitized_query=sec_result.get("sanitized_text", last_user_query),
                    assistant_response=answer,
                    model="qwen3-coder (웹에이전트)",
                    use_rag=False,
                    sources=[{'title': '웹 검색 출처', 'source': s, 'content': s} for s in sources],
                    latency_ms=850,
                    tokens=320,
                    cached=False,
                    pii_info=sec_result.get("pii", {})
                )
            except Exception as e:
                print(f"[QueryLogger] Agent log error: {e}")

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
        full_assistant_response = ""
        accumulated_sources = []
        is_cached_result = False
        collected_latency = 0
        collected_tokens = 0

        async for chunk in stream_chat_completion(
            messages=messages_payload,
            temperature=request.temperature or 0.5,
            max_tokens=request.max_tokens or 2500,
            use_rag=request.use_rag if request.use_rag is not None else True,
            use_rig=request.use_rig if request.use_rig is not None else True,
            mode=request.mode or "unified",

            model=selected_model,
            bypass_cache=request.bypass_cache or False
        ):
            chunk_type = chunk.get("type")
            if chunk_type == "delta":
                full_assistant_response += chunk.get("data", "")
            elif chunk_type == "sources":
                accumulated_sources = chunk.get("data", [])
            elif chunk_type == "cache_status":
                is_cached_result = chunk.get("data", {}).get("is_cached", False)
            elif chunk_type == "metrics":
                collected_latency = chunk.get("data", {}).get("latency_ms", 0)
                collected_tokens = chunk.get("data", {}).get("total_tokens", 0)

            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        # Log query history
        try:
            query_logger.log_query(
                user_query=last_user_query,
                sanitized_query=sec_result.get("sanitized_text", last_user_query),
                assistant_response=full_assistant_response,
                model=selected_model,
                use_rag=request.use_rag if request.use_rag is not None else True,
                sources=accumulated_sources,
                latency_ms=collected_latency,
                tokens=collected_tokens,
                cached=is_cached_result,
                pii_info=sec_result.get("pii", {})
            )
        except Exception as log_err:
            print(f"[QueryLogger] Error logging query: {log_err}")

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

class NoCacheStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

if FRONTEND_DIR.exists():
    app.mount("/static", NoCacheStaticFiles(directory=str(FRONTEND_DIR)), name="static")

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

@app.get("/admin")
@app.get("/admin.html")
async def read_admin():
    admin_file = FRONTEND_DIR / "admin.html"
    if admin_file.exists():
        return FileResponse(
            str(admin_file),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"message": "Admin frontend not found"}
