import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

DATA_DIR = Path(__file__).parent.parent / "data"
LOGS_FILE = DATA_DIR / "query_logs.json"

# 대한민국 표준시 (KST = UTC+9)
KST = timezone(timedelta(hours=9))

class QueryLogger:
    """
    가족관계등록 AI 실무 질의 이력 감사 및 분석 로거 (Query Audit Logger)
    - 당사자 질의, AI 실무 답변, 인용 법령 출처, 소요시간, 토큰 소비량, PII 감지 여부 기록
    - 한국표준시(KST) 기준 정확한 일시 및 통계 제공
    - 인메모리 + JSON 영속화 관리 (최대 5,000건 자동 유지)
    """
    def __init__(self, max_logs: int = 5000):
        self.max_logs = max_logs
        self.logs: List[Dict[str, Any]] = []
        self._load_logs()

    def _get_kst_now(self) -> datetime:
        return datetime.now(KST)

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
                self.logs = self.logs[:self.max_logs]
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
        """새 질의응답 이력 저장 (KST 한국 표준시 기준 정확한 일시 기록)"""
        now = self._get_kst_now()
        timestamp = now.timestamp()
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

    def get_stats_summary(self) -> Dict[str, Any]:
        """전체 질의 이력 기반 종합 통계 계산"""
        now_kst = self._get_kst_now()
        today_str = now_kst.strftime("%Y-%m-%d")
        total_logs = len(self.logs)

        today_logs = sum(1 for l in self.logs if l.get("date_str") == today_str)
        rag_count = sum(1 for l in self.logs if l.get("use_rag", False))
        cached_count = sum(1 for l in self.logs if l.get("cached", False))
        pii_count = sum(1 for l in self.logs if l.get("has_pii", False))
        total_tokens = sum(l.get("tokens", 0) for l in self.logs)

        total_latency = sum(l.get("latency_ms", 0) for l in self.logs)
        avg_latency_ms = round(total_latency / total_logs, 1) if total_logs > 0 else 0.0

        # Model breakdown
        model_counts: Dict[str, int] = {}
        for l in self.logs:
            m = l.get("model", "llama-3.3-70b")
            model_counts[m] = model_counts.get(m, 0) + 1

        # Estimated cost (approx. $0.0000008 per token)
        estimated_cost = round(total_tokens * 0.0000008, 4)

        return {
            "total_logs": total_logs,
            "today_logs": today_logs,
            "rag_count": rag_count,
            "rag_ratio_pct": round((rag_count / total_logs * 100), 1) if total_logs > 0 else 0.0,
            "cached_count": cached_count,
            "cached_ratio_pct": round((cached_count / total_logs * 100), 1) if total_logs > 0 else 0.0,
            "pii_detected_count": pii_count,
            "total_tokens": total_tokens,
            "avg_latency_ms": avg_latency_ms,
            "avg_latency_sec": round(avg_latency_ms / 1000, 2),
            "estimated_cost_usd": f"${estimated_cost:.4f}",
            "model_breakdown": model_counts,
            "server_time_kst": now_kst.strftime("%Y-%m-%d %H:%M:%S")
        }

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

        return {
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total_count + page_size - 1) // page_size),
            "logs": paginated,
            "stats": self.get_stats_summary()
        }

    def get_log_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        for l in self.logs:
            if l.get("id") == log_id:
                return l
        return None

    def clear_logs(self):
        self.logs = []
        self._save_logs()

    def import_logs(self, imported_entries: List[Dict[str, Any]], merge: bool = True) -> int:
        """외부 백업 JSON 파일로부터 이력 불러오기 (기존 이력과 병합 또는 교체)"""
        if not isinstance(imported_entries, list):
            return 0
        existing_ids = {l.get("id") for l in self.logs if "id" in l}
        added_count = 0
        if not merge:
            self.logs = []
            existing_ids = set()
        
        for item in imported_entries:
            if isinstance(item, dict):
                item_id = item.get("id")
                if item_id and item_id in existing_ids:
                    continue
                self.logs.append(item)
                added_count += 1
                if item_id:
                    existing_ids.add(item_id)
        
        # Sort by timestamp descending
        self.logs.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[:self.max_logs]
        self._save_logs()
        return added_count

query_logger = QueryLogger()
