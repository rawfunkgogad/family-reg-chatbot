import time
from typing import Dict, Any, List

class MetricsCollector:
    """
    요청별 지연시간(Latency), 토큰 소비량(Prompt/Completion/Total), 모델별 효율성 수집기
    """
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.history: List[Dict[str, Any]] = []
        self.model_stats: Dict[str, Dict[str, Any]] = {
            "llama-3.3-70b": {"requests": 0, "total_tokens": 0, "total_latency_ms": 0},
            "gpt-oss-120b": {"requests": 0, "total_tokens": 0, "total_latency_ms": 0}
        }

    def record_request(
        self,
        model: str,
        mode: str,
        latency_ms: int,
        prompt_tokens: int,
        completion_tokens: int,
        cached: bool = False
    ):
        total_tokens = prompt_tokens + completion_tokens
        entry = {
            "timestamp": time.time(),
            "model": model,
            "mode": mode,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached": cached
        }
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        if model not in self.model_stats:
            self.model_stats[model] = {"requests": 0, "total_tokens": 0, "total_latency_ms": 0}

        self.model_stats[model]["requests"] += 1
        self.model_stats[model]["total_tokens"] += total_tokens
        self.model_stats[model]["total_latency_ms"] += latency_ms

    def get_summary(self) -> Dict[str, Any]:
        total_reqs = len(self.history)
        if total_reqs == 0:
            return {
                "total_requests": 0,
                "avg_latency_ms": 0,
                "total_tokens_consumed": 0,
                "model_breakdown": self.model_stats
            }

        avg_lat = sum(h["latency_ms"] for h in self.history) / total_reqs
        total_tok = sum(h["total_tokens"] for h in self.history)

        return {
            "total_requests": total_reqs,
            "avg_latency_ms": round(avg_lat, 1),
            "total_tokens_consumed": total_tok,
            "recent_latency_ms": self.history[-1]["latency_ms"] if self.history else 0,
            "model_breakdown": {
                m: {
                    "requests": s["requests"],
                    "total_tokens": s["total_tokens"],
                    "avg_latency_ms": round(s["total_latency_ms"] / s["requests"], 1) if s["requests"] > 0 else 0
                }
                for m, s in self.model_stats.items()
            }
        }

metrics_collector = MetricsCollector()
