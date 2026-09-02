import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

DATA_DIR = Path(__file__).parent.parent / "data"
LOGS_FILE = DATA_DIR / "query_logs.json"

class QueryLogger:
    """
    가족관계등록 AI 실무 질의 이력 감사 및 분석 로거 (Query Audit Logger)
    - 당사자 질의, AI 실무 답변, 인용 법령 출처, 소요시간, 토큰 소비량, PII 감지 여부 기록
    - 인메모리 + JSON 영속화 관리 (최대 5,000건 자동 유지)
    """
    def __init__(self, max_logs: int = 5000):
        self.max_logs = max_logs
        self.logs: List[Dict[str, Any]] = []
        self._load_logs()

    def _load_logs(self):
        if LOGS_FILE.exists():
            try:
                with open(LOGS_FILE, "r", encoding="utf-8") as f:
                    self.logs = json.load(f)
            except Exception as e:
                print(f"[QueryLogger] Failed to load existing logs: {e}")
                self.logs = []
        else:
            self.logs = []

    def _save_logs(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            # Maintain max_logs limit (keep latest)
            if len(self.logs) > self.max_logs:
                self.logs = self.logs[-self.max_logs:]
            with open(LOGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.logs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[QueryLogger] Failed to save logs: {e}")

    def log_query(
        self,
        user_query: str,
        sanitized_query: str,
        assistant_response: str,
        model: str,
        use_rag: bool,
        sources: Optional[List[Dict[str, Any]]] = None,
        latency_ms: int = 0,
        tokens: int = 0,
        cached: bool = False,
        pii_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """새 질의응답 이력 저장"""
        now = datetime.now()
        timestamp = time.time()
        log_id = f"LOG-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

        has_pii = False
        pii_types = []
        if pii_info:
            has_pii = pii_info.get("has_pii", False)
            pii_types = pii_info.get("detected_types", [])

        # Clean source summary
        source_summaries = []
        if sources:
            for s in sources:
                if isinstance(s, dict):
                    source_summaries.append({
                        "id": s.get("id", ""),
                        "category": s.get("category", "법령/선례"),
                        "title": s.get("title", ""),
                        "source": s.get("source", ""),
                        "preview": s.get("content", "")[:120] if s.get("content") else ""
                    })

        entry = {
            "id": log_id,
            "timestamp": timestamp,
            "datetime_str": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date_str": now.strftime("%Y-%m-%d"),
            "user_query": sanitized_query or user_query,
            "raw_user_query_masked": sanitized_query != user_query,
            "assistant_response": assistant_response,
            "response_preview": assistant_response[:150] + "..." if len(assistant_response) > 150 else assistant_response,
            "model": model,
            "use_rag": use_rag,
            "sources_count": len(source_summaries),
            "sources": source_summaries,
            "latency_ms": latency_ms,
            "tokens": tokens,
            "cached": cached,
            "has_pii": has_pii,
            "pii_types": pii_types
        }

        # Prepend so newest is first
        self.logs.insert(0, entry)
        self._save_logs()
        return entry

    def get_logs(self, page: int = 1, page_size: int = 20, search: str = "") -> Dict[str, Any]:
        """필터링 및 페이지네이션된 질의 이력 목록 및 통계 반환"""
        filtered = self.logs
        if search:
            kw = search.strip().lower()
            filtered = [
                l for l in self.logs
                if kw in l.get("user_query", "").lower()
                or kw in l.get("assistant_response", "").lower()
                or any(kw in s.get("title", "").lower() or kw in s.get("source", "").lower() for s in l.get("sources", []))
            ]

        total_count = len(filtered)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated = filtered[start_idx:end_idx]

        # Summary statistics
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_count = sum(1 for l in self.logs if l.get("date_str") == today_str)
        rag_count = sum(1 for l in self.logs if l.get("use_rag", False))
        pii_count = sum(1 for l in self.logs if l.get("has_pii", False))
        cached_count = sum(1 for l in self.logs if l.get("cached", False))

        return {
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total_count + page_size - 1) // page_size),
            "logs": paginated,
            "stats": {
                "total_logs": len(self.logs),
                "today_logs": today_count,
                "rag_ratio_pct": round((rag_count / len(self.logs) * 100), 1) if self.logs else 0.0,
                "cached_ratio_pct": round((cached_count / len(self.logs) * 100), 1) if self.logs else 0.0,
                "pii_detected_count": pii_count
            }
        }

    def get_log_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        for l in self.logs:
            if l.get("id") == log_id:
                return l
        return None

    def clear_logs(self):
        self.logs = []
        self._save_logs()

query_logger = QueryLogger()
